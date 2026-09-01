#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import time
from types import SimpleNamespace

from arduino.app_utils import App, Logger
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection

log = Logger("PeopleDetection")

# -----------------------------------------------------------------------------
# 1. CONFIGURATION
# -----------------------------------------------------------------------------
PERSON_LABEL = "person"   # must match the label used in your Edge Impulse project
CONFIDENCE   = 0.5        # minimum confidence (0-1) to accept a detection
DEBOUNCE_SEC = 0.0        # 0 = report every frame (good for live counting)

# -----------------------------------------------------------------------------
# 2. INSTANTIATE THE BRICKS
# -----------------------------------------------------------------------------
# WebUI: serves ./assets and opens a Socket.IO channel on port 7000.
ui = WebUI()

# VideoObjectDetection: with no camera argument it defaults to the USB camera
# declared in app.yaml (usb_camera_0). It automatically loads the FOMO model
# you place in ./models (or the one selected in the App Lab Brick settings).
detection_stream = VideoObjectDetection(
    confidence=CONFIDENCE,
    debounce_sec=DEBOUNCE_SEC,
)

# Expose the live camera stream to the WebUI at /video_stream.
# This uses the same camera instance from the detection brick.
ui.expose_camera("/video_stream", detection_stream._camera)

# Shared state pushed to the browser
_last_seen = 0.0


# -----------------------------------------------------------------------------
# 3. DETECTION CALLBACKS
# -----------------------------------------------------------------------------
def send_detections_to_ui(detections):
    """Called by the Brick on every processed frame with ALL detections.

    `detections` can be either:
      - a dict from label to list of detection dicts (the current VideoObjectDetection output)
      - a list of detection-like objects.
    """
    global _last_seen

    normalized = []
    if isinstance(detections, dict):
        for label, items in detections.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                bbox = item.get("bounding_box_xyxy", ())
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    x, y, x2, y2 = bbox
                    width = max(0, x2 - x)
                    height = max(0, y2 - y)
                else:
                    x = y = width = height = 0
                normalized.append(SimpleNamespace(
                    label=label,
                    confidence=item.get("confidence", 0.0),
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                ))
    else:
        normalized = detections

    # Keep only people above the confidence threshold.
    people = [d for d in normalized
              if getattr(d, "label", "").lower() == PERSON_LABEL
              and getattr(d, "confidence", 0) >= CONFIDENCE]

    count = len(people)
    best = max((d.confidence for d in people), default=0.0)

    # Get frame dimensions from the detection stream
    frame_width = getattr(detection_stream, 'frame_width', 640)
    frame_height = getattr(detection_stream, 'frame_height', 480)
    
    # Initialize zone counters
    zone_0_count = 0
    zone_1_count = 0
    zone_2_count = 0
    zone_3_count = 0
    
    # Process each person and assign to zones
    detection_details = []
    for idx, person in enumerate(people, 1):
        # Get bounding box coordinates
        x = getattr(person, 'x', 0)
        y = getattr(person, 'y', 0)
        width = getattr(person, 'width', 0)
        height = getattr(person, 'height', 0)
        confidence = getattr(person, 'confidence', 0)
        
        # Calculate center point
        center_x = x + (width / 2)
        center_y = y + (height / 2)
        
        # Determine zone based on center_x
        if center_x < frame_width * 0.25:
            zone = 0
            zone_0_count += 1
        elif center_x < frame_width * 0.50:
            zone = 1
            zone_1_count += 1
        elif center_x < frame_width * 0.75:
            zone = 2
            zone_2_count += 1
        else:
            zone = 3
            zone_3_count += 1
        
        # Build detection detail object
        detection_details.append({
            "person_id": idx,
            "label": "person",
            "confidence": round(confidence, 2),
            "zone": zone,
            "bbox": {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height)
            }
        })

    # Build payload with zone information
    payload = {
        "total_people_count": count,
        "confidence": round(best * 100, 1),
        "timestamp": time.strftime("%H:%M:%S"),
        "frame_width": frame_width,
        "frame_height": frame_height,
        "zone_counts": {
            "zone_0": zone_0_count,
            "zone_1": zone_1_count,
            "zone_2": zone_2_count,
            "zone_3": zone_3_count
        },
        "detections": detection_details
    }

    # Broadcast to every connected browser (no client arg = broadcast).
    ui.send_message("detection", payload)

    # Print to serial terminal with zone information
    print("\n" + "=" * 50)
    print("People Detection Result")
    print("=" * 50)
    print()
    print(f"Zone 0 Count: {zone_0_count}")
    print(f"Zone 1 Count: {zone_1_count}")
    print(f"Zone 2 Count: {zone_2_count}")
    print(f"Zone 3 Count: {zone_3_count}")
    print()
    print(f"Total People Count: {count}")
    print()
    if count > 0:
        print("Detection Details:")
        for det in detection_details:
            print(f"Person {det['person_id']} -> Zone {det['zone']}")
    print()

    # Log detection events
    if count > 0:
        _last_seen = time.time()
        log.info(f"👤 {count} person(s) detected | Zones: [0:{zone_0_count}, 1:{zone_1_count}, 2:{zone_2_count}, 3:{zone_3_count}]")


def on_person(detection):
    """Fires only for the 'person' label - handy for single-event logic."""
    log.debug(f"person @ {getattr(detection, 'confidence', 0):.2f}")


# -----------------------------------------------------------------------------
# 4. WEB UI -> BACKEND CONTROLS (Socket.IO events from the browser)
# -----------------------------------------------------------------------------
def override_threshold(client, data):
    """Browser slider changes the live confidence threshold."""
    try:
        value = float(data.get("value", CONFIDENCE))
        value = max(0.0, min(1.0, value))
        detection_stream.override_threshold(value)
        log.info(f"Threshold updated to {value:.2f}")
        ui.send_message("threshold_ack", {"value": value})
    except Exception as e:
        log.warning(f"override_threshold error: {e}")


# Simple health endpoint (open http://<board>.local:7000/health)
ui.expose_api("GET", "/health", lambda: {"status": "ok", "label": PERSON_LABEL})

# Wire up the events
ui.on_message("override_th", override_threshold)     # slider from the dashboard
detection_stream.on_detect_all(send_detections_to_ui)  # every frame
detection_stream.on_detect(PERSON_LABEL, on_person)    # person-only hook


# -----------------------------------------------------------------------------
# 5. LAUNCH  (App.run() starts every registered Brick and blocks)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    log.info("Starting People Detection app on http://<board>.local:7000")
    App.run()
