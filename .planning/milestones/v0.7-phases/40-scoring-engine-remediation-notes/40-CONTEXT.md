# Phase 40: Scoring Engine, Veto & Parity Remediation - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the ten validated scoring defects (F1–F10, HANDOVER §10.2) inside the four existing
HubSpot company workflows on the fix-in-place path sealed by 39-DECISION.md (flow IDs
4626124224, 4626722240, 4626722237, 4625147345), rebuild veto ownership on the n8n pipeline
side per HANDOVER §5 decision 2, and land a parity harness that asserts HubSpot's live
scores against `compute_icp_score`. Covers ENGINE-01–07, VETO-01–03, PARITY-01–02.
Score stays in `lv_icp_fit_score`, tier in `lv_icp_tier` — the write target does not change.
No mass backfill of the 712 existing companies (mechanism only; the portfolio-wide run is
Phase 41), no rubric-weight changes, no lead-scoring-tool build.

</domain>

<decisions>
## Implementation Decisions

### Veto Ownership Mechanics
- **D-01:** `lv_anti_icp_flag` / `lv_anti_icp_reason` are written by the **n8n pipeline
  only**. The Geography flow's veto branch (today's only live writer, and the F4 AU-spelling
  bug) is deleted; no HubSpot workflow touches the flag after remediation. The pipeline
  derives the veto deterministically from canonical inputs (`lv_country_region_normalized`,
  `lv_produces_content`, `lv_is_hardware_vendor`). Honors HANDOVER §5 decision 2 literally.
  — **Reversibility:** costly — moving the writer back to HubSpot later means rebuilding
  workflow branches and re-fixing the same symmetric set/clear defects (F4–F6) in a second
  place.
- **D-02:** Stale-flag policy: a manual property fix in HubSpot leaves the flag stale
  **until the next enrichment run** — accepted. The refresh path is the existing one:
  operator sets `lv_enrichment_requested="true"` and the 15-min poller picks it up.
  VETO-02 ("correcting clears the flag") is satisfied via that path — the plan must
  document this operator procedure explicitly.
- **D-03:** F8 fix target: a sub-15 score **without** a veto grades **Unscored** — matching
  the parity oracle `src/icp_scoring.py` exactly (user initially preferred keeping D; the
  conflict with locked ENGINE-07 / ROADMAP SC3 / oracle was surfaced and Unscored
  confirmed). D stays veto-only.
- **D-04:** P2/P4 latent bugs close in this phase, before the pipeline veto write goes
  live: give `lv_anti_icp_flag`/`lv_anti_icp_reason` a **real `min_confidence` threshold**
  (~80; veto derives from already-validated inputs) in `n8n/code/mergeCompanies.js`, and
  coerce booleans to `"true"`/`"false"` strings before they reach `canonicalPatch` — the
  same fix pattern 36-07 applied to `lv_enrichment_requested` (HubSpot EQ filters compare
  strings; a bare boolean silently breaks every view/trigger reading the flag).

### Remediation Surface
- **D-05:** Workflow fixes are **API-driven with flow JSON in the repo**: fetch each flow's
  definition via `GET /automation/v4/flows/{id}`, fix the JSON in the repo, apply via PUT
  (automation scope already granted). Snapshot before/after. Portal-UI hand-edit is the
  fallback only for what the API rejects. Versioned, reproducible, re-checkable.
- **D-06:** Keep the existing component architecture — per-input `*_score` mapper flows +
  calculated sum + tier workflow. F1 is fixed by **adding** a `produces_content_score`
  property + mapper flow (trigger: `lv_produces_content`) + a new term in the
  calculated-sum formula. 5 components total. No consolidation/rebuild of working
  machinery (operator's architecture-reuse requirement extends here).
- **D-07:** Change-safety protocol: **disable each flow, apply the edit, validate on
  disposable `ZZ-SCORING-TEST-DELETE-ME-*` companies, then re-enable**. No half-fixed flow
  ever fires on a real record. The brief scoring outage is harmless — nothing consumes
  scores in real time.
- **D-08:** Execution: **Claude executes flow PUTs directly in-session** — no
  armed/disarmed script gate for the flow mutations (unlike the 39-03 probe convention).
  D-07's disable/validate/re-enable protocol is the safety envelope.

### Backfill for the 712
- **D-09:** Scope split: Phase 40 **builds and proves the backfill mechanism on a small
  sample** (fixtures + a few real records — doubles as PARITY-01's real-record sample);
  the portfolio-wide run belongs to **Phase 41**, after enrichment populates inputs so
  scores land meaningful rather than mass-Unscored.
- **D-10:** Backfill trigger mechanism: **batch-seed the component scores** — batch PATCH
  writes `org_type_score` / `geography_score` / `annual_revenue_score` /
  `produces_content_score` computed from each record's current inputs (0 where the input
  is missing), mirroring the `PROPERTY_DEFAULT_VALUE` stamp new records get. The sum then
  computes and WF1 fires. Deterministic, scoring-only, zero enrichment/provider cost. No
  reliance on unverified same-value re-enrollment behavior.

### Parity Harness
- **D-11:** Form: **both layers** — `tests/` pytest module (fixtures parametrized from
  `config/icp_scoring.yaml`, oracle = `compute_icp_score`, live HubSpot calls behind an
  opt-in marker) **plus** a thin `scripts/` wrapper that runs the sweep and writes a JSON
  verdict report for scheduled/report use.
- **D-12:** Standing cadence: **two-tier** — the script wrapper does a cheap **read-only
  pass on the real-record sample** (recompute vs live scores, no record creation) on the
  unattended sweep cadence; the **full fixture run** (create/exercise/delete disposables)
  stays on-demand, run before/after any rubric or flow change.
- **D-13:** Veto regression coverage (F4/F7 named cases): **live end-to-end only** — drive
  full enrichment runs against disposable companies and assert the final
  `lv_anti_icp_flag`/`lv_icp_tier` state. No offline node-driver substitute for the veto
  cases. Consequence accepted: these cases burn Anthropic spend per run and belong to the
  on-demand full tier (D-12), never the scheduled read-only pass.

### Claude's Discretion
- `lv_anti_icp_reason` string format/content (derive from `config/icp_scoring.yaml`
  hard-veto reason strings).
- Exact `min_confidence` value for the veto fields (~80 suggested, not locked).
- Revenue-branch boundary encoding in flow JSON (exclusive bounds vs re-ordering) — must
  produce rubric-exact results at 500M/750M/1B/1.2B boundaries (ENGINE-04).
- Real-record sample size/selection for PARITY-01.
- Flow-JSON storage location in repo and snapshot naming.
- Batch sizes / rate handling for the backfill seed mechanism.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Defect Inventory & Path Decision
- `HANDOVER-2026-08-06-icp-scoring.md` §10.1 — the four flow IDs, triggers, writes,
  latencies, component-default behavior; §10.2 — the F1–F10 validated defect table (the
  remediation target list); §10.3 — the smallest fix set; §5 decision 2 — vetoes stay
  pipeline-owned (locked).
- `.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md` — the sealed
  fix-in-place path verdict, what it shapes downstream, re-check procedure.
- `.planning/phases/40-scoring-engine-remediation-notes/PIPELINE-DEFECTS-VALIDATION.md` —
  P1–P4 verdicts; P2 (`min_confidence: 0`) and P4 (boolean-vs-string) are the latent bugs
  D-04 closes; names the exact code sites (`n8n/code/mergeCompanies.js:60-61`, ENRICH
  wrapper candidate lists, BUG-27 coercion loop).

### Rubric Oracle
- `config/icp_scoring.yaml` — rubric of record (lv-icp-v0.1): point values, boundaries,
  hard-veto reasons, tier rules.
- `src/icp_scoring.py` — `compute_icp_score`, the parity oracle every fix is asserted
  against (D-03 pins tier semantics to it).

### Milestone Framing
- `.planning/REQUIREMENTS.md` — ENGINE-01–07, VETO-01–03, PARITY-01–02 wording.
- `.planning/ROADMAP.md` — Phase 40 success criteria (path-neutral observable behavior);
  Phase 41 boundary (mass backfill + E2E proof live there).

### Prior Fix Pattern
- `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-07-SUMMARY.md`
  — the boolean→string HubSpot EQ-filter fix precedent D-04 replicates.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Disposable-company validation pattern (`ZZ-SCORING-TEST-DELETE-ME-*` create/exercise/
  delete, zero real records) — the validation vehicle for D-07 and the parity fixture runs.
- `scripts/snapshot_hubspot_schema.py` — schema snapshot before portal mutations (D-05).
- `src/hubspot_client.py` + `delete_record()` (Phase 39 asset) — record lifecycle for
  fixtures.
- `tests/test_icp_scoring.py` — existing oracle tests; parity fixtures extend from here.
- P2/P3 repro tooling in prior session scratchpad (extract_node.py, node-driver sandbox) —
  pattern reusable for offline n8n assertions if planning wants them beyond D-13's scope.
- Archived flow definitions: `scratchpad/flows_full.json` (session scratch — re-fetch via
  `GET /automation/v4/flows/{4625147345,4626124224,4626722237,4626722240}` if gone).

### Established Patterns
- Portal 22617666 on **ap1**; `hs` CLI needs `--account=22617666`; private app token
  carries `automation` scope (granted 2026-08-06).
- `.env` is permission-blocked to Read/Bash — hand the operator a `!` command when a token
  value is needed interactively.
- HubSpot property gotchas: bools need `"true"`/`"false"` string values for EQ filters
  (36-07); property names lowercase; both only fail live.
- n8n stored-vs-running: bare PUT never reloads a running workflow — bounce after every
  n8n-side change (applies to the D-01/D-04 pipeline changes, not HubSpot flows).
- Test commands: `.venv/bin/python -m pytest` + `node --test tests/n8n/*.test.mjs`.

### Integration Points
- `n8n/code/mergeCompanies.js` (`DEFAULT_COMPANY_POLICY`, `_gate()`) + the
  `ENRICH_MERGE_CO` / `ENRICH_DECIDE_CO_CLOUD` wrappers in
  `scripts/build_cloud_workflows.py` — where D-01's veto computation and D-04's
  threshold/coercion fixes land; candidate lists currently exclude the veto fields (dead
  policy).
- HubSpot calculated-property formula behind `lv_icp_fit_score` — gains the
  `produces_content_score` term (D-06).
- WF1 (4625147345) — tier logic changes for F7 (recompute on flag change) and F8
  (sub-15 → Unscored per D-03).
- Phase 41 consumes the backfill mechanism (D-09/D-10) for the portfolio-wide run.

</code_context>

<specifics>
## Specific Ideas

- D-03 records a deliberate reversal: the operator first chose "keep D" for sub-15 scores,
  then confirmed Unscored once the ENGINE-07/oracle conflict was laid out — planner should
  treat Unscored as settled, not revisit.
- D-08 is a deliberate departure from the armed/disarmed script convention for this
  phase's flow PUTs — speed over ceremony, with D-07 as the safety envelope.
- D-13 deliberately rejects offline veto assertions in the harness: the operator wants
  veto regression proven on the real wire, cost accepted.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Sweep re-notifies a fixed failure until 100 executions displace it"
  (`2026-08-03-sweep-lookback-has-no-time-window.md`) — sweep concern, outside scoring
  scope (also reviewed in Phase 39).
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep"
  (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`) — same; backlog.
- "Enrichment throughput — 82% of every full run is two sequential Anthropic calls"
  (`2026-08-04-enrichment-throughput-ceiling.md`) — pipeline performance, not scoring
  correctness.
- "UAT 2.2 names two header aliases the column mapping does not support"
  (`2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`) — contact-upload concern.

</deferred>

---

*Phase: 40-Scoring Engine, Veto & Parity Remediation*
*Context gathered: 2026-08-06*
