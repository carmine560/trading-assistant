"""Tests for pure data, datetime, and file helpers."""

import os

from core_utilities.data_utilities import (
    create_acronym,
    dictionary_to_tuple,
    title_except_acronyms,
)
from core_utilities.datetime_utilities import normalize_datetime_string
from core_utilities.file_utilities import backup_file


def test_dictionary_to_tuple_sorts_nested_dictionary_items():
    value = {"b": 2, "a": {"y": 2, "x": 1}}

    assert dictionary_to_tuple(value) == (
        ("a", (("x", 1), ("y", 2))),
        ("b", 2),
    )


def test_create_acronym_splits_on_non_word_characters():
    assert create_acronym("margin-call_watch list") == "MCWL"


def test_title_except_acronyms_preserves_requested_words():
    assert title_except_acronyms("watch sbi api feed", {"SBI", "API"}) == (
        "Watch SBI API Feed"
    )


def test_normalize_datetime_string_rolls_over_hours_past_midnight():
    assert normalize_datetime_string("2026-05-01 26:15") == "2026-05-02 02:15"


def test_normalize_datetime_string_keeps_same_day_under_twenty_four_hours():
    assert normalize_datetime_string("2026-05-01 09:05") == "2026-05-01 09:05"


def test_backup_file_skips_duplicate_content_when_compare_enabled(tmp_path):
    source = tmp_path / "watchlist.txt"
    source.write_text("same data\n", encoding="utf-8")
    backup_directory = tmp_path / "backups"

    os.utime(source, (1_700_000_000, 1_700_000_000))
    backup_file(str(source), str(backup_directory), number_of_backups=5)

    os.utime(source, (1_700_000_100, 1_700_000_100))
    backup_file(str(source), str(backup_directory), number_of_backups=5)

    assert len(list(backup_directory.iterdir())) == 1


def test_backup_file_prunes_old_backups_when_limit_is_exceeded(tmp_path):
    source = tmp_path / "watchlist.txt"
    backup_directory = tmp_path / "backups"

    for index, text in enumerate(("first\n", "second\n", "third\n"), start=1):
        source.write_text(text, encoding="utf-8")
        timestamp = 1_700_000_000 + index
        os.utime(source, (timestamp, timestamp))
        backup_file(str(source), str(backup_directory), number_of_backups=2)

    backups = sorted(backup_directory.iterdir())
    backup_contents = [
        path.read_text(encoding="utf-8") for path in backups
    ]

    assert len(backups) == 2
    assert backup_contents == ["second\n", "third\n"]
