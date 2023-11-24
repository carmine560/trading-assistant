# trading-assistant #

<!-- Python script that assists with discretionary day trading of stocks on
margin using Hyper SBI 2 -->

The `trading_assistant.py` Python script assists with discretionary day trading
of stocks on margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html).  By defining an
action consisting of a sequence of commands, this script can:

  * Show required windows,
  * Calculate the maximum number of shares for a market order on margin
    trading,
  * Manipulate widgets to prepare your order,
  * Trigger actions using the mouse and keyboard,
  * Schedule actions.

> **Disclaimer**: `trading_assistant.py` does not analyze or make decisions for
> you.  If you operate under incorrect assumptions, the potential for loss may
> increase because of the script’s fast and frequent order placement.  Use at
> your own risk.

> **Warning**: `trading_assistant.py` is currently under heavy development.
> Changes in functionality may occur at any time.

## Prerequisites ##

`trading_assistant.py` has been tested in [Python
3.11.6](https://www.python.org/downloads/release/python-3116/) with Hyper SBI 2
on Windows 10 and uses the following packages:

  * [`requests`](https://requests.readthedocs.io/en/latest/),
    [`chardet`](https://github.com/chardet/chardet),
    [`pandas`](https://pandas.pydata.org/), and
    [`lxml`](https://lxml.de/index.html) to save the customer margin ratios and
    the previous market data from websites
  * [`pywin32`](https://github.com/mhammond/pywin32) to access Windows APIs
  * [`pytesseract`](https://github.com/madmaze/pytesseract) to invoke
    [Tesseract](https://tesseract-ocr.github.io/) to recognize prices and
    securities codes on Hyper SBI 2
  * [`pyautogui`](https://pyautogui.readthedocs.io/en/latest/index.html) to
    automate manipulation of Hyper SBI 2
  * [`pynput`](https://github.com/moses-palmer/pynput) to monitor the mouse and
    keyboard
  * [`pyttsx3`](https://github.com/nateshmbhat/pyttsx3) to speak information
  * [`psutil`](https://github.com/giampaolo/psutil) to calculate CPU
    utilization
  * [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/en/master/index.html)
    to complete possible values or a previous value in configuring
  * [`python-gnupg`](https://docs.red-dove.com/python-gnupg/) to invoke
    [GnuPG](https://gnupg.org/index.html) to encrypt and decrypt the
    configuration file

Install each package as needed.  For example:

``` powershell
winget install UB-Mannheim.TesseractOCR
winget install GnuPG.GnuPG
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -U
```

## Usage ##

### Create Startup Script ###

To calculate the maximum number of shares, save the customer margin ratios from
the [*Stocks Subject to Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
page and the previous market data from the [*Most Active Stocks
Today*](https://kabutan.jp/warning/?mode=2_9&market=1) page beforehand.  The
following option creates the
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ps1` startup
script that processes the above and starts Hyper SBI 2.

> **Note**: This option adds virtual environment activation to the startup
> script if the `.venv\Scripts\Activate.ps1` script exists.

```powershell
python trading_assistant.py -I
```

### Configure Cash Balance and Price Limit Regions ###

Configure the cash balance and (optional) price limit regions on Hyper SBI 2
for Tesseract to recognize these prices.  `trading_assistant.py` only
references a price limit if the previous closing price does not exist in the
market data above.  Because a region may contain more than one price, you need
to specify the index of the price you want to refer to.

``` powershell
python trading_assistant.py -CB
python trading_assistant.py -PL
```

### Create or Modify Action ###

Create or modify an action for processing by `trading_assistant.py`.

> **Note**: This option adds virtual environment activation to the target of a
> shortcut to the action if the `.venv\Scripts\activate.bat` script exists.

``` powershell
python trading_assistant.py -A ACTION
```

An action is a list of sequential tuples, where each tuple consists of a
command and its arguments.  Possible commands include:

``` ini
[HYPERSBI2 Actions]
ACTION = [
    # Return the cursor to the previous position.
    ('back_to',),
    ('beep', 'FREQUENCY, DURATION'), # Beep.
    ('calculate_share_size', 'POSITION'), # Calculate a share size.
    ('click', 'X, Y'),               # Click at coordinates X, Y.
    # Wait for and locate a widget image in a region and click it, assuming the
    # image file is located in the HYPERSBI2 subdirectory of the same directory
    # as the configuration file.
    ('click_widget', 'IMAGE_FILE', 'X, Y, WIDTH, HEIGHT'),
    # Copy symbols from the current market data to the clipboard.
    ('copy_symbols_from_market_data',),
    # Recognize a numeric column and copy symbols to the clipboard.
    ('copy_symbols_from_numeric_column', 'X, Y, WIDTH, HEIGHT'),
    ('count_trades',),               # Count the number of trades for the day.
    ('drag_to', 'X, Y'),             # Drag the cursor to a position.
    ('get_symbol', 'TITLE_REGEX'),   # Get the symbol from a window title.
    ('hide_window', 'TITLE_REGEX'),  # Hide a window.
    ('move_to', 'X, Y'),             # Move the cursor to a position.
    ('press_hotkeys', 'KEY[, ...]'), # Press hotkeys.
    ('press_key', 'KEY[, PRESSES]'), # Press a key.
    ('show_hide_window', 'TITLE_REGEX'), # Show or hide a window.
    ('show_window', 'TITLE_REGEX'),  # Show a window.
    ('sleep', 'PERIOD'),             # Sleep for a period.
    ('speak_config', 'SECTION', 'OPTION'), # Speak a configuration value.
    # Calculate CPU utilization for an interval and speak it.
    ('speak_cpu_utilization', 'INTERVAL'),
    # Speak seconds until a specific time.
    ('speak_seconds_until_time', '%H:%M:%S'),
    ('speak_text', 'TEXT'),          # Speak text.
    # Take a screenshot with the number of trades and symbol as the filename.
    ('take_screenshot',),
    ('wait_for_key', 'KEY'),         # Wait for keyboard input.
    # Wait for prices to be displayed in a region.
    ('wait_for_prices', 'X, Y, WIDTH, HEIGHT, INDEX'),
    ('wait_for_window', 'TITLE_REGEX'), # Wait for a window.
    ('write_share_size',),           # Write the calculated share size.
    ('write_string', 'STRING'),      # Write a string.

    # Control Flow Command
    # Execute an ACTION if recording a screencast is a BOOL value.
    ('is_recording', 'BOOL', ACTION)]
```

### Execute Action ###

Execute a created or modified action.

``` powershell
python trading_assistant.py -a ACTION
```

### Trigger Actions Using Mouse and Keyboard ###

You can also trigger actions using the mouse and keyboard by configuring the
input map for mapping buttons and keys to them.

``` powershell
python trading_assistant.py -L
```

Then, start the mouse and keyboard listeners while Hyper SBI 2 is running.

``` powershell
python trading_assistant.py -l
```

### Schedule Actions ###

You can also schedule actions using the `-S` option and the following time
format:

``` powershell
python trading_assistant.py -S
```

``` ini
[HYPERSBI2 Schedules]
SCHEDULE = ('%H:%M:%S', 'ACTION')
```

Then, start the scheduler while Hyper SBI 2 is running.

``` powershell
python trading_assistant.py -s
```

### Encrypt Configuration File ###

The `%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ini`
configuration file stores the configurations above.  If your GnuPG-encrypted
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ini.gpg`
configuration file exists, `trading_assistant.py` will read from and write to
that file.  By default, it uses the default key pair of GnuPG.  However, you
can also specify a key fingerprint as the value of the `fingerprint` option in
the `General` section of your configuration file.

### Action Argument Completion ###

The `-A` and `-D` options generate completion scripts for action arguments.
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
running `trading_assistant.py` with the `-a`, `-A`, or `-D` options:

``` powershell
python trading_assistant.py -a a⇥
python trading_assistant.py -a action
```

### Options ###

  * `-P BROKERAGE PROCESS`: set the brokerage and the process [defaults: `SBI
    Securities` and `HYPERSBI2`]
  * `-r`: save the customer margin ratios
  * `-d`: save the previous market data
  * `-s`: start the scheduler
  * `-l`: start the mouse and keyboard listeners
  * `-a ACTION`: execute an action
  * `-I`: configure the startup script, create a shortcut to it, and exit
  * `-S`: configure schedules and exit
  * `-L`: configure the input map for buttons and keys and exit
  * `-A ACTION`: configure an action, create a shortcut to it, and exit
  * `-CB`: configure the cash balance region and exit
  * `-B`: configure the fixed cash balance and exit
  * `-U`: configure the utilization ratio of the cash balance and exit
  * `-PL`: configure the price limit region and exit
  * `-D SCRIPT_BASE | ACTION`: delete the startup script or an action, delete
    the shortcut to it, and exit
  * `-C`: check configuration changes and exit

## Examples ##

The following are some examples of the configurations in my environment.
Because `trading_assistant.py` will execute anything that is an executable
configuration, you should not use these configurations without understanding
them.

> **Note**: I tested these examples in an environment with 1080p resolution, a
> maximized ‘Watchlists’ window, a left-snapped ‘Summary’ window, and a
> right-snapped ‘Chart’ window.  Additionally, my Hyper SBI 2 settings differ
> from the default settings.

### Startup Script ###

The following action and options configure the processing of Hyper SBI 2 pre-
and post-startup and during running.

``` ini
[HYPERSBI2 Actions]
show_hide_watchlists = [
    ('show_hide_window', '登録銘柄')] # Show or hide the Watchlists window.

[HYPERSBI2 Startup Script]
# Save the customer margin ratios and the previous market data.
pre_start_options = -rd
# Start the mouse and keyboard listeners and the scheduler, and execute the
# login action mentioned in the next section.
post_start_options = -lsa login
# Execute the show_hide_window action above.
running_options = -a show_hide_watchlists
```

### Actions ###

#### Login ####

The following `login` action waits for the ‘Login’ dialog box to appear and
then clicks its button.  Next, it enters your trading password and
authenticates in the ‘Pre-authentication of Trading Password’ dialog box.  If
you want to include your password as the value of an option, as demonstrated in
this example, refer to the ‘[Encrypt Configuration
File](#encrypt-configuration-file)’ section above.

``` ini
[HYPERSBI2 Actions]
login = [
    # Wait for and locate the Login button in the region and click it.
    ('click_widget', 'login.png', '759, 320, 402, 381'),
    # Wait for the Pre-authentication of Trading Password dialog box.
    ('wait_for_window', '取引パスワードのプレ認証'),
    ('show_window', '取引パスワードのプレ認証'), # Show the dialog box.
    ('press_key', 'tab, 2'),         # Focus on the trading password field.
    ('write_string', 'TRADING_PASSWORD'), # Enter your trading password.
    ('press_key', 'tab, 2'),         # Focus on the Acknowledgment checkbox.
    ('press_key', 'space'),          # Check the checkbox.
    ('press_key', 'tab, 2'),         # Focus on the Authenticate button.
    ('press_key', 'enter'),          # Press the button.
    # Wait for and locate the OK button in the region and click it.
    ('click_widget', 'ok.png', '793, 450, 334, 120'),
    ('hide_window', '登録銘柄'),     # Hide the Watchlists window.
    # Show the Chart window.
    ('show_window', '個別チャート\\s.*\\((\\d[\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    ('sleep', '0.4'),                # Sleep for 0.4 seconds.
    # Show the Summary window.
    ('show_window', '個別銘柄\\s.*\\((\\d[\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)')],
    # Return the cursor to the previous position.
    ('back_to',)
```

#### Replace Watchlist with Market Data on Website ####

The following `watch_active_stocks` action replaces the stocks in the
‘Watchlists’ window with new ones scraped from the current market data above.

> **Note**: The free market data provided by Kabutan has a 20-minute delay.

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
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # Paste the symbols copied above.
    ('press_key', 'enter'),          # Confirm the registration.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('click', '1676, 41'),           # Select the Tile view.

    # Optional Commands
    ('press_key', 'tab, 5'),         # Focus on the number of columns field.
    ('press_key', '6'),              # Enter 6.
    ('press_key', 'tab, 6'),         # Focus on the Chart button.
    ('press_key', 'space'),          # Press the button.
    ('press_key', 'tab, 6'),         # Focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # Open the menu.
    ('press_key', 'home'),           # Move to the first item.
    ('press_key', 'down, 2'),        # Select the 5-minute time frame.
    ('press_key', 'enter'),          # Close the menu.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    ('click', '561, 90'),            # Select the 1-day date range.
    # Return the cursor to the previous position.
    ('back_to',)]
```

#### Replace Watchlist with Hyper SBI 2 Ranking ####

The following `watch_tick_count` action replaces the stocks in the ‘Watchlists’
window with new ones recognized in the ‘Rankings’ window.

> **Note**: Hyper SBI updates the ‘Rankings’ window in real-time, but the text
> recognition by Tesseract is not as accurate as the scraped market data above.

``` ini
[HYPERSBI2 Actions]
watch_tick_count = [
    ('show_window', '登録銘柄'),     # Show the Watchlists window.
    ('press_hotkeys', 'ctrl, 7'),    # Open the Rankings window.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    ('click', '38, 39'),             # Select the Rankings tab.
    ('click', '88, 338'),            # Select the Tick Count ranking.
    ('click', '315, 63'),            # Click the Prime Market button.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    # Recognize a numeric column and copy symbols to the clipboard.
    ('copy_symbols_from_numeric_column', '328, 149, 52, 661'),
    ('press_hotkeys', 'alt, f4'),    # Close the window.
    ('click', '44, 120'),            # Select the second watchlist.
    ('click', '1612, 41'),           # Select the List view.
    ('press_key', 'tab, 3'),         # Focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # Select all stocks.
    ('press_key', 'del'),            # Delete them.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # Paste the symbols copied above.
    ('press_key', 'enter'),          # Confirm the registration.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('click', '1676, 41'),           # Select the Tile view.

    # Optional Commands
    ('press_key', 'tab, 5'),         # Focus on the number of columns field.
    ('press_key', '6'),              # Enter 6.
    ('press_key', 'tab, 6'),         # Focus on the Chart button.
    ('press_key', 'space'),          # Press the button.
    ('press_key', 'tab, 6'),         # Focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # Open the menu.
    ('press_key', 'home'),           # Move to the first item.
    ('press_key', 'down, 2'),        # Select the 5-minute time frame.
    ('press_key', 'enter'),          # Close the menu.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    ('click', '561, 90'),            # Select the 1-day date range.
    # Return the cursor to the previous position.
    ('back_to',)]
```

#### Center Open ####

The following `center_open` action centers the open in the main chart of the
‘Chart’ window.

``` ini
[HYPERSBI2 Actions]
center_open = [
    # Show the Chart window.
    ('show_window', '個別チャート\\s.*\\((\\d[\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    ('click', '1814, 76'),           # Click the Show Thumbnail Chart button.
    # Move to the current viewport of the thumbnail chart.
    ('move_to', '1621, 1018'),
    ('drag_to', '1411, 1018'),       # Center the open in the main chart.
    ('click', '1814, 76'),           # Click the Show Thumbnail Chart button.
    # Return the cursor to the previous position.
    ('back_to',)]
```

#### Open and Close Long Position ####

The following `open_close_long_position` action shows the required windows and
waits for a buy order with the maximum number of shares.  If you place the
order, it prepares a sell order for repayment.

``` ini
[HYPERSBI2 Actions]
open_close_long_position = [
    # Open Long Position
    # Show the Chart window.
    ('show_window', '個別チャート\s.*\((\d[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)'),
    # Show the Summary window.
    ('show_window', '個別銘柄\s.*\((\d[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)'),
    ('click', '208, 726'),           # Select the New Order tab.
    ('click', '541, 797'),           # Focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # Select an existing value.
    # Get the symbol from the Summary window.
    ('get_symbol', '個別銘柄\s.*\((\d[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)'),
    ('calculate_share_size', 'long'), # Calculate the share size.
    ('write_share_size',),           # Enter the calculated share size.
    ('click', '477, 819'),           # Click the Market Order button.
    ('press_key', 'tab, 3'),         # Focus on the Buy Order button.
    ('speak_text', 'Long.'),         # Speak the readiness of a buy order.
    # Return the cursor to the previous position.
    ('back_to',),
    ('wait_for_key', 'space'),       # Wait for space input.
    ('wait_for_prices', '201, 956, 470, 20, 0'), # Wait for the execution.

    # Close Long Position
    ('click', '292, 726'),           # Select the Repayment tab.
    ('click', '605, 838'),           # Focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # Select an existing value.
    ('write_share_size',),           # Enter the calculated share size.
    ('click', '448, 935'),           # Click the Market Order button.
    ('press_key', 'tab, 5'),         # Focus on the Sell Order button.
    ('count_trades',),               # Count the number of trades for the day.
    # Speak the number above and notify you of the readiness of a sell order.
    ('speak_config', 'Variables', 'number_of_trades'),
    # Return the cursor to the previous position.
    ('back_to',)]
```

### Input Map ###

The following input map maps mouse buttons and keyboard keys to actions.

``` ini
[HYPERSBI2]
input_map = {
    # The left button is used to click widgets.
    'left': '',
    # Execute the show_hide_watchlists action above.  The middle button also
    # toggles between prices and price changes in the order book.
    'middle': 'show_hide_watchlists',
    # The right button is used for context menus.
    'right': '',
    'x1': '',
    'x2': '',
    # Execute an action to open and close a short position.
    'f1': 'open_close_short_position',
    # Execute the open_close_long_position action above.
    'f2': 'open_close_long_position',
    'f3': '',
    # The F4 key is used to close a window above.
    'f4': '',
    # Execute the show_hide_watchlists action above.
    'f5': 'show_hide_watchlists',
    # Execute an action to watch favorite stocks.
    'f6': 'watch_favorites',
    # Execute the watch_tick_count action above.
    'f7': 'watch_tick_count',
    # Execute the watch_active_stocks action above.
    'f8': 'watch_active_stocks',
    # The F9 key is used for manual recording below.
    'f9': '',
    # Execute the speak_cpu_utilization action below.
    'f10': 'speak_cpu_utilization',
    # Execute the center_open action above.
    'f11': 'center_open',
    # Execute an action to undo the center_open action.
    'f12': 'undo_center_open'}
```

### Schedules ###

#### Start and Stop Manual Recording ####

The following actions and schedules start and stop manual recording of a
screencast using Nvidia ShadowPlay.

``` ini
[HYPERSBI2 Actions]
start_manual_recording = [
    # Start a new recording if one is not already in progress.
    ('is_recording', 'False', [
        ('press_hotkeys', 'alt, f9'),
        ('sleep', '2'),              # Sleep for 2 seconds.
        # Check if recording is currently in progress.
        ('is_recording', 'False', [('speak_text', 'Not recording.')])])]
stop_manual_recording = [
    # Stop a recording if one is currently in progress.
    ('is_recording', 'True', [('press_hotkeys', 'alt, f9')])]

[HYPERSBI2 Schedules]
# Trigger the start_manual_recording action at 08:50:00.
start_new_manual_recording = ('08:50:00', 'start_manual_recording')
# Trigger the stop_manual_recording action at 10:00:00.
stop_current_manual_recording = ('10:00:00', 'stop_manual_recording')
```

#### Speak CPU Utilization ####

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

#### Speak Number of Seconds until Open ####

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

| Window          | Regular Expression for Title                                                 |
|-----------------|------------------------------------------------------------------------------|
| Announcements   | `お知らせ`                                                                   |
| Summary         | `個別銘柄\s.*\((\d[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)`     |
| Watchlists      | `登録銘柄`                                                                   |
| Holdings        | `保有証券`                                                                   |
| Order Status    | `注文一覧`                                                                   |
| Chart           | `個別チャート\s.*\((\d[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)` |
| Markets         | `マーケット`                                                                 |
| Rankings        | `ランキング`                                                                 |
| Stock Lists     | `銘柄一覧`                                                                   |
| Account         | `口座情報`                                                                   |
| News            | `ニュース`                                                                   |
| Trading         | `取引ポップアップ`                                                           |
| Notifications   | `通知設定`                                                                   |
| Full Order Book | `全板\s.*\((\d[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)`         |

## License ##

[MIT](LICENSE.md)

## Link ##

  * [*Python Scripting to Assist in Day Trading on Margin Using Hyper SBI
    2*](): a blog post about computing the maximum number of shares for a
    market order on margin trading
