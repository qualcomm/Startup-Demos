# //===-----------------vision_main.py----------------------------------------===//
# // Part of the Startup-Demos Project, under the MIT License
# // See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# // for license information.
# // Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# // SPDX-License-Identifier: MIT License
# //===----------------------------------------------------------------------===//

from detection import detect_objects
from ocr import perform_ocr
from audio import speak_text
import cv2
import multiprocessing

# Main function to invoke the application 
def main():
    image_path = "..\\images\\traffic.jpeg"
    image = cv2.imread(image_path)

    results, labels_texts = detect_objects(image, image_path)

    if labels_texts:
        for label, text in labels_texts:
            spoken_text = f"Detected a {label}: {text}"
            print(spoken_text)
            speak_text(spoken_text)
    else:
        text = perform_ocr(image_path)
        spoken_text = f"Detected text: {text}"
        print(spoken_text)
        speak_text(spoken_text)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
