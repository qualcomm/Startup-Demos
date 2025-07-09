# ===--receive_people_count_dashboard.py----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
# ===----------------------------------------------------------------------===//
import streamlit as st
import socket
import re
import time
from streamlit_autorefresh import st_autorefresh

# Auto-refresh every 1 seconds
st_autorefresh(interval=1000, key="groupcountrefresh")

# Initialize session state
if "socket" not in st.session_state:
    st.session_state.socket = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "group_counts" not in st.session_state:
    st.session_state.group_counts = []
if "last_data_time" not in st.session_state:
    st.session_state.last_data_time = None
if "disconnected_due_to_timeout" not in st.session_state:
    st.session_state.disconnected_due_to_timeout = False

def connect_to_server(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.settimeout(1.0)
        st.session_state.socket = s
        st.session_state.connected = True
        st.session_state.last_data_time = time.time()
        return True
    except Exception as e:
        return f"Connection failed: {e}"

def receive_group_counts():
    try:
        s = st.session_state.socket
        if s:
            data = s.recv(1024).decode()
            match = re.search(r"Group counts:\s*([\d,\s]+)", data)
            if match:
                counts_str = match.group(1)
                st.session_state.group_counts = [int(x.strip()) for x in counts_str.split(",") if x.strip().isdigit()]
                st.session_state.last_data_time = time.time()
    except socket.timeout:
        pass
    except Exception as e:
        st.session_state.connected = False
        st.error(f"Error receiving data: {e}")

st.title("📊 Live People Count Monitor")


st.markdown("### 🔌 Enter Server IP Address")
host = st.text_input("Server Host", placeholder="e.g., 10.91.49.188")
st.caption("Example: Enter the IP address of the server running the people counter.")
port = st.number_input("Server Port", 58001, step=1)

if st.button("Connect to Server") and not st.session_state.connected:
    result = connect_to_server(host, port)
    if result is True:
        st.success("✅ Connected to server.")
    else:
        st.error(result)

# If connected, try to receive new data
if st.session_state.connected:
    receive_group_counts()
    st.subheader("📈 Live People Counts")

    cols = st.columns(len(st.session_state.group_counts))
    for i, (col, count) in enumerate(zip(cols, st.session_state.group_counts), start=1):
        with col:
            st.markdown(f"""
                <div style="border:2px solid #4CAF50; border-radius:10px; padding:10px; text-align:center;">
                    <h4>Zone {i}</h4>
                    <p style="font-size:24px; font-weight:bold;">{count}</p>
                </div>
            """, unsafe_allow_html=True)

    # Check if data has been received recently
    if st.session_state.last_data_time:
        time_since_last = time.time() - st.session_state.last_data_time
        if time_since_last > 30:
            st.session_state.connected = False
            st.session_state.disconnected_due_to_timeout = True
            try:
                st.session_state.socket.close()
            except:
                pass
            st.error("❌ No data received from server in the last 30 seconds. Disconnected.")
        else:
            st.success("✅ Receiving data from server.")
    else:
        st.info("⏳ Waiting for first data from server...")

elif st.session_state.disconnected_due_to_timeout:
    st.error("🚫 Application stopped: No data from server. Please restart to reconnect.")
else:
    st.info("🔌 Not connected to server.")
