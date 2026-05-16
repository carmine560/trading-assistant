"""Indicator and message window rendering for trading state."""

import threading
import time
import tkinter as tk
from tkinter import TclError

from win32api import GetMonitorInfo, MonitorFromPoint

from core_utilities.errors import WidgetPositionError

RATIO_EPSILON = 1e-4


class IndicatorThread(threading.Thread):
    """Handle a thread for displaying trading indicators."""

    def __init__(self, trade, config):
        """Construct a new IndicatorThread object."""
        super().__init__()
        self.trade = trade
        self.config = config
        self.root = None
        self.error = None
        self.stop_event = threading.Event()
        self._utilization_ratio_string = None

    def run(self):
        """Run the thread, creating and placing widgets on the screen."""
        try:
            self.root = tk.Tk()
            self.root.attributes("-alpha", 0.8)
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-transparentcolor", "black")
            self.root.config(bg="black")
            self.root.overrideredirect(True)
            self.root.title(
                self.config[self.trade.process]["title"] + " Indicator"
            )
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            is_clock_label_enabled = self.config[
                self.trade.widgets_section
            ].getboolean("is_clock_label_enabled")
            maximum_daily_number_of_trades = int(
                self.config[self.trade.process][
                    "maximum_daily_number_of_trades"
                ]
            )

            if is_clock_label_enabled:
                clock_label = tk.Label(
                    self.root,
                    font=(
                        "Tahoma",
                        -int(
                            self.config[self.trade.widgets_section][
                                "clock_label_font_size"
                            ]
                        ),
                    ),
                    bg="gray5",
                    fg="tan1",
                )
                self._place_widget(
                    clock_label,
                    self.config[self.trade.widgets_section][
                        "clock_label_position"
                    ],
                )
                IndicatorTooltip(clock_label, "Current system time")

            status_bar_frame_font_size = int(
                self.config[self.trade.widgets_section][
                    "status_bar_frame_font_size"
                ]
            )
            status_bar_frame = tk.Frame(self.root, bg="gray5")
            self._place_widget(
                status_bar_frame,
                self.config[self.trade.widgets_section][
                    "status_bar_frame_position"
                ],
            )

            current_number_of_trades_label = tk.Label(
                status_bar_frame,
                bg="gray5",
                fg="tan1",
                font=("Bahnschrift", -status_bar_frame_font_size),
                height=1,
                width=5,
            )
            current_number_of_trades_label.grid(row=0, column=0)
            if maximum_daily_number_of_trades:
                text = (
                    "Current number of trades / maximum daily number of trades"
                )
            else:
                text = "Current number of trades"

            IndicatorTooltip(current_number_of_trades_label, text)

            self._utilization_ratio_string = tk.StringVar()
            self._utilization_ratio_string.set(
                self.config[self.trade.process]["utilization_ratio"]
            )
            utilization_ratio_spinbox = tk.Spinbox(
                status_bar_frame,
                bd=0,
                bg="gray5",
                fg="tan1",
                font=("Bahnschrift", -status_bar_frame_font_size),
                # 'from' is a reserved keyword in Python.
                from_=RATIO_EPSILON,
                highlightthickness=0,
                increment=0.01,
                insertbackground="tan1",
                justify="center",
                relief="flat",
                selectbackground="tan1",
                selectforeground="gray5",
                textvariable=self._utilization_ratio_string,
                to=1.0,
                width=5,
                # 'validate' and 'validatecommand' are inherited from
                # tk.Entry.
                validate="key",
                validatecommand=(
                    self.root.register(self._is_valid_float),
                    "%P",
                ),
            )
            utilization_ratio_spinbox.grid(row=0, column=1)
            self._utilization_ratio_string.trace_add(
                "write", self._on_utilization_ratio_change
            )
            utilization_ratio_spinbox.bind(
                "<MouseWheel>", self._on_mouse_wheel
            )
            IndicatorTooltip(utilization_ratio_spinbox, "Utilization ratio")

            while not self.stop_event.is_set():
                try:
                    if is_clock_label_enabled:
                        clock_label.config(text=time.strftime("%H:%M:%S"))

                    current_number_of_trades = self.config[
                        self.trade.variables_section
                    ]["current_number_of_trades"]
                    if maximum_daily_number_of_trades:
                        current_number_of_trades_label.config(
                            text=(
                                f"{current_number_of_trades}"
                                f"/{maximum_daily_number_of_trades}"
                            )
                        )
                    else:
                        current_number_of_trades_label.config(
                            text=current_number_of_trades
                        )

                    self.root.update()
                except TclError:
                    break
                time.sleep(0.01)
        except (TclError, WidgetPositionError) as e:
            self.error = e
        finally:
            if self.root:
                try:
                    self.root.destroy()
                except TclError:
                    pass

    def stop(self):
        """Set the stop event to signal the thread to stop."""
        self.stop_event.set()

    def on_closing(self):
        """Handle window close event."""
        self.stop_event.set()
        self.root.quit()

    def _place_widget(self, widget, position):
        """Place the widget according to the specified position."""
        work_left, work_top, work_right, work_bottom = GetMonitorInfo(
            MonitorFromPoint((0, 0))
        ).get("Work")
        work_center_x = int(0.5 * work_right)
        work_center_y = int(0.5 * work_bottom)
        position_map = {
            "n": (work_center_x, work_top),
            "ne": (work_right, work_top),
            "e": (work_right, work_center_y),
            "se": (work_right, work_bottom),
            "s": (work_center_x, work_bottom),
            "sw": (work_left, work_bottom),
            "w": (work_left, work_center_y),
            "nw": (work_left, work_top),
            "center": (work_center_x, work_center_y),
        }
        if position in position_map:
            widget.place(
                x=position_map[position][0],
                y=position_map[position][1],
                anchor=position,
            )
        elif "," in position:
            x, y = map(int, position.split(","))
            widget.place(x=x, y=y)
        else:
            raise WidgetPositionError(f"Invalid widget position: {position}")

    def _is_valid_float(self, user_input):
        """Check if the user input is a valid float."""
        if user_input == "":
            return True
        try:
            float(user_input)
            return True
        except ValueError:
            return False

    # Accept and ignore all positional arguments.
    def _on_utilization_ratio_change(self, *_):
        """Clamp and store the utilization ratio when the input changes."""
        value = self._utilization_ratio_string.get()
        if value in ("0", "0.", "0.0"):
            return
        try:
            float_value = float(value)
            float_value = max(RATIO_EPSILON, min(1.0, float_value))
            self._utilization_ratio_string.set(f"{float_value:.2f}")
            self.config[self.trade.process][
                "utilization_ratio"
            ] = self._utilization_ratio_string.get()
        except ValueError:
            pass

    def _on_mouse_wheel(self, event):
        """Adjust the utilization ratio with mouse wheel scroll."""
        try:
            delta = 0.1 if event.delta > 0 else -0.1
            current = float(self._utilization_ratio_string.get())
            new_value = max(RATIO_EPSILON, min(1.0, current + delta))
            self._utilization_ratio_string.set(f"{new_value:.2f}")
        except ValueError:
            pass


class IndicatorTooltip:
    """Manage a tooltip for a specific widget."""

    def __init__(self, widget, text):
        """Construct a new IndicatorTooltip object."""
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, _):
        """Show the tooltip when the mouse hovers over the widget."""
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.attributes("-alpha", 0.8)
        self.tooltip.attributes("-topmost", True)
        self.tooltip.geometry(f"+{x}+{y}")
        self.tooltip.overrideredirect(True)

        tk.Label(
            self.tooltip,
            bg="tan1",
            fg="gray5",
            font=("Bahnschrift", -12),
            text=self.text,
        ).pack()

    def hide_tooltip(self, _):
        """Hide the tooltip when the mouse leaves the widget."""
        if hasattr(self, "tooltip"):
            self.tooltip.destroy()


class MessageThread(threading.Thread):
    """Handle a thread for displaying a message in a Tkinter window."""

    def __init__(self, trade, config, text):
        """Construct a new MessageThread object."""
        super().__init__()
        self.trade = trade
        self.config = config
        self.text = text
        self.root = None
        self.error = None

    def run(self):
        """Run the thread, creating and displaying a message window."""
        try:
            self.root = tk.Tk()
            self.root.attributes("-alpha", 0.8)
            self.root.attributes("-toolwindow", True)
            self.root.attributes("-topmost", True)
            self.root.bind("<Escape>", lambda event: self.root.destroy())
            self.root.resizable(False, False)
            self.root.title(
                self.config[self.trade.process]["title"] + " Message"
            )
            self.root.withdraw()

            tk.Message(
                self.root,
                bg="gray5",
                fg="tan1",
                font=(
                    "Bahnschrift",
                    -int(
                        self.config[self.trade.widgets_section][
                            "message_font_size"
                        ]
                    ),
                ),
                text=self.text,
            ).pack()

            self.root.update()
            _, _, work_right, work_bottom = GetMonitorInfo(
                MonitorFromPoint((0, 0))
            ).get("Work")
            self.root.geometry(
                f"+{int(0.5 * (work_right - self.root.winfo_width()))}"
                f"+{int(0.5 * (work_bottom - self.root.winfo_height()))}"
            )
            self.root.deiconify()
            self.root.mainloop()
        except (TclError, WidgetPositionError) as e:
            self.error = e
        finally:
            if self.root:
                try:
                    self.root.destroy()
                except TclError:
                    pass
