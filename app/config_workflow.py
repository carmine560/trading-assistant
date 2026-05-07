"""Configuration workflow helpers extracted from the entrypoint."""

import os
import sys


def is_xy(value):
    """Return True if the value represents exactly two integers (X, Y)."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return False
    try:
        int(parts[0])
        int(parts[1])
        return True
    except ValueError:
        return False


def create_completion(trade, config, configuration, file_utilities):
    """Generate completion scripts for options and values."""
    options = ("-a", "-A", "-D")
    trade.instruction_items["preset_additional_values"] = (
        configuration.list_section(config, trade.actions_section)
    )

    file_utilities.create_powershell_completion(
        trade.script_base,
        options,
        trade.instruction_items.get("preset_additional_values"),
        ("py", "python"),
        os.path.join(trade.resource_directory, "completion.ps1"),
    )
    file_utilities.create_bash_completion(
        trade.script_base,
        options,
        trade.instruction_items.get("preset_additional_values"),
        ("py.exe", "python.exe"),
        os.path.join(trade.resource_directory, "completion.sh"),
    )


def configure_exit(
    args,
    trade,
    deps,
):
    """Configure parameters based on command-line arguments and exit."""
    configure_fn = deps["configure_fn"]
    configuration = deps["configuration"]
    create_completion_fn = deps["create_completion_fn"]
    create_startup_script_fn = deps["create_startup_script_fn"]
    file_utilities = deps["file_utilities"]
    is_xy_fn = deps["is_xy_fn"]
    ratio_epsilon = deps["ratio_epsilon"]
    script_path = deps["script_path"]

    config = configure_fn(trade, can_interpolate=False)
    backup_parameters = {"number_of_backups": 8}
    trade.instruction_items["preset_additional_values"] = (
        configuration.list_section(config, trade.actions_section)
    )

    if any((args.S, args.L, args.CB, args.U, args.PL, args.DLL, args.MDN)):
        _configure_sections(
            args,
            trade,
            config,
            configuration,
            backup_parameters,
            ratio_epsilon,
        )
        return True
    if args.SS and configuration.modify_section(
        config,
        trade.startup_script_section,
        trade.config_path,
        backup_parameters=backup_parameters,
        is_encrypted=True,
    ):
        configuration.write_config(
            config, trade.config_path, is_encrypted=True
        )
        config = configure_fn(trade)
        create_startup_script_fn(trade, config)
        powershell = file_utilities.select_executable(
            ["pwsh.exe", "powershell.exe"]
        )
        if powershell:
            file_utilities.create_shortcut(
                trade.startup_script_base,
                powershell,
                f'-WindowStyle Hidden -File "{trade.startup_script}"',
                program_group_base=config[trade.process]["title"],
                icon_location=file_utilities.create_icon(
                    trade.startup_script_base,
                    icon_directory=trade.resource_directory,
                ),
            )
        return True
    if args.A:
        items = (
            option
            for option, value in config[trade.geometries_section].items()
            if is_xy_fn(value)
        )
        trade.instruction_items["preset_geometries"] = [
            f"${{HYPERSBI2 Geometries:{option}}}" for option in sorted(items)
        ]
        if configuration.modify_option(
            config,
            trade.actions_section,
            args.A[0],
            trade.config_path,
            backup_parameters=backup_parameters,
            can_insert_delete=True,
            initial_value="[()]",
            prompts={
                "key": "command",
                "value": "argument",
                "additional_value": "additional argument",
                "preset_additional_value": "action",
                "end_of_list": "end of commands",
            },
            items=trade.instruction_items,
            is_encrypted=True,
        ):
            _create_action_shortcut(
                trade,
                config,
                args.A[0],
                file_utilities,
                script_path,
            )
        else:
            file_utilities.delete_shortcut(
                args.A[0],
                program_group_base=config[trade.process]["title"],
                icon_location=os.path.join(
                    trade.resource_directory, args.A[0] + ".ico"
                ),
            )

        create_completion_fn(trade, config)
        return True
    if args.D:
        _delete_script_or_action(
            args,
            trade,
            config,
            configuration,
            create_completion_fn,
            backup_parameters,
            file_utilities,
        )
        return True
    if args.C:
        configuration.check_config_changes(
            configure_fn(trade, can_interpolate=False, can_override=False),
            trade.config_path,
            excluded_sections=(
                trade.geometries_section,
                trade.variables_section,
            ),
            user_option_ignored_sections=(trade.actions_section,),
            backup_parameters=backup_parameters,
            is_encrypted=True,
        )
        return True
    return False


def _configure_sections(
    args,
    trade,
    config,
    configuration,
    backup_parameters,
    ratio_epsilon,
):
    """Handle simple section-editing configure-and-exit options."""
    option_map = {
        "L": (
            trade.process,
            "input_map",
            False,
            {"value": "action"},
            trade.instruction_items.get("preset_additional_values"),
            (),
        ),
        "S": (
            trade.schedules_section,
            None,
            True,
            {
                "key": "schedule",
                "values": ("trigger", "action"),
                "end_of_list": "end of schedules",
            },
            (
                trade.instruction_items.get("preset_values"),
                trade.instruction_items.get("preset_additional_values"),
            ),
            (),
        ),
        "CB": (
            trade.geometries_section,
            "cash_balance_region",
            False,
            {"value": "x, y, width, height, index"},
            None,
            (),
        ),
        "U": (
            trade.process,
            "utilization_ratio",
            False,
            None,
            None,
            (ratio_epsilon, 1.0),
        ),
        "PL": (
            trade.geometries_section,
            "price_limit_region",
            False,
            {"value": "x, y, width, height, index"},
            None,
            (),
        ),
        "DLL": (
            trade.process,
            "daily_loss_limit_ratio",
            False,
            None,
            None,
            (-1.0, -ratio_epsilon),
        ),
        "MDN": (
            trade.process,
            "maximum_daily_number_of_trades",
            False,
            None,
            None,
            (0, sys.maxsize),
        ),
    }
    for argument, values in option_map.items():
        if getattr(args, argument):
            (
                section,
                option,
                can_insert_delete,
                prompts,
                all_values,
                limits,
            ) = values
            configuration.modify_section(
                config,
                section,
                trade.config_path,
                backup_parameters=backup_parameters,
                can_insert_delete=can_insert_delete,
                option=option,
                prompts=prompts,
                all_values=all_values,
                limits=limits,
                is_encrypted=True,
            )
            break


def _create_action_shortcut(
    trade,
    config,
    action_name,
    file_utilities,
    script_path,
):
    """Create or update the shortcut for a configured action."""
    powershell = file_utilities.select_executable(
        ["pwsh.exe", "powershell.exe"]
    )
    activate_path, interpreter = file_utilities.select_venv(
        os.path.dirname(script_path), activate="Activate.ps1"
    )
    # To pin the shortcut to the Taskbar, specify an executable file as the
    # 'target_path' argument.
    file_utilities.create_shortcut(
        action_name,
        powershell if powershell else "py.exe",
        (
            f'-Command ". {activate_path};'
            f' {interpreter} {script_path} -a {action_name}"'
            if activate_path
            else f"{script_path} -a {action_name}"
        ),
        program_group_base=config[trade.process]["title"],
        icon_location=file_utilities.create_icon(
            action_name, icon_directory=trade.resource_directory
        ),
    )


def _delete_script_or_action(
    args,
    trade,
    config,
    configuration,
    create_completion_fn,
    backup_parameters,
    file_utilities,
):
    """Delete a startup script or action and its shortcut."""
    base = args.D[0]
    if base == trade.script_base:
        base = trade.startup_script_base
        if os.path.isfile(trade.startup_script):
            os.remove(trade.startup_script)
    else:
        configuration.delete_option(
            config,
            trade.actions_section,
            base,
            trade.config_path,
            backup_parameters=backup_parameters,
            is_encrypted=True,
        )
        create_completion_fn(trade, config)

    file_utilities.delete_shortcut(
        base,
        program_group_base=config[trade.process]["title"],
        icon_location=os.path.join(trade.resource_directory, f"{base}.ico"),
    )
