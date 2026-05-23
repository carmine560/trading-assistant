"""Time-based action scheduling for active trading assistant sessions."""

import sched
import time

from app import action_errors, actions, listeners, notifications
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
SCHEDULED_ACTION_ERROR = "Scheduled action failed."


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
        schedules = _register_scheduled_actions(
            scheduler,
            config[trade.schedules_section],
            config[trade.actions_section],
            trade,
            config,
            gui_state,
        )
        _run_scheduler_until_empty(scheduler, schedules, process)
    finally:
        if should_stop_speaking_process:
            speech_synthesis.stop_speaking_process(
                base_manager, trade.speech_manager, trade.speaking_process
            )


def _register_scheduled_actions(
    scheduler,
    section,
    actions_section,
    trade,
    config,
    gui_state,
):
    """Register future configured actions and return their schedule handles."""
    schedules = []
    for option in section:
        trigger, action = evaluate_value(section[option])
        trigger = time.strptime(
            time.strftime("%Y-%m-%d ") + trigger,
            "%Y-%m-%d %H:%M:%S",
        )
        trigger = time.mktime(trigger)
        if time.time() >= trigger:
            continue

        try:
            scheduled_action = actions_section[action]
        except KeyError as e:
            raise action_errors.ActionLookupError(
                f"Action '{action}' is not defined.",
                action_name=action,
            ) from e

        is_blocking_schedule_action = _is_blocking_schedule_action(
            scheduled_action,
            actions_section,
            (action,),
        )
        schedule = scheduler.enterabs(
            trigger,
            1,
            _run_scheduled_action,
            argument=(
                trade,
                config,
                gui_state,
                action,
                scheduled_action,
                is_blocking_schedule_action,
            ),
            kwargs={},
        )
        schedules.append(schedule)
    return schedules


def _run_scheduler_until_empty(scheduler, schedules, process):
    """Run pending scheduled events while the target process is alive."""
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


def _run_scheduled_action(
    trade,
    config,
    gui_state,
    action_name,
    scheduled_action,
    is_blocking_schedule_action,
):
    """Run one scheduled action and report failures without stopping."""
    try:
        if not actions.execute_action(
            trade,
            config,
            gui_state,
            scheduled_action,
            should_initialize=is_blocking_schedule_action,
            should_acquire_lock=is_blocking_schedule_action,
            action_path=(action_name,),
        ):
            error = action_errors.ActionFailureError(
                f"Action '{action_name}' failed.",
                action_name=action_name,
            )
            previous_error = getattr(trade, "last_action_error", None)
            if previous_error is None:
                trade.last_action_error = error
            raise error from previous_error
    except Exception as e:
        trade.scheduler_error = e
        notifications.set_speech_text(trade, SCHEDULED_ACTION_ERROR)


def _is_blocking_schedule_action(action, actions_section, action_path):
    """Return True unless an action is confirmed as speech-only."""
    if isinstance(action, str):
        action = evaluate_value(action)

    for instruction_index, instruction in enumerate(action, start=1):
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
            _is_blocking_schedule_action(
                additional_argument,
                actions_section,
                (*action_path, f"inline@{instruction_index}"),
            )
        ):
            return True
        if isinstance(additional_argument, str):
            if additional_argument in action_path:
                raise action_errors.ActionExecutionError(
                    (
                        "Action path "
                        f"'{' -> '.join(action_path)}' failed at "
                        f"instruction {instruction_index} ({command}): "
                        f"nested action '{additional_argument}' creates "
                        "a cycle."
                    ),
                    action_path=action_path,
                    instruction_index=instruction_index,
                    command=command,
                )
            try:
                nested_action = actions_section[additional_argument]
            except KeyError as e:
                raise action_errors.ActionExecutionError(
                    (
                        "Action path "
                        f"'{' -> '.join(action_path)}' failed at "
                        f"instruction {instruction_index} ({command}): "
                        f"nested action '{additional_argument}' is not "
                        "defined."
                    ),
                    action_path=action_path,
                    instruction_index=instruction_index,
                    command=command,
                ) from e
            if _is_blocking_schedule_action(
                nested_action,
                actions_section,
                (*action_path, additional_argument),
            ):
                return True
    return False
