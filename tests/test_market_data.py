"""Tests for extracted market data helpers."""

from pathlib import Path

from app import market_data
from core_utilities.errors import MarketDataError

CODE_REGEX = r"[1-9][\dACDFGHJKLMNPRSTUWXY]\d" r"[\dACDFGHJKLMNPRSTUWXY]5?"


def test_split_rankings_by_digit_saves_valid_symbols(rankings_csv, tmp_path):
    closing_prices_prefix = str(tmp_path / "closing_prices_")

    assert market_data.split_rankings_by_digit(
        rankings=str(rankings_csv),
        closing_prices_prefix=closing_prices_prefix,
        code_regex=CODE_REGEX,
    )
    assert not rankings_csv.exists()

    closing_prices_1 = Path(f"{closing_prices_prefix}1.csv")
    closing_prices_9 = Path(f"{closing_prices_prefix}9.csv")

    assert closing_prices_1.read_text(encoding="utf-8").strip() == "1234,1500"
    assert closing_prices_9.read_text(encoding="utf-8").strip() == "9876,2500"


def test_split_rankings_by_digit_returns_false_for_missing_file(tmp_path):
    try:
        market_data.split_rankings_by_digit(
            rankings=str(tmp_path / "missing.csv"),
            closing_prices_prefix=str(tmp_path / "closing_prices_"),
            code_regex=CODE_REGEX,
        )
    except MarketDataError:
        pass
    else:
        raise AssertionError("Expected MarketDataError for missing file.")


def test_split_rankings_by_digit_raises_for_malformed_row(tmp_path):
    rankings = tmp_path / "rankings.csv"
    rankings.write_text(
        "\n".join(
            (
                'a,b,c,d,e,f,1234,h,i,"1,500"',
                "too,short,row",
            )
        ),
        encoding="utf-8",
    )

    try:
        market_data.split_rankings_by_digit(
            rankings=str(rankings),
            closing_prices_prefix=str(tmp_path / "closing_prices_"),
            code_regex=CODE_REGEX,
        )
    except MarketDataError as e:
        assert "malformed row 2 has 3 columns" in str(e)
    else:
        raise AssertionError("Expected MarketDataError for malformed row.")
