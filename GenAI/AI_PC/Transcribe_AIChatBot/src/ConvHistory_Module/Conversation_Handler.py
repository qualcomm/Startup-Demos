#===--Conversation_Handler.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import os

class ConvHistory_Module:
    def __init__(self, name="default"):
        self.name = name
        if 'conversation_history' not in st.session_state:
            st.session_state.conversation_history = []

    def print_history(self):
        if st.session_state.conversation_history:
            st.markdown("### History")
            for i, (query, response) in enumerate(reversed(st.session_state.conversation_history)):
                Query_ID = len(st.session_state.conversation_history) - i
                
                st.markdown(f"**Query {Query_ID}:**")
                st.markdown(f"```\n{query}\n```" if query else "No Query")
                
                st.markdown(f"**Response {Query_ID}:**")
                st.markdown(response)
                
                st.markdown("---")

    def clear_history(self):
        if st.session_state.conversation_history:
            del st.session_state.conversation_history
            st.session_state.conversation_history = []
            st.success("Conversation history cleared!")

