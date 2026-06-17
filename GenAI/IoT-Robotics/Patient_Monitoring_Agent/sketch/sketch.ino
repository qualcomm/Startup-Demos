//===----------------------------sketch.ino --------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

#include "Arduino_RouterBridge.h"
#include <Arduino_LED_Matrix.h>

ArduinoLEDMatrix matrix;

// 8 rows x 13 cols = 104 bytes
static const uint8_t ICON_GOOD[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,1,0,0,0,0,
  0,0,0,0,0,0,0,1,0,1,0,0,0,
  0,0,0,0,0,0,1,0,0,0,1,0,0,
  0,0,0,0,0,1,0,0,0,0,0,1,0,
  0,0,0,0,1,0,0,0,0,0,0,0,1,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

static const uint8_t ICON_LOW[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

static const uint8_t ICON_MODERATE[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,0,1,0,0,0,0,0,
  0,0,0,0,1,0,0,0,1,0,0,0,0,
  0,0,0,1,0,0,0,0,0,1,0,0,0,
  0,0,1,0,0,0,0,0,0,0,1,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

static const uint8_t ICON_HIGH[104] = {
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  0,1,0,0,0,0,0,0,0,0,0,1,0,
  0,0,1,0,0,0,0,0,0,0,1,0,0,
  0,0,0,1,0,0,0,0,0,1,0,0,0,
  0,0,1,0,0,0,0,0,0,0,1,0,0,
  0,1,0,0,0,0,0,0,0,0,0,1,0,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

static void draw_icon(int level) {
  if (level == 0) matrix.draw(ICON_GOOD);
  else if (level == 1) matrix.draw(ICON_LOW);
  else if (level == 2) matrix.draw(ICON_MODERATE);
  else matrix.draw(ICON_HIGH);
}

// Bridge-callable function: Python -> MCU
void set_alert(int patientIndex, int level) {
  Monitor.print("Alert patient=");
  Monitor.print(patientIndex);
  Monitor.print(" level=");
  Monitor.println(level);
  draw_icon(level);
}

void setup() {
  matrix.begin();

  Bridge.begin();   // Bridge RPC init (MPU<->MCU) 
  Monitor.begin();

  Bridge.provide("set_alert", set_alert);
  draw_icon(0);
}

void loop() {
  // Event-driven
}


