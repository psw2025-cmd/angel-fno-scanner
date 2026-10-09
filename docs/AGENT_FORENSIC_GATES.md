# Mandatory Agent Forensic Gate — Lessons from --json-only Partial Fix

**Date:** 2026-10-09. **Evidence source:** user-provided `w.txt`, live independent isolated worktree `fix/json-only-flag` at historical SHA `4f76525`. **Scope:** all AGY, ChatGPT, Codex, Cursor, Gemini and CI agents working on angel-fno-scanner. **Do not infer a PASS from a narrative.**

## Proven incident and causal chain

1. CLI handler `elif args.verify` used `getattr(args,'json_only',False)`, but `argparse` never registered `--json-only`. The fallback silently hid incomplete implementation during ordinary `--format json` testing.
2. The reported indentation failures came from partial string replacement and unsafe editor encodings; syntax checks must precede test execution, but AST checks cannot prove CLI semantics.
3. Live `--verify` calls involve external Sheets/BQ and may fail due to access, HTML error responses, credentials, service availability, stale spreadsheet ID, or network; distinguish CLI protocol errors from upstream audit failures.
4. Windows shell `python`, subprocess PATH resolution, PowerShell pipeline exit semantics, `PYTHONIOENCODING`, stdout and stderr can disagree. Always record `sys.executable`, environment, exact exit code and both streams, without exposing secrets.
5. Repeated tests are only independent if they exercise the correct process, same pinned source and isolated dependencies; a three-times PASS on a mocked CLI does not certify production Sheets/BQ.
6. Destructive branch reset or `checkout -B` can erase uncommitted work; create isolated worktrees, preserve dirty state, and use ordinary non-force push.
7. Proof text in `C:\Temp` is a local snapshot, not durable signed cloud evidence. Publish sanitized artifacts and hashes through reviewed CI.
8. A green CI job can coexist with critical `BLOCKED` proof ledger checks. Require evidence-complete gate, not workflow success alone.

## Universal rules 17–30 (mandatory before every code change)

17. **Structural Python edits:** no regex/string indentation surgery. Use AST-aware tooling or bounded line-index edit with exact anchors; compile after each edit.
18. **Layered tests:** AST parse, CLI `--help`, parser option, handler behavior with fake services, stdout/stderr JSON protocol, CP1252 console, backward compatibility, full pytest, and external readbacks are separate gates.
19. **One logical change per commit:** keep parser/handler feature and its regression tests together; do not bundle unrelated gitignore, emoji, deployment, or workflow edits.
20. **Non-destructive Git preflight:** capture `git status --porcelain`, branch, HEAD, worktrees, remote; never reset dirty branch or rewrite shared history.
21. **Evidence before claims:** write `C:\Temp\AGENT_PROOF_<UTC>.txt` with exact commands, exit codes, raw *sanitized* output, source SHA, environment, timestamps, and rollback; no false PASS.
22. **No force push by default:** use ordinary push; `--force-with-lease` only when explicitly authorized for an isolated branch.
23. **Source and environment identity:** pin `sys.executable`, installed dependency hashes, interpreter encoding, timezone, OS, shell, Git SHA, and service endpoint before reproducing.
24. **Test protocol independently of external availability:** mock `run_full_verification` with PASS/FAIL and warning-on-stderr cases; separately test live Sheets/BQ with credentials.
25. **Machine-readable contract:** JSON-only mode must produce exactly one valid JSON document on stdout; stderr must not contain secrets; non-PASS audit exits nonzero but valid JSON can still be emitted.
26. **No hidden exception masking:** exceptions become classified error evidence with a stable code, never silent PASS or HTML dumped as a JSON result.
27. **Change-impact graph:** search all CLI invocations in repo, workflows, PowerShell, tests, documentation and cloud manifests; update every affected caller or retain compatibility.
28. **Cross-agent review:** AGY provides local dependency analysis; ChatGPT independently verifies exact Git diff, tests, cloud gates and output hashes. Record disagreements; neither agent self-certifies.
29. **Evidence retention:** archive redacted proof, test matrix, source SHA and rollback to CI artifacts/immutable store; do not commit raw secrets or personal data.
30. **Fail closed on unresolved blockers:** do not commit/push a claimed completed repair when mandated tests fail. Document missing prerequisites and next evidence-driven repair.

## Minimum automated regression matrix

| Layer | Expected evidence | Failure interpretation |
|---|---|---|
| Python syntax | AST parse + `py_compile` | Parser/encoding break |
| CLI discovery | `--help` lists `--json-only` | Registration break |
| CLI positive | Mocked PASS; parse exactly one JSON stdout | Output contract break |
| CLI negative | Mocked FAIL; parse JSON and exit 1 | Error propagation break |
| CLI compatibility | `--format json` still works | Public API regression |
| Encoding | CP1252 and UTF-8 subprocess output | Terminal encoding break |
| Live verification | Independent Sheets/BQ/exchange timestamps and run IDs | External data/auth/consistency break |
| Repo impact | Ripgrep callers + CI YAML + PowerShell + docs | Unpatched downstream caller |
| Multi-run | 3 repeat executions with semantic normalization | Nondeterminism/side effects |
| Recovery | Worktree isolation, clean diff, rollback command | Destructive branch risk |

## Latest live status

The independent worktree inserted the missing `argparse` line and confirmed AST and interactive help in PowerShell. The mandated live verification failed due to external service and/or interpreter context problems; therefore no commit/push of the CLI repair is authorized. The authoritative text proof is under `C:\Temp\AGENT_PROOF_*.txt` and must be read before next work. **Do not claim permanent resolution until the full matrix and cross-agent review pass.**
