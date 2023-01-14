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

import configure_option
import file_utilities
import gui_interactions

class PlaceTrade:
    def __init__(self):
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
    parser.add_argument(
        '-r', action='store_true',
        help='save customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    parser.add_argument(
        '-M', nargs='*',
        help='create or modify an action and create a shortcut to it ([action [hotkey]])')
    parser.add_argument(
        '-e', nargs='?', const='LIST_ACTIONS',
        help='execute an action')
    parser.add_argument(
        '-T', nargs='?', const='LIST_ACTIONS',
        help='delete an action and a shortcut to it')
    parser.add_argument(
        '-I', nargs='?', const='WITHOUT_HOTKEY',
        help='configure and create a startup script and create a shortcut to it ([hotkey])')
    parser.add_argument(
        '-B', action='store_true',
        help='configure a cash balance')
    parser.add_argument(
        '-C', nargs=5,
        help='configure the cash balance region and the index of the price (x y width height index)')
    parser.add_argument(
        '-L', nargs=5,
        help='configure the price limit region and the index of the price (x y width height index)')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    config = configure()
    # TODO
    # if args.k:
    config.image_name = \
        os.path.basename(config['Startup Script']['trading_software'])
    config.process_name = os.path.splitext(config.image_name)[0]
    config.path = \
        os.path.splitext(__file__)[0] + '-' + config.process_name + '.ini'
    config.read(config.path, encoding='utf-8')
    config.startup_script = \
        os.path.splitext(__file__)[0] + '-' + config.process_name + '.ps1'

    place_trade = PlaceTrade()
    gui_callbacks = gui_interactions.GuiCallbacks()

    if args.r:
        save_customer_margin_ratios(config)
    elif args.d:
        save_market_data(config)
    elif args.M is not None:
        if len(args.M) == 0:
            configure_option.list_section(config, 'Actions')
        else:
            file_utilities.backup_file(config.path, number_of_backups=8)
            if configure_option.modify_tuple_list(config, 'Actions', args.M[0],
                                                  ['click', 'move_to']):
                # To pin the shortcut to the Taskbar, specify an
                # executable file as the argument target_path.
                if len(args.M) == 1:
                    file_utilities.create_shortcut(
                        args.M[0], 'py.exe',
                        '"' + __file__ + '" -e ' + args.M[0])
                elif len(args.M) == 2:
                    file_utilities.create_shortcut(
                        args.M[0], 'py.exe',
                        '"' + __file__ + '" -e ' + args.M[0], args.M[1])
            else:
                file_utilities.delete_shortcut(args.M[0])
    elif args.e == 'LIST_ACTIONS':
        configure_option.list_section(config, 'Actions')
    elif args.e:
        execute_action(config, place_trade, gui_callbacks, args.e)
    elif args.T == 'LIST_ACTIONS':
        print(os.path.splitext(os.path.basename(config.startup_script))[0])
        configure_option.list_section(config, 'Actions')
    elif args.T:
        if os.path.exists(config.startup_script):
            try:
                os.remove(config.startup_script)
            except OSError as e:
                print(e)
                sys.exit(1)

        file_utilities.backup_file(config.path, number_of_backups=8)
        configure_option.delete_option(config, 'Actions', args.T)
        file_utilities.delete_shortcut(args.T)
    elif args.I:
        file_utilities.backup_file(config.path, number_of_backups=8)
        configure_startup_script(config)
        create_startup_script(config)

        basename = os.path.splitext(os.path.basename(config.startup_script))[0]
        if args.I == 'WITHOUT_HOTKEY':
            file_utilities.create_shortcut(
                basename, 'powershell.exe',
                '-WindowStyle Hidden -File "' + config.startup_script + '"')
        else:
            file_utilities.create_shortcut(
                basename, 'powershell.exe',
                '-WindowStyle Hidden -File "' + config.startup_script + '"',
                args.I)
    elif args.B:
        file_utilities.backup_file(config.path, number_of_backups=8)
        configure_cash_balance(config)
    elif args.C:
        file_utilities.backup_file(config.path, number_of_backups=8)
        configure_ocr_region(config, 'cash_balance_region', args.C)
    elif args.L:
        file_utilities.backup_file(config.path, number_of_backups=8)
        configure_ocr_region(config, 'price_limit_region', args.L)

def configure():
    # date_format requires the argument interpolation=None.
    config = configparser.ConfigParser(interpolation=None)
    # config['Trading Software'] = {
    # config['SBI Securities'] = {
    config['HYPERSBI2'] = {
        'trading_software':
        r'${Env:ProgramFiles(x86)}\SBI SECURITIES\HYPERSBI2\HYPERSBI2.exe',
        'title_case': 'Hyper SBI 2',
        # ast.literal_eval
        'clickable_windows': ['お知らせ',                    # Announcements
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
                              '通知設定'],                   # Notifications
        'cash_balance_region': '0, 0, 0, 0, 0',
        'price_limit_region': '0, 0, 0, 0, 0',
    }
    config['Paths'] = {
        # Customer Margin Ratios
        'customer_margin_ratios':
        os.path.join(os.path.dirname(__file__), 'customer_margin_ratios.csv'),
        # Market Data
        'closing_prices':
        os.path.join(os.path.dirname(__file__), 'closing_prices_')}
    config['Startup Script'] = {
        'pre_start_options': '-r, -d',
        'trading_software':
        r'${Env:ProgramFiles(x86)}\SBI SECURITIES\HYPERSBI2\HYPERSBI2.exe',
        'post_start_options': '',
        'post_start_path': '',
        'post_start_arguments': '',
        'running_options': ''}
    config['Market Holidays'] = {
        'market_holiday_url':
        'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'market_holidays':
        os.path.join(os.path.dirname(__file__), 'market_holidays.csv'),
        'date_header': '日付',
        'date_format': '%Y/%m/%d'}
    # SBI Securities
    # config['HYPERSBI2'] = {
    config['Customer Margin Ratios'] = {
        'update_time': '20:00:00',
        'time_zone': 'Asia/Tokyo',
        'customer_margin_ratio_url':
        'https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html',
        'symbol_header': 'コード',
        'regulation_header': '規制内容',
        'header': '銘柄, コード, 建玉, 信用取引区分, 規制内容',
        'customer_margin_ratio': '委託保証金率',
        'suspended': '新規建停止'}
    config['Market Data'] = {
        'update_time': '20:00:00',
        'time_zone': 'Asia/Tokyo',
        'market_data_url':
        'https://kabudata-dll.com/wp-content/uploads/%Y/%m/%Y%m%d.csv',
        'encoding': 'cp932',
        'symbol_header': '銘柄コード',
        'closing_price_header': '終値'}
    config['Cash Balance'] = {
        'fixed_cash_balance': '0',
        'utilization_ratio': '1.0'}
    # config['HYPERSBI2'] = {
    config['OCR Regions'] = {
        'cash_balance_region': '0, 0, 0, 0, 0',
        'price_limit_region': '0, 0, 0, 0, 0'}
    config['Trading'] = {
        'date': str(date.today()),
        'number_of_trades': '0'}
    return config

def create_startup_script(config):
    section = config['Startup Script']
    pre_start_options = section['pre_start_options']
    trading_software = section['trading_software']
    post_start_options = section['post_start_options']
    post_start_path = section['post_start_path']
    post_start_arguments = section['post_start_arguments']
    running_options = section['running_options']

    if len(pre_start_options):
        pre_start_options = \
            list(map(str.strip, section['pre_start_options'].split(',')))
    if len(post_start_options):
        post_start_options = \
            list(map(str.strip, section['post_start_options'].split(',')))
    if len(running_options):
        running_options = \
            list(map(str.strip, section['running_options'].split(',')))

    with open(config.startup_script, 'w') as f:
        lines = []
        lines.append('if (Get-Process "' + config.process_name
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

        lines.append('    Start-Process "' + trading_software
                     + '" -NoNewWindow\n')
        for i in range(len(post_start_options)):
            lines.append('    Start-Process "py.exe" -ArgumentList "`"'
                         + __file__ + '`" ' + post_start_options[i]
                         + '" -NoNewWindow\n')
        if len(post_start_path):
            if len(post_start_arguments):
                lines.append('    Start-Process "' + post_start_path
                             + '" -ArgumentList "' + post_start_arguments
                             + '" -NoNewWindow\n')
            else:
                lines.append('    Start-Process "' + post_start_path
                             + '" -NoNewWindow\n')

        lines.append('}\n')
        f.writelines(lines)

def save_customer_margin_ratios(config):
    global pd
    import pandas as pd

    section = config['Customer Margin Ratios']
    update_time = section['update_time']
    time_zone = section['time_zone']
    customer_margin_ratio_url = section['customer_margin_ratio_url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = section['header']
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']
    customer_margin_ratios = config['Paths']['customer_margin_ratios']

    if get_latest(config, update_time, time_zone, customer_margin_ratios):
        dfs = pd.DataFrame()
        try:
            dfs = pd.read_html(customer_margin_ratio_url,
                               match=regulation_header, header=0)
        except Exception as e:
            print(e)
            sys.exit(1)

        header = tuple(map(str.strip, header.split(',')))
        for index, df in enumerate(dfs):
            if tuple(df.columns.values) == header:
                df = dfs[index][[symbol_header, regulation_header]]
                break

        df = df[df[regulation_header].str.contains(
            suspended + '|' + customer_margin_ratio)]
        df[regulation_header].replace('.*' + suspended + '.*',
                                      'suspended', inplace=True, regex=True)
        df[regulation_header].replace('.*' + customer_margin_ratio + '(\d+).*',
                                      r'0.\1', inplace=True, regex=True)
        df.to_csv(customer_margin_ratios, header=False, index=False)

def save_market_data(config):
    global pd
    import pandas as pd

    section = config['Market Data']
    update_time = section['update_time']
    time_zone = section['time_zone']
    market_data_url = section['market_data_url']
    encoding = section['encoding']
    symbol_header = section['symbol_header']
    closing_price_header = section['closing_price_header']
    closing_prices = config['Paths']['closing_prices']

    paths = []
    for i in range(1, 10):
        paths.append(closing_prices + str(i) + '.csv')

    latest = get_latest(config, update_time, time_zone, *paths)
    if latest:
        df = pd.DataFrame()
        try:
            df = pd.read_csv(latest.strftime(market_data_url), dtype=str,
                             encoding=encoding)
        except Exception as e:
            print(e)
            sys.exit(1)

        df = df[[symbol_header, closing_price_header]]
        df.replace('^\s+$', float('NaN'), inplace=True, regex=True)
        df.dropna(subset=[symbol_header, closing_price_header], inplace=True)
        df.sort_values(by=symbol_header, inplace=True)
        for i in range(1, 10):
            subset = df.loc[df[symbol_header].str.match(str(i) + '\d{3}5?$')]
            subset.to_csv(closing_prices + str(i) + '.csv', header=False,
                          index=False)

def get_latest(config, update_time, time_zone, *paths):
    import requests

    section = config['Market Holidays']
    market_holiday_url = section['market_holiday_url']
    market_holidays = section['market_holidays']
    date_header = section['date_header']
    date_format = section['date_format']

    modified_time = pd.Timestamp(0, tz='UTC', unit='s')
    if os.path.exists(market_holidays):
        modified_time = pd.Timestamp(os.path.getmtime(market_holidays),
                                     tz='UTC', unit='s')

    head = requests.head(market_holiday_url)
    try:
        head.raise_for_status()
    except Exception as e:
        print(e)
        sys.exit(1)

    last_modified = pd.Timestamp(head.headers['last-modified'])

    if modified_time < last_modified:
        dfs = pd.read_html(market_holiday_url, match=date_header)
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
        return latest

def execute_action(config, place_trade, gui_callbacks, action):
    commands = eval(config['Actions'][action])
    for i in range(len(commands)):
        command = commands[i][0]
        arguments = commands[i][1]
        if command == 'back_to':
            pyautogui.moveTo(place_trade.previous_position)
        elif command == 'beep':
            import winsound

            frequency, duration = eval(arguments)
            winsound.Beep(frequency, duration)
        elif command == 'calculate_share_size':
            calculate_share_size(config, place_trade, arguments)
        elif command == 'click':
            coordinates = eval(arguments)
            if gui_callbacks.swapped:
                pyautogui.rightClick(coordinates)
            else:
                pyautogui.click(coordinates)
        elif command == 'click_widget':
            arguments = arguments.split(',')
            image = ','.join(arguments[0:-4])
            region = arguments[-4:len(arguments)]
            gui_interactions.click_widget(gui_callbacks, image, *region)
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

            with open(config.path, 'w', encoding='utf-8') as f:
                config.write(f)
        elif command == 'get_symbol':
            win32gui.EnumWindows(place_trade.get_symbol, arguments)
        elif command == 'hide_parent_window':
            win32gui.EnumWindows(gui_interactions.hide_parent_window,
                                 arguments)
        elif command == 'hide_window':
            win32gui.EnumWindows(gui_interactions.hide_window, arguments)
        elif command == 'move_to':
            pyautogui.moveTo(eval(arguments))
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
            # FIXME
            gui_callbacks.clickable_windows = ['お知らせ',
                                               '個別銘柄\s.*\((\d{4})\)',
                                               '登録銘柄',
                                               '保有証券',
                                               '注文一覧',
                                               '個別チャート\s.*\((\d{4})\)',
                                               'マーケット',
                                               'ランキング',
                                               '銘柄一覧',
                                               '口座情報',
                                               'ニュース',
                                               '取引ポップアップ',
                                               '通知設定']
            gui_interactions.show_hide_window_on_click(
                gui_callbacks, config.image_name, arguments)
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
            gui_interactions.wait_for_key(gui_callbacks, arguments)
        elif command == 'wait_for_period':
            import time

            time.sleep(float(arguments))
        elif command == 'wait_for_prices':
            arguments = list(map(str.strip, arguments.split(',')))
            get_prices(*arguments)
        elif command == 'wait_for_window':
            gui_interactions.wait_for_window(gui_callbacks, arguments)
        elif command == 'write_alt_symbol':
            symbols = list(map(str.strip, arguments.split(',')))
            if symbols[0] == place_trade.symbol:
                alt_symbol = symbols[1]
            else:
                alt_symbol = symbols[0]

            pyautogui.write(alt_symbol)
        elif command == 'write_share_size':
            pyautogui.write(str(place_trade.share_size))

def configure_startup_script(config):
    section = config['Startup Script']
    pre_start_options = section['pre_start_options']
    trading_software = section['trading_software']
    post_start_options = section['post_start_options']
    post_start_path = section['post_start_path']
    post_start_arguments = section['post_start_arguments']
    running_options = section['running_options']

    section['pre_start_options'] = \
        input('pre_start_options [' + pre_start_options + '] ') \
        or pre_start_options
    section['trading_software'] = \
        input('trading_software [' + trading_software + '] ') \
        or trading_software
    section['post_start_options'] = \
        input('post_start_options [' + post_start_options + '] ') \
        or post_start_options
    section['post_start_path'] = \
        input('post_start_path [' + post_start_path + '] ') \
        or post_start_path
    section['post_start_arguments'] = \
        input('post_start_arguments [' + post_start_arguments + '] ') \
        or post_start_arguments
    section['running_options'] = \
        input('running_options [' + running_options + '] ') \
        or running_options
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_cash_balance(config):
    section = config['Cash Balance']
    fixed_cash_balance = section['fixed_cash_balance']
    utilization_ratio = section['utilization_ratio']

    section['fixed_cash_balance'] = \
        input('fixed_cash_balance [' + fixed_cash_balance + '] ') \
        or fixed_cash_balance
    fixed_cash_balance = \
        int(float(section['fixed_cash_balance'].replace(',', '')))
    if fixed_cash_balance < 0:
        section['fixed_cash_balance'] = '0'
    else:
        section['fixed_cash_balance'] = str(fixed_cash_balance)

    section['utilization_ratio'] = \
        input('utilization_ratio [' + utilization_ratio + '] ') \
        or utilization_ratio
    utilization_ratio = float(section['utilization_ratio'].replace(',', ''))
    if utilization_ratio < 0.0:
        section['utilization_ratio'] = '0.0'
    elif utilization_ratio > 1.0:
        section['utilization_ratio'] = '1.0'
    else:
        section['utilization_ratio'] = str(utilization_ratio)

    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_ocr_region(config, key, region):
    config['OCR Regions'][key] = ', '.join(region)
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def calculate_share_size(config, place_trade, position):
    fixed_cash_balance = int(config['Cash Balance']['fixed_cash_balance'])
    if fixed_cash_balance > 0:
        place_trade.cash_balance = fixed_cash_balance
    else:
        region = config['OCR Regions']['cash_balance_region'].split(', ')
        place_trade.cash_balance = get_prices(*region)

    customer_margin_ratio = 0.31
    try:
        with open(config['Paths']['customer_margin_ratios'], 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == place_trade.symbol:
                    if row[1] == 'suspended':
                        sys.exit()
                    else:
                        customer_margin_ratio = float(row[1])
                    break
    except OSError as e:
        print(e)

    price_limit = get_price_limit(config, place_trade)

    trading_unit = 100
    utilization_ratio = float(config['Cash Balance']['utilization_ratio'])
    share_size = int(place_trade.cash_balance * utilization_ratio
                     / customer_margin_ratio / price_limit / trading_unit) \
                     * trading_unit
    if share_size == 0:
        sys.exit()
    if position == 'short' and share_size > 50 * trading_unit:
        share_size = 50 * trading_unit

    place_trade.share_size = share_size

def get_prices(x, y, width, height, index, integer=True):
    if integer:
        config = '-c tessedit_char_whitelist=\ ,0123456789 --psm 7'
    else:
        config = '-c tessedit_char_whitelist=\ .,0123456789 --psm 7'

    prices = []
    while not len(prices):
        try:
            image = pyautogui.screenshot(region=(x, y, width, height))
            separated_prices = pytesseract.image_to_string(image,
                                                           config=config)
            prices = list(map(lambda price: float(price.replace(',', '')),
                              separated_prices.split(' ')))
        except:
            pass
    return prices[int(index)]

def get_price_limit(config, place_trade):
    closing_price = 0.0
    try:
        with open(config['Paths']['closing_prices'] + place_trade.symbol[0]
                  + '.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == place_trade.symbol:
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
        region = config['OCR Regions']['price_limit_region'].split(', ')
        price_limit = get_prices(*region, False)
    return price_limit

if __name__ == '__main__':
    main()
