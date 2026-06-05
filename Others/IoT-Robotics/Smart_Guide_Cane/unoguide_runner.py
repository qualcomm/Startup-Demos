#===--unoguide_runner.py----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unoguide_runner.py

python3 unoguide_runner.py \
  --model /home/arduino/unoguide-linux-aarch64-v1.eim \
  --camera /dev/video0 \
  --label-file /home/arduino/ArduinoApps/unoguide/python/label.txt \
  --preview --preview-port 8080

Core features:
- anti-flicker + OFF confirm
- faster recovery from OFF:
    --anti-flicker-from-off (default 2)
    --red-immediate-from-off

Deployment / debug toggles:
- One-click deployment mode disables preview:
    export APP_DEPLOYMENT=1
  or:
    --deployment-mode

Preview speed knobs:
- export APP_PREVIEW_FPS=8          # preview encode rate (default 8)
- export APP_PREVIEW_SCALE=1.0      # resize preview before encoding (default 1.0)
- export APP_SIMPLE_OVERLAY=1       # concise overlay text (default 1)
- export APP_WEBPREVIEW=1           # allow preview when --preview is set (default 1)
"""

import os
import sys
import time
import json
import signal
import argparse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import cv2
from edge_impulse_linux.image import ImageImpulseRunner


# -----------------------------
# Helpers
# -----------------------------
def env_flag(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v == "":
        return default
    return v in ("1", "true", "yes", "y", "on")


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    if v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    v = os.environ.get(name, "").strip()
    if v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def atomic_write(path: str, content: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def throttle(max_fps: float, last_ts: float) -> float:
    if max_fps <= 0:
        return time.time()
    period = 1.0 / max_fps
    now = time.time()
    dt = now - last_ts
    if dt < period:
        time.sleep(period - dt)
    return time.time()


def normalize_color(label):
    if not label:
        return None
    s = str(label).strip().lower()

    if s in ("red", "yellow", "green"):
        return s
    if s in ("red_light", "yellow_light", "green_light"):
        return s.split("_")[0]

    if "red" in s:
        return "red"
    if "yellow" in s:
        return "yellow"
    if "green" in s:
        return "green"
    return None


def color_bgr(c: str):
    if c == "red":
        return (0, 0, 255)
    if c == "green":
        return (0, 255, 0)
    if c == "yellow":
        return (0, 255, 255)
    return (255, 255, 255)


def clamp_bbox(x, y, w, h, W, H):
    x = max(0, min(int(x), W - 1))
    y = max(0, min(int(y), H - 1))
    w = max(0, int(w))
    h = max(0, int(h))
    if x + w > W:
        w = max(0, W - x)
    if y + h > H:
        h = max(0, H - y)
    return x, y, w, h


# -----------------------------
# Defaults
# -----------------------------
DEFAULT_MODEL = os.environ.get("APP_MODEL", "/home/arduino/unoguide-linux-aarch64-v1.eim")
DEFAULT_CAMERA = os.environ.get("APP_CAMERA", "/dev/video0")
DEFAULT_LABEL_FILE = os.environ.get("APP_LABEL_FILE", "/home/arduino/ArduinoApps/unoguide/python/label.txt")

# If camera/inference fails, this label will be written initially.
DEFAULT_LABEL = os.environ.get("APP_DEFAULT_LABEL", "yellow_light")
OFF_LABEL = "off"

DEFAULT_TH = {
    "red": env_float("APP_TH_RED", 0.80),
    "green": env_float("APP_TH_GREEN", 0.80),
    "yellow": env_float("APP_TH_YELLOW", 0.80),
    "off": 0.80
}

DEFAULT_ANTI_FLICKER = env_int("APP_ANTI_FLICKER", 5)
DEFAULT_OFF_CONFIRM = env_int("APP_OFF_CONFIRM", 10)
DEFAULT_DEBUG_EVERY_SEC = env_float("APP_DEBUG_EVERY_SEC", 2.0)
DEFAULT_MAX_FPS = env_float("APP_MAX_FPS", 15.0)

DEFAULT_PREVIEW_PORT = env_int("APP_PREVIEW_PORT", 8080)
DEFAULT_JPEG_QUALITY = env_int("APP_JPEG_QUALITY", 80)

# Preview performance knobs
PREVIEW_FPS = max(1, env_int("APP_PREVIEW_FPS", 8))   # encode rate
PREVIEW_SCALE = max(0.1, min(1.0, env_float("APP_PREVIEW_SCALE", 1.0)))  # downscale before encoding
SIMPLE_OVERLAY = env_flag("APP_SIMPLE_OVERLAY", True)

_stop = False
_runner = None
_cap = None

# Latest preview frame (BGR) from inference loop (already with bbox + text overlay)
_latest_overlay_bgr = None
_latest_overlay_ts = 0.0
_overlay_lock = threading.Lock()

# Latest encoded JPEG for MJPEG streaming
_latest_jpeg = None
_latest_state = {}
_preview_lock = threading.Lock()
_preview_cond = threading.Condition(_preview_lock)


# -----------------------------
# Decision pipeline (keep boxes; keep decision reasons minimal)
# -----------------------------
def decide_from_boxes(boxes, TH):
    """
    Decision logic:
    1) any red >= TH['red'] => red_light (reason=red_seen)
    2) valid exists and all green >= TH['green'] => green_light (reason=all_green)
    3) no valid boxes over thresholds => off (reason=off)
    4) else => yellow_light (reason=fallback)
    """
    valid = []
    valid_colors = []
    red_hit = None

    # also keep top few boxes for drawing (even if below threshold, for debug)
    draw_boxes = []

    for b in boxes:
        raw_lab = b.get("label")
        c = normalize_color(raw_lab)
        score = safe_float(b.get("value"), 0.0)

        if c is None:
            continue

        x = int(b.get("x", 0))
        y = int(b.get("y", 0))
        w = int(b.get("width", 0))
        h = int(b.get("height", 0))

        draw_boxes.append({
            "color": c,
            "value": score,
            "x": x, "y": y, "w": w, "h": h,
            "label": raw_lab
        })

        if score < TH.get(c, 0.0):
            continue

        item = {
            "color": c,
            "value": score,
            "x": x, "y": y, "w": w, "h": h,
            "label": raw_lab
        }
        valid.append(item)
        valid_colors.append(c)
        if c == "red" and red_hit is None:
            red_hit = item

    # limit draw boxes to reduce clutter
    draw_boxes = sorted(draw_boxes, key=lambda d: d["value"], reverse=True)[:5]

    if red_hit is not None:
        return "red_light", {"reason": "red_seen", "draw_boxes": draw_boxes}

    if valid and all(c == "green" for c in valid_colors):
        return "green_light", {"reason": "all_green", "draw_boxes": draw_boxes}

    if not valid:
        return OFF_LABEL, {"reason": "off", "draw_boxes": draw_boxes}

    return "yellow_light", {"reason": "fallback", "draw_boxes": draw_boxes}


def extract_and_decide(res, TH):
    if not isinstance(res, dict):
        return DEFAULT_LABEL, {"reason": "res_not_dict", "draw_boxes": []}

    result = res.get("result", {})
    if not isinstance(result, dict):
        return DEFAULT_LABEL, {"reason": "result_not_dict", "draw_boxes": []}

    boxes = result.get("bounding_boxes")
    if isinstance(boxes, list):
        label, dbg = decide_from_boxes(boxes, TH)
        return label, dbg

    return DEFAULT_LABEL, {"reason": "no_boxes", "draw_boxes": []}


# -----------------------------
# Overlay drawing (FAST: on inference/cropped frame)
# -----------------------------
def draw_overlay_on_inference_frame(infer_rgb, dbg, stable_label, cand_label, cand_count, off_run, off_confirm):
    """
    infer_rgb: RGB image in model input space (e.g., 320x320)
    boxes from EI are aligned with this image -> no mapping needed (fast & stable).
    """
    out = cv2.cvtColor(infer_rgb, cv2.COLOR_RGB2BGR)
    H, W = out.shape[:2]

    # draw boxes
    for b in dbg.get("draw_boxes", []):
        c = b.get("color", "yellow")
        x, y, w, h = clamp_bbox(b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 0), W, H)
        v = safe_float(b.get("value", 0.0), 0.0)
        cv2.rectangle(out, (x, y), (x + w, y + h), color_bgr(c), 2)
        cv2.putText(out, f"{c}:{v:.2f}", (x, max(0, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr(c), 2, cv2.LINE_AA)

    reason = dbg.get("reason", "-")
    lines = [
        f"stable={stable_label}",
        f"reason={reason}",
        f"cand={cand_label} ({cand_count})",
    ]

    if not SIMPLE_OVERLAY:
        off_pending = (stable_label != OFF_LABEL and off_run > 0)
        if stable_label == OFF_LABEL or off_pending:
            lines.append(f"off_run={off_run}/{off_confirm}" + (" (pending)" if off_pending else ""))

    y0 = 24
    for line in lines:
        cv2.putText(out, line, (10, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60,
                    (255, 255, 255), 2, cv2.LINE_AA)
        y0 += 24

    return out


# -----------------------------
# Web preview server (MJPEG) - always serve latest JPEG (drop frames)
# -----------------------------
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            html = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>UnoGuide Preview</title></head>
<body style="background:#111;color:#eee;font-family:Arial;">
  <h3>UnoGuide Preview</h3>
  <div><img src="/stream.mjpg" style="max-width:100%;height:auto;" /></div>
  <p>JSON: <a href="/state.json" style="color:#8cf">/state.json</a></p>
</body>
</html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        if self.path.startswith("/state.json"):
            with _preview_lock:
                body = json.dumps(_latest_state, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.startswith("/stream.mjpg"):
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()

            last_sent_ts = 0.0
            try:
                while not _stop:
                    # Wait for a new frame, but do not block forever
                    with _preview_cond:
                        _preview_cond.wait(timeout=1.0 / max(1, PREVIEW_FPS))
                        frame = _latest_jpeg
                        ts = _latest_state.get("_ts", 0.0)

                    if frame is None:
                        continue

                    # If nothing new, still allow re-send occasionally (keeps browser alive)
                    if ts == last_sent_ts:
                        continue
                    last_sent_ts = ts

                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("utf-8"))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except Exception:
                return

        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        # suppress HTTP logs
        return


def start_preview_server(port: int):
    srv = ThreadingHTTPServer(("0.0.0.0", port), PreviewHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


# -----------------------------
# Preview encoder thread (fixed FPS, downscale, drop frames)
# -----------------------------
def preview_encoder_loop(jpeg_quality: int):
    global _latest_jpeg, _latest_state

    period = 1.0 / float(PREVIEW_FPS)
    last_encode = 0.0

    while not _stop:
        now = time.time()
        dt = now - last_encode
        if dt < period:
            time.sleep(period - dt)
        last_encode = time.time()

        # get latest overlay frame
        with _overlay_lock:
            frame = _latest_overlay_bgr
            fts = _latest_overlay_ts

        if frame is None:
            continue

        # downscale for faster encode/bandwidth
        if PREVIEW_SCALE < 0.999:
            new_w = int(frame.shape[1] * PREVIEW_SCALE)
            new_h = int(frame.shape[0] * PREVIEW_SCALE)
            if new_w >= 16 and new_h >= 16:
                frame_enc = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            else:
                frame_enc = frame
        else:
            frame_enc = frame

        ok, jpg = cv2.imencode(".jpg", frame_enc, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
        if not ok:
            continue

        # update shared latest jpeg + minimal state
        with _preview_cond:
            _latest_jpeg = jpg.tobytes()
            # keep existing state but ensure timestamp changes so stream sees "new"
            _latest_state["_ts"] = fts if fts else time.time()
            _preview_cond.notify_all()


# -----------------------------
# Signal handling
# -----------------------------
def _sig_handler(sig, frame):
    global _stop, _runner, _cap
    _stop = True
    try:
        if _cap is not None:
            _cap.release()
    except Exception:
        pass
    try:
        if _runner is not None:
            _runner.stop()
    except Exception:
        pass


# -----------------------------
# Args
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(description="EI UnoQ runner (fast preview with bbox)")

    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--camera", default=DEFAULT_CAMERA)
    p.add_argument("--label-file", default=DEFAULT_LABEL_FILE)

    p.add_argument("--anti-flicker", type=int, default=DEFAULT_ANTI_FLICKER)
    p.add_argument("--off-confirm", type=int, default=DEFAULT_OFF_CONFIRM)
    p.add_argument("--anti-flicker-from-off", type=int, default=2,
                   help="When stable is off, smaller anti-flicker for faster recovery")
    p.add_argument("--red-immediate-from-off", action="store_true",
                   help="If stable is off and raw becomes red_light, switch immediately")

    p.add_argument("--debug-every", type=float, default=DEFAULT_DEBUG_EVERY_SEC)
    p.add_argument("--max-fps", type=float, default=DEFAULT_MAX_FPS)

    # Debug-only preview controls
    p.add_argument("--preview", action="store_true")
    p.add_argument("--no-preview", action="store_true",
                   help="Disable web preview even if --preview is set")
    p.add_argument("--deployment-mode", action="store_true",
                   help="One-click deployment mode: disable debug features (e.g., web preview)")
    p.add_argument("--preview-port", type=int, default=DEFAULT_PREVIEW_PORT)
    p.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY)

    p.add_argument("--th-red", type=float, default=DEFAULT_TH["red"])
    p.add_argument("--th-green", type=float, default=DEFAULT_TH["green"])
    p.add_argument("--th-yellow", type=float, default=DEFAULT_TH["yellow"])
    return p.parse_args()


# -----------------------------
# Main
# -----------------------------
def main():
    global _runner, _cap, _latest_overlay_bgr, _latest_overlay_ts

    args = parse_args()

    deploy_mode = (
        args.deployment_mode
        or env_flag("APP_DEPLOYMENT", False)
        or env_flag("DEPLOYMENT_MODE", False)
        or env_flag("DEPLOYMENT", False)
    )

    enable_preview = (
        args.preview
        and (not args.no_preview)
        and (not deploy_mode)
        and env_flag("APP_WEBPREVIEW", True)
    )

    TH = {
        "red": args.th_red,
        "green": args.th_green,
        "yellow": args.th_yellow,
        "off": DEFAULT_TH["off"],
    }

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # init output label
    atomic_write(args.label_file, DEFAULT_LABEL)

    # preview server + encoder thread
    srv = None
    enc_thread = None
    if enable_preview:
        srv = start_preview_server(args.preview_port)
        print(f"[PREVIEW] http://<UNOQ_IP>:{args.preview_port}/ (stream=/stream.mjpg json=/state.json)", flush=True)

        enc_thread = threading.Thread(target=preview_encoder_loop, args=(args.jpeg_quality,), daemon=True)
        enc_thread.start()

    _runner = ImageImpulseRunner(args.model)
    _cap = None

    stable = DEFAULT_LABEL
    candidate = None
    cand_count = 0
    off_run = 0

    last_dbg = time.time()
    last_ts = time.time()

    try:
        _runner.init()
        try:
            print(f"[EI] resizeMode={_runner.resizeMode} input_dim={_runner.dim}", flush=True)
        except Exception:
            pass

        _cap = cv2.VideoCapture(args.camera)
        if not _cap.isOpened():
            print(f"[ERR] Cannot open camera: {args.camera}", flush=True)
            return 2

        try:
            _cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        while not _stop:
            last_ts = throttle(args.max_fps, last_ts)

            ok, frame_bgr = _cap.read()
            if not ok or frame_bgr is None:
                raw_label = DEFAULT_LABEL
                dbg = {"reason": "no_frame", "draw_boxes": []}
                infer_rgb = None
            else:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

                # Use EI auto studio settings; cropped is model input view (RGB)
                features, cropped = _runner.get_features_from_image_auto_studio_settings(frame_rgb)
                infer_rgb = cropped  # RGB in inference space

                try:
                    res = _runner.classify(features)
                except Exception as e:
                    raw_label = DEFAULT_LABEL
                    dbg = {"reason": "classify_exception", "draw_boxes": []}
                else:
                    raw_label, dbg = extract_and_decide(res, TH)

            # OFF confirm
            if raw_label == OFF_LABEL:
                off_run += 1
            else:
                off_run = 0

            if off_run >= args.off_confirm:
                if stable != OFF_LABEL:
                    stable = OFF_LABEL
                    candidate = OFF_LABEL
                    cand_count = off_run
                    atomic_write(args.label_file, stable)
            else:
                # prevent unconfirmed OFF from breaking anti-flicker
                effective_raw = raw_label
                if raw_label == OFF_LABEL:
                    effective_raw = stable

                # Fast recovery from OFF
                need = args.anti_flicker
                if stable == OFF_LABEL and effective_raw != OFF_LABEL:
                    need = max(1, int(args.anti_flicker_from_off))
                    if args.red_immediate_from_off and effective_raw == "red_light":
                        need = 1

                if effective_raw == candidate:
                    cand_count += 1
                else:
                    candidate = effective_raw
                    cand_count = 1

                if cand_count >= need and effective_raw != stable:
                    stable = effective_raw
                    atomic_write(args.label_file, stable)

            # Update preview (FAST): build overlay on inference view (cropped)
            if enable_preview and infer_rgb is not None:
                overlay_bgr = draw_overlay_on_inference_frame(
                    infer_rgb, dbg, stable, candidate, cand_count, off_run, args.off_confirm
                )

                # publish overlay frame for encoder thread
                with _overlay_lock:
                    _latest_overlay_bgr = overlay_bgr
                    _latest_overlay_ts = time.time()

                # update minimal state.json (no heavy dbg)
                with _preview_lock:
                    _latest_state.update({
                        "raw": raw_label,
                        "stable": stable,
                        "reason": dbg.get("reason", "-"),
                        "cand": candidate,
                        "cnt": cand_count,
                        "off_run": off_run,
                        "off_confirm": args.off_confirm,
                        "preview_fps": PREVIEW_FPS,
                        "preview_scale": PREVIEW_SCALE,
                    })

            # Periodic debug print (keep lightweight)
            if time.time() - last_dbg >= args.debug_every:
                print(
                    f"[EI] raw={raw_label} stable={stable} cand={candidate} cnt={cand_count} "
                    f"off_run={off_run}/{args.off_confirm}",
                    flush=True,
                )
                last_dbg = time.time()

    finally:
        try:
            _runner.stop()
        except Exception:
            pass
        try:
            if _cap is not None:
                _cap.release()
        except Exception:
            pass
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())