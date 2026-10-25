#!/usr/bin/env python3
#===--update_readme.py-----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Commit and push the generated README through the shared Git helpers."""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

from common.auth import resolve_token
from common.cli import build_parser, resolve_dry_run, run_main
from common.clone import check_branch_name
from common.config import load_config, validate_common_config, validate_required
from common.git import GitRunner
from common.log import setup_logging
from common.merge import configure_identity
from common.push import commit_paths, push_with_retries
from common.sanitizer import TokenSanitizer

DEFAULT_CONFIG = Path(__file__).with_name("update_readme_config.yaml")
REQUIRED_KEYS = ("git_identity.name", "git_identity.email", "commit.paths", "push.remote")


def validate_readme_config(config: dict[str, Any]) -> None:
    validate_common_config(config)
    validate_required(config, ("git_identity", "commit", "push"), REQUIRED_KEYS)


def push_readme(
    config: dict[str, Any],
    repository: Path,
    branch: str,
    message: str,
    token: str,
    sanitizer: TokenSanitizer,
    dry_run: bool = False,
) -> None:
    execution = config["execution"]
    paths = [str(path) for path in config["commit"]["paths"]]
    with tempfile.TemporaryDirectory(prefix="readme-git-auth-") as credential_directory:
        with GitRunner(
            repository,
            token,
            int(execution["operation_timeout_seconds"]),
            sanitizer,
            credential_directory=Path(credential_directory),
        ) as git:
            check_branch_name(git, branch)
            if dry_run:
                status = git.run(["git", "status", "--short", "--", *paths]).stdout.strip()
                logging.info("Dry run: would commit and push to %s:\n%s", branch, status or "(no changes)")
                return
            configure_identity(git, repository, config["git_identity"])
            commit_paths(git, repository, paths, message)
            push_with_retries(
                git,
                repository,
                str(config["push"]["remote"]),
                branch,
                int(execution["push_retry_count"]),
                float(execution["push_retry_delay_seconds"]),
            )
    logging.info("README update pushed successfully.")


def main() -> int:
    parser = build_parser(__doc__, DEFAULT_CONFIG)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    sanitizer = TokenSanitizer()

    def run() -> int:
        config_path = Path(args.config).expanduser().resolve()
        config = load_config(config_path, validate_readme_config)
        token = resolve_token(config, config_path, "source")
        sanitizer.add(token)
        setup_logging(config["logging"], config_path, sanitizer)
        push_readme(config, Path.cwd(), args.branch, args.message, token, sanitizer, resolve_dry_run(args, config))
        return 0

    return run_main(run, sanitizer)


if __name__ == "__main__":
    sys.exit(main())
