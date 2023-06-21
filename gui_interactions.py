import re
import sys
import threading
import time

import pyautogui
import win32api
import win32gui

class GuiCallbacks:
    def __init__(self, interactive_windows):
        self.interactive_windows = interactive_windows
        self.swapped = win32api.GetSystemMetrics(23)
        self.previous_position = pyautogui.position()
        self.moved_focus = 0

        # check_for_window
        self.exist = []

    def initialize_attributes(self):
        self.previous_position = pyautogui.position()
        self.moved_focus = 0

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

def show_window(hwnd, title_regex):
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        return False

def take_screenshot(output):
    from ctypes import wintypes
    import ctypes
    import mss

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    rect = wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), wintypes.DWORD(9),
        ctypes.byref(rect), ctypes.sizeof(rect))

    with mss.mss() as screenshot:
        image = screenshot.grab((rect.left, rect.top, rect.right, rect.bottom))
        mss.tools.to_png(image.rgb, image.size, output=output)

def wait_for_window(gui_callbacks, title_regex):
    while next((False for i in range(len(gui_callbacks.exist))
                if gui_callbacks.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(gui_callbacks.check_for_window, title_regex)
        time.sleep(0.001)
