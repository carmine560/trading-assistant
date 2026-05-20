"""Customer margin ratio refresh and market-data freshness helpers."""

import os
import re
from decimal import Decimal
from io import BytesIO

import pandas as pd
import requests

from core_utilities import errors
from core_utilities.config_io import write_file_atomically
from core_utilities.config_validation import (
    ensure_section_exists,
    evaluate_value,
)
from web_utilities import web_utilities


def save_customer_margin_ratios(trade, config):
    """Save customer margin ratios for a given trade."""
    ensure_section_exists(config, trade.customer_margin_ratios_section)

    section = config[trade.customer_margin_ratios_section]

    if get_latest(
        config,
        trade.market_holidays,
        section["update_time"],
        section["timezone"],
        trade.customer_margin_ratios,
    ):
        try:
            response = requests.get(section["url"], timeout=5)
            response.raise_for_status()
            # lxml reads the <meta charset> tag, so raw bytes are decoded
            # correctly.
            dfs = pd.read_html(
                BytesIO(response.content),
                match=section["regulation_header"],
                flavor="lxml",
                header=0,
            )
        except (
            OSError,
            ValueError,
            requests.exceptions.RequestException,
        ) as e:
            raise errors.ExternalServiceError(
                f"Unable to refresh customer margin ratios: {e}"
            ) from e

        matched_df = None
        headers = evaluate_value(section["headers"])
        for df in dfs:
            if tuple(df.columns.values) == headers:
                matched_df = df[
                    [section["symbol_header"], section["regulation_header"]]
                ]
                break
        if matched_df is None:
            raise errors.ExternalServiceError(
                "Unable to refresh customer margin ratios: "
                "expected table headers were not found."
            )

        matched_df = matched_df[
            matched_df[section["regulation_header"]].str.contains(
                f"{section['suspended']}|"
                f"{section['customer_margin_ratio_string']}"
            )
        ]
        matched_df[section["regulation_header"]] = matched_df[
            section["regulation_header"]
        ].replace(f".*{section['suspended']}.*", "suspended", regex=True)
        customer_margin_ratio_rows = matched_df[
            section["regulation_header"]
        ].str.contains(section["customer_margin_ratio_string"])
        customer_margin_ratios = matched_df.loc[
            customer_margin_ratio_rows,
            section["regulation_header"],
        ].str.extract(
            rf"{re.escape(section['customer_margin_ratio_string'])}(\d+)"
        )
        if (
            customer_margin_ratios[0].isna().any()
            or (customer_margin_ratios[0].map(Decimal) <= 0).any()
        ):
            raise errors.ExternalServiceError(
                "Unable to refresh customer margin ratios: "
                "invalid customer margin ratio was found."
            )
        matched_df.loc[
            customer_margin_ratio_rows,
            section["regulation_header"],
        ] = customer_margin_ratios[0].map(lambda v: str(Decimal(v) / 100))
        try:
            write_file_atomically(
                trade.customer_margin_ratios,
                "w",
                lambda f: matched_df.to_csv(f, header=False, index=False),
                newline="",
            )
        except OSError as e:
            raise errors.ExternalServiceError(
                f"Unable to refresh customer margin ratios: {e}"
            ) from e


def get_latest(
    config, market_holidays, update_time, timezone, *paths, volatile_time=None
):
    """Check if the latest market data needs to be fetched."""
    section = config["Market Holidays"]
    holidays_modified_time = _get_file_modified_time(market_holidays)
    _refresh_market_holidays_cache(
        section,
        market_holidays,
        holidays_modified_time,
    )
    modified_time = _get_paths_modified_time(paths)
    df = _load_market_holidays_cache(market_holidays)
    latest = _get_latest_trading_day(df, section, update_time, timezone)

    if modified_time >= latest:
        return False
    if volatile_time and not _is_stable_refresh_window(
        df,
        section,
        timezone,
        update_time,
        volatile_time,
    ):
        return False

    return latest


def _get_file_modified_time(path):
    """Return the file modification time, or the epoch if absent."""
    if os.path.isfile(path):
        return pd.Timestamp(os.path.getmtime(path), tz="UTC", unit="s")
    return pd.Timestamp(0, tz="UTC", unit="s")


def _refresh_market_holidays_cache(section, market_holidays, modified_time):
    """Refresh the market-holidays cache when the upstream page is newer."""
    last_modified = _get_market_holidays_last_modified(section["url"])
    if last_modified is None:
        if modified_time > pd.Timestamp(0, tz="UTC", unit="s"):
            return
    elif modified_time >= last_modified:
        return

    try:
        response = requests.get(section["url"], timeout=5)
        response.raise_for_status()
        dfs = pd.read_html(
            BytesIO(response.content),
            match=section["date_header"],
        )
        df = pd.concat(dfs)[section["date_header"]]
        df.replace(
            r"^(\d{4}/\d{2}/\d{2}).*$",
            r"\1",
            inplace=True,
            regex=True,
        )
        write_file_atomically(
            market_holidays,
            "w",
            lambda f: df.to_csv(f, header=False, index=False),
            newline="",
        )
    except (
        KeyError,
        OSError,
        ValueError,
        requests.exceptions.RequestException,
    ) as e:
        raise errors.ExternalServiceError(
            f"Unable to refresh market holidays: {e}"
        ) from e


def _get_market_holidays_last_modified(url):
    """Fetch the last-modified timestamp for the market-holidays page."""
    try:
        head = web_utilities.make_head_request(url)
        return pd.Timestamp(head.headers["last-modified"])
    except (
        KeyError,
        ValueError,
        errors.ExternalServiceError,
        requests.exceptions.RequestException,
    ):
        return None


def _get_paths_modified_time(paths):
    """Return the oldest modification time across required output paths."""
    modified_time = pd.Timestamp.now(tz="UTC")
    for path in paths:
        if not os.path.isfile(path):
            return pd.Timestamp(0, tz="UTC", unit="s")
        modified_time = min(modified_time, _get_file_modified_time(path))
    return modified_time


def _load_market_holidays_cache(market_holidays):
    """Load the cached market-holidays file with validation."""
    try:
        df = pd.read_csv(market_holidays, header=None, dtype=str)
        if df.empty or 0 not in df:
            raise ValueError("market holidays cache is empty or malformed")
        return df
    except (OSError, pd.errors.EmptyDataError, ValueError) as e:
        raise errors.MarketDataError(
            f"Unable to read market holidays cache: {e}"
        ) from e


def _get_latest_trading_day(df, section, update_time, timezone):
    """Return the most recent trading day implied by the holiday calendar."""
    latest = pd.Timestamp(update_time, tz=timezone)
    if pd.Timestamp.now(tz="UTC") < latest:
        latest -= pd.Timedelta(days=1)

    while _is_holiday_or_weekend(df, section["date_format"], latest):
        latest -= pd.Timedelta(days=1)

    return latest


def _is_holiday_or_weekend(df, date_format, date):
    """Return True when the date is a weekend or listed holiday."""
    return (
        date.weekday() >= 5
        or df[0].str.contains(date.strftime(date_format)).any()
    )


def _is_stable_refresh_window(
    df, section, timezone, update_time, volatile_time
):
    """Return True when a volatile refresh window should still refresh."""
    now = pd.Timestamp.now(tz=timezone)
    if _is_holiday_or_weekend(df, section["date_format"], now):
        return True
    return not (
        pd.Timestamp(volatile_time, tz=timezone)
        <= now
        <= pd.Timestamp(update_time, tz=timezone)
    )
