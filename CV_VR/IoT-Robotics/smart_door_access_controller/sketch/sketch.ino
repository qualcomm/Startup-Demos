//===--sketch.ino------------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===------------------------------------------------------------------------===//

// Exposes a single Bridge provider, "draw", which receives an 8x13 (104 byte)
// grayscale frame (0..7 per pixel) and renders it on the built-in LED matrix.
// The Python app decides which pattern to send (e.g. O for access granted,
// X for denied) and pushes it whenever the recognition state changes.

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>

Arduino_LED_Matrix matrix;

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3); // accept 0..7 brightness levels
  matrix.clear();

  Bridge.begin();
  Bridge.provide("draw", draw);
}

void loop() {
  // All work happens in the "draw" Bridge provider.
}

void draw(std::vector<uint8_t> frame) {
  if (frame.empty()) return;
  matrix.draw(frame.data());
}
