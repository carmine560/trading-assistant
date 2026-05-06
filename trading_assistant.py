"""Assist with discretionary day trading of stocks on margin."""

from datetime import date
from io import BytesIO
from multiprocessing.managers import BaseManager
import argparse
import atexit
import configparser
import csv
import os
import re
import sys
import threading
import win32clipboard

from pynput import keyboard
from pynput import mouse
import pandas as pd
import psutil
import pyautogui
import requests

from core_utilities import (
    configuration,
    data_utilities,
    file_utilities,
    process_utilities,
)
from app import actions as app_actions
from app import listeners as app_listeners
from app import market_data
from app import models as app_models
from app import runtime as app_runtime
from app import scheduler as app_scheduler
from app import startup_script as app_startup_script
from app import trade_service
from app import ui as app_ui
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
Trade = app_models.Trade
IndicatorThread = app_ui.IndicatorThread
MessageThread = app_ui.MessageThread


# Entry Point


def main():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(
        *args.P,
        script_path=__file__,
        start_execute_action_thread_fn=start_execute_action_thread,
    )

    file_utilities.create_launchers_exit(args, __file__)
    configure_exit(args, trade)

    config = configure(trade)
    configuration.ensure_section_exists(config, trade.process)
    gui_state = gui_interactions.GuiState(
        configuration.evaluate_value(
            config[trade.process]["interactive_windows"]
        )
    )
    app_runtime.run(
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
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
    else:
        config = configparser.ConfigParser(interpolation=None)

    config["General"] = {
        "fingerprint": "",
        "voice_name": "Microsoft Zira Desktop",
        "speech_rate": "2",
        "countdown_seconds_before_candle_close": "30, 10, 5",
    }
    config["Market Holidays"] = {
        "url": "https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html",
        "date_header": "日付",
        "date_format": "%Y/%m/%d",
    }
    config["Market Data"] = {
        "opening_time": "09:00:00",
        "midday_break_time": "11:30:00",
        "reopening_time": "12:30:00",
        "last_order_time": "15:25:00",
        "closing_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        # Double backslashes are required because these values are stored as
        # Python string literals for 'evaluate_value()':
        # 'securities_code_regex' via 'interactive_windows' and user-defined
        # actions, and 'rankings' via user-defined actions.
        "securities_code_regex": SECURITIES_CODE_REGEX.replace("\\", "\\\\"),
        "rankings": os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            "rankings.csv",
        ).replace("\\", "\\\\"),
    }
    config[trade.geometries_section] = {
        "cash_balance_region": "0, 0, 0, 0, 0",
        "price_limit_region": "0, 0, 0, 0, 0",
    }
    config[trade.actions_section] = {
        "show_hide_indicator": [("show_hide_indicator",)],
        "start_manual_recording": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "is_recording",
                        "False",
                        [
                            ("press_hotkeys", "alt, f9"),
                            ("sleep", "2"),
                            (
                                "is_recording",
                                "False",
                                [("speak_text", "Not recording.")],
                            ),
                        ],
                    )
                ],
            )
        ],
        "create_opening_chapter": [("write_chapter", "Opening", "Pre-market")],
        "create_midday_break_chapter": [("write_chapter", "Midday Break")],
        "create_reopening_chapter": [("write_chapter", "Reopening")],
        "stop_manual_recording": [
            ("is_recording", "True", [("press_hotkeys", "alt, f9")])
        ],
        "speak_cpu_utilization": [
            ("is_trading_day", "True", [("speak_cpu_utilization", "1")])
        ],
        "speak_seconds_until_open": [
            (
                "is_trading_day",
                "True",
                [("speak_seconds_until_time", "${Market Data:opening_time}")],
            )
        ],
        "speak_seconds_until_midday_break": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        "${Market Data:midday_break_time}",
                    )
                ],
            )
        ],
        "speak_seconds_until_reopen": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        "${Market Data:reopening_time}",
                    )
                ],
            )
        ],
        "speak_seconds_until_last_order": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        "${Market Data:last_order_time}",
                    )
                ],
            )
        ],
        "speak_seconds_until_end": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        f"${{{trade.process}:end_time}}",
                    )
                ],
            )
        ],
    }
    config[trade.schedules_section] = {}
    config[trade.variables_section] = {
        "current_date": date.min.strftime("%Y-%m-%d"),
        "initial_cash_balance": "0",
        "current_number_of_trades": "0",
    }

    if trade.vendor == "SBI Securities":
        config[trade.customer_margin_ratios_section] = {
            "customer_margin_ratio": "0.31",
            "update_time": "20:00:00",
            "timezone": "${Market Data:timezone}",
            "url": (
                "https://search.sbisec.co.jp/v2/popwin/attention/stock/"
                "margin_M29.html"
            ),
            "symbol_header": "コード",
            "regulation_header": "規制内容",
            "headers": ("銘柄", "コード", "建玉", "信用取引区分", "規制内容"),
            "customer_margin_ratio_string": "委託保証金率",
            "suspended": "新規建停止",
        }

    if trade.process == "HYPERSBI2":
        if not trade.executable:
            location_dat = os.path.join(
                os.path.expandvars("%LOCALAPPDATA%"),
                trade.vendor,
                trade.process,
                "location.dat",
            )
            try:
                with open(location_dat, encoding="utf-8") as f:
                    trade.executable = os.path.normpath(
                        os.path.join(f.read(), trade.process + ".exe")
                    )
            except OSError as e:
                print(e)
                for program_files in ("%ProgramFiles%", "%ProgramFiles(x86)%"):
                    executable = os.path.join(
                        os.path.expandvars(program_files),
                        trade.vendor,
                        trade.process,
                        trade.process + ".exe",
                    )
                    if os.path.isfile(executable):
                        trade.executable = executable
                        break
                if not trade.executable:
                    print(
                        f"The executable file for {trade.process}"
                        " does not exist."
                    )
                    sys.exit(1)

        file_description = file_utilities.get_file_description(
            trade.executable
        )
        title = (
            data_utilities.title_except_acronyms(file_description, ["SBI"])
            + " Assistant"
            if file_description
            else re.sub(r"[\W_]+", " ", trade.script_base).strip().title()
        )

        config[trade.window_titles_section] = {
            # Double backslashes are required because these values are stored
            # as Python string literals for 'evaluate_value()', used via
            # 'interactive_windows' and user-defined actions.
            "announcements": "お知らせ",
            "summary": (
                "個別銘柄" r"\\s.*\\((${Market Data:securities_code_regex})\\)"
            ),
            "watchlists": "登録銘柄",
            "holdings": "保有証券",
            "order status": "注文一覧",
            "chart": (
                "個別チャート"
                r"\\s.*\\((${Market Data:securities_code_regex})\\).*"
            ),
            "markets": "マーケット",
            "rankings": "ランキング",
            "stock lists": "銘柄一覧",
            "account": "口座情報",
            "news": "ニュース",
            "trading": "取引ポップアップ",
            "notifications": "通知設定",
            "full order book": (
                "全板" r"\\s.*\\((${Market Data:securities_code_regex})\\)"
            ),
        }
        config[trade.process] = {
            "start_time": "${Market Data:opening_time}",
            "end_time": "${Market Data:closing_time}",
            "executable": trade.executable,
            "title": title,
            "interactive_windows": (
                file_description,
                "${HYPERSBI2 Window Titles:announcements}",
                "${HYPERSBI2 Window Titles:summary}",
                "${HYPERSBI2 Window Titles:watchlists}",
                "${HYPERSBI2 Window Titles:holdings}",
                "${HYPERSBI2 Window Titles:order status}",
                "${HYPERSBI2 Window Titles:chart}",
                "${HYPERSBI2 Window Titles:markets}",
                "${HYPERSBI2 Window Titles:rankings}",
                "${HYPERSBI2 Window Titles:stock lists}",
                "${HYPERSBI2 Window Titles:account}",
                "${HYPERSBI2 Window Titles:news}",
                "${HYPERSBI2 Window Titles:trading}",
                "${HYPERSBI2 Window Titles:notifications}",
                "${HYPERSBI2 Window Titles:full order book}",
                r"${title}\s.*",
            ),
            "input_map": {
                "left": "",
                "middle": "show_hide_watchlists",
                "right": "",
                "x1": "",
                "x2": "",
                "f1": "",
                "f2": "",
                "f3": "",
                "f4": "",
                "f5": "show_hide_watchlists",
                "f6": "",
                "f7": "",
                "f8": "",
                "f9": "",
                "f10": "",
                "f11": "",
                "f12": "",
            },
            "utilization_ratio": "1.0",
            "daily_loss_limit_ratio": "-0.01",
            "maximum_daily_number_of_trades": "0",
            "image_magnification": "2",
            "binarization_threshold": "128",
            "is_dark_theme": "True",
            "screencast_directory": os.path.join(
                os.path.expanduser("~"), "Videos", trade.process.title()
            ),
            "screencast_regex": (
                trade.process.title()
                + r" \d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}\.\d{2}\.\d+\.mp4"
            ),
        }
        config[trade.widgets_section] = {
            "is_clock_label_enabled": "False",
            "clock_label_position": "nw",
            "clock_label_font_size": "12",
            "status_bar_frame_position": "sw",
            "status_bar_frame_font_size": "17",
            "message_font_size": "14",
        }
        config[trade.startup_script_section] = {
            "pre_start_options": "",
            "post_start_options": "-rl",
            "running_options": "-l",
        }
        config[trade.actions_section]["show_hide_watchlists"] = str(
            [("show_hide_window", "${HYPERSBI2 Window Titles:watchlists}")]
        )

    if can_override:
        configuration.read_config(config, trade.config_path, is_encrypted=True)

    current_date = date.today()
    if (
        date.fromisoformat(config[trade.variables_section]["current_date"])
        != current_date
    ):
        config[trade.variables_section]["current_date"] = str(current_date)
        config[trade.variables_section]["initial_cash_balance"] = "0"
        config[trade.variables_section]["current_number_of_trades"] = "0"

    if trade.process == "HYPERSBI2":
        theme_config = configparser.ConfigParser(interpolation=None)
        theme_config.read(
            os.path.join(
                os.path.expandvars("%APPDATA%"),
                trade.vendor,
                trade.process,
                "theme.ini",
            )
        )
        if (
            theme_config.has_option("General", "theme")
            and theme_config["General"]["theme"] == "Light"
        ):
            config[trade.process]["is_dark_theme"] = "False"

    return config


def configure_exit(args, trade):
    """Configure parameters based on command-line arguments and exit."""
    config = configure(trade, can_interpolate=False)
    backup_parameters = {"number_of_backups": 8}
    trade.instruction_items["preset_additional_values"] = (
        configuration.list_section(config, trade.actions_section)
    )

    if any((args.S, args.L, args.CB, args.U, args.PL, args.DLL, args.MDN)):
        for argument, (
            section,
            option,
            can_insert_delete,
            prompts,
            all_values,
            limits,
        ) in {
            "L": (
                trade.process,
                "input_map",
                False,
                {"value": "action"},
                trade.instruction_items.get("preset_additional_values"),
                (),
            ),
            "S": (
                trade.schedules_section,
                None,
                True,
                {
                    "key": "schedule",
                    "values": ("trigger", "action"),
                    "end_of_list": "end of schedules",
                },
                (
                    trade.instruction_items.get("preset_values"),
                    trade.instruction_items.get("preset_additional_values"),
                ),
                (),
            ),
            "CB": (
                trade.geometries_section,
                "cash_balance_region",
                False,
                {"value": "x, y, width, height, index"},
                None,
                (),
            ),
            "U": (
                trade.process,
                "utilization_ratio",
                False,
                None,
                None,
                (RATIO_EPSILON, 1.0),
            ),
            "PL": (
                trade.geometries_section,
                "price_limit_region",
                False,
                {"value": "x, y, width, height, index"},
                None,
                (),
            ),
            "DLL": (
                trade.process,
                "daily_loss_limit_ratio",
                False,
                None,
                None,
                (-1.0, -RATIO_EPSILON),
            ),
            "MDN": (
                trade.process,
                "maximum_daily_number_of_trades",
                False,
                None,
                None,
                (0, sys.maxsize),
            ),
        }.items():
            if getattr(args, argument):
                configuration.modify_section(
                    config,
                    section,
                    trade.config_path,
                    backup_parameters=backup_parameters,
                    can_insert_delete=can_insert_delete,
                    option=option,
                    prompts=prompts,
                    all_values=all_values,
                    limits=limits,
                    is_encrypted=True,
                )
                break

        sys.exit()
    if args.SS and configuration.modify_section(
        config,
        trade.startup_script_section,
        trade.config_path,
        backup_parameters=backup_parameters,
        is_encrypted=True,
    ):
        configuration.write_config(
            config, trade.config_path, is_encrypted=True
        )
        config = configure(trade)
        create_startup_script(trade, config)
        powershell = file_utilities.select_executable(
            ["pwsh.exe", "powershell.exe"]
        )
        if powershell:
            file_utilities.create_shortcut(
                trade.startup_script_base,
                powershell,
                f'-WindowStyle Hidden -File "{trade.startup_script}"',
                program_group_base=config[trade.process]["title"],
                icon_location=file_utilities.create_icon(
                    trade.startup_script_base,
                    icon_directory=trade.resource_directory,
                ),
            )

        sys.exit()
    if args.A:
        items = (
            option
            for option, value in config[trade.geometries_section].items()
            if _is_xy(value)
        )
        trade.instruction_items["preset_geometries"] = [
            f"${{HYPERSBI2 Geometries:{option}}}" for option in sorted(items)
        ]
        if configuration.modify_option(
            config,
            trade.actions_section,
            args.A[0],
            trade.config_path,
            backup_parameters=backup_parameters,
            can_insert_delete=True,
            initial_value="[()]",
            prompts={
                "key": "command",
                "value": "argument",
                "additional_value": "additional argument",
                "preset_additional_value": "action",
                "end_of_list": "end of commands",
            },
            items=trade.instruction_items,
            is_encrypted=True,
        ):
            powershell = file_utilities.select_executable(
                ["pwsh.exe", "powershell.exe"]
            )
            activate_path, interpreter = file_utilities.select_venv(
                os.path.dirname(__file__), activate="Activate.ps1"
            )

            # To pin the shortcut to the Taskbar, specify an executable
            # file as the 'target_path' argument.
            file_utilities.create_shortcut(
                args.A[0],
                powershell if powershell else "py.exe",
                (
                    f'-Command ". {activate_path};'
                    f' {interpreter} {__file__} -a {args.A[0]}"'
                    if activate_path
                    else f"{__file__} -a {args.A[0]}"
                ),
                program_group_base=config[trade.process]["title"],
                icon_location=file_utilities.create_icon(
                    args.A[0], icon_directory=trade.resource_directory
                ),
            )
        else:
            file_utilities.delete_shortcut(
                args.A[0],
                program_group_base=config[trade.process]["title"],
                icon_location=os.path.join(
                    trade.resource_directory, args.A[0] + ".ico"
                ),
            )

        create_completion(trade, config)
        sys.exit()
    if args.D:
        base = args.D[0]
        if base == trade.script_base:
            base = trade.startup_script_base
            if os.path.isfile(trade.startup_script):
                try:
                    os.remove(trade.startup_script)
                except OSError as e:
                    print(e)
        else:
            configuration.delete_option(
                config,
                trade.actions_section,
                base,
                trade.config_path,
                backup_parameters=backup_parameters,
                is_encrypted=True,
            )
            create_completion(trade, config)

        file_utilities.delete_shortcut(
            base,
            program_group_base=config[trade.process]["title"],
            icon_location=os.path.join(
                trade.resource_directory, f"{base}.ico"
            ),
        )
        sys.exit()
    if args.C:
        configuration.check_config_changes(
            configure(trade, can_interpolate=False, can_override=False),
            trade.config_path,
            excluded_sections=(
                trade.geometries_section,
                trade.variables_section,
            ),
            user_option_ignored_sections=(trade.actions_section,),
            backup_parameters=backup_parameters,
            is_encrypted=True,
        )
        sys.exit()


# Core Predicates


def _is_xy(value):
    """Return True if the value represents exactly two integers (X, Y)."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return False
    try:
        int(parts[0])
        int(parts[1])
        return True
    except ValueError:
        return False


def is_trading_day(date, market_holidays, date_format):
    """Check if the given date is a trading day."""
    return date.weekday() < 5 and date.strftime(date_format) not in set(
        pd.read_csv(market_holidays, header=None, dtype=str)[0]
    )


# Data Creation and Persistence


def create_completion(trade, config):
    """Generate completion scripts for options and values."""
    options = ("-a", "-A", "-D")
    trade.instruction_items["preset_additional_values"] = (
        configuration.list_section(config, trade.actions_section)
    )

    file_utilities.create_powershell_completion(
        trade.script_base,
        options,
        trade.instruction_items.get("preset_additional_values"),
        ("py", "python"),
        os.path.join(trade.resource_directory, "completion.ps1"),
    )
    file_utilities.create_bash_completion(
        trade.script_base,
        options,
        trade.instruction_items.get("preset_additional_values"),
        ("py.exe", "python.exe"),
        os.path.join(trade.resource_directory, "completion.sh"),
    )


def save_customer_margin_ratios(trade, config):
    """Save customer margin ratios for a given trade."""
    configuration.ensure_section_exists(
        config, trade.customer_margin_ratios_section
    )

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
            print(e)
            sys.exit(1)

        df = None
        headers = configuration.evaluate_value(section["headers"])
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
    return market_data.split_rankings_by_digit(
        rankings=rankings,
        closing_prices_prefix=trade.closing_prices,
        code_regex=SECURITIES_CODE_REGEX,
    )


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
    app_scheduler.start_scheduler(
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
    app_listeners.start_listeners(
        trade,
        config,
        gui_state,
        base_manager,
        _get_listener_dependencies(),
        is_persistent=is_persistent,
    )


def _start_speaking_process(trade, config):
    """Start a speaking process using the configured voice settings."""
    return app_listeners.start_speaking_process(
        trade, config, speech_synthesis
    )


# Action Execution Pipeline


def start_execute_action_thread(trade, config, gui_state, action):
    """Start a new thread to execute a specified action."""
    app_actions.start_execute_action_thread(
        trade,
        config,
        gui_state,
        action,
        _get_action_dependencies(),
    )


def execute_action(trade, config, gui_state, action, should_initialize=True):
    """Execute a sequence of commands for a trade."""
    return app_actions.execute_action(
        trade,
        config,
        gui_state,
        action,
        _get_action_dependencies(),
        should_initialize=should_initialize,
    )


def _get_action_dependencies():
    """Return runtime dependencies required by the action executor."""
    return {
        "calculate_share_size_fn": calculate_share_size,
        "configuration": configuration,
        "data_utilities": data_utilities,
        "file_utilities": file_utilities,
        "gui_interactions": gui_interactions,
        "indicator_thread_cls": IndicatorThread,
        "is_trading_day_fn": is_trading_day,
        "keyboard": keyboard,
        "message_thread_cls": MessageThread,
        "pd": pd,
        "psutil": psutil,
        "pyautogui": pyautogui,
        "save_market_data_fn": save_market_data,
        "text_recognition": text_recognition,
        "win32clipboard": win32clipboard,
    }


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
        "configuration": configuration,
        "execute_action_fn": execute_action,
        "process_utilities": process_utilities,
        "speech_synthesis": speech_synthesis,
        "start_speaking_process_fn": _start_speaking_process,
    }


def _get_runtime_dependencies():
    """Return runtime dependencies required by the app runtime."""
    return {
        "atexit": atexit,
        "base_manager_cls": BaseManager,
        "configuration": configuration,
        "execute_action_fn": execute_action,
        "process_utilities": process_utilities,
        "save_customer_margin_ratios_fn": save_customer_margin_ratios,
        "speech_synthesis": speech_synthesis,
        "start_listeners_fn": start_listeners,
        "start_scheduler_fn": start_scheduler,
        "threading": threading,
    }


# Startup Automation


def create_startup_script(trade, config):
    """Create a startup script for a trade."""
    app_startup_script.create_startup_script(
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
        except OSError as e:
            print(e)

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
    except OSError as e:
        print(e)

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
    except configuration.ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
