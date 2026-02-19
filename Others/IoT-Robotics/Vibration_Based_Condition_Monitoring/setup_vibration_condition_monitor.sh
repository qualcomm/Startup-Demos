#===--setup_vibration_condition_monitor.sh----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
# Usage:
#   ARD_TAG=<tag> ./setup_vibration_condition_monitor.sh
# Example:
#   ARD_TAG=0.6.3 ./setup_vibration_condition_monitor.sh

set -euo pipefail

ARD_TAG="${ARD_TAG:-0.6.3}"

# Qualcomm source (already cloned by you)
QCOM_SRC_DIR="$HOME/Startup-Demos"
QCOM_SRC_SUB="Others/IoT-Robotics/Vibration_Based_Condition_Monitoring"
QCOM_SRC="$QCOM_SRC_DIR/$QCOM_SRC_SUB"

# Final destination (requested: under ~/ArduinoApps)
BASE="$HOME/ArduinoApps"
DST="$BASE/Vibration_Based_Condition_Monitoring"

# Arduino repo (temporary clone only to read the example)
ARD_REPO="https://github.com/arduino/app-bricks-examples.git"
ARD_DIR="$HOME/app-bricks-examples"      # temporary, will be removed at the end
SRC_SUB="examples/real-time-accelerometer"

# Patch settings
PATCH_FILE="${PATCH_FILE:-}"
PATCH_DIR="${PATCH_DIR:-$DST/patch}"
PATCH_STRIP="${PATCH_STRIP:-3}"  # strip 'a', 'examples', 'real-time-accelerometer'

# --- Helpers ---
die() { echo "[ERR] $*" >&2; exit 1; }

apply_patch_file() {
  local p="$1"
  echo "[INFO] Applying patch: $p"

  # Ensure we're at $DST
  cd "$DST"

  # If not a git repo, initialize and make a seed commit
  if [ ! -d .git ]; then
    echo "[INFO] Initializing git repo in $DST"
    git init -q
    git config user.name "${GIT_USER_NAME:-Local Patch Bot}"
    git config user.email "${GIT_USER_EMAIL:-local@patch}"
    git add -A
    git commit -q -m "Seed app (Arduino example: $SRC_SUB @ $ARD_TAG) + Qualcomm app files"
  fi

  # Detect mailbox/format-patch vs plain diff
  if head -n 1 "$p" | grep -qE '^From [0-9a-f]{7,40} '; then
    echo "[INFO] Detected mailbox patch; attempting git am -p$PATCH_STRIP"
    if git am -p"$PATCH_STRIP" --keep-cr "$p"; then
      echo "[INFO] git am applied: $(basename "$p")"
      return 0
    else
      echo "[WARN] git am failed; aborting am and falling back to git apply"
      git am --abort || true
    fi
  else
    echo "[INFO] Plain unified diff detected; using git apply -p$PATCH_STRIP"
  fi

  # Fallback to git apply (stages changes with --index)
  if git apply -p"$PATCH_STRIP" --index --reject --whitespace=fix "$p"; then
    git commit -q -m "Apply patch: $(basename "$p")"
    echo "[INFO] git apply committed: $(basename "$p")"
  else
    die "Failed to apply patch: $p (even after fallback)"
  fi
}

# --- Pre-checks ---
[ -d "$QCOM_SRC" ] || die "Qualcomm app not found at: $QCOM_SRC"

# Ensure destination exists; if missing, seed once with your Qualcomm app
mkdir -p "$BASE"
if [ ! -d "$DST" ]; then
  echo "[INFO] Creating destination and seeding with Qualcomm app..."
  mkdir -p "$DST"
  cp -rn "$QCOM_SRC"/. "$DST"/
fi

# Optional convenience symlink
ln -sf "$DST" "$HOME/Vibration_Based_Condition_Monitoring"

# --- 1) Shallow clone Arduino repo directly at the tag; sparse-checkout the example ---
rm -rf "$ARD_DIR"
git clone --no-checkout --filter=tree:0 --depth=1 --branch "$ARD_TAG" "$ARD_REPO" "$ARD_DIR"
cd "$ARD_DIR"
git sparse-checkout init --no-cone
git sparse-checkout set "$SRC_SUB"
git checkout

SRC="$ARD_DIR/$SRC_SUB"
[ -d "$SRC" ] || die "Source example not found: $SRC"

# --- 2) Copy only missing files from Arduino example into DST ---
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

# --- 3) Apply patch(es) inside DST ---
if [ -n "$PATCH_FILE" ] && [ -f "$PATCH_FILE" ]; then
  apply_patch_file "$PATCH_FILE"
elif [ -d "$PATCH_DIR" ]; then
  shopt -s nullglob
  found_any=false
  for p in "$PATCH_DIR"/*.patch "$PATCH_DIR"/*.diff; do
    found_any=true
    apply_patch_file "$p"
  done
  shopt -u nullglob
  if [ "$found_any" = false ]; then
    echo "[INFO] No *.patch or *.diff files found in $PATCH_DIR; skipping patch step."
  fi
else
  echo "[INFO] No PATCH_FILE provided and PATCH_DIR not found ($PATCH_DIR); skipping patch step."
fi

# --- 4) Clean up temporary clone to keep workspace tidy ---
cd ~
rm -rf "$ARD_DIR"

echo
echo "[DONE] Synced new files into: $DST"
echo "[INFO] Source example: $SRC_SUB  (tag: $ARD_TAG)"
echo "[INFO] Final location: $DST"

