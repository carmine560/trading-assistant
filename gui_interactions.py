"""Manage GUI state and handle interactions."""

import re
import time

import pyautogui
import pywintypes
import win32api
import win32gui


class GuiState:
    """Manage the state of the Graphical User Interface."""

    def __init__(self, interactive_windows):
        """Initialize a new GuiState instance."""
        self.interactive_windows = interactive_windows
        self.swapped = win32api.GetSystemMetrics(23)

        self.initialize_attributes()

    def is_interactive_window(self):
        """Check if the foreground window is an interactive window."""
        foreground_window = win32gui.GetWindowText(
            win32gui.GetForegroundWindow())
        for title_regex in self.interactive_windows:
            if re.fullmatch(title_regex, foreground_window):
                return True
        return False

    def initialize_attributes(self):
        """Initialize the previous position and moved focus of the GUI."""
        self.previous_position = pyautogui.position()
        self.moved_focus = 0


def click_widget(gui_state, image, x, y, width, height):
    """Locate an image on the screen and perform a click action."""
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
    """Enumerate all open windows and apply a callback function."""
    try:
        win32gui.EnumWindows(callback, extra)
    except pywintypes.error as e:
        if e.args[0] in (0, 5):
            pass
        else:
            print(e)


def hide_window(hwnd, title_regex):
    """Hide a window if its title matches a regular expression."""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return False
    return True


def show_hide_window(hwnd, title_regex):
    """Show or hide a window based on its current state and title."""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.ShowWindow(hwnd, 6)
        return False
    return True


def show_window(hwnd, title_regex):
    """Show a window if its title matches a regular expression."""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        # Allow the OS to process the window focus and redraw.
        time.sleep(0.06)
        # return False            # TODO: Add max_count
    return True


def wait_for_window(title_regex):
    """Wait for a window with a title matching a regular expression."""
    def check_for_window(hwnd, extra):
        """Check if a window's title matches a regular expression."""
        if re.fullmatch(extra[0], win32gui.GetWindowText(hwnd)):
            extra[1] = False
            return False
        return True

    extra = [title_regex, True]
    while extra[1]:
        enumerate_windows(check_for_window, extra)
        time.sleep(0.001)
