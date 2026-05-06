"""Startup-script helpers extracted from the main entrypoint."""

import os


def create_startup_script(trade, config, script_path, file_utilities):
    """Create a startup script for a trade."""

    def generate_script_lines(interpreter, current_script_path, options):
        """Generate lines of script for given options."""
        return [
            f"    {interpreter} `\n"
            f"      {current_script_path} `\n"
            f"      {option.strip()}\n"
            for option in options
            if option
        ]

    activate_path, interpreter = file_utilities.select_venv(
        os.path.dirname(script_path), activate="Activate.ps1"
    )
    if not interpreter:
        interpreter = "python.exe"

    start_process = (
        "    Start-Process "
        f'"{os.path.basename(config[trade.process]["executable"])}" `\n'
        "      -WorkingDirectory "
        f'"{os.path.dirname(config[trade.process]["executable"])}"\n'
    )
    pre_start_options = config[trade.startup_script_section][
        "pre_start_options"
    ].split(",")
    post_start_options = config[trade.startup_script_section][
        "post_start_options"
    ].split(",")
    running_options = config[trade.startup_script_section][
        "running_options"
    ].split(",")

    lines = []
    if activate_path:
        lines.append(f". {activate_path}\n")

    lines.append(
        f'if (Get-Process "{trade.process}" '
        "-ErrorAction SilentlyContinue) {\n"
    )
    lines.append(f'    Stop-Process -Name "{trade.process}"\n')
    lines.append(
        f'    while (Get-Process "{trade.process}" '
        "-ErrorAction SilentlyContinue) {\n"
    )
    lines.append("        Start-Sleep -Seconds 0.1\n")
    lines.append("    }\n")
    lines.append("    Start-Sleep -Seconds 1.0\n")
    lines.append(start_process)
    lines.extend(
        generate_script_lines(interpreter, script_path, running_options)
    )
    lines.append("}\n")
    lines.append("else {\n")
    lines.extend(
        generate_script_lines(interpreter, script_path, pre_start_options)
    )
    lines.append(start_process)
    lines.extend(
        generate_script_lines(interpreter, script_path, post_start_options)
    )
    lines.append("}\n")
    if activate_path:
        lines.append("deactivate\n")

    with open(trade.startup_script, "w", encoding="utf-8") as f:
        f.writelines(lines)
