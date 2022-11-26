from datetime import date
from pynput import keyboard
import os, argparse, sys, win32gui, csv, pyautogui, pytesseract, win32api, \
    configparser, re, time

class PlaceTrade:
    def __init__(self):
        self.exist = []
        self.swapped = win32api.GetSystemMetrics(23)
        self.previous_position = pyautogui.position()
        self.cash_balance = 0
        self.symbol = ''
        self.share_size = 0
        self.key = None
        self.released = False

    def check_for_window(self, hwnd, title_regex):
        if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 1)

            win32gui.SetForegroundWindow(hwnd)
            self.exist.append((hwnd, title_regex))
            return

    def get_symbol(self, hwnd, title_regex):
        matched = re.search(title_regex, str(win32gui.GetWindowText(hwnd)))
        if matched:
            self.symbol = matched.group(1)
            return

    def on_release(self, key):
        if hasattr(key, 'char') and key.char == self.key:
            self.released = True
            return False
        elif key == self.key:
            self.released = True
            return False
        elif key == keyboard.Key.esc:
            return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', action='store_true',
        help='create a startup script and a shortcut to it')
    parser.add_argument(
        '-r', action='store_true',
        help='save customer margin ratios')
    parser.add_argument(
        '-d', action='store_true',
        help='save the previous market data')
    parser.add_argument(
        '-u', action='store_true',
        help='save ETF trading units')
    parser.add_argument(
        '-M', nargs='?', const='LIST_ACTIONS',
        help='create or modify an action')
    parser.add_argument(
        '-e', nargs='?', const='LIST_ACTIONS',
        help='execute an action')
    parser.add_argument(
        '-T', nargs='?', const='LIST_ACTIONS',
        help='delete an action')
    parser.add_argument(
        '-S', nargs='?', const='LIST_ACTIONS',
        help='create a shortcut to an action')
    parser.add_argument(
        '-P', action='store_true',
        help='configure paths')
    parser.add_argument(
        '-I', action='store_true',
        help='configure a startup script')
    parser.add_argument(
        '-H', action='store_true',
        help='configure market holidays')
    parser.add_argument(
        '-R', action='store_true',
        help='configure customer margin ratios')
    parser.add_argument(
        '-D', action='store_true',
        help='configure market data')
    parser.add_argument(
        '-U', action='store_true',
        help='configure ETF trading units')
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

    config = configure_default()
    place_trade = PlaceTrade()

    if args.i:
        create_startup_script(config)
    elif args.r:
        save_customer_margin_ratios(config)
    elif args.d:
        save_market_data(config)
    elif args.u:
        save_etf_trading_units(config)
    elif args.M == 'LIST_ACTIONS' or args.e == 'LIST_ACTIONS' \
         or args.T == 'LIST_ACTIONS' or args.S == 'LIST_ACTIONS':
        list_actions(config)
    elif args.M:
        modify_action(config, args.M)
    elif args.e:
        execute_action(config, place_trade, args.e)
    elif args.T:
        delete_action(config, args.T)
    elif args.S:
        create_shortcut(args.S, 'py.exe',
                        '"' + os.path.abspath(__file__) + '"' + ' -e ' + args.S)
    elif args.P:
        configure_paths(config)
    elif args.I:
        configure_startup_script(config)
    elif args.H:
        configure_market_holidays(config)
    elif args.R:
        configure_customer_margin_ratios(config)
    elif args.D:
        configure_market_data(config)
    elif args.U:
        configure_etf_trading_units(config)
    elif args.B:
        configure_cash_balance(config)
    elif args.C:
        configure_ocr_region(config, 'cash_balance_region', args.C)
    elif args.L:
        configure_ocr_region(config, 'price_limit_region', args.L)

def configure_default():
    config = configparser.ConfigParser(interpolation=None)
    config['Paths'] = {
        'customer_margin_ratios':
        os.path.normpath(os.path.join(os.path.dirname(__file__),
                                      'customer_margin_ratios.csv')),
        'symbol_close':
        os.path.normpath(os.path.join(os.path.dirname(__file__),
                                      'symbol_close_')),
        'etf_trading_units':
        os.path.normpath(os.path.join(os.path.dirname(__file__),
                                      'etf_trading_units.csv'))}
    config['Startup Script'] = {
        'pre_start_options': '-r, -d',
        'trading_software':
        r'${Env:ProgramFiles(x86)}\SBI SECURITIES\HYPERSBI2\HYPERSBI2.exe',
        'post_start_options': '',
        'post_start_path': '',
        'post_start_arguments': ''}
    config['Market Holidays'] = {
        'market_holiday_url':
        'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'market_holidays':
        os.path.normpath(os.path.join(os.path.dirname(__file__),
                                      'market_holidays.csv')),
        'date_header': '日付',
        'date_format': '%Y/%m/%d'}
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
        'close_header': '終値',
        'additional_symbols': ''}
    config['ETF Trading Units'] = {
        'update_time': '20:00:00',
        'time_zone': 'Asia/Tokyo',
        'etf_urls':
        'https://www.jpx.co.jp/english/equities/products/etfs/issues/tvdivq000001j45s-att/b5b4pj000002nyru.pdf, https://www.jpx.co.jp/english/equities/products/etfs/leveraged-inverse/b5b4pj000004jncy-att/b5b4pj000004jnei.pdf',
        'trading_unit_header': 'Trading',
        'symbol_relative_position': '-1'}
    config['Cash Balance'] = {
        'fixed_cash_balance': '0',
        'utilization_ratio': '1.0'}
    config['OCR Regions'] = {
        'cash_balance_region': '0, 0, 0, 0, 0',
        'price_limit_region': '0, 0, 0, 0, 0'}
    config['Trading'] = {
        'date': str(date.today()),
        'number_of_trades': '0'}
    config.path = os.path.splitext(__file__)[0] + '.ini'
    config.read(config.path, encoding='utf-8')
    return config

def create_startup_script(config):
    section = config['Startup Script']
    pre_start_options = section['pre_start_options']
    trading_software = section['trading_software']
    post_start_options = section['post_start_options']
    post_start_path = section['post_start_path']
    post_start_arguments = section['post_start_arguments']

    startup_script = os.path.splitext(__file__)[0] + '.ps1'
    if len(pre_start_options):
        pre_start_options = \
            list(map(str.strip, section['pre_start_options'].split(',')))
    if len(post_start_options):
        post_start_options = \
            list(map(str.strip, section['post_start_options'].split(',')))

    with open(startup_script, 'w') as f:
        lines = []
        for i in range(len(pre_start_options)):
            lines.append('Start-Process -FilePath "py.exe" -ArgumentList "`"'
                         + os.path.abspath(__file__) + '`" '
                         + pre_start_options[i] + '" -NoNewWindow\n')

        lines.append('Start-Process -FilePath "' + trading_software
                     + '" -NoNewWindow\n')
        for i in range(len(post_start_options)):
            lines.append('Start-Process -FilePath "py.exe" -ArgumentList "`"'
                         + os.path.abspath(__file__) + '`" '
                         + post_start_options[i] + '" -NoNewWindow\n')
        if len(post_start_path):
            if len(post_start_arguments):
                lines.append('Start-Process -FilePath "' + post_start_path
                             + '" -ArgumentList "' + post_start_arguments
                             + '" -NoNewWindow\n')
            else:
                lines.append('Start-Process -FilePath "' + post_start_path
                             + '" -NoNewWindow\n')

        f.writelines(lines)

    basename = os.path.splitext(os.path.basename(startup_script))[0]
    create_shortcut(basename, 'powershell.exe',
                    '-WindowStyle Hidden -File "' + startup_script + '"')

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
    close_header = section['close_header']
    additional_symbols = []
    if section['additional_symbols']:
        additional_symbols = \
            list(map(str.strip, section['additional_symbols'].split(',')))

    symbol_close = config['Paths']['symbol_close']

    paths = []
    for i in range(1, 10):
        paths.append(symbol_close + str(i) + '.csv')

    latest = get_latest(config, update_time, time_zone, *paths)
    if latest:
        df = pd.DataFrame()
        try:
            df = pd.read_csv(latest.strftime(market_data_url), dtype=str,
                             encoding=encoding)
        except Exception as e:
            print(e)
            sys.exit(1)

        df = df[[symbol_header, close_header]]
        df.replace('^\s+$', float('NaN'), inplace=True, regex=True)
        df.dropna(subset=[symbol_header, close_header], inplace=True)
        df.sort_values(by=symbol_header, inplace=True)
        for i in range(1, 10):
            subset = df.loc[df[symbol_header].str.match(str(i) + '\d{3}5?$')]
            subset.to_csv(symbol_close + str(i) + '.csv', header=False,
                          index=False)

        if additional_symbols:
            import pandas_datareader.data as web

            start = end = latest.strftime('%Y-%m-%d')
            df = web.DataReader(additional_symbols[::-1], 'yahoo', start=start,
                                end=end)
            df_transposed = df.Close.T
            for index, row in df_transposed.iterrows():
                index = index.replace('.T', '')
                with open(symbol_close + index[0] + '.csv', 'r+') as f:
                    current = f.read()
                    f.seek(0)
                    f.write(index + ',' + str(row[0]) + '\n' + current)

def save_etf_trading_units(config):
    import tabula
    global pd
    import pandas as pd

    section = config['ETF Trading Units']
    update_time = section['update_time']
    time_zone = section['time_zone']
    etf_urls = list(map(str.strip, section['etf_urls'].split(',')))
    trading_unit_header = section['trading_unit_header']
    symbol_relative_position = int(section['symbol_relative_position'])
    etf_trading_units = config['Paths']['etf_trading_units']

    # FIXME
    if get_latest(config, update_time, time_zone, etf_trading_units):
        dfs = []
        for i in range(len(etf_urls)):
            dfs += tabula.read_pdf(etf_urls[i], pages='all')

        concatenated = pd.DataFrame()
        for i in range(len(dfs)):
            trading_unit = dfs[i].columns.get_loc(trading_unit_header)
            df = dfs[i].iloc[:, [trading_unit + symbol_relative_position,
                                 trading_unit]].dropna()
            df.columns = ['symbol', 'trading_unit']
            df['trading_unit'] = \
                df['trading_unit'].str.replace(',', '').astype(int)
            df = df[df['symbol'].apply(lambda value: str(value).isdigit())]
            df = df[df['trading_unit'].apply(lambda value:
                                             str(value).isdigit())]
            concatenated = pd.concat([concatenated, df])

        concatenated.sort_values(by='symbol', inplace=True)
        concatenated.to_csv(etf_trading_units, header=False, index=False)

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

def list_actions(config):
    if config.has_section('Actions'):
        for key in config['Actions']:
            print(key)

def modify_action(config, action):
    create = False
    if not config.has_section('Actions'):
        config['Actions'] = {}
    if not config.has_option('Actions', action):
        create = True
        config['Actions'][action] = '[]'
        i = -1
    else:
        i = 0

    commands = eval(config['Actions'][action])
    while i < len(commands):
        if create:
            answer = input('[i]nsert/[q]uit: ').lower()
        else:
            print(commands[i])
            answer = \
                input('[i]nsert/[m]odify/[a]ppend/[d]elete/[q]uit: ').lower()

        if len(answer):
            if answer[0] == 'i' or answer[0] == 'a':
                command = input('command: ')
                if command == 'click' or command == 'move_to':
                    arguments = input('input/[c]lick: ')
                    if len(arguments) and arguments[0].lower() == 'c':
                        arguments = configure_position()
                else:
                    arguments = input('arguments: ')
                if len(arguments) == 0 or arguments == 'None':
                    arguments = None
                if answer[0] == 'a':
                    i += 1

                commands.insert(i, (command, arguments))
            elif answer[0] == 'm':
                command = commands[i][0]
                arguments = commands[i][1]
                command = input('command [' + str(command) + '] ') or command
                if command == 'click' or command == 'move_to':
                    arguments = input('input/[c]lick [' + str(arguments)
                                      + '] ') or arguments
                    if len(arguments) and arguments[0].lower() == 'c':
                        arguments = configure_position()
                else:
                    arguments = input('arguments [' + str(arguments) + '] ') \
                        or arguments
                if len(arguments) == 0 or arguments == 'None':
                    arguments = None

                commands[i] = command, arguments
            elif answer[0] == 'd':
                del commands[i]
                i -= 1
            elif answer[0] == 'q':
                i = len(commands)

        i += 1

    if len(commands):
        config['Actions'][action] = str(commands)
        with open(config.path, 'w', encoding='utf-8') as f:
            config.write(f)
    else:
        delete_action(config, action)

def execute_action(config, place_trade, action):
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
            if place_trade.swapped:
                pyautogui.rightClick(coordinates)
            else:
                pyautogui.click(coordinates)
        elif command == 'click_widget':
            arguments = arguments.split(',')
            image = ','.join(arguments[0:-4])
            region = arguments[-4:len(arguments)]
            click_widget(place_trade, image, *region)
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
        elif command == 'hide_window':
            win32gui.EnumWindows(hide_window, arguments)
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
        elif command == 'show_window':
            win32gui.EnumWindows(show_window, arguments)
        elif command == 'speak_config':
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            engine.setProperty('voice', voices[1].id)
            arguments = list(map(str.strip, arguments.split(',')))
            engine.say(config[arguments[0]][arguments[1]])
            engine.runAndWait()
        elif command == 'wait_for_key':
            wait_for_key(place_trade, arguments)
        elif command == 'wait_for_period':
            time.sleep(float(arguments))
        elif command == 'wait_for_prices':
            arguments = list(map(str.strip, arguments.split(',')))
            get_prices(*arguments)
        elif command == 'wait_for_window':
            wait_for_window(place_trade, arguments)
        elif command == 'write_alt_symbol':
            symbols = list(map(str.strip, arguments.split(',')))
            if symbols[0] == place_trade.symbol:
                alt_symbol = symbols[1]
            else:
                alt_symbol = symbols[0]

            pyautogui.write(alt_symbol)
        elif command == 'write_share_size':
            pyautogui.write(str(place_trade.share_size))

def delete_action(config, action):
    import win32com.client

    config.remove_option('Actions', action)
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

    icon = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                         action + '.ico'))
    if os.path.exists(icon):
        os.remove(icon)

    shell = win32com.client.Dispatch('WScript.Shell')
    desktop = shell.SpecialFolders('Desktop')
    title = re.sub('[\W_]+', ' ', action).rstrip().title()
    shortcut = os.path.join(desktop, title + '.lnk')
    if os.path.exists(shortcut):
        os.remove(shortcut)

def create_shortcut(basename, target_path, arguments):
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    desktop = shell.SpecialFolders('Desktop')
    title = re.sub('[\W_]+', ' ', basename).rstrip().title()
    shortcut = shell.CreateShortCut(os.path.join(desktop, title + '.lnk'))
    shortcut.WindowStyle = 7
    shortcut.IconLocation = create_icon(basename)
    shortcut.TargetPath = target_path
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = os.path.dirname(__file__)
    shortcut.save()

def create_icon(basename):
    from PIL import Image, ImageDraw, ImageFont
    import winreg

    acronym = ''
    for word in re.split('[\W_]+', basename):
        if len(word):
            acronym = acronym + word[0].upper()

    image_width = image_height = 256
    image = Image.new('RGBA', (image_width, image_height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
        try:
            is_light_theme, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        except OSError:
            is_light_theme = True
    if is_light_theme:
        fill = 'black'
    else:
        fill = 'white'

    if len(acronym) == 0:
        return False
    elif len(acronym) == 1:
        font = ImageFont.truetype('consolab.ttf', 401)

        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_width - text_width) / 2, -offset_y), acronym,
                  font=font, fill=fill)
    elif len(acronym) == 2:
        font = ImageFont.truetype('consolab.ttf', 180)

        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_width - text_width) / 2,
                   (image_height - text_height) / 2 - offset_y), acronym,
                  font=font, fill=fill)
    elif len(acronym) >= 3:
        font = ImageFont.truetype('consolab.ttf', 180)

        upper = acronym[0:2]
        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), upper, font=font)
        draw.text(((image_width - text_width) / 2, -offset_y), upper,
                  font=font, fill=fill)

        lower = acronym[2:4]
        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), lower, font=font)
        draw.text(((image_width - text_width) / 2,
                   image_height - text_height), lower, font=font,
                  fill=fill)

    icon = os.path.normpath(os.path.join(os.path.dirname(__file__),
                                         basename + '.ico'))
    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return icon

def configure_paths(config):
    section = config['Paths']
    customer_margin_ratios = section['customer_margin_ratios']
    symbol_close = section['symbol_close']
    etf_trading_units = section['etf_trading_units']

    section['customer_margin_ratios'] = \
        input('customer_margin_ratios [' + customer_margin_ratios + '] ') \
        or customer_margin_ratios
    section['symbol_close'] = \
        input('symbol_close [' + symbol_close + '] ') \
        or symbol_close
    section['etf_trading_units'] = \
        input('etf_trading_units [' + etf_trading_units + '] ') \
        or etf_trading_units
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_startup_script(config):
    section = config['Startup Script']
    pre_start_options = section['pre_start_options']
    trading_software = section['trading_software']
    post_start_options = section['post_start_options']
    post_start_path = section['post_start_path']
    post_start_arguments = section['post_start_arguments']

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
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_market_holidays(config):
    section = config['Market Holidays']
    market_holiday_url = section['market_holiday_url']
    market_holidays = section['market_holidays']
    date_header = section['date_header']
    date_format = section['date_format']

    section['market_holiday_url'] = \
        input('market_holiday_url [' + market_holiday_url + '] ') \
        or market_holiday_url
    section['market_holidays'] = \
        input('market_holidays [' + market_holidays + '] ') \
        or market_holidays
    section['date_header'] = \
        input('date_header [' + date_header + '] ') \
        or date_header
    section['date_format'] = \
        input('date_format [' + date_format + '] ') \
        or date_format
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_customer_margin_ratios(config):
    section = config['Customer Margin Ratios']
    update_time = section['update_time']
    time_zone = section['time_zone']
    customer_margin_ratio_url = section['customer_margin_ratio_url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = section['header']
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']

    section['update_time'] = \
        input('update_time [' + update_time + '] ') \
        or update_time
    section['time_zone'] = \
        input('time_zone [' + time_zone + '] ') \
        or time_zone
    section['customer_margin_ratio_url'] = \
        input('customer_margin_ratio_url [' + customer_margin_ratio_url + '] ') \
        or customer_margin_ratio_url
    section['symbol_header'] = \
        input('symbol_header [' + symbol_header + '] ') \
        or symbol_header
    section['regulation_header'] = \
        input('regulation_header [' + regulation_header + '] ') \
        or regulation_header
    section['header'] = \
        input('header [' + header + '] ') \
        or header
    section['customer_margin_ratio'] = \
        input('customer_margin_ratio [' + customer_margin_ratio + '] ') \
        or customer_margin_ratio
    section['suspended'] = \
        input('suspended [' + suspended + '] ') \
        or suspended
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_market_data(config):
    section = config['Market Data']
    update_time = section['update_time']
    time_zone = section['time_zone']
    market_data_url = section['market_data_url']
    encoding = section['encoding']
    symbol_header = section['symbol_header']
    close_header = section['close_header']
    additional_symbols = section['additional_symbols']

    section['update_time'] = \
        input('update_time [' + update_time + '] ') \
        or update_time
    section['time_zone'] = \
        input('time_zone [' + time_zone + '] ') \
        or time_zone
    section['market_data_url'] = \
        input('market_data_url [' + market_data_url + '] ') \
        or market_data_url
    section['encoding'] = \
        input('encoding [' + encoding + '] ') \
        or encoding
    section['symbol_header'] = \
        input('symbol_header [' + symbol_header + '] ') \
        or symbol_header
    section['close_header'] = \
        input('close_header [' + close_header + '] ') \
        or close_header
    section['additional_symbols'] = \
        input('additional_symbols [' + additional_symbols + '] ') \
        or additional_symbols
    with open(config.path, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_etf_trading_units(config):
    section = config['ETF Trading Units']
    update_time = section['update_time']
    time_zone = section['time_zone']
    etf_urls = section['etf_urls']
    trading_unit_header = section['trading_unit_header']
    symbol_relative_position = section['symbol_relative_position']

    section['update_time'] = \
        input('update_time [' + update_time + '] ') \
        or update_time
    section['time_zone'] = \
        input('time_zone [' + time_zone + '] ') \
        or time_zone
    section['etf_urls'] = \
        input('etf_urls [' + etf_urls + '] ') \
        or etf_urls
    section['trading_unit_header'] = \
        input('trading_unit_header [' + trading_unit_header + '] ') \
        or trading_unit_header
    section['symbol_relative_position'] = \
        input('symbol_relative_position [' + symbol_relative_position + '] ') \
        or symbol_relative_position
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

def configure_position():
    previous_key_state = win32api.GetKeyState(0x01)
    current_number = 0
    coordinates = ''
    while True:
        key_state = win32api.GetKeyState(0x01)
        if key_state != previous_key_state:
            if key_state not in [0, 1]:
                x, y = pyautogui.position()
                coordinates = str(x) + ', ' + str(y)
                break

        time.sleep(0.001)

    return coordinates

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
    etf_trading_units = config['Paths']['etf_trading_units']
    if os.path.exists(etf_trading_units):
        try:
            with open(etf_trading_units, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == place_trade.symbol:
                        trading_unit = int(row[1])
                        break
        except OSError as e:
            print(e)

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
        with open(config['Paths']['symbol_close'] + place_trade.symbol[0]
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

def click_widget(place_trade, image, x, y, width, height):
    location = None
    x = int(x)
    y = int(y)
    width = int(width)
    height = int(height)
    while not location:
        location = pyautogui.locateOnScreen(image,
                                            region=(x, y, width, height))
        time.sleep(0.001)

    if place_trade.swapped:
        pyautogui.rightClick(pyautogui.center(location))
    else:
        pyautogui.click(pyautogui.center(location))

def hide_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return

def show_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 1)

        win32gui.SetForegroundWindow(hwnd)
        return

def wait_for_key(place_trade, key):
    if len(key) == 1:
        place_trade.key = key
    else:
        place_trade.key = keyboard.Key[key]
    with keyboard.Listener(on_release=place_trade.on_release) as listener:
        listener.join()
    if not place_trade.released:
        sys.exit()

def wait_for_window(place_trade, title_regex):
    while next((False for i in range(len(place_trade.exist))
                if place_trade.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(place_trade.check_for_window, title_regex)
        time.sleep(0.001)

if __name__ == '__main__':
    main()
