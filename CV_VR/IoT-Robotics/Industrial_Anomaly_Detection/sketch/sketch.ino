//===--sketch.ino----------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
//===----------------------------------------------------------------------===//

#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>
#include "anomaly_detection_frames.h"

Arduino_LED_Matrix matrix;

void setup() {
  matrix.begin();
  matrix.clear();
  Bridge.begin();
  // Start with OK frame (default state)
  matrix.loadFrame(ok_frame_0);
}

void loop() {
  static int i = 0;
  String detectionStatus;
  bool ok = Bridge.call("get_detection_status").result(detectionStatus);
  
  const uint32_t* const* detected_frames;
  
  if (ok) {
    // Only handle Fire, Leakage, and OK states
    if (detectionStatus == "Fire") {
      detected_frames = fire_frames;
    } else if (detectionStatus == "Leakage") {
      detected_frames = leak_frames;
    } else {
      // Default to OK for any other status (including "OK")
      detected_frames = ok_frames;
    }
  } else {
    // If bridge call fails, default to OK frames
    detected_frames = ok_frames;
  }

  // Cycle through animation frames
  i++;
  if (i == ANIMATION_FRAME_COUNT) {
    i = 0;
  }
  
  matrix.loadFrame(detected_frames[i]);
  delay(20);
}
