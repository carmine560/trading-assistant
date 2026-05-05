"""Tests for extracted market data helpers."""

from pathlib import Path

from app import market_data


def test_split_rankings_by_digit_saves_valid_symbols(rankings_csv, tmp_path):
    closing_prices_prefix = str(tmp_path / "closing_prices_")

    assert market_data.split_rankings_by_digit(
        rankings=str(rankings_csv),
        closing_prices_prefix=closing_prices_prefix,
        code_regex=r"[1-9][\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?",
    )
    assert not rankings_csv.exists()

    closing_prices_1 = Path(f"{closing_prices_prefix}1.csv")
    closing_prices_9 = Path(f"{closing_prices_prefix}9.csv")

    assert closing_prices_1.read_text(encoding="utf-8").strip() == "1234,1500"
    assert closing_prices_9.read_text(encoding="utf-8").strip() == "9876,2500"


def test_split_rankings_by_digit_returns_false_for_missing_file(tmp_path):
    assert not market_data.split_rankings_by_digit(
        rankings=str(tmp_path / "missing.csv"),
        closing_prices_prefix=str(tmp_path / "closing_prices_"),
        code_regex=r"[1-9][\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?",
    )
