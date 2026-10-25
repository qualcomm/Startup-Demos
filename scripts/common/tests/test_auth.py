#===--test_auth.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

import logging
from pathlib import Path

import pytest
import yaml

from common import auth
from common.auth import EXAMPLE_TOKEN_PLACEHOLDER, resolve_token
from common.errors import AuthenticationError, ConfigurationError
from common.repositories import resolve_repository, validate_remote_url

TOKEN_ENV_VARS = ("TEST_SOURCE_TOKEN", "TEST_DEST_TOKEN")


@pytest.fixture(autouse=True)
def clear_tokens(monkeypatch):
    for name in TOKEN_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def auth_config(**overrides) -> dict:
    authentication = {
        "credentials_file": "credentials.yaml",
        "allow_credentials_file": True,
        "strict_credentials_file_permissions": False,
        "allow_gh_cli_fallback": False,
        "tokens": {
            "source": {"env_var": "TEST_SOURCE_TOKEN", "credentials_key": "source_token"},
            "destination": {"env_var": "TEST_DEST_TOKEN", "credentials_key": "destination_token", "fallback": "source"},
        },
    }
    authentication.update(overrides)
    return {"authentication": authentication}


def write_credentials(path: Path, mode: int = 0o600, **tokens: str) -> None:
    path.write_text(yaml.safe_dump(tokens), encoding="utf-8")
    path.chmod(mode)


def test_environment_token_takes_precedence_over_credentials_file(monkeypatch, tmp_path):
    write_credentials(tmp_path / "credentials.yaml", source_token="file-token")
    monkeypatch.setenv("TEST_SOURCE_TOKEN", "env-token")

    assert resolve_token(auth_config(), tmp_path / "config.yaml", "source") == "env-token"


def test_credentials_file_used_when_environment_token_is_missing(tmp_path):
    write_credentials(tmp_path / "credentials.yaml", source_token="file-token")

    assert resolve_token(auth_config(), tmp_path / "config.yaml", "source") == "file-token"


def test_credentials_file_ignored_when_not_allowed(tmp_path):
    write_credentials(tmp_path / "credentials.yaml", source_token="file-token")

    with pytest.raises(AuthenticationError, match="TEST_SOURCE_TOKEN"):
        resolve_token(auth_config(allow_credentials_file=False), tmp_path / "config.yaml", "source")


def test_placeholder_token_is_rejected_from_credentials_file(tmp_path):
    write_credentials(tmp_path / "credentials.yaml", source_token=EXAMPLE_TOKEN_PLACEHOLDER)

    with pytest.raises(AuthenticationError, match="placeholder token"):
        resolve_token(auth_config(), tmp_path / "config.yaml", "source")


def test_placeholder_token_is_rejected_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_SOURCE_TOKEN", EXAMPLE_TOKEN_PLACEHOLDER)

    with pytest.raises(AuthenticationError, match="placeholder token"):
        resolve_token(auth_config(), tmp_path / "config.yaml", "source")


def test_strict_credentials_permissions_reject_group_or_other_access(tmp_path):
    write_credentials(tmp_path / "credentials.yaml", mode=0o644, source_token="file-token")

    with pytest.raises(AuthenticationError, match="accessible by group or others"):
        resolve_token(auth_config(strict_credentials_file_permissions=True), tmp_path / "config.yaml", "source")


def test_non_strict_credentials_permissions_warn(tmp_path, caplog):
    write_credentials(tmp_path / "credentials.yaml", mode=0o644, source_token="file-token")

    with caplog.at_level(logging.WARNING):
        token = resolve_token(auth_config(), tmp_path / "config.yaml", "source")

    assert token == "file-token"
    assert "accessible by group or others" in caplog.text


def test_destination_token_preferred_over_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_SOURCE_TOKEN", "source-token")
    monkeypatch.setenv("TEST_DEST_TOKEN", "destination-token")

    assert resolve_token(auth_config(), tmp_path / "config.yaml", "destination") == "destination-token"


def test_destination_token_falls_back_to_source(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_SOURCE_TOKEN", "source-token")

    assert resolve_token(auth_config(), tmp_path / "config.yaml", "destination") == "source-token"


def test_missing_token_lists_every_environment_variable_tried(tmp_path):
    with pytest.raises(AuthenticationError, match="TEST_DEST_TOKEN, TEST_SOURCE_TOKEN"):
        resolve_token(auth_config(), tmp_path / "config.yaml", "destination")


def test_fallback_cycle_is_rejected(tmp_path):
    config = auth_config()
    config["authentication"]["tokens"]["source"]["fallback"] = "destination"

    with pytest.raises(ConfigurationError, match="cycle"):
        resolve_token(config, tmp_path / "config.yaml", "destination")


def test_gh_cli_fallback_used_only_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "resolve_gh_cli_token", lambda host: f"gh-token-for-{host}")

    with pytest.raises(AuthenticationError):
        resolve_token(auth_config(), tmp_path / "config.yaml", "source", "github.example")
    token = resolve_token(auth_config(allow_gh_cli_fallback=True), tmp_path / "config.yaml", "source", "github.example")
    assert token == "gh-token-for-github.example"


def test_repository_env_vars_override_config(monkeypatch):
    config = {"repositories": {"source": {"url_env": "TEST_URL", "branch_env": "TEST_BRANCH", "url": "https://a/b"}}}
    monkeypatch.setenv("TEST_URL", "https://github.com/org/repo")
    monkeypatch.setenv("TEST_BRANCH", "main")

    assert resolve_repository(config, "source") == {
        "url": "https://github.com/org/repo",
        "branch": "main",
        "clone_directory": "source",
    }


def test_repository_missing_values_name_the_environment_variables(monkeypatch):
    monkeypatch.delenv("TEST_URL", raising=False)
    monkeypatch.delenv("TEST_BRANCH", raising=False)
    config = {"repositories": {"source": {"url_env": "TEST_URL", "branch_env": "TEST_BRANCH"}}}

    with pytest.raises(ConfigurationError, match="TEST_URL and TEST_BRANCH"):
        resolve_repository(config, "source")


@pytest.mark.parametrize(
    "url",
    ["http://github.com/org/repo", "https://user:pass@github.com/org/repo", "/local/path", "https:///no-host"],
)
def test_remote_url_validation_rejects_unsafe_urls(url):
    with pytest.raises(ConfigurationError):
        validate_remote_url(url)


def test_local_paths_allowed_when_file_scheme_enabled():
    validate_remote_url("/local/path", ["https", "file"])
