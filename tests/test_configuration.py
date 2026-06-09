"""Tests for configuration helper error boundaries."""

from configparser import ConfigParser
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import config_builder
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


def test_configure_resets_daily_state_after_closing_time_using_market_timezone(
    monkeypatch,
):
    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            frozen_utc = datetime(
                2026,
                1,
                2,
                6,
                30,
                tzinfo=timezone.utc,
            )
            return frozen_utc.astimezone(tz)

    def read_config_fn(config, *_args, **_kwargs):
        config["Market Data"]["timezone"] = "Asia/Tokyo"
        config["Variables"]["current_date"] = "2026-01-01"
        config["Variables"]["initial_cash_balance"] = "100000"
        config["Variables"]["current_number_of_trades"] = "3"

    trade = SimpleNamespace(
        vendor="Other",
        process="OTHER",
        geometries_section="OTHER Geometries",
        actions_section="OTHER Actions",
        schedules_section="OTHER Schedules",
        variables_section="Variables",
        config_path="config.ini",
    )

    monkeypatch.setattr(config_builder, "datetime", FrozenDateTime)

    config = config_builder.configure(
        trade,
        SimpleNamespace(),
        SimpleNamespace(),
        r"\d{4}",
        read_config_fn=read_config_fn,
    )

    assert config["Variables"]["current_date"] == "2026-01-02"
    assert config["Variables"]["initial_cash_balance"] == "0"
    assert config["Variables"]["current_number_of_trades"] == "0"
