#===--config_ui.py--------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Streamlit UI for viewing and editing config.yaml.
"""
import streamlit as st
import yaml
import os

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../app_config.yaml'))

class ConfigEditor:
    def __init__(self, config_path=CONFIG_PATH):
        self.config_path = config_path
        self.session_key = 'config_editor_values'

    def load_config(self):
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def save_config(self, config):
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)

    def ensure_session_state(self):
        if self.session_key not in st.session_state:
            config = self.load_config()
            st.session_state[self.session_key] = {
                'api_key': config.get('api_key', ''),
                'model_server_base_url': config.get('model_server_base_url', ''),
                'workspace_slug': config.get('workspace_slug', ''),
                'stream': bool(config.get('stream', False)),
                'stream_timeout': int(config.get('stream_timeout', 60)),
                'document_folder': config.get('document_folder', 'default_folder'),
                'thread_name': config.get('thread_name', 'default_thread'),
            }

    def render(self):
        st.title('AnythingLLM Config Editor')
        self.ensure_session_state()
        values = st.session_state[self.session_key]
        st.info('Edit the configuration below and click Save to update config.yaml.')
        with st.form('config_form'):
            api_key = st.text_input('API Key', values['api_key'], key='config_api_key')
            model_server_base_url = st.text_input('Model Server Base URL', values['model_server_base_url'], key='config_model_server_base_url')
            workspace_slug = st.text_input('Workspace Slug', values['workspace_slug'], key='config_workspace_slug')
            stream = st.checkbox('Stream', value=values['stream'], key='config_stream')
            stream_timeout = st.number_input('Stream Timeout (seconds)', min_value=1, max_value=600, value=values['stream_timeout'], key='config_stream_timeout')
            document_folder = st.text_input('Document Folder', values.get('document_folder', 'default_folder'), key='config_document_folder')
            thread_name = st.text_input('Thread Name', values.get('thread_name', 'default_thread'), key='config_thread_name')
            submitted = st.form_submit_button('Save and Test Connection')
            test_result = None
            if submitted:
                new_config = {
                    'api_key': api_key,
                    'model_server_base_url': model_server_base_url,
                    'workspace_slug': workspace_slug,
                    'stream': stream,
                    'stream_timeout': stream_timeout,
                    'document_folder': document_folder,
                    'thread_name': thread_name
                }
                self.save_config(new_config)
                st.session_state[self.session_key] = new_config
                # Reinitialize AuthManager after saving config
                from llm import config_manager as auth
                auth._auth_manager = None
                auth.init(config_path=self.config_path)
                
                # Test connection using AuthManager
                if auth.check_auth():
                    # Reinitialize workspace manager if auth is successful
                    from llm.workspace_manager import init_workspace_manager
                    workspace_manager = init_workspace_manager()
                    if workspace_manager:
                        # Check if the configured workspace exists, create if not
                        workspace_manager.check_and_create()
                    st.success('Configuration saved and connection successful!')
                else:
                    st.error('Configuration saved, but connection failed! Please check your settings.')
        st.markdown('---')
        st.markdown('**Raw config.yaml:**')
        with open(self.config_path, 'r') as f:
            st.code(f.read(), language='yaml')

def render_config_editor():
    ConfigEditor().render()
