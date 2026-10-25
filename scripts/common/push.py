#===--push.py--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Commit, push with retries, and restore helpers."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from pathlib import Path

from .errors import AutomationError, GitCommandError
from .git import GitRunner


def commit_paths(git: GitRunner, repo_dir: Path, paths: Iterable[str], message: str) -> None:
    git.run(["git", "add", "--", *paths], cwd=repo_dir)
    git.run(["git", "commit", "-m", message], cwd=repo_dir)


def push_with_retries(
    git: GitRunner,
    repo_dir: Path,
    remote: str,
    branch: str,
    retry_count: int,
    retry_delay_seconds: float,
    auth_token: str | None = None,
) -> None:
    command = ["git", "push", remote, f"HEAD:refs/heads/{branch}"]
    attempts = retry_count + 1
    last_error: GitCommandError | None = None
    for attempt in range(1, attempts + 1):
        try:
            git.run(command, cwd=repo_dir, authenticated=True, auth_token=auth_token)
            return
        except GitCommandError as error:
            last_error = error
            if attempt == attempts:
                break
            logging.warning("Push attempt %s failed; retrying in %s seconds.", attempt, retry_delay_seconds)
            time.sleep(retry_delay_seconds)
    raise GitCommandError(
        "Push failed. Repository permissions or branch-protection settings may have prevented the update. "
        f"Details: {last_error}"
    )


def restore_repository(git: GitRunner, repo_dir: Path) -> None:
    try:
        git.run(["git", "reset", "--hard", "HEAD"], cwd=repo_dir)
        git.run(["git", "clean", "-fdx"], cwd=repo_dir)
    except AutomationError as error:
        logging.warning("Failed to restore repository %s after error: %s", repo_dir, error)
