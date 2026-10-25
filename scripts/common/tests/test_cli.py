#===--test_cli.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

import logging
import subprocess
from pathlib import Path

from common.cli import build_parser, resolve_dry_run, run_main
from common.errors import ConfigurationError
from common.log import setup_logging
from common.sanitizer import TokenSanitizer


def test_dry_run_flags_override_config_default():
    parser = build_parser("test", Path("config.yaml"))
    config = {"execution": {"dry_run_default": True}}

    assert resolve_dry_run(parser.parse_args([]), config) is True
    assert resolve_dry_run(parser.parse_args(["--no-dry-run"]), config) is False
    assert resolve_dry_run(parser.parse_args(["--dry-run"]), {"execution": {"dry_run_default": False}}) is True
    assert parser.parse_args([]).config == "config.yaml"


def test_run_main_maps_expected_failures_to_exit_code_and_redacts(capsys):
    sanitizer = TokenSanitizer("secret-token")

    def failing() -> int:
        raise ConfigurationError("bad secret-token")

    def timing_out() -> int:
        raise subprocess.TimeoutExpired(["git", "fetch"], 5)

    assert run_main(failing, sanitizer) == 1
    assert run_main(timing_out, sanitizer) == 1
    assert run_main(lambda: 0, sanitizer) == 0
    err = capsys.readouterr().err
    assert "bad [REDACTED_TOKEN]" in err
    assert "timed out after 5 seconds: git fetch" in err
    assert "secret-token" not in err


def test_setup_logging_writes_sanitized_file(tmp_path):
    sanitizer = TokenSanitizer("secret-token")

    log_file = setup_logging({"level": "INFO", "file": "logs/run.log"}, tmp_path / "config.yaml", sanitizer)
    logging.info("value=secret-token")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_file == tmp_path / "logs" / "run.log"
    assert "value=[REDACTED_TOKEN]" in log_file.read_text(encoding="utf-8")


def test_setup_logging_without_file_is_console_only(tmp_path):
    assert setup_logging({"level": "DEBUG", "file": None}, tmp_path / "config.yaml", TokenSanitizer()) is None
    assert logging.getLogger().level == logging.DEBUG
