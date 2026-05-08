//===--sketch.ino----------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
//===----------------------------------------------------------------------===//

#include <Arduino_RouterBridge.h>
#include <Modulino.h>

ModulinoBuzzer buzzer;

// Buzzer control variables
unsigned long buzzerStartTime = 0;
bool buzzerActive = false;
const unsigned long BUZZER_DURATION = 5000; // 5 seconds in milliseconds
bool lastBuzzerTrigger = false;

void setup() {
  Serial.begin(115200);
  
  // Initialize Modulino
  Modulino.begin();
  buzzer.begin();
  
  // Initialize Bridge
  Bridge.begin();
  
  Serial.println("Plant Disease Detection System Initialized");
}

void loop() {
  String detectionStatus;
  bool statusOk = Bridge.call("get_detection_status").result(detectionStatus);
  
  // Check if buzzer should be triggered
  bool shouldTrigger = false;
  bool triggerOk = Bridge.call("should_trigger_buzzer").result(shouldTrigger);
  
  // Handle buzzer triggering
  if (triggerOk && shouldTrigger && !lastBuzzerTrigger) {
    // New detection - start buzzer
    buzzerStartTime = millis();
    buzzerActive = true;
    buzzer.tone(1000, BUZZER_DURATION); // 1000 Hz tone for 5 seconds
    Serial.println("Buzzer activated - Disease detected!");
  }
  
  lastBuzzerTrigger = shouldTrigger;
  
  // Check if buzzer duration has elapsed
  if (buzzerActive && (millis() - buzzerStartTime >= BUZZER_DURATION)) {
    buzzerActive = false;
    Serial.println("Buzzer deactivated");
  }
  
  // Print status for debugging
  if (statusOk) {
    static String lastStatus = "";
    if (detectionStatus != lastStatus) {
      Serial.print("Detection Status: ");
      Serial.println(detectionStatus);
      lastStatus = detectionStatus;
    }
  }
  
  delay(100); // Small delay to prevent excessive polling
}
