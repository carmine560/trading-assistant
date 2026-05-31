"""Configured action execution for trading assistant workflows."""

import csv
import math
import os
import re
import threading
import time

import pandas as pd
import psutil
import pyautogui
import win32clipboard
from pynput import keyboard

from app import (
    action_errors,
    customer_margin_ratios,
    listeners,
    notifications,
    trade_service,
    ui,
)
from core_utilities import data_utilities, errors, file_utilities
from core_utilities.config_io import write_config
from core_utilities.config_validation import evaluate_value
from interaction_utilities import gui_interactions, text_recognition

ARCHIVE_MARKET_DATA_ERROR = "Unable to archive market data."
CUSTOMER_MARGIN_RATIOS_FILE_ERROR = (
    "Unable to read customer margin ratios file"
)
CUSTOMER_MARGIN_RATIOS_FRESHNESS_CACHE_SECONDS = 30 * 60
MARKET_DATA_FILE_ERROR = "Unable to read market data file"
PRICE_LIMIT_ERROR = "Unable to get price limit."
PRICE_LIMIT_MARKET_DATA_FILE_ERROR = "Closing prices file invalid."
SHARE_SIZE_ERROR = "Unable to calculate share size."
UI_THREAD_STARTUP_TIMEOUT_SECONDS = 1
UI_THREAD_STOP_TIMEOUT_SECONDS = 1


def start_execute_action_thread(trade, config, gui_state, action):
    """Start a new thread to execute a specified action."""
    try:
        configured_action = config[trade.actions_section][action]
    except KeyError as e:
        raise action_errors.ActionLookupError(
            f"Action '{action}' is not defined.",
            action_name=action,
        ) from e

    execute_action_thread = threading.Thread(
        target=_execute_action_thread,
        args=(
            trade,
            config,
            gui_state,
            configured_action,
            action,
        ),
    )
    execute_action_thread.start()
    return execute_action_thread


def _execute_action_thread(trade, config, gui_state, action, action_name):
    """Execute one listener-triggered action and report thread failures."""
    try:
        execute_action(
            trade,
            config,
            gui_state,
            action,
            action_path=(action_name,),
        )
    except errors.CoreUtilitiesError as e:
        trade.last_action_error = e
        notifications.set_speech_text(trade, "Action failed.")
    except Exception as e:
        trade.last_action_error = e
        notifications.set_speech_text(
            trade,
            "Action failed unexpectedly.",
        )


def execute_action(
    trade,
    config,
    gui_state,
    action,
    should_initialize=True,
    is_top_level_action=True,
    action_path=None,
):
    """Execute a sequence of commands for a trade."""
    action_path = tuple(action_path or ("inline action",))
    lock_acquired = False
    if is_top_level_action:
        if not trade.action_lock.acquire(blocking=False):
            action_name = action_path[0]
            trade.last_action_error = action_errors.ActionConcurrencyError(
                (
                    f"Action '{action_name}' skipped because another action "
                    "is running."
                ),
                action_name=action_name,
            )
            notifications.set_speech_text(trade, "Action busy.")
            return False
        lock_acquired = True
        trade.last_action_error = None
        trade.last_action_warning = None
        trade.last_action_canceled = False

    try:
        action = _evaluate_action(action, action_path)
        _preflight_action(trade, config, action, action_path)

        if should_initialize:
            trade.initialize_attributes()
            trade.has_cash_balance = False
            gui_state.initialize_attributes()

        for instruction_index, instruction in enumerate(action, start=1):
            listeners.raise_listener_monitor_error(trade)
            command, argument, additional_argument = _unpack_instruction(
                instruction,
                action_path,
                instruction_index,
            )
            if command not in ALL_KEYS:
                _raise_unknown_command_error(
                    action_path,
                    instruction_index,
                    command,
                )
            argument, additional_argument = _normalize_instruction_arguments(
                command,
                argument,
                additional_argument,
                action_path,
                instruction_index,
            )
            if not _execute_instruction(
                trade,
                config,
                gui_state,
                command,
                argument,
                additional_argument,
                action_path,
                instruction_index,
            ):
                return False

        return True
    finally:
        if lock_acquired:
            trade.action_lock.release()


def _preflight_action(trade, config, action, action_path):
    """Validate configured action structure before executing side effects."""
    for instruction_index, instruction in enumerate(action, start=1):
        command, argument, additional_argument = _unpack_instruction(
            instruction,
            action_path,
            instruction_index,
        )
        if command not in ALL_KEYS:
            _raise_unknown_command_error(
                action_path,
                instruction_index,
                command,
            )
        argument, additional_argument = _normalize_instruction_arguments(
            command,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        )

        if command == "execute_action":
            nested_action = argument
            is_nested_action_required = True
        elif command in (
            "is_now_after",
            "is_now_before",
            "is_recording",
            "is_trading_day",
        ):
            nested_action = additional_argument
            is_nested_action_required = True
        elif command in (
            "wait_for_key",
            "wait_for_key_count_down",
            "wait_for_price",
            "wait_for_window",
        ):
            nested_action = additional_argument
            is_nested_action_required = False
        else:
            nested_action = None
            is_nested_action_required = False

        if nested_action is None:
            if is_nested_action_required:
                _raise_invalid_argument_error(
                    action_path,
                    instruction_index,
                    command,
                    "expected nested action list or action name",
                )
            else:
                continue

        if isinstance(nested_action, list):
            _preflight_action(
                trade,
                config,
                nested_action,
                (*action_path, f"inline@{instruction_index}"),
            )
            continue

        if not isinstance(nested_action, str):
            _raise_invalid_argument_error(
                action_path,
                instruction_index,
                command,
                "expected nested action list or action name",
            )

        # A nested action must not appear in its ancestry, or the action graph
        # would cycle (for example, A -> B -> A).
        if nested_action in action_path:
            raise action_errors.ActionExecutionError(
                (
                    "Action path "
                    f"'{_format_action_path(action_path)}' failed at "
                    f"instruction {instruction_index} (execute_action): "
                    f"nested action '{nested_action}' creates a cycle."
                ),
                action_path=action_path,
                instruction_index=instruction_index,
                command="execute_action",
            )
        if nested_action not in config[trade.actions_section]:
            raise action_errors.ActionExecutionError(
                (
                    "Action path "
                    f"'{_format_action_path(action_path)}' failed at "
                    f"instruction {instruction_index} (execute_action): "
                    f"nested action '{nested_action}' is not defined."
                ),
                action_path=action_path,
                instruction_index=instruction_index,
                command="execute_action",
            )

        named_action_path = (*action_path, nested_action)
        named_action = _evaluate_action(
            config[trade.actions_section][nested_action],
            named_action_path,
        )

        _preflight_action(
            trade,
            config,
            named_action,
            named_action_path,
        )


def _evaluate_action(action, action_path):
    """Evaluate and validate one configured action."""
    if isinstance(action, str):
        action = evaluate_value(action)

    if not isinstance(action, list):
        raise action_errors.ActionExecutionError(
            (
                "Action path "
                f"'{_format_action_path(action_path)}' failed: "
                f"malformed action {action!r}."
            ),
            action_path=action_path,
            instruction_index=None,
            command=None,
        )

    return action


def _unpack_instruction(instruction, action_path, instruction_index):
    """Validate and unpack one action instruction."""
    command = None
    if not isinstance(instruction, (str, bytes)):
        try:
            command = instruction[0] if instruction else None
            instruction_length = len(instruction)
        except (IndexError, TypeError):
            instruction_length = None

    if command is None or instruction_length not in range(1, 4):
        raise action_errors.ActionExecutionError(
            (
                "Action path "
                f"'{_format_action_path(action_path)}' failed at "
                f"instruction {instruction_index}: "
                f"malformed instruction {instruction!r}."
            ),
            action_path=action_path,
            instruction_index=instruction_index,
            command=command,
        )

    return (
        command,
        instruction[1] if len(instruction) > 1 else None,
        instruction[2] if len(instruction) > 2 else None,
    )


def _raise_unknown_command_error(action_path, instruction_index, command):
    """Raise a contextual error for an unknown action command."""
    raise action_errors.ActionExecutionError(
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


def _raise_invalid_argument_error(
    action_path,
    instruction_index,
    command,
    details,
):
    """Raise a contextual error for malformed command arguments."""
    raise action_errors.ActionExecutionError(
        (
            "Action path "
            f"'{_format_action_path(action_path)}' failed at "
            f"instruction {instruction_index} ({command}): "
            f"invalid argument: {details}."
        ),
        action_path=action_path,
        instruction_index=instruction_index,
        command=command,
    )


def _parse_integer_tuple(
    value,
    expected_count,
    action_path,
    instruction_index,
    command,
):
    """Parse a comma-separated integer tuple for action geometry arguments."""
    try:
        parsed = tuple(int(part.strip()) for part in value.split(","))
    except (AttributeError, ValueError):
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            f"expected {expected_count} comma-separated integers",
        )
    if len(parsed) != expected_count:
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            f"expected {expected_count} comma-separated integers",
        )
    return parsed


def _normalize_point_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize one X, Y command argument."""
    argument = _parse_integer_tuple(
        argument,
        2,
        action_path,
        instruction_index,
        command,
    )
    return argument, additional_argument


def _normalize_click_widget_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize the click_widget image name and region arguments."""
    additional_argument = _parse_integer_tuple(
        additional_argument,
        4,
        action_path,
        instruction_index,
        command,
    )
    return argument, additional_argument


def _normalize_ocr_region_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize one X, Y, WIDTH, HEIGHT, INDEX OCR region argument."""
    argument = _parse_integer_tuple(
        argument,
        5,
        action_path,
        instruction_index,
        command,
    )
    return argument, additional_argument


def _normalize_ocr_column_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize one X, Y, WIDTH, HEIGHT OCR column argument."""
    argument = _parse_integer_tuple(
        argument,
        4,
        action_path,
        instruction_index,
        command,
    )
    return argument, additional_argument


def _normalize_press_key_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize press_key's KEY[, PRESSES] argument."""
    try:
        key_parts = tuple(part.strip() for part in argument.split(","))
    except AttributeError:
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            "expected KEY[, PRESSES]",
        )
    if not key_parts or not key_parts[0] or len(key_parts) > 2:
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            "expected KEY[, PRESSES]",
        )
    try:
        presses = int(key_parts[1]) if len(key_parts) > 1 else 1
    except ValueError:
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            "expected integer key press count",
        )
    return (key_parts[0], presses), additional_argument


def _normalize_float_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize one numeric command argument."""
    try:
        argument = float(argument)
    except (TypeError, ValueError):
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            "expected a number",
        )
    return argument, additional_argument


def _normalize_show_window_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize show_window's optional maximum window count."""
    try:
        additional_argument = int(additional_argument or 1)
    except (TypeError, ValueError):
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            "expected integer maximum window count",
        )
    return argument, additional_argument


def _normalize_wait_for_key_argument(
    argument,
    additional_argument,
    action_path,
    instruction_index,
    command,
):
    """Normalize wait_for_key's single character or special key argument."""
    try:
        argument = argument if len(argument) == 1 else keyboard.Key[argument]
    except (KeyError, TypeError):
        _raise_invalid_argument_error(
            action_path,
            instruction_index,
            command,
            "expected a single character or keyboard key name",
        )
    return argument, additional_argument


def _normalize_instruction_arguments(
    command,
    argument,
    additional_argument,
    action_path,
    instruction_index,
):
    """Validate and normalize action command arguments before side effects."""
    if command in ("is_recording", "is_trading_day"):
        try:
            argument = argument.lower()
        except AttributeError:
            _raise_invalid_argument_error(
                action_path,
                instruction_index,
                command,
                "expected true or false",
            )
        if argument not in ("true", "false"):
            _raise_invalid_argument_error(
                action_path,
                instruction_index,
                command,
                "expected true or false",
            )
        argument = argument == "true"

    normalizer = _ARGUMENT_NORMALIZERS.get(command)
    if normalizer is None:
        return argument, additional_argument
    return normalizer(
        argument,
        additional_argument,
        action_path,
        instruction_index,
        command,
    )


def _format_action_path(action_path):
    """Return a readable representation of nested action context."""
    return " -> ".join(action_path)


def _stop_ui_thread_after_startup_failure(
    thread,
    action_path,
    instruction_index,
    command,
):
    """Stop a failed UI thread and raise if it remains alive."""
    stop_thread = getattr(thread, "stop", None)
    if stop_thread:
        stop_thread()
    thread.join(timeout=UI_THREAD_STOP_TIMEOUT_SECONDS)
    if thread.is_alive():
        raise action_errors.ActionExecutionError(
            (
                "Action path "
                f"'{_format_action_path(action_path)}' failed at "
                f"instruction {instruction_index} ({command}): "
                "UI thread did not stop within "
                f"{UI_THREAD_STOP_TIMEOUT_SECONDS} seconds."
            ),
            action_path=action_path,
            instruction_index=instruction_index,
            command=command,
        )


def _start_ui_thread(thread, action_path, instruction_index, command):
    """Start a UI thread and raise contextual errors on startup failure."""
    thread.start()
    is_started = thread.startup_event.wait(UI_THREAD_STARTUP_TIMEOUT_SECONDS)
    # The thread did not signal startup within the timeout.
    if not is_started:
        _stop_ui_thread_after_startup_failure(
            thread,
            action_path,
            instruction_index,
            command,
        )
        raise action_errors.ActionExecutionError(
            (
                "Action path "
                f"'{_format_action_path(action_path)}' failed at "
                f"instruction {instruction_index} ({command}): "
                "UI thread did not start within "
                f"{UI_THREAD_STARTUP_TIMEOUT_SECONDS} seconds."
            ),
            action_path=action_path,
            instruction_index=instruction_index,
            command=command,
        )
    # The thread signaled startup but then reported an error.
    if thread.error:
        _stop_ui_thread_after_startup_failure(
            thread,
            action_path,
            instruction_index,
            command,
        )
        raise action_errors.ActionExecutionError(
            (
                "Action path "
                f"'{_format_action_path(action_path)}' failed at "
                f"instruction {instruction_index} ({command}): "
                f"{thread.error}"
            ),
            action_path=action_path,
            instruction_index=instruction_index,
            command=command,
        )


def _execute_instruction(
    trade,
    config,
    gui_state,
    command,
    argument,
    additional_argument,
    action_path,
    instruction_index,
):
    """Execute a single instruction."""
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
        return handler(
            trade,
            config,
            command,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        )
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
        return handler(
            trade,
            config,
            command,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        )
    if handler is _handle_market_data_command:
        return handler(trade, config, command, argument)
    if handler in (
        _handle_share_size_command,
        _handle_risk_guard_command,
        _handle_trade_input_command,
    ):
        return handler(trade, config, command, argument, additional_argument)
    if handler is _handle_trade_accounting_command:
        return handler(
            trade,
            config,
            command,
            argument,
            additional_argument,
            action_path,
            instruction_index,
        )
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
            *argument
        )
    elif command == "click_widget":
        trade.keyboard_listener_state = 1
        trade.key_to_check = None
        trade.should_continue = True
        try:
            gui_interactions.click_widget(
                gui_state,
                os.path.join(trade.resource_directory, argument),
                *additional_argument,
                should_continue_reference=(
                    lambda: (
                        listeners.raise_listener_monitor_error(trade)
                        or trade.should_continue
                    )
                ),
            )
        finally:
            trade.keyboard_listener_state = 0
            trade.key_to_check = None
        if not trade.should_continue:
            trade.speech_manager.set_speech_text("Canceled.")
            return False
    elif command == "drag_to":
        pyautogui.dragTo(*argument)
    elif command == "move_to":
        pyautogui.moveTo(*argument)
    elif command == "press_hotkeys":
        pyautogui.hotkey(*tuple(map(str.strip, argument.split(","))))
    elif command == "press_key":
        pyautogui.press(argument[0], presses=argument[1])
    elif command == "right_click":
        pyautogui.click(
            *argument,
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
    action_path,
    instruction_index,
):
    """Handle window and indicator visibility commands."""
    if command == "hide_window":
        gui_interactions.enumerate_windows(
            gui_interactions.hide_window, argument
        )
    elif command == "show_hide_indicator":
        if trade.indicator_thread:
            trade.indicator_thread.stop()
            trade.indicator_thread.join(timeout=UI_THREAD_STOP_TIMEOUT_SECONDS)
            if trade.indicator_thread.is_alive():
                raise action_errors.ActionExecutionError(
                    (
                        "Action path "
                        f"'{_format_action_path(action_path)}' failed at "
                        f"instruction {instruction_index} ({command}): "
                        "UI thread did not stop within "
                        f"{UI_THREAD_STOP_TIMEOUT_SECONDS} seconds."
                    ),
                    action_path=action_path,
                    instruction_index=instruction_index,
                    command=command,
                )
            trade.indicator_thread = None
        elif trade.widgets_section in config:
            indicator_thread = ui.IndicatorThread(trade, config)
            _start_ui_thread(
                indicator_thread,
                action_path,
                instruction_index,
                command,
            )
            trade.indicator_thread = indicator_thread
        else:
            return False
    elif command == "show_hide_window":
        gui_interactions.enumerate_windows(
            gui_interactions.show_hide_window, argument
        )
    elif command == "show_window":
        gui_interactions._show_window_state["count"] = 0
        gui_interactions._show_window_state["max_count"] = additional_argument
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
        time.sleep(argument)
    elif command == "wait_for_key":
        if not _wait_for_key(
            trade,
            config,
            gui_state,
            argument,
            additional_argument,
            action_path=action_path,
            instruction_index=instruction_index,
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
        try:
            text_recognition.recognize_text(
                *argument,
                int(config[trade.process]["image_magnification"]),
                int(config[trade.process]["binarization_threshold"]),
                config[trade.process].getboolean("is_dark_theme"),
                should_continue_reference=(
                    lambda: (
                        listeners.raise_listener_monitor_error(trade)
                        or trade.should_continue
                    )
                ),
                max_attempts=None,
            )
        finally:
            trade.keyboard_listener_state = 0
            trade.key_to_check = None
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
        try:
            gui_interactions.wait_for_window(
                argument,
                should_continue_reference=(
                    lambda: (
                        listeners.raise_listener_monitor_error(trade)
                        or trade.should_continue
                    )
                ),
            )
        finally:
            trade.keyboard_listener_state = 0
            trade.key_to_check = None
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
    action_path,
    instruction_index,
):
    """Handle speech and user notification commands."""
    if command == "speak_config":
        trade.speech_manager.set_speech_text(
            config[argument][additional_argument]
        )
    elif command == "speak_cpu_utilization":
        trade.speech_manager.set_speech_text(
            f"{round(psutil.cpu_percent(interval=argument))}%."
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
        message_thread = ui.MessageThread(trade, config, argument)
        _start_ui_thread(
            message_thread,
            action_path,
            instruction_index,
            command,
        )
    elif command == "speak_text":
        trade.speech_manager.set_speech_text(argument)

    return True


def _handle_market_data_command(trade, config, command, argument):
    """Handle market data retrieval and persistence commands."""
    if command == "archive_market_data":
        if not archive_market_data(trade, config)[0]:
            trade.speech_manager.set_speech_text(ARCHIVE_MARKET_DATA_ERROR)
            return False
    elif command == "copy_symbols_from_column":
        _copy_symbols_from_column(trade, config, argument)

    return True


def _copy_symbols_from_column(trade, config, argument):
    """Recognize symbols from a column region and copy them to clipboard."""
    symbols = text_recognition.recognize_text(
        *argument,
        None,
        int(config[trade.process]["image_magnification"]),
        int(config[trade.process]["binarization_threshold"]),
        config[trade.process].getboolean("is_dark_theme"),
        text_type="securities_code_column",
    )
    # ast.literal_eval() needs a complete Python string literal to decode \\d
    # as \d, such as "\\d".
    securities_code_regex = re.compile(
        evaluate_value(f'"{config["Market Data"]["securities_code_regex"]}"')
    )
    valid_symbols = []
    invalid_symbols = []
    for row, symbol in enumerate(symbols, start=1):
        stripped_symbol = symbol.strip()
        if not stripped_symbol:
            continue
        if securities_code_regex.fullmatch(stripped_symbol):
            valid_symbols.append(stripped_symbol)
        else:
            invalid_symbols.append((row, stripped_symbol))
    if invalid_symbols or not valid_symbols:
        if invalid_symbols:
            invalid_rows = ", ".join(
                f"row {row}: {symbol!r}" for row, symbol in invalid_symbols
            )
            message = f"OCR produced invalid securities codes: {invalid_rows}."
        else:
            message = "OCR produced no valid securities codes."
        raise errors.TextRecognitionError(
            message,
            attempts=1,
            last_output="\n".join(symbols),
            region=tuple(argument[:4]),
            text_type="securities_code_column",
        )

    is_clipboard_open = False
    try:
        win32clipboard.OpenClipboard()
        is_clipboard_open = True
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(" ".join(valid_symbols))
    finally:
        if is_clipboard_open:
            win32clipboard.CloseClipboard()


def archive_market_data(trade, config):
    """Move existing market data files for today's default export names."""
    section = config["Market Data"]
    market_data_directory = section["market_data_directory"]
    market_data_name_regex = re.compile(
        config[trade.process]["market_data_name_regex"]
    )
    now = pd.Timestamp.now(tz=section["timezone"])
    target_date_string = now.strftime("%Y%m%d")

    try:
        filenames = sorted(os.listdir(market_data_directory))
        matched_filenames = []
        for filename in filenames:
            matched = market_data_name_regex.fullmatch(filename)
            if matched and matched.group("date") == target_date_string:
                matched_filenames.append(filename)

        if not matched_filenames:
            return (True, None)

        market_data_archive_directory = section[
            "market_data_archive_directory"
        ]
        archive_batch_name = (
            f"{now.strftime('%Y%m%dT%H%M%S')}."
            f"{now.microsecond // 1000:03d}"
        )
        archive_batch_directory = os.path.join(
            market_data_archive_directory,
            archive_batch_name,
        )
        temporary_archive_batch_directory = os.path.join(
            market_data_archive_directory,
            f".{archive_batch_name}.tmp",
        )
        completed_moves = []

        os.makedirs(temporary_archive_batch_directory)
        try:
            for filename in matched_filenames:
                source_path = os.path.join(market_data_directory, filename)
                archive_path = os.path.join(
                    temporary_archive_batch_directory,
                    filename,
                )
                os.replace(source_path, archive_path)
                completed_moves.append((source_path, archive_path))
            os.replace(
                temporary_archive_batch_directory,
                archive_batch_directory,
            )
        except OSError:
            for source_path, archive_path in reversed(completed_moves):
                if os.path.exists(archive_path):
                    os.replace(archive_path, source_path)
            try:
                os.rmdir(temporary_archive_batch_directory)
            except OSError:
                pass
            raise
        return (True, None)
    except (IndexError, OSError) as e:
        return (False, f"{ARCHIVE_MARKET_DATA_ERROR} {e}")


def _handle_share_size_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
):
    """Handle share-size calculation commands."""
    if command == "calculate_share_size":
        is_successful, text = calculate_share_size(trade, config, argument)
        if not is_successful and text:
            trade.speech_manager.set_speech_text(text)
            return False

    return True


def _handle_risk_guard_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
):
    """Handle trade risk guard commands."""
    if command == "check_daily_loss_limit":
        if not getattr(trade, "has_cash_balance", False):
            trade.speech_manager.set_speech_text("Cash balance not provided.")
            return False
        should_stop = False
        with trade.config_lock:
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
                should_stop = daily_profit < daily_loss_limit
        if should_stop:
            trade.speech_manager.set_speech_text(argument)
            return False
    elif command == "check_maximum_daily_number_of_trades":
        with trade.config_lock:
            is_trade_limit_reached = (
                0
                < int(config[trade.process]["maximum_daily_number_of_trades"])
                <= int(
                    config[trade.variables_section]["current_number_of_trades"]
                )
            )
        if is_trade_limit_reached:
            trade.speech_manager.set_speech_text(argument)
            return False

    return True


def _handle_trade_accounting_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
    action_path,
    instruction_index,
):
    """Handle trade count and chapter accounting commands."""
    latest_video = file_utilities.get_latest_file(
        config[trade.process]["screencast_directory"],
        config[trade.process]["screencast_regex"],
    )
    # Check latest_video before these commands; the repeated is_writing() check
    # is cheap enough here.
    if not latest_video or not file_utilities.is_writing(latest_video):
        raise action_errors.ActionExecutionError(
            (
                "Action path "
                f"'{_format_action_path(action_path)}' failed at "
                f"instruction {instruction_index} ({command}): "
                "No active recording was found for chapter metadata."
            ),
            action_path=action_path,
            instruction_index=instruction_index,
            command=command,
        )

    if command == "count_trades":
        with trade.config_lock:
            current_number_of_trades = (
                int(
                    config[trade.variables_section]["current_number_of_trades"]
                )
                + 1
            )
            config[trade.variables_section]["current_number_of_trades"] = str(
                current_number_of_trades
            )
            write_config(config, trade.config_path, is_encrypted=True)
        file_utilities.write_chapter(
            latest_video,
            (
                f"Trade {current_number_of_trades}"
                f"{f' for {trade.symbol}' if trade.symbol else ''}"
                f" at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            previous_title="Pre-trading",
            offset=argument,
        )
    elif command == "write_chapter":
        file_utilities.write_chapter(
            latest_video,
            argument,
            previous_title=additional_argument,
        )

    return True


def _handle_trade_input_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
):
    """Handle trade input and output commands."""
    if command == "get_cash_balance":
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
        trade.has_cash_balance = True
    elif command == "get_symbol":
        gui_interactions.enumerate_windows(trade.get_symbol, argument)
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
        ) == argument and not _recursively_execute_action(
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
        ) == argument and not (
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
            is_top_level_action=False,
            action_path=(*action_path, f"inline@{instruction_index}"),
        )
    if isinstance(additional_argument, str):
        if additional_argument in action_path:
            raise action_errors.ActionExecutionError(
                (
                    "Action path "
                    f"'{_format_action_path(action_path)}' failed at "
                    f"instruction {instruction_index} (execute_action): "
                    f"nested action '{additional_argument}' creates a cycle."
                ),
                action_path=action_path,
                instruction_index=instruction_index,
                command="execute_action",
            )
        if additional_argument not in config[trade.actions_section]:
            raise action_errors.ActionExecutionError(
                (
                    "Action path "
                    f"'{_format_action_path(action_path)}' failed at "
                    f"instruction {instruction_index} (execute_action): "
                    f"nested action '{additional_argument}' is not defined."
                ),
                action_path=action_path,
                instruction_index=instruction_index,
                command="execute_action",
            )
        return execute_action(
            trade,
            config,
            gui_state,
            config[trade.actions_section][additional_argument],
            should_initialize=False,
            is_top_level_action=False,
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
    try:
        trade.key_to_check = argument
        trade.keyboard_listener_state = 1
        countdown_seconds = [
            int(seconds.strip())
            for seconds in config["General"][
                "countdown_seconds_before_candle_close"
            ].split(",")
        ]
        announced_minutes = {seconds: -1 for seconds in countdown_seconds}

        while trade.keyboard_listener_state == 1:
            listeners.raise_listener_monitor_error(trade)
            if should_count_down:
                now = pd.Timestamp.now()
                current_second = now.second
                current_minute = now.minute

                for seconds in countdown_seconds:
                    if (
                        current_second == 60 - seconds
                        and current_minute != announced_minutes[seconds]
                    ):
                        trade.speech_manager.set_speech_text(
                            f"{seconds} seconds."
                        )
                        announced_minutes[seconds] = current_minute

            time.sleep(0.01)
    finally:
        trade.keyboard_listener_state = 0
        trade.key_to_check = None

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
        if not _recursively_execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            action_path,
            instruction_index,
        ):
            raise action_errors.ActionExecutionError(
                (
                    "Action path "
                    f"'{_format_action_path(action_path)}' failed at "
                    f"instruction {instruction_index}: "
                    "cancellation cleanup action failed."
                ),
                action_path=action_path,
                instruction_index=instruction_index,
                command="cancellation_cleanup",
            )

    trade.speech_manager.set_speech_text("Canceled.")
    trade.last_action_canceled = True
    return True


_COMMAND_DISPATCH = {
    # GUI Interaction Commands
    "back_to": _handle_gui_command,
    "click": _handle_gui_command,
    "click_widget": _handle_gui_command,
    "drag_to": _handle_gui_command,
    "move_to": _handle_gui_command,
    "press_hotkeys": _handle_gui_command,
    "press_key": _handle_gui_command,
    "right_click": _handle_gui_command,
    "write_string": _handle_gui_command,
    # Window and Indicator Visibility Commands
    "hide_window": _handle_window_command,
    "show_hide_indicator": _handle_window_command,
    "show_hide_window": _handle_window_command,
    "show_window": _handle_window_command,
    # Blocking and Wait-Related Commands
    "sleep": _handle_wait_command,
    "wait_for_key": _handle_wait_command,
    "wait_for_key_count_down": _handle_wait_command,
    "wait_for_price": _handle_wait_command,
    "wait_for_window": _handle_wait_command,
    # Speech and User Notification Commands
    "speak_config": _handle_speak_command,
    "speak_cpu_utilization": _handle_speak_command,
    "speak_minutes_since_hour": _handle_speak_command,
    "speak_seconds_since_time": _handle_speak_command,
    "speak_seconds_until_time": _handle_speak_command,
    "speak_show_text": _handle_speak_command,
    "speak_text": _handle_speak_command,
    # Market Data Retrieval and Persistence Commands
    "archive_market_data": _handle_market_data_command,
    "copy_symbols_from_column": _handle_market_data_command,
    # Trade State and Accounting Commands
    "calculate_share_size": _handle_share_size_command,
    "check_daily_loss_limit": _handle_risk_guard_command,
    "check_maximum_daily_number_of_trades": _handle_risk_guard_command,
    "count_trades": _handle_trade_accounting_command,
    "get_cash_balance": _handle_trade_input_command,
    "get_symbol": _handle_trade_input_command,
    "write_chapter": _handle_trade_accounting_command,
    "write_share_size": _handle_trade_input_command,
    # Conditional Control-Flow Commands
    "is_now_after": _handle_control_flow_command,
    "is_now_before": _handle_control_flow_command,
    "is_recording": _handle_control_flow_command,
    "is_trading_day": _handle_control_flow_command,
    # Execution and Delegation Commands
    "execute_action": _handle_execution_command,
}
_ARGUMENT_NORMALIZERS = {
    "click": _normalize_point_argument,
    "click_widget": _normalize_click_widget_argument,
    "copy_symbols_from_column": _normalize_ocr_column_argument,
    "drag_to": _normalize_point_argument,
    "move_to": _normalize_point_argument,
    "press_key": _normalize_press_key_argument,
    "right_click": _normalize_point_argument,
    "show_window": _normalize_show_window_argument,
    "sleep": _normalize_float_argument,
    "speak_cpu_utilization": _normalize_float_argument,
    "wait_for_key": _normalize_wait_for_key_argument,
    "wait_for_key_count_down": _normalize_wait_for_key_argument,
    "wait_for_price": _normalize_ocr_region_argument,
}
ALL_KEYS = tuple(sorted(_COMMAND_DISPATCH))


def is_trading_day(date, market_holidays, date_format):
    """Check if the given date is a trading day."""
    return date.weekday() < 5 and date.strftime(date_format) not in set(
        pd.read_csv(market_holidays, header=None, dtype=str)[0]
    )


def get_price_limit(trade, config):
    """Calculate the price limit for a trade."""
    closing_price = 0.0
    if trade.process == "HYPERSBI2":
        try:
            closing_price = _get_closing_price_from_hypersbi2_rankings(
                trade,
                config,
            )
        except errors.MarketDataError as e:
            # Corrupted market data means the structured source is known bad.
            # Fail closed instead of falling through to less reliable OCR.
            trade.last_action_error = e
            notifications.set_speech_text(
                trade,
                PRICE_LIMIT_MARKET_DATA_FILE_ERROR,
            )
            raise ValueError(PRICE_LIMIT_ERROR) from e
        except OSError as e:
            # Market data may simply be unavailable, so record diagnostics
            # without speaking on every order.
            trade.last_action_warning = errors.MarketDataError(
                f"{MARKET_DATA_FILE_ERROR}: {e}"
            )

    if closing_price:
        return trade_service.calculate_price_limit_from_closing_price(
            closing_price
        )

    if not config[trade.process].getboolean(
        "is_price_limit_ocr_fallback_enabled", fallback=False
    ):
        raise ValueError(PRICE_LIMIT_ERROR)

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


def _get_closing_price_from_hypersbi2_rankings(trade, config):
    """Return the previous closing price from Hyper SBI 2 rankings CSVs."""
    section = config["Market Data"]
    market_data_directory = section["market_data_directory"]
    market_data_name_regex = re.compile(
        config[trade.process]["market_data_name_regex"]
    )
    now = pd.Timestamp.now(tz=section["timezone"])
    previous_trading_day = now - pd.Timedelta(days=1)
    while not is_trading_day(
        previous_trading_day,
        trade.market_holidays,
        config["Market Holidays"]["date_format"],
    ):
        previous_trading_day -= pd.Timedelta(days=1)
    current_time = now.strftime("%H:%M:%S")
    if current_time < "07:59:00":  # Rankings clearing time
        target_dates = (previous_trading_day, now)
    elif current_time < section["closing_time"]:
        target_dates = (previous_trading_day,)
    else:
        target_dates = (now,)

    filenames = sorted(os.listdir(market_data_directory))

    for target_date in target_dates:
        target_date_string = target_date.strftime("%Y%m%d")
        for filename in filenames:
            matched = market_data_name_regex.fullmatch(filename)
            if not matched:
                continue
            if matched.group("date") == target_date_string:
                closing_price = _find_price_in_csv(
                    os.path.join(market_data_directory, filename),
                    trade.symbol,
                    symbol_column=6,
                    price_column=9,
                )
                if closing_price:
                    return closing_price
    return 0.0


def _find_price_in_csv(path, symbol, symbol_column, price_column):
    """Return a symbol's price from one CSV table."""
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row_number, row in enumerate(reader, start=1):
            if len(row) <= max(symbol_column, price_column):
                raise errors.MarketDataError(
                    f"{MARKET_DATA_FILE_ERROR} {path}: row "
                    f"{row_number} has {len(row)} columns."
                )
            if row[symbol_column].strip() == symbol:
                current_price = row[price_column].strip().replace(",", "")
                try:
                    return float(current_price)
                except ValueError as e:
                    raise errors.MarketDataError(
                        f"{MARKET_DATA_FILE_ERROR} {path}: row "
                        f"{row_number} has invalid closing price "
                        f"{row[price_column].strip()!r}."
                    ) from e
    return 0.0


def calculate_share_size(trade, config, position):
    """Determine the share size for a given trade."""
    if trade.symbol and trade.cash_balance:
        section = config[trade.customer_margin_ratios_section]
        freshness_error = _get_customer_margin_ratios_freshness_error(
            trade,
            config,
            section,
        )
        if freshness_error:
            return (False, freshness_error)

        customer_margin_ratio = float(section["default_customer_margin_ratio"])
        margin_ratio_error, customer_margin_ratio = _get_customer_margin_ratio(
            trade,
            customer_margin_ratio,
        )
        # _get_customer_margin_ratio() returns either an error tuple or a
        # ratio.
        if margin_ratio_error:
            return margin_ratio_error

        try:
            share_size = trade_service.calculate_share_size_from_inputs(
                cash_balance=trade.cash_balance,
                utilization_ratio=float(
                    config[trade.process]["utilization_ratio"]
                ),
                customer_margin_ratio=customer_margin_ratio,
                price_limit=get_price_limit(trade, config),
                position=position,
            )
        except errors.TextRecognitionError as e:
            trade.last_action_error = e
            return (False, PRICE_LIMIT_ERROR)
        except ValueError as e:
            if str(e) == PRICE_LIMIT_ERROR:
                return (False, PRICE_LIMIT_ERROR)
            trade.last_action_error = e
            return (False, SHARE_SIZE_ERROR)
        if share_size == 0:
            return (False, "Insufficient cash balance.")

        trade.share_size = share_size
        return (True, None)

    return (False, "Symbol or cash balance not provided.")


def _get_customer_margin_ratios_freshness_error(trade, config, section):
    """Return a blocking message for stale or unverifiable margin ratios."""
    customer_margin_ratios_checked_at = getattr(
        trade,
        "customer_margin_ratios_checked_at",
        None,
    )
    if (
        customer_margin_ratios_checked_at is not None
        and time.monotonic() - customer_margin_ratios_checked_at
        <= CUSTOMER_MARGIN_RATIOS_FRESHNESS_CACHE_SECONDS
    ):
        return None

    try:
        if customer_margin_ratios.get_latest(
            config,
            trade.market_holidays,
            section["update_time"],
            section["timezone"],
            trade.customer_margin_ratios,
        ):
            return "Customer margin ratios are stale."
    except errors.CoreUtilitiesError as e:
        trade.last_action_error = e
        return "Unable to verify customer margin ratios."

    trade.customer_margin_ratios_checked_at = time.monotonic()
    return None


def _get_customer_margin_ratio(trade, customer_margin_ratio):
    """Return a trade-specific customer margin ratio or a blocking error."""
    try:
        with open(trade.customer_margin_ratios, encoding="utf-8") as f:
            reader = csv.reader(f)
            for row_number, row in enumerate(reader, start=1):
                if len(row) < 2:
                    raise errors.MarketDataError(
                        f"{CUSTOMER_MARGIN_RATIOS_FILE_ERROR} "
                        f"{trade.customer_margin_ratios}: row "
                        f"{row_number} has {len(row)} columns."
                    )
                if row[0] == trade.symbol:
                    if row[1] == "suspended":
                        return (False, "Margin trading suspended."), None

                    try:
                        customer_margin_ratio = float(row[1])
                    except ValueError as e:
                        raise errors.MarketDataError(
                            f"{CUSTOMER_MARGIN_RATIOS_FILE_ERROR} "
                            f"{trade.customer_margin_ratios}: row "
                            f"{row_number} has invalid margin ratio "
                            f"{row[1]!r}."
                        ) from e
                    break
    except errors.MarketDataError as e:
        trade.last_action_error = e
        return (False, f"{CUSTOMER_MARGIN_RATIOS_FILE_ERROR}."), None
    except OSError as e:
        trade.last_action_error = errors.MarketDataError(
            f"{CUSTOMER_MARGIN_RATIOS_FILE_ERROR} "
            f"{trade.customer_margin_ratios}: {e}"
        )
        return (False, f"{CUSTOMER_MARGIN_RATIOS_FILE_ERROR}."), None

    return None, customer_margin_ratio
