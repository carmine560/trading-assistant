"""Tests for configuration helper error boundaries."""

from configparser import ConfigParser

import pytest

from core_utilities import configuration


def test_list_section_raises_for_missing_section():
    config = ConfigParser(interpolation=None)

    with pytest.raises(configuration.ConfigError, match="does not exist"):
        configuration.list_section(config, "Missing")


def test_modify_section_raises_for_missing_section(tmp_path):
    config = ConfigParser(interpolation=None)
    config_path = tmp_path / "config.ini"

    with pytest.raises(configuration.ConfigError, match="does not exist"):
        configuration.modify_section(config, "Missing", str(config_path))


def test_modify_option_raises_for_missing_option(tmp_path):
    config = ConfigParser(interpolation=None)
    config["General"] = {}
    config_path = tmp_path / "config.ini"

    with pytest.raises(configuration.ConfigError, match="does not exist"):
        configuration.modify_option(
            config,
            "General",
            "missing",
            str(config_path),
        )


def test_delete_option_raises_for_missing_option(tmp_path):
    config = ConfigParser(interpolation=None)
    config["General"] = {}
    config_path = tmp_path / "config.ini"

    with pytest.raises(configuration.ConfigError, match="does not exist"):
        configuration.delete_option(
            config,
            "General",
            "missing",
            str(config_path),
        )
