#===--build_host.sh-------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env_host.sh"

source "$WORKDIR/.venv/bin/activate"

# Install ExecuTorch
cd "$EXECUTORCH_ROOT"
./install_executorch.sh 2>&1 | tee "$HOST_OUTPUT_DIR/install_executorch.log"
examples/models/llama/install_requirements.sh

# Build Qualcomm backend
./backends/qualcomm/scripts/build.sh --skip_linux_android 2>&1 | tee "$HOST_OUTPUT_DIR/build_qualcomm.log"
