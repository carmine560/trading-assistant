"""Assist with discretionary day trading of stocks on margin."""

from io import BytesIO
import argparse
import os
import sys

import pandas as pd
import requests

from app import (
    actions,
    config_builder,
    config_workflow,
    listeners,
    models,
    runtime,
    scheduler,
    startup_script,
)
from core_utilities import (
    data_utilities,
    errors,
    file_utilities,
)
from core_utilities.config_io import read_config
from core_utilities.config_validation import (
    ConfigError,
    ensure_section_exists,
    evaluate_value,
)
from interaction_utilities import gui_interactions
from web_utilities import web_utilities

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
    trade.save_customer_margin_ratios_fn = save_customer_margin_ratios
    trade.start_listeners_fn = start_listeners
    trade.start_scheduler_fn = start_scheduler

    if file_utilities.create_launchers_exit(args, __file__):
        return
    if config_workflow.configure_exit(
        args,
        trade,
        configure,
        create_completion,
        create_startup_script,
        __file__,
        1e-4,
    ):
        return

    config = configure(trade)
    ensure_section_exists(config, trade.process)
    gui_state = gui_interactions.GuiState(
        evaluate_value(config[trade.process]["interactive_windows"])
    )
    runtime.run(args, trade, config, gui_state)


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


# Data Creation and Persistence


def create_completion(trade, config):
    """Generate completion scripts for options and values."""
    config_workflow.create_completion(trade, config)


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
    scheduler.start_scheduler(trade, config, gui_state, process, base_manager)


def start_listeners(
    trade, config, gui_state, base_manager, is_persistent=False
):
    """Initiate listeners for mouse and keyboard events."""
    listeners.start_listeners(
        trade,
        config,
        gui_state,
        base_manager,
        is_persistent=is_persistent,
    )


# Startup Automation


def create_startup_script(trade, config):
    """Create a startup script for a trade."""
    startup_script.create_startup_script(
        trade, config, __file__, file_utilities
    )


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
