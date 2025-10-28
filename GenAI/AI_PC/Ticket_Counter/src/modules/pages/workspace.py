#===--workspace.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import sqlite3
import os
from datetime import datetime
import qrcode
from PIL import Image
import io
from pathlib import Path

from modules.utils.transcription_utils import list_input_devices, record_audio, transcribe_audio
from modules.utils.llm_utils import extract_with_llm, get_destination_insights
from modules.utils.fare_utils import get_fare_and_platform

# Resolve base directory
BASE_DIR = Path(__file__).resolve().parents[2]
DB_DIR = BASE_DIR / 'modules' / 'db'

def workspace_page():

    st.title('🎫 Ticket Counter')

    # Username input
    username = st.sidebar.text_input("Enter your username", value=st.session_state.get("username", "guest"))
    st.session_state.username = username

    # Sidebar: LLM API Settings
    st.sidebar.header("🔐 LLM API Settings")
    base_url = st.sidebar.text_input("Base URL", value=st.session_state.get("base_url", "http://localhost:3001/api/v1/workspace"))
    workspace_name = st.sidebar.text_input("Workspace Name", value=st.session_state.get("workspace_name", "test"))
    api_key = st.sidebar.text_input("API Key", value=st.session_state.get("llm_api_key", ""), type="password")

    llm_api_url = f"{base_url}/{workspace_name}/chat"
    st.session_state.base_url = base_url
    st.session_state.workspace_name = workspace_name
    st.session_state.llm_api_url = llm_api_url
    st.session_state.llm_api_key = api_key

    # Sidebar: Recording Settings
    st.sidebar.header("🎛️ Recording Settings")
    duration = st.sidebar.slider('Recording duration (seconds)', 1, 10, 5)
    input_devices, device_names = list_input_devices()
    selected_device_index = st.sidebar.selectbox("Select Microphone Device", options=range(len(device_names)), format_func=lambda x: device_names[x])

    # Load station list
    station_db_path = DB_DIR / 'stations.db'
    station_conn = sqlite3.connect(station_db_path)
    station_cursor = station_conn.cursor()
    station_cursor.execute('SELECT name FROM stations')
    stations = [row[0] for row in station_cursor.fetchall()]
    station_conn.close()

    with st.expander("ℹ️ Showing all capital cities for user reference"):
        st.markdown("### 🏙️ Available Capital Cities")
        st.markdown("\n".join([f"- {city}" for city in stations]))

    if st.button('🎤 Voice Input'):
        audio_file = record_audio(selected_device_index, duration)
        transcription = transcribe_audio(audio_file)
        print("transcription", transcription)

        if not transcription.strip():
            st.warning("⚠️ No speech detected. Please speak again.")
            if os.path.exists(audio_file):
                os.remove(audio_file)
            return

        st.session_state.transcription = transcription
        st.session_state.audio_file = audio_file
        st.session_state.confirm = None
        st.success("✅ Transcription complete")

    if st.session_state.get('transcription'):
        st.text_area('Transcribed Text', value=st.session_state.transcription, height=100)
        st.write("Is the above transcription correct?")

        col1, col2 = st.columns(2)
        if col1.button("✅ Yes"):
            st.session_state.confirm = "Yes"
        elif col2.button("❌ No"):
            st.session_state.confirm = "No"

        if st.session_state.confirm == "No":
            if 'audio_file' in st.session_state and os.path.exists(st.session_state.audio_file):
                os.remove(st.session_state.audio_file)
            st.warning("❌ Transcription rejected. Please record again.")
            del st.session_state['transcription']
            del st.session_state['confirm']
            return

        if st.session_state.confirm == "Yes":
            source, destination, ticket_count = extract_with_llm(
                st.session_state.transcription,
                stations,
                st.session_state.llm_api_url,
                st.session_state.llm_api_key
            )
            print("LLM Extraction:", source, destination, ticket_count)

            if not destination:
                st.error("❌ Could not extract destination. Please try again.")
                st.code(st.session_state.transcription, language="text")
                return

            # ✅ Use fare_utils to get fare and platform
            fare, platform = get_fare_and_platform(source, destination, ticket_count)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            qr_data = f"Fare: ₹{fare} | Platform: {platform} | Source: {source} | Destination: {destination} | Tickets: {ticket_count} | Time: {timestamp}"

            ticket_db_path = DB_DIR / 'tickets.db'
            ticket_conn = sqlite3.connect(ticket_db_path)
            ticket_cursor = ticket_conn.cursor()
            ticket_cursor.execute(
                """
                INSERT INTO tickets (username, source_station, destination_station, ticket_count, timestamp, qr_data, transcription, fare, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (username, source, destination, ticket_count, timestamp, qr_data, st.session_state.transcription, fare, platform)
            )
            ticket_conn.commit()
            ticket_conn.close()

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=5,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")

            travel_text = get_destination_insights(
                destination,
                st.session_state.llm_api_url,
                st.session_state.llm_api_key
            )

            tab1, tab2 = st.tabs(["🎫 Ticket", "🧭 Travel Info"])
            with tab1:
                st.image(buf.getvalue(), caption="🎫 Ticket QR Code")
                st.write(f"**Source:** {source}")
                st.write(f"**Destination:** {destination}")
                st.write(f"**Tickets:** {ticket_count}")
                st.write(f"**Fare:** ₹{fare}")
                st.write(f"**Platform:** {platform}")
                st.write(f"**Timestamp:** {timestamp}")
                st.write(f"**QR Data:** `{qr_data}`")
                st.download_button(
                    label="📥 Download QR Code",
                    data=buf.getvalue(),
                    file_name="ticket_qr.png",
                    mime="image/png"
                )

            with tab2:
                st.markdown(travel_text)

            if 'audio_file' in st.session_state and os.path.exists(st.session_state.audio_file):
                os.remove(st.session_state.audio_file)
                del st.session_state['audio_file']

