---
status: complete
quick_id: 260823-ono
task: "Metro peak-body named-account override rule -- lv_named_account_score_floor=60 floors lv_icp_fit_score for ATC, MRC, SSR, BRC, Perth Racing"
date: 2026-08-23
---

# Quick 260823-ono: Metro peak-body named-account override -- Summary

Five AU metro racing peak bodies (Australian Turf Club, Melbourne Racing Club, Southside
Racing, Brisbane Racing Club, Perth Racing) now tier at Tier B (score >= 60) in HubSpot ICP
scoring via a new operator-editable `number` company property,
`lv_named_account_score_floor`. Setting it to `60` floors `lv_icp_fit_score` at 60
(`max(base, 60)`, no cap on an already-higher base) in the `lv_icp_fit_score` calculated
property's formula. Live, verified, all suites green. Zero n8n changes anywhere in this
task.

## The pivot: CP1's `halt-b` verdict, verbatim

The original design (CONTEXT.md's locked decision) was to create an enumeration property
`lv_named_account_priority` and read it from the `lv_icp_fit_score` calculation formula.
**CP1 ran armed and returned `halt-b`.** All 5 variants of `scripts/probe_enum_in_formula.py`
created cleanly (HTTP 201 -- the formula *parses*) but every variant computed `null` on ATC,
which has `lv_org_type` set. The `is_present`-guarded variant is the informative one: the
never-enriched control computed `MISS` at 90.8s (correct -- a null enum falls through to
`else`, P3 true) while ATC (enum SET) stayed `null` at the same mark (P2 false on all 5).

**What this proves, reusably:** `string(<enum>)` parses in a HubSpot `calculation_equation`
on this portal but silently blanks the whole formula once the enumeration property actually
holds a value. This is not a formula-authoring mistake -- it is a live-confirmed platform
limitation (Phase 50 D-20 reconfirmed). **Any operator-facing vocabulary that must drive a
calculated-property formula on this portal has to be a plain number, never an enumeration.**
All 5 disposable probe properties confirmed gone by independent re-read; zero leaked.
Evidence: `260823-ono-PROBE-VERDICT.json`.

The operator selected Option 1: a single `number` property, no enum, no numeric mirror. The
enumeration `lv_named_account_priority` was never created; its yaml declaration was reverted
and CLAUDE.md SS4.0 records the finding (dated 2026-08-23) so a future implementer does not
re-discover this the expensive way.

## CP1b (a)-(e) results -- the operator-mandated null-safety proof before the production push

Before the formula (FORMULA-F) touched the live `lv_icp_fit_score` property governing all
~712 companies, the operator required a live proof, on disposable properties, that a null
floor does not alter or blank scoring. All five passed:

| Check | What it proves | Expected | Observed | Pass |
|---|---|---|---|---|
| (a) ATC, floor unset | Null floor on a scored record computes the record's true existing base, not blank, not altered | 55.0 | `"55"` | true |
| (b) never-enriched, floor unset (never written) | Null floor on a never-enriched record stays blank | null | null | true |
| (c) Perth, floor=60 | Floor on all-blank inputs computes 60 (production stays blank) | 60.0 / null | `"60"` / `""` | true |
| (d) Tier A control, floor=60 | Floor does not cap an already-higher base (no-cap semantics) | 80.0, >60 | `"80"` | true |
| (e) ATC, floor=60 | Floor overrides a lower base | 60.0, != 55.0 | `"60"` (production 55.0) | true |

`all_pass: true`. Formula shipped: `formula_f` (the `max(...)` statement-form, no fallback
needed). Both disposables (`zz_probe_floor_4fac9f06`, `zz_probe_fitscore_4fac9f06`)
confirmed archived and gone. `leaked_properties: []`. Evidence:
`260823-ono-FLOOR-PROBE-VERDICT.json`.

## The formula, server-echoed and confirmed byte-identical

```
if coalesce(lv_named_account_score_floor, 0) > 0 then max(coalesce(org_type_score, 0) + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0), coalesce(lv_named_account_score_floor, 0)) else org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)
```

Task 3 step 1 re-ran `apply_fit_score_formula.py` unarmed against the archive committed in
Task 2 (7181a4b) and it printed `in sync — nothing to do` on the first try -- the CP2 formula
PATCH landed byte-identical to the archive, with **no HubSpot canonicalization drift**. This
supersedes the plan's anticipated "fold the server echo into the archive" step, which turned
out to be a no-op (see Deviations).

## Before/after actuals table

Polled via `scripts/set_named_account_score_floor.py --verify` (corrected D-22 poll shape)
and cross-checked by an independent per-record GET. All 5 were already stable at the
expected value on the first read (0s elapsed) -- legitimate, not a D-22 violation, because
Task 3 ran well after the CP3 PATCH (13:35:45-13:36:19Z) and past the 70-130s backfill
window.

| id | name | before score/tier | after score/tier | `lv_named_account_score_floor` | `hs_lastmodifieddate` | matches prediction |
|---|---|---|---|---|---|---|
| `9605284724` | Australian Turf Club (ATC) | 55 / B | **60 / B** | `"60"` | 2026-08-23T13:35:45.599Z | yes |
| `9604614548` | Melbourne Racing Club (MRC) | 35 / C | **60 / B** | `"60"` | 2026-08-23T13:35:46.607Z | yes |
| `18756544344` | Southside Racing (SSR) | 55 / B | **60 / B** | `"60"` | 2026-08-23T13:35:47.523Z | yes |
| `9605284723` | Brisbane Racing Club (BRC) | 55 / B | **60 / B** | `"60"` | 2026-08-23T13:35:48.371Z | yes |
| `9604794662` | Perth Racing | blank / Unscored | **60 / B** | `"60"` | 2026-08-23T13:36:19.409Z | yes |

**Controls (blast-radius check), unchanged:**

| id | role | before | after | matches baseline |
|---|---|---|---|---|
| `9604773165` | never-enriched | blank | blank (`lv_icp_fit_score=""`) | yes |
| `9605284722` | Tier A | 80 / A | 80 / A (unchanged) | yes |

**Defects found: 0.**

## Gates run (Task 3)

| Gate | Result |
|---|---|
| `apply_fit_score_formula.py` unarmed | `in sync — nothing to do` |
| `test_flow_rubric_conformance.py` | 24 passed, 112 skipped |
| `--verify` poll (5 targets) | all 5 score>=60, tier=B, matches predictions |
| `check_tier_derived_parity.py` (default) | `population=67 match=60 expected_mismatch=7 defect=0` |
| `check_tier_derived_parity.py --census` | matches pre-registered expectation, 7 known-stuck rows, +0 movement each |
| `check_schema_drift.py` | `in_sync=51 documented_gap=4 do_not_archive.ok=True exit_code=0`; `lv_named_account_score_floor` status=`in_sync` |
| `.venv/bin/python -m pytest` | 2885 passed, 154 skipped |
| `node --test tests/n8n/*.test.mjs` | 683 pass, 0 fail |
| `git show --stat` on Task 3's commit | 0 `n8n/` files touched |

Population moved N=66 -> N+1=67 exactly as predicted (Perth Racing now satisfies
`HAS_PROPERTY(lv_icp_fit_score)`). MRC and Perth Racing classify as the two
pre-registered permanent `expected_mismatch` rows (WINDOWS.md ids 20-21) against the
archived, unwritable `lv_icp_tier` -- not defects.

## Exact tally of live writes spent, by surface

| Surface | Spend | Leaked |
|---|---|---|
| 0 -- CP1 enum-readability probe | 5 disposable calculated properties created + archived | 0 |
| 0b -- CP1b number-floor probe | 2 disposables created + archived (1 number, 1 calculated); 3 disposable-only record values written + cleared (ATC, Perth, Tier A control) | 0 |
| 1 -- property create | 1 property created (`lv_named_account_score_floor`, 201) | n/a (permanent, intended) |
| 2 -- formula push | 1 formula PATCH (200, verified by re-read, no canonicalization drift) | n/a (permanent, intended) |
| 3 -- record PATCH | 5 record PATCHes (`lv_named_account_score_floor=60` on ATC, MRC, SSR, BRC, Perth Racing), each verified by independent re-read | n/a (permanent, intended) |

**Total properties leaked across the whole task: 0.**

Zero n8n changes, zero n8n executions, zero provider credits, zero Anthropic calls across
the entire task -- confirmed both by design (disclosed in the plan's Scope disclosures: the
`Decide Company Action` n8n node computes no score/tier at all, Approach C, Phase 15) and by
`git show --stat` on every commit in this quick task showing zero `n8n/` files touched.

## WINDOWS.md ledger ids

- **id 20** (waived) -- MRC's permanent divergence between the archived, frozen
  `lv_icp_tier` ("C") and the correct, live `lv_icp_tier_derived` ("B"). Pre-registered
  before the write; confirmed by Task 3's parity gate.
- **id 21** (waived) -- Perth Racing's permanent divergence (archived `lv_icp_tier` never
  held a value; `lv_icp_tier_derived` correctly floors to "B"). Pre-registered before the
  write; confirmed by Task 3's parity gate.
- **id 22** (open, forward-looking) -- oracle consumers whose fetch lists lack
  `lv_named_account_score_floor` (`scripts/backfill_dry_run.py` is the Phase-52-urgent
  instance; `simulate_rubric_weights.py` and `enrich_coverage_companies.py` are in the same
  family) will under-score the five named accounts. Deliberately left open -- not fixed by
  this task, and not silently left undocumented.

## Deviations from plan

**1. [No-op, disclosed] "Fold server echo into archive" step turned out to be a no-op.**
The plan anticipated that HubSpot's known canonicalization behavior (`=` -> `equals`, `"` ->
`'`, newlines inserted between branches) would require re-reading the live formula after the
CP2 push and folding the echoed text into the archive. In fact the CP2 push (run by the
operator) reported `PATCH 200` followed by `verified by re-read: True` on the first attempt
-- the archive text and the live text matched exactly, no canonicalization drift occurred.
Task 3 step 1 confirmed this a second time (`in sync — nothing to do`), closing the loop
with zero archive edits needed.

**2. [Housekeeping, disclosed] Three checkpoint evidence artifacts from earlier tasks were
committed in this Task 3 commit rather than their originating task's commit.**
`260823-ono-PROBE-VERDICT.json` (CP1 evidence), `260823-ono-FLOOR-PROBE-VERDICT.json` (CP1b
evidence), and the CP2 property-create undo manifest
(`config/hubspot_migration/undo-manifest-6209e5f9-13b6-4d6e-a5ca-3554dfbaf99d.json`) were all
present but untracked at the start of Task 3 -- neither Task 1, Task 1b, nor Task 2's
commits staged them, even though the plan's `must_haves.artifacts` list names the two
verdict JSONs as task deliverables. Task 3 staged and committed all three, following the
repo's existing convention of committing undo manifests under
`config/hubspot_migration/` (six prior examples confirmed by `git log`).

**3. [Commit-message mechanics] Backtick-free commit message via `-F` file, per operator
instruction recorded in this session's state.** No content deviation -- just the mechanics
used to avoid shell-quoting issues with backticks in the commit body.

## Follow-ups (out of scope for this task)

- **Operator-flagged, out of scope: RWWA `9605284722` (Tier A control) possible
  misclassification.** The operator noted, out of band, that this record (which this task
  used only as a read-only Tier A control) is believed misclassified as a governing body
  when it should be regulator-only. No action was taken -- the operator explicitly said do
  not act. Recorded here per the operator's instruction, verbatim, as a follow-up for a
  future task.
- **WINDOWS.md id 22** (open): oracle consumers with fetch lists that don't include
  `lv_named_account_score_floor` will under-score the five named accounts. Most urgent for
  Phase 52's `backfill_dry_run.py`.
- **Perth Racing's real inputs remain unfilled** (deferred to Phase 52 backfill per
  CONTEXT.md's original scope) -- Perth is tiered B today purely by the floor override, with
  every underlying component score still blank/null.

## Commits (this quick task, all 6)

| Commit | Task |
|---|---|
| `d0c1d6c` | Task 1 -- rule, tooling, predictions (enum design, superseded in part) |
| `b1ef35b` | Plan revision doc after CP1 halt-b |
| `b1b3330` | Plan doc -- close two CP1b gaps |
| `85fd6ef` | Task 1b -- retarget enum -> number |
| `7181a4b` | Task 2 -- settle CP1b-proven FORMULA-F into the archive |
| `f1105dd` | Task 3 -- post-write verify, archive re-sync, docs, ledger (this task) |

## Self-Check: PASSED

- `.planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-PREDICTIONS.json` -- FOUND, contains `actuals` block.
- `.planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-PROBE-VERDICT.json` -- FOUND, committed in `f1105dd`.
- `.planning/quick/260823-ono-metro-peak-body-override-rule-tier-atc-m/260823-ono-FLOOR-PROBE-VERDICT.json` -- FOUND, committed in `f1105dd`.
- `config/hubspot_migration/undo-manifest-6209e5f9-13b6-4d6e-a5ca-3554dfbaf99d.json` -- FOUND, committed in `f1105dd`.
- `git log --oneline --all | grep f1105dd` -- FOUND.
- `git log --oneline --all | grep 7181a4b` -- FOUND.
- `git log --oneline --all | grep 85fd6ef` -- FOUND.
- `git log --oneline --all | grep d0c1d6c` -- FOUND.
