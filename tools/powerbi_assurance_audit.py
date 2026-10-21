#!/usr/bin/env python3
"""Power BI production assurance audit generator (READ-ONLY, ASCII-only output).

Parses the Power BI project (PBIP: TMDL semantic model + PBIR report) from this
repository, joins it with raw evidence captured from the running Power BI
Desktop engine and from the upstream sources (GitHub raw JSON, Google Sheet
gviz CSV, BigQuery metadata), and writes the twelve audit CSV files plus
diagram sources.

It never connects to a broker, never writes to any production system and never
modifies the Power BI project. Raw evidence files live in <out>/raw and are
hashed into 11_Evidence_Register.csv.

Usage:
    python tools/powerbi_assurance_audit.py [--out audit/powerbi_assurance_20261017]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from market_calendar import NSE_HOLIDAYS_2026

REPO = Path(__file__).resolve().parent.parent
OUT_DEFAULT = REPO / "audit" / "powerbi_assurance_20261017"
OPENED_PBIP_ROOT = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner")
PBIT_PATH = Path(r"C:\Users\ADMIN\Documents\ANGEL_FNO_MONITOR2.pbit")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
OBSERVED_AT = dt.datetime(2026, 10, 17, 14, 14, 0, tzinfo=IST)
LAST_SESSION_CLOSE = dt.datetime(2026, 10, 16, 15, 30, 0, tzinfo=IST)
OBSERVED_STR = OBSERVED_AT.isoformat()
EXPECTED_UNIVERSE = 219

SOURCE_PRODUCERS = {
    "OptionPredictions": (
        "agent_cli.py snapshot export -> data/latest_predictions.json committed by "
        ".github/workflows/market_bot.yml (github-actions[bot]); engine truth is "
        "angel_prediction_engine.py -> BigQuery option_predictions_live"
    ),
    "News": (
        "agent_cli.py snapshot export -> data/market_news.json committed by "
        ".github/workflows/market_bot.yml (github-actions[bot])"
    ),
    "PaperLog": "angel_prediction_engine.py append to Google Sheet tab PAPER_ALERT_LOG",
    "SheetNews": "angel_prediction_engine.py sync to Google Sheet tab NEWS_LIVE (strict 12 columns)",
    "Heartbeat": "NONE CONNECTED - frozen copy of Sheet tab HEARTBEAT taken 2026-09-29",
    "ForensicLive": "NONE CONNECTED - frozen copy of Sheet tab FORENSIC_LIVE taken 2026-09-29",
    "CERank": "NONE CONNECTED - frozen copy of Sheet tab CE_PE_RANK taken 2026-09-29",
    "Calibration": "NONE CONNECTED - 2 hand-typed rows (BigQuery prediction_calibration_log has 405 rows)",
}
FROZEN_TABLES = {"Heartbeat", "ForensicLive", "CERank", "Calibration"}
AGG_NAMES = {0: "Sum", 1: "Avg", 2: "Count", 3: "Min", 4: "Max", 5: "CountNonNull",
             6: "Median", 7: "StdDev", 8: "Variance"}


# ---------------------------------------------------------------- helpers
def ascii_clean(value) -> str:
    return str("" if value is None else value).encode("ascii", "backslashreplace").decode("ascii")


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def norm_hash(path: Path) -> str:
    return hashlib.sha256(read_text(path).encode("utf-8")).hexdigest()


def write_csv(path: Path, fields, rows) -> None:
    with open(path, "w", newline="", encoding="ascii") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ascii_clean(row.get(k, "")) for k in fields})


def unquote(name: str) -> str:
    name = name.strip()
    if name.startswith("'") and name.endswith("'") and len(name) >= 2:
        return name[1:-1].replace("''", "'")
    return name


def run(cmd, cwd=None) -> str:
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return (res.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001 - evidence collector must never crash
        return "ERR:" + str(exc)


def num(text):
    try:
        return float(str(text).replace(",", "").replace("%", "").replace("+", "").strip())
    except Exception:  # noqa: BLE001
        return None


def parse_ts(text):
    if not text:
        return None
    try:
        t = dt.datetime.fromisoformat(str(text).replace("Z", "+00:00").replace(" ", "T", 1)
                                      if "T" not in str(text) else str(text).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=IST)
    return t


def weekdays_between(a: dt.datetime, b: dt.datetime) -> int:
    d, n = a.date(), 0
    while d < b.date():
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in NSE_HOLIDAYS_2026:
            n += 1
    return n


# ---------------------------------------------------------------- TMDL
def dedent(lines):
    lines = [ln for ln in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    indent = min(len(ln) - len(ln.lstrip("\t")) for ln in lines if ln.strip())
    return "\n".join(ln[indent:] for ln in lines)


def parse_tmdl_table(path: Path) -> dict:
    lines = read_text(path).split("\n")
    table = {"name": None, "file": path.name, "columns": [], "measures": [], "partitions": []}
    blocks, cur = [], None
    for ln in lines:
        if not ln.strip():
            if cur is not None:
                cur["body"].append(ln)
            continue
        tabs = len(ln) - len(ln.lstrip("\t"))
        if tabs == 0:
            if ln.startswith("table "):
                table["name"] = unquote(ln[6:].strip())
            cur = None
        elif tabs == 1:
            cur = {"head": ln.strip(), "body": []}
            blocks.append(cur)
        elif cur is not None:
            cur["body"].append(ln)
    for blk in blocks:
        head, body = blk["head"], blk["body"]
        props = {}
        for ln in body:
            tabs = len(ln) - len(ln.lstrip("\t"))
            if tabs == 2 and ":" in ln and not ln.strip().startswith("source"):
                key, _, val = ln.strip().partition(":")
                props[key.strip()] = val.strip()
        m = re.match(r"^measure\s+('(?:[^']|'')+'|[^\s=]+)\s*=\s*(.*)$", head)
        if m:
            expr_lines = [m.group(2)] if m.group(2).strip() else []
            for ln in body:
                tabs = len(ln) - len(ln.lstrip("\t"))
                if tabs == 2 and ln.strip():
                    break
                expr_lines.append(ln)
            table["measures"].append({
                "name": unquote(m.group(1)),
                "expression": dedent(expr_lines) if len(expr_lines) > 1 else expr_lines[0].strip(),
                "formatString": props.get("formatString", ""),
            })
            continue
        m = re.match(r"^column\s+('(?:[^']|'')+'|\S+)(?:\s*=\s*(.*))?$", head)
        if m:
            table["columns"].append({
                "name": unquote(m.group(1)),
                "dataType": props.get("dataType", ""),
                "sourceColumn": props.get("sourceColumn", ""),
                "summarizeBy": props.get("summarizeBy", ""),
                "formatString": props.get("formatString", ""),
                "hidden": "isHidden" in [ln.strip() for ln in body],
                "calculated": bool(m.group(2)),
            })
            continue
        m = re.match(r"^partition\s+('(?:[^']|'')+'|\S+)\s*=\s*(\w+)", head)
        if m:
            src_lines, in_src = [], False
            for ln in body:
                tabs = len(ln) - len(ln.lstrip("\t"))
                if tabs == 2 and ln.strip().startswith("source"):
                    in_src = True
                    rest = ln.strip()[len("source"):].strip()
                    if rest.startswith("="):
                        rest = rest[1:].strip()
                    if rest:
                        src_lines.append(rest)
                    continue
                if in_src:
                    src_lines.append(ln)
            table["partitions"].append({
                "name": unquote(m.group(1)),
                "kind": m.group(2),
                "mode": props.get("mode", ""),
                "source": dedent(src_lines) if len(src_lines) > 1 else (src_lines[0] if src_lines else ""),
            })
    return table


def classify_partition(table: dict) -> dict:
    out = {"class": "NONE", "locator": "", "embedded_rows": "", "silent_fallback": "NO", "steps": ""}
    if not table["partitions"]:
        return out
    p = table["partitions"][0]
    src = p["source"]
    if p["kind"] == "calculated":
        if "DATATABLE(" in src:
            out["class"] = "EMBEDDED_STATIC_CONSTANT"
            out["embedded_rows"] = str(len(re.findall(r'^\s*\{"', src, flags=re.M)))
            out["locator"] = "DATATABLE literal inside TMDL"
        elif "CALENDAR(" in src.upper():
            out["class"] = "CALCULATED_DATE_TABLE"
            out["locator"] = src.strip().replace("\n", " ")[:120]
        else:
            out["class"] = "CALCULATED_HELPER"
            out["locator"] = src.strip()[:80]
        return out
    m_url = re.search(r'Url\s*=\s*"([^"]+)"', src)
    m_sheet = re.search(r'SheetCsv\("([^"]+)"\s*,\s*"([^"]+)"\)', src)
    if "Web.Contents" in src and m_url:
        out["class"] = "EXTERNAL_HTTP_JSON"
        out["locator"] = m_url.group(1)
    elif m_sheet:
        out["class"] = "GOOGLE_SHEET_GVIZ_CSV"
        out["locator"] = "sheet tab %s range %s" % (m_sheet.group(1), m_sheet.group(2))
    elif "#table(" in src:
        out["class"] = "EMBEDDED_STATIC_CONSTANT"
        out["embedded_rows"] = str(len(re.findall(r'^\s*\{"', src, flags=re.M)))
        out["locator"] = "#table literal inside TMDL"
    else:
        out["class"] = "UNKNOWN_M"
    if re.search(r"try\s+(Web\.Contents|SheetCsv)", src) and "otherwise" in src:
        out["silent_fallback"] = "YES"
    out["steps"] = ">".join(re.findall(r"^\s{4,}(#?\"?\w[\w ]*\"?)\s*=\s", src, flags=re.M))
    return out


def parse_model(model_dir: Path) -> dict:
    definition = model_dir / "definition"
    tables = {}
    for f in sorted((definition / "tables").glob("*.tmdl")):
        t = parse_tmdl_table(f)
        tables[t["name"]] = t
    rel_text = read_text(definition / "relationships.tmdl")
    rels = []
    for blk in re.split(r"\n(?=relationship )", rel_text):
        mf = re.search(r"fromColumn:\s*(\S+)", blk)
        mt = re.search(r"toColumn:\s*(\S+)", blk)
        if mf and mt:
            rels.append({"from": mf.group(1), "to": mt.group(1),
                         "join": (re.search(r"joinOnDateBehavior:\s*(\S+)", blk) or [None, ""])[1]})
    expr_text = read_text(definition / "expressions.tmdl")
    params = []
    for m in re.finditer(r"^expression\s+(\S+)\s*=\s*(.+?)\s+meta\s+\[(.*?)\]", expr_text, flags=re.M):
        params.append({"name": m.group(1), "value": m.group(2).strip(), "meta": m.group(3)})
    funcs = re.findall(r"^expression\s+(\S+)\s*=\s*\n", expr_text, flags=re.M)
    model_text = read_text(definition / "model.tmdl")
    database_text = read_text(definition / "database.tmdl")
    return {"tables": tables, "relationships": rels, "parameters": params, "functions": funcs,
            "model_text": model_text, "database_text": database_text}


def measure_deps(expr: str, table_names, measure_names):
    tables, cols, meas = set(), set(), set()
    for m in re.finditer(r"(?:'([^']+)'|\b([A-Za-z_][A-Za-z0-9_]*))?\[([^\]]+)\]", expr):
        tbl = m.group(1) or m.group(2)
        name = m.group(3)
        if tbl and tbl in table_names:
            tables.add(tbl)
            cols.add("%s[%s]" % (tbl, name))
        elif name in measure_names and not (tbl and tbl in table_names):
            meas.add(name)
    return tables, cols, meas


# ---------------------------------------------------------------- PBIR
def walk_fields(node, role, out, agg=None):
    if isinstance(node, dict):
        if "Aggregation" in node and isinstance(node["Aggregation"], dict):
            agg_fn = AGG_NAMES.get(node["Aggregation"].get("Function"), str(node["Aggregation"].get("Function")))
            walk_fields(node["Aggregation"].get("Expression", {}), role, out, agg_fn)
            return
        for kind in ("Column", "Measure"):
            d = node.get(kind)
            if isinstance(d, dict):
                ent = d.get("Expression", {}).get("SourceRef", {}).get("Entity")
                prop = d.get("Property")
                if ent and prop:
                    out.append({"role": role, "kind": kind, "entity": ent, "prop": prop, "agg": agg or ""})
        for k, v in node.items():
            if k not in ("Column", "Measure"):
                walk_fields(v, role, out, agg)
    elif isinstance(node, list):
        for v in node:
            walk_fields(v, role, out, agg)


def collect_text_runs(node, out):
    if isinstance(node, dict):
        if "textRuns" in node and isinstance(node["textRuns"], list):
            for tr in node["textRuns"]:
                if isinstance(tr, dict) and "value" in tr:
                    out.append(str(tr["value"]))
        for v in node.values():
            collect_text_runs(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_text_runs(v, out)


def literal_title(vj) -> str:
    try:
        t = vj["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]
        return t.strip("'")
    except Exception:  # noqa: BLE001
        return ""


def parse_report(report_dir: Path) -> dict:
    defn = report_dir / "definition"
    meta = json.loads(read_text(defn / "pages" / "pages.json"))
    pages, visuals = [], []
    for idx, pid in enumerate(meta["pageOrder"], 1):
        pdir = defn / "pages" / pid
        if not (pdir / "page.json").exists():
            pages.append({"no": idx, "id": pid, "name": "MISSING_PAGE_FILE", "visuals": 0})
            continue
        pj = json.loads(read_text(pdir / "page.json"))
        vdir = pdir / "visuals"
        count = 0
        for vd in sorted(vdir.iterdir()) if vdir.exists() else []:
            vf = vd / "visual.json"
            if not vf.exists():
                continue
            vj = json.loads(read_text(vf))
            vis = vj.get("visual", {})
            fields = []
            for role, rv in (vis.get("query", {}).get("queryState", {}) or {}).items():
                for proj in rv.get("projections", []):
                    tmp = []
                    walk_fields(proj.get("field", {}), role, tmp)
                    for f in tmp:
                        f["display"] = proj.get("displayName", "")
                    fields.extend(tmp)
            filt = []
            walk_fields(vj.get("filterConfig", {}), "Filter", filt)
            fvals = re.findall(r"'([A-Z_]{4,})'", json.dumps(vj.get("filterConfig", {})))
            texts = []
            collect_text_runs(vis.get("objects", {}), texts)
            title = literal_title(vj) or " ".join(texts)
            vtype = vis.get("visualType") or ("visualGroup" if "visualGroup" in vj else "unknown")
            visuals.append({"page_no": idx, "page_id": pid, "page_name": pj.get("displayName", ""),
                            "id": vj.get("name", vd.name), "type": vtype, "title": title.strip(),
                            "fields": fields, "filters": filt, "filter_values": fvals, "has_filterconfig": "filterConfig" in vj})
            count += 1
        pages.append({"no": idx, "id": pid, "name": pj.get("displayName", ""), "visuals": count})
    return {"pages": pages, "visuals": visuals, "active": meta.get("activePageName", "")}


# ---------------------------------------------------------------- raw evidence
def load_csv(path: Path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        return list(csv.DictReader(fh))


def analyse_raw(raw: Path) -> dict:
    A = {}
    pred = json.loads(read_text(raw / "latest_predictions_json_20261017.json"))
    A["pred_rows"] = len(pred)
    A["pred_symbols"] = len({r.get("symbol") for r in pred})
    ts = sorted({r.get("snapshot_timestamp") for r in pred if r.get("snapshot_timestamp")})
    A["pred_snapshot"] = ts[-1] if ts else ""
    A["pred_snapshot_distinct"] = len(ts)

    def liq(r):
        g = lambda k: (r.get(k) or 0)  # noqa: E731
        if g("ce_oi") <= 0 or g("pe_oi") <= 0 or g("ce_ltp") <= 0 or g("pe_ltp") <= 0:
            return "REJECT"
        for s, l in (("ce_bid_ask_spread", "ce_ltp"), ("pe_bid_ask_spread", "pe_ltp")):
            if r.get(s) is not None and r[s] > r[l] * 0.25:
                return "REJECT"
        return "PASS"

    c = Counter(liq(r) for r in pred)
    A["pred_pass"], A["pred_reject"] = c.get("PASS", 0), c.get("REJECT", 0)
    A["pred_avg_conf"] = round(sum(r["confidence_pct"] for r in pred) / max(1, len(pred)), 4)
    A["pred_max_ce"] = max(r["ce_win_prob"] for r in pred)
    A["pred_max_pe"] = max(r["pe_win_prob"] for r in pred)
    A["pred_max_gap"] = max(r["expected_gap_pct"] for r in pred)
    A["pred_min_gap"] = min(r["expected_gap_pct"] for r in pred)
    A["pred_prob_err"] = sum(1 for r in pred if abs((r.get("ce_win_prob") or 0) + (r.get("pe_win_prob") or 0) - 100) > 0.25)
    news = json.loads(read_text(raw / "market_news_json_20261017.json"))
    A["news_rows"] = len(news)
    A["news_symbols"] = len({r.get("symbol") for r in news})
    A["news_domains"] = len({urllib.parse.urlparse(r.get("source_url") or "").hostname for r in news})
    nts = sorted(r.get("timestamp") for r in news if r.get("timestamp"))
    A["news_latest"] = nts[-1] if nts else ""
    hb = load_csv(raw / "sheet_HEARTBEAT_20261017.csv")
    A["hb_last_ping"] = hb[0].get("Last Ping (IST)", "") if hb else ""
    A["hb_symbols"] = hb[0].get("Auto-Discovered Symbols", "") if hb else ""
    A["hb_engine"] = hb[0].get("Engine Status", "") if hb else ""
    A["hb_age_cell"] = hb[0].get("Seconds Since Last Write", "") if hb else ""
    fl = load_csv(raw / "sheet_FORENSIC_LIVE_20261017.csv")
    A["fl_rows"] = len(fl)
    A["fl_time"] = fl[0].get("Timestamp (IST)", "") if fl else ""

    def top(rows, chg, ltp, oi):
        best = None
        for r in rows:
            v = num(r.get(chg))
            if v is not None and (best is None or v > best[0]):
                best = (v, r.get("Symbol"), num(r.get(ltp)), num(r.get(oi)))
        return best

    A["fl_top_ce"] = top(fl, "CE Chg %", "CE LTP", "CE OI")
    A["fl_top_pe"] = top(fl, "PE Chg %", "PE LTP", "PE OI")
    A["rank_rows"] = len(load_csv(raw / "sheet_CE_PE_RANK_20261017.csv"))
    A["rank_time"] = (load_csv(raw / "sheet_CE_PE_RANK_20261017.csv") or [{}])[0].get(
        next(iter((load_csv(raw / "sheet_CE_PE_RANK_20261017.csv") or [{}])[0].keys()), ""), "")
    A["newslive_rows"] = len(load_csv(raw / "sheet_NEWS_LIVE_20261017.csv"))
    with open(raw / "sheet_PAPER_ALERT_LOG_20261017.csv", newline="", encoding="utf-8-sig", errors="replace") as fh:
        rows = list(csv.reader(fh))
    A["paper_header0"] = rows[0][0][:40] if rows else ""
    A["paper_header_len"] = len(rows[0][0]) if rows else 0
    A["paper_rows"] = max(0, len(rows) - 1)
    bq = {}
    for line in read_text(raw / "bq_query_option_predictions_live_20261017.txt").split("\n"):
        if "=" in line:
            k, _, v = line.partition("=")
            bq[k.strip()] = v.strip()
    A["bq_rows"] = bq.get("rows", "")
    A["bq_syms"] = bq.get("distinct_symbols", "")
    A["bq_snapshot"] = bq.get("max_snapshot_timestamp", "")
    A["bq_tables"] = load_csv(raw / "bq_tables_20261017.csv")
    A["live_measures"] = {r["Measure"]: r for r in load_csv(raw / "live_measure_values_20261017.csv")}
    A["live_parts"] = {r["Name"]: r for r in load_csv(raw / "live_partitions_20261017.csv")}
    A["live_rows"] = {r["Table"]: r["Rows"] for r in load_csv(raw / "live_rowcounts_20261017.csv")}
    A["page_scan"] = {r["Page"]: r for r in load_csv(raw / "pbi_page_error_scan_20261017.csv")}
    A["live_top_pe"] = load_csv(raw / "live_top_pe_20261017.csv")
    A["live_paper"] = (load_csv(raw / "live_paperlog_20261017.csv") or [{}])[0]
    A["runs"] = [ln for ln in read_text(raw / "market_bot_runs_20261017.txt").split("\n") if ln.strip()]
    fw = load_csv(raw / "live_forecast_window_20261017.csv")
    A["fw_total_rows"] = sum(int(r["rows"]) for r in fw)
    A["fw_next_rows"] = sum(int(r["rows"]) for r in fw if r["forecast_window"] == "NEXT_SESSION_ELIGIBLE")
    return A


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--model-ref", default="origin/main", help="git ref holding the model as loaded in Desktop, or WORKTREE")
    args = ap.parse_args()
    out = Path(args.out)
    raw = out / "raw"
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagrams").mkdir(exist_ok=True)

    import io
    import tarfile
    import tempfile

    # Audit the model exactly as it was loaded in Desktop: export from the git ref
    # (default origin/main) so later patches on this branch do not change the findings.
    tmp = Path(tempfile.mkdtemp(prefix="pbi_audit_"))
    if args.model_ref.upper() == "WORKTREE":
        model_root = REPO
    else:
        proc = subprocess.run(["git", "archive", "--format=tar", args.model_ref, "ANGEL_FNO_MONITOR.SemanticModel", "ANGEL_FNO_MONITOR.Report"],
                              cwd=REPO, capture_output=True, timeout=120)
        if proc.returncode != 0:
            print("git archive failed: " + proc.stderr.decode("ascii", "replace"))
            return 2
        with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
            tf.extractall(tmp)
        model_root = tmp
    model = parse_model(model_root / "ANGEL_FNO_MONITOR.SemanticModel")
    report = parse_report(model_root / "ANGEL_FNO_MONITOR.Report")
    branch_measures = {m["name"]: m["expression"] for m in parse_tmdl_table(
        REPO / "ANGEL_FNO_MONITOR.SemanticModel" / "definition" / "tables" / "_Measures.tmdl")["measures"]}
    A = analyse_raw(raw)
    tables = model["tables"]
    table_names = set(tables)
    measures = {}
    for t in tables.values():
        for m in t["measures"]:
            m["table"] = t["name"]
            measures[m["name"]] = m
    measure_names = set(measures)
    src_info = {n: classify_partition(t) for n, t in tables.items()}

    # ---- measure dependency closure
    for m in measures.values():
        m["deps_tables"], m["deps_cols"], m["deps_measures"] = measure_deps(m["expression"], table_names, measure_names)

    def closure(name, seen=None):
        seen = seen or set()
        if name in seen or name not in measures:
            return set(), set()
        seen.add(name)
        t, c = set(measures[name]["deps_tables"]), set(measures[name]["deps_cols"])
        for d in measures[name]["deps_measures"]:
            t2, c2 = closure(d, seen)
            t |= t2
            c |= c2
        return t, c

    for m in measures.values():
        m["base_tables"], m["base_cols"] = closure(m["name"])

    # ---- visual usage per measure / frozen deps
    usage = defaultdict(set)
    for v in report["visuals"]:
        for f in v["fields"] + v["filters"]:
            usage[(f["entity"], f["prop"])].add(v["id"])

    live_m = A["live_measures"]

    def live_status(name):
        r = live_m.get(name)
        if r is None:
            return "NOT_EVALUATED"
        if r.get("Error"):
            return "ERROR"
        return "BLANK" if r.get("Value", "") == "" else "OK"

    # ================================================================ 01 inventory
    inv = []
    n = [0]

    def add_inv(cat, item, locator, size, mtime, h, notes, ev):
        n[0] += 1
        inv.append({"Item_ID": "INV-%03d" % n[0], "Category": cat, "Item": item, "Path_or_Locator": locator,
                    "Size_or_Count": size, "Last_Modified": mtime, "Hash12": h, "Notes": notes, "Evidence_ID": ev})

    procs = json.loads(read_text(raw / "processes_20261017.json"))
    if isinstance(procs, dict):
        procs = [procs]
    for p in procs:
        add_inv("RUNTIME_PROCESS", p["Name"], "PID %s parent %s" % (p["ProcessId"], p["ParentProcessId"]), "",
                p["CreationDateIST"], "", ascii_clean(p["CommandLine"])[:240], "E-01")
    add_inv("RUNTIME_PORT", "msmdsrv listener", "127.0.0.1:59161 and ::1:59161 (owner PID 11740)", "", "", "",
            "Local Analysis Services workspace behind the open report", "E-01")
    roots = []
    for base in (Path(r"C:\AngelFNO_Workstation"),):
        try:
            for dirpath, dirnames, filenames in __import__("os").walk(base):
                dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv")]
                if "ANGEL_FNO_MONITOR.pbip" in filenames:
                    roots.append(Path(dirpath))
        except Exception:  # noqa: BLE001
            pass
    groups = defaultdict(list)
    for r in sorted(roots):
        sm = r / "ANGEL_FNO_MONITOR.SemanticModel" / "definition"
        if not sm.exists():
            continue
        digest = hashlib.sha256("".join(norm_hash(f) for f in sorted(sm.rglob("*")) if f.is_file()).encode()).hexdigest()[:12]
        groups[digest].append(r)
    for digest, paths in groups.items():
        opened = any(str(p).lower() == str(OPENED_PBIP_ROOT).lower() for p in paths)
        add_inv("PBIP_CONTENT_GROUP", "PBIP semantic-model content hash " + digest, "%d copies" % len(paths), len(paths), "",
                digest, ("CONTAINS the copy currently open in Power BI Desktop. " if opened else "") + "e.g. " + str(paths[0]), "E-02")
    add_inv("OPENED_PROJECT", "ANGEL_FNO_MONITOR.pbip (open in Desktop)", str(OPENED_PBIP_ROOT / "ANGEL_FNO_MONITOR.pbip"), "", "", "",
            "Title bar: Last saved 9/30/2026 4:51 AM", "E-12")
    if PBIT_PATH.exists():
        add_inv("PBIT_TEMPLATE", "ANGEL_FNO_MONITOR2.pbit", str(PBIT_PATH), PBIT_PATH.stat().st_size,
                dt.datetime.fromtimestamp(PBIT_PATH.stat().st_mtime, IST).isoformat(), sha256_file(PBIT_PATH)[:12],
                "Stale template from 2026-09-30; compared below", "E-15")
    for name, t in tables.items():
        s = src_info[name]
        add_inv("MODEL_TABLE", name, s["class"] + " | " + s["locator"], "%d cols / %d measures" % (len(t["columns"]), len(t["measures"])),
                "", "", "Live rows: %s" % A["live_rows"].get(name, "n/a"), "E-03")
    add_inv("REPORT", "ANGEL_FNO_MONITOR.Report (PBIR)", "%d pages / %d visuals" % (len(report["pages"]), len(report["visuals"])), len(report["visuals"]),
            "", "", "Pages: " + "; ".join(p["name"] for p in report["pages"]), "E-14")
    for label, fname, ev in (("GitHub raw latest_predictions.json", "latest_predictions_json_20261017.json", "E-06"),
                             ("GitHub raw market_news.json", "market_news_json_20261017.json", "E-07"),
                             ("Sheet HEARTBEAT", "sheet_HEARTBEAT_20261017.csv", "E-08"),
                             ("Sheet FORENSIC_LIVE", "sheet_FORENSIC_LIVE_20261017.csv", "E-08"),
                             ("Sheet CE_PE_RANK", "sheet_CE_PE_RANK_20261017.csv", "E-08"),
                             ("Sheet NEWS_LIVE", "sheet_NEWS_LIVE_20261017.csv", "E-08"),
                             ("Sheet PAPER_ALERT_LOG", "sheet_PAPER_ALERT_LOG_20261017.csv", "E-08")):
        add_inv("UPSTREAM_SOURCE", label, "raw/" + fname, (raw / fname).stat().st_size, OBSERVED_STR, sha256_file(raw / fname)[:12], "Fetched anonymously (HTTP 200, no credentials)", ev)
    for bt in A["bq_tables"]:
        if bt["Table"] in ("option_predictions_live", "next_day_gap_predictions", "market_news_sentiment", "prediction_calibration_log"):
            add_inv("UPSTREAM_BIGQUERY", "fno_predictions." + bt["Table"], "BigQuery table", bt["Rows"], bt["LastModifiedUTC"] + "Z", "", "Age hours %s at query time" % bt["AgeHours"], "E-09")
    for label, path in (("Local repo (opened by Desktop)", OPENED_PBIP_ROOT), ("Audit worktree", REPO)):
        add_inv("REPOSITORY", label, str(path), "", "", "", "branch=" + run(["git", "branch", "--show-current"], cwd=path), "E-16")
    write_csv(out / "01_Inventory.csv", ["Item_ID", "Category", "Item", "Path_or_Locator", "Size_or_Count", "Last_Modified", "Hash12", "Notes", "Evidence_ID"], inv)

    # ================================================================ 02 model
    mrows = []
    for key in ("compatibilityLevel",):
        m = re.search(key + r":\s*(\S+)", model["database_text"])
        mrows.append({"Object_Type": "MODEL_SETTING", "Object": key, "Detail": m.group(1) if m else "", "Evidence_ID": "E-14"})
    for k in ("culture", "defaultPowerBIDataSourceVersion", "sourceQueryCulture"):
        m = re.search(k + r":\s*(\S+)", model["model_text"])
        mrows.append({"Object_Type": "MODEL_SETTING", "Object": k, "Detail": m.group(1) if m else "", "Evidence_ID": "E-14"})
    for p in model["parameters"]:
        mrows.append({"Object_Type": "PARAMETER", "Object": p["name"], "Detail": p["value"], "Notes": "Power Query parameter; not user-visible in report", "Evidence_ID": "E-14"})
    for f in model["functions"]:
        mrows.append({"Object_Type": "POWER_QUERY_FUNCTION", "Object": f, "Detail": "Google gviz CSV loader (anonymous HTTP)", "Evidence_ID": "E-14"})
    for rel in model["relationships"]:
        mrows.append({"Object_Type": "RELATIONSHIP", "Object": rel["from"] + " -> " + rel["to"], "Detail": "join=" + rel["join"],
                      "Notes": "Only relationship in the model; all other tables are isolated (no cross-filtering)", "Evidence_ID": "E-14"})
    for name, t in tables.items():
        s = src_info[name]
        lp = A["live_parts"].get(name) or A["live_parts"].get(name + "_Partition") or {}
        mrows.append({"Object_Type": "TABLE", "Table": name, "Object": name, "Source_Class": s["class"], "Source_Locator": s["locator"],
                      "Embedded_Rows": s["embedded_rows"], "Silent_Fallback": s["silent_fallback"], "Live_RefreshedTime": lp.get("RefreshedTime", ""),
                      "Live_Rows": A["live_rows"].get(name, ""), "Detail": "PQ steps: " + s["steps"][:200], "Evidence_ID": "E-03"})
        for c in t["columns"]:
            risk = ""
            if c["summarizeBy"] in ("sum", "average") and re.search(r"(pct|ltp|prob|score|rate|gap|iv|delta|gamma|spread|pcr)", c["name"]):
                risk = "Default aggregation %s on a non-additive field (totals can mislead)" % c["summarizeBy"]
            mrows.append({"Object_Type": "COLUMN", "Table": name, "Object": c["name"], "Data_Type": c["dataType"],
                          "Detail": "summarizeBy=%s src=%s" % (c["summarizeBy"], c["sourceColumn"]), "Notes": risk, "Evidence_ID": "E-14"})
    write_csv(out / "02_PowerBI_Model.csv", ["Object_Type", "Table", "Object", "Data_Type", "Source_Class", "Source_Locator", "Embedded_Rows",
                                             "Silent_Fallback", "Live_RefreshedTime", "Live_Rows", "Detail", "Notes", "Evidence_ID"], mrows)

    # ================================================================ 03 measures
    drows = []
    for name, m in sorted(measures.items()):
        expr = m["expression"]
        flags = []
        if re.search(r"\b216\b", expr):
            flags.append("HARDCODED_UNIVERSE_216_VS_219")
        if re.search(r"VAR\s+\w+\s*=\s*IF\(\s*COUNTROWS\([^)]*\)\s*>\s*0\s*,\s*\w+\s*,\s*\w+\s*\)", expr):
            flags.append("TABLE_VALUED_IF_PATTERN")
        if "Actionable" in name and not re.search(r"(ltp|_oi|spread|volume)", expr, flags=re.I):
            flags.append("NO_LIQUIDITY_OR_PENNY_GATE")
        if name == "Timestamp Safety Status":
            flags.append("WEAK_ASSURANCE_LABEL")
        if not m["base_cols"] and not m["deps_measures"] and expr.startswith('"'):
            flags.append("STATIC_STRING")
        if expr.strip() == "BLANK()":
            flags.append("CONSTANT_BLANK")
        frozen = sorted(t for t in m["base_tables"] if t in FROZEN_TABLES)
        if frozen:
            flags.append("DEPENDS_ON_FROZEN_TABLE:" + "+".join(frozen))
        ls = live_status(name)
        if ls == "ERROR":
            flags.append("LIVE_ENGINE_ERROR")
        if ls == "BLANK":
            flags.append("LIVE_BLANK")
        used = len(usage.get(("_Measures", name), []))
        r = live_m.get(name, {})
        patched = "PATCHED_ON_BRANCH" if (name in branch_measures and branch_measures[name].strip() != expr.strip()) else ""
        drows.append({"Measure": name, "Branch_Status": patched, "Format": m["formatString"], "Expression": expr.replace("\n", " ").replace("\t", " ")[:600],
                      "Base_Tables": "+".join(sorted(m["base_tables"])), "Base_Columns": "+".join(sorted(m["base_cols"]))[:300],
                      "Depends_On_Measures": "+".join(sorted(m["deps_measures"])), "Used_In_Visuals": used,
                      "Live_Value_20261017": (r.get("Value", "") or "")[:80], "Live_Error": (r.get("Error", "") or "")[:140],
                      "Live_Status": ls, "Defect_Flags": ";".join(flags), "Evidence_ID": "E-05"})
    write_csv(out / "03_DAX_Measures.csv", ["Measure", "Branch_Status", "Format", "Expression", "Base_Tables", "Base_Columns", "Depends_On_Measures", "Used_In_Visuals",
                                            "Live_Value_20261017", "Live_Error", "Live_Status", "Defect_Flags", "Evidence_ID"], drows)

    # ================================================================ 04 visuals + 05 lineage
    vrows, lrows = [], []
    unresolved = []
    err_measures = {n for n in measures if live_status(n) == "ERROR"}
    for v in report["visuals"]:
        refs = v["fields"]
        ms = sorted({f["prop"] for f in refs if f["kind"] == "Measure"})
        cs = sorted({"%s[%s]" % (f["entity"], f["prop"]) for f in refs if f["kind"] == "Column"})
        base_tables = set(f["entity"] for f in refs if f["kind"] == "Column")
        for mname in ms:
            base_tables |= measures.get(mname, {}).get("base_tables", set())
        flags = []
        frozen = sorted(t for t in base_tables if t in FROZEN_TABLES)
        if frozen:
            flags.append("FROZEN_TABLE:" + "+".join(frozen))
        broken = sorted(m for m in ms if m in err_measures)
        if broken:
            flags.append("LIVE_MEASURE_ERROR:" + "+".join(broken))
        for f in refs + v["filters"]:
            ok = (f["entity"] in tables and (f["prop"] in measures if f["kind"] == "Measure" else any(c["name"] == f["prop"] for c in tables[f["entity"]]["columns"])))
            if not ok:
                unresolved.append((v["id"], f["entity"], f["prop"]))
                flags.append("UNRESOLVED_FIELD:%s.%s" % (f["entity"], f["prop"]))
        if v["type"] not in ("textbox", "shape", "actionButton", "image", "visualGroup") and not refs:
            flags.append("EMPTY_PLACEHOLDER_NO_FIELDS_BOUND")
        if "NEXT_SESSION_ELIGIBLE" in v.get("filter_values", []) and A["fw_next_rows"] == 0:
            flags.append("FILTER_YIELDS_ZERO_ROWS:forecast_window=NEXT_SESSION_ELIGIBLE(0 of %d rows)" % A["fw_total_rows"])
        for f in refs:
            if f["kind"] == "Column" and f["agg"] in ("Sum",) and re.search(r"(pct|ltp|prob|rate|gap|score|iv|spread|pcr)", f["prop"]):
                flags.append("SUM_OF_NON_ADDITIVE:" + f["prop"])
                break
        page_scan = A["page_scan"].get(v["page_name"], {})
        vrows.append({"Page_No": v["page_no"], "Page_Name": v["page_name"], "Visual_ID": v["id"], "Visual_Type": v["type"],
                      "Title_or_Text": v["title"][:100], "Measures": "+".join(ms), "Columns": "+".join(cs)[:300],
                      "Tables": "+".join(sorted(base_tables)), "Has_Visual_Filters": "YES" if v["filters"] else "NO",
                      "Page_Live_Error_Cards": page_scan.get("FixThisButtons", ""), "Defect_Flags": ";".join(dict.fromkeys(flags)), "Evidence_ID": "E-12;E-14"})
        seen = set()
        for f in refs:
            key = (f["kind"], f["entity"], f["prop"], f["role"])
            if key in seen:
                continue
            seen.add(key)
            if f["kind"] == "Measure":
                m = measures.get(f["prop"])
                tbls = sorted(m["base_tables"]) if m else []
                chain = "measure %s -> cols %s" % (f["prop"], "+".join(sorted(m["base_cols"]))[:200] if m else "UNRESOLVED")
                status = live_status(f["prop"])
            else:
                tbls, chain, status = [f["entity"]], "column %s[%s]" % (f["entity"], f["prop"]), "COLUMN"
            for t in tbls or ["(none: constant measure)"]:
                s = src_info.get(t, {"class": "N/A", "locator": ""})
                lp = A["live_parts"].get(t) or A["live_parts"].get(t + "_Partition") or {}
                verdict = ("BROKEN_LIVE_ERROR" if status == "ERROR" else
                           "FROZEN_NOT_REFRESHABLE" if t in FROZEN_TABLES else
                           "STALE_DATA_LOADED" if lp.get("RefreshedTime", "").startswith("29/09/2026") else
                           "CONSTANT_NO_LINEAGE" if t.startswith("(none") else "TRACEABLE")
                lrows.append({"Level": "VISUAL_FIELD", "Page": v["page_name"], "Visual_ID": v["id"], "Visual_Type": v["type"],
                              "Field_Role": f["role"], "Field": "%s.%s%s" % (f["entity"], f["prop"], (" (" + f["agg"] + ")") if f["agg"] else ""),
                              "Field_Kind": f["kind"], "Measure_Live_Status": status if f["kind"] == "Measure" else "", "Chain": chain,
                              "Table": t, "Source_Class": s["class"], "Source_Locator": s["locator"],
                              "Upstream_Producer": SOURCE_PRODUCERS.get(t, ""), "Live_Partition_RefreshedTime": lp.get("RefreshedTime", ""),
                              "Lineage_Verdict": verdict, "Evidence_ID": "E-03;E-05;E-14"})
    # table-level chain rows (Source -> ETL -> Power Query -> Model -> Measure -> Visual -> Dashboard)
    tbl_visuals = defaultdict(set)
    tbl_measures = defaultdict(set)
    for m in measures.values():
        for t in m["base_tables"]:
            tbl_measures[t].add(m["name"])
    for v in report["visuals"]:
        tb = set(f["entity"] for f in v["fields"] if f["kind"] == "Column")
        for f in v["fields"]:
            if f["kind"] == "Measure" and f["prop"] in measures:
                tb |= measures[f["prop"]]["base_tables"]
        for t in tb:
            tbl_visuals[t].add(v["id"])
    for name, t in tables.items():
        if name.startswith(("DateTableTemplate", "LocalDateTable")) or name == "_Measures":
            continue
        s = src_info[name]
        lp = A["live_parts"].get(name) or A["live_parts"].get(name + "_Partition") or {}
        lrows.insert(0, {"Level": "TABLE_CHAIN", "Table": name, "Source_Class": s["class"], "Source_Locator": s["locator"],
                         "Upstream_Producer": SOURCE_PRODUCERS.get(name, ""),
                         "Chain": "SOURCE -> ETL(PowerQuery steps: %s) -> MODEL table %s (%d cols) -> %d measures -> %d visuals -> %d pages" % (
                             (s["steps"] or "n/a")[:120], name, len(t["columns"]), len(tbl_measures[name]), len(tbl_visuals[name]),
                             len({v["page_no"] for v in report["visuals"] if v["id"] in tbl_visuals[name]})),
                         "Live_Partition_RefreshedTime": lp.get("RefreshedTime", ""),
                         "Lineage_Verdict": "FROZEN_NOT_REFRESHABLE" if name in FROZEN_TABLES else "STALE_DATA_LOADED", "Evidence_ID": "E-03;E-14"})
    write_csv(out / "04_Visual_Inventory.csv", ["Page_No", "Page_Name", "Visual_ID", "Visual_Type", "Title_or_Text", "Measures", "Columns", "Tables",
                                                "Has_Visual_Filters", "Page_Live_Error_Cards", "Defect_Flags", "Evidence_ID"], vrows)
    write_csv(out / "05_Lineage.csv", ["Level", "Page", "Visual_ID", "Visual_Type", "Field_Role", "Field", "Field_Kind", "Measure_Live_Status", "Chain", "Table",
                                       "Source_Class", "Source_Locator", "Upstream_Producer", "Live_Partition_RefreshedTime", "Lineage_Verdict", "Evidence_ID"], lrows)

    # ================================================================ 06 reconciliation
    def lm(name):
        return (live_m.get(name, {}).get("Value", "") or "")

    pred_ts = parse_ts(A["pred_snapshot"])
    rec = []

    def add_rec(metric, model_val, src_val, src_name, status, why, ev):
        rec.append({"Recon_ID": "REC-%02d" % (len(rec) + 1), "Metric": metric, "Power_BI_Live_Model": model_val, "Independent_Source_Value": src_val,
                    "Independent_Source": src_name, "Status": status, "Explanation": why, "Evidence_ID": ev})

    add_rec("Universe symbol count (rows)", A["live_rows"].get("OptionPredictions"), A["bq_rows"] + " (BQ) / " + str(A["pred_rows"]) + " (GitHub JSON) / " + str(A["fl_rows"]) + " (Sheet FORENSIC_LIVE)",
            "BigQuery + GitHub + Sheet", "FAIL", "Model holds 171 rows; all three independent sources hold 219; engine contract EXPECTED_FNO_UNIVERSE_COUNT=219", "E-03;E-06;E-08;E-09")
    add_rec("Universe Health measure", lm("Universe Health"), "PASS expected only if distinct symbols == 219", "universe_contract.py", "FAIL",
            "Measure literal is 216 (stale). It can never say PASS against a 219-symbol universe, and today shows FAIL because the loaded model is incomplete", "E-05;E-13")
    add_rec("Latest model snapshot", lm("Latest Model Snapshot IST"), A["pred_snapshot"] + " (GitHub JSON) ; BQ " + A["bq_snapshot"], "GitHub JSON + BigQuery", "FAIL",
            "Loaded snapshot is 2026-09-29. GitHub JSON is 2026-10-09; BQ table was modified 2026-10-16 18:11 UTC", "E-03;E-06;E-09")
    add_rec("Liquidity PASS / REJECT", "%s / %s (sum %d = rows 171: internally consistent)" % (lm("Liquidity PASS Count"), lm("Liquidity REJECT Count"), int(lm("Liquidity PASS Count") or 0) + int(lm("Liquidity REJECT Count") or 0)),
            "%d / %d recomputed from current GitHub JSON with the same rule" % (A["pred_pass"], A["pred_reject"]), "GitHub JSON (DAX rule re-implemented in Python)", "STALE",
            "Internal arithmetic is correct; the values differ only because the loaded data is old", "E-05;E-06")
    add_rec("Average confidence %", lm("Average Confidence %")[:7], str(A["pred_avg_conf"]), "GitHub JSON", "STALE", "Same rule; different snapshot", "E-05;E-06")
    add_rec("Top model CE / PE probability", "%s / %s" % (lm("Top Model CE Probability"), lm("Top Model PE Probability")), "%s / %s" % (A["pred_max_ce"], A["pred_max_pe"]), "GitHub JSON", "STALE", "Different snapshot", "E-05;E-06")
    add_rec("Largest expected gap up / down", "%s / %s" % (lm("Largest Expected Gap Up %"), lm("Largest Expected Gap Down %")), "%s / %s" % (A["pred_max_gap"], A["pred_min_gap"]), "GitHub JSON", "STALE", "Different snapshot", "E-05;E-06")
    add_rec("Probability error count (CE+PE != 100)", "blank (safe variant = %s)" % lm("Probability Error Count Safe"), str(A["pred_prob_err"]), "GitHub JSON", "PASS", "Both zero; unsafe measure shows blank instead of 0 on page 1/9", "E-05;E-06")
    add_rec("Top gap-up / gap-down symbol", "ERROR (measure fails on live engine)", "Fixed measure returns KALYANKJIL / BAJFINANCE on the loaded rows; independent TOPN recompute agrees", "Live engine DEFINE MEASURE test", "FAIL", "6 measures use a table-valued IF and throw an error; two visuals on page 6 render error cards", "E-05;E-17")
    add_rec("News rows / symbols / domains", "%s / %s / %s" % (lm("News Rows"), lm("News Symbols"), lm("Independent News Domains")), "%d / %d / %d (GitHub market_news.json); NEWS_LIVE sheet %d rows" % (A["news_rows"], A["news_symbols"], A["news_domains"], A["newslive_rows"]),
            "GitHub JSON + Sheet", "PARTIAL", "Row count matches (50); symbols/domains differ; news file latest item " + A["news_latest"], "E-05;E-07;E-08")
    add_rec("ForensicLive rows / latest time", "%s rows / %s" % (A["live_rows"].get("ForensicLive"), lm("Latest Forensic Time")), "%d rows / %s (Sheet FORENSIC_LIVE)" % (A["fl_rows"], A["fl_time"]), "Google Sheet", "FAIL", "Embedded 29-Sep constant (216 rows) vs live 219 rows from 16-Oct", "E-03;E-08")
    top = A["fl_top_pe"]
    add_rec("Top real PE (symbol / % / LTP / OI)", "KFINTECH / 9900 / LTP 5.0 / OI 6900 (frozen)", "%s / %s / LTP %s / OI %s (current sheet)" % (top[1], top[0], top[2], top[3]) if top else "n/a", "Google Sheet", "FAIL",
            "Dashboard leader is a frozen 29-Sep raw value labelled 'real'; no liquid/executable winner is displayed", "E-05;E-08;E-12")
    add_rec("Page 6 chart and detail table rows", "0 rows (visual filter forecast_window = NEXT_SESSION_ELIGIBLE)", "%d of %d loaded rows are NEXT_SESSION_ELIGIBLE" % (A["fw_next_rows"], A["fw_total_rows"]), "Live engine", "PASS_BY_DESIGN",
            "Empty is the honest result for the loaded data; the problem is the LIVE wording on the status card and the stale data", "E-12;E-14")
    add_rec("CE_PE_RANK rows / session", "%s rows / all MARKET CLOSED (frozen)" % A["live_rows"].get("CERank"), "%d rows (Sheet CE_PE_RANK, 219 expected)" % (A["rank_rows"]), "Google Sheet", "FAIL", "Frozen constant; live tab itself holds 216 not 219 rows (tracker item)", "E-03;E-08")
    add_rec("Heartbeat symbols / writer age / cycle", "216 / 0 s / Cycle #228 (frozen 2026-09-29 22:54)", "%s / cell=%s / %s / last ping %s" % (A["hb_symbols"], A["hb_age_cell"], A["hb_engine"].split("|")[-1].strip(), A["hb_last_ping"]), "Google Sheet", "FAIL",
            "Dashboard shows HEALTHY and 0 s writer age from a constant. Independent age (now - last ping) is about 14.6 h (market closed Saturday)", "E-05;E-08;E-12")
    add_rec("PaperLog rows / session range", "%s rows / %s to %s" % (A["live_rows"].get("PaperLog"), A["live_paper"].get("min_sess", ""), A["live_paper"].get("max_sess", "")), "%d data rows (Sheet PAPER_ALERT_LOG); header mangled by gviz" % A["paper_rows"], "Google Sheet", "FAIL",
            "Loaded 29-Sep copy; current gviz response merges row values into the header label, so a refresh will not match the Rename step (columns become null)", "E-03;E-08;E-18")
    add_rec("PaperLog totals", "Sum Fut LTP %s ; Sum session %% %s" % (A["live_paper"].get("sum_fut", ""), A["live_paper"].get("sum_pct", "")), "Totals of prices and percentages have no meaning", "Method review", "FAIL", "Total row on page 10 table adds LTPs and percentages", "E-12;E-14")
    add_rec("Calibration table", "%s rows (100%% hit rate)" % A["live_rows"].get("Calibration"), "%s rows in BQ prediction_calibration_log" % next((b["Rows"] for b in A["bq_tables"] if b["Table"] == "prediction_calibration_log"), "n/a"), "BigQuery", "FAIL",
            "Two hand-typed rows displayed as KPI. Title says NOT FORWARD ACCURACY, which is honest, but the numbers are not from the calibration log", "E-03;E-09")
    add_rec("Forward accuracy KPI", lm("Forward Accuracy %") or "BLANK", "No forward outcomes qualify (forward_accuracy_eligible=false for every row)", "PaperLog M step", "PASS", "Honest: blank, with a BLOCKED/PENDING label (AGENTS section 22)", "E-05;E-14")
    write_csv(out / "06_Reconciliation.csv", ["Recon_ID", "Metric", "Power_BI_Live_Model", "Independent_Source_Value", "Independent_Source", "Status", "Explanation", "Evidence_ID"], rec)

    # ================================================================ 08 freshness
    def age_h(ts):
        return round((OBSERVED_AT - ts).total_seconds() / 3600.0, 1) if ts else ""

    def lag(ts):
        return weekdays_between(ts, LAST_SESSION_CLOSE) if ts else ""

    fres = []

    def add_fr(src, ts, ts_note, ev, sla="covers last session (2026-10-16) while market is closed"):
        a = age_h(ts)
        sessions = lag(ts) if ts else ""
        if ts is None:
            status = "UNKNOWN"
        elif ts >= LAST_SESSION_CLOSE:
            status = "LAST_PRINT_OK"
        else:
            status = "STALE"
        fres.append({"Source": src, "Source_Timestamp_IST": ts.isoformat() if ts else "", "Timestamp_Note": ts_note, "Observed_At_IST": OBSERVED_STR,
                     "Independent_Age_Hours": a, "Weekdays_Behind": sessions, "SLA_Applied": sla, "Status": status, "Evidence_ID": ev})

    pm = {}
    for k, r in A["live_parts"].items():
        pm[k] = parse_ts(dt.datetime.strptime(r["RefreshedTime"], "%d/%m/%Y %I:%M:%S %p").isoformat()) if r.get("RefreshedTime") else None
    for t in ("OptionPredictions", "News", "PaperLog", "SheetNews", "Calibration"):
        add_fr("Power BI model partition " + t, pm.get(t), "Partition RefreshedTime from live engine", "E-03")
    for t in ("Heartbeat_Partition", "ForensicLive_Partition", "CERank_Partition"):
        add_fr("Power BI model partition " + t.replace("_Partition", "") + " (embedded constant)", pm.get(t), "Last time the constant was pasted into the model; cannot refresh", "E-03")
    add_fr("Open report file (last saved)", dt.datetime(2026, 9, 30, 4, 51, tzinfo=IST), "Desktop title bar", "E-12")
    add_fr("GitHub data/latest_predictions.json", pred_ts.astimezone(IST) if pred_ts else None, "snapshot_timestamp field, tz semantics NOT PROVEN (UTC label)", "E-06")
    add_fr("GitHub data/market_news.json (latest item)", parse_ts(A["news_latest"]).astimezone(IST) if parse_ts(A["news_latest"]) else None, "max item timestamp", "E-07")
    git_last = run(["git", "log", "origin/main", "-1", "--format=%cI", "--", "data/latest_predictions.json"], cwd=REPO)
    add_fr("GitHub data/latest_predictions.json (last bot commit)", parse_ts(git_last).astimezone(IST) if parse_ts(git_last) else None, "git commit date of the file on origin/main", "E-10")
    add_fr("Google Sheet HEARTBEAT last ping", parse_ts(A["hb_last_ping"]), "Last Ping (IST) cell", "E-08")
    add_fr("Google Sheet FORENSIC_LIVE", parse_ts(A["fl_time"]), "Timestamp (IST) of first row", "E-08")
    bqrow = next((b for b in A["bq_tables"] if b["Table"] == "option_predictions_live"), None)
    if bqrow:
        add_fr("BigQuery option_predictions_live (table Modified)", parse_ts(bqrow["LastModifiedUTC"].replace(" ", "T") + ":00+00:00").astimezone(IST), "Table metadata lastModifiedTime (authoritative)", "E-09")
    bq_col = parse_ts(A["bq_snapshot"].replace(" ", "T").replace("+00", "+00:00")).astimezone(IST)
    fres.append({"Source": "BigQuery option_predictions_live snapshot_timestamp column", "Source_Timestamp_IST": bq_col.isoformat(),
                 "Timestamp_Note": "Read as UTC this is 2026-10-17 05:10 IST, which is AFTER the table was last modified (2026-10-16 23:41 IST): IST wall-clock labelled UTC",
                 "Observed_At_IST": OBSERVED_STR, "Independent_Age_Hours": age_h(bq_col), "Weekdays_Behind": "", "SLA_Applied": "AGENTS section 24 timezone standard",
                 "Status": "TIMEZONE_DEFECT_FUTURE_DATED", "Evidence_ID": "E-09"})
    for line in A["runs"][:1]:
        parts = line.split()
        add_fr("GitHub workflow market_bot.yml (latest run, %s)" % parts[3], parse_ts(parts[1]).astimezone(IST), "Last run of the workflow that commits data/*.json", "E-11")
    fres.append({"Source": "Heartbeat 'Seconds Since Last Write' cell", "Source_Timestamp_IST": "", "Timestamp_Note": "Stored value %s; independent age = now - last ping = %s h" % (A["hb_age_cell"], age_h(parse_ts(A["hb_last_ping"]))),
                 "Observed_At_IST": OBSERVED_STR, "Independent_Age_Hours": age_h(parse_ts(A["hb_last_ping"])), "Weekdays_Behind": "", "SLA_Applied": "AGENTS section 12: never trust a stored 0s",
                 "Status": "UNTRUSTWORTHY_CELL", "Evidence_ID": "E-08"})
    write_csv(out / "08_Data_Freshness.csv", ["Source", "Source_Timestamp_IST", "Timestamp_Note", "Observed_At_IST", "Independent_Age_Hours", "Weekdays_Behind", "SLA_Applied", "Status", "Evidence_ID"], fres)

    # ================================================================ 07 repo audit
    repo = []

    def add_repo(area, finding, observed, expected, status, ev):
        repo.append({"Check_ID": "REPO-%02d" % (len(repo) + 1), "Area": area, "Finding": finding, "Observed": observed, "Expected": expected, "Status": status, "Evidence_ID": ev})

    main_sha = run(["git", "rev-parse", "origin/main"], cwd=REPO)
    opened_branch = run(["git", "branch", "--show-current"], cwd=OPENED_PBIP_ROOT)
    behind = run(["git", "rev-list", "--count", "HEAD..origin/main"], cwd=OPENED_PBIP_ROOT)
    dirty = len([ln for ln in run(["git", "status", "--short"], cwd=OPENED_PBIP_ROOT).split("\n") if ln.strip()])
    add_repo("Provenance", "origin/main SHA at audit time", main_sha, "recorded", "INFO", "E-16")
    add_repo("Authority", "Repo opened by Power BI Desktop", "%s on branch %s, %s commits behind main, %d dirty/untracked entries" % (OPENED_PBIP_ROOT, opened_branch, behind, dirty), "clean checkout of main", "RISK", "E-16")
    same = []
    for sub in ("ANGEL_FNO_MONITOR.SemanticModel", "ANGEL_FNO_MONITOR.Report"):
        base = model_root / sub
        for f in base.rglob("*"):
            if f.is_file() and ".pbi" not in f.parts:
                o = OPENED_PBIP_ROOT / f.relative_to(model_root)
                same.append(o.exists() and norm_hash(o) == norm_hash(f))
    add_repo("Authority", "Opened copy vs main model/report content (line endings normalised)", "%d/%d files identical" % (sum(same), len(same)), "all identical", "PASS" if same and all(same) else "FAIL", "E-02")
    add_repo("Sprawl", "Number of PBIP copies across worktrees", "%d copies in %d content groups" % (len(roots), len(groups)), "1 authoritative copy", "RISK", "E-02")
    tracked = run(["git", "ls-files", "ANGEL_FNO_MONITOR.SemanticModel/.pbi"], cwd=REPO)
    add_repo("Hygiene", ".pbi folder tracked despite .gitignore **/.pbi/", tracked or "none", "none tracked", "RISK" if tracked else "PASS", "E-16")
    tests = run(["git", "grep", "-l", "-i", "-E", "tmdl|pbip|ANGEL_FNO_MONITOR", "--", "tests"], cwd=REPO)
    add_repo("Tests", "Automated tests covering the Power BI model/report", tests or "0 test files", ">= 1 contract test", "FAIL" if not tests else "PASS", "E-16")
    wf = run(["git", "grep", "-l", "-i", "-E", "pbip|tmdl", "--", ".github/workflows"], cwd=REPO)
    add_repo("CI", "CI workflows that validate the Power BI project", wf or "0 workflows", ">= 1 workflow", "FAIL" if not wf else "PASS", "E-16")
    add_repo("Governance claim", "Proof ledger P-21 'PowerBI Refresh & Process Safety' = PASS", "Command checked process names and .gitignore only; no data freshness or measure check", "PASS must include data/refresh evidence", "MISLEADING_LABEL", "E-19")
    add_repo("Governance claim", "tools/build_nasa_82_matrix.py marks 'Stale Predictions Snaps' RESOLVED_TWO_PARTY", "data/latest_predictions.json last bot commit %s; market_bot.yml last run %s" % (git_last, A["runs"][0] if A["runs"] else ""), "resolved = feed is fresh", "CONTRADICTED", "E-10;E-11")
    sec_hits = []
    for f in list((model_root / "ANGEL_FNO_MONITOR.SemanticModel").rglob("*.tmdl")) + list((model_root / "ANGEL_FNO_MONITOR.Report").rglob("*.json")):
        txt = read_text(f)
        if re.search(r"(-----BEGIN|AIza[0-9A-Za-z_\-]{20,}|private_key|client_secret|api[_-]?key\s*[=:])", txt, flags=re.I):
            sec_hits.append(f.name)
    add_repo("Security", "Secrets embedded in model/report files", ", ".join(sec_hits) or "none found (pattern scan)", "none", "PASS" if not sec_hits else "FAIL", "E-16")
    vis = run(["gh", "repo", "view", "psw2025-cmd/angel-fno-scanner", "--json", "visibility", "-q", ".visibility"], cwd=REPO)
    add_repo("Security", "Repository visibility (model embeds Sheet ID and raw URLs)", vis, "private or intentionally public", "RISK" if vis == "PUBLIC" else "INFO", "E-20")
    add_repo("Security", "Google Sheet readable with no login (gviz CSV HTTP 200)", "7 tabs fetched anonymously", "least-privilege access", "RISK", "E-08")
    if PBIT_PATH.exists():
        with zipfile.ZipFile(PBIT_PATH) as z:
            names = z.namelist()
            schema_raw = z.read("DataModelSchema") if "DataModelSchema" in names else b""
        try:
            schema = json.loads(schema_raw.decode("utf-16"))
            pbit_measures = sum(len(t.get("measures", [])) for t in schema["model"]["tables"])
            pbit_tables = [t["name"] for t in schema["model"]["tables"]]
        except Exception:  # noqa: BLE001
            pbit_measures, pbit_tables = "unreadable", []
        try:
            pbit_names = {m["name"] for t in schema["model"]["tables"] for m in t.get("measures", [])}
            pbit_same = pbit_names == set(measures)
        except Exception:  # noqa: BLE001
            pbit_same = False
        add_repo("Template", "ANGEL_FNO_MONITOR2.pbit measure set vs current PBIP", "%s measures in template, %d in PBIP, names identical=%s; tables=%s" % (pbit_measures, len(measures), pbit_same, ",".join(pbit_tables)),
                 "template matches model or is retired", "PASS" if pbit_same else "RISK", "E-15")
    add_repo("Report", "Visual fields that do not resolve to a model column/measure", "%d unresolved" % len(unresolved), "0", "PASS" if not unresolved else "FAIL", "E-14")
    add_repo("Report", "Visuals total / pages total", "%d / %d" % (len(report["visuals"]), len(report["pages"])), "n/a", "INFO", "E-14")
    write_csv(out / "07_Repo_Audit.csv", ["Check_ID", "Area", "Finding", "Observed", "Expected", "Status", "Evidence_ID"], repo)

    # ================================================================ 09 risk register
    err_list = sorted(err_measures)
    risks = [
        ("R01", "Dashboard shows 18-day-old data (all partitions last refreshed 2026-09-29; file last saved 2026-09-30)", "DATA_FRESHNESS", 5, 5, "E-03;E-12", "Live partition RefreshedTime read from msmdsrv", "OBSERVED", "A01"),
        ("R02", "The only API-style source (GitHub data/*.json) is dead: last bot commit 2026-10-09, market_bot.yml last run 2026-10-13 (failure). A refresh would still load stale data and look refreshed", "DATA_FRESHNESS", 5, 5, "E-06;E-10;E-11", "git log + gh run list + file timestamp", "OBSERVED", "A02"),
        ("R03", "Heartbeat, ForensicLive, CERank and Calibration are constants pasted into the model: they can never refresh, yet pages are titled live and Heartbeat shows HEALTHY / 216 symbols / 0 s writer age", "FALSE_GREEN", 5, 5, "E-03;E-05;E-12", "TMDL partition source + live card text + screenshot", "OBSERVED", "A03"),
        ("R04", "Universe Health compares to a hard-coded 216; engine contract is 219. After any correct refresh the KPI would read FAIL (or PASS at the wrong number)", "LOGIC", 5, 4, "E-05;E-13", "TMDL expression vs universe_contract.py + 219 in BQ/Sheet/JSON", "OBSERVED", "A04"),
        ("R05", "Six DAX measures fail on the live engine (Top Gap Up/Down Symbol, Expected %, Display Safe). Page 6 shows two error cards, an empty chart and an empty table", "MEASURE_DEFECT", 5, 4, "E-05;E-12;E-17", "Direct EVALUATE on msmdsrv + UI error scan + corrected DEFINE test", "OBSERVED", "A05"),
        ("R06", "No executable (liquid) winner is shown. Page 1 displays only the raw leader ('Top real PE' = KFINTECH, Rs 5 premium, +9900 %), and the 'Top Actionable CE/PE' measures that exist are unused and gate only on the words ILLIQUID/AVOID, with no LTP, OI or spread test (AGENTS section 17)", "MODEL_LOGIC", 4, 5, "E-05;E-12", "Measure text + live top PE rows + page 1 screenshot", "OBSERVED", "A06"),
        ("R18", "Labels claim LIVE on stale data: page 6 status card reads ACTIVE INTRADAY PREDICTIONS LIVE and page 1 is titled LIVE COMMAND CENTER while every row is from 2026-09-29; page 6 chart/table are filtered to NEXT_SESSION_ELIGIBLE and hold 0 of 171 rows; two placeholder cards have no fields", "FALSE_GREEN", 5, 3, "E-05;E-12;E-14", "Measure value + PBIR filter + screenshot of page 6", "OBSERVED", "A08"),
        ("R07", "Total rows add up prices and percentages (PaperLog totals 1,257,387 fut LTP / 144,755 %; Prediction QA totals CE+PE=100.00 etc.)", "VISUAL_DEFECT", 4, 3, "E-12;E-14", "Screenshots pages 9 and 10 + default summarizeBy", "OBSERVED", "A07"),
        ("R08", "Silent failure design: try ... otherwise null / empty table on every external source and no row-count or freshness gate; 'Timestamp Safety Status' prints USING CORRECTED IST TIMESTAMP whenever any window label exists", "FALSE_GREEN", 4, 4, "E-14", "TMDL M code review + measure text", "OBSERVED", "A08"),
        ("R09", "PAPER_ALERT_LOG: gviz now returns a merged header label, so the M Rename step will not match and columns become null on next refresh", "REFRESH_REGRESSION", 4, 4, "E-08;E-18", "Raw gviz CSV header vs M rename list (refresh itself NOT executed)", "INFERENCE", "A09"),
        ("R10", "Timezone: BigQuery snapshot_timestamp holds IST wall time labelled UTC (23:40 vs table modified 18:11 UTC). Model applies one wall-clock switch to every source; GitHub JSON semantics are unproven. A 5.5 h error flips NEXT_SESSION_ELIGIBLE vs INTRADAY", "TIMEZONE", 4, 4, "E-09;E-06", "BQ column vs table metadata; JSON vs commit time", "DISPUTED", "A10"),
        ("R11", "Encoding: emoji/status strings are stored corrupted (mojibake) in the model and show on the dashboard (page 10 'HEALTHY' card)", "ENCODING", 4, 2, "E-12;E-14", "TMDL bytes + screenshot", "OBSERVED", "A11"),
        ("R12", "Security/exposure: public GitHub repo; Sheet readable with no login; no least-privilege path for Power BI", "SECURITY", 3, 4, "E-08;E-20", "Anonymous HTTP 200 fetches + gh repo view", "OBSERVED", "A12"),
        ("R13", "No automated test or CI covers the Power BI model/report; governance ledger P-21 PASS covers process names only", "GOVERNANCE", 4, 4, "E-16;E-19", "git grep tests/workflows + ledger text", "OBSERVED", "A13"),
        ("R14", "24 copies of the PBIP across worktrees and an opened copy on a stale dirty branch: risk of editing or publishing the wrong one", "CHANGE_CONTROL", 3, 3, "E-02;E-16", "Filesystem scan + git state", "OBSERVED", "A14"),
        ("R15", "Calibration/self-learning KPIs show 100% from two hand-typed rows while BigQuery holds 405 calibration rows", "DATA_INTEGRITY", 3, 4, "E-03;E-09", "TMDL #table vs BQ metadata", "OBSERVED", "A03"),
        ("R16", "Refresh path is manual Desktop only: no gateway, schedule or Service workspace evidence found; refresh success is never recorded", "OPERATIONS", 4, 3, "E-16", "No .pbix, no workflow, no schedule; Service state NOT VERIFIED", "INFERENCE", "A15"),
        ("R17", "Cross-filtering is absent: the model has one relationship (date helper); fact tables are islands, so slicers on one table cannot affect others", "MODEL_DESIGN", 2, 3, "E-14", "relationships.tmdl", "OBSERVED", "A16"),
    ]
    rr = [{"Risk_ID": r[0], "Risk": r[1], "Category": r[2], "Likelihood_1to5": r[3], "Impact_1to5": r[4], "Score": r[3] * r[4],
           "Severity": "CRITICAL" if r[3] * r[4] >= 20 else "HIGH" if r[3] * r[4] >= 12 else "MEDIUM" if r[3] * r[4] >= 6 else "LOW",
           "Evidence_ID": r[5], "Verification_Method": r[6], "Status_Vocabulary": r[7], "Action_ID": r[8]} for r in risks]
    write_csv(out / "09_Risk_Register.csv", ["Risk_ID", "Risk", "Category", "Likelihood_1to5", "Impact_1to5", "Score", "Severity", "Evidence_ID", "Verification_Method", "Status_Vocabulary", "Action_ID"], rr)

    # ================================================================ 12 action plan
    actions = [
        ("A01", "P0", "Refresh the report from a verified source and prove it (all tables)", "R01", "After A02/A03, refresh in Desktop, then re-run this audit; require partition RefreshedTime within the last session and Live Symbols = 219", "AGENT+USER (open Desktop)", "OPEN", "Re-run tools/powerbi_assurance_audit.py; 06 shows no FAIL", "NO"),
        ("A02", "P0", "Repoint OptionPredictions and News to a live authoritative source (BigQuery or current Sheet tabs) instead of the dead GitHub JSON, or revive the exporter with a freshness gate", "R02", "Design decision: BigQuery connector needs credential; Sheet gviz path already works anonymously", "USER decision + AGENT build", "WAITING_FOR_USER", "Source timestamp within one session of now", "YES"),
        ("A03", "P0", "Replace the embedded constants (Heartbeat, ForensicLive, CERank, Calibration) with live Sheet/BQ queries; remove the HEALTHY/0s cards or compute age as NOW minus source timestamp", "R03;R15", "Same SheetCsv function; add status column derived from age rule in AGENTS section 12", "AGENT", "OPEN", "Partition class != EMBEDDED_STATIC_CONSTANT in 02_PowerBI_Model.csv; card age matches independent calculation", "NO"),
        ("A04", "P0", "Make Universe Health compare to the engine contract (219) and add a test that ties the TMDL number to universe_contract.EXPECTED_FNO_UNIVERSE_COUNT", "R04", "Implemented on branch in this PR (tests/test_powerbi_model_contract.py)", "AGENT", "IMPLEMENTED_NOT_DEPLOYED", "Test passes in CI; live engine shows PASS 219/219 after refresh on fixed model", "NO"),
        ("A05", "P0", "Fix the six failing measures (replace table-valued IF with a scalar HasNext flag)", "R05", "Corrected DAX verified read-only against the live engine: returns KALYANKJIL / BAJFINANCE, matching an independent TOPN", "AGENT", "IMPLEMENTED_NOT_DEPLOYED", "Open fixed PBIP; UI error scan shows 0 error cards on page 6", "NO"),
        ("A06", "P1", "Add an executable-quality gate to Top Actionable CE/PE (minimum LTP, OI, spread) and split raw vs executable KPIs", "R06", "Thresholds are a business/risk decision (AGENTS section 17)", "USER decision + AGENT build", "WAITING_FOR_USER", "Penny premiums never lead the actionable KPI", "YES"),
        ("A07", "P1", "Set summarizeBy=none on non-additive columns and remove Total rows from PaperLog and Prediction QA tables", "R07", "TMDL columns + PBIR table visual total settings", "AGENT", "OPEN", "No summed price/percent in any visual", "NO"),
        ("A08", "P1", "Add a refresh gate: row-count and freshness measures, and make Timestamp Safety Status test the real timestamp offset; surface a visible STALE banner", "R08", "Replace try/otherwise-empty with explicit error rows", "AGENT", "OPEN", "Deliberately break a source and confirm the banner turns red", "NO"),
        ("A09", "P1", "Fix PAPER_ALERT_LOG ingestion (read by explicit header row via range A1 with headers=1 or use a fixed column order) and test a real refresh", "R09", "Requires one controlled refresh to prove", "AGENT", "OPEN", "PaperLog entry_time non-null after refresh", "NO"),
        ("A10", "P1", "Resolve timestamp semantics per source and drop the single wall-clock switch (fix BQ writer to store real UTC, per AGENTS section 24)", "R10", "Engine fix plus model parameter per source", "AGENT", "WAITING_FOR_PEER", "Source timestamp minus table Modified is within seconds", "NO"),
        ("A11", "P2", "Repair mojibake strings in the model (PM-001) and use ASCII status text", "R11", "Byte-safe edit of TMDL", "AGENT", "OPEN", "No non-ASCII in tracked TMDL; card text readable", "NO"),
        ("A12", "P2", "Decide on access model: private repo or sanitised public feed; service-account or signed access for the Sheet", "R12", "Business and security decision", "USER decision", "WAITING_FOR_USER", "Anonymous fetch returns 401/403", "YES"),
        ("A13", "P1", "Add CI: model contract test, field-resolution test, freshness assertion; correct ledger P-21 wording", "R13", "tests/test_powerbi_model_contract.py added here; CI wiring follows", "AGENT", "IMPLEMENTED_NOT_DEPLOYED", "CI job green on main", "NO"),
        ("A14", "P2", "Declare one authoritative PBIP path and archive the other copies after review", "R14", "No deletion without owner approval", "USER approval", "WAITING_FOR_USER", "Inventory shows one PBIP copy", "YES"),
        ("A15", "P1", "Decide delivery: Desktop-only or publish to Service with scheduled refresh; record every refresh result in an append-only log", "R16", "Service workspace/licensing is an owner decision", "USER decision", "WAITING_FOR_USER", "Refresh history visible with timestamps", "YES"),
        ("A16", "P2", "Add a shared Symbol dimension and relationships if cross-filtering is wanted", "R17", "Design change", "AGENT", "OPEN", "Slicer on symbol filters all pages", "NO"),
    ]
    ar = [{"Action_ID": a[0], "Priority": a[1], "Title": a[2], "Fixes_Risks": a[3], "Detail": a[4], "Owner": a[5], "Status": a[6], "Verification_To_Close": a[7], "Needs_User_Approval": a[8]} for a in actions]
    write_csv(out / "12_Action_Plan.csv", ["Action_ID", "Priority", "Title", "Fixes_Risks", "Detail", "Owner", "Status", "Verification_To_Close", "Needs_User_Approval"], ar)

    # ================================================================ 11 evidence register
    def rawh(*names):
        return ";".join("%s=%s" % (n, sha256_file(raw / n)[:16]) for n in names if (raw / n).exists())

    page_err_total = sum(int(r.get("FixThisButtons") or 0) for r in A["page_scan"].values())
    ev_rows = [
        ("E-01", "Runtime identity", "Windows process table + TCP listeners", "Get-CimInstance Win32_Process; Get-NetTCPConnection", "PBIDesktop PID 23416 started 13:53:04 IST; msmdsrv PID 11740 child; listener 59161; file opened: repos\\angel-fno-scanner\\ANGEL_FNO_MONITOR.pbip", rawh("processes_20261017.json", "listeners_20261017.json"), 99, "E-12"),
        ("E-02", "Project authority", "Filesystem + hashes", "SHA-256 of TMDL/PBIR with CRLF normalised", "%d PBIP copies in %d content groups; opened copy content-identical to main" % (len(roots), len(groups)), "see 01_Inventory.csv", 97, "E-16"),
        ("E-03", "Live partitions and row counts", "msmdsrv localhost:59161 DMV $SYSTEM.TMSCHEMA_PARTITIONS and EVALUATE COUNTROWS", "Microsoft.PowerBI.AdomdClient, read-only", "All 5 imported partitions RefreshedTime 2026-09-29 (21:49-21:52); constants 23:20; rows OptionPredictions 171, News 50, PaperLog 464, SheetNews 216, Heartbeat 1, ForensicLive 216, CERank 216, Calibration 2", rawh("live_partitions_20261017.csv", "live_rowcounts_20261017.csv"), 99, "E-12"),
        ("E-04", "Measure inventory", "TMDL _Measures.tmdl vs live DMV", "Parse + $SYSTEM.TMSCHEMA_MEASURES", "%d measures parsed; live engine reports 59" % len(measures), "03_DAX_Measures.csv", 98, "E-05"),
        ("E-05", "Measure values", "msmdsrv EVALUATE ROW(measure) per measure", "Direct DAX evaluation at 2026-10-17 14:12:53 IST", "59 evaluated: %d ERROR (%s); Live Symbols 171; Universe Health FAIL / INCOMPLETE; Heartbeat Freshness 0 sec writer age" % (len(err_list), ", ".join(err_list)), rawh("live_measure_values_20261017.csv"), 99, "E-12"),
        ("E-06", "GitHub JSON predictions", "raw.githubusercontent.com data/latest_predictions.json (HTTP 200)", "Fetch + Python recompute of DAX rules", "%d rows, %d symbols, snapshot %s (age %s h), liquidity %d PASS / %d REJECT" % (A["pred_rows"], A["pred_symbols"], A["pred_snapshot"], age_h(pred_ts), A["pred_pass"], A["pred_reject"]), rawh("latest_predictions_json_20261017.json"), 97, "E-10"),
        ("E-07", "GitHub JSON news", "raw.githubusercontent.com data/market_news.json", "Fetch + count", "%d rows, %d symbols, %d domains, latest item %s" % (A["news_rows"], A["news_symbols"], A["news_domains"], A["news_latest"]), rawh("market_news_json_20261017.json"), 95, ""),
        ("E-08", "Google Sheet tabs", "docs.google.com gviz CSV (HTTP 200, anonymous)", "Fetch 7 tabs + parse", "HEARTBEAT last ping %s (cell age %s s), %s symbols; FORENSIC_LIVE %d rows; CE_PE_RANK %d rows; NEWS_LIVE %d rows; PAPER_ALERT_LOG header merged (%d chars)" % (A["hb_last_ping"], A["hb_age_cell"], A["hb_symbols"], A["fl_rows"], A["rank_rows"], A["newslive_rows"], A["paper_header_len"]),
         rawh("sheet_HEARTBEAT_20261017.csv", "sheet_FORENSIC_LIVE_20261017.csv", "sheet_CE_PE_RANK_20261017.csv", "sheet_NEWS_LIVE_20261017.csv", "sheet_PAPER_ALERT_LOG_20261017.csv"), 96, "E-09"),
        ("E-09", "BigQuery", "BigQuery REST tables.get + jobs.query (read-only, 3,753 bytes)", "Metadata + COUNT query", "option_predictions_live: %s rows, %s symbols, modified 2026-10-16 18:11 UTC; snapshot_timestamp column %s (IST labelled UTC)" % (A["bq_rows"], A["bq_syms"], A["bq_snapshot"]), rawh("bq_tables_20261017.csv", "bq_query_option_predictions_live_20261017.txt"), 98, "E-08"),
        ("E-10", "GitHub data file history", "git log origin/main -- data/latest_predictions.json", "Git history", "last bot commit %s (github-actions[bot])" % git_last, "git history", 99, "E-06"),
        ("E-11", "GitHub workflow runs", "gh run list --workflow market_bot.yml", "GitHub API", "latest run %s" % (A["runs"][0] if A["runs"] else ""), rawh("market_bot_runs_20261017.txt"), 98, "E-10"),
        ("E-12", "Rendered dashboard", "Power BI Desktop window capture via PrintWindow + UI Automation scan of 10 pages", "Screenshots + element scan", "Pages scanned: 10; error cards: %d (page 6: Gap-up candidate, Gap-down candidate; plus 2 empty placeholder cards and chart/table filtered to 0 rows); page 1 shows Universe Health FAIL, CE/PE alerts (Blank); page 10 shows 216 symbols / 0 sec writer age / HEALTHY; title bar Last saved 9/30/2026 4:51 AM" % page_err_total,
         rawh("pbi_page_error_scan_20261017.csv", "pbi_page_1.png", "pbi_page_6.png", "pbi_page_9.png", "pbi_page_10.png"), 96, "E-05"),
        ("E-13", "Engine universe contract", "git grep EXPECTED_FNO_UNIVERSE_COUNT on main", "Source code", "universe_contract.py and scanner.py define 219; measure 'Universe Health' literal 216", "git", 99, "E-09"),
        ("E-14", "Static model/report analysis", "tools/powerbi_assurance_audit.py parsing TMDL + PBIR", "Deterministic parser", "%d tables, %d columns, %d measures, %d relationship(s), %d pages, %d visuals, %d unresolved fields" % (len(tables), sum(len(t["columns"]) for t in tables.values()), len(measures), len(model["relationships"]), len(report["pages"]), len(report["visuals"]), len(unresolved)), "this script", 95, "E-05"),
        ("E-15", "Stale template", "C:\\Users\\ADMIN\\Documents\\ANGEL_FNO_MONITOR2.pbit", "Zip + DataModelSchema parse", "Template dated 2026-09-30; not the current model", sha256_file(PBIT_PATH)[:16] if PBIT_PATH.exists() else "absent", 80, ""),
        ("E-16", "Repo state", "git status/branch/ls-files/grep in repos", "Git", "see 07_Repo_Audit.csv", "git", 97, "E-02"),
        ("E-17", "Corrected measure test", "msmdsrv EVALUATE with DEFINE MEASURE (no model change)", "Query-scoped measure vs independent TOPN", "Fixed Top Gap Up = KALYANKJIL, Down = BAJFINANCE; independent TOPN recompute identical", rawh("fix_test_top_gap_20261017.txt", "fix_verify_query_20261017.dax", "fix_verify_result_20261017.txt", "live_forecast_window_20261017.csv"), 95, "E-05"),
        ("E-21", "Regression tests", "pytest tests/test_powerbi_model_contract.py", "Run against unfixed origin/main file and against the fixed file", "Unfixed main: 3 failed, 4 passed (universe literal, table-valued IF, HasNext flag). Fixed file: 7 passed. Patched measures evaluated on the live engine: Top Gap Up KALYANKJIL +1.53%, Down BAJFINANCE -1.61%, all six no longer error", "tests/test_powerbi_model_contract.py", 97, "E-17"),
        ("E-18", "PAPER_ALERT_LOG header", "gviz CSV first line", "Raw file inspection", "header label is a %d-char concatenation of row values, not 'Logged at IST'" % A["paper_header_len"], rawh("sheet_PAPER_ALERT_LOG_20261017.csv"), 85, ""),
        ("E-19", "Proof ledger claim", "docs/PROVEN_PROOF_LEDGER.json P-21", "Text review", "P-21 command: Get-Process and .gitignore inspection only", "git", 99, ""),
        ("E-20", "Repository visibility", "gh repo view", "GitHub API", "PUBLIC", "gh", 99, ""),
    ]
    er = [{"Evidence_ID": e[0], "Area": e[1], "Source": e[2], "Verification_Method": e[3], "Result": e[4], "Observed_At_IST": OBSERVED_STR,
           "Raw_Artifact_SHA256_16": e[5], "Confidence_Pct": e[6], "Independent_Path": e[7]} for e in ev_rows]
    write_csv(out / "11_Evidence_Register.csv", ["Evidence_ID", "Area", "Source", "Verification_Method", "Result", "Observed_At_IST", "Raw_Artifact_SHA256_16", "Confidence_Pct", "Independent_Path"], er)

    # ================================================================ 10 readiness
    ready = [
        ("Runtime", "Power BI Desktop + engine alive and owning the open report", "PASS", "E-01", "Process, parent link, listener", 99, "PID 23416 / 11740 / port 59161"),
        ("Data freshness", "Loaded data within last session", "FAIL", "E-03;E-12", "Partition RefreshedTime", 99, "18 days old"),
        ("Data freshness", "Upstream feed Power BI reads is alive", "FAIL", "E-06;E-10;E-11", "git log, run list, JSON timestamp", 97, "GitHub JSON dead since 2026-10-09"),
        ("Data freshness", "Operational sources alive (Sheet, BigQuery)", "PASS WITH RISKS", "E-08;E-09", "Sheet ping + BQ Modified agree (2026-10-16 ~23:40 IST)", 96, "Fresh for last session; BQ timestamp column mislabelled"),
        ("Universe", "216/219 symbol completeness shown correctly", "FAIL", "E-05;E-13;E-09", "Live Symbols 171; measure literal 216; contract 219", 98, "Both loaded data and KPI logic wrong"),
        ("ETL / Power Query", "Silent failure prevented", "FAIL", "E-14", "try/otherwise-empty on all sources", 90, "No gate"),
        ("ETL / Power Query", "PaperLog refresh will map columns", "FAIL", "E-18", "Header mismatch", 80, "INFERENCE; refresh not executed"),
        ("Data model", "Relationships and keys", "PASS WITH RISKS", "E-14", "1 relationship only", 90, "Islands; no cross-filter"),
        ("DAX", "All measures evaluate without error", "FAIL", "E-05", "6 of 59 error", 99, "Top Gap family"),
        ("DAX", "KPI logic matches engine contract and AGENTS rules", "FAIL", "E-05;E-13", "216 literal, actionable gate missing", 95, "R04 R06"),
        ("Visuals", "All 76 visuals render", "FAIL", "E-12", "UI scan: 2 error cards (+ empty chart/table) on page 6", 96, "9 of 10 pages render without error cards"),
        ("Visuals", "Totals and aggregations are meaningful", "FAIL", "E-12", "Screenshots pages 9-10", 90, "R07"),
        ("Dashboard truthfulness", "No false-green status", "FAIL", "E-05;E-12", "Heartbeat HEALTHY/0s from constant", 99, "AGENTS sections 12, 34"),
        ("Dashboard truthfulness", "Forward accuracy not overstated", "PASS", "E-05;E-14", "Forward Accuracy blank + BLOCKED label; titles say not forward accuracy", 95, "Honest labelling"),
        ("Reconciliation", "Internal consistency of loaded model (PASS+REJECT = rows)", "PASS", "E-05", "93 + 78 = 171", 99, "Arithmetic right on stale data"),
        ("Governance", "Automated tests and CI cover the model", "FAIL", "E-16", "0 tests, 0 workflows", 97, "R13"),
        ("Governance", "Single authoritative project copy", "PASS WITH RISKS", "E-02;E-16", "Open copy identical to main but 24 copies exist", 90, "R14"),
        ("Security", "No secrets embedded; PAPER-only; no order code in model", "PASS", "E-16", "Pattern scan of TMDL/PBIR", 85, "Absence of match, not proof of absence"),
        ("Security", "Least-privilege data access", "FAIL", "E-08;E-20", "Public repo + anonymous Sheet", 95, "R12"),
        ("Operations", "Refresh recorded and monitored", "FAIL", "E-16", "No schedule, no log", 80, "NOT VERIFIED beyond local evidence"),
    ]
    counts = Counter(r[2] for r in ready)
    overall = "FAIL" if counts.get("FAIL", 0) else ("PASS WITH RISKS" if counts.get("PASS WITH RISKS", 0) else "PASS")
    rd = [{"Domain": r[0], "Criterion": r[1], "Result": r[2], "Evidence_ID": r[3], "Verification_Method": r[4], "Confidence_Pct": r[5], "Notes": r[6]} for r in ready]
    rd.append({"Domain": "OVERALL", "Criterion": "Production readiness verdict", "Result": overall, "Evidence_ID": "E-01..E-20",
               "Verification_Method": "Any critical FAIL overrides averages (AGENTS section 34)", "Confidence_Pct": 96,
               "Notes": "FAIL=%d PASS WITH RISKS=%d PASS=%d" % (counts.get("FAIL", 0), counts.get("PASS WITH RISKS", 0), counts.get("PASS", 0))})
    write_csv(out / "10_Production_Readiness.csv", ["Domain", "Criterion", "Result", "Evidence_ID", "Verification_Method", "Confidence_Pct", "Notes"], rd)

    # ================================================================ diagrams (mermaid sources)
    (out / "diagrams" / "1_system_architecture.mmd").write_text(
        "flowchart LR\n"
        "  subgraph Producers\n    ANG[Angel One SmartAPI] --> ENG[angel_prediction_engine.py / scanner.py]\n    ENG --> CR[Cloud Run job angel-market-scan-job]\n  end\n"
        "  subgraph Stores\n    CR --> BQ[(BigQuery option_predictions_live 219 rows)]\n    CR --> SH[(Google Sheet OPTION_SHEET tabs)]\n    GHA[GitHub Actions market_bot.yml - last run 2026-10-13 failed] -.dead feed.-> GH[(GitHub data/latest_predictions.json - 2026-10-09)]\n  end\n"
        "  subgraph PowerBI[Power BI Desktop PID 23416 + msmdsrv 11740]\n    GH -->|Web.Contents| OP[OptionPredictions 171 rows 2026-09-29]\n    GH -->|Web.Contents| NW[News 50 rows]\n    SH -->|gviz CSV| PL[PaperLog 464 rows]\n    SH -->|gviz CSV| SN[SheetNews 216 rows]\n    FZ[Embedded constants Heartbeat ForensicLive CERank Calibration 2026-09-29]\n    OP --> M[59 DAX measures - 6 error]\n    NW --> M\n    PL --> M\n    FZ --> M\n    M --> V[76 visuals on 10 pages]\n  end\n"
        "  V --> USER[Owner dashboard]\n", encoding="ascii")
    (out / "diagrams" / "2_data_lineage.mmd").write_text(
        "flowchart LR\n  S1[Angel One quotes] --> E1[engine cycle] --> B1[(BQ option_predictions_live)]\n  E1 --> S2[(Sheet HEARTBEAT / FORENSIC_LIVE / CE_PE_RANK / NEWS_LIVE / PAPER_ALERT_LOG)]\n"
        "  B1 -.exporter stopped 2026-10-09.-> J1[data/latest_predictions.json]\n  J1 --> PQ1[PQ: Web.Contents > FromRecords > FixSnapshot > Liquidity > ForecastWindow] --> T1[OptionPredictions]\n"
        "  S2 --> PQ2[PQ: SheetCsv > Rename > Types] --> T2[PaperLog and SheetNews]\n  S2 -.manual paste 2026-09-29.-> T3[Heartbeat ForensicLive CERank constants]\n"
        "  T1 --> D1[Live Symbols, Universe Health, Liquidity, Gap measures]\n  T3 --> D2[Top Real CE/PE, Heartbeat displays, alert counts]\n  T2 --> D3[PaperLog table]\n  D1 --> VIS[Pages 1,5,6,7,9]\n  D2 --> VIS2[Pages 1,2,3,4,10]\n  D3 --> VIS3[Page 10]\n", encoding="ascii")
    (out / "diagrams" / "3_refresh_flow.mmd").write_text(
        "flowchart TD\n  A[Owner presses Refresh in Desktop] --> B{Per table}\n  B -->|OptionPredictions, News| C[Download GitHub raw JSON]\n  C --> C2{Fresh?}\n  C2 -->|No - 2026-10-09| C3[Loads old data and still shows Refreshed]\n  B -->|PaperLog, SheetNews| D[Download Sheet gviz CSV]\n  D --> D2{Header matches Rename?}\n  D2 -->|No for PAPER_ALERT_LOG| D3[Columns become null silently]\n  B -->|Heartbeat, ForensicLive, CERank, Calibration| E[No query: constants unchanged]\n  C3 --> F[DAX measures]\n  D3 --> F\n  E --> F\n  F --> G[Visuals]\n  G --> H[No recorded refresh result, no stale banner]\n", encoding="ascii")
    (out / "diagrams" / "4_dependency_graph.mmd").write_text(
        "flowchart LR\n  OptionPredictions --> LiveSymbols --> UniverseHealth\n  OptionPredictions --> LiquidityPass\n  OptionPredictions --> TopGapMeasures[6 Top Gap measures - ERROR]\n  OptionPredictions --> ConfidenceMeasures\n  ForensicLive --> TopRealCE --> TopActionableCE\n  ForensicLive --> TopRealPE --> TopActionablePE\n  CERank --> AlertCounts[CE/PE Alert Count - Blank]\n  Heartbeat --> HeartbeatDisplays[Status / Symbols / Freshness / Feed]\n  Calibration --> SelfCalKPIs\n  News --> NewsKPIs\n  PaperLog --> PaperLogTable\n  OptionPredictions -->|only relationship| LocalDateTable\n", encoding="ascii")

    summary = {"generated_at_ist": OBSERVED_STR, "origin_main": main_sha, "tables": len(tables), "measures": len(measures), "pages": len(report["pages"]),
               "visuals": len(report["visuals"]),
               "visuals_depending_on_frozen_tables": sum(1 for r in vrows if "FROZEN_TABLE" in r["Defect_Flags"]),
               "visuals_empty_placeholder": sum(1 for r in vrows if "EMPTY_PLACEHOLDER" in r["Defect_Flags"]),
               "visuals_with_live_measure_error": sum(1 for r in vrows if "LIVE_MEASURE_ERROR" in r["Defect_Flags"]), "live_error_measures": err_list, "page_error_cards": page_err_total, "unresolved_fields": len(unresolved),
               "readiness_counts": dict(counts), "overall": overall}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="ascii")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
