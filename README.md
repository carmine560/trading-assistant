# trading-assistant #

<!-- Python script that assists in discretionary day trading of stocks on
margin using Hyper SBI 2 -->

<!-- hypersbi2 python pandas pywin32 pytesseract tesseract pyautogui pynput
pyttsx3 python-prompt-toolkit -->

A `trading_assistant.py` Python script assists in discretionary day trading of
stocks on margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html).  By defining an
action consisting of a sequence of commands, this script:

  * shows required windows
  * calculates the maximum share size for a market order on margin trading
  * manipulates widgets to prepare your order
  * also schedules these actions

> **Disclaimer** This script does not analyze and make decisions for the user.
> If the user has incorrect assumptions, they can lose more because this script
> can place orders more quickly and repeatedly.  Use at your own risk.

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
  * (optional)
    [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/en/master/index.html)
    to complete possible values or a previous value in configuring

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
pip install prompt_toolkit
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
py trading_assistant.py -A ACTION
```

An action is a list of sequential tuples, and each tuple consists of a command
and its arguments.  The configuration file stores these actions.  Possible
commands are:

``` ini
[HYPERSBI2 Actions]
ACTION = [
    # Back the cursor to the previous position.
    ('back_to',),
    ('beep', 'FREQUENCY, DURATION'), # Beep.
    ('calculate_share_size', 'POSITION'), # Calculate a share size.
    ('click', 'X, Y'),               # Click.
    # Locate a widget image in a region and click on it, assuming that it is in
    # The same directory as the configuration file.
    ('click_widget', 'IMAGE', 'X, Y, WIDTH, HEIGHT'),
    # Copy symbols from the current market data to the clipboard.
    ('copy_symbols_from_market_data',),
    # Recognize a numeric column and copy symbols to the clipboard.
    ('copy_symbols_from_numeric_column', 'X, Y, WIDTH, HEIGHT'),
    ('count_trades',),               # Count the number of trades for the day.
    ('get_symbol', 'TITLE_REGEX'),   # Get the symbol from a window title.
    ('hide_parent_window', 'TITLE_REGEX'), # Hide a parent window.
    ('hide_window', 'TITLE_REGEX'),  # Hide a window.
    ('move_to', 'X, Y'),             # Move the cursor to a position.
    ('press_hotkeys', 'KEY[, ...]'), # Press hotkeys.
    ('press_key', 'KEY[, PRESSES]'), # Press a key.
    ('show_hide_window', 'TITLE_REGEX'), # Show or hide a window.
    ('show_window', 'TITLE_REGEX'),  # Show a window.
    ('speak_config', 'SECTION', 'OPTION'), # Speak a configuration.
    # Calculate CPU utilization for an interval and speak it.
    ('speak_cpu_utilization', 'INTERVAL'),
    # Speak seconds until a specific time.
    ('speak_seconds_until_time', '%H:%M:%S'),
    ('speak_text', 'TEXT'),          # Speak text.
    # Take a screenshot with the number of trades and symbol as the filename.
    ('take_screenshot',),
    ('wait_for_key', 'KEY'),         # Wait for keyboard input.
    ('wait_for_period', 'PERIOD'),   # Wait for a period.
    # Wait for prices to be displayed in a region.
    ('wait_for_prices', 'X, Y, WIDTH, HEIGHT, INDEX'),
    ('wait_for_window', 'TITLE_REGEX'), # Wait for a window.
    ('write_share_size',),           # Write the calculated share size.

    # Boolean Command
    # Execute an ACTION if recording a screencast is a BOOL value.
    ('is_recording', 'BOOL', ACTION)]
```

### Execute Action ###

Execute an action saved in the configuration file.

``` powershell
py trading_assistant.py -a ACTION
```

### Schedule Actions ###

You can also schedule the actions above as the following configurations:

``` ini
[HYPERSBI2 Schedules]
SCHEDULE = ('%H:%M:%S', 'ACTION')
```

### Action Argument Completion ###

The `-A` and `-T` options generate completion scripts for action arguments.
They are located at `%LOCALAPPDATA%\trading-assistant\HYPERSBI2\completion.ps1`
for PowerShell and `%LOCALAPPDATA%\trading-assistant\HYPERSBI2\completion.sh`
for Bash.

To enable action argument completion in PowerShell, source the script in your
current shell:

``` powershell
. $Env:LOCALAPPDATA\trading-assistant\HYPERSBI2\completion.ps1
```

To enable action argument completion in Bash, source the script in your current
shell:

``` shell
. $USERPROFILE/AppData/Local/trading-assistant/HYPERSBI2/completion.sh
```

After sourcing the script, you can use tab completion for action arguments when
running this script with the `-a`, `-A`, or `-T` options:

``` powershell
py trading_assistant.py -a a⇥
py trading_assistant.py -a action
```

``` shell
py.exe trading_assistant.py -a a⇥
py.exe trading_assistant.py -a action
```

### Options ###

  * `-P BROKERAGE PROCESS`: set a brokerage and a process [default: `SBI
    Securities` and `HYPERSBI2`]
  * `-r`: save customer margin ratios
  * `-d`: save the previous market data
  * `-s`: start the scheduler
  * `-l`: start the mouse and keyboard listeners
  * `-a ACTION`: execute an action
  * `-I`: configure a startup script, create a shortcut to it, and exit
  * `-S`: configure schedules and exit
  * `-A ACTION`: configure an action, create a shortcut to it, and exit
  * `-C`: configure the cash balance region and the index of the price
  * `-B`: configure an arbitrary cash balance
  * `-L`: configure the price limit region and the index of the price
  * `-T SCRIPT_BASE | ACTION`: delete a startup script or an action, delete a
    shortcut to it, and exit

## Action Examples ##

### Login ###

The following `login` action waits for the Login window to show and clicks its
button.

> **Note** These examples below underwent in an environment with 1080p
> resolution, a maximized Watchlists window, a left-snapped Summary window, and
> a right-snapped Chart window.  In addition, my Hyper SBI 2 settings differ
> from the default settings.

``` ini
[HYPERSBI2 Actions]
login = [
    # Locate the Login button in the region, and click it.
    ('click_widget', 'login.png', '759, 320, 402, 381'),
    # Back the cursor to the previous position.
    ('back_to',),
    ('wait_for_window', 'HYPER SBI 2'), # Wait for the Toolbar.
    ('wait_for_period', '1'),        # Wait for 1 second.
    ('hide_parent_window', 'HYPER SBI 2'), # Hide the Toolbar.
    ('wait_for_window', '登録銘柄'), # Wait for the Watchlists window.
    ('wait_for_period', '1'),        # Wait for 1 second.
    ('hide_window', '登録銘柄')]     # Hide the Watchlists window.
```

### Replace Watchlist with Market Data on Website ###

The following `watch_active_stocks` action replaces the stocks in the
Watchlists window with new ones scraped from the current market data above.

> **Note** The free market data provided by Kabutan has a 20-minute delay.

``` ini
[HYPERSBI2 Actions]
watch_active_stocks = [
    # Copy symbols from the current market data to the clipboard.
    ('copy_symbols_from_market_data',),
    ('show_window', '登録銘柄'),     # Show the Watchlists window.
    ('click', '44, 95'),             # Select the first watchlist.
    ('click', '1612, 41'),           # Select the List view.
    ('press_key', 'tab, 3'),         # Focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # Select all stocks.
    ('press_key', 'del'),            # Delete them.
    ('wait_for_period', '0.6'),      # Wait for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # Paste the symbols copied above.
    ('press_key', 'enter'),          # Confirm the registration.
    ('wait_for_period', '0.6'),      # Wait for 0.6 seconds.
    ('click', '1676, 41'),           # Select the Tile view.

    # Optional Commands
    ('press_key', 'tab, 6'),         # Focus on the number of columns input.
    ('press_key', '6'),              # Enter 6.
    ('press_key', 'tab, 3'),         # Focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # Open the menu.
    ('press_key', 'home'),           # Move to the first item.
    ('press_key', 'down, 2'),        # Select the 5-minute time frame.
    ('press_key', 'enter'),          # Close the menu.
    ('click', '420, 90'),            # Select the 1-day date range.
    ('click', '508, 68'),            # Click the Chart button.
    # Back the cursor to the previous position.
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
    ('show_window', '登録銘柄'),     # Show the Watchlists window.
    ('press_hotkeys', 'ctrl, 7'),    # Open the Rankings window.
    ('wait_for_period', '0.2'),      # Wait for 0.2 seconds.
    ('click', '38, 39'),             # Select the Rankings tab.
    ('click', '88, 338'),            # Select the Tick Count ranking.
    ('click', '315, 63'),            # Click the Prime Market button.
    ('wait_for_period', '0.2'),      # Wait for 0.2 seconds.
    # Recognize a numeric column and copy symbols to the clipboard.
    ('copy_symbols_from_numeric_column', '328, 149, 52, 661'),
    ('press_hotkeys', 'alt, f4'),    # Close the window.
    ('click', '44, 120'),            # Select the second watchlist.
    ('click', '1612, 41'),           # Select the List view.
    ('press_key', 'tab, 3'),         # Focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # Select all stocks.
    ('press_key', 'del'),            # Delete them.
    ('wait_for_period', '0.6'),      # Wait for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # Paste the symbols copied above.
    ('press_key', 'enter'),          # Confirm the registration.
    ('wait_for_period', '0.6'),      # Wait for 0.6 seconds.
    ('click', '1676, 41'),           # Select the Tile view.

    # Optional Commands
    ('press_key', 'tab, 6'),         # Focus on the number of columns input.
    ('press_key', '6'),              # Enter 6.
    ('press_key', 'tab, 3'),         # Focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # Open the menu.
    ('press_key', 'home'),           # Move to the first item.
    ('press_key', 'down, 2'),        # Select the 5-minute time frame.
    ('press_key', 'enter'),          # Close the menu.
    ('click', '420, 90'),            # Select the 1-day date range.
    ('click', '508, 68'),            # Click the Chart button.
    # Back the cursor to the previous position.
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
    ('show_window', '個別チャート\s.*\((\d{4})\)'), # Show the Chart window.
    ('show_window', '個別銘柄\s.*\((\d{4})\)'), # Show the Summary window.
    ('click', '208, 726'),           # Select the New Order tab.
    ('click', '541, 797'),           # Focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # Select an existing value.
    # Get the symbol from the Summary window.
    ('get_symbol', '個別銘柄\s.*\((\d{4})\)'),
    ('calculate_share_size', 'long'), # Calculate the share size.
    ('write_share_size',),           # Write the calculated share size.
    ('click', '477, 819'),           # Click the Market Order button.
    ('press_key', 'tab, 3'),         # Focus on the Buy Order button.
    # Notify you of the readiness of a buy order.
    ('speak_text', 'Long.'),
    # Back the cursor to the previous position.
    ('back_to',),
    ('wait_for_key', 'space'),       # Wait for space input.
    ('wait_for_prices', '201, 956, 470, 20, 0'), # Wait for the execution.

    # Close Long Position
    ('click', '292, 726'),           # Select the Repayment tab.
    ('click', '605, 838'),           # Focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # Select an existing value.
    ('write_share_size',),           # Write the calculated share size.
    ('click', '448, 935'),           # Click the Market Order button.
    ('press_key', 'tab, 5'),         # Focus on the Sell Order button.
    ('count_trades',),               # Count the number of trades for the day.
    # Speak the number above and notify you of the readiness of a sell order.
    ('speak_config', 'Variables', 'number_of_trades'),
    # Back the cursor to the previous position.
    ('back_to',)]
```

## Startup Script Example ##

The following actions and options configure the processing of Hyper SBI 2 pre-
and post-startup and during running.

``` ini
[HYPERSBI2 Actions]
minimize_all_windows = [
    ('press_hotkeys', 'win, m')]     # Minimize all windows.
show_hide_watchlists = [
    ('show_hide_window', '登録銘柄')] # Show or hide the Watchlists window.

[HYPERSBI2 Startup Script]
# Save customer margin ratios and the previous market data and execute the
# minimize_all_windows action above.
pre_start_options = -rda minimize_all_windows
# Start the scheduler, mouse and keyboard listeners, and execute the login
# action mentioned in the previous section.
post_start_options = -sla login
# Execute the show_hide_window action above.
running_options = -a show_hide_watchlists
```

## Schedule Examples ##

### Start and Stop Manual Recording ###

The following actions and schedules start and stop manual recording of a
screencast using Nvidia ShadowPlay.

``` ini
[HYPERSBI2 Actions]
start_manual_recording = [
    # Start a new recording if one is not already in progress.
    ('is_recording', 'False', [('press_hotkeys', 'alt, f9')])]
stop_manual_recording = [
    # Stop a recording if one is currently in progress.
    ('is_recording', 'True', [('press_hotkeys', 'alt, f9')])]

[HYPERSBI2 Schedules]
# Trigger the start_manual_recording action at 08:50:00.
start_new_manual_recording = ('08:50:00', 'start_manual_recording')
# Trigger the stop_manual_recording action at 10:00:00.
stop_current_manual_recording = ('10:00:00', 'stop_manual_recording')
```

### Speak CPU Utilization ###

The following action and schedule calculate CPU utilization and speak it.

``` ini
[HYPERSBI2 Actions]
speak_cpu_utilization = [
    # Calculate CPU utilization for 1 second and speak it.
    ('speak_cpu_utilization', '1')]

[HYPERSBI2 Schedules]
# Trigger the speak_cpu_utilization action at 08:50:10.
speak_cpu_utilization = ('08:50:10', 'speak_cpu_utilization')
```

### Speak the Number of Seconds until the Open ###

The following action and schedules speak the number of seconds until the open.

``` ini
[HYPERSBI2 Actions]
speak_seconds_until_open = [
    # Speak seconds until the open.
    ('speak_seconds_until_time', '${Market Data:opening_time}')]

[HYPERSBI2 Schedules]
# Trigger the speak_seconds_until_open action at 08:59:00.
speak_60_seconds_until_open = ('08:59:00', 'speak_seconds_until_open')
# Trigger the speak_seconds_until_open action at 08:59:30.
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
    2*](): a blog post about computing the maximum share size for a market
    order on margin trading
