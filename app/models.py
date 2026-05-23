"""Trading assistant state models and input event handlers."""

import os
import re
import threading
import time

import win32gui
from pynput import keyboard

from app import actions
from core_utilities import file_utilities, initializer
from core_utilities.config_validation import evaluate_value


class Trade(initializer.Initializer):
    """Handle trading operations for a specific vendor and process."""

    _MODIFIER_KEYS = {
        keyboard.Key.alt,
        keyboard.Key.alt_gr,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r,
        keyboard.Key.cmd,
        keyboard.Key.cmd_l,
        keyboard.Key.cmd_r,
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r,
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r,
    }
    _FUNCTION_KEYS = (
        keyboard.Key.f1,
        keyboard.Key.f2,
        keyboard.Key.f3,
        keyboard.Key.f4,
        keyboard.Key.f5,
        keyboard.Key.f6,
        keyboard.Key.f7,
        keyboard.Key.f8,
        keyboard.Key.f9,
        keyboard.Key.f10,
        keyboard.Key.f11,
        keyboard.Key.f12,
    )

    def __init__(
        self,
        vendor,
        process,
        script_path,
        start_execute_action_thread_fn,
    ):
        """Initialize the Trade with the vendor, process, and callbacks."""
        super().__init__(vendor, process, script_path)
        self._start_execute_action_thread_fn = start_execute_action_thread_fn
        self.market_directory = os.path.join(self.config_directory, "market")
        self.resource_directory = os.path.join(
            self.config_directory, self.process
        )
        for directory in [self.market_directory, self.resource_directory]:
            file_utilities.check_directory(directory)

        self.market_holidays = os.path.join(
            self.market_directory, "market_holidays.csv"
        )
        self.closing_prices = os.path.join(
            self.market_directory, "closing_prices_"
        )

        self.geometries_section = f"{self.process} Geometries"
        self.schedules_section = f"{self.process} Schedules"

        self.customer_margin_ratios_section = (
            f"{self.vendor} Customer Margin Ratios"
        )
        self.customer_margin_ratios = os.path.join(
            self.resource_directory, "customer_margin_ratios.csv"
        )

        self.window_titles_section = f"{self.process} Window Titles"
        self.widgets_section = f"{self.process} Widgets"
        self.indicator_thread = None

        self.startup_script_section = f"{self.process} Startup Script"
        self.startup_script_base = f"{self.process.lower()}_assistant"
        self.startup_script = os.path.join(
            self.resource_directory, f"{self.startup_script_base}.ps1"
        )

        self.mouse_listener = None
        self.keyboard_listener = None
        self.keyboard_listener_state = 0
        self.action_lock = threading.Lock()
        self.last_action_error = None
        self.last_action_warning = None
        self._pressed_modifiers = set()
        self._last_action_time = 0
        self.key_to_check = None
        self.should_continue = False

        self.speech_manager = None
        self.speaking_process = None

        self.stop_listeners_event = None
        self.wait_listeners_thread = None

        self.instruction_items = {
            "all_keys": sorted(actions.ALL_KEYS),
            "no_value_keys": {
                "archive_market_data",
                "back_to",
                "get_cash_balance",
                "show_hide_indicator",
                "write_share_size",
            },
            "optional_value_keys": {
                "count_trades",
                "speak_minutes_since_hour",
            },
            "additional_value_keys": {"click_widget", "speak_config"},
            "optional_additional_value_keys": {"write_chapter"},
            "positioning_keys": {"click", "drag_to", "move_to", "right_click"},
            "preset_geometries": None,
            "nested_keys": {"execute_action"},
            "optional_additional_nested_keys": {
                "wait_for_key",
                "wait_for_key_count_down",
                "wait_for_price",
                "wait_for_window",
            },
            "control_flow_keys": {
                "is_now_after",
                "is_now_before",
                "is_recording",
                "is_trading_day",
            },
            "preset_value_keys": {
                "is_now_after",
                "is_now_before",
                "speak_minutes_since_hour",
                "speak_seconds_since_time",
                "speak_seconds_until_time",
            },
            "preset_values": (
                "${Market Data:opening_time}",
                "${Market Data:midday_break_time}",
                "${Market Data:reopening_time}",
                "${Market Data:last_order_time}",
                "${Market Data:closing_time}",
                f"${{{self.process}:start_time}}",
                f"${{{self.process}:end_time}}",
            ),
            "boolean_value_keys": {"is_recording", "is_trading_day"},
            "preset_additional_values": None,
        }

        self.symbol = ""
        self.initialize_attributes()

    def initialize_attributes(self):
        """Reset the symbol, cash balance, and share size to initial states."""
        self.symbol = ""
        self.cash_balance = 0
        self.share_size = 0

    def get_symbol(self, hwnd, title_regex):
        """Get the symbol from a window title matching a regular expression."""
        matched = re.fullmatch(title_regex, win32gui.GetWindowText(hwnd))
        if matched:
            self.symbol = matched.group(1)
            return False
        return True

    def on_click(self, _1, _2, button, pressed, config, gui_state):
        """Handle mouse click events."""
        if gui_state.is_interactive_window() and not pressed:
            action = evaluate_value(config[self.process]["input_map"]).get(
                button.name
            )
            if action:
                self._start_execute_action_thread_fn(
                    self, config, gui_state, action
                )

    def on_press(self, key, config, gui_state):
        """Handle key press events."""
        if gui_state.is_interactive_window():
            # Add context for whether modifiers are pressed.
            if key in Trade._MODIFIER_KEYS:
                self._pressed_modifiers.add(key)
                return
            if self.keyboard_listener_state == 0:
                if key in Trade._FUNCTION_KEYS and not self._pressed_modifiers:
                    now = time.time()
                    # A 0.3-second debounce interval prevents double-triggers
                    # from both software detection and hardware chattering.
                    if now - self._last_action_time > 0.3:
                        action = evaluate_value(
                            config[self.process]["input_map"]
                        ).get(key.name)
                        if action:
                            self._start_execute_action_thread_fn(
                                self, config, gui_state, action
                            )
                            self._last_action_time = now
            elif self.keyboard_listener_state == 1:
                if (
                    hasattr(key, "char") and key.char == self.key_to_check
                ) or key == self.key_to_check:
                    self.should_continue = True
                    self.keyboard_listener_state = 0
                elif key == keyboard.Key.esc:
                    self.should_continue = False
                    self.keyboard_listener_state = 0

    def on_release(self, key, gui_state):
        """Handle key release events to update modifiers."""
        self._pressed_modifiers.discard(key)
