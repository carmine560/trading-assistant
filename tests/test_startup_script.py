"""Tests for PowerShell startup script generation."""

from types import SimpleNamespace

from app import startup_script


def test_create_startup_script_quotes_paths_and_option_arguments(tmp_path):
    script_path = "C:/Users/Test User/Trading's Bot/trading_assistant.py"
    startup_script_path = tmp_path / "assistant.ps1"
    trade = SimpleNamespace(
        process="HYPER'SBI2",
        startup_script_section="HYPER'SBI2 Startup Script",
        startup_script=str(startup_script_path),
    )
    config = {
        "HYPER'SBI2": {
            "executable": (
                "C:/Program Files/SBI'Sec/HYPER SBI2/HYPER'SBI2.exe"
            ),
        },
        "HYPER'SBI2 Startup Script": {
            "pre_start_options": "-r",
            "post_start_options": '-a "Bob\'s Action"',
            "running_options": '-lsa "login action"',
        },
    }
    file_utilities = SimpleNamespace(
        select_venv=lambda *_args, **_kwargs: (
            "C:/Users/Test User/Trading's Bot/.venv/Scripts/Activate.ps1",
            "python.exe",
        )
    )

    startup_script.create_startup_script(
        trade,
        config,
        script_path,
        file_utilities,
    )

    assert startup_script_path.read_text(encoding="utf-8") == (
        ". 'C:/Users/Test User/Trading''s Bot/.venv/Scripts/Activate.ps1'\n"
        "if (Get-Process 'HYPER''SBI2' -ErrorAction SilentlyContinue) {\n"
        "    Stop-Process -Name 'HYPER''SBI2'\n"
        "    while (Get-Process 'HYPER''SBI2' "
        "-ErrorAction SilentlyContinue) {\n"
        "        Start-Sleep -Seconds 0.1\n"
        "    }\n"
        "    Start-Sleep -Seconds 1.0\n"
        "    Start-Process `\n"
        "      -FilePath 'HYPER''SBI2.exe' `\n"
        "      -WorkingDirectory 'C:/Program Files/SBI''Sec/HYPER SBI2'\n"
        "    & 'python.exe' `\n"
        "      'C:/Users/Test User/Trading''s Bot/trading_assistant.py' `\n"
        "      '-lsa' `\n"
        "      'login action'\n"
        "}\n"
        "else {\n"
        "    & 'python.exe' `\n"
        "      'C:/Users/Test User/Trading''s Bot/trading_assistant.py' `\n"
        "      '-r'\n"
        "    Start-Process `\n"
        "      -FilePath 'HYPER''SBI2.exe' `\n"
        "      -WorkingDirectory 'C:/Program Files/SBI''Sec/HYPER SBI2'\n"
        "    & 'python.exe' `\n"
        "      'C:/Users/Test User/Trading''s Bot/trading_assistant.py' `\n"
        "      '-a' `\n"
        "      'Bob''s Action'\n"
        "}\n"
        "deactivate\n"
    )


def test_create_startup_script_uses_python_when_venv_is_missing(tmp_path):
    script_path = "C:/Projects/trading-assistant/trading_assistant.py"
    startup_script_path = tmp_path / "assistant.ps1"
    trade = SimpleNamespace(
        process="HYPERSBI2",
        startup_script_section="HYPERSBI2 Startup Script",
        startup_script=str(startup_script_path),
    )
    config = {
        "HYPERSBI2": {
            "executable": "C:/Program Files/SBI/HYPERSBI2/HYPERSBI2.exe",
        },
        "HYPERSBI2 Startup Script": {
            "pre_start_options": "",
            "post_start_options": "-rl",
            "running_options": "-l",
        },
    }
    file_utilities = SimpleNamespace(
        select_venv=lambda *_args, **_kwargs: (None, None)
    )

    startup_script.create_startup_script(
        trade,
        config,
        script_path,
        file_utilities,
    )

    text = startup_script_path.read_text(encoding="utf-8")
    assert ". " not in text
    assert "deactivate" not in text
    assert "    & 'python.exe' `\n" in text
