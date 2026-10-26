# V4 GitHub publication audit — 2026-10-26

Status: **PARTIAL / HANDOFF BLOCKED**. Do not merge or certify as a complete 16-file upload.

Authenticated GitHub write and readback have been demonstrated on branch `docs/architecture-v4-handoff-20261026`. The repository's `main` branch has not been modified.

## Uploaded content
Twelve source document files have been uploaded, plus the original validator script:
01_BASELINE_ARCHITECTURE_V1.md
02_EXECUTION_AND_COORDINATION_V2.md
03_LOCAL_AGENT_EXECUTION_ORDER.md
04_MACHINE_READABLE_STATUS_TEMPLATE.json
05_FAILURE_FORENSICS_AND_PREVENTION_V3.md
06_RELEASE_ACCEPTANCE_MATRIX.csv
07_HISTORICAL_INCIDENT_REGISTER.csv
09_PREHANDOFF_GAP_CLOSURE_V4.md
10_AGENT_HANDOFF_PROTOCOL_V4.md
11_OWNER_OUTCOME_AND_METRIC_CONTRACT.md
13_HARD_STOP_ACCEPTANCE.csv
README_START_HERE.md

This file (UPLOAD_STATUS.md) is a publication receipt, not one of the 16 archive members.

## Original archive publication gaps (3 missing files; 1 validator published)
- 08_MANIFEST_SHA256.json — not yet published
- 12_SOURCE_AND_PERMISSION_REGISTER.csv — GitHub upload blocked by tool safety checks; do not evade the block
- 14_FILE_MANIFEST.json — not yet published
- validate_package.py — published; remote execution is still unverified

## Byte-exact validation warning
The authored ZIP is available in the chat artifact workspace and locally passed its internal SHA-256 manifest validation (14/14). Some GitHub uploads were sourced through document text extraction rather than raw ZIP byte streaming. **These remote blobs have not been verified to match the original ZIP byte-for-byte.** Original checksums must not be represented as GitHub blob checksum evidence.

Original ZIP SHA-256: 954cfa663b513dd6ee1ddad2eadf7206bb4b736f6bb4eaf48bcbc6dfdb8ce1e0

## Acceptance gates still required
1. Complete upload of all 16 original files under a single prefix using a byte-preserving transfer.
2. Scan original and destination for secrets; do not publish credentials or privately scoped identities.
3. Recalculate original SHA-256 hashes from GitHub-readback file bytes.
4. Execute package validator against readback files and preserve negative-control evidence.
5. Open and review documentation PR; only merge after evidence checks pass.
6. Update AGENTS.md pointer and post redacted handoff status to GitHub Issue #3 after the verified merge.
7. Never claim any F&O/equity runtime success merely from document upload.
