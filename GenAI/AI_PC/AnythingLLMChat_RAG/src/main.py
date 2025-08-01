#===--main.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Main entry point for the LLM Streamlit app.
"""
import streamlit as st
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from llm.llm_client import AnythingLLMClient
from llm.config_manager import init, check_auth
from typing import AsyncGenerator
from ui.chat_ui import render_chat_ui
from llm.workspace_manager import init_workspace_manager

async def anythingllm_stream(prompt: str, reset: bool = False):
    async for chunk in AnythingLLMClient().generate_stream(prompt, reset=reset):
        yield chunk

def main():
    init()  # Initialize config at program launch
    
    # Basic authentication check at startup
    if not check_auth():
        print("Authentication failed. Please check your API key and server settings.")

    st.set_page_config(page_title="AnythingLLM Chat", page_icon="💬", layout="wide")
    page = st.sidebar.radio("Navigation", ["Home", "Workspaces", "Settings"], index=0)

    if page == "Home":
        render_chat_ui(anythingllm_stream)
    elif page == "Workspaces":
        from ui.workspace_ui import render_workspace_ui
        render_workspace_ui()
    elif page == "Settings":
        from ui.config_ui import ConfigEditor
        ConfigEditor().render()

if __name__ == "__main__":
    main()
