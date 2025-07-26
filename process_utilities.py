"""Manage and monitor application processes and listeners."""

import re
import subprocess
import time


def is_running(process):
    """Determine if a process is currently running."""
    image = process + ".exe"
    output = subprocess.check_output(
        ["tasklist", "/fi", "imagename eq " + image]
    )
    return bool(re.search(image, str(output)))


def wait_listeners(
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
    """Wait for listeners until the stop event is set or process ends."""
    while not stop_listeners_event.is_set():
        if is_running(process) or is_persistent:
            time.sleep(1)
        else:
            stop_listeners(
                mouse_listener,
                keyboard_listener,
                base_manager,
                speech_manager,
                speaking_process,
                indicator_thread=indicator_thread,
            )
            break


def stop_listeners(
    mouse_listener,
    keyboard_listener,
    base_manager,
    speech_manager,
    speaking_process,
    indicator_thread=None,
):
    """Stop all listeners and shutdown the managers."""
    if mouse_listener:
        mouse_listener.stop()
    if keyboard_listener:
        keyboard_listener.stop()
    if base_manager and speech_manager and speaking_process:
        if speech_manager.get_speech_text():
            time.sleep(0.01)

        speech_manager.set_can_speak(False)
        speaking_process.join()
        base_manager.shutdown()
    if indicator_thread:
        indicator_thread.stop()
