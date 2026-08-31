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
