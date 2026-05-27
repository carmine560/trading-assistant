"""Tests for listener startup helpers."""

from types import SimpleNamespace

from app import listeners
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
    )
    config = {"General": {"voice_name": "voice", "speech_rate": "1"}}
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
