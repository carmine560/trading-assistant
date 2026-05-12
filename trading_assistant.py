"""Assist with discretionary day trading of stocks on margin."""

import argparse
import sys

from app import (
    actions,
    config_builder,
    config_workflow,
    models,
    runtime,
)
from core_utilities import (
    data_utilities,
    errors,
    file_utilities,
)
from core_utilities.config_io import read_config
from core_utilities.config_validation import (
    ConfigError,
    ensure_section_exists,
    evaluate_value,
)
from interaction_utilities import gui_interactions

RATIO_EPSILON = 1e-4
SANS_INITIAL_SECURITIES_CODE_REGEX = (
    r"[\dACDFGHJKLMNPRSTUWXY]\d[\dACDFGHJKLMNPRSTUWXY]5?"
)
SECURITIES_CODE_REGEX = "[1-9]" + SANS_INITIAL_SECURITIES_CODE_REGEX
Trade = models.Trade


# Entry Point


def main():
    """Execute the main program based on command-line arguments."""
    args = get_arguments()
    trade = Trade(
        *args.P,
        script_path=__file__,
        start_execute_action_thread_fn=actions.start_execute_action_thread,
    )

    if file_utilities.create_launchers_exit(args, __file__):
        return
    if config_workflow.configure_exit(
        args,
        trade,
        configure,
        config_workflow.create_completion,
        __file__,
        RATIO_EPSILON,
    ):
        return

    config = configure(trade)
    ensure_section_exists(config, trade.process)
    gui_state = gui_interactions.GuiState(
        evaluate_value(config[trade.process]["interactive_windows"])
    )
    runtime.run(args, trade, config, gui_state)


# CLI and Configuration


def get_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        "-P",
        nargs=2,
        default=("SBI Securities", "HYPERSBI2"),
        help="set the brokerage and the process [defaults: %(default)s]",
        metavar=("BROKERAGE", "PROCESS|EXECUTABLE_PATH"),
    )
    parser.add_argument(
        "-r", action="store_true", help="save the customer margin ratios"
    )
    parser.add_argument("-s", action="store_true", help="start the scheduler")
    parser.add_argument(
        "-l",
        action="store_true",
        help="start the mouse and keyboard listeners",
    )
    parser.add_argument(
        "-a", nargs=1, help="execute an action", metavar="ACTION"
    )

    file_utilities.add_launcher_options(group)
    group.add_argument(
        "-SS",
        action="store_true",
        help="configure the startup script, create a shortcut to it,"
        " and exit",
    )
    group.add_argument(
        "-S", action="store_true", help="configure schedules and exit"
    )
    group.add_argument(
        "-L",
        action="store_true",
        help="configure the input map for buttons and keys and exit",
    )
    group.add_argument(
        "-A",
        nargs=1,
        help="configure an action, create a shortcut to it, and exit",
        metavar="ACTION",
    )
    group.add_argument(
        "-CB",
        action="store_true",
        help="configure the cash balance region and exit",
    )
    group.add_argument(
        "-U",
        action="store_true",
        help="configure the utilization ratio of the cash balance and exit",
    )
    group.add_argument(
        "-PL",
        action="store_true",
        help="configure the price limit region and exit",
    )
    group.add_argument(
        "-DLL",
        action="store_true",
        help="configure the daily loss limit ratio and exit",
    )
    group.add_argument(
        "-MDN",
        action="store_true",
        help="configure the maximum daily number of trades and exit",
    )
    group.add_argument(
        "-D",
        nargs=1,
        help="delete the startup script or an action,"
        " delete the shortcut to it, and exit",
        metavar="SCRIPT_BASE|ACTION",
    )
    group.add_argument(
        "-C", action="store_true", help="check configuration changes and exit"
    )

    return parser.parse_args(None if sys.argv[1:] else ["-h"])


def configure(trade, can_interpolate=True, can_override=True):
    """Set up the configuration for a trade."""
    return config_builder.configure(
        trade,
        file_utilities=file_utilities,
        data_utilities=data_utilities,
        securities_code_regex=SECURITIES_CODE_REGEX,
        read_config_fn=read_config,
        can_interpolate=can_interpolate,
        can_override=can_override,
    )


if __name__ == "__main__":
    try:
        main()
    except ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except errors.TradingAssistantError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
