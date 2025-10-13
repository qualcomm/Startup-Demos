#===--xfeat_realtime_inference_qcs6490.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import argparse
import numpy as np

# GStreamer
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Visualization
import cv2

# TFLite runtime (preferred)
_using_tf_interpreter = False
try:
    import tflite_runtime.interpreter as tflite
except Exception:
    from tensorflow.lite.python.interpreter import Interpreter as TFInterpreter
    class _TFWrap:
        Interpreter = TFInterpreter
        @staticmethod
        def load_delegate(path, options=None):
            raise RuntimeError(
                "Currently using TensorFlow Interpreter; load_delegate is not supported. "
                "Please use tflite-runtime or set backend=cpu."
            )
    tflite = _TFWrap()
    _using_tf_interpreter = True


def log(msg: str):
    print(msg, flush=True)


# -----------------------------
# SuperPoint decoding
# -----------------------------
def softmax_channel(x: np.ndarray, axis=0):
    x = x - np.max(x, axis=axis, keepdims=True)
    ex = np.exp(x)
    return ex / (np.sum(ex, axis=axis, keepdims=True) + 1e-12)

def decode_superpoint_k1_to_heat(k1_4d: np.ndarray, cell: int = 8) -> np.ndarray:
    """
    k1_4d: [1,65,Hc,Wc] (NCHW) or [1,Hc,Wc,65] (NHWC)
    return: [Hc*cell, Wc*cell] full-res heatmap
    """
    if k1_4d.ndim != 4:
        raise ValueError(f"k1 dims invalid: {k1_4d.shape}")

    if k1_4d.shape[1] == 65:          # NCHW
        k1 = k1_4d[0]                 # [65,Hc,Wc]
    elif k1_4d.shape[3] == 65:        # NHWC
        k1 = np.transpose(k1_4d[0], (2, 0, 1))  # -> [65,Hc,Wc]
    else:
        raise ValueError(f"Cannot find 65-ch axis in {k1_4d.shape}")

    c, hc, wc = k1.shape
    assert c == (cell*cell + 1), f"expected 65 channels, got {c}"

    prob = softmax_channel(k1, axis=0)       # [65,Hc,Wc]
    prob_no_dust = prob[:cell*cell]          # [64,Hc,Wc]
    p = prob_no_dust.reshape(cell, cell, hc, wc)
    p = np.transpose(p, (2, 0, 3, 1))        # (Hc,8,Wc,8)
    full = p.reshape(hc*cell, wc*cell)       # (H,W)
    return full


# -----------------------------
# GStreamer
# -----------------------------
def build_gst_pipeline(args):
    w, h, fps = args.width, args.height, args.fps
    if args.src == "qti":
        pipe = (
            "qtiqmmfsrc name=cam0 ! "
            f"video/x-raw,format=NV12,width={w},height={h},framerate={fps}/1 ! "
            "videoconvert n-threads=2 ! video/x-raw,format=RGB ! "
            "queue leaky=2 max-size-buffers=2 ! "
            "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
        )
    else:
        pipe = (
            f"v4l2src device={args.device} ! "
            f"video/x-raw,format=YUY2,width={w},height={h},framerate={fps}/1 ! "
            "videoconvert n-threads=2 ! video/x-raw,format=RGB ! "
            "queue leaky=2 max-size-buffers=2 ! "
            "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
        )
    return pipe

def gst_sample_to_numpy(sample):
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
        frame = arr.reshape((height, width, 3))
        return frame
    finally:
        buf.unmap(mapinfo)


# -----------------------------
# TFLite
# -----------------------------
def load_tflite(model_path: str, backend: str, num_threads: int = 2):
    delegates = []
    if backend.lower() == "htp":
        if _using_tf_interpreter:
            log("[Warn] TensorFlow Interpreter in use; QNN delegate is not supported. Falling back to CPU.")
        else:
            delegate_path = os.environ.get("QNN_DELEGATE_PATH", "libQnnTFLiteDelegate.so")
            try:
                opts = {"backend_type": "htp"}
                delegates.append(tflite.load_delegate(delegate_path, options=opts))
                log(f"[TFLite] Using QNN Delegate: {delegate_path} (backend=htp)")
            except Exception as e:
                log(f"[Warn] Failed to load QNN delegate. Falling back to CPU: {e}")

    interpreter = tflite.Interpreter(
        model_path=model_path,
        experimental_delegates=delegates or None,
        num_threads=num_threads
    )
    interpreter.allocate_tensors()

    in_det = interpreter.get_input_details()[0]
    out_dets = interpreter.get_output_details()
    log(f"[TFLite] Input: index={in_det['index']}, shape={in_det['shape']}, dtype={in_det['dtype']}")
    for i, od in enumerate(out_dets):
        q = od.get("quantization_parameters", {})
        log(
            f"[TFLite] Output[{i}]: index={od['index']}, shape={od['shape']}, dtype={od['dtype']} "
            f"(scale={q.get('scales')}, zp={q.get('zero_points')})"
        )
    return interpreter, in_det, out_dets


# -----------------------------
# Utils
# -----------------------------
def nms_peaks(heat2d: np.ndarray, thresh: float = 0.3, nms: int = 3, max_points: int = 1000):
    h = heat2d.astype(np.float32)
    mx = float(h.max()) if h.size else 0.0
    if mx > 0:
        h = h / (mx + 1e-6)
    kernel = np.ones((2 * nms + 1, 2 * nms + 1), np.uint8)
    dil = cv2.dilate(h, kernel)
    peaks = (h >= thresh) & (h >= (dil - 1e-6))
    ys, xs = np.where(peaks)
    if ys.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    scores = h[ys, xs]
    order = np.argsort(-scores)[:max_points]
    xs = xs[order]
    ys = ys[order]
    scores = scores[order]
    return np.stack([xs.astype(np.float32), ys.astype(np.float32), scores.astype(np.float32)], axis=1)


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=str, required=True)
    ap.add_argument("--backend", type=str, choices=["htp", "cpu"], default="cpu")
    ap.add_argument("--threads", type=int, default=2)

    # Camera
    ap.add_argument("--src", type=str, choices=["qti", "v4l2"], default="qti")
    ap.add_argument("--device", type=str, default="/dev/video0")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)

    # Preprocess
    ap.add_argument("--preproc", type=str, choices=["01", "imagenet", "none", "gray01"], default="01")
    ap.add_argument("--color-order", type=str, choices=["rgb", "bgr"], default="rgb")

    # SuperPoint head
    ap.add_argument("--cell", type=int, default=8)
    ap.add_argument("--k1-idx", type=int, default=-1)
    ap.add_argument("--h1-idx", type=int, default=-1)

    # Postprocess
    ap.add_argument("--use-reli", action="store_true")
    ap.add_argument("--reli-act", type=str, choices=["none", "sigmoid", "tanh", "relu"], default="sigmoid")
    ap.add_argument("--blur", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=0.15)
    ap.add_argument("--nms", type=int, default=2)
    ap.add_argument("--max-points", type=int, default=1500)

    # Display
    ap.add_argument("--show-heat", action="store_true")
    ap.add_argument("--window", type=str, default="XFeat Realtime (SuperPoint)")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    # Init GStreamer
    Gst.init(None)
    pipeline_str = build_gst_pipeline(args)
    log(f"[GStreamer] Pipeline: {pipeline_str}")
    pipeline = Gst.parse_launch(pipeline_str)
    appsink = pipeline.get_by_name("appsink")
    if appsink is None:
        log("[Error] appsink not found.")
        sys.exit(2)
    pipeline.set_state(Gst.State.PLAYING)
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    # Load TFLite
    interpreter, in_det, out_dets = load_tflite(args.model, backend=args.backend, num_threads=args.threads)
    inp_index = in_det["index"]
    inp_shape = list(in_det["shape"])
    inp_dtype = in_det["dtype"]
    if len(inp_shape) != 4:
        log(f"[Error] Unsupported input shape: {inp_shape}")
        sys.exit(3)
    nhwc = (inp_shape[3] == 3)
    in_h, in_w = (inp_shape[1], inp_shape[2]) if nhwc else (inp_shape[2], inp_shape[3])

    # Window
    show = True
    try:
        cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(args.window, args.width, args.height)
    except Exception:
        log("[Warn] OpenCV window creation failed. Running headless.")
        show = False

    try:
        last_fps = 0.0
        fps_update_t = time.time()
        frames_since_update = 0
        while True:
            sample = appsink.emit("try_pull_sample", int(2 * Gst.SECOND))
            if sample is None:
                msg = bus.timed_pop_filtered(0, Gst.MessageType.ERROR | Gst.MessageType.EOS)
                if msg is not None:
                    if msg.type == Gst.MessageType.ERROR:
                        err, debug = msg.parse_error()
                        log(f"[GStreamer Error] {err}, debug={debug}")
                    else:
                        log("[GStreamer] EOS")
                    break
                continue

            # ---- pull frame ----
            frame_rgb = gst_sample_to_numpy(sample)
            if frame_rgb is None:
                continue

            # ---- preprocess ----
            img = frame_rgb  # RGB
            if args.preproc == "gray01":
                g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                img = np.stack([g, g, g], axis=-1)
            if args.color_order == "bgr":
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            if (img.shape[1] != in_w) or (img.shape[0] != in_h):
                img = cv2.resize(img, (in_w, in_h), interpolation=cv2.INTER_LINEAR)

            if args.preproc == "01":
                img_f = img.astype(np.float32) / 255.0
            elif args.preproc == "imagenet":
                img_f = img.astype(np.float32) / 255.0
                mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
                std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                img_f = (img_f - mean) / std
            elif args.preproc == "none":
                img_f = img.astype(np.float32)
            elif args.preproc == "gray01":
                img_f = img.astype(np.float32) / 255.0
            else:
                img_f = img.astype(np.float32) / 255.0

            if inp_dtype == np.uint8:
                tin = (img_f * 255.0).clip(0, 255).astype(np.uint8)
            else:
                tin = img_f.astype(np.float32)

            if nhwc:
                tin = tin[None, ...]
            else:
                tin = np.transpose(tin, (2, 0, 1))[None, ...]

            # ---- inference ----
            interpreter.set_tensor(inp_index, tin)
            interpreter.invoke()
            raw_outs = [interpreter.get_tensor(od["index"]) for od in out_dets]

            # ---- pick K1/H1 ----
            k1_4d = raw_outs[args.k1_idx] if args.k1_idx >= 0 else None
            h1_4d = raw_outs[args.h1_idx] if args.h1_idx >= 0 else None

            if k1_4d is None:
                for out in raw_outs:
                    shp = out.shape
                    if len(shp) == 4 and (shp[1] == 65 or (shp[3] == 65)):
                        k1_4d = out
                        break

            if h1_4d is None:
                for out in raw_outs:
                    shp = out.shape
                    if len(shp) == 4 and (shp[1] == 1 or (shp[3] == 1)):
                        h1_4d = out
                        break

            if k1_4d is None:
                raise RuntimeError("Could not find a 65-channel K1 output; specify it explicitly via --k1-idx.")

            # ---- SuperPoint decode ----
            heat2d = decode_superpoint_k1_to_heat(k1_4d, cell=args.cell)

            # reliability weighting
            if args.use_reli and (h1_4d is not None):
                if h1_4d.shape[1] == 1:
                    reli = h1_4d[0, 0, :, :]
                else:
                    reli = h1_4d[0, :, :, 0]
                if args.reli_act == "sigmoid":
                    reli = 1.0 / (1.0 + np.exp(-reli))
                elif args.reli_act == "tanh":
                    reli = np.tanh(reli)
                elif args.reli_act == "relu":
                    reli = np.maximum(reli, 0.0)
                # resize to full
                reli = cv2.resize(reli, (heat2d.shape[1], heat2d.shape[0]), interpolation=cv2.INTER_LINEAR)
                heat2d *= np.clip(reli, 0.0, 1.0)

            if args.blur >= 3 and args.blur % 2 == 1:
                heat2d = cv2.GaussianBlur(heat2d, (args.blur, args.blur), 0.0)

            # ---- NMS ----
            peaks = nms_peaks(heat2d, thresh=args.threshold, nms=args.nms, max_points=args.max_points)

            # ---- draw ----
            disp_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            if args.show_heat:
                h = heat2d.copy()
                h -= h.min()
                if h.max() > 0:
                    h /= h.max()
                hm = (h * 255).astype(np.uint8)
                hm = cv2.applyColorMap(hm, cv2.COLORMAP_JET)
                hm = cv2.resize(hm, (disp_bgr.shape[1], disp_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
                disp_bgr = cv2.addWeighted(disp_bgr, 1.0, hm, 0.35, 0.0)

            # heat2d resolution equals model input size; map back to camera frame by scaling
            H_full, W_full = heat2d.shape[:2]
            H_show, W_show = frame_rgb.shape[:2]
            sx, sy = W_show / float(W_full), H_show / float(H_full)
            for xh, yh, sc in peaks:
                x_img = int((xh + 0.5) * sx)
                y_img = int((yh + 0.5) * sy)
                cv2.circle(disp_bgr, (x_img, y_img), 2, (0, 255, 0), -1, lineType=cv2.LINE_AA)

            frames_since_update += 1
            now = time.time()
            elapsed = now - fps_update_t
            if elapsed >= 1.0:
                last_fps = frames_since_update / elapsed
                fps_update_t = now
                frames_since_update = 0

            # Draw HUD every frame (use last computed values to avoid flicker)
            hud = f"FPS: {last_fps:.1f} | Pts: {len(peaks)}"
            cv2.putText(disp_bgr, hud, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 255), 2, cv2.LINE_AA)

            if show:
                cv2.imshow(args.window, disp_bgr)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break

    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)
        if show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())