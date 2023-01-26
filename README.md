# trading-assistant #

<!-- Python script that assists in discretionary day trading of stocks
on margin using Hyper SBI 2 -->

<!-- hypersbi2 python pandas pywin32 pytesseract tesseract pyautogui
pynput pyttsx3 -->

`trading_assistant.py` assists in discretionary day trading of stocks
on margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html).  By defining
an action consisting of a sequence of commands, this script executes:

  * showing required windows
  * calculating the maximum share size for a market order on margin
    trading
  * manipulating widgets to prepare your order

> **Warning** This script is currently under heavy development.
> Changes in functionality can occur at any time.

## Prerequisites ##

This script has been tested with [Python for
Windows](https://www.python.org/downloads/windows/) and Hyper SBI 2
and uses the following packages:

  * [pandas](https://pandas.pydata.org/) to save customer margin
    ratios and the previous market data from websites
  * [pywin32](https://github.com/mhammond/pywin32) to access the
    Windows APIs
  * [pytesseract](https://github.com/madmaze/pytesseract) to invoke
    [Tesseract](https://tesseract-ocr.github.io/) to recognize prices
    on Hyper SBI 2
  * [pyautogui](https://pyautogui.readthedocs.io/en/latest/index.html)
    to automate interactions with Hyper SBI 2
  * [pynput](https://github.com/moses-palmer/pynput) to monitor
    keyboard input
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

To calculate a maximum share size, save customer margin ratios from
[*SBI Securities Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
and the previous market data from [*Most Active Stocks Today —
Kabutan*](https://kabutan.jp/warning/?mode=2_9) etc. in advance.  The
following option creates a startup script
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ps1`
that processes them and starts Hyper SBI 2.

``` batchfile
py trading_assistant.py -I [HOTKEY]
```

### Configure Cash Balance and Price Limit Regions ###

Configure the cash balance and (optional) price limit regions on Hyper
SBI 2 so that Tesseract recognizes these prices.  A price limit is
only referenced if the previous closing price does not exist in the
market data above.  Because there can be multiple prices in a region,
specify the index of the price.  These configurations are saved in the
configuration file
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ini`.

``` batchfile
py trading_assistant.py -C
py trading_assistant.py -L
```

### Create or Modify Action ###

Create or modify an action to be processed by this script.

``` batchfile
py trading_assistant.py -M [ACTION [HOTKEY]]
```

Then insert, modify, or delete each command of the action.  An action
is a list of commands, and a command is a tuple of itself and its
arguments.  Commands are executed in order from the beginning of the
list.  These actions are saved in the configuration file.  Possible
commands are:

``` python
ACTION = [
    ('back_to',),                    # back the cursor to the previous position.
    ('beep', 'FREQUENCY, DURATION'), # beep.
    ('calculate_share_size', 'POSITION'), # calculate a share size.
    ('click', 'X, Y'),               # click.
    ('click_widget', 'IMAGE, X, Y, WIDTH, HEIGHT'), # locate a widget image in a region, and click it.
    ('count_trades',),               # count the number of trades for the day.
    ('get_symbol', 'TITLE_REGEX'),   # get the symbol from a window title.
    ('hide_parent_window', 'TITLE_REGEX'), # hide a parent window.
    ('hide_window', 'TITLE_REGEX'),  # hide a window.
    ('move_to', 'X, Y'),             # move the cursor to a position.
    ('press_hotkeys', 'KEY, ...'),   # press hotkeys.
    ('press_key', 'KEY, PRESSES'),   # press a key.
    ('show_hide_window', 'TITLE_REGEX'), # show or hide a window.
    ('show_hide_window_on_click', 'TITLE_REGEX') # show or hide a window on the middle click.
    ('show_window', 'TITLE_REGEX'),  # show a window.
    ('wait_for_key', 'KEY'),         # wait for keyboard input.
    ('wait_for_period', 'PERIOD'),   # wait for a period.
    ('wait_for_prices', 'X, Y, WIDTH, HEIGHT, INDEX'), # wait for prices to be displayed in a region.
    ('wait_for_window', 'TITLE_REGEX'), # wait for a window.
    ('write_alt_symbol', 'SYMBOL_1, SYMBOL_2'), # write the alternative symbol.
    ('write_share_size',),           # write the calculated share size.

    # Optional command
    ('speak_config', 'SECTION, KEY'), # speak a configuration.
]
```

#### Example: Show or Hide Watchlists Window on Middle Click ####

The following example `show_hide_watchlists_on_click` shows or hides
the Watchlists window on the middle click while Hyper SBI 2 is
running.

``` python
show_hide_watchlists_on_click = [('show_hide_window_on_click', '登録銘柄')]
```

> **Note** This example contains no coordinates or images and can be
> tested immediately in many environments.

![A screenshot of Windows Terminal where trading_assistant.py -M was
executed.](https://dl.dropboxusercontent.com/s/bfi0o7ployesuwb/20230122T151015.png)

#### Example: Login ####

The following example `login` waits for the Login window to show and
clicks the Login button.

``` python
login = [
    # locate the Login button in the region, and click it.
    ('click_widget', '\\path\\to\\login.png, 890, 510, 140, 31'),
    ('back_to',),                    # back the cursor to the previous position.
    ('wait_for_window', 'HYPER SBI 2'), # wait for the Toolbar.
    ('wait_for_period', '2.8'),      # wait for 2.8 seconds.
    ('hide_parent_window', 'HYPER SBI 2'), # hide the Toolbar.
    ('wait_for_window', '登録銘柄'), # wait for the Watchlists window.
    ('wait_for_period', '2.8'),      # wait for 2.8 seconds.
    ('hide_window', '登録銘柄'),     # hide the Watchlists window.
]
```

#### Example: Toggle between Stocks ####

The following example `toggle_between_stocks` toggles between the
specified stocks.

``` python
toggle_between_stocks = [
    ('show_window', '個別チャート\\s.*\\((\\d{4})\\)'), # show the Chart window.
    ('show_window', '個別銘柄\\s.*\\((\\d{4})\\)'), # show the Summary window.
    ('click', '54, 45'),             # focus on the Symbol text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('get_symbol', '個別銘柄\\s.*\\((\\d{4})\\)'), # get the symbol from the Summary window.
    ('write_alt_symbol', '8306, 8308'), # write the alternative symbol.
    ('press_key', 'enter'),          # press the Enter key.
    ('back_to',),                    # back the cursor to the previous position.
    ('wait_for_period', '1.2'),      # wait for 1.2 second.
    ('press_key', 'esc'),            # close the symbol suggest drop-down list.
]
```

#### Example: Open and Close Long Position ####

The following example `open_close_long_position` shows required
windows, enters the maximum share size, and prepares a buy order.  If
the order is placed, then it prepares a sell order for repayment.

``` python
open_close_long_position = [
    # Open a Long Position
    ('show_window', '個別チャート\\s.*\\((\\d{4})\\)'), # show the Chart window.
    ('show_window', '個別銘柄\\s.*\\((\\d{4})\\)'), # show the Summary window.
    ('click', '201, 757'),           # select the New Order tab.
    ('click', '531, 823'),           # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('get_symbol', '個別銘柄\\s.*\\((\\d{4})\\)'), # get the symbol from the Summary window.
    ('calculate_share_size', 'long'), # calculate the share size.
    ('write_share_size',),           # write the calculated share size.
    ('click', '466, 843'),           # click the Market Order button.
    ('press_key', 'tab, 3'),         # focus on the Buy Order button.
    ('beep', '1000, 100'),           # notify completion.
    ('back_to',),                    # back the cursor to the previous position.
    ('wait_for_key', 'space'),       # wait for space input.
    ('wait_for_prices', '193, 964, 467, 19, 0'), # wait for the execution.

    # Close the Long Position
    ('click', '284, 757'),           # select the Repayment tab.
    ('click', '606, 861'),           # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('write_share_size',),           # write the calculated share size.
    ('click', '446, 944'),           # click the Market Order button.
    ('press_key', 'tab, 5'),         # focus on the Sell Order button.
    ('beep', '1000, 100'),           # notify completion.
    ('back_to',),                    # back the cursor to the previous position.
    ('count_trades',),               # count the number of trades for the day.
    ('speak_config', 'Trading, number_of_trades'), # speak the number above.
]
```

### Execute Action ###

Execute an action saved in the configuration file.

``` batchfile
py trading_assistant.py -e [ACTION]
```

### Options ###

  * `-r` save customer margin ratios
  * `-d` save the previous market data
  * `-M [ACTION [HOTKEY]]` create or modify an action and create a
    shortcut to it
  * `-e [ACTION]` execute an action
  * `-T [SCRIPT_BASE | ACTION]` delete a startup script or an action
    and a shortcut to it
  * `-I [HOTKEY]` create or modify a startup script and create a
    shortcut to it
  * `-B` configure a cash balance
  * `-C` configure the cash balance region and the index of the price
  * `-L` configure the price limit region and the index of the price
  * `-k` monitor hotkeys and execute actions
  * `-K` configure a mapping from hotkeys to actions

## Appendix ##

### Hyper SBI 2 Window Titles ###

| Window        | Regular Expression for Title  | Shortcut     |
|---------------|-------------------------------|--------------|
| Announcements | `お知らせ`                    | `Ctrl` + `I` |
| Summary       | `個別銘柄\s.*\((\d{4})\)`     | `Ctrl` + `1` |
| Watchlists    | `登録銘柄`                    | `Ctrl` + `2` |
| Holdings      | `保有証券`                    | `Ctrl` + `3` |
| Order Status  | `注文一覧`                    | `Ctrl` + `4` |
| Chart         | `個別チャート\s.*\((\d{4})\)` | `Ctrl` + `5` |
| Markets       | `マーケット`                  | `Ctrl` + `6` |
| Rankings      | `ランキング`                  | `Ctrl` + `7` |
| Stock Lists   | `銘柄一覧`                    | `Ctrl` + `8` |
| Account       | `口座情報`                    | `Ctrl` + `9` |
| News          | `ニュース`                    | `Ctrl` + `N` |
| Trading       | `取引ポップアップ`            | `Ctrl` + `T` |
| Notifications | `通知設定`                    | `Ctrl` + `G` |

## License ##

[MIT](LICENSE.md)

## Links ##

  * [*Python Scripting to Assist in Day Trading on Margin Using Hyper
    SBI 2*](): a blog post for more details.
