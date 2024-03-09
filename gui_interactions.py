import re
import time

import pyautogui
import win32api
import win32gui

class GuiState:
    def __init__(self, interactive_windows):
        self.interactive_windows = interactive_windows
        self.swapped = win32api.GetSystemMetrics(23)

        self.initialize_attributes()

    def is_interactive_window(self):
        foreground_window = win32gui.GetWindowText(
            win32gui.GetForegroundWindow())
        for title_regex in self.interactive_windows:
            if re.fullmatch(title_regex, foreground_window):
                return True
        return False

    def initialize_attributes(self):
        self.previous_position = pyautogui.position()
        self.moved_focus = 0

def click_widget(gui_state, image, x, y, width, height):
    location = None
    x = int(x)
    y = int(y)
    width = int(width)
    height = int(height)
    while not location:
        try:
            location = pyautogui.locateOnScreen(image,
                                                region=(x, y, width, height))
        except pyautogui.ImageNotFoundException:
            pass

        time.sleep(0.001)

    if gui_state.swapped:
        pyautogui.rightClick(pyautogui.center(location))
    else:
        pyautogui.click(pyautogui.center(location))

def enumerate_windows(callback, extra):
    try:
        win32gui.EnumWindows(callback, extra)
    except Exception as e:
        if e.args[0] in (0, 5):
            pass
        else:
            print(e)

def hide_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return False

def show_hide_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.ShowWindow(hwnd, 6)
        return False

def show_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        return False

def wait_for_window(title_regex):
    def check_for_window(hwnd, extra):
        if re.fullmatch(extra[0], win32gui.GetWindowText(hwnd)):
            extra[1] = False
            return False

    extra = [title_regex, True]
    while extra[1]:
        enumerate_windows(check_for_window, extra)
        time.sleep(0.001)
