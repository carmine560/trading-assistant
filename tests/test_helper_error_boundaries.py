"""Tests for helper-level exception boundaries."""

import sys
import threading

import pytest

from configparser import ConfigParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

from app import ui
from core_utilities.errors import (
    BrowserAutomationError,
    GuiInteractionError,
    ProcessStateError,
    WidgetPositionError,
)
from core_utilities import process_utilities

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


def _load_speech_synthesis_module():
    """Load the speech helper module with lightweight Win32 COM stubs."""
    win32com_module = ModuleType("win32com")
    win32com_client_module = ModuleType("win32com.client")
    win32com_client_module.Dispatch = lambda *_args, **_kwargs: None
    win32com_module.client = win32com_client_module
    sys.modules["win32com"] = win32com_module
    sys.modules["win32com.client"] = win32com_client_module

    spec = spec_from_file_location(
        "test_speech_synthesis_module",
        PROJECT_ROOT / "interaction_utilities" / "speech_synthesis.py",
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

    with pytest.raises(GuiInteractionError) as e:
        module.enumerate_windows(lambda *_args: None, None)

    assert "Unable to enumerate windows" in str(e.value)


def test_click_widget_clicks_found_widget(monkeypatch):
    module = _load_gui_interactions_module()
    calls = []
    location = object()
    module.pyautogui.ImageNotFoundException = Exception
    module.pyautogui.locateOnScreen = (
        lambda image, region: calls.append((image, region)) or location
    )
    module.pyautogui.center = lambda found: ("center", found)
    module.pyautogui.click = lambda position: calls.append(("click", position))
    module.pyautogui.rightClick = lambda position: calls.append(
        ("right", position)
    )
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda _seconds: calls.append("sleep"),
    )

    assert module.click_widget(
        SimpleNamespace(swapped=False),
        "button.png",
        1,
        2,
        3,
        4,
    )

    assert calls == [
        ("button.png", (1, 2, 3, 4)),
        ("click", ("center", location)),
    ]


def test_click_widget_returns_none_when_canceled_before_polling():
    module = _load_gui_interactions_module()
    calls = []
    module.pyautogui.ImageNotFoundException = Exception
    module.pyautogui.locateOnScreen = lambda *_args, **_kwargs: calls.append(
        "locate"
    )

    assert (
        module.click_widget(
            SimpleNamespace(swapped=False),
            "button.png",
            1,
            2,
            3,
            4,
            should_continue_reference=lambda: False,
        )
        is None
    )
    assert calls == []


def test_click_widget_raises_typed_error_after_timeout(monkeypatch):
    module = _load_gui_interactions_module()
    module.pyautogui.ImageNotFoundException = Exception
    module.pyautogui.locateOnScreen = lambda *_args, **_kwargs: None
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monotonic_values = iter((0.0, 2.0))
    monkeypatch.setattr(
        module.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    with pytest.raises(GuiInteractionError) as e:
        module.click_widget(
            SimpleNamespace(swapped=False),
            "button.png",
            1,
            2,
            3,
            4,
            timeout_seconds=1.0,
            retry_interval_seconds=0,
        )

    assert "Widget image was not found within 1.0 seconds" in str(e.value)


def test_wait_for_window_returns_true_when_window_exists():
    module = _load_gui_interactions_module()

    def enum_windows(callback, extra):
        callback("hwnd", extra)

    module.win32gui.EnumWindows = enum_windows
    module.win32gui.GetWindowText = lambda _hwnd: "Order"

    assert module.wait_for_window("Order")


def test_wait_for_window_returns_none_when_canceled_before_polling():
    module = _load_gui_interactions_module()
    calls = []
    module.win32gui.EnumWindows = lambda *_args: calls.append("enum")

    assert (
        module.wait_for_window(
            "Order",
            should_continue_reference=lambda: False,
        )
        is None
    )
    assert calls == []


def test_wait_for_window_raises_typed_error_after_timeout(monkeypatch):
    module = _load_gui_interactions_module()
    module.win32gui.EnumWindows = lambda callback, extra: None
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monotonic_values = iter((0.0, 2.0))
    monkeypatch.setattr(
        module.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    with pytest.raises(GuiInteractionError) as e:
        module.wait_for_window(
            "Order",
            timeout_seconds=1.0,
            retry_interval_seconds=0,
        )

    assert "Window was not found within 1.0 seconds" in str(e.value)


def test_browser_execute_action_raises_typed_error_for_unknown_command(
    capsys,
):
    browser_driver = _load_browser_driver_module()

    with pytest.raises(BrowserAutomationError) as e:
        browser_driver.execute_action(SimpleNamespace(), [("unknown",)])

    assert "Unrecognized browser command" in str(e.value)
    assert capsys.readouterr().out == ""


def test_browser_execute_action_wraps_instruction_failures(capsys):
    browser_driver = _load_browser_driver_module()

    with pytest.raises(BrowserAutomationError) as e:
        browser_driver.execute_action(
            SimpleNamespace(),
            [("sleep", "not-a-number")],
        )

    assert "Browser instruction failed" in str(e.value)
    assert isinstance(e.value.__cause__, ValueError)
    assert capsys.readouterr().out == ""


def test_speech_process_start_timeout_terminates_process(monkeypatch):
    speech_synthesis = _load_speech_synthesis_module()

    class FakeProcess:
        instance = None

        def __init__(self, *_args, **_kwargs):
            self.calls = []
            FakeProcess.instance = self

        def start(self):
            self.calls.append("start")

        def terminate(self):
            self.calls.append("terminate")

        def join(self, timeout=None):
            self.calls.append(("join", timeout))

    speech_manager = SimpleNamespace(is_ready=lambda: False)
    monkeypatch.setattr(speech_synthesis, "Process", FakeProcess)
    monkeypatch.setattr(speech_synthesis.time, "monotonic", lambda: 0)
    monkeypatch.setattr(speech_synthesis.time, "sleep", lambda _seconds: None)

    with pytest.raises(ProcessStateError) as e:
        speech_synthesis.start_speaking_process(
            speech_manager,
            ready_timeout=0,
        )

    assert "did not become ready" in str(e.value)
    assert FakeProcess.instance.calls == [
        "start",
        "terminate",
        ("join", speech_synthesis.TERMINATE_TIMEOUT_SECONDS),
    ]


def test_speech_process_stop_timeout_terminates_process():
    speech_synthesis = _load_speech_synthesis_module()
    calls = []
    speech_manager = SimpleNamespace(
        get_speech_text=lambda: "",
        set_can_speak=lambda value: calls.append(("can_speak", value)),
    )
    speaking_process = SimpleNamespace(
        join=lambda timeout=None: calls.append(("join", timeout)),
        is_alive=lambda: True,
        terminate=lambda: calls.append("terminate"),
    )
    base_manager = SimpleNamespace(shutdown=lambda: calls.append("shutdown"))

    with pytest.raises(ProcessStateError) as e:
        speech_synthesis.stop_speaking_process(
            base_manager,
            speech_manager,
            speaking_process,
            join_timeout=0,
        )

    assert "did not stop" in str(e.value)
    assert calls == [
        ("can_speak", False),
        ("join", 0),
        "terminate",
        ("join", speech_synthesis.TERMINATE_TIMEOUT_SECONDS),
        "shutdown",
    ]


def test_is_running_wraps_process_status_probe_failure(monkeypatch):
    def raise_called_process_error(*_args, **_kwargs):
        raise process_utilities.subprocess.CalledProcessError(
            1,
            ["tasklist"],
        )

    monkeypatch.setattr(
        process_utilities.subprocess,
        "check_output",
        raise_called_process_error,
    )

    with pytest.raises(ProcessStateError) as e:
        process_utilities.is_running("HYPERSBI2")

    assert "Unable to check whether process 'HYPERSBI2' is running" in str(
        e.value
    )
    assert isinstance(
        e.value.__cause__,
        process_utilities.subprocess.CalledProcessError,
    )


def test_wait_listeners_stops_resources_after_process_probe_failure(
    monkeypatch,
):
    calls = []

    def raise_process_state_error(_process):
        raise ProcessStateError("tasklist failed")

    monkeypatch.setattr(
        process_utilities,
        "is_running",
        raise_process_state_error,
    )
    monkeypatch.setattr(
        process_utilities,
        "stop_listeners",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(ProcessStateError) as e:
        process_utilities.wait_listeners(
            SimpleNamespace(is_set=lambda: False),
            "HYPERSBI2",
            "mouse",
            "keyboard",
            "base_manager",
            "speech_manager",
            "speaking_process",
            indicator_thread="indicator",
        )

    assert str(e.value) == "tasklist failed"
    assert calls == [
        (
            (
                "mouse",
                "keyboard",
                "base_manager",
                "speech_manager",
                "speaking_process",
            ),
            {"indicator_thread": "indicator"},
        )
    ]


def test_stop_listeners_timeout_terminates_speech_process():
    calls = []
    mouse_listener = SimpleNamespace(stop=lambda: calls.append("mouse.stop"))
    keyboard_listener = SimpleNamespace(
        stop=lambda: calls.append("keyboard.stop")
    )
    speech_manager = SimpleNamespace(
        get_speech_text=lambda: "",
        set_can_speak=lambda value: calls.append(("can_speak", value)),
    )
    speaking_process = SimpleNamespace(
        join=lambda timeout=None: calls.append(("join", timeout)),
        is_alive=lambda: True,
        terminate=lambda: calls.append("terminate"),
    )
    base_manager = SimpleNamespace(shutdown=lambda: calls.append("shutdown"))

    with pytest.raises(ProcessStateError) as e:
        process_utilities.stop_listeners(
            mouse_listener,
            keyboard_listener,
            base_manager,
            speech_manager,
            speaking_process,
            speech_join_timeout=0,
        )

    assert "did not stop" in str(e.value)
    assert calls == [
        "mouse.stop",
        "keyboard.stop",
        ("can_speak", False),
        ("join", 0),
        "terminate",
        ("join", process_utilities.TERMINATE_TIMEOUT_SECONDS),
        "shutdown",
    ]


def test_indicator_thread_raises_typed_error_for_invalid_position():
    thread = ui.IndicatorThread(
        SimpleNamespace(),
        SimpleNamespace(),
    )
    widget = SimpleNamespace(place=lambda **_kwargs: None)

    ui.GetMonitorInfo = lambda *_args, **_kwargs: {"Work": (0, 0, 100, 100)}
    ui.MonitorFromPoint = lambda *_args, **_kwargs: None

    with pytest.raises(WidgetPositionError) as e:
        thread._place_widget(widget, "invalid")

    assert "Invalid widget position" in str(e.value)


def test_indicator_thread_captures_tk_error(monkeypatch):
    def raise_tcl_error():
        raise ui.TclError("tk failed")

    monkeypatch.setattr(ui.tk, "Tk", raise_tcl_error)
    thread = ui.IndicatorThread(
        SimpleNamespace(),
        SimpleNamespace(),
    )

    thread.run()

    assert isinstance(thread.error, ui.TclError)
    assert "tk failed" in str(thread.error)
    assert thread.root is None


def test_indicator_thread_destroys_root_and_ignores_destroy_error(monkeypatch):
    calls = []

    class FakeRoot:
        def attributes(self, *args):
            calls.append(("attributes", args))

        def config(self, **kwargs):
            calls.append(("config", kwargs))

        def overrideredirect(self, value):
            calls.append(("overrideredirect", value))

        def title(self, text):
            calls.append(("title", text))

        def protocol(self, name, callback):
            calls.append(("protocol", name, callback))

        def register(self, callback):
            calls.append(("register", callback))
            return callback

        def update(self):
            calls.append("update")
            raise ui.TclError("update failed")

        def destroy(self):
            calls.append("destroy")
            raise ui.TclError("destroy failed")

    class FakeLabel:
        def __init__(self, *args, **kwargs):
            calls.append(("label", args, kwargs))

        def grid(self, **kwargs):
            calls.append(("label.grid", kwargs))

        def bind(self, event, callback):
            calls.append(("label.bind", event, callback))

        def bbox(self, *_args):
            return (0, 0, 0, 0)

        def winfo_rootx(self):
            return 0

        def winfo_rooty(self):
            return 0

        def config(self, **kwargs):
            calls.append(("label.config", kwargs))

    class FakeFrame:
        def __init__(self, *args, **kwargs):
            calls.append(("frame", args, kwargs))

        def place(self, **kwargs):
            calls.append(("frame.place", kwargs))

    class FakeSpinbox:
        def __init__(self, *args, **kwargs):
            calls.append(("spinbox", args, kwargs))

        def grid(self, **kwargs):
            calls.append(("spinbox.grid", kwargs))

        def bind(self, event, callback):
            calls.append(("spinbox.bind", event, callback))

    class FakeStringVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value
            calls.append(("stringvar.set", value))

        def get(self):
            return self.value

        def trace_add(self, mode, callback):
            calls.append(("stringvar.trace_add", mode, callback))

    monkeypatch.setattr(ui.tk, "Tk", FakeRoot)
    monkeypatch.setattr(ui.tk, "Label", FakeLabel, raising=False)
    monkeypatch.setattr(ui.tk, "Frame", FakeFrame, raising=False)
    monkeypatch.setattr(ui.tk, "Spinbox", FakeSpinbox, raising=False)
    monkeypatch.setattr(ui.tk, "StringVar", FakeStringVar, raising=False)
    monkeypatch.setattr(
        ui,
        "GetMonitorInfo",
        lambda *_args, **_kwargs: {"Work": (0, 0, 100, 100)},
    )
    monkeypatch.setattr(ui, "MonitorFromPoint", lambda *_args, **_kwargs: None)

    trade = SimpleNamespace(
        process="HYPERSBI2",
        variables_section="Variables",
        widgets_section="Widgets",
        config_lock=threading.RLock(),
    )
    config = ConfigParser(interpolation=None)
    config["HYPERSBI2"] = {
        "title": "Trading",
        "maximum_daily_number_of_trades": "1",
        "utilization_ratio": "0.5",
    }
    config["Variables"] = {"current_number_of_trades": "0"}
    config["Widgets"] = {
        "is_clock_label_enabled": "false",
        "status_bar_frame_font_size": "12",
        "status_bar_frame_position": "center",
    }
    thread = ui.IndicatorThread(trade, config)

    thread.run()

    assert thread.error is None
    assert "update" in calls
    assert "destroy" in calls


def test_indicator_utilization_change_writes_config_under_lock():
    class RecordingLock:
        def __init__(self):
            self.is_held = False

        def __enter__(self):
            self.is_held = True

        def __exit__(self, *_args):
            self.is_held = False

    class ConfigSection(dict):
        def __init__(self, lock, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lock = lock

        def __setitem__(self, key, value):
            assert self.lock.is_held
            super().__setitem__(key, value)

    class StringValue:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    lock = RecordingLock()
    trade = SimpleNamespace(process="HYPERSBI2", config_lock=lock)
    config = {
        "HYPERSBI2": ConfigSection(lock, {"utilization_ratio": "0.5"}),
    }
    thread = ui.IndicatorThread(trade, config)
    thread._utilization_ratio_string = StringValue("0.75")

    thread._on_utilization_ratio_change()

    assert config["HYPERSBI2"]["utilization_ratio"] == "0.75"


def test_message_thread_captures_tk_error(monkeypatch):
    def raise_tcl_error():
        raise ui.TclError("tk failed")

    monkeypatch.setattr(ui.tk, "Tk", raise_tcl_error)
    thread = ui.MessageThread(
        SimpleNamespace(),
        SimpleNamespace(),
        "message",
    )

    thread.run()

    assert isinstance(thread.error, ui.TclError)
    assert "tk failed" in str(thread.error)
    assert thread.root is None


def test_message_thread_destroys_root_and_ignores_destroy_error(monkeypatch):
    calls = []

    class FakeRoot:
        def attributes(self, *args):
            calls.append(("attributes", args))

        def bind(self, *_args):
            calls.append("bind")

        def resizable(self, *_args):
            calls.append("resizable")

        def title(self, text):
            calls.append(("title", text))

        def withdraw(self):
            calls.append("withdraw")

        def update(self):
            calls.append("update")

        def winfo_width(self):
            return 20

        def winfo_height(self):
            return 10

        def geometry(self, value):
            calls.append(("geometry", value))

        def deiconify(self):
            calls.append("deiconify")

        def mainloop(self):
            calls.append("mainloop")

        def destroy(self):
            calls.append("destroy")
            raise ui.TclError("destroy failed")

    class FakeMessage:
        def __init__(self, root, **kwargs):
            calls.append(("message", root, kwargs["text"]))

        def pack(self):
            calls.append("pack")

    monkeypatch.setattr(ui.tk, "Tk", FakeRoot)
    monkeypatch.setattr(ui.tk, "Message", FakeMessage, raising=False)
    monkeypatch.setattr(
        ui,
        "GetMonitorInfo",
        lambda *_args, **_kwargs: {"Work": (0, 0, 100, 100)},
    )
    monkeypatch.setattr(ui, "MonitorFromPoint", lambda *_args, **_kwargs: None)

    trade = SimpleNamespace(process="HYPERSBI2", widgets_section="Widgets")
    config = {
        "HYPERSBI2": {"title": "Trading"},
        "Widgets": {"message_font_size": "12"},
    }
    thread = ui.MessageThread(trade, config, "message")

    thread.run()

    assert thread.error is None
    assert "mainloop" in calls
    assert "destroy" in calls
