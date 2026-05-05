"""Tests for extracted action execution helpers."""

from types import SimpleNamespace

from app import actions


def test_execute_action_speaks_text_with_explicit_dependencies():
    spoken = []
    trade = SimpleNamespace(
        initialize_attributes=lambda: None,
        speech_manager=SimpleNamespace(set_speech_text=spoken.append),
    )
    gui_state = SimpleNamespace(initialize_attributes=lambda: None)
    config = {}
    deps = {
        "configuration": SimpleNamespace(evaluate_value=lambda value: value),
    }

    assert actions.execute_action(
        trade,
        config,
        gui_state,
        [("speak_text", "ready")],
        deps,
    )
    assert spoken == ["ready"]


def test_all_keys_includes_execute_action_and_save_market_data():
    assert "execute_action" in actions.ALL_KEYS
    assert "save_market_data" in actions.ALL_KEYS
