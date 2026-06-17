#===-----------------------main.py------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===------------------------------------------------------------------------===//

# -*- coding: utf-8 -*-
import time
import json
from collections import deque
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)
from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
from sensors.vital_simulator import VitalSimulator
from run_agentic_pipeline import run_agentic_pipeline

# =========================================================
# CONFIG
# =========================================================
LOOP_PERIOD_SEC = 2
TEST_MODE = True
AGENTIC_COOLDOWN_SEC = 0 if TEST_MODE else 120
LEVEL_GOOD = 0
LEVEL_LOW = 1
LEVEL_MODERATE = 2
LEVEL_HIGH = 3
LEVEL_NAME = {0: "GOOD", 1: "LOW", 2: "MODERATE", 3: "HIGH"}
PATIENTS = [
    {"id": "P1", "name": "Patient 1"},
    {"id": "P2", "name": "Patient 2"},
    {"id": "P3", "name": "Patient 3"},
    {"id": "P4", "name": "Patient 4"},
]

# =========================================================
# STATE
# =========================================================
def new_patient(name: str):
    return {
        "name": name,
        "vitals": None,
        "history": deque(maxlen=300),
        "level": LEVEL_GOOD,
        "level_name": "GOOD",
        "reasons": ["Stable"],
        "nurse_alert": "No alert | Stable",
        "monitor_summary": "",
        "nurse_summary": "",
        "doctor_report": "",
        "nurse_followup": "",
        "last_agentic_ts": 0,
    }

STATE: Dict[str, Any] = {
    "patients": {p["id"]: new_patient(p["name"]) for p in PATIENTS},
    "last_update_ts": 0,
    "worst_patient": None,
    "worst_level": LEVEL_GOOD,
    "test_mode": TEST_MODE,
}

# =========================================================
# TEST SCENARIO CONTROL
# =========================================================
SCENARIO = {p["id"]: "GOOD" for p in PATIENTS}

# =========================================================
# SIMULATORS
# =========================================================
SIM = {p["id"]: VitalSimulator() for p in PATIENTS}
ui = WebUI()

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def nurse_action(level: int) -> str:
    if level == LEVEL_HIGH:
        return "ESCALATE to Doctor"
    if level == LEVEL_MODERATE:
        return "ALERT Nurse"
    if level == LEVEL_LOW:
        return "Watchlist"
    return "No alert | Stable"

def force_vitals_for_scenario(vitals: dict, scenario: str) -> dict:
    s = (scenario or "GOOD").upper()
    v = dict(vitals)
    if s == "GOOD":
        v["spo2"] = max(float(v["spo2"]), 96.0)
        v["temperature"] = min(float(v["temperature"]), 37.2)
        v["heart_rate"] = min(max(float(v["heart_rate"]), 65.0), 95.0)
    elif s == "LOW":
        v["spo2"] = 94.0
        v["temperature"] = max(float(v["temperature"]), 37.9)
    elif s == "MODERATE":
        v["temperature"] = 38.7
        v["heart_rate"] = max(float(v["heart_rate"]), 125.0)
        v["spo2"] = min(float(v["spo2"]), 93.0)
    elif s == "HIGH":
        v["spo2"] = 90.0
        v["temperature"] = 39.1
        v["heart_rate"] = max(float(v["heart_rate"]), 130.0)
    return v

def compute_level_from_vitals(patient_name: str, vitals: dict, scenario: str):
    s = (scenario or "GOOD").upper()
    
    if s == "HIGH":
        return LEVEL_HIGH, ["Test: Forced HIGH"]
    if s == "MODERATE":
        return LEVEL_MODERATE, ["Test: Forced MODERATE"]
    if s == "LOW":
        return LEVEL_LOW, ["Test: Forced LOW"]
    
    try:
        result = run_agentic_pipeline(
            patient_name=patient_name,
            vitals=vitals,
            level_name="PENDING",
            reasons=["Analyzing..."],
        )
        
        level_decision = result.get("level_decision", "GOOD")
        reasons = result.get("reasons", ["Agentic analysis"])
        
        level_map = {
            "GOOD": LEVEL_GOOD,
            "LOW": LEVEL_LOW,
            "MODERATE": LEVEL_MODERATE,
            "HIGH": LEVEL_HIGH
        }
        level = level_map.get(level_decision, LEVEL_GOOD)
        
        return level, reasons
    except Exception as e:
        print(f"Error in agentic classification for {patient_name}: {str(e)}")
        return LEVEL_GOOD, ["Classification error"]

def maybe_run_agentic(now: float, pid: str, pdata: dict):
    """Run agentic for all patients"""
    if (now - pdata["last_agentic_ts"]) < AGENTIC_COOLDOWN_SEC:
        return
    
    out = run_agentic_pipeline(
        patient_name=pdata["name"],
        vitals=pdata["vitals"],
        level_name=pdata["level_name"],
        reasons=pdata["reasons"],
    )
    
    pdata["monitor_summary"] = out.get("monitor_summary", "")
    pdata["nurse_summary"] = out.get("nurse_summary", "")
    pdata["doctor_report"] = out.get("doctor_report", "")
    pdata["nurse_followup"] = out.get("nurse_followup", "")
    pdata["last_agentic_ts"] = now

# =========================================================
# MAIN LOOP
# =========================================================
def tick():
    now = time.time()
    worst_level = LEVEL_GOOD
    worst_pid = None
    
    for pid, pdata in STATE["patients"].items():
        vitals = SIM[pid].get_vitals()
        scenario = SCENARIO.get(pid, "GOOD")
        vitals = force_vitals_for_scenario(vitals, scenario)
        
        pdata["vitals"] = vitals
        pdata["history"].append(vitals)
        
        level, reasons = compute_level_from_vitals(pdata["name"], vitals, scenario)
        pdata["level"] = level
        pdata["level_name"] = LEVEL_NAME[level]
        pdata["reasons"] = reasons
        
        pdata["nurse_alert"] = f"{nurse_action(level)} | " + (" | ".join(reasons) if reasons else "Stable")
        
        try:
            maybe_run_agentic(now, pid, pdata)
        except Exception as e:
            pdata["doctor_report"] = f"Agentic error: {e}"
        
        if level > worst_level:
            worst_level = level
            worst_pid = pid
    
    STATE["worst_patient"] = worst_pid
    STATE["worst_level"] = worst_level
    STATE["last_update_ts"] = int(now)
    
    if worst_pid:
        try:
            Bridge.call("set_alert", int(worst_pid[-1]), int(worst_level))
        except Exception:
            pass

# =========================================================
# REST APIs
# =========================================================
ui.expose_api("GET", "/api/latest", lambda: STATE)
ui.expose_api("GET", "/api/scenario", lambda: SCENARIO)

def api_set_scenario(body=None):
    if isinstance(body, str):
        body = json.loads(body)
    pid = body.get("patient_id")
    scenario = body.get("scenario", "GOOD").upper()
    if pid in SCENARIO and scenario in ("GOOD", "LOW", "MODERATE", "HIGH"):
        SCENARIO[pid] = scenario
        return {"ok": True, "patient_id": pid, "scenario": scenario}
    return {"ok": False, "error": "invalid patient_id or scenario"}

ui.expose_api("POST", "/api/scenario", api_set_scenario)

def api_test_high(_body=None):
    SCENARIO["P1"] = "GOOD"
    SCENARIO["P2"] = "GOOD"
    SCENARIO["P3"] = "GOOD"
    SCENARIO["P4"] = "HIGH"
    return {"ok": True, "scenario": SCENARIO}

ui.expose_api("POST", "/api/test-high", api_test_high)

def api_all_high(_body=None):
    for pid in SCENARIO.keys():
        SCENARIO[pid] = "HIGH"
    return {"ok": True, "scenario": SCENARIO}

ui.expose_api("POST", "/api/all-high", api_all_high)

def api_test_pattern(_body=None):
    SCENARIO["P1"] = "GOOD"
    SCENARIO["P2"] = "LOW"
    SCENARIO["P3"] = "MODERATE"
    SCENARIO["P4"] = "HIGH"
    return {"ok": True, "scenario": SCENARIO}

ui.expose_api("POST", "/api/test-pattern", api_test_pattern)

# =========================================================
# Continuous execution
# =========================================================
def user_loop():
    tick()
    time.sleep(LOOP_PERIOD_SEC)

App.run(user_loop=user_loop)

