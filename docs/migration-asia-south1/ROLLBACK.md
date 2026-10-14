# Rollback

Mumbai was not cut over. Rollback of the scheduler clock, if 09:15 IST is not wanted, is:

```
gcloud scheduler jobs update http angel-market-scan-job --project=fno-angel-prod-1790444589 --location=us-central1 --schedule="45 3 * * 1-5" --time-zone="Asia/Kolkata"
gcloud scheduler jobs pause angel-market-scan-job --project=fno-angel-prod-1790444589 --location=us-central1
```

Do not resume it unless the US job is still the intended paper publisher. Do not delete the US job or the US scheduler.

The US image was not replaced. To return to the inspected image, keep:

`us-central1-docker.pkg.dev/fno-angel-prod-1790444589/cloud-run-source-deploy/scanner@sha256:c7a001cbaad51c9a815f49930a77f11f8652dbd0484b94e9062aa8b0ce89c59b`

Sheet formula rollback, only if the approved 200-row contract must be undone:

- `C10`: `=COUNTA(CE_PE_RANK!C3:C218)&" / 216"`
- `E10`: `=IF(COUNTA(CE_PE_RANK!C3:C218)=216,"PASS","FAIL")`
- `C11`: `=COUNTIF(CE_PE_RANK!Y3:Y218,"CE ALERT")+COUNTIF(CE_PE_RANK!Y3:Y218,"PE ALERT")`

Do not delete `option_predictions_live` or `option_predictions_live_backup_20261005`. Do not force-push `main`. Do not disable branch protection.

Local dirty files `angel_prediction_engine.py` and `paper_log.py` are preserved in `evidence/20261014-052520/local-uncommitted.diff`. Do not revert them from that diff unless the operator asks.
