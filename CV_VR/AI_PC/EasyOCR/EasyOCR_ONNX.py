#===--EasyOCR_ONNX.py-----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from __future__ import annotations
import argparse
import os
import sys
import onnxruntime as ort
import torch
from PIL import Image
from qai_hub_models.models.easyocr.app import EasyOCRApp
import numpy as np


# onnxruntime-qnn inference session
def create_session(model_path: str, qnn_path: str) -> ort.InferenceSession:
    so = ort.SessionOptions()
    so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

    ep_options = {
        "backend_path": qnn_path,
        "enable_htp_fp16_precision": "1",
        "htp_performance_mode": "burst",
        "htp_graph_finalization_optimization_mode": "1",
    }

    return ort.InferenceSession(
        model_path,
        sess_options=so,
        providers=["QNNExecutionProvider"],
        provider_options=[ep_options]
    )


# Build a callable detector function that matches EasyOCRApp expectation
def build_detector(session: ort.InferenceSession):
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    def detector(x: torch.Tensor) -> torch.Tensor:
        # Convert Torch tensor -> numpy for ORT
        x_np = x.detach().cpu().numpy()
        
        # Run inference
        y_np = session.run([output_name], {input_name: x_np})[0]

        # Convert numpy -> Torch tensor
        return torch.from_numpy(y_np)

    return detector


# Build a callable recognizer function that matches EasyOCRApp expectation
def build_recognizer(session: ort.InferenceSession):
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    def recognizer(x: torch.Tensor) -> torch.Tensor:
        # Convert Torch tensor -> numpy for ORT
        x_np = x.detach().cpu().numpy()
        
        if x_np.ndim == 5 and x_np.shape[2] == 1:
            x_np = np.squeeze(x_np, axis=2)  # (1,1,1,64,800) -> (1,1,64,800)

        # Run inference
        y_np = session.run([output_name], {input_name: x_np})[0]

        # Convert numpy -> Torch tensor
        return torch.from_numpy(y_np)

    return recognizer


# OCR runner
def run_ocr_on_image(app: EasyOCRApp, image_path: str):
    img = Image.open(image_path).convert("RGB")
    
    outputs = app.predict_text_from_image(img)

    # EasyOCRApp returns a list
    out_img, texts, confidences = outputs[0]

    # Create output filename
    base = os.path.splitext(os.path.basename(image_path))[0]
    out_path = os.path.join(os.path.dirname(image_path), f"{base}_ocr.jpg")

    out_img.save(out_path)
    
    return out_path, texts, confidences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qnn_path", default="QnnHtp.dll", help="Path to QnnHtp.dll")
    parser.add_argument("--det_model", required=True, help="detector onnx")
    parser.add_argument("--recog_model", required=True, help="recognizer onnx")
    args = parser.parse_args()

    # Load QNN sessions
    det_sess = create_session(args.det_model, args.qnn_path)
    rec_sess = create_session(args.recog_model, args.qnn_path)

    # Build callables for EasyOCRApp
    detector = build_detector(det_sess)
    recognizer = build_recognizer(rec_sess)

    # Infer model input shapes
    det_inp = det_sess.get_inputs()[0].shape  # [1, 3, H, W]
    rec_inp = rec_sess.get_inputs()[0].shape  # [1, 1, H, W]

    detector_img_shape = (int(det_inp[2]), int(det_inp[3]))
    recognizer_img_shape = (int(rec_inp[2]), int(rec_inp[3]))

    # Create EasyOCR app
    app = EasyOCRApp(
        detector=detector,
        recognizer=recognizer,
        detector_img_shape=detector_img_shape,
        recognizer_img_shape=recognizer_img_shape,
        lang_list=["en"],
        decoder_mode="greedy",
    )

    while True:
        try:
            image_path = input("Enter the path to the image file (or type 'exit' to quit): ").strip()
            
            if image_path.lower() == "exit":
                break

            if not os.path.isfile(image_path):
                print("File does not exist. Please try again.")
                continue
            
            out_path, texts, confidences = run_ocr_on_image(app, image_path)

            print("\n=== OCR Result ===")
            for t, c in zip(texts, confidences):
                print(f"{t}  ({float(c):.3f})")

            print("Saved:", out_path)
            
            img = Image.open(out_path)
            img.show()
            
        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Exiting...")
            sys.exit()

        except Exception as e:
            print("Error:", e)
            continue


if __name__ == "__main__":
    main()
