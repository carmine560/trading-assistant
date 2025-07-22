"""Manage and control speech processes."""

from multiprocessing import Process
import time

import win32com.client


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


def start_speaking_process(speech_manager, voice_name=None, speech_rate=None):
    """Start a new process for speaking."""
    speaking_process = Process(
        target=start_speaking, args=(speech_manager, voice_name, speech_rate)
    )
    speaking_process.start()
    while not speech_manager.is_ready():
        time.sleep(0.01)
    return speaking_process


def start_speaking(speech_manager, voice_name, speech_rate):
    """Initiate the speech process based on the speech manager's state."""
    speech_engine = win32com.client.Dispatch("SAPI.SpVoice")

    voices_collection = speech_engine.GetVoices()
    selected_sapi_voice_token = None
    if voice_name:
        for i in range(voices_collection.Count):
            voice_token = voices_collection.Item(i)
            if voice_name.lower() in voice_token.GetDescription().lower():
                selected_sapi_voice_token = voice_token
                break
    if selected_sapi_voice_token:
        speech_engine.Voice = selected_sapi_voice_token
    elif voices_collection.Count > 0:
        speech_engine.Voice = voices_collection.Item(0)

    if speech_rate:
        speech_engine.Rate = max(-10, min(10, speech_rate))

    speech_manager.set_ready(True)
    while speech_manager.can_speak():
        text = speech_manager.get_speech_text()
        speech_manager.set_speech_text("")
        if text:
            speech_engine.Speak(text)

        time.sleep(0.01)


def stop_speaking_process(base_manager, speech_manager, speaking_process):
    """Stop the speaking process and shutdown the base manager."""
    if speech_manager.get_speech_text():
        time.sleep(0.01)

    speech_manager.set_can_speak(False)
    speaking_process.join()
    base_manager.shutdown()
