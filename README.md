# place-trade #

<!-- Python script that assists in discretionary day trading of stocks
on margin using Hyper SBI 2 -->

<!-- hypersbi2 pandas pyautogui pytesseract python pywin32 tesseract
tabula-py pandas-datareader pynput -->

`place-trade.py` assists in discretionary day trading of stocks on
margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html).  By defining
an action consisting of a sequence of commands, this script executes:

  * showing required windows
  * calculating the maximum share size for a market order on margin
    trading
  * manipulating widgets to prepare your order

## Prerequisites ##

This script has been tested with [Python for
Windows](https://www.python.org/downloads/windows/) and Hyper SBI 2
and uses the following packages:

  * [pandas](https://pandas.pydata.org/) to save customer margin
    ratios and the previous market data from websites
  * [pywin32](https://github.com/mhammond/pywin32) to access to the
    Windows APIs
  * [pytesseract](https://github.com/madmaze/pytesseract) to invoke
    [Tesseract](https://tesseract-ocr.github.io/) to recognize prices
    on Hyper SBI 2
  * [pyautogui](https://pyautogui.readthedocs.io/en/latest/index.html)
    to automate interactions with Hyper SBI 2
  * [pynput](https://github.com/moses-palmer/pynput) to monitor
    keyboard input
  * (optional)
    [tabula-py](https://tabula-py.readthedocs.io/en/latest/index.html)
    to save ETF trading units from JPX
  * (optional)
    [pandas-datareader](https://pydata.github.io/pandas-datareader/stable/index.html)
    to save ETF closing prices from Yahoo Finance
  * (optional) [pyttsx3](https://github.com/nateshmbhat/pyttsx3) to
    speak a configuration

Install each package as needed.  For example:

``` batchfile
pip install pandas
pip install pywin32
pip install pytesseract
pip install pyautogui
pip install pynput
```

## Usage ##

### Create Startup Script ###

In order to calculate a maximum share size, save customer margin
ratios and the previous market data from [*SBI Securities Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
and [*Download Stock Market Data*](https://kabudata-dll.com/) in
advance.  The following option creates a startup script
`place-trade.ps1` that processes them and starts Hyper SBI 2.

``` batchfile
py place-trade.py -i
```

### Configure Cash Balance and Price Limit Regions ###

Configure the cash balance and (optional) price limit regions on Hyper
SBI 2 in order that Tesseract recognizes these prices.  A price limit
is only referenced if the previous closing price does not exist in the
market data above.  Because there can be multiple prices in a region,
specify the index of the price.  These configurations are saved in the
configuration file `place-trade.ini`.

``` batchfile
py place-trade.py -C X Y WIDTH HEIGHT INDEX
py place-trade.py -L X Y WIDTH HEIGHT INDEX
```

### Create or Modify Action ###

Create or modify an action to be processed by this script.

``` batchfile
py place-trade.py -M ACTION
```

Then insert, modify, or delete each command of the action.  An action
is a list of commands, and a command is a tuple of itself and its
arguments.  Commands are executed in order from the beginning of the
list.  These actions are saved in the configuration file.  Possible
commands are:

``` python
ACTION = [
    ('back_to', None),               # back the cursor to the previous position.
    ('beep', 'FREQUENCY, DURATION'), # beep.
    ('calculate_share_size', 'POSITION'), # calculate a share size.
    ('click', 'X, Y'),               # click.
    ('click_widget', 'IMAGE, X, Y, WIDTH, HEIGHT'), # locate a widget image in a region, and click it.
    ('count_trades', None),          # count the number of trades for the day.
    ('get_symbol', 'TITLE_REGEX'),   # get the symbol from a window title.
    ('hide_window', 'TITLE_REGEX'),  # hide a window.
    ('move_to', 'X, Y'),             # move the cursor to a position.
    ('press_hotkeys', 'KEY, ...'),   # press hotkeys.
    ('press_key', 'KEY, PRESSES'),   # press a key.
    ('show_window', 'TITLE_REGEX'),  # show a window.
    ('wait_for_key', 'KEY'),         # wait for keyboard input.
    ('wait_for_period', 'PERIOD'),   # wait for a period.
    ('wait_for_prices', 'X, Y, WIDTH, HEIGHT, INDEX'), # wait for prices to be displayed in a region.
    ('wait_for_window', 'TITLE_REGEX'), # wait for a window.
    ('write_alt_symbol', 'SYMBOL_1, SYMBOL_2'), # write the alternative symbol.
    ('write_share_size', None),      # write the calculated share size.

    # Optional command
    ('speak_config', 'SECTION, KEY'), # speak a configuration.
]
```

#### Example 1: Login ####

The following example `login` waits for the Login window showing, and
then clicks the Login button.

``` python
login = [
    # locate the Login button in the region, and click it.
    ('click_widget', '\\path\\to\\login.png, 890, 510, 140, 31'),
    ('back_to', None),               # back the cursor to the previous position.
]
```

#### Example 2: Toggle between Stocks ####

The following example `toggle_between_stocks` toggles between the
specified stocks.

``` python
toggle_between_stocks = [
    ('show_window', '^個別チャート\\s.*\\((\\d{4})\\)$'), # show the Chart window.
    ('hide_window', '^登録銘柄$'),   # hide the Watchlists window.
    ('show_window', '^個別銘柄\\s.*\\((\\d{4})\\)$'), # show the Summary window.
    ('click', '54, 45'),             # focus on the Symbol text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('get_symbol', '^個別銘柄\\s.*\\((\\d{4})\\)$'), # get the symbol from the Summary window.
    ('write_alt_symbol', '1570, 1360'), # write the alternative symbol.
    ('press_key', 'enter'),          # press the Enter key.
    ('back_to', None),               # back the cursor to the previous position.
    ('wait_for_period', '1'),        # wait for 1 second.
    ('press_key', 'esc'),            # close the symbol suggest drop-down list.
]
```

#### Example 3: Open and Close Long Position ####

The following example `open_close_long_position` shows required
windows, enters the maximum share size, and prepares a buy order.  If
the order is placed, then it prepares a sell order for repayment.

``` python
open_close_long_position = [
    # Open a Long Position
    ('hide_window', '^ランキング$'), # hide the Ranking window.
    ('show_window', '^個別チャート\\s.*\\((\\d{4})\\)$'), # show the Chart window.
    ('hide_window', '^登録銘柄$'),   # hide the Watchlists window.
    ('show_window', '^個別銘柄\\s.*\\((\\d{4})\\)$'), # show the Summary window.
    ('click', '201, 757'),           # select the New Order tab.
    ('click', '531, 823'),           # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('get_symbol', '^個別銘柄\\s.*\\((\\d{4})\\)$'), # get the symbol from the Summary window.
    ('calculate_share_size', 'long'), # calculate the share size.
    ('write_share_size', None),      # write the calculated share size.
    ('click', '466, 843'),           # click the Market Order button.
    ('press_key', 'tab, 3'),         # focus on the Buy Order button.
    ('beep', '1000, 100'),           # notify completion.
    ('back_to', None),               # back the cursor to the previous position.
    ('wait_for_key', 'space'),       # wait for space input.
    ('wait_for_prices', '193, 964, 467, 19, 0'), # wait for the execution.

    # Close the Long Position
    ('click', '284, 757'),           # select the Repayment tab.
    ('click', '606, 861'),           # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('write_share_size', None),      # write the calculated share size.
    ('click', '446, 944'),           # click the Market Order button.
    ('press_key', 'tab, 5'),         # focus on the Sell Order button.
    ('beep', '1000, 100'),           # notify completion.
    ('back_to', None),               # back the cursor to the previous position.
    ('count_trades', None),          # count the number of trades for the day.
    ('speak_config', 'Trading, number_of_trades'), # speak the number above.
]
```

### Execute Action ###

Execute an action saved in the configuration file.

``` batchfile
py place-trade.py -e ACTION
```

### Options ###

  * `-i` create a startup script and a shortcut to it
  * `-r` save customer margin ratios
  * `-d` save the previous market data
  * `-u` save ETF trading units
  * `-M [ACTION]` create or modify an action
  * `-e [ACTION]` execute an action
  * `-T [ACTION]` delete an action
  * `-S [ACTION]` create a shortcut to an action
  * `-P` configure paths
  * `-I` configure a startup script
  * `-H` configure market holidays
  * `-R` configure customer margin ratios
  * `-D` configure market data
  * `-U` configure ETF trading units
  * `-B` configure a cash balance
  * `-C X Y WIDTH HEIGHT INDEX` configure the cash balance region and
    the index of the price
  * `-L X Y WIDTH HEIGHT INDEX` configure the price limit region and
    the index of the price

## License ##

[MIT](LICENSE.md)

## Links ##

  * [*Python Scripting to Assist in Day Trading on Margin Using Hyper
    SBI 2*](): a blog post for more details.
