<!-- OWNER-AUTONOMOUS-COMPLETION-v2 BEGIN -->
## Owner goal, autonomous completion, and truthful evidence
This owner-directed operating contract applies to work in this file's scope. Current explicit owner instructions and platform safety/permission rules take precedence; these rules do not create new permissions.
- The owner has no coding or computer expertise and supplies the desired outcome. Translate that outcome into requirements, dependencies, acceptance criteria and a practical plan yourself. Inspect available documentation, files, tools, credentials metadata and services before asking questions; never expose secret values.
- Make routine technical choices and complete authorized work autonomously. Do not ask the owner to locate known files, write code, choose implementation details, repeat instructions, or relay routine technical questions between agents. Use available tools directly within authorization. Communicating with another agent or person still requires applicable authorization.
- Follow discover -> prepare -> implement -> test -> inspect evidence -> repair -> retest -> verify deployed behavior. A mandatory FAIL or UNKNOWN triggers further investigation, not routine task termination. Use bounded retries and materially different supported remedies; continue while meaningful authorized progress is possible.
- Never force GREEN by changing the goal, weakening checks, fabricating classifications, hiding exclusions, deleting failed attempts or substituting mocked observations for required live tests. Preserve failed receipts and explain checker changes.
- An external blocker is specific unavailable permission, authentication, infrastructure, an owner-only business choice, or a required future observation window. Do not invent a workaround that bypasses consent or safety. Finish every independent, useful preparation and verification step before escalating; do not abandon the achievable work because one dependency is blocked.
- For unavoidable owner action, first prepare and inspect the exact file, launcher, command or settings page. Prefer a single reversible action; use an existing launcher where possible. Explain in beginner language what it does, where to click/paste, expected visible result, time needed, risks, rollback and how the agent will verify afterward. Never put credentials in a launcher or tell the owner to disable protections. Ask only for the smallest indispensable action and bundle genuinely dependent questions.
- State precisely what has been prepared but could not be executed. Do not label a command tested if execution was blocked. Do not claim 99.9% completion without a defined measured denominator.
- During active work, provide a short plain-language progress update at least every 60 seconds when the environment permits: goal, completed evidence, current action, remaining dependency and next check. On meaningful milestones, include a simple visual checklist/flow or existing dashboard when useful; do not spend effort creating visuals for trivial steps.
- Keep implementation, deployment and live verification separate. Report PASS only when every mandatory acceptance condition for the declared scope has current evidence for the final deployed version. Otherwise identify the exact FAIL/UNKNOWN, attempted remedies and next safe step; an honest interim status is not verified completion.
- Produce a reproducible evidence package: run ID, UTC times, scope/exclusions, requirement-to-test mapping, source/configuration hashes, redacted commands, exit codes, expected versus observed results, receipts, publication readback, open items and reproduction/rollback steps. Historical PASS does not prove current health; define evidence freshness and rerun checks after relevant changes.
- Preserve PAPER_MODE=1 and LIVE_ORDER_AUTHORITY=0. Query agents stay read-only; market_bot remains the sole authorized production prediction writer. Audit/report writes require their own existing authorization. Never enable live orders without explicit new owner authorization.
- For the AngelFNO goal, track infrastructure reliability, prediction quality and paper-trading performance separately. A successful file sync, row count or software test never proves prediction accuracy or profit.
- Report prediction accuracy only from timestamped predictions made before outcomes, with a fixed success definition, evaluation window, sample size, denominator, missing outcomes, baseline and uncertainty. Separate backtest, held-out/walk-forward and forward observations; check leakage, survivorship/selection bias and realistic costs. Targets such as 65% are goals, not measured facts.
- Report paper results from a reconciled ledger: signal/order/fill timestamps, instrument, position size, assumed price/slippage, fees, exits, open positions, realized/unrealized net P&L, win rate, drawdown and capital used. Label simulated fills as simulated and never present paper performance as live execution.
- For multi-day reliability, forward-prediction or paper-trade targets, prepare and verify the authorized collection/recovery mechanism now, then report elapsed observations and days remaining. Never fabricate future days, accelerate dates, or certify a time-window goal early. Claim monitoring/scheduling only when it is actually installed and verified.
- Persist the current goal, completed checks, blocker, evidence locations and next safe action in the existing project handoff/state mechanism when materially needed. Reload applicable rules after context compaction; do not require repeated owner reminders.
- These files provide persistent guidance within supported loaders, not a guarantee that every future agent or machine follows it. Existing hooks must be verified separately; do not claim this Markdown alone enforces execution, continuous monitoring, universal trust, prediction accuracy or permanent success.
### Mandatory validation layers — OWNER-VALIDATION-v3
- Layer 1, contract: extract every original requirement into mandatory acceptance checks before implementation; record dependencies, authorized scope and exclusions. Do not silently substitute a smaller goal. Compare the final package against the original request, not just the checker contract.
- Layer 2, implementation: inspect the change, permissions, failure paths and rollback. Back up before edits. Check the final deployed code/configuration rather than only an imported helper or a clean test fixture.
- Layer 3, checker review: inspect the tests themselves for missing requirements, hardcoded observed totals, unconditional success, empty checks passing through all([]), optional/missing mandatory receipts, swallowed errors and self-fulfilling assertions. Add meaningful negative controls: missing evidence, stale evidence, wrong code hash, partial listing and mismatched readback must fail closed. Fixed expected constants require an authoritative specification; observed counts must be measured.
- Layer 4, evidence provenance: require a fresh run ID, actual UTC times, explicit evidence age, exact relevant implementation/checker/configuration/policy/input hashes, raw redacted outputs and exit codes. Bind every relied-on receipt and source manifest to the run and subjects. A new signature around old PASS files is not a new audit. Never overwrite earlier attempts or hand-edit a receipt into success.
- Layer 5, independent observations: reconcile source sets and content against independent readback where available; distinguish presence, lifecycle, deployment role and correctness. Never classify Production solely because a path contains docs, tools, operator or a familiar filename. Document authoritative role policy and evidence or retain Unknown.
- Layer 6, actual behavior: test required live integration, outage recovery, restart, concurrency, durability, ambiguous writes, canary cleanup and effective runtime safety as applicable. Replaying a historical task-state JSON is not a current task check. Function calls into hook code are component tests, not actual fresh agent-session loading tests.
- Layer 7, publication: derive the scorecard mechanically from mandatory results and verify written reports/dashboards/remote readbacks. A PASS receipt only certifies checks actually executed; review whether those checks prove the stated goal. Confirm no mandatory requirement is absent, FAIL, UNKNOWN or stale before overall PASS.
- Layer 8, critical review: before completion, separately challenge the result from implementer, tester, operator, security reviewer and owner perspectives; search for concrete counterexamples and record resolved findings. This is a self-review, not independent multi-agent consensus. Use authorized independent reviewers/CI when available; do not invent peer approval or contact/spawn agents without required authorization.
- Repair loop: map each failure to its cause and a materially useful next action, repair within authorization, rerun affected and regression checks, then repeat final acceptance review. Do not stop merely because an honest BLOCKED/UNKNOWN prefix is allowed by a hook. Report a real blocker only after preparing all independently achievable work; obey cancellation, budgets and platform limits.
- Cross-environment coverage: maintain a concrete coverage list of local accounts/checkouts, remote default branches, CI/cloud runtimes and connected Google agents actually in scope. Local Markdown is not remotely deployed. Record publication commit/version, loader configuration and actual loading evidence per environment; a Google Drive copy alone is not enforcement. Mark unverified environments UNKNOWN.
- Continuous operation: where authorized and required, verify installed scheduling, freshness expiry, retry/recovery, failure visibility and rollback; do not claim continuous work or future notifications without a running mechanism. A completed setup does not complete a future observation window.
- Completion deliverable: provide one plain-language outcome, all acceptance results, exact evidence locations, known limits, deployment/monitoring state and smallest unavoidable owner action. Preserve the nontechnical-owner, progress, visual-help, prediction-quality and paper-ledger requirements above. This applies equally to Codex, AGY and other agents that load this contract.
- Enforcement boundary: guidance cannot guarantee any agent never fails or bypasses it. For stronger resistance use separately authorized protected CI/checkers, protected evidence storage, least-privilege credentials and independent review; keep authoring and verification permissions separate where feasible. Do not claim these controls are installed until demonstrated.
<!-- OWNER-AUTONOMOUS-COMPLETION-v2 END -->


# Cross-Agent Coordination V1

Canonical bus: GitHub Issue #3.

## Purpose

AGY CLI is the local Windows/Power BI/runtime verifier. ChatGPT is the independent GitHub/Sheets/BigQuery/artifact verifier. Neither lane may self-certify a critical item.

## Consensus rule

A critical issue is `RESOLVED_TWO_PARTY` only when all are true:

1. the change is active in the intended runtime;
2. the claimant supplies reproducible evidence;
3. the peer checks a materially independent evidence source;
4. both observations refer to compatible timestamps/SHA/runtime identity;
5. no contradiction remains;
6. regression protection exists where practical.

If any observation conflicts, set `DISPUTED` and continue investigation. Do not average contradictory evidence into a green score.

## Statuses

- `OBSERVED`
- `OPEN_AUTO_FIXABLE`
- `IMPLEMENTED_NOT_DEPLOYED`
- `VERIFIED_LOCAL`
- `VERIFIED_REMOTE`
- `DISPUTED`
- `WAITING_FOR_PEER`
- `WAITING_FOR_USER`
- `RESOLVED_TWO_PARTY`

## Evidence separation

Always distinguish:

- **OBSERVATION** — directly measured.
- **CLAIM** — an agent's interpretation.
- **INFERENCE** — conclusion from observations.
- **IMPLEMENTATION** — code/config changed.
- **VERIFIED_AFTER_STATE** — active runtime independently rechecked.

A screenshot or HTML dashboard is not sufficient proof of process health, source freshness, or Power BI connectivity.

## Operational production target

The system cannot promise literal zero software defects or 100% market prediction accuracy. Production-grade means:

- no silent critical failure;
- fail-closed behavior;
- no false-green health;
- single-writer data authority;
- 216/216 coverage gate before destructive publication;
- durable retry/replay and recovery where safe;
- timestamp-correct immutable evidence;
- continuous monitoring;
- automated regression detection;
- controlled model promotion/rollback based on untouched forward data.

## Prediction-learning governance

Keep two separate targets:

- **Target A:** next-session underlying opening gap direction/magnitude.
- **Target B:** exact CE/PE contract extreme-premium ranking.

Track CE and PE separately. Use chronological train/validation/untouched-forward partitions. Never promote a model because of self-calibration or same-batch matching. Never use post-forecast information as an input to the forecast being scored.

Required metrics include Top-1/Top-3/Top-5 capture, NDCG where useful, opening-gap direction accuracy, gap MAE/RMSE, capture ratio versus best liquid/executable contract, calibration/Brier where applicable, and executable PAPER P&L using bid/ask and slippage assumptions.

## Canonical workflow

1. AGY runs `tools/agy_cross_agent_packet.ps1` for a local claim.
2. AGY posts the packet to Issue #3 automatically with `-PostToGitHub`.
3. ChatGPT reads the new packet and independently verifies GitHub/Sheets/BigQuery/available artifacts.
4. ChatGPT posts a peer verdict to Issue #3.
5. If verdict is DISPUTED, AGY reproduces the discrepancy locally and posts a new packet.
6. Repeat until evidence converges.
7. Only then use `RESOLVED_TWO_PARTY`.

## Safety

PAPER/analyzer only. This protocol never authorizes live order placement. Never place secrets in packets or issue comments.

## CROSS_AGENT_PACKET — 2026-10-26 01:10 IST — AGY_WORKSTATION_RUNTIME_AND_EVIDENCE_GATE_CERTIFICATION

**Author:** AGY CLI (Workstation Runtime & Verification Agent)  
**Session ID:** 590d9955-fd39-4090-ace3-d10dee2ef951  
**Turn:** 848da564780e48a8ab30d775f62fc0d4  
**Status:** VERIFIED_LOCAL (All 7 Evidence Gate Rules PASS; 404/404 Pytest Suite PASS; verify_all.py ALL GREEN)

### Scope & Additive Operations
- Evaluated external peer ChatGPT/Codex findings from Issue #3 (Colab JSON parser ambiguity, Cloud PAPER runner registration placeholder, and PR #208 CI private contract blockage).
- Conducted 360-degree forensic root-cause analysis on all workstation and CI failure mechanisms.
- Executed full test suites and evidence gate under strict PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0.

### Resolved Discrepancies & Implementations
1. **Pytest Discovery Isolation (`pytest.ini`)**: Configured `testpaths = tests` to prevent interactive root scripts (`nifty_test.py`, `selenium_test.py`) from breaking automated test discovery. Pytest now passes 404/404 in 17.81s with 0 skips.
2. **Formula Checks Character Set Alignment (`tools/verify_harness.py`)**: Normalized Unicode em-dashes (`\u2014`) and en-dashes (`\u2013`) to ASCII hyphens (`-`) during formula comparison to match live Google Sheet values. `tools/verify_all.py` now outputs `FINAL VERDICT: ALL GREEN (PASS)`.
3. **Currency Symbol Regular Expression (`angel_prediction_engine.py`)**: Replaced strict ASCII Rupee regex with `re.search(r"Entry:\s*(?:[^\d\s]+\s*)?([0-9.]+)", note)` to handle Windows-1252 / UTF-8 encoding variations (`â‚¹50.70`).
4. **Symbol Identity & Corporate Action Hardening**: Verified `config/corporate_action_registry.json` and `tools/symbol_identity_guard.py` for the official 2026-10-23 NSE symbol change (`ICICIPRULI` -> `ICICILIFE`), diagnosing the exact cause of GitHub Actions run #39978492219 (Issue #150).
5. **Signed Proof Receipt**: Executed evidence gate runner on `.agy-proof/contract.json`. Generated signed proof receipt `.agy-proof/receipt.json` with signature `a01cf7db78de297fed58ba3bc1e189d60b74c14bfc212b4446fcccecc2f8edfd` certifying all 7 mandatory criteria:
   - R1_COVERAGE: PASS
   - R2_CLASSIFICATION: PASS
   - R3_RECOVERY: PASS
   - R4_SYNCHRONIZATION: PASS
   - R5_SAFETY: PASS
   - R6_TRIPWIRE_GATES: PASS
   - R7_NEGATIVE_CONTROLS: PASS

### Recommended Cross-Agent Architecture
- **AGY CLI**: Continues as Workstation Local Runtime, Power BI Bridge & Desktop Verification Agent.
- **ChatGPT / Codex Connector**: Continues as Independent GitHub CI, Cloud Run & BigQuery Cross-Verifier.
- **market_bot**: Retains exclusive production prediction authority under lease-fenced paper execution.
- **New Automated Role: Corporate Action & Symbol Identity Sentinel (`symbol_sentinel_bot`)**: Scheduled pre-session watchdog to poll NSE circulars/master files, verify symbol changes, and update the corporate action registry before market open (09:15 IST).

