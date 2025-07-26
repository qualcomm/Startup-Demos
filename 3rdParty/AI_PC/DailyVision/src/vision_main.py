# //===-----------------vision_main.py----------------------------------------===//
# // Part of the Startup-Demos Project, under the MIT License
# // See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# // for license information.
# // Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# // SPDX-License-Identifier: MIT License
# //===----------------------------------------------------------------------===//

import argparse
import cv2
import multiprocessing
from detection import detect_objects
from ocr import perform_ocr
from audio import speak_text

# Main function to invoke the application 
def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run object detection and OCR on an image.")
    parser.add_argument("image_path", type=str, help="Path to the input image")
    args = parser.parse_args()

    # Load image
    image = cv2.imread(args.image_path)
    if image is None:
        print(f"Error: Could not load image from {args.image_path}")
        return

    # Run detection
    results, labels_texts = detect_objects(image, args.image_path)

    # Speak results
    if labels_texts:
        for label, text in labels_texts:
            spoken_text = f"Detected a {label}: {text}"
            print("spoken_text", spoken_text)
            speak_text(spoken_text)
    else:
        text = perform_ocr(args.image_path)
        spoken_text = f"Detected text: {text}"
        print("spoken_text", spoken_text)
        speak_text(spoken_text)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
