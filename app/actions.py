"""Configured action execution for trading assistant workflows."""

import csv
import math
import os
import threading
import time

from pynput import keyboard
import pandas as pd
import psutil
import pyautogui
import win32clipboard

from app import market_data, trade_service, ui
from core_utilities import data_utilities, errors, file_utilities
from core_utilities.config_io import write_config
from core_utilities.config_validation import evaluate_value
from interaction_utilities import gui_interactions, text_recognition

SANS_INITIAL_SECURITIES_CODE_REGEX = (
    r"[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?"
)
SECURITIES_CODE_REGEX = "[1-9]" + SANS_INITIAL_SECURITIES_CODE_REGEX
SAVE_MARKET_DATA_ERROR = "Unable to save market data."


def start_execute_action_thread(trade, config, gui_state, action):
    """Start a new thread to execute a specified action."""
    execute_action_thread = threading.Thread(
        target=execute_action,
        args=(
            trade,
            config,
            gui_state,
            config[trade.actions_section][action],
        ),
        kwargs={"action_path": (action,)},
    )
    execute_action_thread.start()


def execute_action(
    trade,
    config,
    gui_state,
    action,
    should_initialize=True,
    action_path=None,
):
    """Execute a sequence of commands for a trade."""
    if should_initialize:
        trade.initialize_attributes()
        gui_state.initialize_attributes()

    action_path = tuple(action_path or ("inline action",))
    if isinstance(action, str):
        action = evaluate_value(action)

    for instruction_index, instruction in enumerate(action, start=1):
        command = instruction[0]
        if command not in ALL_KEYS:
            _raise_unknown_command_error(
                action_path,
                instruction_index,
                command,
            )
        if not _execute_instruction(
            trade,
            config,
            gui_state,
            instruction,
            action_path,
            instruction_index,
        ):
            return False

    return True


def _raise_unknown_command_error(action_path, instruction_index, command):
    """Raise a contextual error for an unknown action command."""
    raise errors.ActionExecutionError(
        (
            "Action path "
            f"'{_format_action_path(action_path)}' failed at "
            f"instruction {instruction_index} ({command}): "
            "unknown command."
        ),
        action_path=action_path,
        instruction_index=instruction_index,
        command=command,
    )


def _format_action_path(action_path):
    """Return a readable representation of nested action context."""
    return " -> ".join(action_path)


def _execute_instruction(
    trade,
    config,
    gui_state,
    instruction,
    action_path,
    instruction_index,
):
    """Execute a single instruction."""
    command, argument, additional_argument = _unpack_instruction(instruction)
    handler = _COMMAND_DISPATCH[command]

    if handler is _handle_gui_command:
        return handler(
            trade,
            gui_state,
            command,
            argument,
            additional_argument,
        )
    if handler is _handle_window_command:
        return handler(trade, config, command, argument, additional_argument)
    if handler is _handle_wait_command:
        return handler(
            trade,
            config,
            gui_state,
            command,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        )
    if handler is _handle_speak_command:
        return handler(trade, config, command, argument, additional_argument)
    if handler is _handle_market_data_command:
        return handler(trade, config, command, argument)
    if handler is _handle_trade_state_command:
        return handler(trade, config, command, argument, additional_argument)
    if handler is _handle_control_flow_command:
        return handler(
            trade,
            config,
            gui_state,
            command,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        )
    if handler is _handle_execution_command:
        return handler(
            trade,
            config,
            gui_state,
            argument,
            action_path,
            instruction_index,
        )
    return True


def _unpack_instruction(instruction):
    """Extract command name and up to two arguments from an instruction."""
    return (
        instruction[0],
        instruction[1] if len(instruction) > 1 else None,
        instruction[2] if len(instruction) > 2 else None,
    )


def _handle_gui_command(
    trade,
    gui_state,
    command,
    argument,
    additional_argument,
):
    """Handle GUI interaction commands."""
    if command == "back_to":
        pyautogui.moveTo(gui_state.previous_position)
    elif command == "click":
        (pyautogui.rightClick if gui_state.swapped else pyautogui.click)(
            *map(int, argument.split(","))
        )
    elif command == "click_widget":
        gui_interactions.click_widget(
            gui_state,
            os.path.join(trade.resource_directory, argument),
            *map(int, additional_argument.split(",")),
        )
    elif command == "drag_to":
        pyautogui.dragTo(*map(int, argument.split(",")))
    elif command == "move_to":
        pyautogui.moveTo(*map(int, argument.split(",")))
    elif command == "press_hotkeys":
        pyautogui.hotkey(*tuple(map(str.strip, argument.split(","))))
    elif command == "press_key":
        argument = tuple(map(str.strip, argument.split(",")))
        presses = int(argument[1]) if len(argument) > 1 else 1
        pyautogui.press(argument[0], presses=presses)
    elif command == "right_click":
        pyautogui.click(
            *map(int, argument.split(",")),
            button="left" if gui_state.swapped else "right",
        )
    elif command == "write_string":
        pyautogui.write(argument)

    return True


def _handle_window_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
):
    """Handle window and indicator visibility commands."""
    if command == "hide_window":
        gui_interactions.enumerate_windows(
            gui_interactions.hide_window, argument
        )
    elif command == "show_hide_indicator":
        if trade.indicator_thread:
            trade.indicator_thread.stop()
            trade.indicator_thread = None
        elif trade.widgets_section in config:
            trade.indicator_thread = ui.IndicatorThread(trade, config)
            trade.indicator_thread.start()
        else:
            return False
    elif command == "show_hide_window":
        gui_interactions.enumerate_windows(
            gui_interactions.show_hide_window, argument
        )
    elif command == "show_window":
        gui_interactions._show_window_state["count"] = 0
        gui_interactions._show_window_state["max_count"] = int(
            additional_argument or 1
        )
        gui_interactions.enumerate_windows(
            gui_interactions.show_window, argument
        )

    return True


def _handle_wait_command(
    trade,
    config,
    gui_state,
    command,
    argument,
    additional_argument,
    action_path,
    instruction_index,
):
    """Handle blocking and wait-related commands."""
    if command == "sleep":
        time.sleep(float(argument))
    elif command == "wait_for_key":
        if not _wait_for_key(
            trade,
            config,
            gui_state,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        ):
            return False
    elif command == "wait_for_key_count_down":
        if not _wait_for_key(
            trade,
            config,
            gui_state,
            argument,
            additional_argument,
            should_count_down=True,
            action_path=action_path,
            instruction_index=instruction_index,
        ):
            return False
    elif command == "wait_for_price":
        trade.keyboard_listener_state = 1
        trade.key_to_check = None
        trade.should_continue = True
        text_recognition.recognize_text(
            *map(int, argument.split(",")),
            int(config[trade.process]["image_magnification"]),
            int(config[trade.process]["binarization_threshold"]),
            config[trade.process].getboolean("is_dark_theme"),
            should_continue_reference=lambda: trade.should_continue,
        )
        trade.keyboard_listener_state = 0
        if not trade.should_continue and _handle_cancellation_exit(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        ):
            return False
    elif command == "wait_for_window":
        trade.keyboard_listener_state = 1
        trade.key_to_check = None
        trade.should_continue = True
        gui_interactions.wait_for_window(
            argument,
            should_continue_reference=lambda: trade.should_continue,
        )
        trade.keyboard_listener_state = 0
        if not trade.should_continue and _handle_cancellation_exit(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        ):
            return False

    return True


def _handle_speak_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
):
    """Handle speech and user notification commands."""
    if command == "speak_config":
        trade.speech_manager.set_speech_text(
            config[argument][additional_argument]
        )
    elif command == "speak_cpu_utilization":
        trade.speech_manager.set_speech_text(
            f"{round(psutil.cpu_percent(interval=float(argument)))}%."
        )
    elif command == "speak_minutes_since_hour":
        if argument:
            target_time = data_utilities.get_target_time(argument)
        else:
            now = pd.Timestamp.now()
            target_time = time.mktime(
                time.strptime(
                    f"{now.strftime('%Y-%m-%d')} {now.hour}:00:00",
                    "%Y-%m-%d %H:%M:%S",
                )
            )
        now = time.time()
        minutes_since = int((now - target_time) // 60)
        if int(now % 60) >= 30:
            minutes_since += 1
        if minutes_since == 1:
            trade.speech_manager.set_speech_text("1 minute.")
        else:
            trade.speech_manager.set_speech_text(f"{minutes_since} minutes.")
    elif command == "speak_seconds_since_time":
        seconds_since = math.floor(
            time.time() - data_utilities.get_target_time(argument)
        )
        trade.speech_manager.set_speech_text(f"{seconds_since} seconds.")
    elif command == "speak_seconds_until_time":
        seconds_until = math.ceil(
            data_utilities.get_target_time(argument) - time.time()
        )
        trade.speech_manager.set_speech_text(f"{seconds_until} seconds.")
    elif command == "speak_show_text":
        trade.speech_manager.set_speech_text(argument)
        ui.MessageThread(trade, config, argument).start()
    elif command == "speak_text":
        trade.speech_manager.set_speech_text(argument)

    return True


def _handle_market_data_command(trade, config, command, argument):
    """Handle market data retrieval and persistence commands."""
    if command == "copy_symbols_from_column":
        _copy_symbols_from_column(trade, config, argument)
    elif command == "save_market_data":
        is_successful, text = save_market_data(trade, config)
        if not is_successful:
            trade.speech_manager.set_speech_text(text)
            return False

    return True


def _copy_symbols_from_column(trade, config, argument):
    """Recognize symbols from a column region and copy them to clipboard."""
    is_clipboard_open = False
    try:
        win32clipboard.OpenClipboard()
        is_clipboard_open = True
        win32clipboard.EmptyClipboard()
        symbols = text_recognition.recognize_text(
            *map(int, argument.split(",")),
            None,
            int(config[trade.process]["image_magnification"]),
            int(config[trade.process]["binarization_threshold"]),
            config[trade.process].getboolean("is_dark_theme"),
            text_type="securities_code_column",
        )
        win32clipboard.SetClipboardText(" ".join(symbols))
    finally:
        if is_clipboard_open:
            win32clipboard.CloseClipboard()


def _handle_trade_state_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
):
    """Handle trade state and accounting commands."""
    if command == "calculate_share_size":
        is_successful, text = calculate_share_size(trade, config, argument)
        if not is_successful and text:
            trade.speech_manager.set_speech_text(text)
            return False
    elif command == "check_daily_loss_limit":
        daily_loss_limit = (
            trade.cash_balance
            * float(config[trade.process]["utilization_ratio"])
            * float(config[trade.process]["daily_loss_limit_ratio"])
        )
        initial_cash_balance = int(
            config[trade.variables_section]["initial_cash_balance"]
        )
        if initial_cash_balance == 0:
            config[trade.variables_section]["initial_cash_balance"] = str(
                trade.cash_balance
            )
            write_config(config, trade.config_path, is_encrypted=True)
        else:
            daily_profit = trade.cash_balance - initial_cash_balance
            if daily_profit < daily_loss_limit:
                trade.speech_manager.set_speech_text(argument)
                return False
    elif command == "check_maximum_daily_number_of_trades":
        if (
            0
            < int(config[trade.process]["maximum_daily_number_of_trades"])
            <= int(config[trade.variables_section]["current_number_of_trades"])
        ):
            trade.speech_manager.set_speech_text(argument)
            return False
    elif command == "count_trades":
        current_number_of_trades = (
            int(config[trade.variables_section]["current_number_of_trades"])
            + 1
        )
        config[trade.variables_section]["current_number_of_trades"] = str(
            current_number_of_trades
        )
        write_config(config, trade.config_path, is_encrypted=True)
        file_utilities.write_chapter(
            file_utilities.get_latest_file(
                config[trade.process]["screencast_directory"],
                config[trade.process]["screencast_regex"],
            ),
            (
                f"Trade {current_number_of_trades}"
                f"{f' for {trade.symbol}' if trade.symbol else ''}"
                f" at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            previous_title="Pre-trading",
            offset=argument,
        )
    elif command == "get_cash_balance":
        trade.cash_balance = int(
            text_recognition.recognize_text(
                *map(
                    int,
                    config[trade.geometries_section][
                        "cash_balance_region"
                    ].split(","),
                ),
                int(config[trade.process]["image_magnification"]),
                int(config[trade.process]["binarization_threshold"]),
                config[trade.process].getboolean("is_dark_theme"),
            )
        )
    elif command == "get_symbol":
        gui_interactions.enumerate_windows(trade.get_symbol, argument)
    elif command == "write_chapter":
        file_utilities.write_chapter(
            file_utilities.get_latest_file(
                config[trade.process]["screencast_directory"],
                config[trade.process]["screencast_regex"],
            ),
            argument,
            previous_title=additional_argument,
        )
    elif command == "write_share_size":
        pyautogui.write(str(trade.share_size))

    return True


def _handle_control_flow_command(
    trade,
    config,
    gui_state,
    command,
    argument,
    additional_argument,
    action_path,
    instruction_index,
):
    """Handle conditional control-flow commands."""
    if command == "is_now_after":
        if data_utilities.get_target_time(
            argument
        ) < time.time() and not _recursively_execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        ):
            return False
    elif command == "is_now_before":
        if time.time() < data_utilities.get_target_time(
            argument
        ) and not _recursively_execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        ):
            return False
    elif command == "is_recording":
        if file_utilities.is_writing(
            file_utilities.get_latest_file(
                config[trade.process]["screencast_directory"],
                config[trade.process]["screencast_regex"],
            )
        ) == bool(
            argument.lower() == "true"
        ) and not _recursively_execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        ):
            return False
    elif command == "is_trading_day":
        if is_trading_day(
            pd.Timestamp.now(tz=config["Market Data"]["timezone"]),
            trade.market_holidays,
            config["Market Holidays"]["date_format"],
        ) == bool(argument.lower() == "true") and not (
            _recursively_execute_action(
                trade,
                config,
                gui_state,
                additional_argument,
                action_path,
                instruction_index,
            )
        ):
            return False

    return True


def _handle_execution_command(
    trade,
    config,
    gui_state,
    argument,
    action_path,
    instruction_index,
):
    """Handle execution and delegation commands."""
    if not _recursively_execute_action(
        trade,
        config,
        gui_state,
        argument,
        action_path,
        instruction_index,
    ):
        return False

    return True


def _recursively_execute_action(
    trade,
    config,
    gui_state,
    additional_argument,
    action_path,
    instruction_index,
):
    """Recursively execute an action if it is a list or a string."""
    if isinstance(additional_argument, list):
        return execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            should_initialize=False,
            action_path=(*action_path, f"inline@{instruction_index}"),
        )
    if isinstance(additional_argument, str):
        return execute_action(
            trade,
            config,
            gui_state,
            config[trade.actions_section][additional_argument],
            should_initialize=False,
            action_path=(*action_path, additional_argument),
        )

    return False


def _wait_for_key(
    trade,
    config,
    gui_state,
    argument,
    additional_argument,
    should_count_down=False,
    action_path=None,
    instruction_index=None,
):
    """Wait for a key press with optional countdown."""
    trade.keyboard_listener_state = 1
    trade.key_to_check = (
        argument if len(argument) == 1 else keyboard.Key[argument]
    )
    countdown_seconds = [
        int(seconds.strip())
        for seconds in config["General"][
            "countdown_seconds_before_candle_close"
        ].split(",")
    ]
    announced_minutes = {seconds: -1 for seconds in countdown_seconds}

    while trade.keyboard_listener_state == 1:
        if should_count_down:
            now = pd.Timestamp.now()
            current_second = now.second
            current_minute = now.minute

            for seconds in countdown_seconds:
                if (
                    current_second == 60 - seconds
                    and current_minute != announced_minutes[seconds]
                ):
                    trade.speech_manager.set_speech_text(f"{seconds} seconds.")
                    announced_minutes[seconds] = current_minute

        time.sleep(0.01)

    if not trade.should_continue and _handle_cancellation_exit(
        trade,
        config,
        gui_state,
        additional_argument,
        action_path,
        instruction_index,
    ):
        return False
    return True


def _handle_cancellation_exit(
    trade,
    config,
    gui_state,
    additional_argument,
    action_path,
    instruction_index,
):
    """Perform cancellation actions and signal caller to exit."""
    if additional_argument:
        _recursively_execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        )

    trade.speech_manager.set_speech_text("Canceled.")
    return True


_COMMAND_DISPATCH = {
    # GUI interaction commands
    "back_to": _handle_gui_command,
    "click": _handle_gui_command,
    "click_widget": _handle_gui_command,
    "drag_to": _handle_gui_command,
    "move_to": _handle_gui_command,
    "press_hotkeys": _handle_gui_command,
    "press_key": _handle_gui_command,
    "right_click": _handle_gui_command,
    "write_string": _handle_gui_command,
    # Window and indicator visibility commands
    "hide_window": _handle_window_command,
    "show_hide_indicator": _handle_window_command,
    "show_hide_window": _handle_window_command,
    "show_window": _handle_window_command,
    # Blocking and wait-related commands
    "sleep": _handle_wait_command,
    "wait_for_key": _handle_wait_command,
    "wait_for_key_count_down": _handle_wait_command,
    "wait_for_price": _handle_wait_command,
    "wait_for_window": _handle_wait_command,
    # Speech and user notification commands
    "speak_config": _handle_speak_command,
    "speak_cpu_utilization": _handle_speak_command,
    "speak_minutes_since_hour": _handle_speak_command,
    "speak_seconds_since_time": _handle_speak_command,
    "speak_seconds_until_time": _handle_speak_command,
    "speak_show_text": _handle_speak_command,
    "speak_text": _handle_speak_command,
    # Market data retrieval and persistence commands
    "copy_symbols_from_column": _handle_market_data_command,
    "save_market_data": _handle_market_data_command,
    # Trade state and accounting commands
    "calculate_share_size": _handle_trade_state_command,
    "check_daily_loss_limit": _handle_trade_state_command,
    "check_maximum_daily_number_of_trades": _handle_trade_state_command,
    "count_trades": _handle_trade_state_command,
    "get_cash_balance": _handle_trade_state_command,
    "get_symbol": _handle_trade_state_command,
    "write_chapter": _handle_trade_state_command,
    "write_share_size": _handle_trade_state_command,
    # Conditional control-flow commands
    "is_now_after": _handle_control_flow_command,
    "is_now_before": _handle_control_flow_command,
    "is_recording": _handle_control_flow_command,
    "is_trading_day": _handle_control_flow_command,
    # Execution and delegation commands
    "execute_action": _handle_execution_command,
}
ALL_KEYS = tuple(sorted(_COMMAND_DISPATCH))


def is_trading_day(date, market_holidays, date_format):
    """Check if the given date is a trading day."""
    return date.weekday() < 5 and date.strftime(date_format) not in set(
        pd.read_csv(market_holidays, header=None, dtype=str)[0]
    )


def save_market_data(trade, config):
    """Split the rankings CSV by the first digit of the securities code."""
    rankings = config["Market Data"]["rankings"].replace("\\\\", "\\")
    try:
        market_data.split_rankings_by_digit(
            rankings=rankings,
            closing_prices_prefix=trade.closing_prices,
            code_regex=SECURITIES_CODE_REGEX,
        )
        return (True, None)
    except errors.MarketDataError as e:
        return (False, f"{SAVE_MARKET_DATA_ERROR} {e}")


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
            f"{trade.closing_prices}{trade.symbol[0]}.csv",
            encoding="utf-8",
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
        return trade_service.calculate_price_limit_from_closing_price(
            closing_price
        )

    return text_recognition.recognize_text(
        *map(
            int,
            config[trade.geometries_section]["price_limit_region"].split(","),
        ),
        int(config[trade.process]["image_magnification"]),
        int(config[trade.process]["binarization_threshold"]),
        config[trade.process].getboolean("is_dark_theme"),
        text_type="decimal_numbers",
    )
