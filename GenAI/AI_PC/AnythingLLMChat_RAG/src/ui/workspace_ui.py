#===--workspace_ui.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
UI module for workspace management in Streamlit.
"""
import streamlit as st
from llm.config_manager import check_auth
from llm.workspace_manager import get_workspace_manager, init_workspace_manager

class WorkspaceUI:
    def __init__(self):
        self.workspace_manager = get_workspace_manager()
    
    def render(self):
        """Render the workspace management UI."""
        st.title("Workspace Management")
        
        # Display current workspace
        current_workspace = self.workspace_manager.get_workspace_details()
        if current_workspace:
            st.markdown(f"**Current Workspace:** {current_workspace.get('name', 'Unknown')}")
            st.markdown(f"**Description:** {current_workspace.get('description', 'No description')}")
        else:
            st.warning("No workspace selected or unable to fetch workspace details.")
        
        # List available workspaces
        st.subheader("Available Workspaces")
        workspaces = self.workspace_manager.get_workspaces()
        if workspaces:
            for workspace in workspaces:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{workspace.get('name')}** ({workspace.get('slug')})")
                with col2:
                    if st.button("Select", key=f"select_{workspace.get('slug')}"):
                        self.workspace_manager.set_current_workspace(workspace.get('slug'))
                        st.success(f"Selected workspace: {workspace.get('name')}")
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"delete_{workspace.get('slug')}"):
                        if self.workspace_manager.delete_workspace(workspace.get('slug')):
                            st.success(f"Deleted workspace: {workspace.get('name')}")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete workspace: {workspace.get('name')}")
        else:
            st.info("No workspaces available.")
        
        # Create new workspace
        st.subheader("Create New Workspace")
        with st.form("create_workspace_form"):
            name = st.text_input("Workspace Name")
            description = st.text_area("Description")
            submit = st.form_submit_button("Create")
            
            if submit and name:
                if self.workspace_manager.create_workspace(name, description):
                    st.success(f"Created workspace: {name}")
                    st.rerun()
                else:
                    st.error(f"Failed to create workspace: {name}")

def render_workspace_ui():
    """Render the workspace management UI."""
    # Authorization check at the start
    if not check_auth():
        st.error("Authorization failed: Invalid API key or server unreachable. Please check your settings.")
        st.stop()
    
    # Initialize workspace manager after auth check
    workspace_manager = init_workspace_manager()
    if workspace_manager:
        # Check if the configured workspace exists, create if not
        workspace_manager.check_and_create()
    
    WorkspaceUI().render()
