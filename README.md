# trading-assistant #

<!-- Python script that assists with discretionary day trading of stocks on
margin using Hyper SBI 2 -->

The `trading_assistant.py` Python script assists with discretionary day trading
of stocks on margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html). By defining an action
consisting of a sequence of commands, this script can:

  * Calculate the maximum number of shares for a market order on margin
    trading,
  * Manipulate widgets to prepare your order,
  * Trigger actions using the mouse and keyboard,
  * Schedule actions.

> **Disclaimer**: `trading_assistant.py` does not analyze or make decisions for
> you. If you operate under incorrect assumptions, the potential for loss may
> increase because of the script’s fast and frequent order placement. Use at
> your own risk.

> **Warning**: `trading_assistant.py` is currently under heavy development.
> Changes in functionality may occur at any time.

## Prerequisites ##

`trading_assistant.py` has been tested in [Python
3.11.9](https://www.python.org/downloads/release/python-3119/) for Windows with
Hyper SBI 2 on Windows 10 and requires the following packages:

  * [`chardet`](https://github.com/chardet/chardet),
    [`lxml`](https://lxml.de/index.html),
    [`pandas`](https://pandas.pydata.org/),
    [`pyarrow`](https://arrow.apache.org/docs/python/), and
    [`requests`](https://requests.readthedocs.io/en/latest/) to save the
    customer margin ratios and the previous market data from websites
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

Install each package as needed. For example:

``` powershell
winget install UB-Mannheim.TesseractOCR
winget install GnuPG.GnuPG
py -3.11 -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -U
```

## Usage ##

### Create Startup Script ###

To calculate the maximum number of shares, save the customer margin ratios from
the [*Stocks Subject to Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
page and the previous market data from the [*Most Active Stocks
Today*](https://kabutan.jp/warning/?mode=2_9&market=1) page beforehand. The
following option creates the
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ps1` startup
script that processes the above and starts Hyper SBI 2. This script forcibly
stops and restarts Hyper SBI 2 if it is already running, potentially discarding
unsaved status.

> **Note**: This option adds virtual environment activation to the startup
> script if the `.venv\Scripts\Activate.ps1` script exists.

```powershell
python trading_assistant.py -SS
```

### Configure Cash Balance and Price Limit Regions ###

Configure the cash balance and (optional) price limit regions on Hyper SBI 2
for Tesseract to recognize these prices. `trading_assistant.py` only references
a price limit if the previous closing price does not exist in the market data
in the ‘[Create Startup Script](#create-startup-script)’ section. Because a
region may contain more than one price, you need to specify the index of the
price you want to refer to.

``` powershell
python trading_assistant.py -CB
python trading_assistant.py -PL
```

### Create or Modify Action ###

Create or modify an action for processing by `trading_assistant.py`.

> **Note**: This option adds virtual environment activation to the target of a
> shortcut to the action if the `.venv\Scripts\Activate.ps1` script exists.

``` powershell
python trading_assistant.py -A ACTION
```

An action is a list of sequential tuples, where each tuple consists of a
command and its arguments. Possible commands include:

<table>
<thead>

<tr><th>Command</th>

<th>Description</th></tr>

</thead>
<tbody>

<tr><td><code>('back_to',)</code></td>

<td>Return the mouse pointer to the previous position.</td></tr>

<tr><td><code>('calculate_share_size', 'long|short')</code></td>

<td>Calculate the share size. You must call the <code>get_symbol</code> and
<code>get_cash_balance</code> commands below before using this
command.</td></tr>

<tr><td><code>('check_daily_loss_limit', 'ALERT_TEXT')</code></td>

<td>Check if the loss has reached the daily loss limit. If it has, speak the
alert text and exit. You must call the <code>get_cash_balance</code> command
below before using this command. The <code>-DLL</code> option configures the
non-percent, negative daily loss limit ratio (from -1.0 to 0.0), and the daily
loss limit is: $$\frac{cash\ balance \times utilization\ ratio \times daily\
loss\ limit\ ratio}{customer\ margin\ ratio}.$$ <strong>Note</strong>: Trading
fees, not considered here, may cause further cash balance reduction.</td></tr>

<tr><td><code>('check_maximum_daily_number_of_trades', 'ALERT_TEXT')</code></td>

<td>Check if the current number of trades for the day exceeds the maximum daily
number of trades. If it does, speak the alert text and exit. You must call the
<code>count_trades</code> command below before using this command. The
<code>-MDN</code> option configures the maximum daily number of trades. A zero
value for it indicates unlimited trades.</td></tr>

<tr><td><code>('click', 'X, Y')</code></td>

<td>Click on the coordinates <code>X</code> and <code>Y</code>.</td></tr>

<tr><td><code>('click_widget', 'IMAGE_FILE', 'X, Y, WIDTH, HEIGHT')</code></td>

<td>Wait for and locate the widget image in the region, then click it. The
<code>IMAGE_FILE</code> must reside in the <code>HYPERSBI2</code> subdirectory
of the same directory as the configuration file.</td></tr>

<tr><td><code>('copy_symbols_from_market_data',)</code></td>

<td>Copy symbols from the current market data to the clipboard.</td></tr>

<tr><td><code>('copy_symbols_from_column', 'X, Y, WIDTH, HEIGHT')</code></td>

<td>Recognize an alphanumeric column in the region, then copy symbols to the
clipboard.</td></tr>

<tr><td><code>('count_trades',[ 'CHAPTER_OFFSET'])</code></td>

<td>Count the number of trades for the day. Additionally, write a chapter
section for <a href="https://ffmpeg.org/ffmpeg-formats.html#Metadata-1">FFmpeg
metadata</a> when Nvidia ShadowPlay records a screencast. The ‘CHAPTER_OFFSET’
parameter specifies the offset in seconds for the chapter’s start time. You
must call this command after the execution of an order.</td></tr>

<tr><td><code>('drag_to', 'X, Y')</code></td>

<td>Drag the mouse pointer to the position.</td></tr>

<tr><td><code>('get_cash_balance',)</code></td>

<td>Recognize the cash balance in the cash balance region specified in the ‘<a
href="#configure-cash-balance-and-price-limit-regions">Configure Cash Balance
and Price Limit Regions</a>’ section.</td></tr>

<tr><td><code>('get_symbol', 'TITLE_REGEX')</code></td>

<td>Get the symbol from a window title.</td></tr>

<tr><td><code>('hide_window', 'TITLE_REGEX')</code></td>

<td>Hide a window.</td></tr>

<tr><td><code>('move_to', 'X, Y')</code></td>

<td>Move the mouse pointer to the position.</td></tr>

<tr><td><code>('press_hotkeys', 'KEY[, ...]')</code></td>

<td>Press the hotkeys.</td></tr>

<tr><td><code>('press_key', 'KEY[, PRESSES]')</code></td>

<td>Press the key.</td></tr>

<tr><td><code>('show_hide_window', 'TITLE_REGEX')</code></td>

<td>Show or hide a window.</td></tr>

<tr><td><code>('show_window', 'TITLE_REGEX')</code></td>

<td>Show a window.</td></tr>

<tr><td><code>('sleep', 'PERIOD')</code></td>

<td>Sleep for the period.</td></tr>

<tr><td><code>('speak_config', 'SECTION', 'OPTION')</code></td>

<td>Speak the configuration value.</td></tr>

<tr><td><code>('speak_cpu_utilization', 'INTERVAL')</code></td>

<td>Calculate CPU utilization for the interval and speak it.</td></tr>

<tr><td><code>('speak_seconds_until_time', '%H:%M:%S')</code></td>

<td>Speak seconds until the time.</td></tr>

<tr><td><code>('speak_show_text', 'TEXT')</code></td>

<td>Speak and show the text.</td></tr>

<tr><td><code>('speak_text', 'TEXT')</code></td>

<td>Speak the text.</td></tr>

<tr><td><code>('toggle_indicator',)</code></td>

<td>Toggle the indicator.</td></tr>

<tr><td><code>('wait_for_key', 'KEY')</code></td>

<td>Wait for the keyboard input.</td></tr>

<tr><td><code>('wait_for_price', 'X, Y, WIDTH, HEIGHT, INDEX')</code></td>

<td>Wait until <code>trading_assistant.py</code> recognizes a decimal number in
the region.</td></tr>

<tr><td><code>('wait_for_window', 'TITLE_REGEX')</code></td>

<td>Wait for a window.</td></tr>

<tr><td><code>('write_chapter', 'CURRENT_TITLE'[, 'PREVIOUS_TITLE'])</code></td>

<td>Write a chapter section for FFmpeg metadata. When creating a new metadata
file, the <code>PREVIOUS_TITLE</code> parameter gives the title to the chapter
that precedes the current chapter.</td></tr>

<tr><td><code>('write_share_size',)</code></td>

<td>Write the calculated share size.</td></tr>

<tr><td><code>('write_string', 'STRING')</code></td>

<td>Write the string.</td></tr>

<tr><th>Control Flow Command</th>

<th>Description</th></tr>

<tr><td><code>('is_now_after', '%H:%M:%S', ACTION|'ACTION')</code></td>

<td>Execute the action if the current system time is after the time.</td></tr>

<tr><td><code>('is_now_before', '%H:%M:%S', ACTION|'ACTION')</code></td>

<td>Execute the action if the current system time is before the time.</td></tr>

<tr><td><code>('is_recording', 'BOOL', ACTION|'ACTION')</code></td>

<td>Execute the action if recording a screencast is the bool value.</td></tr>

</tbody>
</table>

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
configuration file stores the configurations. If your GnuPG-encrypted
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ini.gpg`
configuration file exists, `trading_assistant.py` will read from and write to
that file. By default, it uses the default key pair of GnuPG. However, you can
also specify a key fingerprint as the value of the `fingerprint` option in the
`General` section of your configuration file.

### Action Argument Completion ###

The `-A` and `-D` options generate completion scripts for action arguments.
They are located at `%LOCALAPPDATA%\trading-assistant\HYPERSBI2\completion.ps1`
for PowerShell 7 and `%LOCALAPPDATA%\trading-assistant\HYPERSBI2\completion.sh`
for Bash.

To enable action argument completion in PowerShell 7, source the script in your
current shell:

``` powershell
. $Env:LOCALAPPDATA\trading-assistant\HYPERSBI2\completion.ps1
```

To enable action argument completion in Bash, source the script in your current
shell:

``` shell
. $LOCALAPPDATA/trading-assistant/HYPERSBI2/completion.sh
```

After sourcing the script, you can use tab completion for action arguments when
running `trading_assistant.py` with the `-a`, `-A`, or `-D` options:

``` powershell
python trading_assistant.py -a a⇥
python trading_assistant.py -a action
```

### Options ###

  * `-P BROKERAGE PROCESS|EXECUTABLE_PATH`: set the brokerage and the process
    [defaults: `SBI Securities` and `HYPERSBI2`]
  * `-r`: save the customer margin ratios
  * `-d`: save the previous market data
  * `-s`: start the scheduler
  * `-l`: start the mouse and keyboard listeners
  * `-a ACTION`: execute an action
  * `-B [OUTPUT_DIRECTORY]`: generate a WSL Bash script to activate and run
    this script
  * `-PS [OUTPUT_DIRECTORY]`: generate a PowerShell 7 script to activate and
    run this script
  * `-SS`: configure the startup script, create a shortcut to it, and exit
  * `-S`: configure schedules and exit
  * `-L`: configure the input map for buttons and keys and exit
  * `-A ACTION`: configure an action, create a shortcut to it, and exit
  * `-CB`: configure the cash balance region and exit
  * `-U`: configure the utilization ratio of the cash balance and exit
  * `-PL`: configure the price limit region and exit
  * `-DLL`: configure the daily loss limit ratio and exit
  * `-MDN`: configure the maximum daily number of trades and exit.
  * `-D SCRIPT_BASE|ACTION`: delete the startup script or an action, delete the
    shortcut to it, and exit
  * `-C`: check configuration changes and exit

## Examples ##

The following are some examples of the configurations in my environment.
Because `trading_assistant.py` will execute anything that is an executable
configuration, you should not use these configurations without understanding
them.

> **Note**: I tested these examples in the environment with 1080p resolution,
> the maximized ‘Watchlists’ window, the left-snapped ‘Summary’ window, and the
> right-snapped ‘Chart’ window. Additionally, my Hyper SBI 2 settings differ
> from the default settings.

### Startup Script ###

The following action and options configure the processing of Hyper SBI 2 pre-
and post-startup and during running.

``` ini
[HYPERSBI2 Startup Script]
# Save the customer margin ratios and the previous market data, start the mouse
# and keyboard listeners and the scheduler, and execute the 'login' action in
# the 'Login' section.
post_start_options = -rdlsa login
# Start the mouse and keyboard listeners and the scheduler, and execute the
# 'login' action.
running_options = -lsa login
```

### Actions ###

#### Login ####

The following `login` action waits for the ‘Login’ dialog box to appear and
then clicks its button. Next, it enters your trading password and authenticates
in the ‘Pre-authentication of Trading Password’ dialog box. If you want to
include your password as the value of an option, as demonstrated in this
example, refer to the ‘[Encrypt Configuration
File](#encrypt-configuration-file)’ section.

``` ini
[HYPERSBI2 Actions]
login = [
    # Wait for and locate the 'Login' button in the region, then click it.
    ('click_widget', 'login.png', '749, 309, 402, 384'),
    # Wait for the 'Pre-authentication of Trading Password' dialog box.
    ('wait_for_window', '取引パスワードのプレ認証'),
    ('show_window', '取引パスワードのプレ認証'), # Show the dialog box.
    ('press_key', 'tab, 2'),         # Focus on the trading password field.
    ('write_string', 'TRADING_PASSWORD'), # Enter your trading password.
    ('press_key', 'tab, 2'),         # Focus on the 'Acknowledgment' checkbox.
    ('press_key', 'space'),          # Check the checkbox.
    ('press_key', 'tab, 2'),         # Focus on the 'Authenticate' button.
    ('press_key', 'enter'),          # Press the button.
    # Wait for and locate the 'OK' button in the region, then click it.
    ('click_widget', 'ok.png', '783, 442, 334, 118'),
    ('hide_window', '登録銘柄'),     # Hide the 'Watchlists' window.
    # Show the 'Chart' window.
    ('show_window', '個別チャート\\s.*\\(([1-9][\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    ('sleep', '0.4'),                # Sleep for 0.4 seconds.
    # Execute the 'center_open_1_minute_chart' action in the 'Center Open for
    # 1-minute Chart' section if Hyper SBI 2 restarts during ${Market
    # Data:opening_time}-${HYPERSBI2:end_time}.
    ('is_now_after', '${Market Data:opening_time}', [
        ('is_now_before', '${HYPERSBI2:end_time}',
         'center_open_1_minute_chart')]),
    # Show the 'Summary' window.
    ('show_window', '個別銘柄\\s.*\\(([1-9][\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    # Return the mouse pointer to the previous position.
    ('back_to',)
    # Check the 'Skip Confirmation Screen' checkbox if the current system time
    # is before ${HYPERSBI2:end_time}.
    ('is_now_before', '${HYPERSBI2:end_time}', [
        ('click', '231, 727'),
        ('click', '278, 838'),
        ('back_to',)]),
    # Open the 'News' window if the current system time is before the open.
    ('is_now_before', '${Market Data:opening_time}', [
        ('press_hotkeys', 'ctrl, n')]),
    # Start a new recording if one is not already in progress at
    # 08:50:00-${HYPERSBI2:end_time}. This is a fallback if the
    # 'start_trading_recording' schedule in the 'Start and Stop Manual
    # Recording' section does not start recording.
    ('is_now_after', '08:50:00', [
        ('is_now_before', '${HYPERSBI2:end_time}', 'start_manual_recording')])]
```

#### Replace Watchlist with Hyper SBI 2 Ranking ####

The following `watch_tick_count` action replaces the stocks in the ‘Watchlists’
window with new ones recognized in the ‘Rankings’ window.

> **Note**: Hyper SBI updates the ‘Rankings’ window in real time, but the text
> recognition by Tesseract is not as accurate as the scraped market data in the
> ‘[Create Startup Script](#create-startup-script)’ section.

``` ini
[HYPERSBI2 Actions]
watch_tick_count = [
    ('show_window', '登録銘柄'),     # Show the 'Watchlists' window.
    ('press_hotkeys', 'ctrl, 7'),    # Open the 'Rankings' window.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    ('click', '38, 39'),             # Select the 'Rankings' tab.
    ('click', '88, 311'),            # Select the 'Tick Count' ranking.
    ('click', '310, 63'),            # Click the 'Prime Market' button.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    # Recognize an alphanumeric column in the region, then copy symbols to the
    # clipboard.
    ('copy_symbols_from_column', '331, 152, 63, 661'),
    ('press_hotkeys', 'alt, f4'),    # Close the window.
    ('click', '41, 115'),            # Select the second watchlist.
    ('click', '1612, 41'),           # Select the 'List' view.
    ('press_key', 'tab, 3'),         # Focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # Select all stocks.
    ('press_key', 'del'),            # Delete them.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # Paste the symbols copied above.
    ('press_key', 'enter'),          # Confirm the registration.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('click', '1676, 41'),           # Select the 'Tile' view.

    # Optional Commands
    ('press_key', 'tab, 6'),         # Focus on the number of columns field.
    ('press_key', '6'),              # Enter 6.
    ('press_key', 'tab, 6'),         # Focus on the 'Chart' button.
    ('press_key', 'space'),          # Press the button.
    ('click', '524, 88'),            # Click the time frame drop-down menu.
    ('press_key', 'home'),           # Move to the first item.
    ('press_key', 'down, 2'),        # Select the '5-minute' time frame.
    ('press_key', 'enter'),          # Close the menu.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    ('click', '602, 88'),            # Select the '1-day' date range.
    # Return the mouse pointer to the previous position.
    ('back_to',)]
```

#### Replace Watchlist with Market Data on Website ####

The following `watch_active_stocks` action replaces the stocks in the
‘Watchlists’ window with new ones scraped from the current market data in the
‘[Create Startup Script](#create-startup-script)’ section.

> **Note**: The free market data provided by Kabutan has a 20-minute delay.

``` ini
[HYPERSBI2 Actions]
watch_active_stocks = [
    # Copy symbols from the current market data to the clipboard.
    ('copy_symbols_from_market_data',),
    ('show_window', '登録銘柄'),     # Show the 'Watchlists' window.
    ('click', '41, 138'),            # Select the third watchlist.
    ('click', '1612, 41'),           # Select the 'List' view.
    ('press_key', 'tab, 3'),         # Focus on the stock list pane.
    ('press_hotkeys', 'ctrl, a'),    # Select all stocks.
    ('press_key', 'del'),            # Delete them.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('press_hotkeys', 'ctrl, v'),    # Paste the symbols copied above.
    ('press_key', 'enter'),          # Confirm the registration.
    ('sleep', '0.6'),                # Sleep for 0.6 seconds.
    ('click', '1676, 41'),           # Select the 'Tile' view.

    # Optional Commands
    ('press_key', 'tab, 6'),         # Focus on the number of columns field.
    ('press_key', '6'),              # Enter 6.
    ('press_key', 'tab, 6'),         # Focus on the 'Chart' button.
    ('press_key', 'space'),          # Press the button.
    ('press_key', 'tab, 6'),         # Focus on the time frame drop-down menu.
    ('press_hotkeys', 'alt, down'),  # Open the menu.
    ('press_key', 'home'),           # Move to the first item.
    ('press_key', 'down, 2'),        # Select the '5-minute' time frame.
    ('press_key', 'enter'),          # Close the menu.
    ('sleep', '0.2'),                # Sleep for 0.2 seconds.
    ('click', '602, 88'),            # Select the '1-day' date range.
    # Return the mouse pointer to the previous position.
    ('back_to',)]
```

#### Center Open for 1-minute Chart ####

The following `center_open_1_minute_chart` action centers the open in the
1-minute chart of the ‘Chart’ window.

``` ini
[HYPERSBI2 Actions]
center_open_1_minute_chart = [
    # Show the 'Chart' window.
    ('show_window', '個別チャート\\s.*\\(([1-9][\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    ('click', '1814, 76'),           # Click the 'Show Thumbnail Chart' button.
    # Move to the current viewport of the thumbnail chart.
    ('move_to', '1621, 1018'),
    ('drag_to', '1411, 1018'),       # Center the open in the 1-minute chart.
    ('click', '1814, 76'),           # Click the 'Show Thumbnail Chart' button.
    # Return the mouse pointer to the previous position.
    ('back_to',)]
```

#### Open and Close Long Position ####

The following `open_close_long_position` action shows the required windows and
waits for a buy order with the maximum number of shares. If you place the
order, it prepares a sell order for repayment.

``` ini
[HYPERSBI2 Actions]
open_close_long_position = [
    # Open Long Position
    # Show the 'Summary' window.
    ('show_window', '個別銘柄\\s.*\\(([1-9][\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    ('click', '231, 727'),           # Select the 'New Order' tab.
    ('click', '565, 796'),           # Focus on the 'Share Size' text box.
    ('press_hotkeys', 'ctrl, a'),    # Select the existing value.
    # Get the symbol from the 'Summary' window.
    ('get_symbol', '個別銘柄\\s.*\\(([1-9][\\dACDFGHJKLMNPRSTUWXY]\\d[\\dACDFGHJKLMNPRSTUWXY]5?)\\)'),
    # Recognize the cash balance on the 'Summary' window.
    ('get_cash_balance',),
    # Check if the loss has reached the daily loss limit. If it has, speak the
    # alert text and exit.
    ('check_daily_loss_limit', 'Daily loss limit hit.'),
    # Check if the current number of trades for the day exceeds the maximum
    # daily number of trades. If it does, speak the alert text and exit.
    ('check_maximum_daily_number_of_trades',
     'Maximum daily number of trades exceeded.'),
    ('calculate_share_size', 'long'), # Calculate the share size.
    ('write_share_size',),           # Enter the calculated share size.
    ('click', '499, 818'),           # Click the 'Market Order' button.
    ('press_key', 'tab, 3'),         # Focus on the 'Buy Order' button.
    ('speak_text', 'Long.'),         # Speak the readiness of the buy order.
    # Return the mouse pointer to the previous position.
    ('back_to',),
    ('wait_for_key', 'space'),       # Wait for space input.
    # Wait for the order execution.
    ('wait_for_price', '224, 956, 470, 20, 0'),

    # Close Long Position
    ('click', '315, 727'),           # Select the 'Repayment' tab.
    ('click', '628, 837'),           # Focus on the 'Share Size' text box.
    ('press_hotkeys', 'ctrl, a'),    # Select the existing value.
    ('write_share_size',),           # Enter the calculated share size.
    ('click', '470, 932'),           # Click the 'Market Order' button.
    ('press_key', 'tab, 5'),         # Focus on the 'Sell Order' button.
    ('count_trades', '-10.0'),       # Count the number of trades for the day.
    # Speak the number above and notify you of the readiness of the sell order.
    ('speak_config', 'HYPERSBI2 Variables', 'current_number_of_trades'),
    ('back_to',)]
```

### Input Map ###

The following input map maps mouse buttons and keyboard keys to actions.

``` ini
[HYPERSBI2]
input_map = {
    # The left button is used to click widgets.
    'left': '',
    # Execute an action to show or hide the 'Watchlists' window. The middle
    # button also toggles between prices and price changes in the order books.
    'middle': 'show_hide_watchlists',
    # The right button is used for context menus.
    'right': '',
    'x1': '',
    'x2': '',
    # Execute an action to open and close a short position.
    'f1': 'open_close_short_position',
    # Execute the 'open_close_long_position' action in the 'Open and Close Long
    # Position' section.
    'f2': 'open_close_long_position',
    'f3': '',
    # The F4 key is used to close a window.
    'f4': '',
    # Execute the 'show_hide_watchlists' action above.
    'f5': 'show_hide_watchlists',
    # Execute an action to watch favorite stocks.
    'f6': 'watch_favorites',
    # Execute the 'watch_tick_count' action in the 'Replace Watchlist with
    # Hyper SBI 2 Ranking' section.
    'f7': 'watch_tick_count',
    # Execute the 'watch_active_stocks' action in the 'Replace Watchlist with
    # Market Data on Website' section.
    'f8': 'watch_active_stocks',
    # The F9 key is used for manual recording in the 'Start and Stop Manual
    # Recording' section.
    'f9': '',
    # Execute the 'speak_cpu_utilization' action in the 'Speak CPU Utilization'
    # section.
    'f10': 'speak_cpu_utilization',
    # Execute the 'center_open_1_minute_chart' action in the 'Center Open for
    # 1-minute Chart' section.
    'f11': 'center_open_1_minute_chart',
    # Execute the 'toggle_indicator' action below.
    'f12': 'toggle_indicator'}

[HYPERSBI2 Actions]
toggle_indicator = [
    ('toggle_indicator',)]           # Toggle the indicator.
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
        ('sleep', '2'),
        ('is_recording', 'False', [
            ('speak_text', 'Not recording.')])])]
create_pre_trading_chapter = [
    # Write a chapter section for FFmpeg metadata.
    ('write_chapter', 'Pre-trading', 'Pre-market')]
stop_manual_recording = [
    # Stop a recording if one is currently in progress.
    ('is_recording', 'True', [
        ('press_hotkeys', 'alt, f9')])]

[HYPERSBI2 Schedules]
# Trigger the 'start_manual_recording' action at 08:50:00.
start_trading_recording = ('08:50:00', 'start_manual_recording')
# Trigger the 'create_pre_trading_chapter' action at the open.
start_pre_trading_chapter = ('${Market Data:opening_time}',
                             'create_pre_trading_chapter')
# Trigger the 'stop_manual_recording' action at ${HYPERSBI2:end_time}.
stop_trading_recording = ('${HYPERSBI2:end_time}', 'stop_manual_recording')
```

#### Speak CPU Utilization ####

The following action and schedule calculate CPU utilization and speak it.

``` ini
[HYPERSBI2 Actions]
speak_cpu_utilization = [
    # Calculate CPU utilization for 1 second and speak it.
    ('speak_cpu_utilization', '1')]

[HYPERSBI2 Schedules]
# Trigger the 'speak_cpu_utilization' action at 08:50:10.
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
# Trigger the 'speak_seconds_until_open' action at 08:59:00.
speak_60_seconds_until_open = ('08:59:00', 'speak_seconds_until_open')
# Trigger the 'speak_seconds_until_open' action at 08:59:30.
speak_30_seconds_until_open = ('08:59:30', 'speak_seconds_until_open')
```

## Known Issues ##

  * The `toggle_indicator` command in the ‘[Create or Modify
    Action](#create-or-modify-action)’ section does not operate as expected
    when used as an argument to the `is_now_after`, `is_now_before`, or
    `is_recording` commands.

## License ##

[MIT](LICENSE.md)

## Appendix ##

### Hyper SBI 2 Window Titles ###

| Regular Expression for Window Title                                             | Window          |
|---------------------------------------------------------------------------------|-----------------|
| `お知らせ`                                                                      | Announcements   |
| `個別銘柄\s.*\(([1-9][\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)`     | Summary         |
| `登録銘柄`                                                                      | Watchlists      |
| `保有証券`                                                                      | Holdings        |
| `注文一覧`                                                                      | Order Status    |
| `個別チャート\s.*\(([1-9][\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)` | Chart           |
| `マーケット`                                                                    | Markets         |
| `ランキング`                                                                    | Rankings        |
| `銘柄一覧`                                                                      | Stock Lists     |
| `口座情報`                                                                      | Account         |
| `ニュース`                                                                      | News            |
| `取引ポップアップ`                                                              | Trading         |
| `通知設定`                                                                      | Notifications   |
| `全板\s.*\(([1-9][\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?)\)`         | Full Order Book |

## Link ##

  * [*Python Scripting to Assist with Day Trading on Margin Using Hyper SBI
    2*](https://carmine560.blogspot.com/2023/11/python-scripting-to-assist-with-day.html):
    a blog post about computing the maximum number of shares for a market order
    on margin trading
