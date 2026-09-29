# MANDATORY START RULE

Before using this file or performing any project action, read the repository-root **`AGENTS.md`** completely.

`AGENTS.md` is the canonical permanent project operating contract and single start source for all agents, platforms, CLIs, IDE assistants, automations, notebooks, and future tools. GitHub Issue #3 is the canonical living coordination/evidence bus.

If this file conflicts with `AGENTS.md`, stop and record the conflict on Issue #3 before proceeding.

---

# External AI Agent Standard Operating Procedure (SOP) & Interface Guide

This repository hosts a production-grade **Angel One F&O Stock & Index Option (CE/PE) Prediction and Market Intelligence System** covering 216 Indian National Stock Exchange (NSE) F&O contracts.

External AI agents, automated connectors, MCP servers, and LLM orchestrators can read predictions, query live Greeks and news sentiment, trigger on-demand prediction cycles, and execute end-to-end verifications using multiple GitHub-native interfaces.


## 0. Mandatory Cross-Agent Coordination Control

For local Windows AGY CLI / Power BI / runtime work, GitHub Issue #3 is the canonical coordination bus and `docs/CROSS_AGENT_COORDINATION_V1.md` is the governing protocol.

Every material local-runtime claim must be emitted as a `CROSS_AGENT_PACKET`, preferably with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\\tools\\agy_cross_agent_packet.ps1" -Claim "<claim>" -Observation "<measured observation>" -Status WAITING_FOR_PEER -PostToGitHub
```

A critical finding must **not** be marked resolved by the same agent that implemented or observed it. Required sequence:

1. local/claiming agent measures and posts evidence;
2. independent peer checks a different evidence source;
3. disagreements become `DISPUTED` and investigation continues;
4. only active after-state with compatible timestamps/SHA and independent agreement becomes `RESOLVED_TWO_PARTY`.

Do not use dashboard text, a stored `0s` writer age, self-calibration hit rate, or a green CI badge as sole proof of production health. Compute freshness independently, distinguish market-closed last prints from live data, and keep Target A opening-gap prediction separate from Target B exact CE/PE extreme-gainer prediction.

This coordination rule never authorizes live orders. PAPER/analyzer safety remains mandatory.

---
## ⚡ Quick-Start: Interface Selection Matrix

| Integration Method | Latency | Auth Required | Best For |
| :--- | :--- | :--- | :--- |
| **Pre-Rendered Snapshots (`data/`)** | Instant (<10ms) | None (Public) | Reading current predictions, top gap-ups, breakouts, and news |
| **GitHub IssueOps (`/predict`, `/gapup`)** | ~30s | GitHub Issue Access | Interactive agent chat or human-in-the-loop workflows |
| **GitHub Actions Dispatch (REST API)** | ~45s | GitHub Token (`repo` scope) | Programmatic workflows, external CI/CD, webhook integrations |
| **Agent CLI & Python SDK (`agent_cli.py`)** | Live | GCP / BigQuery Sandbox | Local terminal execution, Jupyter/Colab notebooks, direct SDK |

---

## 1. Pre-Rendered Data Snapshots (Zero-Latency Reading)

The repository automatically maintains pre-rendered, real-time data snapshots under the `data/` directory. External agents can fetch these directly via raw HTTP GET requests without any authentication:

| File Path | Description | Raw GitHub URL |
| :--- | :--- | :--- |
| `data/summary.md` | Human & LLM-optimized Markdown briefing of Top Gap-Ups, CE Breakouts, and PE Breakdowns | `https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/summary.md` |
| `data/top_gapup.json` | Top 20 ranked 9:15 AM pre-market gap-up predictions with target strike and conviction | `https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/top_gapup.json` |
| `data/breakouts.json` | Top 10 Call (CE) breakouts and Put (PE) breakdowns with win probabilities | `https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/breakouts.json` |
| `data/latest_predictions.json` | Full 216-symbol universe option predictions with Black-76 Greeks and news signals | `https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/latest_predictions.json` |
| `data/market_news.json` | Multi-source filtered news feed with Bayesian tone scores and categorized impacts | `https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/market_news.json` |
| `data/system_health.json` | Verification audit status across 17 Google Sheet tabs, BigQuery Sandbox, and calibration | `https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/system_health.json` |

### Python Example:
```python
import requests

# Fetch pre-market top gap-ups
gapup_data = requests.get(
    "https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/top_gapup.json"
).json()

print(f"Top 1 Gap-Up Pick: {gapup_data[0]['symbol']} ({gapup_data[0]['target_open_strike']})")
print(f"Expected Gap: +{gapup_data[0]['expected_gap_pct']:.2f}% | Conviction: {gapup_data[0]['pre_open_conviction_pct']:.1f}%")
```

---

## 2. GitHub IssueOps Interactive Interface

External agents that interact via GitHub Issues (or MCP GitHub tools) can issue slash commands in any issue comment:

### Supported Slash Commands:
| Command | Arguments | Description | Example |
| :--- | :--- | :--- | :--- |
| `/predict` | `<SYMBOL>` | Return full Black-76 Greeks, probabilities, and news impact for an F&O stock | `/predict POLICYBZR` |
| `/gapup` | `[LIMIT]` | Rank top predicted 9:15 AM pre-market gap-up winners by conviction | `/gapup 5` |
| `/breakouts` | `[LIMIT]` | Top CE breakouts and PE breakdowns ranked by win probability | `/breakouts 5` |
| `/news` | `<SYMBOL> [LIMIT]` | Query live news headlines, tone, and catalysts for a symbol | `/news FORTIS` |
| `/verify` | None | Full forensic verification of 17 Sheet tabs, BigQuery, and state | `/verify` |
| `/run-cycle` | None | Trigger an immediate live prediction & calibration cycle | `/run-cycle` |
| `/snapshots` | None | Refresh and render latest market intelligence summary | `/snapshots` |
| `/help` | None | Display command help menu | `/help` |

*When an agent posts `/predict FORTIS`, the IssueOps bot acknowledges with an 👀 emoji, executes the command, and replies directly on the issue with a GitHub Flavored Markdown table.*

---

## 3. GitHub Actions Dispatch (REST API)

External agents can trigger background runs and retrieve job output via the GitHub REST API.

### A. Trigger via `repository_dispatch`
```bash
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/psw2025-cmd/angel-fno-scanner/dispatches \
  -d '{
    "event_type": "agent_action",
    "client_payload": {
      "action": "predict",
      "symbol": "POLICYBZR",
      "format": "markdown"
    }
  }'
```

### B. Trigger via `workflow_dispatch` (with GitHub CLI)
```bash
# Query top gap-up candidates
gh workflow run agent_dispatch.yml -f action=top_gapup -f limit=5 -f format=markdown

# Predict specific stock
gh workflow run agent_dispatch.yml -f action=predict -f symbol=KAYNES -f format=markdown

# Run full forensic audit
gh workflow run agent_dispatch.yml -f action=verify -f format=markdown
```

### Output Retrieval:
Every workflow dispatch run uploads its formatted result as a GitHub Actions Artifact named `agent-output-<action>`, and also writes it directly to `$GITHUB_STEP_SUMMARY`.

---

## 4. Unified Agent CLI & Python SDK (`agent_cli.py`)

If the agent has cloned the repository or is operating inside the Cloud Shell / container environment:

```bash
# Display top 5 pre-market gap-up picks in Markdown
python3 agent_cli.py --top-gapup --limit 5 --format markdown

# Query comprehensive predictions for a specific stock in JSON
python3 agent_cli.py --predict POLICYBZR --format json

# Query top CE breakouts and PE breakdowns
python3 agent_cli.py --top-breakouts --limit 5 --format markdown

# Query news impact and sentiment for a stock
python3 agent_cli.py --query-news --symbol FORTIS --limit 10 --format markdown

# Run 100% forensic verification of Google Sheet and BigQuery Sandbox
python3 agent_cli.py --verify --format markdown

# Execute an immediate live prediction & calibration cycle
python3 agent_cli.py --run-cycle --format markdown

# Export all pre-rendered snapshots to data/ directory
python3 agent_cli.py --export-snapshots
```

---

## 5. BigQuery Sandbox Schema Reference ($0 Cost Limits)

The prediction system persists all data into Google Cloud BigQuery Sandbox project `fno-angel-prod-1790444589`, dataset `fno_predictions`. All tables operate within Google Cloud Free Tier Sandbox limits ($0 billing).

### 1. `option_predictions_live` (216 Rows, 48 Columns)
Primary real-time option chain prediction table:
- `rank`: Composite prediction rank (1 to 216).
- `symbol`: NSE F&O contract ticker (e.g. `POLICYBZR`, `KAYNES`, `FORTIS`).
- `action_rating`: Forensic action signal (`🚨 GAMMA SQUEEZE ALERT`, `🔥 STRONG CE BREAKOUT`, `💥 SEVERE PE BREAKDOWN`, etc.).
- `ce_win_prob` / `pe_win_prob`: Calibrated directional win probabilities (0% - 100%).
- `directional_bias`: Dominant direction (`BULLISH_CALL` / `BEARISH_PUT`).
- `expected_gap_pct`: Forecasted 9:15 AM opening gap-up/gap-down percentage.
- `gap_direction`: Predicted opening direction (`GAP_UP` / `GAP_DOWN`).
- `pre_open_conviction_pct`: Conviction metric for the pre-market gap (0% - 100%).
- `target_open_strike`: Most optimal strike for the anticipated breakout (e.g. `1220 CE`, `840 PE`).
- `spot_ltp`, `futures_ltp`, `ce_ltp`, `pe_ltp`: Live market prices.
- `ce_delta`, `ce_gamma`, `dollar_gamma`: Black-76 option Greeks and price-normalized Dollar Gamma ($\Gamma \times S^2 \times 0.01$).
- `ce_iv`, `pe_iv`: Real-time implied volatility calculated via Newton-Raphson.
- `ce_chg_pct`, `pe_chg_pct`: Option price velocity (% change).
- `futures_obi`, `options_obi`: Order Book Imbalance metrics (-1.0 to +1.0).
- `atm_pcr`: Put-Call Ratio of ATM volume/OI.
- `composite_score`: Online calibrated composite ranking metric.
- `top_news_headline`, `top_news_source`, `top_news_tone`: Filtered market catalyst and Bayesian tone score.

### 2. `market_news_sentiment` (21 Columns)
Deduplicated multi-source news knowledge graph:
- `news_id`: SHA-256 fingerprint of `(symbol, title)`.
- `symbol`: Related F&O ticker.
- `source`: Media source (`NSE Corporate Filings`, `Moneycontrol`, `Livemint`, `Economic Times`, `BSE Announcements`, `Reuters India`).
- `title`, `url`, `published_utc`: News headline and timestamp.
- `news_type`: Categorization (`ROUTINE_COMPLIANCE`, `EARNINGS_FINANCIAL`, `FDA_PHARMA_REGULATORY`, `MERGER_ACQUISITION`, `PROMOTER_INSIDER`, etc.).
- `tone_score`: Normalized NLP sentiment score (-1.0 to +1.0). Routine compliance filings are strictly zero-grounded (`0.0`).
- `catalyst_tier`: Impact hierarchy (`TIER_1_TRANSFORMATIVE`, `TIER_2_MATERIAL`, `TIER_3_OPERATIONAL`, `ROUTINE`).

### 3. `prediction_calibration_log` (11 Columns)
Self-calibrating weight optimization history:
- `cycle_number`: Sequential evaluation cycle.
- `hit_rate_pct`: Top-10 prediction hit rate percentage (Target: >= 80%, currently 100.0%).
- `recall_at_10`: Fraction of true top gainers captured in predicted top 10.
- `mean_rank_of_top10`: Mean actual rank of top 10 predicted options (Target: < 12.0, currently 5.5).
- `weight_dollar_gamma`, `weight_opt_velocity`, `weight_oi_velocity`, `weight_fut_obi`, `weight_options_obi`, `weight_news_impact`, `weight_iv`: Real-time adaptive Bayesian weights.

---

## 6. Google Sheet Real-Time Streaming Tabs Reference

The production Google Sheet workbook (`1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs`) contains 17 live streaming worksheets:
1. `OPTION_PREDICTIONS`: Full 216-stock master prediction grid (48 columns).
2. `TOP_GAINERS`: Real-time top 20 Call and Put options ranked by gain percentage.
3. `PRE_BREAKOUT_SCANNER`: High-speed pre-breakout filter.
4. `CE_PE_RANK`: Comprehensive CE vs PE ranking layer.
5. `FORENSIC_LIVE`: Streaming quotes and Black-76 Greeks.
6. `NEWS_LIVE`: Live multi-source headlines and sentiment scores.
7. `NEWS_IMPACT`: Catalyst impact matrix across high-beta stocks.
8. `NEWS_TYPE_TALLY`: Distribution summary of news types across the universe.
9. `NSE_EVENTS`: Corporate events calendar and dividend ex-dates.
10. `PAPER_ALERT_LOG`: Simulated execution tracking and trade signal log.
11. `HEARTBEAT`: 45-second latency monitor and writer clock.
12. `Formula Checks`: Cell-by-cell verification gates (`GATE-01` through `GATE-07`).
13. `PRODUCTION_APPROVED`: Gate compliance certificate.
14. `Sheet1`: Primary streaming data matrix.
15. `F&O Options Top Gainers Tracker Dashboard`: Visual executive dashboard.
16. `LEGACY_F&O_DASHBOARD_OBJECT`: Backward compatibility data object.
17. `Cloud_Automation_Setup`: Architecture and cron documentation.
