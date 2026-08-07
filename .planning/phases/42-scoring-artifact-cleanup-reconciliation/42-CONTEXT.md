# Phase 42: Scoring Artifact Cleanup & Reconciliation - Context

**Gathered:** 2026-08-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Archive (never delete) the scoring artifacts genuinely orphaned by Phase 40's fix-in-place
remediation, and bring `config/hubspot_properties.yaml` into provable zero-drift agreement
with the live portal for every `lv_*` and scoring property the system depends on. Covers
CLEAN-01 only. No rubric changes, no engine changes, no data import (Phase 41), no pipeline
hygiene defects (Phase 43). Nothing that stops the repaired scoring engine from firing.

**Two facts established during discussion that reshape this phase:**

1. **ROADMAP SC1 is superseded by the path decision.** It names `org_type_score`,
   `geography_score`, `annual_revenue_score`, and the calculated `lv_icp_fit_score`
   property as artifacts to archive. Those were written when the lead-scoring-tool rebuild
   was the presumed path. `39-DECISION.md` chose fix-in-place, and Phase 40 repaired and
   *kept* exactly those artifacts — they are the live engine. Archiving them would break
   scoring. See D-01.

2. **`config/hubspot_properties.yaml` is a partial manifest, not a schema mirror.** It
   holds 22 company + 17 contact properties and does not contain `lv_org_type`,
   `lv_produces_content`, `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`,
   `lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`,
   `lv_icp_scoring_version`, `lv_named_account_priority`, or any of the five `*_score`
   components. "Zero drift" is undefined against a partial file. See D-04.

</domain>

<decisions>
## Implementation Decisions

### Superseded Inventory
- **D-01:** ROADMAP SC1's archive list is **reinterpreted, and the reinterpretation is
  recorded**. Phase 42 archives only what is actually orphaned under fix-in-place; the five
  live component-score properties, the calculated `lv_icp_fit_score`, and the four repaired
  flows are explicitly NOT archived. CONTEXT.md carries the supersession rationale so the
  divergence from the roadmap text is traceable rather than silent. ROADMAP.md itself is
  not edited as a prerequisite. — **Reversibility:** reversible — the reinterpretation is a
  written rule; no artifact is destroyed by recording it.
- **D-02:** The orphan list is derived from a **live-portal diff**: enumerate live company
  properties and automation flows via API, cross-reference against what the repaired engine
  and the n8n pipeline actually read/write plus `config/hubspot_flows/*.after.json`.
  Anything referenced by nothing is a candidate. Repo-only derivation is rejected — it
  would miss portal-only leftovers (Phase 39 probe artifacts, pre-remediation flow copies).
- **D-03:** Approval gate: **archive uncontested, ask on doubt**. Clear-cut orphans (items
  with zero references and an obvious provenance, e.g. Phase 39 probe leftovers) are
  archived without pausing; ambiguous items are surfaced to the operator with the evidence
  for each before any action.

### Reconcile Direction
- **D-04:** "Reconciles clean / zero drift" scope = **full mirror of every `lv_*` and
  scoring property** the system depends on. The yaml grows to cover the currently-missing
  set (`lv_org_type`, `lv_produces_content`, `lv_icp_fit_score`, `lv_icp_tier`,
  `lv_anti_icp_flag`, `lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`,
  `lv_icp_scoring_version`, `lv_named_account_priority`, `org_type_score`,
  `geography_score`, `annual_revenue_score`, `produces_content_score`, `gambling_score`).
  HubSpot-native fields (`name`, `domain`, `country`, `annualrevenue`, …) stay out of scope.
- **D-05:** Drift direction: **live wins, yaml catches up**. The portal is reality —
  Phase 40 created and repaired properties directly. Reconciliation performs **no portal
  mutation**; it updates the config file to match. (Archival under D-01/D-02/D-03 is the
  only portal-mutating work in this phase, and it is a separate, gated activity.)
  — **Reversibility:** reversible — yaml is version-controlled; regenerating it differently
  later costs nothing.
- **D-06:** Reconciliation depth: **existence + enum option values**. Property presence
  and exact enum `value` lists must match (this is the defect class that made `lv_icp_tier`
  reject `Unscored`/`Needs Review`). Labels, `displayOrder`, and descriptions are cosmetic —
  reported in the drift output, not treated as failures.

### Archive Semantics
- **D-07:** HubSpot properties archive via **HubSpot's soft-archive** (`DELETE
  /crm/v3/properties/{objectType}/{name}`, which archives rather than destroys — data
  retained, property restorable). The property definition is snapshotted to the repo before
  the call. — **Reversibility:** costly — restoring means recreating the property and
  re-associating it in views/flows; the snapshot makes it possible, not free.
- **D-08:** Orphaned flows: **fetch JSON to repo, then deactivate** — `GET
  /automation/v4/flows/{id}` archived under the dated archive dir, then the flow is
  disabled. Not deleted. Stops it firing, keeps the definition in git, restore is a
  re-enable.
- **D-09:** Locations: schema snapshots keep `scripts/snapshot_hubspot_schema.py`'s
  existing destination and naming (unchanged). Archived flow and property definitions land
  in a **dated archive directory under `config/hubspot_flows/`**, consistent with the
  existing `{id}-{name}.before.json` / `.after.json` convention.

### Reconcile Tooling
- **D-10:** Form: a **standing drift-check script under `scripts/`** — read-only, compares
  yaml against live for the D-04 property set at D-06 depth, emits a JSON report and a
  meaningful exit code. Re-runnable, so "zero drift" stays provable after this phase rather
  than decaying into a one-time claim. Mirrors Phase 40's parity-harness pattern. A new
  script, not a `--reconcile` mode bolted onto the snapshot tool.
- **D-11:** Execution convention: **Claude executes directly, snapshot-first** — same
  envelope as Phase 40 D-08. `scripts/snapshot_hubspot_schema.py` runs before any mutation
  (SC1's literal, still-valid requirement); archival calls run in-session. Justified
  because every archival action here is reversible (soft-archive, JSON preserved in git).
  No operator arming gate for this phase's mutations.
- **D-12:** Cadence: **on-demand and pre/post schema change**, same tier as the parity full
  run. The drift checker is deliberately NOT added to the unattended sweep — schema drifts
  rarely and the noise is not worth the sweep budget.

### Discretionary Exception to D-01 (recorded 2026-08-07)

- **X-01:** D-01 says ROADMAP.md "is not edited as a prerequisite." The planner nonetheless
  added a short "Note on SC1" block to `.planning/ROADMAP.md` (commit `411b971`) warning that
  SC1's archive list is superseded by the fix-in-place path. This is recorded here as a
  **deliberate discretionary exception, not an unflagged deviation.** Rationale: D-01's intent
  was that no roadmap edit be *required before planning could proceed* — not that the roadmap
  must stay silent about a criterion which, read literally, instructs an executor to disable
  the live scoring engine. The note is additive, cites 42-CONTEXT.md D-01, and mitigates the
  same risk F1 exists to mitigate. Revert it if the roadmap should stay untouched; nothing in
  the plans depends on it.

### Claude's Discretion
- Exact archive directory name/date format under `config/hubspot_flows/`.
- Drift-report JSON shape and exit-code semantics.
- Reference-detection method for D-02 (how "referenced by nothing" is computed across flow
  JSON, n8n code, Python source, and config).
- Which cosmetic drift classes appear in the report body vs a summary line.
- Ordering of archive operations within the gated pass.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Path Decision (why SC1 is reinterpreted)
- `.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md` — the sealed
  fix-in-place verdict; the reason the roadmap's archive list inverted.
- `.planning/phases/40-scoring-engine-remediation-notes/40-CONTEXT.md` — D-05 (flow JSON in
  repo via API), D-06 (component architecture kept: five `*_score` mappers + calculated sum
  + tier flow), D-08 (direct-execution convention D-11 inherits).

### Live Engine Inventory (what must NOT be archived)
- `config/hubspot_flows/` — `4626124224-org-type-score`, `4626722240-geography-score`,
  `4626722237-annual-revenue-score`, `4625147345-wf1-set-icp-tier` (`.before`/`.after`),
  plus `produces-content-score.after.json`, `gambling-score.after.json`,
  `lv_icp_fit_score-property.{before,after}.json`,
  `lv_icp_tier-property.{before,after}.json`. The `.after` files are the current live
  definitions.
- `.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` — portal gotchas
  and flow-PUT behavior recorded during remediation.

### Reconciliation Targets
- `config/hubspot_properties.yaml` — the partial manifest D-04 expands (22 companies /
  17 contacts today).
- `scripts/snapshot_hubspot_schema.py` — SC1's mandatory pre-archival snapshot; already
  supports `--label` and a write-gated `--probe`. Its output destination/naming is
  unchanged by D-09.
- `config/icp_scoring.yaml` — enum values of record; D-06's enum comparison must agree with
  the rubric (`lv_org_type`, `lv_content_type`, `lv_revenue_band`, `lv_employee_band`,
  tier values including `Unscored` / `Needs Review`).

### Milestone Framing
- `.planning/REQUIREMENTS.md` — CLEAN-01 wording.
- `.planning/ROADMAP.md` — Phase 42 success criteria (SC1 reinterpreted per D-01; SC2's
  snapshot-first and zero-drift requirements stand).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/snapshot_hubspot_schema.py` — GET-only schema capture with `--label`; already
  contains a `_print_drift()` helper and `_assert_no_secrets()` guard the new drift checker
  can borrow from.
- `config/hubspot_flows/*.{before,after}.json` — established before/after archival
  convention D-09 extends.
- Phase 40 flow fetch/PUT tooling — `GET /automation/v4/flows/{id}` round-trip proven live.
- Phase 40 parity harness (pytest tier + `scripts/` wrapper with JSON verdict) — the shape
  D-10's drift checker mirrors.

### Established Patterns
- Portal 22617666 on ap1; `hs` CLI needs `--account=22617666`; private app token carries
  `automation` scope.
- `.env` permission-blocked to Read/Bash — hand the operator a `!` command for token values.
- HubSpot property gotchas: names must be lowercase; boolean properties need `"true"`/
  `"false"` string option values; both fail only live.
- HubSpot property DELETE is a soft archive, not a destroy — the mechanism D-07 relies on.
- Phase 40 D-08 precedent: Claude executes portal mutations directly when the action is
  reversible and snapshot-protected.

### Integration Points
- `config/hubspot_properties.yaml` is consumed by the property-sync tooling; growing it
  (D-04) changes what that tooling considers managed — planner must check the sync path
  does not start creating/patching properties as a side effect of the expansion.
- The five `*_score` properties feed the calculated `lv_icp_fit_score` formula; any
  archival touching them breaks WF1's tier ladder — the explicit do-not-touch set.
- Phase 43 follows and touches pipeline code, not schema — no ordering conflict.

</code_context>

<specifics>
## Specific Ideas

- The SC1 conflict was discovered during this discussion, not carried in from Phase 40 —
  the planner should treat D-01 as the load-bearing decision of the phase and lead the plan
  with the do-not-archive set, so no executor reads the roadmap literally and disables the
  engine.
- Operator chose "archive uncontested, ask on doubt" over a full approval gate — the plan
  must define what "uncontested" means concretely (zero references AND known provenance),
  not leave it to executor judgment.
- Reconciliation performs no portal writes (D-05); archival does (D-07/D-08). The plan
  should keep those as separate, clearly-labelled activities so the read-only claim stays
  true.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Sweep re-notifies a fixed failure until 100 executions displace it"
  (`2026-08-03-sweep-lookback-has-no-time-window.md`) — sweep concern, not scoring cleanup.
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep"
  (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`) — operator-plugin concern.
- "UAT 2.2 names two header aliases the column mapping does not support"
  (`2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`) — contact-upload concern.
- "Enrichment throughput — 82% of every full run is two sequential Anthropic calls"
  (`2026-08-04-enrichment-throughput-ceiling.md`) — pipeline performance.

### Noted for a future phase
- Adding the drift checker to the unattended sweep was deliberately declined (D-12); if
  schema churn increases later, revisit.

</deferred>

---

*Phase: 42-Scoring Artifact Cleanup & Reconciliation*
*Context gathered: 2026-08-07*
