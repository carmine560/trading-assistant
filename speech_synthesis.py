"""Manage and control speech processes."""

from multiprocessing import Process
import time

import pyttsx3


class SpeechManager:
    """Manage the speech capabilities and text of a speech system."""

    def __init__(self):
        """Initialize a new SpeechManager instance."""
        self._is_ready = False
        self._can_speak = True
        self._speech_text = ""

    def is_ready(self):
        """Get whether the speech system is initialized and ready."""
        return self._is_ready

    def set_ready(self, value):
        """Set whether the speech system is initialized and ready."""
        self._is_ready = value

    def can_speak(self):
        """Get the speech capability of the system."""
        return self._can_speak

    def set_can_speak(self, can_speak):
        """Set the speech capability of the system."""
        self._can_speak = can_speak

    def get_speech_text(self):
        """Get the speech text of the system."""
        return self._speech_text

    def set_speech_text(self, text):
        """Set the speech text of the system."""
        self._speech_text = text


def start_speaking_process(speech_manager, voice_name=None):
    """Start a new process for speaking."""
    speaking_process = Process(
        target=start_speaking, args=(speech_manager, voice_name)
    )
    speaking_process.start()
    while not speech_manager.is_ready():
        time.sleep(0.01)
    return speaking_process


def start_speaking(speech_manager, voice_name):
    """Initiate the speech process based on the speech manager's state."""
    speech_engine = pyttsx3.init()
    voices = speech_engine.getProperty("voices")
    selected_voice = next(
        (
            voice.id
            for voice in voices
            if voice_name and voice_name in voice.name
        ),
        voices[0].id,
    )
    speech_engine.setProperty("voice", selected_voice)
    speech_manager.set_ready(True)

    while speech_manager.can_speak():
        text = speech_manager.get_speech_text()
        speech_manager.set_speech_text("")
        if text:
            speech_engine.say(text)
            speech_engine.runAndWait()

        time.sleep(0.01)


def stop_speaking_process(base_manager, speech_manager, speaking_process):
    """Stop the speaking process and shutdown the base manager."""
    if speech_manager.get_speech_text():
        time.sleep(0.01)

    speech_manager.set_can_speak(False)
    speaking_process.join()
    base_manager.shutdown()
