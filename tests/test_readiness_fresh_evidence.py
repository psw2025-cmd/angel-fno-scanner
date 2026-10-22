"""Regression: readiness verification must consume evidence from its own probe."""
import json
from pathlib import Path
from types import SimpleNamespace

from tools import verify_all


def test_readiness_probe_uses_fresh_isolated_evidence(monkeypatch, tmp_path):
    roots = []

    def fake_mkdtemp(*, prefix):
        assert prefix == "angel-readiness-"
        root = tmp_path / ("probe-" + str(len(roots)))
        root.mkdir()
        roots.append(root)
        return str(root)

    def fake_run(cmd, **kwargs):
        root = Path(cmd[cmd.index("--output-root") + 1])
        assert root == roots[-1]
        evidence = root / "INFRA_READY_test"
        evidence.mkdir()
        (evidence / "SYSTEM_STATUS.json").write_text(
            json.dumps({"checks": [{"check": "fresh_probe", "status": "PASS"}]}),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_all.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(verify_all.subprocess, "run", fake_run)
    first = verify_all.run_readiness_probe()
    second = verify_all.run_readiness_probe()
    assert len(roots) == 2 and roots[0] != roots[1]
    for index, result in enumerate((first, second)):
        assert result["status"] == "PASS"
        assert result["checks"]["fresh_probe"] == "PASS"
        assert Path(result["evidence_dir"]).parent == roots[index]
