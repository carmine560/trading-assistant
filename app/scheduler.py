"""Time-based action scheduling for active trading assistant sessions."""

import sched
import time

from app import action_errors, actions, listeners
from core_utilities import process_utilities
from core_utilities.config_validation import evaluate_value
from interaction_utilities import speech_synthesis

NON_BLOCKING_SCHEDULE_COMMANDS = {
    "is_trading_day",
    "speak_minutes_since_hour",
    "speak_seconds_since_time",
    "speak_seconds_until_time",
    "speak_text",
}


def start_scheduler(trade, config, gui_state, process, base_manager):
    """Start a scheduler for executing actions at specified times."""
    should_stop_speaking_process = False
    if not trade.speaking_process:
        trade.speaking_process = listeners.start_speaking_process(
            trade, config
        )
        should_stop_speaking_process = True

    try:
        scheduler = sched.scheduler(time.time, time.sleep)
        schedules = []

        section = config[trade.schedules_section]
        for option in section:
            trigger, action = evaluate_value(section[option])
            trigger = time.strptime(
                time.strftime("%Y-%m-%d ") + trigger,
                "%Y-%m-%d %H:%M:%S",
            )
            trigger = time.mktime(trigger)
            if time.time() < trigger:
                try:
                    scheduled_action = config[trade.actions_section][action]
                except KeyError as e:
                    raise action_errors.ActionLookupError(
                        f"Action '{action}' is not defined.",
                        action_name=action,
                    ) from e
                is_blocking_schedule_action = _is_blocking_schedule_action(
                    scheduled_action
                )
                schedule = scheduler.enterabs(
                    trigger,
                    1,
                    actions.execute_action,
                    argument=(
                        trade,
                        config,
                        gui_state,
                        scheduled_action,
                    ),
                    kwargs={
                        "should_initialize": is_blocking_schedule_action,
                        "should_acquire_lock": is_blocking_schedule_action,
                        "action_path": (action,),
                    },
                )
                schedules.append(schedule)

        while scheduler.queue:
            if process_utilities.is_running(process):
                scheduler.run(False)
                time.sleep(
                    max(0.0, min(scheduler.queue[0].time - time.time(), 1.0))
                    if scheduler.queue
                    else 1.0
                )
            else:
                for schedule in schedules:
                    if schedule in scheduler.queue:
                        scheduler.cancel(schedule)
    finally:
        if should_stop_speaking_process:
            speech_synthesis.stop_speaking_process(
                base_manager, trade.speech_manager, trade.speaking_process
            )


def _is_blocking_schedule_action(action):
    """Return True unless an action is confirmed as speech-only."""
    if isinstance(action, str):
        action = evaluate_value(action)

    for instruction in action:
        try:
            command = instruction[0]
            additional_argument = (
                instruction[2] if len(instruction) > 2 else None
            )
        except (IndexError, TypeError):
            return True

        if command not in NON_BLOCKING_SCHEDULE_COMMANDS:
            return True
        if isinstance(additional_argument, list) and (
            _is_blocking_schedule_action(additional_argument)
        ):
            return True
    return False
