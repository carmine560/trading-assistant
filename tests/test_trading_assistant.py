"""Tests for deterministic parsing and calculation helpers."""

from pathlib import Path

import trading_assistant


def test_is_xy_accepts_two_integers_with_whitespace():
    assert trading_assistant._is_xy(" 10,  25 ")
    assert not trading_assistant._is_xy("10,25,30")
    assert not trading_assistant._is_xy("10.5,25")


def test_save_market_data_splits_valid_symbols_and_strips_commas(
    sample_trade, sample_config, rankings_csv
):
    sample_config["Market Data"]["rankings"] = str(rankings_csv)

    assert trading_assistant.save_market_data(sample_trade, sample_config)
    assert not rankings_csv.exists()

    closing_prices_1 = Path(f"{sample_trade.closing_prices}1.csv")
    closing_prices_9 = Path(f"{sample_trade.closing_prices}9.csv")

    assert closing_prices_1.read_text(encoding="utf-8").strip() == "1234,1500"
    assert closing_prices_9.read_text(encoding="utf-8").strip() == "9876,2500"


def test_save_market_data_returns_false_for_missing_rankings_file(
    sample_trade, sample_config, tmp_path
):
    sample_config["Market Data"]["rankings"] = str(tmp_path / "missing.csv")

    assert not trading_assistant.save_market_data(sample_trade, sample_config)


def test_get_price_limit_uses_saved_closing_price(sample_trade, sample_config):
    Path(f"{sample_trade.closing_prices}1.csv").write_text(
        "1234,980\n", encoding="utf-8"
    )

    assert (
        trading_assistant.get_price_limit(sample_trade, sample_config)
        == 1130.0
    )


def test_get_price_limit_falls_back_to_recognized_value(
    monkeypatch, sample_trade, sample_config
):
    def fake_recognize_text(*args, **kwargs):
        assert args[:4] == (0, 0, 10, 10)
        assert args[4:] == (1, 128, False)
        assert kwargs == {"text_type": "decimal_numbers"}
        return 4321

    monkeypatch.setattr(
        trading_assistant.text_recognition,
        "recognize_text",
        fake_recognize_text,
    )

    assert (
        trading_assistant.get_price_limit(sample_trade, sample_config) == 4321
    )


def test_calculate_share_size_uses_margin_ratio_file(
    sample_trade, sample_config
):
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    Path(f"{sample_trade.closing_prices}1.csv").write_text(
        "1234,980\n", encoding="utf-8"
    )

    success, message = trading_assistant.calculate_share_size(
        sample_trade, sample_config, "long"
    )

    assert (success, message) == (True, None)
    assert sample_trade.share_size == 200


def test_calculate_share_size_rejects_suspended_symbol(
    sample_trade, sample_config
):
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,suspended\n", encoding="utf-8"
    )

    assert trading_assistant.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, "Margin trading suspended.")


def test_calculate_share_size_caps_short_positions_at_fifty_units(
    sample_trade, sample_config
):
    sample_trade.cash_balance = 10_000_000
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    Path(f"{sample_trade.closing_prices}1.csv").write_text(
        "1234,980\n", encoding="utf-8"
    )

    success, message = trading_assistant.calculate_share_size(
        sample_trade, sample_config, "short"
    )

    assert (success, message) == (True, None)
    assert sample_trade.share_size == 5000


def test_calculate_share_size_requires_symbol_and_cash_balance(
    sample_trade, sample_config
):
    sample_trade.symbol = ""

    assert trading_assistant.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, "Symbol or cash balance not provided.")
