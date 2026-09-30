"""Keep offline tests from publishing fixtures or reaching real services."""
from pathlib import Path
import socket
import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_prediction_state_and_network(monkeypatch, tmp_path):
    engine = sys.modules.get('angel_prediction_engine')
    if engine:
        for name in ('STATE_PATH', 'CALIBRATION_STATE_PATH', 'NSE_CACHE_PATH',
                     'SCRIP_CACHE_PATH', 'NEXT_DAY_GAP_PATH', 'GAP_RECON_HISTORY_PATH'):
            monkeypatch.setattr(engine, name, str(tmp_path / Path(getattr(engine, name)).name))

    def reject_network(*_args, **_kwargs):
        raise AssertionError('Offline tests must not contact external services')

    monkeypatch.setattr(socket.socket, 'connect', reject_network)
    monkeypatch.setattr(socket, 'create_connection', reject_network)
