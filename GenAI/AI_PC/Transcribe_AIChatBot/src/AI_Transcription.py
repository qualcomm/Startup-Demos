#===---------AI_Transcription.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
from datetime import datetime
from pydub import AudioSegment
import tempfile
import os
import yaml
import time

from Audio_Module import Record  # Reusing your existing audio recording logic
from Whisper_Module.whisper_npu import WhisperWrapper_Module  # Modularized Whisper logic

def load_config(config_path="config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    st.set_page_config(page_title="Whisper Transcription", layout="wide")
    st.title("🎙️ Whisper Transcription")
    st.markdown("Transcribe audio using NPU-accelerated Whisper models")

    # Load configuration from YAML
    config = load_config()
    model_size = config.get("model_size", "base")
    encoder_path = config.get("encoder_path")
    decoder_path = config.get("decoder_path")

    # Audio input options
    st.sidebar.header("Audio Input")
    input_mode = st.sidebar.radio("Input Mode", ["Microphone", "Upload File"])

    audio_handler = Record.Audio_Module()
    audio_file = None

    if input_mode == "Microphone":
        devices = audio_handler.list_input_devices()
        device_names = [name for idx, name in devices]
        selected_device = st.sidebar.selectbox("Select Input Device", options=device_names)
        device_index = next(idx for idx, name in devices if name == selected_device)
        duration = st.sidebar.slider("Recording Duration (seconds)", 5, 60, 10)
    else:
        uploaded_file = st.file_uploader("Upload an audio file", type=["wav", "mp3", "m4a"])
        if uploaded_file:
            # Save uploaded file with original extension
            temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1])
            temp_input.write(uploaded_file.read())
            temp_input.close()

            # Convert to WAV if not already WAV
            if not uploaded_file.name.lower().endswith('.wav'):
                audio = AudioSegment.from_file(temp_input.name)
                temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                audio.export(temp_wav.name, format='wav')
                audio_file = temp_wav.name
            else:
                audio_file = temp_input.name

    # Transcription
    if st.button("Start Transcription"):
        if input_mode == "Microphone":
            st.info("Recording audio...")
            audio_file = f"recorded_audio_{int(datetime.now().timestamp())}.wav"
            audio_handler.record_audio(audio_file, duration, device_index)
        elif not audio_file:
            st.warning("Please upload an audio file before clicking the button.")
            return

        try:
            whisper_model = WhisperWrapper_Module(encoder_path, decoder_path, model_size)
            transcription = whisper_model.transcribe_audio(audio_file)

            st.markdown("### Transcription Output")
            if not transcription.strip():
                st.warning("Transcription failed or returned empty. Please try recording again.")
            else:
                st.text_area("Transcribed Text", transcription, height=150)

        except Exception as e:
            st.error(f"Transcription failed: {str(e)}")

        finally:
            if audio_file and os.path.exists(audio_file):
                try:
                    time.sleep(1)
                    os.remove(audio_file)
                except:
                    pass

if __name__ == "__main__":
    main()

