"""Tests for customer margin ratio refresh behavior."""

from configparser import ConfigParser
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

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


def test_get_latest_wraps_market_holiday_refresh_errors(monkeypatch, tmp_path):
    config = _build_market_holidays_config()

    def raise_request_exception(*_args, **_kwargs):
        raise customer_margin_ratios.requests.exceptions.RequestException(
            "boom"
        )

    monkeypatch.setattr(
        customer_margin_ratios.web_utilities,
        "make_head_request",
        raise_request_exception,
    )

    with pytest.raises(ExternalServiceError) as e:
        customer_margin_ratios.get_latest(
            config,
            str(tmp_path / "market_holidays.csv"),
            "15:30:00",
            "Asia/Tokyo",
        )

    assert "Unable to refresh market holidays" in str(e.value)


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
