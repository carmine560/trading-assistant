import os, argparse, sys, win32gui, csv, pyautogui, pytesseract, win32api, \
    configparser, re

class PlaceTrades:
    def __init__(self):
        self.swapped = win32api.GetSystemMetrics(23)
        self.previous_position = pyautogui.position()
        self.symbol = ''

    def get_symbol(self, hwnd, title_regex):
        matched = re.search(title_regex, str(win32gui.GetWindowText(hwnd)))
        if matched:
            self.symbol = matched.group(1)
            return

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', action='store_true',
                        help='generate the startup script')
    parser.add_argument('-r', action='store_true',
                        help='save customer margin ratios')
    parser.add_argument('-d', action='store_true',
                        help='save the previous market data')
    parser.add_argument('-M', nargs='?', const='list_actions',
                        help='create or modify an action')
    parser.add_argument('-e', nargs='?', const='list_actions',
                        help='execute an action')
    parser.add_argument('-T', nargs='?', const='list_actions',
                        help='delete an action')
    parser.add_argument('-P', action='store_true',
                        help='configure paths')
    parser.add_argument('-R', action='store_true',
                        help='configure customer margin ratios')
    parser.add_argument('-D', action='store_true',
                        help='configure the previous market data')
    parser.add_argument('-C', nargs=4,
                        help='configure the cash balance region (x y width height)')
    parser.add_argument('-L', nargs=4,
                        help='configure the price limit region (x y width height)')
    args = parser.parse_args(None if sys.argv[1:] else ['-h'])

    config = configure_default()
    place_trades = PlaceTrades()

    if args.g:
        generate_startup_script(config)
    elif args.r:
        save_customer_margin_ratios(config)
    elif args.d:
        save_market_data(config)
    elif args.M == 'list_actions' or args.e == 'list_actions' \
         or args.T == 'list_actions':
        list_actions(config)
    elif args.M:
        modify_action(config, args.M)
    elif args.e:
        execute_action(config, place_trades, args.e)
    elif args.T:
        delete_action(config, args.T)
    elif args.P:
        configure_paths(config)
    elif args.R:
        configure_customer_margin_ratios(config)
    elif args.D:
        configure_market_data(config)
    elif args.C:
        configure_ocr_region(config, 'cash_balance_region', args.C)
    elif args.L:
        configure_ocr_region(config, 'price_limit_region', args.L)

def configure_default():
    config = configparser.ConfigParser(interpolation=None)
    config['Paths'] = {
        'customer_margin_ratios':
        "os.path.expanduser('~') + '/Downloads/' + 'customer_margin_ratios.csv'",
        'symbol_close':
        "os.path.expanduser('~') + '/Downloads/' + 'symbol_close_'",
        'trading_software':
        '${Env:ProgramFiles(x86)}\SBI SECURITIES\HYPERSBI2\HYPERSBI2.exe'}
    config['Customer Margin Ratios'] = {
        'customer_margin_ratio_url':
        'https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html',
        'symbol_header': 'コード',
        'regulation_header': '規制内容',
        'header': "'銘柄', 'コード', '建玉', '信用取引区分', '規制内容'",
        'customer_margin_ratio': '委託保証金率',
        'suspended': '新規建停止'}
    config['Market Data'] = {
        'calendar_url':
        'https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html',
        'date_header': '日付',
        'market_data_url':
        'https://kabudata-dll.com/wp-content/uploads/%Y/%m/%Y%m%d.csv',
        'symbol_header': '銘柄コード',
        'close_header': '終値'}
    config['OCR Regions'] = {
        'cash_balance_region': '0, 0, 0, 0',
        'price_limit_region': '0, 0, 0, 0'}
    config.configuration = os.path.splitext(__file__)[0] + '.ini'
    config.read(config.configuration, encoding='utf-8')
    return config

def generate_startup_script(config):
    section = config['Paths']
    trading_software = section['trading_software']

    with open(os.path.splitext(__file__)[0] + '.ps1', 'w') as f:
        save_customer_margin_ratios = \
            'Start-Process -FilePath py -ArgumentList "' \
            + os.path.abspath(__file__) + ' -r" -NoNewWindow\n'
        save_market_data = 'Start-Process -FilePath py -ArgumentList "' \
            + os.path.abspath(__file__) + ' -d" -NoNewWindow\n'
        start_trading_software = 'Start-Process -FilePath "' \
            + trading_software + '" -NoNewWindow\n'
        f.writelines([save_customer_margin_ratios,
                      save_market_data,
                      start_trading_software])

def save_customer_margin_ratios(config):
    import pandas as pd

    section = config['Customer Margin Ratios']
    customer_margin_ratio_url = section['customer_margin_ratio_url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = eval(section['header'])
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']

    dfs = pd.read_html(customer_margin_ratio_url, match=regulation_header,
                       header=0)
    for index, df in enumerate(dfs):
        if tuple(df.columns.values) == header:
            df = dfs[index][[symbol_header, regulation_header]]
            break

    df = df[df[regulation_header].str.contains(suspended + '|'
                                               + customer_margin_ratio)]
    df[regulation_header].replace('.*' + suspended + '.*',
                                  'suspended', inplace=True, regex=True)
    df[regulation_header].replace('.*' + customer_margin_ratio + '(\d+).*',
                                  r'0.\1', inplace=True, regex=True)
    df.to_csv(eval(config['Paths']['customer_margin_ratios']), header=False,
              index=False)

def save_market_data(config):
    import pandas as pd

    section = config['Market Data']
    calendar_url = section['calendar_url']
    date_header = section['date_header']
    market_data_url = section['market_data_url']
    symbol_header = section['symbol_header']
    close_header = section['close_header']

    dfs = pd.read_html(calendar_url)
    calendar = pd.concat(dfs, ignore_index=True)
    calendar[date_header].replace('/', '-', inplace=True)
    previous_date = pd.Timestamp.now() - pd.Timedelta(days=1)
    while calendar[date_header].str.contains(previous_date.strftime('%Y-%m-%d')).any() \
          or previous_date.weekday() == 5 or previous_date.weekday() == 6:
        previous_date -= pd.Timedelta(days=1)

    df = pd.read_csv(previous_date.strftime(market_data_url), dtype=str,
                     encoding='cp932')
    df = df[[symbol_header, close_header]]
    df.replace('^\s+$', float('NaN'), inplace=True, regex=True)
    df.dropna(subset=[symbol_header, close_header], inplace=True)
    df.sort_values(by=symbol_header, inplace=True)
    for i in range(1, 10):
        subset = df.loc[df[symbol_header].str.match(str(i) + '\d{3}5?$')]
        subset.to_csv(eval(config['Paths']['symbol_close']) + str(i) + '.csv',
                      header=False, index=False)

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
            answer = input('[i]nsert/[m]odify/[d]elete: ').lower()

        if len(answer):
            if answer[0] == 'i':
                command = input('command: ')
                if command == 'click' or command == 'move_to':
                    arguments = input('input/[c]lick: ').lower()
                    if arguments[0] == 'c':
                        arguments = configure_position()
                else:
                    arguments = input('arguments: ')

                commands.insert(i, (command, arguments))
            elif answer[0] == 'm':
                command = commands[i][0]
                arguments = commands[i][1]
                command = input('command [' + str(command) + '] ') or command
                if command == 'click' or command == 'move_to':
                    arguments = input('input/[c]lick [' + str(arguments)
                                      + '] ').lower()
                    if arguments[0] == 'c':
                        arguments = configure_position()
                else:
                    arguments = input('arguments [' + str(arguments) + '] ') \
                        or arguments

                commands[i] = command, arguments
            elif answer[0] == 'd':
                del commands[i]
                i -= 1
            elif create and answer[0] == 'q':
                i += 1

        i += 1

    if len(commands):
        config['Actions'][action] = str(commands)
        with open(config.configuration, 'w', encoding='utf-8') as f:
            config.write(f)
    else:
        delete_action(config, action)

def execute_action(config, place_trades, action):
    commands = eval(config['Actions'][action])
    for i in range(len(commands)):
        command = commands[i][0]
        arguments = commands[i][1]
        if command == 'back_to':
            pyautogui.moveTo(place_trades.previous_position)
        elif command == 'beep':
            import winsound

            frequency, duration = eval(arguments)
            winsound.Beep(frequency, duration)
        elif command == 'calculate_share_size':
            calculate_share_size(config, place_trades)
        elif command == 'click':
            coordinates = eval(arguments)
            if place_trades.swapped:
                pyautogui.rightClick(coordinates)
            else:
                pyautogui.click(coordinates)
        elif command == 'get_symbol':
            win32gui.EnumWindows(place_trades.get_symbol, arguments)
        elif command == 'move_to':
            pyautogui.moveTo(eval(arguments))
        elif command == 'press_hotkeys':
            keys = arguments.split(', ')
            pyautogui.hotkey(*keys)
        elif command == 'press_key':
            key = arguments.split(', ')[0]
            presses = int(arguments.split(', ')[1])
            pyautogui.press(key, presses=presses)
        elif command == 'show_window':
            win32gui.EnumWindows(show_window, arguments)

def delete_action(config, action):
    config.remove_option('Actions', action)
    with open(config.configuration, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_paths(config):
    section = config['Paths']
    customer_margin_ratios = section['customer_margin_ratios']
    symbol_close = section['symbol_close']
    trading_software = section['trading_software']

    section['customer_margin_ratios'] \
        = input('customer_margin_ratios [' + customer_margin_ratios + '] ') \
        or customer_margin_ratios
    section['symbol_close'] \
        = input('symbol_close [' + symbol_close + '] ') \
        or symbol_close
    section['trading_software'] \
        = input('trading_software [' + trading_software + '] ') \
        or trading_software
    with open(config.configuration, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_customer_margin_ratios(config):
    section = config['Customer Margin Ratios']
    customer_margin_ratio_url = section['customer_margin_ratio_url']
    symbol_header = section['symbol_header']
    regulation_header = section['regulation_header']
    header = section['header']
    customer_margin_ratio = section['customer_margin_ratio']
    suspended = section['suspended']

    section['customer_margin_ratio_url'] \
        = input('customer_margin_ratio_url [' + customer_margin_ratio_url + '] ') \
        or customer_margin_ratio_url
    section['symbol_header'] \
        = input('symbol_header [' + symbol_header + '] ') \
        or symbol_header
    section['regulation_header'] \
        = input('regulation_header [' + regulation_header + '] ') \
        or regulation_header
    section['header'] \
        = input('header [' + header + '] ') \
        or header
    section['customer_margin_ratio'] \
        = input('customer_margin_ratio [' + customer_margin_ratio + '] ') \
        or customer_margin_ratio
    section['suspended'] \
        = input('suspended [' + suspended + '] ') \
        or suspended
    with open(config.configuration, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_market_data(config):
    section = config['Market Data']
    calendar_url = section['calendar_url']
    date_header = section['date_header']
    market_data_url = section['market_data_url']
    symbol_header = section['symbol_header']
    close_header = section['close_header']

    section['calendar_url'] \
        = input('calendar_url [' + calendar_url + '] ') \
        or calendar_url
    section['date_header'] \
        = input('date_header [' + date_header + '] ') \
        or date_header
    section['market_data_url'] \
        = input('market_data_url [' + market_data_url + '] ') \
        or market_data_url
    section['symbol_header'] \
        = input('symbol_header [' + symbol_header + '] ') \
        or symbol_header
    section['close_header'] \
        = input('close_header [' + close_header + '] ') \
        or close_header
    with open(config.configuration, 'w', encoding='utf-8') as f:
        config.write(f)

def configure_position():
    import time

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

def configure_ocr_region(config, key, region):
    config['OCR Regions'][key] = ', '.join(region)
    with open(config.configuration, 'w', encoding='utf-8') as f:
        config.write(f)

def calculate_share_size(config, place_trades):
    region = config['OCR Regions']['cash_balance_region'].split(', ')
    cash_balance = get_price(*region)

    customer_margin_ratio = 0.31
    with open(eval(config['Paths']['customer_margin_ratios']), 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == place_trades.symbol:
                if row[1] == 'suspended':
                    sys.exit()
                else:
                    customer_margin_ratio = float(row[1])
                break

    price_limit = get_price_limit(config, place_trades)
    share_size = int(cash_balance / customer_margin_ratio / price_limit
                     / 100) * 100

    os.system('echo ' + str(share_size) + ' | clip.exe')

def get_price(x, y, width, height):
    price = 0
    while not price:
        try:
            image = pyautogui.screenshot(region=(x, y, width, height))
            separated_price = pytesseract.image_to_string(
                image,
                config='-c tessedit_char_whitelist=\ .,0123456789 --psm 7')
            separated_price = separated_price.split(' ')[-1]
            price = float(separated_price.replace(',', ''))
        except:
            pass
    return price

def get_price_limit(config, place_trades):
    closing_price = 0.0
    with open(eval(config['Paths']['symbol_close']) + place_trades.symbol[0]
              + '.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == place_trades.symbol:
                closing_price = float(row[1])
                break

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
        price_limit = float(get_price(*region))
    return price_limit

def show_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 1)

        win32gui.SetForegroundWindow(hwnd)
        return

if __name__ == '__main__':
    main()
