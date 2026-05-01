"""Tests for source parsing helpers."""

from core_utilities.initializer import extract_commands


def test_extract_commands_collects_command_comparisons():
    source = """
def dispatch(command):
    if command == "buy":
        return 1
    if command == "sell":
        return 2
    if other == "ignore":
        return 3
"""
    assert extract_commands(source) == ["buy", "sell"]


def test_extract_commands_respects_custom_variable_name():
    source = """
def handle(action):
    if action == "save_market_data":
        return True
"""
    assert extract_commands(source, command="action") == ["save_market_data"]
