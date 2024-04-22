"""Module for initializing script execution environment."""

import os

import file_utilities


class Initializer:
    """
    Initialize the script execution environment.

    This class initializes the script execution environment based on the
    provided vendor, process, and script path. It checks if the process exists,
    determines the script file and configuration directory, and ensures the
    configuration directory exists.

    Attributes:
        vendor (str): The vendor name.
        process (str): The process name or path.
        script_path (str): The path to the script.
        executable (str): The absolute path to the process if it exists.
        script_file (str): The base name of the script path.
        script_base (str): The base name of the script file without extension.
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
        self.config_directory = os.path.join(
            os.path.expandvars('%LOCALAPPDATA%'),
            os.path.basename(os.path.dirname(script_path)))
        self.config_path = os.path.join(self.config_directory,
                                        self.script_base + '.ini')

        file_utilities.check_directory(self.config_directory)

        self.actions_section = f'{self.process} Actions'
