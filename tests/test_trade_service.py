"""Tests for extracted pure trading math helpers."""

import pytest

from app import trade_service


def test_calculate_price_limit_from_closing_price_uses_matching_band():
    assert trade_service.calculate_price_limit_from_closing_price(980) == 1130


def test_calculate_share_size_from_inputs_rounds_down_to_unit():
    assert (
        trade_service.calculate_share_size_from_inputs(
            cash_balance=300_000,
            utilization_ratio=0.5,
            customer_margin_ratio=0.5,
            price_limit=1130,
            position="long",
        )
        == 200
    )


def test_calculate_share_size_from_inputs_caps_short_positions():
    assert (
        trade_service.calculate_share_size_from_inputs(
            cash_balance=10_000_000,
            utilization_ratio=0.5,
            customer_margin_ratio=0.5,
            price_limit=1130,
            position="short",
        )
        == 5000
    )


def test_calculate_share_size_from_inputs_keeps_exact_trading_unit():
    assert (
        trade_service.calculate_share_size_from_inputs(
            cash_balance=100_000,
            utilization_ratio=1,
            customer_margin_ratio=1,
            price_limit=1000,
            position="long",
        )
        == 100
    )


@pytest.mark.parametrize(
    ("input_name", "input_value", "message"),
    [
        ("cash_balance", 0, "Cash balance must be positive."),
        ("cash_balance", -1, "Cash balance must be positive."),
        ("utilization_ratio", 0, "Utilization ratio must be positive."),
        ("utilization_ratio", -0.1, "Utilization ratio must be positive."),
        (
            "customer_margin_ratio",
            0,
            "Customer margin ratio must be positive.",
        ),
        (
            "customer_margin_ratio",
            -0.1,
            "Customer margin ratio must be positive.",
        ),
        ("price_limit", 0, "Price limit must be positive."),
        ("price_limit", -1, "Price limit must be positive."),
    ],
)
def test_calculate_share_size_from_inputs_rejects_non_positive_inputs(
    input_name,
    input_value,
    message,
):
    inputs = {
        "cash_balance": 300_000,
        "utilization_ratio": 0.5,
        "customer_margin_ratio": 0.5,
        "price_limit": 1130,
    }
    inputs[input_name] = input_value

    with pytest.raises(ValueError) as e:
        trade_service.calculate_share_size_from_inputs(
            **inputs,
            position="long",
        )

    assert str(e.value) == message
