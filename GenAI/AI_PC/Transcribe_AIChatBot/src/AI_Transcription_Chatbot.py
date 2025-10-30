#===---------AI_Transcription_Chatbot.py---------------------------------------------------===//
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

from Audio_Module import Record, TTS
from Whisper_Module.whisper_npu import WhisperWrapper_Module
from LLM_Module import LLM_Utils
from ConvHistory_Module import Conversation_Handler

def load_config(config_path="config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    st.set_page_config(page_title="AI Transcription ChatBot", layout="wide")
    st.title("🎤 AI Transcription ChatBot")
    st.markdown("Speak your query and get a response from the AI")

    # Load configuration from YAML
    config = load_config()
    model_size = config.get("model_size", "base")
    encoder_path = config.get("encoder_path")
    decoder_path = config.get("decoder_path")

    # Sidebar for settings
    st.sidebar.header("🎛️ Settings")
    base_url = st.sidebar.text_input("Base URL", value=st.session_state.get("base_url", "http://localhost:3001/api/v1/workspace"))
    workspace_name = st.sidebar.text_input("Workspace Name", value=st.session_state.get("workspace_name", "test"))
    api_key = st.sidebar.text_input("API Key", value=st.session_state.get("llm_api_key", ""), type="password")

    st.session_state.base_url = base_url
    st.session_state.workspace_name = workspace_name
    st.session_state.llm_api_key = api_key
    st.session_state.llm_api_url = f"{base_url}/{workspace_name}/chat"

    audio_handler = Record.Audio_Module()
    tts_handler = TTS.TTS_Module()
    conv_handler = Conversation_Handler.ConvHistory_Module()

    devices = audio_handler.list_input_devices()
    device_names = [name for idx, name in devices]
    selected_device = st.sidebar.selectbox("Select Microphone", options=device_names)
    device_index = next(idx for idx, name in devices if name == selected_device)
    duration = st.sidebar.slider("Recording Duration (seconds)", 5, 60, 10)

    if st.button("🎙️ Record and Ask"):
        audio_file = f"recorded_query_{int(datetime.now().timestamp())}.wav"
        st.info("Recording audio...")
        audio_handler.record_audio(audio_file, duration, device_index)

        try:
            whisper_model = WhisperWrapper_Module(encoder_path, decoder_path, model_size)
            transcription = whisper_model.transcribe_audio(audio_file)

            st.markdown("### 📝 Transcription")
            if not transcription.strip():
                st.warning("Transcription failed or returned empty. Please try again.")
                return
            else:
                st.text_area("Transcribed Text", transcription, height=150)

            st.markdown("### 🤖 LLM Response")
            full_response = LLM_Utils.generate_llm_response(transcription)
            if full_response:
                #st.text_area("LLM Response", full_response, height=150)
                speech_file = f"response_audio_{int(time.time())}.wav"
                speech_output = tts_handler.text_to_speech(full_response.strip(), speech_file)
                st.audio(speech_output)
                if os.path.exists(speech_file):
                    os.remove(speech_file)

        except Exception as e:
            st.error(f"Error: {str(e)}")

        finally:
            if audio_file and os.path.exists(audio_file):
                try:
                    time.sleep(1)
                    os.remove(audio_file)
                except:
                    pass

    # Reset button to clear conversation history
    st.sidebar.markdown("**Clear History Settings:**")
    if st.sidebar.button("Reset History"):
        conv_handler.clear_history()

    # Print conversation history
    conv_handler.print_history()

if __name__ == "__main__":
    main()
