#===--document_manager.py-------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Upload Manager module for AnythingLLM API using AuthManager for config.
"""
import httpx
import os
from typing import List, Dict, Any
from llm.config_manager import get_config_value

class UploadManager:
    file_map = []  # Global file map for all instances

    def __init__(self):
        self.api_key = get_config_value("api_key")
        self.base_url = get_config_value("model_server_base_url")
        self.workspace_slug = get_config_value("workspace_slug")
        self.document_folder = get_config_value("document_folder", "default_folder")
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def update_embeddings(self, file_names: list[str]) -> bool:
        """Update embeddings for the given file names in the configured folder/workspace."""
        url = f"{self.base_url}/workspace/{self.workspace_slug}/update-embeddings"
        payload = {
            "adds": [f"{self.document_folder}/{name}" for name in file_names]
        }
        try:
            import json
            response = httpx.post(
                url,
                headers={**self.headers, "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)
            return False
        except Exception as e:
            print(f"Failed to update embeddings: {e}")
            return False

    def upload_pdf_to_anythingllm(self, pdf_path: str) -> bool:
        url = f"{self.base_url}/document/upload/{self.document_folder}"
        try:
            with open(pdf_path, "rb") as pdf_file:
                files = {
                    "file": (os.path.basename(pdf_path), pdf_file, "application/pdf"),
                    "addToWorkspaces": (None, self.workspace_slug)
                }
                response = httpx.post(url, headers=self.headers, files=files, timeout=60)
            if response.status_code == 200:
                data = response.json()
                new_names = []
                for doc in data.get("documents", []):
                    new_names.append(doc.get("name"))
                # Immediately update embeddings for the new files
                if new_names:
                    embedding_success = self.update_embeddings(new_names)
                    # After embedding, update pin for each file
                    for name in new_names:
                        doc_path = f"{self.document_folder}/{name}"
                        self.update_pin(doc_path, True)
                return True
            return False
        except Exception as e:
            print(f"Upload failed: {e}")
            return False

    def get_uploaded_files(self) -> List[Dict[str, str]]:
        # Use the document_folder from config to get files in that folder
        url = f"{self.base_url}/documents/folder/{self.document_folder}"
        try:
            response = httpx.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Build file map: list of dicts with name and title from the 'documents' key
            UploadManager.file_map = []
            for file in data.get("documents", []):
                if file.get('type') == 'file':
                    UploadManager.file_map.append({'name': file.get('name'), 'title': file.get('title')})
            return UploadManager.file_map
        except Exception as e:
            print(f"Failed to fetch uploaded files: {e}")
            return []

    def clear_documents(self) -> bool:
        """Delete the complete document folder using AnythingLLM API."""
        url = f"{self.base_url}/document/remove-folder"
        payload = {"name": self.document_folder}
        try:
            import json
            response = httpx.request(
                method="DELETE",
                url=url,
                headers={**self.headers, "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)
            return False
        except Exception as e:
            print(f"Failed to clear documents: {e}")
            return False

    def update_pin(self, doc_path: str, pin_status: bool) -> bool:
        """Update pin status for a document in the configured workspace."""
        url = f"{self.base_url}/workspace/{self.workspace_slug}/update-pin"
        payload = {
            "docPath": doc_path,
            "pinStatus": pin_status
        }
        try:
            import json
            response = httpx.post(
                url,
                headers={**self.headers, "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)
            return False
        except Exception as e:
            print(f"Failed to update pin: {e}")
            return False

# Module-level singleton instance
_upload_manager = None

def get_upload_manager():
    global _upload_manager
    if _upload_manager is None:
        _upload_manager = UploadManager()
    return _upload_manager
