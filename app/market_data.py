"""Market data helpers extracted from the main entrypoint."""

from collections import defaultdict
import csv
import os
import re

from core_utilities.errors import MarketDataError


def split_rankings_by_digit(rankings, closing_prices_prefix, code_regex):
    """Split the rankings CSV by the first digit of the securities code."""
    data_by_digit = defaultdict(list)

    try:
        with open(rankings, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                securities_code = row[6].strip()
                if not re.fullmatch(code_regex, securities_code):
                    continue
                data_by_digit[securities_code[0]].append(
                    (securities_code, row[9].strip().replace(",", ""))
                )
    except OSError as e:
        raise MarketDataError(
            f"Unable to read rankings file: {rankings}"
        ) from e

    for digit in range(1, 10):
        digit_string = str(digit)
        try:
            with open(
                f"{closing_prices_prefix}{digit}.csv",
                "w",
                encoding="utf-8",
                # 'csv.writer()' on Windows writes '\r\n' itself; without
                # 'newline=""', 'open()' would translate '\n' to '\r\n',
                # producing '\r\r\n' (seen as '^M') and causing extra blank
                # lines.
                newline="",
            ) as f:
                writer = csv.writer(f)
                if digit_string in data_by_digit:
                    for securities_code, current_price in data_by_digit[
                        digit_string
                    ]:
                        writer.writerow([securities_code, current_price])
        except OSError as e:
            raise MarketDataError(
                "Unable to write closing prices file for "
                f"digit {digit_string}."
            ) from e

    if os.path.isfile(rankings):
        try:
            os.remove(rankings)
        except OSError as e:
            raise MarketDataError(
                f"Unable to remove processed rankings file: {rankings}"
            ) from e

    return True
