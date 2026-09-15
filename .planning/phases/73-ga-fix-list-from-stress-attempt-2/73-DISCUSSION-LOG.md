# Phase 73: GA fix list from stress attempt 2 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-15
**Phase:** 73-ga-fix-list-from-stress-attempt-2
**Areas discussed:** Ingest create containment (F-A6 + F-A5); Company match + freemail (F-B7 + F-B3, F-B2 ruling); Plugin report truth (F-B5 + run_manifest todo); Throttle, cost envelope, balances (F-A3r, F-A1/A2/B1/B6)

---

## Ingest create containment (F-A6 + F-A5)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-item error output | `onError: continueErrorOutput`, failed item → `create_failed` refusal row | |
| Keep fail-fast, fix via dedupe only | Leave Create as is | |
| Both: dedupe + error output | Dedupe prevents the known case; error output contains the unknown | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| No repair tool | Per-item continue prevents new orphans; reset covers UAT | ✓ |
| Script: associate orphans | Operator script from written_records | |
| Sweep condition | Named condition in backend-sweep | |

| Option | Description | Selected |
|--------|-------------|----------|
| Plugin pre-flight | extraction/preingest collapses on identity rule | ✓ |
| Backend Decide Action | n8n collapses | |
| Both | Plugin + backend safety net | |

| Option | Description | Selected |
|--------|-------------|----------|
| Report as duplicate_in_csv | First wins; loser names winner | ✓ |
| Merge into winner | Union non-conflicting fields | |
| Refuse the batch | Preview blocks dispatch | |

**Notes:** none.

---

## Company match + freemail (F-B7 + F-B3, F-B2 ruling)

| Option | Description | Selected |
|--------|-------------|----------|
| IN [bare, www.bare] | One search, operator IN | ✓ |
| Two searches | Second EQ node + carry Merge | |
| Normalise stored domains | Portal migration | |

| Option | Description | Selected |
|--------|-------------|----------|
| Out | F-B2 stays a known gap | ✓ |
| In: TLD-variant domain search | IN over TLD swaps | |
| In: fuzzy name to review | Near-name → review | |

| Option | Description | Selected |
|--------|-------------|----------|
| Both engines | Plugin clean + Decide Company Action, shared FREEMAIL_DOMAINS | ✓ |
| Plugin only | | |
| Backend only | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Review with reason | "freemail domain — supply the real website" | ✓ |
| Skip silently | | |
| Create without domain | | |

**Notes:** none.

---

## Plugin report truth (F-B5 + run_manifest todo)

| Option | Description | Selected |
|--------|-------------|----------|
| runData of Decide + Update nodes | D-70-05 channel, join row_id / hs_object_id | ✓ |
| Backend emits outcome rows | | |
| HubSpot re-read | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Join by hs_object_id | Research rows land in their company bucket | ✓ |
| Own bucket: researched | | |
| Leave unjoinable | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Fold: scope manifest per run_id | run_manifest_path(run_id); count only this run's entries | ✓ |
| Fold: key on stable_key | | |
| Do not fold | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Frozen runData fixture | 12434/12449, 24 updates + 11 creates + 1 skip | ✓ |
| Live only at attempt 3 | | |

**Notes:** none.

---

## Throttle, cost envelope, balances (F-A3r, F-A1/A2/B1/B6)

| Option | Description | Selected |
|--------|-------------|----------|
| 300 ms | 34% headroom | |
| 400 ms | 50% headroom, ~58 s per 48-row send | ✓ |
| Retry-on-429 instead | retryOnFail on the three search nodes | |

| Option | Description | Selected |
|--------|-------------|----------|
| Per-lane rate + execution model | cost_guard keyed by lane; plan_grant reads lane | ✓ |
| Keep over-statement, label it | | |
| Providers only | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Give backend-status provider keys | Lusha + ZoomInfo via provisioned credentials; Apollo unknown | ✓ |
| Accept unknown, say so | | |
| Plugin reads providers directly | | |

| Option | Description | Selected |
|--------|-------------|----------|
| One deploy, all fixes, then attempt 3 | | ✓ |
| Two deploys: ingest first | | |

**Notes:** user chose 400 ms over the recommended 300 ms.

## Claude's Discretion

- F-E1 semicolon-join in Apply Review (mechanical; shared helper or copy).
- Refusal-row shape and carry Merge / sentinel placement for the create error output.
- Preview wording for `duplicate_in_csv` and the freemail review reason.
- F-B4 fold only under §31 rule 3 with a plan-time ruling.

## Deferred Ideas

- F-B2 name + TLD variants; F-B4 name-only rows; orphan repair; retry-on-429; handoff tasks 8–12.
