"""Tests for extracted configuration workflow helpers."""

from app import config_workflow


def test_is_xy_accepts_two_integers_with_whitespace():
    assert config_workflow.is_xy(" 10,  25 ")
    assert not config_workflow.is_xy("10,25,30")
    assert not config_workflow.is_xy("10.5,25")
