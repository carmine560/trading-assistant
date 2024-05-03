"""Module for initializing script execution environment."""

import ast
import os

import file_utilities


class Initializer:
    """Initialize the script execution environment."""

    def __init__(self, vendor, process, script_path):
        """Construct an Initializer instance."""
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
    """Extract specific commands from the given source code."""
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
