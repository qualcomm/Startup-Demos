#===--repositories.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Repository URL/branch resolution from configurable environment variables."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from .errors import ConfigurationError

DEFAULT_ALLOWED_SCHEMES = ("https",)


def validate_remote_url(url: str, allowed_schemes: tuple[str, ...] | list[str] = DEFAULT_ALLOWED_SCHEMES) -> None:
    parsed = urlsplit(url)
    # Plain filesystem paths have no scheme; treat them as `file` so tests can opt in explicitly.
    scheme = parsed.scheme or "file"
    if scheme not in allowed_schemes:
        raise ConfigurationError(
            f"Repository URL scheme '{scheme}' is not allowed (allowed: {', '.join(allowed_schemes)})."
        )
    if parsed.username or parsed.password:
        raise ConfigurationError("Repository URLs must not embed credentials.")
    if scheme != "file" and not parsed.netloc:
        raise ConfigurationError("Repository URL must include a host.")


def resolve_repository(config: dict[str, Any], name: str) -> dict[str, str]:
    """Resolve `repositories.<name>`; env vars named by `url_env`/`branch_env` win over literal values."""
    section = (config.get("repositories") or {}).get(name) or {}
    url_env = section.get("url_env")
    branch_env = section.get("branch_env")
    url = (os.environ.get(url_env) if url_env else None) or section.get("url")
    branch = (os.environ.get(branch_env) if branch_env else None) or section.get("branch")
    if not url or not branch:
        hint = f"Set {url_env} and {branch_env}" if url_env and branch_env else "Set url and branch"
        raise ConfigurationError(
            f"Missing repository configuration for '{name}'. {hint}, or repositories.{name}.url/branch in the config file."
        )
    allowed_schemes = (config.get("security") or {}).get("allowed_url_schemes") or DEFAULT_ALLOWED_SCHEMES
    validate_remote_url(str(url), list(allowed_schemes))
    return {
        "url": str(url),
        "branch": str(branch),
        "clone_directory": str(section.get("clone_directory") or name),
    }
