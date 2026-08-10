---
status: diagnosed
trigger: "scoring adjustment likely required, the rubric may be faulty. Review HubSpot view hubspot-crm-exports-lv-scored-uat-2026-08-10.csv. (1) Entain -70 appears to be a mistake from testing, check and revert if it is, if not explain why. (2) Many horse racing/turf clubs are scored low — scoring issue or enrichment issue?"
created: 2026-08-10
updated: 2026-08-10
diagnose_only: true
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
  documented rubric.

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

hypothesis: An unknown/blank `lv_country_region_normalized` is being treated as a positive
  non-ANZ determination, converting an *absence of enrichment* into a *disqualifying veto*.
test: Score a fixture with blank region and confirm tier D + non-ANZ veto; assert it should be
  Unscored/Needs Review with 0 geography points and no veto.
expecting: Fix shape — unknown region yields 0 geo points and **no** veto; the record routes to
  Unscored/Needs Review. Do not award points to unknowns.
next_action: Confirm the live surface. These scores come from the four HubSpot workflows, not
  the Python oracle — verify the veto branch's blank-region handling in the live flow JSON via
  `scripts/fetch_hubspot_flow.py` before changing anything, then add a blank-region fixture to
  `tests/test_scoring_parity.py` as the regression home.

## Three distinct buckets (do not conflate)

1. **Scoring defect** — blank region → false non-ANZ veto. 17 records. Fix in code + flows.
2. **Enrichment gap** — 18 of 66 never got `lv_org_type`. The defect turns that gap into a
   false veto instead of an honest `Unscored`.
3. **Business calibration (operator's call, not a bug)** — `individual_club_team=5` caps clubs
   at 35-45 while governing bodies reach 80. If racing clubs are LV's core market, that weight
   is a rubric decision to revisit deliberately; it was not auto-adjusted.

## Resolution

root_cause: `src/icp_scoring.py:70` maps any region outside {AU,NZ,ANZ} — including unknown —
  to `non_anz`, which `:87-89` treats as a hard veto. Live HubSpot flow parity unconfirmed.
fix: NOT APPLIED — diagnosis only; live-flow confirmation pending and any HubSpot re-score is
  an operator-gated write.
verification: pending
files_changed: none
