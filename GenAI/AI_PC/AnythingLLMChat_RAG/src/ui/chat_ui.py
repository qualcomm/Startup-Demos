#===--chat_ui.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
UI module for Streamlit-based chat interface.
"""
import streamlit as st
from typing import AsyncGenerator, Callable
from llm.config_manager import check_auth
from llm.document_manager import get_upload_manager
from llm.workspace_manager import init_workspace_manager, get_workspace_manager

async def stream_response(
    response_generator: AsyncGenerator[str, None],
    placeholder: st.delta_generator.DeltaGenerator,
) -> None:
    """
    Stream the LLM response to the Streamlit UI in real-time.
    Args:
        response_generator: Async generator yielding response chunks
        placeholder: Streamlit placeholder for dynamic updates
    """
    full_response = ""
    async for chunk in response_generator:
        full_response += chunk
        placeholder.markdown(full_response)
    placeholder.markdown(full_response)

def render_chat_ui(
    on_submit: Callable[[str, bool], AsyncGenerator[str, None]]
) -> None:
    from ui.sidebar_ui import render_sidebar
    from ui.config_ui import render_config_editor
    
    # Authorization check at the start
    if not check_auth():
        st.error("Authorization failed: Invalid API key or server unreachable. Please check your settings.")
        st.stop()
    
    # Initialize workspace manager after auth check
    workspace_manager = init_workspace_manager()
    if workspace_manager:
        # Check if the configured workspace exists, create if not
        workspace_manager.check_and_create()
    
    # Initialize thread manager after auth check
    from llm.conversation_manager import get_thread_manager
    thread_manager = get_thread_manager()
    thread_manager.create_thread()  # Ensure thread exists
    
    # Always fetch latest chat history from backend
    thread_manager.get_thread_chat_history()

    # Navigation: if user clicks config editor button, show config editor
    if st.session_state.get('show_config_editor'):
        render_config_editor()
        # Clear the flag so returning to main UI works
        st.session_state['show_config_editor'] = False
        st.stop()  # Prevent further UI rendering in this run
        return
    render_sidebar()
    st.title("Anything LLM Chat + RAG")

    # Initialize chat history in thread manager if empty
    if not thread_manager.get_chat_history():
        thread_manager.clear_chat_history()

    # User prompt input at the bottom
    with st.form(key='chat_input_form', clear_on_submit=True):
        user_prompt = st.text_area("Your message:", "", height=60, key='chat_input')
        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("Send")
        with col2:
            new_chat = st.checkbox("New Chat", value=False, key="new_chat_checkbox", help="Start a new chat thread")

    placeholder = st.empty()
    if submit and user_prompt.strip():
        # Add user message to thread manager
        thread_manager.append_chat('user', user_prompt.strip())
        st.info("Streaming response...")
        import asyncio
        async def get_bot_response():
            bot_response = ""
            async for chunk in on_submit(user_prompt.strip(), new_chat):
                bot_response += chunk
                placeholder.markdown(f"<div style='text-align: left; margin-bottom: 8px;'><span style='background: #f1f0f0; color: #222; padding: 8px 14px; border-radius: 16px; display: inline-block; font-size: 1.05em;'>🤖 {bot_response}</span></div>", unsafe_allow_html=True)
            return bot_response
        bot_response = asyncio.run(get_bot_response())
        placeholder.empty()
        # Add bot response to thread manager
        thread_manager.append_chat('bot', bot_response)
        st.rerun()

    for msg in thread_manager.get_chat_history():
        if msg['role'] == 'user':
            st.markdown(f"<div style='text-align: right; margin-bottom: 8px;'><span style='background: #e6f7ff; color: #005a9e; padding: 8px 14px; border-radius: 16px; display: inline-block; font-size: 1.05em;'>🙋‍♂️ {msg['content']}</span></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align: left; margin-bottom: 8px;'><span style='background: #f1f0f0; color: #222; padding: 8px 14px; border-radius: 16px; display: inline-block; font-size: 1.05em;'>🤖 {msg['content']}</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
