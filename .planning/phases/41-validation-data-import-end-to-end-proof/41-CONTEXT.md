# Phase 41: Validation Data Import & End-to-End Proof - Context

**Gathered:** 2026-08-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Land the 66 web-researched companies (49 high-confidence) from the ICP validation analysis
in HubSpot as a real, scoreable population with `lv_*` inputs and provenance stamped, at
zero provider spend (no ZoomInfo/Apollo/Lusha credits; Anthropic spend accepted, ~$5), and
prove — at small, reviewable volume — that the Phase 40-remediated engine fires
automatically on the actual import/enrichment write path. Covers DATA-01 and DATA-02 only.
No rubric changes, no artifact cleanup (Phase 42), no pipeline hygiene defects (Phase 43),
no full 712-company backfill beyond what the imported population plus Phase 40's proven
mechanism already covers.

**Source-of-truth finding (validated this session):** the research dataset physically
exists at `../ausgtm-lightningvisuals-data/data/enriched_companies.json` (sibling repo) —
66 entries keyed by June-2026 HubSpot company IDs, produced 2026-06-29 by
`../icp-analysis/enrich.mjs` via the Perplexity API (`sonar`). Confidence distribution:
49 high / 16 medium / 1 low — the "49 high-confidence" claim is accurate. Each record
carries org_type, produces-content, sponsorship, hq_country, is_australia,
employee_estimate, evidence summary, and source URLs. All 66 are existing CRM companies
(enrich-in-place, not net-new creates).

</domain>

<decisions>
## Implementation Decisions

### Source Dataset
- **D-01:** Re-verify **all 66** via a fresh Claude web-research pass before import — the
  June Perplexity data is ~5.5 weeks old and 17 records are medium/low confidence. Zero
  provider credits; ~$5 Anthropic at measured rates ($0.0686/record). Fresh research is
  the source of truth for what lands.
- **D-02:** June→`lv_*` enum mapping is a **deterministic table plus a hand-curated
  exception list** (e.g. QRIC → `regulator`, which the coarse Perplexity enum bucketed as
  governing body). Perplexity enum: `Team/Club` → `individual_club_team`,
  `League/Governing-Body` → `governing_body_league`, `Broadcaster/Production` →
  `broadcaster` (exception list may promote to `content_producer`), `Non-sports-leisure` /
  `Other` → `other`. Exact exception list is planner/executor work.
- **D-03:** Categorical confidence maps **high→85, medium→65, low→40** wherever the June
  data is used numerically (pseudo-provider candidates, provenance stamps). Fresh research
  emits native 0–100 confidence.
- **D-04:** The June dataset acts as a **conflict check**: disagreement with fresh research
  on `lv_org_type` or `lv_produces_content` routes that record to `needs_review` instead of
  silently overwriting — implemented via D-07 (pseudo-provider), so the existing conflict
  machinery adjudicates.

### Import Write Path
- **D-05:** Vehicle is the **real n8n cloud enrichment pipeline**: queue the 66 via
  `enrichment_requested="true"`, let the 15-min poller + enrichment workflow do research,
  merge, and PATCH. Re-verification (D-01) and import are one motion, and this is the exact
  write path DATA-02 requires proving — not a standalone script, not the local Python path.
  — **Reversibility:** costly — a standalone-script import would satisfy DATA-01 faster but
  leaves DATA-02 unproven; switching later means re-running the population through the
  pipeline anyway.
- **D-06:** Arming: **manual arm for the whole run** — operator arms canonical writes once,
  all 66 process across poller cycles, operator disarms at the end. The operator-arms
  boundary holds (Claude never arms writes; hand the operator the exact command). Longer
  exposure window accepted over scheduled_arm.py's bounded windows.
- **D-07:** Canonical-write scope for this run: **scoring inputs only** — `lv_org_type`,
  `lv_produces_content`, `lv_content_type`, `lv_country_region_normalized`,
  `lv_revenue_band`, `lv_employee_band`, `lv_is_hardware_vendor`,
  `lv_is_gambling_operator`, `lv_sponsorship_reliant`. Firmographics (`domain`,
  `annualrevenue`, `numberofemployees`, `industry`) stay staged-only. Matches the pilot
  promotion ramp.
- **D-08:** June-vs-fresh comparison runs **inside the pipeline as a pseudo-provider**: the
  June dataset is injected as a provider candidate so the existing conflict-detection /
  Sonnet-escalation / needs_review machinery does the adjudication naturally. No separate
  diff harness.

### Record Matching
- **D-09:** Records are existing CRM companies keyed by June-era HubSpot IDs. Pre-flight
  resolves all 66 IDs against the live portal; dead IDs (merged/deleted since June) are
  **re-matched via HubSpot search on name/domain**; still-unmatched records are skipped and
  listed in the run report. No net-new company creation in this phase.

### Auto-Score Proof
- **D-10:** Ramp: **canary then rest** — ~5 records first, verify `lv_*` inputs land,
  component scores + `lv_icp_fit_score` + `lv_icp_tier` compute automatically with zero
  per-record manual touch, provenance stamped; then release the remaining ~61 in the same
  armed session. A bad enum mapping or write defect is caught on 5 records, not 66.
- **D-11:** DATA-02 closes with the **Phase 40 parity harness run over the imported
  population post-landing**: assert live score/tier == `compute_icp_score` for every
  imported record, plus a committed JSON verdict report and evidence doc. Reuses existing
  machinery (`scripts/` parity wrapper); no new proof harness.
- **D-12:** Review-queue policy: **accept + report** — needs_review routing (unknown
  org_type, June conflicts) is the system working as designed. The run report lists which
  records queued and why; operator triages afterward via the existing review flow. No cap,
  no pre-triage gate.

### Claude's Discretion
- Exact enum-mapping table content and the exception list (D-02) — planner proposes,
  grounded in the analysis doc's named misfits.
- Canary record selection (~5) and batch/poller cadence details within the armed session.
- Pseudo-provider injection mechanics (how the June dataset enters the candidate set —
  fixture adapter vs staged upload) and its provider name/trust rank.
- Run-report format and location.
- Pre-flight ID-resolution script shape.
- Latency threshold used to declare "scores automatically on landing" (anchor to Phase 40
  measured mapper-flow latencies).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source Dataset & Its Provenance
- `../ausgtm-lightningvisuals-data/data/enriched_companies.json` — THE import source:
  66 records, HubSpot-ID-keyed, with evidence/sources/confidence (sibling repo, outside
  this git root).
- `../icp-analysis/enrich.mjs` — how the June data was produced (Perplexity `sonar`,
  prompt schema, enum definitions); defines the coarse enum D-02 maps from.
- `docs/business/icp-scoring.md` — the ICP validation analysis narrative; §2 method
  (66/49 claim), §4 named misfits for the exception list (QRIC regulator note), §6
  enrichment plan.
- `HANDOVER-2026-08-06-icp-scoring.md` §11 — "research never landed in the CRM" framing,
  review-queue swamp warning (711/712 route to review when org_type unknown).

### Phase 40 Outputs This Phase Consumes
- `.planning/phases/40-scoring-engine-remediation-notes/40-CONTEXT.md` — D-09/D-10
  (backfill mechanism, Phase 41 consumption), D-01 (veto pipeline-owned), D-04
  (boolean-string coercion + min_confidence).
- `scripts/backfill_seed_company_scores.py` — proven component-score seeding mechanism
  (for any imported record whose inputs land without firing flows).
- Phase 40 parity harness: `tests/` live-gated fixture tier + `scripts/` read-only sweep
  wrapper — D-11's proof vehicle.
- `docs/OPERATOR-VETO-REFRESH.md` — operator refresh procedure for stale flags.

### Rubric & Merge Policy
- `config/icp_scoring.yaml` — rubric of record (lv-icp-v0.1); enum values the mapping
  must hit exactly.
- `src/icp_scoring.py` — `compute_icp_score`, the parity oracle for D-11.
- `config/field_policy.yaml` — min_confidence thresholds D-03's numbers must clear;
  field classes governing D-07's canonical scope.
- `config/source_registry.yaml` — where the pseudo-provider (D-08) needs a registry entry.

### Milestone Framing
- `.planning/REQUIREMENTS.md` — DATA-01/DATA-02 wording.
- `.planning/ROADMAP.md` — Phase 41 success criteria; Phase 42 boundary (cleanup lives
  there).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- n8n cloud enrichment workflow (`n8n/wf_enrichment_cloud.json` + `scripts/build_cloud_workflows.py`) —
  the D-05 vehicle; research lane already does Claude web research with native confidence.
- `scripts/backfill_seed_company_scores.py` — Phase 40's proven, gated seeding mechanism.
- Parity harness (Phase 40 D-11/D-12) — pytest fixture tier + sweep wrapper with JSON
  verdict output.
- `src/hubspot_client.py` — search/get/patch primitives for pre-flight ID resolution.
- Disposable-company pattern (`ZZ-SCORING-TEST-DELETE-ME-*`) — available if a dry
  canary-of-the-canary is wanted before touching real records.
- Mock-provider fixture pattern (`src/providers.py`) — template for the June-data
  pseudo-provider adapter.

### Established Patterns
- Write gates disarmed by default; **arming is operator-only** — Claude prepares exact
  commands, operator runs them (n8n-deploy classifier boundary).
- n8n stored-vs-running: bounce (deactivate→activate) after every workflow content change.
- Booleans must land as `"true"`/`"false"` strings in HubSpot properties (EQ-filter gotcha).
- `scheduled_arm.py` dispatch honors a 2-per-request record cap (webhook refuses more).
- Portal 22617666 on ap1; `.env` permission-blocked — hand operator a `!` command for
  token values.
- Measured costs: ~$0.0686 Anthropic/record full enrichment; Lusha/provider credits NOT
  touched by research lane.
- Enrichment throughput: two sequential Anthropic calls dominate (~82% of run time) —
  66 records across 15-min poller cycles takes a while; plan the armed window accordingly.

### Integration Points
- `enrichment_requested="true"` PATCH → 15-min poller → enrichment workflow → merge →
  canonical PATCH → HubSpot mapper flows fire component scores → calculated
  `lv_icp_fit_score` → WF1 tier ladder. DATA-02 proves this whole chain.
- June pseudo-provider enters at the candidate-normalization stage alongside claude_web
  research results (`n8n/code/mergeCompanies.js` candidate lists must include the veto and
  input fields per Phase 40 D-04 fixes).
- Phase 42 consumes this phase's outcome (cleanup/reconciliation happens after the
  population lands).

</code_context>

<specifics>
## Specific Ideas

- Operator asked "where did the 66 come from — validate that assertion" — the validation
  trail (enrich.mjs → enriched_companies.json, counts confirmed 49/16/1) is recorded in
  the domain section and must survive into the plan's evidence narrative.
- Operator chose manual whole-run arming over scheduled_arm.py bounded windows —
  deliberate simplicity-over-ceremony choice for this run; disarm at end is part of the
  run's definition of done.
- Zero provider spend is a hard fence (no ZoomInfo/Apollo/Lusha credits); Anthropic
  research spend (~$5) is explicitly accepted.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Enrichment throughput — 82% of every full run is two sequential Anthropic calls"
  (`2026-08-04-enrichment-throughput-ceiling.md`) — matters operationally for the 66-record
  run duration (noted in code_context) but the fix stays backlog; not folded.
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep"
  (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`) — operator-plugin concern;
  backlog.

</deferred>

---

*Phase: 41-Validation Data Import & End-to-End Proof*
*Context gathered: 2026-08-07*
