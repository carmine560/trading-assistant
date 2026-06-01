"""Tests for file utility exception-boundary helpers."""

import io
import subprocess
import tarfile
from types import SimpleNamespace

import pytest

from core_utilities import file_utilities
from core_utilities.errors import UtilityOperationError


class _IterableFiles(list):
    """Provide list iteration plus a pandas-like `values` attribute."""

    @property
    def values(self):
        return list(self)


def _encrypted_tar_bytes(members):
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:xz") as tar:
        for member in members:
            tar.addfile(*member)
    return tar_stream.getvalue()


def _directory_member(name):
    member = tarfile.TarInfo(name)
    member.type = tarfile.DIRTYPE
    return member, None


def _file_member(name, data):
    encoded_data = data.encode()
    member = tarfile.TarInfo(name)
    member.size = len(encoded_data)
    return member, io.BytesIO(encoded_data)


def _mock_decrypted_archive(monkeypatch, archive_bytes):
    class FakeGpg:
        def decrypt_file(self, _file):
            return SimpleNamespace(ok=True, data=archive_bytes)

    monkeypatch.setattr(file_utilities, "GNUPG_IMPORT_ERROR", None)
    monkeypatch.setattr(file_utilities.gnupg, "GPG", lambda: FakeGpg())


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


def test_decrypt_extract_file_restores_archive_root(monkeypatch, tmp_path):
    archive = tmp_path / "archive.gpg"
    archive.write_bytes(b"encrypted")
    output = tmp_path / "output"
    output.mkdir()
    _mock_decrypted_archive(
        monkeypatch,
        _encrypted_tar_bytes(
            [
                _directory_member("snapshot"),
                _file_member("snapshot/config.ini", "restored=true\n"),
            ]
        ),
    )

    file_utilities.decrypt_extract_file(str(archive), str(output))

    assert (output / "snapshot" / "config.ini").read_text(
        encoding="utf-8"
    ) == "restored=true\n"
    assert not (output / "snapshot.tmp").exists()
    assert not (output / "snapshot.bak").exists()


def test_decrypt_extract_file_rejects_path_traversal(monkeypatch, tmp_path):
    archive = tmp_path / "archive.gpg"
    archive.write_bytes(b"encrypted")
    output = tmp_path / "output"
    output.mkdir()
    _mock_decrypted_archive(
        monkeypatch,
        _encrypted_tar_bytes([_file_member("../outside.txt", "unsafe\n")]),
    )

    with pytest.raises(ValueError, match="Unsafe archive member"):
        file_utilities.decrypt_extract_file(str(archive), str(output))

    assert not (tmp_path / "outside.txt").exists()
    assert not list(output.iterdir())


def test_decrypt_extract_file_rejects_non_file_directory_member(
    monkeypatch,
    tmp_path,
):
    archive = tmp_path / "archive.gpg"
    archive.write_bytes(b"encrypted")
    output = tmp_path / "output"
    output.mkdir()
    link_member = tarfile.TarInfo("snapshot/link")
    link_member.type = tarfile.SYMTYPE
    link_member.linkname = "config.ini"
    _mock_decrypted_archive(
        monkeypatch,
        _encrypted_tar_bytes(
            [
                _directory_member("snapshot"),
                (link_member, None),
            ]
        ),
    )

    with pytest.raises(ValueError, match="Unsafe archive member"):
        file_utilities.decrypt_extract_file(str(archive), str(output))

    assert not list(output.iterdir())


def test_decrypt_extract_file_restores_existing_root_after_swap_failure(
    monkeypatch,
    tmp_path,
):
    archive = tmp_path / "archive.gpg"
    archive.write_bytes(b"encrypted")
    output = tmp_path / "output"
    output.mkdir()
    existing_root = output / "snapshot"
    existing_root.mkdir()
    (existing_root / "config.ini").write_text(
        "existing=true\n", encoding="utf-8"
    )
    _mock_decrypted_archive(
        monkeypatch,
        _encrypted_tar_bytes(
            [
                _directory_member("snapshot"),
                _file_member("snapshot/config.ini", "restored=true\n"),
            ]
        ),
    )
    real_rename = file_utilities.os.rename

    def fail_restore_rename(source, destination):
        if str(source).replace("\\", "/").endswith("snapshot.tmp/snapshot"):
            raise OSError("swap failed")
        real_rename(source, destination)

    monkeypatch.setattr(file_utilities.os, "rename", fail_restore_rename)

    with pytest.raises(OSError, match="swap failed"):
        file_utilities.decrypt_extract_file(str(archive), str(output))

    assert (existing_root / "config.ini").read_text(
        encoding="utf-8"
    ) == "existing=true\n"
    assert not (output / "snapshot.tmp").exists()
    assert not (output / "snapshot.bak").exists()


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
