#===---------AI_ChatBot.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
from LLM_Module import LLM_Utils
from Audio_Module import TTS
from ConvHistory_Module import Conversation_Handler
import os
import time

def main():
    st.set_page_config(page_title="AI ChatBot", layout="wide")
    st.title("AI ChatBot")
    st.markdown("*Chat with the AI*")

    # Sidebar for LLM API Settings
    st.sidebar.header("🔐 LLM API Settings")
    base_url = st.sidebar.text_input("Base URL", value=st.session_state.get("base_url", "http://localhost:3001/api/v1/workspace"))
    workspace_name = st.sidebar.text_input("Workspace Name", value=st.session_state.get("workspace_name", "test"))
    api_key = st.sidebar.text_input("API Key", value=st.session_state.get("llm_api_key", ""), type="password")

    # Save to session state
    st.session_state.base_url = base_url
    st.session_state.workspace_name = workspace_name
    st.session_state.llm_api_key = api_key
    st.session_state.llm_api_url = f"{base_url}/{workspace_name}/chat"

    # Initialize session state variables
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []

    if 'user_input' not in st.session_state:
        st.session_state.user_input = ""

    tts_handler = TTS.TTS_Module()
    conv_handler = Conversation_Handler.ConvHistory_Module()

    user_input = st.text_area(
        "Type your Query",
        value=st.session_state.user_input,
        height=100,
        placeholder="Enter Query",
        max_chars=1000,
        key="input_area"
    )

    if st.button(" 📚 Generate Response"):
        if not user_input.strip():
            st.error("Please enter a question or topic first!")
            return

        st.markdown("**Generating Text Response**")
        try:
            full_response = LLM_Utils.generate_llm_response(user_input)
            if full_response:
                # Convert response to speech
                st.markdown("**Text-to-Speech**")
                speech_file = f"speech_audio_{int(time.time())}.wav"
                speech_output = tts_handler.text_to_speech(full_response.strip(), speech_file)
                st.audio(speech_output)

                # Remove the speech file after use
                if os.path.exists(speech_file):
                    os.remove(speech_file)
        except Exception as e:
            st.error(f"Error generating response: {str(e)}")

    # Reset button to clear conversation history
    st.sidebar.markdown("**Clear History Settings:**")
    if st.sidebar.button("Reset History"):
        conv_handler.clear_history()

    # Print conversation history
    conv_handler.print_history()

if __name__ == "__main__":
    main()

