"""Tests for file utility exception-boundary helpers."""

import subprocess

import pytest

from core_utilities import file_utilities
from core_utilities.errors import UtilityOperationError


class _IterableFiles(list):
    """Provide list iteration plus a pandas-like `values` attribute."""

    @property
    def values(self):
        return list(self)


def test_archive_encrypt_directory_raises_when_gpg_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        file_utilities,
        "GNUPG_IMPORT_ERROR",
        ModuleNotFoundError("No module named 'gnupg'"),
    )

    with pytest.raises(UtilityOperationError, match="gnupg"):
        file_utilities.archive_encrypt_directory("source", "output")


def test_decrypt_extract_file_raises_when_gpg_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        file_utilities,
        "GNUPG_IMPORT_ERROR",
        ModuleNotFoundError("No module named 'gnupg'"),
    )

    with pytest.raises(UtilityOperationError, match="gnupg"):
        file_utilities.decrypt_extract_file("archive.gpg", "output")


def test_move_to_trash_raises_typed_error_for_subprocess_failure(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["trash-put"])

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    with pytest.raises(UtilityOperationError, match="Unable to move"):
        file_utilities.move_to_trash("example.txt")


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


def test_compare_directory_list_returns_structured_discrepancies(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    (directory / "present.txt").write_text("", encoding="utf-8")
    (directory / "unexpected.txt").write_text("", encoding="utf-8")

    result = file_utilities.compare_directory_list(
        str(directory),
        r".+\.txt",
        _IterableFiles(["present.txt", "missing.txt"]),
    )

    assert result == {
        "unexpected_files": [str(directory / "unexpected.txt")],
        "missing_files": [str(directory / "missing.txt")],
    }
