# Phase 1 — Independent Cloud Forensic Baseline and Zero-Laptop Reproducibility

**Author:** ChatGPT, independent auditor architect. **Scope:** planning and audit contracts only; no implementation, secret export, runtime edits, or activation. **Independent source rule:** this document was prepared from the ChatGPT local/cloud audit and repository observations, **without consulting AGY's architecture plan**. **Date:** 2026-10-09.

**Evidence anchor:** The six-minute-forty-one-second local audit found Windows `DESKTOP-DM6NHPI`, WSL2 Ubuntu 24.04, Node v24.21.0, n8n `5678/healthz` HTTP 200, sandbox API and runner Docker containers healthy, and read-only listener `5680/health` HTTP 200. The service sets `N8N_USER_FOLDER=/home/pritam/n8n-data`; its SQLite database holds **17 workflows (10 active, 7 inactive)**. The other `~/.n8n/database.sqlite` is a separate non-authoritative instance. Historical GitHub scanner run [37919835552](https://github.com/psw2025-cmd/angel-fno-scanner/actions/runs/37919835552) succeeded after run 37917651040 failed. **Run success is not proof of cloud n8n readiness.** The user-provided `main=3c4db62` is a historical audit anchor; at document creation, GitHub `main` resolved to `786b5eff2b95dcc808b58f9cc0a32a844e84240e`. Local hash `1d09336`, when observed, is likewise time-indexed. Do not overwrite or silently equate these versions.

## Mission and independent design principles

A fresh cloud agent with only `git clone` must be able to **discover** missing dependencies, reconstruct a safe read-only or PAPER environment from declared infrastructure and attested artifacts, and prove that it has the same inputs, workflow definitions, release policy and sink contracts as the authoritative system. It must never infer correctness from green status indicators alone. The objective is long-term portability and verifiable recoverability, **not** a literal 100-year uptime guarantee. GitHub is the code/configuration authority; cloud deployment attestation is runtime authority; Sheets and BigQuery are independently validated data sinks. No broker live order until a separate, explicitly approved Phase 4 gate.

## A. Exactly 50 things a new agent will NOT see after a plain git clone

The following are **blind spots to test**, not claims that every item is absent from every current repo file. Items describing live DB/service state are directly evidenced by the local audit; others require targeted verification. A clone includes only tracked committed content, not arbitrary workstation, service or cloud state.

| # | Category | Blind spot | Required cloud solution |
|---:|---|---|---|
| 1 | Identity and authority | **Git worktree topology** — A clone does not contain workstation worktrees or their uncommitted changes | Enumerate tracked branches, remote refs and provenance manifest |
| 2 | Identity and authority | **Local HEAD divergence** — Historical local SHA 1d09336 is not an immutable production reference | Capture local, origin/main and deployed SHA at same timestamp |
| 3 | Identity and authority | **Historical main identity** — 3c4db62 was a historical reference, not necessarily current main | Resolve refs via authenticated GitHub API on every run |
| 4 | Identity and authority | **Untracked operational files** — Untracked files and ignored configs are absent after clone | Generate sanitized inventory and required-file manifest |
| 5 | Identity and authority | **Uncommitted changes** — Dirty worktree patches are not transmitted by git clone | Collect patch hashes and review before migration |
| 6 | Identity and authority | **Git ignored paths** — gitignored local secrets and tools are invisible | Publish required-path schema without secret values |
| 7 | Identity and authority | **Local symlinks/junctions** — NTFS junction targets are not portable to cloud | Resolve dependencies and replace with explicit artifacts |
| 8 | Identity and authority | **Git LFS/submodules** — Optional fetch and auth may hide data or pin wrong revisions | Pin hashes and verify recursive materialization |
| 9 | Identity and authority | **GitHub Actions run artifacts** — Ephemeral artifacts expire and are not cloned | Export signed indexes to immutable cloud evidence store |
| 10 | Identity and authority | **Repository/environment variables** — GitHub Actions secrets and variables are not in a clone | Document names, ownership, scope and validation probes |
| 11 | n8n and orchestration | **Authoritative n8n user folder** — Service env N8N_USER_FOLDER differs from default home folder | Enforce canonical instance identity in exporter |
| 12 | n8n and orchestration | **n8n SQLite content** — Workflow definitions and credentials metadata live outside git | Sanitized deterministic export and DB migration |
| 13 | n8n and orchestration | **SQLite WAL and SHM** — Live writes may be missing from naive file copy | Use online consistent backup and integrity check |
| 14 | n8n and orchestration | **Workflow active flags** — JSON presence does not establish activation state | Signed desired-state and observed-state parity |
| 15 | n8n and orchestration | **Workflow stable IDs** — IDs can change on import or conflict across instances | Use canonical logical IDs and mapping table |
| 16 | n8n and orchestration | **Workflow node credentials** — Encrypted credential bindings do not survive naive export | Map opaque credential refs to cloud IAM identities |
| 17 | n8n and orchestration | **n8n encryption key** — Key required to decrypt credentials is not cloned | KMS-backed secret escrow and recovery drill |
| 18 | n8n and orchestration | **Workflow execution history** — Last failures and execution outcomes reside in DB | Export redacted execution metadata to cloud observability |
| 19 | n8n and orchestration | **n8n binary data** — File-backed execution payloads may be outside SQLite | Move to encrypted object storage with lifecycle |
| 20 | n8n and orchestration | **Workflow timezone and cron** — Host timezone affects market schedule semantics | Explicit Asia/Kolkata and exchange calendar tests |
| 21 | n8n and orchestration | **n8n runtime version** — Node 24.21.0 and n8n version differ from clone defaults | Pin image digest and compatibility tests |
| 22 | n8n and orchestration | **Community/custom nodes** — Installed packages and native deps may not be in Git | SBOM and reproducible container build |
| 23 | n8n and orchestration | **Workflow environment variables** — Node expressions may refer to undocumented runtime env | Typed env contract and startup validation |
| 24 | n8n and orchestration | **Webhooks and callback URLs** — localhost callbacks cannot be reached by cloud | Authenticated ingress and replay-safe endpoint migration |
| 25 | n8n and orchestration | **Workflow trigger ownership** — Multiple active schedulers can double-publish | Leader election and single-writer lease |
| 26 | Local services and dependencies | **Windows/WSL boundary** — PowerShell, WSL paths and host mounts are machine-specific | Eliminate C: and /mnt/c paths from production |
| 27 | Local services and dependencies | **n8n systemd unit** — Service restart and N8N_USER_FOLDER not in clone | Commit sanitized IaC and boot contract |
| 28 | Local services and dependencies | **n8n 5678 listener** — HTTP 200 local does not imply cloud readiness | Private ingress with auth and end-to-end health |
| 29 | Local services and dependencies | **Sandbox API 8080** — Local Docker API and runner are not reproducible by clone | Isolated cloud runner and signed image |
| 30 | Local services and dependencies | **Sandbox authentication** — Header key exists outside tracked source | Secret Manager reference and authenticated smoke test |
| 31 | Local services and dependencies | **Read-only listener 5680** — Local Python service serves health and diagnostics | Replace with versioned cloud evidence API |
| 32 | Local services and dependencies | **Listener route contract** — Undocumented /health /runtime-evidence routes may drift | OpenAPI contract tests and permissions matrix |
| 33 | Local services and dependencies | **Docker compose state** — Running containers, volumes and networks are not cloned | IaC, image digests and ephemeral staging test |
| 34 | Local services and dependencies | **Local watchdog** — Task scheduler and 30-second watchdog not deployed by Git | Cloud monitoring with escalation and recovery rules |
| 35 | Local services and dependencies | **Desktop Commander startup** — Desktop-only recovery scripts are not cloud orchestration | Remove from production dependency graph |
| 36 | Local services and dependencies | **Power BI desktop engine** — Local msmdsrv process cannot run in serverless n8n | Cloud BI/Fabric integration or decouple |
| 37 | Local services and dependencies | **Excel COM add-in** — Windows Excel automation is not cloud portable | Replace with API/data pipeline or retire with evidence |
| 38 | Local services and dependencies | **OS-level environment** — Host locale, clock, permissions, proxy and firewall are implicit | Container policy and environment attestation |
| 39 | Cloud data and market integrity | **Google Sheet identity** — Spreadsheet ID is external to repo and requires IAM | Verify 1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs |
| 40 | Cloud data and market integrity | **Sheet tabs and formulas** — Dynamic formulas and revision history are not Git data | Version formula templates and verify actual cells |
| 41 | Cloud data and market integrity | **BigQuery table identity** — Dataset/table and permissions are external | Check fno-angel-prod-1790444589.fno_predictions.option_predictions_live |
| 42 | Cloud data and market integrity | **BQ schema and partitioning** — Schema drift and retention are not inferred from code | Schema contracts and INFORMATION_SCHEMA diff |
| 43 | Cloud data and market integrity | **219-symbol universe** — Exchange membership and row identity change over time | Signed cycle-specific universe and exact-set compare |
| 44 | Cloud data and market integrity | **200 strict CE/PE ranks** — Sheet may contain headers/metadata and stale formulas | Count ranked contracts only; fail on stale 216 |
| 45 | Cloud data and market integrity | **Cycle run_id provenance** — Sheets and BQ may refer to different publication cycles | Cross-sink run_id/git_sha/cycle_id equality |
| 46 | Cloud data and market integrity | **Exchange timestamp source** — Wall-clock fallback can forge freshness | Exchange-verified timestamp and lineage gate |
| 47 | Cloud data and market integrity | **Historical checksum** — 3f6153d1e221ae43 alone is truncated/unbound to artifact | Recompute full SHA-256 over canonical artifact |
| 48 | Cloud data and market integrity | **Partial writes across sinks** — Success in one sink is not atomic cross-sink success | Outbox, staged publication and commit marker |
| 49 | Cloud data and market integrity | **Synthetic and quarantined data** — Legacy test rows may contaminate analytics | Quarantine labels and read-path enforcement |
| 50 | Cloud data and market integrity | **Broker session state** — Local tokens and broker API quotas not portable | Scoped cloud broker adapter; PAPER-only |

**Beyond the minimum 50:** separately inventory the remaining operations/security gaps before deployment: secret rotation, provider quotas, cloud budgets, backup restore, broker LIVE risk, alert receipts, incident ledgers, CI supply-chain attestations, model dataset licensing and long-term retention. None may be waived simply because they are not in the 50-row minimum.

## B. Fifteen hidden, invisible failure patterns

| # | Pattern | Failure mechanism | Detection and permanent guard |
|---:|---|---|---|
| 1 | **Split-brain authority** | Git main, local worktree, n8n DB, Sheets and BQ can each tell a different truth | Bind every claim to timestamped SHA and cycle IDs |
| 2 | **Green health, broken semantics** | HTTP 200 can coexist with stale predictions and disabled agents | Semantic probes and exact-cycle readbacks |
| 3 | **False rank PASS** | A 216-based formula can report PASS while 219 symbols are expected | Formula hash and 219/200 fail-closed contracts |
| 4 | **Time-of-check/time-of-use drift** | Exchange data can age between validation and publication | Immutable cycle snapshot and bounded age gate |
| 5 | **Lexical timestamp trap** | Comparing timestamp strings may not preserve chronological order | Parse timezone-aware instants and validate provenance |
| 6 | **Split transaction** | Sheets updated while BQ or git snapshot fails | Durable outbox and commit marker; consumers require COMMITTED |
| 7 | **Dual scheduler race** | Local and cloud n8n can fire same schedule | Single-writer lease with fencing token |
| 8 | **Duplicate retry side effects** | At-least-once delivery can publish twice | Idempotency key per cycle and sink |
| 9 | **Hidden credentials coupling** | Workflow JSON references locally encrypted credential IDs | Identity mapping and scoped cloud secret references |
| 10 | **Silent inactive workflows** | Imported definitions look complete but triggers disabled | Desired-vs-observed activation attestation |
| 11 | **Self-healer privilege escalation** | Agent can modify policy, tests or production to create false PASS | Allowlisted repairs, independent review and immutable gates |
| 12 | **Evidence survivorship bias** | Only successful logs survive or are copied to Git | Append-only failure ledger and missing-evidence alerts |
| 13 | **Cloud-cost runaway** | Retry loops and log verbosity multiply costs | Quota, budgets, backpressure and circuit breakers |
| 14 | **Restore illusion** | Backup files exist but encryption key/schema/queue state cannot be restored | Monthly isolated full-stack recovery drill |
| 15 | **Centennial lock-in** | 100-year retention or provider dependence prevents safe migration | Portable formats, staged retention, annual exit rehearsal |

## C. Phase 1 cloud solution for a brand-new agent

### C1. Reproducible bootstrap contract
1. Clone **only** the approved GitHub repository; verify branch protection, commit SHA, signed release manifest, pinned dependencies and expected tool versions.
2. Read `AGENTS.md` and a future machine-readable `cloud/bootstrap-manifest.json`; **fail closed** if it is missing. Manifest must declare workflow count and IDs, expected active flags, required secrets by *name*, external Sheets/BQ identifiers, listener API contract, cloud deployment SHA, dataset version, image digests and expected tests.
3. Authenticate via GitHub OIDC to a narrowly scoped GCP Workload Identity pool; no long-lived GCP JSON keys, broker PIN/TOTP or plaintext secrets in clone/CI logs.
4. Pull signed, sanitized n8n workflow bundles and validate hashes; fetch credentials by references, never export decrypted values. Stage imports into an isolated **non-production** n8n with managed PostgreSQL.
5. Build cloud evidence API as an authenticated replacement for local port 5680; replace local sandbox 8080 with restricted isolated jobs; keep external BQ and Sheets integrations read-only during bootstrap.
6. Run deterministic tests, 219/219 symbol identity checks, CE_PE strict 200 ranking, exchange timestamp/freshness checks, cross-sink `run_id`/`cycle_id`/`git_sha` parity, memory guard, chaos tests, secret scans and dependency checks. Counts and checksums must be recomputed from actual artifacts, not inherited from a past report.
7. Produce `BOOTSTRAP_ATTESTATION.json` containing source commit, workflow manifest SHA, deployment SHA, test report SHA, cloud IAM principal, verification timestamp, all failures and signed readback evidence. Publish to immutable cloud evidence storage with an index linked from GitHub Actions.
8. Only after independent review, promote cloud schedules under a **single-writer lease**. Local schedulers must be disabled *after* successful cloud canary and rollback validation; no double-publishing.
9. Verify disaster recovery by restoring into an isolated environment from offsite encrypted backup and checking the n8n encryption-key recovery process, 17 workflow identities, database schema and sample execution results.
10. Keep `LIVE_TRADING_ENABLED=false` enforced by IAM and broker-side controls, not only a workflow toggle.

### C2. Required proposed GitOps artifacts (not asserted to exist)

```text
cloud/
  bootstrap-manifest.json           # signed manifest and schema
  infra/                            # reviewed IaC, IAM, network, PostgreSQL, storage
  policies/                         # read-only/PAPER safety, branch rules, budgets
n8n-workflows/
  manifest.json                     # 17 logical IDs, hashes, active flags, versions
  *.json                            # sanitized deterministic workflow exports
contracts/
  evidence-api.openapi.yaml         # replacement for local 5680
  sheets-option-schema.json         # sheet/formula and 219/200 contracts
  bigquery-schema.json              # source and reconciliation contracts
tests/
  test_n8n_workflow_parity.py
  test_cloud_bootstrap_fail_closed.py
  test_cross_sink_cycle_commit.py
  test_no_live_broker_order.py
docs/
  cloud-runbook.md
  cloud-disaster-recovery.md
  cloud-credential-map.md           # names/roles only; no secret values
```

### C3. Five independent release gates

| Gate | Machine-verifiable acceptance | Blocking outcome |
|---|---|---|
| P1-G1: Inventory | 17/17 stable workflow IDs, hash and desired-active parity; no missing local dependency left unclassified | No cloud deployment |
| P1-G2: Security | Zero plaintext secrets in commits/artifacts; WIF verified; distinct read-only, publisher and risk roles | No credential migration |
| P1-G3: Reproducibility | Fresh cloud agent can build staging from pinned Git SHA without Windows, WSL or localhost | No scheduler switch |
| P1-G4: Data integrity | Same committed cycle across Sheets and BQ; exact 219 symbols and strict 200 ranks; exchange-verified timestamps | No publication promotion |
| P1-G5: Recovery | Independent offsite restore drill with measurable RPO/RTO, rollback and alert delivery | No laptop retirement |

**Phase 1 definition of done:** sanitized workflow bundle reviewed in PR; signed manifest; all 50 gaps classified with owner and evidence; all 15 patterns covered by test or explicit unresolved risk; no live secret leak; reproducible staging bootstrap and backup-restore proof. **This is a proposed gate, not an assertion it currently passes.**

## D. Independent ownership and verification model

- **Local discovery agent:** read-only inventory of the authoritative n8n DB, Windows/WSL dependencies, execution history, local files and credentials *references*. Output sanitized manifest and evidence with timestamp/hash.
- **Cloud auditor (ChatGPT):** independent GitHub/Actions/Sheets/BQ readback; threat modeling; challenge claims; test design; verify the exact same artifact SHA and cycle IDs. Never accept an agent's self-reported PASS without evidence.
- **CI verifier:** deterministic schema/security/unit/integration tests on pinned commit, with attestations and fail-closed behavior.
- **Release owner:** approves cloud scheduler cutover, budget and recovery policy; broker LIVE remains disabled and requires separate approval.
- **Conflict handling:** if local and cloud results disagree, record both in an immutable discrepancy ledger with source, time, hash and confidence; do not choose the more favorable claim.

## E. Immediate safe sequence and proof package

1. **Discover** and timestamp local n8n source folder, 17 workflow identities, current execution outcomes, Docker image digests, service units, local routes, Git dirty state and cloud provider configuration. Redact sensitive fields.
2. **Compare** inventory with tracked repo files and GitHub `main` using a path-by-path missing-dependency report; preserve current uncommitted files and avoid destructive resets.
3. **Export** sanitized workflow definitions using a consistent SQLite online backup or n8n export API; do not copy a live SQLite DB without WAL handling; never commit raw DB or decrypted credentials.
4. **Create PR** containing the manifest, proposed contracts, CI and IaC; no automatic activation, privileged healer, or cloud writes in the inventory PR.
5. **Verify independently** with fresh cloud runner, external readbacks and restore drill; produce signed, machine-readable evidence and a human-readable red/yellow/green matrix.

**Security and cost guardrails:** Do not publish localhost API keys, service account JSON, broker secrets, user data, credential IDs tied to active accounts or raw execution payloads. Treat 100-year retention locks and vendor uptime promises as unsafe without governance and tested exit strategy. Price estimates require current provider quotes and explicit logging/egress/LLM/billing budgets.

## F. Independent auditor verdict

**Current proven state:** local n8n services healthy, 17 workflow definitions in authoritative local database, 10 active / 7 inactive at audit, scanner run 37919835552 success. **Not proven:** 17 workflows committed to Git with parity, successful cloud deployment, last execution outcome of each workflow, independent Sheets/BQ parity for latest cycle, secretless cloud boot, or disaster recovery. **Release verdict: PHASE 1 NOT COMPLETE; PAPER/ANALYZE ONLY; LIVE DISABLED.**

**Traceability:** This plan is intentionally independent of AGY's proposal. It can be compared side-by-side in a later review, but no claims in this file depend on AGY's document.
