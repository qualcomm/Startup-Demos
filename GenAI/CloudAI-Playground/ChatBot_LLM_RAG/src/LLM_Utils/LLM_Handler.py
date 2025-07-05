#===--LLM_Handler.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from openai import OpenAI
import httpx

class LLM_Module:
    def __init__(self, endpoint: str, api_key: str, model: str = "Llama-3.1-8B"):
        self.api_endpoint = endpoint
        self.api_key = api_key
        self.model_name = model
        self.timeout = 60
        self.openai_client = None
        
    def set_model(self, model: str = "Llama-3.1-8B"):
        if not model:
            raise ValueError("Model name cannot be empty")
        self.model_name = model

    def get_client(self) -> OpenAI:
        if not self.openai_client:
            self.openai_client = OpenAI(
                base_url=self.api_endpoint,
                api_key=self.api_key,
                http_client=httpx.Client(verify=False)
            )
        return self.openai_client

    def generate(self, prompt, max_length: int = 2048) -> str:
        client = self.get_client()
        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=prompt,
                # stream=True,
                stream=False,
                max_tokens=512
            )
            return response.choices[0].message.content
        except httpx.TimeoutException:
            raise Exception("Request timed out. Please try again.")
        except httpx.HTTPError as e:
            raise Exception(f"HTTP error: {str(e)}")
        except Exception as e:
            raise Exception(f"Network error: {str(e)}")

    def get_models(self) -> list:
        client = self.get_client()
        try:
            models = client.models.list()
            return models.llm
        except Exception as e:
            raise Exception("LLM_Module: Get Models Failed!")
