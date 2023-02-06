from datetime import date
import argparse
import configparser
import csv
import os
import re
import sys

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

    def get_symbol(self, hwnd, title_regex):
        matched = re.fullmatch(title_regex, win32gui.GetWindowText(hwnd))
        if matched:
            self.symbol = matched.group(1)
            return

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        '-r', action='store_true',
        help='save customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    group.add_argument(
        '-M', metavar=('ACTION', 'HOTKEY'), nargs='*',
        help=('create or modify an action and create a shortcut to it'))
    group.add_argument(
        '-e', const='LIST_ACTIONS', metavar='ACTION', nargs='?',
        help='execute an action')
    group.add_argument(
        '-T', const='LIST_ACTIONS', metavar='SCRIPT_BASE | ACTION', nargs='?',
        help=('delete a startup script or an action and a shortcut to it'))
    group.add_argument(
        '-I', const='WITHOUT_HOTKEY', metavar='HOTKEY', nargs='?',
        help=('create or modify a startup script and create a shortcut to it'))
    parser.add_argument(
        '-B', action='store_true',
        help='configure a cash balance')
    parser.add_argument(
        '-C', action='store_true',
        help=('configure the cash balance region and the index of the price'))
    parser.add_argument(
        '-L', action='store_true',
        help=('configure the price limit region and the index of the price'))
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    trade = Trade('HYPERSBI2')
    config = configure(trade)
    gui_callbacks = gui_interactions.GuiCallbacks()

    if args.r:
        save_customer_margin_ratios(trade, config)
    if args.d:
        save_market_data(config)
    if args.M == []:
        # args.M is an empty list if no arguments are given.
        configuration.list_section(config, 'Actions')
    if args.M:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        if configuration.modify_tuples(config, 'Actions', args.M[0],
                                       trade.config_file, key_prompt='command',
                                       value_prompt='arguments',
                                       end_of_list_prompt='end of commands',
                                       positioning_keys=['click', 'move_to']):
            # To pin the shortcut to the Taskbar, specify an
            # executable file as the argument target_path.
            if len(args.M) == 1:
                file_utilities.create_shortcut(
                    args.M[0], 'py.exe', '"' + __file__ + '" -e ' + args.M[0],
                    program_group_base=config[trade.process_name]['title'],
                    icon_directory=trade.config_directory)
            elif len(args.M) == 2:
                file_utilities.create_shortcut(
                    args.M[0], 'py.exe', '"' + __file__ + '" -e ' + args.M[0],
                    program_group_base=config[trade.process_name]['title'],
                    icon_directory=trade.config_directory, hotkey=args.M[1])
        else:
            file_utilities.delete_shortcut(
                args.M[0],
                program_group_base=config[trade.process_name]['title'],
                icon_directory=trade.config_directory)
    if args.e == 'LIST_ACTIONS':
        configuration.list_section(config, 'Actions')
    elif args.e:
        execute_action(trade, config, gui_callbacks, args.e)
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
        if args.I == 'WITHOUT_HOTKEY':
            file_utilities.create_shortcut(
                trade.script_base, 'powershell.exe',
                '-WindowStyle Hidden -File "' + trade.startup_script + '"',
                program_group_base=config[trade.process_name]['title'],
                icon_directory=trade.config_directory)
        else:
            file_utilities.create_shortcut(
                trade.script_base, 'powershell.exe',
                '-WindowStyle Hidden -File "' + trade.startup_script + '"',
                program_group_base=config[trade.process_name]['title'],
                icon_directory=trade.config_directory, hotkey=args.I)
    if args.B:
        file_utilities.backup_file(trade.config_file, number_of_backups=8)
        configuration.modify_option(config, 'Trading', 'fixed_cash_balance',
                                    trade.config_file)
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
    config['Common'] = {
        'market_directory': trade.market_directory,
        'config_directory': trade.config_directory}
    config['Market Holidays'] = {
        'url': 'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'market_holidays':
        os.path.join('${Common:market_directory}', 'market_holidays.csv'),
        'date_header': '日付',
        'date_format': '%Y/%m/%d'}
    config['Market Data'] = {
        'opening_time': '9:00:00',
        'closing_time': '15:30:00',
        'delay': '20',
        'time_zone': 'Asia/Tokyo',
        'url': 'https://kabutan.jp/warning/?mode=2_9',
        'number_of_pages': '2',
        'symbol_header': 'コード',
        'price_header': '株価',
        'closing_prices':
        os.path.join('${Common:market_directory}', 'closing_prices_'),
        'maximum_price': '0'}
    config['Startup Script'] = {
        'pre_start_options': '-r -d',
        'post_start_options': '',
        'running_options': ''}
    config['HYPERSBI2'] = {
        'update_time': '20:00:00',
        'time_zone': 'Asia/Tokyo',
        'url': 'https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html',
        'symbol_header': 'コード',
        'regulation_header': '規制内容',
        'header': ('銘柄', 'コード', '建玉', '信用取引区分', '規制内容'),
        'customer_margin_ratio': '委託保証金率',
        'suspended': '新規建停止',
        'customer_margin_ratios':
        os.path.join('${Common:config_directory}',
                     'customer_margin_ratios.csv'),
        'executable':
        r'$${Env:ProgramFiles(x86)}\SBI SECURITIES\HYPERSBI2\HYPERSBI2.exe',
        'title': 'Hyper SBI 2 Assistant',
        'clickable_windows': ('お知らせ',                    # Announcements
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
                              '通知設定'),                   # Notifications
        'cash_balance_region': '0, 0, 0, 0, 0',
        'price_limit_region': '0, 0, 0, 0, 0'}
    config['Trading'] = {
        'fixed_cash_balance': '0',
        'utilization_ratio': '1.0',
        'date': str(date.today()),
        'number_of_trades': '0'}
    config.read(trade.config_file, encoding='utf-8')

    for directory in [config['Common']['market_directory'],
                      config['Common']['config_directory']]:
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                print(e)
                sys.exit(1)

    return config

def create_startup_script(trade, config):
    section = config['Startup Script']
    pre_start_options = section['pre_start_options']
    post_start_options = section['post_start_options']
    running_options = section['running_options']

    if pre_start_options:
        pre_start_options = \
            list(map(str.strip, section['pre_start_options'].split(',')))
    if post_start_options:
        post_start_options = \
            list(map(str.strip, section['post_start_options'].split(',')))
    if running_options:
        running_options = \
            list(map(str.strip, section['running_options'].split(',')))

    with open(trade.startup_script, 'w') as f:
        lines = []
        lines.append('if (Get-Process "' + trade.process_name
                     + '" -ErrorAction SilentlyContinue)\n{\n')
        for i in range(len(running_options)):
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + running_options[i]
                         + '" -NoNewWindow\n')

        lines.append('}\nelse\n{\n')
        for i in range(len(pre_start_options)):
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + pre_start_options[i]
                         + '" -NoNewWindow\n')

        lines.append('    Start-Process "'
                     + config[trade.process_name]['executable']
                     + '" -NoNewWindow\n')
        for i in range(len(post_start_options)):
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + post_start_options[i]
                         + '" -NoNewWindow\n')

        lines.append('}\n')
        f.writelines(lines)

def save_customer_margin_ratios(trade, config):
    import ast

    global pd
    import pandas as pd

    section = config[trade.process_name]
    update_time = section['update_time']
    time_zone = section['time_zone']
    url = section['url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = section['header']
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']
    customer_margin_ratios = section['customer_margin_ratios']

    if get_latest(config, update_time, time_zone, customer_margin_ratios):
        dfs = pd.DataFrame()
        try:
            dfs = pd.read_html(url, match=regulation_header, header=0)
        except Exception as e:
            print(e)
            sys.exit(1)

        header = ast.literal_eval(header)
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
    maximum_price = float(section['maximum_price'])

    # TODO
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
        # TODO
        for i in range(number_of_pages):
            try:
                dfs = dfs + pd.read_html(url + '&page=' + str(i + 1),
                                         match=symbol_header)
            except Exception as e:
                print(e)
                sys.exit(1)

        df = pd.concat(dfs)
        if clipboard:
            if maximum_price > 0:
                df = df.loc[df[price_header] < maximum_price]

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

def execute_action(trade, config, gui_callbacks, action):
    import ast

    commands = ast.literal_eval(config['Actions'][action])
    for i in range(len(commands)):
        command = commands[i][0]
        if len(commands[i]) == 2:
            arguments = commands[i][1]
        if command == 'back_to':
            pyautogui.moveTo(trade.previous_position)
        elif command == 'beep':
            import winsound

            winsound.Beep(*ast.literal_eval(arguments))
        elif command == 'calculate_share_size':
            calculate_share_size(trade, config, arguments)
        elif command == 'click':
            coordinates = ast.literal_eval(arguments)
            if gui_callbacks.swapped:
                pyautogui.rightClick(coordinates)
            else:
                pyautogui.click(coordinates)
        elif command == 'click_widget':
            arguments = arguments.split(',')
            image = ','.join(arguments[:-4])
            region = arguments[-4:len(arguments)]
            gui_interactions.click_widget(gui_callbacks, image, *region)
        elif command == 'copy_symbols_from_market_data':
            save_market_data(config, clipboard=True)
        elif command == 'copy_symbols_from_numeric_columns':
            import win32clipboard

            arguments = list(map(int, arguments.split(',')))
            split_string = recognize_text(*arguments[:4], None,
                                          text_type='numeric_columns')
            maximum_price = float(config['Market Data']['maximum_price'])
            symbols = []
            for split_item in split_string:
                if maximum_price > 0 \
                   and float(split_item[arguments[5]].replace(',', '')) \
                   < maximum_price:
                    symbols.append(split_item[arguments[4]].replace('.', ''))

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(' '.join(symbols))
            win32clipboard.CloseClipboard()
        elif command == 'count_trades':
            section = config['Trading']
            previous_date = date.fromisoformat(section['date'])
            current_date = date.today()
            if previous_date == current_date:
                section['number_of_trades'] = \
                    str(int(section['number_of_trades']) + 1)
            else:
                section['date'] = str(date.today())
                section['number_of_trades'] = '1'

            configuration.check_config_directory(trade.config_file)
            with open(trade.config_file, 'w', encoding='utf-8') as f:
                config.write(f)
        elif command == 'get_symbol':
            win32gui.EnumWindows(trade.get_symbol, arguments)
        elif command == 'hide_parent_window':
            win32gui.EnumWindows(gui_interactions.hide_parent_window,
                                 arguments)
        elif command == 'hide_window':
            win32gui.EnumWindows(gui_interactions.hide_window, arguments)
        elif command == 'move_to':
            pyautogui.moveTo(ast.literal_eval(arguments))
        elif command == 'press_hotkeys':
            keys = list(map(str.strip, arguments.split(',')))
            pyautogui.hotkey(*keys)
        elif command == 'press_key':
            arguments = list(map(str.strip, arguments.split(',')))
            key = arguments[0]
            if len(arguments) >= 2:
                presses = int(arguments[1])
            else:
                presses = 1

            pyautogui.press(key, presses=presses)
            if key == 'tab':
                gui_callbacks.moved_focus = presses
        elif command == 'show_hide_window_on_click':
            gui_callbacks.clickable_windows = ast.literal_eval(
                config[trade.process_name]['clickable_windows'])
            gui_interactions.show_hide_window_on_click(
                gui_callbacks, trade.process_name + '.exe', arguments)
        elif command == 'show_hide_window':
            win32gui.EnumWindows(gui_interactions.show_hide_window, arguments)
        elif command == 'show_window':
            win32gui.EnumWindows(gui_interactions.show_window, arguments)
        elif command == 'speak_config':
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            engine.setProperty('voice', voices[1].id)
            arguments = list(map(str.strip, arguments.split(',')))
            engine.say(config[arguments[0]][arguments[1]])
            engine.runAndWait()
        elif command == 'wait_for_key':
            if not gui_interactions.wait_for_key(gui_callbacks, arguments):
                return
        elif command == 'wait_for_period':
            import time

            time.sleep(float(arguments))
        elif command == 'wait_for_prices':
            arguments = list(map(int, arguments.split(',')))
            recognize_text(*arguments)
        elif command == 'wait_for_window':
            gui_interactions.wait_for_window(gui_callbacks, arguments)
        elif command == 'write_alt_symbol':
            symbols = list(map(str.strip, arguments.split(',')))
            if symbols[0] == trade.symbol:
                alt_symbol = symbols[1]
            else:
                alt_symbol = symbols[0]

            pyautogui.write(alt_symbol)
        elif command == 'write_share_size':
            pyautogui.write(str(trade.share_size))

def calculate_share_size(trade, config, position):
    fixed_cash_balance = \
        int(config['Trading']['fixed_cash_balance'].replace(',', '') or 0)
    if fixed_cash_balance > 0:
        trade.cash_balance = fixed_cash_balance
    else:
        region = list(map(int,
                          config[trade.process_name]['cash_balance_region']
                          .split(',')))
        trade.cash_balance = recognize_text(*region)

    customer_margin_ratio = 0.31
    try:
        with open(config[trade.process_name]['customer_margin_ratios'], 'r') \
             as f:
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

    utilization_ratio = float(config['Trading']['utilization_ratio'])
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

def recognize_text(x, y, width, height, index, text_type='integers',
                   multiplier=4, threshold=128, target_color=(0, 0, 255),
                   replacement_color=(0, 0, 0)):
    from PIL import Image
    from PIL import ImageGrab

    if text_type == 'integers':
        config = '-c tessedit_char_whitelist=\ ,0123456789 --psm 7'
    elif text_type == 'decimal_numbers':
        config = '-c tessedit_char_whitelist=\ .,0123456789 --psm 7'
    elif text_type == 'numeric_columns':
        config = '-c tessedit_char_whitelist=\ .,0123456789 --psm 6'

    split_string = []
    while not split_string:
        try:
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            # TODO
            image = image.resize((multiplier * width, multiplier * height),
                                 Image.LANCZOS)
            image = image.point(lambda p: 255 if p > threshold else 0)
            pixel_data = image.load()
            for y in range(image.size[1]):
                for x in range(image.size[0]):
                    if pixel_data[x, y] == target_color:
                        pixel_data[x, y] = replacement_color

            string = pytesseract.image_to_string(image, config=config)
            if text_type == 'integers' or text_type == 'decimal_numbers':
                split_string = list(map(lambda s: float(s.replace(',', '')),
                                        string.split(' ')))
            elif text_type == 'numeric_columns':
                for item in string.splitlines():
                    split_string.append(item.split(' '))
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
        region = list(map(int,
                          config[trade.process_name]['price_limit_region']
                          .split(',')))
        price_limit = recognize_text(*region, text_type='decimal_numbers')
    return price_limit

if __name__ == '__main__':
    main()
