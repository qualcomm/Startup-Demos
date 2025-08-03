#===--config_manager.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Authorization module for AnythingLLM API using config.yaml.
"""
import yaml
import httpx
import os
from typing import Dict, Any

class AuthManager:
    def __init__(self, config_path: str = "app_config.yaml"):
        self._config_cache: Dict[str, Any] = {}
        # Resolve path relative to the src directory
        if not os.path.isabs(config_path):
            # Get the directory where this file is located
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(current_dir, config_path)
        else:
            self.config_path = config_path
        self.init_config()

    def init_config(self):
        with open(self.config_path, "r") as file:
            self._config_cache = yaml.safe_load(file)

    def get_config_value(self, key: str, default=None):
        return self._config_cache.get(key, default)

    def check_auth(self) -> bool:
        api_key = self.get_config_value("api_key")
        base_url = self.get_config_value("model_server_base_url")
        url = f"{base_url}/auth"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        try:
            response = httpx.get(url, headers=headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def get_document_folder(self):
        return self.get_config_value("document_folder", "default_folder")

    def get_thread_name(self):
        return self.get_config_value("thread_name", "default_thread")

# Module-level singleton instance
_auth_manager = None

def init(config_path: str = "app_config.yaml"):
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager(config_path)

def get_config_value(key: str, default=None):
    if _auth_manager is None:
        raise RuntimeError("AuthManager not initialized. Call init() first.")
    return _auth_manager.get_config_value(key, default)

def check_auth() -> bool:
    if _auth_manager is None:
        raise RuntimeError("AuthManager not initialized. Call init() first.")
    return _auth_manager.check_auth()
