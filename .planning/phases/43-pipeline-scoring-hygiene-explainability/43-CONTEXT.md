# Phase 43: Pipeline Scoring Hygiene & Explainability - Context

**Gathered:** 2026-08-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the pipeline-side residue of the 2026-08-06 scoring audit: the live boolean-vs-string
defect on review flags, the dormant veto site's missing guards, a producer for
`lv_icp_score_breakdown`, and first consumption of the closed-lost feedback signal. Covers
PIPE-01 through PIPE-04. No rubric weight changes (REQ-signoff-gate is an external business
gate on this milestone). No pipeline-side score computation — the engine stays
HubSpot-resident and `src/icp_scoring.py` remains oracle-only. P1 (revenue units) and P3
(research-lane row loss) are deliberately absent: both were exercised and DISPROVEN in
PIPELINE-DEFECTS-VALIDATION.md.

**Facts established during discussion:**

1. **Two live boolean writers confirmed** — `n8n/code/reviewApply.js:89` emits
   `lv_enrichment_needs_review: false` and `scripts/build_cloud_workflows.py:2637` emits
   `properties.lv_enrichment_needs_review = true`. Both are JS booleans; HubSpot EQ filters
   (`build_cloud_workflows.py:5088` filters on the string `"true"`) can never match them.
2. **`lv_closed_lost_reason` has no implementation surface.** It appears in no config, no
   pipeline code (only a mention in `scripts/smoke_closed_won_research.py`), it is a **Deal**
   property, `config/hubspot_properties.yaml` manages only `companies` and `contacts`, and
   PROJECT.md records the field as 0% filled. PIPE-04 builds consumption for a signal that
   is currently empty.
3. **PIPE-03 conflicts with Phase 40 D-12** — D-12 defined the scheduled parity tier as
   read-only (recompute vs live, no record mutation). PIPE-03 asks the parity harness to
   write. Resolved by D-01 below.

</domain>

<decisions>
## Implementation Decisions

### Breakdown Write Path (PIPE-03)
- **D-01:** The breakdown write is a **new opt-in mode on the parity harness**
  (`--write-breakdown`, off by default). Phase 40 D-12's scheduled read-only pass stays
  genuinely read-only and its guarantee survives; writing the breakdown is always a
  deliberate invocation. Rejected: making the scheduled pass write (destroys the read-only
  claim) and a separate script (duplicates fetch/recompute logic the harness already has).
- **D-02:** Truncation for the 60k property limit: **drop detail, keep totals**. Shed
  per-component evidence/reason strings first; always retain rubric version, component
  points, hard vetoes, graduated deductions, and the total; stamp `truncated: true` when
  shedding occurred. A truncated breakdown must still be valid JSON and still explain the
  tier. Rejected: the bare `json.dumps(...)[:60000]` slice used elsewhere in
  `merge_policy.py` — it can emit invalid JSON.
- **D-03:** Coverage: **the records the harness checks** on that invocation — fixtures, the
  real-record sample, or the Phase 41 imported population, whatever the run targets.
  Portfolio-wide breakdown backfill is not in scope (it would need its own arming
  discussion).

### Loss-Reason Consumption (PIPE-04)
- **D-04:** Deliverable is a **report built against live truth**. The aggregator queries the
  real Deal API; if `lv_closed_lost_reason` is absent or empty the report states that
  explicitly with counts rather than failing or fabricating. The consumption path exists and
  works the moment reps start filling the field. Rejected: creating the Deal property in
  this phase (expands into schema creation on an object the config does not manage).
- **D-05:** Report content: **rubric-version stamp plus a tier cross-tab** — loss reasons
  cross-tabulated against the lost company's ICP tier/score, stamped with the live rubric
  version (`lv-icp-v0.1`). This is what makes "we lose Tier A deals on price" visible, which
  is the signal a future rubric revision needs. Consumption only — no weight changes.
- **D-06:** Surface: an **operator-plugin skill**. This is a deliberate **override of the
  milestone's Out of Scope fence** ("Operator plugin changes | Plugin is v0.6's surface;
  scoring remediation is backend/HubSpot-side"). The operator was shown the conflict and
  chose to admit plugin work into v0.7 for this deliverable. Recorded here the same way
  Phase 42 D-01 records its roadmap reinterpretation — the divergence is traceable, not
  silent. — **Reversibility:** costly — a shipped plugin skill becomes an operator-facing
  surface with its own release/versioning expectations (plugin.json bump + marketplace
  clone refresh per the known install traps); withdrawing it later is a user-visible removal.

### Coercion Blast Radius (PIPE-01)
- **D-07:** Scope is **every boolean property writer**, not just the named flag. The sweep
  covers `lv_enrichment_needs_review`, `lv_icp_needs_review`, and any other
  boolean-valued HubSpot property write found across `n8n/code/`,
  `scripts/build_cloud_workflows.py`, and the Python writers — all coerced to the strings
  `"true"`/`"false"` at their write sites, following the 36-07 idiom. The operator chose the
  widest option deliberately: the class has now recurred three times (36-07
  `lv_enrichment_requested`, Phase 40 D-04 veto fields, this phase), and a named-field-only
  fix guarantees a fourth. — **Reversibility:** reversible — coercion is local at each write
  site.
- **D-08:** Test form: **anchored grep over the generated n8n JSON asserting exactly-string,
  red-checked against a deliberately broken build, plus a live-gated EQ-filter fixture**
  proving the HubSpot filter actually matches after the fix. The grep alone would pass
  without proving the filter behavior; the requirement names both.

### Veto Hardening (PIPE-02)
- **D-09:** `min_confidence` for veto-class fields in `mergeCompanies.js` is **80**,
  matching Phase 40 D-04's suggestion and the existing `lv_is_hardware_vendor` /
  `lv_is_gambling_operator` thresholds in `config/field_policy.yaml` — the very inputs the
  veto derives from. Currently 0.
- **D-10:** Proof shape: **keep the dead-proof test untouched, add a policy-shape test**.
  The existing test proving the veto candidate path is dead stays as-is and must still pass.
  A new test asserts the policy object itself — non-zero `min_confidence`, coercion present
  — by inspecting the policy/config, not by driving the path. Hardening is proven; the path
  stays dead. Rejected: temporarily enabling the path in a fixture (risks the test becoming
  the thing that resurrects it).

### Execution Discipline (SC5)
- **D-11:** All n8n changes go through **`scripts/build_cloud_workflows.py` regeneration —
  no hand-edits to generated JSON**. Deploy stays disarmed; the post-build arming grep must
  read 0; a workflow bounce (deactivate→activate) follows any deploy, per the stored-vs-
  running rule (a bare PUT never reloads a running workflow).

### Claude's Discretion
- The exact boolean-writer inventory produced by D-07's sweep and the order fixes land in.
- Breakdown JSON schema details beyond D-02's retained fields.
- Plugin skill name, trigger phrasing, and whether the aggregator lives in `scripts/` with
  the skill shelling out to it (preferred) or entirely inside the plugin.
- Report file naming/location for any committed artifact the skill produces.
- Whether the EQ-filter fixture reuses the disposable-company pattern or an existing test
  record.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Defect Evidence
- `.planning/phases/40-scoring-engine-remediation-notes/PIPELINE-DEFECTS-VALIDATION.md` —
  P1–P4 verdicts. P2 (`min_confidence: 0`) and P4 (boolean-vs-string) are this phase's
  targets; P1 and P3 are DISPROVEN and out of scope. Names the exact code sites.
- `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-07-SUMMARY.md`
  — the boolean→string EQ-filter fix precedent D-07/D-08 replicate (the "36-07 idiom").

### Code Sites
- `n8n/code/reviewApply.js:89` — live boolean writer (`lv_enrichment_needs_review: false`).
- `scripts/build_cloud_workflows.py:2637` — live boolean writer (`= true`); `:5088` and
  `:5329` show the string-comparing EQ filters that cannot match them.
- `n8n/code/mergeCompanies.js` — `DEFAULT_COMPANY_POLICY` / `_gate()`, the single shared
  veto fix site for D-09/D-10.
- `n8n/code/reviewDecision.js` — the other review-flag surface (`P_NEEDS_REVIEW`).

### Harness & Oracle
- `scripts/run_scoring_parity.py` + `tests/test_scoring_parity.py` — the Phase 40 harness
  D-01 extends with `--write-breakdown`.
- `src/icp_scoring.py` — `compute_icp_score`; its `breakdown` dict is what D-02 serializes.
- `config/icp_scoring.yaml` — rubric version (`lv-icp-v0.1`) stamped into breakdown and the
  loss-reason report.
- `config/field_policy.yaml` — the threshold table D-09's value of 80 aligns to.

### Prior Phase Decisions
- `.planning/phases/40-scoring-engine-remediation-notes/40-CONTEXT.md` — D-04 (the
  min_confidence + coercion fix this phase completes), D-12 (the read-only scheduled tier
  D-01 protects), D-13 (live veto regression convention).

### Milestone Framing
- `.planning/REQUIREMENTS.md` — PIPE-01..04 wording; the "Out of Scope" table whose plugin
  fence D-06 overrides.
- `.planning/ROADMAP.md` — Phase 43 success criteria SC1–SC5.
- `CLAUDE.md` §5.3 — the `lv_closed_lost_reason` picklist and its Deal-object placement.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 40 parity harness (`scripts/run_scoring_parity.py`, `tests/test_scoring_parity.py`)
  — already fetches records and recomputes via `compute_icp_score`; D-01's write mode is an
  additive flag, not new machinery.
- 36-07's anchored-grep test idiom — the exact structural-test shape SC1 names.
- `src/hubspot_client.py` — record fetch/patch primitives; needs a Deal-object read path for
  D-04 (companies/contacts only today).
- Disposable-company pattern (`ZZ-SCORING-TEST-DELETE-ME-*`) — available for D-08's live
  EQ-filter fixture.
- `docs/reports/` convention (dated markdown) — the shape any committed report follows.

### Established Patterns
- Generated n8n JSON is builder output — never hand-edited; regenerate via
  `scripts/build_cloud_workflows.py`.
- n8n stored-vs-running: bare PUT never reloads a running workflow; bounce after every
  deploy.
- Deploys are two-key gated (`DRY_RUN=false` AND `ALLOW_N8N_DEPLOY=true`); arming writes is
  the operator-only line.
- Test commands: `.venv/bin/python -m pytest` + `node --test tests/n8n/*.test.mjs`
  (directory form is broken on node 24; system python lacks deps).
- Plugin release traps (relevant to D-06): a same-version reinstall deletes
  `operator.local.json`; the marketplace clone does not refresh on reinstall; a release
  needs a `plugin.json` version bump or the Update button stays greyed out.
- HubSpot property limit for multi-line text is 60k chars — D-02's truncation budget.

### Integration Points
- The review-queue HubSpot views/filters (`build_cloud_workflows.py:5088`, `:5329`) are the
  consumers that PIPE-01's fix repairs — they are the proof surface for D-08's EQ fixture.
- `lv_icp_score_breakdown` is already a managed company property in
  `config/hubspot_properties.yaml` — D-01 gives it its first producer.
- Phase 42's drift checker and this phase's property writes are independent; no ordering
  conflict, but Phase 42 should land first so the schema baseline is clean.
- D-06's plugin skill touches `operator-claude-plugin/` — the first v0.7 change to that
  surface; coordinate with the plugin's release conventions.

</code_context>

<specifics>
## Specific Ideas

- Two roadmap/scope tensions were surfaced and resolved with the operator during this
  discussion, and both must survive into planning: PIPE-03 vs Phase 40's read-only tier
  (D-01), and the plugin Out of Scope fence (D-06, deliberately overridden). Neither is a
  silent deviation.
- The operator chose the widest coercion scope (D-07) over the named requirement — the
  planner should treat the boolean-writer sweep as a first-class task with its own
  inventory step, not a one-line fix.
- PIPE-04 will produce a report over an empty dataset on first run. That is the expected,
  accepted outcome — the plan must not treat "zero loss reasons found" as a failure.

</specifics>

<deferred>
## Deferred Ideas

- Creating `lv_closed_lost_reason` on the Deal object with the CLAUDE.md picklist, and
  bringing deals under `config/hubspot_properties.yaml` management — considered for PIPE-04,
  declined as schema-creation scope creep. Natural candidate for a follow-on phase once the
  report proves the consumption path.
- Portfolio-wide `lv_icp_score_breakdown` backfill — out of scope per D-03; would need its
  own arming discussion.

### Reviewed Todos (not folded)
- Carried from Phases 41/42, all still backlog: sweep lookback window, sweep crontab
  versioned path, contact-upload header aliases, enrichment throughput ceiling.

</deferred>

---

*Phase: 43-Pipeline Scoring Hygiene & Explainability*
*Context gathered: 2026-08-07*
