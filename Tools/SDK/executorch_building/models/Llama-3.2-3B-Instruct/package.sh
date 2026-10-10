#===--package.sh----------------------------------------------------------===//
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
ARTIFACTS="$WORKDIR/artifacts/Llama-3.2-3B-Instruct"
RAW_MODEL="$LLAMA_RAW_MODEL_DIR"
BUILD="$EXECUTORCH_BUILD_DIR/examples/qualcomm/oss_scripts/llama"

mkdir -p "$DEPLOY"
cp "$BUILD/qnn_llama_persistent_runner" "$DEPLOY/"
cp "$QNN_BACKEND_LIB" "$DEPLOY/"
cp "$ARTIFACTS/hybrid_llama_qnn.pte" "$DEPLOY/"
cp "$RAW_MODEL/original/tokenizer.model" "$DEPLOY/"

echo "Packaged Llama-3.2-3B-Instruct to $DEPLOY"
