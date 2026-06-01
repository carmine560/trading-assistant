"""Mouse, keyboard, and speech listener startup helpers."""

import threading

from pynput import keyboard, mouse

from app import notifications
from core_utilities import errors, process_utilities
from core_utilities.config_common import ConfigError
from core_utilities.config_validation import evaluate_value
from interaction_utilities import speech_synthesis

LISTENER_MONITOR_ERROR = "Listener monitor failed."
LISTENER_STOP_REASON_PROCESS_EXITED = "process_exited"


def start_listeners(
    trade,
    config,
    gui_state,
    base_manager,
    is_persistent=False,
):
    """Initiate listeners for mouse and keyboard events."""
    input_map = evaluate_value(config[trade.process]["input_map"])
    if not isinstance(input_map, dict):
        raise ConfigError(
            f"{trade.process}.input_map must be "
            "a mapping of inputs to actions."
        )
    supported_input_names = {
        "left",
        "middle",
        "right",
        "x1",
        "x2",
        *(f"f{number}" for number in range(1, 13)),
    }
    for input_name, action_name in input_map.items():
        if input_name not in supported_input_names:
            raise ConfigError(
                (
                    f"{trade.process}.input_map[{input_name!r}] is not "
                    "a supported input."
                )
            )
        if not action_name:
            continue
        if not isinstance(action_name, str):
            raise ConfigError(
                (
                    f"{trade.process}.input_map[{input_name!r}] must be "
                    "an action name."
                )
            )
        if action_name not in config[trade.actions_section]:
            raise ConfigError(
                (
                    f"{trade.process}.input_map[{input_name!r}] references "
                    f"undefined action '{action_name}'."
                )
            )

    try:
        trade.listener_stop_reason = None
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
    except Exception as startup_error:
        stop_listeners_event = getattr(trade, "stop_listeners_event", None)
        if stop_listeners_event:
            stop_listeners_event.set()
        speaking_process = getattr(trade, "speaking_process", None)
        try:
            process_utilities.stop_listeners(
                getattr(trade, "mouse_listener", None),
                getattr(trade, "keyboard_listener", None),
                base_manager,
                getattr(trade, "speech_manager", None),
                speaking_process,
                indicator_thread=getattr(trade, "indicator_thread", None),
            )
        except Exception as cleanup_error:
            raise startup_error from cleanup_error
        finally:
            trade.mouse_listener = None
            trade.keyboard_listener = None
            trade.speaking_process = None
            if speaking_process:
                trade.speech_manager = None
            trade.stop_listeners_event = None
            trade.wait_listeners_thread = None
        raise


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
            on_process_exit=(
                lambda: setattr(
                    trade,
                    "listener_stop_reason",
                    LISTENER_STOP_REASON_PROCESS_EXITED,
                )
            ),
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


def raise_listener_monitor_error(trade):
    """Raise if the listener monitor stopped with an error."""
    listener_error = getattr(trade, "last_listener_error", None)
    if listener_error is not None:
        raise errors.ProcessStateError(
            LISTENER_MONITOR_ERROR
        ) from listener_error


def start_speaking_process(trade, config):
    """Start a speaking process using the configured voice settings."""
    return speech_synthesis.start_speaking_process(
        trade.speech_manager,
        voice_name=config["General"]["voice_name"],
        speech_rate=int(config["General"]["speech_rate"]),
    )
