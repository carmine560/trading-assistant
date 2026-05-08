"""Tests for helper-level exception boundaries."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from core_utilities.errors import (
    BrowserAutomationError,
    GuiInteractionError,
    WidgetPositionError,
)
from app import ui

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_gui_interactions_module():
    """Load the real GUI helper module with lightweight Win32 stubs."""
    pywintypes_module = ModuleType("pywintypes")
    pywintypes_module.error = type("FakeWin32Error", (Exception,), {})
    sys.modules["pywintypes"] = pywintypes_module

    spec = spec_from_file_location(
        "test_gui_interactions_module",
        PROJECT_ROOT / "interaction_utilities" / "gui_interactions.py",
    )
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_browser_driver_module():
    """Load the browser helper module with lightweight Selenium stubs."""
    selenium_module = ModuleType("selenium")
    webdriver_module = ModuleType("selenium.webdriver")
    webdriver_module.Chrome = lambda **_kwargs: None

    common_exceptions_module = ModuleType("selenium.common.exceptions")
    common_exceptions_module.TimeoutException = type(
        "TimeoutException",
        (Exception,),
        {},
    )

    chrome_options_module = ModuleType("selenium.webdriver.chrome.options")
    chrome_options_module.Options = type("Options", (), {})

    by_module = ModuleType("selenium.webdriver.common.by")
    by_module.By = SimpleNamespace(XPATH="xpath")

    keys_module = ModuleType("selenium.webdriver.common.keys")
    keys_module.Keys = SimpleNamespace(ENTER="enter")

    support_module = ModuleType("selenium.webdriver.support")
    expected_conditions_module = ModuleType(
        "selenium.webdriver.support.expected_conditions"
    )
    expected_conditions_module.visibility_of_element_located = (
        lambda locator: locator
    )

    ui_module = ModuleType("selenium.webdriver.support.ui")
    ui_module.WebDriverWait = type(
        "WebDriverWait",
        (),
        {"__init__": lambda self, *_args, **_kwargs: None, "until": None},
    )

    sys.modules["selenium"] = selenium_module
    sys.modules["selenium.webdriver"] = webdriver_module
    sys.modules["selenium.common.exceptions"] = common_exceptions_module
    sys.modules["selenium.webdriver.chrome.options"] = chrome_options_module
    sys.modules["selenium.webdriver.common.by"] = by_module
    sys.modules["selenium.webdriver.common.keys"] = keys_module
    sys.modules["selenium.webdriver.support"] = support_module
    sys.modules["selenium.webdriver.support.expected_conditions"] = (
        expected_conditions_module
    )
    sys.modules["selenium.webdriver.support.ui"] = ui_module

    spec = spec_from_file_location(
        "test_browser_driver_module",
        PROJECT_ROOT / "web_utilities" / "browser_driver.py",
    )
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_enumerate_windows_returns_false_for_expected_win32_errors():
    module = _load_gui_interactions_module()

    def raise_expected_error(*_args, **_kwargs):
        raise module.pywintypes.error(5, "expected")

    module.win32gui.EnumWindows = raise_expected_error

    assert not module.enumerate_windows(lambda *_args: None, None)


def test_enumerate_windows_raises_typed_error_for_unexpected_failure():
    module = _load_gui_interactions_module()

    def raise_unexpected_error(*_args, **_kwargs):
        raise module.pywintypes.error(99, "unexpected")

    module.win32gui.EnumWindows = raise_unexpected_error

    with pytest.raises(GuiInteractionError) as exc_info:
        module.enumerate_windows(lambda *_args: None, None)

    assert "Unable to enumerate windows" in str(exc_info.value)


def test_browser_execute_action_raises_typed_error_for_unknown_command(
    capsys,
):
    browser_driver = _load_browser_driver_module()

    with pytest.raises(BrowserAutomationError) as exc_info:
        browser_driver.execute_action(SimpleNamespace(), [("unknown",)])

    assert "Unrecognized browser command" in str(exc_info.value)
    assert capsys.readouterr().out == ""


def test_browser_execute_action_wraps_instruction_failures(capsys):
    browser_driver = _load_browser_driver_module()

    with pytest.raises(BrowserAutomationError) as exc_info:
        browser_driver.execute_action(
            SimpleNamespace(),
            [("sleep", "not-a-number")],
        )

    assert "Browser instruction failed" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert capsys.readouterr().out == ""


def test_indicator_thread_raises_typed_error_for_invalid_position():
    thread = ui.IndicatorThread(
        SimpleNamespace(),
        SimpleNamespace(),
    )
    widget = SimpleNamespace(place=lambda **_kwargs: None)

    ui.GetMonitorInfo = lambda *_args, **_kwargs: {"Work": (0, 0, 100, 100)}
    ui.MonitorFromPoint = lambda *_args, **_kwargs: None

    with pytest.raises(WidgetPositionError) as exc_info:
        thread._place_widget(widget, "invalid")

    assert "Invalid widget position" in str(exc_info.value)
