#!/usr/bin/env bash
#===--forward-sync.test.sh-------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

set -euo pipefail

script_directory=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
repo_root=$(cd "$script_directory/../.." && pwd)
script_path="$script_directory/forward_sync.py"
test_directory=$(mktemp -d)
trap 'rm -rf "$test_directory"' EXIT

setup_repository() {
  scenario_directory="$test_directory/$1"
  mkdir -p "$scenario_directory"
  git init --quiet --bare "$scenario_directory/destination.git"
  git init --quiet --initial-branch=main "$scenario_directory/source"
  source_directory="$scenario_directory/source"
  git -C "$source_directory" config user.name "Sync Test"
  git -C "$source_directory" config user.email "sync-test@example.com"
  printf 'base\n' > "$source_directory/shared.txt"
  git -C "$source_directory" add shared.txt
  git -C "$source_directory" commit --quiet -m base
  git -C "$source_directory" push --quiet "$scenario_directory/destination.git" main
  base_commit=$(git -C "$source_directory" rev-parse HEAD)
}

commit_source() {
  printf 'source\n' > "$source_directory/source.txt"
  git -C "$source_directory" add source.txt
  git -C "$source_directory" commit --quiet -m source
  source_commit=$(git -C "$source_directory" rev-parse HEAD)
}

commit_destination() {
  git -C "$source_directory" checkout --quiet -b destination "$base_commit"
  printf 'destination\n' > "$source_directory/destination.txt"
  git -C "$source_directory" add destination.txt
  git -C "$source_directory" commit --quiet -m destination
  destination_commit=$(git -C "$source_directory" rev-parse HEAD)
  git -C "$source_directory" push --quiet "$scenario_directory/destination.git" HEAD:main
  git -C "$source_directory" checkout --quiet main
}

run_sync() (
  cd "$source_directory"
  PYTHONPATH="$repo_root/scripts" \
    SYNC_DEST_TOKEN=test-token \
    SYNC_DEST_URL=https://destination.example/repository.git \
    SYNC_DEST_BRANCH=main \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="url.file://$scenario_directory/destination.git.insteadOf" \
    GIT_CONFIG_VALUE_0=https://destination.example/repository.git \
    python3 "$script_path" > "$scenario_directory/sync.log" 2>&1
)

destination_head() {
  git --git-dir="$scenario_directory/destination.git" rev-parse refs/heads/main
}

setup_repository fast-forward
commit_source
run_sync
[[ $(destination_head) == "$source_commit" ]]
echo "PASS: fast-forward preserves the exact source commit"

setup_repository diverged
commit_source
commit_destination
run_sync
merged_commit=$(destination_head)
[[ $(git -C "$source_directory" rev-parse "$merged_commit^1") == "$destination_commit" ]]
[[ $(git -C "$source_directory" rev-parse "$merged_commit^2") == "$source_commit" ]]
echo "PASS: divergence creates a merge commit preserving both histories"

setup_repository destination-ahead
commit_destination
run_sync
[[ $(destination_head) == "$destination_commit" ]]
echo "PASS: an already-ahead destination remains unchanged"

setup_repository conflict
printf 'source conflict\n' > "$source_directory/shared.txt"
git -C "$source_directory" commit --quiet -am "source conflict"
git -C "$source_directory" checkout --quiet -b destination "$base_commit"
printf 'destination conflict\n' > "$source_directory/shared.txt"
git -C "$source_directory" commit --quiet -am "destination conflict"
destination_commit=$(git -C "$source_directory" rev-parse HEAD)
git -C "$source_directory" push --quiet "$scenario_directory/destination.git" HEAD:main
git -C "$source_directory" checkout --quiet main
if run_sync; then
  echo "FAIL: conflicting histories unexpectedly succeeded" >&2
  exit 1
fi
[[ $(destination_head) == "$destination_commit" ]]
[[ ! -f "$source_directory/.git/MERGE_HEAD" ]]
echo "PASS: conflicts fail without pushing and abort the local merge"