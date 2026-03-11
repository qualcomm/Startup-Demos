#===-- openai_client_stream.py -------------------------------------------===#
# Derived from vLLM:
#   examples/online_serving/openai_chat_completion_client.py
#   https://github.com/vllm-project/vllm/blob/main/examples/online_serving/openai_chat_completion_client.py
# SPDX-License-Identifier: Apache-2.0
#
# Modifications (c) Qualcomm Technologies, Inc.
#===----------------------------------------------------------------------===#


"""
Streaming client for OpenAI Chat Completion using vLLM API server
"""

from openai import OpenAI

# set vLLM API server endpoint
openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8000/v1"

# content
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Who won the world series in 2020?"},
    {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
    {"role": "user", "content": "Where was it played?"}
]

def main():
    # init OpenAI client
    client = OpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )

    # get model
    models = client.models.list()
    model = models.data[0].id

    # set stream
    chat_completion = client.chat.completions.create(
        messages=messages,
        model=model,
        stream=True, 
    )

    print("-" * 50)
    print("Streaming chat completion results:")

    # print token streamly
    for chunk in chat_completion:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)

    print("\n" + "-" * 50)

if __name__ == "__main__":
    main()
