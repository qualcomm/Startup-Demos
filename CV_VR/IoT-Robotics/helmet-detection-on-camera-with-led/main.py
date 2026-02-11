#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import threading
import time

# ---------------------------------------------------------
# global state
# ---------------------------------------------------------
current_status = "Unknown"      # Helmet / No Helmet / Unknown
status_lock = threading.Lock()

HELMET_LABELS = ["Helmet", "helmet"]
NO_HELMET_LABELS = ["No Helmet", "no helmet", "no_helmet", "no-helmet"]

MIN_CONFIDENCE = 0.5

last_decision = "Unknown"
same_decision_count = 0
DEBOUNCE_COUNT = 3

# Timeout: if no detection occurs beyond this number of seconds, force the status to Unknown
TIMEOUT_SECONDS = 1.0
last_detection_time = time.time()

# ---------------------------------------------------------
# Web UI & Video Object Detection
# ---------------------------------------------------------
ui = WebUI()
detection_stream = VideoObjectDetection(confidence=MIN_CONFIDENCE, debounce_sec=0.0)

ui.on_message("override_th",
           lambda sid, threshold: detection_stream.override_threshold(threshold))


def decide_status_from_detections(detections: dict) -> str:
 global last_detection_time

 # If there are any detections, update last_detection_time
 if detections:
     last_detection_time = time.time()
 else:
     print("[DEBUG] detections is empty (no boxes this frame)")

 found_helmet = False
 found_no_helmet = False

 for label, info in detections.items():
     conf = info.get("confidence", 0.0)
     print(f"[DEBUG] detection label='{label}' confidence={conf}")

     if conf < MIN_CONFIDENCE:
         continue

     l = label.lower()

     if label in HELMET_LABELS or ("helmet" in l and "no" not in l):
         found_helmet = True
     elif label in NO_HELMET_LABELS or ("no" in l and "helmet" in l):
         found_no_helmet = True

 if found_no_helmet and not found_helmet:
     return "No Helmet"
 elif found_helmet and not found_no_helmet:
     return "Helmet"
 elif found_helmet and found_no_helmet:
     return "No Helmet"
 else:
     # Although this frame contains detections, all of them are below the threshold or have unrecognized labels
     return "Unknown"


def update_status_with_debounce(new_status: str):
 global last_decision, same_decision_count, current_status

 if new_status == last_decision:
     same_decision_count += 1
 else:
     last_decision = new_status
     same_decision_count = 1

 if same_decision_count >= DEBOUNCE_COUNT:
     with status_lock:
         if current_status != new_status:
             print(f"[INFO] Helmet status changed: {current_status} -> {new_status}")
         current_status = new_status


# ---------------------------------------------------------
# VideoObjectDetection callback
# ---------------------------------------------------------
def send_detections_to_ui(detections: dict):
 for key, value in detections.items():
     entry = {
         "content": key,
         "confidence": value.get("confidence"),
         "timestamp": datetime.now(UTC).isoformat()
     }
     ui.send_message("detection", message=entry)

 status = decide_status_from_detections(detections)
 update_status_with_debounce(status)


detection_stream.on_detect_all(send_detections_to_ui)

# ---------------------------------------------------------
# Timeout background thread: set status to Unknown if no detection for over 1 second
# ---------------------------------------------------------
def timeout_watcher():
 global current_status
 while True:
     now = time.time()
     dt = now - last_detection_time
     if dt > TIMEOUT_SECONDS:
         with status_lock:
             if current_status != "Unknown":
                 print(f"[INFO] No detections for {dt:.2f}s -> force Unknown")
                 current_status = "Unknown"
     time.sleep(0.1)


# Start the timeout thread
threading.Thread(target=timeout_watcher, daemon=True).start()

# ---------------------------------------------------------
# Bridge: For MCU
# ---------------------------------------------------------
def get_helmet_status():
 with status_lock:
     status = current_status
 print(f"[DEBUG] get_helmet_status -> {status}")
 return status


Bridge.provide("get_helmet_status", get_helmet_status)

# ---------------------------------------------------------
# main
# ---------------------------------------------------------
App.run()