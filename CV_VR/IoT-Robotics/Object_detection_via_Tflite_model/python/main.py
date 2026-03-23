"""
#===--YOLOX (TFLite) Object Detection Streaming Demo-----------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

What this app does:
1) Capture frames from a USB camera
2) Run YOLOX inference via a TFLite model
3) Post-process detections (score threshold, NMS, Top-K)
4) Draw results on the image and expose a REST endpoint that
   returns the latest JPEG (base64)

Notes:
- You can override model and labels via environment variables:
    APP_MODEL, APP_LABELS
- You can tune runtime & quality via:
    APP_THREADS, APP_JPEG_QUALITY, APP_LOOP_SLEEP
    APP_SCORE_TH, APP_IOU_TH, APP_TOPK
"""
import io, os, time, base64
from typing import Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import threading

# TFLite runtime (Edge AI)
from ai_edge_litert.interpreter import Interpreter

# Arduino app framework, Web UI, and USB camera wrapper
from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI
from arduino.app_peripherals.usb_camera import USBCamera

# =========================
# Settings
# =========================
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Model & label paths (can be overridden by env)
MODEL_PATH  = os.environ.get("APP_MODEL",  os.path.join(APP_DIR, "./yolox-yolo-x-float.tflite"))
LABELS_PATH = os.environ.get("APP_LABELS", os.path.join(APP_DIR, "./coco_labels.txt"))

# Runtime & performance
NUM_THREADS   = int(os.environ.get("APP_THREADS", "4"))
JPEG_QUALITY  = int(os.environ.get("APP_JPEG_QUALITY", "80"))
LOOP_SLEEP    = float(os.environ.get("APP_LOOP_SLEEP", "0.03"))

# Post-processing
SCORE_TH = float(os.environ.get("APP_SCORE_TH", "0.25"))
IOU_TH   = float(os.environ.get("APP_IOU_TH",   "0.45"))
TOPK     = int(os.environ.get("APP_TOPK",      "20"))

# Rendering
TEXT_PX = 16
TEXT_WIDTH_PER_PX = 0.5  # approx text width ≈ 0.5 * px * len(text)
TEXT_HEIGHT_SCALE = 1.2  # approx text height ≈ 1.2 * px

# =========================
# Utility functions
# =========================

def load_labels(path: str):
    """
    Load labels (one class name per line). If the file doesn't exist,
    returns None so we can fall back to class indices.
    """    
    try:
        with open(path, "r", encoding="utf-8") as f:
            labels = [line.strip() for line in f if line.strip()]
        print(f"[INFO] Loaded {len(labels)} labels from {path}")
        return labels
    except Exception:
        print(f"[WARN] labels file not found: {path} (use class index)")
        return None


def letterbox_resize(img: Image.Image, size_hw: Tuple[int, int], pad_val: int = 114):
    """
    Resize with letterboxing to target size (H, W) while preserving aspect ratio.
    The image is centered on a padded canvas.

    Returns:
      - canvas: resized RGB PIL image of size (W, H)
      - (scale, pad_w, pad_h): scale factor and total padding in width/height
    """
    H, W = size_hw
    img = img.convert("RGB")
    w, h = img.size
    
    # Uniform scale to fit within target (W,H)
    scale = min(W / w, H / h)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = img.resize((new_w, new_h), Image.BILINEAR)
    
    # Paste onto centered canvas
    canvas = Image.new("RGB", (W, H), (pad_val, pad_val, pad_val))
    pad_left = (W - new_w) // 2
    pad_top  = (H - new_h) // 2
    canvas.paste(resized, (pad_left, pad_top))
    pad_w = W - new_w
    pad_h = H - new_h
    return canvas, (scale, pad_w, pad_h)


def preprocess_input(img: Image.Image, size_hw: Tuple[int, int], expect_dtype):
    """
    Preprocess pipeline:
      1) Letterbox to model input size
      2) Normalize for float models (or keep uint8 as-is)
      3) Add batch dim -> [1, H, W, 3]

    Returns:
      - input array
      - meta dict for reversing letterbox (used in post-processing)
    """
    H, W = size_hw
    img_resized, (scale, pad_w, pad_h) = letterbox_resize(img, (H, W))

    if expect_dtype == np.float32:
        arr = np.asarray(img_resized, dtype=np.float32) / 255.0
    else:
        arr = np.asarray(img_resized, dtype=np.uint8)

    arr = np.expand_dims(arr, axis=0)  # [1,H,W,3]
    meta = {
        "orig_size": (img.size[1], img.size[0]),  # (H0, W0)
        "input_size": (H, W),
        "scale": scale, "pad_w": pad_w, "pad_h": pad_h, "add_batch": True
    }
    return arr, meta


def unletterbox_boxes(boxes: np.ndarray, meta: dict):
    """
    Convert boxes from letterboxed input coordinates back to original image
    coordinates. Assumes boxes in xyxy format.
    """
    H_in, W_in = meta["input_size"]
    H0, W0 = meta["orig_size"]
    scale = meta["scale"]
    pad_w = meta["pad_w"]
    pad_h = meta["pad_h"]
    pad_left = pad_w / 2.0
    pad_top  = pad_h / 2.0
    boxes = boxes.copy().astype(np.float32)
    
    # Remove letterbox offsets
    boxes[:, [0, 2]] -= pad_left
    boxes[:, [1, 3]] -= pad_top
    
    # Reverse scaling
    boxes /= max(scale, 1e-6)
    
    # Clip to image bounds
    boxes[:, 0] = np.clip(boxes[:, 0], 0, W0 - 1)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, H0 - 1)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, W0 - 1)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, H0 - 1)
    return boxes


def iou_xyxy(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Pairwise IoU for two sets of xyxy boxes.
    Returns an array of shape [len(a), len(b)].
    """
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(br - tl, 0, None)
    inter = wh[..., 0] * wh[..., 1]
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    union = area_a[:, None] + area_b[None, :] - inter
    return inter / np.clip(union, 1e-6, None)


def nms_fast(boxes: np.ndarray, scores: np.ndarray, iou_th: float) -> np.ndarray:
    """
    Simple NMS:
      - Sort by score (desc)
      - Iteratively keep the highest and drop those with IoU > threshold
    Returns indices to keep.
    """
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        ious = iou_xyxy(boxes[i:i+1], boxes[order[1:]])[0]
        remain = np.where(ious <= iou_th)[0]
        order = order[remain + 1]
    return np.array(keep, dtype=np.int32)


def postprocess_yolox(boxes: np.ndarray, scores: np.ndarray, classes: np.ndarray, meta: dict, score_th: float, iou_th: float, topk: int):
    """
    YOLOX post-processing:
      1) Un-letterbox coordinates back to original image
      2) Score thresholding
      3) NMS
      4) Keep top-K by score

    Returns: boxes_pp, scores_pp, classes_pp, order_idx
    """                          
    boxes = unletterbox_boxes(boxes, meta)
    
     # Score filter
    mask = scores >= float(score_th)
    boxes, scores, classes = boxes[mask], scores[mask], classes[mask]
    if boxes.shape[0] == 0:
        return boxes, scores, classes, np.array([], dtype=np.int32)
    
     # NMS
    keep = nms_fast(boxes, scores, iou_th)
    boxes, scores, classes = boxes[keep], scores[keep], classes[keep]
    
    # Top-K
    order = scores.argsort()[::-1][:min(topk, scores.size)]
    return boxes[order], scores[order], classes[order], order


def _make_color(cls_id: int) -> tuple:
    """
    Generate a visually distinct RGB color from a class id (simple HSV ramp).
    """
    h = (cls_id * 37) % 360
    s = 0.9; v = 0.9
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def estimate_text_size(text: str, px: int = TEXT_PX) -> tuple[int, int]:
    """
    Estimate text box size without font metrics.
    Returns (estimated_width, estimated_height).
    """
    w = max(10, int(TEXT_WIDTH_PER_PX * px * len(text)))
    h = max(10, int(TEXT_HEIGHT_SCALE * px))
    return w, h


def render_on_pil(pil_img: Image.Image, boxes: np.ndarray, scores: np.ndarray, classes: np.ndarray, labels):
    """
    Draw detection results on the image:
      - rectangle, class name, and confidence
    """    
    img = pil_img.convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    
    W0, H0 = img.size
    for i in range(boxes.shape[0]):
        x1, y1, x2, y2 = boxes[i].tolist()
        cls_id = int(classes[i]); score = float(scores[i])
        name = labels[cls_id] if (labels and cls_id < len(labels)) else f"class_{cls_id}"
        color = _make_color(cls_id)
        draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=2)  # Bounding box
        
        # Text background + text
        text = f"{name} {score:.2f}" 
        tw, th = estimate_text_size(text, px=TEXT_PX)
        y0 = max(0, y1 - th - 2) 
        x2_text = min(W0 - 1, x1 + tw + 4)
        draw.rectangle([(x1, y0), (x2_text, y0 + th + 2)], fill=color) # Text background
        draw.text((x1 + 2, y0 + 1), text, fill=(0, 0, 0), font=font)
    return img

# =========================
# Inference main flow
# =========================
# Load labels
_labels = load_labels(LABELS_PATH)

# Create TFLite interpreter and prepare I/O
_interpreter = Interpreter(model_path=MODEL_PATH, num_threads=NUM_THREADS)
_interpreter.allocate_tensors()
_input_details  = _interpreter.get_input_details()
_output_details = _interpreter.get_output_details()

# Input tensor info
in_idx   = _input_details[0]["index"]
in_shape = tuple(_input_details[0]["shape"])  # [N,H,W,C]
in_dtype = _input_details[0]['dtype']

print(f"[INFO] Model: {MODEL_PATH}")
print(f"[INFO] Input shape={in_shape}, dtype={in_dtype}, quant={_input_details[0].get('quantization',(0.0,0))}")

# Latest JPEG cache (served by REST)
latest_jpeg = b""
latest_ts = 0
#timestep
_latest_lock = threading.Lock()
#_cam_started = False

def encode_jpeg(pil_img, quality: int = JPEG_QUALITY) -> bytes:
    """
    Encode a PIL image to JPEG bytes
    """
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

def run_yolox_on_frame(pil_img: Image.Image):
    """
    Run YOLOX inference on a single image, returning:
      - composed: PIL image with drawn detections
      - boxes_pp, scores_pp, classes_pp: post-processed arrays
    """
    # preprocess
    input_tensor, meta = preprocess_input(pil_img, (in_shape[1], in_shape[2]), expect_dtype=in_dtype)
    
    # Inference
    _interpreter.set_tensor(in_idx, input_tensor)
    _interpreter.invoke()

    # Locate output tensors by name
    idx_boxes = idx_scores = idx_classes = None
    for i, d in enumerate(_output_details):
        name = (d.get('name') or '').lower()
        if 'box' in name:
            idx_boxes = i
        elif 'score' in name:
            idx_scores = i
        elif 'class' in name:
            idx_classes = i

    # If any output is missing, return original image and empty results safely
    if None in (idx_boxes, idx_scores, idx_classes):
        return pil_img, np.empty((0, 4)), np.empty((0,), np.float32), np.empty((0,), np.int32)

    # Read outputs and normalize dtypes
    boxes = np.squeeze(_interpreter.get_tensor(_output_details[idx_boxes]['index']))
    scores = np.squeeze(_interpreter.get_tensor(_output_details[idx_scores]['index']))
    classes = np.squeeze(_interpreter.get_tensor(_output_details[idx_classes]['index']))

    # No dequant: use float directly; cast classes to int
    if boxes.dtype != np.float32:
        boxes = boxes.astype(np.float32)
    if scores.dtype != np.float32:
        scores = scores.astype(np.float32)
    if np.issubdtype(classes.dtype, np.floating):
        classes = np.rint(classes).astype(np.int32)
    else:
        classes = classes.astype(np.int32)

    # Post-process (un-letterbox, filter, NMS, top-K)
    boxes_pp, scores_pp, classes_pp, _ = postprocess_yolox(
        boxes, scores, classes, meta, score_th=SCORE_TH, iou_th=IOU_TH, topk=TOPK
    )

    # Draw results
    composed = render_on_pil(pil_img, boxes_pp, scores_pp, classes_pp, _labels)
    return composed, boxes_pp, scores_pp, classes_pp

# =========================
# REST API: get latest JPEG
# =========================
def get_latest_frame():
    """
    WebUI endpoint: return the latest JPEG as a base64 string and a timestamp.
    """
    with _latest_lock:
        payload = latest_jpeg
        ts_local = latest_ts

    if not payload:
        # 首次或目前還沒有可用影格
        return {
            "mime": "image/jpeg",
            "payload_b64": "",
            "ts": 0,
            "status": "no_frame_yet"
        }

    return {
        "mime": "image/jpeg",
        "payload_b64": base64.b64encode(latest_jpeg).decode("ascii"),
        "ts": ts_local,
    }

# =========================
# Main loop
# =========================
def user_loop():
    """
    Main capture & inference loop:
      - Start camera on first run
      - Capture a frame, run inference, draw results
      - Encode to JPEG and cache it
    """    
    global latest_jpeg, _cam_started, latest_ts
    
    # Start camera
    # if not _cam_started:
        # cam.start()
        # _cam_started = True
    
    # Capture a frame
    frame = cam.capture()  
    
    # run inference and draw results
    composed, boxes_pp, scores_pp, classes_pp = run_yolox_on_frame(frame)
    
    # Encode to JPEG
    jpeg_bytes = encode_jpeg(composed, quality=JPEG_QUALITY)
    with _latest_lock:
        latest_jpeg = jpeg_bytes
        latest_ts = int(time.time() * 1000)

    time.sleep(LOOP_SLEEP)

# Start the app
print("[INFO] YOLOX stream starting …")
try:
    # Web UI and USB camera
    ui = WebUI()
    cam = USBCamera( )
    
    # Expose GET /frame/latest
    ui.expose_api("GET", "/frame/latest", get_latest_frame)
    
    cam.start()
    App.run(user_loop=user_loop)
finally:
    cam.stop()
