#===--cli.py---------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Command-line conventions shared by all automation scripts."""

from __future__ import annotations

import argparse
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import AutomationError
from .log import setup_console_logging
from .sanitizer import TokenSanitizer


def build_parser(description: str, default_config: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        default=str(default_config),
        help=f"Path to the script configuration file (default: {default_config.name}).",
    )
    dry_run_group = parser.add_mutually_exclusive_group()
    dry_run_group.add_argument("--dry-run", action="store_true", help="Detect changes without committing or pushing.")
    dry_run_group.add_argument("--no-dry-run", action="store_true", help="Commit and push detected changes.")
    return parser


def resolve_dry_run(args: argparse.Namespace, config: dict[str, Any]) -> bool:
    if args.no_dry_run:
        return False
    if args.dry_run:
        return True
    return bool(config["execution"]["dry_run_default"])


def run_main(entrypoint: Callable[[], int], sanitizer: TokenSanitizer) -> int:
    """Run a script body, turning expected failures into a redacted log line and exit code 1."""
    setup_console_logging(sanitizer)
    try:
        return entrypoint()
    except AutomationError as error:
        logging.error(sanitizer.clean(str(error)))
        return 1
    except subprocess.TimeoutExpired as error:
        command = " ".join(error.cmd) if isinstance(error.cmd, (list, tuple)) else str(error.cmd)
        logging.error(sanitizer.clean(f"Operation timed out after {error.timeout} seconds: {command}"))
        return 1
