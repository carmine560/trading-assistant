# trading-assistant

<!-- Python script that assists with discretionary day trading of stocks on
margin using Hyper SBI 2 -->

The `trading_assistant.py` Python script assists with discretionary day trading
of stocks on margin using [Hyper SBI
2](https://go.sbisec.co.jp/lp/lp_hyper_sbi2_211112.html). By defining an action
consisting of a sequence of commands, this script can:

  * Calculate the maximum number of shares for a market order on margin trading
  * Manipulate widgets to prepare your order
  * Trigger actions using the mouse and keyboard
  * Schedule actions

> **Disclaimer**: `trading_assistant.py` does not analyze or make decisions for
> you. If you operate under incorrect assumptions, the potential for loss may
> increase because of the script’s fast and frequent order placement. You
> assume full responsibility for all trading decisions and outcomes.

## Prerequisites

`trading_assistant.py` has been tested in [Python
3.13.9](https://www.python.org/downloads/release/python-3139/) for Windows with
Hyper SBI 2 on Windows 10 with ESU and requires the following packages:

  * [`chardet`](https://github.com/chardet/chardet),
    [`lxml`](https://lxml.de/index.html),
    [`pandas`](https://pandas.pydata.org/),
    [`pyarrow`](https://arrow.apache.org/), and
    [`requests`](https://requests.readthedocs.io/en/latest/) to save the
    customer margin ratios and the previous market data from websites
  * [`pywin32`](https://github.com/mhammond/pywin32) to access Windows APIs
  * [`pytesseract`](https://github.com/madmaze/pytesseract) to invoke
    [Tesseract](https://github.com/tesseract-ocr/tesseract) to recognize prices
    and securities codes on Hyper SBI 2
  * [`pyautogui`](https://github.com/asweigart/pyautogui) to automate
    manipulation of Hyper SBI 2
  * [`pynput`](https://github.com/moses-palmer/pynput) to monitor the mouse and
    keyboard
  * [`psutil`](https://github.com/giampaolo/psutil) to calculate CPU
    utilization
  * [`prompt_toolkit`](https://github.com/prompt-toolkit/python-prompt-toolkit)
    to complete possible values or a previous value in configuring
  * [`python-gnupg`](https://github.com/vsajip/python-gnupg) to invoke
    [GnuPG](https://gnupg.org/index.html) to encrypt and decrypt the
    configuration file

Install each package as needed. For example:

``` powershell
winget install UB-Mannheim.TesseractOCR
winget install GnuPG.GnuPG
git clone --recurse-submodules git@github.com:carmine560/trading-assistant.git
cd trading-assistant
# Run 'git submodule update --init' if you cloned without
# '--recurse-submodules'.
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -U
```

## Usage

### Create Startup Script

To calculate the maximum number of shares, save the customer margin ratios from
the [*Stocks Subject to Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
page and the previous market data from the [*Most Active Stocks
Today*](https://kabutan.jp/warning/?mode=2_9&market=1) page beforehand. The
following option creates the
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\hypersbi2_assistant.ps1` startup
script that processes the above and starts Hyper SBI 2. This script forcibly
stops and restarts Hyper SBI 2 if it is already running, potentially discarding
unsaved status.

> **Note**: This option adds virtual environment activation to the startup
> script if the `.venv\Scripts\Activate.ps1` script exists.

```powershell
python trading_assistant.py -SS
```

### Configure Cash Balance and Price Limit Regions

Configure the cash balance and (optional) price limit regions on Hyper SBI 2
for Tesseract to recognize these prices. `trading_assistant.py` only references
a price limit if the previous closing price does not exist in the market data
in the “[Create Startup Script](#create-startup-script)” section. Because a
region may contain more than one price, you need to specify the index of the
price you want to refer to.

``` powershell
python trading_assistant.py -CB
python trading_assistant.py -PL
```

### Create or Modify Action

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

<td>Return the mouse pointer to its previous position.</td></tr>

<tr><td><code>('calculate_share_size', 'long|short')</code></td>

<td>Calculate the share size. You must call the <code>get_symbol</code> and
<code>get_cash_balance</code> commands below before using this
command.</td></tr>

<tr><td><code>('check_daily_loss_limit', 'ALERT_TEXT')</code></td>

<td>Check if the loss has reached the daily loss limit. If it has, speak the
alert text and exit. You must call the <code>get_cash_balance</code> command
below before using this command. The <code>-DLL</code> option configures the
non-percent, negative daily loss limit ratio (from -1.0 to 0.0), and the daily
loss limit is: $$cash\ balance \times utilization\ ratio \times daily\ loss\
limit\ ratio$$. <strong>Note</strong>: Trading fees, not considered here, may
cause further cash balance reduction.</td></tr>

<tr><td><code>('check_maximum_daily_number_of_trades', 'ALERT_TEXT')</code></td>

<td>Check if the current number of trades for the day exceeds the maximum daily
number of trades. If it does, speak the alert text and exit. You must call the
<code>count_trades</code> command below before using this command. The
<code>-MDN</code> option configures the maximum daily number of trades. A zero
value for it indicates unlimited trades.</td></tr>

<tr><td><code>('click', 'X, Y')</code></td>

<td>Click at the coordinates <code>X</code> and <code>Y</code>.</td></tr>

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
metadata</a> when Nvidia ShadowPlay records a screencast. The “CHAPTER_OFFSET”
parameter specifies the offset in seconds for the chapter’s start time. You
must call this command after the execution of an order.</td></tr>

<tr><td><code>('drag_to', 'X, Y')</code></td>

<td>Drag the mouse pointer to the position.</td></tr>

<tr><td><code>('execute_action', ACTION|'ACTION')</code></td>

<td>Execute the action. If the action fails, cancel the current
action.</td></tr>

<tr><td><code>('get_cash_balance',)</code></td>

<td>Recognize the cash balance in the cash balance region specified in the “<a
href="#configure-cash-balance-and-price-limit-regions">Configure Cash Balance
and Price Limit Regions</a>” section.</td></tr>

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

<tr><td><code>('right_click', 'X, Y')</code></td>

<td>Right-click at the coordinates <code>X</code> and <code>Y</code>.</td></tr>

<tr><td><code>('show_hide_indicator',)</code></td>

<td>Show or hide the indicator.</td></tr>

<tr><td><code>('show_hide_window', 'TITLE_REGEX')</code></td>

<td>Show or hide a window.</td></tr>

<tr><td><code>('show_window', 'TITLE_REGEX'[, 'MAX_COUNT'])</code></td>

<td>Show a window. The <code>MAX_COUNT</code> parameter (default 1) limits the
number of windows to show.</td></tr>

<tr><td><code>('sleep', 'PERIOD')</code></td>

<td>Sleep for the period.</td></tr>

<tr><td><code>('speak_config', 'SECTION', 'OPTION')</code></td>

<td>Speak the configuration value.</td></tr>

<tr><td><code>('speak_cpu_utilization', 'INTERVAL')</code></td>

<td>Calculate CPU utilization for the interval and speak it.</td></tr>

<tr><td><code>('speak_seconds_since_time', '%H:%M:%S')</code></td>

<td>Speak seconds since the time.</td></tr>

<tr><td><code>('speak_seconds_until_time', '%H:%M:%S')</code></td>

<td>Speak seconds until the time.</td></tr>

<tr><td><code>('speak_show_text', 'TEXT')</code></td>

<td>Speak and show the text.</td></tr>

<tr><td><code>('speak_text', 'TEXT')</code></td>

<td>Speak the text.</td></tr>

<tr><td><code>('wait_for_key', 'KEY'[, ACTION|'ACTION'])</code></td>

<td>Wait for a key press. Pressing the <code>Esc</code> key cancels the current
action and executes the specified action, if provided.</td></tr>

<tr><td><code>('wait_for_key_count_down', 'KEY'[, ACTION|'ACTION'])</code></td>

<td>Wait for a key press and speak a countdown until the next 1-minute candle
close. Pressing the <code>Esc</code> key cancels the current action and
executes the specified action, if provided.</td></tr>

<tr><td><code>('wait_for_price', 'X, Y, WIDTH, HEIGHT, INDEX'[, ACTION|'ACTION'])</code></td>

<td>Wait until <code>trading_assistant.py</code> recognizes a decimal number in
the region. Pressing the <code>Esc</code> key cancels the current action and
executes the specified action, if provided.</td></tr>

<tr><td><code>('wait_for_window', 'TITLE_REGEX'[, ACTION|'ACTION'])</code></td>

<td>Wait for a window. Pressing the <code>Esc</code> key cancels the current
action and executes the specified action, if provided.</td></tr>

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

<td>Execute the action if a screencast is being recorded.</td></tr>

<tr><td><code>('is_trading_day', 'BOOL', ACTION|'ACTION')</code></td>

<td>Execute the action if today is a trading day.</td></tr>

</tbody>
</table>

### Execute Action

Execute a created or modified action.

``` powershell
python trading_assistant.py -a ACTION
```

### Trigger Actions Using Mouse and Keyboard

You can also trigger actions using the mouse and keyboard by configuring the
input map for mapping buttons and keys to them.

``` powershell
python trading_assistant.py -L
```

Then, start the mouse and keyboard listeners while Hyper SBI 2 is running.

``` powershell
python trading_assistant.py -l
```

### Schedule Actions

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

### Encrypt Configuration File

The GnuPG-encrypted configuration file,
`%LOCALAPPDATA%\trading-assistant\HYPERSBI2\trading_assistant.ini.gpg`, stores
the configurations. By default, `trading_assistant.py` uses the default key
pair of GnuPG. However, you can also specify a key fingerprint as the value of
the `fingerprint` option in the `General` section in your configuration file.

### Complete Action Argument

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

### Options

  * `-P BROKERAGE PROCESS|EXECUTABLE_PATH`: set the brokerage and the process
    [defaults: `SBI Securities` and `HYPERSBI2`]
  * `-r`: save the customer margin ratios
  * `-d`: save the previous market data
  * `-s`: start the scheduler
  * `-l`: start the mouse and keyboard listeners
  * `-a ACTION`: execute an action
  * `-BS`: save a WSL Bash script to `%USERPROFILE%\Downloads` to launch this
    script and exit
  * `-PS`: save a PowerShell 7 script to `%USERPROFILE%\Downloads` to launch
    this script and exit
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

## Examples

Visit the
“[Examples](https://github.com/carmine560/trading-assistant/wiki#examples)”
section in the wiki for practical demonstrations of `trading_assistant.py`.

## License

This project is licensed under the [MIT License](LICENSE). The `.gitignore`
file is sourced from [`gitignore`](https://github.com/github/gitignore), which
is licensed under the CC0-1.0 license.

## Appendix

### Hyper SBI 2 Window Titles

| Regular Expression for Window Title                          | Window          |
|--------------------------------------------------------------|-----------------|
| `お知らせ`                                                   | Announcements   |
| `個別銘柄\s.*\((${Market Data:securities_code_regex})\)`     | Summary         |
| `登録銘柄`                                                   | Watchlists      |
| `保有証券`                                                   | Holdings        |
| `注文一覧`                                                   | Order Status    |
| `個別チャート\s.*\((${Market Data:securities_code_regex})\)` | Chart           |
| `マーケット`                                                 | Markets         |
| `ランキング`                                                 | Rankings        |
| `銘柄一覧`                                                   | Stock Lists     |
| `口座情報`                                                   | Account         |
| `ニュース`                                                   | News            |
| `取引ポップアップ`                                           | Trading         |
| `通知設定`                                                   | Notifications   |
| `全板\s.*\((${Market Data:securities_code_regex})\)`         | Full Order Book |

## Link

  * [*Python Scripting to Assist with Day Trading on Margin Using Hyper SBI
    2*](https://carmine560.blogspot.com/2023/11/python-scripting-to-assist-with-day.html):
    a blog post about computing the maximum number of shares for a market order
    on margin trading
