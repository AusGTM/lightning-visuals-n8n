# Phase 41: Validation Data Import & End-to-End Proof - Research

**Researched:** 2026-08-07
**Domain:** HubSpot data import via existing n8n Cloud enrichment pipeline; write-safety arming; provenance/parity proof
**Confidence:** HIGH for pipeline mechanics and gate locations (all file:line verified); MEDIUM for wall-clock/throughput and multi-source conflict architecture (partially unverified, flagged below)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Re-verify all 66 via a fresh Claude web-research pass before import — the June
  Perplexity data is ~5.5 weeks old and 17 records are medium/low confidence. Zero provider
  credits; ~$5 Anthropic at measured rates ($0.0686/record). Fresh research is the source of
  truth for what lands.
- **D-02:** June→`lv_*` enum mapping is a deterministic table plus a hand-curated exception
  list (e.g. QRIC → `regulator`, which the coarse Perplexity enum bucketed as governing
  body). Perplexity enum: `Team/Club` → `individual_club_team`, `League/Governing-Body` →
  `governing_body_league`, `Broadcaster/Production` → `broadcaster` (exception list may
  promote to `content_producer`), `Non-sports-leisure` / `Other` → `other`. Exact exception
  list is planner/executor work.
- **D-03:** Categorical confidence maps high→85, medium→65, low→40 wherever the June data is
  used numerically. Fresh research emits native 0–100 confidence.
- **D-04:** The June dataset acts as a conflict check: disagreement with fresh research on
  `lv_org_type` or `lv_produces_content` routes that record to `needs_review` instead of
  silently overwriting — implemented via D-07 (pseudo-provider).
- **D-05:** Vehicle is the real n8n cloud enrichment pipeline: queue the 66 via
  `enrichment_requested="true"`, let the 15-min poller + enrichment workflow do research,
  merge, and PATCH. Not a standalone script, not the local Python path.
- **D-06:** Arming: manual arm for the whole run — operator arms canonical writes once, all
  66 process across poller cycles, operator disarms at the end. Claude never arms writes;
  hand the operator the exact command.
- **D-07:** Canonical-write scope for this run: scoring inputs only — `lv_org_type`,
  `lv_produces_content`, `lv_content_type`, `lv_country_region_normalized`,
  `lv_revenue_band`, `lv_employee_band`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`,
  `lv_sponsorship_reliant`. Firmographics (`domain`, `annualrevenue`, `numberofemployees`,
  `industry`) stay staged-only.
- **D-08:** June-vs-fresh comparison runs inside the pipeline as a pseudo-provider: the June
  dataset is injected as a provider candidate so the existing conflict-detection/
  Sonnet-escalation/needs_review machinery does the adjudication naturally. No separate diff
  harness.
- **D-09:** Records are existing CRM companies keyed by June-era HubSpot IDs. Pre-flight
  resolves all 66 IDs against the live portal; dead IDs (merged/deleted since June) are
  re-matched via HubSpot search on name/domain; still-unmatched records are skipped and
  listed in the run report. No net-new company creation.
- **D-10:** Ramp: canary then rest — ~5 records first, verify `lv_*` inputs land, component
  scores + `lv_icp_fit_score` + `lv_icp_tier` compute automatically with zero per-record
  manual touch, provenance stamped; then release the remaining ~61 in the same armed
  session.
- **D-11:** DATA-02 closes with the Phase 40 parity harness run over the imported population
  post-landing: assert live score/tier == `compute_icp_score` for every imported record,
  plus a committed JSON verdict report and evidence doc. Reuses existing machinery; no new
  proof harness.
- **D-12:** Review-queue policy: accept + report — needs_review routing (unknown org_type,
  June conflicts) is the system working as designed. The run report lists which records
  queued and why; operator triages afterward. No cap, no pre-triage gate.

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

### Deferred Ideas (OUT OF SCOPE)
- "Enrichment throughput — 82% of every full run is two sequential Anthropic calls" —
  matters operationally for run duration but the fix stays backlog; not folded.
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep" — operator-
  plugin concern; backlog.
- No rubric changes, no artifact cleanup (Phase 42), no pipeline hygiene defects (Phase 43),
  no full 712-company backfill beyond what the imported population plus Phase 40's proven
  mechanism already covers.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | The 66 web-researched companies (49 high-confidence) from the ICP validation analysis land in HubSpot with `lv_*` inputs and provenance stamped — zero provider spend. | Confirms zero-spend is structural via SJ-3's providers-less dispatch event (Pitfall 1); confirms provenance is the single `lv_enrichment_provenance` blob + 2 verified-at keys, not per-field properties (Summary point 2, Code Example 3); flags that `lv_revenue_band`/`lv_employee_band` have no populating mechanism via web research and must come from the June pseudo-provider or be accepted as gaps (Pitfall 2) |
| DATA-02 | Imported companies score automatically on landing — no per-record manual touch. (Proves triggers fire on the write path enrichment/import actually uses.) | Names the exact write path (Architecture Diagram) and the existing parity harness invocation contract (`PARITY_SAMPLE_IDS`, Code Example 4) as the proof vehicle; flags unverified `mode: "each"` throughput at N=66 as the key risk to de-risk via the D-10 canary (Pitfall 4) |
</phase_requirements>

## Summary

This phase does not build new pipeline machinery — it drives the **existing** n8n Cloud
enrichment pipeline (`scripts/build_cloud_workflows.py` → `n8n/wf_enrichment_cloud.json` +
`n8n/wf_scheduled_maintenance_cloud.json`) against a real population, using the write-safety
overlay the `operator-claude-plugin` already ships (`n8n_arming.py`, `n8n_control.py`). Three
findings materially change how the plan should be shaped versus what CONTEXT.md's
`code_context` section implies:

1. **Zero provider spend is structural, not a switch to flip.** SJ-3 (the 15-min
   `lv_enrichment_requested` poller) builds its dispatch event with no `providers` key at all
   (`ENRICH_SJ3_BUILD_DISPATCH_EVENT`, `scripts/build_cloud_workflows.py:5636-5666`), and the
   parser resolves an absent `providers` key to zero enabled providers
   (`operator-claude-plugin/scripts/enrichment.py:14-16`). Because D-05 already commits to the
   SJ-3 poller as the vehicle, ZoomInfo/Apollo/Lusha are **never called on this path by
   construction** — there is no env var to set or unset for this run.

2. **Provenance is one JSON blob property, not per-field `*_source`/`*_confidence`
   properties.** The live schema has exactly `lv_enrichment_provenance` (textarea),
   `lv_org_type_verified_at`, `lv_produces_content_verified_at`
   (`config/hubspot_properties.yaml:192-204`), matching `mergeCompanies.js`'s own header
   comment (`n8n/code/mergeCompanies.js:9-14`). The per-field `<field>_source`/
   `<field>_confidence`/`<field>_evidence_url` pattern described in the project's `CLAUDE.md`
   §6.1/§7.2/§8.2 is the **original local-MVP design** and was superseded before the cloud
   pipeline shipped. SC1's "provenance stamped" bar is met by the single
   `lv_enrichment_provenance` JSON blob plus the two verified-at cache keys — not by 5-7
   properties per field.

3. **The manual "arm for the whole run" style D-06 locked has no existing single-command
   wrapper.** Every exposed arm path in the plugin (`control_actions.py`'s `arm_dispatch`
   action, `scheduled_arm.py`) binds arm→dispatch→disarm into one bounded cycle via
   `n8n_arming.armed_window` (`operator-claude-plugin/scripts/n8n_arming.py:418-453`). D-06's
   chosen pattern — arm once, let SJ-3's own internal 15-min tick write across many cycles,
   disarm at the end — requires calling `n8n_arming.arm_for_dispatch()` and
   `n8n_arming.disarm()` **as two separate, un-paired calls**, which nothing in the repo does
   today outside the context manager. This is buildable (both functions are already
   library-shaped for it — `arm_for_dispatch` at `n8n_arming.py:264-363`, `disarm` at
   `n8n_arming.py:366-415`) but the plan needs to say so explicitly rather than assume a
   `scheduled_arm.py`-style command exists.

**Primary recommendation:** queue via `lv_enrichment_requested="true"`, call
`n8n_arming.arm_for_dispatch(workflow_id, record_ids=<66 ids>, record_domains=[],
allow_create=False, config)` directly (not through `armed_window`) with the 66 resolved
HubSpot IDs as the write allowlist, let SJ-3's own 15-min internal tick process the backlog
(no external re-dispatch needed — SJ-3 will pick them up and write, since the enrichment
workflow is left armed), then call `n8n_arming.disarm(workflow_id, config)` once done. Both
calls require `ALLOW_N8N_ARM=true` in the operator's shell — hand the operator exact `!`
commands for both the arm and the disarm.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Population source (66 records) | Sibling data repo (static file) | — | `enriched_companies.json` is a build artifact of a separate research project, read once to seed the exception-list/comparison logic, not queried live |
| Fresh re-verification research (D-01) | n8n Cloud (Claude web-research lane) | Anthropic API | Existing `needsResearch()` gap-predicate + research prompt in `wf_enrichment_cloud.json`; no new research code |
| June-vs-fresh conflict check (D-04/D-08) | n8n Cloud (Code node, `mergeCompanies.js`) | — | Deterministic merge/gate logic already lives here; June must enter as a second `mergeCompanies()` invocation or an upstream reconciliation step — **no existing multi-source comparator today** (see Pitfall 3) |
| Write-safety arming (D-06) | operator-claude-plugin (Python, local CLI) | n8n workflow JSON (mutated in place) | `n8n_arming.py` mutates baked JS constants inside the deployed workflow via `PUT /workflows/{id}`; the "arm" is a workflow-content mutation, not a database row |
| Record queueing (`lv_enrichment_requested`) | HubSpot CRM (property write) | n8n SJ-3 poller (read) | Standard property-driven trigger pattern already used for SJ-1/SJ-2/SJ-3 |
| Canonical scoring writes | HubSpot Automation flows (mapper flows + WF1) | n8n (writes canonical `lv_*` inputs only) | Phase 40 already separated "n8n writes inputs" from "HubSpot flows compute score/tier" — this phase's job is only to get inputs written, not to touch scoring flows |
| Auto-score proof (DATA-02) | HubSpot Automation flows (existing, Phase 40) | Parity harness (`scripts/run_scoring_parity.py`) | No new proof machinery; point the existing harness at the imported IDs |
| Pre-flight ID resolution (D-09) | `src/hubspot_client.py` (search/get) | — | Generic `search_records()`/`get_record()` exist; no dedicated batch-read or name/domain convenience wrapper (see Pitfall 5) |

## Standard Stack

No new libraries or packages are introduced by this phase. Everything needed already exists
in the repo:

| Component | Location | Purpose |
|-----------|----------|---------|
| n8n Cloud enrichment workflow | `n8n/wf_enrichment_cloud.json` (built by `scripts/build_cloud_workflows.py`) | The write path DATA-02 must prove fires |
| n8n Cloud scheduled maintenance | `n8n/wf_scheduled_maintenance_cloud.json` | Hosts SJ-3, the 15-min `lv_enrichment_requested` poller |
| Merge/gate logic | `n8n/code/mergeCompanies.js` | Non-clobber merge, provenance blob construction |
| Write-safety overlay | `operator-claude-plugin/scripts/n8n_arming.py`, `n8n_control.py` | D-06's arm/disarm mechanism |
| Batch write helper | `src/hubspot_client.py::batch_update_companies` (100/call cap, `src/hubspot_client.py:95-98`) | Setting `lv_enrichment_requested="true"` on all 66 in ≤1 call |
| Parity harness | `scripts/run_scoring_parity.py`, `tests/scoring_fixtures.py` | D-11's proof vehicle |
| ICP rubric oracle | `src/icp_scoring.py`, `config/icp_scoring.yaml` | What the parity harness compares against |
| Taxonomy source of truth | `config/taxonomy.yaml`, `n8n/code/taxonomy.generated.js` | `lv_org_type`/`lv_content_type` synonym vocabulary D-02's mapping table should reuse, not reinvent |

## Package Legitimacy Audit

Not applicable — no new external packages are introduced by this phase (Python
stdlib/existing `src/hubspot_client.py` primitives and existing n8n/JS code only).

## Architecture Patterns

### System Architecture Diagram

```
../ausgtm-lightningvisuals-data/data/enriched_companies.json  (66 records, static, read once)
        │
        ▼
[Pre-flight: ID resolution]  src/hubspot_client.py (search_records / get_record)
        │  resolve 66 June-era HubSpot IDs against live portal;
        │  dead IDs → re-match by name/domain search; unmatched → skip + report (D-09)
        ▼
[Pre-flight: enum mapping]  deterministic table (Perplexity org_type → lv_org_type)
        │  + hand-curated exception list (D-02) — QRIC-class misfits
        │  produces a per-company "June candidate" row, confidence 85/65/40 (D-03)
        ▼
[Arm]  n8n_arming.arm_for_dispatch(enrichment_workflow_id, record_ids=<66>, ...)
        │  PUTs TEST_RECORD_IDS=<66 ids>, ALLOW_HUBSPOT_RECORD_WRITES=true onto the
        │  deployed "LV Enrichment (Cloud template)" workflow (deactivate→PUT→activate,
        │  handled internally by n8n_control.apply_mutation)
        ▼
[Queue]  batch_update_companies: lv_enrichment_requested="true" on all 66 (≤1 API call, 100/call cap)
        ▼
[SJ-3 poller, every 15 min]  "LV Scheduled Maintenance (Cloud)" workflow
        │  HubSpot search: lv_enrichment_requested=true AND lv_enrichment_status!=running
        │  (default limit=100 — all 66 can match on one tick)
        │  → Extract Rows → Build Dispatch Event (no `providers` key) →
        │    Execute Workflow node, mode="each" (one sub-execution per matched company)
        ▼
[Enrichment sub-execution, per company]  "LV Enrichment (Cloud template)"
        │  Execute Workflow Trigger → Parse HubSpot Event → ... → Company Gate →
        │  needsResearch()? → Claude web-research (org_type/content/veto/geography fields
        │  only — NOT revenue/employee band) → judge.js evidence-sufficiency + optional
        │  Sonnet escalation → mergeCompanies() → write-safety gate → HubSpot PATCH
        │  (canonical `lv_*` inputs + lv_enrichment_provenance blob + 2 verified_at keys)
        ▼
[HubSpot company record]  lv_org_type, lv_produces_content, lv_content_type,
        │  lv_country_region_normalized, lv_is_hardware_vendor, lv_is_gambling_operator,
        │  lv_sponsorship_reliant land; lv_revenue_band/lv_employee_band do NOT land via
        │  this lane (see Pitfall 2)
        ▼
[HubSpot Automation mapper flows, Phase 40's remediated engine]
        │  per-input `*_score` flows → calculated lv_icp_fit_score → WF1 tier ladder
        │  (fires automatically on the property write — this is what DATA-02 proves)
        ▼
[Disarm]  n8n_arming.disarm(enrichment_workflow_id, config) — verified re-read
        ▼
[Proof]  scripts/run_scoring_parity.py  PARITY_SAMPLE_IDS=<66 ids> PARITY_REPORT_DIR=<phase 41 dir>
        │  asserts live lv_icp_fit_score/lv_icp_tier == compute_icp_score(props) per record
        ▼
Committed JSON verdict + run report (D-11/D-12)
```

### Recommended Project Structure (new artifacts this phase is likely to add)

```
scripts/
├── (new) build_june_candidates.py   # or similar — reads enriched_companies.json,
│                                     #   applies D-02 mapping table + confidence (D-03),
│                                     #   emits per-company June candidate rows
├── (existing) run_scoring_parity.py # reused unmodified via PARITY_SAMPLE_IDS
.planning/phases/41-validation-data-import-end-to-end-proof/
├── (new) run-report.{md,json}       # D-12's run report — location is Claude's discretion
├── (new) parity-report-*.json       # D-11's verdict, via run_scoring_parity.py
```

### Pattern 1: Direct arm/disarm (not `armed_window`) for D-06's whole-run style

**What:** Call `n8n_arming.arm_for_dispatch()` once with all 66 IDs, do NOT wrap it in
`armed_window`/`control_actions.arm_dispatch`. Let SJ-3's own scheduled tick perform the
writes across however many 15-min cycles it takes. Call `n8n_arming.disarm()` once at the end.

**Why this works without a new dispatch mechanism:** `scheduled_arm.py`'s own docstring
establishes that SJ-3's internal `Execute Workflow` dispatch **keeps running on its own
15-min schedule regardless of anything external** (`operator-claude-plugin/scripts/
scheduled_arm.py:44-54`) — it only reports `write_blocked` when the enrichment workflow isn't
armed at the moment SJ-3 ticks. If the workflow is left armed continuously (D-06's chosen
approach), SJ-3's own tick succeeds on its own; no re-dispatch companion (`scheduled_arm.py`)
is needed at all for this phase.

**Example (illustrative shape, not a verified working script — someone must write and test
this against the real config-loading/transport wiring in `operator-claude-plugin/scripts/`):**
```python
# Source: operator-claude-plugin/scripts/n8n_arming.py:264-363, 366-415
import n8n_arming, config_gate, executions_client
cfg = config_gate.load_config()
workflow_id = executions_client.resolve_workflow_id(
    cfg, workflow_name="LV Enrichment (Cloud template)")  # scripts/build_cloud_workflows.py:4930
result = n8n_arming.arm_for_dispatch(
    workflow_id, record_ids=[...66 ids...], record_domains=[], allow_create=False, config=cfg)
# ... wait across poller cycles, monitor via executions_client / backend_status ...
disarm_result = n8n_arming.disarm(workflow_id, cfg)
```
Requires `ALLOW_N8N_ARM=true` set in the operator's shell for both calls
(`operator-claude-plugin/scripts/n8n_arming.py:178,203-221`) — Claude must hand the operator
the literal command, never set this itself.

### Pattern 2: Queueing 66 records for the SJ-3 poller

**What:** `batch_update_companies` (`src/hubspot_client.py:88-118`) caps at 100 updates per
call (`src/hubspot_client.py:95-98`) — all 66 fit in one call. Boolean values must be the
literal strings `"true"`/`"false"` (known landmine, confirmed live pattern throughout
`n8n/code/*.js` and `config/hubspot_properties.yaml`'s `booleancheckbox` options blocks, e.g.
`config/hubspot_properties.yaml:185-189`).

### Pattern 3: SJ-3's search has no explicit record-per-run cap

**What:** `SJ-3 Search (requested poller)` uses `_hs_http_search_node(..., limit=100)` (the
default — no explicit override at the call site, `scripts/build_cloud_workflows.py:5644-5650`
vs. the helper's default `limit=100` at `scripts/build_cloud_workflows.py`'s
`_hs_http_search_node` signature). 66 < 100, so **the entire population can match on a single
SJ-3 tick** — there is no need to release the 66 in smaller batches to respect a poller-side
cap. The known "2-per-request cap" (`ENRICH_MAX_LIST_RECORDS = 2`,
`scripts/build_cloud_workflows.py:3540`) governs a **different** entry point (list-based or
direct-record-id dispatch through the webhook's `Parse HubSpot Event` node,
`MAX_WRITE_EVENTS = __MAX_LIST_RECORDS__` at `scripts/build_cloud_workflows.py:3463`) and does
not bind SJ-3's path in practice, because SJ-3's `Execute Workflow` node runs in `mode:
"each"` (`scripts/build_cloud_workflows.py:3931-3932` node type definition;
`_execute_workflow_node`'s `"mode": "each"`) — one sub-execution per matched company, so each
sub-execution's `Execute Workflow Trigger → Parse HubSpot Event` hop only ever sees a single
event, never near the 2-event ceiling.

### Anti-Patterns to Avoid

- **Assuming the plugin's local-MVP `CLAUDE.md` design (`ALLOW_CANONICAL_WRITES`,
  per-field `*_source` properties, `main.py`, `src/merge_policy.py`) is what runs in
  production.** That design is real code in this repo (`src/merge_policy.py`,
  `src/web_research.py`, etc.) but D-05 explicitly rejects the local Python path. The gate
  names, provenance shape, and write mechanics that actually govern this phase's run are the
  **cloud** ones (`ALLOW_HUBSPOT_RECORD_WRITES`, `TEST_RECORD_IDS`,
  `lv_enrichment_provenance`), documented above.
- **Reusing `scripts/scheduled_arm.py` verbatim.** It implements a *different*, narrower
  arming style (per-cycle bounded windows) than D-06 explicitly chose. It's a good reference
  for the arm/disarm/verify pattern but should not be invoked as-is for this phase.
- **Expecting the Claude web-research lane to populate `lv_revenue_band`/
  `lv_employee_band`.** It structurally does not (see Pitfall 2).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Write-safety arm/disarm/verify | A new script that PUTs raw n8n workflow JSON | `n8n_arming.arm_for_dispatch` / `disarm` (direct calls, not via `armed_window`) | Already handles deactivate→PUT→verify→re-activate bounce (`n8n_control.py:279-360`), fail-closed re-scan, and allowlist charset validation |
| Score/tier computation | Any pipeline-side scoring code | HubSpot Automation flows (Phase 40) | `src/icp_scoring.py` is oracle-only per `REQUIREMENTS.md` Out of Scope table; scoring stays HubSpot-resident |
| Live-vs-oracle comparison | A new diff script | `scripts/run_scoring_parity.py` with `PARITY_SAMPLE_IDS` | Already read-only, already writes a JSON verdict, already guards against a false-green empty-sample result |
| Org-type/content-type vocabulary | A fresh enum list for the mapping table | `config/taxonomy.yaml` (the NORMATIVE source, `config/taxonomy.yaml:1-19`) | Already carries synonym lists — e.g. `regulator: [regulatory body, commission, integrity body]` (`config/taxonomy.yaml:75-80`) directly matches "Queensland Racing Integrity Commission"'s name text, which is a stronger, reusable signal for the exception list than a hand-typed one-off |

**Key insight:** every mechanism this phase needs (arming, dispatch, merge, provenance,
scoring, parity) already exists and is already tested elsewhere in this repo. The work is
almost entirely **data preparation** (66-row mapping table) and **orchestration sequencing**
(arm → queue → wait → disarm → prove), not new pipeline code.

## Common Pitfalls

### Pitfall 1: Confusing the two "provider spend" surfaces
**What goes wrong:** Assuming a config flag (`ALLOW_PROVIDER_CALLS`, `USE_MOCK_PROVIDERS`)
needs to be set for zero spend.
**Why it happens:** Those flags are real, live in `CLAUDE.md`'s described local-MVP
(`src/providers.py`), and easy to conflate with the cloud pipeline.
**How to avoid:** The cloud pipeline's provider waterfall is gated by the `providers` key on
the dispatch event (`operator-claude-plugin/scripts/enrichment.py:8-16`,
`scripts/build_cloud_workflows.py:3486-3488`). SJ-3's dispatch event never sets this key
(`scripts/build_cloud_workflows.py`'s `ENRICH_SJ3_BUILD_DISPATCH_EVENT`) — zero spend is
automatic on this path, nothing to configure.
**Warning signs:** A plan task that says "set `ALLOW_PROVIDER_CALLS=false`" — that flag does
not exist in the cloud builder (verified: no match for `ALLOW_PROVIDER_CALLS` anywhere in
`scripts/build_cloud_workflows.py`).

### Pitfall 2: `lv_revenue_band` and `lv_employee_band` have no populating mechanism in this run
**What goes wrong:** D-07 lists `lv_revenue_band` and `lv_employee_band` among the nine
canonical-write-scope fields, but the Claude web-research lane's `required_fields` list
excludes both (`scripts/build_cloud_workflows.py:2002-2004`) — the model only returns a
free-text `entity_resolution.likely_revenue_band` hint
(`scripts/build_cloud_workflows.py:1974-1975`), which is never copied into the `data` object
that becomes a merge candidate. The research gap-predicate (`needsResearch()`,
`scripts/build_cloud_workflows.py:1949-1958`) also never checks for a missing revenue/employee
band, so research is never triggered for that reason either.
**Why it happens:** Firmographics (revenue, employee count) were designed to come from paid
providers (ZoomInfo/Apollo/Lusha), which this run deliberately excludes.
**How to avoid:** These two fields will land, if at all, **only** via the June pseudo-provider
(D-08) — mapping June's free-text `employee_estimate` (values observed: `"200-500"`,
`"500+"`, `"50-100"`, `"10-50"`, `"1000+"`, etc. — verified across all 66 records) onto the
live `lv_employee_band` enum (`"1-9"|"10-50"|"51-200"|"201-500"|"501-1000"|"1001+"|"Unknown"`,
`config/hubspot_properties.yaml:78-108`). Note the boundary mismatch: June's `"200-500"` and
`"500+"` bands do not align cleanly with HubSpot's `201-500`/`501-1000`/`1001+` cut points —
this needs an explicit, documented rounding rule if the plan wants `lv_employee_band` to land
at all. June has **no revenue signal whatsoever** (confirmed: `enriched_companies.json`'s
union of all keys across 66 records is `[confidence, employee_estimate, evidence, hq_country,
id, is_australia, is_sports, name, org_type, produces_broadcast_or_streaming_content,
sources, sponsorship_reliant]` — no revenue field) — `lv_revenue_band` structurally cannot
populate from either source this phase controls. `lv_revenue_band` does feed the ICP score
(`config/icp_scoring.yaml:29-38`); `lv_employee_band` does not feed the score at all (absent
from `config/icp_scoring.yaml`'s `base_score` block — confirmed by reading the full file).
**Warning signs:** A plan step that assumes revenue/employee bands "come from research" like
the other seven fields.

### Pitfall 3: No existing multi-source conflict comparator for D-08's "pseudo-provider"
**What goes wrong:** `mergeCompanies(existingProps, candidateRow, fieldPolicy, opts)`
(`n8n/code/mergeCompanies.js:167-256`) takes ONE flat `candidateRow` and ONE
`opts.source`/`opts.confidence` per call — it is not designed to receive two competing
candidate sets (fresh Claude research vs. June pseudo-provider) in a single invocation and
detect disagreement between them. `judge.js`'s escalation logic
(`n8n/code/judge.js:1-60`+) operates on a single research candidate's evidence sufficiency,
not on cross-source comparison either.
**Why it happens:** The pipeline's provider waterfall (ZoomInfo/Apollo/Lusha) *is* designed
for multi-source input, but that machinery lives in `normalizeProviders.js`/`providerSelection.js`
— not verified in this session whether those modules are wired into the *company* enrichment
lane's research path at all, or only the contact lane's provider waterfall. This needs
direct verification before the plan commits to "the existing conflict machinery adjudicates
naturally" (D-04's framing) — that framing may require **new** wiring, not just a new
candidate row.
**How to avoid:** Before planning D-08's mechanics in detail, read `normalizeProviders.js`
and the companies branch of `scripts/build_cloud_workflows.py`'s `COMPANIES_TARGET` /
`EnrichTarget` machinery end-to-end to confirm whether a second candidate source can be
injected pre-merge (so `mergeCompanies` sees a merged candidate row and conflicting fields
naturally route to `needs_review` via existing confidence/gate logic) or whether the
comparison must happen as a **separate step** that runs both June and fresh-research
candidates through `mergeCompanies` independently and diffs the two `canonicalPatch` outputs
before writing — the latter is a new (small) piece of logic, not existing machinery.
**Warning signs:** A plan task worded as "inject June as a provider" without a named node/
function that actually consumes two sources for the same field in one decision.

### Pitfall 4: `mode: "each"` throughput is unverified for 66 sequential sub-executions
**What goes wrong:** SJ-3's `Execute Workflow` node runs in `mode: "each"`
(`scripts/build_cloud_workflows.py:3931-3932`), meaning one sub-execution per matched company.
Whether n8n Cloud processes those 66 sub-executions **sequentially within one SJ-3 parent
execution** (each waiting for the last to finish) or with concurrency is **not verified in
this session** — n8n's Execute Workflow node version-specific wait/concurrency semantics were
not confirmed against n8n's own docs or a live trace. Given ~82% of a full enrichment run is
two sequential Anthropic calls (documented in `CONTEXT.md`'s `code_context`, sourced from
`2026-08-04-enrichment-throughput-ceiling.md`), 66 sequential sub-executions inside one SJ-3
tick could take a long time (tens of minutes) and risk n8n Cloud's own execution-duration
limits.
**Why it happens:** This is architecture no one has driven at N=66 before — Phase 40 proved
the write path on N=1 real record (Melbourne Racing Club, `~11s`, but that was a
component-score *backfill* PATCH, not a full research-lane enrichment run —
`.planning/phases/40-scoring-engine-remediation-notes/40-07-SUMMARY.md:155-156`).
**How to avoid:** D-10's canary-then-rest ramp (~5 records first) is the right mitigation —
treat the canary explicitly as a throughput probe, not just a correctness probe. Watch the
SJ-3 execution in n8n's UI/API (`operator-claude-plugin/scripts/executions_client.py`) during
the canary to observe whether all 5 land in one SJ-3 execution or split across ticks, and
extrapolate wall-clock for the remaining 61 from that, before committing to a specific armed
window duration in the plan.
**Warning signs:** A plan step that assumes "all 66 process within one 15-min cycle."

### Pitfall 5: No existing batch-ID-resolution helper
**What goes wrong:** `src/hubspot_client.py` has `get_record` (singular), `search_records`
(generic filters, `limit=100` default), and `batch_update_companies` (writes only, 100/call
cap) — but no batch-read-by-ID helper (`src/hubspot_client.py:1-119`, full function list:
`hs_headers`, `get_record`, `patch_record`, `create_record`, `delete_record`,
`batch_update_companies`, `search_records`). Resolving 66 IDs against the live portal will
need either 66 sequential `get_record` calls or one `search_records` call with a
`hs_object_id IN [...]` filter (HubSpot CRM Search API supports the `IN` operator for this,
not verified against this specific wrapper's filter-building code in this session).
**How to avoid:** Plan a small pre-flight script (or extend `hubspot_client.py`) rather than
assuming a ready-made batch-read function exists.

### Pitfall 6: `.env` is permission-blocked — every token-bearing command must be handed to the operator
**What goes wrong:** Claude cannot `Read` or `Bash`-cat `.env` in this environment (documented
project-wide finding, `env-file-permission-blocked` memory). Any script requiring
`HUBSPOT_PRIVATE_APP_TOKEN`, `ANTHROPIC_API_KEY`, or `ALLOW_N8N_ARM` must be handed to the
operator as a literal `!`-prefixed shell command, never executed directly by Claude.
**How to avoid:** Every plan task that touches arming, dispatch, or the parity harness's live
tier must end with "hand the operator this exact command" rather than "run this command."

## Code Examples

### Existing SJ-3 poller search filter (verbatim)
```javascript
// Source: scripts/build_cloud_workflows.py:5645-5650
sj3_search = _hs_http_search_node(
    "SJ-3 Search (requested poller)", "company", x, y,
    filter_groups=[[
        {"propertyName": "lv_enrichment_requested", "operator": "EQ", "value": "true"},
        {"propertyName": "lv_enrichment_status", "operator": "NEQ", "value": "running"},
    ]],
    properties_csv="hs_object_id,lv_enrichment_requested,lv_enrichment_status")
```

### Existing write-safety allowlist gate (verbatim, the gate this phase's arm targets)
```javascript
// Source: scripts/build_cloud_workflows.py:917-934
function _writeSafetyAllows(action, hsObjectId, domain) {
  if (action === "review") {
    if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
  } else {
    if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
    if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
  }
  const allowedDomains = String(TEST_RECORD_DOMAINS).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowedDomains.length && !allowedIds.length) return false;  // empty allowlist denies everything
  if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
  if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
  return false;
}
```

### Existing taxonomy synonym vocabulary (verbatim, reusable for D-02's exception list)
```yaml
# Source: config/taxonomy.yaml:75-80
regulator:
  score: 5
  requires_evidence: false
  synonyms:
    - regulatory body
    - regulator authority
    - commission
    - integrity body
```
"Queensland Racing Integrity Commission"'s name text contains both "commission" and
"integrity" — directly matching two of these synonyms, independent of the D-02 hand-curated
exception list. This is corroborated by `judge.js`'s own comment naming QRIC as a real,
already-known example (`n8n/code/judge.js:15`: *"an evidenced `false` claim (e.g. QRIC) is a
DIFFERENT judgement"*).

### Existing parity harness invocation contract (verbatim env-var contract)
```python
# Source: scripts/run_scoring_parity.py:19-26
# Env vars:
#     PARITY_SAMPLE_IDS  Comma-separated real company ids to check. If unset, ids are
#                         selected via a HAS_PROPERTY search on lv_icp_fit_score.
#     PARITY_REPORT_DIR  Directory the JSON verdict report is written to. Defaults to
#                         .planning/phases/40-scoring-engine-remediation-notes/.
#
# `.env` is Read/Bash permission-blocked this session — the operator invocation is:
#     .venv/bin/python -c \
#         "from dotenv import load_dotenv; load_dotenv(); import runpy; \
#          runpy.run_path('scripts/run_scoring_parity.py', run_name='__main__')"
```
For DATA-02/D-11, hand the operator:
```bash
PARITY_SAMPLE_IDS=<comma-separated 66 resolved ids> \
PARITY_REPORT_DIR=.planning/phases/41-validation-data-import-end-to-end-proof/ \
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; \
runpy.run_path('scripts/run_scoring_parity.py', run_name='__main__')"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Local Python MVP (`main.py`, `src/merge_policy.py`, per-field `*_source` provenance properties, `ALLOW_CANONICAL_WRITES`/`ALLOW_STAGING_WRITES` env gates) | n8n Cloud pipeline (`n8n/code/mergeCompanies.js`, single `lv_enrichment_provenance` blob, `ALLOW_HUBSPOT_RECORD_WRITES`/`TEST_RECORD_IDS` gates) | Sometime before Phase 40 (exact phase not identified this session) | The project's `CLAUDE.md` describes the superseded local design; this phase must build against the cloud design documented here, not the CLAUDE.md skeleton |
| SJ-3 dispatched via a webhook-only entry point ("Missing node to start execution", WINDOWS.md #3) | SJ-3 dispatches via a dedicated `Execute Workflow Trigger` entry point feeding straight into `Parse HubSpot Event` | Phase 40 (`scripts/build_cloud_workflows.py:5656` comment: "fix(40) / WINDOWS.md #3") | SJ-3's internal dispatch now actually reaches the enrichment workflow — a precondition this phase's whole D-05/D-06 design depends on |
| `ALLOW_HUBSPOT_RECORD_WRITES` baked `false` at every build, no live writes possible at all | Confirmed live-writable via the arm/disarm overlay, proven on a real record | Phase 40-05 (`STATE.md` Decisions, "VETO-WRITE-EVIDENCE.md" entry) | This phase's write path is now provably unblocked, not still gated behind the WINDOWS.md #2 blocker |

**Deprecated/outdated:** the `CLAUDE.md` §4-§30 local-MVP design (schemas, `field_policy.yaml`
class names like `ALLOW_CANONICAL_WRITES`) should be treated as historical/reference design
intent, not the operative contract for this phase's plan.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot CRM Search API's `IN` operator works for resolving 66 `hs_object_id`s in one `search_records()` call | Pitfall 5 | Pre-flight ID resolution plan step may need 66 sequential GETs instead of 1 search call — larger but not blocking |
| A2 | n8n's `Execute Workflow` node in `mode: "each"` processes sub-executions sequentially within one parent execution (not concurrently) | Pitfall 4 | If concurrent instead, 66-record wall-clock could be much shorter than estimated — not harmful, just a planning-margin overestimate |
| A3 | `normalizeProviders.js`/`providerSelection.js` company-lane wiring supports injecting a second (non-Claude-web) research candidate for the same record in one enrichment pass | Pitfall 3 | If not, D-08's pseudo-provider needs a standalone comparison step outside `mergeCompanies`, not "the existing conflict machinery" as CONTEXT.md's D-04 framing implies — a real design decision the planner must make explicitly rather than assume is free |
| A4 | HubSpot CRM Search API accepts a 66-element allowlist comma-joined into `TEST_RECORD_IDS` without a length/size limit on that JS string constant | Pattern 1 | `_render_literal`/`_ALLOWLIST_VALUE_RE` (`n8n_arming.py:71,81-97`) enforce a charset but not a length cap — untested at 66 IDs' string length (likely ~700-800 chars, well within any reasonable n8n Code-node string limit, but not verified live) |

**If this table is empty:** not applicable — see entries above.

## Open Questions

1. **Does the company enrichment lane's research pass currently accept more than one
   candidate source per record, or is `mergeCompanies()` always called with exactly one
   `opts.source`?**
   - What we know: `mergeCompanies(existingProps, candidateRow, fieldPolicy, opts)`'s
     signature takes one `opts.source`/`opts.confidence` per call
     (`n8n/code/mergeCompanies.js:167-183`).
   - What's unclear: whether the wrapping n8n workflow calls this function multiple times per
     record (once per source, accumulating) or once with a single already-reconciled
     candidate row.
   - Recommendation: read `COMPANIES_TARGET`'s validate/merge stage end-to-end
     (`scripts/build_cloud_workflows.py`, the `EnrichTarget` dataclass instance around line
     1946 and its downstream node wiring) before finalizing D-08's injection mechanics in the
     plan.

2. **What is the actual wall-clock for one SJ-3 tick processing N=5 (the canary), and does it
   scale linearly to N=61?**
   - What we know: ~82% of a full run is two sequential Anthropic calls (per-record cost
     ~$0.0686, `CONTEXT.md` code_context); Phase 40's one real-record write (a scoring
     backfill, not a full research pass) settled in ~11s.
   - What's unclear: whether `mode: "each"` serializes 5+ sub-executions inside one SJ-3
     parent execution, and whether n8n Cloud enforces any execution-duration ceiling that a
     66-record serialized run could hit.
   - Recommendation: treat D-10's canary explicitly as a throughput probe (Pitfall 4) and let
     its observed timing set the plan's expectation for the remaining 61, rather than
     estimating in advance.

3. **What exactly counts as "dead ID" for D-09's re-match branch, and how many of the 66 are
   expected to hit it?**
   - What we know: nothing — no live HubSpot query was run this session (`.env` blocked, no
     credentials available to this research agent).
   - What's unclear: the actual live/dead split among the 66 June-era IDs.
   - Recommendation: the pre-flight ID-resolution step is itself the answer; the plan should
     not try to estimate this in advance.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud API access (`N8N_API_KEY` or equivalent) | Arm/disarm, execution monitoring | Not verified this session (`.env` blocked) | — | Operator must confirm before the plan's arm step; hand operator a `!` command to check |
| `ALLOW_N8N_ARM=true` | `n8n_arming.arm_for_dispatch`/`disarm` | Operator-set only, per-shell, never by Claude | — | None — this is the deliberate kill switch (`n8n_arming.py:203-221`) |
| HubSpot private-app token | ID resolution, batch write, parity harness | Not verified this session (`.env` blocked) | — | None — hard dependency, hand operator the exact `!` command |
| `.venv` (Python) with `pyyaml`, `python-dotenv`, `requests` etc. | `scripts/run_scoring_parity.py`, pre-flight scripts | Assumed present (used throughout Phase 40 per `40-07-SUMMARY.md`) | — | — |

**Missing dependencies with no fallback:** live HubSpot/n8n credential availability was not
directly verified this session — the executing agent/operator must confirm before the plan's
first live-writing task runs.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`.venv/bin/python -m pytest`) |
| Config file | none dedicated — repo-root `tests/` package, existing `tests/scoring_fixtures.py` |
| Quick run command | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k "not live"` (offline tier, no `RUN_LIVE_PARITY` set) |
| Full suite command | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py` (live tier, create/exercise/delete disposables — D-13 precedent) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | 66 companies land with `lv_*` inputs + provenance at zero provider spend | read-only live check | `scripts/run_scoring_parity.py` (repurposed: reads `lv_enrichment_provenance` presence, not just score parity — may need a small extension) | ✅ harness exists; ❌ a "provenance stamped" assertion is not currently part of it — Wave 0 gap |
| DATA-02 | Imported companies score automatically, no per-record manual touch | live integration | `PARITY_SAMPLE_IDS=<66 ids> scripts/run_scoring_parity.py` | ✅ exists, reusable as-is per its own contract |

### Sampling Rate
- **Per task commit:** offline pytest tier (`-k "not live"`) — free, no HubSpot/Anthropic cost
- **Per canary (D-10):** live parity check against the ~5 canary IDs before releasing the
  remaining 61
- **Phase gate:** full `run_scoring_parity.py` sweep over all successfully-landed IDs before
  closing DATA-02

### Wave 0 Gaps
- [ ] `scripts/run_scoring_parity.py` currently asserts score/tier/veto parity only
  (`tests/scoring_fixtures.py::expected_for`) — it does not check `lv_enrichment_provenance`
  presence/shape. If DATA-01's "provenance stamped" bar needs an automated check (rather than
  a manual spot-check in the run report), this is a small addition, not a new harness.
- [ ] No existing script builds the 66-row "June candidate" table (D-02/D-03) from
  `enriched_companies.json` — this is net-new, scoped entirely to this phase.
- [ ] No existing script resolves/re-matches the 66 IDs against the live portal (D-09) — net
  new, small (`src/hubspot_client.py` primitives are sufficient building blocks).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No new auth surface — reuses existing HubSpot private-app token and n8n API credential |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes | The write-safety allowlist gate (`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS`, `_writeSafetyAllows`, `scripts/build_cloud_workflows.py:917-934`) is exactly an access-control mechanism scoping writes to a named record set — this phase's whole safety model rests on it being armed correctly and disarmed reliably |
| V5 Input Validation | Yes | `_ALLOWLIST_VALUE_RE` (`n8n_arming.py:71`) enforces a restrictive charset on the allowlist string to prevent a value that could split the declaration line the fail-closed re-scan depends on |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arm window left open indefinitely (operator forgets to disarm) | Elevation of Privilege | `n8n_arming.disarm()`'s independent re-read verification (`n8n_arming.py:366-415`); plan should explicitly schedule/remind the disarm step as its own checkpoint, not assume it happens |
| Allowlist string injection via a malformed record ID | Tampering | `_ALLOWLIST_VALUE_RE` charset enforcement (already in place, no new work needed) |
| Partial rewrite leaving the workflow in an inconsistent armed/disarmed state | Tampering / Denial of Service | `set_write_safety`'s fail-closed re-scan (`n8n_arming.py:141-159`) — already handles this |

## Sources

### Primary (HIGH confidence — read directly this session)
- `.planning/phases/41-validation-data-import-end-to-end-proof/41-CONTEXT.md` — locked decisions
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — requirement wording, Phase 40 outcomes
- `.planning/phases/40-scoring-engine-remediation-notes/40-CONTEXT.md` — Phase 40 decisions this phase consumes
- `../ausgtm-lightningvisuals-data/data/enriched_companies.json` — the 66-record dataset (full field-coverage audit run this session)
- `../icp-analysis/enrich.mjs` — how the dataset was produced
- `docs/business/icp-scoring.md` — QRIC/Supertech/Simtech/Sportsbet/Entain named misfits
- `scripts/build_cloud_workflows.py` (SJ-3, write-safety gate, research prompt, `_hs_http_search_node`, `_execute_workflow_node`, `ENRICH_MAX_LIST_RECORDS`)
- `n8n/code/mergeCompanies.js` (`DEFAULT_COMPANY_POLICY`, `mergeCompanies()` signature and body)
- `n8n/code/judge.js` (evidence sufficiency, QRIC reference)
- `operator-claude-plugin/scripts/n8n_arming.py`, `n8n_control.py`, `chunking.py`, `scheduled_arm.py`
- `src/hubspot_client.py` (all functions enumerated)
- `config/icp_scoring.yaml`, `config/taxonomy.yaml`, `config/field_policy.yaml`, `config/source_registry.yaml`, `config/hubspot_properties.yaml`
- `scripts/run_scoring_parity.py`, `tests/scoring_fixtures.py`
- `docs/OPERATOR-VETO-REFRESH.md`

### Secondary (MEDIUM confidence)
- `.planning/phases/40-scoring-engine-remediation-notes/40-07-SUMMARY.md` (~11s latency citation)

### Tertiary (LOW confidence / unverified — flagged in Assumptions Log and Open Questions)
- n8n `Execute Workflow` node `mode: "each"` sequential-vs-concurrent semantics (not verified against n8n docs or a live trace)
- Whether the company research lane's merge stage supports multi-source candidate injection (`normalizeProviders.js`/`providerSelection.js` company-lane wiring not read this session)
- HubSpot CRM Search API `IN` operator support for `hs_object_id` batch resolution (not tested live)

## Metadata

**Confidence breakdown:**
- Standard stack / architecture: HIGH — every gate, node, and property cited was read directly this session with file:line references
- Pipeline mechanics (arming, queueing, provenance shape): HIGH — cross-verified across `n8n_arming.py`, `build_cloud_workflows.py`, and `config/hubspot_properties.yaml`
- Wall-clock/throughput for 66 records: MEDIUM-LOW — no live trace available this session; recommend treating D-10's canary as the actual measurement
- Multi-source conflict architecture for D-08: MEDIUM — a real gap was found (no existing multi-candidate `mergeCompanies` call site confirmed) that the planner must resolve as a design decision, not assume is already handled

**Research date:** 2026-08-07
**Valid until:** 14 days (fast-moving — this phase's own execution will change the pipeline's live-tested state; re-verify write-safety gate values immediately before arming if more than a few days elapse)
