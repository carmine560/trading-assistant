"""Tests for extracted runtime orchestration."""

from types import SimpleNamespace

from app import runtime


def test_run_executes_single_action_with_transient_listeners():
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

    def start_listeners_fn(trade, config, gui_state, base_manager, **kwargs):
        calls.append(("start_listeners", kwargs))

    deps = {
        "atexit": SimpleNamespace(
            register=lambda *args: calls.append("atexit")
        ),
        "base_manager_cls": FakeManager,
        "configuration": SimpleNamespace(
            write_config=lambda *args, **kwargs: None
        ),
        "execute_action_fn": (
            lambda trade, config, gui_state, action: calls.append(
                ("execute_action", action)
            )
        ),
        "process_utilities": SimpleNamespace(
            is_running=lambda process: False,
            stop_listeners=lambda *args: calls.append("stop_listeners"),
        ),
        "save_customer_margin_ratios_fn": (
            lambda trade, config: calls.append("save_customer_margin_ratios")
        ),
        "speech_synthesis": SimpleNamespace(SpeechManager=object),
        "start_listeners_fn": start_listeners_fn,
        "start_scheduler_fn": lambda *args: calls.append("start_scheduler"),
        "threading": SimpleNamespace(
            Thread=lambda *args, **kwargs: SimpleNamespace(
                start=lambda: calls.append("thread.start")
            )
        ),
    }

    runtime.run(args, trade, config, gui_state, deps)

    assert ("start_listeners", {"is_persistent": True}) in calls
    assert ("execute_action", [("speak_text", "ready")]) in calls
    assert "stop_listeners" in calls
    assert "event.set" in calls
    assert "thread.join" in calls
