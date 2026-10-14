# Configuration diff

## Cloud Scheduler `angel-market-scan-job` (us-central1)

| Field | Before | After |
| --- | --- | --- |
| cron | `45 3 * * 1-5` | `15 9 * * 1-5` |
| time zone | `Asia/Kolkata` | `Asia/Kolkata` |
| fires at | 03:45 IST | 09:15 IST |
| state when described | `PAUSED` (list a minute earlier showed `ENABLED`; `userUpdateTime` `2026-10-13T23:55:46Z` was not made by this change) | `PAUSED` |
| HTTP target | US Cloud Run job `:run` | unchanged |
| service account | `angel-sheets-bot@fno-angel-prod-1790444589.iam.gserviceaccount.com` | unchanged |

## Cloud Run job

Unchanged. Still `us-central1`, image tag `scanner:v1`, digest `sha256:c7a001cbaad51c9a815f49930a77f11f8652dbd0484b94e9062aa8b0ce89c59b`, 2 CPU, 4Gi, timeout 14400s, `ALLOW_PRODUCTION_WRITES=1`, placeholder `RUN_ID` and `GIT_SHA`.

## Asia-south1

No job, service, or scheduler before or after this inspection.

## Sheet formulas

| Cell | Before | After |
| --- | --- | --- |
| Formula Checks C10 | `=COUNTA(CE_PE_RANK!C3:C218)&" / 216"` | `=COUNTA(CE_PE_RANK!A5:A204)&" / 200"` |
| Formula Checks E10 | `=IF(COUNTA(CE_PE_RANK!C3:C218)=216,"PASS","FAIL")` | `=IF(COUNTA(CE_PE_RANK!A5:A204)=200,"PASS","FAIL")` |
| Formula Checks C11 | `=COUNTIF(CE_PE_RANK!Y3:Y218,"CE ALERT")+COUNTIF(CE_PE_RANK!Y3:Y218,"PE ALERT")` | `=COUNTIF(CE_PE_RANK!U5:U204,"HIGH MOMENTUM")` |

## GitHub snapshot publication

Before: `git push origin HEAD:main` with a commit message that contains a CI-skip marker. After, in the branch: push `data/snapshot-$GITHUB_RUN_ID` and open a pull request. That workflow change is not on `main` until the pull request merges.
