"""Trading assistant runtime orchestration for actions and services."""

import atexit
import threading
from multiprocessing.managers import BaseManager

from app import (
    action_errors,
    actions,
    customer_margin_ratios,
    listeners,
    notifications,
    scheduler,
)
from core_utilities import errors, process_utilities
from core_utilities.config_io import write_config
from interaction_utilities import speech_synthesis

LISTENER_WAIT_THREAD_JOIN_TIMEOUT_SECONDS = 5
RUN_SCHEDULER_ERROR = "Scheduler stopped."


def run(args, trade, config, gui_state):
    """Run the application."""
    atexit.register(persist_config_on_exit, trade, config)

    if args.r:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    is_running = process_utilities.is_running(trade.process)
    base_manager = None
    if args.a or ((args.s or args.l) and is_running):
        base_manager = _start_speech_manager(trade)

    if args.a:
        _execute_single_action(
            args,
            trade,
            config,
            gui_state,
            base_manager,
            is_running,
        )
    if args.l and is_running:
        try:
            listeners.start_listeners(trade, config, gui_state, base_manager)
        except Exception:
            speech_manager = getattr(trade, "speech_manager", None)
            speaking_process = getattr(trade, "speaking_process", None)
            stop_event = getattr(trade, "stop_listeners_event", None)
            wait_thread = getattr(trade, "wait_listeners_thread", None)
            try:
                process_utilities.stop_listeners(
                    getattr(trade, "mouse_listener", None),
                    getattr(trade, "keyboard_listener", None),
                    base_manager,
                    speech_manager,
                    speaking_process,
                )
            finally:
                if base_manager and speech_manager and not speaking_process:
                    base_manager.shutdown()
                if stop_event:
                    stop_event.set()
                if wait_thread:
                    wait_thread.join(
                        timeout=LISTENER_WAIT_THREAD_JOIN_TIMEOUT_SECONDS
                    )
                    if wait_thread.is_alive():
                        raise errors.ProcessStateError(
                            "Listener wait thread did not stop within "
                            f"{LISTENER_WAIT_THREAD_JOIN_TIMEOUT_SECONDS} "
                            "seconds."
                        )
            raise
    if args.s and is_running:

        def run_scheduler():
            try:
                scheduler.start_scheduler(
                    trade,
                    config,
                    gui_state,
                    trade.process,
                    base_manager,
                )
            except Exception as e:
                trade.scheduler_error = e
                if not notifications.set_speech_text(
                    trade,
                    RUN_SCHEDULER_ERROR,
                ):
                    print(f"Scheduler stopped: {e}")

        threading.Thread(
            target=run_scheduler,
        ).start()


def _execute_single_action(
    args,
    trade,
    config,
    gui_state,
    base_manager,
    is_running,
):
    """Execute a single configured action and manage transient listeners."""
    should_start_transient_listeners = not (is_running and args.l)
    try:
        if should_start_transient_listeners:
            listeners.start_listeners(
                trade,
                config,
                gui_state,
                base_manager,
                is_persistent=True,
            )

        action_name = args.a[0]
        try:
            action = config[trade.actions_section][action_name]
        except KeyError as e:
            raise action_errors.ActionLookupError(
                f"Action '{action_name}' is not defined.",
                action_name=action_name,
            ) from e

        if not actions.execute_action(
            trade,
            config,
            gui_state,
            action,
            action_path=(action_name,),
        ):
            if getattr(trade, "last_action_canceled", False):
                return
            error = action_errors.ActionFailureError(
                f"Action '{action_name}' failed.",
                action_name=action_name,
            )
            previous_error = getattr(trade, "last_action_error", None)
            if previous_error is None:
                trade.last_action_error = error
            raise error from previous_error
    finally:
        if should_start_transient_listeners:
            speech_manager = getattr(trade, "speech_manager", None)
            speaking_process = getattr(trade, "speaking_process", None)
            stop_event = getattr(trade, "stop_listeners_event", None)
            wait_thread = getattr(trade, "wait_listeners_thread", None)
            try:
                process_utilities.stop_listeners(
                    getattr(trade, "mouse_listener", None),
                    getattr(trade, "keyboard_listener", None),
                    base_manager,
                    speech_manager,
                    speaking_process,
                )
            finally:
                if base_manager and speech_manager and not speaking_process:
                    base_manager.shutdown()
                if stop_event:
                    stop_event.set()
                if wait_thread:
                    wait_thread.join(
                        timeout=LISTENER_WAIT_THREAD_JOIN_TIMEOUT_SECONDS
                    )
                    if wait_thread.is_alive():
                        raise errors.ProcessStateError(
                            "Listener wait thread did not stop within "
                            f"{LISTENER_WAIT_THREAD_JOIN_TIMEOUT_SECONDS} "
                            "seconds."
                        )


def _start_speech_manager(trade):
    """Create and start the speech manager used by runtime workflows."""
    # Use BaseManager to share SpeechManager across processes.
    BaseManager.register("SpeechManager", speech_synthesis.SpeechManager)
    base_manager = BaseManager()
    base_manager.start()
    trade.speech_manager = base_manager.SpeechManager()
    return base_manager


def persist_config_on_exit(trade, config):
    """Persist configuration on interpreter shutdown."""
    # Ensure the config is written on normal interpreter shutdown, since
    # IndicatorThread.stop() or IndicatorThread.on_closing() may not run if the
    # main thread terminates abruptly.
    write_config(config, trade.config_path, is_encrypted=True)
