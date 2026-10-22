# LangSmith free tier for the paper scanner

The LangSmith page for agent `angel-fno`, environment `local`, is a Developer-plan tracing workspace. Retention on that page is 14 days. That is the free base tier.

This repository sends traces only inside that plan. Publication to Sheets and BigQuery finishes before a trace is attempted. A LangSmith error does not change a prediction and does not stop the paper cycle.

## What runs automatically

When `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` is present in the environment or in a gitignored `.env`, each successful prediction cycle can send one trace:

- Address: `lrn:agents/angel-fno/environments/local`
- If that workspace rejects agent addressing, one fallback post uses project `angel-fno`
- Payload: symbol count, illiquid count, top 5 ranks, reconciliation counts, paper mode, live orders = 0
- Feedback keys `paper_safety` and `free_tier_contract`, scored by local rules with no model call
- Minimum interval: 900 seconds
- Per-host monthly cap: 2000, and the cap cannot be configured above 4500

Headlines, source URLs, and credentials are not part of the trace. A payload that still contains secret material is not sent.

`credentials.load_env()` reads `.env`, `C:\AngelFNO_Workstation\.env`, and `C:\AngelFNO_Workstation\secrets\.env`. It does not replace variables that are already set. The real key stays in one of those local files. It is not committed.

Check the redacted status:

```text
python -m observability.langsmith_free --status --json-only
```

Send one smoke trace (this spends one trace from the monthly cap):

```text
python -m observability.langsmith_free --smoke --json-only
```

Exit 0 means the smoke was sent, tracing is off, or the key is absent. Exit 1 means the smoke was refused by the local contract or by LangSmith.

## Free plan limits that this code enforces

The Developer plan includes one seat and 5,000 base traces per month. A personal organization stops at 5,000 traces until a payment card is added. After a card is added, traces beyond the included amount are billed. Extended retention is a second billable metric. This code never requests extended retention.

One trace per 45-second market cycle would be about 10,000 traces in a trading month. The 900-second interval and the 2000-trace host cap keep a single workstation on the free side of the 5,000 stop. Two hosts can still add up, so the cap is per host on purpose and stays at 2000.

## Blocked because it can create a bill

These actions raise `PaidFeatureBlocked`. No environment variable turns them on.

| Action | Why it is blocked |
|---|---|
| Add a payment card | Removes the 5,000-trace stop and starts pay-as-you-go |
| Extended retention | Separate billable upgrade, 180 days |
| Automation rule from + New | A matching rule upgrades the whole trace to extended retention |
| `create_deep_agent()` and `ANTHROPIC_API_KEY` | The quickstart calls a model provider, and that provider bills the call |
| LangSmith Deployment | Dedicated compute bills while idle. Serverless replicas bill while running |
| Plus or Enterprise plan | Plus is a paid seat. Enterprise is a paid contract |
| Automatic dataset copy | Dataset rows persist after the 14-day trace is deleted. Copying is a manual data decision |

## Operator steps that stay in the LangSmith UI

The API key in this workspace cannot safely change billing settings, and this code does not call billing endpoints.

- Leave project retention on Base, 14 days.
- Do not add a card on Billing and Usage.
- Do not create an automation.
- Do not run the deepagents quickstart shown on the tracing page.

## Rollback

Remove the `_emit_free_langsmith_trace(...)` call from `run_prediction_pipeline`. Cycles continue with tracing disabled. Existing LangSmith traces expire after 14 days on the base tier.
