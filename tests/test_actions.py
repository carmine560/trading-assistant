"""Tests for extracted action execution helpers."""

from configparser import ConfigParser
from types import SimpleNamespace

import pytest

from app import actions
from core_utilities.errors import ActionExecutionError


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
    monkeypatch.setattr(actions, "save_market_data", lambda *_args: True)
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


def test_copy_symbols_from_column_closes_clipboard_on_error(monkeypatch):
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
    assert calls == ["open", "empty", "close"]


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


def test_save_market_data_failure_speaks_error_and_stops(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    _patch_action_modules(monkeypatch)
    monkeypatch.setattr(actions, "save_market_data", lambda *_args: False)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            ("save_market_data", None),
            ("speak_text", "should not run"),
        ],
    )
    assert spoken == [actions.SAVE_MARKET_DATA_ERROR]


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


def test_all_keys_includes_execute_action_and_save_market_data():
    assert "execute_action" in actions.ALL_KEYS
    assert "save_market_data" in actions.ALL_KEYS


def test_all_keys_are_sorted_command_dispatch_keys():
    assert actions.ALL_KEYS == tuple(sorted(actions._COMMAND_DISPATCH))
