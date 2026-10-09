# Agent Contract

Every agent working in this repository MUST follow these rules. They are enforced by the pre-commit hook and verified by the post-commit sync workflow.

## Rule 1 — Every change has a commit
If you edit a file, commit it before stopping. No work-in-progress left in the working tree.

## Rule 2 — Every commit updates CHANGELOG.md
Add a section to `docs/CHANGELOG.md` describing: what, why, evidence, rollback. Same commit. Same push.

## Rule 3 — Every fix has a test
If the defect was not caught by an existing test, add one. If the fix only passes existing tests, say so explicitly.

## Rule 4 — Every schema change has a backup
Before any `ALTER TABLE` or `CREATE OR REPLACE`, create `<table>_backup_<YYYYMMDD_HHMMSS>`. Verify the backup row count matches the source. Keep for 24 hours minimum. Document the rollback in `CHANGELOG.md`.

## Rule 5 — Every claim has pasted output
Never write "PASS" without the command output that proves it. Never paraphrase. Paste verbatim.

## Rule 6 — Never edit .py files with PowerShell Set-Content
Use Python `pathlib` with `encoding="utf-8"`, or VS Code, or any UTF-8-safe editor. PowerShell `Set-Content` corrupts emoji and normalizes line endings. This has broken the repo twice.

## Rule 7 — Every BigQuery change is verified after
After any DDL, query `INFORMATION_SCHEMA.COLUMNS` for the affected table and column. Paste the result. Confirm it matches intent.

## Rule 8 — Protected files require reading first
`writer_guard.py`, `publication.py`, `universe_contract.py`, all files in `tests/`. Read before editing. Understand the role. Then change.

## Rule 9 — Revert on failure
If a fix fails a test, run `git checkout HEAD -- <file>` before trying again. Never stack partial fixes. The cascade of failures on 2026-10-05 was caused by stacking partial fixes.

## Rule 10 — Update AGENT_HANDOFF.md when finished
The next agent reads it first. Keep it current or the next agent starts blind.

## Rule 11 — Do not rename public helpers
Any function referenced by `tests/` is a public interface. `build_news_append_job_config` is one example. Renaming breaks the suite. If you must rename, update every reference in the same commit.

## Rule 12 — Every DDL migration is reversible
Document the rollback SQL in `CHANGELOG.md`. Verify the rollback works in a scratch dataset before running the migration on production.

## Rule 13 — Verify before you claim
Run `python tools/verify_all.py` before declaring any fix complete. Paste its output.

## Rule 14 — One file, one purpose
Do not create catch-all files. `CHANGELOG.md` is append-only history. `DEFECT_REGISTER.md` is defects. `AGENT_HANDOFF.md` is current state. Do not mix.

## Rule 15 — Agents coordinate through AGENT_LOCK.md
Before editing any file, read `docs/AGENT_LOCK.md`. If another agent holds the lock, do not proceed. Claim the lock, do the work, release it after push.

## Rule 16 — Never delete history
Append to `CHANGELOG.md` and `DEFECT_REGISTER.md`. Do not remove entries, even for closed defects. History is the audit trail.

## Rules 17–30 — Mandatory forensic verification
The complete, enforceable definitions and regression matrix are in [AGENT_FORENSIC_GATES.md](AGENT_FORENSIC_GATES.md). These rules cover structural source edits, AST+CLI+JSON tests, one logical commit, clean Git preflight, evidence before commit, no force push, pinned interpreter, mock/live isolation, stderr/encoding, error classification, impact search, independent cross-agent review, durable proof, and fail-closed blockers.
