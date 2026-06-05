//===--sketch.ino----------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

#include <Arduino_RouterBridge.h>

// -----------------------------------------------------------------------------
// One-click deployment mode (MCU side)
// -----------------------------------------------------------------------------
// Set DEPLOYMENT_MODE=1 to disable ALL debug-only outputs (RGB LEDs + LED matrix).
// You can set this in code or via compiler flags: -DDEPLOYMENT_MODE=1
#ifndef DEPLOYMENT_MODE
#define DEPLOYMENT_MODE 0
#endif

// -----------------------------------------------------------------------------
// Debug feature toggles (MCU side)
// -----------------------------------------------------------------------------
// These are DEBUG / development aids and can be disabled for deployment.
// Set to 0 to disable the corresponding debug function.
#ifndef DBG_RGB_LED
#define DBG_RGB_LED   1   // RGB traffic-light LEDs (D6/D7/D8) - debug only
#endif

#ifndef DBG_LED_MATRIX
#define DBG_LED_MATRIX 1  // 8x13 LED matrix distance display - debug only
#endif

// If deployment mode is enabled, force-disable debug features
#if DEPLOYMENT_MODE
  #undef DBG_RGB_LED
  #define DBG_RGB_LED 0
  #undef DBG_LED_MATRIX
  #define DBG_LED_MATRIX 0
#endif

// -----------------------------------------------------------------------------
// Hardware pin definitions
// -----------------------------------------------------------------------------
#define TRIGGER_PIN   11
#define ECHO_PIN      12
#define LED_RED       6
#define LED_YELLOW    7
#define LED_GREEN     8
#define BUZZER_PIN    5

#if DBG_LED_MATRIX
#include <Arduino_LED_Matrix.h>

// LED matrix object and frame buffer
Arduino_LED_Matrix matrix;
uint8_t fb[104];

// 3x5 digit font
const uint8_t DIGIT_3x5[10][5] PROGMEM = {
  {0b111,0b101,0b101,0b101,0b111}, {0b010,0b110,0b010,0b010,0b111},
  {0b111,0b001,0b111,0b100,0b111}, {0b111,0b001,0b111,0b001,0b111},
  {0b101,0b101,0b111,0b001,0b001}, {0b111,0b100,0b111,0b001,0b111},
  {0b111,0b100,0b111,0b101,0b111}, {0b111,0b001,0b001,0b001,0b001},
  {0b111,0b101,0b111,0b101,0b111}, {0b111,0b101,0b111,0b001,0b111}
};

static void renderDistance(int v) {
  memset(fb, 0, 104);

  // Handle invalid or out-of-range value
  if (v < 0 || v > 99) {
    for (int r = 0; r < 5; r++) {
      fb[(r + 1) * 13 + 4] = 1;
      fb[(r + 1) * 13 + 8] = 1;
    }
  } else {
    int tens = v / 10;
    int ones = v % 10;

    for (int r = 0; r < 5; r++) {
      uint8_t rowT = pgm_read_byte(&DIGIT_3x5[tens][r]);
      uint8_t rowO = pgm_read_byte(&DIGIT_3x5[ones][r]);

      for (int c = 0; c < 3; c++) {
        // Tens digit
        if ((rowT >> (2 - c)) & 1)
          fb[(r + 1) * 13 + (c + 3)] = 1;

        // Ones digit
        if ((rowO >> (2 - c)) & 1)
          fb[(r + 1) * 13 + (c + 7)] = 1;
      }
    }
  }

  matrix.draw(fb);
}

#else
// Matrix disabled (deployment mode): keep a stub to simplify call sites.
static void renderDistance(int) { /* no-op */ }
#endif


static unsigned long customPulseIn(int pin, int state, unsigned long timeout) {
  unsigned long startMicros = micros();

  // Wait for pin to match desired state
  while (digitalRead(pin) != state) {
    if (micros() - startMicros > timeout) return 0;
  }

  unsigned long pulseStart = micros();

  // Measure the pulse length
  while (digitalRead(pin) == state) {
    if (micros() - pulseStart > timeout) return 0;
  }

  return micros() - pulseStart;
}


static int getDistance() {
  // Send trigger pulse
  digitalWrite(TRIGGER_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIGGER_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIGGER_PIN, LOW);

  // Measure echo
  unsigned long duration = customPulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return -1;

  // Convert time to distance (cm)
  return (int)(duration * 0.034f / 2.0f);
}


// --- AI label state ---
String g_label = "off";
unsigned long last_ai_poll_ms = 0;
const unsigned long AI_POLL_INTERVAL_MS = 100;  // Poll AI label every 100ms


static void applyTrafficLight(const String &label) {
#if DBG_RGB_LED
  digitalWrite(LED_RED,    label == "red_light");
  digitalWrite(LED_YELLOW, label == "yellow_light");
  digitalWrite(LED_GREEN,  label == "green_light");
#else
  (void)label;
#endif
}


void setup() {
  Bridge.begin();  // Initialize UNO Q RouterBridge

  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);

#if DBG_RGB_LED
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
#endif

#if DBG_LED_MATRIX
  matrix.begin();
  renderDistance(-1);  // Initial screen
#endif

  // Turn off all debug LEDs at start
  applyTrafficLight("off");
}


void loop() {
  // 1) Poll AI label periodically
  unsigned long now = millis();
  if (now - last_ai_poll_ms >= AI_POLL_INTERVAL_MS) {
    last_ai_poll_ms = now;

    String label;
    bool ok = Bridge.call("get_ai_label").result(label);  // Provided by Python side
    if (ok) {
      label.trim();
      g_label = label;
      applyTrafficLight(g_label);
    } else {
      // If call fails, turn all debug LEDs off for safety
      applyTrafficLight("off");
    }
  }

  // 2) Measure distance and update display (matrix is debug only)
  int d = getDistance();
  renderDistance(d);

  // 3) Buzzer alert if too close (core user alert)
  if (d > 0 && d < 50) {
    tone(BUZZER_PIN, 1000, 50);
  } else {
    noTone(BUZZER_PIN);
  }

  delay(50);
}
