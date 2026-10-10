#===--export.sh-----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../common/env_host.sh"

if [[ ! -d "$LLAMA_RAW_MODEL_DIR" ]]; then
  echo "Download Llama-3.2-3B-Instruct from https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct"
  echo "Place it at: $LLAMA_RAW_MODEL_DIR"
  exit 1
fi

mkdir -p "$LLAMA_ARTIFACT_DIR"

cd "$EXECUTORCH_ROOT"
python3 examples/qualcomm/oss_scripts/llama/llama.py \
  --build_folder "$QNN_BUILD_FOLDER" \
  --soc_model "$SOC_MODEL" \
  --checkpoint "$LLAMA_RAW_MODEL_DIR/original/consolidated.00.pth" \
  --params "$LLAMA_RAW_MODEL_DIR/original/params.json" \
  --tokenizer_model "$LLAMA_RAW_MODEL_DIR/original/tokenizer.model" \
  --decoder_model llama3_2-3b_instruct \
  --model_mode hybrid \
  --prefill_ar_len 128 \
  --max_seq_len 1024 \
  --prompt "I would like to learn python, could you teach me with a simple example?" \
  --calib_tasks wikitext \
  --calib_limit 1 \
  --artifact "$LLAMA_ARTIFACT_DIR" \
  --compile_only 2>&1 | tee "$HOST_OUTPUT_DIR/export_llama_3_2_3b.log"
