---
status: awaiting_human_verify
trigger: "scoring adjustment likely required, the rubric may be faulty. Review HubSpot view hubspot-crm-exports-lv-scored-uat-2026-08-10.csv. (1) Entain -70 appears to be a mistake from testing, check and revert if it is, if not explain why. (2) Many horse racing/turf clubs are scored low — scoring issue or enrichment issue?"
created: 2026-08-10
updated: 2026-08-10
diagnose_only: false  # superseded 2026-08-10: continuation invoked with goal: find_and_fix
---

# Blank lv_country_region_normalized fires the non-ANZ hard veto

## Symptoms

- **Expected:** an Australian racing club with unknown enrichment scores `Unscored` /
  `Needs Review`. A hard veto fires only for a *genuinely* non-ANZ company.
- **Actual:** 17 of the 66 scored companies carry `lv_anti_icp_flag=true` +
  `lv_anti_icp_reason="Non-ANZ geography"` while `lv_country_region_normalized` is **blank**.
  13 of the 17 are Australian racing clubs; one is NZ (Waikato). All are tier D (disqualify).
- **Repro:** any company with blank `lv_country_region_normalized` — regardless of the native
  `country` field — scores tier D with a non-ANZ veto.
- **Timeline:** present in the current scored population (UAT export 2026-08-10, v0.7 engine).

## Evidence

- timestamp: 2026-08-10 — Blast radius over all 66 scored records (live read via
  `src/hubspot_client.get_record`): **17 false veto** (blank region + "Non-ANZ" reason),
  **3 genuine** (Ironman/US, Gravity Media/UK, Entain/Isle of Man — all `region=Other`),
  46 no veto. **18 of 66 have no `lv_org_type` at all** (never enriched).
- timestamp: 2026-08-10 — `src/icp_scoring.py:70`
  `region_key = region if region in ["AU","NZ","ANZ"] else "non_anz"` — **unknown collapses to
  non_anz**, and `:87-89` fires the hard veto off `region_key`. The `:41-42` fallback to native
  `country` is dead code that cannot help: the raw value "Australia" is never in the AU/NZ/ANZ
  set, so it maps to non_anz too.
- timestamp: 2026-08-10 — Sample records: Bunbury Turf Club (9604738976) country=Australia,
  region blank, no `lv_org_type`, score 0, tier D, reason "Non-ANZ geography".
  Kalgoorlie-Boulder (18796602894) country=Australia, region blank, revenue band set, score 10,
  tier D. Contrast Geraldton Turf Club (9605284721): region=AU, org_type=individual_club_team,
  produces_content=true → 35, tier C, no veto.
- timestamp: 2026-08-10 — Rubric contract in `config/icp_scoring.yaml`: hard vetoes are
  specified to fire for non-ANZ / no-content / hardware-vendor; missing required inputs are
  specified to yield `Unscored`. Unknown ≠ non-ANZ, so the current behaviour contradicts the
  documented rubric. `config/icp_scoring.yaml`'s `geography:` map already has an
  `unknown: 0` key sitting unused next to `non_anz: 0` — the config was already correct;
  only the code (Python AND its JS port, see below) never distinguished the two.
- timestamp: 2026-08-10 — **Live-flow parity check (next_action from the prior pass), done.**
  `config/hubspot_flows/4626722240-geography-score.after.json` (currently-armed HubSpot
  native "Geography Score" automation flow) has ONLY two branches — `lv_country_region_
  normalized IN [AU,NZ,ANZ]` -> `geography_score=10`, default -> `geography_score=0` — no
  veto-writing action at all. `.before.json` (pre-Phase-40) DID have a third branch
  (`IS_UNKNOWN` -> no veto) plus a default-path `lv_anti_icp_flag=true` action; Phase 40
  deleted the veto action entirely when retargeting from native `country` to
  `lv_country_region_normalized` (`PORTAL-FACTS.md` "Plan 05 — Task 1"). Confirmed by
  `tests/test_flow_rubric_conformance.py::test_no_archived_flow_writes_veto_properties`:
  zero archived `.after.json` flows write `lv_anti_icp_flag`/`lv_anti_icp_reason`. **The
  HubSpot native automation flows are NOT the source of the 17 live false vetoes** — they
  were already fixed in Phase 40 and do not fire this bug.
- timestamp: 2026-08-10 — `PORTAL-FACTS.md` "Plan 05 Task 3" measured (2026-08-07, read-only
  portal search): `lv_anti_icp_flag EQ "true"` -> **0** records; `lv_anti_icp_flag
  HAS_PROPERTY` (any value at all) -> **0** records, portal-wide (711 companies). "No real
  company in this portal has ever had the veto branch actually fire and land a write" as of
  2026-08-07. The 17 false vetoes in the 2026-08-10 UAT export therefore landed via a write
  path that fired AFTER 2026-08-07 and is NOT any HubSpot native automation flow.
- timestamp: 2026-08-10 — **Live HubSpot property-history trace, Bunbury Turf Club
  (9604738976)**: `GET /crm/v3/objects/companies/9604738976?propertiesWithHistory=
  lv_anti_icp_flag,lv_anti_icp_reason,lv_country_region_normalized,geography_score,
  lv_icp_tier`. `lv_anti_icp_flag="true"` and `lv_anti_icp_reason="Non-ANZ geography"` were
  both written **2026-08-08T11:00:37Z, sourceType=INTEGRATION, sourceId=44179801** (a
  private-app write — the n8n Cloud HubSpot credential, NOT `sourceType=AUTOMATION_PLATFORM`
  which is how the native flows write). `lv_icp_tier="D"` was written 2 seconds later
  (11:00:39Z) by `sourceType=AUTOMATION_PLATFORM` (WF1, reading the already-`true` flag —
  confirms WF1 itself is innocent, it just obeys what it's given). `lv_country_region_
  normalized` property history is **empty (`[]`)** — this field has never been set on this
  record, ever; "blank" is not a stale/missing-refresh artifact, it is a record that has
  genuinely never been enriched.
- timestamp: 2026-08-10 — **Root cause located: `scripts/build_cloud_workflows.py`'s
  `ENRICH_DECIDE_CO_CLOUD` Code node (compiled into the "Decide Company Action" node of
  `n8n/wf_enrichment_cloud.json`, the ARMED n8n Cloud enrichment workflow)**. Its
  `_regionKey(v)` function is a byte-parity JS port of `src/icp_scoring.py`'s Python bug —
  `return (v === "AU" || v === "NZ" || v === "ANZ") ? v : "non_anz"` — collapsing
  `undefined`/`null`/`""` into `"non_anz"` exactly like the Python oracle, then
  `if (region === "non_anz") vetoReasons.push("Non-ANZ geography")` fires the veto and this
  node PATCHes it directly to HubSpot (explaining the `INTEGRATION` sourceType). This is a
  **split-brain defect**: two independent implementations of the same rubric rule
  (`src/icp_scoring.py`, the Python oracle used only by offline tests/backfill component
  scoring, and this inlined JS, the actual live production write path) both had the
  identical unknown-collapses-to-non_anz bug, and only the JS copy is ever exercised
  against real HubSpot records — `scripts/backfill_seed_company_scores.py` (the only other
  live writer touching these inputs) is confirmed clean: it patches only the five
  component-score properties, never `lv_anti_icp_flag`/`lv_anti_icp_reason` (own docstring
  + code inspection). `ENRICH_DECIDE_CO_LOCAL` (the dry-run/local sibling variant) has no
  veto derivation at all, so it was never a second copy to fix.
- timestamp: 2026-08-10 — A closely related comment block at (pre-fix) line ~4011 of
  `scripts/build_cloud_workflows.py` documents a Phase 40 fix (VETO-01/02, 2026-08-07) for a
  *different* manifestation of the same `_regionKey(undefined) -> "non_anz"` mechanism: the
  company-search HTTP fetch nodes omitted `lv_country_region_normalized` from their
  requested-properties CSV, so `existing.lv_country_region_normalized` read `undefined` on
  every run that didn't freshly re-promote the field — even for a company whose region WAS
  set in HubSpot. That fix (adding the property to the CSV) only closes the "unfetched this
  run" case. It does nothing for a company whose region has **genuinely never been
  enriched** (this bug's case, and the actual shape of all 17 live false vetoes) — the CSV
  fetch correctly returns blank for those, and `_regionKey` still turned that blank into a
  veto. Same root function, two different trigger paths; only one was previously fixed.

## Eliminated

- hypothesis: Entain's -70 is a testing artifact — **ELIMINATED**. Live values: org_type
  `gambling_operator` (base 0), produces_content false (0), region `Other` (0), revenue band
  `1.2B+` (**-50**), gambling deduction (**-20**) = **-70**, both hard vetoes legitimately fired.
  Record 10024564084 is the global Entain plc (Isle of Man, $4.69B revenue, 21,226 employees).
  Correct per rubric — **no revert warranted**. Note the separate unscored record
  **29846742629 "Entain Australia & New Zealand" (Brisbane)** is the right target for an ANZ
  gambling assessment; gambling is a -20 deduction, not a veto, so an ANZ entity with content
  could still land B/C.
- hypothesis: the 35/45 club cluster is a bug — **ELIMINATED, rubric-by-design**. Geraldton 35 =
  individual_club_team 5 + content 20 + ANZ 10 + `<1M` revenue 0. ATC 45 adds the 50-500M band.
  Governing bodies score 40 for org_type alone, which is why Harness Racing Victoria / Racing
  Queensland / RWWA / Tasracing all reach 80/tier A. This is the deliberate
  governing-body-first design (tier C → `work_via_league`), **not** a defect.

## Current Focus

reasoning_checkpoint:
  hypothesis: "`_regionKey`/`region_key` in both `src/icp_scoring.py` (Python oracle) and
    `scripts/build_cloud_workflows.py`'s `ENRICH_DECIDE_CO_CLOUD` (the live n8n Cloud
    'Decide Company Action' Code node) collapse an unenriched/blank
    `lv_country_region_normalized` into the same bucket as a genuinely-known non-ANZ value
    ('non_anz'), and the hard-veto check fires on that bucket -- converting absence of
    enrichment into a disqualifying tier-D veto."
  confirming_evidence:
    - "Live property-history GET on Bunbury Turf Club (9604738976): lv_anti_icp_flag/
      lv_anti_icp_reason written sourceType=INTEGRATION sourceId=44179801 (n8n Cloud's
      HubSpot credential), lv_country_region_normalized history=[] (never set, ever)."
    - "config/hubspot_flows/4626722240-geography-score.after.json (armed HubSpot native
      flow) has zero veto-writing action -- ruled out as the producer."
    - "PORTAL-FACTS.md 2026-08-07 measurement: 0 companies portal-wide had
      lv_anti_icp_flag set at all -- the 17 false vetoes landed strictly AFTER that date,
      narrowing the write window to exactly the n8n Cloud pipeline."
    - "scripts/build_cloud_workflows.py:_regionKey source read directly: byte-identical
      unknown-collapses-to-non_anz logic to src/icp_scoring.py:70 (pre-fix)."
  falsification_test: "A fixture with lv_country_region_normalized absent/None/empty-string
    scores anti_icp_flag=true with reason 'Non-ANZ geography' -- true pre-fix (both
    Python and JS, confirmed red), false post-fix (confirmed green, both suites)."
  fix_rationale: "config/icp_scoring.yaml already carries an unused geography.unknown: 0
    key distinct from geography.non_anz: 0 -- the rubric config was already correct. The
    fix restores that 3-way distinction (AU/NZ/ANZ, non_anz, unknown) in both engines: only
    a KNOWN, different region value maps to 'non_anz' and fires the veto; a genuinely
    blank/never-enriched value maps to 'unknown', contributes the same 0 geo points as
    before, but never fires the veto. Root cause addressed at its single point of
    definition in each engine, not patched at a caller."
  blind_spots: "Did not re-run the live n8n Cloud workflow or re-score the 17 real HubSpot
    records -- operator-gated write, out of this pass's scope (see Resolution). Did not
    audit every other n8n Cloud Code node for a similar unknown-collapse pattern outside
    the geography veto specifically (scoped this pass to the reported symptom)."
  candidate_causes:
    - "code: _regionKey/region_key's binary AU-NZ-ANZ-vs-non_anz partition, in BOTH the
      Python oracle and its independently-hand-ported JS twin (split-brain -- two
      implementations of one rubric rule, only one exercised live)."
    - "data/enrichment gap (separate, already-documented bucket 2): 18 of 66 records were
      never enriched at all, which is why the defect above had input to fire on -- but the
      enrichment gap itself is not a defect this session fixes."
  and_gate: "no -- the veto fires off a single boolean partition (region_key==non_anz);
    the enrichment-gap bucket is a pre-condition that supplies blank input, not a second
    simultaneously-required fault condition in the scoring logic itself."
next_action: Present CHECKPOINT REACHED to the operator for the two remaining operator-gated
  live actions (deploy the rebuilt n8n Cloud workflow; refresh the 17 already-mis-scored
  records) -- the code fix itself is applied and self-verified (see Resolution).

## Three distinct buckets (do not conflate)

1. **Scoring defect** — blank region → false non-ANZ veto. 17 records. Fix in code + flows.
2. **Enrichment gap** — 18 of 66 never got `lv_org_type`. The defect turns that gap into a
   false veto instead of an honest `Unscored`.
3. **Business calibration (operator's call, not a bug)** — `individual_club_team=5` caps clubs
   at 35-45 while governing bodies reach 80. If racing clubs are LV's core market, that weight
   is a rubric decision to revisit deliberately; it was not auto-adjusted.

## Resolution

root_cause: Two independent implementations of the ICP geography-veto rule both collapsed an
  unenriched/blank `lv_country_region_normalized` into the same "non_anz" bucket as a
  genuinely-known non-ANZ value, firing the hard veto on absence of enrichment: (1)
  `src/icp_scoring.py:70` (Python oracle, used by offline tests + the component-score
  backfill script — never itself PATCHes the veto fields live) and (2) `_regionKey` inside
  `ENRICH_DECIDE_CO_CLOUD` in `scripts/build_cloud_workflows.py`, compiled into the "Decide
  Company Action" node of the ARMED `n8n/wf_enrichment_cloud.json` workflow — THIS is the
  actual live producer of the 17 false vetoes, confirmed via HubSpot property-history
  (`sourceType=INTEGRATION`, not `AUTOMATION_PLATFORM`). The HubSpot native automation
  flows were ruled out — Phase 40 already removed their veto-writing action entirely; they
  contribute zero to this bug.
fix: Restored the AU/NZ/ANZ vs. non_anz vs. unknown 3-way distinction in both engines
  (`config/icp_scoring.yaml`'s existing-but-unused `geography.unknown: 0` key was already
  correct — only the code never used it). `src/icp_scoring.py`: added `region_raw` (checked
  before the native-`country` fallback) so `region_key` is `"unknown"` — not `"non_anz"` —
  whenever `lv_country_region_normalized` itself is absent/None/empty, distinct from a
  known-different value. `scripts/build_cloud_workflows.py`'s `_regionKey(v)`: added the
  same three-way branch (`AU`/`NZ`/`ANZ` -> itself, `undefined`/`null`/`""` -> `"unknown"`,
  else -> `"non_anz"`); only `"non_anz"` fires `vetoReasons.push("Non-ANZ geography")`.
  Regenerated `n8n/wf_enrichment_cloud.json` via `.venv/bin/python
  scripts/build_cloud_workflows.py` (local codegen, no network/no live write) — the built
  JSON now carries the fixed JS, ready to deploy. Behavioral nuance (documented, not a
  defect): a record whose region is blank but whose `lv_org_type`/`lv_produces_content` ARE
  known now lands a real tier off its remaining points (e.g. individual_club_team + content
  = C, no geo bonus) rather than being forced to Unscored — blank region alone is a missing
  +10, not a data-completeness gate. A record like Bunbury Turf Club, where `lv_org_type` is
  ALSO unknown, still resolves to Unscored via the existing confidence-downgrade branch —
  this is the debug session's literal "Unscored/Needs Review" expectation, reachable now
  that no veto short-circuits to D first.
verification: |
  Both suites green after the fix, both new regression suites confirmed RED before / GREEN
  after (git-stash roundtrip, not just written-then-passing):
    - `.venv/bin/python -m pytest -q` -> 2491 passed, 121 skipped (was 2490 passed before
      the new tests were added; zero regressions).
    - `node --test tests/n8n/*.test.mjs` -> 658 passed, 0 failed.
    - Single-producer scan unaffected: `tests/test_flow_rubric_conformance.py::
      test_no_archived_flow_writes_veto_properties` still passes (native flows still write
      nothing) -- this fix touches only the two engines that DO own the veto derivation.
    - Built-artifact diff is a single-line jsCode string change in
      `n8n/wf_enrichment_cloud.json` (git diff --stat), confirming no codegen drift beyond
      the intended node.
  NOT verified (operator-gated, out of this pass's scope):
    - Deploying the rebuilt `n8n/wf_enrichment_cloud.json` to the live n8n Cloud workflow
      (PUT + a workflow bounce -- a bare PUT does not reload a running workflow, per prior
      session learning).
    - Refreshing the 17 already-mis-scored HubSpot records (remediation path per
      `tests/test_scoring_parity.py::test_veto_clear_after_correction`: PATCH
      `lv_enrichment_requested="true"` per record -- NOT `enrichment_requested`, that
      property is a confirmed no-op for the SJ-3 poller -- then the 15-min scheduled poller
      re-runs the pipeline and the veto recomputes to false by construction, no manual
      per-field correction needed).
files_changed:
  - src/icp_scoring.py (region_raw / 3-way region_key split)
  - scripts/build_cloud_workflows.py (_regionKey JS fix + 2 comment updates)
  - n8n/wf_enrichment_cloud.json (regenerated build artifact, local codegen only)
  - tests/test_scoring_parity.py (+5 offline regression tests)
  - tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs (+2 regression tests)
