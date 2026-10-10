#===--run.sh--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../common/env_target.sh"

DEPLOY="$LLAMA_DEPLOY_DIR"

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8081}
SEQ_LEN=${SEQ_LEN:-1024}

exec python3 "$SCRIPT_DIR/api.py" \
  --host "$HOST" --port "$PORT" \
  --runner-binary "$DEPLOY/qnn_llama_persistent_runner" \
  --model-path "$DEPLOY/hybrid_llama_qnn.pte" \
  --tokenizer-path "$DEPLOY/tokenizer.model" \
  --decoder-model-version llama3 \
  --eval-mode 0 \
  --seq-len "$SEQ_LEN"
