#===-Data_Payload_Dashboard.py----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import json
import os
import pandas as pd
import threading
import socket
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Sensor Dashboard", layout="wide")
# Auto-refresh every 10 seconds
st_autorefresh(interval=10 * 1000, key="datarefresh")
st.title("📈 Data Payload Dashboard")

history_file = "history.json"

if "server_active" not in st.session_state:
    st.session_state.server_active = False

if not os.path.exists(history_file):
    with open(history_file, "w") as f:
        json.dump([], f)

# Socket listener
def dashboard_listener(host='0.0.0.0', port=9090):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    print(f"[DASHBOARD LISTENING] on {host}:{port}")
    while True:
        conn, addr = server.accept()
        with conn:
            try:
                buffer = ""
                while True:
                    chunk = conn.recv(4096).decode()
                    if not chunk:
                        break
                    buffer += chunk
                if buffer:
                    try:
                        data = json.loads(buffer)
                        new_data = data if isinstance(data, list) else [data]
                        print(f"[RECEIVED] from {addr}: {len(new_data)} records")
                        if os.path.exists(history_file):
                            with open(history_file, "r") as f:
                                history = json.load(f)
                        else:
                            history = []
                        history = [*new_data, *history]
                        with open(history_file, "w") as f:
                            json.dump(history, f, indent=2)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] JSON decode failed: {e}")
            except Exception as e:
                print(f"[ERROR] Receiving data: {e}")

threading.Thread(target=dashboard_listener, daemon=True).start()

# Server control
col1, col2 = st.columns(2)
with col1:
    if st.button("🟢 Start Server"):
        st.session_state.server_active = True
        st.success("Dashboard server started.")
with col2:
    if st.button("🔴 Stop Server"):
        st.session_state.server_active = False
        st.warning("Dashboard server stopped.")

# Flag legend
st.markdown("""
### 🚩 Flag Indicators
- 🚨 **Critical**: Dangerously high or low value  
- ⚠️ **Warning**: Slightly outside healthy range  
- ✅ **Healthy**: Normal range  
- ❓ **Unknown**: Status not available
""")

with st.expander("ℹ️ Sensor Ranges & Flag Legend"):
    st.markdown("""
    ### Heart Rate (bpm)
    - **Critical Low**: < 50  
    - **Low**: 50–59  
    - **Healthy**: 60–100  
    - **High**: 101–120  
    - **Critical High**: > 120  

    ### SpO₂ (%)
    - **Critical Low**: < 85  
    - **Low**: 85–94  
    - **Healthy**: ≥ 95  

    ### Body Temperature (°C)
    - **Critical Low**: < 35.0  
    - **Low**: 35.0–35.9  
    - **Healthy**: 36.0–37.5  
    - **High**: 37.6–39.0  
    - **Critical High**: > 39.0  
    """)

# Reset button
st.markdown("---")
if st.button("🧹 Reset Dashboard Data"):
    with open(history_file, "w") as f:
        json.dump([], f)
    st.session_state["cleared"] = True
    st.success("Dashboard data has been reset.")

# Display data
if st.session_state.get("server_active", False) and not st.session_state.get("cleared", False):
    try:
        with open(history_file, "r") as f:
            data = json.load(f)
        #df = pd.DataFrame(data)
        flattened_data = []
        for entry in data:
            if isinstance(entry, list):
                flattened_data.extend(entry)
            else:
                flattened_data.append(entry)

        df = pd.DataFrame(flattened_data)


        if not df.empty:
            st.subheader("📋 Historical Sensor Data")

            def add_flag(value, status_dict, key):
                if isinstance(status_dict, dict):
                    status = status_dict.get(key, "Unknown")
                    if "Critical" in status:
                        return f"{value} - <span style='color:red; font-weight:bold'>{status} 🚨</span>"
                    elif status != "Healthy":
                        return f"{value} - <span style='color:orange; font-weight:bold'>{status} ⚠️</span>"
                    elif status == "Healthy":
                        return f"{value} - <span style='color:green; font-weight:bold'>{status} ✅</span>"
                return f"{value} - <span style='color:gray'>Unknown ❓</span>"

            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata")
            latest_time = df["timestamp"].max()
            now_ist = datetime.now(timezone.utc).astimezone()

            if (now_ist - latest_time.to_pydatetime()) > timedelta(seconds=30):
                st.warning("⚠️ No new data received in the last 30 seconds. The client may have stopped transmitting.")

            df["Heart Rate"] = df.apply(lambda row: add_flag(row.get("heart_rate"), row.get("status"), "heart_rate"), axis=1)
            df["SpO₂"] = df.apply(lambda row: add_flag(row.get("spo2"), row.get("status"), "spo2"), axis=1)
            df["Body Temp"] = df.apply(lambda row: add_flag(row.get("body_temperature"), row.get("status"), "body_temperature"), axis=1)

            styled_df = df[["timestamp", "client", "Heart Rate", "SpO₂", "Body Temp"]].copy()
            styled_df.columns = ["Timestamp", "Client", "Heart Rate", "SpO₂", "Body Temp"]

            # Serial No. from bottom (oldest = 1)
            styled_df.insert(0, "Serial No.", range(len(styled_df), 0, -1))

            st.markdown(
                styled_df.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )

            st.subheader("📊 Real-Time Charts")
            chart_df = df[["timestamp", "heart_rate", "spo2", "body_temperature"]].copy()
            chart_df.set_index("timestamp", inplace=True)
            st.line_chart(chart_df)
        else:
            st.info("No data available yet.")
    except Exception as e:
        st.error(f"Error loading data: {e}")
elif st.session_state.get("cleared", False):
    st.info("Dashboard data has been cleared. No data to display.")
else:
    st.info("Dashboard server is not active.")

