# //===------DailyVision-src\utils.py-----------------------------------------===//
# // Part of the Startup-Demos Project, under the MIT License
# // See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# // for license information.
# // Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# // SPDX-License-Identifier: MIT License
# // Project done by - Vishnudatta (vindraga@qti.qualcomm.com)
# //===----------------------------------------------------------------------===//

import cv2
import numpy as np

def classify_traffic_light(cropped_image):
    hsv = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2HSV)

    red_lower1 = np.array([0, 100, 100])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([160, 100, 100])
    red_upper2 = np.array([180, 255, 255])
    yellow_lower = np.array([15, 100, 100])
    yellow_upper = np.array([35, 255, 255])
    green_lower = np.array([40, 100, 100])
    green_upper = np.array([90, 255, 255])

    mask_red1 = cv2.inRange(hsv, red_lower1, red_upper1)
    mask_red2 = cv2.inRange(hsv, red_lower2, red_upper2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)
    mask_green = cv2.inRange(hsv, green_lower, green_upper)

    red_percentage = np.sum(mask_red) / (cropped_image.shape[0] * cropped_image.shape[1])
    yellow_percentage = np.sum(mask_yellow) / (cropped_image.shape[0] * cropped_image.shape[1])
    green_percentage = np.sum(mask_green) / (cropped_image.shape[0] * cropped_image.shape[1])

    if red_percentage > yellow_percentage and red_percentage > green_percentage:
        return "red"
    elif yellow_percentage > red_percentage and yellow_percentage > green_percentage:
        return "yellow"
    else:
        return "green"
