# FRONT DOOR - MANDATORY FOR ALL AGENTS - V10

Owner is non-technical. Goal: maximum % gain on paper, 2x to unlimited upside.
This file is the single source of truth for all agents (Perplexity, ChatGPT, Gemini, Claude, Cursor, Fig, n8n, future agents).

## 0. Golden rule: no questions for paper work, with a permanent paper-only lock
1. Inside the paper-only boundary, do not ask the owner for approval. Do the work, validate it with output, commit to a branch, and open a PR.
2. Paper-only lock (permanent, never remove from any document):
   - No real order placement, ever.
   - No `.env` leak and no secrets in files.
   - Angel One streaming uses market-data read-only keys only (no key that can place orders), stored only in n8n credentials, never in a file.
   - Never force-push to main.
   - Merge to main only when every check on the PR's latest commit is green.
3. Inside the lock, agents may read, build, test, deploy paper workflows, stream and update docs.
4. Docs that must carry the pointer to this file: `README.md`, `AGENTS.md` (and `CLAUDE.md` / `.cursorrules` if they exist), `PERMISSIONS.md`.
5. No document may be edited to remove the paper-only lock.

## 1. Goal
- Floor: 2x required. If the probability of 2x is below 60%, no trade.
- No fixed cap on upside.
- Exit logic: at 2x book 30% and move stop to cost; at 4x book 30% more and trail to the 2x level; after 4x, every further 50% rise trails the stop up by 25%.
- This exit logic is a hypothesis. Backtest it on paper data before treating it as proven.

## 2. Prediction inputs
Technical: price, volume, OI, PCR, VWAP, Supertrend, order flow.
News: news API, X/Twitter, Telegram, economic calendar, FII/DII, US cues.
AI: ML, sentiment.
Add an input only if it improves out-of-sample results, with proof.

## 3. Architecture
Repo `psw2025-cmd/angel-fno-scanner`: the core engine is the reference. Read it, build on top in `n8n_automation/`, `fig_automation/`, `enhancements/`. Core bug fixes only by PR with failing-then-passing test proof.
Work in 10 micro-steps: step, validate existing flow still works, commit, next step.

## 4. n8n workflows (importable JSON)
- WF-1: 50 FNO LTP stream plus news stream in parallel
- WF-2: 2x-to-unlimited engine
- WF-3: local-cloud sync (Sheets, Telegram/WhatsApp, Issues/PRs)
- WF-4: self-learning (fail -> lessons.json -> improve)
- WF-5: master controller (hourly health check, auto-restart, 9:15-3:30 IST)

## 5. Duty
Check streams often and restart them if down. Daily: look for a new source or indicator, add it to `enhancements/`, log results in `lessons.json`.

## 6. Self-check twice with output
Build -> Check 1 (file exists, JSON valid) -> Check 2 (dry run, logic works) -> paste output as proof -> done. No output means not done. Show py_compile, JSON validity and dry-run output.

## 7. Delivery
Two clicks for a non-coder: import and activate in n8n. Paper-only. 5 JSONs, README with a 2-click guide, Sheets log, Telegram alert.
