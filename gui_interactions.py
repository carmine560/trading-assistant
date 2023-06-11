from threading import Thread
import re
import sys
import time

from pynput import keyboard
from pynput import mouse
import pyautogui
import win32api
import win32gui

class GuiCallbacks:
    """A class to handle GUI callbacks.

    Attributes:
        interactive_windows : list of regular expressions to match
        window titles
        swapped : system metric for swapped mouse buttons
        moved_focus : flag to indicate if focus has moved

    Methods:
        enumerate_windows_on_click : callback function to enumerate
        windows on mouse click
        compare_keys_on_release : callback function to compare keys on
        key release
        is_interactive_window : check if the current window is
        interactive
        check_for_window : check if a window exists based on its title
        regex"""
    def __init__(self, interactive_windows):
        """Initialize the class with the given parameters.

        Args:
            interactive_windows : a list of interactive windows

        Attributes:
            interactive_windows : a list of interactive windows
            swapped : the swapped value
            moved_focus : the moved focus value
            callback : a function to be called when a window is clicked
            extra : extra information to be passed to the callback
            function
            key : the key to be compared when released
            released : a boolean value indicating whether the key has
            been released
            exist : a list of existing windows"""
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

    def enumerate_windows_on_click(self, x, y, button, pressed):
        """Enumerate windows on mouse click.

        Args:
            x : x-coordinate of the mouse click
            y : y-coordinate of the mouse click
            button : mouse button clicked
            pressed : whether the button was pressed or released

        Returns:
            None"""
        if button == mouse.Button.middle and not pressed:
            if self.is_interactive_window():
                win32gui.EnumWindows(self.callback, self.extra)

    def compare_keys_on_release(self, key):
        """Compare keys on release.

        Args:
            key: The key to compare with.

        Returns:
            False if the key is the same as the stored key and the key
            has been released. Otherwise, returns True.

        Raises:
            None."""
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
        """Check if the current window is an interactive window.

        Args:
            self: An instance of the class

        Returns:
            True if the current window is an interactive window, False
            otherwise."""
        foreground_window = \
            win32gui.GetWindowText(win32gui.GetForegroundWindow())
        for title_regex in self.interactive_windows:
            if re.fullmatch(title_regex, foreground_window):
                return True

    def check_for_window(self, hwnd, title_regex):
        """Check if a window with a given title regex exists.

        Args:
            hwnd : handle to the window
            title_regex : regular expression to match the title of the
            window

        Returns:
            None

        Raises:
            None"""
        if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 9)

            win32gui.SetForegroundWindow(hwnd)
            self.exist.append((hwnd, title_regex))
            return

def click_widget(gui_callbacks, image, x, y, width, height):
    """Click a widget on the screen.

    Args:
        gui_callbacks: An object containing GUI callbacks.
        image: The image of the widget to be clicked.
        x: The x coordinate of the region where the widget is located.
        y: The y coordinate of the region where the widget is located.
        width: The width of the region where the widget is located.
        height: The height of the region where the widget is located.

    Returns:
        None

    Raises:
        None"""
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
    """Hides the parent window of a given window handle if the title
    matches the given regular expression.

    Args:
        hwnd : int
            Window handle of the child window
        title_regex : str
            Regular expression to match the title of the parent window

    Returns:
        None"""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        parent = win32gui.GetParent(hwnd)
        if parent and not win32gui.IsIconic(parent):
            win32gui.ShowWindow(parent, 6)
            return

def hide_window(hwnd, title_regex):
    """Hide a window based on its handle and title regex.

    Args:
        hwnd : handle of the window to hide
        title_regex : regular expression to match the title of the
        window

    Returns:
        None"""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if not win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 6)
        return

def show_hide_window(hwnd, title_regex):
    """Show or hide a window based on the window title regex.

    Args:
        hwnd: Window handle
        title_regex: Regular expression to match the window title

    Returns:
        None"""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.ShowWindow(hwnd, 6)
        return

def show_hide_window_on_click(gui_callbacks, process, title_regex,
                              is_running_function, callback=show_hide_window):
    """Show or hide a window on mouse click.

    Args:
        gui_callbacks: A callback function to be called on mouse click
        process: A process to be checked
        title_regex: A regular expression to match the title of the
        window
        is_running_function: A function to check if the process is
        running
        callback: A function to be called on mouse click. Default is
        show_hide_window.

    Returns:
        None."""
    gui_callbacks.callback = callback
    gui_callbacks.extra = title_regex
    with mouse.Listener(on_click=gui_callbacks.enumerate_windows_on_click) \
         as listener:
        thread = Thread(target=check_process,
                        args=(is_running_function, process, listener))
        thread.start()
        listener.join()

def show_window(hwnd, title_regex):
    """Show a window with the given title regex.

    Args:
        hwnd : handle to the window
        title_regex : regular expression to match the title of the
        window

    Returns:
        None"""
    if re.fullmatch(title_regex, win32gui.GetWindowText(hwnd)):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)
        return

def wait_for_key(gui_callbacks, key):
    """Waits for a specific key to be pressed.

    Args:
        gui_callbacks: An object containing the callbacks to be executed
        when the key is pressed.
        key: The key to be pressed.

    Returns:
        True if the key was pressed, False otherwise."""
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
    """Wait for a window with a given title regex.

    Args:
        gui_callbacks: GUI callbacks object
        title_regex: Regular expression to match the title of the window

    Returns:
        None"""
    while next((False for i in range(len(gui_callbacks.exist))
                if gui_callbacks.exist[i][1] == title_regex), True):
        win32gui.EnumWindows(gui_callbacks.check_for_window, title_regex)
        time.sleep(0.001)

def check_process(is_running_function, process, listener):
    """Check if a process is running.

    Args:
        is_running_function: A function that returns True if the process
        is running, False otherwise.
        process: The process to check.
        listener: An object that listens to the process.

    Returns:
        None."""
    while True:
        if is_running_function(process):
            time.sleep(1)
        else:
            listener.stop()
            break
