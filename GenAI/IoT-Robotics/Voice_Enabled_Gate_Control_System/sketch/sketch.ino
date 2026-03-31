//===----------------------------sketch.ino --------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>

ArduinoLEDMatrix matrix;

// -------- CLOSE GATE --------
uint8_t gate_close[] = {
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1
};

// -------- OPEN GATE --------
uint8_t gate_open[] = {
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,1,1,1,0,0,0,0,0,1,1,1,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,1
};

// -------- IDLE / NONE (optional default) --------
// A simple "dot" pattern in center
uint8_t gate_idle[] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

// Keep track of last shown command to avoid redraw spam
String last_cmd_shown = "NONE";


// ---------------------------
// NEW: set_led method for Python -> MCU call
// ---------------------------
// Python may call: Bridge.call("set_led", "OPEN") or "CLOSE"
String set_led(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "OPEN") {
    matrix.draw(gate_open);
    last_cmd_shown = "OPEN";
    return "OK:OPEN";
  }
  else if (cmd == "CLOSE") {
    matrix.draw(gate_close);
    last_cmd_shown = "CLOSE";
    return "OK:CLOSE";
  }
  else {
    // Unknown command -> show idle
    matrix.draw(gate_idle);
    last_cmd_shown = "NONE";
    return "OK:NONE";
  }
}


void setup() {
  matrix.begin();
  Bridge.begin();

  // Provide MCU method so Python Bridge.call("set_led", cmd) works
  Bridge.provide("set_led", set_led);

  // Optional: show idle at startup
  matrix.draw(gate_idle);
}


void loop() {
  String cmd;
  bool ok = Bridge.call("detect_gate_command").result(cmd);

  if (ok) {
    cmd.trim();
    cmd.toUpperCase();

    // Only redraw if command changes (avoids flicker)
    if (cmd != last_cmd_shown) {
      if (cmd == "OPEN") {
        matrix.draw(gate_open);
        last_cmd_shown = "OPEN";
      }
      else if (cmd == "CLOSE") {
        matrix.draw(gate_close);
        last_cmd_shown = "CLOSE";
      }
      else {
        // Optional: show idle when NONE/unknown
        matrix.draw(gate_idle);
        last_cmd_shown = "NONE";
      }
    }
  }

  delay(200);  // faster response than 500ms
}

