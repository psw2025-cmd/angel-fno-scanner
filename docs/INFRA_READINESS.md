# Metadata readiness evidence

From a checkout containing these scripts, run in Windows PowerShell 5.1:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare_infra_readiness.ps1
```

The launcher selects `.venv\Scripts\python.exe`, falling back to `python.exe`.
Requires Python 3.11+ and existing `google-cloud-bigquery`, `gspread`, Google auth,
and `tzdata` dependencies from requirements.txt. It installs nothing.
Use `-PythonExe "C:\path\python.exe"` to select another environment.

Credentials: existing SHEETS_KEY_JSON (JSON or path), GOOGLE_APPLICATION_CREDENTIALS,
Google-only keys from repo `.env`, workstation service-account file, or application
default credentials. The identity needs BigQuery metadata read/update and access
to OPTION_SHEET. No broker credentials are needed. Optional GH_TOKEN/GITHUB_TOKEN
permits private GitHub CI reads; public reads work anonymously within rate limits.

Default preparation patches only the schema of four **existing** production tables,
adding nullable STRING run_id/git_sha/writer_id/source_timestamp fields. Existing
nullable TIMESTAMP/DATETIME source_timestamp fields are preserved. Conflicting
types/modes, views, missing tables, and nonempty conflicting Sheet headers fail
closed. Existing columns and runtime rows are preserved. Missing WRITE_PROVENANCE
is created, and only its empty header is initialized with the writer's six columns.
Historical rows are not backfilled. No datasets/tables or runtime events are invented.

`-VerifyOnly` suppresses cloud mutations. `-Offline` suppresses all cloud/network
checks and generates local evidence with UNKNOWN cloud status. Preparation should
be run while the normal writer is idle; this utility does not acquire a distributed
writer lease. Etag-protected BigQuery updates reject concurrent metadata changes.
Sheet APIs have no conditional header write; do not run concurrent preparation.

`-OutputRoot "C:\path\reports"` changes the evidence location. Each run creates a
unique timestamped INFRA_READY folder, with HTML/JSON/Markdown, checks/schema/
symbols/CI CSVs, metadata raw logs, and SHA256SUMS.csv. Provider error messages and
credentials are withheld from logs; exception classes indicate troubleshooting paths.
Open SYSTEM_STATUS.html locally; no hosted service or external visual dependency.

Exit 0 means all infrastructure checks passed; 1 means a failed/unknown check;
2 means launcher failure. A branch checkout differs from current main and is
reported as such. CI qualifies only the latest PR Tests run on the exact local SHA.
The script does not dispatch tests or market workflows. Run the repo tests separately
in a test environment when needed. The 219-symbol check is configuration evidence,
not actual live symbol coverage. Single-writer verification inspects workflow/guard
source, not cloud IAM or cross-runtime lease ownership.

Market runtime remains NOT_PROVEN even if infrastructure passes. Next normal
market_bot evidence must prove a shared run_id, writer identity, fresh full universe,
zero duplicates, and one prediction cycle. No scanner execution, manual market_bot
trigger, production snapshot load, LIVE trading change, or broker call occurs here.
