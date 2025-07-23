#===-Sensor_Data_Process.py----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import socket
import threading
import json
import time
import sys
from datetime import datetime, timezone

# Threshold Constants
HR_CRITICAL_LOW = 50
HR_LOW = 60
HR_HEALTHY_MAX = 100
HR_HIGH_MAX = 120

SPO2_CRITICAL_LOW = 85
SPO2_LOW = 95

TEMP_CRITICAL_LOW = 35.0
TEMP_LOW = 36.0
TEMP_HEALTHY_MAX = 37.5
TEMP_HIGH_MAX = 39.0

buffer = []
buffer_lock = threading.Lock()

def classify_data(data):
    status = {}
    cause = {}

    hr = data.get("heart_rate")
    spo2 = data.get("spo2")
    temp = data.get("body_temperature")

    if hr is not None:
        if hr < HR_CRITICAL_LOW:
            status["heart_rate"] = "Critical Low"
            cause["heart_rate"] = "Severe Bradycardia"
        elif hr < HR_LOW:
            status["heart_rate"] = "Low"
            cause["heart_rate"] = "Bradycardia"
        elif hr <= HR_HEALTHY_MAX:
            status["heart_rate"] = "Healthy"
            cause["heart_rate"] = "Normal range"
        elif hr <= HR_HIGH_MAX:
            status["heart_rate"] = "High"
            cause["heart_rate"] = "Mild Tachycardia"
        else:
            status["heart_rate"] = "Critical High"
            cause["heart_rate"] = "Severe Tachycardia"

    if spo2 is not None:
        if spo2 < SPO2_CRITICAL_LOW:
            status["spo2"] = "Critical Low"
            cause["spo2"] = "Severe Hypoxemia"
        elif spo2 < SPO2_LOW:
            status["spo2"] = "Low"
            cause["spo2"] = "Mild Hypoxemia"
        else:
            status["spo2"] = "Healthy"
            cause["spo2"] = "Normal oxygen level"

    if temp is not None:
        if temp < TEMP_CRITICAL_LOW:
            status["body_temperature"] = "Critical Low"
            cause["body_temperature"] = "Severe Hypothermia"
        elif temp < TEMP_LOW:
            status["body_temperature"] = "Low"
            cause["body_temperature"] = "Mild Hypothermia"
        elif temp <= TEMP_HEALTHY_MAX:
            status["body_temperature"] = "Healthy"
            cause["body_temperature"] = "Normal temperature"
        elif temp <= TEMP_HIGH_MAX:
            status["body_temperature"] = "High"
            cause["body_temperature"] = "Fever"
        else:
            status["body_temperature"] = "Critical High"
            cause["body_temperature"] = "Hyperpyrexia"

    return status, cause

def handle_client(conn, addr):
    print(f"[CONNECTED] {addr}")
    try:
        while True:
            raw = conn.recv(1024).decode()
            if not raw:
                break
            data = json.loads(raw)
            data["client"] = str(addr)
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            status, cause = classify_data(data)
            data["status"] = status
            data["cause"] = cause

            with buffer_lock:
                buffer.append(data)

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        conn.close()
        print(f"[DISCONNECTED] {addr}")

def forward_to_dashboard(dashboard_ip, dashboard_port):
    while True:
        time.sleep(10)
        with buffer_lock:
            if buffer:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_id:
                        server_id.connect((dashboard_ip, dashboard_port))
                        payload = json.dumps(buffer).encode()
                        server_id.sendall(payload)
                        print(f"[SENT] {len(buffer)} records to dashboard")
                    buffer.clear()
                except Exception as e:
                    print(f"[ERROR] Sending to dashboard: {e}")

def start_server(host='0.0.0.0', port=7070):
    if len(sys.argv) < 3:
        print("Usage: python Sensor_Data_Process.py <DASHBOARD_IP> <DASHBOARD_PORT>")
        return
    dashboard_ip = sys.argv[1]
    dashboard_port = int(sys.argv[2])

    threading.Thread(target=forward_to_dashboard, args=(dashboard_ip, dashboard_port), daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    print(f"[LISTENING] Server on {host}:{port}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()

