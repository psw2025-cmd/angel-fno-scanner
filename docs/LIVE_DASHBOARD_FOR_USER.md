# LIVE DASHBOARD FOR OPERATOR — 2-MINUTE HEALTH CHECK

> **Operator Quick-Check Protocol**: Run this 2-minute checklist to verify overall system health across all 8 integrated layers without writing code or inspecting logs.

---

## 2-Minute Health Checklist (8 Critical Verification Checks)

| # | Subsystem / Dimension | Quick Verification Method | Current Verified State | Status |
|---|---|---|---|:---:|
| **1** | **GitHub Actions CI** | Check [Encoding Safety Runs](https://github.com/psw2025-cmd/angel-fno-scanner/actions/workflows/encoding-safety.yml) on `main` and PR branches | Run 37966316702: `ubuntu-latest` (PASS), `windows-latest` (PASS) | **[PASS] GREEN** |
| **2** | **Proven Proof Ledger** | Inspect `docs/PROVEN_PROOF_LEDGER.json` total checks | 25/25 checks PASS / DOCUMENTED with timestamp & SHA | **[PASS] GREEN** |
| **3** | **Git Working Tree Hygiene** | Run `git status --porcelain` on local clone | Orphans < 10, zero tracked `desktop.ini`, clean tree | **[PASS] GREEN** |
| **4** | **Power BI Environment** | Check local `msmdsrv.exe` and `**/.pbi/` in `.gitignore` | `**/.pbi/` and `*.pbix` ignored; no zombie model locks | **[PASS] GREEN** |
| **5** | **Data Chain Parity** | Check `latest_predictions.json` length vs Sheets & BQ | Exact 219 underlying universe match (`test_data_chain.py` PASS) | **[PASS] GREEN** |
| **6** | **Excel & CSV Safety** | Run `pytest tests/test_data_chain.py -k test_excel` | Binary skip active; zero cp1252 decoder crashes | **[PASS] GREEN** |
| **7** | **Colab / Research Notebooks** | Check `.ipynb` files via `test_encoding_gate.py` | UTF-8 enforced; no console-breaking unescaped emoji prints | **[PASS] GREEN** |
| **8** | **Cloud Evidence & Snapshots** | Inspect `C:\Temp\RESET_BASELINE_*.txt` & GCS readiness | Local forensic evidence preserved; GCS bucket configured | **[PASS] GREEN** |

---

## Operator System Status Verdict

```text
========================================================================================
CURRENT SYSTEM OPERATIONAL STATE: 100% HEALTHY & FAIL-CLOSED COMPLIANT
SAFETY ENFORCEMENT:               PAPER / ANALYZER = ON | REAL BROKER ORDERS = 0
DUAL-AGENT SOVEREIGN STATUS:      AGY CLI (LOCAL) + CHATGPT (CLOUD) SYNCHRONIZED
========================================================================================
```

### Guidance for Alerts:
- If **any** check from 1-7 fails: System automatically fails closed. No live updates are published.
- Live broker order placement remains permanently disabled under all circumstances.
