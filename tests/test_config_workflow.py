"""Tests for extracted configuration workflow helpers."""

from configparser import ConfigParser
import subprocess
from types import SimpleNamespace

from app import config_workflow


def test_is_xy_accepts_two_integers_with_whitespace():
    assert config_workflow.is_xy(" 10,  25 ")
    assert not config_workflow.is_xy("10,25,30")
    assert not config_workflow.is_xy("10.5,25")


def test_configure_exit_uses_trade_geometry_section_for_presets(monkeypatch):
    config = ConfigParser()
    config["MYPROC"] = {"title": "My Process"}
    config["MYPROC Geometries"] = {
        "main": "10, 20",
        "offset": "30,40",
        "region": "1,2,3,4",
    }
    config["MYPROC Actions"] = {}

    captured = {}

    def fake_modify_option(*_args, **kwargs):
        captured["items"] = kwargs["items"]["preset_geometries"]
        return False

    monkeypatch.setattr(config_workflow, "modify_option", fake_modify_option)
    monkeypatch.setattr(
        config_workflow.file_utilities,
        "delete_shortcut",
        lambda *_args, **_kwargs: None,
    )

    args = SimpleNamespace(
        S=False,
        L=False,
        CB=False,
        U=False,
        PL=False,
        DLL=False,
        MDN=False,
        SS=False,
        A=("open_order",),
        D=False,
        C=False,
    )
    trade = SimpleNamespace(
        geometries_section="MYPROC Geometries",
        actions_section="MYPROC Actions",
        config_path="config.ini",
        process="MYPROC",
        resource_directory=".",
        instruction_items={},
    )

    assert config_workflow.configure_exit(
        args,
        trade,
        lambda *_args, **_kwargs: config,
        lambda *_args, **_kwargs: None,
        "script.py",
        0.01,
    )
    assert captured["items"] == [
        "${MYPROC Geometries:main}",
        "${MYPROC Geometries:offset}",
    ]


def test_create_action_shortcut_quotes_powershell_command_arguments():
    captured = {}
    script_path = "C:/Users/Test User/Trading's Bot/trading_assistant.py"
    action_name = "Bob's Action"
    trade = SimpleNamespace(
        process="HYPERSBI2",
        resource_directory="C:/Users/Test User/Trading's Bot/resources",
    )
    config = {"HYPERSBI2": {"title": "Hyper SBI 2 Assistant"}}

    def create_shortcut(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    file_utilities = SimpleNamespace(
        select_executable=lambda _executables: (
            "C:/Program Files/PowerShell/7/pwsh.exe"
        ),
        select_venv=lambda *_args, **_kwargs: (
            "C:/Users/Test User/Trading's Bot/.venv/Scripts/Activate.ps1",
            "python.exe",
        ),
        create_icon=lambda *_args, **_kwargs: "C:/icons/Bob's Action.ico",
        create_shortcut=create_shortcut,
    )

    config_workflow._create_action_shortcut(
        trade,
        config,
        action_name,
        file_utilities,
        script_path,
    )

    expected_command = (
        ". 'C:/Users/Test User/Trading''s Bot/.venv/Scripts/Activate.ps1'; "
        "& 'python.exe' "
        "'C:/Users/Test User/Trading''s Bot/trading_assistant.py' "
        "'-a' 'Bob''s Action'"
    )
    assert captured["args"] == (
        action_name,
        "C:/Program Files/PowerShell/7/pwsh.exe",
        subprocess.list2cmdline(["-Command", expected_command]),
    )
    assert captured["kwargs"] == {
        "program_group_base": "Hyper SBI 2 Assistant",
        "icon_location": "C:/icons/Bob's Action.ico",
    }
