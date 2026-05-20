"""Tests for customer margin ratio refresh behavior."""

import sys

from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from core_utilities import config_io
from core_utilities.errors import ExternalServiceError, MarketDataError
from app import customer_margin_ratios


def _build_market_holidays_config():
    config = ConfigParser(interpolation=None)
    config["Market Holidays"] = {
        "url": "https://example.invalid/holidays",
        "date_header": "Date",
        "date_format": "%Y/%m/%d",
    }
    return config


def test_save_customer_margin_ratios_requires_matching_headers(
    monkeypatch, tmp_path
):
    trade = SimpleNamespace(
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        market_holidays=str(tmp_path / "market_holidays.csv"),
    )
    config = ConfigParser()
    config["SBI Customer Margin Ratios"] = {
        "update_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        "url": "https://example.invalid/ratios",
        "regulation_header": "Regulation",
        "headers": "('Symbol', 'Regulation')",
        "symbol_header": "Symbol",
        "suspended": "Suspended",
        "customer_margin_ratio_string": "Ratio ",
    }

    monkeypatch.setattr(
        customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setattr(
        customer_margin_ratios.pd,
        "read_html",
        lambda *_args, **_kwargs: [
            pd.DataFrame([["1234", "Ratio 30"]], columns=["Code", "Status"])
        ],
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    assert "expected table headers were not found" in str(e.value)
    assert not Path(trade.customer_margin_ratios).exists()


def test_save_customer_margin_ratios_wraps_http_status_errors(
    monkeypatch, tmp_path
):
    trade = SimpleNamespace(
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        market_holidays=str(tmp_path / "market_holidays.csv"),
    )
    config = ConfigParser()
    config["SBI Customer Margin Ratios"] = {
        "update_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        "url": "https://example.invalid/ratios",
        "regulation_header": "Regulation",
        "headers": "('Symbol', 'Regulation')",
        "symbol_header": "Symbol",
        "suspended": "Suspended",
        "customer_margin_ratio_string": "Ratio ",
    }

    def raise_http_error():
        raise customer_margin_ratios.requests.exceptions.HTTPError(
            "500 Server Error"
        )

    monkeypatch.setattr(
        customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=raise_http_error,
        ),
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    assert "Unable to refresh customer margin ratios" in str(e.value)
    assert "500 Server Error" in str(e.value)
    assert not Path(trade.customer_margin_ratios).exists()


def test_save_customer_margin_ratios_wraps_html_parse_errors(
    monkeypatch, tmp_path
):
    trade = SimpleNamespace(
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        market_holidays=str(tmp_path / "market_holidays.csv"),
    )
    config = ConfigParser()
    config["SBI Customer Margin Ratios"] = {
        "update_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        "url": "https://example.invalid/ratios",
        "regulation_header": "Regulation",
        "headers": "('Symbol', 'Regulation')",
        "symbol_header": "Symbol",
        "suspended": "Suspended",
        "customer_margin_ratio_string": "Ratio ",
    }

    def raise_parse_error(*_args, **_kwargs):
        raise ValueError("No tables found")

    monkeypatch.setattr(
        customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setattr(
        customer_margin_ratios.pd,
        "read_html",
        raise_parse_error,
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    assert "Unable to refresh customer margin ratios" in str(e.value)
    assert "No tables found" in str(e.value)
    assert not Path(trade.customer_margin_ratios).exists()


def test_save_customer_margin_ratios_preserves_previous_file_on_write_error(
    monkeypatch, tmp_path
):
    trade = SimpleNamespace(
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        market_holidays=str(tmp_path / "market_holidays.csv"),
    )
    config = ConfigParser()
    config["SBI Customer Margin Ratios"] = {
        "update_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        "url": "https://example.invalid/ratios",
        "regulation_header": "Regulation",
        "headers": "('Symbol', 'Regulation')",
        "symbol_header": "Symbol",
        "suspended": "Suspended",
        "customer_margin_ratio_string": "Ratio ",
    }
    target_path = Path(trade.customer_margin_ratios)
    target_path.write_text("1111,0.9\n", encoding="utf-8")

    monkeypatch.setattr(
        customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setattr(
        customer_margin_ratios.pd,
        "read_html",
        lambda *_args, **_kwargs: [
            pd.DataFrame(
                [["1234", "Ratio 30"]],
                columns=["Symbol", "Regulation"],
            )
        ],
    )

    def raise_replace_error(*_args, **_kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(config_io.os, "replace", raise_replace_error)

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    assert "Unable to refresh customer margin ratios" in str(e.value)
    assert "replace failed" in str(e.value)
    assert target_path.read_text(encoding="utf-8") == "1111,0.9\n"
    assert not list(tmp_path.glob(".customer_margin_ratios.csv.*.tmp"))


def test_save_customer_margin_ratios_does_not_double_carriage_returns(
    monkeypatch, tmp_path
):
    trade = SimpleNamespace(
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        market_holidays=str(tmp_path / "market_holidays.csv"),
    )
    config = ConfigParser()
    config["SBI Customer Margin Ratios"] = {
        "update_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        "url": "https://example.invalid/ratios",
        "regulation_header": "Regulation",
        "headers": "('Symbol', 'Regulation')",
        "symbol_header": "Symbol",
        "suspended": "Suspended",
        "customer_margin_ratio_string": "Ratio ",
    }

    monkeypatch.setattr(
        customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setattr(
        customer_margin_ratios.pd,
        "read_html",
        lambda *_args, **_kwargs: [
            pd.DataFrame(
                [
                    ["1234", "Ratio 5"],
                    ["2345", "Ratio 30"],
                    ["3456", "Ratio 100"],
                    ["5678", "Suspended"],
                ],
                columns=["Symbol", "Regulation"],
            )
        ],
    )

    customer_margin_ratios.save_customer_margin_ratios(trade, config)

    csv_bytes = Path(trade.customer_margin_ratios).read_bytes()
    assert b"\r\r\n" not in csv_bytes
    assert csv_bytes.replace(b"\r\n", b"\n") == (
        b"1234,0.05\n2345,0.3\n3456,1\n5678,suspended\n"
    )


def test_save_customer_margin_ratios_rejects_zero_ratio(monkeypatch, tmp_path):
    trade = SimpleNamespace(
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        market_holidays=str(tmp_path / "market_holidays.csv"),
    )
    config = ConfigParser()
    config["SBI Customer Margin Ratios"] = {
        "update_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        "url": "https://example.invalid/ratios",
        "regulation_header": "Regulation",
        "headers": "('Symbol', 'Regulation')",
        "symbol_header": "Symbol",
        "suspended": "Suspended",
        "customer_margin_ratio_string": "Ratio ",
    }

    monkeypatch.setattr(
        customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setattr(
        customer_margin_ratios.pd,
        "read_html",
        lambda *_args, **_kwargs: [
            pd.DataFrame(
                [["1234", "Ratio 0"]],
                columns=["Symbol", "Regulation"],
            )
        ],
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    assert "invalid customer margin ratio was found" in str(e.value)
    assert not Path(trade.customer_margin_ratios).exists()


def test_get_latest_wraps_market_holiday_refresh_get_errors(
    monkeypatch, tmp_path
):
    config = _build_market_holidays_config()

    def raise_head_exception(*_args, **_kwargs):
        raise customer_margin_ratios.requests.exceptions.RequestException(
            "head failed"
        )

    def raise_get_exception(*_args, **_kwargs):
        raise customer_margin_ratios.requests.exceptions.RequestException(
            "boom"
        )

    monkeypatch.setattr(
        customer_margin_ratios.web_utilities,
        "make_head_request",
        raise_head_exception,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        raise_get_exception,
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.get_latest(
            config,
            str(tmp_path / "market_holidays.csv"),
            "15:30:00",
            "Asia/Tokyo",
        )

    assert "Unable to refresh market holidays" in str(e.value)


def test_get_latest_uses_cached_market_holidays_after_head_timeout(
    monkeypatch, tmp_path
):
    config = _build_market_holidays_config()
    market_holidays = tmp_path / "market_holidays.csv"
    market_holidays.write_text("2026/01/01\n", encoding="utf-8")

    def raise_head_timeout(*_args, **_kwargs):
        raise customer_margin_ratios.requests.exceptions.Timeout(
            "head timed out"
        )

    monkeypatch.setattr(
        customer_margin_ratios.web_utilities,
        "make_head_request",
        raise_head_timeout,
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: pytest.fail("GET should not run"),
    )

    assert (
        customer_margin_ratios.get_latest(
            config,
            str(market_holidays),
            "00:00:00",
            "Asia/Tokyo",
        )
        is False
    )


def test_get_latest_uses_cached_market_holidays_without_last_modified(
    monkeypatch, tmp_path
):
    config = _build_market_holidays_config()
    market_holidays = tmp_path / "market_holidays.csv"
    market_holidays.write_text("2026/01/01\n", encoding="utf-8")

    monkeypatch.setattr(
        customer_margin_ratios.web_utilities,
        "make_head_request",
        lambda *_args, **_kwargs: SimpleNamespace(headers={}),
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: pytest.fail("GET should not run"),
    )

    assert (
        customer_margin_ratios.get_latest(
            config,
            str(market_holidays),
            "00:00:00",
            "Asia/Tokyo",
        )
        is False
    )


def test_refresh_market_holidays_wraps_http_status_errors(
    monkeypatch, tmp_path
):
    config = _build_market_holidays_config()
    market_holidays = tmp_path / "market_holidays.csv"

    def raise_http_error():
        raise customer_margin_ratios.requests.exceptions.HTTPError(
            "500 Server Error"
        )

    monkeypatch.setattr(
        customer_margin_ratios,
        "_get_market_holidays_last_modified",
        lambda *_args, **_kwargs: pd.Timestamp("2024-01-01", tz="UTC"),
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=b"<html></html>",
            raise_for_status=raise_http_error,
        ),
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios._refresh_market_holidays_cache(
            config["Market Holidays"],
            str(market_holidays),
            pd.Timestamp(0, tz="UTC", unit="s"),
        )

    assert "Unable to refresh market holidays" in str(e.value)
    assert "500 Server Error" in str(e.value)
    assert not market_holidays.exists()


def test_refresh_market_holidays_wraps_read_timeouts(monkeypatch, tmp_path):
    config = _build_market_holidays_config()
    market_holidays = tmp_path / "market_holidays.csv"
    calls = []

    def raise_timeout(url, **kwargs):
        calls.append((url, kwargs))
        raise customer_margin_ratios.requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(
        customer_margin_ratios,
        "_get_market_holidays_last_modified",
        lambda *_args, **_kwargs: pd.Timestamp("2024-01-01", tz="UTC"),
    )
    monkeypatch.setattr(
        customer_margin_ratios.requests,
        "get",
        raise_timeout,
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios._refresh_market_holidays_cache(
            config["Market Holidays"],
            str(market_holidays),
            pd.Timestamp(0, tz="UTC", unit="s"),
        )

    assert "Unable to refresh market holidays" in str(e.value)
    assert "timed out" in str(e.value)
    assert calls == [("https://example.invalid/holidays", {"timeout": 5})]
    assert not market_holidays.exists()


def test_get_latest_wraps_empty_market_holidays_cache(monkeypatch, tmp_path):
    config = _build_market_holidays_config()
    market_holidays = tmp_path / "market_holidays.csv"
    market_holidays.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        customer_margin_ratios.web_utilities,
        "make_head_request",
        lambda *_args, **_kwargs: SimpleNamespace(
            headers={"last-modified": "Thu, 01 Jan 1970 00:00:00 GMT"}
        ),
    )

    with pytest.raises(MarketDataError) as e:
        customer_margin_ratios.get_latest(
            config,
            str(market_holidays),
            "15:30:00",
            "Asia/Tokyo",
        )

    assert "Unable to read market holidays cache" in str(e.value)
