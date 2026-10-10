#===--env_host.sh---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
# Usage: source executorch_building/common/env_host.sh

_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WORKDIR="$(cd "$_script_dir/../.." && pwd)"
export EXECUTORCH_ROOT="$WORKDIR/executorch"
export QAIRT_VERSION=2.45.0.260326
export QNN_SDK_ROOT="$WORKDIR/qairt/$QAIRT_VERSION"
export SOC_MODEL=QCS9100
export EXECUTORCH_COMMIT=fa4508ee452129722d796d03cd45c67c5d97ab98

export QNN_BUILD_FOLDER="$EXECUTORCH_ROOT/build-x86"
export ARTIFACTS_DIR="$WORKDIR/artifacts"

# InternVL
export INTERNVL_MODEL=internvl3_1b
export INTERNVL_HF_REPO="OpenGVLab/InternVL3-1B-hf"
export INTERNVL_ARTIFACT_DIR="$ARTIFACTS_DIR/$INTERNVL_MODEL"

# Llama
export LLAMA_MODEL=Llama-3.2-3B-Instruct
export LLAMA_RAW_MODEL_DIR="$WORKDIR/raw_model/Llama-3.2-3B-Instruct"
export LLAMA_ARTIFACT_DIR="$ARTIFACTS_DIR/$LLAMA_MODEL"

# Output logs
export HOST_OUTPUT_DIR="$WORKDIR/output/host"

if [[ -f "$WORKDIR/.venv/bin/activate" ]]; then
  source "$WORKDIR/.venv/bin/activate"
fi
if [[ -f "$QNN_SDK_ROOT/bin/envsetup.sh" ]]; then
  source "$QNN_SDK_ROOT/bin/envsetup.sh"
fi
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/x86_64-linux-clang:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$WORKDIR:${PYTHONPATH:-}"
