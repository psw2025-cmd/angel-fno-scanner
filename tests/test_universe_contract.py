import json

import pytest

from universe_contract import require_verified_symbols, select_verified_universe, verified_symbols


def test_new_listing_cannot_silently_change_reviewed_universe():
    discovered = dict.fromkeys(verified_symbols(), object())
    discovered["UNREVIEWED"] = object()
    selected = select_verified_universe(discovered)
    assert len(selected) == 219
    assert "UNREVIEWED" not in selected


def test_equal_count_with_wrong_identity_is_rejected():
    discovered = dict.fromkeys(verified_symbols(), object())
    del discovered["SAIL"]
    discovered["UNREVIEWED"] = object()
    with pytest.raises(RuntimeError, match="SAIL"):
        select_verified_universe(discovered)


def test_count_cannot_be_lowered_by_environment(monkeypatch):
    monkeypatch.setenv("EXPECTED_FNO_UNIVERSE_COUNT", "1")
    with pytest.raises(RuntimeError, match="missing verified symbols"):
        select_verified_universe({"SAIL": object()})


def test_duplicate_manifest_is_rejected(tmp_path):
    symbols = list(verified_symbols())
    symbols[-1] = symbols[0]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"universe": {"total_symbols": 219, "symbols": symbols}}))
    with pytest.raises(RuntimeError, match="219 unique"):
        verified_symbols(path)


def test_scanner_prediction_failure_is_not_false_green(monkeypatch):
    import scanner
    import angel_prediction_engine as engine
    from types import SimpleNamespace

    monkeypatch.setattr(scanner, "load_env", lambda: None)
    monkeypatch.setattr(scanner, "require_authorized_writer", lambda: None)
    monkeypatch.setenv("SHEET_ID", "test-only")
    monkeypatch.setattr(scanner, "load_service_account", lambda: {})
    monkeypatch.setattr(scanner.gspread, "service_account_from_dict",
                        lambda _: SimpleNamespace(open_by_key=lambda _: object()))
    monkeypatch.setattr(scanner, "heartbeat_age_seconds", lambda *_: None)
    monkeypatch.setattr(scanner, "angel_login", lambda: object())
    monkeypatch.setattr(scanner, "run_angel_loop", lambda *_: None)

    def failed_prediction(**_):
        raise RuntimeError("prediction publication failed")

    monkeypatch.setattr(engine, "run_prediction_pipeline", failed_prediction)
    with pytest.raises(RuntimeError, match="prediction publication failed"):
        scanner.main()


def test_partial_publication_preserves_sinks(monkeypatch):
    import angel_prediction_engine as engine
    monkeypatch.setenv("ALLOW_PRODUCTION_WRITES", "1")
    monkeypatch.setenv("WRITER_ID", "market_bot")
    rows = [{"symbol": s} for s in verified_symbols() if s != "SAIL"]
    # No cloud client may be reached before the fail-closed coverage check.
    monkeypatch.setattr(engine, "get_bigquery_client", lambda: pytest.fail("BQ accessed"))
    monkeypatch.setattr(engine, "get_gspread_client", lambda: pytest.fail("Sheets accessed"))
    with pytest.raises(RuntimeError, match="SAIL"):
        engine.sync_to_bigquery(rows, [], {}, None)
    with pytest.raises(RuntimeError, match="SAIL"):
        engine.sync_to_google_sheet(rows, {}, [], "test-only")


def test_duplicate_output_identity_rejected():
    symbols = list(verified_symbols())
    symbols[-1] = symbols[0]
    with pytest.raises(RuntimeError, match="publication incomplete"):
        require_verified_symbols(symbols)


def test_malformed_forensic_row_cannot_be_dropped_into_partial_publication(monkeypatch):
    import angel_prediction_engine as engine
    monkeypatch.setenv("ALLOW_PRODUCTION_WRITES", "1")
    monkeypatch.setenv("WRITER_ID", "market_bot")
    monkeypatch.setattr(engine, "get_gspread_client", lambda: pytest.fail("Sheets accessed"))
    predictions = [{"symbol": s} for s in verified_symbols()]
    forensic = [["test", s] + [0] * 16 for s in verified_symbols()]
    forensic[0] = forensic[0][:2]
    with pytest.raises(RuntimeError, match="row width"):
        engine.sync_to_google_sheet(predictions, {}, forensic, "test")


def test_fresh_heartbeat_still_runs_one_prediction(monkeypatch):
    import scanner
    import angel_prediction_engine as engine
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(scanner, "load_env", lambda: None)
    monkeypatch.setattr(scanner, "require_authorized_writer", lambda: None)
    monkeypatch.setenv("SHEET_ID", "test-only")
    monkeypatch.setattr(scanner, "load_service_account", lambda: {})
    monkeypatch.setattr(scanner.gspread, "service_account_from_dict",
                        lambda _: SimpleNamespace(open_by_key=lambda _: object()))
    monkeypatch.setattr(scanner, "heartbeat_age_seconds", lambda *_: 10)
    monkeypatch.setattr(scanner, "refresh_from_forensic", lambda *_: calls.append("refresh"))
    monkeypatch.setattr(scanner, "angel_login", lambda: pytest.fail("duplicate scanner login"))
    monkeypatch.setattr(engine, "run_prediction_pipeline", lambda **_: calls.append("predict"))
    scanner.main()
    assert calls == ["refresh", "predict"]
