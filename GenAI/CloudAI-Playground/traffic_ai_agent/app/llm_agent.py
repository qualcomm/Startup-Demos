#===--llm_agent.py---------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------===//

import os
import json
import requests
from typing import Generator, Optional

# ============================================================
# vLLM Config
# ============================================================
VLLM_CHAT_URL = os.getenv(
    "VLLM_CHAT_URL",
    "http://localhost:8000/v1/chat/completions",
)
VLLM_MODEL = os.getenv(
    "VLLM_MODEL",
    "meta-llama/Llama-3.3-70B-Instruct",
)
VLLM_TIMEOUT = float(os.getenv("VLLM_TIMEOUT", "300"))

# Output budget (increase to avoid truncation)
# - For English structured explanation, 900~1600 is usually safe.
# - Keep below your server constraints if any.
MAX_COMPLETION_TOKENS = int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "1400"))

# Generation controls
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))

# ============================================================
# System Prompt (ENGLISH)
# ============================================================
SYSTEM_PROMPT = """You are the Traffic AI System's Explanation & Guidance Agent.

Rules:
- You MUST ONLY use the facts, numbers, events, trends, routing costs, and decisions that appear in the input JSON.
- Do NOT invent any missing numbers. Do NOT change signal timings or phases. You only explain and guide.
- Output MUST be in English.
- If data is insufficient, explicitly say "INSUFFICIENT DATA" and list exactly what is missing.

Write your response with the following sections (keep the numbering):
(1) Signal Adjustment Summary (phase, seconds, delta)
(2) Decision Rationale (cite trend / events / reason_codes and reference recent decisions)
(3) Two-Route Recommendation (direct vs via_B) with cost comparison and reasoning
(4) Driver Actions (1–3 bullets)
(5) Data Quality / Limitations (explicitly note what is missing, if anything)

Keep it concise but complete. Do not omit section (5).
"""

# ============================================================
# Helpers
# ============================================================
def _extract_token_from_chunk(chunk: dict) -> str:
    """
    vLLM OpenAI-compatible streaming chunks may look like:
      - {"choices":[{"delta":{"content":"..."}}], ...}
      - {"choices":[{"text":"..."}], ...}   (some variants)
    This function extracts token text in a robust way.
    """
    try:
        choice0 = chunk.get("choices", [None])[0] or {}
        # Standard OpenAI streaming
        delta = choice0.get("delta") or {}
        if isinstance(delta, dict) and delta.get("content"):
            return str(delta["content"])
        # Some server variants
        if choice0.get("text"):
            return str(choice0["text"])
        # Some may embed full message (non-stream), keep safe
        msg = choice0.get("message") or {}
        if isinstance(msg, dict) and msg.get("content"):
            return str(msg["content"])
    except Exception:
        pass
    return ""


# ============================================================
# Streaming LLM call (generator)
# ============================================================
def call_llm_stream(user_json: dict) -> Generator[str, None, None]:
    """
    Stream tokens from vLLM OpenAI-compatible server.
    Yields incremental text chunks.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here is the system context (JSON):\n"
                f"{json.dumps(user_json, ensure_ascii=False)}\n\n"
                "Please produce the full explanation strictly following the rules and section format."
            ),
        },
    ]

    # Use max_completion_tokens (newer schema) and keep max_tokens as fallback
    payload = {
        "model": VLLM_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        # fallback for older implementations
        "max_tokens": MAX_COMPLETION_TOKENS,
    }

    with requests.post(
        VLLM_CHAT_URL,
        json=payload,
        stream=True,
        timeout=VLLM_TIMEOUT,
    ) as resp:
        resp.raise_for_status()

        # vLLM uses SSE: lines like `data: {...}` and `data: [DONE]`
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue

            line = line.strip()
            if not line.startswith("data:"):
                continue

            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            token = _extract_token_from_chunk(chunk)
            if token:
                yield token


# ============================================================
# Non-stream wrapper (compatibility)
# ============================================================
def call_llm(user_json: dict) -> str:
    """
    Collect all stream chunks into a single string.
    """
    out = []
    for t in call_llm_stream(user_json):
        out.append(t)
    return "".join(out)
