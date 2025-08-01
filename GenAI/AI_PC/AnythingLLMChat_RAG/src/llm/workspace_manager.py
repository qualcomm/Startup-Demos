#===--workspace_manager.py-------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Workspace Manager module for AnythingLLM API using AuthManager for config.
"""
import httpx
from typing import List, Dict, Any
from llm.config_manager import get_config_value, check_auth

class WorkspaceManager:
    def __init__(self):
        self.api_key = get_config_value("api_key")
        self.base_url = get_config_value("model_server_base_url")
        self.workspace_slug = get_config_value("workspace_slug")
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get all available workspaces. Returns a list of workspace objects."""
        url = f"{self.base_url}/workspaces"
        try:
            response = httpx.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("workspaces", [])
            else:
                print(f"Failed to get workspaces: {response.status_code} {response.text}")
                return []
        except Exception as e:
            print(f"Failed to get workspaces: {e}")
            return []

    def create_workspace(self, name: str, description: str = "") -> bool:
        """Create a new workspace with the given name and description. Returns True if successful."""
        url = f"{self.base_url}/workspace/new"
        # Generate a slug from the name (lowercase, replace spaces with hyphens)
        slug = name.lower().replace(" ", "-")
        payload = {
            "name": name,
            "slug": slug,
            "description": description
        }
        try:
            response = httpx.request(
                "POST",
                url,
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                return True
            else:
                print(f"Failed to create workspace: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Failed to create workspace: {e}")
            return False

    def delete_workspace(self, slug: str) -> bool:
        """Delete a workspace by slug. Returns True if successful."""
        url = f"{self.base_url}/workspace/{slug}"
        try:
            response = httpx.request("DELETE", url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return True
            else:
                print(f"Failed to delete workspace: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Failed to delete workspace: {e}")
            return False

    def get_workspace_details(self, slug: str = None) -> Dict[str, Any]:
        """Get details for a specific workspace. If slug is None, uses the current workspace_slug."""
        if slug is None:
            slug = self.workspace_slug
        url = f"{self.base_url}/workspace/{slug}"
        try:
            response = httpx.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get workspace details: {response.status_code} {response.text}")
                return {}
        except Exception as e:
            print(f"Failed to get workspace details: {e}")
            return {}

    def set_current_workspace(self, slug: str) -> bool:
        """Set the current workspace slug in the configuration."""
        # This is a local operation that would update the config
        # In a real implementation, this would update the config file
        # For now, we'll just update the instance variable
        self.workspace_slug = slug
        return True
        
    def check_and_create(self) -> bool:
        """
        Check if the workspace specified in config.yaml exists.
        If not, create it with a default description.
        Returns True if the workspace exists or was created successfully.
        """
        # Get all available workspaces
        workspaces = self.get_workspaces()
        
        # Check if current workspace_slug exists in the list of workspaces
        workspace_exists = any(workspace.get('slug') == self.workspace_slug for workspace in workspaces)
        
        if workspace_exists:
            print(f"Workspace '{self.workspace_slug}' already exists.")
            return True
        else:
            # Workspace doesn't exist, create it
            print(f"Workspace '{self.workspace_slug}' not found. Creating it...")
            # Use the slug as the name (with first letter capitalized)
            name = self.workspace_slug.replace('-', ' ').capitalize()
            description = f"Auto-created workspace for {self.workspace_slug}"
            
            success = self.create_workspace(name, description)
            if success:
                print(f"Workspace '{self.workspace_slug}' created successfully.")
                return True
            else:
                print(f"Failed to create workspace '{self.workspace_slug}'.")
                return False

# Module-level singleton instance
_workspace_manager = None

def get_workspace_manager():
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager

def init_workspace_manager():
    """Initialize the workspace manager if auth check passes."""
    if check_auth():
        return get_workspace_manager()
    return None
