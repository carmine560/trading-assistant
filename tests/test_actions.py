"""Tests for extracted action execution helpers."""

import ast
from configparser import ConfigParser
from types import SimpleNamespace

from app import actions


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


def _build_deps(monkeypatch, spoken, extra=None):
    """Create a dependency bundle for action execution tests."""
    sleep_calls = []
    monkeypatch.setattr(actions.time, "sleep", sleep_calls.append)

    deps = {
        "calculate_share_size_fn": lambda *_args: (True, None),
        "configuration": SimpleNamespace(
            evaluate_value=lambda value: (
                ast.literal_eval(value) if isinstance(value, str) else value
            )
        ),
        "data_utilities": SimpleNamespace(get_target_time=lambda *_args: 0),
        "file_utilities": SimpleNamespace(
            get_latest_file=lambda *_args: "video.mp4",
            is_writing=lambda *_args: False,
            write_chapter=lambda *_args, **_kwargs: None,
        ),
        "gui_interactions": SimpleNamespace(
            _show_window_state={"count": 0, "max_count": 0},
            click_widget=lambda *_args, **_kwargs: None,
            enumerate_windows=lambda *_args, **_kwargs: None,
            hide_window=lambda *_args, **_kwargs: None,
            show_hide_window=lambda *_args, **_kwargs: None,
            show_window=lambda *_args, **_kwargs: None,
            wait_for_window=lambda *_args, **_kwargs: None,
        ),
        "indicator_thread_cls": lambda *_args: SimpleNamespace(
            start=lambda: None
        ),
        "is_trading_day_fn": lambda *_args: True,
        "keyboard": SimpleNamespace(Key={"enter": object()}),
        "message_thread_cls": lambda *_args: SimpleNamespace(
            start=lambda: None
        ),
        "pd": SimpleNamespace(
            Timestamp=SimpleNamespace(
                now=lambda **_kwargs: SimpleNamespace(
                    second=0, minute=0, strftime=lambda _fmt: "2026-05-06"
                )
            )
        ),
        "psutil": SimpleNamespace(cpu_percent=lambda interval: 12.4),
        "pyautogui": SimpleNamespace(
            click=lambda *_args, **_kwargs: None,
            dragTo=lambda *_args, **_kwargs: None,
            hotkey=lambda *_args, **_kwargs: None,
            moveTo=lambda *_args, **_kwargs: None,
            press=lambda *_args, **_kwargs: None,
            rightClick=lambda *_args, **_kwargs: None,
            write=lambda *_args, **_kwargs: None,
        ),
        "save_market_data_fn": lambda *_args: True,
        "text_recognition": SimpleNamespace(
            recognize_text=lambda *_args, **_kwargs: 100
        ),
        "win32clipboard": SimpleNamespace(
            OpenClipboard=lambda: None,
            EmptyClipboard=lambda: None,
            SetClipboardText=lambda _text: None,
            CloseClipboard=lambda: None,
        ),
    }
    if extra:
        deps.update(extra)
    return deps, sleep_calls


def test_execute_action_speaks_text_with_explicit_dependencies(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    deps, _ = _build_deps(monkeypatch, spoken)

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("speak_text", "ready")],
        deps,
    )
    assert spoken == ["ready"]
    assert (trade.initialized, gui_state.initialized) == (1, 1)


def test_execute_action_runs_named_nested_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    config["Actions"]["nested"] = str([("speak_text", "nested")])
    deps, _ = _build_deps(monkeypatch, spoken)

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("execute_action", "nested"), ("speak_text", "done")],
        deps,
    )
    assert spoken == ["nested", "done"]
    assert (trade.initialized, gui_state.initialized) == (1, 1)


def test_execute_action_returns_false_for_unknown_command(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    deps, _ = _build_deps(monkeypatch, spoken)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("unknown_command",)],
        deps,
    )
    assert spoken == []


def test_execute_action_unknown_command_does_not_print(monkeypatch, capsys):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    deps, _ = _build_deps(monkeypatch, spoken)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("unknown_command",)],
        deps,
    )
    assert capsys.readouterr().out == ""


def test_wait_for_price_cancellation_runs_cleanup_action(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()

    def fake_recognize_text(*_args, **kwargs):
        should_continue_reference = kwargs["should_continue_reference"]
        assert should_continue_reference()
        trade.should_continue = False
        return None

    deps, _ = _build_deps(
        monkeypatch,
        spoken,
        extra={
            "text_recognition": SimpleNamespace(
                recognize_text=fake_recognize_text
            )
        },
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
        deps,
    )
    assert spoken == ["cleanup", "Canceled."]


def test_calculate_share_size_failure_speaks_error_and_stops(monkeypatch):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    deps, _ = _build_deps(
        monkeypatch,
        spoken,
        extra={
            "calculate_share_size_fn": (
                lambda *_args: (False, "Margin trading suspended.")
            )
        },
    )

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [
            ("calculate_share_size", "long"),
            ("speak_text", "should not run"),
        ],
        deps,
    )
    assert spoken == ["Margin trading suspended."]


def test_show_hide_indicator_returns_false_without_widgets_section(
    monkeypatch,
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    deps, _ = _build_deps(monkeypatch, spoken)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("show_hide_indicator",)],
        deps,
    )


def test_invalid_nested_action_argument_returns_false_without_printing(
    monkeypatch, capsys
):
    spoken = []
    trade = _build_trade(spoken)
    gui_state = _build_gui_state()
    config = _build_config()
    deps, _ = _build_deps(monkeypatch, spoken)

    assert not actions.execute_action(
        trade,
        config,
        gui_state,
        [("is_now_after", "00:00:00", 123)],
        deps,
    )
    assert capsys.readouterr().out == ""


def test_all_keys_includes_execute_action_and_save_market_data():
    assert "execute_action" in actions.ALL_KEYS
    assert "save_market_data" in actions.ALL_KEYS
