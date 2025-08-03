#===--conversation_manager.py---------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Thread Manager module for AnythingLLM API using AuthManager for config.
"""
from llm.config_manager import get_config_value
import httpx

class ThreadManager:
    def __init__(self):
        self.api_key = get_config_value("api_key")
        self.base_url = get_config_value("model_server_base_url")
        self.workspace_slug = get_config_value("workspace_slug")
        self.thread_name = get_config_value("thread_name", "default_thread")
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.chat_history = []  # Store chat history for the thread

    def create_thread(self, thread_name=None):
        """Create a new thread with the given name (or current thread_name if not specified). Returns True if successful."""
        if thread_name is None:
            thread_name = self.thread_name
        url = f"{self.base_url}/workspace/{self.workspace_slug}/thread/new"
        payload = {"name": thread_name, "slug": thread_name}
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
                print(f"Failed to create thread: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Failed to create thread: {e}")
            return False

    def delete_thread(self, thread_name=None):
        """Delete a thread by name (uses current thread if not specified). Returns True if successful. Clears chat history on success."""
        if thread_name is None:
            thread_name = self.thread_name
        url = f"{self.base_url}/workspace/{self.workspace_slug}/thread/{thread_name}"
        try:
            response = httpx.request("DELETE", url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                self.clear_chat_history()
                return True
            else:
                print(f"Failed to delete thread: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Failed to delete thread: {e}")
            return False

    def get_thread_chat_history(self, thread_name=None):
        """Get chat history for a thread. Returns a list of dicts with 'role' and 'content'."""
        if thread_name is None:
            thread_name = self.thread_name
        url = f"{self.base_url}/workspace/{self.workspace_slug}/thread/{thread_name}/chats"
        try:
            response = httpx.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Extract only 'role' and 'content' from each message in 'history'
            history = [
                {"role": msg.get("role"), "content": msg.get("content")}
                for msg in data.get("history", [])
                if msg.get("role") and msg.get("content")
            ]
            self.chat_history = history
            return history
        except Exception as e:
            print(f"Failed to fetch thread chat history: {e}")
            return []

    def clear_chat_history(self):
        """Clear the in-memory chat history for the current thread."""
        self.chat_history = []

    def get_chat_history(self):
        """Return the in-memory chat history for the current thread."""
        return self.chat_history

    def get_thread_name(self):
        return self.thread_name

    def append_chat(self, role, content):
        """Append a new chat message to the in-memory chat history."""
        if role and content:
            self.chat_history.append({"role": role, "content": content})

# Module-level singleton instance
_thread_manager = None

def get_thread_manager():
    global _thread_manager
    if _thread_manager is None:
        _thread_manager = ThreadManager()
    return _thread_manager
