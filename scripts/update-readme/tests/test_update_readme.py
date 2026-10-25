#===--test_update_readme.py------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

import importlib.util
import subprocess
from pathlib import Path

from common.config import load_config
from common.sanitizer import TokenSanitizer

SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1]
MODULE_PATH = SCRIPT_DIRECTORY / "update_readme.py"
SPEC = importlib.util.spec_from_file_location("update_readme", MODULE_PATH)
update_readme = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(update_readme)


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def prepare_repository(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    repository = tmp_path / "checkout"
    git("init", "--bare", str(remote))
    repository.mkdir()
    git("init", "-b", "main", cwd=repository)
    git("config", "user.name", "Test", cwd=repository)
    git("config", "user.email", "test@example.com", cwd=repository)
    (repository / "README.md").write_text("initial\n", encoding="utf-8")
    git("add", "README.md", cwd=repository)
    git("commit", "-m", "initial", cwd=repository)
    git("remote", "add", "origin", str(remote), cwd=repository)
    git("push", "origin", "HEAD:refs/heads/main", cwd=repository)
    (repository / "README.md").write_text("updated\n", encoding="utf-8")
    return remote, repository


def readme_config() -> dict:
    return load_config(SCRIPT_DIRECTORY / "update_readme_config.yaml", update_readme.validate_readme_config)


def test_readme_push_commits_and_updates_branch(tmp_path: Path):
    remote, repository = prepare_repository(tmp_path)

    update_readme.push_readme(
        readme_config(), repository, "main", "update generated README", "test-token", TokenSanitizer("test-token")
    )

    assert git("--git-dir", str(remote), "log", "-1", "--format=%s", "refs/heads/main") == "update generated README"
    assert git("--git-dir", str(remote), "show", "refs/heads/main:README.md") == "updated"
    assert git("log", "-1", "--format=%an", cwd=repository) == "github-actions[bot]"


def test_readme_dry_run_does_not_commit_or_push(tmp_path: Path):
    remote, repository = prepare_repository(tmp_path)
    remote_before = git("--git-dir", str(remote), "rev-parse", "refs/heads/main")

    update_readme.push_readme(
        readme_config(), repository, "main", "msg", "test-token", TokenSanitizer("test-token"), dry_run=True
    )

    assert git("--git-dir", str(remote), "rev-parse", "refs/heads/main") == remote_before
    assert git("log", "-1", "--format=%s", cwd=repository) == "initial"
