#===--HandDetection_ONNX.py-----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import argparse
import math
from dataclasses import dataclass
import cv2
import numpy as np
import onnxruntime as ort

# MediaPipe 21 landmarks
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17)
]


def sigmoid(x):
    x = np.clip(x, -80.0, 80.0)  # prevent exp overflow
    return 1.0 / (1.0 + np.exp(-x))


def create_qnn_session(model_path: str, 
                       qnn_backend_path: str,
                       perf_mode="burst", 
                       finalize_opt="3",
                       disable_cpu_fallback=True):
    options = ort.SessionOptions()
    if disable_cpu_fallback:
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

    ep_options = {
        "backend_path": qnn_backend_path,
        "enable_htp_fp16_precision": "1",
        "htp_performance_mode": perf_mode,
        "htp_graph_finalization_optimization_mode": finalize_opt
    }

    return ort.InferenceSession(
        model_path,
        sess_options=options,
        providers=["QNNExecutionProvider"],
        provider_options=[ep_options]
    )


def nchw_from_rgb(img_rgb, size_hw):
    h, w = size_hw
    x = cv2.resize(img_rgb, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    x /= 255.0
    x = np.transpose(x, (2, 0, 1))[None, ...]  # HWC -> CHW -> NCHW
    return x


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def crop_with_affine(frame_bgr, center_xy, side, rot_deg, out_size):
    cx, cy = center_xy
    side = max(1e-6, float(side))

    scale = out_size / side
    M = cv2.getRotationMatrix2D((cx, cy), rot_deg, scale)

    M[0, 2] += (out_size * 0.5) - cx
    M[1, 2] += (out_size * 0.5) - cy

    crop = cv2.warpAffine(
        frame_bgr, M, (out_size, out_size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )

    invM = cv2.invertAffineTransform(M)
    return crop, invM


def draw_hand(frame, pts, color=(0, 255, 0)):
    for a, b in HAND_CONNECTIONS:
        cv2.line(
            frame,
            (int(pts[a, 0]), int(pts[a, 1])),
            (int(pts[b, 0]), int(pts[b, 1])),
            color, 2, cv2.LINE_AA
        )

    for i in range(pts.shape[0]):
        cv2.circle(frame, (int(pts[i, 0]), int(pts[i, 1])), 3, (0, 0, 255), -1, cv2.LINE_AA)


@dataclass
class HandConfig:
    det_thresh: float = 0.6
    nms_iou: float = 0.3
    max_hands: int = 2
    roi_scale: float = 2.2
    lm_pres_thresh: float = 0.85


def init_hands_pipeline(sess_palm, sess_lm, anchors_npy: str, cfg: HandConfig):
    palm_in = sess_palm.get_inputs()[0]
    _, _, palm_h, palm_w = palm_in.shape

    lm_in = sess_lm.get_inputs()[0]
    _, _, lm_h, lm_w = lm_in.shape
    lm_out_size = int(lm_w)

    anchors = np.load(anchors_npy).astype(np.float32)

    state = {
        "sess_palm": sess_palm,
        "sess_lm": sess_lm,
        "cfg": cfg,
        "anchors": anchors,

        "palm_in": palm_in,
        "palm_h": int(palm_h),
        "palm_w": int(palm_w),

        "lm_in": lm_in,
        "lm_h": int(lm_h),
        "lm_w": int(lm_w),
        "lm_out_size": lm_out_size,
    }
    return state


# Palm detect + decode + NMS
def decode_and_nms(state, reg, cls):
    cfg = state["cfg"]
    anchors = state["anchors"]
    palm_w = state["palm_w"]
    palm_h = state["palm_h"]

    reg = np.squeeze(reg, axis=0)  # [2944,18]
    cls = np.squeeze(cls, axis=0)  # [2944,1]

    cls = cls[:, 0]

    if reg.shape[0] != anchors.shape[0]:
        raise ValueError(f"Anchor count mismatch: reg N={reg.shape[0]} vs anchors N={anchors.shape[0]}")

    scores = sigmoid(cls)
    keep = scores >= cfg.det_thresh
    if not np.any(keep):
        return []

    r = reg[keep]          # [K,18]
    s = scores[keep]       # [K]
    a = anchors[keep]      # [K,4]

    x_scale = float(palm_w)
    y_scale = float(palm_h)
    w_scale = float(palm_w)
    h_scale = float(palm_h)

    cx = (r[:, 0] / x_scale) + a[:, 0]
    cy = (r[:, 1] / y_scale) + a[:, 1]
    w  = (r[:, 2] / w_scale)
    h  = (r[:, 3] / h_scale)

    x1 = cx - w * 0.5
    y1 = cy - h * 0.5
    x2 = cx + w * 0.5
    y2 = cy + h * 0.5

    # Decode 7 keypoints
    kps = []
    for k in range(7):

        kx = (r[:, 4 + 2 * k]     / x_scale) + a[:, 0]
        ky = (r[:, 4 + 2 * k + 1] / y_scale) + a[:, 1]
        kps.append(np.stack([kx, ky], axis=1))

    kps = np.stack(kps, axis=1).astype(np.float32)  # [K,7,2]

    boxes_xywh = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
    idxs = cv2.dnn.NMSBoxes(
        boxes_xywh, s.tolist(),
        score_threshold=cfg.det_thresh,
        nms_threshold=cfg.nms_iou
    )

    if idxs is None or len(idxs) == 0:
        return []
    idxs = np.array(idxs).reshape(-1)

    idxs = idxs[np.argsort(-s[idxs])]
    idxs = idxs[:cfg.max_hands]

    dets = []
    for i in idxs:
        dets.append({
            "score": float(s[i]),
            "box": (float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i])),
            "kps": kps[i]
        })
    return dets


def detect_palms(state, frame_bgr):
    cfg = state["cfg"]
    sess_palm = state["sess_palm"]
    palm_in = state["palm_in"]
    palm_h = state["palm_h"]
    palm_w = state["palm_w"]

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    blob = nchw_from_rgb(rgb, (palm_h, palm_w))

    outs = sess_palm.run(None, {palm_in.name: blob})
    reg = np.asarray(outs[0])
    cls = np.asarray(outs[1])

    return decode_and_nms(state, reg, cls)



# ROI + Landmark inference
def rotation_from_palm_kps(kps_img):
    p0, p2 = kps_img[0], kps_img[2]
    dx, dy = (p2[0] - p0[0]), (p2[1] - p0[1])
    theta = math.degrees(math.atan2(dy, dx))
    return 90.0 + theta


def roi_from_detection(state, det, w_img, h_img):
    cfg = state["cfg"]
    x1, y1, x2, y2 = det["box"]
    x1, y1, x2, y2 = map(clamp01, (x1, y1, x2, y2))

    bw = (x2 - x1) * w_img
    bh = (y2 - y1) * h_img
    
    # Filter out small detections by comparing box area to the full image area
    if bw * bh < 0.008 * (w_img * h_img):
        return None

    cx = (x1 + x2) * 0.5 * w_img
    cy = (y1 + y2) * 0.5 * h_img
    side = max(bw, bh) * cfg.roi_scale

    kps = det["kps"]
    kps_img = np.stack([kps[:, 0] * w_img, kps[:, 1] * h_img], axis=1)
    rot = rotation_from_palm_kps(kps_img)

    return (cx, cy, side, rot, kps_img)


def project_landmarks(lm_norm, invM, out_size):
    xy = lm_norm[:, :2] * (out_size - 1)
    ones = np.ones((xy.shape[0], 1), np.float32)
    xy1 = np.concatenate([xy, ones], axis=1)
    out = (invM @ xy1.T).T  # [21,2]
    pts = np.concatenate([out, lm_norm[:, 2:3]], axis=1)
    return pts.astype(np.float32)


def infer_landmarks(state, frame_bgr, roi):
    cfg = state["cfg"]
    sess_lm = state["sess_lm"]
    lm_in = state["lm_in"]
    lm_h = state["lm_h"]
    lm_w = state["lm_w"]
    out_size = state["lm_out_size"]

    cx, cy, side, rot, _ = roi
    crop, invM = crop_with_affine(frame_bgr, (cx, cy), side, rot, out_size)

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    blob = nchw_from_rgb(rgb, (lm_h, lm_w))

    outs = sess_lm.run(None, {lm_in.name: blob})

    pres = float(np.asarray(outs[0]).reshape(-1)[0])
    handed = float(np.asarray(outs[1]).reshape(-1)[0])
    lm = np.asarray(outs[2]).reshape(21, 3).astype(np.float32)

    if pres < cfg.lm_pres_thresh:
        return None

    pts = project_landmarks(lm, invM, out_size)
    return pts, pres, handed


def process_frame(state, frame_bgr):
    h_img, w_img = frame_bgr.shape[:2]
    dets = detect_palms(state, frame_bgr)

    results = []
    for d in dets:
        roi = roi_from_detection(state, d, w_img, h_img)
        if roi is None:
            continue

        lm_res = infer_landmarks(state, frame_bgr, roi)
        if lm_res is None:
            continue

        pts, pres, handed = lm_res

        xs = pts[:, 0]
        ys = pts[:, 1]
        area = (xs.max() - xs.min()) * (ys.max() - ys.min())
        if area < 0.0005 * (w_img * h_img):
            continue

        results.append((d, roi, pts, pres, handed))

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--palm_model", required=True)
    ap.add_argument("--landmark_model", required=True)
    ap.add_argument("--anchors_npy", required=True)
    ap.add_argument("--qnn_path", default="QnnHtp.dll")

    ap.add_argument("--cam_id", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--mirror", action="store_true")

    ap.add_argument("--det_thresh", type=float, default=0.8)
    ap.add_argument("--nms_iou", type=float, default=0.3)
    ap.add_argument("--max_hands", type=int, default=2)
    ap.add_argument("--roi_scale", type=float, default=2.2)

    ap.add_argument("--lm_pres_thresh", type=float, default=0.85)

    args = ap.parse_args()
    
    try:
        sess_palm = create_qnn_session(args.palm_model, args.qnn_path)
        sess_lm = create_qnn_session(args.landmark_model, args.qnn_path)

        cfg = HandConfig(
            det_thresh=args.det_thresh,
            nms_iou=args.nms_iou,
            max_hands=args.max_hands,
            roi_scale=args.roi_scale,
            lm_pres_thresh=args.lm_pres_thresh
        )

        state = init_hands_pipeline(sess_palm, sess_lm, args.anchors_npy, cfg)

        cap = cv2.VideoCapture(args.cam_id)
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open camera {args.cam_id}")
                
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if args.mirror:
                frame = cv2.flip(frame, 1)

            results = process_frame(state, frame)

            h_img, w_img = frame.shape[:2]
            for d, roi, pts, pres, handed in results:
                x1, y1, x2, y2 = d["box"]
                x1, y1, x2, y2 = map(clamp01, (x1, y1, x2, y2))

                px1, py1 = int(x1 * w_img), int(y1 * h_img)
                px2, py2 = int(x2 * w_img), int(y2 * h_img)

                cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 128, 0), 2)
                cv2.putText(frame, f"palm {d['score']:.2f}", (px1, py1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 128, 0), 2)

                draw_hand(frame, pts, (0, 255, 0))
                cv2.putText(frame, f"lm {pres:.2f} hand {handed:.2f}", (px1, py2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            cv2.imshow("Hands detection with QNN", frame)
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                break
    
    finally:
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
