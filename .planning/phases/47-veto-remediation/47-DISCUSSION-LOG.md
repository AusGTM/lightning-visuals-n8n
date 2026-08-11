# Phase 47: Veto Remediation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-11
**Phase:** 47-veto-remediation
**Areas discussed:** Phase 47/48 boundary, What triggers the recompute, Write-window shape, Unscored is the honest outcome

---

## Pre-discussion scouting findings

Three findings surfaced before questioning began and shaped every area:

1. **All 17 false-veto records are also blank-`lv_org_type` records** — a strict subset of Phase
   48's 18, not a partial overlap. ROADMAP.md had asked this be checked; the answer made 47 and
   48 nearly the same rows.
2. **Nothing writes `lv_anti_icp_flag` / `lv_anti_icp_reason` directly** — stated at
   `scripts/backfill_seed_company_scores.py:19-20`, asserted by a T-40-22 guard. Those fields are
   derived.
3. **Re-scoring alone leaves the 17 at `Unscored`** — visible in Phase 46's simulation output
   (0/Unscored, 10/Unscored), because they carry no `lv_org_type`.

---

## Phase 47/48 boundary

| Option | Description | Selected |
|--------|-------------|----------|
| One armed touch, in 47 | 47 enriches org type AND clears the veto for the 17; 48 shrinks to the remainder | ✓ |
| Keep 47 and 48 separate as scoped | Two armed windows, 17 records touched twice, two recompute cycles | |
| Clear vetoes in 47, decide 48's scope later | Defer the coupling decision rather than resolve it | |

**User's choice:** One armed touch, in 47
**Notes:** Honours the "touch once" principle that drove Phase 46's rubric-first sequencing.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — estimate before, report after | Mirror COVER-02's discipline in 47; refuse rather than truncate | ✓ |
| No — 47 stays write-only, no providers | Keep provider spend entirely in 48 | |
| You decide | Let research determine it | |

**User's choice:** Yes — estimate before, report after

| Option | Description | Selected |
|--------|-------------|----------|
| COVER-01/02 map to both 47 and 48 | Both phases carry the IDs; neither closes claiming full coverage alone | ✓ |
| Move COVER-01/02 wholly to 47 | 47 owns coverage; 48 becomes the remainder | |
| Mint new IDs for 47's share | e.g. VETO-04, keeping each ID single-phase | |

**User's choice:** COVER-01/02 map to both 47 and 48
**Notes:** Matches Phase 46's precedent of broadening existing requirement wording rather than minting new IDs.

| Option | Description | Selected |
|--------|-------------|----------|
| Enrich org_type, then one recompute | One write, one derived-field cycle, one honest end state | ✓ |
| Recompute first, then enrich | Veto-clear verifiable before provider spend; two recompute cycles | |
| You decide | Let research determine the settle order | |

**User's choice:** Enrich org_type, then one recompute

---

## What triggers the recompute

| Option | Description | Selected |
|--------|-------------|----------|
| Direct batch PATCH, backfill pattern | Reuse `compute_components` + `batch_update_companies`; ~0 n8n executions; 17 fits under `HARD_CEILING_RECORDS=25` | ✓ |
| Set `lv_enrichment_requested`, use the pipeline | Production path end-to-end, but a DAILY trigger fanning out against the 2,500/month allowance | |
| Write inputs only, no components | Smallest write surface; depends on the derived chain firing unaided | |

**User's choice:** Direct batch PATCH, backfill pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Claude web research | No provider credits; ~$0.0686/record measured in the Phase 20 canary | ✓ |
| Provider waterfall (ZoomInfo/Apollo/Lusha) | Firmographic data of record; poor org-type coverage, Lusha bills per contact | |
| Manual — they are all clubs | Set `individual_club_team` directly with recorded evidence | |
| You decide | Let research determine the source | |

**User's choice:** Claude web research
**Notes:** The "manual — they are all clubs" option was offered on a **false premise** and would
have written wrong data. See the correction section below. The web-research choice made that
error harmless.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — stamp source metadata on all 17 | Full metadata block even where policy does not compel it | ✓ |
| No — follow the policy as written | Policy scoped evidence to high-risk values only | |
| Evidence URL only | Middle path: URL and source, skip the rest | |

**User's choice:** Yes — stamp source metadata on all 17
**Notes:** Subsequently discovered to be policy-*compelled* for part of the set, not optional — see correction.

| Option | Description | Selected |
|--------|-------------|----------|
| Poll and read back per record | Reuse the existing `_settle(id, 'lv_icp_tier')` helper; fail loudly on non-settle | ✓ |
| One read-back sweep after the batch | Simpler; a slow-settling record reads as failure | |
| The HubSpot search is the proof | Treat VETO-03's zero-result search as sufficient | |

**User's choice:** Poll and read back per record

---

## Write-window shape

| Option | Description | Selected |
|--------|-------------|----------|
| Arm the batch-PATCH script itself | The armed surface is the write that actually happens | ✓ |
| Reuse `june_run_arm.py` as-is | Satisfies VETO-02's letter while arming a surface the write never touches | |
| You decide | Let research determine whether an existing gate covers direct CRM writes | |

**User's choice:** Arm the batch-PATCH script itself
**Notes:** Raised by Claude as a wrinkle — `june_run_arm.py` arms n8n, but the chosen path bypasses n8n entirely.

| Option | Description | Selected |
|--------|-------------|----------|
| Exactly 17, refuse anything larger | Cap doubles as a row-set-drift assertion | |
| Reuse `HARD_CEILING_RECORDS=25` | No new knob; would not catch drift up to 25 | ✓ |
| Small chunks, e.g. 5 at a time | Earliest possible stop; more arming cycles | |

**User's choice:** Reuse `HARD_CEILING_RECORDS=25`
**Notes:** The drift gap this leaves was flagged immediately and closed by the next question.

| Option | Description | Selected |
|--------|-------------|----------|
| Pin the 17 IDs explicitly | Cap bounds volume, pinned list bounds identity; excludes the 3 correct records by construction | ✓ |
| Re-derive live and compare before writing | Catches drift, but unrelated portal changes would block the run | |
| Cap alone is enough | The query is the definition of the target set | |

**User's choice:** Pin the 17 IDs explicitly

| Option | Description | Selected |
|--------|-------------|----------|
| Dry-run printing the exact PATCH payloads | Matches the repo's `DRY_RUN=true` default and established pattern | ✓ |
| Dry-run plus a diff against current values | Overwrites cannot hide; more output across 17 records | |
| You decide | Let planning pick the shape | |

**User's choice:** Dry-run printing the exact PATCH payloads

---

## Unscored is the honest outcome

| Option | Description | Selected |
|--------|-------------|----------|
| Land at Unscored, recorded as un-enrichable | COVER-01's bar: unresolved must be distinguishable from never-attempted | |
| Enrich content and region too, in the same touch | Every record lands on a real tier; widens 47 further | ✓ |
| Org type only, ignore the tier outcome | Whatever falls out is Phase 49's problem | |

**User's choice:** Enrich content and region too, in the same touch
**Notes:** Third scope widening. Flagged as such before the confirmation question below.

| Option | Description | Selected |
|--------|-------------|----------|
| Flag false, reason cleared | The false veto was never real; this is what makes VETO-03 return zero | ✓ |
| Flag false, reason records why it was cleared | Preserves history at the cost of VETO-03's search matching | |
| You decide | Let research determine what the derived chain produces | |

**User's choice:** Flag false, reason cleared

| Option | Description | Selected |
|--------|-------------|----------|
| Leave unknown, never write false | Writing `false` on absent evidence manufactures the very false-veto class this phase clears | ✓ |
| Write false when research finds no content | Every record gets a definite tier; punishes thin websites | |
| Flag for human review | Honest, but requires defining a review queue | |

**User's choice:** Leave unknown, never write false

| Option | Description | Selected |
|--------|-------------|----------|
| Confirmed — record it as deliberate | Final boundary: enrich all scoring inputs for the 17, clear vetoes, one armed touch | ✓ |
| Too wide — pull back to org_type only | Records may land Unscored, recorded as un-enrichable | |
| Too wide — unmerge, keep 47 as originally scoped | Two armed windows, 17 records touched twice | |

**User's choice:** Confirmed — record it as deliberate

---

## Correction made during discussion

Claude stated early that the 17 records were "all named jockey/turf clubs" and offered a
"set them manually, they are all clubs" option on that basis. **That premise was wrong.**
Enumerating the IDs from `46-SIMULATION-REPORT.md` showed at least five non-clubs:

| Record | HubSpot ID | Likely org type |
|---|---|---|
| Simtech LED | 18047161864 | `hardware_vendor` — a **hard veto** |
| Jam TV | 17317850381 | broadcaster / content producer |
| Editix | 17317381378 | content producer |
| The Rumble / Pacific Action Sports | 20943964946 | content producer |
| Thoroughbred Park / Wyong / Pinjarra Park | 10152138518 / 10215097384 / 17696004613 | venues, not obviously clubs |

The manual option would have scored a likely LED hardware vendor as a club at +15. It was not
selected. Two further consequences were folded into CONTEXT.md as D-17: several of these values
are policy-compelled to carry an evidence URL, and Waikato Racing Club (`20538284384`) is NZ
rather than AU, proving region must be researched rather than defaulted.

---

## Claude's Discretion

- Exact chunking within the 17 (one chunk permitted; smaller allowed).
- Dry-run output format beyond printing the exact PATCH payloads.
- Whether the per-record "could not establish" note lives in a property, the run report, or both.
- Polling interval and timeout for `_settle`.

---

## Deferred Ideas

- The 1 remaining blank-`lv_org_type` record outside the 17 — Phase 48.
- Full-population re-score and closing the parity red window — Phase 49.
- A `lv_icp_scoring_version` property — still rejected under no-new-properties; second phase to pay its cost.
- A needs-review queue for un-enrichable records — considered for the evidence-less case, not taken.

### Reviewed Todos (not folded)

Same three keyword-noise matches as Phase 46, none in scope for a record-write phase:
- Sweep crontab pins a versioned plugin path (0.60) — admin/install concern.
- UAT 2.2 names two header aliases the column mapping does not support (0.60) — contact ingestion.
- Enrichment throughput, 82% two sequential Anthropic calls (0.40) — concerns the n8n path D-06 rejected.
