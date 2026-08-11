# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** (shipped 2026-07-29)
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see Ledger gaps below)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` (shipped 2026-08-04)
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 (shipped 2026-08-08)
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 (shipped 2026-08-11)
- 📋 **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–49 (roadmapped, not started)

## Phases

### 📋 v0.9 ICP Rubric Calibration & Veto Remediation (Phases 46–49)

- [ ] **Phase 46: Rubric Decision, Simulation & Engine Parity** - Decide the org-type weights (`individual_club_team`, `regulator`, and the `gambling_operator` deduction) with evidence, simulate re-tiering with zero record writes, prove any change lands identically in all three scoring engines, and update every doc that prints the superseded rubric — before either downstream write phase runs
- [ ] **Phase 47: Veto Remediation** - Clear the 17 false non-ANZ vetoes under the settled rubric, inside a deliberately armed and capped write window, verifiable from HubSpot alone
- [ ] **Phase 48: Enrichment Coverage** - Fill or document `lv_org_type` for the 18 never-enriched companies, under a pre-estimated and budget-refusing armed write window
- [ ] **Phase 49: Re-score Strategy & Reporting** - Define and (if triggered) execute the budget-bounded full-population re-score procedure, and report the milestone's net tier-distribution effect in plain language

<details>
<summary>✅ v0.8 Execution Budget Safety (Phases 44–45) — SHIPPED 2026-08-11</summary>

- [x] Phase 44: SJ-3 Dispatch Gate, Drain & Cap (3/3 plans) — completed 2026-08-10, verified
- [x] Phase 45: Burn-Rate Alarm (3/3 plans) — completed 2026-08-10, verified

Full detail: `milestones/v0.8-ROADMAP.md` · Phase artifacts: `milestones/v0.8-phases/`
Requirements: `milestones/v0.8-REQUIREMENTS.md` (15/15 complete)

</details>

<details>
<summary>✅ Earlier milestones — archived</summary>

Phase-level detail for shipped milestones lives in the archives rather than here, to keep this
file constant-size:

| Milestone | Roadmap archive | Phase artifacts |
|---|---|---|
| v0.8 Execution Budget Safety | `milestones/v0.8-ROADMAP.md` | `milestones/v0.8-phases/` |
| v0.7 HubSpot Scoring Engine Remediation | `milestones/v0.7-ROADMAP.md` | `milestones/v0.7-phases/` |
| v0.4 Reachability & Verification Debt | `milestones/v0.4-ROADMAP.md` | `milestones/v0.4-phases/` |
| v0.3 | `milestones/v0.3-ROADMAP.md` | `milestones/v0.3-phases/` |

</details>

## Phase Details

### Phase 46: Rubric Decision, Simulation & Engine Parity

**Goal**: Decide the org-type weight questions with evidence, and prove that any change lands
identically in every scoring engine — before either the 17 false-veto records (Phase 47) or the
18 uncovered records (Phase 48) are touched. Deciding weights once, first, costs less than the
alternative: re-scoring the 17 veto records under the old rubric and then again under a changed
one. This phase writes nothing to a HubSpot **record** — the simulation reads current `lv_*`
inputs only, and any engine deploy is a workflow artifact change, not a record write.

**Scope amended 2026-08-11** (during `/gsd-discuss-phase 46`, operator-directed — see
`46-CONTEXT.md` D-01…D-03, D-13): the decision covers **three** org-type levers rather than one
(`individual_club_team`, `regulator`, and removal of the `gambling_operator` deduction), the
parity surface is **three** engines rather than two (the HubSpot flow `4626124224-org-type-score`
was found to be a third native scoring engine), and **documentation sync is in scope** so no doc
still prints the superseded rubric after the change ships.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: RUBRIC-01, RUBRIC-02, RUBRIC-03

**Success Criteria** (what must be TRUE):

  1. A written decision on each changed org-type weight exists, citing specific closed-deal
     evidence from `icp-scoring.md` — and where the decision *overrides* that evidence on GTM
     grounds, the override and its reasoning are recorded rather than the evidence being rewritten.
     Confirming a current weight unchanged is an equally valid, evidenced outcome.

  2. Operator can view a re-tier simulation of the 66 currently-scored companies under proposed
     weights, computed from current `lv_*` inputs, that writes nothing to HubSpot. Records
     affected by the 17 false vetoes or the 18 blank `lv_org_type` values are annotated so they
     are not misread as genuine outcomes.

  3. The parity harness (`tests/test_scoring_parity.py`, `scripts/run_scoring_parity.py`) passes
     against the decided weights in all three engines — `config/icp_scoring.yaml` (Python oracle),
     the JS port compiled into `n8n/wf_enrichment_cloud.json`, and the HubSpot flow
     `config/hubspot_flows/4626124224-org-type-score.*.json` (guarded by
     `tests/test_flow_rubric_conformance.py`) — trivially if a weight is unchanged, substantively
     if it changed.

  4. If a weight changed, the new value reached the live workflow only via
     `build_cloud_workflows.py` → deploy → bounce, and a read-back of the running (not merely
     stored) workflow content confirms the new weight is what actually executes.

  5. No live document still prints a superseded weight or deduction: `docs/business/icp-scoring.md`,
     `CLAUDE.md` §10, `.planning/intel/*`, and `docs/WEB-RESEARCH-SPEC.md` agree with
     `config/icp_scoring.yaml`. Archived milestone artifacts under `.planning/milestones/` are
     deliberately left verbatim as historical record.

**Amendment (2026-08-11, Phase 46 Plan 05 — `46-ENGINE-INVENTORY.md`, `46-DECISION.md`):**
The "three engines" premise in the Scope-amended paragraph above and in success criterion 3 is
corrected: an exhaustive word-boundary-adjacent-to-number grep of the n8n leg
(`n8n/wf_enrichment_cloud.json`, `scripts/build_cloud_workflows.py`) found **no**
org-type-keyed numeric table there. Only **two** engines carry `base_score.org_type` weights —
`config/icp_scoring.yaml` (Python oracle) and the HubSpot flow `4626124224` ("Update Score
Based on Org Type"). See `46-ENGINE-INVENTORY.md` for the full evidence and
`tests/test_n8n_org_type_absence.py` for the permanent guard against regression.

- **Criterion 4 status: NOT TRIGGERED, not satisfied.** No org-type or gambling-deduction
  weight reaches the live n8n workflow at all, so there is no build to deploy and no running
  content to bounce or read back this phase. Re-triggers if a future phase touches categorical
  promotion logic, taxonomy membership, evidence gating, or merge policy in the n8n leg (the
  four triggers `46-ENGINE-INVENTORY.md` names).

- **Criterion 3 status: satisfied at engine level; the live record-level parity sweep is
  expected red by design.** The offline parity harness, `tests/test_flow_rubric_conformance.py`,
  and Plan 04's running-content read-back all agree with the rubric of record for both live
  engines. `scripts/run_scoring_parity.py`'s live-population sweep is red from the moment
  Plan 04 committed the new weights (commit `caae5d6`, 2026-08-11) until **Phase 49** executes
  the full-population re-score and closes the window — by design it compares each record's
  old-weight live score against the new-weight oracle, per `46-DECISION.md`'s "Parity red
  window" section. This is expected and self-inflicted, not a new defect.

**Plans**: 5/5 plans executed

Plans:

- [x] 46-01-PLAN.md — Reconcile the engine count, and prove the simulation machinery end-to-end
      on one record before any weight is committed

- [x] 46-02-PLAN.md — Simulate the full live scored population under the proposed weights and
      commit the per-company before/after report (zero HubSpot writes)

- [x] 46-03-PLAN.md — Write `46-DECISION.md` and take operator sign-off (blocking gate on every
      engine write below)

- [x] 46-04-PLAN.md — Commit the signed-off weights to `config/icp_scoring.yaml` and land them
      identically in the HubSpot flows, with a running-content read-back

- [x] 46-05-PLAN.md — Sync every live document to the new rubric and record the engine-count
      amendment

---

### Phase 47: Veto Remediation

**Goal**: Clear the 17 companies carrying a false non-ANZ veto, re-scored under the rubric
Phase 46 settled — once, not twice — inside a deliberately bounded write window, and
verifiable from HubSpot alone with no script. Excludes the 3 companies verified correct on
2026-08-11 — Entain (`10024564084`), Gravity Media (`15860277364`), Ironman (`17317184159`) —
which carry genuine non-ANZ regions and must not be swept up in this re-score. Before opening
the write window, check whether any of the 17 also fall inside Phase 48's 18-company no-`lv_org_type`
set; an overlapping record should get both fixes in one armed touch rather than two separate
write windows.

**Depends on**: Phase 46 (rubric must be settled before this re-score runs, so it runs once)

**Requirements**: VETO-01, VETO-02, VETO-03

**Success Criteria** (what must be TRUE):

  1. Each of the 17 flagged companies (excluding the 3 confirmed-correct IDs above) has been
     re-scored under the Phase-46-settled rubric, and its `lv_anti_icp_flag` / `lv_anti_icp_reason`
     reflect the corrected region data.

  2. The re-score ran inside a write window that was deliberately armed with a record-count cap,
     then disarmed, with the disarmed state read back and confirmed afterward.

  3. Operator can search HubSpot alone — no scripts — for "non-ANZ veto reason with a blank
     `lv_country_region_normalized`" and get zero results.

**Plans**: TBD

---

### Phase 48: Enrichment Coverage

**Goal**: Every scored company either has a real `lv_org_type` or a documented, distinguishable
reason it can't get one, spent through a cost-estimated, budget-refusing, deliberately armed
write window. This is a separate, larger budget event than Phase 47's cheap recompute — a full
provider waterfall per record, not a rescore of existing data — so it is a separable spend
decision the operator approves on its own terms. Before opening the write window, check the
overlap noted in Phase 47: a record needing both a region fix and org-type enrichment should be
touched once.

**Depends on**: Phase 46 (settled rubric so post-enrichment scores are computed correctly)

**Requirements**: COVER-01, COVER-02

**Success Criteria** (what must be TRUE):

  1. Each of the 18 companies has a non-blank `lv_org_type`, or is marked un-enrichable with a
     stated reason — distinguishable from a company that was never attempted.

  2. Before the enrichment run, operator sees an estimated execution and provider-credit cost
     against the 2,500/month n8n allowance and the current Lusha balance.

  3. A run whose estimated cost would exceed either budget is refused outright, never truncated
     silently mid-run.

  4. The enrichment writes happened inside a deliberately armed, record-count-capped write
     window that was disarmed and read back afterward, and the actual cost is reported against
     the pre-run estimate.

**Plans**: TBD

---

### Phase 49: Re-score Strategy & Reporting

**Goal**: A future rubric-triggered full-population re-score has a defined, budget-bounded
procedure the operator can trust before invoking it, and the milestone's net effect on the
target list is visible in plain language. This holds in both branches of Phase 46's decision:
if the weight changed, this phase's full-66 pass necessarily re-touches the 17 records Phase 47
already wrote — roughly 17 redundant executions, accepted deliberately because it let the known
live veto bug clear one phase earlier rather than waiting on the weight decision. If the weight
did not change, no full re-score is owed and this phase proves the procedure without spending it.

**Depends on**: Phase 46, Phase 47, Phase 48

**Requirements**: RESCORE-01, RESCORE-02, RESCORE-03

**Success Criteria** (what must be TRUE):

  1. Operator can see, before any future rubric change is committed, exactly which records would
     be re-scored, in what chunk size, and under what write window — a documented, budget-bounded
     plan, not an ad-hoc sweep.

  2. Because no `lv_icp_scoring_version` property exists, the plan explicitly re-scores the
     entire 66-company scored population on any rubric change, and states the execution cost up
     front rather than discovering it mid-run.

  3. If Phase 46 changed a weight, the full-population re-score executed under this defined
     procedure; if it didn't, the procedure is proven (e.g. dry-run) without being spent.

  4. Operator receives a plain-language before/after tier-distribution comparison covering this
     milestone's re-scoring activity as a whole (veto clear, coverage enrichment, and any
     weight-driven full re-score).

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 44. SJ-3 Dispatch Gate, Drain & Cap | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 45. Burn-Rate Alarm | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 46. Rubric Decision, Simulation & Engine Parity | v0.9 | 5/5 | In Progress|  |
| 47. Veto Remediation | v0.9 | 0/? | Not started | - |
| 48. Enrichment Coverage | v0.9 | 0/? | Not started | - |
| 49. Re-score Strategy & Reporting | v0.9 | 0/? | Not started | - |

## Ledger gaps (known)

- **v0.5 has no MILESTONES.md entry and no roadmap/phase archive.** Found during the v0.8 close
  on 2026-08-11: the ledger jumps v0.4 → v0.6 and `milestones/` holds no `v0.5-*` files, yet
  `v0.5.0` exists as a git release tag. v0.5 appears to have shipped without being run through
  `/gsd-complete-milestone`. Not reconstructed at v0.8 close (out of scope) — recorded so it is
  not mistaken for a numbering skip.

- **v0.6 has a MILESTONES.md entry but no roadmap/phase archive** under `milestones/`. Same
  likely cause, lesser impact: the narrative record survives, the phase artifacts were never
  archived under a `v0.6-*` label.
