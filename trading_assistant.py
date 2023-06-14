from datetime import date
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

from pynput import keyboard
from pynput import mouse
import pyautogui
import win32gui

import configuration
import file_utilities
import gui_interactions
import process_utilities
import text_recognition

class Trade:
    def __init__(self, brokerage, process):
        self.brokerage = brokerage
        self.process = process
        self.config_directory = os.path.join(
            os.path.expandvars('%LOCALAPPDATA%'),
            os.path.basename(os.path.dirname(__file__)))
        self.script_base = os.path.splitext(os.path.basename(__file__))[0]
        self.config_file = os.path.join(self.config_directory,
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

        self.customer_margin_ratio_section = \
            self.brokerage + ' Customer Margin Ratios'
        self.startup_script_section = self.process + ' Startup Script'
        self.action_section = self.process + ' Actions'
        self.categorized_keys = {
            'all_keys': file_utilities.extract_commands(
                inspect.getsource(execute_action)),
            'boolean_keys': ('is_recording',),
            'additional_value_keys': ('click_widget', 'speak_config'),
            'no_value_keys': ('back_to', 'copy_symbols_from_market_data',
                              'count_trades', 'take_screenshot',
                              'write_share_size'),
            'positioning_keys': ('click', 'move_to')}
        self.schedule_section = self.process + ' Schedules'

        # TODO
        self.keyboard_listener_state = 0
        self.function_keys = (
            keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
            keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
            keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11,
            keyboard.Key.f12)
        self.keys = {}
        self.key_to_check = None
        self.should_continue = False

        self.cash_balance = 0
        self.previous_position = pyautogui.position()
        self.share_size = 0
        self.speech_engine = None
        self.symbol = ''

    # TODO
    def on_click(self, x, y, button, pressed):
        pass

    def on_press(self, key, config, gui_callbacks):
        if gui_callbacks.is_interactive_window():
            if self.keyboard_listener_state == 0:
                print(f'First key pressed: {key}')
                if key in self.function_keys:
                    action = self.keys.get(key)
                    if action:
                        gui_callbacks.moved_focus = 0
                        execute_action_thread = threading.Thread(
                            target=execute_action,
                            args=(self, config, gui_callbacks,
                                  ast.literal_eval(
                                      config[self.action_section][action])))
                        execute_action_thread.start()
            elif self.keyboard_listener_state == 1:
                print(f'Second key pressed: {key}')
                if ((hasattr(key, 'char') and key.char == self.key_to_check)
                    or key == self.key_to_check):
                    self.should_continue = True
                    self.keyboard_listener_state = 0
                elif key == keyboard.Key.esc:
                    self.should_continue = False
                    self.keyboard_listener_state = 0

    def get_symbol(self, hwnd, title_regex):
        matched = re.fullmatch(title_regex, win32gui.GetWindowText(hwnd))
        if matched:
            self.symbol = matched.group(1)
            return

def main():
    execute_action_flag = '-a'

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-P', default=('SBI Securities', 'HYPERSBI2'),
        metavar=('BROKERAGE', 'PROCESS'), nargs=2,
        help='set a brokerage and a process [defaults: %(default)s]')
    parser.add_argument(
        '-r', action='store_true',
        help='save customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    parser.add_argument(
        '-s', action='store_true',
        help='start the scheduler')
    parser.add_argument(
        '-l', action='store_true',
        help='start the mouse and keyboard listeners')
    parser.add_argument(
        execute_action_flag, metavar='ACTION', nargs=1,
        help='execute an action')
    group.add_argument(
        '-I', action='store_true',
        help=('configure a startup script, create a shortcut to it, and exit'))
    group.add_argument(
        '-S', action='store_true',
        help='configure schedules and exit')
    group.add_argument(
        '-A', metavar='ACTION', nargs=1,
        help=('configure an action, create a shortcut to it, and exit'))
    group.add_argument(
        '-C', action='store_true',
        help=('configure the cash balance region and exit'))
    group.add_argument(
        '-B', action='store_true',
        help='configure an arbitrary cash balance and exit')
    group.add_argument(
        '-L', action='store_true',
        help=('configure the price limit region and exit'))
    group.add_argument(
        '-T', metavar='SCRIPT_BASE | ACTION', nargs=1,
        help=('delete a startup script or an action, delete a shortcut to it, '
              'and exit'))
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    trade = Trade(*args.P)
    backup_file = {'backup_function': file_utilities.backup_file,
                   'backup_parameters': {'number_of_backups': 8}}

    if args.I or args.S or args.A or args.C or args.B or args.L:
        config = configure(trade, interpolation=False)
        if args.I and configuration.modify_section(
                config, trade.startup_script_section, trade.config_file,
                **backup_file):
            create_startup_script(trade, config)
            file_utilities.create_shortcut(
                trade.script_base, 'powershell.exe',
                '-WindowStyle Hidden -File "' + trade.startup_script + '"',
                program_group_base=config[trade.process]['title'],
                icon_directory=trade.resource_directory)
            return
        elif args.S and configuration.modify_section(
                config, trade.schedule_section, trade.config_file,
                **backup_file, is_inserting=True, value_format='tuple',
                prompts={'end_of_list': 'end of commands'},
                tuple_info={'element_index': 1,
                            'possible_values': configuration.list_section(
                                config, trade.action_section)}):
            return
        elif args.A:
            if configuration.modify_tuple_list(
                    config, trade.action_section, args.A[0], trade.config_file,
                    **backup_file,
                    prompts={'key': 'command', 'value': 'argument',
                             'additional_value': 'additional argument',
                             'end_of_list': 'end of commands'},
                    categorized_keys=trade.categorized_keys):
                # To pin the shortcut to the Taskbar, specify an
                # executable file as the target_path argument.
                file_utilities.create_shortcut(
                    args.A[0], 'py.exe',
                    '"' + __file__ + '" ' + execute_action_flag + ' '
                    + args.A[0],
                    program_group_base=config[trade.process]['title'],
                    icon_directory=trade.resource_directory)
            else:
                file_utilities.delete_shortcut(
                    args.A[0],
                    program_group_base=config[trade.process]['title'],
                    icon_directory=trade.resource_directory)

            file_utilities.create_powershell_completion(
                trade.script_base, ('-a', '-A', '-T'),
                configuration.list_section(config, trade.action_section),
                'py', os.path.join(trade.resource_directory, 'completion.ps1'))
            file_utilities.create_bash_completion(
                trade.script_base, ('-a', '-A', '-T'),
                configuration.list_section(config, trade.action_section),
                'py.exe',
                os.path.join(trade.resource_directory, 'completion.sh'))
            return
        elif args.C and configuration.modify_option(
                config, trade.process, 'cash_balance_region',
                trade.config_file, **backup_file,
                prompts={'value': 'x, y, width, height, index'}):
            return
        elif args.B and configuration.modify_option(
                config, trade.process, 'fixed_cash_balance', trade.config_file,
                **backup_file):
            return
        elif args.L and configuration.modify_option(
                config, trade.process, 'price_limit_region', trade.config_file,
                **backup_file,
                prompts={'value': 'x, y, width, height, index'}):
            return

        sys.exit(1)
    else:
        config = configure(trade)

    if not config.has_section(trade.process):
        print(trade.process, 'section does not exist')
        sys.exit(1)
    else:
        gui_callbacks = gui_interactions.GuiCallbacks(
            ast.literal_eval(config[trade.process]['interactive_windows']))

    if args.r:
        if config.has_section(trade.customer_margin_ratio_section):
            save_customer_margin_ratios(trade, config)
        else:
            print(trade.customer_margin_ratio_section,
                  'section does not exist')
            sys.exit(1)
    if args.d:
        save_market_data(trade, config)
    if args.s:
        if config.has_section(trade.schedule_section):
            from multiprocessing import Process

            process = Process(
                target=start_scheduler,
                args=(trade, config, gui_callbacks, trade.process))
            process.start()
        else:
            print(trade.schedule_section, 'section does not exist')
            sys.exit(1)
    if args.l:
        if config.has_option(trade.process, 'keymap'):
            keymap = ast.literal_eval(config[trade.process]['keymap'])
            for key_name, action in keymap.items():
                key = getattr(keyboard.Key, key_name)
                trade.keys[key] = action

            start_listeners(trade, config, gui_callbacks,
                            process_utilities.is_running)
        else:
            print(option, 'option does not exist')
            sys.exit(1)
    if args.a:
        if config.has_section(trade.action_section):
            execute_action(
                trade, config, gui_callbacks,
                ast.literal_eval(config[trade.action_section][args.a[0]]))
        else:
            print(trade.action_section, 'section does not exist')
            sys.exit(1)
    if args.T:
        if args.T[0] == trade.script_base \
           and os.path.exists(trade.startup_script):
            try:
                os.remove(trade.startup_script)
            except OSError as e:
                print(e)
        else:
            configuration.delete_option(config, trade.action_section,
                                        args.T[0], trade.config_file,
                                        **backup_file)

        file_utilities.delete_shortcut(
            args.T[0], program_group_base=config[trade.process]['title'],
            icon_directory=trade.resource_directory)
        file_utilities.create_powershell_completion(
            trade.script_base, ('-a', '-A', '-T'),
            configuration.list_section(config, trade.action_section),
            'py', os.path.join(trade.resource_directory, 'completion.ps1'))
        file_utilities.create_bash_completion(
            trade.script_base, ('-a', '-A', '-T'),
            configuration.list_section(config, trade.action_section), 'py.exe',
            os.path.join(trade.resource_directory, 'completion.sh'))
        return

def configure(trade, interpolation=True):
    if interpolation:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
    else:
        config = configparser.ConfigParser()

    config['General'] = {
        'screenshot_directory':
        os.path.join(os.path.expanduser('~'), 'Pictures'),
        'screencast_directory':
        os.path.join(os.path.expanduser('~'), r'Videos\Desktop'),
        'screencast_pattern':
        r'Desktop \d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}\.\d{2}\.\d{2}\.mp4'}
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
    config['SBI Securities Customer Margin Ratios'] = {
        'update_time': '20:00:00',
        'time_zone': '${Market Data:time_zone}',
        'url': 'https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html',
        'symbol_header': 'コード',
        'regulation_header': '規制内容',
        'header': ('銘柄', 'コード', '建玉', '信用取引区分', '規制内容'),
        'customer_margin_ratio': '委託保証金率',
        'suspended': '新規建停止'}
    config['HYPERSBI2'] = {
        'executable': '',
        'title': 'Hyper SBI 2 Assistant',
        'interactive_windows': (
            'お知らせ',                    # Announcements
            '個別銘柄\s.*\((\d{4})\)',     # Summary
            '登録銘柄',                    # Watchlists
            '保有証券',                    # Holdings
            '注文一覧',                    # Order Status
            '個別チャート\s.*\((\d{4})\)', # Chart
            'マーケット',                  # Markets
            'ランキング',                  # Rankings
            '銘柄一覧',                    # Stock Lists
            '口座情報',                    # Account
            'ニュース',                    # News
            '取引ポップアップ',            # Trading
            '通知設定',                    # Notifications
            '全板\s.*\((\d{4})\)'),        # Full Order Book
        'keymap': {
            'f1': '', 'f2': '', 'f3': '', 'f4': '', 'f5': '', 'f6': '',
            'f7': '', 'f8': '', 'f9': '', 'f10': '', 'f11': '', 'f12': ''},
        'fixed_cash_balance': '0',
        'cash_balance_region': '0, 0, 0, 0, 0',
        'utilization_ratio': '1.0',
        'price_limit_region': '0, 0, 0, 0, 0',
        'image_magnification': '2',
        'binarization_threshold': '128'}
    config['HYPERSBI2 Startup Script'] = {
        'pre_start_options': '-rd',
        'post_start_options': '-s',
        'running_options': ''}
    config['HYPERSBI2 Actions'] = {}
    config['HYPERSBI2 Schedules'] = {}
    config['Variables'] = {
        'current_date': str(date.today()),
        'current_number_of_trades': '0'}
    config.read(trade.config_file, encoding='utf-8')

    if trade.process == 'HYPERSBI2':
        section = config[trade.process]

        location_dat = os.path.join(os.path.expandvars('%LOCALAPPDATA%'),
                                    trade.brokerage, trade.process,
                                    'location.dat')
        try:
            with open(location_dat, 'r') as f:
                section['executable'] = os.path.normpath(
                    os.path.join(f.read(), trade.process + '.exe'))
        except OSError as e:
            print(e)
            section['executable'] = os.path.join(
                r'$${Env:ProgramFiles(x86)}\SBI SECURITIES',
                trade.process, trade.process + '.exe')

        theme_config = configparser.ConfigParser()
        theme_ini = os.path.join(os.path.expandvars('%APPDATA%'),
                                 trade.brokerage, trade.process, 'theme.ini')
        theme_config.read(theme_ini)
        if theme_config.has_option('General', 'theme') \
           and theme_config['General']['theme'] == 'Light':
            section['currently_dark_theme'] = 'False'
        else:                   # Dark as a fallback
            section['currently_dark_theme'] = 'True'

    return config

def save_customer_margin_ratios(trade, config):
    global pd
    import pandas as pd

    section = config[trade.customer_margin_ratio_section]
    update_time = section['update_time']
    time_zone = section['time_zone']
    url = section['url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = ast.literal_eval(section['header'])
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']

    if get_latest(config, trade.market_holidays, update_time, time_zone,
                  trade.customer_margin_ratios):
        try:
            dfs = pd.read_html(url, match=regulation_header, header=0)
        except Exception as e:
            print(e)
            sys.exit(1)

        for index, df in enumerate(dfs):
            if tuple(df.columns.values) == header:
                df = dfs[index][[symbol_header, regulation_header]]
                break

        df = df[df[regulation_header].str.contains(
            suspended + '|' + customer_margin_ratio)]
        df[regulation_header].replace('.*' + suspended + '.*', 'suspended',
                                      inplace=True, regex=True)
        df[regulation_header].replace('.*' + customer_margin_ratio + '(\d+).*',
                                      r'0.\1', inplace=True, regex=True)

        df.to_csv(trade.customer_margin_ratios, header=False, index=False)

def save_market_data(trade, config, clipboard=False):
    global pd
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
                str(i) + '\d{3}5?$')]
            subset.to_csv(trade.closing_prices + str(i) + '.csv', header=False,
                          index=False)

def get_latest(config, market_holidays, update_time, time_zone, *paths,
               volatile_time=None):
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
        df.replace('^(\d{4}/\d{2}/\d{2}).*$', r'\1', inplace=True, regex=True)

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

    # Assume the web page is updated at update_time.
    now = pd.Timestamp.now(tz='UTC')
    latest = pd.Timestamp(update_time, tz=time_zone)
    if now < latest:
        latest -= pd.Timedelta(days=1)

    df = pd.read_csv(market_holidays, header=None)
    while df[0].str.contains(latest.strftime(date_format)).any() \
          or latest.weekday() == 5 or latest.weekday() == 6:
        latest -= pd.Timedelta(days=1)

    if modified_time < latest:
        if volatile_time:
            now = pd.Timestamp.now(tz=time_zone)
            if df[0].str.contains(now.strftime(date_format)).any() \
               or now.weekday() == 5 or now.weekday() == 6:
                return latest
            elif not pd.Timestamp(volatile_time, tz=time_zone) <= now \
                 <= pd.Timestamp(update_time, tz=time_zone):
                return latest
        else:
            return latest

def start_scheduler(trade, config, gui_callbacks, process):
    import sched

    scheduler = sched.scheduler(time.time, time.sleep)
    schedules = []

    section = config[trade.schedule_section]
    speech = False
    for option in section:
        schedule_time, action = ast.literal_eval(section[option])
        action = ast.literal_eval(config[trade.action_section][action])
        schedule_time = time.strptime(time.strftime('%Y-%m-%d ')
                                      + schedule_time, '%Y-%m-%d %H:%M:%S')
        schedule_time = time.mktime(schedule_time)
        if schedule_time > time.time():
            for index in range(len(action)):
                command = action[index][0]
                if command in ('speak_config', 'speak_cpu_utilization',
                               'speak_string', 'speak_seconds_until_time'):
                    speech = True

            schedule = scheduler.enterabs(
                schedule_time, 1, execute_action,
                argument=(trade, config, gui_callbacks, action))
            schedules.append(schedule)

    if speech:
        initialize_speech_engine(trade)

    while scheduler.queue:
        if process_utilities.is_running(process):
            scheduler.run(False)
            time.sleep(1)
        else:
            for schedule in schedules:
                scheduler.cancel(schedule)

# TODO
def start_listeners(trade, config, gui_callbacks, is_running_function):
    mouse_listener = mouse.Listener(on_click=trade.on_click)
    mouse_listener.start()

    keyboard_listener = keyboard.Listener(
        on_press=lambda key: trade.on_press(key, config, gui_callbacks))
    keyboard_listener.start()

    stop_listeners_thread = threading.Thread(
        target=process_utilities.stop_listeners,
        args=(trade.process, mouse_listener, keyboard_listener))
    stop_listeners_thread.start()

    # mouse_listener.join()
    # keyboard_listener.join()
    # stop_listeners_thread.join()

def execute_action(trade, config, gui_callbacks, action):
    for index in range(len(action)):
        command = action[index][0]
        if len(action[index]) > 1:
            argument = action[index][1]
        if len(action[index]) > 2:
            additional_argument = action[index][2]

        if command == 'back_to':
            pyautogui.moveTo(trade.previous_position)
        elif command == 'beep':
            import winsound

            winsound.Beep(*ast.literal_eval(argument))
        elif command == 'calculate_share_size':
            calculate_share_size(trade, config, argument)
        elif command == 'click':
            coordinates = ast.literal_eval(argument)
            if gui_callbacks.swapped:
                pyautogui.rightClick(coordinates)
            else:
                pyautogui.click(coordinates)
        elif command == 'click_widget':
            image = os.path.join(trade.resource_directory, argument)
            region = ast.literal_eval(additional_argument)
            gui_interactions.click_widget(gui_callbacks, image, *region)
        elif command == 'copy_symbols_from_market_data':
            save_market_data(trade, config, clipboard=True)
        elif command == 'copy_symbols_from_numeric_column':
            import win32clipboard

            argument = ast.literal_eval(argument)
            split_string = text_recognition.recognize_text(
                config[trade.process], *argument, None,
                text_type='numeric_column')
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(' '.join(split_string))
            win32clipboard.CloseClipboard()
        elif command == 'count_trades':
            section = config['Variables']
            previous_date = date.fromisoformat(section['current_date'])
            current_date = date.today()
            if previous_date == current_date:
                section['current_number_of_trades'] = \
                    str(int(section['current_number_of_trades']) + 1)
            else:
                section['current_date'] = str(date.today())
                section['current_number_of_trades'] = '1'

            configuration.write_config(config, trade.config_file)
        elif command == 'get_symbol':
            win32gui.EnumWindows(trade.get_symbol, argument)
        elif command == 'hide_parent_window':
            win32gui.EnumWindows(gui_interactions.hide_parent_window,
                                 argument)
        elif command == 'hide_window':
            win32gui.EnumWindows(gui_interactions.hide_window, argument)
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
                gui_callbacks.moved_focus = presses
        elif command == 'show_hide_window_on_click':
            gui_interactions.show_hide_window_on_click(
                gui_callbacks, trade.process, argument,
                process_utilities.is_running)
        elif command == 'show_hide_window':
            win32gui.EnumWindows(gui_interactions.show_hide_window, argument)
        elif command == 'show_window':
            win32gui.EnumWindows(gui_interactions.show_window, argument)
        elif command == 'speak_config':
            speak_text(trade, config[argument][additional_argument])
        elif command == 'speak_cpu_utilization':
            import psutil

            speak_text(trade,
                       str(round(psutil.cpu_percent(interval=float(argument))))
                       + '%')
        elif command == 'speak_string':
            speak_text(trade, argument)
        elif command == 'speak_seconds_until_time':
            import math

            event_time = time.strptime(time.strftime('%Y-%m-%d ') + argument,
                                       '%Y-%m-%d %H:%M:%S')
            event_time = time.mktime(event_time)
            speak_text(trade,
                       str(math.ceil(event_time - time.time())) + ' seconds')
        elif command == 'take_screenshot':
            from PIL import ImageGrab

            pyautogui.hotkey('alt', 'printscreen')
            image = ImageGrab.grabclipboard()
            section = config['Variables']
            previous_date = date.fromisoformat(section['current_date'])
            current_date = date.today()
            base = str(current_date)
            if previous_date == current_date:
                base += f"-{int(section['current_number_of_trades']):02}"
            if trade.symbol:
                base += '-' + trade.symbol

            base += '-screenshot.png'
            image.save(os.path.join(config['General']['screenshot_directory'],
                                    base))
        elif command == 'wait_for_key':
            if not gui_interactions.wait_for_key(gui_callbacks, argument):
                return
        elif command == 'wait_for_key_':
            # TODO
            trade.keyboard_listener_state = 1
            if len(argument) == 1:
                trade.key_to_check = argument
            else:
                trade.key_to_check = keyboard.Key[argument]
            while trade.keyboard_listener_state == 1:
                time.sleep(0.001)

            if not trade.should_continue:
                import winsound

                for _ in range(gui_callbacks.moved_focus):
                    pyautogui.hotkey('shift', 'tab')

                winsound.Beep(1000, 100)
                return
        elif command == 'wait_for_period':
            time.sleep(float(argument))
        elif command == 'wait_for_prices':
            argument = ast.literal_eval(argument)
            text_recognition.recognize_text(config[trade.process], *argument)
        elif command == 'wait_for_window':
            gui_interactions.wait_for_window(gui_callbacks, argument)
        elif command == 'write_share_size':
            pyautogui.write(str(trade.share_size))

        # Boolean Command
        elif command == 'is_recording':
            section = config['General']
            screencast_directory = section['screencast_directory']
            screencast_pattern = section['screencast_pattern']
            files = [f for f in os.listdir(screencast_directory)
                           if re.fullmatch(screencast_pattern, f)]
            latest = os.path.join(screencast_directory, files[-1])
            if file_utilities.is_writing(latest) == ast.literal_eval(argument):
                execute_action(trade, config, gui_callbacks,
                               additional_argument)

        else:
            print(command, 'is not a recognized command')
            sys.exit(1)

def create_startup_script(trade, config):
    def generate_start_process_lines(options):
        lines = []
        for option in options:
            if option:
                lines.append(f'    Start-Process "py.exe" -ArgumentList `\n'
                             f'      "`"{__file__}`"", `\n'
                             f'      "{option.strip()}" -NoNewWindow\n')
        return lines

    section = config[trade.startup_script_section]
    pre_start_options = section.get('pre_start_options', '').split(',')
    post_start_options = section.get('post_start_options', '').split(',')
    running_options = section.get('running_options', '').split(',')

    with open(trade.startup_script, 'w') as f:
        lines = []
        lines.append(f'if (Get-Process "{trade.process}"'
                     f' -ErrorAction SilentlyContinue)\n{{\n')
        lines.extend(generate_start_process_lines(running_options))
        lines.append('}\nelse\n{\n')
        lines.extend(generate_start_process_lines(pre_start_options))
        lines.append(f'    Start-Process `\n'
                     f'      "{config[trade.process]["executable"]}" `\n'
                     f'      -NoNewWindow\n')
        lines.extend(generate_start_process_lines(post_start_options))
        lines.append('}\n')
        f.writelines(lines)

def calculate_share_size(trade, config, position):
    section = config[trade.process]
    fixed_cash_balance = int(section['fixed_cash_balance'].replace(',', '')
                             or 0)
    if fixed_cash_balance > 0:
        trade.cash_balance = fixed_cash_balance
    else:
        region = ast.literal_eval(section['cash_balance_region'])
        trade.cash_balance = text_recognition.recognize_text(section, *region)

    customer_margin_ratio = 0.31
    try:
        with open(trade.customer_margin_ratios, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == trade.symbol:
                    if row[1] == 'suspended':
                        sys.exit()
                    else:
                        customer_margin_ratio = float(row[1])
                    break
    except OSError as e:
        print(e)

    utilization_ratio = float(section['utilization_ratio'])
    price_limit = get_price_limit(trade, config)
    trading_unit = 100
    share_size = int(trade.cash_balance * utilization_ratio
                     / customer_margin_ratio / price_limit / trading_unit) \
                     * trading_unit
    if share_size == 0:
        sys.exit()
    if position == 'short' and share_size > 50 * trading_unit:
        share_size = 50 * trading_unit

    trade.share_size = share_size

def get_price_limit(trade, config):
    closing_price = 0.0
    try:
        with open(trade.closing_prices + trade.symbol[0] + '.csv', 'r') as f:
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

def initialize_speech_engine(trade):
    if not trade.speech_engine:
        import pyttsx3

        trade.speech_engine = pyttsx3.init()
        voices = trade.speech_engine.getProperty('voices')
        trade.speech_engine.setProperty('voice', voices[1].id)

# TODO: the pyttsx3 engine is not thread-safe.
def speak_text(trade, text):
    initialize_speech_engine(trade)
    trade.speech_engine.say(text)
    trade.speech_engine.runAndWait()

if __name__ == '__main__':
    main()
