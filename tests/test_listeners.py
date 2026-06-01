"""Tests for listener startup helpers."""

from types import SimpleNamespace

import pytest

from app import listeners
from core_utilities.config_common import ConfigError
from core_utilities import errors


def test_start_listeners_records_wait_thread_failure(monkeypatch):
    spoken = []
    calls = []
    failure = errors.ProcessStateError("tasklist failed")
    trade = SimpleNamespace(
        process="HYPERSBI2",
        on_click=lambda *_args: None,
        on_press=lambda *_args: None,
        on_release=lambda *_args: None,
        speech_manager=SimpleNamespace(set_speech_text=spoken.append),
        indicator_thread="indicator",
        last_listener_error=None,
        actions_section="Actions",
    )
    config = {
        "Actions": {"show_indicator": [("show_hide_indicator",)]},
        "General": {"voice_name": "voice", "speech_rate": "1"},
        "HYPERSBI2": {"input_map": "{'f1': 'show_indicator'}"},
    }
    gui_state = SimpleNamespace()

    class FakeListener:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            calls.append(("listener.start", self.kwargs))

    class FakeThread:
        def __init__(self, *, target, args, kwargs):
            self.target = target
            self.args = args
            self.kwargs = kwargs

        def start(self):
            calls.append("thread.start")
            self.target(*self.args, **self.kwargs)

    monkeypatch.setattr(
        listeners.mouse,
        "Listener",
        lambda **kwargs: FakeListener(**kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        listeners.keyboard,
        "Listener",
        lambda **kwargs: FakeListener(**kwargs),
        raising=False,
    )
    monkeypatch.setattr(listeners.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        listeners,
        "start_speaking_process",
        lambda *_args: "speaking_process",
    )
    monkeypatch.setattr(
        listeners.process_utilities,
        "stop_listeners",
        lambda *args, **kwargs: calls.append(("stop_listeners", args, kwargs)),
    )
    monkeypatch.setattr(
        listeners.process_utilities,
        "is_running",
        lambda _process: (_ for _ in ()).throw(failure),
    )

    listeners.start_listeners(
        trade,
        config,
        gui_state,
        "base_manager",
        is_persistent=True,
    )

    assert trade.last_listener_error is failure
    assert spoken == [listeners.LISTENER_MONITOR_ERROR]
    assert "thread.start" in calls
    assert any(call[0] == "stop_listeners" for call in calls)


@pytest.mark.parametrize(
    "failure_stage",
    [
        "keyboard_start",
        "speech_start",
        "thread_init",
        "thread_start",
    ],
)
def test_start_listeners_cleans_up_partial_startup_failure(
    monkeypatch,
    failure_stage,
):
    calls = []
    failure = RuntimeError(f"{failure_stage} failed")
    speech_manager = SimpleNamespace()
    trade = SimpleNamespace(
        process="HYPERSBI2",
        on_click=lambda *_args: None,
        on_press=lambda *_args: None,
        on_release=lambda *_args: None,
        speech_manager=speech_manager,
        indicator_thread="indicator",
        last_listener_error="previous",
        actions_section="Actions",
        mouse_listener=None,
        keyboard_listener=None,
        speaking_process=None,
        stop_listeners_event=None,
        wait_listeners_thread=None,
    )
    config = {
        "Actions": {"show_indicator": [("show_hide_indicator",)]},
        "General": {"voice_name": "voice", "speech_rate": "1"},
        "HYPERSBI2": {"input_map": "{'f1': 'show_indicator'}"},
    }

    class FakeListener:
        def __init__(self, name, **kwargs):
            self.name = name
            self.kwargs = kwargs

        def start(self):
            calls.append((self.name, "start"))
            if failure_stage == f"{self.name}_start":
                raise failure

    class FakeThread:
        def __init__(self, *, target, args, kwargs):
            if failure_stage == "thread_init":
                raise failure
            self.target = target
            self.args = args
            self.kwargs = kwargs

        def start(self):
            calls.append("thread.start")
            if failure_stage == "thread_start":
                raise failure

    monkeypatch.setattr(
        listeners.mouse,
        "Listener",
        lambda **kwargs: FakeListener("mouse", **kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        listeners.keyboard,
        "Listener",
        lambda **kwargs: FakeListener("keyboard", **kwargs),
        raising=False,
    )
    monkeypatch.setattr(listeners.threading, "Thread", FakeThread)

    def fake_start_speaking_process(*_args):
        if failure_stage == "speech_start":
            raise failure
        return "speaking_process"

    def fake_stop_listeners(*args, **kwargs):
        calls.append(("stop_listeners", args, kwargs))

    monkeypatch.setattr(
        listeners,
        "start_speaking_process",
        fake_start_speaking_process,
    )
    monkeypatch.setattr(
        listeners.process_utilities,
        "stop_listeners",
        fake_stop_listeners,
    )

    with pytest.raises(RuntimeError) as e:
        listeners.start_listeners(
            trade,
            config,
            SimpleNamespace(),
            "base_manager",
        )

    assert e.value is failure
    stop_call = [call for call in calls if call[0] == "stop_listeners"][0]
    assert stop_call[1][0].name == "mouse"
    if failure_stage == "keyboard_start":
        assert stop_call[1][1].name == "keyboard"
        assert stop_call[1][4] is None
    elif failure_stage == "speech_start":
        assert stop_call[1][1].name == "keyboard"
        assert stop_call[1][4] is None
    else:
        assert stop_call[1][1].name == "keyboard"
        assert stop_call[1][4] == "speaking_process"
    assert stop_call[1][2] == "base_manager"
    assert stop_call[1][3] is speech_manager
    assert stop_call[2] == {"indicator_thread": "indicator"}
    assert trade.mouse_listener is None
    assert trade.keyboard_listener is None
    assert trade.speaking_process is None
    assert trade.stop_listeners_event is None
    assert trade.wait_listeners_thread is None


def test_start_listeners_rejects_non_mapping_input_map(monkeypatch):
    calls = []
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
    )
    config = {
        "Actions": {},
        "HYPERSBI2": {"input_map": "['f1', 'show_indicator']"},
    }

    monkeypatch.setattr(
        listeners.mouse,
        "Listener",
        lambda **_kwargs: calls.append("mouse.Listener"),
        raising=False,
    )

    with pytest.raises(ConfigError) as e:
        listeners.start_listeners(
            trade,
            config,
            SimpleNamespace(),
            "base_manager",
        )

    assert str(e.value) == (
        "HYPERSBI2.input_map must be a mapping of inputs to actions."
    )
    assert calls == []


def test_start_listeners_rejects_undefined_input_map_action(monkeypatch):
    calls = []
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
    )
    config = {
        "Actions": {},
        "HYPERSBI2": {"input_map": "{'f1': 'show_indicator'}"},
    }

    monkeypatch.setattr(
        listeners.mouse,
        "Listener",
        lambda **_kwargs: calls.append("mouse.Listener"),
        raising=False,
    )

    with pytest.raises(ConfigError) as e:
        listeners.start_listeners(
            trade,
            config,
            SimpleNamespace(),
            "base_manager",
        )

    assert str(e.value) == (
        "HYPERSBI2.input_map['f1'] references undefined action "
        "'show_indicator'."
    )
    assert calls == []


@pytest.mark.parametrize("input_name", ["F1", "middl"])
def test_start_listeners_rejects_unsupported_input_map_key(
    monkeypatch,
    input_name,
):
    calls = []
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
    )
    config = {
        "Actions": {},
        "HYPERSBI2": {"input_map": repr({input_name: ""})},
    }

    monkeypatch.setattr(
        listeners.mouse,
        "Listener",
        lambda **_kwargs: calls.append("mouse.Listener"),
        raising=False,
    )

    with pytest.raises(ConfigError) as e:
        listeners.start_listeners(
            trade,
            config,
            SimpleNamespace(),
            "base_manager",
        )

    assert str(e.value) == (
        f"HYPERSBI2.input_map[{input_name!r}] is not a supported input."
    )
    assert calls == []


def test_start_listeners_preserves_empty_supported_input_map_values(
    monkeypatch,
):
    calls = []
    trade = SimpleNamespace(
        process="HYPERSBI2",
        on_click=lambda *_args: None,
        on_press=lambda *_args: None,
        on_release=lambda *_args: None,
        speech_manager=SimpleNamespace(),
        indicator_thread=None,
        actions_section="Actions",
    )
    config = {
        "Actions": {},
        "General": {"voice_name": "voice", "speech_rate": "1"},
        "HYPERSBI2": {"input_map": "{'middle': '', 'f12': ''}"},
    }

    class FakeListener:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            calls.append(("listener.start", self.kwargs))

    class FakeThread:
        def __init__(self, *, target, args, kwargs):
            self.target = target
            self.args = args
            self.kwargs = kwargs

        def start(self):
            calls.append("thread.start")

    monkeypatch.setattr(
        listeners.mouse,
        "Listener",
        lambda **kwargs: FakeListener(**kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        listeners.keyboard,
        "Listener",
        lambda **kwargs: FakeListener(**kwargs),
        raising=False,
    )
    monkeypatch.setattr(listeners.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        listeners,
        "start_speaking_process",
        lambda *_args: "speaking_process",
    )

    listeners.start_listeners(
        trade,
        config,
        SimpleNamespace(),
        "base_manager",
    )

    assert len([call for call in calls if call[0] == "listener.start"]) == 2
    assert "thread.start" in calls
