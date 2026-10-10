# PM-003 — Windows Shell desktop.ini Creep into Git Trees

## 1. Problem Statement & Root Cause
Windows Explorer automatically generates hidden `desktop.ini` configuration files inside folders whenever view settings, icons, or folder properties are viewed. If `.git/refs/` or working directories contain `desktop.ini`, git operations (especially ref resolution and branch switching) can fail or pollute commit trees.

## 2. Impact
Corrupted ref paths in `.git/refs/heads/`, unexpected dirty working tree statuses, and failed git push operations.

## 3. Resolution & Commit
- Added `**/desktop.ini` and `*.ini.tmp` to `.gitignore`.
- Explicitly excluded `desktop.ini` from git tracking and pre-commit checks.
- Zero `desktop.ini` files tracked in repository index verified by `git ls-files '**/desktop.ini'`.

## 4. Prevention & Forensic Gates
- Pre-commit hook and `tools/encoding_source_gate.py` enforce exclusion of `desktop.ini`.
- Checked in proof ledger check P-04 (`desktop.ini zero tracked`).
