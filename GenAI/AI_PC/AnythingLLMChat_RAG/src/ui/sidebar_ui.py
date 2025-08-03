#===--sidebar_ui.py-------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Sidebar module for Streamlit UI.
"""
import streamlit as st
from llm.config_manager import check_auth
from llm.document_manager import get_upload_manager
from llm.conversation_manager import get_thread_manager
from llm.workspace_manager import get_workspace_manager

def render_sidebar():
    st.sidebar.title("AnythingLLM Chat")
    # Always check and update auth status on every render
    auth_status = check_auth()
    st.session_state['auth_status'] = auth_status
    if not auth_status:
        st.sidebar.markdown('<span style="color:red;"><i>Connection failed. Please check your settings.</i></span>', unsafe_allow_html=True)
        st.stop()
    st.sidebar.markdown('<span style="color:green;"><i>Connection successful.</i></span>', unsafe_allow_html=True)
        
    # Scrollable box for uploaded files
    upload_manager = get_upload_manager()
    files = upload_manager.get_uploaded_files()
    file_map = files  # Already a list of {'name', 'title'} dicts
    st.sidebar.markdown("**Uploaded Documents:**")
    if file_map:
        # Custom scrollable box using HTML/CSS, show title, but keep name in map for future use
        st.sidebar.markdown(f'''
        <div style="max-height: 180px; overflow-y: auto; overflow-x: auto; border: 1px solid #ccc; border-radius: 4px; padding: 8px; background: #fafafa; font-size:70%; white-space: nowrap;">
            {''.join(f'<div style="margin-bottom: 6px; white-space: nowrap;">{file["title"]}</div>' for file in file_map)}
        </div>
        ''', unsafe_allow_html=True)
        if st.sidebar.button('🗑️ Clear All Documents', key='clear_docs_btn', help='Delete all documents in the folder'):
            success = upload_manager.clear_documents()
            if success:
                st.sidebar.success('All documents cleared!')
                st.rerun()
            else:
                st.sidebar.error('Failed to clear documents.')
    else:
        st.sidebar.info("No files found in AnythingLLM.")
        
    # PDF upload in sidebar
    import time
    # Use a unique key based on time to force reset after upload
    upload_key = f'sidebar_pdf_upload_{int(time.time() * 1000)}' if 'reset_upload' in st.session_state else 'sidebar_pdf_upload'
    uploaded_file = st.sidebar.file_uploader('Upload a PDF', type=['pdf'], key=upload_key)
    if uploaded_file is not None:
        import tempfile, os
        progress_placeholder = st.sidebar.empty()
        # Use the original file name for the temp file
        original_filename = uploaded_file.name
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, original_filename)
        with open(temp_path, 'wb') as tmp:
            tmp.write(uploaded_file.read())
        # Show status message while uploading
        progress_placeholder.info('Uploading Please Wait!')
        upload_success = upload_manager.upload_pdf_to_anythingllm(temp_path)
        progress_placeholder.empty()
        st.session_state['reset_upload'] = True
        if upload_success:
            st.sidebar.success('PDF uploaded to AnythingLLM successfully!')
        else:
            st.sidebar.error('Failed to upload PDF to AnythingLLM.')
        # Try to remove the file, retrying if PermissionError occurs (up to 2 minutes)
        deleted = False
        dot_idx = 0
        cleanup_placeholder = st.sidebar.empty()
        for i in range(1200):
            try:
                os.remove(temp_path)
                deleted = True
                break
            except PermissionError:
                cleanup_placeholder.markdown(f'Cleaning up temp file')
                time.sleep(0.1)
        cleanup_placeholder.empty()
        if not deleted:
            st.sidebar.warning(f'Could not delete temp file. Please remove {temp_path} manually.')
    elif 'reset_upload' in st.session_state:
        # Remove the reset flag after the next rerun
        del st.session_state['reset_upload']
    # Display current workspace info
    st.sidebar.markdown('---')
    st.sidebar.markdown('**Workspace Info**')
    workspace_manager = get_workspace_manager()
    current_workspace = workspace_manager.get_workspace_details()
    if current_workspace:
        st.sidebar.markdown(f"Current: **{current_workspace.get('name', 'Unknown')}**")
    else:
        st.sidebar.warning("No workspace selected")
    
    # Add Reset Thread button at the end of the sidebar
    st.sidebar.markdown('---')
    if st.sidebar.button('🔄 Reset Thread', key='reset_thread_btn', help='Delete and recreate the current thread'):
        thread_manager = get_thread_manager()
        thread_name = thread_manager.get_thread_name()
        deleted = thread_manager.delete_thread(thread_name)
        created = thread_manager.create_thread(thread_name) if deleted else False
        if deleted and created:
            st.sidebar.success('Thread reset successfully!')
            st.rerun()
        elif not deleted:
            st.sidebar.error('Failed to delete thread.')
        else:
            st.sidebar.error('Failed to create thread after deletion.')
