#===----------------ai_guard_system cv_pipeline-----------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
"""
dual_cam_sql.py — Dual USB-cam item detection → SQLite (per-minute max aggregation)

Architecture
────────────
GStreamer pipeline (cam0) ─→ appsink0 ─┐
                                       ├─→ single-thread inference (TFLite + QNN NPU)
GStreamer pipeline (cam1) ─→ appsink1 ─┘          │
                                                  ▼
                                          per-frame count
                                          (score > threshold)
                                                  │
                                          ┌───────┴───────┐
                                          │  max tracker   │  (sliding window)
                                          └───────┬───────┘
                                                  │  every N seconds
                                                  ▼
                                             SQLite DB
                              ┌───────────────────────┐
                              │ events                │
                              │  id (PK)              │
                              │  timestamp            │
                              │  camera_id            │
                              │  person_count   INT   │
                              │  vehicle_count  INT   │
                              │  animal_count   INT   │
                              │  item_count     INT   │
                              └───────────────────────┘

Category mapping (COCO-80 → 4 groups)
─────────────────────────────────────
person  : person
vehicle : bicycle, car, motorcycle, airplane, bus, train, truck, boat
animal  : bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe
item  : everything else (accessories, sports, food, furniture …)

Aggregation rule
────────────────
• Only detections with score ≥ --score-thr (default 0.8) are counted.
• Each frame produces a per-category count.
• Over the flush interval the **maximum** per-category count is tracked
  (avoids double-counting the same scene across frames).
• Every --flush-interval seconds (default 60) one row per camera is
  written to SQLite with the max counts, then the tracker resets.

Usage
─────
python dual_cam_sql.py \\
    --model ./yolo26s_int8.tflite \\
    --labels ./coco_labels.txt \\
    --delegate htp \\
    --source mjpeg \\
    --cam0-id 2 --cam1-id 8 \\
    --cam-width 640 --cam-height 480 \\
    --flush-interval 60 \\
    --score-thr 0.8 \\
"""

import argparse
import os
import sys
import time
import signal
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from frame_bridge import SharedFrameWriter

import numpy as np
import cv2

# =====================================================================
#  GStreamer
# =====================================================================
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst  # noqa: E402

# =====================================================================
#  TFLite interpreter
# =====================================================================
try:
    from ai_edge_litert.interpreter import Interpreter, load_delegate
except Exception:
    sys.exit("[ERROR] Please install ai-edge-litert: pip install ai-edge-litert")

# =====================================================================
#  Constants
# =====================================================================
MODEL_W, MODEL_H = 640, 640
DEFAULT_CONF_THR  = 0.5
DEFAULT_NMS_THR   = 0.45
DEFAULT_SCORE_THR = 0.8
DEFAULT_FLUSH_SEC = 60

# Shared-memory frame writers (inference frames → UI)
writer0 = SharedFrameWriter("cam0", height=480, width=640)
writer1 = SharedFrameWriter("cam1", height=480, width=640)

# =====================================================================
#  COCO-80 labels (index-aligned)
# =====================================================================
COCO_80 = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck",
    "boat","traffic light","fire hydrant","stop sign","parking meter","bench",
    "bird","cat","dog","horse","sheep","cow","elephant","bear","zebra",
    "giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee",
    "skis","snowboard","sports ball","kite","baseball bat","baseball glove",
    "skateboard","surfboard","tennis racket","bottle","wine glass","cup",
    "fork","knife","spoon","bowl","banana","apple","sandwich","orange",
    "broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
    "potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink",
    "refrigerator","book","clock","vase","scissors","teddy bear",
    "hair drier","toothbrush",
]

# =====================================================================
#  Category mapping (COCO label → 4 groups)
# =====================================================================
CATEGORY_MAP: Dict[str, str] = {
    # person
    "person":          "person",
    # vehicle
    "bicycle":         "vehicle",
    "car":             "vehicle",
    "motorcycle":      "vehicle",
    "airplane":        "vehicle",
    "bus":             "vehicle",
    "train":           "vehicle",
    "truck":           "vehicle",
    "boat":            "vehicle",
    # animal
    "bird":            "animal",
    "cat":             "animal",
    "dog":             "animal",
    "horse":           "animal",
    "sheep":           "animal",
    "cow":             "animal",
    "elephant":        "animal",
    "bear":            "animal",
    "zebra":           "animal",
    "giraffe":         "animal",
    # item (everything else → default)
    "traffic light":   "item",
    "fire hydrant":    "item",
    "stop sign":       "item",
    "parking meter":   "item",
    "bench":           "item",
    "backpack":        "item",
    "umbrella":        "item",
    "handbag":         "item",
    "tie":             "item",
    "suitcase":        "item",
    "frisbee":         "item",
    "skis":            "item",
    "snowboard":       "item",
    "sports ball":     "item",
    "kite":            "item",
    "baseball bat":    "item",
    "baseball glove":  "item",
    "skateboard":      "item",
    "surfboard":       "item",
    "tennis racket":   "item",
    "bottle":          "item",
    "wine glass":      "item",
    "cup":             "item",
    "fork":            "item",
    "knife":           "item",
    "spoon":           "item",
    "bowl":            "item",
    "banana":          "item",
    "apple":           "item",
    "sandwich":        "item",
    "orange":          "item",
    "broccoli":        "item",
    "carrot":          "item",
    "hot dog":         "item",
    "pizza":           "item",
    "donut":           "item",
    "cake":            "item",
    "chair":           "item",
    "couch":           "item",
    "potted plant":    "item",
    "bed":             "item",
    "dining table":    "item",
    "toilet":          "item",
    "tv":              "item",
    "laptop":          "item",
    "mouse":           "item",
    "remote":          "item",
    "keyboard":        "item",
    "cell phone":      "item",
    "microwave":       "item",
    "oven":            "item",
    "toaster":         "item",
    "sink":            "item",
    "refrigerator":    "item",
    "book":            "item",
    "clock":           "item",
    "vase":            "item",
    "scissors":        "item",
    "teddy bear":      "item",
    "hair drier":      "item",
    "toothbrush":      "item",
}

CATEGORIES = ["person", "vehicle", "animal", "item"]


def label_to_category(label: str) -> str:
    """Map any COCO label (or unknown) to one of the 4 categories."""
    return CATEGORY_MAP.get(label, "item")


# =====================================================================
#  Detection dataclass
# =====================================================================

@dataclass
class Detection:
    box: List[float]       # [x0, y0, x1, y1] pixel coords
    score: float
    class_id: int


# =====================================================================
#  SQLite helpers
# =====================================================================

def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the events database and return a connection."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            camera_id INTEGER NOT NULL,
            person_count INTEGER NOT NULL DEFAULT 0,
            vehicle_count INTEGER NOT NULL DEFAULT 0,
            animal_count INTEGER NOT NULL DEFAULT 0,
            item_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON events(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cam ON events(camera_id)")
    conn.commit()
    print(f"[DB] ✅ SQLite initialised (WAL mode) → {db_path}")
    return conn


def flush_to_db(conn: sqlite3.Connection,
                max_trackers: Dict[int, Dict[str, int]]) -> None:
    """Write one row per camera with the max counts accumulated so far."""
    now = datetime.now().replace(microsecond=0).isoformat()
    for cam_id in sorted(max_trackers):
        t = max_trackers[cam_id]
        p = t.get("person",  0)
        v = t.get("vehicle", 0)
        a = t.get("animal",  0)
        o = t.get("item",  0)

        conn.execute(
            "INSERT INTO events "
            "(timestamp, camera_id, person_count, vehicle_count, animal_count, item_count) "
            "VALUES (?,?,?,?,?,?)",
            (now, cam_id, p, v, a, o),
        )
        print(f"  💾 [CAM{cam_id}] person={p}  vehicle={v}  animal={a}  item={o}")

    conn.commit()
    print(f"  💾 DB flushed at {now}")


# =====================================================================
#  Max tracker (per-camera, per-category)
# =====================================================================

def new_max_trackers(cam_ids: List[int]) -> Dict[int, Dict[str, int]]:
    """Create a fresh max tracker: {cam_id: {category: 0, ...}}."""
    return {cid: {cat: 0 for cat in CATEGORIES} for cid in cam_ids}


def update_max_tracker(tracker: Dict[str, int],
                       frame_counts: Dict[str, int]) -> None:
    """Update with max(existing, this_frame) for each category."""
    for cat in CATEGORIES:
        tracker[cat] = max(tracker[cat], frame_counts.get(cat, 0))


# =====================================================================
#  GStreamer helpers
# =====================================================================

def make_pipeline(cam_id: int, width: int, height: int,
                  source: str, sink_name: str) -> str:
    """Build a single-camera GStreamer pipeline string ending with an RGB appsink."""
    dev = f"/dev/video{cam_id}"

    if source == "mjpeg":
        src = (
            f"v4l2src device={dev} ! "
            f"image/jpeg,width={width},height={height},framerate=30/1 ! "
            f"jpegdec ! videoconvert ! videoscale ! "
        )
    elif source == "v4l2":
        src = (
            f"v4l2src device={dev} ! "
            f"video/x-raw,format=YUY2,width={width},height={height},framerate=30/1 ! "
            f"videoconvert ! videoscale ! "
        )
    else:
        raise ValueError(f"Unsupported source: {source}")

    tail = (
        f"video/x-raw,format=RGB,width={width},height={height} ! "
        f"appsink name={sink_name} emit-signals=false sync=false "
        f"max-buffers=1 drop=true"
    )
    return src + tail


def pull_frame(appsink, w: int, h: int,
               timeout_ns: int = 2_000_000_000) -> Optional[np.ndarray]:
    """Try pulling one RGB frame from appsink; returns HxWx3 uint8 or None."""
    sample = appsink.emit("try-pull-sample", timeout_ns)
    if sample is None:
        return None
    buf = sample.get_buffer()
    ok, info = buf.map(Gst.MapFlags.READ)
    if not ok:
        return None
    try:
        if info.size < w * h * 3:
            return None
        frame = np.ndarray((h, w, 3), dtype=np.uint8, buffer=info.data).copy()
        return frame
    finally:
        buf.unmap(info)


# =====================================================================
#  TFLite model helpers
# =====================================================================

def load_labels(path: Optional[str]) -> List[str]:
    """Load labels from a text file, or fall back to built-in COCO-80."""
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            labels = [l.strip() for l in f if l.strip()]
        print(f"[MODEL] Loaded {len(labels)} labels from {path}")
        return labels
    print("[MODEL] Using built-in COCO-80 labels")
    return COCO_80


def load_model(model_path: str,
               delegate_type: str) -> Tuple:
    """Load TFLite model with optional QNN delegate."""
    delegates: list = []
    if delegate_type != "cpu":
        try:
            d = load_delegate("libQnnTFLiteDelegate.so",
                              options={"backend_type": delegate_type})
            delegates.append(d)
            print(f"[MODEL] ✅ QNN delegate loaded (backend={delegate_type})")
        except Exception as e:
            print(f"[MODEL] ⚠️  QNN delegate failed: {e} → CPU fallback")

    interp = (Interpreter(model_path=model_path, experimental_delegates=delegates)
              if delegates else Interpreter(model_path=model_path))
    interp.allocate_tensors()

    in_det  = interp.get_input_details()[0]
    out_det = interp.get_output_details()

    print(f"[MODEL] Input  : shape={in_det['shape']}  dtype={in_det['dtype']}")
    for i, od in enumerate(out_det):
        print(f"[MODEL] Output{i}: shape={od['shape']}  dtype={od['dtype']}")

    return interp, in_det, out_det


# =====================================================================
#  Pre-processing / Post-processing
# =====================================================================

def preprocess(frame_rgb: np.ndarray, input_detail: dict,
               model_w: int = MODEL_W, model_h: int = MODEL_H) -> np.ndarray:
    """Resize to model size and format to model input dtype."""
    img = cv2.resize(frame_rgb, (model_w, model_h), interpolation=cv2.INTER_LINEAR)
    if input_detail["dtype"] == np.uint8:
        tensor = img.astype(np.uint8)
    else:
        tensor = (img.astype(np.float32) / 255.0)
    return np.expand_dims(tensor, axis=0)


def _quant_params(detail: dict):
    """Extract quantization parameters from output detail."""
    qp = detail.get("quantization_parameters", {})
    s  = qp.get("scales",      None)
    z  = qp.get("zero_points", None)
    if s is None or z is None or len(s) == 0:
        q = detail.get("quantization", None)
        if q and q[0] and q[1] is not None:
            return np.array([q[0]], np.float32), np.array([q[1]], np.int32)
        return np.array([], np.float32), np.array([], np.int32)
    return np.array(s), np.array(z)


def dequantize(tensor: np.ndarray, detail: dict) -> np.ndarray:
    """uint8/int8 tensor → float32 using per-tensor or per-channel quant params."""
    scales, zps = _quant_params(detail)
    if scales.size == 0:
        return tensor.astype(np.float32)
    if scales.size == 1:
        return (tensor.astype(np.float32) - float(zps[0])) * float(scales[0])
    shp = [1] * tensor.ndim
    shp[-1] = scales.size
    return ((tensor.astype(np.float32) - zps.reshape(shp).astype(np.float32))
            * scales.reshape(shp).astype(np.float32))


def _nms_per_class(boxes: np.ndarray, scores: np.ndarray,
                   class_ids: np.ndarray, conf_thr: float,
                   nms_thr: float) -> List[Detection]:
    """Per-class NMS using OpenCV."""
    results: List[Detection] = []
    if boxes.size == 0:
        return results
    for cid in np.unique(class_ids):
        m = class_ids == cid
        cb, cs = boxes[m], scores[m]
        xywh = [[float(b[0]), float(b[1]),
                 float(b[2] - b[0]), float(b[3] - b[1])] for b in cb]
        idxs = cv2.dnn.NMSBoxes(xywh, cs.tolist(), conf_thr, nms_thr)
        if len(idxs):
            for i in idxs.flatten():
                results.append(Detection(box=cb[i].tolist(),
                                         score=float(cs[i]),
                                         class_id=int(cid)))
    results.sort(key=lambda d: d.score, reverse=True)
    return results


def postprocess(interp, out_details, conf_thr, nms_thr):
    """
    Decode model outputs into a list of Detection objects.

    Supports two output formats:
      - 3+ output tensors: boxes[0], scores[1], class_ids[2]  (AI Hub style)
      - 1 output tensor:   raw YOLO format  [cx, cy, w, h, cls_scores...]
    """
    n_out = len(out_details)

    if n_out >= 3:
        # --- AI Hub 3-output format: boxes, scores, class_ids ---
        boxes  = interp.get_tensor(out_details[0]["index"]).squeeze()
        scores = interp.get_tensor(out_details[1]["index"]).squeeze()
        cids   = interp.get_tensor(out_details[2]["index"]).squeeze()

        # Dequantize boxes and scores if quantized
        if out_details[0]["dtype"] == np.uint8:
            boxes  = dequantize(boxes,  out_details[0])
            scores = dequantize(scores, out_details[1])
        else:
            boxes  = boxes.astype(np.float32)
            scores = scores.astype(np.float32)

        cids = cids.astype(int)

        mask = scores > conf_thr
        if not np.any(mask):
            return []

        return _nms_per_class(boxes[mask], scores[mask], cids[mask],
                              conf_thr, nms_thr)

    elif n_out == 1:
        # --- Raw YOLO single-output format ---
        raw = interp.get_tensor(out_details[0]["index"]).squeeze()

        if out_details[0]["dtype"] == np.uint8:
            raw = dequantize(raw, out_details[0])

        # Transpose if shape is (num_features, num_detections)
        if raw.shape[0] < raw.shape[1]:
            raw = raw.T

        cx, cy, w, h = raw[:, 0], raw[:, 1], raw[:, 2], raw[:, 3]
        cls_scores = raw[:, 4:]

        x0 = cx - w / 2
        y0 = cy - h / 2
        x1 = cx + w / 2
        y1 = cy + h / 2

        max_s = cls_scores.max(axis=1)
        cids  = cls_scores.argmax(axis=1)

        mask = max_s > conf_thr
        if not np.any(mask):
            return []

        boxes = np.stack([x0[mask], y0[mask], x1[mask], y1[mask]], axis=1)

        return _nms_per_class(boxes, max_s[mask], cids[mask],
                              conf_thr, nms_thr)

    else:
        print(f"[WARN] Unknown output format ({n_out} tensors)")
        return []


def draw(frame_rgb: np.ndarray, dets: List[Detection],
         labels: List[str]) -> np.ndarray:
    """Draw bounding boxes and labels on the frame (returns BGR image)."""
    img = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    for d in dets:
        x0, y0, x1, y1 = (int(v) for v in d.box)
        cid = d.class_id
        lbl = labels[cid] if cid < len(labels) else f"cls_{cid}"
        tag = f"{lbl} {d.score:.2f}"
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 0), 2)
        cv2.putText(img, tag, (x0, max(y0 - 6, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return img


# =====================================================================
#  Main
# =====================================================================

def main():
    ap = argparse.ArgumentParser(
        description="Dual-cam detection → SQLite (per-minute max aggregation)")

    # Model arguments
    ap.add_argument("--model",    required=True, help="Path to .tflite")
    ap.add_argument("--labels",   default=None,  help="Label file (one per line)")
    ap.add_argument("--delegate", default="htp",
                    choices=["gpu", "htp", "dsp", "cpu"])

    # Camera arguments
    ap.add_argument("--source",     default="mjpeg",
                    choices=["mjpeg", "v4l2", "qti"])
    ap.add_argument("--cam0-id",    type=int, default=2)
    ap.add_argument("--cam1-id",    type=int, default=8)
    ap.add_argument("--cam-width",  type=int, default=640)
    ap.add_argument("--cam-height", type=int, default=480)

    # Model input size
    ap.add_argument("--model-width",  type=int, default=MODEL_W)
    ap.add_argument("--model-height", type=int, default=MODEL_H)

    # Threshold arguments
    ap.add_argument("--conf",      type=float, default=DEFAULT_CONF_THR,
                    help="NMS confidence threshold")
    ap.add_argument("--nms",       type=float, default=DEFAULT_NMS_THR,
                    help="NMS IoU threshold")
    ap.add_argument("--score-thr", type=float, default=DEFAULT_SCORE_THR,
                    help="Min score to count a detection for DB logging")

    # Database arguments
    ap.add_argument("--db",             default="events.db")
    ap.add_argument("--flush-interval", type=int, default=DEFAULT_FLUSH_SEC,
                    help="Seconds between DB flushes (default 60)")

    # Miscellaneous
    ap.add_argument("--max-frames", type=int, default=0, help="0 = forever")
    ap.add_argument("--show",       action="store_true")
    ap.add_argument("--gst-debug",  default="")
    args = ap.parse_args()

    if args.gst_debug:
        os.environ["GST_DEBUG"] = args.gst_debug
    if not os.path.isfile(args.model):
        sys.exit(f"[ERROR] Model not found: {args.model}")

    # ----- GStreamer setup -----
    Gst.init(None)

    p0_str = make_pipeline(args.cam0_id, args.cam_width, args.cam_height,
                           args.source, "sink0")
    p1_str = make_pipeline(args.cam1_id, args.cam_width, args.cam_height,
                           args.source, "sink1")

    pipeline0 = Gst.parse_launch(p0_str)
    pipeline1 = Gst.parse_launch(p1_str)
    sink0 = pipeline0.get_by_name("sink0")
    sink1 = pipeline1.get_by_name("sink1")

    pipeline0.set_state(Gst.State.PLAYING)
    pipeline1.set_state(Gst.State.PLAYING)
    print("🎥 Dual cameras started (GStreamer PLAYING)")

    # ----- Load model -----
    interp, in_detail, out_details = load_model(args.model, args.delegate)
    labels = load_labels(args.labels)
    for i, od in enumerate(out_details):
        raw = interp.get_tensor(od["index"])
        print(f"  Output[{i}]: shape={od['shape']} dtype={od['dtype']} "
              f"min={raw.min()} max={raw.max()}")

    # ----- Initialize database -----
    conn = init_db(args.db)

    # ----- Max tracker -----
    cam_ids = [0, 1]
    max_trackers = new_max_trackers(cam_ids)
    last_flush   = time.time()
    win0, win1 = "cam0", "cam1"

    # ----- Signal handling -----
    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    # ----- Main loop -----
    total_loops = 0
    t_start = time.time()

    print(f"\n🚀 Inference started  |  flush every {args.flush_interval}s"
          f"  |  score ≥ {args.score_thr}\n")

    try:
        while running:
            f0 = pull_frame(sink0, args.cam_width, args.cam_height)
            f1 = pull_frame(sink1, args.cam_width, args.cam_height)

            if f0 is None and f1 is None:
                continue

            for cam_id, frame_rgb in ((0, f0), (1, f1)):
                if frame_rgb is None:
                    continue

                # --- Inference ---
                tensor = preprocess(frame_rgb, in_detail,
                                    args.model_width, args.model_height)
                interp.set_tensor(in_detail["index"], tensor)

                t0 = time.perf_counter()
                interp.invoke()

                dets = postprocess(interp, out_details, args.conf, args.nms)

                # --- Per-frame category count (score ≥ threshold) ---
                frame_counts: Dict[str, int] = {cat: 0 for cat in CATEGORIES}
                for d in dets:
                    if d.score < args.score_thr:
                        continue
                    lbl = labels[d.class_id] if d.class_id < len(labels) else "unknown"
                    cat = label_to_category(lbl)
                    frame_counts[cat] += 1

                # --- Update max tracker ---
                update_max_tracker(max_trackers[cam_id], frame_counts)

                # --- Draw and display ---
                active = {k: v for k, v in frame_counts.items() if v > 0}
                vis = draw(frame_rgb, dets, labels)

                if args.show:
                    cv2.imshow(win0 if cam_id == 0 else win1, vis)

                # --- Write to shared memory for UI ---
                if cam_id == 0:
                    writer0.write(vis)
                else:
                    writer1.write(vis)

                # --- Console heartbeat ---
                infer_ms = (time.perf_counter() - t0) * 1000.0
                if active:
                    summary = "  ".join(f"{k}={v}" for k, v in active.items())
                    print(f"  [CAM{cam_id}] {infer_ms:5.1f} ms | {summary}")

            # --- Periodic flush to DB ---
            elapsed_since_flush = time.time() - last_flush
            if elapsed_since_flush >= args.flush_interval:
                print(f"\n{'='*50}")
                print(f"  ⏱  Flush  (window = {elapsed_since_flush:.0f}s)")
                print(f"{'='*50}")
                flush_to_db(conn, max_trackers)
                max_trackers = new_max_trackers(cam_ids)
                last_flush = time.time()
                print()

            # --- Loop bookkeeping ---
            total_loops += 1
            if total_loops % 100 == 0:
                fps = total_loops / (time.time() - t_start)
                print(f"  --- loops={total_loops}  rate={fps:.1f} Hz ---")

            if args.max_frames and total_loops >= args.max_frames:
                break

            if args.show:
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            time.sleep(0.005)

    finally:
        # Flush remaining data before exit
        remaining = any(
            any(v > 0 for v in t.values())
            for t in max_trackers.values()
        )
        if remaining:
            print(f"\n{'='*50}")
            print(f"  ⏱  Final flush (remaining data)")
            print(f"{'='*50}")
            flush_to_db(conn, max_trackers)

        conn.close()
        pipeline0.set_state(Gst.State.NULL)
        pipeline1.set_state(Gst.State.NULL)
        if args.show:
            cv2.destroyAllWindows()

        writer0.close()
        writer1.close()

        print("\n🛑 Stopped.")


if __name__ == "__main__":
    main()
