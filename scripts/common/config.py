#===--config.py------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Layered YAML configuration: per-script files `extends:` a shared common config."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigurationError

EXTENDS_KEY = "extends"
COMMON_SECTIONS = ("authentication", "execution", "logging")
COMMON_REQUIRED_KEYS = (
    "execution.operation_timeout_seconds",
    "execution.dry_run_default",
    "execution.push_retry_count",
    "execution.push_retry_delay_seconds",
    "logging.level",
)


def resolve_config_path(config_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid YAML in {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise ConfigurationError(f"Configuration file must contain a YAML mapping: {path}")
    return loaded


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new mapping where `override` wins; nested mappings merge, everything else is replaced."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_layered_config(config_path: Path, _chain: tuple[Path, ...] = ()) -> dict[str, Any]:
    config_path = config_path.expanduser().resolve()
    if config_path in _chain:
        cycle = " -> ".join(str(path) for path in (*_chain, config_path))
        raise ConfigurationError(f"Configuration `extends` cycle detected: {cycle}")
    data = load_yaml_mapping(config_path)
    parent = data.pop(EXTENDS_KEY, None)
    if not parent:
        return data
    parent_config = load_layered_config(resolve_config_path(config_path, str(parent)), (*_chain, config_path))
    return deep_merge(parent_config, data)


def load_config(
    config_path: Path,
    validator: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    config = load_layered_config(config_path)
    if validator:
        validator(config)
    return config


def require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"Missing or invalid configuration section: {key}")
    return value


def require_value(config: dict[str, Any], dotted_key: str) -> Any:
    current: Any = config
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConfigurationError(f"Missing required configuration value: {dotted_key}")
        current = current[part]
    if current in (None, ""):
        raise ConfigurationError(f"Configuration value cannot be empty: {dotted_key}")
    return current


def validate_required(config: dict[str, Any], sections: Iterable[str] = (), keys: Iterable[str] = ()) -> None:
    for section in sections:
        require_mapping(config, section)
    for dotted_key in keys:
        require_value(config, dotted_key)


def validate_common_config(config: dict[str, Any]) -> None:
    validate_required(config, COMMON_SECTIONS, COMMON_REQUIRED_KEYS)
    if config["execution"].get("allow_force_push"):
        raise ConfigurationError("Force push is intentionally not supported by these automation scripts.")


def ensure_relative_path(value: str, label: str = "path") -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{label} must be a relative path inside the working directory: {value}")
    return path
