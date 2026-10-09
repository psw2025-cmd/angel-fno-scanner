# PM-010 — Google Colab Notebook Cell Emoji & Unicode Printing Crashes

## 1. Problem Statement & Root Cause
Interactive Google Colab notebooks (`*.ipynb`) often include formatted progress indicators and emojis (e.g., `🚀`, `🔥`, `📊`) inside notebook cell outputs or markdown headers. When exported or run in Windows command-line environments without a UTF-8 console code page, standard output streams crashed.

## 2. Impact
Execution failures when running batch test harnesses across repository notebooks on Windows runners.

## 3. Resolution & Commit
- Notebook execution harnesses require UTF-8 stream wrapping or ASCII fallback indicators.
- Added `*.ipynb text eol=lf` in `.gitattributes`.
- Added notebook check in `tools/generate_reset_baseline.py` and `tests/test_encoding_gate.py`.

## 4. Prevention & Forensic Gates
- Verified by proof ledger check P-23 (`Colab Notebook Emoji & UTF-8 Gate`).
- Enforced across all future research notebooks.
