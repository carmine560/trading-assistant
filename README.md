# place-trades #

<!-- Python script that assists in discretionary day trading of stocks
on margin using Hyper SBI 2 -->

<!-- hypersbi2 pandas pyautogui pytesseract python pywin32 tesseract
-->

`place-trades.py` assists in discretionary day trading of stocks on
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
  * [Tesseract](https://tesseract-ocr.github.io/) to recognize prices
    on Hyper SBI 2
  * [pytesseract](https://github.com/madmaze/pytesseract) to invoke
    Tesseract
  * [pyautogui](https://pyautogui.readthedocs.io/en/latest/index.html)
    to automate interactions with Hyper SBI 2
  * (optional)
    [tabula-py](https://tabula-py.readthedocs.io/en/latest/index.html)
    to save ETF trading units from a website

Install each package as needed.  For example:

``` shell
pip install pandas
pip install pywin32
pip install pytesseract
pip install pyautogui
```

## Usage ##

### Generate Startup Script ###

In order to calculate a maximum share size, save customer margin
ratios and the previous market data from [*SBI Securities Margin
Regulations*](https://search.sbisec.co.jp/v2/popwin/attention/stock/margin_M29.html)
and [*Download Stock Market Data*](https://kabudata-dll.com/) in
advance.  The following option generates a startup script
`place-trades.ps1` that processes them and starts Hyper SBI 2.

``` shell
place-trades.py -g
```

### Configure Cash Balance and Price Limit Regions ###

Configure the cash balance and (optional) price limit regions on Hyper
SBI 2 in order that Tesseract recognizes these prices.  A price limit
is only referenced if the previous closing price does not exist.
Because there can be multiple prices in a region, specify the index of
the price.  These configurations are saved in the configuration file
`place-trades.ini`.

``` shell
place-trades.py -C X Y WIDTH HEIGHT INDEX
place-trades.py -L X Y WIDTH HEIGHT INDEX
```

### Create or Modify Action ###

Create or modify an action to be processed by this script.

``` shell
place-trades.py -M ACTION
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
    ('calculate_share_size', 'POSITION'), # calculate a share size and copy it.
    ('click', 'X, Y'),               # click.
    ('get_symbol', 'TITLE_REGEX'),   # get the symbol from a window title.
    ('hide_window', 'TITLE_REGEX'),  # hide a window.
    ('move_to', 'X, Y'),             # move the cursor to a position.
    ('press_hotkeys', 'KEY, ...'),   # press hotkeys.
    ('press_key', 'KEY, PRESSES'),   # press a key.
    ('show_window', 'TITLE_REGEX'),  # show a window.
    ('wait_for_window', 'ADDITIONAL_PERIOD'), # wait for a window and an additional period.
]
```

#### Example 1: Login ####

The following example `login` waits for the Login window showing, and
then clicks the Login button.

``` python
login = [
    ('wait_for_window', '^HYPER SBI 2$, 1.0'), # wait for the Login window showing.
    ('click', '960, 527'),           # click the Login button.
]
```

#### Example 2: Open Long Position ####

The following example `open_long_position` shows the required windows,
enters the maximum share size, and prepares the order.

``` python
open_long_position = [
    ('hide_window', '^登録銘柄$'),   # hide the Watchlists window.
    ('show_window', '^個別チャート\\s.*\\((\\d{4})\\)$'), # show the Chart window.
    ('show_window', '^個別銘柄\\s.*\\((\\d{4})\\)$'), # show the Summary window.
    ('click', '1157, 713'),          # select the New Order tab.
    ('click', '1492, 785'),          # focus on the Share Size text box.
    ('press_hotkeys', 'ctrl, a'),    # select an existing value.
    ('get_symbol', '^個別銘柄\\s.*\\((\\d{4})\\)$'), # get the symbol from the Summary window.
    ('calculate_share_size', 'short'), # calculate the share size and copy it.
    ('press_hotkeys', 'ctrl, v'),    # paste the share size.
    ('click', '1424, 808'),          # click the Market Order button.
    ('press_key', '\t, 3'),          # focus on the Buy Order button.
    ('beep', '1000, 100'),           # notify completion.
    ('back_to', None),               # back the cursor to the previous position.
]
```

### Execute Action ###

Execute an action saved in the configuration file.

``` shell
place-trades.py -e ACTION
```

### Options ###

  * `-i` generate a startup script and a shortcut to it
  * `-r` save customer margin ratios
  * `-d` save the previous market data
  * `-u` save ETF trading units
  * `-M [ACTION]` create or modify an action
  * `-e [ACTION]` execute an action
  * `-T [ACTION]` delete an action
  * `-S [ACTION]` generate a shortcut to an action
  * `-P` configure paths
  * `-I` configure a startup script
  * `-H` configure market holidays
  * `-R` configure customer margin ratios
  * `-D` configure market data
  * `-U` configure ETF trading units
  * `-C X Y WIDTH HEIGHT INDEX` configure the cash balance region and
    the index of the price
  * `-L X Y WIDTH HEIGHT INDEX` configure the price limit region and
    the index of the price

## License ##

[MIT](LICENSE.md)

## Links ##

  * [*Python Scripting to Assist in Day Trading on Margin using Hyper
    SBI 2*](): a blog post for more details.
