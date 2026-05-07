#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
#===----------------------------------------------------------------------===//

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import threading
import time

## global state

current_status = "OK"      # OK / Fire / Leakage
status_lock = threading.Lock()

FIRE_LABELS = ["Fire", "fire",]
LEAKAGE_LABELS = ["Leakage", "leakage"]

MIN_CONFIDENCE = 0.5

last_decision = "OK"
same_decision_count = 0
DEBOUNCE_COUNT = 3

# Anomaly display duration: show Fire/Leakage for 10 seconds after detection
ANOMALY_DISPLAY_DURATION = 10.0
anomaly_start_time = None
anomaly_type = None  # Store which anomaly was detected (Fire or Leakage)
anomaly_lock = threading.Lock()

# Timeout: if no detection occurs beyond this number of seconds, force the status to OK
TIMEOUT_SECONDS = 1.0
last_detection_time = time.time()


# Web UI & Video Object Detection

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

    found_fire = False
    found_leakage = False

    for label, info in detections.items():
        conf = info.get("confidence", 0.0)
        print(f"[DEBUG] detection label='{label}' confidence={conf}")

        if conf < MIN_CONFIDENCE:
            continue

        l = label.lower()

        # Check for Fire
        if label in FIRE_LABELS or "fire" in l or "flame" in l or "burning" in l:
            found_fire = True
        # Check for Leakage
        elif label in LEAKAGE_LABELS or "leak" in l:
            found_leakage = True

    # Priority order: Fire > Leakage > OK
    # Only Fire and Leakage are considered anomalies, everything else is OK
    if found_fire:
        return "Fire"
    elif found_leakage:
        return "Leakage"
    else:
        # No Fire or Leakage detected, status is OK
        return "OK"


def update_status_with_debounce(new_status: str):
    global last_decision, same_decision_count, current_status, anomaly_start_time, anomaly_type

    # Check if we're in anomaly display period
    with anomaly_lock:
        if anomaly_start_time is not None:
            elapsed = time.time() - anomaly_start_time
            if elapsed < ANOMALY_DISPLAY_DURATION:
                # Still in anomaly display period, keep showing the detected anomaly
                with status_lock:
                    current_status = anomaly_type
                print(f"[DEBUG] Anomaly display active: {anomaly_type} ({elapsed:.1f}s / {ANOMALY_DISPLAY_DURATION}s)")
                return
            else:
                # Anomaly display period ended, reset timer
                print(f"[INFO] Anomaly display period ended for {anomaly_type} (10 seconds elapsed)")
                anomaly_start_time = None
                anomaly_type = None

    if new_status == last_decision:
        same_decision_count += 1
    else:
        last_decision = new_status
        same_decision_count = 1

    if same_decision_count >= DEBOUNCE_COUNT:
        # Check if this is a new Fire or Leakage detection
        if new_status in ["Fire", "Leakage"]:
            with anomaly_lock:
                # Start or restart the anomaly timer
                if anomaly_start_time is None or anomaly_type != new_status:
                    anomaly_start_time = time.time()
                    anomaly_type = new_status
                    print(f"[INFO] {new_status} detected - Starting 10 second display timer")
        
        with status_lock:
            if current_status != new_status:
                print(f"[INFO] Detection status changed: {current_status} -> {new_status}")
            current_status = new_status


# VideoObjectDetection callback

def send_detections_to_ui(detections: dict):
    for key, value in detections.items():
        entry = {
            "content": key,
            "confidence": value.get("confidence"),
            "timestamp": datetime.now(UTC).isoformat(),
            "bbox": value.get("bbox", {})  # Include bounding box coordinates if available
        }
        ui.send_message("detection", message=entry)

    status = decide_status_from_detections(detections)
    update_status_with_debounce(status)


detection_stream.on_detect_all(send_detections_to_ui)


# Timeout background thread: set status to OK if no detection for over 1 second (unless in anomaly display period)

def timeout_watcher():
    global current_status, anomaly_start_time, anomaly_type
    while True:
        now = time.time()
        dt = now - last_detection_time
        
        # Check if we're in anomaly display period
        with anomaly_lock:
            in_anomaly_period = anomaly_start_time is not None and (now - anomaly_start_time) < ANOMALY_DISPLAY_DURATION
        
        if dt > TIMEOUT_SECONDS and not in_anomaly_period:
            with status_lock:
                if current_status != "OK":
                    print(f"[INFO] No detections for {dt:.2f}s -> force OK")
                    current_status = "OK"
        time.sleep(0.1)


# Start the timeout thread
threading.Thread(target=timeout_watcher, daemon=True).start()


# Bridge: For MCU

def get_detection_status():
    with status_lock:
        status = current_status
    print(f"[DEBUG] get_detection_status -> {status}")
    return status

Bridge.provide("get_detection_status", get_detection_status)

App.run()
