# 29-TIMING — the measured watch bound (D-05, D-06, D-06a)

**Measured:** 2026-07-31 · **Plan:** 29-02 Task 3 · **Status: MEASURED** (with one clearly
marked extrapolation — see §4)

Produced by `scripts/enrichment_cost_ledger.py durations`, added by 29-02 Task 2. Read-only:
one GET of `/api/v1/executions` plus one GET per execution for its run data. No new endpoint,
no schema change — the ledger has always fetched `startedAt` and `stoppedAt` and never
subtracted them.

Invoked through the dotenv wrapper verbatim, per D-20:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" durations --limit 250
```

---

## 1. Raw measurement

Filter: workflow `LV Enrichment (Cloud template)`, over the 250 most recent executions on
`https://alexherman.app.n8n.cloud`. **Sample size: 5 executions**, of which 2 carry a
recoverable record count.

| Execution | Run status | Duration (s) | Records written | s/record |
|---|---|---|---|---|
| 443 | success | 34.56 | unknown — no write node in the run data | unknown |
| 442 | success | 32.10 | unknown — no write node in the run data | unknown |
| 337 | success | 36.07 | 1 (`HubSpot Company Update`) | 36.07 |
| 332 | success | 35.65 | 1 (`HubSpot Company Update`) | 35.65 |
| 328 | error | 38.85 | 0 (`HubSpot Company Update` ran, wrote nothing) | unknown |

Summary as printed:

```
sample size: 5 execution(s); 2 yielded a per-record rate
unknown duration: 0   unknown record count: 3
max_duration_seconds: 38.854
max_seconds_per_record: 36.07
p95_seconds_per_record: 36.07
```

Every duration was computable (no run was in flight). Three record counts are **unknown, not
zero**: 443 and 442 never reached a write node at all (the run decided not to write), and 328's
write node ran and emitted nothing — a genuine `0`, which is why it is excluded from the rate
rather than counted as an infinitely fast record.

**What the sample is.** All five are **company-lane, single-record** runs — one webhook event,
one company, the full provider + Haiku + Sonnet chain. The other 245 executions in the page
belong to `LV Scheduled Maintenance (Cloud)` (98 of the most recent 100) and run 0.9–3.4s; they
are schedule ticks, not enrichment work, and are excluded.

---

## 2. The numbers

| Name | Value | Basis |
|---|---|---|
| Observed max single-run duration | **38.9 s** | measured, n=5 |
| Observed max seconds-per-record | **36.1 s** | measured, n=2 |
| **Headroom rate** | **45 s/record** | observed max + ~25% |
| **`watch_bound_seconds` (the default 29-04 ships)** | **600 s (10 minutes)** | see §3 |

---

## 3. The chosen default: `watch_bound_seconds = 600`

Ten minutes, ~15× the observed maximum single run.

The cost is one-sided, which is what picks the number. A bound set too **high** costs a slightly
later "still running" message — the watch says the run has not settled yet and the operator
waits a little longer. A bound set too **low** tells the operator a perfectly healthy run is
unsettled, and after that happens twice they stop believing the watch at all. That is precisely
the failure NOTICE-02 exists to prevent, so the bound is chosen with headroom above the observed
maximum, never at the mean.

**Scaling for multi-record dispatches.** The enrichment workflow has **no `Split In Batches`**
(25-RESEARCH): every record runs the full chain before the response fires, so a dispatch of N
records takes roughly N × the per-record rate. 29-04 scales the bound accordingly:

```
bound_seconds = max(600, records * 45)
```

600 s is the floor, and it covers any dispatch up to ~13 records unaided.

**Sanity check against the platform ceiling.** Cloudflare closes the webhook response at ~100s
(524). At 45 s/record that ceiling is breached by the **third** record in a single synchronous
dispatch — consistent with the measured 32–39s single-record runs and with the observed absence
of any multi-record enrichment execution in this instance's history.

---

## 4. What is measured and what is extrapolated

**Measured:** the per-record rate for a single-record company-lane enrichment run — 32.1–38.9s
wall clock, 35.6–36.1 s/record where a record count was recoverable. n=5 (n=2 for the rate).

**Extrapolated, and labelled as such:** that the rate holds linearly at N > 1. **No multi-record
enrichment execution has ever run on this instance**, so any per-record economy of scale (a
shared token mint, a warm HTTP connection) is unmeasured and the linear assumption is
conservative in the safe direction — it over-estimates duration, which lengthens the bound.

**Re-measure trigger:** the first **10** enrichment executions carrying more than one record.
Re-run the same command and update this file; if the observed per-record rate at N > 1 differs
from 45 s by more than 30%, both the bound and Phase 25's chunk size change with it.

n=5 is a small sample and this document does not pretend otherwise — but it is a *measured*
small sample, not a guess, and the sample size travels with the number everywhere it is quoted.

---

## 5. What Phase 25 should read from this file (25-CONTEXT D-11a)

**Consume the headroom rate: 45 seconds per record.** Not the mean, not the raw 36.1s.

Chunk sizing then falls out of the ~100s webhook ceiling directly:

```
max_records_per_chunk = floor(100 s * safety / 45 s per record)
```

which at any sane safety factor is **2 records per synchronous chunk**, and 1 if the chunk must
also absorb n8n queue wait. Phase 25 should read this number rather than measure its own — that
is the whole point of measuring once (29-CONTEXT D-06, 25-CONTEXT D-11a). If Phase 25's own
canary produces a better multi-record measurement, it belongs **in this file**, replacing §1,
rather than in a second constant somewhere else.

---

## 6. Reproducing

```bash
# the enrichment workflow only (the default)
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" durations --limit 250

# every workflow, for context
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/enrichment_cost_ledger.py', run_name='__main__')" durations --limit 250 --workflow ''
```

Without the dotenv wrapper the script sees no credentials and prints
`skipped (no n8n creds)`. A bare `python scripts/...` that silently produced an empty table
would read exactly like "no executions to measure" — which is why D-20 pins the wrapper, and
why "no credentials" is a finding only once observed *through* it.
