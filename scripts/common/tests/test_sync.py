#===--test_sync.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

import logging
import subprocess
from pathlib import Path

import pytest

from common.clone import fetch_ref, resolve_commit_sha
from common.errors import GitCommandError, MergeConflictError
from common.git import GitRunner
from common.push import push_with_retries
from common.sanitizer import TokenSanitizer
from common.sync import SyncState, apply_sync, classify

IDENTITY = {"name": "Sync Bot", "email": "sync-bot@example.com"}
TEMPLATE = "Merge {incoming} into {current}"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(repository: Path, name: str, content: str) -> str:
    (repository / name).write_text(content, encoding="utf-8")
    git("add", name, cwd=repository)
    git("commit", "-m", f"change {name}", cwd=repository)
    return git("rev-parse", "HEAD", cwd=repository)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git("init", "-b", "main", cwd=path)
    git("config", "user.name", "Test", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    commit(path, "base.txt", "base\n")
    return path


@pytest.fixture
def runner(repository: Path):
    with GitRunner(repository, "token", 30, TokenSanitizer("token")) as git_runner:
        yield git_runner


def branch_from_base(repository: Path, name: str, filename: str, content: str) -> str:
    git("checkout", "-q", "-b", name, "main~0", cwd=repository)
    sha = commit(repository, filename, content)
    git("checkout", "-q", "main", cwd=repository)
    return sha


def test_classify_reports_every_state(repository, runner):
    base = git("rev-parse", "HEAD", cwd=repository)
    ahead = branch_from_base(repository, "ahead", "ahead.txt", "ahead\n")
    other = branch_from_base(repository, "other", "other.txt", "other\n")

    assert classify(runner, repository, base, base) is SyncState.SAME
    assert classify(runner, repository, ahead, base) is SyncState.ALREADY_CONTAINED
    assert classify(runner, repository, base, ahead) is SyncState.FAST_FORWARD
    assert classify(runner, repository, ahead, other) is SyncState.DIVERGED


def test_apply_sync_fast_forwards_and_pushes(repository, runner):
    base = git("rev-parse", "HEAD", cwd=repository)
    incoming = branch_from_base(repository, "incoming", "incoming.txt", "incoming\n")
    pushes = []

    state = apply_sync(
        runner, repository, base, incoming,
        dry_run=False, identity=IDENTITY, merge_message_template=TEMPLATE, push=lambda: pushes.append(True),
    )

    assert state is SyncState.FAST_FORWARD
    assert resolve_commit_sha(runner, repository) == incoming
    assert pushes == [True]


def test_apply_sync_dry_run_never_pushes(repository, runner):
    base = git("rev-parse", "HEAD", cwd=repository)
    incoming = branch_from_base(repository, "incoming", "incoming.txt", "incoming\n")

    apply_sync(
        runner, repository, base, incoming,
        dry_run=True, identity=IDENTITY, merge_message_template=TEMPLATE, push=lambda: pytest.fail("pushed"),
    )

    assert resolve_commit_sha(runner, repository) == base


def test_apply_sync_merges_divergent_history_with_template(repository, runner):
    incoming = branch_from_base(repository, "incoming", "incoming.txt", "incoming\n")
    current = commit(repository, "current.txt", "current\n")

    apply_sync(
        runner, repository, current, incoming,
        dry_run=False, identity=IDENTITY, merge_message_template=TEMPLATE, push=lambda: None,
    )

    assert git("rev-parse", "HEAD^1", cwd=repository) == current
    assert git("rev-parse", "HEAD^2", cwd=repository) == incoming
    assert git("log", "-1", "--format=%s|%an", cwd=repository) == f"Merge {incoming[:12]} into {current[:12]}|Sync Bot"


def test_apply_sync_conflict_aborts_merge(repository, runner, caplog):
    git("checkout", "-q", "-b", "incoming", cwd=repository)
    incoming = commit(repository, "base.txt", "incoming\n")
    git("checkout", "-q", "main", cwd=repository)
    current = commit(repository, "base.txt", "current\n")

    with caplog.at_level(logging.ERROR), pytest.raises(MergeConflictError, match="base.txt"):
        apply_sync(
            runner, repository, current, incoming,
            dry_run=False, identity=IDENTITY, merge_message_template=TEMPLATE, push=lambda: pytest.fail("pushed"),
        )

    assert resolve_commit_sha(runner, repository) == current
    assert not (repository / ".git" / "MERGE_HEAD").exists()


def test_apply_sync_empty_sync_can_be_an_error(repository, runner):
    head = git("rev-parse", "HEAD", cwd=repository)

    with pytest.raises(Exception, match="nothing to sync"):
        apply_sync(
            runner, repository, head, head, dry_run=False, identity=IDENTITY,
            merge_message_template=TEMPLATE, push=lambda: None, empty_sync_is_success=False,
        )


def test_fetch_ref_returns_remote_tip(tmp_path, repository, runner):
    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote), cwd=tmp_path)
    head = git("rev-parse", "HEAD", cwd=repository)
    git("push", str(remote), "HEAD:refs/heads/release", cwd=repository)

    assert fetch_ref(runner, repository, str(remote), "release") == head


def test_push_with_retries_pushes_and_reports_final_failure(tmp_path, repository, runner, caplog):
    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote), cwd=tmp_path)

    push_with_retries(runner, repository, str(remote), "main", retry_count=0, retry_delay_seconds=0)
    assert git("--git-dir", str(remote), "rev-parse", "refs/heads/main", cwd=tmp_path) == git(
        "rev-parse", "HEAD", cwd=repository
    )

    with caplog.at_level(logging.WARNING), pytest.raises(GitCommandError, match="Push failed"):
        push_with_retries(runner, repository, str(tmp_path / "missing.git"), "main", 1, 0)
    assert "Push attempt 1 failed" in caplog.text
