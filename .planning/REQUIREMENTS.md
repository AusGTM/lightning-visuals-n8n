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

- [ ] **VETO-01**: All 17 companies carrying a false non-ANZ veto are re-scored under the fixed
      rubric, and their `lv_anti_icp_flag` / `lv_anti_icp_reason` reflect that re-score.
- [ ] **VETO-02**: The clearing run happens inside a deliberately-opened armed write window with
      a record-count cap, and the window is disarmed and read back as disarmed afterward.
- [ ] **VETO-03**: Operator can confirm from HubSpot alone — no scripts — that no company remains
      with a non-ANZ veto reason and a blank `lv_country_region_normalized`.

### Enrichment Coverage (COVER)

- [ ] **COVER-01**: The 18 scored companies with no `lv_org_type` are either enriched to a real
      org type, or individually recorded as un-enrichable with a stated reason. An unresolved
      company must be distinguishable from one never attempted.
- [ ] **COVER-02**: The execution and provider cost of that enrichment is estimated before the
      run and reported after, against the 2,500/month n8n allowance and the current Lusha
      balance. A run that would exceed either is refused, not truncated silently.

### Re-score Strategy (RESCORE)

- [ ] **RESCORE-01**: A rubric change triggers a defined, budget-bounded re-score of the affected
      population rather than an ad-hoc sweep — including which records, in what chunk size, under
      which write window.
- [ ] **RESCORE-02**: Because rubric-version segmentation is impossible without
      `lv_icp_scoring_version` (operator decision 2026-08-11: no new properties), any rubric
      change re-scores the ENTIRE scored population. The plan states that execution cost up front
      rather than discovering it mid-run.
- [ ] **RESCORE-03**: Operator is told, in plain language, what the tier distribution was before
      and after any re-score — so a rubric change's effect on the target list is visible rather
      than inferred.

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
| VETO-01 | Phase 47 | Not started |
| VETO-02 | Phase 47 | Not started |
| VETO-03 | Phase 47 | Not started |
| COVER-01 | Phase 48 | Not started |
| COVER-02 | Phase 48 | Not started |
| RESCORE-01 | Phase 49 | Not started |
| RESCORE-02 | Phase 49 | Not started |
| RESCORE-03 | Phase 49 | Not started |

*Phase column filled by the roadmapper.*
