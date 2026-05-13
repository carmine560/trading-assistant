"""Tests for extracted runtime orchestration."""

from types import SimpleNamespace

from app import runtime


def test_run_executes_single_action_with_transient_listeners(monkeypatch):
    calls = []
    args = SimpleNamespace(r=False, s=False, l=False, a=["open"])
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
        mouse_listener="mouse",
        keyboard_listener="keyboard",
        speaking_process="speaker",
        stop_listeners_event=SimpleNamespace(
            set=lambda: calls.append("event.set")
        ),
        wait_listeners_thread=SimpleNamespace(
            join=lambda: calls.append("thread.join")
        ),
    )
    config = {"Actions": {"open": [("speak_text", "ready")]}}
    gui_state = object()

    class FakeManager:
        @classmethod
        def register(cls, name, speech_cls):
            calls.append(("register", name, speech_cls))

        def start(self):
            calls.append("manager.start")

        def SpeechManager(self):
            calls.append("manager.SpeechManager")
            return "speech_manager"

    monkeypatch.setattr(
        runtime,
        "atexit",
        SimpleNamespace(register=lambda *args: calls.append("atexit")),
    )
    monkeypatch.setattr(runtime, "BaseManager", FakeManager)
    monkeypatch.setattr(
        runtime,
        "actions",
        SimpleNamespace(
            execute_action=(
                lambda trade, config, gui_state, action: calls.append(
                    ("execute_action", action)
                )
            )
        ),
    )
    monkeypatch.setattr(
        runtime,
        "customer_margin_ratios",
        SimpleNamespace(
            save_customer_margin_ratios=(
                lambda trade, config: calls.append(
                    "save_customer_margin_ratios"
                )
            )
        ),
    )
    monkeypatch.setattr(
        runtime,
        "listeners",
        SimpleNamespace(
            start_listeners=(
                lambda trade, config, gui_state, base_manager, **kwargs: (
                    calls.append(("start_listeners", kwargs))
                )
            )
        ),
    )
    monkeypatch.setattr(
        runtime,
        "process_utilities",
        SimpleNamespace(
            is_running=lambda process: False,
            stop_listeners=lambda *args: calls.append("stop_listeners"),
        ),
    )
    monkeypatch.setattr(
        runtime,
        "speech_synthesis",
        SimpleNamespace(SpeechManager=object),
    )
    monkeypatch.setattr(
        runtime,
        "threading",
        SimpleNamespace(
            Thread=lambda *args, **kwargs: SimpleNamespace(
                start=lambda: calls.append("thread.start")
            )
        ),
    )
    monkeypatch.setattr(runtime, "write_config", lambda *args, **kwargs: None)

    runtime.run(args, trade, config, gui_state)

    assert ("start_listeners", {"is_persistent": True}) in calls
    assert ("execute_action", [("speak_text", "ready")]) in calls
    assert "stop_listeners" in calls
    assert "event.set" in calls
    assert "thread.join" in calls


def test_run_cleans_up_transient_listeners_when_action_raises(monkeypatch):
    calls = []
    args = SimpleNamespace(r=False, s=False, l=False, a=["open"])
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
        mouse_listener="mouse",
        keyboard_listener="keyboard",
        speaking_process="speaker",
        stop_listeners_event=SimpleNamespace(
            set=lambda: calls.append("event.set")
        ),
        wait_listeners_thread=SimpleNamespace(
            join=lambda: calls.append("thread.join")
        ),
    )
    config = {"Actions": {"open": [("speak_text", "ready")]}}
    gui_state = object()

    class FakeManager:
        @classmethod
        def register(cls, name, speech_cls):
            calls.append(("register", name, speech_cls))

        def start(self):
            calls.append("manager.start")

        def SpeechManager(self):
            calls.append("manager.SpeechManager")
            return "speech_manager"

    def raise_execute_action(*_args):
        calls.append("execute_action")
        raise RuntimeError("boom")

    monkeypatch.setattr(
        runtime,
        "atexit",
        SimpleNamespace(register=lambda *args: calls.append("atexit")),
    )
    monkeypatch.setattr(runtime, "BaseManager", FakeManager)
    monkeypatch.setattr(
        runtime,
        "actions",
        SimpleNamespace(execute_action=raise_execute_action),
    )
    monkeypatch.setattr(
        runtime,
        "listeners",
        SimpleNamespace(
            start_listeners=(
                lambda trade, config, gui_state, base_manager, **kwargs: (
                    calls.append(("start_listeners", kwargs))
                )
            )
        ),
    )
    monkeypatch.setattr(
        runtime,
        "process_utilities",
        SimpleNamespace(
            is_running=lambda process: False,
            stop_listeners=lambda *args: calls.append("stop_listeners"),
        ),
    )
    monkeypatch.setattr(
        runtime,
        "speech_synthesis",
        SimpleNamespace(SpeechManager=object),
    )
    monkeypatch.setattr(
        runtime,
        "threading",
        SimpleNamespace(
            Thread=lambda *args, **kwargs: SimpleNamespace(
                start=lambda: calls.append("thread.start")
            )
        ),
    )
    monkeypatch.setattr(runtime, "write_config", lambda *args, **kwargs: None)

    try:
        runtime.run(args, trade, config, gui_state)
    except RuntimeError as e:
        assert str(e) == "boom"
    else:
        raise AssertionError("Expected runtime.run() to re-raise the action.")

    assert ("start_listeners", {"is_persistent": True}) in calls
    assert "execute_action" in calls
    assert "stop_listeners" in calls
    assert "event.set" in calls
    assert "thread.join" in calls
