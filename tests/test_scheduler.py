"""Tests for scheduled action registration."""

from types import SimpleNamespace

import pytest

from app.action_errors import ActionLookupError
from app import scheduler


def test_start_scheduler_raises_typed_error_for_missing_action(monkeypatch):
    trade = SimpleNamespace(
        schedules_section="Schedules",
        actions_section="Actions",
        speaking_process="speaker",
    )
    config = {
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
    assert scheduled[0][2] is scheduler.actions.execute_action
    assert scheduled[0][3] == (
        trade,
        config,
        gui_state,
        [("speak_text", "ready")],
    )
    assert scheduled[0][4] == {"action_path": ("open",)}
