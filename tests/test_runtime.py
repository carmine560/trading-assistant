"""Tests for extracted runtime orchestration."""

from types import SimpleNamespace

from app import action_errors
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
                lambda trade, config, gui_state, action, **kwargs: (
                    calls.append(("execute_action", action))
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


def test_run_raises_typed_error_for_missing_single_action(monkeypatch):
    calls = []
    args = SimpleNamespace(r=False, s=False, l=False, a=["missing"])
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
    config = {"Actions": {}}
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
            execute_action=lambda *_args, **_kwargs: calls.append(
                "execute_action"
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
    monkeypatch.setattr(runtime, "write_config", lambda *args, **kwargs: None)

    try:
        runtime.run(args, trade, config, gui_state)
    except action_errors.ActionLookupError as e:
        assert str(e) == "Action 'missing' is not defined."
        assert e.action_name == "missing"
    else:
        raise AssertionError("Expected missing action to raise typed error.")

    assert ("start_listeners", {"is_persistent": True}) in calls
    assert "execute_action" not in calls
    assert "stop_listeners" in calls
    assert "event.set" in calls
    assert "thread.join" in calls


def test_run_cleans_up_partial_transient_listener_startup(monkeypatch):
    calls = []
    args = SimpleNamespace(r=False, s=False, l=False, a=["open"])
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
        mouse_listener=None,
        keyboard_listener=None,
        speaking_process=None,
        stop_listeners_event=None,
        wait_listeners_thread=None,
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

        def shutdown(self):
            calls.append("manager.shutdown")

    def raise_start_listeners(
        trade, config, gui_state, base_manager, **kwargs
    ):
        trade.mouse_listener = "mouse"
        trade.keyboard_listener = "keyboard"
        calls.append(("start_listeners", kwargs))
        raise RuntimeError("listener boom")

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
            execute_action=lambda *_args, **_kwargs: calls.append(
                "execute_action"
            )
        ),
    )
    monkeypatch.setattr(
        runtime,
        "listeners",
        SimpleNamespace(start_listeners=raise_start_listeners),
    )
    monkeypatch.setattr(
        runtime,
        "process_utilities",
        SimpleNamespace(
            is_running=lambda process: False,
            stop_listeners=lambda *args: calls.append(
                ("stop_listeners", args)
            ),
        ),
    )
    monkeypatch.setattr(
        runtime,
        "speech_synthesis",
        SimpleNamespace(SpeechManager=object),
    )
    monkeypatch.setattr(runtime, "write_config", lambda *args, **kwargs: None)

    try:
        runtime.run(args, trade, config, gui_state)
    except RuntimeError as e:
        assert str(e) == "listener boom"
    else:
        raise AssertionError(
            "Expected partial listener startup failure to re-raise."
        )

    assert ("start_listeners", {"is_persistent": True}) in calls
    assert "execute_action" not in calls
    assert "manager.shutdown" in calls
    assert "event.set" not in calls
    assert "thread.join" not in calls
    stop_call = next(
        call
        for call in calls
        if isinstance(call, tuple) and call[0] == "stop_listeners"
    )
    assert stop_call[1][0] == "mouse"
    assert stop_call[1][1] == "keyboard"
    assert stop_call[1][2].__class__ is FakeManager
    assert stop_call[1][3] == "speech_manager"
    assert stop_call[1][4] is None


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

    def raise_execute_action(*_args, **_kwargs):
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


def test_run_captures_scheduler_thread_failure(monkeypatch):
    calls = []
    spoken = []
    args = SimpleNamespace(r=False, s=True, l=False, a=None)
    trade = SimpleNamespace(process="HYPERSBI2")
    config = {"Actions": {}}
    gui_state = object()

    class FakeManager:
        @classmethod
        def register(cls, name, speech_cls):
            calls.append(("register", name, speech_cls))

        def start(self):
            calls.append("manager.start")

        def SpeechManager(self):
            calls.append("manager.SpeechManager")
            return SimpleNamespace(set_speech_text=spoken.append)

    class FakeThread:
        def __init__(self, *, target):
            self.target = target
            calls.append(("thread", target))

        def start(self):
            calls.append("thread.start")
            self.target()

    def raise_scheduler_error(*_args):
        raise action_errors.ActionLookupError(
            "Action 'open' is not defined.",
            action_name="open",
        )

    monkeypatch.setattr(
        runtime,
        "atexit",
        SimpleNamespace(register=lambda *args: calls.append("atexit")),
    )
    monkeypatch.setattr(runtime, "BaseManager", FakeManager)
    monkeypatch.setattr(
        runtime,
        "process_utilities",
        SimpleNamespace(is_running=lambda process: True),
    )
    monkeypatch.setattr(
        runtime,
        "scheduler",
        SimpleNamespace(start_scheduler=raise_scheduler_error),
    )
    monkeypatch.setattr(
        runtime,
        "speech_synthesis",
        SimpleNamespace(SpeechManager=object),
    )
    monkeypatch.setattr(
        runtime,
        "threading",
        SimpleNamespace(Thread=FakeThread),
    )
    monkeypatch.setattr(runtime, "write_config", lambda *args, **kwargs: None)

    runtime.run(args, trade, config, gui_state)

    assert isinstance(trade.scheduler_error, action_errors.ActionLookupError)
    assert trade.scheduler_error.action_name == "open"
    assert spoken == [runtime.RUN_SCHEDULER_ERROR]
    assert "thread.start" in calls


def test_run_cleans_up_partial_persistent_listener_startup(monkeypatch):
    calls = []
    args = SimpleNamespace(r=False, s=False, l=True, a=None)
    trade = SimpleNamespace(
        process="HYPERSBI2",
        actions_section="Actions",
        mouse_listener=None,
        keyboard_listener=None,
        speaking_process=None,
        stop_listeners_event=None,
        wait_listeners_thread=None,
    )
    config = {"Actions": {}}
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

        def shutdown(self):
            calls.append("manager.shutdown")

    def raise_start_listeners(
        trade, config, gui_state, base_manager, **kwargs
    ):
        trade.mouse_listener = "mouse"
        trade.keyboard_listener = "keyboard"
        calls.append(("start_listeners", kwargs))
        raise RuntimeError("listener boom")

    monkeypatch.setattr(
        runtime,
        "atexit",
        SimpleNamespace(register=lambda *args: calls.append("atexit")),
    )
    monkeypatch.setattr(runtime, "BaseManager", FakeManager)
    monkeypatch.setattr(
        runtime,
        "customer_margin_ratios",
        SimpleNamespace(save_customer_margin_ratios=lambda *_args: None),
    )
    monkeypatch.setattr(
        runtime,
        "listeners",
        SimpleNamespace(start_listeners=raise_start_listeners),
    )
    monkeypatch.setattr(
        runtime,
        "process_utilities",
        SimpleNamespace(
            is_running=lambda process: True,
            stop_listeners=lambda *args: calls.append(
                ("stop_listeners", args)
            ),
        ),
    )
    monkeypatch.setattr(
        runtime,
        "speech_synthesis",
        SimpleNamespace(SpeechManager=object),
    )
    monkeypatch.setattr(runtime, "write_config", lambda *args, **kwargs: None)

    try:
        runtime.run(args, trade, config, gui_state)
    except RuntimeError as e:
        assert str(e) == "listener boom"
    else:
        raise AssertionError(
            "Expected persistent listener startup failure to re-raise."
        )

    assert ("start_listeners", {}) in calls
    assert "manager.shutdown" in calls
    assert "event.set" not in calls
    assert "thread.join" not in calls
    stop_call = next(
        call
        for call in calls
        if isinstance(call, tuple) and call[0] == "stop_listeners"
    )
    assert stop_call[1][0] == "mouse"
    assert stop_call[1][1] == "keyboard"
    assert stop_call[1][2].__class__ is FakeManager
    assert stop_call[1][3] == "speech_manager"
    assert stop_call[1][4] is None
