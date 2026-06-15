"""Tests for file utility exception-boundary helpers."""

import argparse
import os
import subprocess
from types import SimpleNamespace

import pytest

from core_utilities import file_utilities
from core_utilities.errors import UtilityOperationError


def test_get_writing_file_returns_latest_active_match(monkeypatch, tmp_path):
    older = tmp_path / "Hypersbi2" / "recording.mp4"
    newer = tmp_path / "Desktop" / "recording.mp4"
    stale = tmp_path / "Desktop" / "stale.mp4"
    older.parent.mkdir()
    newer.parent.mkdir()
    older.touch()
    newer.touch()
    stale.touch()
    modification_times = {str(older): 1, str(newer): 2, str(stale): 3}

    monkeypatch.setattr(
        file_utilities,
        "is_writing",
        lambda path: path != str(stale),
    )
    monkeypatch.setattr(
        file_utilities.os.path,
        "getmtime",
        lambda path: modification_times[path],
    )

    assert file_utilities.get_writing_file(
        str(tmp_path), r".+/.*\.mp4"
    ) == str(newer)


def test_write_file_atomically_fsyncs_file_before_replace(
    monkeypatch, tmp_path
):
    calls = []
    target = tmp_path / "config.ini"
    directory = os.path.abspath(tmp_path)
    real_open = file_utilities.os.open
    real_replace = file_utilities.os.replace

    def fake_fsync(_fd):
        calls.append("fsync")

    def fake_open(path, flags, *args, **kwargs):
        if os.path.abspath(path) == directory:
            raise OSError("directory fsync unsupported")
        return real_open(path, flags, *args, **kwargs)

    def fake_replace(source, destination):
        calls.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(file_utilities.os, "fsync", fake_fsync)
    monkeypatch.setattr(file_utilities.os, "open", fake_open)
    monkeypatch.setattr(file_utilities.os, "replace", fake_replace)

    file_utilities.write_file_atomically(
        str(target),
        "w",
        lambda f: f.write("persisted=true\n"),
    )

    assert calls == ["fsync", "replace"]
    assert target.read_text(encoding="utf-8") == "persisted=true\n"


def test_write_file_atomically_fsyncs_directory_when_supported(
    monkeypatch,
    tmp_path,
):
    calls = []
    target = tmp_path / "config.ini"
    directory = os.path.abspath(tmp_path)
    directory_fd = 12345
    real_open = file_utilities.os.open
    real_replace = file_utilities.os.replace

    def fake_fsync(fd):
        calls.append("directory fsync" if fd == directory_fd else "file fsync")

    def fake_open(path, flags, *args, **kwargs):
        if os.path.abspath(path) == directory:
            return directory_fd
        return real_open(path, flags, *args, **kwargs)

    def fake_close(fd):
        calls.append("directory close")
        assert fd == directory_fd

    def fake_replace(source, destination):
        calls.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(file_utilities.os, "fsync", fake_fsync)
    monkeypatch.setattr(file_utilities.os, "open", fake_open)
    monkeypatch.setattr(file_utilities.os, "close", fake_close)
    monkeypatch.setattr(file_utilities.os, "replace", fake_replace)

    file_utilities.write_file_atomically(
        str(target),
        "w",
        lambda f: f.write("persisted=true\n"),
    )

    assert calls == [
        "file fsync",
        "replace",
        "directory fsync",
        "directory close",
    ]
    assert target.read_text(encoding="utf-8") == "persisted=true\n"


def test_write_file_atomically_does_not_replace_when_file_fsync_fails(
    monkeypatch,
    tmp_path,
):
    target = tmp_path / "config.ini"
    replace_calls = []

    def fake_fsync(_fd):
        raise OSError("fsync failed")

    def fake_replace(*args):
        replace_calls.append(args)

    monkeypatch.setattr(file_utilities.os, "fsync", fake_fsync)
    monkeypatch.setattr(file_utilities.os, "replace", fake_replace)

    with pytest.raises(OSError, match="fsync failed"):
        file_utilities.write_file_atomically(
            str(target),
            "w",
            lambda f: f.write("persisted=true\n"),
        )

    assert replace_calls == []
    assert not target.exists()
    assert not list(tmp_path.glob(".config.ini.*.tmp"))


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
        file_utilities.create_bash_launcher(
            str(tmp_path / "script.py"), tmp_path
        )

    assert "Unable to create Bash launcher" in str(e.value)
    assert str(tmp_path) in str(e.value)


def test_select_venv_interpreter_returns_first_existing_interpreter(tmp_path):
    interpreter = tmp_path / ".venv" / "Scripts" / "python.exe"
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()

    assert file_utilities.select_venv_interpreter(tmp_path) == str(interpreter)


def test_add_launcher_options_accepts_optional_output_directory(monkeypatch):
    monkeypatch.setattr(file_utilities.sys, "platform", "win32")
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    file_utilities.add_launcher_options(group)

    assert parser.parse_args(["-BS"]).BS == "."
    assert parser.parse_args(["-BS", "launchers"]).BS == "launchers"
    assert parser.parse_args(["-PS"]).PS == "."
    assert parser.parse_args(["-PS", "launchers"]).PS == "launchers"


@pytest.mark.parametrize(
    ("args", "launcher_name", "output_directory"),
    [
        (
            SimpleNamespace(BS="bash-launchers", PS=None),
            "bash",
            "bash-launchers",
        ),
        (
            SimpleNamespace(BS=None, PS="powershell-launchers"),
            "powershell",
            "powershell-launchers",
        ),
    ],
)
def test_create_launchers_exit_passes_output_directory(
    monkeypatch, args, launcher_name, output_directory
):
    calls = []
    monkeypatch.setattr(file_utilities.sys, "platform", "win32")
    monkeypatch.setattr(
        file_utilities,
        "create_bash_launcher",
        lambda script_path, output_directory: calls.append(
            ("bash", script_path, output_directory)
        ),
    )
    monkeypatch.setattr(
        file_utilities,
        "create_powershell_launcher",
        lambda script_path, output_directory: calls.append(
            ("powershell", script_path, output_directory)
        ),
    )

    assert file_utilities.create_launchers_exit(args, "script.py")
    assert calls == [
        (
            launcher_name,
            "script.py",
            output_directory,
        )
    ]


def test_create_bash_launcher_executes_venv_interpreter(monkeypatch, tmp_path):
    output_directory = tmp_path / "launchers"
    output_directory.mkdir()
    project_path = r"C:\Users\carmine\Projects\trading-assistant"
    script_path = rf"{project_path}\script.py"
    interpreter_path = rf"{project_path}\.venv\Scripts\python.exe"
    converted_paths = {
        interpreter_path: (
            "/mnt/c/Users/carmine/Projects/trading-assistant"
            "/.venv/Scripts/python.exe"
        ),
    }

    monkeypatch.setattr(file_utilities.sys, "platform", "win32")
    monkeypatch.setattr(
        file_utilities,
        "select_venv_interpreter",
        lambda _project_path: interpreter_path,
    )
    monkeypatch.setattr(
        file_utilities,
        "windows_to_wsl_path",
        lambda path: converted_paths[path],
    )
    monkeypatch.setattr(file_utilities, "can_overwrite", lambda _path: True)

    file_utilities.create_bash_launcher(script_path, output_directory)

    assert (output_directory / "script.sh").read_text(encoding="utf-8") == (
        "#!/bin/bash\n"
        "\n"
        "set -e\n"
        "\n"
        "exec \\\n"
        "    /mnt/c/Users/carmine/Projects/trading-assistant/"
        ".venv/Scripts/python.exe \\\n"
        f"    '{script_path}' \\\n"
        '    "$@"\n'
    )


def test_create_powershell_launcher_raises_when_venv_is_unavailable(tmp_path):
    with pytest.raises(UtilityOperationError) as e:
        file_utilities.create_powershell_launcher(
            str(tmp_path / "script.py"), tmp_path
        )

    assert "Unable to create PowerShell launcher" in str(e.value)
    assert str(tmp_path) in str(e.value)


def test_create_powershell_launcher_executes_venv_interpreter(
    monkeypatch, tmp_path
):
    output_directory = tmp_path / "launchers"
    output_directory.mkdir()
    project_path = r"C:\Users\carmine\Projects\trading-assistant"
    script_path = rf"{project_path}\script.py"
    interpreter_path = rf"{project_path}\.venv\Scripts\python.exe"

    monkeypatch.setattr(
        file_utilities,
        "select_venv_interpreter",
        lambda _project_path: interpreter_path,
    )
    monkeypatch.setattr(file_utilities, "can_overwrite", lambda _path: True)

    file_utilities.create_powershell_launcher(script_path, output_directory)

    assert (output_directory / "script.ps1").read_text(encoding="utf-8") == (
        '$ErrorActionPreference = "Stop"\n'
        "\n"
        f'& "{project_path}\\.venv\\Scripts\\python.exe" `\n'
        f'  "{script_path}" @args\n'
        "\n"
        "exit $LASTEXITCODE\n"
    )


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
