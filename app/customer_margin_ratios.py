"""Customer margin ratio refresh and market-data freshness helpers."""

from io import BytesIO
import os

import pandas as pd
import requests

from core_utilities import errors
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
            # 'lxml' reads the '<meta charset>' tag, so raw bytes are decoded
            # correctly.
            dfs = pd.read_html(
                BytesIO(response.content),
                match=section["regulation_header"],
                flavor="lxml",
                header=0,
            )
        except (requests.exceptions.RequestException, OSError) as exc:
            raise errors.ExternalServiceError(
                f"Unable to refresh customer margin ratios: {exc}"
            ) from exc

        df = None
        headers = evaluate_value(section["headers"])
        for index, df in enumerate(dfs):
            if tuple(df.columns.values) == headers:
                df = dfs[index][
                    [section["symbol_header"], section["regulation_header"]]
                ]
                break
        if df is not None:
            df = df[
                df[section["regulation_header"]].str.contains(
                    f"{section['suspended']}|"
                    f"{section['customer_margin_ratio_string']}"
                )
            ]
            df[section["regulation_header"]] = df[
                section["regulation_header"]
            ].replace(f".*{section['suspended']}.*", "suspended", regex=True)
            df[section["regulation_header"]] = df[
                section["regulation_header"]
            ].replace(
                rf".*{section['customer_margin_ratio_string']}(\d+).*",
                r"0.\1",
                regex=True,
            )
            df.to_csv(trade.customer_margin_ratios, header=False, index=False)


def get_latest(
    config, market_holidays, update_time, timezone, *paths, volatile_time=None
):
    """Check if the latest market data needs to be fetched."""
    modified_time = pd.Timestamp(0, tz="UTC", unit="s")
    if os.path.isfile(market_holidays):
        modified_time = pd.Timestamp(
            os.path.getmtime(market_holidays), tz="UTC", unit="s"
        )

    head = web_utilities.make_head_request(config["Market Holidays"]["url"])
    if modified_time < pd.Timestamp(head.headers["last-modified"]):
        dfs = pd.read_html(
            config["Market Holidays"]["url"],
            match=config["Market Holidays"]["date_header"],
        )
        df = pd.concat(dfs)[config["Market Holidays"]["date_header"]]
        df.replace(r"^(\d{4}/\d{2}/\d{2}).*$", r"\1", inplace=True, regex=True)
        df.to_csv(market_holidays, header=False, index=False)

    modified_time = pd.Timestamp.now(tz="UTC")
    for i, _ in enumerate(paths):
        if os.path.isfile(paths[i]):
            modified_time = min(
                pd.Timestamp(os.path.getmtime(paths[i]), tz="UTC", unit="s"),
                modified_time,
            )
        else:
            modified_time = pd.Timestamp(0, tz="UTC", unit="s")
            break

    df = pd.read_csv(market_holidays, header=None, dtype=str)
    # Assume the web page is updated at 'update_time'.
    latest = pd.Timestamp(update_time, tz=timezone)
    if pd.Timestamp.now(tz="UTC") < latest:
        latest -= pd.Timedelta(days=1)

    while (
        df[0]
        .str.contains(
            latest.strftime(config["Market Holidays"]["date_format"])
        )
        .any()
        or latest.weekday() >= 5
    ):
        latest -= pd.Timedelta(days=1)

    if modified_time < latest:
        if volatile_time:
            now = pd.Timestamp.now(tz=timezone)
            if (
                df[0]
                .str.contains(
                    now.strftime(config["Market Holidays"]["date_format"])
                )
                .any()
                or now.weekday() >= 5
            ):
                return latest
            if (
                not pd.Timestamp(volatile_time, tz=timezone)
                <= now
                <= pd.Timestamp(update_time, tz=timezone)
            ):
                return latest
        else:
            return latest
    return False
