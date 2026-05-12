"""Assist with discretionary day trading of stocks on margin."""

from io import BytesIO
from multiprocessing.managers import BaseManager
import argparse
import atexit
import csv
import os
import sys
import threading

from pynput import keyboard
from pynput import mouse
import pandas as pd
import requests

from core_utilities import (
    data_utilities,
    errors,
    file_utilities,
    process_utilities,
)
from core_utilities.config_io import read_config, write_config
from core_utilities.config_validation import (
    ConfigError,
    ensure_section_exists,
    evaluate_value,
)
from app import (
    actions,
    config_builder,
    config_workflow,
    listeners,
    market_data,
    models,
    runtime,
    scheduler,
    startup_script,
    trade_service,
)
from interaction_utilities import (
    gui_interactions,
    speech_synthesis,
    text_recognition,
)
from web_utilities import web_utilities

RATIO_EPSILON = 1e-4
SANS_INITIAL_SECURITIES_CODE_REGEX = (
    r"[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?"
)
SECURITIES_CODE_REGEX = "[1-9]" + SANS_INITIAL_SECURITIES_CODE_REGEX
Trade = models.Trade


# Entry Point


def main():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(
        *args.P,
        script_path=__file__,
        start_execute_action_thread_fn=actions.start_execute_action_thread,
    )

    if file_utilities.create_launchers_exit(args, __file__):
        return
    if configure_exit(args, trade):
        return

    config = configure(trade)
    ensure_section_exists(config, trade.process)
    gui_state = gui_interactions.GuiState(
        evaluate_value(config[trade.process]["interactive_windows"])
    )
    runtime.run(
        args,
        trade,
        config,
        gui_state,
        _get_runtime_dependencies(),
    )


# CLI and Configuration


def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        "-P",
        nargs=2,
        default=("SBI Securities", "HYPERSBI2"),
        help="set the brokerage and the process [defaults: %(default)s]",
        metavar=("BROKERAGE", "PROCESS|EXECUTABLE_PATH"),
    )
    parser.add_argument(
        "-r", action="store_true", help="save the customer margin ratios"
    )
    parser.add_argument("-s", action="store_true", help="start the scheduler")
    parser.add_argument(
        "-l",
        action="store_true",
        help="start the mouse and keyboard listeners",
    )
    parser.add_argument(
        "-a", nargs=1, help="execute an action", metavar="ACTION"
    )

    file_utilities.add_launcher_options(group)
    group.add_argument(
        "-SS",
        action="store_true",
        help="configure the startup script, create a shortcut to it,"
        " and exit",
    )
    group.add_argument(
        "-S", action="store_true", help="configure schedules and exit"
    )
    group.add_argument(
        "-L",
        action="store_true",
        help="configure the input map for buttons and keys and exit",
    )
    group.add_argument(
        "-A",
        nargs=1,
        help="configure an action, create a shortcut to it, and exit",
        metavar="ACTION",
    )
    group.add_argument(
        "-CB",
        action="store_true",
        help="configure the cash balance region and exit",
    )
    group.add_argument(
        "-U",
        action="store_true",
        help="configure the utilization ratio of the cash balance and exit",
    )
    group.add_argument(
        "-PL",
        action="store_true",
        help="configure the price limit region and exit",
    )
    group.add_argument(
        "-DLL",
        action="store_true",
        help="configure the daily loss limit ratio and exit",
    )
    group.add_argument(
        "-MDN",
        action="store_true",
        help="configure the maximum daily number of trades and exit",
    )
    group.add_argument(
        "-D",
        nargs=1,
        help="delete the startup script or an action,"
        " delete the shortcut to it, and exit",
        metavar="SCRIPT_BASE|ACTION",
    )
    group.add_argument(
        "-C", action="store_true", help="check configuration changes and exit"
    )

    return parser.parse_args(None if sys.argv[1:] else ["-h"])


def configure(trade, can_interpolate=True, can_override=True):
    """Set up the configuration for a trade."""
    return config_builder.configure(
        trade,
        file_utilities=file_utilities,
        data_utilities=data_utilities,
        securities_code_regex=SECURITIES_CODE_REGEX,
        read_config_fn=read_config,
        can_interpolate=can_interpolate,
        can_override=can_override,
    )


def configure_exit(args, trade):
    """Configure parameters based on command-line arguments and exit."""
    return config_workflow.configure_exit(
        args, trade, _get_config_workflow_dependencies()
    )


def _is_xy(value):
    """Return True if the value represents exactly two integers (X, Y)."""
    return config_workflow.is_xy(value)


# Data Creation and Persistence


def create_completion(trade, config):
    """Generate completion scripts for options and values."""
    config_workflow.create_completion(trade, config, file_utilities)


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
        except (requests.exceptions.RequestException, OSError) as e:
            raise errors.ExternalServiceError(
                f"Unable to refresh customer margin ratios: {e}"
            ) from e

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


def save_market_data(trade, config):
    """Split the rankings CSV by the first digit of the securities code."""
    rankings = config["Market Data"]["rankings"].replace("\\\\", "\\")
    try:
        return market_data.split_rankings_by_digit(
            rankings=rankings,
            closing_prices_prefix=trade.closing_prices,
            code_regex=SECURITIES_CODE_REGEX,
        )
    except errors.MarketDataError:
        return False


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


# Scheduling and Background Processes


def start_scheduler(trade, config, gui_state, process, base_manager):
    """Start a scheduler for executing actions at specified times."""
    scheduler.start_scheduler(
        trade,
        config,
        gui_state,
        process,
        base_manager,
        _get_scheduler_dependencies(),
    )


def start_listeners(
    trade, config, gui_state, base_manager, is_persistent=False
):
    """Initiate listeners for mouse and keyboard events."""
    listeners.start_listeners(
        trade,
        config,
        gui_state,
        base_manager,
        _get_listener_dependencies(),
        is_persistent=is_persistent,
    )


def _start_speaking_process(trade, config):
    """Start a speaking process using the configured voice settings."""
    return listeners.start_speaking_process(trade, config, speech_synthesis)


def _get_listener_dependencies():
    """Return dependencies required by listener startup helpers."""
    return {
        "keyboard": keyboard,
        "mouse": mouse,
        "process_utilities": process_utilities,
        "start_speaking_process_fn": _start_speaking_process,
        "threading": threading,
    }


def _get_scheduler_dependencies():
    """Return dependencies required by scheduler helpers."""
    return {
        "execute_action_fn": actions.execute_action,
        "process_utilities": process_utilities,
        "speech_synthesis": speech_synthesis,
        "start_speaking_process_fn": _start_speaking_process,
    }


def _get_runtime_dependencies():
    """Return runtime dependencies required by the app runtime."""
    return {
        "atexit": atexit,
        "base_manager_cls": BaseManager,
        "execute_action_fn": actions.execute_action,
        "process_utilities": process_utilities,
        "save_customer_margin_ratios_fn": save_customer_margin_ratios,
        "speech_synthesis": speech_synthesis,
        "start_listeners_fn": start_listeners,
        "start_scheduler_fn": start_scheduler,
        "threading": threading,
        "write_config_fn": write_config,
    }


def _get_config_workflow_dependencies():
    """Return dependencies required by config workflow helpers."""
    return {
        "configure_fn": configure,
        "create_completion_fn": create_completion,
        "create_startup_script_fn": create_startup_script,
        "file_utilities": file_utilities,
        "is_xy_fn": _is_xy,
        "ratio_epsilon": RATIO_EPSILON,
        "script_path": __file__,
    }


# Startup Automation


def create_startup_script(trade, config):
    """Create a startup script for a trade."""
    startup_script.create_startup_script(
        trade, config, __file__, file_utilities
    )


# Trading Calculations


def calculate_share_size(trade, config, position):
    """Determine the share size for a given trade."""
    if trade.symbol and trade.cash_balance:
        customer_margin_ratio = float(
            config[trade.customer_margin_ratios_section][
                "customer_margin_ratio"
            ]
        )
        try:
            with open(trade.customer_margin_ratios, encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == trade.symbol:
                        if row[1] == "suspended":
                            return (False, "Margin trading suspended.")

                        customer_margin_ratio = float(row[1])
                        break
        except OSError:
            pass

        share_size = trade_service.calculate_share_size_from_inputs(
            cash_balance=trade.cash_balance,
            utilization_ratio=float(
                config[trade.process]["utilization_ratio"]
            ),
            customer_margin_ratio=customer_margin_ratio,
            price_limit=get_price_limit(trade, config),
            position=position,
        )
        if share_size == 0:
            return (False, "Insufficient cash balance.")

        trade.share_size = share_size
        return (True, None)

    return (False, "Symbol or cash balance not provided.")


def get_price_limit(trade, config):
    """Calculate the price limit for a trade."""
    closing_price = 0.0
    try:
        with open(
            f"{trade.closing_prices}{trade.symbol[0]}.csv", encoding="utf-8"
        ) as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                if row[0].strip() == trade.symbol:
                    closing_price = float(row[1].strip())
                    break
    except OSError:
        pass

    if closing_price:
        price_limit = trade_service.calculate_price_limit_from_closing_price(
            closing_price
        )
    else:
        price_limit = text_recognition.recognize_text(
            *map(
                int,
                config[trade.geometries_section]["price_limit_region"].split(
                    ","
                ),
            ),
            int(config[trade.process]["image_magnification"]),
            int(config[trade.process]["binarization_threshold"]),
            config[trade.process].getboolean("is_dark_theme"),
            text_type="decimal_numbers",
        )
    return price_limit


if __name__ == "__main__":
    try:
        main()
    except ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except errors.TradingAssistantError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
