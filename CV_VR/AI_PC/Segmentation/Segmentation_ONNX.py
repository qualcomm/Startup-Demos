#===--Segmentation_ONNX.py------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import torch
import torch.nn.functional as F
import torchvision
import numpy as np
import cv2
import matplotlib.pyplot as plt
import onnxruntime
import argparse
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--onnx_path', type=str, required=True, help='Path to ONNX model')
parser.add_argument('--qnn_path', type=str, default='QnnHtp.dll', help='Path to QnnHtp.dll')
parser.add_argument('--score_thres', type=float, default=0.5, help='Score threshold for NMS')
parser.add_argument('--iou_thres', type=float, default=0.7, help='IoU threshold for NMS')
args = parser.parse_args()
    
options = onnxruntime.SessionOptions()

# (Optional) Enable configuration that raises an exception if the model can't be run entirely on the QNN HTP backend
options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

ep_options = {
              "backend_path": args.qnn_path,
              "enable_htp_fp16_precision": "1",
              "htp_performance_mode": "burst",
              "htp_graph_finalization_optimization_mode": "3"
             }
             
# Create an ONNX Runtime session
try:
    session = onnxruntime.InferenceSession(args.onnx_path,
                                           sess_options=options,
                                           providers=["QNNExecutionProvider"],
                                           provider_options=[ep_options])

    inputs = session.get_inputs()[0].name
    
except Exception as e:
    print(f"Error creating ONNX session: {e}")
    print("Please check that onnxruntime-qnn and QNN libraries are correctly installed and configured.")
    sys.exit(1)

def image_preprocess(image_path):
    
    # Convert the image to numpy array of shape [1, 3, 640, 640]
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Failed to load image from path: {image_path}. Please check if the file is a valid image format.")
        
    orig_h, orig_w = image.shape[:2]
    target_h, target_w = 640, 640

    # 1) Calculate the proportional scaling ratio and the scaled dimensions
    ratio = min(target_h / orig_h, target_w / orig_w)
    new_w = int(round(orig_w * ratio))
    new_h = int(round(orig_h * ratio))
    
    # 2) Scale proportionally to new_h, new_w
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # 3) Left, right, top, and bottom padding
    pad_w = target_w - new_w
    pad_h = target_h - new_h
    pad_left = pad_w // 2
    pad_right = pad_w - pad_left
    pad_top = pad_h // 2
    pad_bottom = pad_h - pad_top
    
    # 4) Letterbox
    border_color = (0, 0, 0)
    letterboxed = cv2.copyMakeBorder(
        resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        borderType=cv2.BORDER_CONSTANT,
        value=border_color,
    )
    
    # 5) Convert to NCHW [1, 3, 640, 640] and normalize to [0, 1]
    rgb_img = cv2.cvtColor(letterboxed, cv2.COLOR_BGR2RGB)
    input_img = rgb_img.astype(np.float32) / 255.0
    input_array = np.expand_dims(np.transpose(input_img, (2, 0, 1)), axis=0)
    
    # 6) Save config
    meta = {
            "orig_h": orig_h,
            "orig_w": orig_w,
            "ratio": ratio,
            "pad_left": pad_left,
            "pad_top": pad_top,
            "target_h": target_h,
            "target_w": target_w,
    }

    return image, input_array, meta

def run_inference(input_array):

    result = session.run(None, {inputs: input_array})

    return result

def image_postprocessing(result, meta):
    
    target_h = meta["target_h"]
    target_w = meta["target_w"]
    orig_h = meta["orig_h"]
    orig_w = meta["orig_w"]
    ratio = meta["ratio"]
    pad_left = meta["pad_left"]
    pad_top = meta["pad_top"]

    boxes = torch.from_numpy(result[0])
    scores = torch.from_numpy(result[1])
    mask_coeffs = torch.from_numpy(result[2])
    protos = torch.from_numpy(result[3])

    boxes_xyxy_net = boxes[0] # [8400, 4]
    scores_b = scores[0] # [8400]
    mask_coeffs_b = mask_coeffs[0] # [8400, 32])
    protos_b = protos[0] # [1, 32, 160, 160]
    
    # NMS
    score_thr = args.score_thres
    keep = scores_b > score_thr
    boxes_keep_net = boxes_xyxy_net[keep]
    scores_keep = scores_b[keep]
    coeffs_keep = mask_coeffs_b[keep]
    
    if boxes_keep_net.numel() == 0:
        print("No detections exceed the specified thresholds.")
        print("Please verify the score and IoU values, or try running with --score_thres <value> --iou_thres <value>.")
        sys.exit(0)
        
    else:
        keep_idx = torchvision.ops.nms(boxes_keep_net, scores_keep, iou_threshold = args.iou_thres)
        boxes_keep_net = boxes_keep_net[keep_idx]
        scores_keep = scores_keep[keep_idx]
        coeffs_keep = coeffs_keep[keep_idx]

        # prototypes in low resolution
        c_proto, ph, pw = protos_b.shape
        proto_flat = protos_b.view(c_proto, -1)  # (32, 25600)

        # Low resolution mask logits
        masks_lowres = torch.matmul(coeffs_keep, proto_flat).view(-1, ph, pw)  # (N, 160, 160)
    
    # Map the boxes from the network coordinate system to the prototype feature map space (ph, pw)
    wr = pw / float(target_w)
    hr = ph / float(target_h)
    boxes_keep_lowres = boxes_keep_net.clone()
    boxes_keep_lowres[:, 0] *= wr
    boxes_keep_lowres[:, 2] *= wr
    boxes_keep_lowres[:, 1] *= hr
    boxes_keep_lowres[:, 3] *= hr
    
    # Crop low-resolution mask to its corresponding bounding box (outside region set to zero)
    masks_cropped_lowres = []
    for i in range(masks_lowres.shape[0]):
        m = masks_lowres[i]
        x1i = int(max(0, torch.floor(boxes_keep_lowres[i, 0]).item()))
        y1i = int(max(0, torch.floor(boxes_keep_lowres[i, 1]).item()))
        x2i = int(min(pw, torch.ceil(boxes_keep_lowres[i, 2]).item()))
        y2i = int(min(ph, torch.ceil(boxes_keep_lowres[i, 3]).item()))
        
        crop = torch.zeros_like(m)
        if x2i > x1i and y2i > y1i:
            crop[y1i:y2i, x1i:x2i] = m[y1i:y2i, x1i:x2i]
            
        masks_cropped_lowres.append(crop)
        
    masks_cropped_lowres = torch.stack(masks_cropped_lowres, dim=0)

    # Upsample low-resolution masks to the network resolution
    masks_net = F.interpolate(
        masks_cropped_lowres.unsqueeze(1),
        size=(target_h, target_w),
        mode="bilinear",
        align_corners=False
    ).squeeze(1)

    # Convert logits to probabilities with sigmoid
    masks_prob = masks_net.sigmoid()
    mask_thr = 0.5
    masks_net_bin = (masks_prob > mask_thr).to(torch.uint8)

    # Restore boxes and masks back to the original image coordinate system
    # Boxes: remove letterbox padding, undo scaling, then clip to image bounds
    boxes_keep_orig = boxes_keep_net.clone()
    boxes_keep_orig[:, [0, 2]] = (boxes_keep_orig[:, [0, 2]] - pad_left) / ratio
    boxes_keep_orig[:, [1, 3]] = (boxes_keep_orig[:, [1, 3]] - pad_top) / ratio
    boxes_keep_orig[:, [0, 2]] = boxes_keep_orig[:, [0, 2]].clamp(0, orig_w)
    boxes_keep_orig[:, [1, 3]] = boxes_keep_orig[:, [1, 3]].clamp(0, orig_h)

    # Remove the padding region, then resize back to the original image size
    crop = masks_net_bin[:, pad_top:target_h - pad_top, pad_left:target_w - pad_left]

    masks_orig = F.interpolate(
        crop.unsqueeze(1).float(),
        size=(orig_h, orig_w),
        mode="nearest"
    ).squeeze(1).to(torch.uint8)

    # Crop each mask by its original image bounding box to prevent any spill-over beyond the box
    masks_final = []
    for i in range(masks_orig.shape[0]):
        m = masks_orig[i]
        x1i = int(max(0, torch.floor(boxes_keep_orig[i, 0]).item()))
        y1i = int(max(0, torch.floor(boxes_keep_orig[i, 1]).item()))
        x2i = int(min(orig_w, torch.ceil(boxes_keep_orig[i, 2]).item()))
        y2i = int(min(orig_h, torch.ceil(boxes_keep_orig[i, 3]).item()))
        
        crop_mask = torch.zeros_like(m)
        if x2i > x1i and y2i > y1i:
            crop_mask[y1i:y2i, x1i:x2i] = m[y1i:y2i, x1i:x2i]
            
        masks_final.append(crop_mask)
        
    masks_final = torch.stack(masks_final, dim=0)
    
    return masks_final
    
def show_overlay(image, masks_final):
    
    # Visualization
    overlay = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rng = np.random.default_rng(0)
    colors = rng.integers(0, 255, size=(masks_final.shape[0], 3), dtype=np.uint8)
    alpha = 0.5
    
    for i in range(masks_final.shape[0]):
        mask_np = masks_final[i].cpu().numpy().astype(bool)
        color = colors[i]
        overlay[mask_np] = (overlay[mask_np] * (1 - alpha) + color * alpha).astype(np.uint8)

    plt.figure(figsize=(8, 6))
    plt.imshow(overlay)
    plt.axis('off')
    plt.title("FastSAM Segmentation Overlay")
    plt.show()

def main():
    
    while True:
        try:
            image_path = input("Enter the path to the image file (or type 'exit' to quit): ")
            
            if image_path.lower() == 'exit':
                break

            if not os.path.isfile(image_path):
                print("File does not exist. Please try again.")
                continue

            image, input_image, meta = image_preprocess(image_path)

            output = run_inference(input_image)
            
            mask_final = image_postprocessing(output, meta)
            
            show_overlay(image, mask_final)
        
        except ValueError as e:
            print(e)
            continue

        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Exiting...")
            sys.exit()
  
if __name__ == "__main__":
    main()
