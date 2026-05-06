"""Tests for file utility exception-boundary helpers."""

import subprocess

import pytest

from core_utilities import file_utilities
from core_utilities.errors import UtilityOperationError


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
