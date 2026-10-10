import datetime as dt
from collections import defaultdict
from types import SimpleNamespace

import gspread
import pytest

import angel_prediction_engine as engine
from market_calendar import is_trading_day
from publication import (ACTIVE_CYCLE, STATUS_HEADERS, matrix_hash, publish_outputs,
                         verify_current_publication)
from sheet_grid import write_grid
from universe_contract import verified_symbols
from writer_guard import require_authorized_writer


class Worksheet:
    def __init__(self, rows=500, cols=45):
        self.row_count, self.col_count = rows, cols
        self.values, self.cleared, self.events = [], [], []
        self.fail_update = self.fail_clear = False

    def resize(self, rows, cols):
        self.events.append('resize')
        self.row_count, self.col_count = rows, cols

    def update(self, range_name, values, **kwargs):
        self.events.append('update')
        if self.fail_update:
            raise RuntimeError('update unavailable')
        if range_name == 'A1':
            self.values = [list(r) for r in values]
        elif range_name == 'G2':
            self.values[1][6] = values[0][0]

    def batch_clear(self, ranges):
        self.events.append('cleanup')
        if self.fail_clear:
            raise RuntimeError('cleanup unavailable')
        self.cleared.extend(ranges)

    def get_all_values(self, value_render_option=None):
        if value_render_option == 'UNFORMATTED_VALUE':
            return [list(r) for r in self.values]
        return [[str(c) for c in r] for r in self.values]

    def row_values(self, row):
        return self.get_all_values()[row-1] if len(self.values) >= row else []

    def append_row(self, row, **kwargs):
        self.values.append(list(row))


class Book:
    def __init__(self):
        self.tabs = {title:Worksheet() for title in ['FORENSIC_LIVE','OPTION_PREDICTIONS','NEWS_LIVE','HEARTBEAT']}

    def worksheet(self, title):
        if title not in self.tabs:
            raise gspread.WorksheetNotFound(title)
        return self.tabs[title]

    def add_worksheet(self, title, rows, cols):
        self.tabs[title] = Worksheet(int(rows),int(cols))
        return self.tabs[title]


class BQ:
    def __init__(self):
        self.snapshot, self.loads = [], []
        self.fail_load = False

    def dataset(self, name):
        return SimpleNamespace(table=lambda name:name)

    def get_table(self, table):
        return table

    def load_table_from_json(self, rows, table, job_config):
        self.loads.append((table,rows,job_config))
        def result():
            if self.fail_load:
                raise RuntimeError('load unavailable')
            if table == 'option_predictions_live':
                self.snapshot = rows
        return SimpleNamespace(result=result)

    def list_rows(self, table, max_results, page_size):
        return self.snapshot[:max_results]


@pytest.fixture
def authorized(monkeypatch):
    # test isolation only - prod code uses conditional 0/1
    for k,v in {'ALLOW_PRODUCTION_WRITES':'1','WRITER_ID':'market_bot','RUN_ID':'12345','GIT_SHA':'abc123'}.items():
        monkeypatch.setenv(k,v)


def predictions():
    return [defaultdict(lambda:0, symbol=s, rank=i+1, directional_bias='CALL',
                        top_headline='', opt_expiry_date='2026-10-27')
            for i,s in enumerate(verified_symbols())]


def cycle(book, bq):
    preds = predictions()
    recon = dict(cycle=1, hit_rate_pct=0, recall_at_10=0, mean_rank=0)
    forensic = [['2026-10-03 08:00:00',s]+[0]*16 for s in verified_symbols()]
    return publish_outputs(book,bq,'option_predictions_live','2026-10-03 08:00:00',
        lambda:engine.sync_to_google_sheet(preds,recon,forensic,'2026-10-03 08:00:00',sh=book),
        lambda:engine.sync_to_bigquery(preds,[],recon,dt.datetime(2026,10,3,8)))


def test_exact_size_sheet_does_not_clear_outside_grid():
    ws = Worksheet(2,2)
    write_grid(ws,[[1,2],[3,4]])
    assert not ws.cleared


def test_cleanup_is_bounded_and_happens_after_update():
    ws = Worksheet(5,3)
    write_grid(ws,[[1,2],[3,4]])
    assert ws.cleared == ['A3:C5','C1:C2']
    assert ws.events == ['update','cleanup']


def test_sheet_resizes_without_preclear():
    ws = Worksheet(1,1)
    write_grid(ws,[[1,2],[3,4]])
    assert ws.events == ['resize','update']


def test_update_failure_preserves_previous_values():
    ws = Worksheet(3,2)
    ws.values, ws.fail_update = [['previous']], True
    with pytest.raises(RuntimeError):
        write_grid(ws,[[1,2]])
    assert ws.values == [['previous']] and not ws.cleared


def test_cleanup_failure_is_not_success():
    ws = Worksheet(3,2)
    ws.fail_clear = True
    with pytest.raises(RuntimeError,match='cleanup'):
        write_grid(ws,[[1,2]])


def test_authorized_writer_requires_lineage(authorized,monkeypatch):
    monkeypatch.delenv('RUN_ID')
    monkeypatch.delenv('GITHUB_RUN_ID',raising=False)
    with pytest.raises(RuntimeError,match='run_id and git_sha'):
        require_authorized_writer()


def test_complete_cycle_readback_and_load_config(authorized,monkeypatch):
    book,bq = Book(),BQ()
    book.tabs['PRE_BREAKOUT_SCANNER'] = Worksheet()
    monkeypatch.setattr(engine,'get_bigquery_client',lambda:bq)
    identity = cycle(book,bq)
    assert verify_current_publication(book,bq,'option_predictions_live') == identity_subset(identity)
    config = bq.loads[0][2]
    assert config.write_disposition == 'WRITE_TRUNCATE'
    assert not config.schema_update_options
    assert len(bq.snapshot) == 219
    assert all(r['source_timestamp'].endswith('+05:30') for r in bq.snapshot)
    assert all(r['data_freshness_status']=='MARKET_CLOSED' for r in bq.snapshot)
    assert bq.loads[-1][2].schema_update_options == ['ALLOW_FIELD_ADDITION']
    assert ACTIVE_CYCLE.get() is None
    assert 'LEGACY SNAPSHOT' in book.worksheet('PRE_BREAKOUT_SCANNER').values[0][0]


def identity_subset(identity):
    return {k:identity[k] for k in ['cycle_id','run_id','git_sha','writer_id']}


def test_verified_publication_appends_cycle_ledger(authorized,monkeypatch,tmp_path):
    import json
    path = tmp_path / 'cycles.jsonl'
    monkeypatch.setenv('ANGEL_CYCLE_LEDGER_PATH', str(path))
    book,bq = Book(),BQ()
    monkeypatch.setattr(engine,'get_bigquery_client',lambda:bq)
    identity = cycle(book,bq)
    lines = path.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record['cycle_id'] == identity['cycle_id']
    assert record['run_id'] == identity['run_id']
    assert record['status'] == 'VERIFIED'


def test_bq_failure_marks_partial_and_no_false_success(authorized,monkeypatch):
    book,bq = Book(),BQ()
    bq.fail_load=True
    monkeypatch.setattr(engine,'get_bigquery_client',lambda:bq)
    with pytest.raises(RuntimeError,match='BigQuery sync failed'):
        cycle(book,bq)
    assert book.worksheet('PUBLICATION_STATUS').values[1][0] == 'FAILED_PARTIAL'
    assert book.worksheet('OPTION_PREDICTIONS').values[1][6] == 'Publication: PENDING_READBACK'
    with pytest.raises(RuntimeError,match='unverified'):
        verify_current_publication(book,bq,'option_predictions_live')
    assert ACTIVE_CYCLE.get() is None


def test_modified_sheet_after_completion_rejected(authorized,monkeypatch):
    book,bq = Book(),BQ()
    monkeypatch.setattr(engine,'get_bigquery_client',lambda:bq)
    cycle(book,bq)
    book.worksheet('FORENSIC_LIVE').values[1][3] = 99
    with pytest.raises(RuntimeError,match='MIXED_CYCLE'):
        verify_current_publication(book,bq,'option_predictions_live')


def test_bq_mixed_cycle_rejected(authorized,monkeypatch):
    book,bq = Book(),BQ()
    monkeypatch.setattr(engine,'get_bigquery_client',lambda:bq)
    cycle(book,bq)
    bq.snapshot[0]['cycle_id']='other-cycle'
    with pytest.raises(RuntimeError,match='provenance readback mismatch'):
        verify_current_publication(book,bq,'option_predictions_live')


def test_sheet_digest_ignores_only_trailing_blank_cells():
    assert matrix_hash([['x',1,''],[]]) == matrix_hash([['x','1']])
    assert matrix_hash([['x',2]]) != matrix_hash([['x',1]])
    assert matrix_hash([['x',1.0]]) == matrix_hash([['x',1]])


def test_competing_full_universe_write_during_publication_rejected(authorized,monkeypatch):
    book,bq = Book(),BQ()
    monkeypatch.setattr(engine,'get_bigquery_client',lambda:bq)
    original_read = bq.list_rows
    changed = False
    def read_with_competitor(*args, **kwargs):
        nonlocal changed
        if not changed:
            book.worksheet('NEWS_LIVE').values[2][1] = 'COMPETING OUTPUT'
            changed=True
        return original_read(*args, **kwargs)
    bq.list_rows = read_with_competitor
    with pytest.raises(RuntimeError,match='intended output'):
        cycle(book,bq)
    assert book.worksheet('PUBLICATION_STATUS').values[1][0] == 'FAILED_PARTIAL'


def test_holidays_and_utc_session_conversion():
    assert not is_trading_day(dt.datetime(2026,10,2,10))
    assert not is_trading_day(dt.datetime(2026,1,15,10))
    assert engine.is_market_open(dt.datetime(2026,10,5,4,tzinfo=dt.timezone.utc))
    assert not engine.is_pre_market_time(dt.datetime(2026,10,2,8))
    assert not engine.is_pre_close_time(dt.datetime(2026,10,2,15))
    assert not engine.is_morning_reconcile_time(dt.datetime(2026,10,2,9,20))
    with pytest.raises(RuntimeError,match='unreviewed'):
        is_trading_day(dt.datetime(2027,1,4))
