#===--Image_Classification_ONNX.py----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import onnxruntime
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import os
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--onnx_path', type=str, required=True, help='Path to ONNX model')
parser.add_argument('--qnn_path', type=str, required=True, help='Path to QnnHtp.dll')
args = parser.parse_args()

options = onnxruntime.SessionOptions()

# (Optional) Enable configuration that raises an exception if the model can't be run entirely on the QNN HTP backend.
options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

ep_options = {
              "backend_path": args.qnn_path,
              "enable_htp_fp16_precision": "1",
              "htp_performance_mode": "burst",
              "htp_graph_finalization_optimization_mode": "3"
             }
             
# Create an ONNX Runtime session.
session = onnxruntime.InferenceSession(args.onnx_path,
                                       sess_options=options,
                                       providers=["QNNExecutionProvider"],
                                       provider_options=[ep_options])

inputs = session.get_inputs()[0].name

def image_preprocess(image_path):

    # Convert the image to numpy array of shape [1, 3, 224, 224]
    image = Image.open(image_path).convert("RGB").resize((224, 224))
    
    show_image = Image.open(image_path).convert("RGB").resize((512, 512))
    
    img_array = np.array(image, dtype=np.float32)

    # Ensure correct layout (NCHW) and re-scale
    input_array = np.expand_dims(np.transpose(img_array / 255.0 , (2, 0, 1)), axis=0)
    
    return input_array, show_image
    
def run_inference(input_array):

    result = session.run(None, {inputs: input_array})

    return result[0]

def image_postprocessing(out, show_image):

    on_device_probabilities = np.exp(out) / np.sum(np.exp(out), axis=1)

    # Read the class labels for imagenet
    with open("imagenet_classes.txt", "r") as f:
        categories = [s.strip() for s in f.readlines()]

    # Print top five predictions for the on-device model
    top5_classes = np.argsort(on_device_probabilities[0], axis=0)[-5:]
    
    # Display categories on the image
    draw = ImageDraw.Draw(show_image)
    
    try:
        font = ImageFont.truetype("calibrib.ttf", size=20)
    except IOError:
        font = ImageFont.load_default()

    y_offset = 10
    
    draw.text((10, y_offset), "Top-5 Predictions :", fill="Yellow", font=font)
    
    y_offset += 20

    for c in reversed(top5_classes):
        label = f"{categories[c]} : {on_device_probabilities[0][c]:.1%}"
        
        draw.text((10, y_offset), label, fill="White", font=font)
        
        y_offset += 20

    show_image.show()

def main():
    while True:
        try:
            image_path = input("Enter the path to the image file (or type 'exit' to quit): ")
            
            if image_path.lower() == 'exit':
                break

            if not os.path.isfile(image_path):
                print("File does not exist. Please try again.")
                continue

            img, show_image = image_preprocess(image_path)

            output = run_inference(img)
            
            image_postprocessing(output, show_image)

        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Exiting...")
            sys.exit()
  
if __name__ == "__main__":
    main()
