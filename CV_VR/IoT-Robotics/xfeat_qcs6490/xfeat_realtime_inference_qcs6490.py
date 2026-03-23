#===-- xfeat_realtime_inference_qcs6490.py -------------------------------===//
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

# ---------- Optional runtimes ----------
LiteRTInterpreter = None
TFLiteRuntime = None
TFInterpreter = None
USING_TF_INTERPRETER = False

try:
    # AI Edge LiteRT (preferred when available)
    from ai_edge_litert.interpreter import Interpreter as LiteRTInterpreter
except Exception:
    LiteRTInterpreter = None

try:
    import tflite_runtime.interpreter as tflite_runtime
    TFLiteRuntime = tflite_runtime
except Exception:
    try:
        # Fallback: TensorFlow Interpreter (CPU only in most envs)
        from tensorflow.lite.python.interpreter import Interpreter as TFInterpreterRaw
        class _TFWrap:
            Interpreter = TFInterpreterRaw
            @staticmethod
            def load_delegate(path, options=None):
                # In TF Python Interpreter, delegate loading often unsupported
                raise RuntimeError("TensorFlow Interpreter: load_delegate not supported. Use LiteRT or tflite_runtime for NPU.")
        TFLiteRuntime = _TFWrap()
        USING_TF_INTERPRETER = True
    except Exception:
        TFLiteRuntime = None
        TFInterpreter = None

def log(msg: str):
    print(msg, flush=True)

# ---------- Delegate creation (robust) ----------
def create_qnn_delegate(backend: str = "htp"):
    """
    Try multiple known delegate loader entrypoints to create QNN delegate.
    Returns the delegate object or raises.
    """
    lib = os.environ.get("QNN_DELEGATE_PATH", "libQnnTFLiteDelegate.so")
    options = {"backend_type": str(backend)}
    errors = []
    for dotted in [
        "tensorflow.lite.python.interpreter.load_delegate",
        "tensorflow.lite.experimental.load_delegate",
        "tflite_runtime.interpreter.load_delegate",
    ]:
        try:
            mod_name, func_name = dotted.rsplit(".", 1)
            mod = __import__(mod_name, fromlist=[func_name])
            load_delegate = getattr(mod, func_name)
            delegate_obj = load_delegate(lib, options=options)
            log(f"[Delegate] Loaded via {dotted} -> {lib} options={options}")
            return delegate_obj
        except Exception as e:
            errors.append(f"{dotted}: {e}")
    raise RuntimeError("Failed to create QNN delegate.\n" + "\n".join(errors))

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
# GStreamer helpers
# -----------------------------
def has_element(name: str) -> bool:
    try:
        return Gst.ElementFactory.find(name) is not None
    except Exception:
        return False

def build_gst_pipeline(args, in_w=None, in_h=None):
    """
    Build pipeline string for src in {qti, ext, v4l2}.
    For qti/ext, prefer qtivtransform & GBM when available; fallback otherwise.
    """
    w, h, fps = args.width, args.height, args.fps

    if args.src == "qti":
        if has_element("qtiqmmfsrc") and has_element("qtivtransform"):
            # Prefer GBM zero-copy path + hardware transform
            pipe = (
                "qtiqmmfsrc name=cam0 ! "
                f"video/x-raw(memory:GBM),format=NV12,width={w},height={h},framerate={fps}/1 ! "
                "qtivtransform ! video/x-raw,format=RGB ! "
                "queue leaky=2 max-size-buffers=2 ! "
                "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
            )
            return pipe
        else:
            log("[Warn] qti/qtivtransform not available. Falling back to CPU videoconvert pipeline.")
            pipe = (
                "qtiqmmfsrc name=cam0 ! "
                f"video/x-raw,format=NV12,width={w},height={h},framerate={fps}/1 ! "
                "videoconvert n-threads=2 ! video/x-raw,format=RGB ! "
                "queue leaky=2 max-size-buffers=2 ! "
                "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
            )
            return pipe

    if args.src == "ext":
        # OpenCV(BGR) -> videoconvert(NV12, CPU)
        # -> qtivtransform (system->GBM, NV12)
        # -> qtivtransform name=preproc destination=<0,0,in_w,in_h> (GBM scale/crop to model size)
        # -> qtivtransform (GBM->system, NV12)
        # -> videoconvert (CPU, NV12->RGB)
        # -> appsink (RGB, CPU)
        if has_element("qtivtransform"):
            dst_w = in_w if in_w else w
            dst_h = in_h if in_h else h
            pipe = (
                "appsrc name=mysrc is-live=true format=time do-timestamp=true block=true "
                f"caps=video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1 ! "
                "queue leaky=2 max-size-buffers=2 ! "
                "videoconvert ! video/x-raw,format=NV12 ! "
                "qtivtransform ! "
                f"video/x-raw(memory:GBM),format=NV12,width={w},height={h},framerate={fps}/1 ! "
                f"qtivtransform name=preproc destination=<0,0,{dst_w},{dst_h}> ! "
                "qtivtransform ! video/x-raw,format=NV12 ! "
                "videoconvert ! video/x-raw,format=RGB ! "
                "appsink name=appsink caps=video/x-raw,format=RGB "
                "sync=false drop=true max-buffers=1 emit-signals=true"
            )
            return pipe
        else:
            log("[Warn] qtivtransform not available. Using simple appsrc->videoconvert->appsink pipeline.")
            pipe = (
                "appsrc name=mysrc is-live=true format=time do-timestamp=true block=true "
                f"caps=video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1 ! "
                "videoconvert ! video/x-raw,format=RGB ! "
                "queue leaky=2 max-size-buffers=2 ! "
                "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
            )
            return pipe

    # v4l2 (generic)
    pipe = (
        f"v4l2src device={args.device} io-mode=2 ! "
        f"video/x-raw,format=YUY2,width={w},height={h},framerate={fps}/1 ! "
        "videoconvert ! video/x-raw,format=RGB ! "
        "queue leaky=2 max-size-buffers=2 ! "
        "appsink name=appsink sync=false drop=true max-buffers=1 emit-signals=true"
    )
    return pipe

def push_bgr_frame(appsrc, frame_bgr: np.ndarray, fps: int):
    data = frame_bgr.tobytes()
    buf  = Gst.Buffer.new_allocate(None, len(data), None)
    buf.fill(0, data)
    buf.duration = Gst.SECOND // max(1, fps)
    rt = appsrc.get_current_running_time()
    buf.pts = rt
    buf.dts = rt
    return appsrc.emit("push-buffer", buf)

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
# NMS utils
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
# Interpreter selection (auto)
# -----------------------------
def try_litert(model_path: str, backend: str, num_threads: int):
    if LiteRTInterpreter is None:
        raise RuntimeError("LiteRT not installed.")
    delegates = []
    used_delegate = None
    if backend in ("htp", "auto"):
        try:
            used_delegate = create_qnn_delegate("htp")
            delegates.append(used_delegate)
        except Exception as e:
            if backend == "htp":
                raise
            log(f"[Warn] LiteRT QNN delegate failed: {e}. Falling back to CPU.")
    interpreter = LiteRTInterpreter(model_path=model_path,
                                    experimental_delegates=delegates,
                                    num_threads=num_threads)
    interpreter.allocate_tensors()
    return interpreter, "litert", ("qnn" if used_delegate else "cpu")

def try_tflite_runtime(model_path: str, backend: str, num_threads: int):
    if TFLiteRuntime is None:
        raise RuntimeError("tflite_runtime/TF Interpreter not available.")
    delegates = []
    used_delegate = None
    if backend in ("htp", "auto") and not USING_TF_INTERPRETER:
        try:
            # Use robust creator for QNN delegate object
            used_delegate = create_qnn_delegate("htp")
            delegates.append(used_delegate)
        except Exception as e:
            if backend == "htp":
                raise
            log(f"[Warn] tflite_runtime QNN delegate failed: {e}. Falling back to CPU.")
    interpreter = TFLiteRuntime.Interpreter(
        model_path=model_path,
        experimental_delegates=delegates or None,
        num_threads=num_threads
    )
    interpreter.allocate_tensors()
    return interpreter, ("tflite_runtime" if not USING_TF_INTERPRETER else "tf_interpreter"), ("qnn" if used_delegate else "cpu")

def pick_interpreter(model_path: str, backend: str, num_threads: int = 2):
    """
    backend: 'auto' | 'htp' | 'cpu'
    Try LiteRT -> tflite_runtime/TF in order, respecting backend preference.
    """
    if backend not in ("auto", "htp", "cpu"):
        backend = "auto"

    # Prefer LiteRT when available
    if backend in ("auto", "htp"):
        try:
            return try_litert(model_path, backend, num_threads)
        except Exception as e:
            log(f"[Info] LiteRT path unavailable: {e}")

        try:
            return try_tflite_runtime(model_path, backend, num_threads)
        except Exception as e:
            log(f"[Info] tflite_runtime path unavailable: {e}")
            if backend == "htp":
                raise

    # CPU-only fallbacks
    # LiteRT CPU
    try:
        return try_litert(model_path, "cpu", num_threads)
    except Exception as e:
        log(f"[Info] LiteRT CPU unavailable: {e}")

    # tflite_runtime / TF CPU
    return try_tflite_runtime(model_path, "cpu", num_threads)

# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=str, required=True)
    ap.add_argument("--backend", type=str, choices=["auto", "htp", "cpu"], default="auto")
    ap.add_argument("--threads", type=int, default=2)

    # Sources
    ap.add_argument("--src", type=str, choices=["qti", "ext", "v4l2"], default="ext")
    ap.add_argument("--device", type=str, default="/dev/video0")      # v4l2
    ap.add_argument("--cam-index", type=int, default=0, help="OpenCV VideoCapture index（ext 用）")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
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

    # Init interpreter first (we need input dims for ext/qti preproc)
    interpreter, runtime_kind, accel = pick_interpreter(args.model, args.backend, args.threads)
    in_det = interpreter.get_input_details()[0]
    out_dets = interpreter.get_output_details()
    inp_index = in_det["index"]
    inp_shape = list(in_det["shape"])
    inp_dtype = in_det["dtype"]
    if len(inp_shape) != 4:
        log(f"[Error] Unsupported input shape: {inp_shape}")
        return 3
    nhwc = (inp_shape[3] == 3)
    in_h, in_w = (inp_shape[1], inp_shape[2]) if nhwc else (inp_shape[2], inp_shape[3])

    log(f"[Runtime] kind={runtime_kind}, accel={accel}, threads={args.threads}")
    log(f"[TFLite] Input: index={inp_index}, shape={inp_shape}, dtype={inp_dtype}")
    for i, od in enumerate(out_dets):
        q = od.get("quantization_parameters", {})
        log(f"[TFLite] Output[{i}]: index={od['index']}, shape={od['shape']}, dtype={od['dtype']} "
            f"(scale={q.get('scales')}, zp={q.get('zero_points')})")

    # Init GStreamer
    Gst.init(None)
    pipeline_str = build_gst_pipeline(args, in_w=in_w, in_h=in_h)
    log(f"[GStreamer] Pipeline: {pipeline_str}")
    pipeline = Gst.parse_launch(pipeline_str)

    appsrc  = pipeline.get_by_name("mysrc")
    appsink = pipeline.get_by_name("appsink")
    preproc = pipeline.get_by_name("preproc")

    if appsink is None:
        log("[Error] appsink not found.")
        pipeline.set_state(Gst.State.NULL)
        return 2

    bus = pipeline.get_bus()
    bus.add_signal_watch()

    pipeline.set_state(Gst.State.PLAYING)

    # OpenCV source for ext
    cap = None
    if args.src == "ext":
        cap = cv2.VideoCapture(args.cam_index)
        if not cap.isOpened():
            log(f"[Error] Cannot open camera index {args.cam_index}")
            pipeline.set_state(Gst.State.NULL)
            return 1
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        cap.set(cv2.CAP_PROP_FPS,          args.fps)

    # Update preproc destination to model input size
    if preproc is not None:
        try:
            preproc.set_property("destination", f"<0,0,{in_w},{in_h}>")
            log(f"[Gst] preproc.destination set to <0,0,{in_w},{in_h}>")
        except Exception as e:
            log(f"[Warn] set preproc.destination failed: {e}")

    # Display window
    show = True
    try:
        cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(args.window, args.width, args.height)
    except Exception:
        log("[Warn] OpenCV window creation failed. Running headless.")
        show = False

    # Main loop
    try:
        last_fps = 0.0
        fps_update_t = time.time()
        frames_since_update = 0

        while True:
            # ext: push BGR frames via appsrc
            if args.src == "ext" and appsrc is not None:
                ok, frame_bgr = cap.read()
                if not ok:
                    break
                if (frame_bgr.shape[1] != args.width) or (frame_bgr.shape[0] != args.height):
                    frame_bgr = cv2.resize(frame_bgr, (args.width, args.height), interpolation=cv2.INTER_LINEAR)
                _ = push_bgr_frame(appsrc, frame_bgr, args.fps)

            # pull RGB frame
            sample = appsink.emit("try_pull_sample", int(0.5 * Gst.SECOND))
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

            # map points back to display size
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

            hud = f"{runtime_kind}({accel}) | FPS: {last_fps:.1f} | Pts: {len(peaks)}"
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
        if cap: cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    return 0

if __name__ == "__main__":
    sys.exit(main())
