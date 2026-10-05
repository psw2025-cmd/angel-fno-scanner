# Visual files — live vs snapshot

Checked 2026-10-06 01:35 IST.

## Live (always current — do not replace with git copies)

| Surface | Status | Open |
|---|---|---|
| Production Google Sheet `OPTION_SHEET` | LIVE writer target | https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/edit |
| Standby sheet `ANGEL_FNO_LIVE_PROD` | Aligned, **not** switched | https://docs.google.com/spreadsheets/d/1pI0Dp6ehEcsdA6q_Zuhff4mi1o0dSlB1mOUtUL5W3FA/edit |
| Canonical Colab (`AGENTS.md` id `1AUgfSEkpt9CeOf2Nwo_HLNrNCgLSqCUH`) | Link in contract; file **not** found in Drive search | https://colab.research.google.com/drive/1AUgfSEkpt9CeOf2Nwo_HLNrNCgLSqCUH |
| Latest Colab actually in Drive | `Untitled72.ipynb` 2026-10-04 | https://colab.research.google.com/drive/1XU-KHQxXVGXAKOmmQj5iFbMTg82ICc3a |
| Power BI Desktop | Local Windows only. Drive has only stale `op.pbix` from 2024-08-27 | AGY must copy current `.pbix` to `operator/snapshots/` after close |

## Already in this repo (snapshots, not live tape)

| File | What it is | Dated |
|---|---|---|
| [data/summary.md](../data/summary.md) | Trader gap / CE / PE snapshot | 2026-10-05 11:39 UTC |
| [data/latest_predictions.json](../data/latest_predictions.json) | Last prediction dump | same cycle |
| [data/system_health.json](../data/system_health.json) | Writer health dump | same cycle |
| [docs/AGENT_HANDOFF.md](../docs/AGENT_HANDOFF.md) | AGY 12/12 claim from 5 Oct afternoon | **stale vs overnight BQ** |

## Do not commit as live truth

- Full 219-row Sheet xlsx every minute (git would lie within one cycle).
- 25 MB BigQuery JSON dumps (`audit/cloud_exports/` stays local).
- 2024 `op.pbix` — wrong file.

## Daily close pack (AGY laptop, after 15:40 IST)

Copy into `operator/snapshots/YYYY-MM-DD/`:

1. Excel export of `OPTION_SHEET` (File → Download → xlsx)
2. Current Power BI `.pbix`
3. Colab File → Download `.ipynb`
4. Re-run `python tools/verify_harness.py` and save the JSON next to them
