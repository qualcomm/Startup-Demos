#===--test_reverse_sync.py-------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

import importlib.util
import logging
import subprocess
from pathlib import Path

import pytest

from common.config import load_config
from common.errors import ConfigurationError, MergeConflictError
from common.sanitizer import TokenSanitizer

SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPT_DIRECTORY / "reverse_sync.py"
SPEC = importlib.util.spec_from_file_location("reverse_sync", MODULE_PATH)
reverse_sync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reverse_sync)


@pytest.fixture(autouse=True)
def clear_sync_environment(monkeypatch):
    for name in ("SYNC_SOURCE_URL", "SYNC_SOURCE_BRANCH", "SYNC_DEST_URL", "SYNC_DEST_BRANCH"):
        monkeypatch.delenv(name, raising=False)


def base_config(tmp_path: Path) -> dict:
    config = load_config(SCRIPT_DIRECTORY / "reverse_sync_config.yaml", reverse_sync.validate_reverse_config)
    config["repositories"]["source"].update({"url": "https://github.com/example/source", "branch": "main"})
    config["repositories"]["destination"].update({"url": "https://github.com/example/destination", "branch": "main"})
    config["security"]["allowed_url_schemes"] = ["https", "file"]
    config["execution"].update(
        {
            "working_directory": str(tmp_path / ".reverse-sync-work"),
            "operation_timeout_seconds": 300,
            "resync_reset_commit_count": 1,
        }
    )
    config["logging"] = {"level": "INFO", "file": str(tmp_path / "reverse_sync.log")}
    return config


def init_repositories(tmp_path: Path):
    source = tmp_path / "source-repo"
    destination = tmp_path / "destination-repo"

    def git(*args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    source.mkdir()
    git("init", "-b", "main", cwd=source)
    git("config", "user.name", "Test", cwd=source)
    git("config", "user.email", "test@example.com", cwd=source)
    git("config", "receive.denyCurrentBranch", "updateInstead", cwd=source)
    return source, destination, git


def clone_destination(source: Path, destination: Path, git, tmp_path: Path) -> None:
    git("clone", "-b", "main", str(source), str(destination), cwd=tmp_path)
    git("config", "user.name", "Test", cwd=destination)
    git("config", "user.email", "test@example.com", cwd=destination)


def commit(repository: Path, git, name: str, content: str, message: str) -> str:
    (repository / name).write_text(content, encoding="utf-8")
    git("add", name, cwd=repository)
    git("commit", "-m", message, cwd=repository)
    return git("rev-parse", "HEAD", cwd=repository)


def configured(tmp_path: Path, source: Path, destination: Path) -> dict:
    config = base_config(tmp_path)
    config["repositories"]["source"]["url"] = str(source)
    config["repositories"]["destination"]["url"] = str(destination)
    return config


def test_committed_config_extends_common_defaults():
    config = load_config(SCRIPT_DIRECTORY / "reverse_sync_config.yaml", reverse_sync.validate_reverse_config)

    assert config["authentication"]["tokens"]["source"]["env_var"] == "SYNC_SOURCE_TOKEN"
    assert config["authentication"]["credentials_file"] == "reverse_sync_credentials.yaml"
    assert config["execution"]["operation_timeout_seconds"] == 7200
    assert config["execution"]["push_retry_count"] == 2


def test_rejects_unsupported_conflict_strategy(tmp_path):
    config = base_config(tmp_path)
    config["conflict_handling"]["strategy"] = "ours"

    with pytest.raises(ConfigurationError, match="strategy"):
        reverse_sync.validate_reverse_config(config)


def test_rejects_parent_traversal_clone_directory(tmp_path):
    config = base_config(tmp_path)
    config["repositories"]["source"]["clone_directory"] = "../source"

    with pytest.raises(ConfigurationError):
        reverse_sync.run_reverse_sync(config, tmp_path / "config.yaml", True, "token", TokenSanitizer("token"))


def test_destination_already_in_source_history_is_noop(tmp_path, monkeypatch):
    source, destination, git = init_repositories(tmp_path)
    commit(source, git, "file.txt", "destination\n", "destination change")
    git("clone", "-b", "main", str(source), str(destination), cwd=tmp_path)
    destination_sha = git("rev-parse", "HEAD", cwd=destination)
    source_sha = commit(source, git, "source.txt", "source\n", "source change")

    fetch_credentials = []
    original_run = reverse_sync.GitRunner.run

    def capture_destination_fetch(self, args, *run_args, **run_kwargs):
        if args[:2] == ["git", "fetch"]:
            fetch_credentials.append(run_kwargs.get("auth_token"))
        return original_run(self, args, *run_args, **run_kwargs)

    monkeypatch.setattr(reverse_sync.GitRunner, "run", capture_destination_fetch)

    assert reverse_sync.run_reverse_sync(
        configured(tmp_path, source, destination),
        tmp_path / "config.yaml",
        False,
        "source-token",
        TokenSanitizer("source-token"),
        destination_token="destination-token",
    ) == 0
    assert fetch_credentials == ["destination-token"]
    assert git("rev-parse", "HEAD", cwd=source) == source_sha
    assert git("rev-parse", "HEAD", cwd=destination) == destination_sha


def test_destination_ahead_fast_forwards_source(tmp_path):
    source, destination, git = init_repositories(tmp_path)
    commit(source, git, "base.txt", "base\n", "base commit")
    clone_destination(source, destination, git, tmp_path)
    destination_sha = commit(destination, git, "destination.txt", "destination\n", "destination change")

    result = reverse_sync.run_reverse_sync(
        configured(tmp_path, source, destination), tmp_path / "config.yaml", False, "t", TokenSanitizer("t")
    )

    assert result == 0
    assert git("rev-parse", "HEAD", cwd=source) == destination_sha


def test_divergence_cleanly_merges_and_preserves_both_tips(tmp_path, caplog):
    source, destination, git = init_repositories(tmp_path)
    commit(source, git, "base.txt", "base\n", "base commit")
    clone_destination(source, destination, git, tmp_path)
    source_sha = commit(source, git, "source-only.txt", "source\n", "source-only commit")
    destination_sha = commit(destination, git, "destination-only.txt", "destination\n", "destination-only commit")

    with caplog.at_level(logging.INFO):
        result = reverse_sync.run_reverse_sync(
            configured(tmp_path, source, destination),
            tmp_path / "config.yaml",
            False,
            "test-token",
            TokenSanitizer("test-token"),
        )

    assert result == 0
    assert "source-only commit" in caplog.text
    assert "destination-only commit" in caplog.text
    assert "source-only.txt" in caplog.text
    assert "destination-only.txt" in caplog.text
    assert "Divergent histories" in caplog.text
    merged_sha = git("rev-parse", "HEAD", cwd=source)
    assert merged_sha not in {source_sha, destination_sha}
    assert git("rev-parse", f"{merged_sha}^1", cwd=source) == source_sha
    assert git("rev-parse", f"{merged_sha}^2", cwd=source) == destination_sha
    assert git("log", "-1", "--format=%s", merged_sha, cwd=source) == (
        f"Merge destination {destination_sha[:12]} into source {source_sha[:12]}"
    )
    assert git("rev-parse", "HEAD", cwd=destination) == destination_sha


def test_divergence_dry_run_aborts_trial_merge_without_changing_remote(tmp_path, caplog):
    source, destination, git = init_repositories(tmp_path)
    commit(source, git, "source.txt", "source\n", "source change")
    clone_destination(source, destination, git, tmp_path)
    source_sha = commit(source, git, "source-only.txt", "source-only\n", "source-only change")
    destination_sha = commit(destination, git, "destination.txt", "destination\n", "destination change")

    with caplog.at_level(logging.INFO):
        result = reverse_sync.run_reverse_sync(
            configured(tmp_path, source, destination),
            tmp_path / "config.yaml",
            True,
            "test-token",
            TokenSanitizer("test-token"),
        )

    assert result == 0
    assert "merge cleanly" in caplog.text
    assert git("rev-parse", "HEAD", cwd=source) == source_sha
    assert git("rev-parse", "HEAD", cwd=destination) == destination_sha


def test_divergence_with_conflict_aborts_without_pushing(tmp_path, caplog):
    source, destination, git = init_repositories(tmp_path)
    commit(source, git, "shared.txt", "base\n", "base commit")
    clone_destination(source, destination, git, tmp_path)
    source_sha = commit(source, git, "shared.txt", "source edit\n", "source edit")
    destination_sha = commit(destination, git, "shared.txt", "destination edit\n", "destination edit")

    with caplog.at_level(logging.INFO):
        with pytest.raises(MergeConflictError, match="manual conflict resolution"):
            reverse_sync.run_reverse_sync(
                configured(tmp_path, source, destination),
                tmp_path / "config.yaml",
                False,
                "test-token",
                TokenSanitizer("test-token"),
            )

    assert "shared.txt" in caplog.text
    assert git("rev-parse", "HEAD", cwd=source) == source_sha
    assert git("rev-parse", "HEAD", cwd=destination) == destination_sha
