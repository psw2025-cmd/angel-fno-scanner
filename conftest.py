from __future__ import annotations

import os
import tempfile
import uuid


def pytest_configure(config):
    if config.option.basetemp:
        return
    root = os.environ.get("PYTEST_BASETEMP_ROOT")
    if not root:
        root = r"C:\Temp" if os.name == "nt" else tempfile.gettempdir()
    os.makedirs(root, exist_ok=True)
    config.option.basetemp = os.path.join(root, f"pt-{uuid.uuid4().hex}")

