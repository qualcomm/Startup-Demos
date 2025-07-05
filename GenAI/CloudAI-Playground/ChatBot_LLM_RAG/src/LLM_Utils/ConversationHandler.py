#===--ConversationHandler.py----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st

class ConvHistory_Module:
    def __init__(self, name="default"):
        self.name = name
        self.conversation_history = []

    def print_history(self):
        # Print Conversation history
        if self.conversation_history:
            st.markdown("### History")
            for i, (query, response) in enumerate(reversed(self.conversation_history)):
                Query_ID = len(self.conversation_history) - i
                
                st.markdown(f"**Query {Query_ID}:**")
                st.markdown(f"```\n{query}\n```" if query else "No Query")
                
                st.markdown(f"**Response {Query_ID}:**")
                st.markdown(response)
                
                st.markdown("---")
        else:
            st.markdown("### History Empty")
    
    def clear_history(self):
        # Clear All Coversation History
        self.conversation_history.clear()

    def update_conversation_history(self, user_input, full_response):
        self.conversation_history.append((user_input, full_response))

    def get_conversation_history(self, index):
        # Get particular conversation history
        if index < len(self.conversation_history):
            query, response = self.conversation_history[index]
            return f"Query {index}: {query}\nResponse {index}: {response}"
        else:
            return 

    def get_complete_conversation_history(self, n=0):
        if not self.conversation_history:
            return
        if n <= 0:
            return self.conversation_history
        else:
            return self.conversation_history[:n]

# Example usage:
if __name__ == "__main__":

    if 'conv_history' not in st.session_state:
        st.session_state.conv_history = ConvHistory_Module()

    conv_history = st.session_state.conv_history


    with st.form("conversation_form"):
        user_input = st.text_input("User Input")
        submit_button = st.form_submit_button("Submit")

    if submit_button:
        full_response = "This is a sample response."
        conv_history.update_conversation_history(user_input, full_response)
        st.write(conv_history.get_conversation_history(len(conv_history.conversation_history) - 1))

    st.button("Print History", on_click=conv_history.print_history)
    st.button("Clear History", on_click=conv_history.clear_history)
