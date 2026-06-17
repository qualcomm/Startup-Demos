#===-----------------------aisuite_llm.py------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===------------------------------------------------------------------------===//

# -*- coding: utf-8 -*-
import os
import requests
from typing import Any, Dict, List, Optional, Union
from crewai import BaseLLM

class AISuiteLLM(BaseLLM):
    """
    CrewAI Custom LLM wrapper for Cirrascale AISuite Imagine API.
    Base endpoint example:
    https://aisuite.cirrascale.com/apis/v2
    Chat endpoint used here:
    POST {endpoint}/chat/completions
    """
    
    def __init__(
        self,
        model: str,
        api_key: str,
        endpoint: str,
        temperature: float = 0.3,
        ssl_verify: Union[bool, str] = False,
        timeout: int = 60,
    ):
        super().__init__(model=model, temperature=temperature)
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.ssl_verify = ssl_verify
        self.timeout = timeout
    
    def call(
        self,
        messages: Union[str, List[Dict[str, str]]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Call the AISuite API with messages and return response.
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        url = f"{self.endpoint}/chat/completions"
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        
        if tools:
            payload["tools"] = tools
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            print(f"[AISuite] Calling {self.model} at {url}")
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                verify=self.ssl_verify,
            )
            resp.raise_for_status()
            data = resp.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                if content and content.strip():
                    print(f"[AISuite] Response received ({len(content)} chars)")
                    return content
                else:
                    print("[AISuite] Warning: Empty content in response")
                    return "Empty response from LLM"
            else:
                print(f"[AISuite] Invalid response format: {data}")
                return "Invalid response format from LLM"
        
        except requests.exceptions.Timeout:
            print("[AISuite] Request timeout")
            return "LLM request timeout"
        except requests.exceptions.ConnectionError as e:
            print(f"[AISuite] Connection error: {str(e)}")
            return "LLM connection error"
        except requests.exceptions.HTTPError as e:
            print(f"[AISuite] HTTP error: {str(e)}")
            return f"LLM HTTP error: {str(e)}"
        except Exception as e:
            print(f"[AISuite] Unexpected error: {str(e)}")
            return f"LLM error: {str(e)}"

def from_env() -> AISuiteLLM:
    """
    Initialize AISuiteLLM from environment variables.
    
    Required environment variables:
    - AISUITE_API_KEY: Your AISuite API key
    - AISUITE_ENDPOINT: AISuite endpoint (default: https://aisuite.cirrascale.com/apis/v2)
    - AISUITE_MODEL: Model name (default: Llama-3.1-8B)
    - AISUITE_SSL_VERIFY: SSL verification (default: false)
    """
    endpoint = os.getenv(
        "AISUITE_ENDPOINT",
        "https://aisuite.cirrascale.com/apis/v2"
    )
    api_key = os.getenv("AISUITE_API_KEY", "").strip()
    model = os.getenv("AISUITE_MODEL", "Llama-3.1-8B")
    ssl_verify_str = os.getenv("AISUITE_SSL_VERIFY", "false").lower().strip()
    ssl_verify = ssl_verify_str in ("1", "true", "yes")
    
    if not api_key:
        raise ValueError(
            "AISUITE_API_KEY is missing. Please add it to your .env file:\n"
            "AISUITE_API_KEY=your_api_key_here"
        )
    
    print(f"[AISuite] Initializing with model: {model}")
    print(f"[AISuite] Endpoint: {endpoint}")
    print(f"[AISuite] SSL Verify: {ssl_verify}")
    
    return AISuiteLLM(
        model=model,
        api_key=api_key,
        endpoint=endpoint,
        temperature=0.3,
        ssl_verify=ssl_verify,
        timeout=60,
    )

