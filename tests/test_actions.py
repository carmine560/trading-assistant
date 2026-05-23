"""Tests for extracted action execution helpers."""

import threading
from configparser import ConfigParser
from types import SimpleNamespace

import pytest

from app import actions
from app.action_errors import ActionExecutionError, ActionLookupError


def _build_trade(spoken):
    """Create a minimal trade object for action execution tests."""
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
        variables_section="Variables",
        geometries_section="HYPERSBI2 Geometries",
        widgets_section="HYPERSBI2 Widgets",
        market_holidays="market_holidays.csv",
        resource_directory="resources",
        speech_manager=SimpleNamespace(set_speech_text=spoken.append),
        indicator_thread=None,
        keyboard_listener_state=0,
        key_to_check=None,
        should_continue=True,
        action_lock=threading.Lock(),
        last_action_error=None,
        share_size=0,
        cash_balance=0,
        symbol="1234",
    )
    trade.initialized = 0
    trade.initialize_attributes = lambda: setattr(
        trade, "initialized", trade.initialized + 1
    )
    return trade


def _build_gui_state():
    """Create a minimal GUI state object for action execution tests."""
    gui_state = SimpleNamespace(
        previous_position=(0, 0),
        swapped=False,
        initialized=0,
    )
    gui_state.initialize_attributes = lambda: setattr(
        gui_state, "initialized", gui_state.initialized + 1
    )
    return gui_state


def _build_config():
    """Create a minimal config object for action execution tests."""
    config = ConfigParser(interpolation=None)
    config["General"] = {"countdown_seconds_before_candle_close": "30, 10, 5"}
    config["HYPERSBI2"] = {
        "image_magnification": "1",
        "binarization_threshold": "128",
        "is_dark_theme": "false",
        "utilization_ratio": "0.5",
        "daily_loss_limit_ratio": "-0.01",
        "maximum_daily_number_of_trades": "5",
        "screencast_directory": "videos",
        "screencast_regex": r"video\.mp4",
    }
    config["HYPERSBI2 Geometries"] = {"cash_balance_region": "0, 0, 10, 10, 0"}
    config["Variables"] = {
        "initial_cash_balance": "0",
        "current_number_of_trades": "0",
    }
    config["Market Data"] = {"timezone": "Asia/Tokyo"}
    config["Market Holidays"] = {"date_format": "%Y/%m/%d"}
    config["Actions"] = {}
    return config


def _patch_action_modules(monkeypatch):
    """Patch direct module collaborators used by the action executor."""
    sleep_calls = []
    monkeypatch.setattr(actions.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(
        actions,
        "data_utilities",
        SimpleNamespace(get_target_time=lambda *_args: 0),
    )
    monkeypatch.setattr(
        actions,
        "file_utilities",
        SimpleNamespace(
            get_latest_file=lambda *_args: "video.mp4",
            is_writing=lambda *_args: False,
            write_chapter=lambda *_args, **_kwargs: None,
        ),
    )
    monkeypatch.setattr(
        actions,
        "gui_interactions",
        SimpleNamespace(
            _show_window_state={"count": 0, "max_count": 0},
            click_widget=lambda *_args, **_kwargs: None,
            enumerate_windows=lambda *_args, **_kwargs: None,
            hide_window=lambda *_args, **_kwargs: None,
            show_hide_window=lambda *_args, **_kwargs: None,
            show_window=lambda *_args, **_kwargs: None,
            wait_for_window=lambda *_args, **_kwargs: None,
        ),
    )
    monkeypatch.setattr(
        actions,
        "keyboard",
        SimpleNamespace(Key={"enter": object()}),
    )
    monkeypatch.setattr(
        actions,
        "pd",
        SimpleNamespace(
            Timestamp=SimpleNamespace(
                now=lambda **_kwargs: SimpleNamespace(
                    second=0,
                    minute=0,
                    hour=0,
                    strftime=lambda _fmt: "2026-05-06",
                )
            )
        ),
    )
    monkeypatch.setattr(
        actions,
        "psutil",
        SimpleNamespace(cpu_percent=lambda interval: 12.4),
    )
    monkeypatch.setattr(
        actions,
        "pyautogui",
        SimpleNamespace(
            click=lambda *_args, **_kwargs: None,
            dragTo=lambda *_args, **_kwargs: None,
            hotkey=lambda *_args, **_kwargs: None,
            moveTo=lambda *_args, **_kwargs: None,
            press=lambda *_args, **_kwargs: None,
            rightClick=lambda *_args, **_kwargs: None,
            write=lambda *_args, **_kwargs: None,
        ),
    )
    monkeypatch.setattr(
        actions,
        "text_recognition",
        SimpleNamespace(recognize_text=lambda *_args, **_kwargs: 100),
    )
    monkeypatch.setattr(
        actions,
        "ui",
        SimpleNamespace(
            IndicatorThread=lambda *_args: SimpleNamespace(start=lambda: None),
            MessageThread=lambda *_args: SimpleNamespace(start=lambda: None),
        ),
    )
    monkeypatch.setattr(
        actions,
        "win32clipboard",
        SimpleNamespace(
            OpenClipboard=lambda: None,
            EmptyClipboard=lambda: None,
            SetClipboardText=lambda _text: None,
            CloseClipboard=lambda: None,
        ),
    )
    monkeypatch.setattr(
        actions, "calculate_share_size", lambda *_args: (True, None)
    )
    monkeypatch.setattr(actions, "is_trading_day", lambda *_args: True)
    return sleep_calls


def _assert_action_error(e, action_path, instruction_index, command):
    """Assert the common context carried by action execution errors."""
    assert e.value.action_path == action_path
    assert e.value.instruction_index == instruction_index
    assert e.value.command == command


def _patch_clipboard(monkeypatch):
    """Patch clipboard calls and return the call log."""
    calls = []
    monkeypatch.setattr(
        actions,
        "win32clipboard",
        SimpleNamespace(
            OpenClipboard=lambda: calls.append("open"),
            EmptyClipboard=lambda: calls.append("empty"),
            SetClipboardText=lambda text: calls.append(("set", text)),
            CloseClipboard=lambda: calls.append("close"),
        ),
    )
    return calls


def test_start_execute_action_thread_raises_for_missing_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()

    monkeypatch.setattr(
        actions.threading,
        "Thread",
        lambda *_args, **_kwargs: pytest.fail("Thread should not start"),
    )

    with pytest.raises(ActionLookupError) as e:
        actions.start_execute_action_thread(
            trade,
            config,
            gui_state,
            "missing",
        )

    assert str(e.value) == "Action 'missing' is not defined."
    assert e.value.action_name == "missing"


def test_start_execute_action_thread_starts_configured_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["Actions"]["open"] = str([("speak_text", "ready")])
    calls = []

    class FakeThread:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            calls.append(("thread", kwargs["target"], kwargs["args"]))

        def start(self):
            calls.append("start")
            self.kwargs["target"](*self.kwargs["args"])

    monkeypatch.setattr(actions.threading, "Thread", FakeThread)

    thread = actions.start_execute_action_thread(
        trade,
        config,
        gui_state,
        "open",
    )

    assert isinstance(thread, FakeThread)
    assert calls == [
        (
            "thread",
            actions._execute_action_thread,
            (
                trade,
                config,
                gui_state,
                "[('speak_text', 'ready')]",
                "open",
            ),
        ),
        "start",
    ]
    assert spoken == ["ready"]
    assert trade.last_action_error is None
    assert not trade.action_lock.locked()


def test_start_execute_action_thread_suppresses_concurrent_trigger(
    monkeypatch,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["Actions"]["open"] = str([("speak_text", "ready")])
    assert trade.action_lock.acquire(blocking=False)
    calls = []

    class FakeThread:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            calls.append(("thread", kwargs["target"], kwargs["args"]))

        def start(self):
            calls.append("start")
            self.kwargs["target"](*self.kwargs["args"])

    monkeypatch.setattr(actions.threading, "Thread", FakeThread)

    thread = actions.start_execute_action_thread(
        trade,
        config,
        gui_state,
        "open",
    )

    assert isinstance(thread, FakeThread)
    assert calls == [
        (
            "thread",
            actions._execute_action_thread,
            (
                trade,
                config,
                gui_state,
                "[('speak_text', 'ready')]",
                "open",
            ),
        ),
        "start",
    ]
    error = trade.last_action_error
    assert isinstance(error, actions.action_errors.ActionConcurrencyError)
    assert error.action_name == "open"
    assert spoken == ["Action busy."]
    trade.action_lock.release()


def test_execute_action_thread_records_typed_failure(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()

    def fail_execute_action(*_args, **_kwargs):
        raise ActionExecutionError(
            "Action path 'open' failed.",
            action_path=("open",),
            instruction_index=1,
            command="bad",
        )

    monkeypatch.setattr(actions, "execute_action", fail_execute_action)

    actions._execute_action_thread(
        trade,
        config,
        gui_state,
        [("bad",)],
        "open",
    )

    assert isinstance(trade.last_action_error, ActionExecutionError)
    assert spoken == ["Action failed."]
    assert not trade.action_lock.locked()


def test_execute_action_thread_records_unexpected_failure(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()

    def fail_execute_action(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(actions, "execute_action", fail_execute_action)

    actions._execute_action_thread(
        trade,
        config,
        gui_state,
        [("bad",)],
        "open",
    )

    assert isinstance(trade.last_action_error, RuntimeError)
    assert spoken == ["Action failed unexpectedly."]
    assert not trade.action_lock.locked()


def test_execute_action_speaks_text_with_direct_imports(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("speak_text", "ready")],
    )
    assert spoken == ["ready"]
    assert (trade.initialized, gui_state.initialized) == (1, 1)


def test_execute_action_suppresses_concurrent_direct_call(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    assert trade.action_lock.acquire(blocking=False)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("speak_text", "ready")],
        action_path=("cli_action",),
    )

    error = trade.last_action_error
    assert isinstance(error, actions.action_errors.ActionConcurrencyError)
    assert error.action_name == "cli_action"
    assert spoken == ["Action busy."]
    assert (trade.initialized, gui_state.initialized) == (0, 0)
    trade.action_lock.release()


def test_execute_action_can_skip_lock_acquisition(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    assert trade.action_lock.acquire(blocking=False)

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("speak_text", "ready")],
        should_acquire_lock=False,
        action_path=("schedule",),
    )

    assert spoken == ["ready"]
    assert (trade.initialized, gui_state.initialized) == (1, 1)
    trade.action_lock.release()


def test_execute_action_runs_named_nested_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["Actions"]["nested"] = str([("speak_text", "nested")])
    _patch_action_modules(monkeypatch)

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("execute_action", "nested"), ("speak_text", "done")],
    )
    assert spoken == ["nested", "done"]
    assert (trade.initialized, gui_state.initialized) == (1, 1)


def test_click_widget_cancellation_stops_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def cancel_click_widget(*_args, **kwargs):
        assert kwargs["should_continue_reference"]()
        trade.should_continue = False

    monkeypatch.setattr(
        actions,
        "gui_interactions",
        SimpleNamespace(click_widget=cancel_click_widget),
    )

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            ("click_widget", "button.png", "0, 0, 10, 10"),
            ("speak_text", "should not run"),
        ],
    )
    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == ["Canceled."]


def test_execute_action_raises_for_unknown_command(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    with pytest.raises(ActionExecutionError) as e:
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("unknown_command",)],
        )

    _assert_action_error(e, ("inline action",), 1, "unknown_command")
    assert spoken == []


def test_execute_action_unknown_command_does_not_print(monkeypatch, capsys):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    with pytest.raises(ActionExecutionError):
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("unknown_command",)],
        )
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("instruction", "command"),
    [
        ([], None),
        (123, None),
        ("speak_text", None),
        (("speak_text", "ready", None, "extra"), "speak_text"),
    ],
)
def test_execute_action_raises_for_malformed_instruction(
    monkeypatch,
    instruction,
    command,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    with pytest.raises(ActionExecutionError) as e:
        actions.execute_action(
            trade,
            config,
            gui_state,
            [instruction],
        )

    assert "malformed instruction" in str(e.value)
    assert repr(instruction) in str(e.value)
    _assert_action_error(e, ("inline action",), 1, command)
    assert spoken == []


def test_execute_action_reports_inline_nested_action_path(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    with pytest.raises(ActionExecutionError) as e:
        actions.execute_action(
            trade,
            config,
            gui_state,
            [
                (
                    "execute_action",
                    [("unknown_command",)],
                )
            ],
            action_path=("action_1",),
        )

    _assert_action_error(e, ("action_1", "inline@1"), 1, "unknown_command")


def test_execute_action_raises_for_missing_named_nested_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    with pytest.raises(ActionExecutionError) as e:
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("execute_action", "missing_action")],
            action_path=("action_3",),
        )

    assert "nested action 'missing_action' is not defined" in str(e.value)
    _assert_action_error(e, ("action_3",), 1, "execute_action")
    assert spoken == []


def test_execute_action_reports_named_nested_action_path(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["Actions"]["action_2"] = str([("unknown_command",)])
    _patch_action_modules(monkeypatch)

    with pytest.raises(ActionExecutionError) as e:
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("execute_action", "action_2")],
            action_path=("action_3",),
        )

    _assert_action_error(e, ("action_3", "action_2"), 1, "unknown_command")


def test_wait_for_key_cancellation_runs_cleanup_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def stop_wait(_seconds):
        trade.keyboard_listener_state = 0
        trade.should_continue = False

    monkeypatch.setattr(actions.time, "sleep", stop_wait)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("wait_for_key", "enter", [("speak_text", "cleanup")])],
    )
    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == ["cleanup", "Canceled."]


def test_wait_for_key_invalid_key_resets_listener_state(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    with pytest.raises(KeyError):
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("wait_for_key", "missing")],
        )

    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == []


def test_wait_for_key_count_down_cancellation_speaks_countdown(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    monkeypatch.setattr(
        actions,
        "pd",
        SimpleNamespace(
            Timestamp=SimpleNamespace(
                now=lambda: SimpleNamespace(second=30, minute=2)
            )
        ),
    )

    def stop_wait(_seconds):
        trade.keyboard_listener_state = 0
        trade.should_continue = False

    monkeypatch.setattr(actions.time, "sleep", stop_wait)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("wait_for_key_count_down", "enter", [("speak_text", "cleanup")])],
    )
    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == ["30 seconds.", "cleanup", "Canceled."]


def test_wait_for_key_count_down_parse_failure_resets_listener_state(
    monkeypatch,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["General"]["countdown_seconds_before_candle_close"] = "30, bad"
    _patch_action_modules(monkeypatch)

    with pytest.raises(ValueError):
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("wait_for_key_count_down", "enter")],
        )

    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == []


def test_wait_for_price_cancellation_runs_cleanup_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def fake_recognize_text(*_args, **kwargs):
        should_continue_reference = kwargs["should_continue_reference"]
        assert should_continue_reference()
        trade.should_continue = False
        return None

    monkeypatch.setattr(
        actions,
        "text_recognition",
        SimpleNamespace(recognize_text=fake_recognize_text),
    )

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            (
                "wait_for_price",
                "0, 0, 10, 10, 0",
                [("speak_text", "cleanup")],
            )
        ],
    )
    assert spoken == ["cleanup", "Canceled."]


def test_wait_for_price_cancellation_raises_for_cleanup_failure(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def fake_recognize_text(*_args, **kwargs):
        should_continue_reference = kwargs["should_continue_reference"]
        assert should_continue_reference()
        trade.should_continue = False
        return None

    monkeypatch.setattr(
        actions,
        "text_recognition",
        SimpleNamespace(recognize_text=fake_recognize_text),
    )

    with pytest.raises(ActionExecutionError) as e:
        actions.execute_action(
            trade,
            config,
            gui_state,
            [
                (
                    "wait_for_price",
                    "0, 0, 10, 10, 0",
                    [("show_hide_indicator",)],
                )
            ],
        )

    assert "cancellation cleanup action failed" in str(e.value)
    _assert_action_error(e, ("inline action",), 1, "cancellation_cleanup")
    assert spoken == []


def test_wait_for_price_failure_resets_listener_state(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def fail_recognize_text(*_args, **kwargs):
        assert kwargs["should_continue_reference"]()
        raise RuntimeError("ocr failed")

    monkeypatch.setattr(
        actions,
        "text_recognition",
        SimpleNamespace(recognize_text=fail_recognize_text),
    )

    with pytest.raises(RuntimeError, match="ocr failed"):
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("wait_for_price", "0, 0, 10, 10, 0")],
        )

    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == []


def test_wait_for_window_cancellation_runs_cleanup_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def fake_wait_for_window(_title, *, should_continue_reference):
        assert should_continue_reference()
        trade.should_continue = False

    monkeypatch.setattr(
        actions,
        "gui_interactions",
        SimpleNamespace(wait_for_window=fake_wait_for_window),
    )

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("wait_for_window", "Order", [("speak_text", "cleanup")])],
    )
    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == ["cleanup", "Canceled."]


def test_wait_for_window_failure_resets_listener_state(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    def fail_wait_for_window(_title, *, should_continue_reference):
        assert should_continue_reference()
        raise RuntimeError("window failed")

    monkeypatch.setattr(
        actions,
        "gui_interactions",
        SimpleNamespace(wait_for_window=fail_wait_for_window),
    )

    with pytest.raises(RuntimeError, match="window failed"):
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("wait_for_window", "Order")],
        )

    assert trade.keyboard_listener_state == 0
    assert trade.key_to_check is None
    assert spoken == []


def test_copy_symbols_from_column_closes_clipboard(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    calls = _patch_clipboard(monkeypatch)
    monkeypatch.setattr(
        actions,
        "text_recognition",
        SimpleNamespace(
            recognize_text=lambda *_args, **_kwargs: ["1234", "5678"]
        ),
    )

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("copy_symbols_from_column", "0, 0, 10, 10, 0")],
    )
    assert calls == ["open", "empty", ("set", "1234 5678"), "close"]


def test_copy_symbols_from_column_preserves_clipboard_on_ocr_error(
    monkeypatch,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    calls = _patch_clipboard(monkeypatch)

    def fail_recognize_text(*_args, **_kwargs):
        raise RuntimeError("ocr failed")

    monkeypatch.setattr(
        actions,
        "text_recognition",
        SimpleNamespace(recognize_text=fail_recognize_text),
    )

    with pytest.raises(RuntimeError, match="ocr failed"):
        actions.execute_action(
            trade,
            config,
            gui_state,
            [("copy_symbols_from_column", "0, 0, 10, 10, 0")],
        )
    assert calls == []


def test_archive_market_data_failure_speaks_error_and_stops(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    monkeypatch.setattr(
        actions,
        "archive_market_data",
        lambda *_args: (False, "Unable to archive market data. details"),
    )

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            ("archive_market_data", None),
            ("speak_text", "should not run"),
        ],
    )
    assert spoken == [actions.ARCHIVE_MARKET_DATA_ERROR]


def test_calculate_share_size_failure_speaks_error_and_stops(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    monkeypatch.setattr(
        actions,
        "calculate_share_size",
        lambda *_args: (False, "Margin trading suspended."),
    )

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            ("calculate_share_size", "long"),
            ("speak_text", "should not run"),
        ],
    )
    assert spoken == ["Margin trading suspended."]


def test_daily_loss_limit_failure_speaks_error_and_stops(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    trade.cash_balance = 98000
    gui_state = _build_gui_state()
    config = _build_config()
    config["Variables"]["initial_cash_balance"] = "100000"
    _patch_action_modules(monkeypatch)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            ("check_daily_loss_limit", "Daily loss limit reached."),
            ("speak_text", "should not run"),
        ],
    )
    assert spoken == ["Daily loss limit reached."]


def test_maximum_daily_number_of_trades_speaks_error_and_stops(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["Variables"]["current_number_of_trades"] = "5"
    _patch_action_modules(monkeypatch)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            (
                "check_maximum_daily_number_of_trades",
                "Trade count limit reached.",
            ),
            ("speak_text", "should not run"),
        ],
    )
    assert spoken == ["Trade count limit reached."]


def test_show_hide_indicator_returns_false_without_widgets_section(
    monkeypatch,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("show_hide_indicator",)],
    )


def test_invalid_nested_action_argument_returns_false_without_printing(
    monkeypatch,
    capsys,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("is_now_after", "00:00:00", 123)],
    )
    assert capsys.readouterr().out == ""


def test_all_keys_includes_execute_action_and_market_data_commands():
    assert "archive_market_data" in actions.ALL_KEYS
    assert "execute_action" in actions.ALL_KEYS


def test_all_keys_are_sorted_command_dispatch_keys():
    assert actions.ALL_KEYS == tuple(sorted(actions._COMMAND_DISPATCH))
