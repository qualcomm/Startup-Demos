#!/usr/bin/env python3
#===--reverse_sync.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Reverse-sync a destination GitHub repository back into a source repository."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from common.auth import repository_host, resolve_token
from common.cli import build_parser, resolve_dry_run, run_main
from common.clone import clone_or_resync_repository, fetch_ref, resolve_commit_sha
from common.config import ensure_relative_path, load_config, validate_common_config, validate_required
from common.errors import ConfigurationError
from common.git import GitRunner
from common.log import setup_logging
from common.push import push_with_retries, restore_repository
from common.repositories import resolve_repository
from common.sanitizer import TokenSanitizer
from common.sync import apply_sync
from common.workspace import prepared_working_directory, resolve_working_directory

SCRIPT_NAME = "reverse_sync"
DEFAULT_CONFIG = Path(__file__).with_name("reverse_sync_config.yaml")
REQUIRED_SECTIONS = ("git_identity", "merge", "conflict_handling", "synchronization")
REQUIRED_KEYS = (
    "git_identity.name",
    "git_identity.email",
    "merge.message_template",
    "execution.working_directory",
    "execution.keep_working_directory",
    "execution.fetch_full_history",
    "execution.resync_reset_commit_count",
    "execution.empty_sync_is_success",
    "conflict_handling.strategy",
    "conflict_handling.restore_source_on_failure",
    "conflict_handling.allow_automatic_resolution",
    "logging.file",
    "synchronization.commit_marker",
    "synchronization.prevent_sync_loops",
)


def validate_reverse_config(config: dict[str, Any]) -> None:
    validate_common_config(config)
    validate_required(config, REQUIRED_SECTIONS, REQUIRED_KEYS)
    if config["conflict_handling"]["strategy"] != "abort":
        raise ConfigurationError("Only conflict_handling.strategy='abort' is currently supported.")
    if config["conflict_handling"].get("allow_automatic_resolution"):
        raise ConfigurationError("Automatic conflict resolution is not supported in this phase.")


def run_reverse_sync(
    config: dict[str, Any],
    config_path: Path,
    dry_run: bool,
    token: str,
    sanitizer: TokenSanitizer,
    destination_token: str | None = None,
) -> int:
    execution = config["execution"]
    source = resolve_repository(config, "source")
    destination = resolve_repository(config, "destination")
    working_directory = resolve_working_directory(config_path, execution, SCRIPT_NAME)
    source_dir = working_directory / ensure_relative_path(source["clone_directory"], "repositories.source.clone_directory")
    timeout = int(execution["operation_timeout_seconds"])

    def runner() -> GitRunner:
        return GitRunner(working_directory, token, timeout, sanitizer)

    with prepared_working_directory(working_directory, bool(execution["keep_working_directory"])):
        try:
            with runner() as git:
                logging.info("Preparing source repository at %s.", source_dir)
                clone_or_resync_repository(
                    git,
                    source,
                    source_dir,
                    bool(execution["fetch_full_history"]),
                    int(execution["resync_reset_commit_count"]),
                )
                source_commit = resolve_commit_sha(git, source_dir)
                logging.info("Source %s@%s -> %s", source["url"], source["branch"], source_commit)

                # Fetch destination into the source clone; this preserves its commit objects without cloning twice.
                destination_commit = fetch_ref(
                    git, source_dir, destination["url"], destination["branch"], auth_token=destination_token or token
                )
                logging.info("Destination %s@%s -> %s", destination["url"], destination["branch"], destination_commit)

                apply_sync(
                    git,
                    source_dir,
                    source_commit,
                    destination_commit,
                    dry_run=dry_run,
                    identity=config["git_identity"],
                    merge_message_template=str(config["merge"]["message_template"]),
                    empty_sync_is_success=bool(execution["empty_sync_is_success"]),
                    labels=("source", "destination"),
                    push=lambda: push_with_retries(
                        git,
                        source_dir,
                        "origin",
                        source["branch"],
                        int(execution["push_retry_count"]),
                        float(execution["push_retry_delay_seconds"]),
                    ),
                )
                return 0
        except Exception:
            if config["conflict_handling"].get("restore_source_on_failure") and source_dir.exists():
                with runner() as git:
                    restore_repository(git, source_dir)
            raise


def main() -> int:
    args = build_parser(__doc__, DEFAULT_CONFIG).parse_args()
    sanitizer = TokenSanitizer()

    def run() -> int:
        config_path = Path(args.config).expanduser().resolve()
        config = load_config(config_path, validate_reverse_config)
        host = repository_host(resolve_repository(config, "source")["url"])
        token = resolve_token(config, config_path, "source", host)
        destination_token = resolve_token(config, config_path, "destination", host)
        sanitizer.add(token)
        sanitizer.add(destination_token)
        setup_logging(config["logging"], config_path, sanitizer)
        logging.info("Reverse-sync started (config=%s).", config_path)
        dry_run = resolve_dry_run(args, config)
        logging.info("Execution mode: %s.", "dry-run" if dry_run else "live (push enabled)")
        return run_reverse_sync(config, config_path, dry_run, token, sanitizer, destination_token)

    return run_main(run, sanitizer)


if __name__ == "__main__":
    sys.exit(main())
