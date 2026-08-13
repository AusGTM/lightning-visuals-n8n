# Phase 50: Derived Tier Property - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-13
**Phase:** 50-derived-tier-property
**Areas discussed:** Phase existence & milestone placement, Scope lift (gate), Null semantics, Migration shape, Portal dependents, Proof bar

---

## Phase existence & milestone placement

Phase 50 did not exist in ROADMAP.md when `/gsd-discuss-phase 50` was invoked —
`init.phase-op 50` returned `phase_found: false`. The roadmap ended at Phase 49 with v0.9 marked
complete and its close pending.

| Option | Description | Selected |
|--------|-------------|----------|
| Add tier-derivation as Phase 50, then discuss | Write the entry from the tier-derivation spike, then run the discussion against it | ✓ |
| Close v0.9 first, then new milestone | `/gsd-complete-milestone` then `/gsd-new-milestone`; cleaner ledger, discussion waits | |
| Phase 50 is something else | Operator supplies a different goal | |

| Option | Description | Selected |
|--------|-------------|----------|
| New v1.0 | Tier derivation is new scope; keeps v0.9's close honest | |
| Extend v0.9 | The 4 stuck records are v0.9 debt Phase 49 explicitly deferred | ✓ |
| Decide at close | Add unassigned, resolve at `/gsd-complete-milestone` | |

**User's choice:** Add as Phase 50; extend v0.9.
**Notes:** Roadmap and requirements amended and committed as `4173da0` before the discussion
proper began, so the scope amendment is traceable independently of this discussion's output.

---

## Scope lift (blocking gate)

Raised before any discussion question: `.planning/REQUIREMENTS.md` § Out of Scope bans
"New HubSpot properties of any kind" (operator decision 2026-08-11), and Phase 50 cannot exist
without exactly one — enumerations cannot be calculated properties.

| Option | Description | Selected |
|--------|-------------|----------|
| Lift for one derived-tier property only | Scoped, dated, additive amendment in the COVER-01/COVER-02 style | ✓ |
| Lift the ban generally | Repeals the decision outright; reopens `lv_icp_scoring_version` and the §5.3 fields | |
| Keep the ban — don't add Phase 50 | Tier derivation goes to v1.0; the 4 stuck records stay disclosed as unmet truth | |

**User's choice:** Lift for one derived-tier property only.
**Notes:** Amendment written into REQUIREMENTS.md § Out of Scope citing this session.
`lv_icp_scoring_version` and the three §5.3 fields explicitly remain excluded.

---

## Null semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Uncoalesced — never-scored stay blank | Preserves today's behaviour exactly; zero visible change beyond the 4 stuck records | ✓ |
| `coalesce(score, -1)` — never-scored read "Unscored" | ~646 companies flip blank→"Unscored"; arguably more honest, but a mass visible change | |
| You decide | Claude picks from what the live null test shows | |

| Option (fallback if uncoalesced proves impossible) | Description | Selected |
|--------|-------------|----------|
| Take coalesce — accept the ~646 flip | Disclose as a deliberate consequence, Phase 49 unmet-truth style | ✓ |
| Stop and re-decide at a checkpoint | Round-trip mid-phase with real numbers in hand | |
| Abandon derivation if blank can't be preserved | Close as a recorded negative result | |

| Option (gating of the live null test) | Description | Selected |
|--------|-------------|----------|
| Fresh two-key-gated script in `scripts/` | Paired `DRY_RUN=false` gate; closes Phase 49 code review CR-01 | ✓ |
| Throwaway again, outside `scripts/` | Same posture as the spike; repeats the shape CR-01 objected to | |
| You decide | | |

**User's choice:** Uncoalesced preferred; coalesce as the forced fallback with the flip disclosed;
permanent two-key-gated script.
**Notes:** The runtime null question is the one thing the spike could not answer from syntax —
Phase 41 proved HubSpot blanks a calculated property when a referenced term is null *for a bare
sum*; whether that extends into an untaken branch is unknown.

---

## Migration shape

| Option (old enum) | Description | Selected |
|--------|-------------|----------|
| Keep both, derived is truth, old frozen | Nothing breaks day one; two tier fields visible until later cleanup | |
| Keep both, old kept in sync | Preserves dependents but reintroduces the event-dependent writer this phase removes | |
| Retire the old property in this phase | Cleanest end state; highest risk since dependents are repo-invisible | ✓ |

| Option (WF1 `4625147345`) | Description | Selected |
|--------|-------------|----------|
| Switch off, keep the definition | Off-but-present is a one-action rollback; archived JSON already exists | ✓ |
| Leave running as a backstop | Re-admits the stale-write failure mode | |
| Delete it | No rollback path short of rebuilding from archive | |

| Option (6th label `Needs Review`, PARITY-01) | Description | Selected |
|--------|-------------|----------|
| No — mirror WF1's 5-value ladder exactly | Tier changes stay attributable to the mechanism, not a smuggled rubric change | ✓ |
| Yes — close PARITY-01 while we're here | Structurally free on a string property, but confounds two changes | |
| You decide | | |

| Option (cutover for the 4 stuck records) | Description | Selected |
|--------|-------------|----------|
| As a side effect, no record write at all | Score already correct at 45; derived tier lands them on B with no event | ✓ |
| Derived first, then a corrective write to the old enum | Needs an armed window; only coherent if the old enum stays alive | |
| You decide | | |

**User's choice:** Retire in this phase; WF1 off with definition kept; 5-value ladder only;
4 records fixed as a side effect.
**Notes:** Operator's WF1 answer carried freetext — *"defer full cleanup until new property passes
evaluation"* — which pulled against "retire in this phase". Reconciled below rather than passed
downstream ambiguous.

### Reconciliation pass

| Option (is retirement gated?) | Description | Selected |
|--------|-------------|----------|
| Yes — retirement is the last gated step | Ship, prove, migrate, then archive; all inside Phase 50 | ✓ |
| Yes, and retirement may slip out of Phase 50 | Safer; duplicate-field clutter persists past the milestone | |
| No — retire it regardless | Fastest clean state; commits to an archive before the replacement proves out | |

| Option (what is the gate?) | Description | Selected |
|--------|-------------|----------|
| Derived matches WF1 on all 66 scored, zero mismatches | Except the 4 stuck records, which must differ; provable from HubSpot alone | ✓ |
| That, plus a settling period before retirement | Pushes retirement out of Phase 50 by construction | |
| You decide | | |

| Option (blocked dependent) | Description | Selected |
|--------|-------------|----------|
| Dependent wins — old property stays, disclosed | Phase 49 unmet-truth posture | |
| Retirement wins — the dependent gets rebuilt or dropped | Breaks something a human uses without their say | |
| Stop and bring it to me | Checkpoint on the real case rather than a rule decided in advance | ✓ |

---

## Portal dependents

| Option (known dependents, multi-select) | Description | Selected |
|--------|-------------|----------|
| Sales lists / saved views filtered by tier | The A/B/C/D prioritisation surface | ✓ |
| Reports or dashboards grouping by tier | Portal-native, invisible to any repo grep | ✓ |
| Other HubSpot workflows reading tier | Enumerable via the flows API | |
| Nothing I know of — enumerate from scratch | | |

| Option (how to enumerate) | Description | Selected |
|--------|-------------|----------|
| Read-only API sweep, committed as an artifact | Repeatable, re-runnable right before cutover | ✓ |
| You walk the portal UI and tell me | Catches what the API cannot see; not re-runnable | |
| Both — API sweep, then you confirm the gaps | Most complete; costs operator clicking | |

| Option (naming) | Description | Selected |
|--------|-------------|----------|
| Distinct name now, no rename later | Cheap; survivor named "derived" reads oddly | |
| Distinct name now, rename to `lv_icp_tier` after retirement | Cleanest final name; two moves per reference | ✓ |
| Neutral name that reads fine either way | No rename needed | |

**User's choice:** Lists and reports known; scripted API sweep; rename intent.
**Notes:** Rename feasibility challenged rather than accepted — HubSpot internal names are not
editable after creation and archived names are generally not reusable. Fallback taken below.

### Naming feasibility fallback

| Option (if rename proves impossible) | Description | Selected |
|--------|-------------|----------|
| Keep the distinct name permanently | Every repo reference moves once instead of twice | ✓ |
| Change the label only, keep the internal name | Labels ARE editable; sales sees "ICP Tier" | |
| Don't retire the old property — keep the canonical name occupied | Contradicts the retirement decision | |

| Option (name to create under) | Description | Selected |
|--------|-------------|----------|
| `lv_icp_tier_calc` | Reads correctly as a permanent survivor; matches the spike's disposables | |
| `lv_icp_tier_derived` | More explicit about mechanism; awkward as a survivor name | ✓ |
| You decide | | |

**Notes:** Operator chose `lv_icp_tier_derived` after being shown the survivor-name argument for
`lv_icp_tier_calc`. Recorded as an explicit override, not an oversight.

---

## Proof bar

| Option (write windows) | Description | Selected |
|--------|-------------|----------|
| Declare zero company write windows | A calculated property computes itself; no company PATCH needed | ✓ |
| Declare one, in reserve | Phase 47 declared 1 and spent 5, disclosed | |
| You decide | | |

| Option (regression protection, multi-select) | Description | Selected |
|--------|-------------|----------|
| Pin the formula against the Python ladder | Shape of Phase 49's `test_rubric_change_guard.py` | ✓ |
| Update `scripts/check_schema_drift.py` | Its enum pin and PARITY-01 divergence go stale on archive | ✓ |
| Update `config/hubspot_properties.yaml` + flow archives | Or the repo's record of the portal goes wrong | ✓ |
| Parity check across all 66, committed as an artifact | Makes the gate decision auditable after the fact | ✓ |

| Option (rollback after WF1 is off) | Description | Selected |
|--------|-------------|----------|
| Re-enable WF1 + a forced re-enrolment trigger | Re-enabling alone re-grades nothing — that IS the bug | ✓ |
| Re-enable WF1 and accept slow convergence | Leaves stale tiers for an unbounded period | |
| Don't switch WF1 off until retirement | Both writers coexist longer | |

| Option (operator reporting) | Description | Selected |
|--------|-------------|----------|
| Before/after tier census, Phase 49 format | Expected result pre-registered: identical except 4 records C→B | ✓ |
| That, plus a published private Artifact | Continuous narrative for the v0.9 close | |
| Run report only | Lighter; loses the visual before/after | |

**User's choice:** Zero windows; all four regression items; rollback includes forced re-enrolment;
census report only.

---

## Claude's Discretion

None. Every question was answered with an explicit selection — no "You decide" option was taken
in any area. Where judgement remains, it is bounded by a named fallback (null-semantics fallback,
naming fallback) rather than delegated.

## Deferred Ideas

- **PARITY-01 / the 6th `Needs Review` tier label** — becomes structurally free once the tier is a
  string property, since the enum-option addition that blocked it in Phase 40 no longer applies.
  Not taken here to avoid confounding a mechanism change with a rubric change.
- **`lv_icp_scoring_version`** — remains out of scope; the lift is one property only.
- **The three CLAUDE.md §5.3 fields** — remain deferred to v1.0 alongside EVID-01..03.
- **Three pending todos reviewed, none folded** — all matched at 0.6 on stopwords only
  (`claude`, `operator`, `run`, `records`); none touches tiering.
