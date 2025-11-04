#===---------LLM_Utils.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import os
import requests
import uuid

def generate_prompt(conversation_history, user_input, max_length=100, num_conversations=5):
    def truncate(text, max_length):
        return text if len(text) <= max_length else text[:max_length] + '...'

    history = "\n".join([f"User: {truncate(q, max_length)}\nAI: {truncate(r, max_length)}"
                         for q, r in conversation_history[-num_conversations:]])
    prompt = f"{history}\nUser: {truncate(user_input, max_length)}\nAI:"
    return prompt

def generate_llm_response(user_input):
    prompt = generate_prompt(st.session_state.conversation_history, user_input, num_conversations=5)

    # Dynamic configuration from session state
    config = {
        "endpoint": st.session_state.get("llm_api_url", "http://localhost:3001/api/v1/workspace/test/chat"),
        "api_key": st.session_state.get("llm_api_key", "")
    }

    if not config["api_key"] or not config["endpoint"]:
        st.error("API Key or Endpoint is missing. Please check the sidebar settings.")
        return ""

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }

    payload = {
        "message": prompt,
        "mode": "chat",
        "sessionId": str(uuid.uuid4()),
        "enable_thinking": False,
        "context": "",
        "overrideConfig": {
            "max_tokens": 512
        }
    }

    response_placeholder = st.empty()
    full_response = ""

    with st.spinner("Thinking..."):
        try:
            response = requests.post(config["endpoint"], headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    full_response = json_data.get("response") or json_data.get("textResponse") or "No valid response field found."
                    response_placeholder.markdown(full_response)
                    st.session_state.conversation_history.append((user_input, full_response))
                    st.session_state.user_input = ""
                except Exception as parse_error:
                    st.error(f"Failed to parse JSON response: {str(parse_error)}")
                    st.text(response.text)
            else:
                st.error(f"LLM API Error: {response.status_code} - {response.text}")
        except requests.exceptions.Timeout:
            st.error("Request timed out. The model might be busy, please try again.")
        except requests.exceptions.RequestException as e:
            st.error(f"Network error: {str(e)}")

    return full_response

