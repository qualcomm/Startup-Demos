//===-- sketch.ino ---------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>
#include "air_quality_frames.h"

Arduino_LED_Matrix matrix;

void setup() {
matrix.begin();
matrix.clear();

Bridge.begin();
matrix.loadFrame(unknown);
}

void loop() {
String helmetStatus;
bool ok = Bridge.call("get_helmet_status").result(helmetStatus);

if (ok) {
 if (helmetStatus == "Helmet") {
   matrix.loadFrame(good);       // ✓
 } else if (helmetStatus == "No Helmet") {
   matrix.loadFrame(hazardous);  // ✗
 } else {
   matrix.loadFrame(unknown);    // ？
 }
}
delay(500);
}