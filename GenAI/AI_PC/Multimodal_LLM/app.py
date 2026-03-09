#===--app.py--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import argparse
from pathlib import Path
from openai import OpenAI

def build_messages(texts, image_paths, system_prompt):

    user_content = []

    for t in texts:
        user_content.append({"type": "text", "text": t})

    for p in image_paths:
        user_content.append({
            "type": "image_url", "image_url": {"url": p}})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    return messages

def main():

    parser = argparse.ArgumentParser()
    
    parser.add_argument(
        "--text",
        action="append",
        help="User prompt.",
        default=[]
    )

    parser.add_argument(
        "--image",
        nargs="+",
        help="One or more image file paths.",
        default=[]
    )
    
    parser.add_argument("--system", default="You are a helpful AI assistant", help="System prompt.")
    parser.add_argument("--model", default="NexaAI/Qwen3-VL-4B-Instruct-NPU", help="Model name.")
    parser.add_argument("--base_url", default="http://127.0.0.1:8080/v1", help="URL of the local server.")
    parser.add_argument("--api_key", default="", help="API key if required.")
    
    args = parser.parse_args()
    
    if not args.text:
        parser.error("At least one --text prompt is required.")
    
    image_paths = []
    
    for item in args.image:
        p = Path(item)
        if not p.exists():
            raise FileNotFoundError(f"Image path not found: {item}")
        image_paths.append(item)

    try:
        client = OpenAI(base_url=args.base_url, api_key=args.api_key)

        messages = build_messages(args.text, image_paths, args.system)

        resp = client.chat.completions.create(
            model=args.model,
            messages=messages,
            stream=False
        )

        print(resp.choices[0].message.content)
    
    except Exception as e:
        print(f"Error communicating with the server: {e}")
        print("Please check your configuration and try again.")
        exit(1)

if __name__ == "__main__":
    main()
