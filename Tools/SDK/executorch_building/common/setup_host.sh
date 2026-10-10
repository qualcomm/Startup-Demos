#===--setup_host.sh-------------------------------------------------------===//
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

# System deps
sudo apt install -y cmake ninja-build python3-venv python3-dev pkg-config libc++1 libc++abi1

# Python venv
cd "$WORKDIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

# Clone and patch ExecuTorch
git clone https://github.com/pytorch/executorch.git
cd executorch
git checkout "$EXECUTORCH_COMMIT"
git fetch "$SCRIPT_DIR/../patch/deepak-executorch-main.bundle" HEAD:my_runner
git checkout my_runner
git submodule sync --recursive
git submodule update --init --recursive

# Download QAIRT SDK
cd "$WORKDIR"
wget "https://softwarecenter.qualcomm.com/api/download/software/sdks/Qualcomm_AI_Runtime_Community/All/${QAIRT_VERSION}/v${QAIRT_VERSION}.zip"
unzip "v${QAIRT_VERSION}.zip"
rm "v${QAIRT_VERSION}.zip"
cd "$WORKDIR"

# Output log directory
mkdir -p "$HOST_OUTPUT_DIR"
