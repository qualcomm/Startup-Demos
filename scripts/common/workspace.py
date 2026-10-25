#===--workspace.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Per-script working directory handling."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import resolve_config_path


def resolve_working_directory(config_path: Path, execution_config: dict[str, Any], script_name: str) -> Path:
    base_directory = resolve_config_path(config_path, str(execution_config["working_directory"]))
    return base_directory / script_name


@contextmanager
def prepared_working_directory(path: Path, keep: bool) -> Iterator[Path]:
    """Create `path`, wiping it before and after use unless `keep` is set."""
    if path.exists() and not keep:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        if path.exists() and not keep:
            shutil.rmtree(path, ignore_errors=True)
