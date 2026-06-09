"""Tests for configuration file I/O helpers."""

from configparser import ConfigParser
import subprocess

import pytest

from core_utilities import config_io, file_utilities
from core_utilities.config_common import ConfigError


def test_write_encrypted_config_uses_default_recipient_self(
    monkeypatch, tmp_path
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

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)
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
                "input": (
                    b"[General]\nfingerprint = \n\n"
                    b"[Section]\noption = value\n\n"
                ),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "check": False,
                "timeout": file_utilities.GPG_TIMEOUT_SECONDS,
            },
        )
    ]
    assert (tmp_path / "config.ini.gpg").read_bytes() == b"encrypted config"


def test_write_encrypted_config_uses_explicit_recipient(
    monkeypatch,
    tmp_path,
):
    config = ConfigParser()
    config["General"] = {"fingerprint": "ABCD1234"}
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

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    config_io.write_config(config, str(config_path), is_encrypted=True)

    assert calls == [
        (
            [
                "gpg",
                "--batch",
                "--yes",
                "--encrypt",
                "--recipient",
                "ABCD1234",
            ],
            {
                "input": (
                    b"[General]\nfingerprint = ABCD1234\n\n"
                    b"[Section]\noption = value\n\n"
                ),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "check": False,
                "timeout": file_utilities.GPG_TIMEOUT_SECONDS,
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

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

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

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    with pytest.raises(ConfigError, match="Unable to run gpg"):
        config_io.write_config(config, str(config_path), is_encrypted=True)

    assert not (tmp_path / "config.ini.gpg").exists()


def test_read_encrypted_config_uses_gpg_decrypt(monkeypatch, tmp_path):
    config = ConfigParser()
    config_path = tmp_path / "config.ini"
    encrypted_path = tmp_path / "config.ini.gpg"
    encrypted_path.write_bytes(b"encrypted config")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=b"[Section]\noption = value\n",
            stderr=b"",
        )

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    config_io.read_config(config, str(config_path), is_encrypted=True)

    assert calls == [
        (
            [
                "gpg",
                "--batch",
                "--yes",
                "--decrypt",
                str(encrypted_path),
            ],
            {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "check": False,
                "timeout": file_utilities.GPG_TIMEOUT_SECONDS,
            },
        )
    ]
    assert config["Section"]["option"] == "value"


def test_read_encrypted_config_reports_gpg_failure(monkeypatch, tmp_path):
    config = ConfigParser()
    config_path = tmp_path / "config.ini"
    encrypted_path = tmp_path / "config.ini.gpg"
    encrypted_path.write_bytes(b"encrypted config")

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            2,
            stdout=b"",
            stderr=b"gpg: decryption failed\n",
        )

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    with pytest.raises(ConfigError) as e:
        config_io.read_config(config, str(config_path), is_encrypted=True)

    assert (
        str(e.value) == "GPG decryption failed while reading config: "
        "gpg: decryption failed"
    )


def test_read_encrypted_config_reports_missing_gpg_executable(
    monkeypatch,
    tmp_path,
):
    config = ConfigParser()
    config_path = tmp_path / "config.ini"
    encrypted_path = tmp_path / "config.ini.gpg"
    encrypted_path.write_bytes(b"encrypted config")

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("gpg")

    monkeypatch.setattr(file_utilities.subprocess, "run", fake_run)

    with pytest.raises(ConfigError, match="Unable to run gpg"):
        config_io.read_config(config, str(config_path), is_encrypted=True)
