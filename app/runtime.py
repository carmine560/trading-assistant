"""Trading assistant runtime orchestration for actions and services."""

import atexit
import threading
from multiprocessing.managers import BaseManager

from app import actions, customer_margin_ratios, listeners, scheduler

from core_utilities import errors, process_utilities
from core_utilities.config_io import write_config
from interaction_utilities import speech_synthesis


def run(args, trade, config, gui_state):
    """Run the application."""
    atexit.register(persist_config_on_exit, trade, config)

    if args.r:
        customer_margin_ratios.save_customer_margin_ratios(trade, config)

    is_running = process_utilities.is_running(trade.process)
    base_manager = None
    if args.s or args.l or args.a:
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
        listeners.start_listeners(trade, config, gui_state, base_manager)
    if args.s and is_running:
        threading.Thread(
            target=scheduler.start_scheduler,
            args=(trade, config, gui_state, trade.process, base_manager),
        ).start()


def persist_config_on_exit(trade, config):
    """Persist configuration on interpreter shutdown."""
    # Ensure the config is written on normal interpreter shutdown, since
    # 'IndicatorThread.stop()' or 'IndicatorThread.on_closing()' may not run if
    # the main thread terminates abruptly.
    write_config(config, trade.config_path, is_encrypted=True)


def _start_speech_manager(trade):
    """Create and start the speech manager used by runtime workflows."""
    # Use 'BaseManager' to share 'SpeechManager' across processes.
    BaseManager.register("SpeechManager", speech_synthesis.SpeechManager)
    base_manager = BaseManager()
    base_manager.start()
    trade.speech_manager = base_manager.SpeechManager()
    return base_manager


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
    if should_start_transient_listeners:
        listeners.start_listeners(
            trade,
            config,
            gui_state,
            base_manager,
            is_persistent=True,
        )

    try:
        action_name = args.a[0]
        try:
            action = config[trade.actions_section][action_name]
        except KeyError as e:
            raise errors.ActionLookupError(
                f"Action '{action_name}' is not defined.",
                action_name=action_name,
            ) from e

        actions.execute_action(
            trade,
            config,
            gui_state,
            action,
            action_path=(action_name,),
        )
    finally:
        if should_start_transient_listeners:
            process_utilities.stop_listeners(
                trade.mouse_listener,
                trade.keyboard_listener,
                base_manager,
                trade.speech_manager,
                trade.speaking_process,
            )
            trade.stop_listeners_event.set()
            trade.wait_listeners_thread.join()
