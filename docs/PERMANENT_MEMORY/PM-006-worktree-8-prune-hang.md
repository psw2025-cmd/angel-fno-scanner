# PM-006 — Git Worktree Proliferation & Prune Hang Under Process Locks

## 1. Problem Statement & Root Cause
Multiple agents spawned isolated worktrees across `C:\AngelFNO_Workstation\` and external Codex paths. When `git worktree prune` was invoked while VS Code, PyCharm, or Python background processes had open handles to those directories, git operations hung or failed on Windows file locks.

## 2. Impact
Terminal deadlock, unable to switch branches cleanly, and stale worktree directories persisting in `.git/worktrees/`.

## 3. Resolution & Commit
- Documented safe worktree lifecycle protocol in `docs/AGENT_EXPERT_ROUTING.md`.
- Required process lock inspection (checking for IDEs, daemons, terminal processes) before pruning.
- Used dedicated isolated repair branches and pruned cleanly once processes detached.

## 4. Prevention & Forensic Gates
- Verified by ledger check P-19 (`Git worktree safety`).
- Strict non-destructive worktree rule: never force prune active worktrees.
