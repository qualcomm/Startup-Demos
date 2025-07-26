# //===----------------detection.py-----------------------------------------===//
# // Part of the Startup-Demos Project, under the MIT License
# // See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# // for license information.
# // Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# // SPDX-License-Identifier: MIT License
# //===----------------------------------------------------------------------===//

from ultralytics import YOLO
import cv2
from PIL import Image
import numpy as np
from ocr import perform_ocr
from utils import classify_traffic_light

# Detecting objects via Yolov8 Model
def detect_objects(image, image_path):
    yolo_model = YOLO('yolov8l.pt')
    results = yolo_model(image)
    labels_texts = []

    if any(len(result.boxes) > 0 for result in results):
        annotated_image = results[0].plot()
        cv2.imwrite("annotated_output.jpg", annotated_image)
        Image.open("annotated_output.jpg").show()

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cropped = image[y1:y2, x1:x2]
                label = yolo_model.names[int(box.cls[0])] if hasattr(box, 'cls') else "object"

                if label == "traffic light":
                    color = classify_traffic_light(cropped)
                    labels_texts.append((label, f"with color: {color}"))
                else:
                    cv_image = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
                    temp_path = "temp.jpg"
                    Image.fromarray(cv_image).save(temp_path)
                    text = perform_ocr(temp_path)
                    labels_texts.append((label, text))

    return results, labels_texts
