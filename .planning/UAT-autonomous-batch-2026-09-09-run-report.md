**REPORT INCOMPLETE** — 2 gap(s), 0 contradiction(s) named below. This report joins FIVE primary durable stores plus one run-audit record; not all of them could be read cleanly.

## End-of-run report — a254d1eda71246a2a964922cdf5c2bd2

### Row accounting
- This run's own registered row count (run_state.total_row_ids): 2.
- Matches the original batch's 2 row(s) — every row accounted for.

### Per-record outcomes
- (no records)

### Held rows
- (no rows held by this run)
- Backlog (global held_queue, NOT attributed to this run): 4 row(s) held across all runs.

### Remainder queue
- Note: the remainder queue records only DELIBERATE ceiling stops and accepted allowance splits — it says nothing about a run that crashed mid-dispatch; a crash's own account lives in written_records, not here.
- (nothing queued)

### Spend against ceiling
- Projected executions this run (from what was attempted): None
- Ceiling verdict: **ok** — projected 7, sampled 247 spent, 2253 remaining of the configured 2500 allowance.
- Basis: projected: 1 webhook execution per chunk + 1 sub-execution per record (write_grant.EXECUTIONS_BASIS) — 61-SPIKE-VERDICT.md's P-10 found this formula OVER-STATES a real chunk's cost by roughly 3x, so treat this as a ceiling estimate, never an invoice
- 1 webhook execution per chunk + 1 sub-execution per record (the enrichment workflow has no batching node, so it fans out per record)
- If the month-to-date sample rested on an exhausted listing rather than on back-paging, the sampled spend is a LOWER bound (n8n prunes history and a pruned execution was still billed) — so the headroom the ceiling worked from was an UPPER bound.
- The ceiling is a conservative point-in-time LOCAL control; other sessions, schedulers, and grants consume the same instance-wide allowance, so zero local overshoot is not zero instance-wide overrun.

### Provider balances
- apollo: unreadable (remaining credits could not be read (not_reported_by_status_endpoint))
- lusha: unreadable (remaining credits could not be read (not_reported_by_status_endpoint))
- zoominfo: unreadable (remaining credits could not be read (not_reported_by_status_endpoint))
- Spend was bounded only for the balance(s) that could be read: none. ['apollo', 'lusha', 'zoominfo'] could not be confirmed readable, so the ceiling did not guard that part of spend (D-57-02).

### Disarm
- disarmed.

### Known gaps
- written_records: absent — no durable file exists for this run.
- held_queue: 4 backlog row(s) exist globally; held_queue carries no run attribution at all, so this report cannot confirm any of them belong to this run — shown as backlog only, never counted into this run's own held total.
