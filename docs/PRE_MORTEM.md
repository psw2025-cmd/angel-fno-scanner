# Pre-mortem — Angel F&O unattended operations

1. **Encoding fails at 03:00.** Emit a timestamped JSONL event with task ID, attempt, agent, worktree, SHA, status, exception class and traceback fingerprint. A RETRY_PENDING without that evidence is itself a reliability defect.

2. **AGY review times out.** Likely causes: unavailable account/network, CLI waiting for interaction, or process-tree deadlock. Probe account readiness with a bounded noninteractive call; capture child-process command lines and output without credentials; compare a minimal review in a temporary repository. Do not infer an Angel One rate limit from an AGY timeout.

3. **Merge half-succeeds.** Record target main SHA and PR ID before merge; query GitHub for the resulting merge commit and CI status. If a bad merge is verified, prepare a revert PR with `git revert <merge-sha>` in a new branch rather than resetting shared main.

4. **Orphan survives.** Fingerprint process PID, parent PID, command line, executable, creation time, worktree path, run ID, heartbeat and owned ports. Kill only processes whose ownership and expired heartbeat are established; never kill all Python/PowerShell processes.

5. **Cycle record disappears.** Use append-only JSONL with unique cycle IDs, flush and fsync on commit, and reconstruct from workflow run IDs and immutable artifacts. Deduplicate on `(cycle_id, run_id)`.

6. **File lock belongs to another application.** Detect lock failure, retry boundedly, then quarantine the worktree and report. Never terminate unknown processes or forcibly rename live Git metadata.

7. **Safety conflicts with speed.** Safety wins: deny unallowlisted paths, keep PAPER separate from LIVE, preserve forensic evidence, and require CI plus independent review before merge.
