#===--test_config.py-------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

from pathlib import Path

import pytest
import yaml

from common.config import deep_merge, ensure_relative_path, load_config, load_layered_config, require_value
from common.config import validate_common_config
from common.errors import ConfigurationError

COMMON_CONFIG = Path(__file__).resolve().parents[1] / "common_config.yaml"


def write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_deep_merge_overrides_scalars_and_merges_mappings():
    merged = deep_merge({"a": {"x": 1, "y": 2}, "b": [1]}, {"a": {"y": 3}, "b": [2]})

    assert merged == {"a": {"x": 1, "y": 3}, "b": [2]}


def test_extends_is_resolved_relative_to_the_child(tmp_path):
    (tmp_path / "common").mkdir()
    write(tmp_path / "common" / "base.yaml", {"execution": {"timeout": 10, "retries": 2}})
    child = write(tmp_path / "child.yaml", {"extends": "common/base.yaml", "execution": {"timeout": 99}})

    assert load_layered_config(child) == {"execution": {"timeout": 99, "retries": 2}}


def test_extends_chains_multiple_levels(tmp_path):
    write(tmp_path / "a.yaml", {"value": "a", "only_a": True})
    write(tmp_path / "b.yaml", {"extends": "a.yaml", "value": "b"})
    child = write(tmp_path / "c.yaml", {"extends": "b.yaml", "value": "c"})

    assert load_layered_config(child) == {"value": "c", "only_a": True}


def test_extends_cycle_is_rejected(tmp_path):
    write(tmp_path / "a.yaml", {"extends": "b.yaml"})
    child = write(tmp_path / "b.yaml", {"extends": "a.yaml"})

    with pytest.raises(ConfigurationError, match="cycle"):
        load_layered_config(child)


def test_missing_config_file_is_a_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError, match="not found"):
        load_config(tmp_path / "missing.yaml")


def test_require_value_rejects_missing_and_empty_values():
    with pytest.raises(ConfigurationError, match="Missing"):
        require_value({"a": {}}, "a.b")
    with pytest.raises(ConfigurationError, match="empty"):
        require_value({"a": {"b": ""}}, "a.b")
    assert require_value({"a": {"b": 0}}, "a.b") == 0


def test_common_config_is_valid_on_its_own():
    validate_common_config(load_config(COMMON_CONFIG))


def test_force_push_is_rejected(tmp_path):
    child = write(tmp_path / "child.yaml", {"extends": str(COMMON_CONFIG), "execution": {"allow_force_push": True}})

    with pytest.raises(ConfigurationError, match="Force push"):
        load_config(child, validate_common_config)


@pytest.mark.parametrize("value", ["/tmp/source", "../source", "a/../../b"])
def test_ensure_relative_path_rejects_escape(value):
    with pytest.raises(ConfigurationError):
        ensure_relative_path(value)
