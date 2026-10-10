#===--run.sh--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

screen -dmS video-analysis-backend bash -lc 'cd "'$ROOT_DIR'" && ./venv/bin/python -m flask --app backend/app.py run --host 0.0.0.0 --port 5000 --debug'
screen -dmS video-analysis-frontend bash -lc 'cd "'$ROOT_DIR'" && npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173'

echo "backend: screen -r video-analysis-backend"
echo "frontend: screen -r video-analysis-frontend"
