"""Tests for trading assistant state models."""

from app import models


def test_trade_exposes_wait_commands_with_optional_cleanup(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    trade = models.Trade(
        "SBI",
        "HYPERSBI2",
        str(tmp_path / "trading_assistant.py"),
        lambda *_args, **_kwargs: None,
    )

    assert trade.instruction_items["optional_additional_nested_keys"] == {
        "wait_for_key",
        "wait_for_key_count_down",
        "wait_for_price",
        "wait_for_window",
    }
