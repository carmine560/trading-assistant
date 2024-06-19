"""Make HTTP HEAD requests and handle potential errors."""

import sys

import requests


def make_head_request(url):
    """Perform HTTP HEAD request and handle errors."""
    head = requests.head(url, timeout=5)
    try:
        head.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    return head
