"""Perform data conversions, text operations, and time computations."""

import re
import time


# Data Conversions


def dictionary_to_tuple(dictionary):
    """Convert a dictionary to a tuple of key-value pairs."""
    if isinstance(dictionary, dict):
        items = []
        for key, value in sorted(dictionary.items()):
            items.append((key, dictionary_to_tuple(value)))
        return tuple(items)
    return dictionary


# Text Operations


def create_acronym(phrase):
    """Generate an acronym from the given phrase."""
    acronym = ""
    if isinstance(phrase, str):
        acronym = "".join(
            word[0].upper() for word in re.split(r"[\W_]+", phrase) if word
        )
    return acronym


def title_except_acronyms(string, acronyms):
    """Convert a string to title case, excluding specified acronyms."""
    words = string.split()
    for i, _ in enumerate(words):
        if words[i] not in acronyms:
            words[i] = words[i].title()
    return " ".join(words)


# Time Computations


def get_target_time(time_string):
    """Compute the target time from a given time string."""
    return time.mktime(
        time.strptime(
            time.strftime(f"%Y-%m-%d {time_string}"), "%Y-%m-%d %H:%M:%S"
        )
    )
