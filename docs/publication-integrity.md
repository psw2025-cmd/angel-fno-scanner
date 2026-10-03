# Publication integrity and incident37081049121

The failed main run wrote prediction Sheets before its BigQuery snapshot load
failed. GitHub job failure cannot roll back those earlier writes. Whole-table
WRITE_TRUNCATE must not use schema update options; append loads retain them.

Worksheet replacement now updates before bounded cleanup and resizes only when
required. Cleanup failure is failure, not a successful truncated publication.
Scanner publication errors propagate. Prediction/news state advances only after
successful sink completion and readback.

## Completion contract

Each prediction attempt receives a unique cycle_id. BigQuery rows carry that
identity together with required run_id/git_sha/writer_id and an aware observation
timestamp. Source_timestamp currently denotes the analysis snapshot observation,
not independently verified exchange tick time. Positive LTP alone is never proof
of LIVE freshness.

PUBLICATION_STATUS starts PENDING before required prediction output writes. It
becomes VERIFIED only after exact219 symbol readback from FORENSIC_LIVE, the full
OPTION_PREDICTIONS matrix, NEWS_LIVE and BigQuery, matching BQ provenance, and
stable Sheet matrix digests. Failures become FAILED_PARTIAL where the status
service is reachable. An unreachable marker is not positive completion evidence.
This protocol detects mixed output; it does not undo partial writes or create a
distributed lease. Consumers must invoke the read-only verifier before accepting
combined outputs. Both full-verification entry points now include that gate.

Read-only command: `python scripts/verify_publication.py`. Missing legacy status
or provenance fails closed. No retrospective provenance is manufactured for old
rows. Existing PAPER journals/news append deduplication are not a transactional
outbox; durable exactly-once delivery remains a separately tracked requirement.

## Output contracts

- Manifest, FORENSIC_LIVE and the complete OPTION_PREDICTIONS matrix: exactly the
  canonical219 identities; repeated top-N sections are excluded from this check.
- NEWS_LIVE: one news-summary row per canonical underlying.
- Current scanner CE_PE_RANK/TOP_GAINERS: top200 eligible option contracts, CE and
  PE combined, positive premium and available previous-close change, exact
  contract text, ordered by measured change. Unique-underlying coverage can be
  less than219. They are not a full-universe source of truth. No prices are
  invented to fill missing ranks.
- Live CE_PE_RANK observed2026-10-03 has a legacy per-underlying schema, unlike
  current scanner output. Missing identities on that legacy output are unresolved
  until its actual publisher/filter is identified; current contract semantics
  cannot be retroactively applied to it.
- PRE_BREAKOUT_SCANNER is an unmaintained legacy tab with an observed216 label.
  It is not updated by the current authoritative prediction publisher and cannot
  establish current system health. Its banner is marked LEGACY on the next
  authorized publication; historical data remains. Consumers should use the
  verified full matrix.

## Calendar

Regular session functions share the official reviewed2026 NSE equity-derivatives
calendar, including January15's election closure and October2. Aware inputs are
converted to IST. Unknown calendar years fail closed with an update-required
error; special Muhurat sessions need a reviewed override. No schedule is changed.
Source: https://www.nseindia.com/resources/exchange-communication-holidays

## Deployment and review

Original PR11 remains separate: it contains overlapping BQ/grid fixes plus G19
forecast identity work. This incident branch preserves main's PR13 universe and
single-cycle guards without rewriting PR11 or the staged original checkout.
Before merging either PR, review the combined diff and rerun CI. A merged code
fix is not closure: require one authorized PAPER analysis publication at an
appropriate session, direct readback, and independent peer evidence. No new
prediction schedule, live orders, services or distributed-lock infrastructure
are introduced here.
