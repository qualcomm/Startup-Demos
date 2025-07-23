#===-Sensor_Data_Simulator.py----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import socket
import json
import time
import random
import pandas as pd

# Constants
DEFAULT_HEART_RATE = 70
DEFAULT_SPO2 = 98
DEFAULT_TEMP = 36.5
DEFAULT_INTERVAL = 1
DEFAULT_DURATION = 60

DEFAULT_HR_VARIATION = 5
DEFAULT_SPO2_VARIATION = 2
DEFAULT_TEMP_VARIATION = 0.5
MIN_INTERVAL = 0.1

st.set_page_config(page_title="🩺 Sensor Simulator", layout="centered")
st.title("🩺 Sensor Simulator")

st.sidebar.title("🛠️ Sensor Configuration")
st.markdown("### 🔌 Enter Server IP Address and Port")
HOST = st.text_input("Server IP Address", placeholder="e.g. 192.168.1.10")
PORT = st.text_input("Server Port", placeholder="e.g. 7070")

heart_rate = st.sidebar.number_input("Heart Rate (bpm)", 30, 200, DEFAULT_HEART_RATE)
spo2 = st.sidebar.number_input("SpO₂ (%)", 70, 100, DEFAULT_SPO2)
temperature = st.sidebar.number_input("Body Temperature (°C)", 34.0, 42.0, DEFAULT_TEMP)
interval = st.sidebar.number_input("Interval (seconds)", value=float(DEFAULT_INTERVAL), min_value=0.0)
duration = st.sidebar.number_input("Duration (seconds)", value=DEFAULT_DURATION, min_value=1)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Tolerance Levels")
heart_rate_variation = st.sidebar.number_input("Heart Rate ±", value=DEFAULT_HR_VARIATION)
spo2_variation = st.sidebar.number_input("SpO₂ ±", value=DEFAULT_SPO2_VARIATION)
temperature_variation = st.sidebar.number_input("Temperature ±", value=DEFAULT_TEMP_VARIATION)

if interval < MIN_INTERVAL:
    st.sidebar.warning(f"Interval too low. Using minimum interval of {MIN_INTERVAL} seconds.")
    interval = MIN_INTERVAL

# Ensure at least one data point is sent
total_points = max(1, int(duration / interval))
st.sidebar.info(f"📈 Total data points to send: {total_points}")

if "connected" not in st.session_state:
    st.session_state.connected = False
if "socket" not in st.session_state:
    st.session_state.socket = None

if not st.session_state.connected and HOST and PORT:
    if st.button("🔌 Connect to Server"):
        try:
            server_id = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_id.connect((HOST, int(PORT)))
            st.session_state.socket = server_id
            st.session_state.connected = True
            st.success("✅ Connected to server.")
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")

if st.session_state.connected and st.button("🚀 Start Transmission"):
    log_area = st.empty()
    chart_area = st.empty()

    server_id = st.session_state.socket
    heart_data = []
    spo2_data = []
    temp_data = []
    timestamps = []

    try:
        for i in range(total_points):
            simulated_data = {
                "heart_rate": int(random.uniform(heart_rate - heart_rate_variation, heart_rate + heart_rate_variation)),
                "spo2": int(random.uniform(spo2 - spo2_variation, spo2 + spo2_variation)),
                "body_temperature": round(random.uniform(temperature - temperature_variation, temperature + temperature_variation), 1)
            }

            try:
                server_id.send(json.dumps(simulated_data).encode())
                log_area.code(f"📤 Sent ({i+1}/{total_points}): {json.dumps(simulated_data)}")
            except Exception as e:
                st.error("❌ Server disconnected. Please reconnect.")
                st.session_state.connected = False
                st.session_state.socket = None
                break

            heart_data.append(simulated_data["heart_rate"])
            spo2_data.append(simulated_data["spo2"])
            temp_data.append(simulated_data["body_temperature"])
            timestamps.append(time.strftime("%H:%M:%S"))

            df = pd.DataFrame({
                "Time": timestamps,
                "Heart Rate": heart_data,
                "SpO₂": spo2_data,
                "Body Temp": temp_data
            })
            df.set_index("Time", inplace=True)
            chart_area.line_chart(df)

            time.sleep(interval)

        if st.session_state.connected:
            st.success(f"✅ Data transmission completed. {len(heart_data)} data points sent.")

    except Exception as e:
        st.error(f"❌ Error during transmission: {e}")
        st.session_state.connected = False
        st.session_state.socket = None

if st.session_state.connected:
    if st.button("🔌 Disconnect"):
        try:
            st.session_state.socket.close()
        except:
            pass
        st.session_state.connected = False
        st.session_state.socket = None
        st.warning("Disconnected from server.")

