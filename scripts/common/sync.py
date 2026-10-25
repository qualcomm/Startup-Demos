#===--sync.py--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Direction-agnostic sync engine: bring HEAD (current) up to date with an incoming commit."""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .clone import is_ancestor
from .errors import AutomationError
from .git import GitRunner
from .merge import fast_forward, log_divergence_details, merge_or_abort


class SyncState(enum.Enum):
    SAME = "same"
    ALREADY_CONTAINED = "already_contained"
    FAST_FORWARD = "fast_forward"
    DIVERGED = "diverged"


def classify(git: GitRunner, repo_dir: Path, current_commit: str, incoming_commit: str) -> SyncState:
    if current_commit == incoming_commit:
        return SyncState.SAME
    if is_ancestor(git, repo_dir, incoming_commit, current_commit):
        return SyncState.ALREADY_CONTAINED
    if is_ancestor(git, repo_dir, current_commit, incoming_commit):
        return SyncState.FAST_FORWARD
    return SyncState.DIVERGED


def log_sync_preview(git: GitRunner, repo_dir: Path, current_commit: str, incoming_commit: str) -> None:
    commit_log = git.run(
        ["git", "log", "--oneline", f"{current_commit}..{incoming_commit}"], cwd=repo_dir
    ).stdout.strip()
    logging.info("Commits that would be synchronized:\n%s", commit_log or "(none)")
    diff_stat = git.run(["git", "diff", "--stat", current_commit, incoming_commit], cwd=repo_dir).stdout.strip()
    logging.info("Files that would be synchronized:\n%s", diff_stat or "(none)")


def apply_sync(
    git: GitRunner,
    repo_dir: Path,
    current_commit: str,
    incoming_commit: str,
    *,
    dry_run: bool,
    identity: dict[str, Any],
    merge_message_template: str,
    push: Callable[[], None],
    empty_sync_is_success: bool = True,
    labels: tuple[str, str] = ("current", "incoming"),
) -> SyncState:
    """Fast-forward or merge `incoming_commit` into HEAD at `current_commit`, then call `push` unless dry run."""
    current_label, incoming_label = labels
    state = classify(git, repo_dir, current_commit, incoming_commit)
    logging.info("Sync state (%s <- %s): %s.", current_label, incoming_label, state.value)

    if state in (SyncState.SAME, SyncState.ALREADY_CONTAINED):
        message = f"{incoming_label.capitalize()} commit is already contained in {current_label} history; nothing to sync."
        if not empty_sync_is_success:
            raise AutomationError(message)
        logging.info(message)
        return state

    if state is SyncState.DIVERGED:
        log_divergence_details(git, repo_dir, current_commit, incoming_commit, labels)
        merge_commit = merge_or_abort(
            git, repo_dir, current_commit, incoming_commit, dry_run, identity, merge_message_template
        )
        if dry_run:
            return state
        push()
        logging.info("Sync completed with merge commit %s.", merge_commit)
        return state

    log_sync_preview(git, repo_dir, current_commit, incoming_commit)
    if dry_run:
        logging.info(
            "Dry run: %s would fast-forward to %s; no commit or push performed.", current_label, incoming_commit
        )
        return state
    logging.info("Fast-forwarding %s to %s.", current_label, incoming_commit)
    fast_forward(git, repo_dir, incoming_commit)
    push()
    logging.info("Sync completed successfully; %s now at %s.", current_label, incoming_commit)
    return state
