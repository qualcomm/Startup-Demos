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

mkdir -p "$INTERNVL_ARTIFACT_DIR"

cd "$EXECUTORCH_ROOT"
python3 examples/qualcomm/oss_scripts/llama/llama.py \
  --build_folder "$QNN_BUILD_FOLDER" \
  --soc_model "$SOC_MODEL" \
  --decoder_model "$INTERNVL_MODEL" \
  --model_mode hybrid \
  --prefill_ar_len 32 \
  --max_seq_len 1024 \
  --prompt "Can you describe this image?" \
  --calib_samples examples/qualcomm/oss_scripts/llama/assets/samples/vision.json \
  --artifact "$INTERNVL_ARTIFACT_DIR" \
  --compile_only 2>&1 | tee "$HOST_OUTPUT_DIR/export_internvl3_1b.log"
