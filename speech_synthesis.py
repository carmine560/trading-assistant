"""Module for managing and controlling speech processes."""

from multiprocessing import Process
import time

import pyttsx3


class SpeechManager:
    """
    Manage the speech capabilities and text of a speech system.

    This class manages the speech capabilities and text of a speech
    system. It provides methods to get and set whether the system can
    speak and what text it should speak.

    Attributes:
        _can_speak (bool): A flag indicating whether the system can
            speak.
        _speech_text (str): The text that the system should speak.
    """

    def __init__(self):
        """
        Initialize a new SpeechManager instance.

        Initializes the speech capability to True and the speech text to
        an empty string.
        """
        self._can_speak = True
        self._speech_text = ''

    def can_speak(self):
        """
        Get the speech capability of the system.

        Returns:
            bool: True if the system can speak, False otherwise.
        """
        return self._can_speak

    def set_can_speak(self, can_speak):
        """
        Set the speech capability of the system.

        Args:
            can_speak (bool): The new speech capability.
        """
        self._can_speak = can_speak

    def get_speech_text(self):
        """
        Get the speech text of the system.

        Returns:
            str: The current speech text.
        """
        return self._speech_text

    def set_speech_text(self, text):
        """
        Set the speech text of the system.

        Args:
            text (str): The new speech text.
        """
        self._speech_text = text


def start_speaking_process(speech_manager):
    """
    Start a new process for speaking.

    This function creates and starts a new process that calls the
    start_speaking function with the provided speech manager as an
    argument.

    Args:
        speech_manager (SpeechManager): The speech manager to be used in
            the start_speaking function.

    Returns:
        Process: The started speaking process.
    """
    speaking_process = Process(target=start_speaking, args=(speech_manager,))
    speaking_process.start()
    return speaking_process


def start_speaking(speech_manager):
    """
    Initiate the speech process based on the speech manager's state.

    This function initializes a speech engine, sets its voice property,
    and continuously checks if the speech manager is allowed to speak.
    If it is, the function fetches the text from the speech manager,
    resets the speech text in the manager, and makes the speech engine
    say the text. The function runs until the speech manager is no
    longer allowed to speak.

    Args:
        speech_manager (SpeechManager): The speech manager controlling
            the speech process.
    """
    speech_engine = pyttsx3.init()
    voices = speech_engine.getProperty('voices')
    speech_engine.setProperty('voice', voices[1].id)

    while speech_manager.can_speak():
        text = speech_manager.get_speech_text()
        speech_manager.set_speech_text('')
        if text:
            speech_engine.say(text)
            speech_engine.runAndWait()

        time.sleep(0.01)


def stop_speaking_process(base_manager, speech_manager, speaking_process):
    """
    Stop the speaking process and shutdown the base manager.

    This function checks if there is any text left in the speech
    manager. If there is, it waits for a short period of time to allow
    the speaking process to finish. It then sets the speech manager to
    stop speaking, joins the speaking process, and shuts down the base
    manager.

    Args:
        base_manager (Manager): The base manager to shutdown.
        speech_manager (SpeechManager): The speech manager to stop
            speaking.
        speaking_process (Process): The speaking process to join.
    """
    if speech_manager.get_speech_text():
        time.sleep(0.01)

    speech_manager.set_can_speak(False)
    speaking_process.join()
    base_manager.shutdown()
