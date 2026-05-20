"""Tests for OCR retry and failure handling."""

import sys

import pytest

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from core_utilities.errors import TextRecognitionError

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "interaction_utilities"
    / "text_recognition.py"
)


def _load_text_recognition_module():
    """Load the real OCR helper module without the test stub."""
    spec = spec_from_file_location("test_text_recognition_module", MODULE_PATH)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_recognize_text_retries_until_it_parses(monkeypatch):
    module = _load_text_recognition_module()

    image = SimpleNamespace(
        resize=lambda *_args, **_kwargs: image,
        point=lambda *_args, **_kwargs: image,
    )
    monkeypatch.setattr(module.ImageGrab, "grab", lambda **_kwargs: image)
    monkeypatch.setattr(
        module.pytesseract,
        "image_to_string",
        lambda *_args, **_kwargs: next(outputs),
    )
    sleep_calls = []
    monkeypatch.setattr(module.time, "sleep", sleep_calls.append)
    outputs = iter(("bad", "1234"))

    assert (
        module.recognize_text(
            0,
            0,
            10,
            10,
            0,
            1,
            128,
            False,
            max_attempts=3,
        )
        == 1234.0
    )
    assert sleep_calls == [0.1]


def test_recognize_text_raises_typed_failure_after_max_attempts(monkeypatch):
    module = _load_text_recognition_module()

    image = SimpleNamespace(
        resize=lambda *_args, **_kwargs: image,
        point=lambda *_args, **_kwargs: image,
    )
    monkeypatch.setattr(module.ImageGrab, "grab", lambda **_kwargs: image)
    monkeypatch.setattr(
        module.pytesseract,
        "image_to_string",
        lambda *_args, **_kwargs: "still bad",
    )
    monkeypatch.setattr(module.time, "sleep", lambda *_args: None)

    with pytest.raises(TextRecognitionError) as e:
        module.recognize_text(
            10,
            20,
            30,
            40,
            0,
            1,
            128,
            False,
            max_attempts=2,
        )

    error = e.value
    assert error.attempts == 2
    assert error.last_output == "still bad"
    assert error.region == (10, 20, 30, 40)
    assert error.text_type == "integers"
    assert "2 attempts" in str(error)


def test_recognize_text_returns_none_when_canceled(monkeypatch):
    module = _load_text_recognition_module()

    grab_called = False

    def fake_grab(**_kwargs):
        nonlocal grab_called
        grab_called = True
        raise AssertionError("grab should not be called after cancellation")

    monkeypatch.setattr(module.ImageGrab, "grab", fake_grab)

    assert (
        module.recognize_text(
            0,
            0,
            10,
            10,
            0,
            1,
            128,
            False,
            should_continue_reference=lambda: False,
        )
        is None
    )
    assert not grab_called
