# Phase 75: Config-driven region whitelist and scoring-version staleness - Research

**Researched:** 2026-09-20
**Domain:** Internal codegen (yaml → generated JS), HubSpot schema/flow migration, n8n Cloud
workflow topology (recompute lane, SJ-2 scheduled sweep), write-safety arming
**Confidence:** HIGH (every claim below is grounded in a file this session actually opened with
`Read`/`cat -n`/`sed -n`; nothing here rests on training-data assumptions about this repo)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Veto reason string**
- **D-75-01:** Rename the geography veto reason now, region-agnostic. Default string
  `"Outside target regions"` (Claude's discretion on exact wording; no region suffix — tests
  assert byte-equality on one constant). — **Reversibility:** costly — ~15 asserting test sites
  (`tests/test_scoring_parity.py`, `tests/test_icp_scoring.py`,
  `tests/test_veto_remediation_report.py`, `tests/test_simulate_rubric_weights.py`,
  `tests/test_remediate_veto_companies.py`, `tests/test_backfill_dry_run.py`,
  `tests/n8n/antiIcpFlagMirror.test.mjs`, `tests/n8n/companyRecomputeLaneFlow.test.mjs`,
  `tests/n8n/materialConflictNoVetoFlip.test.mjs`, `tests/n8n/reviewQueueEndpoint.test.mjs`,
  `tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs`) change with it, and
  `lv_anti_icp_reason` churns once on every vetoed record at its next recompute.
- **D-75-02:** ALL THREE hard-veto reason strings come from `config/icp_scoring.yaml`
  (`hard_vetoes.<key>.reason`) via the generated JS (`HARD_VETO_REASONS` or equivalent).
  `Decide Company Action` (`scripts/build_cloud_workflows.py`, the three hard-coded
  `vetoReasons.push(...)` literals) stops hand-typing any of them. `src/icp_scoring.py` already
  reads them from yaml. Content and hardware strings keep their current VALUES.
- **D-75-03:** Records already carrying `"Non-ANZ geography"` are refreshed by the
  `config.version` bump + stale sweep only. No dedicated armed remediation script for the
  string.
- **D-75-04:** Frozen runData fixtures (`tests/n8n/fixtures/frozen/*`) and stress logs
  (`tests/stress-tests/*`) stay byte-identical — they are recordings, refresh policy none
  (README). Only tests that ASSERT the string change. Optional, additive only: freeze the
  phase-exit proof executions as a new fixture showing the new string.

**Whitelist + enum contents**
- **D-75-05:** `regions.home` from day one = `AU, NZ, ANZ, US, GB, IE, CA, ZA, HK, SG, AE, IN`.
  Selection criteria (record in the yaml comment): English-speaking or native-English-audience
  market with a strong sports-broadcasting ecosystem. Considered and NOT included: `NG`, `KE`,
  `JM`, `PH`. — **Reversibility:** reversible — one-line yaml edit + version bump; but note
  every currently-vetoed company whose region resolves into this set flips at the first armed
  sweep, and the flip COUNT is unknown offline (researcher: size it before the first armed
  sweep).
- **D-75-06:** The normalisers emit the alias region code for any KNOWN mapped country
  (`US`, `GB`, `IE`, `CA`, `ZA`, `HK`, `SG`, `AE`, `IN`, plus `AU`/`NZ`); an unmapped known
  country still emits `Other`; blank/absent still emits the lane's blank sentinel (JS `null`,
  Python `"Unknown"`, ZoomInfo `None` — the existing per-lane contract is unchanged). Today
  everything non-AU/NZ collapses to `Other`, which is why a whitelist edit alone cannot rescue
  an already-stamped record (see Open items).
- **D-75-07:** Region token for the United Kingdom is `GB` (ISO2, matches the existing phone
  map). The existing `UK` enum option on `lv_country_region_normalized` is HIDDEN
  (`hidden: true`), never deleted. New enum options `GB, IE, CA, ZA, HK, SG, AE, IN` are added in
  `config/hubspot_properties.yaml`; `n8n/code/hubspotEnums.generated.js` is regenerated
  (`scripts/gen_hubspot_enums_js.py`). `EU` option: leave as-is (no alias emits it; Claude's
  discretion). — **Reversibility:** costly — HubSpot enum option delete is destructive; hide is
  the only undo.
- **D-75-08:** `regions.aliases` in `config/icp_scoring.yaml` is the SINGLE source for
  country-name/ISO2 → region code. `scripts/gen_icp_scoring_js.py` emits `REGION_ALIASES`, and
  that generated constant REPLACES the hand-typed `_COUNTRY_ISO2` map in
  `n8n/code/normalizeProviders.js` (phone normalisation reads the generated constant). The
  aliases table MUST be a superset of `_COUNTRY_ISO2`'s existing keys (`canada`, `ireland`,
  `india`, `singapore`, `great britain`, `england`, `united states of america`, …) or phone
  normalisation regresses to the AU heuristic for those — pin with the yaml-vs-JS parity test.

**HubSpot geography_score flow**
- **D-75-09:** HubSpot flow `4626722240 Geography Score` REMAINS the `geography_score` writer.
  Its body (`config/hubspot_flows/4626722240-geography-score.after.json`, the `IN [AU,NZ,ANZ]`
  branch values) is REGENERATED from `regions.home` by the generator, never hand-edited, and
  pushed with `scripts/put_hubspot_flow.py`. `Decide Company Action` does NOT start writing
  `geography_score` (Approach C unchanged). Formulas cannot read enums (D-20), so no formula
  path exists.
- **D-75-10:** The flow PUT AND the schema writes (`lv_icp_scoring_version` property create,
  the new enum options, the `UK` hide, via `scripts/sync_hubspot_properties.py`) are run by the
  EXECUTOR in-plan, not deferred to the operator's exit UAT. The plan MUST state the fallback:
  if the permission classifier blocks the armed HubSpot write from a subagent, the executor
  stops at a checkpoint and the operator runs the identical command. Undo manifests as usual.
  — **Reversibility:** costly — a live HubSpot automation edit; the `.before.json` is the
  rollback body.
- **D-75-11:** yaml-vs-flow agreement is enforced twice: (a) an offline test asserting the
  committed `after.json` branch values == `regions.home`; (b) `scripts/check_schema_drift.py`
  gains a live compare of the fetched flow's branch values vs yaml (ordinary drift, exit 1 —
  the flow's presence/enabled state stays in the exit-2 do-not-archive set).
- Planner note: after the PUT, HubSpot re-evaluates the flow only when
  `lv_country_region_normalized` CHANGES (`shouldReEnroll: true`, event-based on that property).
  Existing records are not re-scored by the PUT itself; a record gains its new `geography_score`
  when its region is (re)written.

**Stale-version sweep path**
- **D-75-12:** Route: inside `wf_enrichment_cloud`, the company branch's skip path
  (`IF Company Skip`) additionally tests `lv_icp_scoring_version != <generated VERSION>`; a
  mismatch reroutes the gate's `skip` into `Decide Company Action` (recompute), so EVERY path
  through the workflow ends in Decide. The webhook `recompute: true` lane (§13.0) is unchanged.
  `Company Gate`'s fetch list must include `lv_icp_scoring_version`.
- **D-75-13:** SJ-2 (monthly) carries the version-stale filter as the BACKSTOP, per ROADMAP.
  Verified blocker the planner must solve: `SJ-2 Company Gate` (`SJ2_CO_GATE`, REQUIRED
  `lv_org_type`/`lv_produces_content`, 180d TTL, `RECOMPUTE_REQUESTED = false` constant) runs
  BEFORE `SJ-2 Set Requested`; a version-stale but fresh record gets `skip` there and never has
  `lv_enrichment_requested` set — the search filter alone is inert. `SJ-2 Search`'s fetch list
  must add `lv_icp_scoring_version` and `SJ2_CO_GATE` must treat version mismatch as not-skip.
- **D-75-14:** A `config.version` bump is followed by an OPERATOR one-shot sweep: a
  `scripts/remediate_veto_companies.py::post_webhook_event`-style chunked POST with
  `recompute: true`, under bounded windows. The scheduled path is only the backstop.
- **D-75-15:** Version-stale scope = `lv_icp_scoring_version != current` AND the record carries
  scoring inputs (`HAS_PROPERTY lv_org_type` or `lv_produces_content`). Never-enriched companies
  are excluded. Researcher question: HubSpot search `NEQ` vs an UNSET property — on day one no
  record carries the property; likely shape is OR'd groups (`NOT_HAS_PROPERTY` + `NEQ`), each
  ANDed with the inputs `HAS_PROPERTY`; verify against HubSpot's documented operator semantics
  before building the filter.
- **D-75-16 (operator ruling 2026-09-20, supersedes Phase 57 / D-61-08 for THIS lane only):**
  STANDING arming for recompute writes. New builder constant `ALLOW_HUBSPOT_RECOMPUTE_WRITES`;
  `_writeSafetyAllows` gains a branch for a distinct recompute classification that checks this
  flag ALONE — no `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` allowlist. The existing three
  `ALLOW_HUBSPOT_*` flags are untouched and stay `"false"`. Planner-verified facts that shape
  the wiring: (a) today the recompute path REWRITES `action` from `skip` to `"enrich"` in
  Decide, and every write gate calls `_writeSafetyAllows("enrich", ...)` — there is NO
  `"recompute"` action today, so the new branch needs its own signal (a new action value or
  `row.recompute === true` / the D-75-12 reroute marker carried to the gate); (b) Decide's PATCH
  on that path is NOT just the veto triple — it also writes `lv_enrichment_status`
  (`complete`/`needs_review`), `lv_enrichment_needs_review`, and on needs-review
  `lv_enrichment_review_reason`/`lv_enrichment_review_candidate_json`; the flag's blast-radius
  statement in the plan must enumerate the ACTUAL property set (veto triple + version stamp +
  those status props) and the planner decides whether the status props ride the recompute PATCH
  or are dropped on that path. — **Reversibility:** one-way-adjacent — undo is an operator
  ruling re-instating Phase 57 for this lane, not a code revert; the flag itself is one
  literal.
- **D-75-17:** Ship `ALLOW_HUBSPOT_RECOMPUTE_WRITES = "false"`. The operator flips it `"true"`
  (deploy + bounce) only after the FIRST supervised bump sweep (D-75-14) is reviewed. The flip is
  a documented one-line deploy step in the phase's UAT/runbook, not part of the exit gate.
- **D-75-18:** Tooling consequences of a fourth, deliberately-true literal: (a)
  `operator-claude-plugin/scripts/n8n_arming.py`'s `OVERLAY_DISABLED_LITERALS`/
  `OVERLAYABLE_FLAGS`/`WRITE_ENABLING_FLAGS` must NOT include the new flag, so `disarm()` and
  `arm_for_dispatch()` never rewrite it; (b) every deploy/bounce/UAT read-back that asserts "all
  `ALLOW_*` literals read `false`" (`scripts/bounce_n8n_workflows.py` exits 1 while armed;
  `scripts/deploy_n8n_workflows.py`; UAT scripts) must enumerate `ALLOW_HUBSPOT_RECOMPUTE_WRITES`
  as allowed-true; (c) `config/execution_budget.yaml` is unchanged — the recompute lane rides
  the existing SJ-3 dispatch cap.
- **D-75-19:** Under the standing flag with `ALLOW_HUBSPOT_RECORD_WRITES = "false"`, a
  disarmed SJ-1/SJ-3 ENRICH dispatch still reaches Decide with a non-recompute action and is
  `write_blocked` — the version stamp lands only on recompute-classified runs and on armed
  enrich runs. State this plainly in the plan; nobody may assume every Decide run stamps.

**Rubric change guard**
- **D-75-20:** `tests/test_rubric_change_guard.py` pins `base_score.geography`'s keys
  (`ANZ/AU/NZ/non_anz/unknown`); the rename to `home/other/unknown` turns it RED and its message
  demands the RUNBOOK re-score procedure before re-baselining. THIS phase's version bump +
  stale sweep IS that procedure: the executor re-baselines `PINNED_BASE_SCORE` in the same plan
  that adds the version stamp and sweep, never as a standalone edit, and the guard's message is
  updated to name `lv_icp_scoring_version` as the segmentation mechanism it said did not exist.

### Claude's Discretion
- Geography points: flat `home: 10`, `other: 0`, `unknown: 0` (ROADMAP default; no tiering).
- Exact rename string (default `"Outside target regions"`).
- Generated-JS module layout (`icpScoring.generated.js` exporting `VERSION`, `REGIONS_HOME`,
  `REGION_ALIASES`, `HARD_VETO_REASONS`, `GEOGRAPHY_POINTS`) and how
  `scripts/zoominfo_company_client.py::zoominfo_country_region` loads the yaml (import from
  `src/icp_scoring.py`'s loaded config, no second parser).
- Whether `sync_hubspot_properties.py` already supports `hidden: true` on an existing option
  (verify; add if not).

### Deferred Ideas (OUT OF SCOPE)
- **Event-driven recompute:** subscribe `company.propertyChange` on the veto inputs
  (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`,
  `lv_is_hardware_vendor`) so a human portal edit dispatches a recompute immediately instead of
  waiting for a scheduled dispatch. New capability (webhook subscriptions, §20.2 "later
  subscriptions"); its own phase.
- Wave-2 regions were folded into `regions.home` on day one (D-75-05); no separate wave remains.
</user_constraints>

## Summary

This phase has no new external dependency, no new library, and no new provider integration —
it is entirely an internal refactor of three already-existing surfaces this repo has a
standing precedent for: (1) a yaml → generated-JS codegen pipeline
(`scripts/gen_escalation_js.py` → `n8n/code/escalation.generated.js`, to be mirrored for
`scripts/gen_icp_scoring_js.py` → `n8n/code/icpScoring.generated.js`), (2) a HubSpot live-schema
migration tool (`scripts/sync_hubspot_properties.py`) that **only handles property CREATE, never
UPDATE of an existing property's enum options** — a hard blocker for D-75-07's new region codes
and the `UK`→hidden change that CONTEXT.md did not fully anticipate (see Pitfall 1), and (3) the
n8n Cloud recompute lane wired in Phase 47.5/70 (`Company Gate` → `IF Company Recompute` →
`IF Company Skip`), which D-75-12 must splice a new branch into under the v1
`executionOrder` Merge/sentinel discipline documented in CLAUDE.md §13.0.3.

**Primary recommendation:** build the generator first (`gen_icp_scoring_js.py`, copying
`gen_escalation_js.py`'s `json.dumps` + `render()`/currency-test shape exactly), get both
scoring engines and all three normalisers reading the SAME generated constants (Phase 46
parity, one commit), and treat the HubSpot-side work (enum options, `UK` hide,
`lv_icp_scoring_version` property create, the geography-score flow PUT) as a **second,
separable** plan — `sync_hubspot_properties.py` needs new code before it can do the enum-option
half of that work at all, and the `lv_icp_scoring_version` property create (the easy half) can
ship through the tool completely unmodified since the property does not exist in
`config/hubspot_properties.yaml` yet (confirmed absent — see Pitfall 2).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Region whitelist definition (`regions.home`/`regions.aliases`) | Config (`config/icp_scoring.yaml`) | — | Single source; both engines and all normalisers read it, never re-derive it |
| Region-key/veto derivation at score time | API/Backend — Python (`src/icp_scoring.py`) AND n8n Code node (`Decide Company Action` in `scripts/build_cloud_workflows.py`) | — | Phase 46 parity: two runtimes, one predicate, one commit |
| Region normalisation from raw provider/native values | API/Backend — three lanes (`n8n/code/normalizeProviders.js`, `src/normalizer.py`, `scripts/zoominfo_company_client.py`) | — | Each lane owns its own blank-sentinel contract (JS `null`, Python `"Unknown"`, ZoomInfo `None`); whitelist expansion must not change any lane's sentinel |
| HubSpot enum schema (`lv_country_region_normalized` options) | Database/Storage (HubSpot property schema) | — | Live portal state; no live UPDATE path exists in this repo's tooling today (Pitfall 1) |
| `geography_score` component | Database/Storage (HubSpot native flow `4626722240`) | — | Regenerated body only; Decide Company Action does NOT become a second writer (Approach C unchanged) |
| `lv_icp_scoring_version` stamp + staleness filter | API/Backend (`Decide Company Action` write) + Database/Storage (HubSpot search filter, `SJ-2 Search`) | — | Written by the n8n engine, read by the scheduled search |
| Recompute-write arming (`ALLOW_HUBSPOT_RECOMPUTE_WRITES`) | API/Backend (n8n Cloud Code-node constant + `_writeSafetyAllows`) | Operator tooling (`n8n_arming.py`, `bounce_n8n_workflows.py`) | New authority, deliberately unreachable from the other three `ALLOW_HUBSPOT_*` flags |

<phase_requirements>
## Phase Requirements

No `.planning/REQUIREMENTS.md` IDs apply to this phase (that file is milestone v1.0's; this
phase belongs to no open milestone's requirement ledger). Per the phase brief, this research is
keyed on the D-75-NN decisions `75-CONTEXT.md` records. Every D-75-NN decision below is mapped
to the research finding(s) that ground its implementation.

| Decision | Research Support |
|----------|-------------------|
| D-75-01/02/03/04 (rename veto string, all 3 from yaml, no dedicated remediation, frozen fixtures untouched) | Pitfall 3 (exact byte-assertion site list, file:line, confirmed by grep this session) |
| D-75-05/06/07/08 (whitelist contents, alias emission, GB token + UK hidden, yaml single source) | Pitfall 1 (no live enum-UPDATE path exists yet); `n8n/code/normalizeProviders.js:21-32` (`_COUNTRY_ISO2`, the minimum alias superset) |
| D-75-09/10/11 (HubSpot flow regen, executor runs schema+flow writes in-plan, dual enforcement) | Code Examples §"Flow PUT precedent"; Pitfall 2 (`lv_icp_scoring_version` absent from yaml, cheap to add) |
| D-75-12/13 (skip→recompute reroute; SJ-2 backstop blocker) | Architecture Patterns §"Recompute lane" and §"SJ-2 gate ordering" (exact node wiring, `scripts/build_cloud_workflows.py:8331-8340`, `:11079-11095`) |
| D-75-14/16/17/18/19 (bump sweep, standing arming flag, ship-false, tooling consequences) | Code Examples §"Write-safety gate"; Pitfall 4 (`bounce_n8n_workflows.py`'s hard-coded `WRITE_FLAGS` tuple) |
| D-75-20 (rubric change guard re-baseline) | `tests/test_rubric_change_guard.py:32-58,79-109` (quoted verbatim below) |

</phase_requirements>

## Standard Stack

Not applicable in the conventional sense — this phase adds no new library, framework, or
provider SDK. The "stack" is this repo's own established codegen and migration tooling:

| Tool | Role in this phase | Precedent |
|------|--------------------|-----------|
| `scripts/gen_escalation_js.py` | Template to copy for `scripts/gen_icp_scoring_js.py` | `[VERIFIED: scripts/gen_escalation_js.py:1-74]` |
| `scripts/sync_hubspot_properties.py` | Property CREATE only (see Pitfall 1) | `[VERIFIED: scripts/sync_hubspot_properties.py:1-254]` |
| `scripts/snapshot_hubspot_schema.py` | Refreshes the pinned enum-options baseline the JS generator reads from | `[VERIFIED: scripts/snapshot_hubspot_schema.py:35,92]` |
| `scripts/put_hubspot_flow.py` / `scripts/fetch_hubspot_flow.py` | Flow body PUT/GET, two-key gated | `[VERIFIED: scripts/put_hubspot_flow.py:1-45]` |
| `scripts/check_schema_drift.py` | Live enum/flow drift comparator, read-only | `[VERIFIED: scripts/check_schema_drift.py:1-180]` |
| `.venv/bin/python -m pytest -q --tb=short` | Python suite runner (`[VERIFIED: .planning/config.json:8]`, project `test_command`) — this research task's own `<additional_context>` brief adds `-p no:cacheprovider`, which is not present in the committed `test_command` string; carry it forward if the orchestrator's invocation prompt specifies it, but do not attribute it to `config.json` | `[VERIFIED: .planning/config.json:8]` |
| `node --test tests/n8n/*.test.mjs` | JS suite runner — **glob form only**; directory form is broken on node 24 (memory: `test-suite-run-commands`) | `[CITED: user memory note]` |

No package-legitimacy audit applies — zero external packages are introduced by this phase.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external package in any ecosystem.

## Architecture Patterns

### System flow: config → generated JS → both engines → HubSpot

```
config/icp_scoring.yaml (regions.home, regions.aliases, hard_vetoes.*.reason, base_score.geography)
        │
        ├─► scripts/gen_icp_scoring_js.py (NEW — mirrors gen_escalation_js.py exactly)
        │         │
        │         ▼
        │   n8n/code/icpScoring.generated.js  ──► inline()'d into ENRICH_DECIDE_CO_CLOUD,
        │   (VERSION, REGIONS_HOME,               SJ2_CO_GATE, and normalizeProviders.js's
        │    REGION_ALIASES,                       region-alias lookup, by scripts/build_cloud_workflows.py
        │    HARD_VETO_REASONS,
        │    GEOGRAPHY_POINTS)
        │
        └─► src/icp_scoring.py (load_yaml("config/icp_scoring.yaml") directly — Python
              reads the yaml at call time, needs no generated-JS twin; already reads
              hard_vetoes.<key>.reason, confirmed at src/icp_scoring.py:177,181,193)

scripts/gen_hubspot_enums_js.py reads a SEPARATE, PINNED SNAPSHOT FILE
  (config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json),
  NOT config/hubspot_properties.yaml directly — see Pitfall 1.
```

### Recompute lane — exact current wiring (Company branch of `wf_enrichment_cloud`)

Confirmed live in the builder (`scripts/build_cloud_workflows.py:8331-8340`), quoted verbatim:

```python
conns["Company Gate"] = {
    "main": [[{"node": "IF Company Recompute", "type": "main", "index": 0}]]}
conns["IF Company Recompute"] = {"main": [
    [{"node": "Decide Company Action", "type": "main", "index": 0}],  # true
    [{"node": "IF Company Skip", "type": "main", "index": 0}],        # false
]}
conns["IF Company Skip"] = {"main": [
    [{"node": "Build Response", "type": "main", "index": 0}],          # true
    [{"node": "Build Company Requests", "type": "main", "index": 0}],  # false
]}
```
`[VERIFIED: scripts/build_cloud_workflows.py:8331-8340]`

`IF Company Skip` is defined at `scripts/build_cloud_workflows.py:7830-7832`:
```python
nodes.append(_if_bool_expr_node(
    "IF Company Skip", '$json.action === "skip"', hs_co_search_x, crby,
))
```
`[VERIFIED: scripts/build_cloud_workflows.py:7830-7832]`

**D-75-12's reroute target does not exist as a node today.** `IF Company Skip`'s TRUE branch
(`action === "skip"`) currently goes straight to `Build Response` (a bare 200, no
enrichment/recompute work). The plan must splice a NEW condition here — evaluating
`$json.existingRecord.lv_icp_scoring_version !== VERSION` — routing a version-stale skip into
`Decide Company Action` (recompute-shaped, zero provider/research/judge/merge cost, per §13.0)
while a version-fresh skip still reaches `Build Response` unchanged. `IF Company Skip` reads
`$json` **bare**, not by node name — its own comment states why: *"its immediate upstream is a
Code node, with no HTTP hop in between that could have replaced the item"*
(`scripts/build_cloud_workflows.py:8342-8344`). A new IF spliced at this exact point can read
`$json` bare too, IF it sits directly downstream of `Company Gate`/`IF Company Skip` with no
HTTP hop in between — but the moment it sits behind `Build Response`'s Merge convergence, v1
Merge/sentinel rules (CLAUDE.md §13.0.3) apply: **every branch reaching a Merge input must be
guaranteed to deliver something, or that Merge's downstream never runs at all under v1** (a
node fed zero items simply never executes; there is no "empty item" rescue under v1, unlike the
legacy engine). The two splice primitives already built for exactly this — `[VERIFIED:
scripts/build_cloud_workflows.py:10619-10645]` (`splice_carry_merge_after`) and `[VERIFIED:
scripts/build_cloud_workflows.py:10906-10932]` (`_add_starved_lane_sentinel`) — are the
established mechanism the plan should reuse rather than hand-wire a new Merge.

**`Company Gate`'s fetch list must add `lv_icp_scoring_version`.** The property list both
`"HubSpot Company Search"` and `"HubSpot Company Fetch By Id"` feed from is
`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` at `scripts/build_cloud_workflows.py:7068` (quoted in
part):
```python
ENRICH_COMPANY_SEARCH_PROPERTIES_CSV = (
    "name,domain,industry,annualrevenue,"
    "numberofemployees,hs_object_id,lv_org_type,"
    ...
    "lv_country_region_normalized,country,city,"
    "lv_revenue_band,lv_employee_band,"
    ...
)
```
`[VERIFIED: scripts/build_cloud_workflows.py:7068-7100]` — this constant does NOT currently
list `lv_icp_scoring_version`, and this file's own history (`fix-40 VETO-01/02`, `58-05`,
`Phase 66 Plan 02`) repeatedly shows the SAME bug shape: a property omitted here reads as
`undefined` on `existingRecord`, which is indistinguishable from blank and silently defeats
whatever logic depends on it. The local-live sibling `HS_CO_SEARCH_BODY_EXPR`
(`scripts/build_cloud_workflows.py:3628-3652`) needs the identical addition or it drifts again
exactly as WR-01 documents happened before.

### SJ-2 gate ordering — the verified blocker D-75-13 names

`scripts/build_cloud_workflows.py:9934-9971` (`SJ2_CO_GATE`) runs **before**
`"SJ-2 Set Requested"` and only two fields are `REQUIRED`:
```python
const REQUIRED = ["lv_org_type", "lv_produces_content"];
```
`[VERIFIED: scripts/build_cloud_workflows.py:3934,3940]`

The routing, confirmed at `scripts/build_cloud_workflows.py:11079-11095`:
```python
sj2_if_not_skip = _if_node("SJ-2 IF Skip", "skip", x2, y2)
...
conns[sj2_if_not_skip["name"]] = {"main": [
    [{"node": "SJ-2 Skip (NoOp)", "type": "main", "index": 0}],   # true: still stale-gate says skip
    [{"node": sj2_dispatch["name"], "type": "main", "index": 0}],  # false: confirmed stale -> dispatch
]}
```
`[VERIFIED: scripts/build_cloud_workflows.py:11095-11098]`

A record whose `lv_org_type`/`lv_produces_content` are both fresh (not past the 180-day TTL)
gates to `"skip"` here **regardless of `lv_icp_scoring_version`** — the search filter
(`lv_org_type_verified_at LT cutoff` OR `lv_produces_content_verified_at LT cutoff`) never even
selects such a record in the first place, since `"SJ-2 Search (stale refresh)"`'s filter groups
are keyed on those two verified-at timestamps only
(`scripts/build_cloud_workflows.py:11063-11069`), not on scoring version. D-75-13's fix needs
BOTH: (a) `"SJ-2 Search"`'s `filter_groups` widened with an OR'd `lv_icp_scoring_version`
NOT_HAS_PROPERTY/NEQ group (so the record is even fetched), AND (b) `SJ2_CO_GATE`'s
`REQUIRED`/action logic taught to treat a version mismatch as not-skip (so a record that IS
fresh on the two ICP fields, but stale on version, still reaches `"SJ-2 Set Requested"`). Both
`"SJ-2 Search"`'s `properties_csv` (currently 6 fields,
`scripts/build_cloud_workflows.py:11071-11072`) and `SJ2_CO_GATE`'s inputs need
`lv_icp_scoring_version` added — same "must fetch or it reads undefined" rule as above.

### `HAS_PROPERTY`/`NOT_HAS_PROPERTY` OR-group precedent (answers D-75-15's open question)

This repo already ships an OR'd `NOT_HAS_PROPERTY` + `EQ` filter-group pattern in production —
`"SJ-1 Search (input-gap scan)"`:
```python
filter_groups=[
    [{"propertyName": "lv_org_type", "operator": "NOT_HAS_PROPERTY"}],
    [{"propertyName": "lv_org_type", "operator": "EQ", "value": "unknown"}],
    [{"propertyName": "lv_produces_content", "operator": "NOT_HAS_PROPERTY"}],
],
```
`[VERIFIED: scripts/build_cloud_workflows.py:11022-11031]` — each top-level list entry in
`filter_groups` is OR'd against the others (HubSpot's `filterGroups` semantics), each entry's
own `filters` list is AND'd within itself. D-75-15's scope (`version != current AND HAS_PROPERTY
lv_org_type` OR `HAS_PROPERTY lv_produces_content`, with an unset `lv_icp_scoring_version`
folded in via `NOT_HAS_PROPERTY`) fits this exact shape:
```
filterGroups: [
  [ {NOT_HAS_PROPERTY lv_icp_scoring_version}, {HAS_PROPERTY lv_org_type} ],
  [ {NEQ lv_icp_scoring_version, "<VERSION>"}, {HAS_PROPERTY lv_org_type} ],
  [ {NOT_HAS_PROPERTY lv_icp_scoring_version}, {HAS_PROPERTY lv_produces_content} ],
  [ {NEQ lv_icp_scoring_version, "<VERSION>"}, {HAS_PROPERTY lv_produces_content} ],
]
```
This shape is `[ASSUMED]` as the correct HubSpot filter structure for THIS specific
combination (never live-tested with this exact 4-group NEQ/NOT_HAS_PROPERTY/HAS_PROPERTY
combination in this repo) — the SJ-1 precedent proves the general OR'd-groups mechanism works
live, but the planner should verify the 4-group form against HubSpot's documented `filterGroups`
semantics (or a disarmed dry-run search) before shipping, per D-75-15's own "verify... before
building" instruction.

### Write-safety gate — the shared `_writeSafetyAllows` predicate D-75-16 must extend

`scripts/build_cloud_workflows.py:2547-2565`, quoted in full (the function every gated write
calls):
```javascript
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
`[VERIFIED: scripts/build_cloud_workflows.py:2547-2565]`

Confirms D-75-16(a): there is no `"recompute"` action branch today — every gated write's action
falls into `"review"` or the else-branch (`"create"`/`"enrich"`), and the else-branch is
allowlist-gated. A new `"recompute"` branch (or a `row.recompute === true` short-circuit read
before this function is called) must be added that checks `ALLOW_HUBSPOT_RECOMPUTE_WRITES`
alone, bypassing the `allowedDomains`/`allowedIds` check entirely — this is the concrete
diff-shape D-75-16 asks for.

`WRITE_SAFETY_DEFAULTS` (`scripts/build_cloud_workflows.py:174-182`) is where every existing
flag's disabled-default literal is baked at build time; a fifth entry
(`"ALLOW_HUBSPOT_RECOMPUTE_WRITES": "false"`) belongs here (ships `"false"` per D-75-17).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| yaml → JS literal codegen | A second `.write_text` script with a bespoke escaping scheme | `scripts/gen_escalation_js.py`'s `json.dumps(...)` pattern, copied verbatim | `json.dumps` handles all JS-literal escaping; this repo's own ponytail comment at `scripts/gen_escalation_js.py:16-17` states the rule explicitly |
| Region alias lookup | A second hand-typed name→ISO2 table alongside `_COUNTRY_ISO2` | `REGION_ALIASES` generated from `config/icp_scoring.yaml`, REPLACING `_COUNTRY_ISO2` (D-75-08) | Two tables drift; this repo has hit exactly this class of bug five times already for the region/veto surface alone (fix-40 VETO-01/02, 58-05, 66-02) |
| Node splice at a Merge boundary under v1 | A hand-wired new Merge node | `splice_carry_merge_after` / `_add_starved_lane_sentinel` (`scripts/build_cloud_workflows.py:10619`, `:10906`) | These exist specifically because a hand-wired splice at a Merge boundary is exactly how the Phase 70 defect class (G-70-2/G-70-3) happened |

**Key insight:** every prior bug this repo has logged against the geography/veto surface (the
2026-08-10 blank-region incident, fix-40 VETO-01/02, 58-05 Task 1/2, Phase 66 Plan 02 Task 2)
has the SAME shape: a property present in the yaml/engine but absent from a search node's
`properties_csv`, so it reads `undefined` and silently mis-scores. This phase adds ONE more
property (`lv_icp_scoring_version`) to that exact class of risk — audit every `properties_csv`/
`HS_CO_SEARCH_BODY_EXPR`/`SJ-2 Search` fetch list this phase touches, not just the ones D-75
names explicitly.

## Runtime State Inventory

This phase touches live HubSpot schema and flow state, and its rename (D-75-01/03) and
whitelist expansion (D-75-05) both leave EXISTING records affected. Answering the five
categories explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Every company record currently carrying `lv_anti_icp_reason = "Non-ANZ geography"` (literal string, HubSpot property value) — population size unknown offline (D-75's own "Open items" flags this). Every company currently `lv_country_region_normalized = "Other"` whose native `country` would newly resolve into `regions.home` (e.g. a US/GB/CA/etc company enriched BEFORE this phase) cannot be rescued by the whitelist edit alone — its stored region is already `"Other"`, and neither engine re-derives region from native `country` unless `lv_country_region_normalized` is blank (see `src/icp_scoring.py:82-85`: region falls back to `country` ONLY when `region_raw` is falsy). This is a genuine gap D-75-CONTEXT.md's "Open items" section flags and leaves to the planner. |
| Live service config | HubSpot flow `4626722240 Geography Score` — its branch filter values (`config/hubspot_flows/4626722240-geography-score.after.json:31-34`, currently `["AU","NZ","ANZ"]`) live in HubSpot's flow-builder UI/API, not in git as the source of truth (the `.after.json` is a tracked SNAPSHOT of what was PUT, not the live source). Regeneration + `put_hubspot_flow.py` PUT required. |
| OS-registered state | None found — no cron/launchd/Task Scheduler registration references geography or scoring version. |
| Secrets/env vars | None — no secret name references the geography rule or scoring version. |
| Build artifacts | `n8n/code/icpScoring.generated.js` (new artifact this phase creates) and `n8n/code/hubspotEnums.generated.js` (existing, but its INPUT — the pinned snapshot file `config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json` — must be refreshed via `scripts/snapshot_hubspot_schema.py` AFTER the live enum-option PUT, or the generated JS keeps emitting the OLD option set even though the live portal has the new one. See Pitfall 1. |

## Common Pitfalls

### Pitfall 1: `sync_hubspot_properties.py` cannot update an existing property's enum options — D-75-07/D-75-11 need NEW code, not existing code

**What goes wrong:** The plan assumes `scripts/sync_hubspot_properties.py` handles "the new
enum options... `UK`... hidden" (D-75-10's own phrasing groups this with the `lv_icp_scoring_version`
create as if both go through the same tool the same way). They do not.

**Why it happens:** `compute_property_diff` (`scripts/sync_hubspot_properties.py:72-91`)
classifies any existing live property whose `options` set differs from desired as **`drift`**,
and the function's own docstring states: *"matching-name-mismatching-shape = drift (report
only, never auto-fixed)"* (`scripts/sync_hubspot_properties.py:73-74`). The only live-write path
in the whole file is `_create_property_live` (`scripts/sync_hubspot_properties.py:126-133`),
which issues `POST /crm/v3/properties/{object_type}` — a CREATE endpoint. There is zero
`requests.patch`/`requests.put` call anywhere in this file (confirmed: `grep -n "PATCH\|patch"
scripts/sync_hubspot_properties.py` returns one match, and it's a code COMMENT naming the
create-body shape, not a call). `hidden` does not appear anywhere in the file (0 matches) —
D-75's own "Claude's Discretion" item ("whether `sync_hubspot_properties.py` already supports
`hidden: true`") resolves to **no, and neither does it support ANY option update at all**, a
larger gap than the discretion item implied.

**How to avoid:** the plan needs a NEW function (e.g. `_update_property_options_live`, a
`PATCH /crm/v3/properties/{objectType}/{propertyName}` call carrying the full desired `options`
array) before D-75-07's new region codes or the `UK` hide can be executed live. This is new
code, not a config-only change to an existing tool. Confirm HubSpot's exact PATCH contract for
updating an enumeration property's options (whether a full-array replace or a
dedicated-per-option endpoint is required) before writing it — `[ASSUMED]`, not verified this
session.

**Warning signs:** if the plan cites `sync_hubspot_properties.py`'s existing dry-run report as
proof the enum-option work is covered, check whether the property shows up under `"create"` or
`"drift"` in that report — `drift` means nothing will be written even with
`ALLOW_HUBSPOT_PROPERTY_WRITES=true`.

### Pitfall 2: the enum-option generator reads a PINNED SNAPSHOT FILE, not `config/hubspot_properties.yaml`

**What goes wrong:** After PUTting the new enum options live (once Pitfall 1's new code
exists), a plan might assume `scripts/gen_hubspot_enums_js.py` will pick them up automatically
on next regen.

**Why it happens:** `SNAPSHOT = "config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json"`
(`scripts/gen_hubspot_enums_js.py:27`) is a hardcoded path to a COMMITTED, DATED snapshot file —
not a live GET, and not `config/hubspot_properties.yaml` (which is the DESIRED-state manifest
`sync_hubspot_properties.py` diffs against, a different file entirely). The generator's own
comment states: *"the checked-in copy still needs regenerating by hand after a snapshot
refresh"* (`scripts/gen_hubspot_enums_js.py:12-13`).

**How to avoid:** after the live enum-option PUT succeeds, run
`scripts/snapshot_hubspot_schema.py --label <new-suffix>` to produce a fresh baseline file,
then either overwrite the pinned `SNAPSHOT` filename or repoint the `SNAPSHOT` constant at the
new file, THEN regenerate `hubspotEnums.generated.js`. Skipping this step means the generated
JS keeps validating against the OLD option set even though the live portal has moved.

**Warning signs:** `tests/test_hubspot_enums_generated_currency.py` is the currency guard for
this file (`scripts/gen_hubspot_enums_js.py:14`) — if it stays green after the enum PUT without
this snapshot-refresh step having run, that is itself suspicious (it means the test is
comparing the generated file against the SAME stale snapshot, not proving currency against the
live portal).

### Pitfall 3: exact byte-assertion sites for `"Non-ANZ geography"` and the `non_anz` key (D-75-01/02 blast radius)

Confirmed by grep this session (every hit quoted with its file:line — this is the full,
non-approximate list the plan must touch in the SAME commit as the rename):

```
tests/test_hubspot_properties_config.py:275  (comment reference only, not an assertion)
tests/test_veto_remediation_report.py:102,103,119,120,126,127,135,137,155
tests/n8n/materialConflictNoVetoFlip.test.mjs:161
tests/n8n/reviewQueueEndpoint.test.mjs:255,289
tests/n8n/antiIcpFlagMirror.test.mjs:104
tests/n8n/companyRecomputeLaneFlow.test.mjs:221
tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json:4608,4729 (RECORDING — leave untouched per D-75-04)
tests/test_scoring_parity.py:211(comment),259(test name only),409,443,913,925
tests/test_icp_scoring.py:62(test name only),231
tests/test_simulate_rubric_weights.py:286
tests/test_remediate_veto_companies.py:227(test name only),243(test name only),247
tests/test_backfill_dry_run.py:95
tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs:83 (plus comment lines 4,91)
```
`[VERIFIED: grep -n "Non-ANZ geography" across the repo, this session]`

**One extra site CONTEXT.md's own list does not name:** `tests/test_scoring_parity.py:443`
asserts against `HARD_VETOES["non_anz"]["reason"]` — a dict lookup **keyed on the string
`"non_anz"`**, not `"Non-ANZ geography"` as a value. If `hard_vetoes.non_anz` is renamed to
`hard_vetoes.outside_home_regions` in the yaml (per the phase goal's own text: *"`hard_vetoes.outside_home_regions`
replacing `non_anz`"*), this key lookup breaks independently of the reason-STRING rename — it
is a SEPARATE byte-assertion site the D-75-01 list in CONTEXT.md does not enumerate (that list
is about the reason STRING; this is about the YAML KEY). `HARD_VETOES` is defined at
`tests/test_scoring_parity.py:59` as `HARD_VETOES = CFG["hard_vetoes"]` — a direct load of the
live yaml, so its `["non_anz"]`/`["no_content"]`/`["hardware_vendor"]` key lookups
(`tests/test_scoring_parity.py:443-445`) fail the moment the yaml key is renamed, independent of
whether the STRING value changes.

**Correction to an earlier read of `src/icp_scoring.py`: the Python engine ALSO does a
yaml-key lookup, not a hard-coded string literal, and is therefore equally exposed by a
`hard_vetoes` KEY rename** (this matters because the two engines need the SAME two-part fix —
region-key AND yaml-key — not two different fixes). Quoted verbatim,
`src/icp_scoring.py:175-177`:
```python
if region_key == "non_anz":
    anti_icp_flag = True
    anti_reasons.append(cfg["hard_vetoes"]["non_anz"]["reason"])
```
`[VERIFIED: src/icp_scoring.py:175-177]` — line 177 is a yaml-KEY lookup
(`cfg["hard_vetoes"]["non_anz"]`), not a string literal; renaming `hard_vetoes.non_anz` to
`hard_vetoes.outside_home_regions` in the yaml and leaving this line untouched raises
`KeyError` at score time. The comparable JS in `Decide Company Action`
(`scripts/build_cloud_workflows.py:5145`, quoted in Pitfall 5 below) is the OPPOSITE shape — a
hard-coded STRING literal (`vetoReasons.push("Non-ANZ geography")`), not a yaml-key lookup — so
D-75-02's "reasons come from yaml via generated JS" fix changes the JS site from a literal to a
lookup, while the SAME fix in Python changes an EXISTING lookup's key. Both sites, plus
`region_key`'s own internal sentinel value (`src/icp_scoring.py:124`:
`region_key = region if region in ["AU", "NZ", "ANZ"] else "non_anz"` — the STRING `"non_anz"`
used as BOTH the internal branch value and the yaml-key), need to move together: whatever
`region_key` resolves to when a KNOWN, non-home region is seen must be the SAME string as the
renamed `hard_vetoes` key.

### Pitfall 4: `bounce_n8n_workflows.py`'s all-false assertion does not know about a 4th flag

**What goes wrong:** once `ALLOW_HUBSPOT_RECOMPUTE_WRITES` is flipped `"true"` post-supervised-
sweep (D-75-17), the existing exit-1-while-armed guard will start failing spuriously.

**Why it happens:** `scripts/bounce_n8n_workflows.py:34` hard-codes
`WRITE_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")` and `_row_ok`
(`scripts/bounce_n8n_workflows.py:56-68`) asserts `all(v in ([], ["false"]) for v in
flags.values())` — a tuple that only tracks TWO of the (eventually four) `ALLOW_HUBSPOT_*`
literals, and does not even include `ALLOW_HUBSPOT_REVIEW_WRITES` today (a pre-existing gap,
not introduced by this phase). This is EXACTLY the tooling consequence D-75-18b names.

**How to avoid:** either add `ALLOW_HUBSPOT_RECOMPUTE_WRITES` to a SEPARATE allowed-true
tracking set in `_flag_values`/`_row_ok` (so the script can assert it correctly reads `"true"`
post-flip, rather than silently ignoring it or falsely failing), matching D-75-18b's
instruction to "enumerate `ALLOW_HUBSPOT_RECOMPUTE_WRITES` as allowed-true."

**Warning signs:** a green `bounce_n8n_workflows.py` run after the operator flips the flag is
NOT proof the flip landed correctly if the script never reads that flag's literal at all.

### Pitfall 5: `Decide Company Action`'s three hard-coded veto-reason `push()` calls are STRING LITERALS today, and one of the two engines already differs subtly in comparison semantics

`scripts/build_cloud_workflows.py:5145-5147`, quoted in full:
```javascript
if (region === "non_anz") vetoReasons.push("Non-ANZ geography");
if (producesContent === false) vetoReasons.push("No broadcast or streaming content");
if (isHardwareVendor === true || orgType === "hardware_vendor") vetoReasons.push("Hardware/AV/LED vendor, not sports-media buyer");
```
`[VERIFIED: scripts/build_cloud_workflows.py:5145-5147]` — the JS `_regionKey` function
(`scripts/build_cloud_workflows.py:5116-5120`) returns exactly `"AU"|"NZ"|"ANZ"|"unknown"|"non_anz"`
today, a **5-value enum**, whereas D-75's rename replaces the whitelist test with a set
membership check against `regions.home` (a JSON array, not 3 hard-coded strings). The comment
directly above this block (`scripts/build_cloud_workflows.py:5112-5114`) explicitly states the
JS and Python region logic "must stay byte-identical to the oracle, since
`tests/test_scoring_parity.py` asserts live state against it" — this is the Phase 46 parity
obligation D-75-02 is written against, and it is currently satisfied by two SEPARATE hand-typed
`if (v === "AU" || v === "NZ" || v === "ANZ") return v;` / Python `region in ["AU", "NZ",
"ANZ"]` literals (`scripts/build_cloud_workflows.py:5118`; `src/icp_scoring.py:124`) that both
need replacing with a `REGIONS_HOME.includes(...)` / `region in cfg["base_score"]["geography"]`-
shaped lookup against the SAME generated/loaded set, not independently hand-edited to add 9 new
literal strings each.

### Pitfall 6: `inline()` strips `require()` — `normalizeProviders.js` needs `icpScoring.generated.js` prepended at every one of its 3 call sites or it throws live

**What goes wrong:** D-75-08 has `normalizeProviders.js`'s region logic read the generated
`REGION_ALIASES` constant instead of its own hand-typed `_COUNTRY_ISO2` map. If the generated
module is not ALSO inlined into the same Code node, the reference resolves to nothing at
runtime.

**Why it happens:** `inline()` (`scripts/build_cloud_workflows.py:168-170`) concatenates
stripped module source with every `require(...)` line removed (`strip_module`,
`scripts/build_cloud_workflows.py:150-165`) — n8n Code nodes cannot `require()` a sibling file
at all (the standing constraint this whole builder exists to work around, stated in the file's
own header comment). A module that references a constant it does not itself define must have
that constant's DEFINING module inlined into the SAME `inline(...)` call, ahead of it in
argument order. `normalizeProviders.js` is inlined at exactly three call sites, all with the
IDENTICAL four-module list and none currently including `icpScoring.generated.js`:
```python
ENRICH_NORMALIZE_SCORE = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
)
```
`[VERIFIED: scripts/build_cloud_workflows.py:2703-2705]` (constant `ENRICH_NORMALIZE_SCORE`) —
the identical four-module `inline(...)` list recurs verbatim at
`scripts/build_cloud_workflows.py:3171-3173` (`ENRICH_NORMALIZE_SCORE_CLOUD`) and
`scripts/build_cloud_workflows.py:3996-3998` (`ENRICH_NORMALIZE_SCORE_CO`).

**How to avoid:** all three call sites need `"icpScoring.generated.js"` added to the `inline()`
argument list, placed BEFORE `"normalizeProviders.js"` (JS `const` bindings are not visible
before their own declaration executes in the concatenated script, so declaration order inside
the single Code-node body matters even though this is all one file at runtime). This is the
exact same shape as `ENRICH_DECIDE_CO_CLOUD`'s own `inline(...)` call
(`scripts/build_cloud_workflows.py:5040-5041`), which already lists
`"taxonomy.generated.js", "hubspotEnums.generated.js", "hubspotEnums.js", "mergeCompanies.js",
"matchProposal.js"` — generated modules first, consumers after.

**Warning signs:** a live execution error reading `REGION_ALIASES is not defined` (or a silent
`ReferenceError` swallowed by `onError: continueRegularOutput` on whichever HTTP/Code node
feeds this branch) — this would not be caught by an offline unit test that calls
`normalizeCountryRegion` directly against the stand-alone `.js` file (which still works fine in
isolation); it only fails inside the INLINED, concatenated Code-node body the builder emits.
Grep the three generated `wf_*.json` outputs for the relevant node's `jsCode` after
regeneration to confirm `icpScoring.generated.js`'s `const REGION_ALIASES = ...;` line actually
appears ahead of `normalizeProviders.js`'s own body in each.

## Code Examples

### Generator precedent — full file, this is what `gen_icp_scoring_js.py` should mirror

```python
# Source: scripts/gen_escalation_js.py:1-74 (verified this session, quoted in the tool_strategy
# `<code_context>` findings above — reproduced here for direct copy-adaptation)
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.icp_scoring import load_yaml  # or a new dedicated loader — Claude's discretion (D-75)

OUT = ROOT / "n8n" / "code" / "icpScoring.generated.js"

def render() -> str:
    cfg = load_yaml("config/icp_scoring.yaml")
    lines = [
        "// n8n/code/icpScoring.generated.js",
        "//",
        "// GENERATED FROM config/icp_scoring.yaml — DO NOT EDIT.",
        "// Regenerate with: .venv/bin/python scripts/gen_icp_scoring_js.py",
        "",
        f"const VERSION = {json.dumps(cfg['version'])};",
        f"const REGIONS_HOME = {json.dumps(cfg['regions']['home'], indent=2)};",
        f"const REGION_ALIASES = {json.dumps(cfg['regions']['aliases'], indent=2)};",
        # HARD_VETO_REASONS keyed by whatever the renamed hard_vetoes keys become
        f"const HARD_VETO_REASONS = {json.dumps({k: v['reason'] for k, v in cfg['hard_vetoes'].items()}, indent=2)};",
        f"const GEOGRAPHY_POINTS = {json.dumps(cfg['base_score']['geography'], indent=2)};",
        "",
        "module.exports = { VERSION, REGIONS_HOME, REGION_ALIASES, HARD_VETO_REASONS, GEOGRAPHY_POINTS };",
        "",
    ]
    return "\n".join(lines)

def main():
    OUT.write_text(render())
    print(f"wrote {OUT.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
```
Build-step registration precedent (`scripts/build_cloud_workflows.py:53,60`, quoted):
```python
import gen_escalation_js  # noqa: E402
...
(CODE / "escalation.generated.js").write_text(gen_escalation_js.render())
```
`[VERIFIED: scripts/build_cloud_workflows.py:53,60]` — the new generator needs the SAME
`import gen_icp_scoring_js` + `(CODE / "icpScoring.generated.js").write_text(gen_icp_scoring_js.render())`
pair added near the top of `build_cloud_workflows.py`, before any `inline(...)` call references
`icpScoring.generated.js`.

### Currency test precedent (`tests/test_judge_spec.py:62`)

```python
# Source: tests/test_judge_spec.py:62 — the pattern to mirror for icpScoring.generated.js
checked_in = (ROOT / "n8n" / "code" / "escalation.generated.js").read_text()
```
`[VERIFIED: tests/test_judge_spec.py:62]` — the full test (not read this session beyond this
line) presumably compares `checked_in` against a freshly-called `render()` output; the planner
should read the surrounding test body directly when writing the icpScoring parity test.

## State of the Art

Not applicable — no external library/API version changes. The "state of the art" question here
is purely about this repo's own conventions, all covered above.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot's `PATCH /crm/v3/properties/{objectType}/{propertyName}` accepts a full `options` array replace for updating an enumeration property's options (adding new codes, setting `hidden: true` on an existing one) | Pitfall 1 | If HubSpot actually requires a dedicated per-option endpoint or additive-only semantics, the new `_update_property_options_live` function needs a different shape; verify against HubSpot's live API (a disarmed dry-run PATCH against a disposable enum property) before writing the real migration |
| A2 | The 4-group `filterGroups` shape proposed for D-75-15 (`NOT_HAS_PROPERTY`/`NEQ` × `HAS_PROPERTY lv_org_type`/`lv_produces_content`) is valid HubSpot search syntax when combined this way | Architecture Patterns §"HAS_PROPERTY/NOT_HAS_PROPERTY OR-group precedent" | If HubSpot rejects or mis-evaluates this specific 4-group combination, SJ-2's widened search either 400s or silently returns the wrong population; D-75-15 itself flags this as unverified and asks the researcher/planner to confirm before building |
| A3 | `regions.home`'s day-one contents (`AU, NZ, ANZ, US, GB, IE, CA, ZA, HK, SG, AE, IN`) will flip an unknown, currently-unmeasured number of already-vetoed companies at the first armed sweep | D-75-05's own reversibility note | CONTEXT.md explicitly asks the researcher to "size it before the first armed sweep" — this was not sized in this research session (would require a live HubSpot search for `lv_anti_icp_flag=true AND lv_anti_icp_reason contains "Non-ANZ" AND country IN (whitelist candidates)`, not run here); flag as an operator-facing unknown, not a blocker to planning |

## Open Questions

1. **Can a version-stale record with `lv_country_region_normalized = "Other"` (stamped before
   this phase, under the OLD 3-value whitelist) be rescued by the recompute lane alone, or does
   it need re-enrichment?**
   - What we know: `Decide Company Action`'s veto derivation reads
     `properties.lv_country_region_normalized ?? existing.lv_country_region_normalized`
     (`scripts/build_cloud_workflows.py:5128`) — on a bare recompute row (no `merge` object,
     `properties = {}`), this resolves straight to `existing.lv_country_region_normalized`,
     i.e. the STORED `"Other"` value, never re-derived from native `country` through the new
     `REGION_ALIASES` table.
   - What's unclear: whether the plan should teach the recompute path to re-derive region from
     native `country` when the stored region is `"Other"` (CONTEXT.md's own "Open items" names
     this exact fork), or whether it accepts that such records need a full re-enrichment pass
     (not a recompute) to pick up the new whitelist.
   - Recommendation: this is a genuine open design fork CONTEXT.md deliberately left to the
     planner — surface it explicitly in the plan rather than silently picking one branch.

2. **Does the D-75-15 4-group HubSpot filter combination actually work as specified?**
   - Covered under Assumption A2 above — recommend a disarmed dry-run `HubSpot Search` call
     (or the equivalent read-only probe) against the real portal before committing to this
     exact filter shape in the generated workflow JSON.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| HubSpot private-app token (`HUBSPOT_PRIVATE_APP_TOKEN`) | `sync_hubspot_properties.py`, `put_hubspot_flow.py`, `check_schema_drift.py` (all live-schema/flow work) | Not probed this session (`.env` is Read/Bash permission-blocked per repo convention — memory `env-file-permission-blocked`) | — | Every script in this family exits 0 with "skipped (no credentials)" when absent — safe to plan the offline half (generator, both engines, tests) without live credentials, but the D-75-10 in-plan executor writes need them |
| n8n Cloud API (`N8N_URL`/`N8N_API_KEY`) | `scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py`, `scripts/remediate_veto_companies.py` | Not probed this session | — | Same "skipped (no creds)" pattern |
| `node` (for `node --test tests/n8n/*.test.mjs`) | JS parity/routing tests | Not probed this session; assumed present per project `test_command` in `.planning/config.json:8` | — | — |

**Missing dependencies with no fallback:** none identified for the offline half of this phase
(generator + both engines + tests can be built and verified with zero live credentials).

**Missing dependencies with fallback:** live HubSpot/n8n writes degrade to disarmed dry-run /
"skipped (no credentials)" exits per this repo's standing convention — the phase's own D-75-10
already plans for an executor-blocked-by-permission-classifier fallback to an operator-run
identical command.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python) + node's built-in `node:test` (JS) |
| Config file | none dedicated — `.planning/config.json:8` names both commands as one `test_command` string |
| Quick run command | `.venv/bin/python -m pytest -q --tb=short tests/test_icp_scoring.py tests/test_scoring_parity.py tests/test_rubric_change_guard.py` (scoped) |
| Full suite command | `.venv/bin/python -m pytest -q --tb=short && node --test tests/n8n/*.test.mjs` |

### Phase Requirements → Test Map

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|--------------------|-------------|
| D-75-02/D-75-20 | `config/icp_scoring.yaml`'s scoring surface change is caught and forces the runbook | unit | `pytest tests/test_rubric_change_guard.py -x` | ✅ (needs re-baseline, not a new file) |
| D-75-01/02/03 | All 3 hard-veto reasons come from yaml via generated JS in BOTH engines | unit + parity | `pytest tests/test_scoring_parity.py -x`; new currency test mirroring `test_judge_spec.py:62` for `icpScoring.generated.js` | ✅ scoring_parity exists; ❌ new currency test — Wave 0 gap |
| D-75-06/D-75-08 | Region aliases superset `_COUNTRY_ISO2`'s existing keys; phone normalisation does not regress | unit | new yaml-vs-JS parity test (mirroring `tests/n8n/columnMapIdentityParity.test.mjs`'s shape) | ❌ — Wave 0 gap |
| D-75-12 | Version-stale record reaches `Decide Company Action` via the recompute lane | integration (offline walker) | `node --test tests/n8n/companyRecomputeLaneFlow.test.mjs` (extend with a version-mismatch case) | ✅ file exists, needs a new case |
| D-75-13 | SJ-2 dispatches a version-stale-but-input-fresh record | integration (offline) | new test exercising `SJ2_CO_GATE` with a version-mismatch row | ❌ — Wave 0 gap |
| D-75-16/17/18 | `ALLOW_HUBSPOT_RECOMPUTE_WRITES` gates recompute writes alone, never touched by disarm, tracked correctly by bounce script | unit | `tests/test_control_arming.py`-shaped new test; `tests/test_control_flag_parity.py` (existing parity pin — needs the 5th/6th flag) | ✅ files exist, need extension |
| D-75-09/11 | Geography-score flow body == `regions.home`, live drift check catches divergence | unit + live (deferred) | new offline test asserting `after.json` branch values == yaml; `check_schema_drift.py` live compare (operator/executor, in-plan per D-75-10) | ❌ offline test — Wave 0 gap; live check is existing infra, new invariant |

### Sampling Rate
- **Per task commit:** the scoped pytest command above, plus the specific new/touched `.mjs` files via `node --test`.
- **Per wave merge:** full suite (`.venv/bin/python -m pytest -q --tb=short && node --test tests/n8n/*.test.mjs`).
- **Phase gate:** full suite green before `/gsd-verify-work`, PLUS the disarmed deploy+bounce
  and one recompute proof each (whitelisted / non-whitelisted company) the ROADMAP exit
  criteria name — these are `[documented]` only until the operator/executor actually runs them
  (per D-75-10, the executor runs the HubSpot writes in-plan; the n8n deploy+bounce+recompute
  proof is the phase's own exit gate, analogous to every prior phase's end-of-phase UAT per the
  "back-load human gates" operator ruling in memory).

### Wave 0 Gaps
- [ ] A new yaml-vs-JS currency test for `icpScoring.generated.js`, mirroring `tests/test_judge_spec.py:62`'s pattern.
- [ ] A new yaml-vs-JS parity test asserting `REGION_ALIASES` is a superset of `_COUNTRY_ISO2`'s current keys (D-75-08's own instruction: "pin with the yaml-vs-JS parity test").
- [ ] A new offline test for `SJ2_CO_GATE`'s version-mismatch-but-input-fresh case (D-75-13).
- [ ] A new offline test asserting `config/hubspot_flows/4626722240-geography-score.after.json`'s branch values equal `regions.home` (D-75-11a).
- [ ] Extension of `tests/n8n/companyRecomputeLaneFlow.test.mjs` with a version-mismatch-reroute case (D-75-12).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface touched |
| V3 Session Management | no | — |
| V4 Access Control | **yes** | The new `ALLOW_HUBSPOT_RECOMPUTE_WRITES` flag is a NEW authorization boundary — a standing (not session-scoped) write-enabling gate, deliberately excluded from `operator-claude-plugin/scripts/n8n_arming.py`'s `OVERLAY_DISABLED_LITERALS`/`WRITE_ENABLING_FLAGS` (D-75-18a) so the existing disarm-on-panic mechanism CANNOT touch it. This is a deliberate, operator-ruled exception to an existing control, not a gap — but the plan must be explicit that `disarm()` no longer disarms this ONE flag, and any future "kill everything" runbook step needs a SEPARATE, explicit step for this flag. |
| V5 Input Validation | yes | Region/alias values pass through `json.dumps` (no hand-built string interpolation) per the generator precedent; HubSpot enum options are closed-set server-side validated |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A standing arming flag left `"true"` after its supervised-sweep purpose has passed, silently authorizing unattended writes indefinitely | Elevation of Privilege | D-75-17 documents the flip as a manual, one-line, DOCUMENTED deploy step — not an automatic revert. The plan should consider whether `bounce_n8n_workflows.py`'s read-back (once it tracks this flag, per Pitfall 4) should also SURFACE the flag's current value prominently in its output, so an operator scanning bounce output notices it is still armed weeks later. This is a recommendation, not an existing control — flag it for the planner's discretion. |
| A version-stale recompute row silently reroutes an operator's genuine `enrich` request into a cheaper `recompute`-shaped write path, writing FEWER properties than the operator expected | Tampering (of intent, not data) | D-75-19 already documents this precisely: "a disarmed SJ-1/SJ-3 ENRICH dispatch still reaches Decide with a non-recompute action... nobody may assume every Decide run stamps [the version]." Keep the two action classifications (`"enrich"` vs whatever the version-stale-skip reroute uses) visibly distinct in the row's `action` field, never silently merged. |

## Sources

### Primary (HIGH confidence — files opened this session)
- `config/icp_scoring.yaml` (full file, 83 lines) — current rubric shape
- `src/icp_scoring.py` (full file, 239 lines) — Python scoring engine
- `scripts/build_cloud_workflows.py` — multiple ranges: 1-70, 150-260, 2480-2600, 3600-3980, 5030-5340, 7020-7100, 7760-7850, 8280-8350, 9850-9910, 9930-10030, 10619-10660, 10906-10950, 10990-11100, 13160-13200
- `scripts/gen_escalation_js.py` (full file, 74 lines) — generator precedent
- `n8n/code/normalizeProviders.js` (lines 1-175) — JS region normaliser + `_COUNTRY_ISO2`
- `src/normalizer.py` (lines 80-172) — Python region normaliser
- `scripts/zoominfo_company_client.py` (lines 107-137) — ZoomInfo region normaliser
- `config/hubspot_properties.yaml` (lines 112-142, plus a `name:` grep across the whole file)
- `scripts/gen_hubspot_enums_js.py` (full file portion, lines 1-80)
- `scripts/sync_hubspot_properties.py` (full file, 254 lines)
- `scripts/snapshot_hubspot_schema.py` (lines 1-50, plus targeted greps)
- `scripts/check_schema_drift.py` (lines 1-60, 100-170)
- `config/hubspot_flows/4626722240-geography-score.after.json` (lines 1-100)
- `scripts/put_hubspot_flow.py` (lines 1-45)
- `tests/test_rubric_change_guard.py` (lines 1-140)
- `operator-claude-plugin/scripts/n8n_arming.py` (lines 1-60)
- `scripts/bounce_n8n_workflows.py` (lines 1-80)
- `scripts/deploy_n8n_workflows.py` (lines 220-260)
- `config/execution_budget.yaml` (full file)
- `scripts/backfill_seed_company_scores.py` (lines 112-181)
- `scripts/remediate_veto_companies.py` (lines 660-700)
- `tests/n8n/fixtures/frozen/README.md` (full file)
- `tests/test_judge_spec.py` (line 62 targeted)
- Repo-wide `grep -n "Non-ANZ geography"` and `grep -n "lv_icp_scoring_version"`, this session

### Secondary (MEDIUM confidence)
- CLAUDE.md §4.0, §10.3.1, §10.3.2, §13.0, §13.0.3, §19.0/19.1, §21.1 (project instructions, provided in system context, not independently re-verified against live HubSpot/n8n this session — but internally self-consistent with everything read above)

### Tertiary (LOW confidence — flagged as [ASSUMED] in-text)
- The exact HubSpot API contract for updating an existing enumeration property's options (Assumption A1)
- The validity of the proposed 4-group `filterGroups` combination for D-75-15 (Assumption A2)

## Metadata

**Confidence breakdown:**
- Codegen/generator pattern: HIGH — direct file read of the precedent and its build-step registration
- n8n node wiring (recompute lane, SJ-2 gate, write-safety gate): HIGH — every quoted snippet read directly from `scripts/build_cloud_workflows.py` this session with exact line numbers
- HubSpot live-schema migration capability: HIGH confidence in the GAP FINDING (sync script cannot update options); LOW/ASSUMED confidence in the exact fix (HubSpot's real PATCH contract, not verified live)
- Test byte-assertion site list: HIGH — exhaustive grep, not sampled

**Research date:** 2026-09-20
**Valid until:** short shelf life — 7-14 days. This phase touches a fast-moving internal codebase (per-day commits) and a live HubSpot portal whose schema this research explicitly found gaps in; re-verify `sync_hubspot_properties.py`'s capabilities and the exact node names in `scripts/build_cloud_workflows.py` immediately before planning if more than a few days have passed.
