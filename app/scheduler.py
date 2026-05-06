"""Scheduler helpers extracted from the main entrypoint."""

import sched
import time


def start_scheduler(trade, config, gui_state, process, base_manager, deps):
    """Start a scheduler for executing actions at specified times."""
    configuration = deps["configuration"]
    process_utilities = deps["process_utilities"]
    speech_synthesis = deps["speech_synthesis"]

    should_stop_speaking_process = False
    if not trade.speaking_process:
        trade.speaking_process = deps["start_speaking_process_fn"](
            trade, config
        )
        should_stop_speaking_process = True

    scheduler = sched.scheduler(time.time, time.sleep)
    schedules = []

    section = config[trade.schedules_section]
    for option in section:
        trigger, action = configuration.evaluate_value(section[option])
        trigger = time.strptime(
            time.strftime("%Y-%m-%d ") + trigger, "%Y-%m-%d %H:%M:%S"
        )
        trigger = time.mktime(trigger)
        if time.time() < trigger:
            schedule = scheduler.enterabs(
                trigger,
                1,
                deps["execute_action_fn"],
                argument=(
                    trade,
                    config,
                    gui_state,
                    config[trade.actions_section][action],
                ),
            )
            schedules.append(schedule)

    try:
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
