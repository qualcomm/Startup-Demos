#===--llm_client.py-------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
LLM Client module for AnythingLLM and mock streaming.
"""
from typing import AsyncGenerator, Dict, Any
import httpx
from pydantic import BaseModel
import asyncio
import random
import yaml
import json
from llm.config_manager import get_config_value

class LLMResponse(BaseModel):
    """Model for LLM response data"""
    response: str
    done: bool

class LLMClientBase:
    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Abstract streaming method for LLM responses."""
        raise NotImplementedError

class MockLLMClient(LLMClientBase):
    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Mock streaming LLM that yields a fake response word by word."""
        response = f"You said: {prompt}. This is a mock LLM response."
        for word in response.split():
            await asyncio.sleep(random.uniform(0.05, 0.2))
            yield word + ' '

class AnythingLLMClient(LLMClientBase):
    def __init__(self):
        # Do not call init_config here; assume it is called at program launch
        self.api_key = get_config_value("api_key")
        self.base_url = get_config_value("model_server_base_url")
        self.stream = get_config_value("stream")
        self.stream_timeout = get_config_value("stream_timeout")
        self.workspace_slug = get_config_value("workspace_slug")
        # Initialize and use the shared ThreadManager instance
        from llm.conversation_manager import get_thread_manager
        self.thread_manager = get_thread_manager()
        self.thread_name = self.thread_manager.get_thread_name()
        # URL now includes thread_name
        if self.stream:
            self.chat_url = f"{self.base_url}/workspace/{self.workspace_slug}/thread/{self.thread_name}/stream-chat"
        else:
            self.chat_url = f"{self.base_url}/workspace/{self.workspace_slug}/thread/{self.thread_name}/chat"
        self.headers = {
            "accept": "application/json" if not self.stream else "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key
        }

    async def generate_stream(self, prompt: str, reset: bool = False) -> AsyncGenerator[str, None]:
        data = {
            "message": prompt,
            "mode": "chat",
            "sessionId": "example-session-id",
            "attachments": [],
            "reset": reset
        }
        buffer = ""
        async with httpx.AsyncClient(timeout=self.stream_timeout) as client:
            async with client.stream("POST", self.chat_url, headers=self.headers, json=data) as response:
                async for chunk in response.aiter_text():
                    if chunk:
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            if line.startswith("data: "):
                                line = line[len("data: ") :]
                            try:
                                parsed_chunk = json.loads(line.strip())
                                text = parsed_chunk.get("textResponse", "")
                                if text:
                                    yield text
                                if parsed_chunk.get("close", False):
                                    return
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                print(f"Error processing chunk: {e}")
                                return
