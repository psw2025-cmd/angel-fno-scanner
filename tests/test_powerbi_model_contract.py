"""Contract tests for the Power BI project (ANGEL_FNO_MONITOR).

These tests read the TMDL/PBIR files only. They do not need Power BI Desktop.
They protect against defects found in the 2026-10-17 production assurance audit
(see audit/powerbi_assurance_20261017):

* Universe Health compared against a stale hard-coded 216 while the engine
  contract is 219.
* Six "Top Gap" measures used a table-valued IF and raised a DAX error on the
  live engine, which broke two visuals on page 6.
* Visual fields that point to a column or measure that does not exist.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import powerbi_assurance_audit as pbi  # noqa: E402
from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT  # noqa: E402

MODEL_DIR = ROOT / "ANGEL_FNO_MONITOR.SemanticModel"
REPORT_DIR = ROOT / "ANGEL_FNO_MONITOR.Report"
MEASURES_FILE = MODEL_DIR / "definition" / "tables" / "_Measures.tmdl"

TOP_GAP_MEASURES = (
    "Top Gap Up Symbol",
    "Top Gap Down Symbol",
    "Top Gap Up Expected %",
    "Top Gap Down Expected %",
    "Top Gap Up Display Safe",
    "Top Gap Down Display Safe",
)


def _measures():
    table = pbi.parse_tmdl_table(MEASURES_FILE)
    return {m["name"]: m for m in table["measures"]}


def test_measures_file_is_ascii():
    data = MEASURES_FILE.read_bytes()
    assert all(b < 128 for b in data), "PM-001: _Measures.tmdl must stay ASCII"


def test_universe_health_matches_engine_contract():
    expr = _measures()["Universe Health"]["expression"]
    numbers = [int(n) for n in re.findall(r"\b(\d{3})\b", expr)]
    assert numbers, "Universe Health must state the expected universe size"
    assert set(numbers) == {EXPECTED_FNO_UNIVERSE_COUNT}, (
        "Universe Health uses %s but universe_contract.EXPECTED_FNO_UNIVERSE_COUNT is %s"
        % (sorted(set(numbers)), EXPECTED_FNO_UNIVERSE_COUNT)
    )


def test_top_gap_measures_do_not_use_table_valued_if():
    measures = _measures()
    bad_pattern = re.compile(r"VAR\s+\w+\s*=\s*IF\(\s*COUNTROWS\([^)]*\)\s*>\s*0\s*,\s*\w+\s*,\s*\w+\s*\)")
    offenders = [n for n, m in measures.items() if bad_pattern.search(m["expression"])]
    assert not offenders, "table-valued IF raised a live-engine error: %s" % offenders


def test_top_gap_measures_use_scalar_has_next_flag():
    measures = _measures()
    for name in TOP_GAP_MEASURES:
        expr = measures[name]["expression"]
        assert "VAR HasNext" in expr, name
        assert "NOT HasNext" in expr, name
        assert 'liquidity_status] = "PASS"' in expr, name


def test_all_visual_fields_resolve_to_model_objects():
    model = pbi.parse_model(MODEL_DIR)
    report = pbi.parse_report(REPORT_DIR)
    columns = {t: {c["name"] for c in tbl["columns"]} for t, tbl in model["tables"].items()}
    measures = {m["name"] for tbl in model["tables"].values() for m in tbl["measures"]}
    unresolved = []
    for v in report["visuals"]:
        for f in v["fields"] + v["filters"]:
            if f["entity"] not in columns:
                unresolved.append((v["id"], f["entity"], f["prop"]))
            elif f["kind"] == "Measure" and f["prop"] not in measures:
                unresolved.append((v["id"], f["entity"], f["prop"]))
            elif f["kind"] == "Column" and f["prop"] not in columns[f["entity"]]:
                unresolved.append((v["id"], f["entity"], f["prop"]))
    assert not unresolved, unresolved


def test_report_has_ten_pages_and_pages_exist_on_disk():
    report = pbi.parse_report(REPORT_DIR)
    assert len(report["pages"]) == 10
    assert all(p["name"] != "MISSING_PAGE_FILE" for p in report["pages"])


def test_embedded_constant_tables_are_declared():
    """Document-by-test: these tables are frozen constants and cannot refresh.

    When they are replaced by live queries (audit action A03) this test must be
    updated deliberately, which forces the lineage CSV to be regenerated.
    """
    model = pbi.parse_model(MODEL_DIR)
    classes = {n: pbi.classify_partition(t)["class"] for n, t in model["tables"].items()}
    for name in ("Heartbeat", "ForensicLive", "CERank", "Calibration"):
        assert classes[name] == "EMBEDDED_STATIC_CONSTANT", name
    for name in ("OptionPredictions", "News"):
        assert classes[name] == "EXTERNAL_HTTP_JSON", name
    for name in ("PaperLog", "SheetNews"):
        assert classes[name] == "GOOGLE_SHEET_GVIZ_CSV", name
