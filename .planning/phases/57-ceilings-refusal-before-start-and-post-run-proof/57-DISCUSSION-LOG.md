# Phase 57 Discussion Log

**Date:** 2026-08-31
**Mode:** discuss (standard)
**Output:** `57-CONTEXT.md`

Human-reference record only. Downstream agents read `57-CONTEXT.md`, not this file.

## D-57-00 — supersedes D-53-02 (recorded at Task 3, plan 57-01, since it is the ruling
## the rest of this phase's decisions sit on)

> **D-57-00 supersedes D-53-02 for every run this milestone covers.** D-53-02 recorded that a
> grant's computed ceiling is disclosure, not constraint — correct while a human watched every
> send. Phase 57 makes the execution allowance a conservative binding preflight refusal and a
> pre-send mid-run stop. The prior behaviour remains historical context, not current behaviour.
> Sampling limits and the retention caveat are disclosed rather than pretended away.

## Areas offered, and what the operator chose to discuss

All four offered areas were selected: ceiling authority, unknowable budgets, report vocabulary,
and what refusal offers.

## Area 1 — Ceiling authority

**Asked:** what should a breach actually do, given RUN-05 only covers refusing before start and
P-10 measured the projection as inexact?

**Options presented:** hold remaining rows and finish (recommended) · abort the run · refuse
before start only · breach is advisory.

**Chosen:** hold the remaining rows, finish the batch, emit `ceiling_breach`.

**Note:** chosen option is the one consistent with D-61-07's existing hold-don't-block shape, so
the breach reuses a mechanism rather than adding a fifth way for a row not to land.

## Area 2 — Unknowable budgets

**Asked:** what should a ceiling do when it cannot read a balance? n8n exposes no usage endpoint
(P-12) and G-4 records two of three provider balances reading `unknown`.

**Options presented:** proceed and record the blind spot (recommended) · refuse on unknown ·
drop that provider · operator acknowledges at grant time.

**Chosen:** proceed, record the blind spot in the grant and the report.

**Surfaced during the exchange, and carried into CONTEXT as a constraint:** refusing would block
essentially every run today, since 2 of 3 balances are unknown. And because provider spend is
therefore only partly guarded, the mid-run breach of Area 1 becomes the main protection — which
raises how confidently a breach must be *detected*.

## Area 3 — Report vocabulary

**First attempt withdrawn.** The initial option set included an outcome labelled "refused (backend
declined)". The operator asked what would actually cause the backend to refuse — a question the
option could not answer, because the label was invented rather than read off the system.

**Investigated instead of answered from memory.** `written_records.classify_item` collapses every
non-write action into `not_written`. The backend's real `action` vocabulary is `create`, `update`,
`write_blocked`, `review`, `needs_match_review`, `skip`, `proposed`, `research_failed`,
`recompute_refused`. Two concrete defects follow from the collapse: a `write_blocked` row (which
WOULD have been written — AFTER-03's exact case) is indistinguishable from a failure, and
`skip`/`proposed` rows, which are successes, make a clean run read as half-unlanded.

**Re-asked with the real vocabulary. Chosen:** preserve the backend's own distinctions —
`written` / `created_id_unknown` / `gated` / `held` / `failed` / `no_action`.

## Area 4 — What refusal offers

**Asked:** RUN-05 says a refusing run "offers a smaller batch" — framed as a consent question, since
a 300-row batch trimmed to 180 may or may not still be the batch that was agreed to.

**Options presented:** largest affordable prefix with re-consent · offer covered by the original
grant · operator names the size · auto-split across runs.

**Chosen:** auto-split across runs.

**Derived constraint recorded without asking (D-57-05):** GRANT-06 says a grant is never persisted
and a resumed run gets a fresh one. Auto-split therefore queues WORK, not AUTHORITY — each
subsequent run opens its own grant. Recorded as `one-way` reversibility and flagged as a
checkpoint for the operator if the planner finds the two cannot both hold.

## Scope creep

None raised. Three pending todos were reviewed; none folded. The enrichment-throughput todo was
flagged to the planner as overlapping the Anthropic ceiling without being in scope.

## CHECKPOINT RULINGS (waves 1 and 2 — owned by plan 57-02, per M-2)

Three writers across this phase, in wave order, each named — never two at once: this section
(57-02, waves 1 and 2's rulings), 57-05 Task 4 (wave 3, its own entry), and `.planning/STATE.md`
(57-03's own one-way ruling). Recorded here by 57-02's continuation agent.

### 57-01 Task 2 (RUN-05) — option-a selected

Ship the preflight refusal with its sampling limits disclosed; the pre-send mid-run tally is the
load-bearing guard. Measurement, read-only against the live instance: `allowance 2500,
spent_sampled 134, remaining_sampled 2366, covers_full_window false, listing_exhausted true,
truncated_by_page_cap false, observed_span_hours 159.88, sampled TRUE`.

Two facts the record must carry:

1. `sampled: true` arrives via `listing_exhausted` while `covers_full_window` is false —
   exactly the path 57-01's REVIEW-57-H1 fix created, so on this quiet instance that fix is what
   makes RUN-05's refusal reachable at all.
2. An earlier `sampled: false` reading was SUPERSEDED and must not be recorded as the result — it
   was caused by `n8n_monthly_execution_allowance` being absent from the live plugin config, not
   by an unsampleable account. Setting that key to 2500 (the value `config/execution_budget.yaml:24`
   pins) also re-armed Phase 45's burn-rate alarm, which had not been watching the execution
   budget while the key was missing.

### 57-02 Task 1 (this plan) — the write vs write_attempted split — option-b selected

Split the outcome vocabulary by what the evidence actually supports: `written` for a **create**
whose id was **echoed back** in the response — terminal evidence the record now exists;
`write_attempted` — a NEW eighth word — for an **update**/**enrich** whose `hs_object_id` was
**known before** the PATCH — proves the write was permitted and attempted, never that it landed
(`Build Ingest Response` even falls back to `row.hs_object_id` when no write response was
joined). Closes REVIEW-57-H6 and satisfies CONTEXT's `<specifics>` rule that "'Written' must
never be inferred", at the cost of an eighth word and this amendment to D-57-03's table.

No id is ever fabricated; `created_id_unknown` stays as-is; `write_blocked` keeps its own
recoverable word `gated`; `skip`/`proposed` remain successes.

**D-57-03's table, amended** (was: `written` | `create`/`update` with an `hs_object_id` | nothing):

| Outcome | Backend `action` | What the operator does |
| --- | --- | --- |
| `written` | `create` **with** an `hs_object_id` (the id was echoed back — terminal evidence) | nothing |
| `write_attempted` | `update`/`enrich` **with** an `hs_object_id` (the id was known before the write — proves attempt, not landing) | spot-check the record if it matters |
| `created_id_unknown` | `create` whose response carried no id | nothing; id unrecoverable, never fabricated |
| `written_id_unknown` | `update`/`enrich` whose response carried no id | open this row's record and confirm |
| `gated` | `write_blocked` | **open a grant and re-send — this row would have been written** |
| `held` | `review`, `needs_match_review` | review the row and decide |
| `failed` | `research_failed`, `recompute_refused`, or an unrecognised action | retry, or fix the input |
| `no_action` | `skip`, `proposed` | **nothing — these are successes** |

### 57-04 Task 2 (ZoomInfo probe) — option-run selected and executed

Verdict `readable`, 9381 raw ZoomInfo credits, `lusha_delta` 0, instance
`alexherman.app.n8n.cloud`, checked 2026-08-31T07:15:27Z. G-4 closure-table row: CLOSED for the
ZoomInfo half. The `provider_error` from the 2026-08-25 walk is gone and needed no fix — the
suspected missing `Accept` header was already fixed in current code.
