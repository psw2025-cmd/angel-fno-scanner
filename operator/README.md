# Operator board — open this first

You are not expected to read code. Open **[TODAY.md](TODAY.md)** every morning.

| Color | Meaning |
|---|---|
| GREEN | Independently proven on two paths |
| YELLOW | Code exists, live proof missing or stale |
| RED | Broken, disputed, or unsafe to trade from |
| GREY | File not in repo yet; lives only on laptop/Drive |

## Rule

- Live Google Sheet, Power BI, and Colab stay live in Google / Windows.
- This folder is the **dated scoreboard + links**, not a second live market.
- A git Excel/CSV from yesterday is a snapshot. Never treat it as this morning's live tape.
- PAPER / analyzer only. No real orders.

## What you look at

1. [TODAY.md](TODAY.md) — GREEN / YELLOW / RED
2. [LINKS.md](LINKS.md) — Sheet, Colab, Power BI, Excel snapshot
3. [MISSING_AND_UPSTREAM.md](MISSING_AND_UPSTREAM.md) — what agents must fix next
4. [STATUS.json](STATUS.json) — same facts for every agent

## Parallel lanes (do not block each other)

| Lane | Owns |
|---|---|
| You | Visual judgement on Sheet + Power BI + this board |
| AGY laptop | Windows / Power BI PID / local harness / dated Excel+pbix copy |
| GitHub `market_bot` | Only production writer |
| Remote agents (Grok / ChatGPT) | GitHub + Sheet + BigQuery cross-check |
| Gemini Cloud Shell | Do **not** generate a new `run_production_sequence.py` from the old 216-symbol doc |
