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

DEPLOY="$INTERNVL_DEPLOY_DIR"
ARTIFACTS="$WORKDIR/artifacts/internvl3_1b"
BUILD="$EXECUTORCH_BUILD_DIR/examples/qualcomm/oss_scripts/llama"

mkdir -p "$DEPLOY"
cp "$BUILD/qnn_multimodal_persistent_runner" "$DEPLOY/"
cp "$BUILD/qnn_multimodal_runner" "$DEPLOY/"
cp "$QNN_BACKEND_LIB" "$DEPLOY/"
cp "$ARTIFACTS/hybrid_llama_qnn.pte" "$DEPLOY/"
cp "$ARTIFACTS/tok_embedding_qnn.pte" "$DEPLOY/"
cp "$ARTIFACTS/vision_encoder_qnn.pte" "$DEPLOY/"
cp "$ARTIFACTS/tokenizer.json" "$DEPLOY/"

echo "Packaged internvl3_1b to $DEPLOY"
