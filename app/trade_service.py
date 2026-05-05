"""Trading math helpers extracted from the main entrypoint."""

PRICE_RANGES = (
    (100, 30),
    (200, 50),
    (500, 80),
    (700, 100),
    (1000, 150),
    (1500, 300),
    (2000, 400),
    (3000, 500),
    (5000, 700),
    (7000, 1000),
    (10000, 1500),
    (15000, 3000),
    (20000, 4000),
    (30000, 5000),
    (50000, 7000),
    (70000, 10000),
    (100000, 15000),
    (150000, 30000),
    (200000, 40000),
    (300000, 50000),
    (500000, 70000),
    (700000, 100000),
    (1000000, 150000),
    (1500000, 300000),
    (2000000, 400000),
    (3000000, 500000),
    (5000000, 700000),
    (7000000, 1000000),
    (10000000, 1500000),
    (15000000, 3000000),
    (20000000, 4000000),
    (30000000, 5000000),
    (50000000, 7000000),
    (float("inf"), 10000000),
)
TRADING_UNIT = 100
SHORT_SHARE_SIZE_LIMIT = 50 * TRADING_UNIT


def calculate_price_limit_from_closing_price(closing_price):
    """Return the price limit using the previous closing price."""
    for maximum_price, limit in PRICE_RANGES:
        if closing_price < maximum_price:
            return closing_price + limit
    raise ValueError("No price limit found for the closing price.")


def calculate_share_size_from_inputs(
    cash_balance,
    utilization_ratio,
    customer_margin_ratio,
    price_limit,
    position,
):
    """Return the share size using only already-resolved numeric inputs."""
    share_size = (
        int(
            cash_balance
            * utilization_ratio
            / customer_margin_ratio
            / price_limit
            / TRADING_UNIT
        )
        * TRADING_UNIT
    )
    if position == "short" and share_size > SHORT_SHARE_SIZE_LIMIT:
        return SHORT_SHARE_SIZE_LIMIT
    return share_size
