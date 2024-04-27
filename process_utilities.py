"""Module for managing and monitoring application processes and listeners."""

import re
import subprocess
import time


def is_running(process):
    """
    Determine if a process is currently running.

    This function checks if a specified process is currently running on
    the system by using the 'tasklist' command and searching its output.

    Args:
        process (str): The name of the process to check.

    Returns:
        bool: True if the process is running, False otherwise.
    """
    image = process + '.exe'
    output = subprocess.check_output(['tasklist', '/fi',
                                      'imagename eq ' + image])
    return bool(re.search(image, str(output)))


def wait_listeners(stop_listeners_event, process, mouse_listener,
                   keyboard_listener, base_manager, speech_manager,
                   speaking_process, is_persistent=False):
    """
    Wait for listeners until the stop event is set or process ends.

    This function continuously checks if a stop event is set or if a
    process is running. If the process is not running and the function
    is not set to be persistent, it stops the listeners and breaks the
    loop.

    Args:
        stop_listeners_event (Event): An event to signal stopping
            listeners.
        process (str): The name of the process to check.
        mouse_listener (Listener): The mouse listener to stop.
        keyboard_listener (Listener): The keyboard listener to stop.
        base_manager (Manager): The base manager to stop.
        speech_manager (Manager): The speech manager to stop.
        speaking_process (Process): The speaking process to stop.
        is_persistent (bool, optional): Whether to keep listeners
            running even if the process is not running. Defaults to
            False.
    """
    while not stop_listeners_event.is_set():
        if is_running(process) or is_persistent:
            time.sleep(1)
        else:
            stop_listeners(mouse_listener, keyboard_listener, base_manager,
                           speech_manager, speaking_process)
            break


def stop_listeners(mouse_listener, keyboard_listener, base_manager,
                   speech_manager, speaking_process):
    """
    Stop all listeners and shutdown the managers.

    This function stops the mouse and keyboard listeners if they exist.
    It also checks if the base manager, speech manager, and speaking
    process exist. If they do, it waits for any ongoing speech to
    finish, prevents further speaking, joins the speaking process, and
    shuts down the base manager.

    Args:
        mouse_listener (Listener): The mouse listener to stop.
        keyboard_listener (Listener): The keyboard listener to stop.
        base_manager (Manager): The base manager to shutdown.
        speech_manager (Manager): The speech manager to prevent further
            speaking.
        speaking_process (Process): The speaking process to join.
    """
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
