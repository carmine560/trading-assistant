"""Tests for pure data and datetime helpers."""

from core_utilities.data_utilities import (
    create_acronym,
    dictionary_to_tuple,
    title_except_acronyms,
)
from core_utilities.datetime_utilities import normalize_datetime_string


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
