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

## Six mandatory release gates — 2026-10-09

**These are release-blocking checks, not a claim of implementation success.** Every check requires Git SHA, UTC timestamp, interpreter, exit code, and redacted evidence. BLOCKED is never PASS.

### Gate 1 — Structural edit, parser, handler and tests
Argparse registration, handler and regression tests must ship in one logical commit. AST/py_compile alone is insufficient. Test CLI help and offline mocked PASS, FAIL and exception paths. Missing --json-only in --help is CLI_BROKEN.

### Gate 2 — Exit code semantics
Exit 0 = audit PASS. Exit 1 = valid audit FAIL when machine-readable JSON explains the failure; this is not necessarily a CLI defect. Exit 2 from argparse = CLI_BROKEN. Unhandled exceptions are INFRA_OR_RUNTIME_ERROR. Capture exit code before any pipeline and inspect stdout/stderr separately.

### Gate 3 — JSON-only purity
Stdout must contain exactly one JSON document even when dependencies write to stderr. On Linux run:

    set +e
    python agent_cli.py --verify --json-only 1>/tmp/out.json 2>/tmp/err.txt
    rc=$?
    python -m json.tool /tmp/out.json >/dev/null
    echo "audit_exit=$rc"

Do not use && to skip JSON validation after a legitimate audit FAIL (exit 1). Validate offline mocked PASS/FAIL/exception, UTF-8 and CP1252. A Google Sheets APIError that prevents JSON emission is a separate JSON contract defect.

### Gate 4 — Cloud evidence and independent readback
C:\Temp local proof is insufficient. Publish sanitized evidence to GitHub Actions artifacts, authenticated GCS gs://fno-angel-evidence/ and an idempotent BigQuery fno_predictions.ledger row. GCS uses short-lived Workload Identity Federation, not service account JSON keys. BigQuery insertion is BLOCKED until project, dataset/table schema, IAM, deduplication key and retention are verified. Never create/overwrite a table blindly. Each proof includes SHA, UTC timestamp, run ID, checks, artifact SHA-256 and readback. Never expose secrets or raw API HTML.

### Gate 5 — Git worktree safety
Never git push --force. Use ordinary push; --force-with-lease only if a history rewrite is explicitly approved for an isolated branch. Before checkout/reset/prune inspect git status --porcelain, git worktree list --porcelain, branch, HEAD and agent locks. Never discard uncommitted changes, delete untracked proof, or remove another agent's worktree. Previous recovery reportedly discarded two modified files.

### Gate 6 — AGY independent cross-agent signoff
AGY must independently reproduce and classify gspread.exceptions.APIError [-1] with redacted HTTP status, Sheets ID provenance, authorization and scopes; separately validate JSON-only protocol. An AGY CLI timeout is not signoff. Retry with bounded read-only calls; record AGY raw redacted response and independent ChatGPT review. Until verified, CROSS_AGENT_SIGNOFF=BLOCKED and no production readiness claim or LIVE trading.

**Prior baseline:** commit 5f099c3. These six gates strengthen the universal rules and must be adopted by every agent after the PR merges.

## Mandatory Windows encoding gate
Past: review PM-001, historical regressions and prior fixes. Present: inspect staged blobs, branch, dirty worktrees, interpreter and code page. Pre-action: parse before write and preserve original. Post-action: run tools/encoding_source_gate.py --all, pytest tests/test_encoding_gate.py tests/test_cli_contract.py, Windows/Linux CI, and independent review. Future: enforce CI, retain negative tests and reopen regressions. Never claim live Sheets/BQ verified from a syntax PASS.

---

## Gate 7 — Permanent Quality Control & Future-Proof Safety Gates

Gate 7 establishes the permanent layered governance model across P0, P1, and P2 priority levels:

### Priority P0 Gates (Execution-Blocking)
1. **P0 Python Syntax & BOM Gate**: All `.py` files must parse cleanly with `ast.parse` and be decodable as `utf-8-sig` with zero syntax or unexpected BOM issues.
2. **P0 Console Encoding (cp1252 / UTF-8) Gate**: Output emitted by CLI and test scripts must be compatible with Windows code page 1252. No bare unicode emojis or unhandled characters that crash standard Windows shells.
3. **P0 Branch Protection Gate**: Remote `main` branch protection requires passing `encoding-safety (ubuntu-latest)` and `encoding-safety (windows-latest)`. No administrative bypass or unilateral forced merges.
4. **P0 Non-Destructive Git Safety Gate**: Never use destructive `git checkout -f`, `git reset --hard`, or `git push --force`. All working trees, stashes, and untracked proofs must be preserved.
5. **P0 CLI Protocol Contract Gate**: `agent_cli.py` must register `--json-only`, support `--format json`, reconfigure UTF-8 streams, and emit strictly valid JSON on stdout when requested.

### Priority P1 Gates (Verification & Integrity)
6. **P1 Source Scanner Gate**: `tools/encoding_source_gate.py` detects delta of non-ASCII characters introduced in staged commits, preventing regressions before commit.
7. **P1 Agent Rules Enforcement Gate**: All collaborating agents must adhere to `AGENTS.md` operating contracts and record handoffs on Issue #3 / PR #45.
8. **P1 Layered Test Suite Gate**: Positive and negative tests in `test_encoding_gate.py`, `test_cli_contract.py`, and `test_data_chain.py` must pass 100% across Linux and Windows.
9. **P1 Permanent Incident Memory Gate**: Every critical bug or architectural regression must have an immutable postmortem document under `docs/PERMANENT_MEMORY/PM-*.md`.
10. **P1 Independent Dual-Party Verification Gate**: Changes to shared sinks (Sheets, BigQuery, workflows) must be validated independently by both AGY (local host/data) and ChatGPT (remote/cloud).

### Priority P2 Gates (Monitoring & Long-Term Health)
11. **P2 Scheduled Drift Detection Gate**: Automated daily workflows (`.github/workflows/nasa-daily-proof.yml`) verify 219 universe parity and table freshness.
12. **P2 Evidence Dashboard Gate**: `docs/LIVE_DASHBOARD_FOR_USER.md` maintains live status tracking all 8 systems (Local, Cloud, PowerBI, Sheets, Excel, Colab, BigQuery, GCS, n8n) with clear proof links.

