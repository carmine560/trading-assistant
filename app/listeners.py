"""Mouse, keyboard, and speech listener startup helpers."""

import threading

from pynput import keyboard, mouse

from app import notifications
from core_utilities import process_utilities
from interaction_utilities import speech_synthesis

LISTENER_MONITOR_ERROR = "Listener monitor failed."


def start_listeners(
    trade,
    config,
    gui_state,
    base_manager,
    is_persistent=False,
):
    """Initiate listeners for mouse and keyboard events."""
    trade.mouse_listener = mouse.Listener(
        on_click=lambda x, y, button, pressed: trade.on_click(
            x, y, button, pressed, config, gui_state
        )
    )
    trade.mouse_listener.start()

    trade.keyboard_listener = keyboard.Listener(
        on_press=lambda key: trade.on_press(key, config, gui_state),
        on_release=lambda key: trade.on_release(key, gui_state),
    )
    trade.keyboard_listener.start()

    trade.speaking_process = start_speaking_process(trade, config)

    trade.stop_listeners_event = threading.Event()
    trade.last_listener_error = None
    trade.wait_listeners_thread = threading.Thread(
        target=_wait_listeners,
        args=(
            trade,
            trade.stop_listeners_event,
            trade.process,
            trade.mouse_listener,
            trade.keyboard_listener,
            base_manager,
            trade.speech_manager,
            trade.speaking_process,
        ),
        kwargs={
            "indicator_thread": trade.indicator_thread,
            "is_persistent": is_persistent,
        },
    )
    trade.wait_listeners_thread.start()


def _wait_listeners(
    trade,
    stop_listeners_event,
    process,
    mouse_listener,
    keyboard_listener,
    base_manager,
    speech_manager,
    speaking_process,
    indicator_thread=None,
    is_persistent=False,
):
    """Wait for listeners and record monitor-thread failures."""
    try:
        process_utilities.wait_listeners(
            stop_listeners_event,
            process,
            mouse_listener,
            keyboard_listener,
            base_manager,
            speech_manager,
            speaking_process,
            indicator_thread=indicator_thread,
            is_persistent=is_persistent,
        )
    except Exception as e:
        trade.last_listener_error = e
        try:
            notified = notifications.set_speech_text(
                trade, LISTENER_MONITOR_ERROR
            )
        except Exception:
            notified = False
        if not notified:
            print(f"{LISTENER_MONITOR_ERROR} {e}")


def start_speaking_process(trade, config):
    """Start a speaking process using the configured voice settings."""
    return speech_synthesis.start_speaking_process(
        trade.speech_manager,
        voice_name=config["General"]["voice_name"],
        speech_rate=int(config["General"]["speech_rate"]),
    )
