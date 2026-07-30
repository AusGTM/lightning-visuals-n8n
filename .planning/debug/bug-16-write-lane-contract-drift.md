---
status: resolved
created: 2026-07-29
trigger: "Fix the three write nodes left carrying the BUG 11/13 empty-field-map defect (found by the 16.9 verifier)"
---

## Symptoms

Three write nodes outside `wf_enrichment_cloud.json` still carry the original empty-field-map defect:

| workflow | node | defect |
|---|---|---|
| `wf_scheduled_maintenance_cloud.json` | `Review Apply Update` | `updateFields: {}` |
| `wf_contact_ingest_cloud.json` | `HubSpot Update` | `updateFields: {}` |
| `wf_contact_ingest_cloud.json` | `HubSpot Create` | `additionalFields: {}` + `email: $json.properties.email` |

Both workflows are INACTIVE and all three sit behind write-safety gates (16.10), so there is no live
exposure. But a gate stops an unauthorised write; it does not make a broken write work.

## No investigation was needed for the reported defect

Root cause was already established: the BUG 11 (Phase 16.7-01) and BUG 13 (Phase 16.9) fixes were
applied to `wf_enrichment_cloud.json` only. The other two workflows are built by different functions
and were never touched. The claims that those bugs were "fixed" were scoped to the enrichment
workflow and should be read that way.

## What the pre-fix audit found instead — BUG 16, and it is mine

The proposed fix ("reuse `_hs_http_patch_node` / `_hs_http_create_node`") was **wrong as stated**.
Reading each lane's actual row contract before touching anything — the discipline BUG 13 exists to
enforce — shows three DIFFERENT contracts:

| lane | id field | patch field |
|---|---|---|
| enrichment (`Decide Action` / `Decide Company Action`) | `hs_object_id` | `properties` |
| contact ingest (`Decide Action`) | **`contact_id`** | `properties` |
| review (`Apply Review`, scheduled) | `hs_object_id` | **`canonicalPatch` + `clearPatch`** (no `properties` key at all) |

Dropping the shared helpers in unchanged would have produced:

- `PATCH /crm/v3/objects/contacts/undefined` on the contact-ingest lane (helper builds the URL from
  `$json.hs_object_id`, which that lane never emits), and
- `{"properties": undefined}` on the review lane (helper reads `$json.properties`, which
  `Apply Review` never emits).

i.e. exactly the BUG 13 failure mode — a node reading a field its own input does not carry — in two
new places.

### BUG 16 proper: the contact-ingest write gates can never pass

Worse, the same class of mistake is ALREADY committed. The write gates spliced into contact ingest in
Phase 16.10 read:

```js
it.json.hs_object_id || (it.json.existingRecord && it.json.existingRecord.hs_object_id) || null
```

That lane emits `contact_id`, never `hs_object_id`, and has no `existingRecord`. Both gates therefore
evaluate `_writeSafetyAllows(action, null, null)`, which returns false on the null id and the null
domain — **unconditionally, regardless of the allowlist**.

The contact-ingest write gates are not gates, they are walls. This is fail-CLOSED, so it is safe and
was never a live risk, but an operator who allowlisted a contact and activated the workflow would get
silent no-ops with no indication why. It was introduced in 16.10, hours after the 16.9 verifier
flagged this exact pattern.

## Fix

Converge the lane contracts rather than parameterising the helpers three ways — one added field per
lane makes the existing gate and helper code correct everywhere:

1. contact-ingest `Decide Action` additionally emits `hs_object_id` (alias of `contact_id`, which is
   retained; `Resolve Identity` and the response path still use it).
2. review-lane `Apply Review` additionally emits `properties` = `{...canonicalPatch, ...clearPatch}`.
3. All three write nodes then move onto `_hs_http_patch_node` / `_hs_http_create_node` unchanged.
4. The contact-ingest gates start working as written, closing BUG 16 as a side effect of (1).

## Verification

- Red test first: `tests/test_write_lane_contracts.py`, asserting for EVERY gated write node in EVERY
  cloud workflow that the id and patch fields it reads are actually emitted by its upstream lane.
  That is the generic guard this whole bug class needs — not three one-off pins.

## Resolution — 2026-07-29

**Fix applied** (converged the contracts; the shared helpers were NOT parameterised):

1. contact-ingest `Decide Action` now emits `hs_object_id` alongside `contact_id`. `contact_id` is
   retained — `Resolve Identity` and the response path still read it.
2. review-lane `Apply Review` now emits `properties` = `{...canonicalPatch, ...clearPatch}`.
3. All three write nodes moved onto `_hs_http_patch_node` / `_hs_http_create_node` unchanged:
   contact-ingest `HubSpot Update` (PATCH `/contacts/{{hs_object_id}}`), contact-ingest
   `HubSpot Create` (POST `/contacts`), scheduled `Review Apply Update` (PATCH
   `/companies/{{hs_object_id}}`). All credential-bound, `onError` absent so a rejected write fails
   its execution.
4. **BUG 16 closed as a consequence of (1)**: the contact-ingest write gates read `hs_object_id`,
   which the lane now emits, so they gate rather than deny unconditionally.

**Guard**: `tests/test_write_lane_contracts.py` — three generic properties across every cloud
workflow, not per-node pins:

- a write node may only reference fields its upstream lane actually emits (BUG 13's shape);
- a write gate's id expression must be satisfiable by something the lane emits (BUG 16's shape);
- no write node may ship an empty `updateFields`/`additionalFields` (BUG 11's shape).

**Red before green**: 5 failures pre-fix, covering all three defects plus both BUG 16 gates.

**Non-vacuity proven, not assumed.** The extractor was loosened twice during development (to handle
`.filter()` pass-through nodes and ES6 shorthand keys), either of which could have silently defanged
the guard. Re-ran the predicates against the PRE-FIX artifacts from `git show HEAD:` and confirmed
they still fire:

```
wf_contact_ingest_cloud.json      BUG11: [HubSpot Update/updateFields, HubSpot Create/additionalFields]
                                  BUG16: [HubSpot Update Write Gate, HubSpot Create Write Gate]
wf_scheduled_maintenance_cloud.json  BUG11: [Review Apply Update/updateFields]
```

Suite 542 -> **551 pytest / 278 node**, zero regressions. Rebuild deterministic.

**Still not live-verified.** Both workflows remain INACTIVE and none of these three nodes has ever
executed. This fix is offline-correct and structurally guarded; per this project's own record, that
says nothing about the transport layer. Whoever activates either workflow should treat the first run
as a canary, allowlist a single throwaway record, and judge it node-by-node from `runData`.
