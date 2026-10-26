#===--test.sh-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

curl -s http://127.0.0.1:8081/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Write one short paragraph about ExecuTorch."}'
