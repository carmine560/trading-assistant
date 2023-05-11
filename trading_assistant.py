from datetime import date
import argparse
import ast
import configparser
import csv
import os
import re
import sys
import time

from pynput import keyboard
import pyautogui
import pytesseract
import win32gui

import configuration
import file_utilities
import gui_interactions

class Trade:
    def __init__(self, process_name):
        config_directory = os.path.join(
            os.path.expandvars('%LOCALAPPDATA%'),
            os.path.basename(os.path.dirname(__file__)))
        self.market_directory = os.path.join(config_directory, 'market')
        self.process_name = process_name
        self.config_directory = os.path.join(config_directory,
                                             self.process_name)
        self.script_base = os.path.splitext(os.path.basename(__file__))[0]
        self.config_file = os.path.join(self.config_directory,
                                        self.script_base + '.ini')
        self.startup_script = os.path.join(self.config_directory,
                                           self.script_base + '.ps1')

        self.previous_position = pyautogui.position()
        self.cash_balance = 0
        self.symbol = ''
        self.share_size = 0

        self.speech_engine = None

    def get_symbol(self, hwnd, title_regex):
        matched = re.fullmatch(title_regex, win32gui.GetWindowText(hwnd))
        if matched:
            self.symbol = matched.group(1)
            return

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-p', default='HYPERSBI2', metavar='PROCESS_NAME',
        help='set a process name '
        '(this requires its configurations; default: %(default)s)')
    parser.add_argument(
        '-r', action='store_true',
        help='save customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    parser.add_argument(
        '-s', action='store_true',
        help='run the scheduler')
    group.add_argument(
        '-M', const='LIST_ACTIONS', metavar='ACTION', nargs='?',
        help=('create or modify an action and create a shortcut to it'))
    group.add_argument(
        '-e', const='LIST_ACTIONS', metavar='ACTION', nargs='?',
        help='execute an action')
    group.add_argument(
        '-T', const='LIST_ACTIONS', metavar='SCRIPT_BASE | ACTION', nargs='?',
        help=('delete a startup script or an action and a shortcut to it'))
    parser.add_argument(
        '-I', action='store_true',
        help=('create or modify a startup script and create a shortcut to it'))
    parser.add_argument(
        '-B', action='store_true',
        help='set an arbitrary cash balance')
    parser.add_argument(
        '-C', action='store_true',
        help=('set the cash balance region and the index of the price'))
    parser.add_argument(
        '-L', action='store_true',
        help=('set the price limit region and the index of the price'))
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    trade = Trade(args.p)
    config = configure(trade)
    if not config.has_section(trade.process_name):
        print(trade.process_name, 'section does not exist')
        sys.exit(1)

    gui_callbacks = gui_interactions.GuiCallbacks(
        ast.literal_eval(config[trade.process_name]['interactive_windows']))

    if args.r:
        save_customer_margin_ratios(trade, config)
    if args.d:
        save_market_data(config)
    if args.s:
        from multiprocessing import Process

        process = Process(
            target=run_scheduler,
            args=(trade, config, gui_callbacks, trade.process_name + '.exe'))
        process.start()
    if args.M == 'LIST_ACTIONS':
        configuration.list_section(config, 'Actions')
    elif args.M:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        if configuration.modify_tuple_option(
                config, 'Actions', args.M, trade.config_file,
                key_prompt='command', value_prompt='argument',
                additional_value_prompt='additional argument',
                end_of_list_prompt='end of commands',
                boolean_keys=['writing_file'],
                additional_value_keys=['click_widget', 'speak_config'],
                no_value_keys=['back_to', 'copy_symbols_from_market_data',
                               'count_trades', 'take_screenshot',
                               'write_share_size'],
                positioning_keys=['click', 'move_to']):
            # To pin the shortcut to the Taskbar, specify an
            # executable file as the argument target_path.
            file_utilities.create_shortcut(
                args.M, 'py.exe', '"' + __file__ + '" -e ' + args.M,
                program_group_base=config[trade.process_name]['title'],
                icon_directory=trade.config_directory)
        else:
            file_utilities.delete_shortcut(
                args.M, program_group_base=config[trade.process_name]['title'],
                icon_directory=trade.config_directory)
    if args.e == 'LIST_ACTIONS':
        configuration.list_section(config, 'Actions')
    elif args.e:
        execute_action(trade, config, gui_callbacks,
                       ast.literal_eval(config['Actions'][args.e]))
    if args.T == 'LIST_ACTIONS':
        if os.path.exists(trade.startup_script):
            print(trade.script_base)
            configuration.list_section(config, 'Actions')
    elif args.T:
        if args.T == trade.script_base \
           and os.path.exists(trade.startup_script):
            try:
                os.remove(trade.startup_script)
            except OSError as e:
                print(e)
                sys.exit(1)
        else:
            file_utilities.backup_file(trade.config_file, number_of_backups=8)
            configuration.delete_option(config, 'Actions', args.T,
                                        trade.config_file)

        file_utilities.delete_shortcut(
            args.T, program_group_base=config[trade.process_name]['title'],
            icon_directory=trade.config_directory)
    if args.I:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        configuration.modify_section(config, 'Startup Script',
                                     trade.config_file)
        create_startup_script(trade, config)
        file_utilities.create_shortcut(
            trade.script_base, 'powershell.exe',
            '-WindowStyle Hidden -File "' + trade.startup_script + '"',
            program_group_base=config[trade.process_name]['title'],
            icon_directory=trade.config_directory)
    if args.B:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        configuration.modify_option(config, trade.process_name,
                                    'fixed_cash_balance', trade.config_file)
    if args.C:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        configuration.modify_option(config, trade.process_name,
                                    'cash_balance_region', trade.config_file,
                                    value_prompt='x, y, width, height, index')
    if args.L:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        configuration.modify_option(config, trade.process_name,
                                    'price_limit_region', trade.config_file,
                                    value_prompt='x, y, width, height, index')

def configure(trade):
    config = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation())
    config['General'] = {
        'market_directory': trade.market_directory,
        'config_directory': trade.config_directory,
        'screenshot_directory':
        os.path.join(os.path.expanduser('~'), 'Pictures'),
        'screencast_directory':
        os.path.join(os.path.expanduser('~'), r'Videos\Desktop'),
        'screencast_pattern':
        r'Desktop \d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}\.\d{2}\.\d{2}\.mp4'}
    config['Market Holidays'] = {
        'url': 'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'market_holidays':
        os.path.join('${General:market_directory}', 'market_holidays.csv'),
        'date_header': '日付',
        'date_format': '%Y/%m/%d'}
    config['Market Data'] = {
        'opening_time': '09:00:00',
        'closing_time': '15:30:00',
        'delay': '20',
        'time_zone': 'Asia/Tokyo',
        'url': 'https://kabutan.jp/warning/?mode=2_9&market=1',
        'number_of_pages': '2',
        'symbol_header': 'コード',
        'price_header': '株価',
        'closing_prices':
        os.path.join('${General:market_directory}', 'closing_prices_')}
    config['Startup Script'] = {
        'pre_start_options': '-rd',
        'post_start_options': '',
        'running_options': ''}
    config['HYPERSBI2'] = {
        'update_time': '20:00:00',
        'time_zone': '${Market Data:time_zone}',
        'url': 'https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html',
        'symbol_header': 'コード',
        'regulation_header': '規制内容',
        'header': ('銘柄', 'コード', '建玉', '信用取引区分', '規制内容'),
        'customer_margin_ratio': '委託保証金率',
        'suspended': '新規建停止',
        'customer_margin_ratios':
        os.path.join('${General:config_directory}',
                     'customer_margin_ratios.csv'),
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
        'fixed_cash_balance': '0',
        'cash_balance_region': '0, 0, 0, 0, 0',
        'utilization_ratio': '1.0',
        'price_limit_region': '0, 0, 0, 0, 0',
        'image_magnification': '2',
        'binarization_threshold': '128'}
    config['Actions'] = {
        'minimize_all_windows': [('press_hotkeys', 'win, m')],
        'show_hide_watchlists': [('show_hide_window', '登録銘柄')],
        'show_hide_watchlists_on_click':
        [('show_hide_window_on_click', '登録銘柄')],
        'speak_seconds_until_open':
        [('speak_seconds_until_event', '${Market Data:opening_time}')],
        'start_manual_recording':
        [('writing_file', 'False', [('press_hotkeys', 'alt, f9')])],
        'stop_manual_recording':
        [('writing_file', 'True', [('press_hotkeys', 'alt, f9')])]}
    config['Schedules'] = {
        'start_new_manual_recording': ('08:50:00', 'start_manual_recording'),
        'speak_60_seconds_until_open':
        ('08:59:00', 'speak_seconds_until_open'),
        'speak_30_seconds_until_open':
        ('08:59:30', 'speak_seconds_until_open'),
        'stop_current_manual_recording': ('10:00:00', 'stop_manual_recording')}
    config['Variables'] = {
        'current_date': str(date.today()),
        'current_number_of_trades': '0'}
    config.read(trade.config_file, encoding='utf-8')

    if trade.process_name == 'HYPERSBI2':
        section = config[trade.process_name]

        location_dat = os.path.join(os.path.expandvars('%LOCALAPPDATA%'),
                                    'SBI Securities', trade.process_name,
                                    'location.dat')
        try:
            with open(location_dat, 'r') as f:
                section['executable'] = os.path.normpath(
                    os.path.join(f.read(), trade.process_name + '.exe'))
        except OSError as e:
            print(e)
            section['executable'] = os.path.join(
                r'$${Env:ProgramFiles(x86)}\SBI SECURITIES',
                trade.process_name, trade.process_name + '.exe')

        theme_config = configparser.ConfigParser()
        theme_ini = os.path.join(os.path.expandvars('%APPDATA%'),
                                 'SBI Securities', trade.process_name,
                                 'theme.ini')
        theme_config.read(theme_ini)
        if theme_config.has_option('General', 'theme') \
           and theme_config['General']['theme'] == 'Light':
            section['currently_dark_theme'] = 'False'
        else:                   # Dark as a fallback
            section['currently_dark_theme'] = 'True'

    for directory in [config['General']['market_directory'],
                      config['General']['config_directory']]:
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                print(e)
                sys.exit(1)

    return config

def save_customer_margin_ratios(trade, config):
    global pd
    import pandas as pd

    section = config[trade.process_name]
    update_time = section['update_time']
    time_zone = section['time_zone']
    url = section['url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = ast.literal_eval(section['header'])
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']
    customer_margin_ratios = section['customer_margin_ratios']

    if get_latest(config, update_time, time_zone, customer_margin_ratios):
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

        df.to_csv(customer_margin_ratios, header=False, index=False)

def save_market_data(config, clipboard=False):
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
    closing_prices = section['closing_prices']

    if clipboard:
        latest = True
    else:
        paths = []
        for i in range(1, 10):
            paths.append(closing_prices + str(i) + '.csv')

        opening_time = (pd.Timestamp(opening_time, tz=time_zone)
                        + pd.Timedelta(minutes=delay)).strftime('%X')
        closing_time = (pd.Timestamp(closing_time, tz=time_zone)
                        + pd.Timedelta(minutes=delay)).strftime('%X')
        latest = get_latest(config, closing_time, time_zone, *paths,
                            volatile_time=opening_time)

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
            subset.to_csv(closing_prices + str(i) + '.csv', header=False,
                          index=False)

def get_latest(config, update_time, time_zone, *paths, volatile_time=None):
    import requests

    section = config['Market Holidays']
    url = section['url']
    market_holidays = section['market_holidays']
    date_header = section['date_header']
    date_format = section['date_format']

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

def run_scheduler(trade, config, gui_callbacks, image_name):
    import sched
    import subprocess

    scheduler = sched.scheduler(time.time, time.sleep)
    schedules = []

    section = config['Schedules']
    speech = False
    for option in section:
        schedule_time, action = ast.literal_eval(section[option])
        schedule_time = time.strptime(time.strftime('%Y-%m-%d ')
                                      + schedule_time, '%Y-%m-%d %H:%M:%S')
        schedule_time = time.mktime(schedule_time)
        if schedule_time > time.time():
            if action in ['speak_config', 'speak_seconds_until_open']:
                speech = True

            schedule = scheduler.enterabs(
                schedule_time, 1, execute_action,
                argument=(trade, config, gui_callbacks,
                          ast.literal_eval(config['Actions'][action])))
            schedules.append(schedule)

    if speech:
        initialize_speech_engine(trade)

    while scheduler.queue:
        output = subprocess.check_output(['tasklist', '/fi',
                                          'imagename eq ' + image_name])
        if re.search(image_name, str(output)):
            scheduler.run(False)
            time.sleep(1)
        else:
            for schedule in schedules:
                scheduler.cancel(schedule)

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
            image = os.path.join(config['General']['config_directory'],
                                 argument)
            region = ast.literal_eval(additional_argument)
            gui_interactions.click_widget(gui_callbacks, image, *region)
        elif command == 'copy_symbols_from_market_data':
            save_market_data(config, clipboard=True)
        elif command == 'copy_symbols_from_numeric_column':
            import win32clipboard

            argument = ast.literal_eval(argument)
            split_string = recognize_text(config[trade.process_name],
                                          *argument, None,
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

            configuration.check_config_directory(trade.config_file)
            with open(trade.config_file, 'w', encoding='utf-8') as f:
                config.write(f)
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
                gui_callbacks, trade.process_name + '.exe', argument)
        elif command == 'show_hide_window':
            win32gui.EnumWindows(gui_interactions.show_hide_window, argument)
        elif command == 'show_window':
            win32gui.EnumWindows(gui_interactions.show_window, argument)
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
        elif command == 'wait_for_period':
            time.sleep(float(argument))
        elif command == 'wait_for_prices':
            argument = ast.literal_eval(argument)
            recognize_text(config[trade.process_name], *argument)
        elif command == 'wait_for_window':
            gui_interactions.wait_for_window(gui_callbacks, argument)
        elif command == 'write_share_size':
            pyautogui.write(str(trade.share_size))

        # Boolean Command
        elif command == 'writing_file':
            section = config['General']
            screencast_directory = section['screencast_directory']
            screencast_pattern = section['screencast_pattern']
            files = [f for f in os.listdir(screencast_directory)
                           if re.fullmatch(screencast_pattern, f)]
            latest = os.path.join(screencast_directory, files[-1])
            if file_utilities.writing_file(latest) \
               == ast.literal_eval(argument):
                execute_action(trade, config, gui_callbacks,
                               additional_argument)

        # Optional Commands
        elif command == 'speak_config':
            initialize_speech_engine(trade)
            trade.speech_engine.say(config[argument][additional_argument])
            trade.speech_engine.runAndWait()
        elif command == 'speak_seconds_until_event':
            import math

            initialize_speech_engine(trade)
            event_time = time.strptime(time.strftime('%Y-%m-%d ') + argument,
                                       '%Y-%m-%d %H:%M:%S')
            event_time = time.mktime(event_time)
            trade.speech_engine.say(str(math.ceil(event_time - time.time()))
                                    + ' seconds')
            trade.speech_engine.runAndWait()

        else:
            print(command + ' is not a recognized command')
            sys.exit(1)

def create_startup_script(trade, config):
    section = config['Startup Script']
    pre_start_options = section['pre_start_options']
    post_start_options = section['post_start_options']
    running_options = section['running_options']

    if pre_start_options:
        pre_start_options = \
            tuple(map(str.strip, section['pre_start_options'].split(',')))
    if post_start_options:
        post_start_options = \
            tuple(map(str.strip, section['post_start_options'].split(',')))
    if running_options:
        running_options = \
            tuple(map(str.strip, section['running_options'].split(',')))

    with open(trade.startup_script, 'w') as f:
        lines = []
        lines.append('if (Get-Process "' + trade.process_name
                     + '" -ErrorAction SilentlyContinue)\n{\n')
        for option in running_options:
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + option + '" -NoNewWindow\n')

        lines.append('}\nelse\n{\n')
        for option in pre_start_options:
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + option + '" -NoNewWindow\n')

        lines.append('    Start-Process "'
                     + config[trade.process_name]['executable']
                     + '" -NoNewWindow\n')
        for option in post_start_options:
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + option + '" -NoNewWindow\n')

        lines.append('}\n')
        f.writelines(lines)

def calculate_share_size(trade, config, position):
    section = config[trade.process_name]
    fixed_cash_balance = int(section['fixed_cash_balance'].replace(',', '')
                             or 0)
    if fixed_cash_balance > 0:
        trade.cash_balance = fixed_cash_balance
    else:
        region = ast.literal_eval(section['cash_balance_region'])
        trade.cash_balance = recognize_text(section, *region)

    customer_margin_ratio = 0.31
    try:
        with open(section['customer_margin_ratios'], 'r') as f:
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

def recognize_text(section, x, y, width, height, index, text_type='integers'):
    from PIL import Image
    from PIL import ImageGrab
    from PIL import ImageOps

    image_magnification = int(section['image_magnification'])
    binarization_threshold = int(section['binarization_threshold'])
    currently_dark_theme = section.getboolean('currently_dark_theme')

    if text_type == 'integers':
        config = '-c tessedit_char_whitelist=\ ,0123456789 --psm 7'
    elif text_type == 'decimal_numbers':
        config = '-c tessedit_char_whitelist=\ .,0123456789 --psm 7'
    elif text_type == 'numeric_column':
        config = '-c tessedit_char_whitelist=0123456789 --psm 6'

    split_string = []
    while not split_string:
        try:
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            image = image.resize((image_magnification * width,
                                  image_magnification * height),
                                 Image.LANCZOS)
            image = image.point(lambda p:
                                255 if p > binarization_threshold else 0)
            if currently_dark_theme:
                image = ImageOps.invert(image)

            string = pytesseract.image_to_string(image, config=config)
            if text_type == 'integers' or text_type == 'decimal_numbers':
                split_string = list(map(lambda s: float(s.replace(',', '')),
                                        string.split(' ')))
            elif text_type == 'numeric_column':
                for item in string.splitlines():
                    split_string.append(item)
        except:
            pass

    if index is None:
        return split_string
    else:
        return split_string[int(index)]

def get_price_limit(trade, config):
    closing_price = 0.0
    try:
        with open(config['Market Data']['closing_prices'] + trade.symbol[0]
                  + '.csv', 'r') as f:
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
        section = config[trade.process_name]
        region = ast.literal_eval(section['price_limit_region'])
        price_limit = recognize_text(section, *region,
                                     text_type='decimal_numbers')
    return price_limit

def initialize_speech_engine(trade):
    if not trade.speech_engine:
        import pyttsx3

        trade.speech_engine = pyttsx3.init()
        voices = trade.speech_engine.getProperty('voices')
        trade.speech_engine.setProperty('voice', voices[1].id)

if __name__ == '__main__':
    main()
