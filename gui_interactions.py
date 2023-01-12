from threading import Thread
import re
import subprocess
import sys
import time

from pynput import keyboard
from pynput import mouse
import pyautogui
import win32api
import win32gui

class GuiCallbacks:
    def __init__(self):
        self.swapped = win32api.GetSystemMetrics(23)
        self.moved_focus = 0

        # enumerate_windows_on_click
        self.callback = None
        self.extra = ''

        # compare_keys_on_release
        self.key = None
        self.released = False

        # check_for_window
        self.exist = []

    def enumerate_windows_on_click(self, x, y, button, pressed):
        if button == mouse.Button.middle:
            if not pressed:
                win32gui.EnumWindows(self.callback,
                                     self.extra)

    def compare_keys_on_release(self, key):
        if hasattr(key, 'char') and key.char == self.key:
            self.released = True
            return False
        elif key == self.key:
            self.released = True
            return False
        elif key == keyboard.Key.esc:
            return False

    def check_for_window(self, hwnd, title_regex):
        if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 9)

            win32gui.SetForegroundWindow(hwnd)
            self.exist.append((hwnd, title_regex))
            return

def click_widget(gui_callbacks, image, x, y, width, height):
    location = None
    x = int(x)
    y = int(y)
    width = int(width)
    height = int(height)
    while not location:
        location = pyautogui.locateOnScreen(image,
                                            region=(x, y, width, height))
        time.sleep(0.001)

    if gui_callbacks.swapped:
        pyautogui.rightClick(pyautogui.center(location))
    else:
        pyautogui.click(pyautogui.center(location))

def hide_parent_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        parent = win32gui.GetParent(hwnd)
        if parent and not win32gui.IsIconic(parent):
            win32gui.ShowWindow(parent, 6)
            return

def hide_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return

def show_hide_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)
            # pywintypes.error: (5, 'SetForegroundWindow', 'Access is denied.')
            win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.ShowWindow(hwnd, 6)
        return

def show_hide_window_on_click(gui_callbacks, process, title_regex,
                              callback=show_hide_window):
    gui_callbacks.callback = callback
    gui_callbacks.extra = title_regex
    with mouse.Listener(on_click=gui_callbacks.enumerate_windows_on_click) \
         as listener:
        thread = Thread(target=check_process, args=(process, listener))
        thread.start()
        listener.join()

def show_window(hwnd, title_regex):
    if re.search(title_regex, str(win32gui.GetWindowText(hwnd))):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        return

def wait_for_key(gui_callbacks, key):
    if len(key) == 1:
        gui_callbacks.key = key
    else:
        gui_callbacks.key = keyboard.Key[key]
    with keyboard.Listener(on_release=gui_callbacks.compare_keys_on_release) \
         as listener:
        listener.join()
    if not gui_callbacks.released:
        for _ in range(gui_callbacks.moved_focus):
            pyautogui.hotkey('shift', 'tab')

        sys.exit()

def wait_for_window(gui_callbacks, title_regex):
    while next((False for i in range(len(gui_callbacks.exist))
                if gui_callbacks.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(gui_callbacks.check_for_window, title_regex)
        time.sleep(0.001)

def check_process(process, listener):
    while True:
        output = subprocess.check_output(['tasklist', '/fi',
                                          'imagename eq ' + process])
        if re.search(process, str(output)):
            time.sleep(1)
        else:
            listener.stop()
            break
