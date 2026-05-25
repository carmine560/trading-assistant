"""Tests for scheduled action registration."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from app import action_errors, scheduler
from app.action_errors import ActionLookupError


def test_start_scheduler_raises_typed_error_for_missing_action(monkeypatch):
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'missing')"},
        "Actions": {},
    }

    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    with pytest.raises(ActionLookupError) as e:
        scheduler.start_scheduler(
            trade,
            config,
            object(),
            "HYPERSBI2",
            object(),
        )

    assert str(e.value) == "Action 'missing' is not defined."
    assert e.value.action_name == "missing"


def test_start_scheduler_registers_future_scheduled_action(monkeypatch):
    scheduled = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'open')"},
        "Actions": {"open": [("speak_text", "ready")]},
    }
    gui_state = object()

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            scheduled.append((trigger, priority, action, argument, kwargs))
            return "schedule"

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    scheduler.start_scheduler(
        trade,
        config,
        gui_state,
        "HYPERSBI2",
        object(),
    )

    assert len(scheduled) == 1
    assert scheduled[0][1] == 1
    assert scheduled[0][2] is scheduler._run_scheduled_action
    assert scheduled[0][3][:3] == (trade, config, gui_state)
    assert scheduled[0][3][3:] == ("open", [("speak_text", "ready")], False)
    assert scheduled[0][4] == {}


def test_start_scheduler_uses_configured_timezone_for_trigger(monkeypatch):
    scheduled = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'open')"},
        "Actions": {"open": [("speak_text", "ready")]},
    }

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 25, 8, 30, tzinfo=tz)

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            scheduled.append((trigger, priority, action, argument, kwargs))
            return "schedule"

    current_epoch = datetime(
        2026,
        5,
        24,
        23,
        30,
        tzinfo=scheduler.ZoneInfo("UTC"),
    ).timestamp()
    expected_trigger = datetime(
        2026,
        5,
        25,
        9,
        0,
        tzinfo=scheduler.ZoneInfo("Asia/Tokyo"),
    ).timestamp()

    monkeypatch.setattr(scheduler, "datetime", FakeDateTime)
    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: current_epoch)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert scheduled[0][0] == expected_trigger


def test_start_scheduler_locks_blocking_scheduled_action(monkeypatch):
    scheduled = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'open')"},
        "Actions": {"open": [("click", "1,2")]},
    }

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            scheduled.append((trigger, priority, action, argument, kwargs))
            return "schedule"

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert scheduled[0][2] is scheduler._run_scheduled_action
    assert scheduled[0][3][3:] == ("open", [("click", "1,2")], True)
    assert scheduled[0][4] == {}


def test_start_scheduler_does_not_lock_inline_nested_speech_action(
    monkeypatch,
):
    scheduled = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    action = [
        (
            "is_trading_day",
            "True",
            [("speak_minutes_since_hour",)],
        )
    ]
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'announce')"},
        "Actions": {"announce": action},
    }

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            scheduled.append((trigger, priority, action, argument, kwargs))
            return "schedule"

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert scheduled[0][2] is scheduler._run_scheduled_action
    assert scheduled[0][3][3:] == ("announce", action, False)
    assert scheduled[0][4] == {}


def test_start_scheduler_locks_named_nested_blocking_action(monkeypatch):
    scheduled = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    action = [("is_trading_day", "True", "place_order")]
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'conditional_order')"},
        "Actions": {
            "conditional_order": action,
            "place_order": [("click", "1,2")],
        },
    }

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            scheduled.append((trigger, priority, action, argument, kwargs))
            return "schedule"

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert scheduled[0][2] is scheduler._run_scheduled_action
    assert scheduled[0][3][3:] == ("conditional_order", action, True)
    assert scheduled[0][4] == {}


def test_start_scheduler_does_not_lock_named_nested_speech_action(monkeypatch):
    scheduled = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    action = [("is_trading_day", "True", "announce")]
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'conditional_announce')"},
        "Actions": {
            "conditional_announce": action,
            "announce": [("speak_text", "ready")],
        },
    }

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            scheduled.append((trigger, priority, action, argument, kwargs))
            return "schedule"

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert scheduled[0][2] is scheduler._run_scheduled_action
    assert scheduled[0][3][3:] == ("conditional_announce", action, False)
    assert scheduled[0][4] == {}


def test_start_scheduler_rejects_missing_named_nested_action(monkeypatch):
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'conditional_order')"},
        "Actions": {
            "conditional_order": [("is_trading_day", "True", "place_order")],
        },
    }

    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    with pytest.raises(action_errors.ActionExecutionError) as e:
        scheduler.start_scheduler(
            trade,
            config,
            object(),
            "HYPERSBI2",
            object(),
        )

    assert "nested action 'place_order' is not defined" in str(e.value)
    assert e.value.action_path == ("conditional_order",)
    assert e.value.instruction_index == 1
    assert e.value.command == "is_trading_day"


def test_start_scheduler_rejects_cyclic_named_nested_action(monkeypatch):
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {"morning": "('09:00:00', 'conditional_order')"},
        "Actions": {
            "conditional_order": [("is_trading_day", "True", "place_order")],
            "place_order": [("is_trading_day", "True", "conditional_order")],
        },
    }

    monkeypatch.setattr(scheduler.time, "time", lambda: 0)

    with pytest.raises(action_errors.ActionExecutionError) as e:
        scheduler.start_scheduler(
            trade,
            config,
            object(),
            "HYPERSBI2",
            object(),
        )

    assert "nested action 'conditional_order' creates a cycle" in str(e.value)
    assert e.value.action_path == ("conditional_order", "place_order")
    assert e.value.instruction_index == 1
    assert e.value.command == "is_trading_day"


def test_start_scheduler_continues_after_scheduled_action_failure(monkeypatch):
    calls = []
    spoken = []
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
        speech_manager=SimpleNamespace(set_speech_text=spoken.append),
    )
    first_action = [("speak_text", "first")]
    second_action = [("speak_text", "second")]
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {
            "first": "('09:00:00', 'first_action')",
            "second": "('09:00:01', 'second_action')",
        },
        "Actions": {
            "first_action": first_action,
            "second_action": second_action,
        },
    }

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            event = SimpleNamespace(
                time=trigger,
                priority=priority,
                action=action,
                argument=argument,
                kwargs=kwargs,
            )
            self.queue.append(event)
            return event

        def run(self, _blocking):
            event = self.queue.pop(0)
            event.action(*event.argument, **event.kwargs)

    def execute_action(*args, **kwargs):
        calls.append((args[3], kwargs))
        if args[3] == first_action:
            raise RuntimeError("first failed")
        return True

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)
    monkeypatch.setattr(scheduler.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        scheduler.process_utilities,
        "is_running",
        lambda _process: True,
    )
    monkeypatch.setattr(scheduler.actions, "execute_action", execute_action)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert calls == [
        (
            first_action,
            {
                "action_path": ("first_action",),
                "is_top_level_action": False,
                "should_initialize": False,
            },
        ),
        (
            second_action,
            {
                "action_path": ("second_action",),
                "is_top_level_action": False,
                "should_initialize": False,
            },
        ),
    ]
    assert isinstance(trade.scheduler_error, RuntimeError)
    assert str(trade.scheduler_error) == "first failed"
    assert spoken == [scheduler.SCHEDULED_ACTION_ERROR]


def test_start_scheduler_reports_false_scheduled_action(monkeypatch):
    calls = []
    spoken = []
    previous_error = RuntimeError("guard failed")
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
        speech_manager=SimpleNamespace(set_speech_text=spoken.append),
        last_action_error=previous_error,
    )
    first_action = [("speak_text", "first")]
    second_action = [("speak_text", "second")]
    config = {
        "Market Data": {"timezone": "Asia/Tokyo"},
        "Schedules": {
            "first": "('09:00:00', 'first_action')",
            "second": "('09:00:01', 'second_action')",
        },
        "Actions": {
            "first_action": first_action,
            "second_action": second_action,
        },
    }

    class FakeScheduler:
        def __init__(self, _timefunc, _delayfunc):
            self.queue = []

        def enterabs(self, trigger, priority, action, argument, kwargs):
            event = SimpleNamespace(
                time=trigger,
                priority=priority,
                action=action,
                argument=argument,
                kwargs=kwargs,
            )
            self.queue.append(event)
            return event

        def run(self, _blocking):
            event = self.queue.pop(0)
            event.action(*event.argument, **event.kwargs)

    def execute_action(*args, **kwargs):
        calls.append((args[3], kwargs))
        return args[3] != first_action

    monkeypatch.setattr(scheduler.sched, "scheduler", FakeScheduler)
    monkeypatch.setattr(scheduler.time, "time", lambda: 0)
    monkeypatch.setattr(scheduler.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        scheduler.process_utilities,
        "is_running",
        lambda _process: True,
    )
    monkeypatch.setattr(scheduler.actions, "execute_action", execute_action)

    scheduler.start_scheduler(
        trade,
        config,
        object(),
        "HYPERSBI2",
        object(),
    )

    assert calls == [
        (
            first_action,
            {
                "action_path": ("first_action",),
                "is_top_level_action": False,
                "should_initialize": False,
            },
        ),
        (
            second_action,
            {
                "action_path": ("second_action",),
                "is_top_level_action": False,
                "should_initialize": False,
            },
        ),
    ]
    assert isinstance(trade.scheduler_error, action_errors.ActionFailureError)
    assert str(trade.scheduler_error) == "Action 'first_action' failed."
    assert trade.scheduler_error.__cause__ is previous_error
    assert trade.last_action_error is previous_error
    assert spoken == [scheduler.SCHEDULED_ACTION_ERROR]
