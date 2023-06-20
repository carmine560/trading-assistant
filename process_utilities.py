import re
import subprocess
import time

def is_running(process):
    image = process + '.exe'
    output = subprocess.check_output(['tasklist', '/fi',
                                      'imagename eq ' + image])
    if re.search(image, str(output)):
        return True
    else:
        return False

def wait_listeners(stop_listeners_event, process, mouse_listener,
                   keyboard_listener, base_manager, speech_manager,
                   speaking_process, is_persistent=False):
    while not stop_listeners_event.is_set():
        if is_running(process) or is_persistent:
            time.sleep(1)
        else:
            stop_listeners(mouse_listener, keyboard_listener, base_manager,
                           speech_manager, speaking_process)
            break

def stop_listeners(mouse_listener, keyboard_listener, base_manager,
                   speech_manager, speaking_process):
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
