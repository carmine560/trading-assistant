"""Perform data conversions and time computations."""

import time


# Data Conversions #

def dictionary_to_tuple(dictionary):
    """Convert a dictionary to a tuple of key-value pairs."""
    if isinstance(dictionary, dict):
        items = []
        for key, value in sorted(dictionary.items()):
            items.append((key, dictionary_to_tuple(value)))
        return tuple(items)
    return dictionary


# Time Computations #

def get_target_time(time_string):
    """Compute the target time from a given time string."""
    return time.mktime(time.strptime(
        time.strftime(f'%Y-%m-%d {time_string}'), '%Y-%m-%d %H:%M:%S'))
