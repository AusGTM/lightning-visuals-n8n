# Phase 31: Enum Validation for Review Approvals - Context

**Gathered:** 2026-08-03
**Status:** Ready for planning
**Source:** PRD Express Path (`.planning/todos/pending/2026-08-03-fix-bugs-28-30-enum-validation-for-review-approvals.md`)

<domain>
## Phase Boundary

Fix three defects found live by the RB-9 armed review canary (30-07, 2026-08-03), so that a
review approval can never carry a value HubSpot will refuse, refusals are explicit at every
layer, and silence stops meaning two opposite things. Backend (n8n code + build) plus the
plugin client's interpretation and the runbook's diagnostic advice. Nothing else about the
review flow changes.
</domain>

<decisions>
## Implementation Decisions

### The fix shape (decided 2026-08-03, operator + agent — do not relitigate)
- **Validate-and-refuse, NO full mapping layer.** Taxonomies don't align (providers speak
  NAICS-ish sector labels; HubSpot's 148 `industry` values are LinkedIn-derived — mapping is
  judgment, not lookup). `industry` feeds no ICP scoring (the `lv_*` taxonomy does). Raw
  provider strings survive in the staging fields (`apollo_industry`, `zoominfo_industry`, …),
  so refusing canonical promotion loses nothing.
- **The ONLY mapping performed: exact case-insensitive label→value match** (`Sports` →
  `SPORTS`). ~5 lines. Everything inexact stays staged-only.

### BUG 28 — staging validation
- Generate an enum-options module (values AND labels) from the HubSpot property schema
  snapshot, following the existing generated-module pattern (`taxonomy.generated.js`, built
  by `scripts/gen_taxonomy_js.py` from `config/taxonomy.yaml`; snapshot capture exists in
  `scripts/snapshot_hubspot_schema.py`).
- Validate enum-bound canonical candidates at staging in `n8n/code/mergeCompanies.js` (field
  policy block at line ~33): an unmappable value is never offered as an approvable candidate;
  it stays staged with an explicit validation status naming why.
- Live evidence: candidate `arts, entertainment, and recreation` vs HubSpot options — approve
  PATCH → 400 "Bad request - please check your parameters", n8n execution 1173 error at node
  `Review Decision Update`. All seven other approve-patch keys validate clean against the live
  schema; `industry` is the sole cause.

### BUG 29 — the preview must stop lying
- The same generated module validates in `n8n/code/reviewDecision.js`'s **shared patch path**,
  so BOTH `dry_run` preview and apply refuse an invalid enum value explicitly, naming the
  value and the property. `preview_decision` returning `outcome: applied` for a write that
  will 400 is the defect.

### BUG 30 — silence must stop meaning two opposite things
- The review write gate currently answers NO body on an allowlist drop; the client reports
  `unparseable_response` for that AND for a workflow error. Make the gate respond an explicit
  refusal body on an allowlist drop.
- Update the plugin client's interpretation (`operator-claude-plugin/scripts/review_decision.py`
  around line 182 — the `unparseable_response` comment and its handling) so the two states are
  distinguishable to the operator.
- Correct OPERATOR-RUNBOOK.md RB-9's diagnostic advice ("silence means not on the allowlist —
  check TEST_RECORD_IDS before investigating anything else"), which pointed exactly wrong in
  the live case.

### Process invariants (from the milestone, non-negotiable)
- **Two-sided tests for every touched contract** (python + n8n reading the same literal/shape) —
  this milestone was burned five times by contracts held in two places and tested on one.
- Committed workflow artifacts remain disarmed (`grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"'
  n8n/*.json` → 0); the closing gate test is `test_control_disarmed_artifacts.py`.
- The fix reaches the live tenant only via a **disarmed redeploy + bounce of active
  workflows** (stored-vs-running reload gap, HANDOFF §2.1). No arming is needed anywhere in
  this phase.

### Claude's Discretion
- Where the generated enum module lives and its exact name (sibling to `taxonomy.generated.js`
  suggested), and whether the generator is a new script or an extension of
  `gen_taxonomy_js.py` / `snapshot_hubspot_schema.py`.
- The exact refusal-body shape for the allowlist drop (must be distinguishable from the
  outcome vocabulary already in `review_decision.py`: WRITING_OUTCOMES / NON_WRITING_OUTCOMES).
- Which enum-bound properties to cover beyond `industry` (any canonical field whose HubSpot
  type is `enumeration` should get the same treatment if cheap; `industry` is the one with
  live evidence).
- Test file placement, following existing conventions (`tests/n8n/*.test.mjs` node suite,
  `operator-claude-plugin/tests/` and root pytest suites).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The live evidence (what happened, verbatim)
- `.planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-07-SUMMARY.md` — the RB-9 run: step 8's failure, root-cause chain, all four findings
- `.planning/workstreams/plugin-entrypoint/HANDOFF.md` — §3 BUGS 28-31 (31 already fixed, `cf196d9`), §2 the reload gap
- `.planning/todos/pending/2026-08-03-fix-bugs-28-30-enum-validation-for-review-approvals.md` — the PRD this context derives from

### The code being changed
- `n8n/code/mergeCompanies.js` — field policy block (~line 33), staging decision (~line 139-143 `stale_refreshable` → needs_review candidate)
- `n8n/code/reviewDecision.js` — the decision endpoint's shared patch path (dry_run + apply)
- `n8n/code/reviewApply.js` — the 15-minute backstop; check whether it needs the same enum guard
- `operator-claude-plugin/scripts/review_decision.py` — client outcome vocabulary and `unparseable_response` handling (~line 182)
- `.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md` — RB-9's "two failure modes" diagnostic paragraph

### The patterns to follow
- `n8n/code/taxonomy.generated.js` + `scripts/gen_taxonomy_js.py` — the generated-module pattern (header marks it generated, source named, DO NOT EDIT)
- `scripts/snapshot_hubspot_schema.py` — existing HubSpot property-schema capture
- `scripts/build_cloud_workflows.py` — how n8n/code/*.js is assembled into deployable workflow JSON (any new module must ride this)
- `operator-claude-plugin/tests/test_control_flag_parity.py` — the read-the-other-side-as-text two-sided test idiom

</canonical_refs>

<specifics>
## Specific Ideas

- The generated module must carry values AND labels so the exact label→value normalization is
  a lookup against generated data, not a live API call inside a Code node (n8n Code nodes
  can't reach the HubSpot properties API mid-run without new credentials plumbing — keep it
  baked, like every other constant in this repo).
- HubSpot `industry` on companies: 148 options, `SPORTS` valid, live-verified 2026-08-03.
- The refusal body should name: the property, the offending value, and the nearest valid
  labels if cheap — the operator seeing "arts, entertainment, and recreation is not a value
  HubSpot accepts for industry" can act; a bare `refused` cannot be acted on.
- After the fix lands: re-run RB-9 step 8 only. Record `9604614548` was cleared manually
  2026-08-03 (reject stands, `industry`=`SPORTS`); a fresh `needs_review` fixture is needed —
  one enrichment run against a test company with a conflicting staged value produces one.
</specifics>

<deferred>
## Deferred Ideas

- Full provider→HubSpot industry mapping table (explicitly rejected 2026-08-03, not deferred —
  recorded here so it is not re-proposed as "missing").
- Semantic/fuzzy label matching beyond exact case-insensitive equality.
- Enum validation for contact-object properties (no live evidence; companies first).
</deferred>

---

*Phase: 31-enum-validation-for-review-approvals*
*Context gathered: 2026-08-03 via PRD Express Path*
