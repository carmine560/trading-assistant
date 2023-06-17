import re
import sys
import threading
import time

from pynput import keyboard
from pynput import mouse
import pyautogui
import win32api
import win32gui

class GuiCallbacks:
    def __init__(self, interactive_windows):
        self.interactive_windows = interactive_windows
        self.swapped = win32api.GetSystemMetrics(23)
        self.previous_position = pyautogui.position()
        self.moved_focus = 0

        # enumerate_windows_on_click
        self.callback = None
        self.extra = ''

        # compare_keys_on_release
        self.key = None
        self.released = False

        # check_for_window
        self.exist = []

    def initialize_attributes(self):
        self.previous_position = pyautogui.position()
        self.moved_focus = 0

    def enumerate_windows_on_click(self, x, y, button, pressed):
        if button == mouse.Button.middle and not pressed:
            if self.is_interactive_window():
                win32gui.EnumWindows(self.callback, self.extra)

    def compare_keys_on_release(self, key):
        if hasattr(key, 'char') and key.char == self.key:
            if self.is_interactive_window():
                self.released = True
                return False
        elif key == self.key:
            if self.is_interactive_window():
                self.released = True
                return False
        elif key == keyboard.Key.esc:
            if self.is_interactive_window():
                return False

    def is_interactive_window(self):
        foreground_window = \
            win32gui.GetWindowText(win32gui.GetForegroundWindow())
        for title_regex in self.interactive_windows:
            if re.fullmatch(title_regex, foreground_window):
                return True
        return False

    def check_for_window(self, hwnd, title_regex):
        if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
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
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        parent = win32gui.GetParent(hwnd)
        if parent and not win32gui.IsIconic(parent):
            win32gui.ShowWindow(parent, 6)
            return

def hide_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return

def show_hide_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.ShowWindow(hwnd, 6)
        return

# TODO: Trade.mouse_listener
def show_hide_window_on_click(gui_callbacks, process, title_regex,
                              is_running_function, callback=show_hide_window):
    gui_callbacks.callback = callback
    gui_callbacks.extra = title_regex
    with mouse.Listener(on_click=gui_callbacks.enumerate_windows_on_click) \
         as listener:
        thread = threading.Thread(
            target=check_process,
            args=(is_running_function, process, listener, None))
        thread.start()
        listener.join()

def show_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        return False

def wait_for_window(gui_callbacks, title_regex):
    while next((False for i in range(len(gui_callbacks.exist))
                if gui_callbacks.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(gui_callbacks.check_for_window, title_regex)
        time.sleep(0.001)

# TODO: remove
def check_process(is_running_function, process, mouse_listener,
                  keyboard_listener):
    while True:
        if is_running_function(process):
            time.sleep(1)
        else:
            if mouse_listener:
                mouse_listener.stop()
            if keyboard_listener:
                keyboard_listener.stop()
            break
