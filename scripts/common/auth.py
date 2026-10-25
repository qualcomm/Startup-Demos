#===--auth.py--------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""GitHub token resolution: environment variable -> credentials file -> fallback token -> gh CLI."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from .config import require_mapping, resolve_config_path
from .errors import AuthenticationError, ConfigurationError

EXAMPLE_TOKEN_PLACEHOLDER = "REPLACE_WITH_LOCAL_TEST_PAT"


def reject_placeholder_token(token: str, source: str) -> None:
    if token == EXAMPLE_TOKEN_PLACEHOLDER:
        raise AuthenticationError(f"Refusing to use placeholder token value from {source}.")


def validate_credentials_file_permissions(path: Path, strict: bool) -> None:
    if platform.system().lower() != "linux" or not path.exists():
        return

    mode = stat.S_IMODE(path.stat().st_mode)
    if not mode & (stat.S_IRWXG | stat.S_IRWXO):
        return

    message = (
        f"Credentials file {path} is accessible by group or others. "
        "Use chmod 600 for controlled local testing."
    )
    if strict:
        raise AuthenticationError(message)
    logging.warning(message)


def resolve_token_from_gh_cli() -> str | None:
    """Fall back to the token of an already-authenticated gh CLI session."""
    gh_path = shutil.which("gh")
    if not gh_path:
        return None
    try:
        completed = subprocess.run(
            [gh_path, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logging.warning("Failed to invoke gh CLI for authentication: %s", error)
        return None
    if completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip()
    logging.debug(
        "`gh auth token` unavailable or unauthenticated (rc=%s); falling back to gh config file.",
        completed.returncode,
    )
    return None


def gh_config_directory() -> Path:
    """Reproduce gh CLI's own config directory resolution order."""
    gh_config_dir = os.environ.get("GH_CONFIG_DIR")
    if gh_config_dir:
        return Path(gh_config_dir).expanduser()
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "gh"
    return Path.home() / ".config" / "gh"


def resolve_token_from_gh_config_file(host: str) -> str | None:
    """Read the OAuth token gh CLI stores locally, for gh versions without `gh auth token`."""
    hosts_path = gh_config_directory() / "hosts.yml"
    if not hosts_path.exists():
        return None
    try:
        with hosts_path.open("r", encoding="utf-8") as hosts_file:
            hosts = yaml.safe_load(hosts_file) or {}
    except (OSError, yaml.YAMLError) as error:
        logging.warning("Failed to read gh CLI hosts file: %s", error)
        return None
    if not isinstance(hosts, dict):
        return None
    host_entry = hosts.get(host)
    if not isinstance(host_entry, dict):
        return None
    token = host_entry.get("oauth_token")
    return str(token) if token else None


def resolve_gh_cli_token(host: str) -> str | None:
    return resolve_token_from_gh_cli() or resolve_token_from_gh_config_file(host)


def repository_host(url: str) -> str:
    return urlsplit(url).netloc or "github.com"


def _token_spec(auth_config: dict[str, Any], name: str) -> dict[str, Any]:
    spec = (auth_config.get("tokens") or {}).get(name)
    if not isinstance(spec, dict) or not spec.get("env_var"):
        raise ConfigurationError(f"Missing configuration value: authentication.tokens.{name}.env_var")
    return spec


def _token_from_environment(spec: dict[str, Any]) -> str | None:
    env_var = str(spec["env_var"])
    token = os.environ.get(env_var)
    if token:
        reject_placeholder_token(token, f"environment variable {env_var}")
    return token or None


def _token_from_credentials_file(
    auth_config: dict[str, Any], spec: dict[str, Any], config_path: Path, name: str
) -> str | None:
    if not auth_config.get("allow_credentials_file", False) or not auth_config.get("credentials_file"):
        return None
    credentials_path = resolve_config_path(config_path, str(auth_config["credentials_file"]))
    if not credentials_path.exists():
        return None
    validate_credentials_file_permissions(
        credentials_path, bool(auth_config.get("strict_credentials_file_permissions", False))
    )
    with credentials_path.open("r", encoding="utf-8") as credentials_file:
        credentials = yaml.safe_load(credentials_file) or {}
    if not isinstance(credentials, dict):
        raise AuthenticationError("Credentials file must contain a YAML mapping.")
    token = credentials.get(str(spec.get("credentials_key", name)))
    if not token:
        return None
    token = str(token)
    reject_placeholder_token(token, str(credentials_path))
    return token


def resolve_token(config: dict[str, Any], config_path: Path, name: str, host: str = "github.com") -> str:
    """Resolve the token named `name` under `authentication.tokens`, following its `fallback` chain."""
    auth_config = require_mapping(config, "authentication")
    visited: list[str] = []
    current: str | None = name
    while current:
        if current in visited:
            raise ConfigurationError(f"Token fallback cycle detected: {' -> '.join([*visited, current])}")
        visited.append(current)
        spec = _token_spec(auth_config, current)
        token = _token_from_environment(spec) or _token_from_credentials_file(auth_config, spec, config_path, current)
        if token:
            return token
        current = spec.get("fallback")

    if auth_config.get("allow_gh_cli_fallback", False):
        gh_token = resolve_gh_cli_token(host)
        if gh_token:
            reject_placeholder_token(gh_token, "gh CLI authentication")
            logging.info("Using GitHub token from authenticated gh CLI session for '%s'.", name)
            return gh_token

    env_vars = ", ".join(str(_token_spec(auth_config, item)["env_var"]) for item in visited)
    raise AuthenticationError(
        f"No GitHub token found for '{name}'. Set {env_vars}, configure a controlled local credentials file, "
        "or authenticate with `gh auth login`."
    )
