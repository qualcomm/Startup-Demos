#===--facial_emotion_detection_inference.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, math, argparse, threading
import numpy as np
import cv2

# --------- GStreamer ----------
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# --------- MediaPipe (primary detector) ----------
import mediapipe as mp

# --------- TFLite Runtime ----------
from tflite_runtime.interpreter import Interpreter, load_delegate

# ------------------- INIT -------------------
Gst.init(None)
os.environ.setdefault("QNN_LOG_LEVEL", "ERROR")
cv2.setNumThreads(1)

EMOTION_LABELS = ['Neutral','Happy','Sad','Surprise','Fear','Disgust','Anger']
BGR_MEAN = np.array([91.4953, 103.8827, 131.0912], dtype=np.float32)

# Guards to prevent “whole‑frame” or nonsense boxes
MAX_AREA_FRAC = 0.85
MAX_SIDE_FRAC = 0.95
MIN_SIDE      = 24

# ------------------- PIPELINES ---------------
def build_gst_pipeline(width=640, height=480, fps=30, src="qti", device="/dev/video0"):
    """
    src='qti'  -> RB3 main camera via qtiqmmfsrc
    src='v4l2' -> /dev/videoX via v4l2src
    """
    if src == "qti":
        return (
            "qtiqmmfsrc name=cam0 ! "
            f"video/x-raw,format=NV12,width={width},height={height},framerate={fps}/1 ! "
            "videoconvert n-threads=2 ! video/x-raw,format=RGB ! "
            "queue leaky=2 max-size-buffers=2 ! "
            "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
        )
    else:  # v4l2
        return (
            f"v4l2src device={device} ! "
            f"video/x-raw,format=YUY2,width={width},height={height},framerate={fps}/1 ! "
            "videoconvert n-threads=2 ! video/x-raw,format=RGB ! "
            "queue leaky=2 max-size-buffers=2 ! "
            "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
        )

def gst_sample_to_numpy(sample):
    """Convert appsink sample -> RGB numpy frame."""
    buf = sample.get_buffer()
    caps = sample.get_caps()
    s = caps.get_structure(0)
    width = s.get_value('width')
    height = s.get_value('height')
    ok, mapinfo = buf.map(Gst.MapFlags.READ)
    if not ok:
        return None
    try:
        arr = np.frombuffer(mapinfo.data, dtype=np.uint8)
        frame = arr.reshape((height, width, 3)).copy()  # writable RGB
        return frame
    finally:
        buf.unmap(mapinfo)

# ------------------- MODEL -------------------
def load_tflite(model_path: str, backend="htp", num_threads=2):
    delegates = []
    if backend.lower() == "htp":
        try:
            delegates.append(load_delegate(
                "libQnnTFLiteDelegate.so", options={"backend_type": "htp"}
            ))
            print("[INFO] QNN Delegate loaded (HTP)")
        except Exception as e:
            print(f"[WARN] QNN delegate load failed, CPU fallback: {e}")
    interpreter = Interpreter(
        model_path=model_path,
        experimental_delegates=delegates if delegates else None,
        num_threads=num_threads
    )
    interpreter.allocate_tensors()
    in_info  = interpreter.get_input_details()[0]
    out_info = interpreter.get_output_details()[0]
    print(f"[TFLite] Input:  shape={in_info['shape']} dtype={in_info['dtype']} quant={in_info['quantization']}")
    print(f"[TFLite] Output: shape={out_info['shape']} dtype={out_info['dtype']} quant={out_info['quantization']}")
    return interpreter

# ---------------- PREPROCESS & MATH ----------
def preprocess_caffe_bgr_from_bgr(bgr, size=(224,224)):
    """
    Input: BGR crop (numpy), Output: (1,3,224,224) float32 with Caffe BGR mean subtract.
    Fast: pure OpenCV (no PIL).
    """
    bgr_resized = cv2.resize(bgr, size, interpolation=cv2.INTER_LINEAR).astype(np.float32)
    bgr_resized -= BGR_MEAN
    # HWC -> CHW
    x = np.transpose(bgr_resized, (2,0,1))
    return np.expand_dims(x, 0)  # (1,3,224,224)

def softmax(z):
    z = z - np.max(z, axis=1, keepdims=True)
    e = np.exp(z)
    return e / np.sum(e, axis=1, keepdims=True)

# -------------- INT8-safe I/O ----------------
def set_input_int8_safe(interpreter, real_tensor):
    in_info = interpreter.get_input_details()[0]
    in_idx  = in_info['index']
    in_shape = tuple(in_info['shape'])
    in_dtype = in_info['dtype']
    in_scale, in_zp = in_info['quantization']

    tensor = real_tensor.astype(np.float32)

    # TFLite commonly expects NHWC
    if len(in_shape) == 4:
        if in_shape[-1] == 3 and tensor.shape == (1,3,224,224):
            tensor = np.transpose(tensor, (0,2,3,1))  # NCHW -> NHWC

    if in_dtype in (np.int8, np.uint8):
        if in_scale == 0.0:
            print("[WARN] Input scale 0.0; using 1.0.")
            in_scale = 1.0
        q = np.round(tensor / in_scale + in_zp)
        q = np.clip(q, np.iinfo(in_dtype).min, np.iinfo(in_dtype).max).astype(in_dtype)
        interpreter.set_tensor(in_idx, q)
    else:
        interpreter.set_tensor(in_idx, tensor.astype(in_dtype))

def get_output_dequantized_logits(interpreter):
    out_info = interpreter.get_output_details()[0]
    out_idx  = out_info['index']
    out = interpreter.get_tensor(out_idx)
    if out_info['dtype'] in (np.int8, np.uint8):
        out_scale, out_zp = out_info['quantization']
        if out_scale == 0.0:
            print("[WARN] Output scale 0.0; returning float copy.")
            return out.astype(np.float32)
        return out_scale * (out.astype(np.float32) - out_zp)
    return out.astype(np.float32)

# -------------- FACE DETECTION ---------------
haar = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def _to_abs_bbox(det, W, H):
    rb = det.location_data.relative_bounding_box
    x0 = int(rb.xmin * W); y0 = int(rb.ymin * H)
    x1 = int((rb.xmin + rb.width) * W)
    y1 = int((rb.ymin + rb.height) * H)
    x0 = max(0, min(W-1, x0)); y0 = max(0, min(H-1, y0))
    x1 = max(0, min(W-1, x1)); y1 = max(0, min(H-1, y1))
    if x1 < x0: x0, x1 = x1, x0
    if y1 < y0: y0, y1 = y1, y0
    return x0, y0, x1, y1

def _valid_guard(x0, y0, x1, y1, W, H):
    w = max(0, x1-x0); h = max(0, y1-y0)
    if w < MIN_SIDE or h < MIN_SIDE:
        return False
    area_frac = (w*h) / float(W*H + 1e-6)
    if area_frac > MAX_AREA_FRAC:
        return False
    if w > MAX_SIDE_FRAC*W or h > MAX_SIDE_FRAC*H:
        return False
    return True

def detect_boxes(rgb, mp_fd):
    """Return all valid face boxes from MediaPipe (else Haar), sorted by area desc."""
    H, W = rgb.shape[:2]
    res = mp_fd.process(rgb)
    boxes = []
    if res and res.detections:
        for d in res.detections:
            x0,y0,x1,y1 = _to_abs_bbox(d, W, H)
            if _valid_guard(x0,y0,x1,y1,W,H):
                boxes.append((x0,y0,x1,y1))
    if boxes:
        boxes.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
        return boxes

    # Fallback Haar: may return multiple faces
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    faces = haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(MIN_SIDE,MIN_SIDE))
    boxes = []
    for (x, y, w, h) in faces:
        box = (x, y, x + w, y + h)
        if _valid_guard(box[0], box[1], box[2], box[3], W, H):
            boxes.append(box)
    boxes.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
    return boxes if boxes else None

def detect_boxes_fast(rgb_full, det_scale, mp_fd):
    """Downscale for speed, detect multiple boxes, then scale them back to full size."""
    H, W = rgb_full.shape[:2]
    if det_scale <= 0.0 or det_scale >= 1.0:
        return detect_boxes(rgb_full, mp_fd)

    dW = max(64, int(W * det_scale))
    dH = max(48, int(H * det_scale))
    rgb_small = cv2.resize(rgb_full, (dW, dH), interpolation=cv2.INTER_AREA)

    boxes_small = detect_boxes(rgb_small, mp_fd)
    if boxes_small is None:
        return None

    sx = W / float(dW); sy = H / float(dH)
    boxes = []
    for (x0, y0, x1, y1) in boxes_small:
        X0 = int(round(x0 * sx)); Y0 = int(round(y0 * sy))
        X1 = int(round(x1 * sx)); Y1 = int(round(y1 * sy))
        X0 = max(0, min(W-1, X0)); Y0 = max(0, min(H-1, Y0))
        X1 = max(0, min(W-1, X1)); Y1 = max(0, min(H-1, Y1))
        if X1 > X0 and Y1 > Y0:
            boxes.append((X0, Y0, X1, Y1))
    return boxes if boxes else None

def square_expand(x0, y0, x1, y1, W, H, scale=1.25):
    """
    Expand a rectangular box to a centered square with configurable scale,
    clamped to image bounds. Returns (nx0, ny0, nx1, ny1).
    """
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    s  = int(math.ceil(scale * max(w, h)))
    half = s // 2
    nx0 = int(round(cx - half)); ny0 = int(round(cy - half))
    nx1 = nx0 + s;                ny1 = ny0 + s
    nx0 = max(0, nx0); ny0 = max(0, ny0)
    nx1 = min(W - 1, nx1); ny1 = min(H - 1, ny1)
    if nx1 <= nx0 or ny1 <= ny0:
        return x0, y0, x1, y1
    return nx0, ny0, nx1, ny1

# -------------- DRAW & OVERLAY ----------------
def draw_result(bgr, box, label, conf, fps_val=None, latency_ms=None):

    # Small, clean font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.55   # smaller text to avoid overlap
    thickness = 1       # thinner stroke
    text_color = (0, 220, 0)  # clean green
    box_color  = (255, 0, 255)
    margin = 6          # spacing around box/text

    if box is not None:
        x0, y0, x1, y1 = box
        cv2.rectangle(bgr, (x0, y0), (x1, y1), box_color, 2)

        if label is not None:
            # Compact text: integer percentage for smaller width
            text = f"{label} ({conf*100:.0f}%)"
            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

            # Prefer text slightly above the box
            text_x = x0
            text_y = y0 - margin

            # If above is out of frame, place inside top-left of box
            if text_y - th < 0:
                text_y = y0 + th + margin

            # Subtle background for legibility
            bg_x0 = max(0, text_x - 2)
            bg_y0 = max(0, text_y - th - 2)
            bg_x1 = min(bgr.shape[1]-1, text_x + tw + 2)
            bg_y1 = min(bgr.shape[0]-1, text_y + baseline + 2)
            cv2.rectangle(bgr, (bg_x0, bg_y0), (bg_x1, bg_y1), (0, 0, 0), -1)

            cv2.putText(bgr, text, (text_x, text_y), font, font_scale, text_color, thickness, lineType=cv2.LINE_AA)

    if latency_ms is not None:
        lat_text = f"Infer: {latency_ms:.1f} ms"
        (ltw, lth), baseline = cv2.getTextSize(lat_text, font, 0.55, 1)
        lx = 10
        ly = 20 + lth
        cv2.rectangle(bgr, (lx - 2, ly - lth - 2), (lx + ltw + 2, ly + baseline + 2), (0, 0, 0), -1)
        cv2.putText(bgr, lat_text, (lx, ly), font, 0.55, (255, 255, 0), 1, lineType=cv2.LINE_AA)

    return bgr

# ---------------- PING–PONG BUFFER ------------
class PingPongBuffer:
    """Double buffer with two slots. Capture writes alternately; processing reads the latest ready slot."""
    def __init__(self):
        self.frames = [None, None]
        self.seq    = [-1, -1]
        self.ready  = [threading.Event(), threading.Event()]
        self.lock   = threading.Lock()
        self.write_idx = 0
        self.read_idx  = 1
        self.global_seq = 0
        self.ready[0].clear(); self.ready[1].clear()

    def write(self, frame):
        with self.lock:
            idx = self.write_idx
            self.frames[idx] = frame
            self.global_seq += 1
            self.seq[idx] = self.global_seq
            self.ready[idx].set()                    # mark this slot ready
            # swap indices for next write
            self.write_idx, self.read_idx = self.read_idx, self.write_idx
            # clear flag on the next write slot (will be overwritten soon)
            self.ready[self.write_idx].clear()

    def read_latest(self, timeout_ms=500):
        # Wait until at least one slot is ready
        waited = 0
        step = 5
        while waited < timeout_ms:
            r0 = self.ready[0].is_set()
            r1 = self.ready[1].is_set()
            if r0 or r1:
                break
            time.sleep(step/1000.0)
            waited += step

        # Pick the slot with the highest seq (latest frame)
        with self.lock:
            idx = None
            if self.ready[0].is_set() and self.ready[1].is_set():
                idx = 0 if self.seq[0] >= self.seq[1] else 1
            elif self.ready[0].is_set():
                idx = 0
            elif self.ready[1].is_set():
                idx = 1
            else:
                return None

            frame = self.frames[idx]
            # Mark consumed so the next read gets the newer frame
            self.ready[idx].clear()
            return frame

# ------------------- CAPTURE THREAD ----------
def camera_thread(pipeline_str, pingpong: PingPongBuffer, rotate: int, stop_event: threading.Event):
    pipeline = Gst.parse_launch(pipeline_str)
    appsink  = pipeline.get_by_name("appsink")
    pipeline.set_state(Gst.State.PLAYING)
    print("[CAPTURE] Camera thread started.")

    try:
        while not stop_event.is_set():
            sample = appsink.emit("try_pull_sample", int(1 * Gst.SECOND))
            if sample is None:
                continue
            rgb = gst_sample_to_numpy(sample)
            if rgb is None:
                continue

            if rotate in (90, 270):
                rgb = cv2.rotate(rgb, cv2.ROTATE_90_CLOCKWISE if rotate == 90 else cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif rotate == 180:
                rgb = cv2.rotate(rgb, cv2.ROTATE_180)

            pingpong.write(rgb)  # non-blocking hand-off
    except Exception as e:
        print(f"[CAPTURE][ERR] {e}")
    finally:
        pipeline.set_state(Gst.State.NULL)
        print("[CAPTURE] Camera thread ended.")

# ---------------- PROCESSING THREAD ----------
# NOTE: fixed parameter order: stop_event (no default) comes BEFORE defaulted args.
def processing_thread(pingpong: PingPongBuffer, interpreter, show_mode, out_path,
                      stop_event: threading.Event, det_scale=0.5, detect_every=5, timing=False,
                      processing_fps: float = None):
    if processing_fps is None:
        raise ValueError("processing_fps is required; pass args.fps from CLI.")
    print("[PROC] Processing thread started.")

    # Create MediaPipe face detector in this thread (safer)
    mp_fd = mp.solutions.face_detection.FaceDetection(
        model_selection=0, min_detection_confidence=0.5
    )

    writer = None
    # Multi-face state cache
    last_boxes = None
    last_detection_frame = None

    frame_count = 0
    t_start = time.time()
    # --- Seed smoother with intended FPS (no magic numbers) ---
    fps_smooth = float(processing_fps)

    # HUD FPS warm-up frames (display stabilization only)
    WARMUP_FRAMES_FOR_FPS = 30  # ~1 second at requested 30 FPS; adjust if desired

    if show_mode == "cv":
        try:
            cv2.namedWindow("Emotion Prediction (Ping–Pong)", cv2.WINDOW_NORMAL)
        except Exception as e:
            print(f"[WARN] Display not available: {e}")
            show_mode = "none"

    try:
        while not stop_event.is_set():
            t_total0 = time.perf_counter()
            rgb = pingpong.read_latest(timeout_ms=500)
            if rgb is None:
                time.sleep(0.001)
                continue

            H, W = rgb.shape[:2]

            # Detection cadence policy
            t_det0 = time.perf_counter()
            trigger_detection = (
                detect_every == 0
                or last_detection_frame is None
                or ((frame_count - last_detection_frame) >= detect_every)
                or (last_boxes is None)
            )
            if trigger_detection:
                boxes = detect_boxes_fast(rgb, det_scale=det_scale, mp_fd=mp_fd)
                if boxes is not None and len(boxes):
                    last_boxes = boxes
                    last_detection_frame = frame_count
            else:
                boxes = last_boxes
            t_det1 = time.perf_counter()

            # Per-face emotion inference (gated by valid boxes)
            labels_confs = []   # [(label, conf, box)]
            latencies = []

            t_pre0 = time.perf_counter()
            t_set0 = t_pre0
            t_inf0 = t_pre0
            t_post0 = t_pre0
            t_pre1 = t_pre0
            t_set1 = t_pre0
            t_inf1 = t_pre0
            t_post1 = t_pre0

            if boxes is not None:
                for box in boxes:
                    x0,y0,x1,y1 = box
                    x0,y0,x1,y1 = square_expand(x0,y0,x1,y1,W,H,scale=1.25)
                    crop_rgb = rgb[y0:y1, x0:x1]
                    if crop_rgb.size == 0:
                        continue

                    crop_bgr = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR)
                    real_input = preprocess_caffe_bgr_from_bgr(crop_bgr)
                    t_pre1 = time.perf_counter()

                    t_set0 = time.perf_counter()
                    set_input_int8_safe(interpreter, real_input)
                    t_set1 = time.perf_counter()

                    t_inf0 = time.perf_counter()
                    interpreter.invoke()
                    t_inf1 = time.perf_counter()
                    latencies.append((t_inf1 - t_inf0) * 1000.0)

                    t_post0 = time.perf_counter()
                    logits = get_output_dequantized_logits(interpreter)
                    probs  = softmax(logits)
                    idx    = int(np.argmax(probs))
                    conf   = float(probs[0][idx])
                    label  = EMOTION_LABELS[idx]
                    labels_confs.append((label, conf, (x0,y0,x1,y1)))
                    t_post1 = time.perf_counter()

            # Convert to BGR for drawing
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            # FPS calc (with warm-up reset for HUD stability; no magic numbers)
            frame_count += 1
            elapsed = time.time() - t_start

            # Reset counters once warm-up frames have passed (HUD only)
            if frame_count == WARMUP_FRAMES_FOR_FPS:
                frame_count = 0
                t_start = time.time()
                # Seed smoother with intended processing FPS
                fps_smooth = float(processing_fps)
                # If you prefer measured seeding, use:
                # fps_smooth = (frame_count / elapsed) if elapsed > 0 else fps_smooth

            inst_fps  = (frame_count / elapsed) if elapsed > 0 else fps_smooth
            fps_smooth = 0.85 * fps_smooth + 0.15 * inst_fps

            # Draw per-face + HUD
            t_draw0 = time.perf_counter()
            for (label, conf, box) in labels_confs:
                bgr = draw_result(bgr, box, label, conf)
            latency_ms = max(latencies) if latencies else None
            bgr_out = draw_result(bgr, None, None, 0.0, fps_val=None, latency_ms=latency_ms)
            t_draw1 = time.perf_counter()

            # Print FPS in terminal (single-line updating)
            print(f"\r[HUD] FPS: {fps_smooth:.1f}", end="", flush=True)

            # Lazy writer init once we know frame size
            t_write0 = time.perf_counter()
            if writer is None and out_path:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                writer = cv2.VideoWriter(out_path, fourcc, float(processing_fps), (W, H))
                if not writer.isOpened():
                    print(f"\n[WARN] Could not open writer at {out_path}")
                    writer = None
                else:
                    print(f"\n[INFO] Writing annotated video to: {out_path} at {W}x{H} @ {processing_fps:.1f} FPS")
            if writer is not None:
                writer.write(bgr_out)
            t_write1 = time.perf_counter()

            if show_mode == "cv":
                cv2.imshow("Emotion Prediction (Ping–Pong)", bgr_out)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n[INFO] Quit requested.")
                    stop_event.set()

            t_total1 = time.perf_counter()

            # Optional per-frame timing print
            if timing:
                print(("[TIMING] "
                       f"detect={(t_det1-t_det0)*1000.0:6.2f}ms | "
                       f"preproc={(t_pre1-t_pre0)*1000.0:6.2f}ms | set_input={(t_set1-t_set0)*1000.0:6.2f}ms | "
                       f"infer={(t_inf1-t_inf0)*1000.0:6.2f}ms | post={(t_post1-t_post0)*1000.0:6.2f}ms | "
                       f"draw={(t_draw1-t_draw0)*1000.0:6.2f}ms | write={(t_write1-t_write0)*1000.0:6.2f}ms | "
                       f"total={(t_total1-t_total0)*1000.0:6.2f}ms"))

    except Exception as e:
        print(f"\n[PROC][ERR] {e}")
    finally:
        # Clean up UI and writer
        if show_mode == "cv":
            try: cv2.destroyAllWindows()
            except: pass
        if writer is not None:
            writer.release()
        # Close MediaPipe resources
        try:
            mp_fd.close()
        except:
            pass
        print("\n[PROC] Processing thread ended.")

# ------------------- MAIN --------------------
def parse_args():
    p = argparse.ArgumentParser(description="RB3 Emotion (Ping–Pong threads, gated emotion, multi-face)")
    p.add_argument("--model",   type=str, required=True, help="Path to TFLite model (float or INT8)")
    p.add_argument("--backend", type=str, default="htp", choices=["cpu","htp"], help="cpu or htp (QNN)")
    p.add_argument("--threads", type=int, default=2, help="CPU threads when not using HTP")

    p.add_argument("--src",     type=str, default="qti", choices=["qti","v4l2"],
                    help="qti (RB3 main cam), v4l2 (/dev/videoX)")
    p.add_argument("--device",  type=str, default="/dev/video0",
                    help="V4L2 device path when --src v4l2")
    p.add_argument("--width",   type=int, default=640)
    p.add_argument("--height",  type=int, default=480)
    p.add_argument("--fps",     type=int, default=30)
    p.add_argument("--rotate",  type=int, default=0, choices=[0,90,180,270],
                    help="Rotate frames if needed (camera orientation)")

    p.add_argument("--det-scale", type=float, default=0.5,
                   help="Downscale factor for detection (0.5 -> detect at 50% size)")
    p.add_argument("--detect-every", type=int, default=5,
                   help="Run detection every N frames; reuse boxes otherwise (0 = detect every frame)")

    p.add_argument("--show",    type=str, default="cv", choices=["cv","none"],
                    help="cv: imshow preview window, none: headless")
    p.add_argument("--output",  type=str, default="",
                    help="Optional annotated MP4 to save (e.g., ./annotated.mp4)")

    # Timing flag
    p.add_argument("--timing", action="store_true",
                   help="Print per-frame timing (detect, preproc, set_input, infer, post, draw, write, total)")
    return p

def main():
    args = parse_args().parse_args()

    # Build pipeline & start capture thread
    pipeline_str = build_gst_pipeline(width=args.width, height=args.height, fps=args.fps,
                                      src=args.src, device=args.device)
    print("[GStreamer] Pipeline:", pipeline_str)

    pingpong = PingPongBuffer()
    stop_event = threading.Event()

    cap_thread = threading.Thread(
        target=camera_thread,
        args=(pipeline_str, pingpong, args.rotate, stop_event),
        daemon=True
    )
    cap_thread.start()

    interpreter = load_tflite(args.model, backend=args.backend, num_threads=args.threads)

    # NOTE: pass stop_event BEFORE defaulted args to match signature
    proc_thread = threading.Thread(
        target=processing_thread,
        args=(pingpong, interpreter, args.show, args.output if args.output else None,
              stop_event, args.det_scale, args.detect_every, args.timing, args.fps),
        daemon=True
    )
    proc_thread.start()

    try:
        while proc_thread.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[MAIN] Ctrl-C received. Stopping...")
        stop_event.set()

    cap_thread.join()
    proc_thread.join()
    print("\n[MAIN] Done.")

if __name__ == "__main__":
    main()

