"""Tests for customer margin ratio refresh behavior."""

from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app import customer_margin_ratios
from core_utilities.errors import ExternalServiceError


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
        lambda *_args, **_kwargs: SimpleNamespace(content=b"<html></html>"),
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
