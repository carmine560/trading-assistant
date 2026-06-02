"""Tests for file utility exception-boundary helpers."""

import subprocess

import pytest

from core_utilities import file_utilities
from core_utilities.errors import UtilityOperationError


def test_windows_to_wsl_path_passes_raw_path_to_wslpath(monkeypatch):
    path = r"C:\Users\carmine\My Project"
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="/mnt/c/Users/carmine/My Project\n",
            stderr="",
        )

    monkeypatch.setattr(file_utilities.shutil, "which", lambda *_args: "wsl")
    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    assert (
        file_utilities.windows_to_wsl_path(path)
        == "/mnt/c/Users/carmine/My Project"
    )
    assert calls == [
        (
            ["wsl", "--exec", "wslpath", path],
            {"capture_output": True, "text": True},
        )
    ]


def test_windows_to_wsl_path_raises_on_conversion_failure(monkeypatch):
    path = r"C:\Users\carmine\Missing Project"

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args,
            1,
            stdout="",
            stderr="wslpath: failed to translate path\n",
        )

    monkeypatch.setattr(file_utilities.shutil, "which", lambda *_args: "wsl")
    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    with pytest.raises(UtilityOperationError) as e:
        file_utilities.windows_to_wsl_path(path)

    assert "Unable to convert Windows path to WSL path" in str(e.value)
    assert "wslpath: failed to translate path" in str(e.value)


def test_create_bash_launcher_raises_when_venv_is_unavailable(tmp_path):
    with pytest.raises(UtilityOperationError) as e:
        file_utilities.create_bash_launcher(str(tmp_path / "script.py"))

    assert "Unable to create Bash launcher" in str(e.value)
    assert str(tmp_path) in str(e.value)


def test_create_powershell_launcher_raises_when_venv_is_unavailable(tmp_path):
    with pytest.raises(UtilityOperationError) as e:
        file_utilities.create_powershell_launcher(str(tmp_path / "script.py"))

    assert "Unable to create PowerShell launcher" in str(e.value)
    assert str(tmp_path) in str(e.value)


def test_write_chapter_ignores_invalid_offset_without_printing(
    monkeypatch, tmp_path, capsys
):
    video = tmp_path / "video.mp4"
    video.write_text("", encoding="utf-8")
    metadata = tmp_path / "video.txt"
    metadata.write_text(";FFMETADATA1\n", encoding="utf-8")

    monkeypatch.setattr(file_utilities, "is_writing", lambda *_args: True)
    monkeypatch.setattr(file_utilities.time, "time", lambda: 1000.0)
    monkeypatch.setattr(file_utilities.os.path, "getctime", lambda *_args: 995)

    file_utilities.write_chapter(str(video), "Current", offset="bad")

    assert capsys.readouterr().out == ""
    assert "title=Current" in metadata.read_text(encoding="utf-8")
