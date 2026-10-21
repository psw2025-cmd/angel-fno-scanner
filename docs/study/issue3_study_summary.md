DEEP STUDY (pre-PHASE-00) - 2026-10-15 ~03:45 IST
Agent: Cursor (integration agent) | Status: OBSERVED | PAPER=ON, LIVE ORDER AUTHORITY=OFF
Branch at time of study: docs/trigger-reference (uncommitted changes present). No commits/pushes made.

OBSERVATIONS
- Code inventory (FunctionDef counts): scanner.py=24, angel_prediction_engine.py=47, writer_guard.py=3
- schemas/: cross_agent_packet.schema, cycle_status, market_news_sentiment, next_day_gap_predictions, option_predictions_live, prediction_calibration_log (6 files)
- BigQuery (region-us, last 2 days): 13 failed jobs, all ad-hoc query errors (syntax errors; lookups of nonexistent datasets option_data / option_predictions). None from scanner pipeline.
- Cloud Run angel-fno-scanner (us-central1): NOT READY. No service URL, no latestReadyRevision. Latest created revision 00003-hr6 Ready=False.
  - startup-cpu-boost=true on the existing revision (conflicts with free-tier constraint 4)
  - Artifact Registry repo in use: cloud-run-source-deploy (backlog PHASE-10 assumes "cloudrun")
- Cloud Scheduler (us-central1): 0 jobs.
- Google Sheet OPTION_SHEET: 27 tabs (backlog PHASE-12 gate expects 55). No PAPER_LOG tab; has PAPER_ALERT_LOG.
- NOT RUN: MASTER_AUDIT.txt / RUNTIME_PROOF.txt study (files absent). IMPLEMENTATION_REPORT.md and CODEX_IMPLEMENTATION_BACKLOG.md also absent from workspace.
- Backlog script defect: credentials.gspread_client() does not exist; use gspread.service_account_from_dict(credentials.load_service_account()).

RISKS FOUND IN BACKLOG
- PHASE-00 `git add -A` would stage .venv, .tmp.driveupload, __pycache__, proof-output, evidence folders.
- Region ambiguity: backlog targets us-central1; docs/migration-asia-south1/ exists.

Raw Cloud Run JSON deliberately not posted (may contain env/project details).
NEXT: waiting on owner for region + missing artifacts before PHASE-00.
