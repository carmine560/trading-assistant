"""Tests for extracted configuration workflow helpers."""

from configparser import ConfigParser
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
