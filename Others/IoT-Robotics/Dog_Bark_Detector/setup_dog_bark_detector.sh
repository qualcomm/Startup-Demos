#===--setup_dog_bark_detector.sh----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
# Usage:
#   ARD_TAG=<tag> ./setup_dog_bark_detector.sh
# Example:
#   ARD_TAG=0.6.3 ./setup_dog_bark_detector.sh

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
  ! -path './assets/app.yaml' \
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

# --- 2) Post-sync: Update web UI labels inside Dog_Bark_Detector ---
echo "[INFO] Updating UI labels in index.html (title and h1)..."

# Find all index.html under the destination (there may be multiple, depending on layout)
mapfile -t INDEX_FILES < <(find "$DST" -type f -iname "index.html" 2>/dev/null || true)

if [ "${#INDEX_FILES[@]}" -eq 0 ]; then
  echo "[WARN] No index.html found under: $DST"
else
  for html in "${INDEX_FILES[@]}"; do
    echo "[INFO] Patching: $html"

    # Create a backup if one doesn't exist already
    [ -f "${html}.bak" ] || cp -n "$html" "${html}.bak"

    # 1) Try exact-structure replacements first (safe, minimal)
    sed -i \
      -e 's|<title>[[:space:]]*Glass[[:space:]]\+breaking[[:space:]]\+sensor[[:space:]]*</title>|<title>Dog Bark Detector</title>|I' \
      -e 's|<h1[[:space:]]\+class="arduino-text">[[:space:]]*Glass[[:space:]]\+breaking[[:space:]]\+sensor[[:space:]]*</h1>|<h1 class="arduino-text">Dog Bark Detector</h1>|I' \
      "$html"

    # 2) Fallback: replace any remaining plain occurrences (case-insensitive)
    sed -i \
      -e 's/Glass[[:space:]]\+breaking[[:space:]]\+sensor/Dog Bark Detector/Ig' \
      "$html"

    # Optional: show what changed (won't fail the script if no diff)
    if command -v diff >/dev/null 2>&1 && [ -f "${html}.bak" ]; then
      echo "[INFO] Diff vs backup:"
      diff -u "${html}.bak" "$html" || true
    fi
  done
fi

# --- 3) Clean up temporary clone to keep workspace tidy ---
cd ~
rm -rf "$ARD_DIR"

echo
echo "[DONE] Synced new files into: $DST"
echo "[INFO] Source example: $SRC_SUB  (tag: $ARD_TAG)"
echo "[INFO] Final location: $DST"
