#===--main.py---------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import os
import re
import secrets
import string
import threading
import time
import base64
from datetime import datetime, UTC

import numpy as np
from PIL import Image
import io

from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
from arduino.app_peripherals.camera import Camera, WebSocketCamera

from face_recognizer import FaceRecognizer
from webui_assets import write_assets

ENROLL_SAMPLES_REQUIRED = 5
ENROLL_SAMPLE_MIN_INTERVAL_SEC = 1.0
MATCH_STREAK_REQUIRED = 5  # consecutive matches needed (i.e. must exceed this) before granting access
ENROLL_NAME_MAX_LENGTH = 40  # matches the enrollNameInput maxlength in assets/index.html
ENROLL_NAME_ALLOWED_CHARS = re.compile(r"[^\w \-']", re.UNICODE)  # strip anything but letters/digits/spaces/hyphens/apostrophes

LED_REFRESH_INTERVAL_SEC = 0.1  # how often to refresh the LED matrix from the latest detection state
FACE_ANNOTATION_TTL_SEC = 1.5  # how long to keep showing the last face box/label after a detection
BBOX_MARGIN_RATIO = 0.2  # expand the detected face bbox by this fraction (per side) before recognition

LED_ROWS, LED_COLS = 8, 13  # built-in LED matrix size

# Set to a USB camera source (e.g. "usb:0" or "/dev/video0") to use a USB webcam
# plugged into the board instead of pairing a phone camera over the network.
# When set, the QR-code pairing flow is skipped entirely.
USB_CAMERA_DEVICE = None


def generate_secret() -> str:
  characters = string.digits
  return ''.join(secrets.choice(characters) for _ in range(6))

using_usb_camera = USB_CAMERA_DEVICE is not None
secret = None if using_usb_camera else generate_secret()

write_assets(os.path.join(os.path.dirname(__file__), "..", "assets"))

ui = WebUI()  # set use_tls=True to enable TLS encryption for HTTPS
camera = Camera(USB_CAMERA_DEVICE) if using_usb_camera else WebSocketCamera(secret=secret, encrypt=True)
camera.on_status_changed(lambda evt_type, data: ui.send_message(evt_type, data))

db = SQLStore()
db.start()
recognizer = FaceRecognizer(db)

detection = VideoObjectDetection(camera, confidence=0.5, debounce_sec=0.0, camera_preview=True)

pending_enrollment_lock = threading.Lock()
pending_enrollment = None  # {"name": str, "count": int, "last_capture": float}

match_streak_lock = threading.Lock()
match_streak_name = None
match_streak_count = 0

last_annotation_lock = threading.Lock()
last_annotation = None  # {"bbox_xyxy": tuple, "label": str, "state": str, "time": float}

def handle_ui_connect(sid):
  welcome = {"client_name": camera.name, "status": camera.status, "using_usb_camera": using_usb_camera}
  if not using_usb_camera:
    welcome.update({"secret": secret, "protocol": camera.protocol, "ip": camera.ip, "port": camera.port})
  ui.send_message("welcome", welcome)
  ui.send_message("faces_list", {"names": recognizer.list_enrolled()})

ui.on_connect(handle_ui_connect)
ui.on_message("override_th", lambda sid, threshold: detection.override_threshold(threshold))


def handle_enroll_face(sid, data):
  global pending_enrollment
  name = (data or {}).get("name", "").strip()[:ENROLL_NAME_MAX_LENGTH]
  name = ENROLL_NAME_ALLOWED_CHARS.sub("", name).strip()
  if not name:
    return
  with pending_enrollment_lock:
    pending_enrollment = {"name": name, "count": 0, "last_capture": 0.0}

ui.on_message("enroll_face", handle_enroll_face)


def handle_delete_face(sid, data):
  name = (data or {}).get("name", "").strip()
  if not name:
    return
  recognizer.delete(name)
  ui.send_message("faces_list", {"names": recognizer.list_enrolled()})

ui.on_message("delete_face", handle_delete_face)


def expand_bbox(bbox_xyxy: tuple, image_size: tuple, margin_ratio: float) -> tuple:
  """Expand a bounding box by margin_ratio per side, clamped to image bounds."""
  x0, y0, x1, y1 = bbox_xyxy
  width, height = image_size
  margin_x = (x1 - x0) * margin_ratio
  margin_y = (y1 - y0) * margin_ratio
  return (
    int(max(0, x0 - margin_x)),
    int(max(0, y0 - margin_y)),
    int(min(width, x1 + margin_x)),
    int(min(height, y1 + margin_y)),
  )


def crop_face(image: Image.Image, bbox_xyxy: tuple) -> Image.Image:
  x0, y0, x1, y1 = (max(0, int(v)) for v in bbox_xyxy)
  x1, y1 = min(image.width, x1), min(image.height, y1)
  return image.crop((x0, y0, x1, y1))


def to_thumbnail_b64(face_crop: Image.Image) -> str:
  with io.BytesIO() as buffer:
    face_crop.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _build_pattern(is_lit) -> list:
  """Build a flat LED_ROWS x LED_COLS frame, lighting each cell where is_lit(row, col) is true."""
  frame = [0] * (LED_ROWS * LED_COLS)
  for row in range(LED_ROWS):
    for col in range(LED_COLS):
      if is_lit(row, col):
        frame[row * LED_COLS + col] = 7
  return frame


def _build_o_pattern() -> list:
  """Draw a ring ('O') centered on the LED matrix, sized to fit within it."""
  cx, cy = (LED_COLS - 1) / 2, (LED_ROWS - 1) / 2
  radius = min(LED_ROWS, LED_COLS) / 2 - 0.5
  return _build_pattern(lambda row, col: radius - 1.0 <= ((col - cx) ** 2 + (row - cy) ** 2) ** 0.5 <= radius)


def _build_x_pattern() -> list:
  """Draw a diagonal cross ('X') spanning the LED matrix."""
  def is_lit(row, col):
    col_a = round(row * (LED_COLS - 1) / (LED_ROWS - 1))
    col_b = (LED_COLS - 1) - col_a
    return col == col_a or col == col_b
  return _build_pattern(is_lit)


def _build_dim_pattern(base_frame: list, brightness: int) -> list:
  return [brightness if v else 0 for v in base_frame]


LED_PATTERN_O = _build_o_pattern()
LED_PATTERN_X = _build_x_pattern()

LED_STATE_PATTERNS = {
  "granted": LED_PATTERN_O,
  "denied": LED_PATTERN_X,
  "verifying": _build_dim_pattern(LED_PATTERN_O, 3),
  "enrolling": _build_dim_pattern(LED_PATTERN_O, 3),
  "idle": [0] * (LED_ROWS * LED_COLS),
}

led_state_lock = threading.Lock()
led_last_state = None


def update_led(state: str):
  """Push the LED matrix pattern for the given state, skipping redundant redraws."""
  global led_last_state

  with led_state_lock:
    if state == led_last_state:
      return
    led_last_state = state

  try:
    Bridge.call("draw", bytes(LED_STATE_PATTERNS[state]))
  except Exception as e:
    print(f"[WARN] LED update failed for state '{state}': {e}")


def process_enrollment(enrollment: dict, embedding: np.ndarray, timestamp: str) -> tuple[str, str]:
  """Capture an enrollment sample if enough time has passed. Returns (label, state)."""
  global pending_enrollment

  now = time.monotonic()
  if now - enrollment["last_capture"] < ENROLL_SAMPLE_MIN_INTERVAL_SEC:
    return enrollment["name"], "enrolling"

  recognizer.add_sample(enrollment["name"], embedding)
  enrollment["count"] += 1
  enrollment["last_capture"] = now

  ui.send_message("enroll_progress", {
    "name": enrollment["name"],
    "count": enrollment["count"],
    "required": ENROLL_SAMPLES_REQUIRED,
    "timestamp": timestamp
  })

  if enrollment["count"] >= ENROLL_SAMPLES_REQUIRED:
    with pending_enrollment_lock:
      pending_enrollment = None
    ui.send_message("enrolled", {"name": enrollment["name"], "timestamp": timestamp})
    ui.send_message("faces_list", {"names": recognizer.list_enrolled()})

  return enrollment["name"], "enrolling"


def process_recognition(embedding: np.ndarray, face_crop: Image.Image, timestamp: str) -> tuple[str, str]:
  """Match the embedding and update the consecutive-match streak. Returns (label, state)."""
  global match_streak_name, match_streak_count

  name, score = recognizer.match(embedding)

  with match_streak_lock:
    if name is not None and name == match_streak_name:
      # Once past the threshold, access is already granted - no need to keep counting.
      if match_streak_count <= MATCH_STREAK_REQUIRED:
        match_streak_count += 1
    elif name is not None:
      # A different enrolled person - reset immediately, never inherit another
      # identity's progress/granted status.
      match_streak_name = name
      match_streak_count = 1
    else:
      # Unknown/no match this frame: decay instead of hard-resetting, so a single
      # missed/unclear frame doesn't throw away progress or revoke a granted status.
      match_streak_count = max(0, match_streak_count - 1)
      if match_streak_count == 0:
        match_streak_name = None

    streak = match_streak_count
    sticky_name = match_streak_name

  granted = sticky_name is not None and streak > MATCH_STREAK_REQUIRED

  ui.send_message("recognition", {
    "name": sticky_name,
    "score": score,
    "streak": streak,
    "required": MATCH_STREAK_REQUIRED,
    "granted": granted,
    "thumbnail": to_thumbnail_b64(face_crop),
    "timestamp": timestamp
  })

  if sticky_name is None:
    return "Unknown", "denied"
  if granted:
    return sticky_name, "granted"
  return f"{sticky_name} ({streak}/{MATCH_STREAK_REQUIRED + 1})", "verifying"


# Register a callback for when all objects are detected
def send_detections_to_ui(detections: dict, frame: bytes | None):
  global last_annotation

  image = Image.open(io.BytesIO(frame)).convert("RGB") if frame else None

  for key, values in detections.items():
    for value in values:
      timestamp = datetime.now(UTC).isoformat()
      content = key

      if key == "face" and image:
        try:
          bbox_xyxy = value["bounding_box_xyxy"]
          padded_bbox = expand_bbox(bbox_xyxy, image.size, BBOX_MARGIN_RATIO)
          face_crop = crop_face(image, padded_bbox)
          if face_crop.width == 0 or face_crop.height == 0:
            raise ValueError("Empty face crop")
          embedding = recognizer.embed(np.asarray(face_crop))

          with pending_enrollment_lock:
            enrollment = pending_enrollment

          if enrollment:
            content, state = process_enrollment(enrollment, embedding, timestamp)
          else:
            content, state = process_recognition(embedding, face_crop, timestamp)

          with last_annotation_lock:
            last_annotation = {"bbox_xyxy": bbox_xyxy, "label": content, "state": state, "time": time.monotonic()}
        except Exception:
          content = "Unknown"

      ui.send_message("detection", {
        "content": content,
        "confidence": value.get("confidence"),
        "timestamp": timestamp
      })

detection.on_detect_all(send_detections_to_ui)


def led_state_loop():
  """Continuously drive the LED matrix from the most recent detection state."""
  while True:
    time.sleep(LED_REFRESH_INTERVAL_SEC)

    with last_annotation_lock:
      annotation = last_annotation
    if annotation and time.monotonic() - annotation["time"] <= FACE_ANNOTATION_TTL_SEC:
      update_led(annotation["state"])
    else:
      update_led("idle")


threading.Thread(target=led_state_loop, daemon=True).start()

App.run()
