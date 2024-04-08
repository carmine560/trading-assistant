import os

import file_utilities

class Initializer:
    def __init__(self, vendor, process, script_path):
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
