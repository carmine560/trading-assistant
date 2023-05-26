# trading-assistant #

<!-- Python script that assists in discretionary day trading of stocks on
margin using Hyper SBI 2 -->

<!-- hypersbi2 python pandas pywin32 pytesseract tesseract pyautogui pynput
pyttsx3 -->

A `trading_assistant.py` Python script assists in discretionary day trading of
stocks on margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html).  By defining an
action consisting of a sequence of commands, this script:

  * shows required windows
  * calculates the maximum share size for a market order on margin trading
  * manipulates widgets to prepare your order
  * also schedules these actions

> **Warning** This script is currently under heavy development.  Changes in
> functionality can occur at any time.

## Prerequisites ##

This script has been tested in [Python for
Windows](https://www.python.org/downloads/windows/) with Hyper SBI 2 and uses
the following packages:

  * [pandas](https://pandas.pydata.org/) to save customer margin ratios and the
    previous market data from websites
  * [pywin32](https://github.com/mhammond/pywin32) to access the Windows APIs
  * [pytesseract](https://github.com/madmaze/pytesseract) to invoke
    [Tesseract](https://tesseract-ocr.github.io/) to recognize prices on Hyper
    SBI 2
  * [pyautogui](https://pyautogui.readthedocs.io/en/latest/index.html) to
    automate interactions with Hyper SBI 2
  * [pynput](https://github.com/moses-palmer/pynput) to monitor keyboard input
  * [pyttsx3](https://github.com/nateshmbhat/pyttsx3) to speak information
  * [psutil](https://github.com/giampaolo/psutil) to calculate CPU utilization

Install each package as needed.  For example:

``` powershell
pip install pandas
pip install pywin32
winget install UB-Mannheim.TesseractOCR
pip install pytesseract
pip install pyautogui
pip install pynput
pip install pyttsx3
pip install psutil
```

## Usage ##

### Create Startup Script ###

To calculate a maximum share size, save customer margin ratios from [*Stocks
Subject to Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
and the previous market data from [*Most Active Stocks
Today*](https://kabutan.jp/warning/?mode=2_9&market=1) beforehand.  The
following option creates a
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ps1` startup
script that processes them and starts Hyper SBI 2.

``` powershell
py trading_assistant.py -I
```

### Configure Cash Balance and Price Limit Regions ###

Configure the cash balance and (optional) price limit regions on Hyper SBI 2 so
that Tesseract recognizes these prices.  This script only references a price
limit if the previous closing price does not exist in the market data above.
Because a region may have more than one price, specify the index of the price
you are referring to.  A
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ini`
configuration file stores these configurations.

``` powershell
py trading_assistant.py -C
py trading_assistant.py -L
```

### Create or Modify Action ###

Create or modify an action for processing by this script.

``` powershell
py trading_assistant.py -M [ACTION]
```

An action is a list of sequential tuples, and each tuple consists of a command
and its arguments.  The configuration file stores these actions.  Possible
commands are:

``` ini
[HYPERSBI2 Actions]
ACTION = [
    # back the cursor to the previous position.
    ('back_to',),
    ('beep', 'FREQUENCY, DURATION'), # beep.
    ('calculate_share_size', 'POSITION'), # calculate a share size.
    ('click', 'X, Y'),               # click.
    # locate a widget image in a region and click on it, assuming that it is in
    # the same directory as the configuration file.
    ('click_widget', 'IMAGE', 'X, Y, WIDTH, HEIGHT'),
    # copy symbols from the current market data to the clipboard.
    ('copy_symbols_from_market_data',),
    # recognize a numeric column and copy symbols to the clipboard.
    ('copy_symbols_from_numeric_column', 'X, Y, WIDTH, HEIGHT'),
    ('count_trades',),               # count the number of trades for the day.
    ('get_symbol', 'TITLE_REGEX'),   # get the symbol from a window title.
    ('hide_parent_window', 'TITLE_REGEX'), # hide a parent window.
    ('hide_window', 'TITLE_REGEX'),  # hide a window.
    ('move_to', 'X, Y'),             # move the cursor to a position.
    ('press_hotkeys', 'KEY[, ...]'), # press hotkeys.
    ('press_key', 'KEY[, PRESSES]'), # press a key.
    ('show_hide_window', 'TITLE_REGEX'), # show or hide a window.
    # show or hide a window on the middle click.
    ('show_hide_window_on_click', 'TITLE_REGEX')
    ('show_window', 'TITLE_REGEX'),  # show a window.
    ('speak_config', 'SECTION', 'OPTION'), # speak a configuration.
    # calculate CPU utilization for an interval and speak it.
    ('speak_cpu_utilization', 'INTERVAL'),
    ('speak_string', 'STRING'),      # speak a string.
    # speak seconds until a specific time.
    ('speak_seconds_until_time', '%H:%M:%S'),
    # take a screenshot with the number of trades and symbol as the filename.
    ('take_screenshot',),
    ('wait_for_key', 'KEY'),         # wait for keyboard input.
    ('wait_for_period', 'PERIOD'),   # wait for a period.
    # wait for prices to be displayed in a region.
    ('wait_for_prices', 'X, Y, WIDTH, HEIGHT, INDEX'),
    ('wait_for_window', 'TITLE_REGEX'), # wait for a window.
    ('write_share_size',),           # write the calculated share size.

    # Boolean Command
    # execute an ACTION if recording a screencast is a BOOL value.
    ('is_recording', 'BOOL', ACTION)]
```

### Execute Action ###

Execute an action saved in the configuration file.

``` powershell
py trading_assistant.py -e [ACTION]
```

### Schedule Actions ###

You can also schedule the actions above as the following configurations:

``` ini
[HYPERSBI2 Schedules]
SCHEDULE = ('%H:%M:%S', 'ACTION')
```

### Options ###

  * `-r`: save customer margin ratios
  * `-d`: save the previous market data
  * `-s`: run the scheduler
  * `-M [ACTION]`: create or modify an action and create a shortcut to it
  * `-e [ACTION]`: execute an action
  * `-T [SCRIPT_BASE | ACTION]`: delete a startup script or an action and a
    shortcut to it
  * `-I`: create or modify a startup script and create a shortcut to it
  * `-P BROKERAGE PROCESS`: set a brokerage and a process [default: `SBI
    Securities` and `HYPERSBI2`]
  * `-B`: set an arbitrary cash balance
  * `-C`: set the cash balance region and the index of the price
  * `-L`: set the price limit region and the index of the price
  * `-S`: configure schedules and exit

## Action Examples ##

### Show or Hide Watchlists Window on Middle Click ###

The following `show_hide_watchlists_on_click` action shows or hides the
Watchlists window on the middle click while Hyper SBI 2 is running.

> **Note** This example contains no coordinates or images and can be tested
> immediately in many environments.

``` ini
[HYPERSBI2 Actions]
show_hide_watchlists_on_click = [('show_hide_window_on_click', '登録銘柄')]
```

### Login ###

The following `login` action waits for the Login window to show and clicks its
button.

> **Note** These examples below underwent in an environment with 1080p
> resolution, a maximized Watchlists window, a left-snapped Summary window, and
> a right-snapped Chart window.

``` ini
[HYPERSBI2 Actions]
login = [
    # locate the Login button in the region, and click it.
    ('click_widget', 'login.png', '759, 320, 402, 381'),
    # back the cursor to the previous position.
    ('back_to',),
    ('wait_for_window', 'HYPER SBI 2'), # wait for the Toolbar.
    ('wait_for_period', '1'),        # wait for 1 second.
    ('hide_parent_window', 'HYPER SBI 2'), # hide the Toolbar.
    ('wait_for_window', '登録銘柄'), # wait for the Watchlists window.
    ('wait_for_period', '1'),        # wait for 1 second.
    ('hide_window', '登録銘柄')]     # hide the Watchlists window.
```

### Replace Watchlist with Market Data on Website ###

The following `watch_active_stocks` action replaces the stocks in the
Watchlists window with new ones scraped from the current market data above.

> **Note** The free market data provided by Kabutan has a 20-minute delay.

``` ini
[HYPERSBI2 Actions]
watch_active_stocks = [
    # copy symbols from the current market data to the clipboard.
    ('copy_symbols_from_market_data',),
    ('show_window', '登録銘柄'),     # show the Watchlists window.
    ('click', '44, 96'),             # select the first watchlist.
    ('click', '1668, 41'),           # select the List view.
    ('press_key', 'tab, 2'),         # focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # select all stocks.
    ('press_key', 'del'),            # delete them.
    ('wait_for_period', '0.2'),      # wait for 0.2 seconds.
    ('press_key', 'enter'),          # confirm the deletion.
    ('wait_for_period', '0.6'),      # wait for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # paste the symbols copied above.
    ('press_key', 'enter'),          # confirm the registration.
    ('wait_for_period', '0.6'),      # wait for 0.6 seconds.
    ('click', '1729, 41'),           # select the Tile view.

    # Optional Commands
    ('press_key', 'tab, 5'),         # focus on the number of columns input.
    ('press_key', '6'),              # enter 6.
    ('press_key', 'tab, 3'),         # focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # open the menu.
    ('press_key', 'home'),           # move to the first item.
    ('press_key', 'down, 2'),        # select the 5-minute time frame.
    ('press_key', 'enter'),          # close the menu.
    ('click', '415, 95'),            # select the 1-day date range.
    ('click', '503, 70'),            # click the Chart button.
    # back the cursor to the previous position.
    ('back_to',)]
```

### Replace Watchlist with Hyper SBI 2 Ranking ###

The following `watch_tick_count` action replaces the stocks in the Watchlists
window with new ones recognized in the Rankings window.

> **Note** Hyper SBI updates the Rankings window in real-time, but the text
> recognition by Tesseract is not as accurate as the scraped market data above.

``` ini
[HYPERSBI2 Actions]
watch_tick_count = [
    ('show_window', '登録銘柄'),     # show the Watchlists window.
    ('press_hotkeys', 'ctrl, 7'),    # open the Rankings window.
    ('wait_for_period', '0.2'),      # wait for 0.2 seconds.
    ('click', '38, 39'),             # select the Rankings tab.
    ('click', '88, 339'),            # select the Tick Count ranking.
    ('click', '315, 65'),            # click the Prime Market button.
    ('wait_for_period', '0.2'),      # wait for 0.2 seconds.
    # recognize a numeric column and copy symbols to the clipboard.
    ('copy_symbols_from_numeric_column', '328, 149, 52, 661'),
    ('press_hotkeys', 'alt, f4'),    # close the window.
    ('click', '44, 122'),            # select the second watchlist.
    ('click', '1668, 41'),           # select the List view.
    ('press_key', 'tab, 2'),         # focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # select all stocks.
    ('press_key', 'del'),            # delete them.
    ('wait_for_period', '0.2'),      # wait for 0.2 seconds.
    ('press_key', 'enter'),          # confirm the deletion.
    ('wait_for_period', '0.6'),      # wait for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # paste the symbols copied above.
    ('press_key', 'enter'),          # confirm the registration.
    ('wait_for_period', '0.6'),      # wait for 0.6 seconds.
    ('click', '1729, 41'),           # select the Tile view.

    # Optional Commands
    ('press_key', 'tab, 5'),         # focus on the number of columns input.
    ('press_key', '6'),              # enter 6.
    ('press_key', 'tab, 3'),         # focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # open the menu.
    ('press_key', 'home'),           # move to the first item.
    ('press_key', 'down, 2'),        # select the 5-minute time frame.
    ('press_key', 'enter'),          # close the menu.
    ('click', '415, 95'),            # select the 1-day date range.
    ('click', '503, 70'),            # click the Chart button.
    # back the cursor to the previous position.
    ('back_to',)]
```

### Open and Close Long Position ###

The following `open_close_long_position` action shows the required windows and
waits for a buy order with the maximum share size.  If you place the order, it
prepares a sell order for repayment.

``` ini
[HYPERSBI2 Actions]
open_close_long_position = [
    # Open Long Position
    ('show_window', '個別チャート\s.*\((\d{4})\)'), # show the Chart window.
    ('show_window', '個別銘柄\s.*\((\d{4})\)'), # show the Summary window.
    ('click', '208, 727'),           # select the New Order tab.
    ('click', '541, 799'),           # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    # get the symbol from the Summary window.
    ('get_symbol', '個別銘柄\s.*\((\d{4})\)'),
    ('calculate_share_size', 'long'), # calculate the share size.
    ('write_share_size',),           # write the calculated share size.
    ('click', '476, 821'),           # click the Market Order button.
    ('press_key', 'tab, 3'),         # focus on the Buy Order button.
    # notify you of the readiness of a buy order.
    ('speak_string', 'long'),
    # back the cursor to the previous position.
    ('back_to',),
    ('wait_for_key', 'space'),       # wait for space input.
    ('wait_for_prices', '201, 955, 470, 21, 0'), # wait for the execution.

    # Close Long Position
    ('click', '292, 727'),           # select the Repayment tab.
    ('click', '604, 842'),           # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('write_share_size',),           # write the calculated share size.
    ('click', '454, 934'),           # click the Market Order button.
    ('press_key', 'tab, 5'),         # focus on the Sell Order button.
    ('count_trades',),               # count the number of trades for the day.
    # speak the number above and notify you of the readiness of a sell order.
    ('speak_config', 'Variables', 'number_of_trades'),
    # back the cursor to the previous position.
    ('back_to',)]
```

## Startup Script Example ##

``` ini
[HYPERSBI2 Startup Script]
pre_start_options = -rde minimize_all_windows
post_start_options = -e login, -se show_hide_watchlists_on_click
running_options = -e show_hide_watchlists
```

## Schedule Examples ##

### Start and Stop Manual Recording ###

The following actions and schedules start and stop manual recording of a
screencast using Nvidia ShadowPlay.

``` ini
[HYPERSBI2 Actions]
start_manual_recording = [
    # start a new recording if one is not already in progress.
    ('is_recording', 'False', [('press_hotkeys', 'alt, f9')])]
stop_manual_recording = [
    # stop a recording if one is currently in progress.
    ('is_recording', 'True', [('press_hotkeys', 'alt, f9')])]

[HYPERSBI2 Schedules]
# trigger the start_manual_recording action at 08:50:00.
start_new_manual_recording = ('08:50:00', 'start_manual_recording')
# trigger the stop_manual_recording action at 10:00:00.
stop_current_manual_recording = ('10:00:00', 'stop_manual_recording')
```

### Speak CPU Utilization ###

The following action and schedule calculate CPU utilization and speak it.

``` ini
[HYPERSBI2 Actions]
speak_cpu_utilization = [
    # calculate CPU utilization for 1 second and speak it.
    ('speak_cpu_utilization', '1')]

[HYPERSBI2 Schedules]
# trigger the speak_cpu_utilization action at 08:50:10.
speak_cpu_utilization = ('08:50:10', 'speak_cpu_utilization')
```

### Speak the Number of Seconds until the Open ###

The following action and schedules speak the number of seconds until the open.

``` ini
[HYPERSBI2 Actions]
speak_seconds_until_open = [
    # speak seconds until the open.
    ('speak_seconds_until_time', '${Market Data:opening_time}')]

[HYPERSBI2 Schedules]
# trigger the speak_seconds_until_open action at 08:59:00.
speak_60_seconds_until_open = ('08:59:00', 'speak_seconds_until_open')
# trigger the speak_seconds_until_open action at 08:59:30.
speak_30_seconds_until_open = ('08:59:30', 'speak_seconds_until_open')
```

## Appendix ##

### Hyper SBI 2 Window Titles ###

| Window          | Regular Expression for Title  | Shortcut     |
|-----------------|-------------------------------|--------------|
| Announcements   | `お知らせ`                    | `Ctrl` + `I` |
| Summary         | `個別銘柄\s.*\((\d{4})\)`     | `Ctrl` + `1` |
| Watchlists      | `登録銘柄`                    | `Ctrl` + `2` |
| Holdings        | `保有証券`                    | `Ctrl` + `3` |
| Order Status    | `注文一覧`                    | `Ctrl` + `4` |
| Chart           | `個別チャート\s.*\((\d{4})\)` | `Ctrl` + `5` |
| Markets         | `マーケット`                  | `Ctrl` + `6` |
| Rankings        | `ランキング`                  | `Ctrl` + `7` |
| Stock Lists     | `銘柄一覧`                    | `Ctrl` + `8` |
| Account         | `口座情報`                    | `Ctrl` + `9` |
| News            | `ニュース`                    | `Ctrl` + `N` |
| Trading         | `取引ポップアップ`            | `Ctrl` + `T` |
| Notifications   | `通知設定`                    | `Ctrl` + `G` |
| Full Order Book | `全板\s.*\((\d{4})\)`         |              |

## License ##

[MIT](LICENSE.md)

## Link ##

  * [*Python Scripting to Assist in Day Trading on Margin Using Hyper SBI
    2*](): a blog post for more details
