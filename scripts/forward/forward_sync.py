#!/usr/bin/env python3
#===--forward_sync.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Fast-forward or merge the checked-out source commit into the configured destination."""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

from common.auth import repository_host, resolve_token
from common.cli import build_parser, resolve_dry_run, run_main
from common.clone import check_branch_name, fetch_ref, resolve_commit_sha
from common.config import load_config, validate_common_config, validate_required
from common.git import GitRunner
from common.log import setup_logging
from common.push import push_with_retries
from common.repositories import resolve_repository
from common.sanitizer import TokenSanitizer
from common.sync import apply_sync

DEFAULT_CONFIG = Path(__file__).with_name("forward_sync_config.yaml")
REQUIRED_KEYS = ("git_identity.name", "git_identity.email", "merge.message_template")


def validate_forward_config(config: dict[str, Any]) -> None:
    validate_common_config(config)
    validate_required(config, ("git_identity", "merge"), REQUIRED_KEYS)


def run_forward_sync(
    config: dict[str, Any], repository: Path, dry_run: bool, token: str, sanitizer: TokenSanitizer
) -> int:
    execution = config["execution"]
    destination = resolve_repository(config, "destination")
    with tempfile.TemporaryDirectory(prefix="forward-sync-git-auth-") as credential_directory:
        with GitRunner(
            repository,
            token,
            int(execution["operation_timeout_seconds"]),
            sanitizer,
            credential_directory=Path(credential_directory),
        ) as git:
            check_branch_name(git, destination["branch"])
            source_commit = resolve_commit_sha(git, repository)
            destination_commit = fetch_ref(git, repository, destination["url"], destination["branch"])
            logging.info("Source HEAD %s; destination %s -> %s.", source_commit, destination["branch"], destination_commit)
            git.run(["git", "checkout", "--detach", destination_commit])
            apply_sync(
                git,
                repository,
                destination_commit,
                source_commit,
                dry_run=dry_run,
                identity=config["git_identity"],
                merge_message_template=str(config["merge"]["message_template"]),
                empty_sync_is_success=bool(execution["empty_sync_is_success"]),
                labels=("destination", "source"),
                push=lambda: push_with_retries(
                    git,
                    repository,
                    destination["url"],
                    destination["branch"],
                    int(execution["push_retry_count"]),
                    float(execution["push_retry_delay_seconds"]),
                ),
            )
    return 0


def main() -> int:
    args = build_parser(__doc__, DEFAULT_CONFIG).parse_args()
    sanitizer = TokenSanitizer()

    def run() -> int:
        config_path = Path(args.config).expanduser().resolve()
        config = load_config(config_path, validate_forward_config)
        host = repository_host(resolve_repository(config, "destination")["url"])
        token = resolve_token(config, config_path, "destination", host)
        sanitizer.add(token)
        setup_logging(config["logging"], config_path, sanitizer)
        dry_run = resolve_dry_run(args, config)
        logging.info("Forward sync started (mode=%s).", "dry-run" if dry_run else "live")
        return run_forward_sync(config, Path.cwd(), dry_run, token, sanitizer)

    return run_main(run, sanitizer)


if __name__ == "__main__":
    sys.exit(main())
