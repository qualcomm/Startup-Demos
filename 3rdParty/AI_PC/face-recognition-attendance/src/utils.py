#===--utils.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import cv2
import numpy as np
import datetime
import os
from PIL import Image

def load_image_from_upload(uploaded_file):
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return image

def save_uploaded_image(uploaded_file, person_name):
    os.makedirs('data/known_faces', exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{person_name}_{timestamp}.jpg"
    file_path = os.path.join('data/known_faces', filename)
    
    img = Image.open(uploaded_file)
    img.save(file_path)
    
    return file_path

def get_image_from_path(image_path):

    image = cv2.imread(image_path)
    return image
