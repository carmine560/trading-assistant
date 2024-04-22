"""Module for managing GUI state and interactions."""

import re
import time

import pyautogui
import pywintypes
import win32api
import win32gui


class GuiState:
    """
    Manage the state of the Graphical User Interface (GUI).

    This class manages the state of the GUI, including the interactive windows,
    the swapped state, the previous position of the GUI, and the moved focus.

    Attributes:
        interactive_windows (list): A list of regular expressions representing
            the titles of the interactive windows.
        swapped (int): The swapped state of the GUI, obtained from the system
            metrics.
        previous_position (tuple): The previous mouse pointer position.
        moved_focus (int): The moved focus of the GUI.
    """

    def __init__(self, interactive_windows):
        """
        Initialize a new GuiState instance.

        Args:
            interactive_windows (list): A list of regular expressions
                representing the titles of the interactive windows.
        """
        self.interactive_windows = interactive_windows
        self.swapped = win32api.GetSystemMetrics(23)

        self.initialize_attributes()

    def is_interactive_window(self):
        """
        Check if the foreground window is an interactive window.

        Returns:
            bool: True if the foreground window is an interactive window,
                False otherwise.
        """
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
    """
    Locate an image on the screen and perform a click action.

    This function tries to locate a given image within a specified region on
    the screen. Once the image is located, it performs a click action at the
    center of the image. If the GUI state is swapped, it performs a
    right-click; otherwise, it performs a left-click.

    Args:
        gui_state (GuiState): The state of the GUI.
        image (str): The path to the image file to locate on the screen.
        x (int): The x-coordinate of the top left corner of the search region.
        y (int): The y-coordinate of the top left corner of the search region.
        width (int): The width of the search region.
        height (int): The height of the search region.

    Returns:
        None
    """
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
    """
    Enumerate all open windows and apply a callback function.

    This function enumerates all open windows and applies a callback function
    to each one. If an error occurs during the enumeration, it prints the error
    unless the error code is 0 or 5, in which case it silently passes.

    Args:
        callback (function): The callback function to apply to each window.
        extra (any): Extra data to pass to the callback function.

    Returns:
        None
    """
    try:
        win32gui.EnumWindows(callback, extra)
    except pywintypes.error as e:
        if e.args[0] in (0, 5):
            pass
        else:
            print(e)


def hide_window(hwnd, title_regex):
    """
    Hide a window if its title matches a regular expression.

    This function checks if the title of a window matches a given regular
    expression. If it does and the window is not already minimized (iconic),
    the function hides the window. If the title does not match, or if the
    window is already minimized, the function does nothing.

    Args:
        hwnd (int): The handle of the window to hide.
        title_regex (str): The regular expression to match against the window
            title.

    Returns:
        bool: False if the window was hidden, True otherwise.
    """
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return False
    return True


def show_hide_window(hwnd, title_regex):
    """
    Show or hide a window based on its current state and title.

    This function checks if the title of a window matches a given regular
    expression. If it does, the function checks if the window is minimized
    (iconic). If it is, the function shows the window and sets it as the
    foreground window. If it's not, the function hides the window.

    Args:
        hwnd (int): The handle of the window to show or hide.
        title_regex (str): The regular expression to match against the window
            title.

    Returns:
        bool: False if the window was shown or hidden, True otherwise.
    """
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.ShowWindow(hwnd, 6)
        return False
    return True


def show_window(hwnd, title_regex):
    """
    Show a window if its title matches a regular expression.

    This function checks if the title of a window matches a given regular
    expression. If it does, the function checks if the window is minimized
    (iconic). If it is, the function shows the window and sets it as the
    foreground window.

    Args:
        hwnd (int): The handle of the window to show.
        title_regex (str): The regular expression to match against the window
            title.

    Returns:
        bool: False if the window was shown, True otherwise.
    """
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        return False
    return True


def wait_for_window(title_regex):
    """
    Wait until a window with a title matching a regular expression appears.

    This function continuously enumerates all open windows and checks if any
    of them have a title that matches a given regular expression. The function
    waits until such a window is found.

    Args:
        title_regex (str): The regular expression to match against the window
            title.

    Returns:
        None
    """
    def check_for_window(hwnd, extra):
        """
        Check if a window's title matches a regular expression.

        This function checks if the title of a window matches a given regular
        expression. If it does, it sets a flag in the extra parameter to False.

        Args:
            hwnd (int): The handle of the window to check.
            extra (list): A list where the first element is the regular
                expression to match against the window title, and the second
                element is a flag that is set to False if a match is found.

        Returns:
            bool: False if a match is found, True otherwise.
        """
        if re.fullmatch(extra[0], win32gui.GetWindowText(hwnd)):
            extra[1] = False
            return False
        return True

    extra = [title_regex, True]
    while extra[1]:
        enumerate_windows(check_for_window, extra)
        time.sleep(0.001)
