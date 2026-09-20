---
created: 2026-09-20T00:00:00.000Z
updated: 2026-09-20
title: SJ-2's version-stale backstop stays allowlist-gated (classified "enrich"), not D-75-16's standing recompute authority -- is that still right after the operator's one-shot bump sweep becomes routine?
area: n8n
severity: low
kind: question
trigger: "the first monthly SJ-2 fire after the D-75-17 flip of ALLOW_HUBSPOT_RECOMPUTE_WRITES to true -- does the version-stale selection still land as an allowlist-gated enrich write (inert), or should it ride the standing recompute authority?"
owner: operator
---

## Found during

Phase 75 Plan 03 Task 3 (D-75-13/D-75-15/D-75-16), 2026-09-20.

## What happened

Plan 03 gave `SJ-2 Search (stale refresh)` a version-stale backstop (two new OR'd
filter groups, ANDed with `HAS_PROPERTY lv_org_type`) and taught `SJ2_CO_GATE` to treat
a version mismatch as not-skip. `SJ2_CO_GATE`'s dispatch deliberately KEEPS its plain
`"enrich"` classification (`write_request: _buildWriteRequest("enrich", ...)`,
unchanged) rather than being reclassified `"recompute"`.

This was a deliberate refusal, not an oversight: `ALLOW_HUBSPOT_RECOMPUTE_WRITES`
(D-75-16) is scoped to "the veto recompute lane" -- an on-demand, per-record
recompute. Classifying SJ-2's monthly, unattended, multi-record `lv_enrichment_requested
= true` write as `"recompute"` would silently WIDEN that standing authority onto a
scheduled batch write D-75-16 never granted it for. So while disarmed (the standing
state), SJ-2 correctly SELECTS and GATES a version-stale record but WRITES nothing --
exactly as SJ-2 has always behaved for every other staleness reason. Not a regression,
not newly inert.

The operator's intended path for a rubric version bump is the one-shot supervised sweep
(D-75-14, `scripts/remediate_veto_companies.py::post_webhook_event`-style chunked POST
with `recompute: true`, under bounded windows) -- SJ-2 is the monthly backstop for
whatever that sweep misses, not the primary mechanism.

## Question

Once the operator's one-shot bump sweep becomes a routine post-bump procedure, does
SJ-2's backstop still need to stay allowlist-gated (`ALLOW_HUBSPOT_RECORD_WRITES` +
`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS`), or does its narrow, well-understood blast
radius (one property, `lv_enrichment_requested`, on records already confirmed
version-stale and input-fresh) justify its own scoped standing authority the way the
recompute lane got one? Revisit at the trigger above -- once a real monthly run has
selected and gated a version-stale record for the first time, there will be a concrete
population size to reason about rather than a hypothetical one.
