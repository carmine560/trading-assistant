"""Tests for configuration file I/O helpers."""

from configparser import ConfigParser
import os
import subprocess

import pytest

from core_utilities import config_io
from core_utilities.config_common import ConfigError


def test_write_file_atomically_fsyncs_file_before_replace(
    monkeypatch, tmp_path
):
    calls = []
    target = tmp_path / "config.ini"
    directory = os.path.abspath(tmp_path)
    real_open = config_io.os.open
    real_replace = config_io.os.replace

    def fake_fsync(_fd):
        calls.append("fsync")

    def fake_open(path, flags, *args, **kwargs):
        if os.path.abspath(path) == directory:
            raise OSError("directory fsync unsupported")
        return real_open(path, flags, *args, **kwargs)

    def fake_replace(source, destination):
        calls.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(config_io.os, "fsync", fake_fsync)
    monkeypatch.setattr(config_io.os, "open", fake_open)
    monkeypatch.setattr(config_io.os, "replace", fake_replace)

    config_io.write_file_atomically(
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
    real_open = config_io.os.open
    real_replace = config_io.os.replace

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

    monkeypatch.setattr(config_io.os, "fsync", fake_fsync)
    monkeypatch.setattr(config_io.os, "open", fake_open)
    monkeypatch.setattr(config_io.os, "close", fake_close)
    monkeypatch.setattr(config_io.os, "replace", fake_replace)

    config_io.write_file_atomically(
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

    monkeypatch.setattr(config_io.os, "fsync", fake_fsync)
    monkeypatch.setattr(config_io.os, "replace", fake_replace)

    with pytest.raises(OSError, match="fsync failed"):
        config_io.write_file_atomically(
            str(target),
            "w",
            lambda f: f.write("persisted=true\n"),
        )

    assert replace_calls == []
    assert not target.exists()
    assert not list(tmp_path.glob(".config.ini.*.tmp"))


def test_write_encrypted_config_uses_default_recipient_self_without_fingerprint(
    monkeypatch,
    tmp_path,
):
    config = ConfigParser()
    config["General"] = {"fingerprint": ""}
    config["Section"] = {"option": "value"}
    config_path = tmp_path / "config.ini"
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=b"encrypted config",
            stderr=b"",
        )

    monkeypatch.setattr(config_io.subprocess, "run", fake_run)
    monkeypatch.setattr(
        config_io,
        "GNUPG_IMPORT_ERROR",
        ModuleNotFoundError("gnupg"),
    )

    config_io.write_config(config, str(config_path), is_encrypted=True)

    assert calls == [
        (
            [
                "gpg",
                "--batch",
                "--yes",
                "--encrypt",
                "--default-recipient-self",
            ],
            {
                "input": b"[General]\nfingerprint = \n\n[Section]\noption = value\n\n",
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "check": False,
            },
        )
    ]
    assert (tmp_path / "config.ini.gpg").read_bytes() == b"encrypted config"


def test_write_encrypted_config_reports_default_recipient_self_failure(
    monkeypatch,
    tmp_path,
):
    config = ConfigParser()
    config["General"] = {"fingerprint": ""}
    config_path = tmp_path / "config.ini"

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            2,
            stdout=b"",
            stderr=b"gpg: no default secret key\n",
        )

    monkeypatch.setattr(config_io.subprocess, "run", fake_run)

    with pytest.raises(ConfigError) as e:
        config_io.write_config(config, str(config_path), is_encrypted=True)

    assert str(e.value) == "GPG encryption failed: gpg: no default secret key"
    assert not (tmp_path / "config.ini.gpg").exists()


def test_write_encrypted_config_reports_missing_gpg_executable(
    monkeypatch,
    tmp_path,
):
    config = ConfigParser()
    config["General"] = {"fingerprint": ""}
    config_path = tmp_path / "config.ini"

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("gpg")

    monkeypatch.setattr(config_io.subprocess, "run", fake_run)

    with pytest.raises(ConfigError, match="Unable to run gpg"):
        config_io.write_config(config, str(config_path), is_encrypted=True)

    assert not (tmp_path / "config.ini.gpg").exists()
