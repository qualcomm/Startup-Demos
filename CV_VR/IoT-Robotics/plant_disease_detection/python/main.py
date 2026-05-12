#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_imageclassification import VideoImageClassification
from datetime import datetime, UTC
import threading
import time
import json

## Disease Scenarios Configuration

# Valid plant disease scenarios
DISEASE_SCENARIOS = {
    # Apple diseases
    "Apple_Black_Rot": {"plant": "Apple", "condition": "diseased", "severity": "high"},
    "Apple_Scab": {"plant": "Apple", "condition": "diseased", "severity": "high"},
    "Apple_Healthy": {"plant": "Apple", "condition": "healthy", "severity": "none"},
    
    # Bell Pepper diseases
    "Bell_Pepper_Bacterial_Spot": {"plant": "Bell Pepper", "condition": "diseased", "severity": "medium"},
    "Bell_Pepper_Healthy": {"plant": "Bell Pepper", "condition": "healthy", "severity": "none"},
    
    # Cherry diseases
    "Cherry_Powdery_Mildew": {"plant": "Cherry", "condition": "diseased", "severity": "medium"},
    "Cherry_Healthy": {"plant": "Cherry", "condition": "healthy", "severity": "none"},
    
    # Corn diseases
    "Corn_Common_Rust": {"plant": "Corn", "condition": "diseased", "severity": "medium"},
    "Corn_Northern_Leaf_Blight": {"plant": "Corn", "condition": "diseased", "severity": "high"},
    "Corn_Healthy": {"plant": "Corn", "condition": "healthy", "severity": "none"},
    
    # Grape diseases
    "Grape_Black_Rot": {"plant": "Grape", "condition": "diseased", "severity": "high"},
    "Grape_Leaf_Blight": {"plant": "Grape", "condition": "diseased", "severity": "high"},
    "Grape_Healthy": {"plant": "Grape", "condition": "healthy", "severity": "none"},
    
    # Tomato diseases
    "Tomato_Late_Blight": {"plant": "Tomato", "condition": "diseased", "severity": "high"},
    "Tomato_Mosaic_Virus": {"plant": "Tomato", "condition": "diseased", "severity": "high"},
    "Tomato_Healthy": {"plant": "Tomato", "condition": "healthy", "severity": "none"},
    
    # Potato diseases
    "Potato_Late_Blight": {"plant": "Potato", "condition": "diseased", "severity": "high"},
    "Potato_Early_Blight": {"plant": "Potato", "condition": "diseased", "severity": "high"},
    "Potato_Healthy": {"plant": "Potato", "condition": "healthy", "severity": "none"},
    
    # Strawberry diseases
    "Strawberry_Scorch": {"plant": "Strawberry", "condition": "diseased", "severity": "medium"},
    "Strawberry_Healthy": {"plant": "Strawberry", "condition": "healthy", "severity": "none"},
}

# Helper function to check if a detection is a disease (not healthy)
def is_disease(classification: str) -> bool:
    """Check if the classification represents a disease (not healthy state)"""
    if classification not in DISEASE_SCENARIOS:
        return False
    return DISEASE_SCENARIOS[classification]["condition"] == "diseased"

# Helper function to get disease info
def get_disease_info(classification: str) -> dict:
    """Get detailed information about a disease classification"""
    return DISEASE_SCENARIOS.get(classification, {
        "plant": "Unknown",
        "condition": "unknown",
        "severity": "unknown"
    })

## global state

current_status = "Unknown"      # Plant disease status or Unknown
status_lock = threading.Lock()

MIN_CONFIDENCE = 0.5

last_decision = "Unknown"
same_decision_count = 0
DEBOUNCE_COUNT = 3

# Timeout: if no detection occurs beyond this number of seconds, force the status to Unknown
TIMEOUT_SECONDS = 1.0
last_detection_time = time.time()

# Track last detection for buzzer control (with lock protection)
last_detected_disease = None
detection_timestamp = 0
detection_lock = threading.Lock()  # Add lock for buzzer state


# Web UI & Video Image Classification

ui = WebUI()
detection_stream = VideoImageClassification(confidence=MIN_CONFIDENCE, debounce_sec=0.0)

ui.on_message("override_th",
              lambda sid, threshold: detection_stream.override_threshold(threshold))


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
                print(f"[INFO] Detection status changed: {current_status} -> {new_status}")
            current_status = new_status


# VideoImageClassification callback

def send_classifications_to_ui(classifications: dict):
    global last_detection_time, last_detected_disease, detection_timestamp
    
    if len(classifications) == 0:
        print("[DEBUG] classifications is empty (no detections this frame)")
        return
    
    # Update last detection time
    last_detection_time = time.time()
    
    entries = []
    best_classification = None
    best_confidence = 0.0
    
    for key, value in classifications.items():
        confidence = value if isinstance(value, float) else value.get("confidence", 0.0)
        
        entry = {
            "content": key,
            "confidence": confidence,
            "timestamp": datetime.now(UTC).isoformat()
        }
        entries.append(entry)
        
        # Validate against known disease scenarios
        if key in DISEASE_SCENARIOS:
            disease_info = get_disease_info(key)
            print(f"[DEBUG] classification label='{key}' confidence={confidence} | "
                  f"Plant: {disease_info['plant']}, Condition: {disease_info['condition']}, "
                  f"Severity: {disease_info['severity']}")
        else:
            print(f"[DEBUG] classification label='{key}' confidence={confidence} (unknown scenario)")
        
        # Track the best classification
        if confidence > best_confidence:
            best_confidence = confidence
            best_classification = key
    
    # Send all classifications to UI
    if len(entries) > 0:
        msg = json.dumps(entries)
        ui.send_message("classifications", message=msg)
    
    # Update status based on best classification
    if best_classification and best_confidence >= MIN_CONFIDENCE:
        current_time = time.time()
        with detection_lock:  # Protect shared state
            if (last_detected_disease != best_classification or 
                (current_time - detection_timestamp) > 5.0):
                last_detected_disease = best_classification
                detection_timestamp = current_time
                print(f"[INFO] New plant disease detected: {best_classification} (confidence: {best_confidence:.2f})")
        
        update_status_with_debounce(best_classification)
    else:
        update_status_with_debounce("Unknown")


detection_stream.on_detect_all(send_classifications_to_ui)


# Timeout background thread: set status to Unknown if no detection for over 1 second

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


# Bridge: For MCU

def get_detection_status():
    with status_lock:
        status = current_status
    print(f"[DEBUG] get_detection_status -> {status}")
    return status

def should_trigger_buzzer():
    """Check if buzzer should be triggered based on new detection"""
    with detection_lock:  # Protect shared state
        current_time = time.time()
        
        # Trigger buzzer only for diseased plants (not healthy ones)
        if last_detected_disease and last_detected_disease != "Unknown":
            time_since_detection = current_time - detection_timestamp
            is_recent = time_since_detection < 5.0
            is_diseased = is_disease(last_detected_disease)
            should_trigger = is_recent and is_diseased
            
            if is_recent:
                disease_info = get_disease_info(last_detected_disease)
                print(f"[DEBUG] should_trigger_buzzer -> {should_trigger} | "
                      f"Disease: {last_detected_disease}, Condition: {disease_info['condition']}, "
                      f"Severity: {disease_info['severity']}, Time since: {time_since_detection:.2f}s")
            
            return should_trigger
        
    return False

Bridge.provide("get_detection_status", get_detection_status)
Bridge.provide("should_trigger_buzzer", should_trigger_buzzer)

App.run()
