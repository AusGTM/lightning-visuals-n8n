# Phase 40: Scoring Engine, Veto & Parity Remediation - Research

**Researched:** 2026-08-06
**Domain:** HubSpot Automation v4 API (workflow/flow mutation) + calculated-property formulas + n8n pipeline veto ownership + pytest parity harness
**Confidence:** MEDIUM — the remediation *targets* (F1–F10) are HIGH confidence (live-validated, HANDOVER §10.2); the HubSpot Automation v4 API's write behavior is MEDIUM (confirmed from official docs + community threads, not yet round-tripped against this portal's actual flow JSON)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `lv_anti_icp_flag` / `lv_anti_icp_reason` are written by the **n8n pipeline
  only**. The Geography flow's veto branch (today's only live writer, and the F4 AU-spelling
  bug) is deleted; no HubSpot workflow touches the flag after remediation. The pipeline
  derives the veto deterministically from canonical inputs (`lv_country_region_normalized`,
  `lv_produces_content`, `lv_is_hardware_vendor`). Honors HANDOVER §5 decision 2 literally.
  Reversibility: costly.
- **D-02:** Stale-flag policy: a manual property fix in HubSpot leaves the flag stale
  **until the next enrichment run** — accepted. Refresh path: operator sets
  `lv_enrichment_requested="true"`, 15-min poller picks it up. VETO-02 is satisfied via that
  path — plan must document this operator procedure explicitly.
- **D-03:** F8 fix target: a sub-15 score **without** a veto grades **Unscored** — matching
  the parity oracle `src/icp_scoring.py` exactly. D stays veto-only.
- **D-04:** P2/P4 latent bugs close in this phase, before the pipeline veto write goes live:
  real `min_confidence` threshold (~80) for `lv_anti_icp_flag`/`lv_anti_icp_reason` in
  `n8n/code/mergeCompanies.js`, and coerce booleans to `"true"`/`"false"` strings before they
  reach `canonicalPatch` (same fix pattern as 36-07).
- **D-05:** Workflow fixes are **API-driven with flow JSON in the repo**: `GET
  /automation/v4/flows/{id}`, fix JSON in repo, apply via PUT (automation scope granted).
  Snapshot before/after. Portal-UI hand-edit is the fallback only for what the API rejects.
- **D-06:** Keep the existing component architecture — per-input `*_score` mapper flows +
  calculated sum + tier workflow. F1 fixed by **adding** a `produces_content_score` property +
  mapper flow + a new calculated-sum formula term. 5 components total. No consolidation.
- **D-07:** Change-safety protocol: **disable each flow, apply the edit, validate on
  disposable `ZZ-SCORING-TEST-DELETE-ME-*` companies, then re-enable**.
- **D-08:** Execution: **Claude executes flow PUTs directly in-session** — no armed/disarmed
  script gate for the flow mutations. D-07's protocol is the safety envelope.
- **D-09:** Scope split: Phase 40 **builds and proves the backfill mechanism on a small
  sample** (fixtures + a few real records — doubles as PARITY-01's real-record sample); the
  portfolio-wide run belongs to **Phase 41**.
- **D-10:** Backfill trigger mechanism: **batch-seed the component scores** — batch PATCH
  writes `org_type_score`/`geography_score`/`annual_revenue_score`/`produces_content_score`
  computed from each record's current inputs (0 where missing). No reliance on unverified
  same-value re-enrollment behavior.
- **D-11:** Parity harness form: **both layers** — `tests/` pytest module (fixtures
  parametrized from `config/icp_scoring.yaml`, oracle = `compute_icp_score`, live HubSpot
  calls behind an opt-in marker) **plus** a thin `scripts/` wrapper that runs the sweep and
  writes a JSON verdict report.
- **D-12:** Standing cadence: **two-tier** — script wrapper does a cheap **read-only pass on
  the real-record sample** on the unattended sweep cadence; the **full fixture run**
  (create/exercise/delete disposables) stays on-demand, run before/after any rubric or flow
  change.
- **D-13:** Veto regression coverage (F4/F7 named cases): **live end-to-end only** — drive
  full enrichment runs against disposable companies and assert final
  `lv_anti_icp_flag`/`lv_icp_tier` state. No offline node-driver substitute. Cost accepted,
  belongs to the on-demand full tier (D-12) only.

### Claude's Discretion
- `lv_anti_icp_reason` string format/content (derive from `config/icp_scoring.yaml`
  hard-veto reason strings).
- Exact `min_confidence` value for the veto fields (~80 suggested, not locked).
- Revenue-branch boundary encoding in flow JSON (exclusive bounds vs re-ordering) — must
  produce rubric-exact results at 500M/750M/1B/1.2B boundaries (ENGINE-04).
- Real-record sample size/selection for PARITY-01.
- Flow-JSON storage location in repo and snapshot naming.
- Batch sizes / rate handling for the backfill seed mechanism.

### Deferred Ideas (OUT OF SCOPE)
- "Sweep re-notifies a fixed failure until 100 executions displace it" — sweep concern,
  outside scoring scope.
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep" — same;
  backlog.
- "Enrichment throughput — 82% of every full run is two sequential Anthropic calls" —
  pipeline performance, not scoring correctness.
- "UAT 2.2 names two header aliases the column mapping does not support" — contact-upload
  concern.
- No mass backfill of the 712 existing companies (mechanism only; portfolio-wide run is
  Phase 41). No rubric-weight changes. No lead-scoring-tool build.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| ENGINE-01 | Company with governing_body_league + content + AU + 50-500M scores 80/A entirely in HubSpot, reading only canonical inputs | Architecture Patterns (system diagram, F1/F2/F3 fix shape); Pitfall 5; Environment Availability (Properties API) |
| ENGINE-02 | `lv_produces_content=true` contributes +20 | D-06's `produces_content_score` component pattern; Pitfall 3 (formula PATCH risk) |
| ENGINE-03 | Scoring reads canonical `lv_country_region_normalized`/`lv_revenue_band`, never native `country`/`annualrevenue` | Flow-retarget pattern (F2/F3) in Architecture Patterns Pattern 1; Anti-Patterns (config/hubspot_properties.yaml gap) |
| ENGINE-04 | Revenue decay exact at boundaries (750M → −15) | Pitfall 2 (IS_BETWEEN branch-edit risk, highest-risk single task); Validation Architecture test map |
| ENGINE-05 | Gambling deduction −20 via `lv_is_gambling_operator`, never sets veto | Pattern 2 (veto derivation excludes gambling by design — only 3 hard-veto inputs); Validation Architecture |
| ENGINE-06 | Org-type points match config exactly, incl. regulator=5 | Flow-fetch-and-fix pattern (Pattern 1); enum sweep test in Validation Architecture |
| ENGINE-07 | Score <15 without veto does not grade D | D-03 confirmed already matches oracle behavior (`src/icp_scoring.py:101-110`, read this session) — WF1 fix must match, Pitfall 5 (Unscored enum-option check) |
| VETO-01 | All 3 hard vetoes set flag+reason | Pattern 2 (full veto-derivation code example, ported from `src/icp_scoring.py:84-97`) |
| VETO-02 | Correcting clears flag+reason, no one-way latch | Pattern 2 (recomputed every `ENRICH_DECIDE_CO_CLOUD` run — not a latch by construction); D-02 refresh-path documentation requirement |
| VETO-03 | Flag change updates tier without unrelated score change | Architecture diagram (WF1 trigger note: "lv_anti_icp_flag known, F7"); this is a HubSpot-side WF1 enrollment-criteria edit, not pipeline-side |
| PARITY-01 | Harness asserts fixtures + real-record sample against live scores | Code Examples (parity assertion shape); Validation Architecture full test map; D-09/PARITY-01 sample-reuse note |
| PARITY-02 | F4/F7/F9/F10 encoded as named regression cases | Validation Architecture test map (`-k` selectors named per defect); D-13 live-only constraint carried through |

</phase_requirements>

## Summary

This phase closes ten live-validated defects (F1–F10) across four already-existing HubSpot
company workflows, moves `lv_anti_icp_flag`/`lv_anti_icp_reason` ownership fully onto the n8n
pipeline (deleting the one HubSpot-side writer), and lands a two-tier pytest parity harness that
asserts HubSpot's live scores against `src/icp_scoring.py`'s `compute_icp_score`. Nothing in this
phase is greenfield: every fix target, every code insertion point, and the oracle to check against
already exist and were located this session. The two genuinely open technical questions are (1)
whether HubSpot's `PUT /automation/v4/flows/{flowId}` can safely round-trip this portal's specific
flow JSON (branch/IS_BETWEEN actions, `shouldReEnroll`) without HubSpot rejecting or silently
dropping something, and (2) whether `calculationFormula` on the existing `lv_icp_fit_score`
calculated property can be PATCHed to add a fifth term. Official docs confirm both operations
exist and are documented as working in the general case; neither has been exercised against this
portal's actual property/flow definitions yet. The plan should treat the first live GET+PUT
round-trip (on a clone/disabled copy, per D-07) as a fast validation task early in the phase, not
an assumption baked into every subsequent task.

**Primary recommendation:** Fetch all four flows via `GET /automation/v4/flows/{id}` first (before
writing any plan task bodies further than "fetch and archive"), strip `createdAt`/`updatedAt`/
`dataSources` per the documented PUT gotcha, and do one disable→trivial-edit→PUT→re-enable round
trip on the smallest flow (likely 4626124224, org-type mapper) as an early-phase validation gate
before committing to the API-only path for all four. If PUT rejects a specific action shape (e.g.
the IS_BETWEEN branch reordering F10 needs), D-05's portal-UI fallback absorbs it — plan for that
contingency explicitly rather than discovering it mid-phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Score computation (org_type/geography/revenue/content points) | HubSpot (4 flows + calculated property) | — | Operator decision, reaffirmed 39-DECISION.md — scoring stays HubSpot-resident, not pipeline-side |
| Veto derivation (`lv_anti_icp_flag`/`lv_anti_icp_reason`) | n8n pipeline (`mergeCompanies.js` via `ENRICH_DECIDE_CO_CLOUD`) | — | D-01/HANDOVER §5 decision 2 — HubSpot workflows must not touch this field after remediation |
| Tier assignment (`lv_icp_tier`) | HubSpot (WF1, flow 4625147345) | — | Reads `lv_icp_fit_score` + `lv_anti_icp_flag`; D-01 doesn't move this, only removes HubSpot's *veto write*, not its veto *read* |
| Backfill/component seeding for the 712 | n8n-adjacent script (batch PATCH via `src/hubspot_client.py`) | HubSpot (flows fire on the resulting property change) | D-10 — deterministic script writes component scores, existing flow chain does the rest; Phase 40 proves the mechanism only, full run is Phase 41 |
| Parity assertion | Python (`tests/` + `scripts/` wrapper) calling HubSpot read APIs + `compute_icp_score` | — | D-11 — oracle is pipeline-side (`src/icp_scoring.py`), subject under test is HubSpot's live state; this is a read-only cross-tier assertion, no tier owns "correctness," the harness does |

## Package Legitimacy Audit

Not applicable — this phase adds no new third-party packages. All work uses `requests`, `PyYAML`,
`pytest`, and `python-dotenv`, already present in `requirements.txt` and already imported by
`src/hubspot_client.py` / `tests/test_icp_scoring.py` (both read this session).

## Architecture Patterns

### System Architecture Diagram

```
n8n pipeline (ENRICH_DECIDE_CO_CLOUD, mergeCompanies.js)
  |
  |  writes canonical inputs (lv_org_type, lv_produces_content,
  |  lv_country_region_normalized, lv_revenue_band, lv_is_hardware_vendor,
  |  lv_is_gambling_operator) + [NEW, D-01] derives and writes
  |  lv_anti_icp_flag / lv_anti_icp_reason as "true"/"false" strings
  v
HubSpot property-change event bus
  |
  +--> Flow 4626124224 (org_type known)      --> org_type_score
  +--> Flow 4626722240 (geography, RETARGET   --> geography_score
  |     to lv_country_region_normalized,       (F2; veto branch DELETED, D-01)
  |     F2/D-01)
  +--> Flow 4626722237 (revenue, RETARGET     --> annual_revenue_score
  |     to lv_revenue_band, F3; exact-bound    (F10 boundary fix)
  |     branches, F10)
  +--> [NEW flow or existing-flow addition]   --> produces_content_score
        (lv_produces_content known, D-06)          (F1)
  |
  v
lv_icp_fit_score (calculated property, SUM of 4 component scores
                   [NEW 5th term produces_content_score, D-06])
  |
  v
Flow 4625147345 "WF1" (lv_icp_fit_score known
                        OR [NEW] lv_anti_icp_flag known, F7)
  |
  +--> reads lv_anti_icp_flag (READ ONLY after D-01)
  |      true  --> lv_icp_tier = D
  |      false --> lv_icp_tier = A/B/C by score band (F8: <15 --> Unscored, not D)
  v
lv_icp_tier (final grade, read by reps/views)

Parity harness (tests/ pytest + scripts/ wrapper)
  reads: HubSpot live lv_icp_fit_score / lv_icp_tier / lv_anti_icp_flag (GET)
  computes: expected via compute_icp_score(record, patch) [oracle, unchanged]
  asserts: live == expected, for fixtures (full tier, on-demand) and a
           real-record sample (read-only tier, scheduled cadence)
```

### Recommended flow-JSON storage location

No existing convention in this repo stores HubSpot flow definitions in git (grep of
`config/`, `n8n/`, `scripts/` for `automation/v4` and `flows_full` returned nothing — the only
place they were ever archived was a *prior session's* scratchpad, which does not persist between
sessions and is confirmed gone). Recommend `config/hubspot_flows/{flow_id}-{slug}.json`, snapshotted
before and after each PUT (`{flow_id}-{slug}.before.json` / `.after.json`), mirroring the
`scripts/snapshot_hubspot_schema.py` before/after discipline named in D-05 and CONTEXT.md's Reusable
Assets list. This is Claude's Discretion per 40-CONTEXT.md — recorded here as the concrete choice,
not re-litigated.

### Pattern 1: Fetch-strip-PUT round trip for flow edits (D-05)
**What:** `GET /automation/v4/flows/{flowId}` returns the full flow definition including
`createdAt`, `updatedAt`, and `dataSources` fields that must be stripped before `PUT
/automation/v4/flows/{flowId}` — HubSpot's own community-reported failure mode is validation
errors when these round-trip unchanged, and *any field omitted from the PUT body is deleted from
the live flow* (not left alone) [CITED: developers.hubspot.com Workflows v4 API guide].
**When to use:** Every one of the four flow edits in this phase (F1 add, F2/F3 retarget, F4–F7
veto-branch removal, F8/F10 revenue-branch/tier fixes).
**Example:**
```python
# Source: HubSpot Automation v4 API guide (developers.hubspot.com/docs/api-reference/
# automation-automation-v4-v4/guide) — PUT semantics confirmed via WebFetch this session.
import requests
from src.hubspot_client import BASE_URL, hs_headers

flow = requests.get(f"{BASE_URL}/automation/v4/flows/{flow_id}",
                     headers=hs_headers(), timeout=30).json()
for k in ("createdAt", "updatedAt", "dataSources"):
    flow.pop(k, None)

# D-07: disable before editing live-reachable branches
flow["isEnabled"] = False
requests.put(f"{BASE_URL}/automation/v4/flows/{flow_id}", headers=hs_headers(),
             json=flow, timeout=30).raise_for_status()

# ... apply the F-fix to flow["actions"] / flow["enrollmentCriteria"] here ...

requests.put(f"{BASE_URL}/automation/v4/flows/{flow_id}", headers=hs_headers(),
             json=flow, timeout=30).raise_for_status()
# validate on ZZ-SCORING-TEST-DELETE-ME-* companies, THEN re-enable (isEnabled: true, D-07)
```
`isEnabled` is a real, PUT-settable field on the flow object — confirmed via WebSearch of a
HubSpot Community post describing the "create disabled, flip to enabled after review" idiom
[CITED: community.hubspot.com — automation v4 API HTTP 400 thread, isEnabled usage pattern].
This directly satisfies D-07/D-08 without a portal-UI fallback for the enable/disable step
specifically — the open risk (see Pitfalls) is whether the *action-content* edits themselves
(specifically F10's `IS_BETWEEN` boundary reordering) are accepted by PUT, which is
undocumented at the action-type level.

### Pattern 2: Veto derivation lands in ENRICH_DECIDE_CO_CLOUD, not mergeCompanies.js's candidate path
**What:** D-01 requires n8n to compute `lv_anti_icp_flag`/`lv_anti_icp_reason` deterministically.
The natural-looking insertion point (adding the two fields to `ENRICH_MERGE_CO`'s candidate list,
scripts/build_cloud_workflows.py:2445/2473, so `mergeCompanies()`'s existing `veto_output` policy
class handles it) is a trap: `DEFAULT_COMPANY_POLICY`'s `veto_output` branch in
`mergeCompanies.js` unconditionally `promote`s once past the confidence gate — it has no concept
of "derive from three OTHER already-merged fields," only "trust the candidate I was handed." The
inputs the veto needs (`lv_country_region_normalized`, `lv_produces_content`,
`lv_is_hardware_vendor`) are only known **after** `mergeCompanies()` has already run (twice — once
for the waterfall candidate, once for the research candidate, `scripts/build_cloud_workflows.py`
lines 2452 and 2486, `finalMerge` assembled at 2501). The correct insertion point is
**`ENRICH_DECIDE_CO_CLOUD`** (scripts/build_cloud_workflows.py:2579–2660), reading off
`finalMerge.canonicalPatch` (falling back to `row.existingRecord` for fields not in this run's
patch, matching `compute_icp_score`'s own `get_signal()` fallback pattern in
`src/icp_scoring.py:28-31`) — i.e. port the hard-veto branch of `compute_icp_score` (lines 84-97
of `src/icp_scoring.py`, read this session) into a small pure function callable from this Code
node, not a `mergeCompanies()` policy class.
**When to use:** D-01's veto write.
**Example:**
```js
// scripts/build_cloud_workflows.py — inside ENRICH_DECIDE_CO_CLOUD, after `properties`
// is built (line ~2601) and before the needsReview branch (line 2603). Port of
// src/icp_scoring.py:84-97 hard-veto logic (verbatim reasons from config/icp_scoring.yaml
// hard_vetoes.*.reason, read this session):
//   non_anz:          "Non-ANZ geography"
//   no_content:        "No broadcast or streaming content"
//   hardware_vendor:  "Hardware/AV/LED vendor, not sports-media buyer"
function _regionKey(v) {
  return (v === "AU" || v === "NZ" || v === "ANZ") ? v : "non_anz";
}
function _boolish(v) {
  if (typeof v === "boolean") return v;
  if (v === "true") return true;
  if (v === "false") return false;
  return null;
}
const existing = row.existingRecord || {};
const region = _regionKey(properties.lv_country_region_normalized ?? existing.lv_country_region_normalized);
const producesContent = _boolish(properties.lv_produces_content ?? existing.lv_produces_content);
const isHardwareVendor = _boolish(properties.lv_is_hardware_vendor ?? existing.lv_is_hardware_vendor);

const reasons = [];
if (region === "non_anz") reasons.push("Non-ANZ geography");
if (producesContent === false) reasons.push("No broadcast or streaming content");
if (isHardwareVendor === true) reasons.push("Hardware/AV/LED vendor, not sports-media buyer");

// D-04: coerce to strings the same way 36-07 fixed lv_enrichment_requested; a bare JS
// boolean silently breaks the EQ filter that view/re-enrollment criteria will read (F7).
properties.lv_anti_icp_flag = reasons.length > 0 ? "true" : "false";
properties.lv_anti_icp_reason = reasons.length > 0 ? reasons.join("; ") : "";
```
This keeps `mergeCompanies.js` byte-identical for the veto fields (P2/P4's fix, D-04, is a
*hardening* of the now-permanently-dead policy entries — delete the `min_confidence: 0` values or
raise them to a real threshold as insurance, per PIPELINE-DEFECTS-VALIDATION.md's own
recommendation, read this session — not a live code path this derivation depends on).

### Pattern 3: Batch-seed component scores for backfill (D-10)
**What:** `POST /crm/v3/objects/companies/batch/update` with up to 100 records per batch, writing
`org_type_score`/`geography_score`/`annual_revenue_score`/`produces_content_score` computed from
each record's *current* canonical inputs (0 where the input is missing) — mirrors the
`PROPERTY_DEFAULT_VALUE` stamp new records already get (HANDOVER §10.1). Writing these triggers
the calculated-sum property to recompute and WF1 to fire, with no re-enrollment assumption needed.
**When to use:** D-09's small-sample proof (fixtures + a handful of real records) — the
portfolio-wide 712-record run is explicitly Phase 41, not this phase.
**Example:**
```python
# No batch-update helper exists in src/hubspot_client.py today (only single-record
# get_record/patch_record/create_record/delete_record/search_records, all read this
# session) — this phase adds one, following the same dry_run-first pattern as patch_record.
import requests
from src.hubspot_client import BASE_URL, hs_headers

def batch_update_companies(updates: list[dict], dry_run=True):
    # updates: [{"id": "789", "properties": {"org_type_score": 40, ...}}, ...]
    payload = {"inputs": updates}
    if dry_run:
        return {"dry_run": True, "payload": payload}
    r = requests.post(f"{BASE_URL}/crm/v3/objects/companies/batch/update",
                       headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
```

### Anti-Patterns to Avoid
- **Editing `n8n/code/mergeCompanies.js` without rebuilding + redeploying + bouncing.** Editing
  the source `.js` file changes nothing live. The chain is: edit `n8n/code/*.js` →
  `scripts/build_cloud_workflows.py` regenerates `n8n/wf_enrichment_cloud.json` →
  `scripts/deploy_n8n_workflows.py` (two-key gate: `DRY_RUN=false ALLOW_N8N_DEPLOY=true`) PUTs it
  to n8n Cloud → the workflow must be **bounced** afterward, because "bare PUT never reloads a
  running workflow" [established pattern, 40-CONTEXT.md Established Patterns, and project memory
  `n8n-stored-vs-running-content.md`]. This applies to D-01/D-04's pipeline-side changes only —
  HubSpot flow edits (D-05) use a completely separate API and are not subject to this trap.
- **Assuming the four HubSpot flows' JSON is already in the repo.** It is not, and the one
  archive that existed (`scratchpad/flows_full.json`) was a *different session's* scratchpad
  directory, confirmed unreachable this session. Every plan task touching a flow must start with
  a live `GET`, not a repo read.
- **Trusting `config/hubspot_properties.yaml` as ground truth for the score-output properties.**
  Grepped this session: `lv_anti_icp_flag`, `lv_icp_fit_score`, `lv_icp_tier`, `org_type_score`,
  `geography_score`, `annual_revenue_score` all have **zero** matches in
  `config/hubspot_properties.yaml`. Only `lv_anti_icp_reason` and `lv_country_region_normalized`/
  `lv_revenue_band` (the canonical *inputs*) are catalogued. This file does not reconcile against
  the live portal for anything this phase touches (CLEAN-01, Phase 42, is the reconciliation
  work) — do not treat its absence of these properties as "they don't exist."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Disposable-record validation before/after a live edit | A new test-company lifecycle helper | The existing `ZZ-SCORING-TEST-DELETE-ME-*` create/exercise/delete pattern (`scripts/probe_scoring_recalc_latency.py`, read this session) + `src/hubspot_client.py`'s `create_record`/`delete_record` (Phase 39 asset) | Already handles dry-run gating, portal-ID guard, and guaranteed teardown-on-exception |
| Veto boundary/rubric logic in n8n | A second hand-written scoring rubric in JS | Port the *exact* branch shape of `compute_icp_score`'s hard-veto block (`src/icp_scoring.py:84-97`) verbatim — same field names, same string reasons pulled from `config/icp_scoring.yaml` | Divergence here is exactly the class of drift PARITY-01/02 exist to catch; hand-deriving a second version defeats the harness's purpose before it's even built |
| Live-vs-dry-run write gating for the new batch-update helper | A bespoke arm/disarm scheme | The `dry_run=True` default + two-key env gate idiom already used by every write function in `src/hubspot_client.py` and every `scripts/probe_*.py`/`scripts/deploy_*.py` in this repo | One safety pattern, consistently applied, is the entire reason this repo has never had a live-write incident this session's evidence surfaces |

**Key insight:** Nothing in this phase needs a new library or a new safety pattern — the repo
already has working analogs for every mechanical piece (record lifecycle, dry-run gating, JSON
build/deploy/bounce). The actual risk surface is entirely in the two external-API unknowns (flow
PUT action-level acceptance, calculated-property formula PATCH) and in getting the veto-derivation
insertion point right (Pattern 2) rather than falling into the `mergeCompanies()` candidate-path
trap that P2/P4 already document as a latent bug class.

## Runtime State Inventory

> Phase 40 relocates the sole live writer of a company property (`lv_anti_icp_flag`) from HubSpot
> to n8n, and deletes a live workflow branch. This is a migration of ownership, not a pure feature
> add — the categories below are answered explicitly per the mandatory trigger.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | An unknown subset of the 712 companies currently carry `lv_anti_icp_flag=true` written by the Geography flow's non-ANZ branch (F4's AU-misspelling bug means some AU companies are wrongly flagged today). D-02 explicitly accepts these stay stale until the next enrichment run touches that record — **no cleanup task required in this phase**, but the plan must state this acceptance rather than silently leaving stale `true` flags unexplained. | None this phase (accepted per D-02); Phase 41's backfill is the natural point stale flags get refreshed as enrichment re-runs. |
| Live service config | The four flow definitions (4626124224, 4626722240, 4626722237, 4625147345) exist **only in the HubSpot portal** — not exported to git today, confirmed by grep this session. The prior session's archive (`scratchpad/flows_full.json`) does not persist. | Every flow-touching task must `GET` live first; D-05 requires the fetched+edited JSON land in the repo (recommend `config/hubspot_flows/`, see Architecture Patterns) so this migration category closes for future sessions. |
| OS-registered state | None — no cron, launchd, or task-scheduler entries are created or modified by this phase. The n8n 15-minute poller referenced in D-02's refresh path is pre-existing and unmodified. | None. |
| Secrets/env vars | `HUBSPOT_PRIVATE_APP_TOKEN` already carries the `automation` scope (granted 2026-08-06 per 40-CONTEXT.md) — no new scope, no new secret. `.env` remains permission-blocked to Read/Bash this session; any token-dependent command must be handed to the operator as a `!`-prefixed command. | None (already provisioned); operator hand-off convention only. |
| Build artifacts | `n8n/wf_enrichment_cloud.json` is generated output of `scripts/build_cloud_workflows.py` (confirmed by reading its header, 2 file). Editing `n8n/code/mergeCompanies.js` or `scripts/build_cloud_workflows.py`'s `ENRICH_DECIDE_CO_CLOUD` (D-01/D-04) is inert until rebuild → `scripts/deploy_n8n_workflows.py` (two-key gate) → bounce. | Must be an explicit task step, not assumed to happen implicitly after a source-file edit. |

## Common Pitfalls

### Pitfall 1: PUT to `/automation/v4/flows/{id}` silently deletes anything omitted from the body
**What goes wrong:** HubSpot's documented behavior is that a PUT is a *replace*, not a *merge* —
any action, branch, or enrollment-criteria block present in the flow today but missing from the
PUT payload is removed from the live flow.
**Why it happens:** v4 REST semantics treat PUT as authoritative-replace; this is explicit in the
official guide [CITED: developers.hubspot.com Workflows v4 API guide, confirmed via WebFetch this
session].
**How to avoid:** Always PUT the full GET response (minus `createdAt`/`updatedAt`/`dataSources`)
with only the targeted fields mutated in place — never construct a PUT body from scratch or from
a partial diff.
**Warning signs:** A flow that "loses" an action or branch nobody intended to touch after an
edit — check the archived `.before.json`/`.after.json` snapshot diff (Architecture Patterns,
storage location) immediately if this is suspected.

### Pitfall 2: The action-level PUT acceptance for branch/`IS_BETWEEN` edits is undocumented
**What goes wrong:** F10's fix (exclusive revenue-band boundaries, or re-ordered branches) requires
editing the *content* of an `IS_BETWEEN`-style branch condition inside the flow's `actions` array.
Neither the official guide nor the community threads found this session describe which action
subtypes are safely API-editable versus UI-only ("Not addressed" per this session's WebFetch of
the guide).
**Why it happens:** v4 Automation API is public beta as of the changelog entry found this session
(2025-01-13) — action-type coverage is not exhaustively documented.
**How to avoid:** Treat the F10 branch-boundary edit as the highest-risk single task in the phase.
Do the disable→edit→PUT→validate→re-enable cycle (D-07/D-08) on this flow *early*, and have the
portal-UI fallback (D-05's explicit fallback clause) ready to invoke immediately if the PUT
succeeds (200) but the live behavior on a `ZZ-SCORING-TEST-DELETE-ME-*` company doesn't match —
HubSpot APIs are known to sometimes 200 an edit that doesn't take effect as expected in the UI
layer for beta endpoints.
**Warning signs:** PUT returns 200 but a disposable-company validation run against exact boundary
values (500,000,000 / 750,000,000 / 1,000,000,000 / 1,200,000,000, per ENGINE-04) doesn't match
the rubric-correct band.

### Pitfall 3: `calculationFormula` PATCH on an *existing* property with existing references has a documented history of 400s
**What goes wrong:** HubSpot Community threads found this session report "There was a problem with
the request" errors specifically when a `calculationFormula` references other properties, though
the same threads report this class of issue has since been fixed.
**Why it happens:** Calculated-property formula validation is comparatively immature tooling
(`fieldType: calculation_equation` is a narrower, newer property type than standard fields).
**How to avoid:** Before adding the `produces_content_score` term (D-06), `GET
/crm/v3/properties/companies/lv_icp_fit_score` first to see the *exact* current formula syntax
this portal's four-term sum uses, then PATCH with that same syntax extended by one term — do not
hand-construct new formula syntax from documentation examples alone, since the working syntax for
this specific property is available by inspection and safer to extend than to reconstruct.
**Warning signs:** A 400 on the PATCH, or a 200 that leaves `lv_icp_fit_score` computing the old
4-term sum (verify with a `ZZ-SCORING-TEST-DELETE-ME-*` company carrying `lv_produces_content=true`
and nothing else, expecting `+20` to actually land).

### Pitfall 4: Adding `lv_anti_icp_flag`/`lv_anti_icp_reason` to `ENRICH_MERGE_CO`'s candidate list instead of `ENRICH_DECIDE_CO_CLOUD`
**What goes wrong:** This is the trap Architecture Pattern 2 above calls out. It looks like the
"obvious" fix given `mergeCompanies.js` already has a `veto_output` policy class for these exact
two fields — but that class was designed for a candidate *supplied by a provider/research call*,
not *derived from three already-merged canonical fields on the same row*. Wiring it through
`ENRICH_MERGE_CO` would require restructuring the merge call order (deriving inputs, then calling
`mergeCompanies()` a third time with the derived veto candidate) for no benefit over a direct pure
function in the Decide node.
**Why it happens:** The policy entry already exists and P2/P4's validation surfaced it recently,
making it feel "half-built" rather than "wrong shape for this job."
**How to avoid:** Follow Pattern 2 exactly — derive in `ENRICH_DECIDE_CO_CLOUD` from
`finalMerge.canonicalPatch` with `row.existingRecord` fallback, bypassing `mergeCompanies()`'s
policy machinery entirely for these two fields.
**Warning signs:** A plan task that says "add `lv_anti_icp_flag` to the candidate list at
scripts/build_cloud_workflows.py:2445 or :2473" — that is the wrong line for this fix.

### Pitfall 5: Forgetting the `Needs Review` tier when re-checking F8/D-03 against the live `lv_icp_tier` dropdown
**What goes wrong:** `src/icp_scoring.py`'s oracle can emit `"Needs Review"` or `"Unscored"` as
tier values, but HANDOVER §9 (Gotchas, read this session) notes HubSpot's `lv_icp_tier` dropdown
historically had **only A/B/C/D** options — an enum-refusal risk if WF1 is edited to write
`Unscored` and that value isn't a valid enum option on the live property.
**Why it happens:** The property was scoped under an earlier design (§9 says this "stops
mattering" only *if* the property gets retired — which it doesn't on the fix-in-place path
39-DECISION.md sealed; `lv_icp_tier` is very much still live and written by WF1).
**How to avoid:** `GET /crm/v3/properties/companies/lv_icp_tier` and confirm `Unscored` is a valid
enum option *before* WF1 is edited to write it (D-03's F8 fix target). If it's missing, adding the
enum option is a small prerequisite PATCH, not part of the flow edit itself.
**Warning signs:** WF1's PUT succeeds but a disposable sub-15-no-veto company's `lv_icp_tier`
comes back empty/unset rather than `Unscored` after the fix.

## Code Examples

### Reading a company's current canonical inputs for parity comparison
```python
# Source: src/hubspot_client.py (read this session) — get_record signature confirmed.
from src.hubspot_client import get_record

FIT_SCORE_PROPS = [
    "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator", "lv_is_hardware_vendor",
    "lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason",
]

def fetch_for_parity(company_id: str) -> dict:
    return get_record("companies", company_id, FIT_SCORE_PROPS)["properties"]
```

### Parity assertion shape (D-11)
```python
# tests/test_scoring_parity.py — sketch. Oracle unchanged; this is a NEW test module,
# not an edit to tests/test_icp_scoring.py (which stays pure-oracle, no network).
import os
import pytest
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score
from src.hubspot_client import get_record

live = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PARITY") != "true",
    reason="opt-in: set RUN_LIVE_PARITY=true to hit the live HubSpot portal",
)

@live
def test_parity_real_record_sample(real_company_ids):
    for cid in real_company_ids:
        props = fetch_for_parity(cid)
        record = HubSpotRecord(object_type="companies", id=cid, properties=props)
        expected = compute_icp_score(record, {})
        assert str(props.get("lv_icp_fit_score")) == str(expected.score)
        assert props.get("lv_icp_tier") == expected.tier
```
No existing `pytest.ini`/`pyproject.toml` marker registration was found this session (grepped for
`[pytest]`/`markers` — none). `skipif` on an explicit env var (mirroring the two-key arm pattern
every `scripts/probe_*.py` in this repo already uses) is the lower-friction choice over a custom
registered marker, since it needs zero new pytest config and the existing repo convention is
already "env-var gated," not "marker gated."

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Legacy `calculation_score` HubSpot Score mechanism | Custom `lv_icp_fit_score` calculated property + 4-workflow chain | Legacy stopped updating 2025-08-31, removed from this portal 2026-01-10 (39-DECISION.md, HANDOVER §5) | Not relevant to Phase 40 directly (already superseded before Phase 39), but explains why the calculated-property + flow-chain architecture exists at all rather than a native score type |
| HubSpot Automation v3 Workflows API | Automation v4 (`/automation/v4/flows`), PUT-update capability added | v4 update/PUT + batch/read added to public beta 2025-01-13 [CITED: developers.hubspot.com changelog] | This is the API D-05 depends on; it is recent enough (~19 months old at research time) that community-reported edge cases (validation 400s, field-stripping requirements) are still actively surfacing, not fully settled |

**Deprecated/outdated:**
- HubSpot Automation v3 Workflows API for flow *mutation* — v4 is required for PUT-update; v3 may
  still work for read-only listing but this phase's write path targets v4 exclusively per D-05.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `PUT /automation/v4/flows/{flowId}` accepts arbitrary edits to existing `actions`/branch content (e.g. `IS_BETWEEN` boundary reordering for F10), not just top-level fields like `isEnabled` | Architecture Patterns Pattern 1, Pitfall 2 | If wrong, F10's revenue-boundary fix and possibly F4-F6's veto-branch deletion must fall back to portal-UI hand-edit per D-05's own fallback clause — plan should sequence this flow's edit early as a validation gate, not assume API-only success |
| A2 | `calculationFormula` on `lv_icp_fit_score` can be PATCHed via `PATCH /crm/v3/properties/companies/lv_icp_fit_score` to add a 5th sum term without breaking the existing 4 terms | Pitfall 3, D-06 | If wrong, D-06's produces_content_score integration needs a portal-UI hand-edit of the formula (small, single-property scope, low risk even if it happens) |
| A3 | No pytest marker/config exists in this repo for gating live-API tests — env-var `skipif` is the lower-friction choice over introducing a registered marker | Code Examples, D-11 | Low risk either way; if the plan prefers a registered marker for `-m live` selection ergonomics, that's a small `pyproject.toml`/`pytest.ini` addition, not a blocker |
| A4 | `ENRICH_DECIDE_CO_CLOUD` (not `ENRICH_MERGE_CO`'s candidate path) is the correct insertion point for D-01's veto derivation | Architecture Patterns Pattern 2, Pitfall 4 | HIGH confidence — based on reading both functions this session, not inference; flagged as an assumption only because the *test coverage decision* (whether `tests/test_cloud_companies_branch.py`'s existing dead-policy test needs updating alongside this) is the planner's call, not verified here |

## Open Questions

1. **Does this portal's `lv_icp_tier` property already have an `Unscored` enum option?**
   - What we know: HANDOVER §9 flags this as a historical gap ("dropdown has only A/B/C/D").
   - What's unclear: whether it was fixed since that note was written (2026-08-06, same day, but
     earlier in the session per the file's own numbering) — not re-verified this research pass.
   - Recommendation: Add a `GET /crm/v3/properties/companies/lv_icp_tier` check as an early task,
     before WF1's F8 fix is written to the flow (Pitfall 5).

2. **What is this portal's exact current `calculationFormula` syntax for `lv_icp_fit_score`?**
   - What we know: HANDOVER §3b promises the formula exists and is a straightforward sum
     ("§3b. The formula itself" section header, not read in full this session — only §5, §10
     were read in depth per the file's line-range budget).
   - What's unclear: the literal formula string (property-name tokens, operator syntax) needed to
     safely extend it for D-06.
   - Recommendation: `GET /crm/v3/properties/companies/lv_icp_fit_score` as a Task 1-adjacent step;
     this is a 30-second read that removes Pitfall 3's biggest risk (guessing formula syntax).

3. **Real-record sample size/selection for PARITY-01 (Claude's Discretion per CONTEXT.md)**
   - What we know: 1/712 companies has any input coverage today (Melbourne Racing Club); D-09's
     backfill mechanism proof supplies "a few real records."
   - What's unclear: exact count/selection criteria.
   - Recommendation: Use whichever handful of real records D-09's backfill-mechanism proof touches
     as the PARITY-01 sample — same records serve both purposes, avoiding a second selection
     exercise (D-09 already notes this overlap explicitly: "doubles as PARITY-01's real-record
     sample").

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| HubSpot Automation v4 API (`automation` scope) | D-05 flow fetch/edit | Yes — scope granted 2026-08-06, confirmed in 39-DECISION.md/40-CONTEXT.md | v4 (public beta since 2025-01-13) | Portal UI hand-edit (D-05's own fallback clause) for any action the API rejects |
| HubSpot CRM v3 Properties API | D-06 calculated-formula PATCH, F10 enum fixes | Yes — same private app token, no additional scope needed (properties are `crm.schemas.companies.write` class, already exercised by `scripts/sync_hubspot_properties.py` per repo convention) | v3 | None needed — this is the same API surface `scripts/snapshot_hubspot_schema.py` already uses |
| HubSpot CRM v3 batch/update (companies) | D-10 backfill-mechanism proof | Yes — standard v3 batch endpoint, same auth as single-record PATCH | v3 | None needed |
| n8n Cloud (deploy target for D-01/D-04) | Pipeline-side veto derivation going live | Yes — existing deployed instance, `scripts/deploy_n8n_workflows.py` already the established path | — | None needed; bounce-after-PUT is a known operational step, not a missing dependency |
| `.env` (`HUBSPOT_PRIVATE_APP_TOKEN`, n8n credentials) | All live operations this phase | Present but Read/Bash permission-blocked this session | — | Hand operator a `!`-prefixed command per established repo convention |

**Missing dependencies with no fallback:** None identified.

**Missing dependencies with fallback:** Flow action-level API editability (Pitfall 2) — fallback
is portal UI, already pre-committed in D-05.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo already uses `.venv/bin/python -m pytest`, confirmed this session and in 40-CONTEXT.md) |
| Config file | None found (`pytest.ini`/`pyproject.toml [tool:pytest]` grep returned nothing) — a Wave 0 gap only if the plan chooses a registered `live` marker over env-var `skipif` (see Code Examples / A3) |
| Quick run command | `.venv/bin/python -m pytest tests/test_icp_scoring.py tests/test_cloud_companies_branch.py -q` |
| Full suite command | `.venv/bin/python -m pytest -q` (existing oracle + branch tests) plus `node --test tests/n8n/*.test.mjs` for any n8n-side JS assertions (D-01/D-04 changes) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENGINE-01 | AU governing_body_league + content + 50-500M scores 80/A entirely in HubSpot | live end-to-end (disposable company) | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py -k engine_01 -q` | ❌ Wave 0 — new file |
| ENGINE-02 | `lv_produces_content=true` contributes +20 | live (component-level check) | same harness, `-k produces_content` | ❌ Wave 0 |
| ENGINE-03 | Scoring reads canonical inputs, never native `country`/`annualrevenue` | live (negative-input regression: set native fields, confirm no score movement) | same harness | ❌ Wave 0 |
| ENGINE-04 | Revenue boundaries exact (750M → −15) | live, 4 boundary-value disposable companies | same harness, `-k revenue_boundary` | ❌ Wave 0 |
| ENGINE-05 | Gambling −20 via `lv_is_gambling_operator`, never sets veto | live | same harness, `-k gambling` | ❌ Wave 0 |
| ENGINE-06 | Org-type points match config exactly (incl. regulator=5) | live, enum sweep | same harness, `-k org_type_sweep` | ❌ Wave 0 |
| ENGINE-07 | Sub-15 without veto → not D | live | same harness, `-k f8_sub15` | ❌ Wave 0 |
| VETO-01 | All 3 hard vetoes set flag+reason | live end-to-end (pipeline veto write, not HubSpot) | same harness, `-k veto_set` | ❌ Wave 0 |
| VETO-02 | Correcting clears flag+reason | live end-to-end | same harness, `-k veto_clear` | ❌ Wave 0 |
| VETO-03 | Flag change updates tier without score change | live end-to-end | same harness, `-k tier_on_flag_change` | ❌ Wave 0 |
| PARITY-01 | Harness asserts fixtures + real-record sample | pytest module + script wrapper | `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` (fixtures) + `RUN_LIVE_PARITY=true` variant (real sample) | ❌ Wave 0 |
| PARITY-02 | F4/F7/F9/F10 named regression cases | live end-to-end, named test functions | same harness, `-k "f4_or_f7_or_f9_or_f10"` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Oracle-only tests (`tests/test_icp_scoring.py`, `tests/test_cloud_companies_branch.py`) — zero network, fast.
- **Per wave merge:** Full fixture parity run (on-demand tier, D-12) before/after any flow edit.
- **Phase gate:** Full suite green, plus one full live end-to-end veto regression pass (D-13) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_scoring_parity.py` — new module, covers PARITY-01/02 and the live components of ENGINE-01–07/VETO-01–03.
- [ ] `scripts/run_scoring_parity.py` (or similar name, D-11's thin wrapper) — sweep runner + JSON verdict report for the scheduled read-only cadence (D-12).
- [ ] A `batch_update_companies()` helper in `src/hubspot_client.py` (does not exist today — confirmed by reading the file in full this session) — needed for D-10's backfill-mechanism proof.
- [ ] Decision on env-var `skipif` vs registered `live` pytest marker (A3) — either is fine, but the plan should pick one explicitly rather than leaving it to task-time improvisation.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No new auth surface — reuses the existing HubSpot private-app bearer token |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes | HubSpot's `automation` + properties scopes gate what the private app token can do; no broader scope is requested this phase (already granted, per 40-CONTEXT.md) |
| V5 Input Validation | Yes | Flow-JSON PUT bodies and batch-PATCH payloads are constructed from this repo's own config (`config/icp_scoring.yaml`) and live GET responses, not user input — the validation risk is schema-shape correctness (Pitfall 1/2), not injection |
| V6 Cryptography | No | No new secret material; `.env` handling unchanged (Read/Bash-blocked, hand operator `!` commands) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Live-write accidents against production HubSpot data during flow edits | Tampering | D-07's disable→edit→validate-on-disposable→re-enable protocol; every write helper in this repo defaults `dry_run=True` |
| Boolean-vs-string serialization silently breaking a downstream EQ filter (the F4/36-07 class of bug) | Tampering (data integrity) | D-04's explicit string coercion, applied at the single insertion point (Pattern 2's `properties.lv_anti_icp_flag = "true"/"false"`) rather than per-caller |
| A parity-harness bug that reports false-green (never actually asserting against live data) | Repudiation (the harness itself becomes untrustworthy) | D-13's "live end-to-end only, no offline substitute" for veto regressions — deliberately trades cost for the harness being provably real, not a mock that always passes |

## Sources

### Primary (HIGH confidence)
- `HANDOVER-2026-08-06-icp-scoring.md` §5, §9, §10 — read this session; the F1–F10 defect
  table and flow-ID/write-mapping table are the ground truth for every remediation target.
- `PIPELINE-DEFECTS-VALIDATION.md` (full file, read this session) — P1–P4 verdicts and exact
  code sites for the pipeline-side dead-code/latent-bug fixes D-04 closes.
- `config/icp_scoring.yaml`, `src/icp_scoring.py` (both read in full this session) — rubric and
  oracle of record.
- `n8n/code/mergeCompanies.js` (lines 1-80 read), `scripts/build_cloud_workflows.py` (lines
  2397-2660 read) — exact insertion-point evidence for Pattern 2/Pitfall 4.
- `src/hubspot_client.py` (full file, read this session) — confirmed the existing write-helper
  shape and confirmed no `batch_update_companies()` exists today.
- `config/field_policy.yaml`, `config/hubspot_properties.yaml` (relevant sections read) —
  confirmed the `veto_output` policy declaration and confirmed the score-output properties are
  absent from the properties catalog.

### Secondary (MEDIUM confidence)
- developers.hubspot.com Automation v4 API guide (`automation-automation-v4-v4/guide`) — fetched
  via WebFetch this session; confirmed PUT-update semantics, `isEnabled` field, batch/read
  endpoint, full-replace-on-PUT behavior. Action-type-level editability (branches, IS_BETWEEN) not
  documented — flagged as A1/Pitfall 2.
- developers.hubspot.com changelog "New features for the v4 Automation API" — fetched via
  WebFetch this session; confirmed PUT-update and batch/read were added 2025-01-13, public beta.
- HubSpot Community thread on `automation/v4` HTTP 400 — WebSearch summary this session;
  corroborates the `isEnabled` create-disabled-then-enable idiom.
- HubSpot Community threads on calculated-property `calculationFormula` API errors — WebSearch
  summary this session; documents a historical validation-error class (since reported fixed) when
  formulas reference other properties.

### Tertiary (LOW confidence)
- None used without corroboration — all WebSearch findings above were cross-checked against at
  least one official-docs WebFetch or a specific community-thread quote.

## Metadata

**Confidence breakdown:**
- Remediation targets (F1–F10) and code insertion points: HIGH — every claim traces to a file
  read this session, not inference.
- HubSpot Automation v4 API write behavior (PUT full-replace, `isEnabled`, batch/read): MEDIUM —
  confirmed from official docs + community threads, but action-type-level editability for this
  portal's specific branch/IS_BETWEEN structures is unverified until the first live round trip.
- Calculated-property formula PATCH mechanics: MEDIUM — documented as generally working, this
  portal's exact current formula syntax not yet inspected (Open Question 2).
- Parity harness shape (D-11/D-12/D-13): HIGH for the *policy* (locked in CONTEXT.md), MEDIUM for
  the *pytest mechanics* (no existing live-test convention in this repo to follow exactly; A3's
  env-var-`skipif` recommendation is a reasonable default, not a locked pattern).

**Research date:** 2026-08-06
**Valid until:** ~14 days (HubSpot's v4 Automation API is public beta and actively changing;
re-verify Pitfall 2/3 findings if this phase's start is delayed past early September 2026).
