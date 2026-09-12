---
created: 2026-09-12T13:00:00.000Z
updated: 2026-09-12
title: "Enrichment lane's contacts branch and the companies branch have no HubSpot property-history hop — only the contact ingest lane does"
area: "n8n-enrichment-lane, n8n-companies-branch"
severity: minor
kind: design
decision_needed: "add a propertiesWithHistory hop to the enrichment lane's contacts branch and the companies branch (mirroring the ingest lane's `HubSpot Contact History` node from Phase 72 Plan 04), or accept the pipeline's own lv_<field>_verified_at cache keys as a narrower substitute there"
owner: operator
files:
  - scripts/build_cloud_workflows.py
  - n8n/code/mergeCompanies.js
---

## Observed (Phase 72 Plan 04, 2026-09-12)

Plan 04 added a real recency/TTL promotion arm to all three merge engines
(`n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `src/merge_policy.py`) — a
`stale_refreshable` field (contacts `jobtitle`, companies `industry`) whose existing value is
older than its own `stale_after_days` now genuinely promotes when a newer provider observation
exists, keyed on `opts.historyByField[field]` — the existing value's OWN clock, sourced only
from HubSpot's `propertiesWithHistory` `versions[].timestamp`.

Plan 04's own scope line held the HTTP fetch that supplies that clock to **the ingest lane
only** (`HubSpot Contact History`, wired into `wf_contact_ingest_cloud`/`wf_contact_ingest_local`).
The enrichment lane's contacts branch and the companies branch get no equivalent hop. This is
recorded as WINDOWS.md ledger id 29 (behaviour-preserving, not a defect) and this todo is its
triaged, decidable form per CLAUDE.md §31.

## Consequence

Company `industry` recency and the enrichment lane's own contact `jobtitle` recency are
**unobservable** on those two lanes — `opts.historyByField` is never populated there, so the
recency gate always falls through to its pre-Phase-72 branch: unknown freshness resolves to
`needs_review`, exactly as it did before this phase. This is behaviour-preserving, not a
regression — an absent history hop means the gate takes the conservative branch it always took,
never a wrong promotion.

## Decision needed

Whether to:
(a) add a `propertiesWithHistory` hop to the enrichment lane's contacts branch and the
    companies branch, mirroring the ingest lane's `HubSpot Contact History` node — same shape,
    another HTTP node + carry Merge + sentinel gate, more n8n executions per run; or
(b) accept the pipeline's own `lv_<field>_verified_at` cache keys (already stamped by the
    provenance mechanism) as a narrower, no-new-HTTP-hop substitute for those two lanes.

Not resolved in Phase 72 — Task 3's own explicit scope boundary (plan 04, "Task 3 scope held
to the ingest lane only").
