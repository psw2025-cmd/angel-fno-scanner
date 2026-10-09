# PM-001 — Windows cp1252 source/output regressions

Observed: Python stdout cp1252, code page 850, and unsafe substitutions corrupted a staged Python file at line 2. Source syntax must be tested before writes. Never blanket-remove legitimate Unicode data.

Prevention: tracked staged Git blob syntax/encoding gate; Windows and Linux CI; explicit cp1252 negative tests; CLI registration tests; preserve dirty worktrees and AGY routing. Existing Unicode is grandfathered; newly introduced non-ASCII is blocked until reviewed.

Historical evidence: 2026-10-09, 105 tracked Python files, 28 with non-ASCII, staged file SyntaxError. Revalidate at every PR and retain negative tests.

Rollback after merge: git revert <merge_sha> (after inspecting dirty state).
