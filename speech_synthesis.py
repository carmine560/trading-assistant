from multiprocessing import Process
import time

import pyttsx3

class SpeechManager:
    def __init__(self):
        self._can_speak = True
        self._speech_text = ''

    def can_speak(self):
        return self._can_speak

    def set_can_speak(self, can_speak):
        self._can_speak = can_speak

    def get_speech_text(self):
        return self._speech_text

    def set_speech_text(self, text):
        self._speech_text = text

def start_speaking_process(speech_manager):
    speaking_process = Process(target=start_speaking, args=(speech_manager,))
    speaking_process.start()
    return speaking_process

def start_speaking(speech_manager):
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
    if speech_manager.get_speech_text():
        time.sleep(0.01)

    speech_manager.set_can_speak(False)
    speaking_process.join()
    base_manager.shutdown()
