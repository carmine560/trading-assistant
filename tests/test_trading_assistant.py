"""Tests for deterministic parsing and calculation helpers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import actions, config_workflow
from core_utilities import errors


def _write_rankings_price(
    monkeypatch,
    sample_config,
    tmp_path,
    symbol="1234",
    price="980",
):
    """Create a previous-day rankings CSV for price-limit tests."""
    monkeypatch.setattr(
        actions.pd.Timestamp,
        "now",
        lambda **_kwargs: actions.pd.Timestamp("2026-05-21 07:58:59"),
    )
    path = tmp_path / "ランキング_ティック回数20260521.csv"
    path.write_text(
        f'a,b,c,d,e,f,{symbol},h,i,"{price}"\n',
        encoding="utf-8",
    )
    sample_config["Market Data"]["market_data_directory"] = str(tmp_path)
    return path


@pytest.fixture(autouse=True)
def _use_fresh_customer_margin_ratios(monkeypatch):
    """Keep calculation tests focused on local ratio parsing."""
    monkeypatch.setattr(
        actions.customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: False,
    )


def test_is_xy_accepts_two_integers_with_whitespace():
    assert config_workflow.is_xy(" 10,  25 ")
    assert not config_workflow.is_xy("10,25,30")
    assert not config_workflow.is_xy("10.5,25")


def test_archive_market_data_moves_current_default_named_files(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    monkeypatch.setattr(
        actions.pd.Timestamp,
        "now",
        lambda **_kwargs: actions.pd.Timestamp("2026-05-22 17:39:00"),
    )
    current_file = tmp_path / "ランキング_ティック回数20260522.csv"
    previous_file = tmp_path / "ランキング_ティック回数20260521.csv"
    unrelated_file = tmp_path / "0.md"
    current_file.write_text("current\n", encoding="utf-8")
    previous_file.write_text("previous\n", encoding="utf-8")
    unrelated_file.write_text("unrelated\n", encoding="utf-8")

    assert actions.archive_market_data(sample_trade, sample_config) == (
        True,
        None,
    )

    archived_file = (
        tmp_path
        / "Archived Market Data"
        / "20260522T173900.000"
        / current_file.name
    )
    assert archived_file.read_text(encoding="utf-8") == "current\n"
    assert not current_file.exists()
    assert previous_file.read_text(encoding="utf-8") == "previous\n"
    assert unrelated_file.read_text(encoding="utf-8") == "unrelated\n"


def test_archive_market_data_uses_unique_same_second_directories(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    timestamps = iter(
        (
            actions.pd.Timestamp("2026-05-22 17:39:00.000"),
            actions.pd.Timestamp("2026-05-22 17:39:00.123"),
        )
    )
    monkeypatch.setattr(
        actions.pd.Timestamp,
        "now",
        lambda **_kwargs: next(timestamps),
    )
    current_file = tmp_path / "ランキング_ティック回数20260522.csv"

    current_file.write_text("first\n", encoding="utf-8")
    assert actions.archive_market_data(sample_trade, sample_config) == (
        True,
        None,
    )

    current_file.write_text("second\n", encoding="utf-8")
    assert actions.archive_market_data(sample_trade, sample_config) == (
        True,
        None,
    )

    archive_root = tmp_path / "Archived Market Data"
    assert (
        archive_root / "20260522T173900.000" / current_file.name
    ).read_text(encoding="utf-8") == "first\n"
    assert (
        archive_root / "20260522T173900.123" / current_file.name
    ).read_text(encoding="utf-8") == "second\n"


def test_archive_market_data_succeeds_without_matching_files(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    monkeypatch.setattr(
        actions.pd.Timestamp,
        "now",
        lambda **_kwargs: actions.pd.Timestamp("2026-05-22 17:39:00"),
    )
    previous_file = tmp_path / "ランキング_ティック回数20260521.csv"
    previous_file.write_text("previous\n", encoding="utf-8")

    assert actions.archive_market_data(sample_trade, sample_config) == (
        True,
        None,
    )
    assert previous_file.read_text(encoding="utf-8") == "previous\n"
    assert not (tmp_path / "Archived Market Data").exists()


def test_get_price_limit_uses_rankings_price(
    monkeypatch, sample_trade, sample_config, tmp_path
):
    _write_rankings_price(monkeypatch, sample_config, tmp_path)

    assert actions.get_price_limit(sample_trade, sample_config) == 1130.0


def test_get_price_limit_falls_back_to_recognized_value(
    monkeypatch, sample_trade, sample_config
):
    def fake_recognize_text(*args, **kwargs):
        assert args[:4] == (0, 0, 10, 10)
        assert args[4:] == (1, 128, False)
        assert kwargs == {"text_type": "decimal_numbers"}
        return 4321

    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        fake_recognize_text,
    )

    assert actions.get_price_limit(sample_trade, sample_config) == 4321


def test_get_price_limit_skips_rankings_for_non_hypersbi2_process(
    monkeypatch, sample_trade, sample_config
):
    sample_trade.process = "OTHER"
    sample_trade.geometries_section = "OTHER Geometries"
    sample_config["OTHER"] = {
        "image_magnification": "1",
        "binarization_threshold": "128",
        "is_dark_theme": "false",
    }
    sample_config["OTHER Geometries"] = {"price_limit_region": "0, 0, 10, 10"}

    def fail_rankings_lookup(*_args, **_kwargs):
        raise AssertionError("Rankings lookup should be Hyper SBI 2 only.")

    def fake_recognize_text(*args, **kwargs):
        assert args[:4] == (0, 0, 10, 10)
        assert args[4:] == (1, 128, False)
        assert kwargs == {"text_type": "decimal_numbers"}
        return 4321

    monkeypatch.setattr(
        actions,
        "_get_closing_price_from_hypersbi2_rankings",
        fail_rankings_lookup,
    )
    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        fake_recognize_text,
    )

    assert actions.get_price_limit(sample_trade, sample_config) == 4321


def test_get_price_limit_records_missing_file_warning_without_speech(
    monkeypatch, sample_trade, sample_config, tmp_path
):
    spoken = []
    sample_config["Market Data"]["market_data_directory"] = str(
        tmp_path / "missing"
    )
    sample_trade.speech_manager = SimpleNamespace(
        set_speech_text=spoken.append,
    )
    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        lambda *_args, **_kwargs: 4321,
    )

    assert actions.get_price_limit(sample_trade, sample_config) == 4321
    assert spoken == []
    assert isinstance(sample_trade.last_action_warning, errors.MarketDataError)
    assert "Unable to read market data file" in str(
        sample_trade.last_action_warning
    )
    assert "missing" in str(sample_trade.last_action_warning)


def test_get_price_limit_falls_back_to_ocr_for_short_rankings_row(
    monkeypatch, sample_trade, sample_config, tmp_path
):
    spoken = []
    monkeypatch.setattr(
        actions.pd.Timestamp,
        "now",
        lambda **_kwargs: actions.pd.Timestamp("2026-05-21 07:58:59"),
    )
    path = tmp_path / "ランキング_ティック回数20260521.csv"
    path.write_text("1234\n", encoding="utf-8")
    sample_trade.speech_manager = SimpleNamespace(
        set_speech_text=spoken.append,
    )
    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        lambda *_args, **_kwargs: 4321,
    )

    assert actions.get_price_limit(sample_trade, sample_config) == 4321
    assert spoken == [actions.PRICE_LIMIT_FALLBACK_WARNING]
    assert isinstance(sample_trade.last_action_warning, errors.MarketDataError)
    assert f"Unable to read market data file {path}" in str(
        sample_trade.last_action_warning
    )
    assert "row 1 has 1 columns" in str(sample_trade.last_action_warning)


def test_get_price_limit_falls_back_to_ocr_for_non_numeric_rankings_price(
    monkeypatch, sample_trade, sample_config, tmp_path
):
    spoken = []
    path = _write_rankings_price(
        monkeypatch,
        sample_config,
        tmp_path,
        price="bad",
    )
    sample_trade.speech_manager = SimpleNamespace(
        set_speech_text=spoken.append,
    )
    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        lambda *_args, **_kwargs: 4321,
    )

    assert actions.get_price_limit(sample_trade, sample_config) == 4321
    assert spoken == [actions.PRICE_LIMIT_FALLBACK_WARNING]
    assert isinstance(sample_trade.last_action_warning, errors.MarketDataError)
    assert f"Unable to read market data file {path}" in str(
        sample_trade.last_action_warning
    )
    assert "row 1 has invalid closing price 'bad'" in str(
        sample_trade.last_action_warning
    )


def test_calculate_share_size_uses_margin_ratio_file(
    monkeypatch, sample_trade, sample_config, tmp_path
):
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    _write_rankings_price(monkeypatch, sample_config, tmp_path)

    success, message = actions.calculate_share_size(
        sample_trade, sample_config, "long"
    )

    assert (success, message) == (True, None)
    assert sample_trade.share_size == 200


def test_calculate_share_size_caches_fresh_margin_ratio_check(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    calls = []
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    _write_rankings_price(monkeypatch, sample_config, tmp_path)
    monkeypatch.setattr(
        actions.customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: calls.append("get_latest") or False,
    )
    monotonic_values = iter((1000.0, 1100.0))
    monkeypatch.setattr(
        actions.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    assert actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    ) == (True, None)
    assert actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    ) == (True, None)
    assert calls == ["get_latest"]


def test_calculate_share_size_refreshes_expired_margin_ratio_check(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    calls = []
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    _write_rankings_price(monkeypatch, sample_config, tmp_path)
    monkeypatch.setattr(
        actions.customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: calls.append("get_latest") or False,
    )
    monotonic_values = iter((1000.0, 2801.0, 2801.0))
    monkeypatch.setattr(
        actions.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    assert actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    ) == (True, None)
    assert actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    ) == (True, None)
    assert calls == ["get_latest", "get_latest"]


def test_calculate_share_size_rejects_suspended_symbol(
    sample_trade, sample_config
):
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,suspended\n", encoding="utf-8"
    )

    assert actions.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, "Margin trading suspended.")


def test_calculate_share_size_rejects_stale_margin_ratios(
    monkeypatch,
    sample_trade,
    sample_config,
):
    monkeypatch.setattr(
        actions.customer_margin_ratios,
        "get_latest",
        lambda *_args, **_kwargs: True,
    )

    assert actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    ) == (False, "Customer margin ratios are stale.")
    assert sample_trade.share_size == 0


def test_calculate_share_size_rejects_unverifiable_margin_ratios(
    monkeypatch,
    sample_trade,
    sample_config,
):
    def raise_market_data_error(*_args, **_kwargs):
        raise errors.MarketDataError("market holidays unavailable")

    monkeypatch.setattr(
        actions.customer_margin_ratios,
        "get_latest",
        raise_market_data_error,
    )

    success, message = actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    )

    assert not success
    assert message == "Unable to verify customer margin ratios."
    assert isinstance(sample_trade.last_action_error, errors.MarketDataError)
    assert str(sample_trade.last_action_error) == "market holidays unavailable"
    assert sample_trade.share_size == 0


def test_calculate_share_size_returns_message_for_invalid_sizing_input(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    sample_config["HYPERSBI2"]["utilization_ratio"] = "0"
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    _write_rankings_price(monkeypatch, sample_config, tmp_path)

    assert actions.calculate_share_size(
        sample_trade,
        sample_config,
        "long",
    ) == (False, actions.SHARE_SIZE_ERROR)
    assert isinstance(sample_trade.last_action_error, ValueError)
    assert str(sample_trade.last_action_error) == (
        "Utilization ratio must be positive."
    )
    assert sample_trade.share_size == 0


def test_calculate_share_size_uses_ocr_for_invalid_rankings_file(
    monkeypatch,
    sample_trade,
    sample_config,
    tmp_path,
):
    spoken = []
    monkeypatch.setattr(
        actions.pd.Timestamp,
        "now",
        lambda **_kwargs: actions.pd.Timestamp("2026-05-21 07:58:59"),
    )
    path = tmp_path / "ランキング_ティック回数20260521.csv"
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    path.write_text("1234\n", encoding="utf-8")
    sample_trade.speech_manager = SimpleNamespace(
        set_speech_text=spoken.append,
    )
    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        lambda *_args, **_kwargs: 1130,
    )

    assert actions.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (True, None)
    assert spoken == [actions.PRICE_LIMIT_FALLBACK_WARNING]
    assert isinstance(sample_trade.last_action_warning, errors.MarketDataError)
    assert f"Unable to read market data file {path}" in str(
        sample_trade.last_action_warning
    )
    assert "row 1 has 1 columns" in str(sample_trade.last_action_warning)
    assert sample_trade.share_size == 200


def test_calculate_share_size_handles_price_limit_ocr_failure(
    monkeypatch,
    sample_trade,
    sample_config,
):
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    ocr_error = errors.TextRecognitionError(
        "OCR failed",
        attempts=50,
        last_output="",
        region=(0, 0, 10, 10),
        text_type="decimal_numbers",
    )
    monkeypatch.setattr(
        actions.text_recognition,
        "recognize_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ocr_error),
    )

    assert actions.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, actions.PRICE_LIMIT_ERROR)
    assert sample_trade.last_action_error is ocr_error
    assert sample_trade.share_size == 0


def test_calculate_share_size_rejects_short_margin_ratio_row(
    sample_trade, sample_config
):
    path = Path(sample_trade.customer_margin_ratios)
    path.write_text("1234\n", encoding="utf-8")

    assert actions.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, f"{actions.CUSTOMER_MARGIN_RATIOS_FILE_ERROR}.")

    assert isinstance(sample_trade.last_action_error, errors.MarketDataError)
    assert f"{actions.CUSTOMER_MARGIN_RATIOS_FILE_ERROR} {path}" in str(
        sample_trade.last_action_error
    )
    assert "row 1 has 1 columns" in str(sample_trade.last_action_error)


def test_calculate_share_size_rejects_non_numeric_margin_ratio(
    sample_trade, sample_config
):
    path = Path(sample_trade.customer_margin_ratios)
    path.write_text("1234,bad\n", encoding="utf-8")

    assert actions.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, f"{actions.CUSTOMER_MARGIN_RATIOS_FILE_ERROR}.")

    assert isinstance(sample_trade.last_action_error, errors.MarketDataError)
    assert f"{actions.CUSTOMER_MARGIN_RATIOS_FILE_ERROR} {path}" in str(
        sample_trade.last_action_error
    )
    assert "row 1 has invalid margin ratio 'bad'" in str(
        sample_trade.last_action_error
    )


def test_calculate_share_size_caps_short_positions_at_fifty_units(
    monkeypatch, sample_trade, sample_config, tmp_path
):
    sample_trade.cash_balance = 10_000_000
    Path(sample_trade.customer_margin_ratios).write_text(
        "1234,0.5\n", encoding="utf-8"
    )
    _write_rankings_price(monkeypatch, sample_config, tmp_path)

    success, message = actions.calculate_share_size(
        sample_trade, sample_config, "short"
    )

    assert (success, message) == (True, None)
    assert sample_trade.share_size == 5000


def test_calculate_share_size_requires_symbol_and_cash_balance(
    sample_trade, sample_config
):
    sample_trade.symbol = ""

    assert actions.calculate_share_size(
        sample_trade, sample_config, "long"
    ) == (False, "Symbol or cash balance not provided.")
