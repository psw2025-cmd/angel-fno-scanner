from pathlib import Path
import pytest
from tools.atomic_snapshots import publish_bundle

def test_staging_failure_does_not_mix_files(tmp_path):
    stage, final = tmp_path / "stage", tmp_path / "final"
    stage.mkdir(); final.mkdir()
    for name in ("a.json", "b.json"):
        (stage / name).write_text("new")
        (final / name).write_text("old")
    calls = [0]
    def fail_second(src, dst):
        calls[0] += 1
        if calls[0] == 2:
            raise OSError("simulated interrupted publication")
        Path(src).replace(dst)
    with pytest.raises(OSError):
        publish_bundle(stage, final, ("a.json", "b.json"), replace=fail_second)
    assert [(final / n).read_text() for n in ("a.json", "b.json")] == ["old", "old"]

def test_complete_bundle_replaces_all(tmp_path):
    stage, final = tmp_path / "stage", tmp_path / "final"
    stage.mkdir(); final.mkdir()
    for n in ("a.json", "b.json"):
        (stage/n).write_text("new")
        (final/n).write_text("old")
    publish_bundle(stage, final, ("a.json", "b.json"))
    assert [(final/n).read_text() for n in ("a.json", "b.json")] == ["new", "new"]
