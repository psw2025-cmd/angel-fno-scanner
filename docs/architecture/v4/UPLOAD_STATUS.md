# V4 handoff publication audit — 2026-10-26

Status: **15/16 original archive members exact-byte GitHub published; HANDOFF BLOCKED; PR #212 DRAFT — DO NOT MERGE**.

## Verified
- 15 original members of the V4 ZIP are present and GitHub blob SHA matches the blob SHA calculated from the original local archive bytes.
- The original `validate_package.py` script is also published with an exact source blob hash, but has not been run successfully against the remote checkout.
- Source archive SHA-256: `954cfa663b513dd6ee1ddad2eadf7206bb4b736f6bb4eaf48bcbc6dfdb8ce1e0`.
- `main`, cloud infrastructure, broker configuration and live-order settings are unchanged.

## The one original archive member NOT published
`12_SOURCE_AND_PERMISSION_REGISTER.csv` — a GitHub write safety check blocked publication. Do not bypass or disguise the blocked content. A user-authorized permitted publication path or approved replacement/redaction would require separately verified provenance and would no longer constitute byte-exact reproduction of the original archive.

## Remaining acceptance gates
1. Resolve permitted publication of the remaining permissions register.
2. Validate full 16-member original SHA-256 manifest against GitHub-readback bytes and execute the package validator on a GitHub checkout.
3. Test negative cases (missing file and corrupted blob) and preserve CI logs.
4. Complete security/privacy review and review exact-final-SHA CI.
5. Get protected documentation PR review/merge into `main`, add stable AGENTS.md reference, and publish an index and Issue #3 handoff.
6. Keep F&O and Phase 5 PAPER-only; this documentation PR is not a production or prediction certification.

Current file completeness: 15/16 = 93.75%. Final handoff certified: NO.
