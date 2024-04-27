"""Module for initializing script execution environment."""

import ast
import os

import file_utilities


class Initializer:
    """
    Initialize the script execution environment.

    This class initializes the script execution environment based on the
    provided vendor, process, and script path. It checks if the process
    exists, determines the script file and configuration directory, and
    ensures the configuration directory exists.

    Attributes:
        vendor (str): The vendor name.
        process (str): The process name or path.
        script_path (str): The path to the script.
        executable (str): The absolute path to the process if it exists.
        script_file (str): The base name of the script path.
        script_base (str): The base name of the script file without
            extension.
        config_directory (str): The configuration directory path.
        config_path (str): The configuration file path.
        actions_section (str): The actions section name.
    """

    def __init__(self, vendor, process, script_path):
        """
        Construct an Initializer instance.

        Args:
            vendor (str): The vendor name.
            process (str): The process name or path.
            script_path (str): The path to the script.
        """
        self.vendor = vendor
        if os.path.exists(process):
            self.executable = os.path.abspath(process)
            self.process = os.path.splitext(
                os.path.basename(self.executable))[0]
        else:
            self.executable = None
            self.process = process

        self.script_file = os.path.basename(script_path)
        self.script_base = os.path.splitext(self.script_file)[0]
        self.config_path = file_utilities.get_config_path(script_path)
        self.config_directory = os.path.dirname(self.config_path)

        self.actions_section = f'{self.process} Actions'


def extract_commands(source, command='command'):
    """
    Extract specific commands from the given source code.

    This function parses the source code and extracts the values of the
    specified command from all 'if' conditions where the command is
    compared with a constant value.

    Args:
        source (str): The source code to parse.
        command (str, optional): The command to look for. Defaults to
            'command'.

    Returns:
        list: A list of command values extracted from the source code.
    """
    commands = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Compare):
                left = test.left
                if isinstance(left, ast.Name) and left.id == command:
                    comparator = test.comparators[0]
                    if isinstance(comparator, ast.Constant):
                        commands.append(comparator.value)
    return commands
