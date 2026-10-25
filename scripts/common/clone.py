#===--clone.py-------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Clone, refresh, fetch, and inspect repositories."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .git import GitRunner


def check_branch_name(git: GitRunner, branch: str) -> None:
    git.run(["git", "check-ref-format", f"refs/heads/{branch}"])


def clone_repository(git: GitRunner, repo_config: dict[str, Any], target_dir: Path, fetch_full_history: bool) -> None:
    logging.info(
        "Cloning %s@%s into %s (full_history=%s).",
        repo_config["url"], repo_config["branch"], target_dir, fetch_full_history,
    )
    command = ["git", "clone", "--progress", "--branch", str(repo_config["branch"]), "--single-branch"]
    if not fetch_full_history:
        command.extend(["--depth", "1"])
    command.extend([str(repo_config["url"]), str(target_dir)])
    git.run(command, authenticated=True)


def resync_repository(
    git: GitRunner,
    repo_config: dict[str, Any],
    target_dir: Path,
    fetch_full_history: bool,
    reset_commit_count: int,
) -> None:
    branch = str(repo_config["branch"])
    git.run(["git", "remote", "set-url", "origin", str(repo_config["url"])], cwd=target_dir)

    fetch_command = ["git", "fetch", "--progress", "origin", branch]
    if not fetch_full_history:
        fetch_command[2:2] = ["--depth", str(reset_commit_count + 1)]
    git.run(fetch_command, cwd=target_dir, authenticated=True)

    git.run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=target_dir)

    # --first-parent matches the ancestry walk that `~N` performs, unlike a plain reachable-commit count.
    completed = git.run(["git", "rev-list", "--count", "--first-parent", f"origin/{branch}"], cwd=target_dir)
    available_commits = int(completed.stdout.strip() or "1")
    rollback_count = min(reset_commit_count, max(available_commits - 1, 0))

    rollback_target = f"origin/{branch}~{rollback_count}" if rollback_count > 0 else f"origin/{branch}"
    git.run(["git", "reset", "--hard", rollback_target], cwd=target_dir)
    git.run(["git", "clean", "-fdx"], cwd=target_dir)
    git.run(["git", "reset", "--hard", f"origin/{branch}"], cwd=target_dir)


def clone_or_resync_repository(
    git: GitRunner,
    repo_config: dict[str, Any],
    target_dir: Path,
    fetch_full_history: bool,
    reset_commit_count: int,
) -> None:
    if (target_dir / ".git").is_dir():
        logging.info("Existing clone found at %s; resyncing instead of re-cloning.", target_dir)
        resync_repository(git, repo_config, target_dir, fetch_full_history, reset_commit_count)
    else:
        clone_repository(git, repo_config, target_dir, fetch_full_history)


def fetch_ref(git: GitRunner, repo_dir: Path, url: str, branch: str, auth_token: str | None = None) -> str:
    """Fetch `branch` from `url` into `repo_dir` and return the fetched commit SHA."""
    git.run(
        ["git", "fetch", "--progress", "--no-tags", url, f"refs/heads/{branch}"],
        cwd=repo_dir,
        authenticated=True,
        auth_token=auth_token,
    )
    return resolve_commit_sha(git, repo_dir, "FETCH_HEAD")


def resolve_commit_sha(git: GitRunner, target_dir: Path, ref: str = "HEAD") -> str:
    return git.run(["git", "rev-parse", ref], cwd=target_dir).stdout.strip()


def is_ancestor(git: GitRunner, target_dir: Path, ancestor_sha: str, descendant_sha: str) -> bool:
    completed = git.run(
        ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
        cwd=target_dir,
        allow_failure=True,
    )
    result = completed.returncode == 0
    logging.debug("Ancestry check %s <= %s: %s", ancestor_sha, descendant_sha, result)
    return result
