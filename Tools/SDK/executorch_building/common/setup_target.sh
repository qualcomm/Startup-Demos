#===--setup_target.sh-----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env_target.sh"

mkdir -p "$TARGET_OUTPUT_DIR"

# Board packages
{
sudo add-apt-repository -y ppa:ubuntu-qcom-iot/qcom-ppa || true
sudo apt update
sudo apt install -y qcom-fastrpc1 qcom-fastrpc-dev qairt-dsp-binaries qairt-libs
sudo apt install -y python3-dev pkg-config libzstd-dev cmake ninja-build
} 2>&1 | tee "$TARGET_OUTPUT_DIR/setup_target.log"

# FastRPC group
sudo usermod -aG fastrpc "$USER"
sudo systemctl restart cdsprpcd

# Python venv
cd "$WORKDIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel 2>&1 | tee "$TARGET_OUTPUT_DIR/pip_setup.log"

# Clone and patch ExecuTorch
git clone https://github.com/pytorch/executorch.git 2>&1 | tee "$TARGET_OUTPUT_DIR/git_clone.log"
cd executorch
git checkout "$EXECUTORCH_COMMIT"
git fetch "$SCRIPT_DIR/../patch/deepak-executorch-main.bundle" HEAD:deepak-runner
git checkout deepak-runner
git submodule sync --recursive
git submodule update --init --recursive 2>&1 | tee "$TARGET_OUTPUT_DIR/git_submodules.log"

# Download QAIRT SDK
cd "$WORKDIR"
wget "https://softwarecenter.qualcomm.com/api/download/software/sdks/Qualcomm_AI_Runtime_Community/All/${QAIRT_VERSION}/v${QAIRT_VERSION}.zip"
unzip "v${QAIRT_VERSION}.zip"
rm "v${QAIRT_VERSION}.zip"
