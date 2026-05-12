"""Trading assistant runtime orchestration for actions and services."""

from io import BytesIO
from multiprocessing.managers import BaseManager
import atexit
import os
import threading

from app import actions, listeners, scheduler
import pandas as pd
import requests

from core_utilities import errors, process_utilities
from core_utilities.config_io import write_config
from core_utilities.config_validation import (
    ensure_section_exists,
    evaluate_value,
)
from interaction_utilities import speech_synthesis
from web_utilities import web_utilities


def run(args, trade, config, gui_state):
    """Run the application."""
    atexit.register(persist_config_on_exit, trade, config)

    if args.r:
        save_customer_margin_ratios(trade, config)

    is_running = process_utilities.is_running(trade.process)
    base_manager = None
    if args.s or args.l or args.a:
        base_manager = _start_speech_manager(trade)

    if args.a:
        _execute_single_action(
            args,
            trade,
            config,
            gui_state,
            base_manager,
            is_running,
        )
    if args.l and is_running:
        listeners.start_listeners(trade, config, gui_state, base_manager)
    if args.s and is_running:
        threading.Thread(
            target=scheduler.start_scheduler,
            args=(trade, config, gui_state, trade.process, base_manager),
        ).start()


def persist_config_on_exit(trade, config):
    """Persist configuration on interpreter shutdown."""
    # Ensure the config is written on normal interpreter shutdown, since
    # 'IndicatorThread.stop()' or 'IndicatorThread.on_closing()' may not run if
    # the main thread terminates abruptly.
    write_config(config, trade.config_path, is_encrypted=True)


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


def _start_speech_manager(trade):
    """Create and start the speech manager used by runtime workflows."""
    # Use 'BaseManager' to share 'SpeechManager' across processes.
    BaseManager.register("SpeechManager", speech_synthesis.SpeechManager)
    base_manager = BaseManager()
    base_manager.start()
    trade.speech_manager = base_manager.SpeechManager()
    return base_manager


def _execute_single_action(
    args,
    trade,
    config,
    gui_state,
    base_manager,
    is_running,
):
    """Execute a single configured action and manage transient listeners."""
    should_start_transient_listeners = not (is_running and args.l)
    if should_start_transient_listeners:
        listeners.start_listeners(
            trade,
            config,
            gui_state,
            base_manager,
            is_persistent=True,
        )

    try:
        actions.execute_action(
            trade,
            config,
            gui_state,
            config[trade.actions_section][args.a[0]],
        )
    finally:
        if should_start_transient_listeners:
            process_utilities.stop_listeners(
                trade.mouse_listener,
                trade.keyboard_listener,
                base_manager,
                trade.speech_manager,
                trade.speaking_process,
            )
            trade.stop_listeners_event.set()
            trade.wait_listeners_thread.join()
