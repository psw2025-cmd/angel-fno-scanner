---
owner: psw2025-cmd
owner_type: non-expert-100-percent-owner
approval: full-auto-fix
project_id: fno-angel-prod-1790444589
repos:
    - psw2025-cmd/angel-fno-scanner
    - psw2025-cmd/Genesis_System3
ultimate_goal: "Prove system can predict gap-up high-rise symbols BEFORE rise with high accuracy and profit, then start small paper trading"
phases:
  phase1_daily_stable:
    goal: "219 rows daily without failure for 30 days"
    fix_file: "FIX-NOW.bat"
    evidence_command: "bq query --project_id=fno-angel-prod-1790444589 'SELECT DATE(snapshot_timestamp) as cycle_date, COUNT(*) FROM \`fno-angel-prod-1790444589.fno_predictions.option_predictions_live\` GROUP BY cycle_date ORDER BY cycle_date DESC LIMIT 5'"
  phase2_backtest_accuracy:
    goal: "Prove 65%+ accuracy for gap >3% from last 1 year data, show profit per lakh"
    missing_file_to_create: "tools/backtest_gapup.py"
    evidence_output: "backtest_results.csv with predicted vs actual + profit"
  phase3_live_gapup_proof:
    goal: "60 days live prediction log - predict at 3:30 PM, verify next day gap"
    missing_file_to_create: "tools/gapup_verifier.py"
    evidence_output: "gapup_live_log sheet"
  phase4_paper_profit:
    goal: "30 days paper trading profit positive"
    blocked_by: "Issue #3 needs independent verification"
    evidence_output: "paper_ledger.csv"
agent_global_rules:
  must_always_provide:
        - simple_truth_2_lines_family_language
        - evidence_from_live_command_not_guess
        - single_bat_or_ps1_file_to_double_click
  must_never_do:
        - guess_pr_number_474_475
        - claim_PASS_or_certification_without_fresh_execution_evidence
        - accept_generic_python_as_scanner_health
        - substitute_bigquery_for_broker_api
        - count_entire_table_without_session_date_filter
        - self_assert_paper_mode_inside_checker
        - treat_nse_holiday_or_weekend_as_scanner_failure
  anti_shortcut_tripwire_rules:
    gate1_process: "Call market_calendar.market_session_state() first. Require a dedicated universal_supervisor.py or scanner.py PID only when status is OPEN (09:15-15:40 IST). Before open, after close, at night, on a weekend, or on a holiday, a missing scanner is expected. Never accept a generic python/pythonw daemon as the scanner."
    gate2_broker: "Verify live HTTP ping to https://apiconnect.angelone.in and https://api.dhan.co. Never substitute BigQuery."
    gate3_bigquery: "Call market_calendar.market_session_state() first. Unless status is OPEN, name the clock state and do not treat a missing scanner or today's row count as a failure. When OPEN, verify 219 rows for that session via CURRENT_DATE('Asia/Kolkata'). Never count the entire table unfiltered."
    gate4_safety: "Inspect deployed state.json/environment for PAPER_MODE=1 and LIVE_ORDER_AUTHORITY=0. Apply the 60-minute freshness limit only when market_session_state() is OPEN. Overnight or closed-market age is not a failure. Never self-assert inside the checker."
    zero_fake_green: "Turn RED (color 4F) and exit code 1 on any gate failure. All 5 negative control modes must fail closed."
  when_owner_says_fix: "Fix Phase 1 only, give FIX-NOW.bat"
  when_owner_says_achieve_ultimate_goal: "Execute all 4 phases, create missing files, give proof CSVs"
---

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



# OWNER CONTRACT - Project guidance for agents that load this file

## Who is Owner
psw2025-cmd - Owner, not expert. Wants 1 file to double-click. Has given FULL approval for: bq DELETE, gcloud run jobs update, gh pr merge, gh issue close.

## Ultimate Goal (1 Year Goal)
Prove system can generate profit with high accuracy for gap-up high-rise symbols BEFORE they rise, then start lesser paper trading.

## What is 100% CLOSED for Owner
- Phase 1: 219 rows daily + 1/1 complete + 0 issues
- Phase 2: backtest_results.csv shows >65% accuracy
- Phase 3: gapup_live_log shows live predictions hitting
- Phase 4: paper_ledger shows profit

## How Agent Must Achieve Goal by Self-Discovery
1. Run gh api to list md files - read them live
2. Run gh pr list - find latest PR (475 or 474) - do not guess
3. Run bq query to check 219 rows only after market_calendar.session_closure() says the NSE session is open. On a holiday or weekend, name the day and do not guess.
4. If missing file for Phase 2/3, CREATE it yourself from present repo code
5. Give 1 file per phase that owner can double-click

## Permanent Fix for Past 1 Year Loop
Same 3 locks: run_id, secret, lease. Create 3 permanent BAT files so owner never faces again.

## Operational Rules & SSOT Infrastructure (Configured Baseline; Reverify Each Run)
1. **Google Sheets SSOT Credentials**:
   - Master File Inventory ID: `1xyqUcEtXrh1pdJTO2N-UASZf4fssxbq7bfEjOp4LvOY`
   - Production Options Stream ID: `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`
   - Active Service Account Key: `C:\Users\ADMIN\Downloads\angel_sheets_key.json`
   - Service Account Identity: `angel-sheets-bot@fno-angel-prod-1790444589.iam.gserviceaccount.com`
2. **Required Safety Constraints (Verify Effective Values in Each Relevant Runtime)**:
   - `PAPER_MODE = 1` permanently.
   - `LIVE_ORDER_AUTHORITY = 0` permanently.
3. **Background Watchdog Automation**:
   - Task Name: `\SSOT_MD_Inventory`
   - Script: `C:\AngelFNO_Workstation\ssot_md_daemon.py --daemon`
   - Trigger: At Logon + Hourly recurring (every 60 minutes) with automatic exponential retry backoff (5s, 15s, 30s).
   - Local Outbox CSV: `C:\AngelFNO_Workstation\Master_File_Inventory_Local.csv`
4. **Visual Analytics & Reporting**:
   - Plotly Interactive Dashboard: `C:\AngelFNO_Workstation\reports\master_visual_audit.html`
   - Heatmap Evidence: `C:\AngelFNO_Workstation\reports\inventory_structure_heatmap.png`

## Autonomous Completion and Evidence Requirement (CODEX-1)
Apply AGY-EVIDENCE-INTEGRITY-v1 in C:\Users\ADMIN\.gemini\config\evidence-integrity\POLICY.md and its RUNBOOK.md for every substantive task.
1. A FAIL or UNKNOWN is an instruction to investigate and continue working; it is not task completion.
2. For every mandatory FAIL or UNKNOWN: identify the exact cause and missing evidence; make authorized repairs or obtain evidence through inspection and testing; rerun affected and regression checks until all pass or an external blocker is hit.
3. Never obtain green by weakening tests, inventing classifications, suppressing errors, or substituting simulated results for live verification.
4. Distinguish temporary failures from persistent blockers with bounded retries; escalate only when genuine external blockers occur, continuing independent work meanwhile.
5. Before declaring completion, verify all requirements against final deployed code and produce a self-contained, reproducible evidence package.
6. Apply this workflow persistently without requiring owner reminders for routine tasks.
