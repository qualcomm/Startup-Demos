#===---xfeat_vo_tflite_delegate.py----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math
import time
from typing import Optional, Tuple, List

import cv2
import numpy as np


# -----------------------------
# TFLite runtime loader
# -----------------------------
def _load_tflite():
    try:
        import tflite_runtime.interpreter as tflite
        return "tflite_runtime", tflite
    except Exception:
        try:
            import tensorflow as tf
            return "tensorflow", tf.lite
        except Exception as e:
            raise RuntimeError(
                "Neither tflite_runtime nor tensorflow is available.\n"
                "Try:\n"
                "  pip install --extra-index-url https://google-coral.github.io/py-repo/ tflite_runtime\n"
                "and ensure numpy<2 (e.g., numpy==1.26.4)."
            ) from e


RUNTIME_KIND, TFL = _load_tflite()


def _load_delegate(delegate_path: str, backend_type: str):
    options = {"backend_type": backend_type}
    if hasattr(TFL, "load_delegate"):
        return TFL.load_delegate(delegate_path, options=options)
    if hasattr(TFL, "experimental") and hasattr(TFL.experimental, "load_delegate"):
        return TFL.experimental.load_delegate(delegate_path, options=options)
    raise RuntimeError("Cannot find load_delegate API in this TFLite package.")


# -----------------------------
# SuperPoint decode + NMS
# -----------------------------
def softmax_channel(x: np.ndarray, axis=0):
    x = x - np.max(x, axis=axis, keepdims=True)
    ex = np.exp(x)
    return ex / (np.sum(ex, axis=axis, keepdims=True) + 1e-12)


def decode_superpoint_k1_to_heat(k1_4d: np.ndarray, cell: int = 8) -> np.ndarray:
    if k1_4d.ndim != 4:
        raise ValueError(f"k1 dims invalid: {k1_4d.shape}")

    if k1_4d.shape[1] == 65:
        k1 = k1_4d[0]  # [65,Hc,Wc]
    elif k1_4d.shape[3] == 65:
        k1 = np.transpose(k1_4d[0], (2, 0, 1))
    else:
        raise ValueError(f"Cannot find 65-ch axis in {k1_4d.shape}")

    c, hc, wc = k1.shape
    assert c == (cell * cell + 1), f"expected 65 channels, got {c}"

    prob = softmax_channel(k1, axis=0)
    prob = prob[:cell * cell]
    p = prob.reshape(cell, cell, hc, wc)
    p = np.transpose(p, (2, 0, 3, 1))
    heat = p.reshape(hc * cell, wc * cell)
    return heat.astype(np.float32)


def nms_peaks(heat2d: np.ndarray, thresh: float, nms: int, max_points: int):
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
    xs = xs[order].astype(np.float32)
    ys = ys[order].astype(np.float32)
    scores = scores[order].astype(np.float32)
    return np.stack([xs, ys, scores], axis=1)


def apply_reliability(heat2d: np.ndarray, reli_4d: Optional[np.ndarray], act: str) -> np.ndarray:
    if reli_4d is None or not isinstance(reli_4d, np.ndarray) or reli_4d.ndim != 4:
        return heat2d

    if reli_4d.shape[1] == 1:
        r = reli_4d[0, 0]
    elif reli_4d.shape[3] == 1:
        r = reli_4d[0, :, :, 0]
    else:
        r = reli_4d[0, :, :, 0]

    r = r.astype(np.float32)
    if act == "sigmoid":
        r = 1.0 / (1.0 + np.exp(-r))
    elif act == "tanh":
        r = np.tanh(r)
    elif act == "relu":
        r = np.maximum(r, 0.0)

    r = cv2.resize(r, (heat2d.shape[1], heat2d.shape[0]), interpolation=cv2.INTER_LINEAR)
    return heat2d * np.clip(r, 0.0, 1.0)


# -----------------------------
# Quant/dequant + layout
# -----------------------------
def _quantize_input(x_float01: np.ndarray, dtype: np.dtype, quant: Tuple[float, int]) -> np.ndarray:
    scale, zp = quant
    if scale is None or scale == 0:
        if dtype == np.uint8:
            return (x_float01 * 255.0).clip(0, 255).astype(np.uint8)
        if dtype == np.int8:
            return (x_float01 * 127.0).clip(-128, 127).astype(np.int8)
        return x_float01.astype(dtype)

    q = np.round(x_float01 / scale + zp)
    if dtype == np.uint8:
        return q.clip(0, 255).astype(np.uint8)
    if dtype == np.int8:
        return q.clip(-128, 127).astype(np.int8)
    if dtype == np.int16:
        return q.clip(-32768, 32767).astype(np.int16)
    return q.astype(dtype)


def _dequantize_output(y: np.ndarray, quant: Tuple[float, int]) -> np.ndarray:
    scale, zp = quant
    if scale is None or scale == 0:
        return y.astype(np.float32)
    return (y.astype(np.float32) - float(zp)) * float(scale)


def _infer_layout_from_shape(shape) -> str:
    if len(shape) != 4:
        return "unknown"
    if shape[1] == 3:
        return "nchw"
    if shape[3] == 3:
        return "nhwc"
    return "unknown"


def _preprocess_frame(frame_bgr: np.ndarray, in_w: int, in_h: int, layout: str) -> np.ndarray:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (in_w, in_h), interpolation=cv2.INTER_LINEAR)
    x = rgb.astype(np.float32) / 255.0
    if layout == "nchw":
        x = np.transpose(x, (2, 0, 1))[None, ...]
    else:
        x = x[None, ...]
    return x


# -----------------------------
# Output parsing
# -----------------------------
def _as_hw_c(desc4d: np.ndarray) -> np.ndarray:
    if desc4d.ndim != 4:
        raise ValueError(f"desc rank must be 4, got {desc4d.shape}")
    if desc4d.shape[0] != 1:
        desc4d = desc4d[:1]
    if 16 <= desc4d.shape[1] <= 512 and desc4d.shape[3] != 3:
        d = np.transpose(desc4d[0], (1, 2, 0))
    else:
        d = desc4d[0]
    return d.astype(np.float32)


def _pick_outputs(outs: List[np.ndarray]):
    k1 = None
    heat1 = None
    reli1 = None
    desc = None

    for o in outs:
        if not isinstance(o, np.ndarray) or o.ndim != 4:
            continue
        if o.shape[1] == 65 or o.shape[3] == 65:
            k1 = o
            continue
        if o.shape[1] == 1 or o.shape[3] == 1:
            if heat1 is None:
                heat1 = o
            else:
                reli1 = o
            continue
        ch = o.shape[1] if o.shape[1] not in (1, 3) else o.shape[3]
        if ch >= 16:
            desc = o

    if k1 is not None:
        mode = "k1"
        heat_or_k1 = k1
    elif heat1 is not None:
        mode = "heat"
        heat_or_k1 = heat1[0, 0].astype(np.float32) if heat1.shape[1] == 1 else heat1[0, :, :, 0].astype(np.float32)
    else:
        return None, None, None, None

    desc_map = _as_hw_c(desc) if desc is not None else None
    return mode, heat_or_k1, desc_map, reli1


# -----------------------------
# Descriptor sampling at keypoints (bilinear)
# -----------------------------
def _bilinear_sample_desc(desc_hwc: np.ndarray, xs: np.ndarray, ys: np.ndarray, H: int, W: int) -> np.ndarray:
    Hc, Wc, C = desc_hwc.shape
    gx = xs / max(W - 1, 1) * (Wc - 1)
    gy = ys / max(H - 1, 1) * (Hc - 1)

    x0 = np.floor(gx).astype(np.int32)
    y0 = np.floor(gy).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, Wc - 1)
    y1 = np.clip(y0 + 1, 0, Hc - 1)

    dx = (gx - x0).astype(np.float32)
    dy = (gy - y0).astype(np.float32)

    d00 = desc_hwc[y0, x0]
    d10 = desc_hwc[y0, x1]
    d01 = desc_hwc[y1, x0]
    d11 = desc_hwc[y1, x1]

    d0 = d00 * (1.0 - dx)[:, None] + d10 * dx[:, None]
    d1 = d01 * (1.0 - dx)[:, None] + d11 * dx[:, None]
    d = d0 * (1.0 - dy)[:, None] + d1 * dy[:, None]

    n = np.linalg.norm(d, axis=1, keepdims=True) + 1e-8
    return d / n


def mask_count(mask: Optional[np.ndarray]) -> int:
    if mask is None:
        return 0
    m = mask.reshape(-1)
    return int((m > 0).sum())


# -----------------------------
# Camera + helpers
# -----------------------------
def open_camera(camera_index: int, cap_w: int, cap_h: int):
    if camera_index >= 0:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open /dev/video{camera_index}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_h)
        ok, _ = cap.read()
        if not ok:
            raise RuntimeError(f"Camera opened but cannot read: /dev/video{camera_index}")
        return camera_index, cap

    for idx in (0, 1, 2, 3):
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_h)
        ok, fr = cap.read()
        if ok and fr is not None and fr.size > 0:
            return idx, cap
        cap.release()
    raise RuntimeError("Cannot open any camera from indices 0~3")


def make_K_from_fov(W: int, H: int, fov_deg: float):
    fov = math.radians(max(10.0, min(170.0, fov_deg)))
    fx = (W / 2.0) / math.tan(fov / 2.0)
    fy = fx
    cx = W / 2.0
    cy = H / 2.0
    return np.array([[fx, 0, cx],
                     [0, fy, cy],
                     [0,  0,  1]], dtype=np.float64)


def rot_angle_deg(R: np.ndarray) -> float:
    tr = float(np.trace(R))
    c = (tr - 1.0) * 0.5
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


def draw_hud(img, line1: str, line2: str, org=(10, 26),
             font=cv2.FONT_HERSHEY_SIMPLEX, base_scale=0.72,
             color=(0, 255, 255), thickness=2):
    x, y = org
    H, W = img.shape[:2]
    scale = base_scale
    for _ in range(7):
        (w1, h1), _ = cv2.getTextSize(line1, font, scale, thickness)
        (w2, h2), _ = cv2.getTextSize(line2, font, scale, thickness)
        if max(w1, w2) <= W - 20:
            break
        scale *= 0.85

    (w1, h1), _ = cv2.getTextSize(line1, font, scale, thickness)
    (w2, h2), _ = cv2.getTextSize(line2, font, scale, thickness)
    bar_h = h1 + h2 + 18
    bar_w = max(w1, w2) + 16
    cv2.rectangle(img, (x - 6, y - h1 - 8), (x - 6 + bar_w, y - h1 - 8 + bar_h), (0, 0, 0), -1)
    cv2.putText(img, line1, (x, y), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(img, line2, (x, y + h2 + 10), font, scale, color, thickness, cv2.LINE_AA)


# -----------------------------
# Main (V5: anti-planar/jump gating)
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="XFeat VO v5 (anti-planar / anti-jump gating)")

    ap.add_argument("--model", type=str, required=True)
    ap.add_argument("--backend", type=str, choices=["htp", "dsp", "cpu"], default="htp")
    ap.add_argument("--delegate_path", type=str, default="libQnnTFLiteDelegate.so")

    ap.add_argument("--camera_index", type=int, default=-1)
    ap.add_argument("--cap_w", type=int, default=1280)
    ap.add_argument("--cap_h", type=int, default=720)

    # feature params
    ap.add_argument("--cell", type=int, default=8)
    ap.add_argument("--threshold", type=float, default=0.15)
    ap.add_argument("--nms", type=int, default=2)
    ap.add_argument("--max_points", type=int, default=1800)
    ap.add_argument("--use_reli", action="store_true")
    ap.add_argument("--reli_act", type=str, choices=["none", "sigmoid", "tanh", "relu"], default="sigmoid")
    ap.add_argument("--blur", type=int, default=3)

    # geometry / VO params
    ap.add_argument("--fov_deg", type=float, default=110.0)
    ap.add_argument("--ratio", type=float, default=0.90)
    ap.add_argument("--ransac_E", type=float, default=2.0)
    ap.add_argument("--ransac_H", type=float, default=3.0)
    ap.add_argument("--min_good_matches", type=int, default=80)
    ap.add_argument("--min_E_inliers", type=int, default=80)
    ap.add_argument("--min_pose_inliers", type=int, default=60)
    ap.add_argument("--min_inlier_ratio", type=float, default=0.15)

    # planar degeneracy detection: if H inliers dominate E inliers -> treat as planar/rotation
    ap.add_argument("--min_H_inliers", type=int, default=120)
    ap.add_argument("--planar_ratio", type=float, default=1.35)  # H_in > planar_ratio * E_in => planar

    # flow/jump gating
    ap.add_argument("--max_median_flow", type=float, default=35.0)
    ap.add_argument("--max_max_flow", type=float, default=140.0)
    ap.add_argument("--max_rot_deg", type=float, default=25.0)
    ap.add_argument("--max_t_change_deg", type=float, default=60.0)

    # keyframe policy
    ap.add_argument("--kf_max_age", type=int, default=25)
    ap.add_argument("--kf_parallax_px", type=float, default=25.0)   # if median flow from KF too big -> refresh KF
    ap.add_argument("--kf_bad_streak", type=int, default=8)

    # smoothing
    ap.add_argument("--t_ema", type=float, default=0.25)

    # visualization
    ap.add_argument("--draw_max_disp", type=float, default=70.0)     # do not draw huge blue lines
    ap.add_argument("--draw_max_lines", type=int, default=160)

    # display
    ap.add_argument("--display_scale", type=float, default=1.15)
    ap.add_argument("--win_w", type=int, default=1050)
    ap.add_argument("--win_h", type=int, default=720)
    ap.add_argument("--traj_w", type=int, default=700)
    ap.add_argument("--traj_h", type=int, default=700)
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--show_heat", action="store_true")
    ap.add_argument("--debug", action="store_true")

    args = ap.parse_args()

    delegates = None
    if args.backend != "cpu":
        delegates = [_load_delegate(args.delegate_path, args.backend)]

    interpreter = TFL.Interpreter(model_path=args.model, experimental_delegates=delegates)
    interpreter.allocate_tensors()

    in_det = interpreter.get_input_details()[0]
    out_dets = interpreter.get_output_details()
    inp_index = in_det["index"]
    inp_shape = list(in_det["shape"])
    inp_dtype = in_det["dtype"]
    inp_quant = in_det.get("quantization", (0.0, 0))

    layout = _infer_layout_from_shape(inp_shape)
    if layout == "unknown":
        layout = "nhwc"
    if layout == "nchw":
        in_h, in_w = int(inp_shape[2]), int(inp_shape[3])
    else:
        in_h, in_w = int(inp_shape[1]), int(inp_shape[2])

    print(f"[INFO] runtime={RUNTIME_KIND} backend={args.backend} delegate={args.delegate_path if args.backend!='cpu' else 'none'}")
    print(f"[INFO] input: shape={inp_shape} layout={layout} dtype={inp_dtype} quant={inp_quant}")
    for i, od in enumerate(out_dets):
        print(f"[INFO] output[{i}]: shape={od['shape']} dtype={od['dtype']} quant={od.get('quantization', (0.0,0))}")

    cam_idx, cap = open_camera(args.camera_index, args.cap_w, args.cap_h)
    print(f"[INFO] camera=/dev/video{cam_idx} capture={args.cap_w}x{args.cap_h} model_in={in_w}x{in_h}")

    K = make_K_from_fov(in_w, in_h, args.fov_deg)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]

    # windows
    win_main = f"XFeat-VOv5({args.backend}) /dev/video{cam_idx}"
    win_traj = "Trajectory (auto-center)"
    cv2.namedWindow(win_main, cv2.WINDOW_NORMAL)
    cv2.namedWindow(win_traj, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_main, args.win_w, args.win_h)
    cv2.resizeWindow(win_traj, args.traj_w, args.traj_h)
    if args.fullscreen:
        cv2.setWindowProperty(win_main, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

    # keyframe
    kf_kp = None
    kf_desc = None
    kf_age = 0
    bad_streak = 0

    # pose
    T_w_c = np.eye(4, dtype=np.float64)
    traj = [(0.0, 0.0)]
    traj_img = np.zeros((args.traj_h, args.traj_w, 3), dtype=np.uint8)
    t_dir_ema = None

    frame_id = 0
    t0 = time.time()

    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok or frame_bgr is None:
                break

            x = _preprocess_frame(frame_bgr, in_w=in_w, in_h=in_h, layout=layout)
            if inp_dtype != np.float32 and inp_dtype != np.float16:
                x_in = _quantize_input(x, inp_dtype, inp_quant)
            else:
                x_in = x.astype(inp_dtype)

            interpreter.set_tensor(inp_index, x_in)
            interpreter.invoke()

            outs = []
            for od in out_dets:
                y = interpreter.get_tensor(od["index"])
                q = od.get("quantization", (0.0, 0))
                if y.dtype != np.float32 and y.dtype != np.float16:
                    y = _dequantize_output(y, q)
                else:
                    y = y.astype(np.float32)
                outs.append(y)

            mode, heat_or_k1, desc_map, reli = _pick_outputs(outs)
            if mode is None or desc_map is None:
                disp0 = cv2.resize(frame_bgr, (in_w, in_h))
                cv2.putText(disp0, "Missing outputs", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow(win_main, disp0)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
                continue

            heat2d = decode_superpoint_k1_to_heat(heat_or_k1, cell=args.cell) if mode == "k1" else heat_or_k1
            if args.use_reli:
                heat2d = apply_reliability(heat2d, reli, act=args.reli_act)
            if args.blur >= 3 and args.blur % 2 == 1:
                heat2d = cv2.GaussianBlur(heat2d, (args.blur, args.blur), 0.0)

            peaks = nms_peaks(heat2d, args.threshold, args.nms, args.max_points)

            Hm, Wm = heat2d.shape[:2]
            sx = in_w / float(Wm)
            sy = in_h / float(Hm)
            xs = (peaks[:, 0] + 0.5) * sx
            ys = (peaks[:, 1] + 0.5) * sy

            # border filter
            m = 8
            valid = (xs >= m) & (xs < in_w - m) & (ys >= m) & (ys < in_h - m)
            xs, ys = xs[valid], ys[valid]

            if xs.size < 120:
                disp0 = cv2.resize(frame_bgr, (in_w, in_h))
                cv2.putText(disp0, f"Too few keypoints: {xs.size}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow(win_main, disp0)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
                continue

            kp_xy = np.stack([xs, ys], axis=1).astype(np.float32)
            hx = xs / max(in_w - 1, 1) * (Wm - 1)
            hy = ys / max(in_h - 1, 1) * (Hm - 1)
            desc = _bilinear_sample_desc(desc_map, hx, hy, Hm, Wm)

            # init keyframe
            if kf_desc is None:
                kf_kp, kf_desc = kp_xy, desc
                kf_age = 0
                bad_streak = 0
                t_dir_ema = None

            # match current -> keyframe
            knn = bf.knnMatch(kf_desc.astype(np.float32), desc.astype(np.float32), k=2)
            good = []
            for pair in knn:
                if len(pair) < 2:
                    continue
                a, b = pair[0], pair[1]
                if a.distance < args.ratio * b.distance:
                    good.append(a)

            # default status
            E_in = 0
            H_in = 0
            pose_in = 0
            pose_ok = False
            planar = False
            jump_reject = False
            median_flow = 0.0
            max_flow = 0.0
            R_deg = 0.0

            disp = cv2.resize(frame_bgr, (in_w, in_h))

            # draw points sparsely
            for (xk, yk) in kp_xy[::max(1, len(kp_xy)//900)]:
                cv2.circle(disp, (int(xk), int(yk)), 2, (0, 255, 0), -1, lineType=cv2.LINE_AA)

            if len(good) >= args.min_good_matches:
                pts1 = np.float32([kf_kp[m.queryIdx] for m in good])
                pts2 = np.float32([kp_xy[m.trainIdx] for m in good])

                # flow stats (pixel displacement from keyframe)
                flow = np.linalg.norm(pts2 - pts1, axis=1)
                median_flow = float(np.median(flow)) if flow.size else 0.0
                max_flow = float(np.max(flow)) if flow.size else 0.0

                # compute Essential (general motion)
                E, maskE = cv2.findEssentialMat(
                    pts1, pts2, focal=float(fx), pp=(float(cx), float(cy)),
                    method=cv2.RANSAC, prob=0.999, threshold=float(args.ransac_E)
                )
                E_in = mask_count(maskE)

                # compute Homography (planar or pure rotation fits well) [1](https://docs.opencv.org/master/d9/dab/tutorial_homography.html)[3](https://cseweb.ucsd.edu/classes/sp04/cse252b/notes/lec04/lec4.pdf)
                H, maskH = cv2.findHomography(pts1, pts2, method=cv2.RANSAC, ransacReprojThreshold=float(args.ransac_H))
                H_in = mask_count(maskH)

                # planar detection: if H inliers clearly dominate E inliers
                if H is not None and H_in >= args.min_H_inliers and (H_in > args.planar_ratio * max(E_in, 1)):
                    planar = True

                # visualization: only draw lines with reasonable displacement
                drawn = 0
                for mm in good:
                    if drawn >= args.draw_max_lines:
                        break
                    p1 = kf_kp[mm.queryIdx]
                    p2 = kp_xy[mm.trainIdx]
                    d = float(np.linalg.norm(p2 - p1))
                    if d <= args.draw_max_disp:
                        cv2.line(disp, (int(p2[0]), int(p2[1])), (int(p1[0]), int(p1[1])),
                                 (255, 0, 0), 1, lineType=cv2.LINE_AA)
                        drawn += 1

                # hard gates: if flow huge -> reject pose and refresh keyframe
                if median_flow > args.max_median_flow or max_flow > args.max_max_flow:
                    jump_reject = True
                elif (not planar) and E is not None and maskE is not None and E_in >= args.min_E_inliers:
                    # use only E-inliers for recoverPose (stability)
                    sel = (maskE.reshape(-1) > 0)
                    pts1_in = pts1[sel]
                    pts2_in = pts2[sel]

                    if pts1_in.shape[0] >= args.min_pose_inliers:
                        _, R, t, maskP = cv2.recoverPose(E, pts1_in, pts2_in, focal=float(fx), pp=(float(cx), float(cy)))
                        pose_in = mask_count(maskP)
                        R_deg = rot_angle_deg(R)

                        denom = max(pts1_in.shape[0], 1)
                        inlier_ratio = pose_in / float(denom)

                        # rotation gate
                        if R_deg > args.max_rot_deg:
                            jump_reject = True
                        else:
                            # t direction gate
                            tn = float(np.linalg.norm(t))
                            if tn > 1e-9:
                                t = t / tn
                            t_dir = t.flatten()

                            if t_dir_ema is None:
                                t_dir_ema = t_dir
                            else:
                                # if direction flips too much -> reject
                                dot = float(np.dot(t_dir_ema, t_dir))
                                dot = max(-1.0, min(1.0, dot))
                                ang = math.degrees(math.acos(dot))
                                if ang > args.max_t_change_deg:
                                    jump_reject = True
                                else:
                                    a = float(np.clip(args.t_ema, 0.0, 0.95))
                                    t_dir_ema = (1.0 - a) * t_dir + a * t_dir_ema
                                    t_dir_ema = t_dir_ema / (np.linalg.norm(t_dir_ema) + 1e-9)

                            if (not jump_reject) and (pose_in >= args.min_pose_inliers) and (inlier_ratio >= args.min_inlier_ratio):
                                # update pose (up-to-scale)
                                T = np.eye(4, dtype=np.float64)
                                T[:3, :3] = R
                                T[:3, 3] = t_dir_ema
                                T_w_c = T_w_c @ T
                                traj.append((float(T_w_c[0, 3]), float(T_w_c[2, 3])))
                                pose_ok = True

            # keyframe update policy (avoid long lines)
            kf_age += 1

            # if planar/rotation dominated or jump_reject -> refresh KF immediately
            if planar or jump_reject:
                kf_kp, kf_desc = kp_xy, desc
                kf_age = 0
                bad_streak = 0
                # do not change pose here (avoid wrong update)
            else:
                if pose_ok:
                    bad_streak = 0
                else:
                    bad_streak += 1

                # refresh KF if too old or parallax too large (avoid long baseline)
                if (kf_age >= args.kf_max_age) or (median_flow >= args.kf_parallax_px) or (bad_streak >= args.kf_bad_streak):
                    kf_kp, kf_desc = kp_xy, desc
                    kf_age = 0
                    bad_streak = 0

            fps = (frame_id + 1) / max(time.time() - t0, 1e-6)
            line1 = f"kpt={len(kp_xy)} good={len(good)} E_in={E_in} H_in={H_in} pose_in={pose_in} FPS={fps:.1f}"
            flags = []
            if planar:
                flags.append("PLANAR")
            if jump_reject:
                flags.append("JUMP_REJ")
            if pose_ok:
                flags.append("POSE_OK")
            else:
                flags.append("POSE_SKIP")
            line2 = f"KF_age={kf_age} bad={bad_streak} flow_med={median_flow:.1f} rot={R_deg:.1f}  {'|'.join(flags)}"
            draw_hud(disp, line1, line2)

            if args.show_heat:
                h = heat2d.copy()
                h -= h.min()
                if h.max() > 0:
                    h /= h.max()
                hm = (h * 255).astype(np.uint8)
                hm = cv2.applyColorMap(hm, cv2.COLORMAP_JET)
                hm = cv2.resize(hm, (in_w, in_h), interpolation=cv2.INTER_LINEAR)
                disp = cv2.addWeighted(disp, 1.0, hm, 0.30, 0.0)

            if args.display_scale != 1.0:
                disp_show = cv2.resize(disp, None, fx=args.display_scale, fy=args.display_scale, interpolation=cv2.INTER_LINEAR)
            else:
                disp_show = disp
            cv2.imshow(win_main, disp_show)

            # trajectory auto-center (last ~200)
            traj_img[:] = (10, 10, 10)
            if len(traj) >= 2:
                recent = min(len(traj), 200)
                xs_tr = np.array([p[0] for p in traj[-recent:]], dtype=np.float64)
                zs_tr = np.array([p[1] for p in traj[-recent:]], dtype=np.float64)
                cx_tr, cz_tr = xs_tr[-1], zs_tr[-1]
                rx = xs_tr - cx_tr
                rz = zs_tr - cz_tr
                spread = max(np.max(np.abs(rx)), np.max(np.abs(rz)), 1e-3)
                scale = 0.40 * min(args.traj_w, args.traj_h) / spread

                ox, oy = args.traj_w // 2, args.traj_h // 2
                pts = []
                for (tx, tz) in traj[-recent:]:
                    px = int(ox + (tx - cx_tr) * scale)
                    pz = int(oy - (tz - cz_tr) * scale)
                    pts.append([px, pz])
                pts = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(traj_img, [pts], False, (0, 255, 0), 2, lineType=cv2.LINE_AA)
                cv2.circle(traj_img, tuple(pts[-1, 0]), 4, (0, 0, 255), -1)

            cv2.putText(traj_img, "Trajectory (auto-center, last ~200)", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2, cv2.LINE_AA)
            cv2.imshow(win_traj, traj_img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

            frame_id += 1

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()