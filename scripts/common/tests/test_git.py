#===--test_git.py----------------------------------------------------------===//
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

from common.git import GitRunner, TokenSanitizer


def test_askpass_supplies_username_and_sanitized_token(tmp_path: Path):
    token = "test-secret-token"
    runner = GitRunner(tmp_path, token, 10, TokenSanitizer(token), "TEST_GIT_TOKEN")

    with runner:
        result = runner.run(
            [
                "sh",
                "-c",
                'printf "%s\\n" "$(\"$GIT_ASKPASS\" Username)"; '
                'printf "%s\\n" "$(\"$GIT_ASKPASS\" Password)"',
            ],
            authenticated=True,
        )
        assert result.stdout.splitlines() == ["x-access-token", "[REDACTED_TOKEN]"]
        assert runner.askpass_path.exists()

    assert not runner.askpass_path.exists()


def test_authenticated_command_can_use_a_different_repository_token(tmp_path: Path):
    runner = GitRunner(tmp_path, "source-token", 10, TokenSanitizer("source-token"), "TEST_GIT_TOKEN")
    with runner:
        result = runner.run(
            [
                "sh",
                "-c",
                'printf "%s\\n" "$(\"$GIT_ASKPASS\" Password)"',
            ],
            authenticated=True,
            auth_token="destination-token",
        )

    assert result.stdout.strip() == "[REDACTED_TOKEN]"
    assert "destination-token" not in result.stdout


def test_runner_rejects_invalid_token_environment_name(tmp_path: Path):
    with pytest.raises(ValueError, match="valid environment variable"):
        GitRunner(tmp_path, "token", 10, TokenSanitizer("token"), "NOT-A-VARIABLE")


def test_git_runner_streams_sanitized_output_and_returns_stdout(tmp_path: Path, caplog):
    sanitizer = TokenSanitizer("secret-token")
    with GitRunner(tmp_path, "secret-token", 10, sanitizer) as git:
        with caplog.at_level(logging.DEBUG):
            result = git.run(["git", "-c", "alias.test=!echo secret-token", "test"], cwd=tmp_path)

    assert result.stdout.strip() == "[REDACTED_TOKEN]"
    assert "[REDACTED_TOKEN]" in caplog.text
    assert "secret-token" not in caplog.text


def test_authenticated_push_uses_askpass_without_token_in_remote_url(tmp_path: Path):
    remote = tmp_path / "remote.git"
    repository = tmp_path / "source"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    (repository / "README.md").write_text("shared runner test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "test"], cwd=repository, check=True, capture_output=True)

    token = "not-used-by-file-transport"
    with GitRunner(repository, token, 10, TokenSanitizer(token), "TEST_GIT_TOKEN") as git:
        git.run(["git", "push", str(remote), "HEAD:refs/heads/main"], authenticated=True)

    pushed_commit = subprocess.run(
        ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    local_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert pushed_commit == local_commit


def test_git_runner_times_out_and_cleans_askpass(tmp_path: Path):
    runner = GitRunner(tmp_path, "test-token", 0.1, TokenSanitizer("test-token"))
    with runner:
        with pytest.raises(subprocess.TimeoutExpired):
            runner.run(["sh", "-c", "while :; do :; done"])
        assert runner.askpass_path.exists()
    assert not runner.askpass_path.exists()