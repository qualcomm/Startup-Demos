#===--log.py---------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Sanitized console/file logging shared by all automation scripts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config import resolve_config_path
from .sanitizer import TokenSanitizer

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


class SanitizingFormatter(logging.Formatter):
    def __init__(self, sanitizer: TokenSanitizer, fmt: str = LOG_FORMAT) -> None:
        super().__init__(fmt)
        self._sanitizer = sanitizer

    def format(self, record: logging.LogRecord) -> str:
        return self._sanitizer.clean(super().format(record))


def _configure_root(level: int, handlers: list[logging.Handler], sanitizer: TokenSanitizer) -> None:
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.close()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    formatter = SanitizingFormatter(sanitizer)
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)


def setup_console_logging(sanitizer: TokenSanitizer, level: int = logging.INFO) -> None:
    """Used before config is loaded so early failures are still logged and redacted."""
    _configure_root(level, [logging.StreamHandler()], sanitizer)


def setup_logging(log_config: dict[str, Any], config_path: Path, sanitizer: TokenSanitizer) -> Path | None:
    """Configure console logging plus an optional file; returns the log file path if one is configured."""
    level = getattr(logging, str(log_config.get("level", "INFO")).upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    log_file: Path | None = None
    if log_config.get("file"):
        log_file = resolve_config_path(config_path, str(log_config["file"]))
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    _configure_root(level, handlers, sanitizer)
    return log_file
