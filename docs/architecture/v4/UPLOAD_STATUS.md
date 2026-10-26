# V4 GitHub publication audit — 2026-10-26

Status: **PARTIAL / HANDOFF BLOCKED / DRAFT PR #212**. Not approved for merge or certification.

## Independently verified
- 9/16 original archive members now have exact Git blob SHA matches against the original ZIP source bytes (Git SHA-1 blobs, independently calculated from the original archive bytes).
- Original source ZIP contains 16 members; all source members exist in the ChatGPT file container.
- GitHub branch: docs/architecture-v4-handoff-20261026
- Main untouched; no cloud or trading setting changed.

## Original archive members exact-byte verified
01_BASELINE_ARCHITECTURE_V1.md
02_EXECUTION_AND_COORDINATION_V2.md
03_LOCAL_AGENT_EXECUTION_ORDER.md
04_MACHINE_READABLE_STATUS_TEMPLATE.json
05_FAILURE_FORENSICS_AND_PREVENTION_V3.md
09_PREHANDOFF_GAP_CLOSURE_V4.md
10_AGENT_HANDOFF_PROTOCOL_V4.md
11_OWNER_OUTCOME_AND_METRIC_CONTRACT.md
README_START_HERE.md

## Present but NOT byte exact (3)
06_RELEASE_ACCEPTANCE_MATRIX.csv
07_HISTORICAL_INCIDENT_REGISTER.csv
13_HARD_STOP_ACCEPTANCE.csv

## Missing from GitHub (3)
08_MANIFEST_SHA256.json
12_SOURCE_AND_PERMISSION_REGISTER.csv — source content upload hit safety block; do not bypass
14_FILE_MANIFEST.json

## Present but NOT source-byte verified
validate_package.py — source file is present and its Git blob matched original; no test execution on remote checkout yet.

## Remaining mandatory gates
1. Secure byte-exact publication of the three unmatched CSVs and three absent files.
2. Verify all 16 original Git blob hashes against source archive SHA-256 manifest.
3. Execute validator on GitHub checkout and negative control; require PASS/FAIL evidence.
4. Review privacy/security and CI status on exact final commit.
5. Obtain review and protected merge; publish canonical AGENTS.md pointer and issue coordination.
6. Do not claim production or prediction success from documentation publication.

Original ZIP SHA-256: 954cfa663b513dd6ee1ddad2eadf7206bb4b736f6bb4eaf48bcbc6dfdb8ce1e0
