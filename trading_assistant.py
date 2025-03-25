"""Assist with discretionary day trading of stocks on margin."""

from datetime import date
from multiprocessing.managers import BaseManager
import argparse
import configparser
import csv
import inspect
import math
import os
import re
import sched
import sys
import threading
import time
import tkinter as tk
import win32clipboard

from pynput import keyboard
from pynput import mouse
from win32api import GetMonitorInfo, MonitorFromPoint
import chardet
import pandas as pd
import psutil
import pyautogui
import requests
import win32gui

import configuration
import data_utilities
import file_utilities
import gui_interactions
import initializer
import process_utilities
import speech_synthesis
import text_recognition
import web_utilities

RATIO_EPSILON = 1e-4
SANS_INITIAL_SECURITIES_CODE_REGEX = (
    r'[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?')
SECURITIES_CODE_REGEX = '[1-9]' + SANS_INITIAL_SECURITIES_CODE_REGEX


class Trade(initializer.Initializer):
    """Handle trading operations for a specific vendor and process."""

    def __init__(self, vendor, process):
        """Initialize the Trade with the vendor and process."""
        super().__init__(vendor, process, __file__)
        self.market_directory = os.path.join(self.config_directory, 'market')
        self.market_holidays = os.path.join(self.market_directory,
                                            'market_holidays.csv')
        self.closing_prices = os.path.join(self.market_directory,
                                           'closing_prices_')
        self.resource_directory = os.path.join(self.config_directory,
                                               self.process)
        self.customer_margin_ratios = os.path.join(
            self.resource_directory, 'customer_margin_ratios.csv')
        self.startup_script_base = f'{self.process.lower()}_assistant'
        self.startup_script = os.path.join(self.resource_directory,
                                           f'{self.startup_script_base}.ps1')

        for directory in [self.market_directory, self.resource_directory]:
            file_utilities.check_directory(directory)

        self.customer_margin_ratios_section = (
            f'{self.vendor} Customer Margin Ratios')

        self.widgets_section = f'{self.process} Widgets'
        self.indicator_thread = None

        self.startup_script_section = f'{self.process} Startup Script'

        self.instruction_items = {
            'all_keys': initializer.extract_commands(
                inspect.getsource(execute_action)),
            'no_value_keys': {'back_to', 'copy_symbols_from_market_data',
                              'get_cash_balance', 'toggle_indicator',
                              'write_share_size'},
            'optional_value_keys': {'count_trades'},
            'additional_value_keys': {'click_widget', 'speak_config'},
            'optional_additional_value_keys': {'write_chapter'},
            'positioning_keys': {'click', 'drag_to', 'move_to'},
            'control_flow_keys': {'is_now_after', 'is_now_before',
                                  'is_recording'},
            'preset_values_keys': {'is_now_after', 'is_now_before',
                                   'speak_seconds_since_time',
                                   'speak_seconds_until_time'},
            'preset_values': ('${Market Data:opening_time}',
                              '${Market Data:midday_break_time}',
                              '${Market Data:reopening_time}',
                              '${Market Data:closing_time}',
                              f'${{{self.process}:start_time}}',
                              f'${{{self.process}:end_time}}'),
            'preset_additional_values': None}

        self.schedules_section = f'{self.process} Schedules'

        self.mouse_listener = None
        self.keyboard_listener = None
        self.keyboard_listener_state = 0
        self.function_keys = (
            keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
            keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
            keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11,
            keyboard.Key.f12)
        self.key_to_check = None
        self.should_continue = False

        self.speech_manager = None
        self.speaking_process = None

        self.stop_listeners_event = None
        self.wait_listeners_thread = None

        self.symbol = ''
        self.initialize_attributes()

    def initialize_attributes(self):
        """Reset the symbol, cash balance, and share size to initial states."""
        self.symbol = ''
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
        if gui_state.is_interactive_window():
            if not pressed:
                action = configuration.evaluate_value(
                    config[self.process]['input_map']).get(button.name)
                if action:
                    start_execute_action_thread(self, config, gui_state,
                                                action)

    def on_press(self, key, config, gui_state):
        """Handle key press events."""
        if gui_state.is_interactive_window():
            if self.keyboard_listener_state == 0:
                if key in self.function_keys:
                    action = configuration.evaluate_value(
                        config[self.process]['input_map']).get(key.name)
                    if action:
                        start_execute_action_thread(self, config, gui_state,
                                                    action)
                        time.sleep(0.2) # TODO: Fix auto-repeat.
            elif self.keyboard_listener_state == 1:
                if ((hasattr(key, 'char') and key.char == self.key_to_check)
                    or key == self.key_to_check):
                    self.should_continue = True
                    self.keyboard_listener_state = 0
                elif key == keyboard.Key.esc:
                    self.should_continue = False
                    self.keyboard_listener_state = 0


class IndicatorThread(threading.Thread):
    """Handle a thread for displaying trading indicators."""

    def __init__(self, trade, config):
        """Construct a new IndicatorThread object."""
        super().__init__()
        self.trade = trade
        self.config = config
        self.root = None
        self.stop_event = threading.Event()

    def run(self):
        """Run the thread, creating and placing widgets on the screen."""
        def place_widget(widget, position):
            work_left, work_top, work_right, work_bottom = GetMonitorInfo(
                MonitorFromPoint((0, 0))).get('Work')
            work_center_x = int(0.5 * work_right)
            work_center_y = int(0.5 * work_bottom)
            position_map = {'n': (work_center_x, work_top),
                            'ne': (work_right, work_top),
                            'e': (work_right, work_center_y),
                            'se': (work_right, work_bottom),
                            's': (work_center_x, work_bottom),
                            'sw': (work_left, work_bottom),
                            'w': (work_left, work_center_y),
                            'nw': (work_left, work_top),
                            'center': (work_center_x, work_center_y)}
            if position in position_map:
                widget.place(x=position_map[position][0],
                             y=position_map[position][1], anchor=position)
            elif ',' in position:
                x, y = map(int, position.split(','))
                widget.place(x=x, y=y)
            else:
                print(f'Invalid position: {position}')
                widget.place(x=work_left, y=work_top)

        process_section = self.config[self.trade.process]
        widgets_section = self.config[self.trade.widgets_section]
        maximum_daily_number_of_trades = int(
            process_section['maximum_daily_number_of_trades'])

        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.8)
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', 'black')
        self.root.config(bg='black')
        self.root.overrideredirect(True)
        self.root.title(process_section['title'] + ' Indicator')

        clock_label = tk.Label(
            self.root,
            font=('Tahoma', -int(widgets_section['clock_label_font_size'])),
            bg='gray5', fg='tan1')
        place_widget(clock_label, widgets_section['clock_label_position'])
        IndicatorTooltip(clock_label, 'Current system time')

        status_bar_frame_font_size = int(
            widgets_section['status_bar_frame_font_size'])
        status_bar_frame = tk.Frame(self.root, bg='gray5')
        place_widget(status_bar_frame,
                     widgets_section['status_bar_frame_position'])

        current_number_of_trades_label = tk.Label(
            status_bar_frame, bg='gray5', fg='tan1',
            font=('Bahnschrift', -status_bar_frame_font_size), height=1,
            width=5)
        current_number_of_trades_label.grid(row=0, column=0)
        if maximum_daily_number_of_trades:
            text = 'Current number of trades / maximum daily number of trades'
        else:
            text = 'Current number of trades'

        IndicatorTooltip(current_number_of_trades_label, text)

        utilization_ratio_entry = tk.Entry(
            status_bar_frame, bd=0, bg='gray5', fg='tan1',
            font=('Bahnschrift', -status_bar_frame_font_size),
            insertbackground='tan1', justify='center', selectbackground='tan1',
            selectforeground='gray5', width=5)
        utilization_ratio_entry.grid(row=0, column=1)
        IndicatorTooltip(utilization_ratio_entry, 'Utilization ratio')

        utilization_ratio_entry.insert(0, process_section['utilization_ratio'])
        utilization_ratio_string = tk.StringVar()
        utilization_ratio_entry.bind(
            '<<Modified>>',
            lambda event: self.on_text_modified(
                event, utilization_ratio_entry, utilization_ratio_string,
                process_section, 'utilization_ratio', (RATIO_EPSILON, 1.0)))
        self.check_for_modifications(
            utilization_ratio_entry, utilization_ratio_string, process_section,
            'utilization_ratio', (RATIO_EPSILON, 1.0))

        command = self.root.register(self.is_valid_float)
        utilization_ratio_entry.config(validate='key',
                                       validatecommand=(command, '%P'))

        while not self.stop_event.is_set():
            clock_label.config(text=time.strftime('%H:%M:%S'))
            current_number_of_trades = self.config[
                self.trade.variables_section]['current_number_of_trades']
            if maximum_daily_number_of_trades:
                current_number_of_trades_label.config(
                    text=(f"{current_number_of_trades}"
                          f"/{maximum_daily_number_of_trades}"))
            else:
                current_number_of_trades_label.config(
                    text=current_number_of_trades)

            self.root.update()
            time.sleep(0.01)

        self.root.destroy()

    def check_for_modifications(self, widget, string, section, key, limits):
        """Check for modifications in the widget and update if necessary."""
        self.on_text_modified(None, widget, string, section, key, limits)
        self.root.after(
            1000,
            lambda: self.check_for_modifications(widget, string, section, key,
                                                 limits))

    def on_text_modified(self, _, widget, string, section, key, limits):
        """Handle text modification in the widget."""
        minimum_value, maximum_value = limits
        modified_text = widget.get() or '0.0'
        modified_text = max(minimum_value, min(maximum_value,
                                               float(modified_text)))
        string.set(modified_text)
        section[key] = string.get()
        configuration.write_config(self.config, self.trade.config_path,
                                   is_encrypted=True)

    def is_valid_float(self, user_input):
        """Check if the user input is a valid float."""
        if user_input == '':
            return True
        try:
            float(user_input)
            return True
        except ValueError:
            return False

    def stop(self):
        """Set the stop_event to signal the thread to stop."""
        self.stop_event.set()

    def is_stopped(self):
        """Check if the thread has been signaled to stop."""
        return self.stop_event.is_set()


class IndicatorTooltip:
    """Manage a tooltip for a specific widget."""

    def __init__(self, widget, text):
        """Construct a new IndicatorTooltip object."""
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind('<Enter>', self.show_tooltip)
        self.widget.bind('<Leave>', self.hide_tooltip)

    def show_tooltip(self, _):
        """Show the tooltip when the mouse hovers over the widget."""
        x, y, _, _ = self.widget.bbox('insert')
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.attributes('-alpha', 0.8)
        self.tooltip.attributes('-topmost', True)
        self.tooltip.geometry(f'+{x}+{y}')
        self.tooltip.overrideredirect(True)

        tk.Label(self.tooltip, bg='tan1', fg='gray5',
                 font=('Bahnschrift', -12), text=self.text).pack()

    def hide_tooltip(self, _):
        """Hide the tooltip when the mouse leaves the widget."""
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()


class MessageThread(threading.Thread):
    """Handle a thread for displaying a message in a Tkinter window."""

    def __init__(self, trade, config, text):
        """Construct a new MessageThread object."""
        super().__init__()
        self.trade = trade
        self.config = config
        self.text = text

    def run(self):
        """Run the thread, creating and displaying a message window."""
        process_section = self.config[self.trade.process]
        widgets_section = self.config[self.trade.widgets_section]

        root = tk.Tk()
        root.attributes('-alpha', 0.8)
        root.attributes('-toolwindow', True)
        root.attributes('-topmost', True)
        root.bind('<Escape>', lambda event: root.destroy())
        root.resizable(False, False)
        root.title(process_section['title'] + ' Message')
        root.withdraw()

        tk.Message(root, bg='gray5', fg='tan1',
                   font=('Bahnschrift',
                         -int(widgets_section['message_font_size'])),
                   text=self.text).pack()

        root.update()
        _, _, work_right, work_bottom = GetMonitorInfo(
            MonitorFromPoint((0, 0))).get('Work')
        root.geometry(f'+{int(0.5 * (work_right - root.winfo_width()))}'
                      f'+{int(0.5 * (work_bottom - root.winfo_height()))}')
        root.deiconify()

        root.mainloop()


def main():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(*args.P)

    file_utilities.create_launchers_exit(args, __file__)
    configure_exit(args, trade)

    config = configure(trade)
    gui_state = gui_interactions.GuiState(
        configuration.evaluate_value(
            config[trade.process]['interactive_windows']))

    if args.a or args.l or args.s:
        BaseManager.register('SpeechManager', speech_synthesis.SpeechManager)
        base_manager = BaseManager()
        base_manager.start()
        trade.speech_manager = base_manager.SpeechManager()

    if args.r:
        save_customer_margin_ratios(trade, config)
    if args.d:
        save_market_data(trade, config)
    if args.a:
        is_running = process_utilities.is_running(trade.process)
        if not (is_running and args.l):
            start_listeners(trade, config, gui_state, base_manager,
                            trade.speech_manager, is_persistent=True)

        execute_action(trade, config, gui_state,
                       config[trade.actions_section][args.a[0]])
        if not (is_running and args.l):
            process_utilities.stop_listeners(
                trade.mouse_listener, trade.keyboard_listener, base_manager,
                trade.speech_manager, trade.speaking_process)
            trade.stop_listeners_event.set()
            trade.wait_listeners_thread.join()
    if args.l and process_utilities.is_running(trade.process):
        start_listeners(trade, config, gui_state, base_manager,
                        trade.speech_manager)
    if args.s and process_utilities.is_running(trade.process):
        if not (args.a or args.l):
            trade.speaking_process = (
                speech_synthesis.start_speaking_process(
                    trade.speech_manager))

        threading.Thread(
            target=start_scheduler,
            args=(trade, config, gui_state, trade.process)).start()

        if not (args.a or args.l):
            speech_synthesis.stop_speaking_process(
                base_manager, trade.speech_manager, trade.speaking_process)


def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        '-P', nargs=2, default=('SBI Securities', 'HYPERSBI2'),
        help='set the brokerage and the process [defaults: %(default)s]',
        metavar=('BROKERAGE', 'PROCESS|EXECUTABLE_PATH'))
    parser.add_argument(
        '-r', action='store_true',
        help='save the customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    parser.add_argument(
        '-a', nargs=1,
        help='execute an action',
        metavar='ACTION')
    parser.add_argument(
        '-l', action='store_true',
        help='start the mouse and keyboard listeners')
    parser.add_argument(
        '-s', action='store_true',
        help='start the scheduler')

    file_utilities.add_launcher_options(group)
    group.add_argument(
        '-SS', action='store_true',
        help='configure the startup script, create a shortcut to it,'
        ' and exit')
    group.add_argument(
        '-A', nargs=1,
        help='configure an action, create a shortcut to it, and exit',
        metavar='ACTION')
    group.add_argument(
        '-L', action='store_true',
        help='configure the input map for buttons and keys and exit')
    group.add_argument(
        '-S', action='store_true',
        help='configure schedules and exit')
    group.add_argument(
        '-CB', action='store_true',
        help='configure the cash balance region and exit')
    group.add_argument(
        '-U', action='store_true',
        help='configure the utilization ratio of the cash balance and exit')
    group.add_argument(
        '-PL', action='store_true',
        help='configure the price limit region and exit')
    group.add_argument(
        '-DLL', action='store_true',
        help='configure the daily loss limit ratio and exit')
    group.add_argument(
        '-MDN', action='store_true',
        help='configure the maximum daily number of trades and exit')
    group.add_argument(
        '-D', nargs=1,
        help='delete the startup script or an action,'
        ' delete the shortcut to it, and exit',
        metavar='SCRIPT_BASE|ACTION')
    group.add_argument(
        '-C', action='store_true',
        help='check configuration changes and exit')

    return parser.parse_args(None if sys.argv[1:] else ['-h'])


def configure(trade, can_interpolate=True, can_override=True):
    """Set up the configuration for a trade."""
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser(interpolation=None)

    config['General'] = {
        'screencast_directory':
        os.path.join(os.path.expanduser('~'), 'Videos', trade.process.title()),
        'screencast_regex':
        (trade.process.title()
         + r' \d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}\.\d{2}\.\d+\.mp4'),
        'fingerprint': ''}
    config['Market Holidays'] = {
        'url': 'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'date_header': '日付',
        'date_format': '%Y/%m/%d'}
    config['Market Data'] = {
        'opening_time': '09:00:00',
        'midday_break_time': '11:30:00',
        'reopening_time': '12:30:00',
        'closing_time': '15:25:00',
        'delay': '20',
        'timezone': 'Asia/Tokyo',
        'url': 'https://kabutan.jp/warning/?mode=2_9&market=1',
        'number_of_pages': '2',
        'symbol_header': 'コード',
        'price_header': '株価'}
    config[trade.customer_margin_ratios_section] = {
        'customer_margin_ratio': '',
        'update_time': '',
        'timezone': '',
        'url': '',
        'symbol_header': '',
        'regulation_header': '',
        'headers': (),
        'customer_margin_ratio_string': '',
        'suspended': ''}
    config[trade.process] = {
        'start_time': '',
        'end_time': '',
        'executable': '',
        'title': '',
        'interactive_windows': (),
        'input_map': {},
        'cash_balance_region': '',
        'utilization_ratio': '',
        'price_limit_region': '',
        'daily_loss_limit_ratio': '',
        'maximum_daily_number_of_trades': '',
        'image_magnification': '',
        'binarization_threshold': '',
        'is_dark_theme': ''}
    config[trade.widgets_section] = {
        'clock_label_position': '',
        'clock_label_font_size': '',
        'status_bar_frame_position': '',
        'status_bar_frame_font_size': '',
        'message_font_size': ''}
    config[trade.startup_script_section] = {
        'pre_start_options': '',
        'post_start_options': '',
        'running_options': ''}
    config[trade.actions_section] = {
        'toggle_indicator': [
            ('toggle_indicator',)],
        'start_manual_recording': [
            ('is_recording', 'False', [
                ('press_hotkeys', 'alt, f9'),
                ('sleep', '2'),
                ('is_recording', 'False', [
                    ('speak_text', 'Not recording.')])])],
        'create_pre_trading_chapter': [
            ('write_chapter', 'Pre-trading', 'Pre-market')],
        'stop_manual_recording': [
            ('is_recording', 'True', [
                ('press_hotkeys', 'alt, f9')])],
        'speak_cpu_utilization': [
            ('speak_cpu_utilization', '1')],
        'speak_seconds_until_open': [
            ('speak_seconds_until_time', '${Market Data:opening_time}')],
        'speak_seconds_since_open': [
            ('speak_seconds_since_time', '${Market Data:opening_time}')],
        'speak_seconds_until_midday_break': [
            ('speak_seconds_until_time', '${Market Data:midday_break_time}')],
        'speak_seconds_until_reopen': [
            ('speak_seconds_until_time', '${Market Data:reopening_time}')],
        'speak_seconds_until_close': [
            ('speak_seconds_until_time', '${Market Data:closing_time}')],
        'speak_seconds_until_end': [
            ('speak_seconds_until_time', f'${{{trade.process}:end_time}}')]}
    config[trade.schedules_section] = {}
    config[trade.variables_section] = {
        'current_date': date.min.strftime('%Y-%m-%d'),
        'initial_cash_balance': '0',
        'current_number_of_trades': '0'}

    if trade.vendor == 'SBI Securities':
        config[trade.customer_margin_ratios_section] = {
            'customer_margin_ratio': '0.31',
            'update_time': '20:00:00',
            'timezone': '${Market Data:timezone}',
            'url':
            ('https://search.sbisec.co.jp/v2/popwin/attention/stock/'
             'margin_M29.html'),
            'symbol_header': 'コード',
            'regulation_header': '規制内容',
            'headers': ('銘柄', 'コード', '建玉', '信用取引区分', '規制内容'),
            'customer_margin_ratio_string': '委託保証金率',
            'suspended': '新規建停止'}

    if trade.process == 'HYPERSBI2':
        if not trade.executable:
            location_dat = os.path.join(os.path.expandvars('%LOCALAPPDATA%'),
                                        trade.vendor, trade.process,
                                        'location.dat')
            try:
                with open(location_dat, encoding='utf-8') as f:
                    trade.executable = os.path.normpath(
                        os.path.join(f.read(), trade.process + '.exe'))
            except OSError as e:
                print(e)
                for program_files in ('%ProgramFiles%', '%ProgramFiles(x86)%'):
                    executable = os.path.join(
                        os.path.expandvars(program_files), trade.vendor,
                        trade.process, trade.process + '.exe')
                    if os.path.isfile(executable):
                        trade.executable = executable
                        break
                if not trade.executable:
                    print(f'The executable file for {trade.process}'
                          ' does not exist.')
                    sys.exit(1)

        file_description = file_utilities.get_file_description(
            trade.executable)
        title = (
            data_utilities.title_except_acronyms(file_description, ['SBI'])
            + ' Assistant' if file_description
            else re.sub(r'[\W_]+', ' ', trade.script_base).strip().title())

        config[trade.process] = {
            'start_time': '${Market Data:opening_time}',
            'end_time': '${Market Data:closing_time}',
            'executable': trade.executable,
            'title': title,
            'interactive_windows': (
                file_description, 'お知らせ',
                fr'個別銘柄\s.*\(({SECURITIES_CODE_REGEX})\)', '登録銘柄',
                '保有証券', '注文一覧',
                fr'個別チャート\s.*\(({SECURITIES_CODE_REGEX})\)',
                'マーケット', 'ランキング', '銘柄一覧', '口座情報', 'ニュース',
                '取引ポップアップ', '通知設定',
                fr'全板\s.*\(({SECURITIES_CODE_REGEX})\)', r'${title}\s.*'),
            'input_map': {
                'left': '', 'middle': 'show_hide_watchlists', 'right': '',
                'x1': '', 'x2': '', 'f1': '', 'f2': '', 'f3': '', 'f4': '',
                'f5': 'show_hide_watchlists', 'f6': '', 'f7': '', 'f8': '',
                'f9': '', 'f10': 'speak_cpu_utilization', 'f11': '',
                'f12': 'toggle_indicator'},
            'cash_balance_region': '0, 0, 0, 0, 0',
            'utilization_ratio': '1.0',
            'price_limit_region': '0, 0, 0, 0, 0',
            'daily_loss_limit_ratio': '-0.01',
            'maximum_daily_number_of_trades': '0',
            'image_magnification': '2',
            'binarization_threshold': '128',
            'is_dark_theme': 'True'}
        config[trade.widgets_section] = {
            'clock_label_position': 'nw',
            'clock_label_font_size': '12',
            'status_bar_frame_position': 'sw',
            'status_bar_frame_font_size': '17',
            'message_font_size': '14'}
        config[trade.startup_script_section] = {
            'pre_start_options': '',
            'post_start_options': '-rdl',
            'running_options': '-l'}
        config[trade.actions_section]['show_hide_watchlists'] = str(
            [('show_hide_window', '登録銘柄')])

    if can_override:
        configuration.read_config(config, trade.config_path, is_encrypted=True)

    current_date = date.today()
    if (date.fromisoformat(
            config[trade.variables_section]['current_date']) != current_date):
        config[trade.variables_section]['current_date'] = str(current_date)
        config[trade.variables_section]['initial_cash_balance'] = '0'
        config[trade.variables_section]['current_number_of_trades'] = '0'

    if trade.process == 'HYPERSBI2':
        theme_config = configparser.ConfigParser(interpolation=None)
        theme_config.read(os.path.join(os.path.expandvars('%APPDATA%'),
                                       trade.vendor, trade.process,
                                       'theme.ini'))
        if (theme_config.has_option('General', 'theme')
            and theme_config['General']['theme'] == 'Light'):
            config[trade.process]['is_dark_theme'] = 'False'

    return config


def configure_exit(args, trade):
    """Configure parameters based on command-line arguments and exit."""
    config = configure(trade, can_interpolate=False)
    backup_parameters = {'number_of_backups': 8}
    trade.instruction_items['preset_additional_values'] = (
        configuration.list_section(config, trade.actions_section))

    if any((args.L, args.S, args.CB, args.U, args.PL, args.DLL, args.MDN)):
        for argument, (
                section, option, can_insert_delete, prompts, all_values, limits
        ) in {
            'L': (trade.process, 'input_map', False, {'value': 'action'},
                  trade.instruction_items.get('preset_additional_values'), ()),
            'S': (trade.schedules_section, None, True,
                  {'key': 'schedule', 'values': ('trigger', 'action'),
                   'end_of_list': 'end of schedules'},
                  (trade.instruction_items.get('preset_values'),
                   trade.instruction_items.get('preset_additional_values')),
                  ()),
            'CB': (trade.process, 'cash_balance_region', False,
                   {'value': 'x, y, width, height, index'}, None, ()),
            'U': (trade.process, 'utilization_ratio', False, None, None,
                  (RATIO_EPSILON, 1.0)),
            'PL': (trade.process, 'price_limit_region', False,
                   {'value': 'x, y, width, height, index'}, None, ()),
            'DLL': (trade.process, 'daily_loss_limit_ratio', False, None, None,
                    (-1.0, -RATIO_EPSILON)),
            'MDN': (trade.process, 'maximum_daily_number_of_trades', False,
                    None, None, (0, sys.maxsize))}.items():
            if getattr(args, argument):
                configuration.modify_section(
                    config, section, trade.config_path,
                    backup_parameters=backup_parameters,
                    can_insert_delete=can_insert_delete, option=option,
                    prompts=prompts, all_values=all_values, limits=limits,
                    is_encrypted=True)
                break

        sys.exit()
    if args.SS and configuration.modify_section(
            config, trade.startup_script_section, trade.config_path,
            backup_parameters=backup_parameters, is_encrypted=True):
        create_startup_script(trade, config)
        powershell = file_utilities.select_executable(
            ['pwsh.exe', 'powershell.exe'])
        if powershell:
            file_utilities.create_shortcut(
                trade.startup_script_base, powershell,
                f'-WindowStyle Hidden -File "{trade.startup_script}"',
                program_group_base=config[trade.process]['title'],
                icon_location=file_utilities.create_icon(
                    trade.startup_script_base,
                    icon_directory=trade.resource_directory))

        sys.exit()
    if args.A:
        if configuration.modify_option(
                config, trade.actions_section, args.A[0],
                trade.config_path, backup_parameters=backup_parameters,
                can_insert_delete=True, initial_value='[()]',
                prompts={'key': 'command', 'value': 'argument',
                         'additional_value': 'additional argument',
                         'preset_additional_value': 'action',
                         'end_of_list': 'end of commands'},
                items=trade.instruction_items, is_encrypted=True):
            powershell = file_utilities.select_executable(
                ['pwsh.exe', 'powershell.exe'])
            activate_path, interpreter = file_utilities.select_venv(
                os.path.dirname(__file__), activate='Activate.ps1')

            # To pin the shortcut to the Taskbar, specify an executable
            # file as the 'target_path' argument.
            file_utilities.create_shortcut(
                args.A[0],
                powershell if powershell else 'py.exe',
                f'-Command ". {activate_path};'
                f' {interpreter} {__file__} -a {args.A[0]}"' if activate_path
                else f'{__file__} -a {args.A[0]}',
                program_group_base=config[trade.process]['title'],
                icon_location=file_utilities.create_icon(
                    args.A[0], icon_directory=trade.resource_directory))
        else:
            file_utilities.delete_shortcut(
                args.A[0], program_group_base=config[trade.process]['title'],
                icon_location=os.path.join(trade.resource_directory,
                                           args.A[0] + '.ico'))

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
                config, trade.actions_section, base, trade.config_path,
                backup_parameters=backup_parameters, is_encrypted=True)
            create_completion(trade, config)

        file_utilities.delete_shortcut(
            base, program_group_base=config[trade.process]['title'],
            icon_location=os.path.join(trade.resource_directory,
                                       f'{base}.ico'))
        sys.exit()
    if args.C:
        configuration.check_config_changes(
            configure(trade, can_interpolate=False, can_override=False),
            trade.config_path, excluded_sections=(trade.variables_section,),
            user_option_ignored_sections=(trade.actions_section,),
            backup_parameters=backup_parameters, is_encrypted=True)
        sys.exit()


def create_completion(trade, config):
    """Generate completion scripts for options and values."""
    options = ('-a', '-A', '-D')
    trade.instruction_items['preset_additional_values'] = (
        configuration.list_section(config, trade.actions_section))

    file_utilities.create_powershell_completion(
        trade.script_base, options,
        trade.instruction_items.get('preset_additional_values'),
        ('py', 'python'),
        os.path.join(trade.resource_directory, 'completion.ps1'))
    file_utilities.create_bash_completion(
        trade.script_base, options,
        trade.instruction_items.get('preset_additional_values'),
        ('py.exe', 'python.exe'),
        os.path.join(trade.resource_directory, 'completion.sh'))


def save_customer_margin_ratios(trade, config):
    """Save customer margin ratios for a given trade."""
    section = config[trade.customer_margin_ratios_section]

    if get_latest(config, trade.market_holidays, section['update_time'],
                  section['timezone'], trade.customer_margin_ratios):
        try:
            response = requests.get(section['url'], timeout=5)
            encoding = chardet.detect(response.content)['encoding']
            dfs = pd.read_html(response.content,
                               match=section['regulation_header'],
                               flavor='lxml', header=0, encoding=encoding)
        except requests.exceptions.RequestException as e:
            print(e)
            sys.exit(1)

        df = None
        headers = configuration.evaluate_value(section['headers'])
        for index, df in enumerate(dfs):
            if tuple(df.columns.values) == headers:
                df = dfs[index][[section['symbol_header'],
                                 section['regulation_header']]]
                break
        if df is not None:
            df = df[df[section['regulation_header']].str.contains(
                f"{section['suspended']}|"
                f"{section['customer_margin_ratio_string']}")]
            df[section['regulation_header']] = df[
                section['regulation_header']].replace(
                    f".*{section['suspended']}.*", 'suspended', regex=True)
            df[section['regulation_header']] = df[
                section['regulation_header']].replace(
                    fr".*{section['customer_margin_ratio_string']}(\d+).*",
                    r'0.\1', regex=True)
            df.to_csv(trade.customer_margin_ratios, header=False, index=False)


def save_market_data(trade, config, clipboard=False):
    """Save market data for a given trade."""
    section = config['Market Data']

    if clipboard:
        latest = True
    else:
        paths = []
        delay = int(section['delay'])
        for i in range(1, 10):
            paths.append(trade.closing_prices + str(i) + '.csv')

        opening_time = (
            pd.Timestamp(section['opening_time'], tz=section['timezone'])
            + pd.Timedelta(minutes=delay)).strftime('%H:%M:%S')
        closing_time = (
            pd.Timestamp(section['closing_time'], tz=section['timezone'])
            + pd.Timedelta(minutes=delay)).strftime('%H:%M:%S')
        latest = get_latest(config, trade.market_holidays, closing_time,
                            section['timezone'], *paths,
                            volatile_time=opening_time)

    if latest:
        number_of_pages = int(section['number_of_pages'])
        dfs = []
        for i in range(number_of_pages):
            try:
                dfs.extend(pd.read_html(f"{section['url']}&page={i + 1}",
                                        match=section['symbol_header']))
            except ValueError as e:
                print(e)
                sys.exit(1)
            if i < number_of_pages - 1:
                time.sleep(1)

        df = pd.concat(dfs)
        if clipboard:
            df = df[[section['symbol_header']]]
            df.to_clipboard(index=False, header=False)
            return

        df = df[[section['symbol_header'], section['price_header']]]
        df[section['symbol_header']] = df[section['symbol_header']].astype(str)
        df.sort_values(by=section['symbol_header'], inplace=True)
        for i in range(1, 10):
            subset = df.loc[df[section['symbol_header']].str.fullmatch(
                f'{i}{SANS_INITIAL_SECURITIES_CODE_REGEX}')]
            subset.to_csv(f'{trade.closing_prices}{i}.csv', header=False,
                          index=False)


def get_latest(config, market_holidays, update_time, timezone, *paths,
               volatile_time=None):
    """Check if the latest market data needs to be fetched."""
    modified_time = pd.Timestamp(0, tz='UTC', unit='s')
    if os.path.isfile(market_holidays):
        modified_time = pd.Timestamp(os.path.getmtime(market_holidays),
                                     tz='UTC', unit='s')

    head = web_utilities.make_head_request(config['Market Holidays']['url'])
    if modified_time < pd.Timestamp(head.headers['last-modified']):
        dfs = pd.read_html(config['Market Holidays']['url'],
                           match=config['Market Holidays']['date_header'])
        df = pd.concat(dfs)[config['Market Holidays']['date_header']]
        df.replace(r'^(\d{4}/\d{2}/\d{2}).*$', r'\1', inplace=True, regex=True)
        df.to_csv(market_holidays, header=False, index=False)

    modified_time = pd.Timestamp.now(tz='UTC')
    for i, _ in enumerate(paths):
        if os.path.isfile(paths[i]):
            modified_time = min(pd.Timestamp(os.path.getmtime(paths[i]),
                                             tz='UTC', unit='s'),
                                modified_time)
        else:
            modified_time = pd.Timestamp(0, tz='UTC', unit='s')
            break

    df = pd.read_csv(market_holidays, header=None)
    # Assume the web page is updated at 'update_time'.
    latest = pd.Timestamp(update_time, tz=timezone)
    if pd.Timestamp.now(tz='UTC') < latest:
        latest -= pd.Timedelta(days=1)

    while (df[0].str.contains(latest.strftime(
            config['Market Holidays']['date_format'])).any()
           or latest.weekday() == 5 or latest.weekday() == 6):
        latest -= pd.Timedelta(days=1)

    if modified_time < latest:
        if volatile_time:
            now = pd.Timestamp.now(tz=timezone)
            if (df[0].str.contains(now.strftime(
                    config['Market Holidays']['date_format'])).any()
                or now.weekday() == 5 or now.weekday() == 6):
                return latest
            if (not pd.Timestamp(volatile_time, tz=timezone) <= now
                <= pd.Timestamp(update_time, tz=timezone)):
                return latest
        else:
            return latest
    return False


def start_scheduler(trade, config, gui_state, process):
    """Start a scheduler for executing actions at specified times."""
    scheduler = sched.scheduler(time.time, time.sleep)
    schedules = []

    section = config[trade.schedules_section]
    for option in section:
        trigger, action = configuration.evaluate_value(section[option])
        trigger = time.strptime(time.strftime('%Y-%m-%d ') + trigger,
                                '%Y-%m-%d %H:%M:%S')
        trigger = time.mktime(trigger)
        if time.time() < trigger:
            schedule = scheduler.enterabs(
                trigger, 1, execute_action,
                argument=(trade, config, gui_state,
                          config[trade.actions_section][action]))
            schedules.append(schedule)

    while scheduler.queue:
        if process_utilities.is_running(process):
            scheduler.run(False)
            time.sleep(1)
        else:
            for schedule in schedules:
                if schedule in scheduler.queue:
                    scheduler.cancel(schedule)


def start_listeners(trade, config, gui_state, base_manager, speech_manager,
                    is_persistent=False):
    """Initiate listeners for mouse and keyboard events."""
    trade.mouse_listener = mouse.Listener(
        on_click=lambda x, y, button, pressed:
        trade.on_click(x, y, button, pressed, config, gui_state))
    trade.mouse_listener.start()

    trade.keyboard_listener = keyboard.Listener(
        on_press=lambda key: trade.on_press(key, config, gui_state))
    trade.keyboard_listener.start()

    trade.speaking_process = speech_synthesis.start_speaking_process(
        speech_manager)

    trade.stop_listeners_event = threading.Event()
    trade.wait_listeners_thread = threading.Thread(
        target=process_utilities.wait_listeners,
        args=(trade.stop_listeners_event, trade.process, trade.mouse_listener,
              trade.keyboard_listener, base_manager, speech_manager,
              trade.speaking_process, is_persistent))
    trade.wait_listeners_thread.start()


def start_execute_action_thread(trade, config, gui_state, action):
    """Start a new thread to execute a specified action."""
    execute_action_thread = threading.Thread(
        target=execute_action,
        args=(trade, config, gui_state, config[trade.actions_section][action]))
    execute_action_thread.start()


def execute_action(trade, config, gui_state, action):
    """Carry out a specified action for a trade."""
    trade.initialize_attributes()
    gui_state.initialize_attributes()

    if isinstance(action, str):
        action = configuration.evaluate_value(action)

    for instruction in action:
        command = instruction[0]
        argument = instruction[1] if len(instruction) > 1 else None
        additional_argument = instruction[2] if len(instruction) > 2 else None

        if command == 'back_to':
            pyautogui.moveTo(gui_state.previous_position)
        elif command == 'calculate_share_size':
            is_successful, text = calculate_share_size(trade, config, argument)
            if not is_successful and text:
                trade.speech_manager.set_speech_text(text)
                return False
        elif command == 'check_daily_loss_limit':
            daily_loss_limit = (
                trade.cash_balance
                * float(config[trade.process]['utilization_ratio'])
                / float(config[trade.customer_margin_ratios_section][
                    'customer_margin_ratio'])
                * float(config[trade.process]['daily_loss_limit_ratio']))
            initial_cash_balance = int(
                config[trade.variables_section]['initial_cash_balance'])
            if initial_cash_balance == 0:
                config[trade.variables_section]['initial_cash_balance'] = str(
                    trade.cash_balance)
                configuration.write_config(config, trade.config_path,
                                           is_encrypted=True)
            else:
                daily_profit = trade.cash_balance - initial_cash_balance
                if daily_profit < daily_loss_limit:
                    trade.speech_manager.set_speech_text(argument)
                    return False
        elif command == 'check_maximum_daily_number_of_trades':
            if (0
                < int(config[trade.process]['maximum_daily_number_of_trades'])
                <= int(config[trade.variables_section][
                    'current_number_of_trades'])):
                trade.speech_manager.set_speech_text(argument)
                return False
        elif command == 'click':
            (pyautogui.rightClick if gui_state.swapped else pyautogui.click)(
                *map(int, argument.split(',')))
        elif command == 'click_widget':
            gui_interactions.click_widget(
                gui_state, os.path.join(trade.resource_directory, argument),
                *map(int, additional_argument.split(',')))
        elif command == 'copy_symbols_from_market_data':
            save_market_data(trade, config, clipboard=True)
        elif command == 'copy_symbols_from_column':
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(' '.join(
                text_recognition.recognize_text(
                    *map(int, argument.split(',')), None,
                    int(config[trade.process]['image_magnification']),
                    int(config[trade.process]['binarization_threshold']),
                    config[trade.process].getboolean('is_dark_theme'),
                    text_type='securities_code_column')))
            win32clipboard.CloseClipboard()
        elif command == 'count_trades':
            current_number_of_trades = int(config[trade.variables_section][
                'current_number_of_trades']) + 1
            config[trade.variables_section]['current_number_of_trades'] = str(
                current_number_of_trades)
            configuration.write_config(config, trade.config_path,
                                       is_encrypted=True)

            file_utilities.write_chapter(
                file_utilities.get_latest_file(
                    config['General']['screencast_directory'],
                    config['General']['screencast_regex']),
                (f"Trade {current_number_of_trades}"
                 f"{f' for {trade.symbol}' if trade.symbol else ''}"
                 f" at {time.strftime('%Y-%m-%d %H:%M:%S')}"),
                previous_title='Pre-trading', offset=argument)
        elif command == 'drag_to':
            pyautogui.dragTo(*map(int, argument.split(',')))
        elif command == 'get_cash_balance':
            trade.cash_balance = int(
                text_recognition.recognize_text(
                    *map(int, config[trade.process]['cash_balance_region']
                         .split(',')),
                    int(config[trade.process]['image_magnification']),
                    int(config[trade.process]['binarization_threshold']),
                    config[trade.process].getboolean('is_dark_theme')))
        elif command == 'get_symbol':
            gui_interactions.enumerate_windows(trade.get_symbol, argument)
        elif command == 'hide_window':
            gui_interactions.enumerate_windows(
                gui_interactions.hide_window, argument)
        elif command == 'move_to':
            pyautogui.moveTo(*map(int, argument.split(',')))
        elif command == 'press_hotkeys':
            pyautogui.hotkey(*tuple(map(str.strip, argument.split(','))))
        elif command == 'press_key':
            argument = tuple(map(str.strip, argument.split(',')))
            presses = int(argument[1]) if len(argument) > 1 else 1
            pyautogui.press(argument[0], presses=presses)
            if argument[0] == 'tab':
                gui_state.moved_focus = presses
        elif command == 'show_hide_window':
            gui_interactions.enumerate_windows(
                gui_interactions.show_hide_window, argument)
        elif command == 'show_window':
            gui_interactions.enumerate_windows(gui_interactions.show_window,
                                               argument)
        elif command == 'sleep':
            time.sleep(float(argument))
        elif command == 'speak_config':
            trade.speech_manager.set_speech_text(
                config[argument][additional_argument])
        elif command == 'speak_cpu_utilization':
            trade.speech_manager.set_speech_text(
                f'{round(psutil.cpu_percent(interval=float(argument)))}%.')
        elif command == 'speak_seconds_since_time':
            time_delta = math.ceil(
                time.time() - data_utilities.get_target_time(argument))
            trade.speech_manager.set_speech_text(f'{time_delta} seconds.')
        elif command == 'speak_seconds_until_time':
            time_delta = math.ceil(
                data_utilities.get_target_time(argument) - time.time())
            trade.speech_manager.set_speech_text(f'{time_delta} seconds.')
        elif command == 'speak_show_text':
            trade.speech_manager.set_speech_text(argument)
            MessageThread(trade, config, argument).start()
        elif command == 'speak_text':
            trade.speech_manager.set_speech_text(argument)
        elif command == 'toggle_indicator':
            if trade.indicator_thread:
                trade.indicator_thread.stop()
                trade.indicator_thread = None
            else:
                trade.indicator_thread = IndicatorThread(trade, config)
                trade.indicator_thread.start()
        elif command == 'wait_for_key':
            trade.keyboard_listener_state = 1
            trade.key_to_check = (argument if len(argument) == 1
                                  else keyboard.Key[argument])
            while trade.keyboard_listener_state == 1:
                time.sleep(0.001)

            if not trade.should_continue:
                for _ in range(gui_state.moved_focus):
                    pyautogui.hotkey('shift', 'tab')

                trade.speech_manager.set_speech_text('Canceled.')
                return True
        elif command == 'wait_for_price':
            text_recognition.recognize_text(
                *map(int, argument.split(',')),
                int(config[trade.process]['image_magnification']),
                int(config[trade.process]['binarization_threshold']),
                config[trade.process].getboolean('is_dark_theme'),
                text_type='decimal_numbers')
        elif command == 'wait_for_window':
            gui_interactions.wait_for_window(argument)
        elif command == 'write_chapter':
            file_utilities.write_chapter(
                file_utilities.get_latest_file(
                    config['General']['screencast_directory'],
                    config['General']['screencast_regex']),
                argument, previous_title=additional_argument)
        elif command == 'write_share_size':
            pyautogui.write(str(trade.share_size))
        elif command == 'write_string':
            pyautogui.write(argument)

        # Control Flow Commands
        elif command == 'is_now_after':
            if (data_utilities.get_target_time(argument) < time.time()
                and not recursively_execute_action(trade, config, gui_state,
                                                   additional_argument)):
                return False
        elif command == 'is_now_before':
            if (time.time() < data_utilities.get_target_time(argument)
                and not recursively_execute_action(trade, config, gui_state,
                                                   additional_argument)):
                return False
        elif command == 'is_recording':
            if (file_utilities.is_writing(
                    file_utilities.get_latest_file(
                        config['General']['screencast_directory'],
                        config['General']['screencast_regex']))
                == bool(argument.lower() == 'true')
                and not recursively_execute_action(trade, config, gui_state,
                                                   additional_argument)):
                return False

        else:
            print(command, 'is not a recognized command.')
            return False
    return True


def recursively_execute_action(trade, config, gui_state, additional_argument):
    """Recursively execute an action if it is a list or a string."""
    if isinstance(additional_argument, list):
        return execute_action(trade, config, gui_state,
                              additional_argument)
    if isinstance(additional_argument, str):
        return execute_action(
            trade, config, gui_state,
            config[trade.actions_section][additional_argument])

    print(additional_argument, 'is not a list or a string.')
    return False


def create_startup_script(trade, config):
    """Create a startup script for a trade."""
    def generate_script_lines(interpreter, script_path, options):
        """Generate lines of script for given options."""
        return [f'    {interpreter} `\n'
                f'      {script_path} `\n'
                f'      {option.strip()}\n'
                for option in options if option]

    activate_path, interpreter = file_utilities.select_venv(
        os.path.dirname(__file__), activate='Activate.ps1')
    if not interpreter:
        interpreter = 'python.exe'

    start_process = (
        '    Start-Process '
        f'"{os.path.basename(config[trade.process]["executable"])}" `\n'
        '      -WorkingDirectory '
        f'"{os.path.dirname(config[trade.process]["executable"])}"\n')
    pre_start_options = (
        config[trade.startup_script_section]['pre_start_options'].split(','))
    post_start_options = (
        config[trade.startup_script_section]['post_start_options'].split(','))
    running_options = (
        config[trade.startup_script_section]['running_options'].split(','))

    lines = []
    if activate_path:
        lines.append(f'. {activate_path}\n')

    lines.append(f'if (Get-Process "{trade.process}" '
                 '-ErrorAction SilentlyContinue) {\n')
    lines.append(f'    Stop-Process -Name "{trade.process}"\n')
    lines.append(f'    while (Get-Process "{trade.process}" '
                 '-ErrorAction SilentlyContinue) {\n')
    lines.append('        Start-Sleep -Seconds 0.1\n')
    lines.append('    }\n')
    lines.append('    Start-Sleep -Seconds 1.0\n')
    lines.append(start_process)
    lines.extend(generate_script_lines(interpreter, __file__,
                                       running_options))
    lines.append('}\n')
    lines.append('else {\n')
    lines.extend(generate_script_lines(interpreter, __file__,
                                       pre_start_options))
    lines.append(start_process)
    lines.extend(generate_script_lines(interpreter, __file__,
                                       post_start_options))
    lines.append('}\n')
    if activate_path:
        lines.append('deactivate\n')

    with open(trade.startup_script, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def calculate_share_size(trade, config, position):
    """Determine the share size for a given trade."""
    if trade.symbol and trade.cash_balance:
        customer_margin_ratio = float(config[
            trade.customer_margin_ratios_section]['customer_margin_ratio'])
        try:
            with open(trade.customer_margin_ratios, encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == trade.symbol:
                        if row[1] == 'suspended':
                            return (False, 'Margin trading suspended.')

                        customer_margin_ratio = float(row[1])
                        break
        except OSError as e:
            print(e)

        trading_unit = 100
        share_size = (int(trade.cash_balance
                          * float(config[trade.process]['utilization_ratio'])
                          / customer_margin_ratio
                          / get_price_limit(trade, config) / trading_unit)
                      * trading_unit)
        if share_size == 0:
            return (False, 'Insufficient cash balance.')

        if position == 'short' and share_size > 50 * trading_unit:
            share_size = 50 * trading_unit

        trade.share_size = share_size
        return (True, None)

    return (False, 'Symbol or cash balance not provided.')


def get_price_limit(trade, config):
    """Calculate the price limit for a trade."""
    closing_price = 0.0
    try:
        with open(f'{trade.closing_prices}{trade.symbol[0]}.csv',
                  encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == trade.symbol:
                    closing_price = float(row[1])
                    break
    except OSError as e:
        print(e)

    if closing_price:
        price_ranges = (
            (100, 30), (200, 50), (500, 80), (700, 100), (1000, 150),
            (1500, 300), (2000, 400), (3000, 500), (5000, 700), (7000, 1000),
            (10000, 1500), (15000, 3000), (20000, 4000), (30000, 5000),
            (50000, 7000), (70000, 10000), (100000, 15000), (150000, 30000),
            (200000, 40000), (300000, 50000), (500000, 70000),
            (700000, 100000), (1000000, 150000), (1500000, 300000),
            (2000000, 400000), (3000000, 500000), (5000000, 700000),
            (7000000, 1000000), (10000000, 1500000), (15000000, 3000000),
            (20000000, 4000000), (30000000, 5000000), (50000000, 7000000),
            (float('inf'), 10000000))
        for maximum_price, limit in price_ranges:
            if closing_price < maximum_price:
                price_limit = closing_price + limit
                break
    else:
        price_limit = text_recognition.recognize_text(
            *map(int, config[trade.process]['price_limit_region'].split(',')),
            int(config[trade.process]['image_magnification']),
            int(config[trade.process]['binarization_threshold']),
            config[trade.process].getboolean('is_dark_theme'),
            text_type='decimal_numbers')
    return price_limit


if __name__ == '__main__':
    main()
