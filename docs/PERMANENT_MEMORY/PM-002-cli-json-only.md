# PM-002 — CLI --json-only Argument and Pure Output Contract Regression

## 1. Problem Statement & Root Cause
In `agent_cli.py`, the verify action attempted to inspect `getattr(args, 'json_only', False)`, but `--json-only` was never registered in the `argparse.ArgumentParser` instance. In addition, mixed human log statements polluted standard output, preventing automation pipelines from parsing stdout directly with `json.tool` or Python `json.loads()`.

## 2. Impact
Automated bots, CI workflows, and orchestrators failed with parser errors when trying to read JSON responses, causing false red statuses in verification pipelines.

## 3. Resolution & Commit
- Added `parser.add_argument("--json-only", action="store_true", help="Output only JSON on stdout - no human text")`.
- Reconfigured stdout and stderr to UTF-8 with replacement error handling.
- Isolated diagnostic human logs to `sys.stderr` when `--json-only` is active, guaranteeing strictly pure JSON on `sys.stdout`.
- Registered exit code 0 for audit pass, 1 for failed audit with valid JSON error payload, and 2 for argument parsing errors.

## 4. Prevention & Forensic Gates
- `tests/test_cli_contract.py` validates argument registration, `--help` output, and exit code semantics.
- `tools/nasa_cli_gate.py` asserts single JSON document on stdout without stderr leakage.
