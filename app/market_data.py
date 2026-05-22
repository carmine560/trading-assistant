"""Market rankings processing into per-digit closing price files."""

import csv
import os
import re
import tempfile
from collections import defaultdict

from core_utilities.errors import MarketDataError

MARKET_DATA_FILE_ERROR = "Unable to read market data file"


def split_rankings_by_digit(rankings, closing_prices_prefix, code_regex):
    """Split the rankings CSV by the first digit of the securities code."""
    data_by_digit = _read_rankings(rankings, code_regex)
    _write_closing_prices_files(closing_prices_prefix, data_by_digit)

    if os.path.isfile(rankings):
        try:
            os.remove(rankings)
        except OSError as e:
            raise MarketDataError(
                f"Unable to remove processed rankings file: {rankings}"
            ) from e

    return True


def _read_rankings(rankings, code_regex):
    """Read rankings rows and group valid prices by leading digit."""
    data_by_digit = defaultdict(list)
    malformed_rows = []

    try:
        with open(rankings, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row_number, row in enumerate(reader, start=1):
                if len(row) <= 9:
                    malformed_rows.append((row_number, len(row)))
                    continue
                securities_code = row[6].strip()
                if not re.fullmatch(code_regex, securities_code):
                    continue
                current_price = row[9].strip().replace(",", "")
                try:
                    float(current_price)
                except ValueError as e:
                    raise MarketDataError(
                        f"{MARKET_DATA_FILE_ERROR}: row "
                        f"{row_number} has invalid closing price "
                        f"{row[9].strip()!r}."
                    ) from e
                data_by_digit[securities_code[0]].append(
                    (securities_code, current_price)
                )
    except OSError as e:
        raise MarketDataError(
            f"{MARKET_DATA_FILE_ERROR}: {rankings}"
        ) from e

    if malformed_rows:
        row_number, column_count = malformed_rows[0]
        raise MarketDataError(
            f"{MARKET_DATA_FILE_ERROR}: malformed row "
            f"{row_number} has {column_count} columns."
        )

    return data_by_digit


def _write_closing_prices_files(closing_prices_prefix, data_by_digit):
    """Write grouped closing-price rows to per-digit output files."""
    temporary_paths = []
    for digit in range(1, 10):
        digit_string = str(digit)
        target_path = f"{closing_prices_prefix}{digit_string}.csv"
        directory = os.path.dirname(os.path.abspath(target_path)) or "."
        prefix = f".{os.path.basename(target_path)}."
        fd = None
        try:
            fd, temporary_path = tempfile.mkstemp(
                prefix=prefix,
                suffix=".tmp",
                dir=directory,
            )
            temporary_paths.append((temporary_path, target_path))
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
                # csv.writer() on Windows writes \r\n itself; without
                # newline="", open() would translate \n to \r\n, producing
                # \r\r\n (seen as ^M) and causing extra blank lines.
                newline="",
            ) as f:
                fd = None
                writer = csv.writer(f)
                for securities_code, current_price in data_by_digit.get(
                    digit_string, []
                ):
                    writer.writerow([securities_code, current_price])
        except OSError as e:
            if fd is not None:
                os.close(fd)
            _remove_temporary_files(temporary_paths)
            raise MarketDataError(
                "Unable to write closing prices file for "
                f"digit {digit_string}."
            ) from e

    try:
        for temporary_path, target_path in temporary_paths:
            os.replace(temporary_path, target_path)
    except OSError as e:
        _remove_temporary_files(temporary_paths)
        raise MarketDataError("Unable to replace closing prices files.") from e


def _remove_temporary_files(temporary_paths):
    """Remove any staged closing-price temp files that still exist."""
    for temporary_path, _target_path in temporary_paths:
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass
