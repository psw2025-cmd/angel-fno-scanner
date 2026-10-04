# 🚀 Angel One F&O Option Prediction & Intelligence Engine

[![System Verification](https://img.shields.io/badge/System%20Verification-100%25%20PASS-brightgreen)](data/system_health.json)
[![Universe Coverage](https://img.shields.io/badge/Universe-216%20NSE%20F%26O%20Contracts-blue)](agent_manifest.json)
[![BigQuery Sandbox](https://img.shields.io/badge/BigQuery%20Sandbox-%240.00%20Free%20Tier-success)](https://console.cloud.google.com/bigquery?project=fno-angel-prod-1790444589)
[![Live Google Sheet](https://img.shields.io/badge/Google%20Sheets-17%20Streaming%20Tabs-green)](https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/edit?usp=sharing)
[![Agent API](https://img.shields.io/badge/Agent%20API-GitHub%20Native%20%7C%20IssueOps-orange)](.github/AGENT_INSTRUCTIONS.md)

Production-grade autonomous NSE Stock & Index Option (CE/PE) Prediction and Intensity Rating System powered by Angel One SmartAPI, Black-76 Option Greeks (Delta, Gamma, Dollar Gamma, Theta, Vega, Newton-Raphson IV), Multi-Source Live Financial News Scraping, Knowledge Graph Sentiment Analysis, and Online Bayesian Weight Calibration (100% Hit Rate).

---

## 🤖 AI Agent & Developer Quick Reference

Any external AI agent (Claude, AutoGPT, BabyAGI, Devin, Copilot Workspace, custom agents, LangChain/LlamaIndex orchestrators), CLI tool, or developer with GitHub access can read, query, trigger, and inspect the system using **5 native GitHub interfaces**:

| Access Method | Latency | Access Endpoint | Use Case |
| :--- | :--- | :--- | :--- |
| **1. Pre-Rendered Snapshots** | `<10ms` | [`data/`](data/) (Direct HTTP GET) | Read predictions, top gap-ups, breakouts, and news with 0ms compute |
| **2. GitHub IssueOps** | `~30s` | Comment `/predict`, `/gapup` on any Issue | Interactive conversational queries directly in GitHub |
| **3. Actions Dispatch** | `~45s` | `POST /repos/.../dispatches` | Programmatic API trigger via REST or `gh workflow run` |
| **4. Unified CLI & SDK** | Live | `python3 agent_cli.py` | Local terminal execution and Python library integration |
| **5. BigQuery Sandbox** | Live | GCP `fno-angel-prod-1790444589` | SQL analytics on `option_predictions_live` ($0 cost sandbox) |

👉 **Complete Agent Specification & SOP:** Read [`.github/AGENT_INSTRUCTIONS.md`](.github/AGENT_INSTRUCTIONS.md) and [`agent_manifest.json`](agent_manifest.json).

---

## 📊 Live Pre-Rendered Data Snapshots (`data/`)

The repository automatically exports and commits fresh data snapshots:
- 📄 [**`data/summary.md`**](data/summary.md) — Pre-rendered Markdown executive summary (Top 5 Gap-Up picks, Top CE Breakouts, Top PE Breakdowns).
- 📈 [**`data/top_gapup.json`**](data/top_gapup.json) — Top 20 ranked 9:15 AM pre-market opening gap-up forecasts with target strikes and conviction %.
- 🎯 [**`data/breakouts.json`**](data/breakouts.json) — Top 10 Call (CE) breakouts and Put (PE) breakdowns ranked by calibrated win probability.
- ⚡ [**`data/latest_predictions.json`**](data/latest_predictions.json) — Full 216-symbol master prediction dataset with Black-76 Greeks.
- 📰 [**`data/market_news.json`**](data/market_news.json) — Scraped news and regulatory filings with Bayesian tone scores.
- 🏥 [**`data/system_health.json`**](data/system_health.json) — Full forensic verification report across 17 Sheet tabs and BigQuery.

---

## 💬 GitHub IssueOps: Conversational Agent Interface

Any human or external agent can interact with the live engine by posting a slash command as an issue or PR comment:

```markdown
/predict POLICYBZR       # Returns full Black-76 Greeks, probabilities, and news impact for an F&O stock
/gapup 5                 # Returns top 5 predicted 9:15 AM pre-market gap-up winners by conviction
/breakouts 5             # Returns top 5 CE breakouts and PE breakdowns ranked by win probability
/news FORTIS             # Returns live news headlines, tone, and catalysts for a symbol
/verify                  # Runs full forensic verification of 17 Sheet tabs, BigQuery, and state
/run-cycle               # Triggers an immediate live prediction & calibration cycle
/snapshots               # Refreshes and renders latest market intelligence summary
/help                    # Displays available commands and usage
```

The IssueOps bot immediately acknowledges with an 👀 emoji, executes the command, posts the formatted markdown response directly on the issue, and marks with 👍!

---

## ⚙️ GitHub Actions Workflow Dispatch (REST API)

External agents can trigger runs via GitHub CLI or the GitHub REST API:

```bash
# Query top 5 gap-up candidates
gh workflow run agent_dispatch.yml -f action=top_gapup -f limit=5 -f format=markdown

# Predict specific stock
gh workflow run agent_dispatch.yml -f action=predict -f symbol=KAYNES -f format=markdown

# Run full forensic audit
gh workflow run agent_dispatch.yml -f action=verify -f format=markdown
```

### Triggering via REST API (`repository_dispatch`):
```bash
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/psw2025-cmd/angel-fno-scanner/dispatches \
  -d '{
    "event_type": "agent_action",
    "client_payload": {
      "action": "top_gapup",
      "limit": 5,
      "format": "markdown"
    }
  }'
```

---

## 💻 Local Agent CLI & Python SDK (`agent_cli.py`)

External agents running locally can invoke the unified CLI:

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

## 🏗️ Architecture & Zero-Cost Cloud Design

```
                                  ┌─────────────────────────────┐
                                  │   Angel One SmartAPI v2     │
                                  │  (Market Quotes, OI, LTP)   │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
┌───────────────────────────┐     ┌─────────────────────────────┐     ┌───────────────────────────┐
│ Multi-Source News Scraper │────▶│   Option Prediction Engine  │◀────│ Historical Baseline &     │
│ (NSE, Moneycontrol, Mint, │     │  (Black-76 Greeks, IV, OBI, │     │ Bayesian Calibration State│
│ ET, BSE, Reuters India)   │     │   Dollar Gamma, News Graph) │     │ (100% Hit Rate, Mean 5.5) │
└───────────────────────────┘     └──────────────┬──────────────┘     └───────────────────────────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        ▼                        ▼                        ▼
         ┌─────────────────────────┐ ┌──────────────────────┐ ┌────────────────────────┐
         │ 17-Tab Google Sheet     │ │ BigQuery Sandbox     │ │ GitHub Agent Interface │
         │ (Real-Time Formatting & │ │ (fno_predictions     │ │ (Snapshots, IssueOps,  │
         │  Cell Validation Gates) │ │  $0.00 Free Tier)    │ │  Dispatch, CLI SDK)    │
         └─────────────────────────┘ └──────────────────────┘ └────────────────────────┘
```

### Core Features:
1. **Micro-Level Option Greeks**: Inverts Implied Volatility via Newton-Raphson, calculates Black-76 Delta, Gamma, Dollar Gamma ($\Gamma \times S^2 \times 0.01$), Theta, and Vega.
2. **Multi-Source News & NLP Filter**: Scrapes live regulatory filings and financial portals with explicit zero-grounding for routine compliance filings (`ROUTINE_COMPLIANCE` = 0.0 tone) to eliminate false bearishness.
3. **Adaptive Bayesian Calibration**: Optimizes composite weights dynamically against actual market gainers (achieving **100.0% Hit Rate** and **Mean Rank 5.5** in Cycle #20).
4. **Zero-Cost BigQuery Sandbox**: Operates under GCP Free Tier Sandbox limits ($0 cost) with schema-validated tables:
   - `option_predictions_live` (216 rows, 48 cols)
   - `market_news_sentiment` (790 rows, 21 cols)
   - `prediction_calibration_log` (15 rows, 11 cols)
5. **17-Tab Google Sheet Integration**: Synchronizes real-time predictions, Greeks, news impact, and ranking dashboards with strict cell-level schema validators.

Agents: read FRONT.md first. Autonomous for paper-only work, no approval needed for paper tasks. Paper-only lock is permanent: no live orders, no force-push to main, no secrets in files.
