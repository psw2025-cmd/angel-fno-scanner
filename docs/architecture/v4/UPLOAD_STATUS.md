# Architecture V4 — verified GitHub handoff status (2026-10-26)

**Publication: 15/16 original ZIP files byte-identical.**
**Full archive certification: BLOCKED. Do not merge PR #212.**
**PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0 remain mandatory.**

## Evidence from authenticated GitHub Actions
- Workflow: [Architecture V4 Integrity run 40263549156](https://github.com/psw2025-cmd/angel-fno-scanner/actions/runs/40263549156)
- Tested SHA: `3999bb3d9005903bf5f7cfef6e247427c07b6760`.
- Job `Source byte parity and fail-closed tests`: **SUCCESS**.
  - SHA-256 and byte counts checked against original `14_FILE_MANIFEST.json` for all 13 present manifest-listed files.
  - Original `validate_package.py` deliberately runs on incomplete checkout and correctly returns FAIL because one required original file is missing.
  - Corrupted-byte negative control demonstrates manifest hash mismatch.
- Job `Full V4 archive certification (requires withheld file)`: **FAILURE**, intentionally fail-closed. Not a production/runtime error.

## Remaining content blocker
Original `12_SOURCE_AND_PERMISSION_REGISTER.csv` was rejected by connected GitHub write safety checks. It must not be silently reconstructed, disguised or omitted from an allegedly byte-exact 16-file archive. Original SHA-256 is `ea1c74f105b2e6860194ce2b689f47eef010c34086e011c94674a8644797e719`; original size 1856 bytes.

Original source ZIP SHA-256: `954cfa663b513dd6ee1ddad2eadf7206bb4b736f6bb4eaf48bcbc6dfdb8ce1e0`.

## Only when content blocker is lawfully resolved
1. Upload unmodified original under this path by an approved channel; if blocked again, use an explicitly approved redacted replacement plus regenerated manifest as a **new version**, never claim original byte parity.
2. Read back bytes and verify original SHA-256 and 16-member completeness.
3. Confirm all full-package tests pass at exact final head SHA.
4. Review protected PR #212; merge only after all required checks pass.
5. Establish canonical `AGENTS.md` pointer and cross-agent Issue #3 continuity with evidence.
6. Separately certify cloud/PAPER options and equity systems only using actual runtime receipts.

## Owner status
- Done: architecture files published where permitted, security-constrained branch, validated individual files, positive and negative CI proof, detailed blocker readback, draft PR.
- Pending due to identified external safety block: original final permissions register, 16/16 verification, full CI and merge.
- Owner action: none established that is safe/required immediately.
- Never claim production success based on document publication.
