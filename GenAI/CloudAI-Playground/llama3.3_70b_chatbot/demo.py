#===--demo.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from typing import List, Optional, Union
from transformers import PreTrainedTokenizer, PreTrainedTokenizerFast
import QEfficient
import transformers
import numpy as np
from QEfficient.generation.text_generation_inference import *

# === Setup model and tokenizer once ===
tokenizer = transformers.AutoTokenizer.from_pretrained("meta-llama/Llama-3.3-70B-Instruct")
qpc_path = "/your/target/folder/qpc"
device_id = [0, 1, 2, 3]
generation_len = 2048

batch_size, ctx_len, full_batch_size = get_compilation_dims(qpc_path)

# Initialize model executor once
generate_text = TextGeneration(
    tokenizer=tokenizer,
    qpc_path=qpc_path,
    device_id=device_id,
    ctx_len=ctx_len,
    enable_debug_logs=False,
    write_io_dir=None,
    full_batch_size=full_batch_size,
    is_tlm=False
)

generate_text._full_batch_size=None

# === Continuous prompt loop ===
while True:
    prompt_text = input("🗣️ Enter your question (or 'exit' to quit): ")
    if prompt_text.strip().lower() == "exit":
        print("👋 Goodbye！")
        break

    prompt_list: List[str] = fix_prompts([prompt_text], batch_size, full_batch_size)
    exec_info = generate_text.generate(
        prompt=prompt_list,
        generation_len=generation_len,
        stream=True
    )

    # Print result
    print("📝 Output：")
    for result in exec_info.generated_texts:
        print(result)

    print_latency_stats_kv(prompt_list, exec_info=exec_info, automation=True)

