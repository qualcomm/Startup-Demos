#===--env_target.sh-------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
# Usage: source executorch_building/common/env_target.sh

_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WORKDIR="$(cd "$_script_dir/../.." && pwd)"
export EXECUTORCH_ROOT="$WORKDIR/executorch"
export QAIRT_VERSION=2.45.0.260326
export QNN_SDK_ROOT="$WORKDIR/qairt/$QAIRT_VERSION"
export SOC_MODEL=QCS9100
export EXECUTORCH_COMMIT=fa4508ee452129722d796d03cd45c67c5d97ab98

export EXECUTORCH_BUILD_DIR="$EXECUTORCH_ROOT/cmake-out-target"
export QNN_BACKEND_LIB="$EXECUTORCH_BUILD_DIR/lib/executorch/backends/qualcomm/libqnn_executorch_backend.so"

# Prefer board-installed QNN libs
if [[ -d "$QNN_SDK_ROOT/lib/aarch64-oe-linux-gcc11.2" ]]; then
  export QNN_TARGET_LIB_DIR="$QNN_SDK_ROOT/lib/aarch64-oe-linux-gcc11.2"
else
  export QNN_TARGET_LIB_DIR="$QNN_SDK_ROOT/lib/aarch64-ubuntu-gcc9.4"
fi

# DSP paths (semicolons, not colons)
export ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib/rfsa/adsp;/dsp"

# Raw model dirs
export LLAMA_RAW_MODEL_DIR="$WORKDIR/raw_model/Llama-3.2-3B-Instruct"

# Deploy dirs
export INTERNVL_DEPLOY_DIR="$WORKDIR/deploy/internvl3_1b"
export LLAMA_DEPLOY_DIR="$WORKDIR/deploy/Llama-3.2-3B-Instruct"

# Output logs
export TARGET_OUTPUT_DIR="$WORKDIR/output/target"

export LD_LIBRARY_PATH="/usr/lib:/lib:/usr/lib/aarch64-linux-gnu:$EXECUTORCH_BUILD_DIR/lib/executorch/backends/qualcomm:$EXECUTORCH_BUILD_DIR/lib:${LD_LIBRARY_PATH:-}"

if [[ -f "$WORKDIR/.venv/bin/activate" ]]; then
  source "$WORKDIR/.venv/bin/activate"
fi
