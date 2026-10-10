# PM-007 — Google Sheets API 429 Quota Exceeded and APIError Handling

## 1. Problem Statement & Root Cause
Google Sheets API v4 enforces a strict limit of 60 read requests per user per minute. Rapid automated polling or multiple tabs requested sequentially without batching triggered `gspread.exceptions.APIError: [429] RESOURCE_EXHAUSTED`.

## 2. Impact
Automated test scripts threw unhandled exceptions, crashing audit runs and reporting false down status for healthy sheets.

## 3. Resolution & Commit
- Added exponential backoff and randomized jitter to `gspread` requests in `publication.py` and `credentials.py`.
- Introduced LRU caching for static metadata and batch cell reading (`get_all_values()`).
- Fail-closed error handling distinguishes network/quota limits from true schema corruption.

## 4. Prevention & Forensic Gates
- Verified by proof ledger check P-05 and P-16.
- Retry policy: max 5 attempts with backoff factor 1.5.
