"""PowerShell startup script generation for trading workflows."""

import os
import shlex


def create_startup_script(trade, config, script_path, file_utilities):
    """Create a startup script for a trade."""

    def generate_script_lines(interpreter, current_script_path, options):
        """Generate lines of script for given options."""
        lines = []
        for option in options:
            option = option.strip()
            if not option:
                continue
            arguments = [
                interpreter,
                current_script_path,
                *shlex.split(option),
            ]
            quoted_arguments = []
            for argument in arguments:
                quoted_arguments.append(
                    "'" + argument.replace("'", "''") + "'"
                )
            line = f"    & {quoted_arguments[0]} `\n"
            line += "\n".join(
                f"      {argument} `" for argument in quoted_arguments[1:-1]
            )
            if len(quoted_arguments) > 2:
                line += "\n"
            line += f"      {quoted_arguments[-1]}\n"
            lines.append(line)
        return lines

    activate_path, interpreter = file_utilities.select_venv(
        os.path.dirname(script_path), activate="Activate.ps1"
    )
    if not interpreter:
        interpreter = "python.exe"

    executable = config[trade.process]["executable"]
    executable_name = os.path.basename(executable).replace("'", "''")
    working_directory = os.path.dirname(executable).replace("'", "''")
    process_name = trade.process.replace("'", "''")
    start_process = (
        "    Start-Process `\n"
        f"      -FilePath '{executable_name}' `\n"
        f"      -WorkingDirectory '{working_directory}'\n"
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
        lines.append(". '" + activate_path.replace("'", "''") + "'\n")

    lines.append(
        f"if (Get-Process '{process_name}' "
        "-ErrorAction SilentlyContinue) {\n"
    )
    lines.append(
        f"    Stop-Process -Name '{process_name}' "
        "-Force -ErrorAction Stop\n"
    )
    lines.append("    $deadline = (Get-Date).AddSeconds(15)\n")
    lines.append(
        f"    while (Get-Process '{process_name}' "
        "-ErrorAction SilentlyContinue) {\n"
    )
    lines.append("        if ((Get-Date) -ge $deadline) {\n")
    lines.append(
        '            throw "Timed out waiting for '
        f"'{process_name}' to stop.\"\n"
    )
    lines.append("        }\n")
    lines.append("        Start-Sleep -Milliseconds 100\n")
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
