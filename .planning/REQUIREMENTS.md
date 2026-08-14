# Requirements: HubSpot Enrichment + ICP Scoring — v0.9

**Defined:** 2026-08-11
**Milestone:** v0.9 ICP Rubric Calibration & Veto Remediation
**Core Value:** Turn a finite, hard-to-reach ANZ sports-media TAM into a ranked, evidence-backed
target list a non-technical operator can act on from inside HubSpot.

## v0.9 Requirements

### Rubric Calibration (RUBRIC)

- [x] **RUBRIC-01**: A decision on each org-type weight under review is recorded with reasoning
      traceable to the closed-deal evidence in `icp-scoring.md`, not intuition. Confirming a
      current weight is a valid outcome — the requirement is that the decision is made and
      evidenced, not that it changes. Where a decision **overrides** the evidence on GTM grounds,
      the override and its reasoning are recorded and the underlying evidence is left intact.
      *(Scope amended 2026-08-11, operator-directed during `/gsd-discuss-phase 46`: covers
      `individual_club_team`, `regulator`, and removal of the `gambling_operator` deduction —
      originally `individual_club_team` alone. Every live doc printing a superseded value is
      updated in the same phase; see `46-CONTEXT.md` D-01…D-03 and D-13.)*

- [x] **RUBRIC-02**: Operator can see how the scored population would re-tier under proposed
      weights BEFORE committing them — a simulation over current `lv_*` inputs that writes
      nothing to HubSpot.

- [x] **RUBRIC-03**: If weights change, **all three** scoring engines carry them identically —
      `config/icp_scoring.yaml` (Python oracle), the JS port compiled into
      `n8n/wf_enrichment_cloud.json`, and the HubSpot flow
      `config/hubspot_flows/4626124224-org-type-score.*.json` — proven by the existing parity
      harness rather than by inspection. A weight that lands in one engine only is the split-brain
      failure v0.7 already paid for once. *(Amended 2026-08-11: the HubSpot org-type-score flow was
      identified during `/gsd-discuss-phase 46` as a third native scoring engine this requirement
      originally omitted. It maps `lv_org_type` → points and feeds `lv_icp_fit_score` directly, so
      a weight change that skips it diverges the portal's own score from the pipeline's.)*
      *(Further amended 2026-08-11, Phase 46 Plan 05: `46-ENGINE-INVENTORY.md`'s exhaustive
      grep found only **two** of the three engines named above actually carry an org-type point
      table — `config/icp_scoring.yaml` (Python oracle) and the HubSpot flow `4626124224`. The
      n8n JS leg (`n8n/wf_enrichment_cloud.json`, built from `n8n/code/mergeCompanies.js`)
      carries no org-type-keyed numeric table at all. For that leg this requirement is satisfied
      by a permanent absence-guard test, `tests/test_n8n_org_type_absence.py`, rather than by a
      ported weight table — see `46-ENGINE-INVENTORY.md` for the full grep evidence.)*

### Veto Remediation (VETO)

- [x] **VETO-01**: All 17 companies carrying a false non-ANZ veto are re-scored under the fixed
      rubric, and their `lv_anti_icp_flag` / `lv_anti_icp_reason` reflect that re-score.
      → 16 cleared; Jam TV `17317850381` correctly RETAINED its veto per D-23 (it is the
      Italian broadcaster, a true veto, mislabelled `false_veto` by Phase 46 only because its
      region was blank). Per-id before/after table and classifications:
      `47-RUN-REPORT.md` § "Per-id outcome"; snapshot `47-AFTER.json` (17 rows);
      classifier `scripts/veto_remediation_report.py` (`correct_non_anz`, pinned by
      `tests/test_veto_remediation_report.py::test_classify_correct_non_anz_for_the_d23_true_veto_record`).

- [x] **VETO-02**: The clearing run happens inside a deliberately-opened armed write window with
      a record-count cap, and the window is disarmed and read back as disarmed afterward.
      → Both surfaces disarmed and proven closed by `n8n_arming.disarm`'s **independent
      re-read**, quoted verbatim in `47-RUN-REPORT.md` § "VETO-02". Allowlist was exactly the
      17 pinned ids every time. **Caveat, disclosed not softened:** this took FIVE
      arm/disarm cycles, not the ONE the plan's must_have required — see
      `47-RUN-REPORT.md` § "Window accounting".

- [x] **VETO-03**: Operator can confirm from HubSpot alone — no scripts — that no company remains
      with a non-ANZ veto reason and a blank `lv_country_region_normalized`.
      → **Operator-confirmed 2026-08-12: "There are no Non-ANZ geography companies with
      Unknown for the lv_country_region_normalized."** Independently corroborated by an API
      census (4 companies portal-wide carry a non-ANZ veto — Jam TV, Ironman, Gravity Media,
      Entain — and all four have `region = "Other"` populated, so zero match the bar; it was
      17 before the window). The three non-Jam-TV rows are D-V6 re-examination candidates for
      Phase 49, tracked in
      `.planning/todos/pending/2026-08-12-d-v6-reexamine-the-four-remaining-non-anz-vetoes.md`.

### Veto Recompute (RECOMP)

*Added 2026-08-12 during `/gsd-plan-phase 47.5`. Phase 47.5 was registered in the ROADMAP as a
debug subphase with no requirement ids of its own; these four give its three workstreams a
traceable bar. They are new requirements, not a re-scoping of VETO-01/02/03, which are closed.*

- [x] **RECOMP-01**: A company whose enrichment inputs are complete can have its veto
      recomputed **on demand**, without degrading, blanking or otherwise falsifying its data
      first, and at zero provider, zero web-research and zero Anthropic cost.
      `Decide Company Action` remains the single writer of `lv_anti_icp_flag` /
      `lv_anti_icp_reason`. The bar is
      `tests/test_scoring_parity.py::test_veto_clear_after_correction` passing live with its
      assertions untouched — red since Phase 40-07 for exactly this reason.

- [x] **RECOMP-02**: A skipped record is observable to the caller. Today a complete record
      returns `status: "success"` with nothing written and no node error — the same
      silent-success class recorded in `47-BLOCKED.md`. The caller must be able to tell
      "complete, nothing to do" from "something broke".

- [x] **RECOMP-03**: The four companies still carrying a non-ANZ veto are re-examined under
      D-V6's operating-presence test, with **researched evidence URLs** rather than assertion,
      and any flip is written inside one bounded, disarmed-afterward window. Jam TV
      `17317850381` is correct and must retain its veto (D-23); Entain `10024564084` cannot
      move on a region flip because `lv_produces_content` fires a second veto.

- [x] **RECOMP-04**: The hardware-vendor veto's trigger field is **decided and recorded with
      reasoning**, and the decision lands in every engine that carries the veto predicate in
      the same commit — `src/icp_scoring.py` and the n8n `Decide Company Action` node. The
      equivalent question for `lv_is_gambling_operator` is answered in writing; the live
      census found zero divergences, so recording the answer closes it.

### Enrichment Coverage (COVER)

- [x] **COVER-01**: The 18 scored companies with no `lv_org_type` are either enriched to a real
      org type, or individually recorded as un-enrichable with a stated reason. An unresolved
      company must be distinguishable from one never attempted.
      *(Scope amended 2026-08-11, operator-directed during `/gsd-discuss-phase 47`: the 18-company
      set is covered in two parts, not one. 17 of the 18 are a strict subset of Phase 48's set,
      being simultaneously the false-veto cohort Phase 47 remediates, and are covered there. The
      1 remaining record — Racing NSW `15008671672`, flagged `blank_org_type` only with no
      `false_veto` flag — is covered by Phase 48. See `47-CONTEXT.md` D-01 and D-02.)*

- [x] **COVER-02**: The execution and provider cost of that enrichment is estimated before the
      run and reported after, against the 2,500/month n8n allowance and the current Lusha
      balance. A run that would exceed either is refused, not truncated silently.
      *(Scope amended 2026-08-11, operator-directed during `/gsd-discuss-phase 47`: this cost
      discipline applies to Phase 47's run as well as Phase 48's, per `47-CONTEXT.md` D-03 —
      the estimate-before/report-after/refuse-rather-than-truncate bar is not deferred to
      Phase 48 alone.)*

### Re-score Strategy (RESCORE)

- [x] **RESCORE-01**: A rubric change triggers a defined, budget-bounded re-score of the affected
      population rather than an ad-hoc sweep — including which records, in what chunk size, under
      which write window.

- [x] **RESCORE-02**: Because rubric-version segmentation is impossible without
      `lv_icp_scoring_version` (operator decision 2026-08-11: no new properties), any rubric
      change re-scores the ENTIRE scored population. The plan states that execution cost up front
      rather than discovering it mid-run.

- [x] **RESCORE-03**: Operator is told, in plain language, what the tier distribution was before
      and after any re-score — so a rubric change's effect on the target list is visible rather
      than inferred.

### Tier Derivation (TIER)

Added 2026-08-13, operator-directed during `/gsd-discuss-phase 50`. These close v0.9 debt rather
than opening new scope: Phase 49 W1 disclosed 4 companies whose `lv_icp_tier` is stale against a
correct `lv_icp_fit_score` and deferred the fix (`WINDOWS.md` ids 9–12). Evidence base is
`.planning/TIER-DERIVATION-SPIKE-2026-08-13.md`.

- [ ] **TIER-01**: `lv_icp_tier` no longer depends on a HubSpot property-change event to be
      correct. A derived tier reproduces WF1's live ladder exactly — `lv_anti_icp_flag` → `D`,
      `>= 70` → `A`, `40..69` → `B`, `15..39` → `C`, else `Unscored` — verified against real
      records. The 4 stuck records (`9605273630`, `9604738976`, `17696004613`, `19100977027`)
      read the tier their score already implies, with no event and no workflow run.

- [x] **TIER-02**: The blank-vs-`"Unscored"` semantics for never-scored companies are a recorded
      decision, not an accident of formula shape. The spike could not settle this from syntax:
      an uncoalesced score preserves today's blank behaviour, `coalesce(lv_icp_fit_score, -1)`
      flips roughly 646 never-enriched companies to `"Unscored"`. The runtime null question is
      answered against live records before the choice is committed.

- [x] **TIER-03**: Cutover is reversible and nothing silently breaks. Portal-side dependents on
      the existing tier *select* — lists, views, saved filters, reports, invisible from the repo —
      are enumerated first; the disposition of the old `lv_icp_tier` enum and of WF1 itself is
      decided explicitly; and no record is re-tiered outside a deliberately armed, capped write
      window, under the Phase 47–49 discipline.

## v1.0 Requirements (deferred)

### Outcome Evidence (EVID) — deferred from v0.9 on 2026-08-11

Deferred because backfill viability is unproven: 59 closed-lost deals were examined during Phase
43-04 and `lv_closed_lost_reason` was 0% filled across all of them. If historical reasons are not
recoverable, only forward capture works, which cannot inform a v0.9 recalibration.

- **EVID-01**: Closed-lost deals carry a reason in `lv_closed_lost_reason` (the property exists
  on Deals today), backfilled where recoverable.

- **EVID-02**: The revenue-band deductions (−5 at 500–750M, −50 at 1.2B+) and the gambling −20
  are tested against actual won/lost outcomes, with the result recorded whether or not it changes
  the weights.

- **EVID-03**: The supporting fields spec'd in CLAUDE.md §5.3 — `lv_qualitative_fit_summary`,
  `lv_budget_timeline_signal`, `lv_loss_reason_detail` — are created and populated. Confirmed
  live 2026-08-11 as NOT existing; creating them requires lifting the no-new-properties
  constraint.

## Out of Scope

- **`lv_icp_scoring_version`** — operator decision 2026-08-11. Accepted consequence: HubSpot
  cannot filter on JSON inside a text property, so records scored under a superseded rubric
  cannot be segmented in a list and must be re-scored wholesale. This is why RESCORE-02 exists.

- **New HubSpot properties of any kind** — same decision. `lv_closed_lost_reason` and
  `deal_source` already exist and may be used; the three §5.3 fields that do not exist are
  deferred rather than created.
  *(Scope amended 2026-08-13, operator-directed during `/gsd-discuss-phase 50`: lifted for
  **exactly one** derived-tier string property and nothing else. The lift is forced, not
  preferred — `lv_icp_tier` is `type: enumeration, calculated: false`, zero of 264 portal
  properties are calculated enumerations, and HubSpot does not support enumeration outputs for
  calculation properties, so TIER-01 is unreachable without a new property. Everything else in
  this bullet stands: `lv_icp_scoring_version` remains out of scope below, and the three §5.3
  fields remain deferred to v1.0. See `50-CONTEXT.md`.)*
  *(Scope amended again 2026-08-14, forced by a live finding during execution (D-20,
  `50-CONTEXT.md`'s Amendment): `calculation_equation` reads only NUMERIC properties, so
  `lv_anti_icp_flag` (a `booleancheckbox`) reads as null even when set and
  `lv_icp_tier_derived`'s veto branch never fired live. The lift extends to a SECOND
  property — `lv_anti_icp_flag_num`, a pipeline-written numeric 0/1 mirror of the same
  single veto derivation (`Decide Company Action` / `src/icp_scoring.py`), never a second
  derivation. Forced, not preferred, for the identical structural reason as the first
  lift — the property/type combination this phase needs does not otherwise exist in the
  portal. Everything else in this bullet still stands.)*

- **Installing the sweep cron/launchd schedule** — an admin action on the operator's machine,
  carried from v0.8 where the burn-rate alarm shipped inert. Not a v0.9 deliverable.

- **JTBD 2 weighted-rubric sign-off as a formal gate** (REQ-signoff-gate) — RUBRIC-01 records a
  decision on one weight with evidence; a full business-owner sign-off of the entire rubric
  remains a separate, downstream event.

- **Re-scoring the 3 correct vetoes** (Entain 10024564084, Gravity Media 15860277364, Ironman
  17317184159) — verified correct on 2026-08-11; they carry known non-ANZ regions and must not be
  swept up in VETO-01.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RUBRIC-01 | Phase 46 | Complete |
| RUBRIC-02 | Phase 46 | Complete |
| RUBRIC-03 | Phase 46 | Complete |
| VETO-01 | Phase 47 | **Complete** (16 cleared + Jam TV correctly retained, D-23) |
| VETO-02 | Phase 47 | **Complete** (disarm re-read verbatim; 5 windows not 1 — disclosed) |
| VETO-03 | Phase 47 | **Complete** (operator-confirmed 2026-08-12, zero results) |
| RECOMP-01 | Phase 47.5 | **Complete** (live exec 11856/11857: gate `skip` -> `enrich`, PATCH landed; test green with assertions byte-identical; 47.5-A-LIVE-PROOF § Armed window #1) |
| RECOMP-02 | Phase 47.5 | **Complete** (live exec 11853: `action:"skip"` + gate reason; 47.5-A-LIVE-PROOF §3d) |
| RECOMP-03 | Phase 47.5 | **Complete** (registry-grade D-V6 evidence: 47.5-B-EVIDENCE.md; written in ONE window, disarm re-read verbatim: 47.5-RUN-REPORT.md § Part 2; census 4 -> 2, Jam TV retains its veto per D-23 and Entain held by its second veto: 47.5-AFTER.json) |
| RECOMP-04 | Phase 47.5 | **Complete** (decision `or-retroactive` + gambling answered: 47.5-C-DECISION.md; both engines in one commit `f817ec5`; deployed and read back out of the RUNNING instance: 47.5-C-DECISION.md § Deploy record) |
| COVER-01 | Phase 47 + 48 | Phase 48's share **complete** — live-derived 5-record population, all 5 now carry a real `lv_org_type` or the D-03 `unknown`+reason marker; `48-RUN-REPORT.md` § Per-record outcomes. Phase 47's 17 records tracked separately; joint closure not asserted here. |
| COVER-02 | Phase 47 + 48 | Phase 48's share **complete** — estimate (`48-COST-ESTIMATE.md`) reported against actuals line by line, refuse-rather-than-truncate proven by test; `48-RUN-REPORT.md` § Cost actuals and § Window accounting. One disclosed gap: Anthropic-dollar spend is an unmeasured floor, not a measured actual. Joint closure not asserted here. |
| RESCORE-01 | Phase 49 | **Complete** (all 4 declaring plans finished — 49-01: `docs/OPERATOR-RESCORE.md` runbook + `scripts/rescore_population.py --plan` mode + `test_rubric_change_guard.py`; 49-02: `scripts/backfill_seed_company_scores.py`'s consuming write path; 49-03: n8n research-prompt org-type-definitions fix built offline; 49-04: that fix deployed, bounced, and proven live — `49-DEPLOY-PROOF.md`) |
| RESCORE-02 | Phase 49 | **Complete** (66/66 companies re-scored under the current rubric in one W1 window; `49-P2-SNAPSHOT.json`/`49-P3-SNAPSHOT.json`) |
| RESCORE-03 | Phase 49 | **Complete** (P2/P3 tier distributions committed and compared against the pre-registered Phase 46 forecast, matched exactly: 14 rows C→B, all `individual_club_team`; `49-W1-ARM-RECORD.md`) |
| TIER-01 | Phase 50 | **Blocked (residual, non-veto defect)** — Plan 06's re-run of D-07's gate (`50-TIER-PARITY-EVIDENCE.md`'s 2026-08-14 post-correction section) confirms the veto-guard defect (`WINDOWS.md` id 13) is FIXED: all 6 real `lv_anti_icp_flag=true` scored companies now correctly derive `D` (Simtech LED settled to `D` under a polled proof, D-22). The gate now reads 61 match / 4 expected_mismatch / 1 defect — exactly the pre-registered expectation. The 1 residual defect (Coffs Harbour Racing Club, `14752488879`, `WINDOWS.md` id 14) is the OPPOSITE polarity of the veto-guard class: the derived tier is CORRECT (`C`) and the stale `lv_icp_tier` enum is wrong (`Unscored`) — evidence FOR the derived property, not against it, and a pre-existing WF1-staleness case unrelated to this fix. Not marked complete: "verified against real records ... reproduces WF1's live ladder exactly" is not literally true while any gate row outside the 4 pre-registered ids is a `defect`; whether to extend the gate's exception list to absorb this class is Plan 04/05's operator decision, not taken here (`KNOWN_STUCK_IDS` unchanged, per this plan's own prohibition). |
| TIER-02 | Phase 50 | **Complete, correction of record superseding the original evidence** — D-21 (`50-CONTEXT.md`'s 2026-08-14 amendment) reversed D-04: Plan 01's original null probe read back immediately after create and mistook an unsettled calculated property for null-propagation (a race, not a finding — D-22). Re-tested with polling, a bare reference to a null `lv_icp_fit_score` fell through to its else branch normally. The shipped formula is now D-03's originally-preferred UNCOALESCED variant; the ~646-record blank→`"Unscored"` flip this row previously described as settled fact is itself now REVERSED (un-flipped back to blank), live-confirmed by a ≥3-minute poll on a named never-scored company (`50-TIER-PARITY-EVIDENCE.md`'s post-correction census, `50-MIRROR-BACKFILL.md`). `50-NULL-PROBE.json` is unedited and stays historical evidence of what was believed at the time. |
| TIER-03 | Phase 50 | **Complete (enumeration half)** — `50-DEPENDENTS-SWEEP.md`: scripted sweep (0 lists, 10 flows scanned, 5 findings all on WF1 itself, no external dependent) plus the operator-attested, dated manual check confirming saved views migrated off `lv_icp_tier` (2026-08-14). **Disclosed residual, not closed by this plan:** reports/dashboards left explicitly UNCONFIRMED, carried forward to Plan 04/05, which own the "disposition decided explicitly" and "armed, capped write window" clauses of this requirement's text. |

*Phase column filled by the roadmapper.*

**COVER-01 / COVER-02 split (D-02, 2026-08-11):** Phase 47 satisfies both requirements for its 17
records; Phase 48 satisfies both for the 1 remaining record. Neither phase may be closed claiming
full coverage of COVER-01 or COVER-02 on its own.
