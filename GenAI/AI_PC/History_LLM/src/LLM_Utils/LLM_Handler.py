#===--LLM_Handler.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import requests
import os

class LLM_Module:
    def __init__(self):
        self.api_base = "http://127.0.0.1:1234"
        self.timeout = 60

    def generate(self, prompt, max_length=2048, additional_context=None, add_ons=None, resp_len=None):
        try:
            
            requests.get(self.api_base, timeout=2)  
        except requests.exceptions.ConnectionError:
            raise Exception(
                "LLM Connection Failure"
                f"at {self.api_base} Initiate Retry."
            )
            
        
        if add_ons:
            prompt = f"Focus on Developmental Aspects {add_ons} and how it impacted the human life. {prompt}"
            
        
        if additional_context:
            prompt = f"Using this historical context:\n{additional_context}\n\n{prompt}"
            
        
        if resp_len:
            prompt = f"Give the summary in no more than {resp_len} words.\n\n{prompt}"
            prompt = f"Prepare the summary in no more than 5 paragraphs.\n\n{prompt}"
        
        try:
            response = requests.post(
                f"{self.api_base}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": max_length,
                    "stream": True
                },
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code == 200:
                return response.iter_lines()
            else:
                raise Exception(f"Error: {response.status_code}, {response.text}")
            
        except requests.exceptions.Timeout:
            raise Exception("Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
