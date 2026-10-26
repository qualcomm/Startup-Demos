#===--build_target.sh-----------------------------------------------------===//
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
source "$WORKDIR/.venv/bin/activate"

# Python deps
cd "$EXECUTORCH_ROOT"
pip install -r requirements-dev.txt torch==2.12.0 --extra-index-url https://download.pytorch.org/whl/test/cpu 2>&1 | tee "$TARGET_OUTPUT_DIR/pip_install.log"
examples/models/llama/install_requirements.sh 2>&1 | tee "$TARGET_OUTPUT_DIR/install_llama_requirements.log"

# Build ExecuTorch
rm -rf "$EXECUTORCH_BUILD_DIR"
cmake -DCMAKE_INSTALL_PREFIX="$EXECUTORCH_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DEXECUTORCH_BUILD_QNN=ON \
  -DEXECUTORCH_BUILD_EXTENSION_LLM=ON \
  -DEXECUTORCH_BUILD_EXTENSION_LLM_RUNNER=ON \
  -DEXECUTORCH_BUILD_EXTENSION_MODULE=ON \
  -DEXECUTORCH_BUILD_EXTENSION_DATA_LOADER=ON \
  -DEXECUTORCH_BUILD_EXTENSION_FLAT_TENSOR=ON \
  -DEXECUTORCH_BUILD_EXTENSION_NAMED_DATA_MAP=ON \
  -DEXECUTORCH_BUILD_EXTENSION_TENSOR=ON \
  -DEXECUTORCH_BUILD_KERNELS_QUANTIZED=ON \
  -DEXECUTORCH_BUILD_DEVTOOLS=ON \
  -DEXECUTORCH_ENABLE_EVENT_TRACER=ON \
  -DEXECUTORCH_ENABLE_LOGGING=ON \
  -DQNN_SDK_ROOT="$QNN_SDK_ROOT" \
  -DPYTHON_EXECUTABLE=python3 \
  -S . -B "$EXECUTORCH_BUILD_DIR"

cmake --build "$EXECUTORCH_BUILD_DIR" -j$(nproc) --target install 2>&1 | tee "$TARGET_OUTPUT_DIR/build_executorch.log"

# Build QNN example runners
cmake examples/qualcomm \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$EXECUTORCH_BUILD_DIR;$EXECUTORCH_BUILD_DIR/third-party/gflags;" \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH \
  -DSUPPORT_REGEX_LOOKAHEAD=ON \
  -DBUILD_TESTING=OFF \
  -DEXECUTORCH_ENABLE_LOGGING=ON \
  -DPYTHON_EXECUTABLE=python3 \
  -B "$EXECUTORCH_BUILD_DIR/examples/qualcomm"

cmake --build "$EXECUTORCH_BUILD_DIR/examples/qualcomm" -j$(nproc) \
  --target qnn_multimodal_runner qnn_multimodal_persistent_runner qnn_llama_persistent_runner 2>&1 | tee "$TARGET_OUTPUT_DIR/build_qnn_runners.log"
