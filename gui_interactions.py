from threading import Thread
import re
import subprocess
import sys
import time

from pynput import keyboard
from pynput import mouse
import pyautogui
import win32gui

class GuiCallbacks:
    def __init__(self):
        self.enumerate_button = None
        self.enumerate_callback = None
        self.enumerate_extra = ''

    def enumerate_on_click(self, x, y, button, pressed):
        if button == self.enumerate_button:
            if not pressed:
                win32gui.EnumWindows(self.enumerate_callback,
                                     self.enumerate_extra)

def click_widget(place_trade, image, x, y, width, height):
    location = None
    x = int(x)
    y = int(y)
    width = int(width)
    height = int(height)
    while not location:
        location = pyautogui.locateOnScreen(image,
                                            region=(x, y, width, height))
        time.sleep(0.001)

    if place_trade.swapped:
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

# FIXME
def show_hide_window_on_click(gui_callbacks, process, title_regex,
                              enumerate_button=mouse.Button.middle,
                              enumerate_callback=show_hide_window):
    gui_callbacks.enumerate_button = enumerate_button
    gui_callbacks.enumerate_callback = enumerate_callback
    gui_callbacks.enumerate_extra = title_regex
    with mouse.Listener(on_click=gui_callbacks.enumerate_on_click) \
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

def wait_for_key(place_trade, key):
    if len(key) == 1:
        place_trade.key = key
    else:
        place_trade.key = keyboard.Key[key]
    with keyboard.Listener(on_release=place_trade.on_release) as listener:
        listener.join()
    if not place_trade.released:
        for _ in range(place_trade.moved_focus):
            pyautogui.hotkey('shift', 'tab')

        sys.exit()

def wait_for_window(place_trade, title_regex):
    while next((False for i in range(len(place_trade.exist))
                if place_trade.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(place_trade.check_for_window, title_regex)
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
