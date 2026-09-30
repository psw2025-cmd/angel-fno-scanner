from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import ast
import re

import pytest

import angel_prediction_engine as engine
import scanner
from runtime_window import session_deadline, wait_seconds_to_open, window_is_active

ROOT = Path(__file__).resolve().parents[1]


def test_scheduled_jobs_cover_close_without_exceeding_hosted_limit():
    caller = (ROOT / '.github/workflows/market_bot.yml').read_text()
    worker = (ROOT / '.github/workflows/market_session.yml').read_text()
    assert 'needs: run-scanner' in caller
    assert 'window: afternoon' in caller
    assert "'morning' || 'once'" in caller
    assert 'cancel-in-progress: false' in caller
    timeout = int(re.search(r'timeout-minutes:\s*(\d+)', worker).group(1))
    assert 240 < timeout <= 360
    assert "'3600' || '14400'" in worker
    assert 'market-session-handoff' in worker
    morning_start = datetime(2026, 9, 30, 9, 10)
    morning_end = session_deadline(morning_start, 'morning')
    close_end = session_deadline(morning_end, 'afternoon')
    assert (morning_end - morning_start).total_seconds() < 14400
    assert (close_end - morning_end).total_seconds() < 14400
    assert close_end == datetime(2026, 9, 30, 15, 55)


@pytest.mark.parametrize('key', [
    'ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_PIN', 'ANGEL_TOTP_SEED',
    'SHEET_ID', 'BQ_PROJECT_ID',
])
def test_config_has_only_empty_source_defaults(key):
    tree = ast.parse((ROOT / 'angel_prediction_engine.py').read_text())
    value = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == key for t in n.targets))
    assert isinstance(value, ast.Call) and value.func.attr == 'strip'
    getenv = value.func.value
    assert isinstance(getenv, ast.Call) and getenv.func.attr == 'getenv'
    assert [a.value for a in getenv.args] == [key, '']


@pytest.mark.parametrize('missing', ['', '   '])
def test_missing_credentials_fail_before_broker_use(monkeypatch, missing):
    broker = Mock(side_effect=AssertionError('Broker must not be called'))
    monkeypatch.setattr(engine, 'SmartConnect', broker)
    monkeypatch.setattr(engine, 'ANGEL_API_KEY', missing)
    with pytest.raises(RuntimeError, match='Missing required configuration:.*ANGEL_API_KEY'):
        engine.get_angel_client()
    broker.assert_not_called()


def test_missing_storage_fails_before_pipeline_broker_use(monkeypatch):
    broker = Mock(side_effect=AssertionError('Broker must not be called'))
    monkeypatch.setattr(engine, 'get_angel_client', broker)
    monkeypatch.setattr(engine, 'SHEET_ID', '')
    with pytest.raises(RuntimeError, match='Missing required configuration:.*SHEET_ID'):
        engine.run_prediction_pipeline()
    broker.assert_not_called()


@pytest.mark.parametrize('hour,minute,market,preclose', [
    (9, 14, False, False), (9, 15, True, False),
    (15, 30, True, True), (15, 35, True, True),
    (15, 40, True, True), (15, 41, False, False),
])
def test_prediction_session_behavior(hour, minute, market, preclose):
    now = datetime(2026, 9, 30, hour, minute)
    assert engine.is_market_open(now) is market
    assert engine.is_pre_close_time(now) is preclose


def test_scheduled_open_wait_and_expired_windows():
    assert wait_seconds_to_open(datetime(2026, 9, 30, 9, 10), 'morning') == 300
    assert wait_seconds_to_open(datetime(2026, 9, 30, 9, 15), 'morning') == 0
    assert wait_seconds_to_open(datetime(2026, 9, 30, 8, 30), 'once') == 0
    assert not window_is_active(datetime(2026, 9, 30, 12, 30), 'morning')
    assert window_is_active(datetime(2026, 9, 30, 12, 30), 'afternoon')
    assert not window_is_active(datetime(2026, 9, 30, 15, 55), 'afternoon')
    assert not window_is_active(datetime(2026, 10, 3, 10), 'morning')
    assert session_deadline(datetime(2026, 9, 30, 7, tzinfo=timezone.utc), 'morning') == datetime(2026, 9, 30, 7, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        session_deadline(datetime(2026, 9, 30), 'typo')


def test_scanner_waits_for_open_then_stops_at_handoff(monkeypatch):
    monkeypatch.setenv('SCANNER_WINDOW', 'morning')
    times = iter([datetime(2026, 9, 30, 9, 10),
                  datetime(2026, 9, 30, 9, 10),
                  datetime(2026, 9, 30, 12, 30)])
    monkeypatch.setattr(scanner, 'now_ist', lambda: next(times))
    monkeypatch.setattr(scanner, 'discover_universe', lambda _api: {})
    fetch = Mock(side_effect=AssertionError('No pre-open or expired-window quotes'))
    monkeypatch.setattr(scanner, 'fetch_chunked', fetch)
    sleep = Mock()
    monkeypatch.setattr(scanner.time, 'sleep', sleep)
    scanner.run_angel_loop(None, None)
    sleep.assert_called_once_with(30)
    fetch.assert_not_called()


def test_fresh_writer_is_monitored_until_takeover(monkeypatch):
    monkeypatch.setenv('SCANNER_WINDOW', 'afternoon')
    monkeypatch.setattr(scanner, 'SHEET_ID', 'offline-sheet')
    monkeypatch.setattr(scanner, 'now_ist', lambda: datetime(2026, 9, 30, 12, 32))
    monkeypatch.setattr(scanner, 'load_service_account', lambda: {})
    monkeypatch.setattr(scanner.gspread, 'service_account_from_dict', Mock())
    ages = iter([30, 60, 121])
    monkeypatch.setattr(scanner, 'heartbeat_age_seconds', lambda *_: next(ages))
    sleep = Mock()
    monkeypatch.setattr(scanner.time, 'sleep', sleep)
    login, run = Mock(), Mock()
    monkeypatch.setattr(scanner, 'angel_login', login)
    monkeypatch.setattr(scanner, 'run_angel_loop', run)
    monkeypatch.setattr(engine, 'run_prediction_pipeline', Mock())
    scanner.main()
    assert sleep.call_count == 2
    login.assert_called_once()
    run.assert_called_once()


def test_expired_window_does_no_external_work(monkeypatch):
    monkeypatch.setenv('SCANNER_WINDOW', 'morning')
    monkeypatch.setattr(scanner, 'now_ist', lambda: datetime(2026, 9, 30, 12, 31))
    load = Mock(side_effect=AssertionError('No external work after deadline'))
    monkeypatch.setattr(scanner, 'load_service_account', load)
    scanner.main()
    load.assert_not_called()


def test_external_writer_stays_authoritative_at_window_end(monkeypatch):
    monkeypatch.setenv('SCANNER_WINDOW', 'morning')
    monkeypatch.setattr(scanner, 'SHEET_ID', 'offline-sheet')
    times = iter([datetime(2026, 9, 30, 12, 29), datetime(2026, 9, 30, 12, 29),
                  datetime(2026, 9, 30, 12, 30)])
    monkeypatch.setattr(scanner, 'now_ist', lambda: next(times))
    monkeypatch.setattr(scanner, 'load_service_account', lambda: {})
    monkeypatch.setattr(scanner.gspread, 'service_account_from_dict', Mock())
    monkeypatch.setattr(scanner, 'heartbeat_age_seconds', lambda *_: 30)
    monkeypatch.setattr(scanner.time, 'sleep', Mock())
    login, pipeline = Mock(), Mock()
    monkeypatch.setattr(scanner, 'angel_login', login)
    monkeypatch.setattr(engine, 'run_prediction_pipeline', pipeline)
    scanner.main()
    login.assert_not_called()
    pipeline.assert_not_called()
    worker = (ROOT / '.github/workflows/market_session.yml').read_text()
    assert 'angel_prediction_engine.py --run-once' not in worker


def test_owned_pipeline_failure_reaches_workflow(monkeypatch):
    monkeypatch.setenv('SCANNER_WINDOW', 'once')
    monkeypatch.setattr(scanner, 'SHEET_ID', 'offline-sheet')
    monkeypatch.setattr(scanner, 'load_service_account', lambda: {})
    monkeypatch.setattr(scanner.gspread, 'service_account_from_dict', Mock())
    monkeypatch.setattr(scanner, 'heartbeat_age_seconds', lambda *_: None)
    monkeypatch.setattr(scanner, 'angel_login', Mock())
    monkeypatch.setattr(scanner, 'run_angel_loop', Mock())
    monkeypatch.setattr(engine, 'run_prediction_pipeline', Mock(side_effect=RuntimeError('pipeline failure')))
    with pytest.raises(RuntimeError, match='pipeline failure'):
        scanner.main()


@pytest.mark.parametrize('window,hour,minute,expected', [
    ('morning', 9, 14, False), ('morning', 9, 15, True),
    ('morning', 9, 45, True), ('morning', 9, 46, False),
    ('afternoon', 14, 59, False), ('afternoon', 15, 0, True),
    ('afternoon', 15, 40, True), ('afternoon', 15, 41, False),
    ('once', 15, 0, False),
])
def test_owned_prediction_runs_in_its_scoring_window(monkeypatch, window, hour, minute, expected):
    api = object()
    pipeline = Mock()
    monkeypatch.setattr(engine, 'run_prediction_pipeline', pipeline)
    assert scanner.run_scheduled_prediction(api, datetime(2026, 9, 30, hour, minute), window) is expected
    if expected:
        pipeline.assert_called_once_with(smart_api=api)
    else:
        pipeline.assert_not_called()


def test_scanner_rejects_blank_credentials_before_client_construction(monkeypatch):
    for name in ('ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_PIN', 'ANGEL_TOTP_SEED'):
        monkeypatch.setenv(name, '   ')
    broker = Mock(side_effect=AssertionError('Broker must not be called'))
    monkeypatch.setattr(scanner, 'SmartConnect', broker)
    with pytest.raises(RuntimeError, match='Missing required configuration:.*ANGEL_API_KEY'):
        scanner.angel_login()
    broker.assert_not_called()
