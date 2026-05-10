"""Tests for configuration helper error boundaries."""

from configparser import ConfigParser

import pytest

from core_utilities.config_common import ConfigError
from core_utilities.config_prompt import (
    delete_option,
    modify_option,
    modify_section,
)
from core_utilities.config_validation import list_section


def test_list_section_raises_for_missing_section():
    config = ConfigParser(interpolation=None)

    with pytest.raises(ConfigError, match="does not exist"):
        list_section(config, "Missing")


def test_modify_section_raises_for_missing_section(tmp_path):
    config = ConfigParser(interpolation=None)
    config_path = tmp_path / "config.ini"

    with pytest.raises(ConfigError, match="does not exist"):
        modify_section(config, "Missing", str(config_path))


def test_modify_option_raises_for_missing_option(tmp_path):
    config = ConfigParser(interpolation=None)
    config["General"] = {}
    config_path = tmp_path / "config.ini"

    with pytest.raises(ConfigError, match="does not exist"):
        modify_option(config, "General", "missing", str(config_path))


def test_delete_option_raises_for_missing_option(tmp_path):
    config = ConfigParser(interpolation=None)
    config["General"] = {}
    config_path = tmp_path / "config.ini"

    with pytest.raises(ConfigError, match="does not exist"):
        delete_option(config, "General", "missing", str(config_path))
