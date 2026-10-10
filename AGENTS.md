# PROJECT START HERE — Angel F&O Permanent Multi-Agent Operating Contract

> **Canonical file for every human, AI agent, CLI agent, automation, notebook, IDE assistant, connector, or future tool working on this project.**
>
> Repository: `psw2025-cmd/angel-fno-scanner`
>
> **Mandatory rule:** Read this file completely before doing any project work. If another instruction conflicts with this file, stop, record the conflict on the canonical coordination bus, and resolve the conflict before proceeding.
>
> Canonical coordination bus: **GitHub Issue #3 — Canonical Cross-Agent Control Bus — AGY CLI ↔ ChatGPT Production Verification**
>
> This file defines the durable project memory and operating contract. Chat/session memory is helpful context but is **not** the authority for project truth.

---

## 1. Project Mission

Build and continuously improve a production-grade, evidence-driven Angel One NSE F&O market-intelligence and PAPER/analyzer system that:

1. maintains reliable live market ingestion for the supported F&O universe;
2. predicts next-session underlying opening gap direction/magnitude;
3. ranks exact CE and PE option contracts for extreme premium-move potential;
4. tracks real outcomes and learns only from timestamp-valid historical/forward evidence;
5. separates raw market observations, model forecasts, self-calibration, and genuine forward results;
6. automatically detects operational/data/model failures;
7. performs safe bounded recovery where technically appropriate;
8. fails closed instead of publishing false-green or partial data;
9. preserves reproducible evidence for every material claim;
10. uses independent multi-agent verification before declaring critical work resolved.

### Production objective

The project may target:

- 100% monitoring coverage of critical components;
- 100% evidence-backed critical resolutions;
- 100% fail-closed handling of known critical failure classes;
- zero silent critical failures;
- zero false-green critical health states;
- measurable forward improvement in prediction quality.

It must **not** claim that software can have literally zero future defects or that market prediction can achieve guaranteed 100% accuracy.

---

## 2. Permanent Project Memory

No individual AI model, chat thread, terminal session, notebook runtime, or local process is permanent enough to be the sole project memory.

Permanent memory is stored in durable project artifacts:

1. **This file — `AGENTS.md`**: permanent operating contract and start point.
2. **GitHub Issue #3**: live cross-agent coordination, disputes, evidence packets, and resolution history.
3. **Git history / PRs / workflow runs**: exact implementation and test provenance.
4. **BigQuery + Google Sheet + immutable evidence artifacts**: runtime/data proof.
5. **Versioned model/forecast/outcome ledgers**: prediction evidence and learning history.

A new agent must reconstruct current truth from these durable sources rather than relying on remembered narrative.

---

## 3. Mandatory Start Protocol for Every Agent and Every Run

Before any analysis, code change, runtime action, model conclusion, or health verdict:

1. Read this `AGENTS.md`.
2. Read new comments/status on GitHub Issue #3.
3. Inspect current remote `main` and record its SHA.
4. Inspect all open PRs relevant to the intended work.
5. Identify the current runtime/data authority for the claim being evaluated.
6. Read the latest unresolved/disputed items from Issue #3.
7. Verify current time/session context if the claim is time-sensitive.
8. Confirm PAPER/analyzer safety and no live-order authority.
9. Continue from previous verified state; do not restart solved work without evidence.
10. Record a durable handoff/evidence packet when the run produces a material result.

Do not begin by trusting dashboards, screenshots, old reports, old chat claims, or an agent's previous PASS label.

---

## 4. Project Identity and Core Authorities

### Repository

`psw2025-cmd/angel-fno-scanner`

### Google Cloud / BigQuery

- Project: `fno-angel-prod-1790444589`
- Dataset: `fno_predictions`

### Google Sheet

- Spreadsheet ID: `1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`
- Title: `OPTION_SHEET`

Important tabs include:

- `HEARTBEAT`
- `FORENSIC_LIVE`
- `CE_PE_RANK`
- `OPTION_PREDICTIONS`
- `PAPER_ALERT_LOG`
- `PRODUCTION_APPROVED`
- `NEWS_LIVE`
- `NEWS_IMPACT`
- `TOP_GAINERS`

### Colab

Notebook ID: `1AUgfSEkpt9CeOf2Nwo_HLNrNCgLSqCUH`

### Coordination

GitHub Issue #3 is the canonical live coordination bus.

### Runtime truth

Runtime authority depends on the claim:

- local Windows / Power BI claim → prove locally with process/port/file/runtime evidence;
- GitHub code claim → exact ref/SHA/diff;
- Google Sheet claim → exact range + timestamp;
- BigQuery claim → direct query/metadata when available;
- model/forecast claim → immutable issued prediction artifact + later outcome;
- broker health → authentication evidence **and** independent fresh market-data evidence.

No single dashboard or agent owns universal truth.

---

## 5. Source-of-Truth Hierarchy

Use the most direct source for the specific claim.

| Claim | Primary proof | Independent validation |
|---|---|---|
| Code implemented | exact Git commit / PR diff | peer inspection on same SHA |
| Tests passed | workflow run/job or reproducible local test output | test source + independent rerun |
| Local process alive | PID, process name, creation time | listener/process relationship or second runtime check |
| Power BI active | PBIDesktop/msmdsrv PID + listener/process owner | rendered data/source freshness |
| Broker authentication | broker session result without secrets | fresh market data |
| Market data fresh | direct source timestamp | independently computed age |
| 216-symbol universe | direct runtime count | Sheet/BQ count |
| BigQuery fresh | direct query / table Modified time | Sheet/GitHub snapshot comparison |
| Pre-open prediction existed | immutable issue ID/hash/timestamp | later outcome comparison |
| CE/PE daily winner | exact contract market history | liquidity/executability qualification |
| Fix resolved | active after-state | independent peer evidence + regression protection |

### Evidence priority

Prefer:

1. immutable commit SHA / workflow run/job ID;
2. exact query output;
3. timestamped machine-readable JSON/CSV;
4. SHA-256 artifact;
5. direct runtime process/port proof;
6. screenshot/PDF as supplemental evidence only.

Narrative summaries are never stronger than their underlying evidence.

---

## 6. Observation vs Claim vs Resolution

Every agent must distinguish:

- **OBSERVATION** — directly measured fact.
- **CLAIM** — interpretation of one or more observations.
- **INFERENCE** — conclusion that may still require proof.
- **IMPLEMENTATION** — code/config was changed.
- **VERIFIED_AFTER_STATE** — intended active runtime behavior was independently rechecked.

Examples:

- "PR contains a timeout change" = IMPLEMENTATION.
- "Production no longer stops early" = runtime CLAIM requiring active-session proof.
- "Sheet says HEALTHY" = observation of a cell, not proof of health.
- "Writer age 0s" = not valid unless independently recomputed from current time minus source timestamp.

---

## 7. Permanent Cross-Agent Coordination Contract

AGY CLI and ChatGPT are independent peer-verification lanes.

### AGY CLI primary responsibility

Direct local Windows / Power BI / runtime verification, including:

- Windows process state;
- PID and process creation time;
- PBIDesktop/msmdsrv state;
- listener ports;
- PowerShell/Python/local daemon processes;
- Windows Task Scheduler/local background automation;
- local file/runtime state;
- local source-age computation;
- local logs;
- local reproduction of defects identified remotely.

### ChatGPT primary responsibility

Independent verification through accessible durable sources, including:

- GitHub main/branches/PRs/commits/workflows;
- Google Sheet values and timestamps;
- BigQuery counts/freshness when directly queryable;
- uploaded artifacts/PDFs/screenshots;
- public source verification where needed;
- reconciliation of AGY claims against independent evidence.

### Neither lane self-certifies

A critical issue becomes resolved only after independent agreement.

---

## 8. Canonical Status Vocabulary

Use only these states for material issues:

- `OBSERVED`
- `OPEN_AUTO_FIXABLE`
- `IMPLEMENTED_NOT_DEPLOYED`
- `VERIFIED_LOCAL`
- `VERIFIED_REMOTE`
- `DISPUTED`
- `WAITING_FOR_PEER`
- `WAITING_FOR_USER`
- `RESOLVED_TWO_PARTY`

### Resolution rule

A critical issue is `RESOLVED_TWO_PARTY` only when:

1. the fix is active in the intended runtime;
2. the implementing/claiming lane posts reproducible evidence;
3. the peer checks a materially independent evidence path;
4. timestamps/SHA/runtime identity are compatible;
5. contradictions are resolved;
6. regression protection exists where practical.

Branch/PR-only code is never `RESOLVED_TWO_PARTY`.

---

## 9. Disagreement Protocol

If two agents disagree:

1. set status to `DISPUTED`;
2. freeze the disputed production claim;
3. compare exact timestamps;
4. compare timezone interpretation;
5. compare Git SHA/branch;
6. compare process/PID/runtime identity;
7. compare source timestamp and dataset version;
8. compare market session state;
9. run targeted reproducible checks;
10. preserve both observations;
11. continue until a common explanation is proven.

Never average contradictory evidence into a green health score.

The goal is not to prove an agent right. The goal is to make the system correct.

---

## 10. CROSS_AGENT_PACKET Contract

Every material local or remote claim should be durable and peer-verifiable.

Required fields:

```text
CLAIM_ID
CLAIMING_AGENT
CLAIM_TIME_IST
HOST_OR_RUNTIME
REPO
BRANCH
BASE_SHA
HEAD_SHA
ARTIFACT_SHA256
CLAIM
OBSERVATION
EXACT_COMMANDS
PRIMARY_EVIDENCE
SOURCE_TIMESTAMPS
PID_PROCESS_PORTS
BEFORE_STATE
ACTION_TAKEN
AFTER_STATE
SAFETY_STATE
SECRETS_REDACTED
PEER_CHECK_REQUEST
KNOWN_LIMITATIONS
STATUS
```

Preferred local helper:

`tools/agy_cross_agent_packet.ps1`

Canonical posting location:

GitHub Issue #3.

---

## 11. Multi-Validation Requirement

Critical claims require at least two independent evidence paths.

Examples:

### Power BI healthy

Require:

- PBIDesktop/msmdsrv process evidence;
- actual listener/process ownership where applicable;
- source freshness/rendered data agreement.

### Broker healthy

Require:

- authenticated broker session;
- fresh market-data observation.

Authentication alone is not market-data health.

### Universe complete

Require:

- local/runtime count;
- independent Sheet or BigQuery count.

### Prediction success

Require:

- immutable issued prediction created before the target event;
- independently observed later outcome.

A post-open recalculation cannot be scored as a pre-open forecast.

---

## 12. Market Session and Freshness Truth

Freshness must be calculated independently:

```text
source_age = NOW_IST - SOURCE_TIMESTAMP
```

Never trust only a stored freshness cell such as `0s`.

Default interpretation unless a component has a stricter SLA:

- <= 90 seconds: FRESH/LIVE during market session
- 91–180 seconds: DEGRADED
- > 180 seconds: STALE
- market closed: LAST_PRINT/CLOSED, not LIVE

A writer timestamp is not automatically an exchange-tick timestamp.

At market close, dashboards must distinguish:

- broker auth state;
- background engine state;
- last market print;
- next-day model state.

Do not label closed-market data "real-time live market."

---

## 13. Single-Writer and Data Publication Rule

The system must converge toward one authoritative production writer for destructive/live publication.

Multiple execution environments may research, verify, or test, but they must not independently overwrite the same production snapshot without coordination.

### Critical rule

A partial universe must never replace a last-known-good qualified full snapshot as healthy production data.

Before destructive publication:

1. validate required universe coverage;
2. validate required fields;
3. validate freshness;
4. validate source/session context;
5. validate writer lease/authority;
6. publish atomically where practical;
7. record before/after evidence.

If coverage is partial:

- mark DEGRADED;
- preserve last good full snapshot;
- retry with bounded policy;
- record the failure;
- never false-green the write.

---

## 14. Upstream Dependency Health

Important upstreams include:

- Angel One SmartAPI;
- NSE/exchange-derived market data;
- news/filing sources;
- Google Sheets;
- BigQuery;
- GitHub/GitHub Actions;
- local Windows/Power BI where used.

No agent may guarantee that an external provider will always remain available.

Instead, production-grade handling requires:

1. independent health/freshness checks;
2. bounded retry/backoff;
3. re-authentication where safe;
4. circuit/degraded state;
5. preserve last-good evidence;
6. no destructive partial overwrite;
7. incident ledger;
8. recovery verification;
9. fallback source only when semantics are equivalent and provenance is explicit.

Upstream failure must become visible degradation, not false success.

---

## 15. Auto-Detection and Auto-Remediation

Continuously detect at least:

- broker disconnect;
- quote/API timeout;
- partial 216-symbol coverage;
- stale source;
- dead writer/daemon;
- duplicate writers;
- workflow overlap;
- scheduled-run delay/failure;
- BigQuery write/replay failure;
- timestamp/timezone anomaly;
- Power BI stale process/model;
- prediction overwrite;
- immutable-baseline failure;
- model degradation;
- penny-option false leader;
- liquidity failure;
- news-source outage;
- post-event/lookahead contamination.

Classify each issue:

- `AUTO_RECOVERABLE`
- `AUTO_FIXABLE_CODE`
- `NEEDS_PEER_VERIFICATION`
- `WAITING_FOR_USER`

### Safe automatic recovery

When permitted and bounded:

```text
detect
→ retry/re-authenticate/restart bounded component
→ re-check
→ if recovered, record proof
→ request peer validation
→ if not recovered, remain DEGRADED/FAIL
```

Never change red to green merely because a retry command ran.

---

## 16. Prediction Targets — Keep Them Separate

### Target A — Underlying opening gap

Predict before the target open:

- GAP-UP / GAP-DOWN / neutral direction;
- expected opening-gap magnitude;
- confidence/probability.

### Target B — Exact CE extreme-premium ranking

Rank exact call contracts likely to become the day's strongest liquid/executable CE premium movers.

### Target C — Exact PE extreme-premium ranking

Rank exact put contracts likely to become the day's strongest liquid/executable PE premium movers.

Do not use Target A success as proof that Target B/C succeeded.

---

## 17. Raw Winner vs Executable Winner

Maintain two outcome concepts:

### RAW MARKET WINNER

Highest observed percentage premium move.

### LIQUID / EXECUTABLE WINNER

Winner that passes defined liquidity/execution checks such as:

- valid bid/ask;
- acceptable spread;
- meaningful OI;
- meaningful volume;
- non-zero executable entry proxy;
- realistic slippage assumption;
- sufficient market depth where available.

Penny-premium explosions must not dominate the actionable ranking solely because of percentage arithmetic.

---

## 18. Immutable Forecast Rule

A scored forecast must be frozen before the event it predicts.

Required identity should include:

- issue ID;
- model/version ID;
- feature version;
- issue timestamp with timezone;
- target session/date;
- exact underlying/contract;
- prediction/rank/probability;
- input-data cutoff timestamp;
- artifact hash.

Post-open or post-event recalculations must be stored separately as dynamic intraday predictions.

Never overwrite the frozen prediction being scored.

---

## 19. Outcome Ledger

For completed sessions, maintain append-only exact-contract evidence where available:

- date;
- symbol;
- expiry;
- strike;
- CE/PE;
- prior close;
- opening bid/ask/LTP;
- executable-entry proxy;
- intraday high and time-to-high;
- closing bid/LTP;
- maximum premium gain;
- executable gain;
- MAE;
- underlying opening gap/session move;
- OI/volume/OI velocity;
- spread/liquidity;
- PCR/OBI;
- IV/Delta/Gamma/Dollar-Gamma/Theta/Vega;
- days to expiry;
- moneyness;
- market/index/sector regime;
- breadth;
- catalyst/news timestamps;
- whether each catalyst was known before forecast issue time.

If data is unavailable, mark it unavailable. Never invent it.

---

## 20. Continuous Learning Governance

Continuous learning means continuously testing improvements, **not** continuously changing production weights without controls.

Required loop:

```text
issue immutable prediction
→ observe later market outcome
→ append outcome
→ diagnose hits/misses
→ propose candidate improvement
→ train on earlier chronological data
→ validate on later chronological data
→ test on untouched forward data
→ independent peer review
→ promote only if improved
→ otherwise reject/rollback
```

No lookahead.

No post-event news backfill.

No tuning on the untouched test after seeing its result.

No same-batch self-calibration metric may be called forward accuracy.

---

## 21. Model Promotion and Rollback

Every model/strategy version should record:

- version ID;
- code SHA;
- feature schema/version;
- training window;
- validation window;
- untouched forward window;
- sample size;
- CE metrics;
- PE metrics;
- gap metrics;
- costs/slippage assumptions;
- approval status;
- prior approved version;
- rollback version.

Promote only when predefined forward criteria are improved without violating safety/data-integrity gates.

If newly promoted behavior degrades:

1. detect;
2. mark DEGRADED;
3. revert/rollback to last approved model when technically safe;
4. preserve evidence;
5. investigate;
6. peer-verify the after-state.

---

## 22. Required Evaluation Metrics

Keep CE, PE, opening-gap, and intraday objectives separate.

Track as appropriate:

- Top-1 hit rate;
- Top-3 hit rate;
- Top-5 recall;
- rank of actual winner;
- NDCG/rank quality;
- capture ratio versus best liquid/executable option;
- opening-gap direction accuracy;
- gap MAE;
- gap RMSE;
- predicted vs actual premium multiple;
- Brier score/calibration;
- executable PAPER P&L using bid/ask and slippage;
- sample size;
- confidence intervals/uncertainty.

### Accuracy naming

Self-calibration hit rate, current-cycle matching, or in-sample fit must never be labeled genuine forward accuracy.

---

## 23. News and Catalyst Governance

For prediction use:

- preserve source URL/identity;
- preserve publication/dissemination timestamp;
- preserve first-observed timestamp where possible;
- preserve symbol/entity mapping;
- distinguish regulatory filing, wire, media, thematic discovery, and social source;
- ensure the information was known before prediction cutoff;
- reject or label post-event catalysts.

Do not infer causation from correlation without evidence.

News coverage should be measured by independent domains/sources and freshness, not by raw headline count alone.

---

## 24. Timezone Standard

Use timezone-aware timestamps end-to-end.

Preferred local market timezone:

`Asia/Kolkata`

Never create IST by manually adding 5:30 to UTC and then serializing it with a UTC offset.

For cross-system records preserve:

- timezone-aware timestamp;
- UTC form where needed;
- IST display form;
- source timestamp;
- observed-at timestamp.

Timezone correctness is required for no-lookahead validation.

---

## 25. BigQuery Reliability

BigQuery production writes should not silently fail and continue as green.

Required design:

- explicit success/failure status;
- bounded retry for transient errors;
- durable replay/dead-letter concept for append events;
- coverage/freshness gate before snapshot replacement;
- no healthy full snapshot replaced by partial data;
- post-write row-count/freshness verification;
- incident evidence on failure.

Use table `Modified` metadata as a freshness aid when application timestamps are known to be defective, but fix the source timestamp defect rather than relying on the workaround permanently.

---

## 26. GitHub / CI Governance

Before code changes:

1. inspect current main SHA;
2. inspect open PR ownership;
3. avoid conflicting modifications;
4. use a dedicated non-main branch;
5. make the smallest correct change;
6. add focused regression tests;
7. run required checks;
8. record exact head SHA;
9. request independent peer verification;
10. merge only under project governance.

A green CI check is code/test evidence, not runtime proof.

### Workflow concurrency

Avoid overlapping production writers.

Use GitHub concurrency controls where appropriate, but remember that GitHub concurrency alone does not protect against an independent Colab/local writer. Cross-runtime writer authority still requires an application-level lease/guard.

---

## 27. Power BI Governance

Power BI visual health must be verified separately from upstream data health.

Do not infer Power BI health from HTML monitor text alone.

For material claims prefer:

- PBIDesktop PID;
- msmdsrv PID;
- process creation time;
- listener/owning process where relevant;
- semantic-model/report load state;
- screenshot/PDF/export;
- independent source timestamps;
- agreement between displayed values and source data.

The dashboard must clearly distinguish:

- REAL MARKET observations;
- MODEL FORECASTS;
- FORWARD RESULTS.

Do not mix them in one KPI.

---

## 28. Security and Secrets

Never expose or commit:

- Angel API key;
- client code;
- PIN;
- TOTP seed;
- JWT;
- service-account private key;
- passwords;
- GitHub tokens;
- other credentials.

If a credential appears in source/history, treat rotation as a separate user/account action even after the code is cleaned.

Do not paste secret values into:

- GitHub Issue #3;
- PR comments;
- logs;
- CROSS_AGENT_PACKET;
- screenshots;
- reports.

---

## 29. Trading Safety

This governance contract authorizes analysis, monitoring, data-quality work, model research, PAPER simulation, and engineering remediation.

It does **not** authorize live broker order placement.

Required safety:

```text
PAPER / ANALYZER = ON
LIVE ORDER AUTHORITY = OFF
REAL BROKER ORDERS = 0
```

Do not enable, place, modify, or cancel real orders under this protocol.

---

## 30. Human/User Dependency Rule

Agents should exhaust safe authorized technical alternatives before asking the user to relay messages or perform manual work.

Normal AGY ↔ ChatGPT communication goes through Issue #3.

Ask the user only for genuine boundaries such as:

- MFA;
- credential rotation;
- account consent;
- permissions unavailable to agents;
- physical/local action that cannot safely be automated;
- explicit business/risk decision.

Use `WAITING_FOR_USER` only when the dependency is genuine.

---

## 31. New Agent / New Tool / New Platform Onboarding

Any new agent, model, IDE plugin, CLI, connector, notebook, runtime, or automation joining the project must:

1. read this `AGENTS.md`;
2. identify itself in Issue #3 when doing material work;
3. read current main and relevant open PRs;
4. read unresolved/disputed items;
5. declare what it can directly observe and what it cannot;
6. avoid claiming authority outside those boundaries;
7. use existing evidence contracts;
8. request independent verification for critical claims;
9. preserve PAPER/analyzer safety;
10. leave a durable handoff before stopping.

A new agent must not create a parallel undocumented governance system.

---

## 32. Durable End-of-Run Handoff

A material run must leave enough evidence for another agent to continue without chat memory.

Record:

```text
RUN_ID
AGENT
TIME_IST
MAIN_SHA
WORKING_BRANCH / PR
TASK
PREVIOUS_STATE
OBSERVATIONS
ACTIONS
TESTS
ARTIFACTS / HASHES
CURRENT_STATUS
DISPUTED_ITEMS
OPEN_ITEMS
PEER_VERIFICATION_REQUIRED
USER_ACTION_REQUIRED
NEXT_OWNER
NEXT_EXACT_ACTION
```

Post material cross-agent handoffs to Issue #3.

---

## 33. Permanent Resolution Register

Issue #3 should maintain or reference the living register:

```text
ISSUE_ID
AREA
STATUS
ROOT_CAUSE
PERMANENT_FIX
CLAIMING_AGENT
PEER_VERIFICATION
CODE_SHA
TEST_PROOF
RUNTIME_PROOF
DATA_PROOF
REGRESSION_PROTECTION
WHY_PENDING
USER_DEPENDENCY
NEXT_OWNER
LAST_UPDATED_IST
```

Never silently drop unresolved items.

A recurrence reopens the same issue/history rather than creating a fake clean slate.

---

## 34. Health Score Governance

Composite health scores such as 98.7% or 100% are allowed only if:

- formula is documented;
- every component is measurable;
- source timestamps are current;
- critical failures cannot be hidden by averaging;
- market-closed state is handled explicitly.

A single critical fail-closed gate overrides a cosmetic high aggregate score.

Do not use decorative labels such as "Quantum DNA", "ECG", "zero blockage", or similar metaphors as engineering proof unless each is mapped to a documented measurable metric.

---

## 35. Current Known High-Priority Engineering Classes

Every agent should continue checking these until Issue #3 shows independently verified closure:

### P0 — integrity/runtime

- cross-runtime single-writer authority;
- prevent partial-universe destructive overwrite;
- independent source freshness;
- false-green heartbeat prevention;
- Angel retry/re-authentication;
- BigQuery retry/replay;
- timezone-aware timestamp correctness;
- degraded-state truth.

### P1 — operational governance

- credential cleanup and user rotation where required;
- workflow concurrency;
- watchdog/self-heal;
- deterministic market-session lifecycle;
- immutable daily prediction IDs;
- Power BI process/source truth.

### P2 — prediction research

- separate opening-gap vs exact CE/PE winner objectives;
- exact-contract append-only outcome ledger;
- raw vs executable winner labels;
- CE/PE-specific models where forward evidence supports them;
- regime-aware models only when forward-proven;
- automatic model rollback on forward degradation.

Live status belongs in Issue #3 and current evidence, not in this static section.

---

## 36. Conflict Resolution Between Instructions

Priority:

1. safety/security constraints;
2. this `AGENTS.md`;
3. current user instruction that does not violate safety/security;
4. current-main project-specific implementation docs;
5. older reports/docs;
6. historical chat summaries.

If two current project documents conflict, do not choose silently. Mark the conflict on Issue #3 and resolve it with evidence.

---

## 37. Definition of Production-Grade for This Project

A production-grade claim requires all applicable categories below to be evidenced:

- current code provenance;
- tests/regression gates;
- runtime identity;
- broker/auth state;
- market-data freshness;
- full required universe;
- no destructive partial writes;
- single writer;
- explicit degraded/failed states;
- bounded recovery;
- timestamp correctness;
- BigQuery/Sheet consistency;
- Power BI truth where applicable;
- immutable forecast evidence;
- honest forward metrics;
- secrets protected;
- live orders disabled;
- independent peer verification.

If any critical category is unknown or contradictory, status is not fully production-grade.

---

## 38. Core Principle

> **Do not optimize for green dashboards. Optimize for truthful system state.**
>
> **Do not optimize for an agent being right. Optimize for independently verified system correctness.**
>
> **Do not optimize for historical accuracy claims. Optimize for reproducible forward evidence and safe continuous improvement.**

This file is the permanent starting point. Read it first. Use Issue #3 for living state. Preserve evidence. Resolve disagreements through independent verification. Leave the project more truthful, safer, and more measurable than you found it.

Agents: read FRONT.md first. Autonomous for paper-only work, no approval needed for paper tasks. Paper-only lock is permanent: no live orders, no force-push to main, no secrets in files.

## Mandatory forensic verification before every agent change
All agents MUST read `docs/AGENT_FORENSIC_GATES.md` and execute the applicable layered tests, source/encoding checks, non-destructive Git preflight and evidence recording before claiming PASS. Never confuse external verification failure with CLI parser failure. No unverified production activation or live trading.

**Forensic gate baseline:** commit [5f099c3](https://github.com/psw2025-cmd/angel-fno-scanner/commit/5f099c3); six mandatory release gates in [docs/AGENT_FORENSIC_GATES.md](docs/AGENT_FORENSIC_GATES.md).

## Permanent encoding regression gates
All agents must read docs/PERMANENT_MEMORY/PM-001-emoji-cp1252.md and docs/AGENT_FORENSIC_GATES.md before source edits. Run tracked source gate, CP1252 and CLI tests, protect worktrees, and preserve AGY routing/self_resolve. CI proof outranks self-reported PASS.
---

## Mandatory multi-agent reliability addendum (2026-10-10)
# Agent Instructions â€” Angel F&O Scanner

All automated agents (AGY, Codex, Claude, or others) must follow the same operating contract.

- Before edits, inspect current Git HEAD/status, existing tasks, prior incident evidence, CI, and dependencies. Never rely on historical PASS alone.
- Maintain a durable issue ledger with stable IDs, severity, root cause, affected paths, reproduction, patch, test proof, and follow-up verification.
- Recheck old fixes for regression when upstream/downstream code changes; add regression tests for new failure classes.
- Edit only approved, explicitly allowlisted paths in an isolated Git worktree. Never delete user files to make a repository clean. Unexpected path prompts are denied.
- Use AGY first, Codex second, Claude third only if each passes its own readiness check; record fallback and cooldown decisions. Do not reuse keys across providers.
- Require syntax, unit, integration, boundary and relevant production-equivalent tests plus independent review before marking complete.
- Store timestamp, commit, changed files, test outputs, and provenance; distinguish simulation, local, GitHub, Sheets, BigQuery, and cloud-runtime verification.
- Keep PAPER/ANALYZE separate from LIVE trading; do not enable real orders or bypass risk gates.
- No automatic merge, push, cloud deployment, secret changes, destructive cleanup or live trading without task-specific authorization.
- Report unresolved conditions as NOT VERIFIED, continue unrelated safe work, and update status artifacts from measured evidence.

Local supervisor contract: C:\AngelFNO_Workstation\angel-agent-supervisor\AGENT_OPERATING_CONTRACT.md
