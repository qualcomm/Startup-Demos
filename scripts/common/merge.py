#===--merge.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Divergence reporting and conflict-aborting merges."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .clone import resolve_commit_sha
from .errors import MergeConflictError
from .git import GitRunner

MAX_LOGGED_COMMITS = 50


def configure_identity(git: GitRunner, repo_dir: Path, identity: dict[str, Any]) -> None:
    git.run(["git", "config", "user.name", str(identity["name"])], cwd=repo_dir)
    git.run(["git", "config", "user.email", str(identity["email"])], cwd=repo_dir)


def log_divergence_details(
    git: GitRunner,
    repo_dir: Path,
    current_commit: str,
    incoming_commit: str,
    labels: tuple[str, str] = ("current", "incoming"),
) -> None:
    current_label, incoming_label = labels
    counts = git.run(
        ["git", "rev-list", "--left-right", "--count", f"{current_commit}...{incoming_commit}"],
        cwd=repo_dir,
    ).stdout.split()
    current_only, incoming_only = (int(count) for count in counts)
    logging.error(
        "Divergent histories: %s has %s %s-only commit(s); %s has %s %s-only commit(s).",
        current_label, current_only, current_label, incoming_label, incoming_only, incoming_label,
    )

    for label, revision_range, count in (
        (f"{current_label.capitalize()}-only", f"{incoming_commit}..{current_commit}", current_only),
        (f"{incoming_label.capitalize()}-only", f"{current_commit}..{incoming_commit}", incoming_only),
    ):
        if count == 0:
            logging.info("%s commits: (none)", label)
            continue
        commits = git.run(
            ["git", "log", "--oneline", "--decorate", f"--max-count={MAX_LOGGED_COMMITS}", revision_range],
            cwd=repo_dir,
        ).stdout.strip()
        logging.info("%s commits (showing up to %s):\n%s", label, MAX_LOGGED_COMMITS, commits or "(none)")
        if count > MAX_LOGGED_COMMITS:
            logging.warning("%s commit list truncated: %s total.", label, count)

    merge_base = git.run(["git", "merge-base", current_commit, incoming_commit], cwd=repo_dir, allow_failure=True)
    if merge_base.returncode != 0:
        logging.warning("The histories have no common ancestor; no three-way comparison is available.")
        return
    base_sha = merge_base.stdout.strip()
    logging.info("Common ancestor: %s", base_sha)
    for label, tip in (
        (f"{current_label.capitalize()}-side changes", current_commit),
        (f"{incoming_label.capitalize()}-side changes", incoming_commit),
    ):
        diff_stat = git.run(["git", "diff", "--stat", base_sha, tip], cwd=repo_dir).stdout.strip()
        logging.info("%s since common ancestor:\n%s", label, diff_stat or "(no file changes)")


def merge_or_abort(
    git: GitRunner,
    repo_dir: Path,
    current_commit: str,
    incoming_commit: str,
    dry_run: bool,
    identity: dict[str, Any],
    message_template: str,
) -> str | None:
    """Merge `incoming_commit` into HEAD with no conflict resolution; return the merge SHA or None on dry run."""
    logging.info("Attempting a non-fast-forward merge without automatic conflict resolution.")
    merge_result = git.run(
        ["git", "merge", "--no-commit", "--no-ff", incoming_commit],
        cwd=repo_dir,
        allow_failure=True,
    )
    if merge_result.returncode != 0:
        conflicts = git.run(
            ["git", "diff", "--name-only", "--diff-filter=U"], cwd=repo_dir, allow_failure=True
        ).stdout.strip()
        merge_in_progress = git.run(
            ["git", "rev-parse", "--verify", "--quiet", "MERGE_HEAD"], cwd=repo_dir, allow_failure=True
        ).returncode == 0
        if merge_in_progress:
            git.run(["git", "merge", "--abort"], cwd=repo_dir)
        if conflicts:
            logging.error("Automatic merge needs manual conflict resolution in:\n%s", conflicts)
            raise MergeConflictError(
                "Automatic merge aborted because manual conflict resolution is required. "
                f"Conflicted files:\n{conflicts}"
            )
        raise MergeConflictError(
            "Git could not merge the divergent histories automatically and reported no resolvable conflict list. "
            f"Merge output: {merge_result.stderr.strip() or merge_result.stdout.strip()}"
        )

    if dry_run:
        git.run(["git", "merge", "--abort"], cwd=repo_dir)
        logging.info(
            "Dry run: divergent histories merge cleanly; a merge commit would preserve %s and %s. "
            "No commit or push performed.",
            current_commit, incoming_commit,
        )
        return None

    configure_identity(git, repo_dir, identity)
    message = message_template.format(current=current_commit[:12], incoming=incoming_commit[:12])
    git.run(["git", "commit", "--no-edit", "-m", message], cwd=repo_dir)
    merge_commit = resolve_commit_sha(git, repo_dir)
    logging.info(
        "Created merge commit %s with first parent %s and second parent %s.",
        merge_commit, current_commit, incoming_commit,
    )
    return merge_commit


def fast_forward(git: GitRunner, repo_dir: Path, incoming_commit: str) -> None:
    git.run(["git", "merge", "--ff-only", incoming_commit], cwd=repo_dir)
