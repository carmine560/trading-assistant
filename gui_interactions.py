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
        self.moved_focus = 0

        # enumerate_windows_on_click
        self.callback = None
        self.extra = ''

        # compare_keys_on_release
        self.key = None
        self.released = False

        # check_for_window
        self.exist = []

        # TODO
        self.function_keys = (
            keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
            keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
            keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11,
            keyboard.Key.f12)
        self.is_function_key_pressed = False
        self.key_to_check = None

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

    def check_for_window(self, hwnd, title_regex):
        if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 9)

            win32gui.SetForegroundWindow(hwnd)
            self.exist.append((hwnd, title_regex))
            return

    # TODO
    def on_click(self, x, y, button, pressed):
        print('{0} at {1}'.format('Pressed' if pressed else 'Released', (x, y)))

    def on_press(self, key):
        if key in self.function_keys:
            if not self.is_function_key_pressed:
                self.is_function_key_pressed = True
                print('Function key pressed: {0}'.format(key))
        elif key == self.key_to_check:
            print('Key pressed: {0}'.format(key))
            self.key_to_check = None

    def on_release(self, key):
        if key in self.function_keys:
            self.is_function_key_pressed = False

# TODO
def start_monitors(gui_callbacks, is_running_function, process):
    # gui_callbacks = GuiCallbacks([])

    mouse_listener = mouse.Listener(on_click=gui_callbacks.on_click)
    mouse_listener.start()

    keyboard_listener = keyboard.Listener(on_press=gui_callbacks.on_press,
                                          on_release=gui_callbacks.on_release)
    keyboard_listener.start()

    # check_process_thread = threading.Thread(
    #     target=check_process,
    #     args=(process_utilities.is_running, 'i_view64', mouse_listener,
    #           keyboard_listener))
    check_process_thread = threading.Thread(
        target=check_process,
        args=(is_running_function, process, mouse_listener, keyboard_listener))
    check_process_thread.start()

    # time.sleep(5)
    # gui_callbacks.key_to_check = keyboard.Key.space
    # print(gui_callbacks.key_to_check)
    # time.sleep(5)
    # gui_callbacks.key_to_check = None
    # print(gui_callbacks.key_to_check)
    # time.sleep(5)
    # gui_callbacks.key_to_check = keyboard.Key.space
    # print(gui_callbacks.key_to_check)
    # time.sleep(5)
    # gui_callbacks.key_to_check = None
    # print(gui_callbacks.key_to_check)

    # mouse_listener.join()
    # keyboard_listener.join()
    # check_process_thread.join()

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

# TODO
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
        return

def wait_for_key(gui_callbacks, key):
    if len(key) == 1:
        gui_callbacks.key = key
    else:
        gui_callbacks.key = keyboard.Key[key]
    with keyboard.Listener(on_release=gui_callbacks.compare_keys_on_release) \
         as listener:
        listener.join()

    if gui_callbacks.released:
        return True
    else:
        for _ in range(gui_callbacks.moved_focus):
            pyautogui.hotkey('shift', 'tab')
        return False

def wait_for_window(gui_callbacks, title_regex):
    while next((False for i in range(len(gui_callbacks.exist))
                if gui_callbacks.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(gui_callbacks.check_for_window, title_regex)
        time.sleep(0.001)

# def check_process(is_running_function, process, listener):
#     while True:
#         if is_running_function(process):
#             time.sleep(1)
#         else:
#             listener.stop()
#             break

# TODO
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
