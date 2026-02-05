#===--setup_dog_dark_detector.sh----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
# Usage:
#   ARD_TAG=<tag> ./setup_dog_dark_detector.sh
# Example:
#   ARD_TAG=0.6.3 ./setup_dog_dark_detector.sh

set -euo pipefail

ARD_TAG="${ARD_TAG:-0.6.3}"

# Qualcomm source (already cloned by you)
QCOM_SRC_DIR="$HOME/Startup-Demos"
QCOM_SRC_SUB="Others/IoT-Robotics/Dog_Bark_Detector"
QCOM_SRC="$QCOM_SRC_DIR/$QCOM_SRC_SUB"

# Final destination (requested: under ~/ArduinoApps)
BASE="$HOME/ArduinoApps"
DST="$BASE/Dog_Bark_Detector"

# Arduino repo (temporary clone only to read the example)
ARD_REPO="https://github.com/arduino/app-bricks-examples.git"
ARD_DIR="$HOME/app-bricks-examples"      # temporary, will be removed at the end
SRC_SUB="examples/audio-classification"

# --- Pre-checks ---
[ -d "$QCOM_SRC" ] || { echo "[ERR] Qualcomm app not found at: $QCOM_SRC"; exit 1; }

# Ensure destination exists; if missing, seed once with your Qualcomm app
mkdir -p "$BASE"
if [ ! -d "$DST" ]; then
  echo "[INFO] Creating destination and seeding with Qualcomm app..."
  mkdir -p "$DST"
  cp -rn "$QCOM_SRC"/. "$DST"/
fi

# Optional convenience symlink
ln -sf "$DST" "$HOME/Dog_Bark_Detector"

# --- 1) Shallow clone Arduino repo directly at the tag; sparse-checkout the example ---
rm -rf "$ARD_DIR"
git clone --no-checkout --filter=tree:0 --depth=1 --branch "$ARD_TAG" "$ARD_REPO" "$ARD_DIR"
cd "$ARD_DIR"
git sparse-checkout init --no-cone
git sparse-checkout set "$SRC_SUB"
git checkout

SRC="$ARD_DIR/$SRC_SUB"
[ -d "$SRC" ] || { echo "[ERR] Source example not found: $SRC"; exit 1; }

cd "$SRC"
find . -type f \
  ! -path './README.md' \
  ! -path './assets/docs_assets/*' \
  ! -path './assets/app.js' \
  ! -path './assets/index.html' \
  ! -path './python/main.py' \
  -print0 | while IFS= read -r -d '' f; do
    rel="${f#./}"
    if [ ! -e "$DST/$rel" ]; then
      mkdir -p "$DST/$(dirname "$rel")"
      cp -n "$SRC/$rel" "$DST/$rel"
      echo "Copied: $rel"
    else
      echo "Skip (exists): $rel"
    fi
  done

# --- 3) Clean up temporary clone to keep workspace tidy ---
cd ~
rm -rf "$ARD_DIR"

echo
echo "[DONE] Synced new files into: $DST"
echo "[INFO] Source example: $SRC_SUB  (tag: $ARD_TAG)"
echo "[INFO] Final location: $DST"

