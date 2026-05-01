"""Shared pytest fixtures and import stubs for platform-specific modules."""

from configparser import ConfigParser
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_stub_modules():
    """Install lightweight stubs required to import trading_assistant."""
    tkinter_module = ModuleType("tkinter")
    tkinter_module.TclError = Exception
    tkinter_module.Tk = object
    tkinter_module.Label = object
    tkinter_module.Frame = object

    keyboard_module = ModuleType("pynput.keyboard")
    keyboard_module.Key = SimpleNamespace(
        alt=object(),
        alt_gr=object(),
        alt_l=object(),
        alt_r=object(),
        cmd=object(),
        cmd_l=object(),
        cmd_r=object(),
        ctrl=object(),
        ctrl_l=object(),
        ctrl_r=object(),
        shift=object(),
        shift_l=object(),
        shift_r=object(),
        esc=object(),
        f1=object(),
        f2=object(),
        f3=object(),
        f4=object(),
        f5=object(),
        f6=object(),
        f7=object(),
        f8=object(),
        f9=object(),
        f10=object(),
        f11=object(),
        f12=object(),
    )
    mouse_module = ModuleType("pynput.mouse")
    pynput_module = ModuleType("pynput")
    pynput_module.keyboard = keyboard_module
    pynput_module.mouse = mouse_module

    win32api_module = ModuleType("win32api")
    win32api_module.GetMonitorInfo = lambda *_args, **_kwargs: {}
    win32api_module.MonitorFromPoint = lambda *_args, **_kwargs: None

    text_recognition_module = ModuleType(
        "interaction_utilities.text_recognition"
    )
    text_recognition_module.recognize_text = lambda *_args, **_kwargs: 0

    stubbed_modules = {
        "tkinter": tkinter_module,
        "pynput": pynput_module,
        "pynput.keyboard": keyboard_module,
        "pynput.mouse": mouse_module,
        "pyautogui": ModuleType("pyautogui"),
        "psutil": ModuleType("psutil"),
        "win32clipboard": ModuleType("win32clipboard"),
        "win32api": win32api_module,
        "win32gui": ModuleType("win32gui"),
        "interaction_utilities.gui_interactions": ModuleType(
            "interaction_utilities.gui_interactions"
        ),
        "interaction_utilities.speech_synthesis": ModuleType(
            "interaction_utilities.speech_synthesis"
        ),
        "interaction_utilities.text_recognition": text_recognition_module,
    }
    for name, module in stubbed_modules.items():
        sys.modules.setdefault(name, module)


_install_stub_modules()


@pytest.fixture
def sample_trade(tmp_path):
    """Provide a simple trade-like object backed by temporary files."""
    return SimpleNamespace(
        symbol="1234",
        cash_balance=300_000,
        share_size=0,
        process="HYPERSBI2",
        geometries_section="HYPERSBI2 Geometries",
        customer_margin_ratios_section="SBI Customer Margin Ratios",
        customer_margin_ratios=str(tmp_path / "customer_margin_ratios.csv"),
        closing_prices=str(tmp_path / "closing_prices_"),
    )


@pytest.fixture
def sample_config():
    """Provide the minimal config sections used by the tests."""
    config = ConfigParser()
    config["HYPERSBI2"] = {
        "utilization_ratio": "0.5",
        "image_magnification": "1",
        "binarization_threshold": "128",
        "is_dark_theme": "false",
    }
    config["HYPERSBI2 Geometries"] = {"price_limit_region": "0, 0, 10, 10"}
    config["SBI Customer Margin Ratios"] = {"customer_margin_ratio": "0.3"}
    config["Market Data"] = {"rankings": ""}
    return config


@pytest.fixture
def rankings_csv(tmp_path) -> Path:
    """Create a small rankings CSV with mixed valid and invalid rows."""
    rankings = tmp_path / "rankings.csv"
    rankings.write_text(
        "\n".join(
            (
                'a,b,c,d,e,f,1234,h,i,"1,500"',
                "a,b,c,d,e,f,9876,h,i,2500",
                "a,b,c,d,e,f,0000,h,i,999",
                "a,b,c,d,e,f,12A4,h,i,3000",
            )
        ),
        encoding="utf-8",
    )
    return rankings
