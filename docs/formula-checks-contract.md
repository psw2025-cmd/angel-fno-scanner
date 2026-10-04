# Formula Checks contract

The `Formula Checks` worksheet is a consumer-facing gate surface. Its formulas
must match the publisher contracts in the repository; they must not infer one
worksheet's semantics from another worksheet's row count.

## Current contracts

- `FORENSIC_LIVE`: exactly 219 unique canonical underlyings, as enforced by
  `universe_contract.py`.
- `CE_PE_RANK` and `TOP_GAINERS`: at most 200 eligible option contracts, ordered
  by measured gain. These tabs are contract-ranked views and are not
  full-underlying-universe sources of truth.
- `HEARTBEAT!C2`, when column C is `Last BigQuery Sync (IST)`, must contain an
  `YYYY-MM-DD HH:MM:SS` timestamp written only after successful BigQuery and
  Sheet readback. A row count in that cell is invalid.
- The overall gate must include both core gates and rank-layer gates. A closed
  session is informational only after every applicable integrity gate passes.

## Required formulas

Assuming the canonical 219-symbol matrix occupies `FORENSIC_LIVE!2:220` and the
200 ranked contracts occupy `CE_PE_RANK!5:204`:

- GATE-01 observed: `=COUNTA(FORENSIC_LIVE!B2:B220)&" / 219"`
- GATE-01 status: `=IF(COUNTA(FORENSIC_LIVE!B2:B220)=219,"PASS","FAIL")`
- GATE-06 observed: `=COUNTA(CE_PE_RANK!A5:A204)&" / 200"`
- GATE-06 status: `=IF(COUNTA(CE_PE_RANK!A5:A204)=200,"PASS","FAIL")`
- GATE-07 observed: `=COUNTIF(CE_PE_RANK!U5:U204,"HIGH MOMENTUM")`

Do not change GATE-06 to `>=200`: the current publisher deliberately caps the
board at exactly 200 whenever at least 200 eligible contracts exist. Do not count
column C for symbol coverage; column C is the option type (`CE` or `PE`).

A stale formula may be repaired in the Sheet only through an authorized writer.
The read-only verifier must continue to fail closed until the Sheet is corrected
and a complete publication/readback is independently verified.
