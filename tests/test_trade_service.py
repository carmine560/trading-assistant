"""Tests for extracted pure trading math helpers."""

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
