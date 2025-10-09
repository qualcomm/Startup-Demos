#===--inference_yolov4_onnx_fixed.py---------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import onnxruntime as ort
import cv2
import numpy as np

# -------- config --------
onnx_file = "/path-to-folder/yolov4.onnx"
img_path = "/path-to-folder/530_42.jpg"
inference_size = 832
conf_thresh = 0.01
nms_thresh = 0.4
class_names = ["object"]
output_path = "output_onnx_530_42.jpg"
# ------------------------

def letterbox_with_params(image, size):
    ih, iw = image.shape[:2]
    w, h = size
    scale = min(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    left = (w - nw) // 2
    top  = (h - nh) // 2
    canvas = np.full((h, w, 3), 128, dtype=np.uint8)
    canvas[top:top+nh, left:left+nw, :] = resized
    return canvas, scale, left, top, nw, nh

def row_to_padded_coords(row, inference_size):
    b = np.array(row, dtype=float).flatten()
    score = float(b[4]) if b.size > 4 else 0.0
    cls_id = int(b[5]) if b.size > 5 else 0
    a0, a1, a2, a3 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
    if (a0 <= 1.0 and a1 <= 1.0 and a2 <= 1.0 and a3 <= 1.0):
        if (a2 >= a0) and (a3 >= a1):
            lx1 = a0 * inference_size; ly1 = a1 * inference_size
            lx2 = a2 * inference_size; ly2 = a3 * inference_size
        else:
            cx = a0 * inference_size; cy = a1 * inference_size
            bw = a2 * inference_size; bh = a3 * inference_size
            lx1 = cx - bw / 2.0; ly1 = cy - bh / 2.0
            lx2 = cx + bw / 2.0; ly2 = cy + bh / 2.0
    else:
        lx1, ly1, lx2, ly2 = a0, a1, a2, a3
    return lx1, ly1, lx2, ly2, score, cls_id

def nms_and_select(box_rows, conf_thresh, nms_thresh, inference_size):
    if box_rows.size == 0:
        return [], []
    scores = box_rows[:, 4].astype(float)
    keep_mask = scores >= conf_thresh
    if not np.any(keep_mask):
        return [], []
    cand = box_rows[keep_mask]
    cand_scores = cand[:, 4].astype(float)
    bboxes = []
    for r in cand:
        lx1, ly1, lx2, ly2, sc, cid = row_to_padded_coords(r, inference_size)
        x = float(lx1); y = float(ly1); w = float(max(0.0, lx2-lx1)); h = float(max(0.0, ly2-ly1))
        bboxes.append([x, y, w, h])
    if len(bboxes) == 0:
        return [], []
    try:
        indices = cv2.dnn.NMSBoxes(bboxes, cand_scores.tolist(), conf_thresh, nms_thresh)
    except Exception as e:
        print("cv2.dnn.NMSBoxes failed:", e)
        order = np.argsort(-cand_scores)[:100]
        kept = order.tolist()
        return kept, [(bboxes[i], float(cand_scores[i]), int(cand[i,5]) if cand.shape[1]>5 else 0) for i in kept]
    if indices is None or len(indices) == 0:
        return [], []
    if isinstance(indices, np.ndarray):
        kept_idx = indices.flatten().tolist()
    elif isinstance(indices, (list, tuple)):
        kept_idx = []
        for x in indices:
            if isinstance(x, (list, tuple, np.ndarray)):
                kept_idx.append(int(x[0]))
            else:
                kept_idx.append(int(x))
    else:
        kept_idx = [int(indices)]
    kept_info = []
    for k in kept_idx:
        r = cand[k]
        lx1, ly1, lx2, ly2, sc, cid = row_to_padded_coords(r, inference_size)
        kept_info.append(([lx1, ly1, lx2, ly2], float(sc), int(cid)))
    return kept_idx, kept_info

# ---- main ----
print(f"Loading ONNX model from {onnx_file} ...")
sess = ort.InferenceSession(onnx_file, providers=["CPUExecutionProvider"])
input_name = sess.get_inputs()[0].name

orig = cv2.imread(img_path)
if orig is None:
    raise FileNotFoundError(f"Cannot read image {img_path}")
oh, ow = orig.shape[:2]

padded, scale, pad_x, pad_y, nw, nh = letterbox_with_params(orig, (inference_size, inference_size))
print(f"Letterbox params: scale={scale:.6f}, pad_x={pad_x}, pad_y={pad_y}, nw={nw}, nh={nh}")

img_rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
img_tensor = np.transpose(img_rgb, (2,0,1)).astype(np.float32) / 255.0
img_tensor = np.expand_dims(img_tensor, axis=0)

outs = sess.run(None, {input_name: img_tensor})
# outs could be [array] or (array,)
arr = outs[0] if isinstance(outs, (list,tuple)) and len(outs)>0 else outs
arr = np.array(arr)
if arr.ndim == 3 and arr.shape[0] == 1:
    arr = arr[0]
elif arr.ndim == 2:
    pass
else:
    arr = arr.reshape(-1, arr.shape[-1])
print("Raw predictions shape (after squeeze):", arr.shape)

kept_idxs, kept_info = nms_and_select(arr, conf_thresh, nms_thresh, inference_size)
print("Kept count:", len(kept_info))

out_img = orig.copy()
for bbox, sc, cid in kept_info:
    lx1, ly1, lx2, ly2 = bbox
    x1 = int((lx1 - pad_x) / scale + 0.5)
    y1 = int((ly1 - pad_y) / scale + 0.5)
    x2 = int((lx2 - pad_x) / scale + 0.5)
    y2 = int((ly2 - pad_y) / scale + 0.5)
    x1 = max(0, min(ow-1, x1)); y1 = max(0, min(oh-1, y1))
    x2 = max(0, min(ow-1, x2)); y2 = max(0, min(oh-1, y2))
    cv2.rectangle(out_img, (x1,y1), (x2,y2), (0,255,0), 2)
    label = f"{class_names[cid]} {sc:.2f}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    cv2.rectangle(out_img, (x1, max(0, y1-th-4)), (x1+tw, y1), (0,255,0), -1)
    cv2.putText(out_img, label, (x1, y1-2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 1, lineType=cv2.LINE_AA)

ok = cv2.imwrite(output_path, out_img)
print(f"Saved {output_path}: {ok}")

