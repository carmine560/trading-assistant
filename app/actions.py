"""Configured action execution for trading assistant workflows."""

import math
import os
import threading
import time

ALL_KEYS = (
    "back_to",
    "calculate_share_size",
    "check_daily_loss_limit",
    "check_maximum_daily_number_of_trades",
    "click",
    "click_widget",
    "copy_symbols_from_column",
    "count_trades",
    "drag_to",
    "execute_action",
    "get_cash_balance",
    "get_symbol",
    "hide_window",
    "is_now_after",
    "is_now_before",
    "is_recording",
    "is_trading_day",
    "move_to",
    "press_hotkeys",
    "press_key",
    "right_click",
    "save_market_data",
    "show_hide_indicator",
    "show_hide_window",
    "show_window",
    "sleep",
    "speak_config",
    "speak_cpu_utilization",
    "speak_minutes_since_hour",
    "speak_seconds_since_time",
    "speak_seconds_until_time",
    "speak_show_text",
    "speak_text",
    "wait_for_key",
    "wait_for_key_count_down",
    "wait_for_price",
    "wait_for_window",
    "write_chapter",
    "write_share_size",
    "write_string",
)


def start_execute_action_thread(trade, config, gui_state, action, deps):
    """Start a new thread to execute a specified action."""
    execute_action_thread = threading.Thread(
        target=execute_action,
        args=(
            trade,
            config,
            gui_state,
            config[trade.actions_section][action],
            deps,
        ),
    )
    execute_action_thread.start()


def execute_action(
    trade,
    config,
    gui_state,
    action,
    deps,
    should_initialize=True,
):
    """Execute a sequence of commands for a trade."""
    if should_initialize:
        trade.initialize_attributes()
        gui_state.initialize_attributes()

    if isinstance(action, str):
        action = deps["configuration"].evaluate_value(action)

    for instruction in action:
        command = instruction[0]
        if command not in ALL_KEYS:
            return False
        if not _execute_instruction(
            trade, config, gui_state, instruction, deps
        ):
            return False

    return True


def _execute_instruction(trade, config, gui_state, instruction, deps):
    """Execute a single instruction."""
    command, argument, additional_argument = _unpack_instruction(instruction)

    if command in {
        "back_to",
        "click",
        "click_widget",
        "drag_to",
        "move_to",
        "press_hotkeys",
        "press_key",
        "right_click",
        "write_string",
    }:
        return _handle_gui_command(
            trade,
            config,
            gui_state,
            command,
            argument,
            additional_argument,
            deps,
        )
    if command in {
        "hide_window",
        "show_hide_indicator",
        "show_hide_window",
        "show_window",
    }:
        return _handle_window_command(
            trade, config, command, argument, additional_argument, deps
        )
    if command in {
        "sleep",
        "wait_for_key",
        "wait_for_key_count_down",
        "wait_for_price",
        "wait_for_window",
    }:
        return _handle_wait_command(
            trade,
            config,
            gui_state,
            command,
            argument,
            additional_argument,
            deps,
        )
    if command in {
        "speak_config",
        "speak_cpu_utilization",
        "speak_minutes_since_hour",
        "speak_seconds_since_time",
        "speak_seconds_until_time",
        "speak_show_text",
        "speak_text",
    }:
        return _handle_speak_command(
            trade, config, command, argument, additional_argument, deps
        )
    if command in {"copy_symbols_from_column", "save_market_data"}:
        return _handle_market_data_command(
            trade, config, command, argument, deps
        )
    if command in {
        "calculate_share_size",
        "check_daily_loss_limit",
        "check_maximum_daily_number_of_trades",
        "count_trades",
        "get_cash_balance",
        "get_symbol",
        "write_chapter",
        "write_share_size",
    }:
        return _handle_trade_state_command(
            trade, config, command, argument, additional_argument, deps
        )
    if command in {
        "is_now_after",
        "is_now_before",
        "is_recording",
        "is_trading_day",
    }:
        return _handle_control_flow_command(
            trade,
            config,
            gui_state,
            command,
            argument,
            additional_argument,
            deps,
        )
    if command == "execute_action":
        return _handle_execution_command(
            trade, config, gui_state, argument, deps
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
    config,
    gui_state,
    command,
    argument,
    additional_argument,
    deps,
):
    """Handle GUI interaction commands."""
    pyautogui = deps["pyautogui"]
    gui_interactions = deps["gui_interactions"]

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
    deps,
):
    """Handle window and indicator visibility commands."""
    gui_interactions = deps["gui_interactions"]

    if command == "hide_window":
        gui_interactions.enumerate_windows(
            gui_interactions.hide_window, argument
        )
    elif command == "show_hide_indicator":
        if trade.indicator_thread:
            trade.indicator_thread.stop()
            trade.indicator_thread = None
        elif trade.widgets_section in config:
            trade.indicator_thread = deps["indicator_thread_cls"](
                trade, config
            )
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
    deps,
):
    """Handle blocking and wait-related commands."""
    if command == "sleep":
        time.sleep(float(argument))
    elif command == "wait_for_key":
        if not _wait_for_key(
            trade, config, gui_state, argument, additional_argument, deps
        ):
            return False
    elif command == "wait_for_key_count_down":
        if not _wait_for_key(
            trade,
            config,
            gui_state,
            argument,
            additional_argument,
            deps,
            should_count_down=True,
        ):
            return False
    elif command == "wait_for_price":
        trade.keyboard_listener_state = 1
        trade.key_to_check = None
        trade.should_continue = True
        deps["text_recognition"].recognize_text(
            *map(int, argument.split(",")),
            int(config[trade.process]["image_magnification"]),
            int(config[trade.process]["binarization_threshold"]),
            config[trade.process].getboolean("is_dark_theme"),
            should_continue_reference=lambda: trade.should_continue,
        )
        trade.keyboard_listener_state = 0
        if not trade.should_continue and _handle_cancellation_exit(
            trade, config, gui_state, additional_argument, deps
        ):
            return False
    elif command == "wait_for_window":
        trade.keyboard_listener_state = 1
        trade.key_to_check = None
        trade.should_continue = True
        deps["gui_interactions"].wait_for_window(
            argument,
            should_continue_reference=lambda: trade.should_continue,
        )
        trade.keyboard_listener_state = 0
        if not trade.should_continue and _handle_cancellation_exit(
            trade, config, gui_state, additional_argument, deps
        ):
            return False

    return True


def _handle_speak_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
    deps,
):
    """Handle speech and user notification commands."""
    if command == "speak_config":
        trade.speech_manager.set_speech_text(
            config[argument][additional_argument]
        )
    elif command == "speak_cpu_utilization":
        psutil = deps["psutil"]
        trade.speech_manager.set_speech_text(
            f"{round(psutil.cpu_percent(interval=float(argument)))}%."
        )
    elif command == "speak_minutes_since_hour":
        data_utilities = deps["data_utilities"]
        if argument:
            target_time = data_utilities.get_target_time(argument)
        else:
            pd = deps["pd"]
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
        data_utilities = deps["data_utilities"]
        seconds_since = math.floor(
            time.time() - data_utilities.get_target_time(argument)
        )
        trade.speech_manager.set_speech_text(f"{seconds_since} seconds.")
    elif command == "speak_seconds_until_time":
        data_utilities = deps["data_utilities"]
        seconds_until = math.ceil(
            data_utilities.get_target_time(argument) - time.time()
        )
        trade.speech_manager.set_speech_text(f"{seconds_until} seconds.")
    elif command == "speak_show_text":
        trade.speech_manager.set_speech_text(argument)
        deps["message_thread_cls"](trade, config, argument).start()
    elif command == "speak_text":
        trade.speech_manager.set_speech_text(argument)

    return True


def _handle_market_data_command(trade, config, command, argument, deps):
    """Handle market data retrieval and persistence commands."""
    if command == "copy_symbols_from_column":
        win32clipboard = deps["win32clipboard"]
        text_recognition = deps["text_recognition"]
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(
            " ".join(
                text_recognition.recognize_text(
                    *map(int, argument.split(",")),
                    None,
                    int(config[trade.process]["image_magnification"]),
                    int(config[trade.process]["binarization_threshold"]),
                    config[trade.process].getboolean("is_dark_theme"),
                    text_type="securities_code_column",
                )
            )
        )
        win32clipboard.CloseClipboard()
    elif command == "save_market_data":
        deps["save_market_data_fn"](trade, config)

    return True


def _handle_trade_state_command(
    trade,
    config,
    command,
    argument,
    additional_argument,
    deps,
):
    """Handle trade state and accounting commands."""
    configuration = deps["configuration"]
    file_utilities = deps["file_utilities"]
    gui_interactions = deps["gui_interactions"]
    pyautogui = deps["pyautogui"]
    text_recognition = deps["text_recognition"]

    if command == "calculate_share_size":
        is_successful, text = deps["calculate_share_size_fn"](
            trade, config, argument
        )
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
            configuration.write_config(
                config, trade.config_path, is_encrypted=True
            )
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
        configuration.write_config(
            config, trade.config_path, is_encrypted=True
        )
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
    deps,
):
    """Handle conditional control-flow commands."""
    data_utilities = deps["data_utilities"]
    file_utilities = deps["file_utilities"]
    pd = deps["pd"]

    if command == "is_now_after":
        if data_utilities.get_target_time(
            argument
        ) < time.time() and not _recursively_execute_action(
            trade, config, gui_state, additional_argument, deps
        ):
            return False
    elif command == "is_now_before":
        if time.time() < data_utilities.get_target_time(
            argument
        ) and not _recursively_execute_action(
            trade, config, gui_state, additional_argument, deps
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
            trade, config, gui_state, additional_argument, deps
        ):
            return False
    elif command == "is_trading_day":
        if deps["is_trading_day_fn"](
            pd.Timestamp.now(tz=config["Market Data"]["timezone"]),
            trade.market_holidays,
            config["Market Holidays"]["date_format"],
        ) == bool(argument.lower() == "true") and not (
            _recursively_execute_action(
                trade, config, gui_state, additional_argument, deps
            )
        ):
            return False

    return True


def _handle_execution_command(trade, config, gui_state, argument, deps):
    """Handle execution and delegation commands."""
    if not _recursively_execute_action(
        trade, config, gui_state, argument, deps
    ):
        return False

    return True


def _recursively_execute_action(
    trade, config, gui_state, additional_argument, deps
):
    """Recursively execute an action if it is a list or a string."""
    if isinstance(additional_argument, list):
        return execute_action(
            trade,
            config,
            gui_state,
            additional_argument,
            deps,
            should_initialize=False,
        )
    if isinstance(additional_argument, str):
        return execute_action(
            trade,
            config,
            gui_state,
            config[trade.actions_section][additional_argument],
            deps,
            should_initialize=False,
        )

    return False


def _wait_for_key(
    trade,
    config,
    gui_state,
    argument,
    additional_argument,
    deps,
    should_count_down=False,
):
    """Wait for a key press with optional countdown."""
    keyboard = deps["keyboard"]
    pd = deps["pd"]

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
        trade, config, gui_state, additional_argument, deps
    ):
        return False
    return True


def _handle_cancellation_exit(
    trade, config, gui_state, additional_argument, deps
):
    """Perform cancellation actions and signal caller to exit."""
    if additional_argument:
        _recursively_execute_action(
            trade, config, gui_state, additional_argument, deps
        )

    trade.speech_manager.set_speech_text("Canceled.")
    return True
