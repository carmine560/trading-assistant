def is_running(process):
    import re
    import subprocess

    image = process + '.exe'
    output = subprocess.check_output(['tasklist', '/fi',
                                      'imagename eq ' + image])
    if re.search(image, str(output)):
        return True
    else:
        return False

def stop_listeners(process, mouse_listener, keyboard_listener, manager,
                   speech_manager, speak_text_process):
    import time

    while True:
        if is_running(process):
            time.sleep(1)
        else:
            if mouse_listener:
                mouse_listener.stop()
            if keyboard_listener:
                keyboard_listener.stop()
            if manager and speech_manager and speak_text_process:
                # TODO
                speech_manager.set_can_speak(False)
                speak_text_process.join()
                manager.shutdown()
            break
