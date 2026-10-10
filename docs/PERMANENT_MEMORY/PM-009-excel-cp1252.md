# PM-009 — Excel Spreadsheet Parsing & cp1252 Compatibility

## 1. Problem Statement & Root Cause
Exported Excel sheets (`*.xlsx`, `*.xls`) or CSV exports generated on Windows often inherit local ANSI/Windows-1252 encoding or binary packaging. When naive source code gates or text linters attempt to read Excel binary spreadsheets using standard UTF-8 text decoders, Python throws `UnicodeDecodeError` or corrupts binary streams.

## 2. Impact
Pre-commit checks and source encoding gates failed when scanning repository files containing exported spreadsheets.

## 3. Resolution & Commit
- Added binary markers for `*.xlsx`, `*.xls`, `*.xlsm`, and `*.pbix` in `.gitattributes`.
- Explicitly excluded spreadsheet files from text-only encoding gates in `tools/encoding_source_gate.py`.
- Enforced UTF-8 reading with `errors='replace'` when handling CSV exports.

## 4. Prevention & Forensic Gates
- Verified by proof ledger check P-22 (`Excel cp1252 Binary Safety`) and `tests/test_data_chain.py`.
