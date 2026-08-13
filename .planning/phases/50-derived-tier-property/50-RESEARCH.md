# Phase 50: Derived Tier Property - Research

**Researched:** 2026-08-13
**Domain:** HubSpot CRM schema (Properties API + Automation v4 Flows API) — no code/library work
**Confidence:** MEDIUM — the mechanism (calculated string property) is HIGH confidence (spike
CONCLUSIVE POSITIVE); the retirement/rollback mechanism (D-18) resolves to a documented negative
finding that changes the shape of the plan; several items remain genuinely unknown pending a live
probe this research is explicitly forbidden from running.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** v0.9's "no new HubSpot properties" rule is lifted for exactly one derived-tier string
  property. `lv_icp_scoring_version` and the three §5.3 fields stay out of scope.
- **D-02:** Phase 50 extends v0.9, does not open v1.0.
- **D-03:** Preferred null variant is **uncoalesced** `lv_icp_fit_score` (blank stays blank for
  never-scored companies — matches WF1's `includeObjectsWithNoValueSet: false` status quo).
- **D-04:** Forced fallback if uncoalesced proves impossible: ship `coalesce(lv_icp_fit_score,
  -1)`, accept ~646 never-enriched companies flipping blank → `"Unscored"`, disclose, do not
  abandon derivation, do not stop for a checkpoint.
- **D-05:** The live null test runs from a **fresh, two-key-gated script kept in `scripts/`**
  (the repo's paired `DRY_RUN=false` key + its own allow-key) — supersedes the spike's
  single-key-gated, not-kept scripts. Disposable property, archived in `finally`, verified gone
  by 404 re-read. No company record read or written.
- **D-06:** Retire `lv_icp_tier` within Phase 50, but only as the **last gated step**. If the gate
  fails, the phase closes with the derived property live and the old enum still present — a
  coherent partial state, not a failure.
- **D-07:** The gate for retirement + WF1 shutdown: derived property matches WF1 on **all 66
  scored companies with zero mismatches**, except the 4 known stuck records where the derived
  value **must differ** (`B`, not stale `C`).
- **D-08:** **WF1 (`4625147345`) is switched off, definition kept** — "Switch off, keep
  definition, defer full cleanup until new property passes evaluation" (operator, verbatim). Not
  deleted; not left running alongside the derived property.
- **D-09:** Derived ladder mirrors WF1's 5 values exactly (`D`/`A`/`B`/`C`/`Unscored`). The 6th
  `Needs Review` label is **not** added even though a string property makes it free (PARITY-01
  stays a documented accepted divergence).
- **D-10:** The 4 stuck records are fixed as a pure side effect of the property existing — no
  record write, verify by read-back only.
- **D-11:** If a portal dependent cannot be migrated, **stop and checkpoint the operator** — not a
  rule decided in advance.
- **D-12:** Two dependent classes confirmed to exist by the operator (not from the repo): sales
  lists/saved views filtered by tier, and reports/dashboards grouping by tier. Treat as
  confirmed-not-complete.
- **D-13:** Dependent enumeration is a **read-only, scripted, re-runnable** API sweep, committed
  as a phase artifact, run again immediately before cutover.
- **D-14:** New property internal name is **`lv_icp_tier_derived`** (operator's explicit choice
  over `lv_icp_tier_calc`). Do not silently substitute.
- **D-15:** Intent to rename to `lv_icp_tier` after retirement is **flagged as unproven, must be
  researched, not assumed**. Fallback if impossible: **keep `lv_icp_tier_derived` permanently**,
  change only the display label to "ICP Tier."
- **D-16:** **Zero company write windows declared.** Any company write during execution is a
  deviation requiring justification, not a budgeted allowance.
- **D-17:** Four required regression-protection pieces: (1) a live-formula-vs-`tier_rules` pin
  test in `test_rubric_change_guard.py`'s shape; (2) `scripts/check_schema_drift.py` updated for
  the new property/WF1-off state; (3) `config/hubspot_properties.yaml` and
  `config/hubspot_flows/lv_icp_tier-property.*.json` updated; (4) a committed derived-vs-WF1
  comparison across all 66 as an evidence artifact (not a test).
- **D-18:** Rollback = re-enable WF1 **plus a forced re-enrolment mechanism**, named and proven
  *before* WF1 is switched off. "Re-enable and let it converge naturally" is explicitly rejected.
- **D-19:** Operator-facing result is a before/after tier census in Phase 49's three-point-report
  format. Pre-registered expectation: **identical distribution except 4 records moving C→B.**

### Claude's Discretion

None. Every question was answered with an explicit choice bounded by a named fallback (D-04,
D-15) — no open "you decide."

### Deferred Ideas (OUT OF SCOPE)

- PARITY-01 / 6th `Needs Review` tier label — structurally free once the tier is a string, but
  deliberately not taken (D-09), to avoid confounding a mechanism change with a rubric change.
- `lv_icp_scoring_version` — remains out of scope.
- The three CLAUDE.md §5.3 fields — remain deferred to v1.0.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TIER-01 | `lv_icp_tier` no longer depends on a HubSpot property-change event; derived tier reproduces WF1's live ladder exactly, verified against real records; 4 stuck records read the score-implied tier with no event/workflow run. | Formula grammar SETTLED by the spike (7/7 ladders accepted) — see § Standard Stack / Code Examples. The 4 stuck records' correctness is a pure side effect of D-10/D-16 (no write needed) — verify by read-back only, see § Validation Architecture. |
| TIER-02 | Blank-vs-`"Unscored"` semantics for never-scored companies is a recorded decision (not a formula-shape accident), settled against live records before commit. | § Open Questions Q4 (null propagation in an untaken branch) is the crux — genuinely UNKNOWN, spike could not settle it, D-05's live test is the only way to answer it. See § Common Pitfalls Pitfall 1. |
| TIER-03 | Cutover is reversible, nothing silently breaks: portal-side dependents enumerated first; disposition of old enum + WF1 decided explicitly; no record re-tiered outside a deliberately armed, capped write window. | § Open Questions Q1 (D-18 forced re-enrolment) resolves to a **documented negative** — no HubSpot API can force re-enrolment of a company into a native flow. This is the single most consequential finding in this research and directly shapes what "reversible" can mean for TIER-03. § Open Questions Q3 (D-13 dependent enumeration) maps exactly which dependent classes are API-visible vs. UI-only. |
</phase_requirements>

## Summary

The formula grammar question is closed — the spike is CONCLUSIVE POSITIVE and this research adds
nothing to it beyond corroborating the live-captured property schema for `lv_icp_fit_score`
(§ Code Examples), which supplies the exact request-body shape a `lv_icp_tier_derived` create call
should mirror.

The research effort here went almost entirely into the phase's real risk, which sits in three
places the spike explicitly left open and CONTEXT.md's open questions correctly identify as
gating: (1) **D-18's forced re-enrolment mechanism does not exist as an API call.** HubSpot has no
programmatic enrolment endpoint for any object type except a legacy, contacts-only, deprecated v2
endpoint (`/automation/v2/workflows/{workflowId}/enrollments/contacts/{email}`) that cannot reach a
company. The only two mechanisms that can force a company back through WF1 are a human clicking
"Enroll now" in the portal UI (requires the workflow to be **on**, which conflicts with D-08), or a
perturb-then-restore double-write on the trigger property (two real, event-firing HubSpot writes
per record). This changes what D-18's rollback story can honestly promise. (2) **The
`check_schema_drift.py` do-not-archive invariant will hard-fail (exit code 2, its most severe
class) the moment WF1's `isEnabled` flips to `false` or `lv_icp_tier` is archived** — both of
which this phase deliberately does. This is a VERIFIED, line-cited finding, not present in
CONTEXT.md's D-17 framing, and is a concrete task the plan must include or every future schema-drift
check breaks red for a reason nobody remembers. (3) **Runtime null propagation inside an untaken
conditional branch (TIER-02's crux) remains genuinely unknown** — the spike could not settle it
from syntax, and this research (constrained to read-only) cannot either; it is named explicitly as
the one item requiring D-05's live probe, with the exact minimal test specified.

**Primary recommendation:** Build the derived property and its live-formula pin test using the
`lv_icp_fit_score`-property.after.json` schema as the literal template (calculated string,
`fieldType: calculation_equation`, same `groupName`), run D-05's null probe first since it gates
the formula string itself, treat D-18 as settled to "no forced-API-enrolment exists" and write the
plan's rollback section around the two real alternatives, and add the `check_schema_drift.py`
do-not-archive-set edit to D-17's task list explicitly — it is not optional cleanup, it is a
same-commit requirement or the very next schema-drift run reports the phase's own success as
portal damage.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tier computation (`lv_icp_tier_derived`) | Database/Storage (HubSpot Properties platform, `calculation_equation` engine) | — | HubSpot computes calculated properties server-side on every read; no application-tier code ever runs this logic (mirrors `lv_icp_fit_score`, already live). |
| Tier gate evaluation for retirement (D-07) | API/Backend (this repo's `scripts/`) | Database/Storage (HubSpot read) | A Python script reads all 66 scored companies via the CRM Search/Batch Read API and diffs derived-vs-WF1 values; no n8n or portal-UI role. |
| WF1 toggle (on/off) | API/Backend | Database/Storage (HubSpot Automation v4 Flows) | `PUT /automation/v4/flows/{id}` with `isEnabled: false`, same mechanism Phase 40-01 already proved live for this portal. |
| Dependent enumeration sweep (D-13) | API/Backend | Browser/Client (manual UI check for saved views/dashboards) | Lists and Flows have documented, scriptable list endpoints; saved views and dashboards/reports have **no** documented public API (confirmed this session) and must be checked by a human in the portal UI. |
| Portal-facing regression guards (D-17) | API/Backend (repo test suite) | — | `test_rubric_change_guard.py`-shaped offline pin + `check_schema_drift.py`'s live comparator; both run from CI/local, never touch the browser tier. |

## Standard Stack

This phase uses no new libraries or npm/pip packages. The "stack" is entirely HubSpot's own APIs,
already in use elsewhere in this repo.

### Core

| API surface | Version in use | Purpose | Why standard (for this repo) |
|---|---|---|---|
| CRM v3 Properties API | `crm/v3/properties/companies` | Create the calculated string property, archive the old enum | Every other property in `config/hubspot_properties.yaml` is managed through this surface; `scripts/sync_hubspot_properties.py` already talks to it (though it has no `calculationFormula` precedent — this phase's create call is the first). [VERIFIED: config/hubspot_properties.yaml:434-439, config/hubspot_flows/lv_icp_fit_score-property.after.json (full file, read this session)] |
| Automation v4 Flows API | `automation/v4/flows/{id}` | Toggle WF1 `isEnabled` | Phase 40-01 already live-proved `PUT /automation/v4/flows/{id}` accepts action-content edits on this exact flow ID's sibling flows; `4625147345`'s own `.after.json` is committed and matches this surface's response shape. [VERIFIED: config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json:304 `"id": "4625147345"`, :312 `"type": "PLATFORM_FLOW"`] |
| CRM v3 Lists API | `crm/v3/lists` | Part of D-13's dependent sweep | `GET /crm/v3/lists` (paginated) enumerates lists; each list's filter-branch definition is returned when the `includeFilters`-equivalent flag is requested. [CITED: developers.hubspot.com/docs/api-reference/latest/crm/lists/list-filters] |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|---|---|---|
| Calculated **string** property (D-01's forced choice) | Calculated **enumeration** property | Not available in this portal per the spike's finding (0/264 calculated enumerations; HubSpot KB states enumeration is unsupported as a calculation output). One external, non-official source found during this session (insidea.com blog) claims `calculation_equation` supports `type: enumeration` — this contradicts the spike and D-01's premise, but D-01 is a **locked decision** already made on the spike's authority; this discrepancy is noted for completeness only and does not reopen D-01. |
| A fresh two-key-gated probe script (D-05) | Reusing `spike_tier_formula*.py` | Explicitly rejected — Phase 49 code review CR-01 flagged the spike scripts as single-key-gated and deliberately not kept in `scripts/`. |

**Installation:** none. No `pip install` / `npm install` required for this phase.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌────────────────────────────┐
                         │  HubSpot company record     │
                         │  (5 scoring components,     │
                         │   lv_icp_fit_score,          │
                         │   lv_anti_icp_flag)          │
                         └──────────────┬───────────────┘
                                        │ read, server-side, every request
                                        ▼
                    ┌───────────────────────────────────────┐
                    │  lv_icp_tier_derived                    │
                    │  (calculated string, calculationFormula)│
                    │  if coalesce(lv_anti_icp_flag,0)=1→"D"  │
                    │  elseif score>=70 →"A" elseif >=40→"B"  │
                    │  elseif >=15 →"C" else "Unscored"       │
                    └──────────────┬───────────────────────┘
                                   │ recomputes on every read, NO event needed
                                   ▼
                     (record view / list filter / report reads
                      the derived value directly — no workflow in the path)

     ── retired path, D-08/D-06 ──────────────────────────────────────
     [old] property-change event (lv_anti_icp_flag OR lv_icp_fit_score)
              │ HAS_COMPLETED, shouldReEnroll:true
              ▼
     [old] WF1 (4625147345, EVENT_BASED) ──writes──▶ lv_icp_tier (enum)
              ▲
              │ value-identical PATCH ⇒ NO event ⇒ NEVER re-enrolls
              │ (root cause of the 4 stuck records — this is the class
              │  the derived property removes structurally, not by patching
              │  this one instance)
     ──────────────────────────────────────────────────────────────────

  D-13 dependent sweep (before cutover):
    scripted, re-runnable ──▶ Lists API (GET /crm/v3/lists, filter branches)
                          ──▶ Automation v4 Flows API (GET .../flows, grep body)
    manual, UI-only       ──▶ saved views (index-page filters) — no public API
                          ──▶ reports/dashboards — no public API to list them
```

### Recommended Project Structure

No new directories. New files land in existing conventions:

```
scripts/
├── check_tier_null_propagation.py   # D-05's fresh, two-key-gated live null probe
├── check_tier_derived_parity.py     # D-07's gate — diffs derived vs WF1 across all 66
├── sweep_tier_dependents.py         # D-13's read-only, re-runnable dependent sweep
tests/
├── test_tier_formula_pin.py         # D-17 item 1 — live formula vs config/icp_scoring.yaml, key-by-key
config/hubspot_flows/
├── lv_icp_tier_derived-property.before.json / .after.json   # D-17 item 3
config/
├── hubspot_properties.yaml           # D-17 item 3 — new property declared
.planning/phases/50-derived-tier-property/
├── 50-TIER-PARITY-EVIDENCE.md        # D-17 item 4 — the committed comparison artifact
```

### Pattern 1: Statement-form calculated property, matching a live existence proof

**What:** The Properties API's `calculationFormula` field uses `if cond then stmt [elseif ...]
[else stmt]`, a different grammar from HubSpot's published UI-editor docs (`if(cond, a, b)`
bracket-ref form). Do not port syntax between the two.

**When to use:** Any new `calculation_equation` property in this portal.

**Example — the spike's accepted, 7/7-tested ladder, verbatim** [SETTLED:
.planning/TIER-DERIVATION-SPIKE-2026-08-13.md, Round 2]:

```
if coalesce(lv_anti_icp_flag, 0) = 1 then "D"
elseif lv_icp_fit_score >= 70 then "A"
elseif lv_icp_fit_score >= 40 then "B"
elseif lv_icp_fit_score >= 15 then "C"
else "Unscored"
```

**Existence proof this portal already runs statement-form grammar in production** [VERIFIED:
`hs_task_label`'s stored formula, quoted in the spike]:
```
if is_present(string(name)) then string(name) else string(domain)
```

### Pattern 2: Live-captured schema as the create-request template

**What:** the exact, live-read-back shape of the portal's one existing calculated property.

**Example** [VERIFIED: config/hubspot_flows/lv_icp_fit_score-property.after.json, full file, read
this session]:

```json
{
  "calculated": true,
  "calculationFormula": "org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)",
  "fieldType": "calculation_equation",
  "formField": false,
  "groupName": "companyinformation",
  "hasUniqueValue": false,
  "label": "ICP Fit Score",
  "modificationMetadata": {
    "archivable": true,
    "readOnlyDefinition": false,
    "readOnlyValue": true
  },
  "name": "lv_icp_fit_score",
  "type": "number"
}
```

For `lv_icp_tier_derived`, the create-request body should mirror every field here except
`type`/`fieldType`'s value pairing (`type: string`, `fieldType: calculation_equation` still, per
HubSpot's supported-types model — string IS a documented supported calculation output type,
unlike enumeration) and `calculationFormula` (Pattern 1's ladder). `modificationMetadata` is a
**response-only** field HubSpot computes — it is not something the create request sets; the create
request supplies `calculationFormula`, HubSpot derives `readOnlyValue: true` from the presence of
`calculated: true`. [INFERRED from the symmetry of `lv_icp_fit_score`'s create-time fields vs. its
read-back `modificationMetadata` — not independently confirmed by fetching the create-request
schema doc, which returned incomplete field coverage this session; see Open Questions Q5.]

### Anti-Patterns to Avoid

- **Porting `if(cond, a, b)` bracket-ref syntax into the API call** — SETTLED 400 by the spike;
  the API grammar is statement-form only.
- **Treating a booked/planned company write as free because "it's just a schema change"** — D-16
  is explicit that any company-record write is a deviation, not a budgeted allowance. The
  perturb-then-restore mechanism discussed under Q1 below IS a company write and must be treated
  with the same armed/capped/disarm-verified discipline as every prior phase's write windows, if
  it is ever exercised.
- **Assuming a same-value PATCH will trigger anything** — PORTAL-FACTS.md's 2026-08-13 entry
  proves a byte-identical batch PATCH is a true no-op: no `hs_lastmodifieddate` bump, no
  property-change event, `shouldReEnroll: true` notwithstanding.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Forcing HubSpot workflow re-evaluation | A custom "poke" mechanism that PATCHes an unrelated property hoping it cascades | Nothing exists that does this cleanly — see Q1. If a forced re-grade is ever needed, the only real options are UI manual-enroll (workflow must be ON) or a genuine trigger-property perturb-and-restore write, both first-class, both auditable. Do not invent a third path (e.g., abusing a webhook subscription retry) that has no live-proven precedent in this portal. | A clever workaround here is exactly the kind of thing that looks clever and breaks silently — this portal's history (WINDOWS.md #2, #3, #8) is full of exactly this failure mode. |
| Detecting portal dependents on a property | Manually clicking through every list/report in the UI with no record of what was checked | D-13's scripted sweep against Lists API + Flows API, **plus** an explicit, dated manual-check log for saved views and reports/dashboards (since those have no API) | The sweep must be re-runnable immediately before cutover (D-13); an undocumented one-time manual click-through cannot be re-run or audited. |

**Key insight:** this phase's hard problems are not code problems — they are "does an API exist
for X" problems, and the honest answer for the two hardest ones (forced re-enrolment, saved-view
enumeration) is **no**. The plan should be built around that negative, not around inventing a
workaround that papers over it.

## Runtime State Inventory

This phase is a property migration with real portal-side runtime dependents (D-12/D-13), so this
section applies even though it is not a rename/rebrand of code.

| Category | Items found | Action required |
|---|---|---|
| Stored data | `lv_icp_tier` values on the 66 already-scored companies (A/B/C/D/Unscored strings written by WF1) and on ~646 never-scored companies (blank). No datastore outside HubSpot stores tier. | None — the derived property computes independently; no backfill/migration of stored values needed. The old enum's stored values become dead once WF1 stops writing and the property is archived (D-06). |
| Live service config | **HubSpot Automation Flow `4625147345`** ("WF1 Set ICP Tier based on ICP Score") — its enrollment criteria and 5-branch action tree exist only in the portal's live Automation config, mirrored in `config/hubspot_flows/4625147345-wf1-set-icp-tier.{before,after}.json` but that mirror is a **snapshot**, not the source of truth. Also **portal-side lists/saved views/reports** (D-12) that filter or group on the tier select — confirmed to exist by the operator, invisible from the repo. | Toggle `isEnabled: false` via `PUT /automation/v4/flows/4625147345` (D-08). Keep definition (do not delete). D-13's sweep enumerates the list/report dependents before cutover; each must be repointed or the operator checkpointed per D-11. |
| OS-registered state | None — no cron, launchd, or Task Scheduler entries reference `lv_icp_tier` (confirmed by grep of `.planning/` and `scripts/`; nothing in this phase's scope touches scheduled infrastructure beyond the already-scheduled maintenance flows, which do not reference the tier property [VERIFIED: `tests/test_hubspot_schema_coverage.py`'s own sticky-note-exclusion comment quotes `wf_scheduled_maintenance_cloud.json`'s prose note that "SJ-1/2/3 never reference `lv_icp_scored_at`" — the adjacent, not-yet-live tier-freshness field; `lv_icp_tier` itself is absent from every `n8n/wf_*_cloud.json` file per the spike's blast-radius finding]). | None. |
| Secrets/env vars | None — no secret or env-var name encodes `lv_icp_tier` or `tier`. | None. |
| Build artifacts / installed packages | `config/hubspot_flows/lv_icp_tier-property.{before,after}.json` and `4625147345-wf1-set-icp-tier.{before,after}.json` are committed **snapshots**, not live state, but will read as stale documentation the moment this phase lands unless refreshed (D-17 item 3). `scripts/check_schema_drift.py`'s `DO_NOT_ARCHIVE_COMPANY_PROPERTIES` frozenset (line 75, `"lv_icp_tier"`) and `DO_NOT_ARCHIVE_FLOW_IDS` dict (line 88, `"4625147345": "wf1-set-icp-tier"`) are **enforcement code**, not documentation — see § Common Pitfalls Pitfall 2, this is the single most important finding of this research. | Update both structures in the same commit that disables WF1 and archives `lv_icp_tier`, or `scripts/check_schema_drift.py` will report `exit_code_for() == 2` ("do-not-archive invariant violated / live scoring engine damaged") for a deliberate, correct state. |

## Common Pitfalls

### Pitfall 1: Assuming the D-18 rollback story can be "re-enable and it converges"

**What goes wrong:** A plan that says "if the derived property is wrong, just re-enable WF1" ships
a rollback that does nothing for any record whose `lv_anti_icp_flag`/`lv_icp_fit_score` values are
already correct — which, by definition, is every record the derived property computed correctly.
Re-enabling WF1 alone can only re-grade a record via a **future** property-change event; it cannot
re-evaluate current state.

**Why it happens:** `shouldReEnroll: true` reads as "will re-check," but HubSpot's own no-op
semantics (PORTAL-FACTS.md 2026-08-13) mean a value-identical write fires no event at all —
re-enrollment needs an event to re-enroll *on*, and there is none.

**How to avoid:** D-18 already names this correctly as the phase's crux. This research's
contribution is settling *what the forced mechanism actually is*: not an API call (none exists —
Q1), but either (a) portal-UI manual "Enroll now" (requires WF1 to be **on**, which the rollback
plan can do — re-enabling WF1 is exactly step 1 of D-18's own rollback), performed by a human, or
(b) an armed, capped, disarm-verified perturb-then-restore double-write on the trigger property
(two real per-record HubSpot writes, in-scope for an armed window under this phase's existing
write-window discipline, but a genuine deviation from D-16's "zero company write windows" if ever
exercised — which is fine, since D-18's rollback is explicitly an *emergency* path, not the happy
path).

**Warning signs:** A rollback runbook that says "toggle WF1 back on" with no second step.

### Pitfall 2: `check_schema_drift.py`'s do-not-archive invariant will hard-fail on this phase's own success

**What goes wrong:** `exit_code_for()` [VERIFIED: scripts/check_schema_drift.py:219-228] returns
`2` — its most severe class, documented in its own docstring as "the live scoring engine itself is
damaged" — whenever `report["do_not_archive"]["ok"]` is `False`. `_compute_do_not_archive()`
[VERIFIED: scripts/check_schema_drift.py:231-246] computes that flag as:

```python
ok = all(p["live"] for p in properties) and all(f["live"] and f["is_enabled"] for f in flows)
```

`DO_NOT_ARCHIVE_COMPANY_PROPERTIES` [VERIFIED: scripts/check_schema_drift.py:68-80, quoted
verbatim]:
```python
DO_NOT_ARCHIVE_COMPANY_PROPERTIES = frozenset({
    "org_type_score", "geography_score", "annual_revenue_score",
    "produces_content_score", "gambling_score", "lv_icp_fit_score",
    "lv_icp_tier", "lv_anti_icp_flag", "lv_org_type",
    "lv_produces_content", "lv_country_region_normalized",
})
```
`DO_NOT_ARCHIVE_FLOW_IDS` [VERIFIED: scripts/check_schema_drift.py:84-91, quoted verbatim]:
```python
DO_NOT_ARCHIVE_FLOW_IDS = {
    "4626124224": "org-type-score", "4626722240": "geography-score",
    "4626722237": "annual-revenue-score", "4625147345": "wf1-set-icp-tier",
    "4634822079": "produces-content-score", "4634822085": "gambling-score",
}
```
Both `lv_icp_tier` and `"4625147345"` appear in these structures. D-06 archives `lv_icp_tier`
(`p["live"]` becomes `False`); D-08 flips WF1's `isEnabled` to `False` (`f["is_enabled"]` becomes
`False`). Either one alone flips `ok` to `False` and `exit_code_for()` to `2` — the same code class
this comparator uses to signal live portal damage.

**Why it happens:** these two structures were written in Phase 42 with a "never archived by
anything" invariant baked in [VERIFIED: scripts/check_schema_drift.py:65-67, comment: "D-01
(42-CONTEXT.md) -- the live scoring engine's company properties. NEVER archived by anything in
Phase 42."]. Phase 42's guard had no way to anticipate a future phase whose entire point is to
retire one of the protected names.

**How to avoid:** this is a required same-commit edit, not covered by D-17's literal wording ("it
currently pins `lv_icp_tier`'s five-value enum (line ~119) and carries `PARITY-01-tier-label` as
an accepted divergence; both go stale") — that wording undersells the severity. The actual fix
needed: remove `"lv_icp_tier"` from `DO_NOT_ARCHIVE_COMPANY_PROPERTIES` and either remove
`"4625147345"` from `DO_NOT_ARCHIVE_FLOW_IDS` or change the `ok` computation to accept
`is_enabled: False` for a flow whose retirement is deliberate (the D-08 "kept but off" state needs
its own truth value distinct from "missing entirely," which the current `f["live"] and
f["is_enabled"]` conjunction cannot express). Whichever shape is chosen, it must land in the same
commit as the archive/disable actions — a schema-drift run between those two events and this fix
would report false portal damage.

**Warning signs:** `scripts/check_schema_drift.py` (or its CI equivalent) newly reporting exit
code 2 with no other explanation immediately after Phase 50's gated retirement step.

### Pitfall 3: Trusting a positive third-party source over the spike's own live 400 body

**What goes wrong:** an external blog (insidea.com) claims `calculation_equation` supports
`type: enumeration`, which if believed would reopen D-01's "new property, not in-place formula
edit" premise.

**Why it happens:** third-party HubSpot content frequently describes aspirational or
version-drifted capability, not this portal's actual, live-tested behavior.

**How to avoid:** trust the spike's live 400-body evidence (0/264 calculated enumerations in this
portal, HubSpot's own KB text as quoted in the spike) over any unofficial secondary source. D-01
is a locked decision either way — this pitfall exists only to warn a future re-reader not to
"helpfully" revisit it based on the blog.

## Code Examples

### The 4 stuck records — exact identity, for D-10's read-back verification

[VERIFIED: `.planning/WINDOWS.md` ids 9-12, quoted verbatim]

| id | company | `lv_icp_fit_score` (correct) | current stale `lv_icp_tier` | expected derived tier |
|---|---|---|---|---|
| `9605273630` | Port Macquarie Race Club | 45 | `C` | `B` |
| `9604738976` | Bunbury Turf Club | 45 | `C` | `B` |
| `17696004613` | Pinjarra Park | 45 | `C` | `B` |
| `19100977027` | Newcastle Harness Racing Club | 45 | `C` | `B` |

### WF1's live enrollment criteria (the event dependency the derived property removes)

[VERIFIED: config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json:240-302, quoted
verbatim]:
```json
"enrollmentCriteria": {
  "eventFilterBranches": [
    { "eventTypeId": "4-655002", "operator": "HAS_COMPLETED",
      "filters": [
        {"property": "hs_name", "operation": {"operator": "IS_EQUAL_TO", "value": "lv_anti_icp_flag"}},
        {"property": "hs_value", "operation": {"operator": "IS_KNOWN"}}
      ]},
    { "eventTypeId": "4-655002", "operator": "HAS_COMPLETED",
      "filters": [
        {"property": "hs_name", "operation": {"operator": "IS_EQUAL_TO", "value": "lv_icp_fit_score"}},
        {"property": "hs_value", "operation": {"operator": "IS_KNOWN"}}
      ]}
  ],
  "shouldReEnroll": true,
  "type": "EVENT_BASED"
}
```

### `tier_rules` — the source of truth the derived formula and the pin test both mirror

[VERIFIED: config/icp_scoring.yaml:55-83, quoted verbatim]:
```yaml
tier_rules:
  A: { min_score: 70, max_score: 999, requires_no_hard_veto: true }
  B: { min_score: 40, max_score: 69, requires_no_hard_veto: true }
  C: { min_score: 15, max_score: 39, requires_no_hard_veto: true }
  D: { hard_veto: true }
  Unscored: { missing_required_inputs: true }
```

### The forced-recompute precedent, and precisely what it does NOT reach

[VERIFIED: scripts/remediate_veto_companies.py:596-625, `post_webhook_event`, docstring and body
quoted]. This function POSTs to `{n8n_url}/webhook/hubspot/enrichment/event` with header
`X-Enrichment-Secret`, driving **n8n's own veto-recompute lane** (Phase 47.5), which ends in an
n8n `HubSpot Company Update` node PATCHing `lv_anti_icp_flag`/`lv_anti_icp_reason` directly. It
never touches HubSpot's native Automation platform, never calls `/automation/v4/flows/*`, and has
no code path that could re-enroll a **HubSpot-native flow** like WF1. If the PATCH it produces
changes `lv_anti_icp_flag`'s value, that PATCH *would* itself fire a property-change event WF1
listens for — but only if the value actually changes; a record whose flag is already correct is,
by this mechanism, in exactly the same unreachable state PORTAL-FACTS.md's 2026-08-13 entry
describes for `lv_icp_fit_score`. **The precedent does not transfer to WF1 retirement.**

## State of the Art

| Old approach | Current approach | When changed | Impact |
|---|---|---|---|
| `lv_icp_tier` as a plain `enumeration`, written by an `EVENT_BASED` HubSpot Automation flow | `lv_icp_tier_derived` as a `calculation_equation` string property, self-computing on every read | This phase | Removes the entire "stale tier vs. correct score" bug class, not just the 4 known instances (TIER-01). |
| Ad-hoc, per-issue spike scripts gated on a single env var (`ALLOW_SPIKE_PROPERTY_WRITE`) | Permanent, two-key-gated scripts kept in `scripts/`, mirroring the repo's `DRY_RUN=false` + feature-specific-allow-key pattern | Phase 49 code review CR-01, applied here via D-05 | Live-write probes become auditable, reusable infrastructure instead of one-shot, discarded scripts. |

**Deprecated/outdated:** none specific to this phase beyond the WF1 retirement itself, which is
explicitly *not* a deletion (D-08) — "deprecated but present" is itself the target state.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | The create-request body for `lv_icp_tier_derived` needs only `calculationFormula` set (with `calculated: true` implied), and HubSpot derives `modificationMetadata.readOnlyValue: true` automatically, mirroring `lv_icp_fit_score`'s read-back shape. | Architecture Patterns, Pattern 2 | Low — if HubSpot instead requires an explicit `modificationMetadata`/`readOnlyValue` field in the request, the create call 400s immediately and visibly; not a silent-failure risk. |
| A2 | Calculated **string** output is supported in this portal the same way calculated **number** output already is (only calculated **enumeration** is confirmed unsupported). | Standard Stack, Alternatives Considered | Low-medium — HubSpot's own docs list `string` as a supported calculation type alongside `number`/`bool`/`date`; not independently live-tested by this research (that would require a write, forbidden here) but is consistent with the spike's `hs_task_label` existence proof, which is itself a calculated **string** property. |
| A3 | Neither saved views (index-page filters) nor reports/dashboards have any documented public HubSpot API for enumeration as of this session. | Open Questions Q3 | Medium — HubSpot ships new API surfaces continuously; if a reports-listing API exists but wasn't surfaced by this session's searches, D-13's sweep would under-cover and the manual-UI fallback would be doing unnecessary work. Recommend one more targeted check (HubSpot's own changelog for "Reporting API" / "Saved Views API") at plan time before committing to the manual-only path. |

## Open Questions

### Q1 (D-18, sharpest — RESOLVED to a documented negative)

**What we know:** HubSpot's Automation v4 Flows API documents create/read/read-batch/update/delete
for flow *definitions* — no enrollment endpoint of any kind [DOCUMENTED:
developers.hubspot.com/docs/guides/api/automation/workflows-v4, confirmed via WebFetch this
session]. A legacy v2 endpoint exists (`PUT /automation/v2/workflows/{workflowId}/enrollments/
contacts/{email}`) but is explicitly **contacts-only** (the path literally names the object type)
and is flagged for future deprecation [DOCUMENTED: legacydocs.hubspot.com/docs/methods/workflows/
current_enrollments; community threads confirming v2/v4 workflow-id mismatch issues, via
WebSearch]. HubSpot's own knowledge base describes manual enrollment as **UI-only**: "you can also
manually enroll records from within a workflow or an object's index page... the workflow must be
turned on; you cannot manually enroll records when a workflow is turned off... If you're trying to
manually enroll a record that has previously gone through the workflow, you must turn on and
select re-enrollment triggers" [CITED: knowledge.hubspot.com/workflows/manually-enroll-objects-into-
workflows].

**What's unclear:** whether any *undocumented* or partner-tier API surface exists that this
session's search did not surface. Given the exhaustiveness of the official v4 docs page (6
documented endpoints, none an enrollment call) this is judged unlikely but not eliminated.

**Recommendation:** treat D-18's rollback as resolved to: **step 1**, re-enable WF1
(`isEnabled: true`, proven-live mechanism per Phase 40-01); **step 2 (forced re-grade)**, choose
explicitly between (a) portal-UI manual "Enroll now" bulk action — a human, out-of-API-scope step,
consistent with the spike's own "portal-side dependents...may need a manual/UI step" framing — or
(b) an armed, capped, disarm-verified perturb-then-restore double-write on `lv_anti_icp_flag` or
`lv_icp_fit_score` for the specific records needing re-grade, under this phase's existing
write-window discipline (D-16 already anticipates deviations require justification — this would be
exactly such a justified deviation, and only in the rollback/emergency path, never the happy path).
Do **not** write a rollback runbook that stops at step 1.

### Q2 (D-15, rename feasibility — RESOLVED, matches CONTEXT.md's own suspicion)

**What we know:** "Once created, the internal name cannot be edited anymore" is stated
consistently across HubSpot community threads and confirmed by the absence of any `name`-mutating
field in the Properties API's update documentation [CITED: multiple community.hubspot.com threads,
via WebSearch, cross-consistent]. Archived-property name reuse: "You can recreate/reuse the same
internal name/label of a property deleted over 90 days" and "hover over the property, hit delete,
then create the new property... tested to work" for immediate reuse after a *permanent* delete
(distinct from a soft archive) [CITED: community.hubspot.com threads on property deletion, via
WebSearch]. Archive vs. permanent delete: archiving preserves the property (and its data) for 90
days in an "Archived" tab, restorable within that window; after 90 days it is permanently deleted
[CITED: knowledge.hubspot.com/properties/organize-and-export-properties, via WebSearch summary —
not independently re-fetched from the primary page this session, so tagged CITED not VERIFIED].

**What's unclear:** the exact mechanics of the CRM v3 Properties API's own `DELETE` call — whether
it performs a soft archive (matching the UI 90-day model) or something else — were not resolvable
from the developer-docs page fetched this session (it covered POST/GET/PATCH only, not DELETE).

**Recommendation:** D-15's fallback (keep `lv_icp_tier_derived` permanently, change only the
label) is the right default to plan around. If a rename is attempted, the mechanism is:
permanently delete the archived `lv_icp_tier` (not merely soft-archive it — the 90-day path likely
still blocks immediate name reuse per the "hasUniqueValue" community caveat and general caution
around re-using a name with live history), then create `lv_icp_tier` fresh and migrate
`lv_icp_tier_derived`'s formula onto it. This is a genuinely separate, higher-risk action beyond
D-06's own archive step and should not be attempted in the same window as D-06/D-07's gate. Mark
this **UNKNOWN-NEEDS-EXECUTION-TIME-PROBE** for the exact DELETE-call semantics in this portal
specifically (soft archive vs. hard delete via the API, not just the UI) before any rename attempt
— do not probe live now.

### Q3 (D-13, dependent enumeration — RESOLVED, mixed)

**What we know:** Lists API (`GET /crm/v3/lists`, paginated, with per-list filter-branch retrieval)
and Automation v4 Flows API (`GET /automation/v4/flows`, batch read, full `enrollmentCriteria` +
`actions` body) are both scriptable and can be grepped for `lv_icp_tier` references — this repo
already does exactly this for flows (`config/hubspot_flows/*.json` snapshots, the spike's own
method). [CITED: developers.hubspot.com/docs/api-reference/latest/crm/lists/list-filters,
Automation v4 docs already fetched for Q1]. Saved views (index-page filters, distinct from Lists)
have **no documented public API** — search results returned only UI-facing knowledge-base articles
[DOCUMENTED-ABSENCE: WebSearch for "HubSpot saved views API endpoint," no API doc surfaced].
Reports/dashboards similarly have **no documented API to enumerate them**: "Currently, HubSpot does
not provide a direct API endpoint to list all dashboards or reports" [CITED: community.hubspot.com
thread + scopiousdigital.com FAQ, cross-consistent, via WebSearch].

**What's unclear:** whether a Reporting API scoped for other purposes (e.g., pulling report *data*)
incidentally exposes a way to enumerate report *definitions* by property reference — not confirmed
either way this session.

**Recommendation:** D-13's script should cover Lists + Flows programmatically (re-runnable, as
required). Saved views and reports/dashboards need an explicit, dated, logged manual check in the
portal UI — treat as confirmed API-blind, not as a gap in the sweep's implementation.

### Q4 (D-04, null propagation in an untaken branch — genuinely UNKNOWN, this is the phase's real open risk)

**What we know:** Phase 41 live-proved that HubSpot blanks a `calculation_equation` result entirely
when *any* referenced term is null, for a **bare arithmetic sum** [VERIFIED:
.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md:186-196,
quoted: "`lv_icp_fit_score`'s `calculation_equation` formula does not treat a missing/null
referenced property as `0` — it returns blank... One null term blanks the entire sum."]. Whether
that same blanking behavior fires when the null term sits inside a **conditional branch that is
never taken** — e.g. `lv_icp_fit_score` referenced bare in the `elseif lv_icp_fit_score >= 70`
branches, for a company whose score is null — is exactly what decides TIER-02's outcome, and it is
explicitly unresolved by the spike ("Runtime null propagation inside a conditional... is
**unknown**, and it decides which variant ships").

**What's unclear:** everything about branch-local evaluation order in HubSpot's calculation engine
— whether it short-circuits on the taken branch only, or eagerly evaluates/type-checks every
referenced property across all branches before selecting one.

**Recommendation (this is D-05's job, not this research's):** the minimal live test is: (1) create
a disposable calculated string property with the accepted 7/7 ladder formula, referencing a
disposable numeric property in place of `lv_icp_fit_score`; (2) create a disposable company with
that numeric property left null (never set, not zero); (3) read the calculated property back —
**blank result** = null propagates even through an untaken branch, ship `coalesce(...,-1)` per
D-04's forced fallback; **`"Unscored"` result** = the uncoalesced variant works as D-03 prefers;
(4) archive both disposables in a `finally`, verify gone by 404 re-read. No company record from
the live population is touched. This is precisely what D-05 already specifies — this research adds
only the confirmation that no documentary source (HubSpot's own docs, any community thread found
this session) states the answer either way, so the live test is not optional groundwork, it is the
only source of truth available.

### Q5 (property-create contract — mostly resolved via the live-captured template, one gap named)

**What we know:** the exact create-time field set is inferable from `lv_icp_fit_score`'s live-read
schema (§ Code Examples) — `calculated: true` (implied by presence of `calculationFormula`, per
HubSpot's docs page fetched this session listing `calculationFormula` as the distinguishing field),
`type: string`, `fieldType: calculation_equation`, `groupName: companyinformation` (same group as
the existing `lv_icp_tier`, which the spike and this research find no evidence forbids —
calculated and non-calculated properties already coexist in `companyinformation`, e.g.
`lv_icp_fit_score` alongside `lv_icp_tier` itself today).

**What's unclear:** whether `modificationMetadata`/`readOnlyValue: true` needs to be explicitly
requested or is purely response-computed (Assumption A1).

**Recommendation:** treat A1 as a low-risk assumption (§ Assumptions Log) — a wrong create-request
shape 400s loudly, it does not create a silently-broken property.

### Q6 (archive contract — mostly resolved, one execution-time gap)

**What we know:** archiving via the portal UI moves a property to a 90-day-recoverable "Archived"
state; it is removed from record views, forms, list filters, and report builders during that
window but data is preserved; after 90 days, permanent [CITED:
knowledge.hubspot.com/properties/organize-and-export-properties, via WebSearch summary].

**What's unclear:** whether the CRM v3 Properties API's `DELETE` call performs exactly this soft
archive (matching D-06's stated intent — "archive... within Phase 50, but only as the last gated
step") or something stricter; the developers.hubspot.com DELETE endpoint page redirected to an
authenticated app URL and could not be fetched this session.

**Recommendation:** UNKNOWN-NEEDS-EXECUTION-TIME-PROBE for the exact API call this phase should
issue to archive `lv_icp_tier` — confirm at plan/execution time that the CRM v3 Properties
`DELETE /crm/v3/properties/{objectType}/{propertyName}` call is the soft-archive path (not a
permanent delete) before D-06's step runs, since D-06 is explicitly this phase's one irreversible
act and CONTEXT.md's own reversibility note for D-06 already flags this.

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| HubSpot Private App token (`HUBSPOT_PRIVATE_APP_TOKEN`) | All property/flow API calls | ✓ (per `.env`, unreadable directly but scripts using `load_dotenv()` work — established project pattern) | n/a | — |
| Portal ID guard (`HUBSPOT_EXPECTED_PORTAL_ID` / `HUBSPOT_PORTAL_ID`) | `scripts/check_schema_drift.py` and every schema-touching script | ✓, defaults to `22617666` in code [VERIFIED: scripts/check_schema_drift.py:63] | — | — |
| `automation` scope on the private app | Flows API read/write (WF1 toggle) | Assumed present — Phase 40-01 already exercised `PUT /automation/v4/flows/{id}` live against this exact flow's sibling flows | — | If missing, the PUT 403s immediately and visibly; no silent-failure risk. |
| Two-key gate env vars for D-05's fresh script (`DRY_RUN=false` + a new allow-key, name TBD by the planner) | D-05's live null probe | Not yet defined — this phase creates them | — | — |

**Missing dependencies with no fallback:** none identified.

**Missing dependencies with fallback:** none identified — all HubSpot API dependencies are already
proven live-reachable by prior phases against this exact portal.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest (Python, offline + live-gated) and `node --test` (n8n JS, not touched by this phase but part of the suite) |
| Config file | none dedicated — repo-wide `pytest.ini`/`conftest.py` absent per prior-phase memory; live tests gated by env vars (`RUN_LIVE_PARITY`-style flags), not pytest markers |
| Quick run command | `.venv/bin/python -m pytest tests/test_tier_formula_pin.py -x` (new, offline, D-17 item 1) |
| Full suite command | `.venv/bin/python -m pytest` (per project memory: system python lacks deps, `.venv/bin/python` required) plus `node --test tests/n8n/*.test.mjs` (glob form — directory form is broken on node 24, per project memory) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| TIER-01 | Derived formula string matches `config/icp_scoring.yaml`'s `tier_rules`, key-by-key | offline unit (pin test) | `.venv/bin/python -m pytest tests/test_tier_formula_pin.py -x` | ❌ Wave 0 — build in `test_rubric_change_guard.py`'s shape |
| TIER-01 | Derived value matches WF1's live value across all 66 scored companies, 4 named exceptions | live evidence artifact (not a pytest assertion — D-17 item 4 is explicitly "an evidence artifact, not a test") | `scripts/check_tier_derived_parity.py` (new), committed output to `50-TIER-PARITY-EVIDENCE.md` | ❌ Wave 0 |
| TIER-01 | The 4 stuck records read `B` post-cutover with zero writes to them | live read-back, D-10's own bar | Included in the same parity artifact above, cross-referenced against `.planning/WINDOWS.md` ids 9-12 | ❌ Wave 0 |
| TIER-02 | Blank-vs-`"Unscored"` semantics settled against live records | live disposable probe, D-05 | `scripts/check_tier_null_propagation.py` (new, two-key-gated), result recorded as a decision doc | ❌ Wave 0 |
| TIER-03 | Dependent sweep is scripted and re-runnable | offline-runnable script (network calls, but no fixture/mock needed — read-only against live) | `scripts/sweep_tier_dependents.py` (new), run twice: once during planning-adjacent research, once immediately pre-cutover | ❌ Wave 0 |
| TIER-03 | `check_schema_drift.py` exit code stays 0 (or documented-nonzero) after WF1-off + `lv_icp_tier` archived | offline/live comparator, existing tool | `python scripts/check_schema_drift.py` (existing) | ✓ exists, needs the Pitfall 2 edit before this phase's D-06/D-08 land |
| TIER-03 (D-07 gate) | Zero mismatches outside the 4 known exceptions | same as TIER-01's parity artifact | — | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** the offline pin test (`test_tier_formula_pin.py`) — sub-second, no network.
- **Per wave merge / before D-06's archive step:** `check_schema_drift.py` full run (must show
  `exit_code_for() == 0` or a *documented, expected* nonzero from the Pitfall 2 fix, never an
  *undocumented* 2).
- **Phase gate (before D-07's evaluation):** the full 66-company parity artifact, freshly generated
  against live HubSpot, not reused from a stale capture (matches this project's repeated
  "re-derive, never trust a stale snapshot" pattern from Phases 47-49).

### Wave 0 Gaps

- [ ] `tests/test_tier_formula_pin.py` — key-by-key pin of the derived `calculationFormula`
      against `config/icp_scoring.yaml`'s `tier_rules`, `test_rubric_change_guard.py`'s shape.
- [ ] `scripts/check_tier_derived_parity.py` — D-07's gate script, produces the D-17-item-4
      evidence artifact.
- [ ] `scripts/check_tier_null_propagation.py` — D-05's two-key-gated live probe.
- [ ] `scripts/sweep_tier_dependents.py` — D-13's scripted, re-runnable dependent enumeration.
- [ ] `scripts/check_schema_drift.py` — Pitfall 2's `DO_NOT_ARCHIVE_*` edit (not a new file, an
      edit to an existing one, but load-bearing enough to list here explicitly).

## Security Domain

This phase's blast radius is CRM schema (property create/archive) and workflow enable/disable, not
an application input surface — most ASVS categories are not applicable. Included per policy since
`security_enforcement` is not disabled in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS category | Applies | Standard control |
|---|---|---|
| V2 Authentication | No | No new auth surface; reuses the existing HubSpot Private App token, unchanged. |
| V3 Session Management | No | N/A — no session-bearing surface touched. |
| V4 Access Control | Marginal | HubSpot's own portal-level permission model (Super Admin / Workflows permission required for manual UI enrollment, per HubSpot's KB) gates the one human-in-the-loop fallback path in Q1 — this is HubSpot's control, not this repo's, and needs no new code. |
| V5 Input Validation | No | No user-facing input; `calculationFormula` is a fixed, spike-validated literal, not user input. |
| V6 Cryptography | No | Not touched. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard mitigation |
|---|---|---|
| Silent wrong-value computation from a booked assumption about HubSpot's type coercion (e.g. treating a boolean as Boolean when it arrives as BigDecimal in formula-land) | Tampering (data integrity, not an attacker) | Already the spike's own headline finding — `coalesce(lv_anti_icp_flag, 0) = 1`, never a bare boolean. The pin test (TIER-01's Wave 0 gap) is the durable guard against this regressing. |
| A calculated property becomes `readOnlyValue: true` on creation — this is a **positive** integrity control, not a threat: nothing (including a well-intentioned corrective script) can PATCH `lv_icp_tier_derived` once created, closing off an entire class of accidental-clobber risk the old writable enum carried. | — | No mitigation needed; noted as a property of the design worth stating explicitly to the planner so no task is written that tries to PATCH the new property. |

## Sources

### Primary (HIGH confidence)

- `.planning/TIER-DERIVATION-SPIKE-2026-08-13.md` — the phase's own primary source, verdict
  CONCLUSIVE POSITIVE on grammar (SETTLED per research constraints, not re-verified this session).
- `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json` — live-captured WF1 definition,
  read in full this session.
- `config/hubspot_flows/lv_icp_fit_score-property.after.json` — live-captured calculated-property
  schema, read in full this session, used as the create-request template.
- `scripts/check_schema_drift.py` — read this session, lines 55-246 covering both do-not-archive
  structures and the exit-code logic that Pitfall 2 depends on.
- `.planning/WINDOWS.md` ids 9-12 — the 4 stuck records, verbatim identity and root cause.
- `PORTAL-FACTS.md` (2026-08-13 entries) and
  `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md:186-196` —
  the two live-proven no-op/null-blanking findings this research builds on.

### Secondary (MEDIUM confidence)

- developers.hubspot.com/docs/guides/api/automation/workflows-v4 — fetched this session, confirms
  no enrollment endpoint exists in v4.
- knowledge.hubspot.com/workflows/manually-enroll-objects-into-workflows — WebSearch-summarized
  this session, UI-only enrollment mechanics.
- developers.hubspot.com/docs/api-reference/latest/crm/properties/create-property — fetched this
  session, calculated-property field list (partial — DELETE semantics not covered by this page).
- community.hubspot.com threads on internal-name immutability and archived-name reuse —
  cross-consistent across multiple independent threads, WebSearch-summarized this session.

### Tertiary (LOW confidence)

- insidea.com blog claiming `calculation_equation` supports `type: enumeration` — contradicts the
  spike's live evidence and D-01's premise; flagged, not trusted, does not reopen D-01.
- Various WebSearch-summarized community threads on saved-views/reports API absence — consistent
  with each other and with the official docs' silence on the topic, but none is an authoritative
  "this does not exist" statement from HubSpot itself.

## Metadata

**Confidence breakdown:**
- Formula grammar / standard stack: HIGH — settled by the spike, corroborated by a live-read
  template this session.
- D-18 forced-enrolment mechanism: MEDIUM-HIGH — resolved to a documented negative from HubSpot's
  own current API docs and KB, but "no undocumented API exists" can never be proven with full
  certainty from documentation alone.
- D-04/TIER-02 null propagation in an untaken branch: LOW / genuinely UNKNOWN — no documentary
  source settles this; D-05's live probe is the only path to an answer, and this research could not
  and should not attempt it (write-forbidden).
- `check_schema_drift.py` do-not-archive collision (Pitfall 2): HIGH — verified by reading the
  actual code this session, not inferred.
- D-15 rename feasibility / D-13 dependent enumeration: MEDIUM — consistent, cross-corroborated
  community and KB sources, but the authoritative DELETE-endpoint page could not be fetched
  (auth-gated redirect) and a Reporting-API enumeration gap cannot be ruled out with full certainty.

**Research date:** 2026-08-13
**Valid until:** ~30 days for the HubSpot-API-surface findings (Q1/Q2/Q3/Q6 — HubSpot ships new
endpoints continuously; re-check before acting if this phase is picked up more than a month out);
indefinite for the repo-internal findings (Pitfall 2, the live-captured schema templates) unless
`scripts/check_schema_drift.py` or `config/hubspot_properties.yaml` change again in the interim.
