#===--SuperResolution_ONNX.py---------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import os
import sys
import argparse
import numpy as np
import cv2
import onnxruntime as ort
import matplotlib.pyplot as plt


# Load input image and convert to RGB
def load_rgb(path: str) -> np.ndarray:
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
 

# Save super resolution output image 
def save_rgb(path: str, rgb: np.ndarray) -> None:
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    output = cv2.imwrite(path, bgr)
    if not output:
        raise RuntimeError(f"cv2.imwrite failed: {path}")


# Add padding to the corners for patch inference
def reflect_pad_rgb(rgb: np.ndarray, pad_bottom: int, pad_right: int) -> np.ndarray:
    if pad_bottom == 0 and pad_right == 0:
        return rgb
    return cv2.copyMakeBorder(
        rgb, 0, pad_bottom, 0, pad_right, borderType=cv2.BORDER_REFLECT_101
    )


# Crop center 30% region to better see fine details and create a side-by-side comparison image
def compare_image(before_rgb: np.ndarray,
                  after_rgb: np.ndarray,
                  labels=("Before", "After"),
                  crop_ratio=0.30,    # Configurable crop ratio
                  divider_px=6) -> np.ndarray:

    # Ensure both are RGB uint8
    before = before_rgb.astype(np.uint8)
    after  = after_rgb.astype(np.uint8)

    Hb, Wb = before.shape[:2]
    Ha, Wa = after.shape[:2]
    
    # Resize before image to match after image height
    scale = Ha / Hb
    new_w = int(round(Wb * scale))
    before_rs = cv2.resize(before, (new_w, Ha), interpolation=cv2.INTER_LINEAR)
    
    # Crop center with crop_ratio
    ch = max(1, int(Ha * crop_ratio))
    cw = max(1, int(min(new_w, Wa) * crop_ratio))

    y0 = (Ha - ch) // 2
    x0_b = (new_w - cw) // 2
    x0_a = (Wa - cw) // 2

    before_crop = before_rs[y0:y0 + ch, x0_b:x0_b + cw]
    after_crop  = after[y0:y0 + ch,  x0_a:x0_a + cw]

    # Add white line
    divider = np.full((ch, divider_px, 3), 255, dtype=np.uint8)
    out = np.hstack([before_crop, divider, after_crop])

    # Labels
    if labels:
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(out, labels[0], (20, 50), font, 1.5, (255, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, labels[1], (before_crop.shape[1] + divider_px + 20, 50),
                    font, 1.5, (0, 255, 0), 3, cv2.LINE_AA)
    
    # Show image
    plt.figure(figsize=(12, 6))
    plt.imshow(out)
    plt.axis('off')
    plt.title(f"Super resolution center {int(crop_ratio*100)}% region comparison")
    plt.tight_layout(pad=0.3)
    plt.show()
    
    return out

# Convert RGB HWC [128, 128, 3] to NCHW float32 [1, 3, 128, 128]
def rgb_to_nchw_input(rgb_128: np.ndarray) -> np.ndarray:
    x = rgb_128
    x = np.transpose(x, (2, 0, 1))    # HWC to CHW
    x = np.expand_dims(x, 0)          # NCHW
    return (x.astype(np.float32) / 255.0)


# Convert model output to RGB uint8 HWC
def output_to_rgb_uint8(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y)

    # Remove batch dim and convert to HWC
    y0 = y[0]
    y0 = np.transpose(y0, (1, 2, 0))

    # uint8 output
    y0 = y0.astype(np.float32)
    y0 = np.clip(y0, 0.0, 1.0) * 255.0
    
    # Add 0.5 before cast to perform rounding instead of truncation
    return (y0 + 0.5).astype(np.uint8)


# Onnxruntime-qnn inference session
def create_session(model_path: str, qnn_path: str) -> ort.InferenceSession:
    so = ort.SessionOptions()
    so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

    ep_options = {
                  "backend_path": qnn_path,
                  "enable_htp_fp16_precision": "1",
                  "htp_performance_mode": "burst",
                  "htp_graph_finalization_optimization_mode": "3"
                 }

    return ort.InferenceSession(model_path, 
                                sess_options=so, 
                                providers=["QNNExecutionProvider"], 
                                provider_options=[ep_options])


# End-to-end patch inference and post-processing
def run_inference(
    sess: ort.InferenceSession,
    rgb: np.ndarray,
    tile: int = 128,
    scale: int = 4,
) -> np.ndarray:

    inp = sess.get_inputs()[0]
    out_node = sess.get_outputs()[0]

    h, w = rgb.shape[:2]
    pad_h = (tile - (h % tile)) % tile
    pad_w = (tile - (w % tile)) % tile
    rgb_pad = reflect_pad_rgb(rgb, pad_h, pad_w)
    H, W = rgb_pad.shape[:2]

    out_pad = np.zeros((H * scale, W * scale, 3), dtype=np.uint8)

    for y in range(0, H, tile):
        for x in range(0, W, tile):
            patch = rgb_pad[y:y+tile, x:x+tile, :]
            x_in = rgb_to_nchw_input(patch)

            y_out = sess.run([out_node.name], {inp.name: x_in})[0]
            patch_out = output_to_rgb_uint8(y_out)

            oy, ox = y * scale, x * scale
            out_pad[oy:oy+patch_out.shape[0], ox:ox+patch_out.shape[1], :] = patch_out

    return out_pad[:h*scale, :w*scale, :]


def main():
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_path", required=True, help="Path to ONNX model")
    ap.add_argument("--qnn_path", type=str, default="QnnHtp.dll", help="Path to QnnHtp.dll")
    args = ap.parse_args()

    sess = create_session(args.model_path, args.qnn_path)
    
    while True:
        try:
            image_path = input("Enter the path to the image file (or type 'exit' to quit): ")
            
            if image_path.lower() == 'exit':
                break

            if not os.path.isfile(image_path):
                print("File does not exist. Please try again.")
                continue
            
            rgb = load_rgb(image_path)
            
            out_rgb = run_inference(sess, rgb)
            
            # Save output image
            base = os.path.splitext(os.path.basename(image_path))[0]
            out_path = os.path.join(os.path.dirname(image_path), f"{base}_x4.jpg")
            save_rgb(out_path, out_rgb)
            print("Saved:", out_path)
            
            compare_image(rgb, out_rgb)

        except Exception as e:
            print("Error:", e)
            continue

        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Exiting...")
            sys.exit()
            
if __name__ == "__main__":
    main()
