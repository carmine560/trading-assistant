from datetime import date
from multiprocessing.managers import BaseManager
import argparse
import ast
import configparser
import csv
import inspect
import os
import re
import sys
import threading
import time
import tkinter as tk

from pynput import keyboard
from pynput import mouse
from win32api import GetMonitorInfo, MonitorFromPoint
import pyautogui
import win32gui

import configuration
import file_utilities
import gui_interactions
import process_utilities
import speech_synthesis
import text_recognition

class Trade:
    def __init__(self, brokerage, process):
        self.brokerage = brokerage
        if os.path.exists(process):
            self.executable = os.path.abspath(process)
            self.process = os.path.splitext(
                os.path.basename(self.executable))[0]
        else:
            self.executable = None
            self.process = process

        self.config_directory = os.path.join(
            os.path.expandvars('%LOCALAPPDATA%'),
            os.path.basename(os.path.dirname(__file__)))
        self.script_file = os.path.basename(__file__)
        self.script_base = os.path.splitext(self.script_file)[0]
        self.config_path = os.path.join(self.config_directory,
                                        self.script_base + '.ini')
        self.market_directory = os.path.join(self.config_directory, 'market')
        self.market_holidays = os.path.join(self.market_directory,
                                            'market_holidays.csv')
        self.closing_prices = os.path.join(self.market_directory,
                                           'closing_prices_')
        self.resource_directory = os.path.join(self.config_directory,
                                               self.process)
        self.customer_margin_ratios = os.path.join(
            self.resource_directory, 'customer_margin_ratios.csv')
        self.startup_script = os.path.join(self.resource_directory,
                                           self.script_base + '.ps1')

        for directory in [self.config_directory, self.market_directory,
                          self.resource_directory]:
            file_utilities.check_directory(directory)

        self.customer_margin_ratios_title = (
            f'{self.brokerage} Customer Margin Ratios')

        self.osd_title = f'{self.process} OSD'
        self.osd_thread = None

        self.startup_script_title = f'{self.process} Startup Script'

        self.actions_title = f'{self.process} Actions'
        self.categorized_keys = {
            'all_keys': file_utilities.extract_commands(
                inspect.getsource(execute_action)),
            'control_flow_keys': ('is_now_before', 'is_recording'),
            'additional_value_keys': ('click_widget', 'speak_config',
                                      'write_chapter'),
            'no_value_keys': ('back_to', 'copy_symbols_from_market_data',
                              'count_trades', 'get_cash_balance',
                              'take_screenshot', 'toggle_osd',
                              'write_share_size'),
            'positioning_keys': ('click', 'move_to')}

        self.schedules_title = f'{self.process} Schedules'

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

        self.initialize_attributes()

    def initialize_attributes(self):
        self.symbol = ''
        self.cash_balance = 0
        self.share_size = 0

    def get_symbol(self, hwnd, title_regex):
        matched = re.fullmatch(title_regex, win32gui.GetWindowText(hwnd))
        if matched:
            self.symbol = matched.group(1)
            return False

    def on_click(self, x, y, button, pressed, config, gui_state):
        if gui_state.is_interactive_window():
            if not pressed:
                action = ast.literal_eval(
                    config[self.process]['input_map']).get(button.name)
                if action:
                    start_execute_action_thread(self, config, gui_state,
                                                action)

    def on_press(self, key, config, gui_state):
        if gui_state.is_interactive_window():
            if self.keyboard_listener_state == 0:
                if key in self.function_keys:
                    action = ast.literal_eval(
                        config[self.process]['input_map']).get(key.name)
                    if action:
                        start_execute_action_thread(self, config, gui_state,
                                                    action)
            elif self.keyboard_listener_state == 1:
                if ((hasattr(key, 'char') and key.char == self.key_to_check)
                    or key == self.key_to_check):
                    self.should_continue = True
                    self.keyboard_listener_state = 0
                elif key == keyboard.Key.esc:
                    self.should_continue = False
                    self.keyboard_listener_state = 0

class OSDThread(threading.Thread):
    # TODO: rename OSD
    def __init__(self, trade, config):
        super().__init__()
        self.trade = trade
        self.config = config
        self.root = None
        self.stop_event = threading.Event()

    def run(self):
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
        osd_section = self.config[self.trade.osd_title]
        maximum_daily_number_of_trades = int(
            process_section['maximum_daily_number_of_trades'])

        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.8)
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', 'black')
        self.root.config(bg='black')
        self.root.overrideredirect(True)
        self.root.title(process_section['title'] + ' OSD')

        clock_label = tk.Label(
            self.root,
            font=('Tahoma', -int(osd_section['clock_label_font_size'])),
            bg='gray5', fg='tan1')
        place_widget(clock_label, osd_section['clock_label_position'])
        OSDTooltip(clock_label, 'Current system time')

        status_bar_frame_font_size = int(
            osd_section['status_bar_frame_font_size'])
        status_bar_frame = tk.Frame(self.root, bg='gray5')
        place_widget(status_bar_frame,
                     osd_section['status_bar_frame_position'])

        current_number_of_trades_label = tk.Label(
            status_bar_frame, bg='gray5', fg='tan1',
            font=('Bahnschrift', -status_bar_frame_font_size), height=1,
            width=5)
        current_number_of_trades_label.grid(row=0, column=0)
        if maximum_daily_number_of_trades:
            text = 'Current number of trades / maximum daily number of trades'
        else:
            text = 'Current number of trades'

        OSDTooltip(current_number_of_trades_label, text)

        utilization_ratio_entry = tk.Entry(
            status_bar_frame, bd=0, bg='gray5', fg='tan1',
            font=('Bahnschrift', -status_bar_frame_font_size),
            insertbackground='tan1', justify='center', selectbackground='tan1',
            selectforeground='gray5', width=5)
        utilization_ratio_entry.grid(row=0, column=1)
        OSDTooltip(utilization_ratio_entry, 'Utilization ratio')

        utilization_ratio_entry.insert(0, process_section['utilization_ratio'])
        utilization_ratio_string = tk.StringVar()
        utilization_ratio_entry.bind(
            '<<Modified>>',
            lambda event: self.on_text_modified(
                event, utilization_ratio_entry, utilization_ratio_string,
                process_section, 'utilization_ratio'))
        self.check_for_modifications(
            utilization_ratio_entry, utilization_ratio_string,
            process_section, 'utilization_ratio')

        command = self.root.register(self.is_valid_float)
        utilization_ratio_entry.config(validate='key',
                                       validatecommand=(command, '%P'))

        while not self.stop_event.is_set():
            clock_label.config(text=time.strftime('%H:%M:%S'))
            current_number_of_trades = self.config['Variables'][
                'current_number_of_trades']
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

    def check_for_modifications(self, widget, string, section, key):
        self.on_text_modified(None, widget, string, section, key)
        self.root.after(
            1000,
            lambda: self.check_for_modifications(widget, string, section, key))

    def on_text_modified(self, event, widget, string, section, key):
        modified_text = widget.get()
        string.set(modified_text)
        section[key] = string.get()
        configuration.write_config(self.config, self.trade.config_path)

    def is_valid_float(self, user_input):
        if user_input == '':
            return True
        try:
            float(user_input)
            return True
        except ValueError:
            return False

    def stop(self):
        self.stop_event.set()

    def is_stopped(self):
        return self.stop_event.is_set()

class OSDTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.widget.bind('<Enter>', self.show_tooltip)
        self.widget.bind('<Leave>', self.hide_tooltip)

    def show_tooltip(self, event):
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

    def hide_tooltip(self, event):
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()

class OSDMessage(threading.Thread):
    def __init__(self, trade, config, text):
        super().__init__()
        self.trade = trade
        self.config = config
        self.text = text

    def run(self):
        process_section = self.config[self.trade.process]
        osd_section = self.config[self.trade.osd_title]

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
                         -int(osd_section['message_font_size'])),
                   text=self.text).pack()

        root.update()
        _, _, work_right, work_bottom = GetMonitorInfo(
            MonitorFromPoint((0, 0))).get('Work')
        root.geometry(f'+{int(0.5 * (work_right - root.winfo_width()))}'
                      f'+{int(0.5 * (work_bottom - root.winfo_height()))}')
        root.deiconify()

        root.mainloop()

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-P', default=('SBI Securities', 'HYPERSBI2'),
        metavar=('BROKERAGE', 'PROCESS|PATH_TO_EXECUTABLE'), nargs=2,
        help='set the brokerage and the process [defaults: %(default)s]')
    parser.add_argument(
        '-r', action='store_true',
        help='save the customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    parser.add_argument(
        '-a', metavar='ACTION', nargs=1,
        help='execute an action')
    parser.add_argument(
        '-l', action='store_true',
        help='start the mouse and keyboard listeners')
    parser.add_argument(
        '-s', action='store_true',
        help='start the scheduler')
    group.add_argument(
        '-SS', action='store_true',
        help=('configure the startup script, create a shortcut to it, '
              'and exit'))
    group.add_argument(
        '-A', metavar='ACTION', nargs=1,
        help=('configure an action, create a shortcut to it, and exit'))
    group.add_argument(
        '-L', action='store_true',
        help='configure the input map for buttons and keys and exit')
    group.add_argument(
        '-S', action='store_true',
        help='configure schedules and exit')
    group.add_argument(
        '-CB', action='store_true',
        help=('configure the cash balance region and exit'))
    group.add_argument(
        '-U', action='store_true',
        help='configure the utilization ratio of the cash balance and exit')
    group.add_argument(
        '-PL', action='store_true',
        help=('configure the price limit region and exit'))
    group.add_argument(
        '-DLL', action='store_true',
        help='configure the daily loss limit ratio and exit')
    group.add_argument(
        '-MDN', action='store_true',
        help='configure the maximum daily number of trades and exit')
    group.add_argument(
        '-D', metavar='SCRIPT_BASE|ACTION', nargs=1,
        help=('delete the startup script or an action, '
              'delete the shortcut to it, and exit'))
    group.add_argument(
        '-C', action='store_true',
        help='check configuration changes and exit')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    trade = Trade(*args.P)
    backup_file = {'backup_function': file_utilities.backup_file,
                   'backup_parameters': {'number_of_backups': 8}}

    if (args.SS or args.A or args.L or args.S or args.CB or args.U or args.PL
        or args.DLL or args.MDN):
        config = configure(trade, can_interpolate=False)
        process_section = config[trade.process]

        if args.SS and configuration.modify_section(
                config, trade.startup_script_title, trade.config_path,
                **backup_file):
            create_startup_script(trade, config)
            file_utilities.create_shortcut(
                trade.script_base, 'powershell.exe',
                '-WindowStyle Hidden -File "' + trade.startup_script + '"',
                program_group_base=process_section['title'],
                icon_directory=trade.resource_directory)
            return
        elif args.A:
            if configuration.modify_tuple_list(
                    config, trade.actions_title, args.A[0],
                    trade.config_path, **backup_file,
                    prompts={'key': 'command', 'value': 'argument',
                             'additional_value': 'additional argument',
                             'end_of_list': 'end of commands'},
                    categorized_keys=trade.categorized_keys):
                activate = None
                if os.path.exists(r'.venv\Scripts\activate.ps1'):
                    activate = r'.venv\Scripts\activate.ps1'

                # To pin the shortcut to the Taskbar, specify an executable
                # file as the 'target_path' argument.
                if activate:
                    target_path = 'powershell.exe'
                    arguments = (
                        f'-Command ". {activate}; '
                        f'python.exe {trade.script_file} -a {args.A[0]}"')
                else:
                    target_path = 'py.exe'
                    arguments = f'{trade.script_file} -a {args.A[0]}'

                file_utilities.create_shortcut(
                    args.A[0], target_path, arguments,
                    program_group_base=process_section['title'],
                    icon_directory=trade.resource_directory)
            else:
                file_utilities.delete_shortcut(
                    args.A[0],
                    program_group_base=process_section['title'],
                    icon_directory=trade.resource_directory)

            file_utilities.create_powershell_completion(
                trade.script_base, ('-a', '-A', '-D'),
                configuration.list_section(config, trade.actions_title),
                ('py', 'python'),
                os.path.join(trade.resource_directory, 'completion.ps1'))
            file_utilities.create_bash_completion(
                trade.script_base, ('-a', '-A', '-D'),
                configuration.list_section(config, trade.actions_title),
                ('py.exe', 'python.exe'),
                os.path.join(trade.resource_directory, 'completion.sh'))
            return
        elif args.L and configuration.modify_option(
                config, trade.process, 'input_map', trade.config_path,
                **backup_file,
                dictionary_info={'possible_values': configuration.list_section(
                    config, trade.actions_title)}):
            return
        elif args.S and configuration.modify_section(
                config, trade.schedules_title, trade.config_path,
                **backup_file, is_inserting=True, value_format='tuple',
                prompts={'end_of_list': 'end of schedules'},
                tuple_info={'element_index': 1,
                            'possible_values': configuration.list_section(
                                config, trade.actions_title)}):
            return
        elif args.CB and configuration.modify_option(
                config, trade.process, 'cash_balance_region',
                trade.config_path, **backup_file,
                prompts={'value': 'x, y, width, height, index'}):
            return
        elif args.U and configuration.modify_option(
                config, trade.process, 'utilization_ratio', trade.config_path,
                **backup_file):
            return
        elif args.PL and configuration.modify_option(
                config, trade.process, 'price_limit_region', trade.config_path,
                **backup_file,
                prompts={'value': 'x, y, width, height, index'}):
            return
        elif args.DLL and configuration.modify_option(
                config, trade.process, 'daily_loss_limit_ratio',
                trade.config_path, **backup_file):
            return
        elif args.MDN and configuration.modify_option(
                config, trade.process, 'maximum_daily_number_of_trades',
                trade.config_path, **backup_file):
            return

        sys.exit(1)
    elif args.C:
        default_config = configure(trade, can_interpolate=False,
                                   can_override=False)
        configuration.check_config_changes(default_config, trade.config_path,
                                           excluded_sections=('Variables',),
                                           **backup_file)
        return
    else:
        config = configure(trade)
        process_section = config[trade.process]

    gui_state = gui_interactions.GuiState(
        ast.literal_eval(process_section['interactive_windows']))

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

        execute_action(
            trade, config, gui_state,
            ast.literal_eval(config[trade.actions_title][args.a[0]]))
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

        start_scheduler_thread = threading.Thread(
            target=start_scheduler,
            args=(trade, config, gui_state, trade.process))
        start_scheduler_thread.start()

        if not (args.a or args.l):
            speech_synthesis.stop_speaking_process(
                base_manager, trade.speech_manager, trade.speaking_process)
    if args.D:
        if (args.D[0] == trade.script_base
            and os.path.exists(trade.startup_script)):
            try:
                os.remove(trade.startup_script)
            except OSError as e:
                print(e)
        else:
            configuration.delete_option(config, trade.actions_title,
                                        args.D[0], trade.config_path,
                                        **backup_file)

        file_utilities.delete_shortcut(
            args.D[0], program_group_base=process_section['title'],
            icon_directory=trade.resource_directory)
        file_utilities.create_powershell_completion(
            trade.script_base, ('-a', '-A', '-D'),
            configuration.list_section(config, trade.actions_title),
            ('py', 'python'),
            os.path.join(trade.resource_directory, 'completion.ps1'))
        file_utilities.create_bash_completion(
            trade.script_base, ('-a', '-A', '-D'),
            configuration.list_section(config, trade.actions_title),
            ('py.exe', 'python.exe'),
            os.path.join(trade.resource_directory, 'completion.sh'))
        return

def configure(trade, can_interpolate=True, can_override=True):
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser()

    if not trade.executable and trade.process == 'HYPERSBI2':
        location_dat = os.path.join(os.path.expandvars('%LOCALAPPDATA%'),
                                    trade.brokerage, trade.process,
                                    'location.dat')
        try:
            with open(location_dat) as f:
                trade.executable = os.path.normpath(
                    os.path.join(f.read(), trade.process + '.exe'))
        except OSError as e:
            print(e)
            trade.executable = os.path.join(
                os.path.expandvars('${ProgramFiles(x86)}'), trade.brokerage,
                trade.process, trade.process + '.exe')
            if not os.path.isfile(trade.executable):
                print(trade.executable, 'file does not exist.')
                sys.exit(1)

    file_description = file_utilities.get_file_description(trade.executable)
    if file_description:
        if trade.process == 'HYPERSBI2':
            file_description = file_utilities.title_except_acronyms(
                file_description, ['SBI'])

        title = file_description + ' Assistant'
    else:
        title = re.sub(r'[\W_]+', ' ', trade.script_base).strip().title()

    config['General'] = {
        'screenshot_directory':
        os.path.join(os.path.expanduser('~'), 'Pictures'),
        'screencast_directory':
        os.path.join(os.path.expanduser('~'), 'Videos', trade.process.title()),
        'screencast_regex':
        (trade.process.title()
         + r' \d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}\.\d{2}\.\d{2}\.mp4'),
        'fingerprint': ''}
    config['Market Holidays'] = {
        'url': 'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'date_header': '日付',
        'date_format': '%%Y/%%m/%%d'}
    config['Market Data'] = {
        'opening_time': '09:00:00',
        'closing_time': '15:30:00',
        'delay': '20',
        'time_zone': 'Asia/Tokyo',
        'url': 'https://kabutan.jp/warning/?mode=2_9&market=1',
        'number_of_pages': '2',
        'symbol_header': 'コード',
        'price_header': '株価'}
    config[trade.customer_margin_ratios_title] = {
        'update_time': '20:00:00',
        'time_zone': '${Market Data:time_zone}',
        'url':
        'https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html',
        'symbol_header': 'コード',
        'regulation_header': '規制内容',
        'headers': ('銘柄', 'コード', '建玉', '信用取引区分', '規制内容'),
        'customer_margin_ratio_string': '委託保証金率',
        'suspended': '新規建停止'}
    config[trade.process] = {
        # TODO: move to config[trade.customer_margin_ratios_title]
        'customer_margin_ratio': '0.31',
        'executable': trade.executable,
        'title': title,
        'interactive_windows': (),
        'input_map': {
            'left': '', 'middle': '', 'right': '', 'x1': '', 'x2': '',
            'f1': '', 'f2': '', 'f3': '', 'f4': '', 'f5': '', 'f6': '',
            'f7': '', 'f8': '', 'f9': '', 'f10': '', 'f11': '', 'f12': ''},
        'cash_balance_region': '0, 0, 0, 0, 0',
        'utilization_ratio': '1.0',
        'price_limit_region': '0, 0, 0, 0, 0',
        'daily_loss_limit_ratio': '-0.01',
        'maximum_daily_number_of_trades': '0',
        'image_magnification': '2',
        'binarization_threshold': '128',
        'is_dark_theme': 'True'}
    config[trade.osd_title] = {
        'clock_label_position': 'nw',
        'clock_label_font_size': '12',
        'status_bar_frame_position': 'sw',
        'status_bar_frame_font_size': '24',
        'message_font_size': '14'}
    config[trade.startup_script_title] = {
        'pre_start_options': '',
        'post_start_options': '',
        'running_options': ''}
    config[trade.actions_title] = {}
    config[trade.schedules_title] = {}
    config['Variables'] = {
        'current_date': date.min.strftime('%Y-%m-%d'),
        'initial_cash_balance': '0',
        'current_number_of_trades': '0'}

    # TODO: contextual prompt
    # TODO: categorized_keys, etc.

    process_section = config[trade.process]
    variables_section = config['Variables']

    SECURITIES_CODE_REGEX = (
        r'[1-9][\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?')
    if trade.process == 'HYPERSBI2':
        process_section['interactive_windows'] = str((
            file_description, 'お知らせ',
            fr'個別銘柄\s.*\(({SECURITIES_CODE_REGEX})\)', '登録銘柄',
            '保有証券', '注文一覧',
            fr'個別チャート\s.*\(({SECURITIES_CODE_REGEX})\)',
            'マーケット', 'ランキング', '銘柄一覧', '口座情報', 'ニュース',
            '取引ポップアップ', '通知設定',
            fr'全板\s.*\(({SECURITIES_CODE_REGEX})\)', r'${title}\s.*'))
        process_section['input_map'] = str({
            'left': '', 'middle': 'show_hide_watchlists', 'right': '',
            'x1': '', 'x2': '', 'f1': '', 'f2': '', 'f3': '', 'f4': '',
            'f5': 'show_hide_watchlists', 'f6': '', 'f7': '', 'f8': '',
            'f9': '', 'f10': 'speak_cpu_utilization', 'f11': '',
            'f12': 'toggle_osd'})
        # Directly assigning a new dictionary to 'config[trade.SECTION_TITLE]'
        # updates the original dictionary.
        config[trade.startup_script_title] = {
            'pre_start_options': '-rd',
            'post_start_options': '-l',
            'running_options': '-a show_hide_watchlists'}
        config[trade.actions_title] = {
            'create_pre_trading_chapter': [
                ('write_chapter', 'Pre-Trading', 'Pre-Market')],
            'show_hide_watchlists': [
                ('show_hide_window', '登録銘柄')],
            'speak_cpu_utilization': [
                ('speak_cpu_utilization', '1')],
            'speak_seconds_until_open': [
                ('speak_seconds_until_time', '${Market Data:opening_time}')],
            'start_manual_recording': [
                ('is_recording', 'False', [
                    ('press_hotkeys', 'alt, f9'),
                    ('sleep', '2'),
                    ('is_recording', 'False', [
                        ('speak_text', 'Not recording.')])])],
            'stop_manual_recording': [
                ('is_recording', 'True', [
                    ('press_hotkeys', 'alt, f9')])],
            'toggle_osd': [
                ('toggle_osd',)]}

    if can_override:
        configuration.read_config(config, trade.config_path)

        previous_date = date.fromisoformat(variables_section['current_date'])
        current_date = date.today()
        if previous_date != current_date:
            variables_section['current_date'] = str(date.today())
            variables_section['initial_cash_balance'] = '0'
            variables_section['current_number_of_trades'] = '0'

        if trade.process == 'HYPERSBI2':
            theme_config = configparser.ConfigParser()
            theme_ini = os.path.join(os.path.expandvars('%APPDATA%'),
                                     trade.brokerage, trade.process,
                                     'theme.ini')
            theme_config.read(theme_ini)
            if (theme_config.has_option('General', 'theme')
                and theme_config['General']['theme'] == 'Light'):
                process_section['is_dark_theme'] = 'False'

    return config

def save_customer_margin_ratios(trade, config):
    import chardet
    import pandas as pd
    import requests

    section = config[trade.customer_margin_ratios_title]
    update_time = section['update_time']
    time_zone = section['time_zone']
    url = section['url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    headers = ast.literal_eval(section['headers'])
    customer_margin_ratio_string = section['customer_margin_ratio_string']
    suspended = section['suspended']

    if get_latest(config, trade.market_holidays, update_time, time_zone,
                  trade.customer_margin_ratios):
        try:
            response = requests.get(url)
            encoding = chardet.detect(response.content)['encoding']
            dfs = pd.read_html(response.content, match=regulation_header,
                               flavor='lxml', header=0, encoding=encoding)
        except Exception as e:
            print(e)
            sys.exit(1)

        for index, df in enumerate(dfs):
            if tuple(df.columns.values) == headers:
                df = dfs[index][[symbol_header, regulation_header]]
                break

        df = df[df[regulation_header].str.contains(
            suspended + '|' + customer_margin_ratio_string)]
        df[regulation_header] = df[regulation_header].replace(
            '.*' + suspended + '.*', 'suspended', regex=True)
        df[regulation_header] = df[regulation_header].replace(
            '.*' + customer_margin_ratio_string + r'(\d+).*', r'0.\1',
            regex=True)

        df.to_csv(trade.customer_margin_ratios, header=False, index=False)

def save_market_data(trade, config, clipboard=False):
    import pandas as pd

    section = config['Market Data']
    opening_time = section['opening_time']
    closing_time = section['closing_time']
    delay = int(section['delay'])
    time_zone = section['time_zone']
    url = section['url']
    number_of_pages = int(section['number_of_pages'])
    symbol_header = section['symbol_header']
    price_header = section['price_header']

    if clipboard:
        latest = True
    else:
        paths = []
        for i in range(1, 10):
            paths.append(trade.closing_prices + str(i) + '.csv')

        opening_time = (pd.Timestamp(opening_time, tz=time_zone)
                        + pd.Timedelta(minutes=delay)).strftime('%H:%M:%S')
        closing_time = (pd.Timestamp(closing_time, tz=time_zone)
                        + pd.Timedelta(minutes=delay)).strftime('%H:%M:%S')
        latest = get_latest(config, trade.market_holidays, closing_time,
                            time_zone, *paths, volatile_time=opening_time)

    if latest:
        dfs = []
        for i in range(number_of_pages):
            try:
                dfs = dfs + pd.read_html(url + '&page=' + str(i + 1),
                                         match=symbol_header)
            except Exception as e:
                print(e)
                sys.exit(1)
            if i < number_of_pages - 1:
                time.sleep(1)

        df = pd.concat(dfs)
        if clipboard:
            df = df[[symbol_header]]
            df.to_clipboard(index=False, header=False)
            return
        else:
            df = df[[symbol_header, price_header]]
            df.sort_values(by=symbol_header, inplace=True)

        for i in range(1, 10):
            subset = df.loc[df[symbol_header].astype(str).str.match(
                str(i)
                + r'[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?$')]
            subset.to_csv(trade.closing_prices + str(i) + '.csv', header=False,
                          index=False)

def get_latest(config, market_holidays, update_time, time_zone, *paths,
               volatile_time=None):
    import pandas as pd
    import requests

    section = config['Market Holidays']
    url = section['url']
    date_header = section['date_header']
    date_format = re.sub('%%', '%', section['date_format'])

    modified_time = pd.Timestamp(0, tz='UTC', unit='s')
    if os.path.exists(market_holidays):
        modified_time = pd.Timestamp(os.path.getmtime(market_holidays),
                                     tz='UTC', unit='s')

    head = requests.head(url)
    try:
        head.raise_for_status()
    except Exception as e:
        print(e)
        sys.exit(1)

    if modified_time < pd.Timestamp(head.headers['last-modified']):
        dfs = pd.read_html(url, match=date_header)
        df = pd.concat(dfs)[date_header]
        df.replace(r'^(\d{4}/\d{2}/\d{2}).*$', r'\1', inplace=True,
                   regex=True)

        df.to_csv(market_holidays, header=False, index=False)

    oldest_modified_time = pd.Timestamp.now(tz='UTC')
    for i in range(len(paths)):
        if os.path.exists(paths[i]):
            modified_time = pd.Timestamp(os.path.getmtime(paths[i]), tz='UTC',
                                         unit='s')
            if modified_time < oldest_modified_time:
                oldest_modified_time = modified_time
        else:
            modified_time = pd.Timestamp(0, tz='UTC', unit='s')
            break

    # Assume the web page is updated at 'update_time'.
    now = pd.Timestamp.now(tz='UTC')
    latest = pd.Timestamp(update_time, tz=time_zone)
    if now < latest:
        latest -= pd.Timedelta(days=1)

    df = pd.read_csv(market_holidays, header=None)
    while (df[0].str.contains(latest.strftime(date_format)).any()
           or latest.weekday() == 5 or latest.weekday() == 6):
        latest -= pd.Timedelta(days=1)

    if modified_time < latest:
        if volatile_time:
            now = pd.Timestamp.now(tz=time_zone)
            if (df[0].str.contains(now.strftime(date_format)).any()
                or now.weekday() == 5 or now.weekday() == 6):
                return latest
            elif (not pd.Timestamp(volatile_time, tz=time_zone) <= now
                  <= pd.Timestamp(update_time, tz=time_zone)):
                return latest
        else:
            return latest

def start_scheduler(trade, config, gui_state, process):
    import sched

    scheduler = sched.scheduler(time.time, time.sleep)
    schedules = []

    section = config[trade.schedules_title]
    for option in section:
        schedule_time, action = ast.literal_eval(section[option])
        action = ast.literal_eval(config[trade.actions_title][action])
        schedule_time = time.strptime(time.strftime('%Y-%m-%d ')
                                      + schedule_time, '%Y-%m-%d %H:%M:%S')
        schedule_time = time.mktime(schedule_time)
        if time.time() < schedule_time:
            schedule = scheduler.enterabs(
                schedule_time, 1, execute_action,
                argument=(trade, config, gui_state, action))
            schedules.append(schedule)

    while scheduler.queue:
        if process_utilities.is_running(process):
            scheduler.run(False)
            time.sleep(1)
        else:
            for schedule in schedules:
                scheduler.cancel(schedule)

def start_listeners(trade, config, gui_state, base_manager, speech_manager,
                    is_persistent=False):
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
    execute_action_thread = threading.Thread(
        target=execute_action,
        args=(trade, config, gui_state,
              ast.literal_eval(config[trade.actions_title][action])))
    # TODO: Python 3.12.0: RuntimeError: can't create new thread at interpreter
    # shutdown
    execute_action_thread.start()

def execute_action(trade, config, gui_state, action):
    def get_latest_screencast():
        section = config['General']
        screencast_directory = section['screencast_directory']
        screencast_regex = section['screencast_regex']
        files = [f for f in os.listdir(screencast_directory)
                           if re.fullmatch(screencast_regex, f)]
        return os.path.join(screencast_directory, files[-1])

    trade.initialize_attributes()
    gui_state.initialize_attributes()

    for index in range(len(action)):
        command = action[index][0]
        if len(action[index]) > 1:
            argument = action[index][1]
        if len(action[index]) > 2:
            additional_argument = action[index][2]

        if command == 'back_to':
            pyautogui.moveTo(gui_state.previous_position)
        elif command == 'beep':
            import winsound

            winsound.Beep(*ast.literal_eval(argument))
        elif command == 'calculate_share_size':
            is_successful, text = calculate_share_size(trade, config, argument)
            if not is_successful and text:
                trade.speech_manager.set_speech_text(text)
                return False
        elif command == 'check_daily_loss_limit':
            section = config[trade.process]
            daily_loss_limit = (trade.cash_balance
                                * float(section['utilization_ratio'])
                                / float(section['customer_margin_ratio'])
                                * float(section['daily_loss_limit_ratio']))

            section = config['Variables']
            initial_cash_balance = int(section['initial_cash_balance'])
            if initial_cash_balance == 0:
                section['initial_cash_balance'] = str(trade.cash_balance)
                configuration.write_config(config, trade.config_path)
            else:
                daily_profit = (trade.cash_balance - initial_cash_balance)
                if daily_profit < daily_loss_limit:
                    trade.speech_manager.set_speech_text(argument)
                    return False
        elif command == 'check_maximum_daily_number_of_trades':
            if (0
                < int(config[trade.process]['maximum_daily_number_of_trades'])
                <= int(config['Variables']['current_number_of_trades'])):
                trade.speech_manager.set_speech_text(argument)
                return False
        elif command == 'click':
            coordinates = ast.literal_eval(argument)
            if gui_state.swapped:
                pyautogui.rightClick(coordinates)
            else:
                pyautogui.click(coordinates)
        elif command == 'click_widget':
            image = os.path.join(trade.resource_directory, argument)
            region = ast.literal_eval(additional_argument)
            gui_interactions.click_widget(gui_state, image, *region)
        elif command == 'copy_symbols_from_market_data':
            save_market_data(trade, config, clipboard=True)
        elif command == 'copy_symbols_from_column':
            import win32clipboard

            argument = ast.literal_eval(argument)
            split_string = text_recognition.recognize_text(
                config[trade.process], *argument, None,
                text_type='securities_code_column')
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(' '.join(split_string))
            win32clipboard.CloseClipboard()
        elif command == 'count_trades':
            section = config['Variables']
            previous_number_of_trades = int(
                section['current_number_of_trades'])
            current_number_of_trades = previous_number_of_trades + 1
            section['current_number_of_trades'] = str(current_number_of_trades)
            configuration.write_config(config, trade.config_path)

            title = (f"Trade {current_number_of_trades}"
                     f"{f' for {trade.symbol}' if trade.symbol else ''}"
                     f" at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            file_utilities.write_chapter(get_latest_screencast(), title,
                                         'Pre-Trading')
        elif command == 'drag_to':
            pyautogui.dragTo(ast.literal_eval(argument))
        elif command == 'get_cash_balance':
            section = config[trade.process]
            region = ast.literal_eval(section['cash_balance_region'])
            trade.cash_balance = int(text_recognition.recognize_text(section,
                                                                     *region))
        elif command == 'get_symbol':
            gui_interactions.enumerate_windows(trade.get_symbol, argument)
        elif command == 'hide_window':
            gui_interactions.enumerate_windows(
                gui_interactions.hide_window, argument)
        elif command == 'move_to':
            pyautogui.moveTo(ast.literal_eval(argument))
        elif command == 'press_hotkeys':
            keys = tuple(map(str.strip, argument.split(',')))
            pyautogui.hotkey(*keys)
        elif command == 'press_key':
            argument = tuple(map(str.strip, argument.split(',')))
            key = argument[0]
            if len(argument) > 1:
                presses = int(argument[1])
            else:
                presses = 1

            pyautogui.press(key, presses=presses)
            if key == 'tab':
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
            import psutil

            trade.speech_manager.set_speech_text(
                f'{round(psutil.cpu_percent(interval=float(argument)))}%.')
        elif command == 'speak_seconds_until_time':
            import math

            event_time = time.strptime(time.strftime('%Y-%m-%d ') + argument,
                                       '%Y-%m-%d %H:%M:%S')
            event_time = time.mktime(event_time)
            trade.speech_manager.set_speech_text(
                f'{math.ceil(event_time - time.time())} seconds.')
        elif command == 'speak_show_text':
            trade.speech_manager.set_speech_text(argument)
            OSDMessage(trade, config, argument).start()
        elif command == 'speak_text':
            trade.speech_manager.set_speech_text(argument)
        elif command == 'take_screenshot':
            section = config['Variables']
            base = section['current_date']
            base += f"-{int(section['current_number_of_trades']):02}"
            if trade.symbol:
                base += f'-{trade.symbol}'

            base += '-screenshot.png'
            pyautogui.screenshot(
                os.path.join(config['General']['screenshot_directory'], base))
        elif command == 'toggle_osd':
            if trade.osd_thread:
                trade.osd_thread.stop()
                trade.osd_thread = None
            else:
                trade.osd_thread = OSDThread(trade, config)
                trade.osd_thread.start()
        elif command == 'wait_for_key':
            trade.keyboard_listener_state = 1
            if len(argument) == 1:
                trade.key_to_check = argument
            else:
                trade.key_to_check = keyboard.Key[argument]
            while trade.keyboard_listener_state == 1:
                time.sleep(0.001)

            if not trade.should_continue:
                for _ in range(gui_state.moved_focus):
                    pyautogui.hotkey('shift', 'tab')

                trade.speech_manager.set_speech_text('Canceled.')
                return
        elif command == 'wait_for_price':
            argument = ast.literal_eval(argument)
            text_recognition.recognize_text(config[trade.process], *argument,
                                            text_type='decimal_numbers')
        elif command == 'wait_for_window':
            gui_interactions.wait_for_window(argument)
        elif command == 'write_chapter':
            file_utilities.write_chapter(get_latest_screencast(), argument,
                                         additional_argument)
        elif command == 'write_share_size':
            pyautogui.write(str(trade.share_size))
        elif command == 'write_string':
            pyautogui.write(argument)

        # Control Flow Commands
        elif command == 'is_now_before':
            target_time = time.strptime(time.strftime('%Y-%m-%d ')
                                        + argument, '%Y-%m-%d %H:%M:%S')
            target_time = time.mktime(target_time)
            if time.time() < target_time:
                execute_action(trade, config, gui_state, additional_argument)
        elif command == 'is_recording':
            if (file_utilities.is_writing(get_latest_screencast())
                == ast.literal_eval(argument)):
                execute_action(trade, config, gui_state, additional_argument)

        else:
            print(command, 'is not a recognized command.')
            return False

def create_startup_script(trade, config):
    def generate_start_process_lines(options):
        lines = []
        activate = None
        if os.path.exists(r'.venv\Scripts\Activate.ps1'):
            activate = r'.venv\Scripts\Activate.ps1'

        parameters = '-WorkingDirectory "$workingDirectory" -NoNewWindow'
        for option in options:
            if option:
                if activate:
                    lines.append(
                        f'    Start-Process powershell.exe `\n'
                        f'      -ArgumentList "{activate};", `\n'
                        f'      "python.exe {trade.script_file} '
                        f'{option.strip()}" `\n'
                        f'      {parameters}\n')
                else:
                    lines.append(
                        f'    Start-Process py.exe `\n'
                        f'      -ArgumentList "{trade.script_file} '
                        f'{option.strip()}" `\n'
                        f'      {parameters}\n')
        return lines

    section = config[trade.startup_script_title]
    pre_start_options = section.get('pre_start_options', '').split(',')
    post_start_options = section.get('post_start_options', '').split(',')
    running_options = section.get('running_options', '').split(',')

    with open(trade.startup_script, 'w') as f:
        lines = []
        lines.append(f'$workingDirectory = "{os.path.dirname(__file__)}"\n'
                     f'\n'
                     f'if (Get-Process "{trade.process}" '
                     f'-ErrorAction SilentlyContinue) {{\n')
        lines.extend(generate_start_process_lines(running_options))
        lines.append('}\nelse {\n')
        lines.extend(generate_start_process_lines(pre_start_options))
        lines.append(f'    Start-Process `\n'
                     f'      "{config[trade.process]["executable"]}" `\n'
                     f'      -NoNewWindow\n')
        lines.extend(generate_start_process_lines(post_start_options))
        lines.append('}\n')
        f.writelines(lines)

def calculate_share_size(trade, config, position):
    if trade.symbol and trade.cash_balance:
        section = config[trade.process]

        customer_margin_ratio = float(section['customer_margin_ratio'])
        try:
            with open(trade.customer_margin_ratios) as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == trade.symbol:
                        if row[1] == 'suspended':
                            return (False, 'Margin trading suspended.')
                        else:
                            customer_margin_ratio = float(row[1])
                        break
        except OSError as e:
            print(e)

        utilization_ratio = float(section['utilization_ratio'])
        price_limit = get_price_limit(trade, config)
        trading_unit = 100
        share_size = (int(trade.cash_balance * utilization_ratio
                          / customer_margin_ratio / price_limit / trading_unit)
                      * trading_unit)
        if share_size == 0:
            return (False, 'Insufficient cash balance.')
        else:
            if position == 'short' and share_size > 50 * trading_unit:
                share_size = 50 * trading_unit

            trade.share_size = share_size
            return (True, None)
    else:
        return (False, 'Symbol or cash balance not provided.')

def get_price_limit(trade, config):
    closing_price = 0.0
    try:
        with open(trade.closing_prices + trade.symbol[0] + '.csv') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == trade.symbol:
                    closing_price = float(row[1])
                    break
    except OSError as e:
        print(e)

    if closing_price:
        if closing_price < 100:
            price_limit = closing_price + 30
        elif closing_price < 200:
            price_limit = closing_price + 50
        elif closing_price < 500:
            price_limit = closing_price + 80
        elif closing_price < 700:
            price_limit = closing_price + 100
        elif closing_price < 1000:
            price_limit = closing_price + 150
        elif closing_price < 1500:
            price_limit = closing_price + 300
        elif closing_price < 2000:
            price_limit = closing_price + 400
        elif closing_price < 3000:
            price_limit = closing_price + 500
        elif closing_price < 5000:
            price_limit = closing_price + 700
        elif closing_price < 7000:
            price_limit = closing_price + 1000
        elif closing_price < 10000:
            price_limit = closing_price + 1500
        elif closing_price < 15000:
            price_limit = closing_price + 3000
        elif closing_price < 20000:
            price_limit = closing_price + 4000
        elif closing_price < 30000:
            price_limit = closing_price + 5000
        elif closing_price < 50000:
            price_limit = closing_price + 7000
        elif closing_price < 70000:
            price_limit = closing_price + 10000
        elif closing_price < 100000:
            price_limit = closing_price + 15000
        elif closing_price < 150000:
            price_limit = closing_price + 30000
        elif closing_price < 200000:
            price_limit = closing_price + 40000
        elif closing_price < 300000:
            price_limit = closing_price + 50000
        elif closing_price < 500000:
            price_limit = closing_price + 70000
        elif closing_price < 700000:
            price_limit = closing_price + 100000
        elif closing_price < 1000000:
            price_limit = closing_price + 150000
        elif closing_price < 1500000:
            price_limit = closing_price + 300000
        elif closing_price < 2000000:
            price_limit = closing_price + 400000
        elif closing_price < 3000000:
            price_limit = closing_price + 500000
        elif closing_price < 5000000:
            price_limit = closing_price + 700000
        elif closing_price < 7000000:
            price_limit = closing_price + 1000000
        elif closing_price < 10000000:
            price_limit = closing_price + 1500000
        elif closing_price < 15000000:
            price_limit = closing_price + 3000000
        elif closing_price < 20000000:
            price_limit = closing_price + 4000000
        elif closing_price < 30000000:
            price_limit = closing_price + 5000000
        elif closing_price < 50000000:
            price_limit = closing_price + 7000000
        else:
            price_limit = closing_price + 10000000
    else:
        section = config[trade.process]
        region = ast.literal_eval(section['price_limit_region'])
        price_limit = text_recognition.recognize_text(
            section, *region, text_type='decimal_numbers')
    return price_limit

if __name__ == '__main__':
    main()
