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

def initialize_speech_engine():
    import pyttsx3

    speech_engine = pyttsx3.init()
    voices = speech_engine.getProperty('voices')
    speech_engine.setProperty('voice', voices[1].id)
    return speech_engine

def speak_directly(speech_engine, text):
    if not speech_engine:
        speech_engine = initialize_speech_engine()

    speech_engine.say(text)
    speech_engine.runAndWait()

def start_speaking(speech_manager):
    import time

    speech_engine = initialize_speech_engine()

    while speech_manager.can_speak():
        text = speech_manager.get_speech_text()
        if text:
            print(f'speak_text: {text}')
            speech_engine.say(text)
            speech_engine.runAndWait()
            speech_manager.set_speech_text('')

        time.sleep(0.01)
