# Architecture

Paper and analyze only. No `placeOrder`, `modifyOrder`, or `cancelOrder` path was added.

```
GitHub Actions market_bot (cron 45 3 UTC = 09:15 IST)
        and
Cloud Scheduler us-central1 (now 15 9 Asia/Kolkata = 09:15 IST, PAUSED)
        |
        v
Cloud Run job angel-market-scan-job (us-central1)
  image scanner:v1
  digest sha256:c7a001cbaad51c9a815f49930a77f11f8652dbd0484b94e9062aa8b0ce89c59b
  service account angel-sheets-bot
        |
        +--> Google Sheet 1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs
        +--> BigQuery fno_predictions (asia-south1)
               option_predictions_live
               transaction_write_lock   (paper-cycle lease, currently empty)
```

The intended single writer is `WRITER_ID=market_bot` with `ALLOW_PRODUCTION_WRITES=1`. GitHub Actions and Cloud Run take the same lock key `paper-cycle:{IST date}:{session}`. The owner id is `{token}|market_bot|{execution id}`. A second live publisher is blocked. An expired publisher is replaced and its token cannot renew.

Asia-south1 had no Cloud Run job, service, or scheduler at inspection. BigQuery is already in asia-south1. The validation job, when built, must set `ALLOW_PRODUCTION_WRITES=0` and must not be the US job.

Universe identity is 219 symbols. The ranked CE/PE board contract is 200 rows at `CE_PE_RANK!A5:A204`.
