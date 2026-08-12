# Phase 48: Enrichment Coverage - Research

**Researched:** 2026-08-12
**Domain:** Brownfield HubSpot/n8n enrichment pipeline — offline data mapping, one live research
call, an n8n control-flow gate, and a budget-gated armed write window
**Confidence:** HIGH (every claim below is either read from a file this session or a live-verified
value already captured in CONTEXT.md; no external library research was needed — this phase adds
zero new dependencies)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Resolve the 4 records with captured evidence by an **offline enum-mapping pass over
  `47-RESEARCH-RESULTS.json`** — zero API cost, zero provider credits. Issue **one** fresh
  enum-constrained web-research call for **Racing NSW `15008671672`** only, which has no captured
  research. **Total paid work: 1 record.** The ex-ante cost estimate is still written per
  COVER-02; it will read roughly one research call (~$0.07 order-of-magnitude, per
  `47-COST-ESTIMATE.md`'s measured $0.0686/record floor).
  Rejected: the ROADMAP's literal "full provider waterfall per record" and re-researching all 5
  with a corrected prompt.
- **D-05:** The Rumble `20943964946` → `content_producer` (not `governing_body_league` — Skate
  Australia governs the sport; The Rumble produces/broadcasts content as a partner).
- **The per-record mapping table:**

  | id | name | outcome | basis |
  |---|---|---|---|
  | `17317850381` | Jam TV | `broadcaster` | research: "Media company / Web television broadcaster", conf 85 |
  | `20538284384` | Waikato Racing Club | `individual_club_team` | research: "Racing Club / Sports Organization", conf 85 |
  | `20943964946` | The Rumble | `content_producer` | D-05 |
  | `17317381378` | Editix | `unknown` + reason (D-03) | research `matched: false`, conf 5 |
  | `15008671672` | Racing NSW | fresh research, then map | no captured evidence |

- **D-02:** Defer `venue`. No record in this population needs it. Amend the LOCKED decision
  `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` with a dated block
  recording the population was examined and the option was not spent — do not silently drop it.
- **D-03:** The un-enrichable marker is `lv_org_type = "unknown"` + a reason in
  `lv_enrichment_review_reason`. Both already exist live, zero portal work. Semantics: blank =
  never attempted; `"unknown"` = attempted, evidence insufficient, reason recorded. Blank region
  is safe (`src/icp_scoring.py:83` maps it to `region_key = "unknown"`, not `non_anz`).
- **D-04:** Fix the lane properly, not just the driver. Add a gate immediately after
  `Claude Web Research` in `scripts/build_cloud_workflows.py` that detects an `error`-shaped
  payload and routes to a failure branch rather than into merge/normalize. This obliges an
  operator deploy (`DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true`, plus a bounce) — the Phase
  47.5 deploy waiver EXPIRED with that phase.
- **D-06:** Declare up front: 1 operator deploy+bounce, 1 armed write window, record cap 5.
  Exceeding the declaration is a disclosure obligation in the run report, not a silent event.
- **D-08:** Touch-once. Editix `17317381378` is the only overlap (blank region AND blank org
  type) — its research resolved neither, so it takes exactly one write (`unknown` + reason). No
  record in this population needs a separate region PATCH.
- **D-09:** Fire a recompute POST per written record and report before/after (the Phase 47.5
  recompute lane, free: 0 provider credits, 0 Anthropic calls, 1 n8n execution per POST). Writing
  `lv_org_type` completes a record, so `Company Gate` would return `skip` on any future trigger
  without this. Plain-language tier-distribution reporting remains Phase 49's deliverable.

### Claude's Discretion

- Chunking, task ordering, and whether the offline mapping pass is a script or a plan-time table.
- Whether the Racing NSW research call reuses `src/web_research.py::claude_web_research` with a
  corrected enum-constrained `RESEARCH_SYSTEM`, or a narrower one-off prompt. Either is fine as
  long as the output is constrained to the 9 live options.
- Where the gate node's failure branch terminates (`Build Response` with a stated reason is the
  established idiom).

### Deferred Ideas (OUT OF SCOPE)

- `venue` as a 10th enum option (D-02) — revisit when a record's evidence actually demands it.
- Entain `10024564084`'s ANZ operating presence — Phase 49.
- A live `D` → non-`D` tier *transition*, proven as a transition — Phase 49.
- Plain-language before/after tier distribution as a deliverable — Phase 49 / RESCORE-03.
- Folded-but-not-this-phase todos: enrichment throughput ceiling, sweep crontab plugin-path
  pinning, UAT CSV header aliases — all unrelated to enrichment coverage.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COVER-01 | Every scored company either carries a real `lv_org_type`, or is individually recorded as un-enrichable with a stated reason distinguishable from "never attempted" | §"The population" (live re-derivation mechanics), §"Offline mapping pass" (JSON shape for D-01), §D-03 marker mechanics (`lv_enrichment_review_reason` confirmed live), §"D-04 gate node" (protects the run from writing garbage that would falsely look like coverage) |
| COVER-02 | Execution/provider cost estimated before the run and reported after, against the 2,500/month n8n allowance and the current Lusha balance; a run that would exceed either is refused outright, not truncated | §"Cost estimation mechanics" (`estimate_cost()`, `refuse_if_over_budget()`, `check_provider_credits.py`) |

</phase_requirements>

## Hard boundaries (restated)

These bind every plan and task this research supports. Copied here verbatim/near-verbatim from
CONTEXT.md's `<constraints>` table so the planner does not have to cross-reference:

1. **Never PATCH `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`, `lv_icp_tier`**
   (project D-07, absolute). Write inputs (`lv_org_type`, `lv_enrichment_review_reason`), let the
   derived chain settle via `Decide Company Action`, read it back.
2. **Never hand-edit `n8n/wf_*.json`.** Edit `scripts/build_cloud_workflows.py` /
   `n8n/code/*.js`, rebuild, deploy, bounce.
3. **Arming and deploys are operator-only this phase.** `D-47.5-01` and its amendment delegated
   both to Claude for Phase 47.5 only; both EXPIRED with that phase. Do not carry them forward,
   do not cite them as authority for this phase.
4. **`.env` is Read/Bash permission-blocked.** Drive any live script through the dotenv-with-
   absolute-path form: `.venv/bin/python -c "from dotenv import load_dotenv;
   load_dotenv('/abs/path/.env'); import runpy; runpy.run_path('scripts/<driver>.py',
   run_name='__main__')"`. `python-dotenv`'s bare `load_dotenv()` resolves relative to the
   **calling file**, not the cwd — with no `conftest.py`, live pytest needs a wrapper passing an
   **absolute** `.env` path or every HubSpot read 401s.
5. **Tests:** `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` — the **glob
   form**; the directory form (`tests/n8n/`) is broken on node 24, and system python lacks the
   deps `.venv` has.
6. **`scripts/run_scoring_parity.py`'s population sweep is RED BY DESIGN until Phase 49.** Do
   NOT "fix" it as part of this phase — oracle-vs-live parity across the whole population is
   Phase 49's scope, not Phase 48's. This phase's Validation Architecture "full suite green" bar
   below refers to the named `tests/*.py`/`tests/n8n/*.test.mjs` suites, not to running
   `run_scoring_parity.py`'s population sweep and expecting it green.

## Summary

Phase 48 is almost entirely a **data-mapping and control-flow-hardening** phase, not a
research-heavy one. 4 of the 5 records needing `lv_org_type` already have research captured on
disk in `.planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json` (confirmed this session —
all 4 ids `17317381378`, `17317850381`, `20538284384`, `20943964946` are present as top-level
keys, each carrying a `ProviderResult`-shaped record). Only Racing NSW `15008671672` needs a new
web-research call. The `lv_org_type` enumeration is confirmed live (`type: enumeration`,
`fieldType: select`, 9 options) in both `config/hubspot_properties.yaml:338-386` and the committed
portal snapshot `config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json`
(read this session) — the CONTEXT.md 9-option list is byte-identical to what's on disk.

`scripts/remediate_veto_companies.py` already carries every write-leg primitive Phase 48 needs
(HubSpot batch PATCH, D-18 webhook POST with `recompute=True`, settle-and-assert polling,
`estimate_cost()`/`refuse_if_over_budget()`) — Phase 48's driver should import and reuse these
functions rather than re-implement them, following exactly the reuse pattern the script's own
docstring recommends for a sibling script. The one genuinely new piece of production code this
phase requires is D-04's gate node in `scripts/build_cloud_workflows.py`, inserted between the
already-built `"Claude Web Research"` HTTP node and `"Validate Research Output"` in the CLOUD
enrichment workflow — the exact insertion point, and the `_if_bool_expr_node()` builder function to
use, are both confirmed by reading the file this session (see "The D-04 gate node" below). The
established idiom for a request/response-shaped IF-gate-with-failure-branch already exists in this
same file (`IF Company Recompute` / `IF Company Skip`, built in Phase 47.5) and should be copied,
not reinvented.

**Primary recommendation:** build a small Phase 48 driver script (new file, e.g.
`scripts/enrich_coverage_companies.py`) that (1) re-derives the live population with the exact
HubSpot search filter CONTEXT.md used, (2) reads `47-RESEARCH-RESULTS.json` for the 4 already-
researched records and runs one fresh `claude_web_research()` call (enum-constrained) for Racing
NSW, (3) maps each record's free-text/enum research output to one of the 9 `VALID_ORG_TYPES`
values per the CONTEXT.md table (or `unknown` + `lv_enrichment_review_reason` for Editix), (4)
calls `estimate_cost()`/`refuse_if_over_budget()` before any write, (5) PATCHes via
`batch_update_companies` inside one declared, capped, disarmed-afterward window, and (6) fires one
`post_webhook_event(..., recompute=True)` per written record and reports before/after. Separately,
land D-04's gate node in `scripts/build_cloud_workflows.py`, rebuild, and hand the deploy+bounce to
the operator (Claude may not arm or deploy this phase — both Phase 47.5 waivers expired).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live population re-derivation | Python driver (`src/hubspot_client.py::search_records`) | — | HubSpot CRM Search API is the source of truth; a committed snapshot is evidence, not a guarantee (CONTEXT.md, restated repeatedly) |
| Offline enum-mapping (4 records) | Python driver, reading `47-RESEARCH-RESULTS.json` | — | Zero-cost — no network call at all, this is a local JSON transform |
| Fresh research (Racing NSW) | `src/web_research.py::claude_web_research` (standalone Python, native `web_search` tool) | — | D-08 (Phase 47 precedent) already chose the standalone Python path over the n8n provider waterfall for this exact reason: providers don't return `lv_org_type` |
| `lv_org_type` write | Direct HubSpot CRM v3 PATCH (`src/hubspot_client.py::batch_update_companies`) | — | Same write leg `remediate_veto_companies.py` already uses; not an n8n concern |
| Veto recompute after write | n8n Cloud (`Decide Company Action` node, via the D-18 webhook + `recompute:true`) | — | `Decide Company Action` is the SOLE writer of `lv_anti_icp_flag`/`lv_anti_icp_reason` (project D-07) — the driver must never PATCH those fields itself |
| Research-error containment (D-04) | n8n Cloud (`scripts/build_cloud_workflows.py`-built gate node) | — | The failure must be caught in the same workflow that made the call, before `Merge Company`/`Decide Company Action` ever see it — a Python-side retro-check cannot un-write a bad merge that already happened inside a *different* execution |
| Cost estimate + budget refusal | Python driver, reusing `estimate_cost()`/`refuse_if_over_budget()` | `scripts/check_provider_credits.py` for the Lusha-balance line | n8n has no usage endpoint (project memory); estimation is necessarily a static local computation, never a live n8n balance read |

## The population — live re-derivation mechanics

CONTEXT.md's population table is dated 2026-08-12 and is the anchor (66 scored, 5 blank
`lv_org_type`), but it explicitly demands re-derivation at plan/execution time. The exact HubSpot
Search filter CONTEXT.md used:

```
filterGroups: [{ filters: [
  { propertyName: "lv_icp_fit_score", operator: "HAS_PROPERTY" },
  { propertyName: "lv_org_type", operator: "NOT_HAS_PROPERTY" },
]}]
```

`src/hubspot_client.py:119` (`search_records(object_type: str, filters: list[dict],
properties: list[str], limit=100)` — confirmed this session by reading the function signature) is
the existing seam for this. The planner should have the executor call this exact filter through
`search_records("companies", [...], ["hs_object_id", "name", "lv_org_type", "lv_icp_fit_score",
"lv_icp_tier", "lv_country_region_normalized", "lv_anti_icp_flag"])`, print the count and id list,
and **stamp the date** in the run report — this is the "re-derive again at plan time and stamp the
date" instruction CONTEXT.md repeats at least four times. `[VERIFIED: src/hubspot_client.py:119]`
`def search_records(object_type: str, filters: list[dict], properties: list[str], limit=100):`

## The offline mapping pass (D-01/D-05)

Confirmed this session by reading `.planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json`
in full: it is a flat JSON object keyed by HubSpot company id (string), 17 entries total. All 4
ids Phase 48 needs are present: `17317381378` (Editix), `17317850381` (Jam TV), `20538284384`
(Waikato), `20943964946` (The Rumble). Racing NSW `15008671672` is **not** present — confirming
CONTEXT.md's "never in the 17 pinned" claim.

Each entry's exact shape (matches Pydantic `ProviderResult` in `src/schemas.py`):

```json
{
  "provider": "claude_web",
  "object_type": "companies",
  "matched": true,
  "confidence": 85,
  "data": {
    "lv_org_type": "<free text, e.g. \"Media company / Web television broadcaster\">",
    "lv_produces_content": true,
    "lv_content_type": ["..."],
    "lv_is_hardware_vendor": false,
    "lv_is_gambling_operator": null,
    "lv_sponsorship_reliant": null,
    "lv_country_region_normalized": "Italy",
    "lv_has_sports_media_fit": false,
    "lv_has_broadcast_or_streaming_signals": true
  },
  "evidence": {
    "last_seen": "2026-08-11",
    "match_basis": ["..."],
    "evidence_urls": ["..."],
    "evidence_summary": "<prose>"
  },
  "model_trace": {"research_model": "claude-web", "classifier_model": null, "validator_model": null},
  "evidence_by_field": {"lv_org_type": "<url>", "lv_produces_content": "<url>", "...": "..."}
}
```

**The free-text org classification lives in `data.lv_org_type`** — it is NOT a member of the 9
live enum values; every one of these 4 records' `data.lv_org_type` is free prose (e.g. "Media
company / Web television broadcaster", "Racing Club / Sports Organization", "Event organizer /
Sports league operator", or — for Editix — `null`). **Confidence is a single top-level integer**
(`confidence`, 0–100), not per-field; per-field evidence is tracked separately in
`evidence_by_field` (URL only, no confidence). This is exactly why D-01 calls it a "mapping pass",
not a re-parse: the offline pass reads `data.lv_org_type`'s free text plus `evidence_summary`
and manually assigns one of the 9 valid enum values per the CONTEXT.md table — it does not attempt
automated keyword matching (`scripts/remediate_veto_companies.py`'s own `_classify_org_type()`,
read this session at lines 283–308, deliberately refuses to keyword-guess for exactly this
reason: "keyword-matching the free text itself … is exactly the guessing D-17 forbids").

**Editix's entry is the D-03 archetype**, confirmed verbatim:
`"matched": false, "confidence": 5, "data": {"lv_org_type": null, ...all null...},
"evidence_by_field": {}`, with `evidence_summary`: "Web searches for 'Editix edetrix.com.au' …
returned no results for a company matching this identity. Results included unrelated companies:
EditiX (XML editor software), Editrix (AI book editing tool), and EditShare (media software), but
none matching the provided company name and domain combination." This is the exact text CONTEXT.md
quotes; confirmed present in the file this session.

## The driver to extend (`scripts/remediate_veto_companies.py`)

Read in full this session (1045 lines). Reusable, precisely-named primitives Phase 48's driver
should import rather than re-implement:

- **`estimate_cost(ids) -> dict`** (lines 650–671). Signature: takes an iterable of company ids,
  returns a dict with keys `web_research_calls`, `redundant_research_calls`, `n8n_executions`,
  `n8n_budget_month` (constant `2500`), `lusha_credits` (always `0` — this script never touches
  the provider waterfall), `lusha_credits_note`, `anthropic_estimate_usd` (rounds
  `n_records * ANTHROPIC_PER_RECORD_ESTIMATE_USD`, where `ANTHROPIC_PER_RECORD_ESTIMATE_USD =
  0.0686`, line 647), `anthropic_estimate_note`. For Phase 48 with `ids=["15008671672"]` (the
  only record needing a live call), this returns `web_research_calls: 1`,
  `anthropic_estimate_usd: 0.0686` — matching D-01's "~$0.07 order-of-magnitude" claim exactly.
  `redundant_research_calls` is computed against `KNOWN_LIKELY_EVIDENCE_GATED_IDS` (line 636–641,
  a frozenset of 4 Phase-47 ids that don't include any Phase 48 id) — this will read `0` for
  Phase 48, which the driver should NOT reuse blindly (Racing NSW is exactly the kind of
  not-plainly-a-club-name record D-20 warns about; if it lands on an `EVIDENCE_REQUIRED_ORG_TYPES`
  value it may re-trigger the deployed workflow's `Research Trigger Gate` a second time when the
  D-09 recompute POST fires — the recompute lane bypasses providers/research/judge/merge
  entirely, so this concern does not apply to D-09's POST, but it does apply if the driver's own
  webhook event is built without `recompute=True`).
- **`post_webhook_event(company_id, armed, config, transport=requests, recompute: bool = False,
  domain: str = None, timeout: float = 300)`** (lines 596–625). `armed` has **no default** —
  raises `NotArmedError` if falsy, before any network call. `recompute=True` adds a real JSON
  boolean `event["recompute"] = True` to the built webhook event (never a string). `timeout`
  defaults to **300s**, not the 30s an earlier throwaway driver hardcoded (the fix that closed
  Trap #2 below). This is the exact function CONTEXT.md's D-09 names as the helper to call with
  `recompute=True`.
- **`VALID_ORG_TYPES`** (lines 153–156, the 9-tuple; the surrounding comment block explaining the
  enum-vs-free-text history starts at line 138 — CONTEXT.md's "near line 142" refers to this
  comment block, the tuple literal itself is at 153). This is the strict allowlist the phase's
  own hard-constraints table calls "load-bearing" — reuse it verbatim rather than re-declaring a
  9-tuple that could silently drift from this one.
- **`PINNED_COMPANY_ID_ORDER`** (lines 71–89, the 17 Phase-47 ids) — Phase 48 must NOT reuse this
  tuple's *membership* (Racing NSW is not in it, and none of Phase 48's ids should be), but should
  copy its **pattern**: a literal, order-preserving tuple plus a `resolve_pinned_ids()`-style
  refusal function (lines 202–221) that raises before any HubSpot/n8n call rather than silently
  accepting an out-of-scope id. `EXCLUDED_COMPANY_IDS` (line 96, the 3 structurally-excluded
  Phase-47 ids) has no Phase-48 analog — no id needs a parallel exclusion set this phase.
- **`build_input_patch`, `unresolved_reasons`, `build_metadata_patch`/`build_metadata_record`,
  `build_component_patch`, `settle_tier`/`settle_veto`, `refuse_if_over_budget`, `verify_post_run`**
  — all present and directly reusable; none need modification for Phase 48's smaller, simpler
  scope (5 records max, only `lv_org_type` + the D-03 marker as new write surfaces, vs. Phase 47's
  3-input widened set).
- **Two-key arm, direct-HubSpot leg:** `_writes_allowed()` (lines 249–252) reads
  `DRY_RUN` (default `"true"`) and `ALLOW_VETO_REMEDIATION` (default `"false"`) — this exact
  env-var pair is Phase-47-specific and should NOT be reused literally (its name says
  "veto remediation"); Phase 48's driver needs its own arm-key name (Claude's Discretion per
  CONTEXT.md), following the identical two-key pattern.
- **`scripts/june_run_arm.py --domains`** (confirmed this session, lines 1–70): a **second,
  independent** arming surface — this is n8n's own write-safety allowlist
  (`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` on the deployed workflow), armed via
  `ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --ids <comma-separated ids>` (or
  `--domains` for a not-yet-existing record) and closed via `--disarm` (deliberately NOT gated on
  `ALLOW_N8N_ARM`, so an operator can always close the window). **This is distinct from
  `ALLOW_VETO_REMEDIATION`/whatever Phase 48 names its own driver-side flag** — the direct HubSpot
  PATCH leg (writing `lv_org_type`/`lv_enrichment_review_reason`) never touches n8n and needs only
  the driver's own gate; the D-09 recompute POST's `Decide Company Action` → `HubSpot Company
  Update` write leg needs the **n8n-side allowlist** armed via `june_run_arm.py` (or equivalent)
  for the same record ids, or it will return `write_blocked` (exactly what happened, disarmed, on
  execution `11858` per 47.5's own run report). **The planner should treat "1 armed write window"
  (D-06) as needing both surfaces armed together, for the same up-to-5 ids, and both disarmed
  together afterward** — this is a genuine two-surface fact the plan must make explicit, not an
  assumption this research is inventing; it is derived directly from reading both scripts this
  session.

## The D-04 gate node

Confirmed this session by reading `scripts/build_cloud_workflows.py`. The **CLOUD** workflow
(`wf_enrichment_cloud.json`, built by the function containing the code at lines ~4760–5110) builds
`"Claude Web Research"` at **lines 4770–4775**:

```python
nodes.append(_http_node(
    "Claude Web Research", "https://api.anthropic.com/v1/messages", csx, cy - 180,
    auth="header",  # credential header x-api-key: <ANTHROPIC_API_KEY>
    headers=[{"name": "anthropic-version", "value": "2023-06-01"},
             {"name": "content-type", "value": "application/json"}],
    json_body="={{ JSON.stringify($json.research_request_body) }}"))
```

`_http_node()`'s default `on_error="continueRegularOutput"` (confirmed at its definition, lines
3337–3356) is **why** the folded todo's failure mode happens: this is a deliberate, documented
default ("every existing call site keeps its current behaviour") — the 400 is carried as data on
the node's main output rather than failing the execution, exactly as `47-BLOCKED.md`/exec `11833`
observed. The connection wiring at **line 5085** is the exact insertion point:
`"Claude Web Research": {"main": [[{"node": "Validate Research Output", "type": "main", "index":
0}]]}` — D-04's gate must be spliced between these two nodes.

**The established idiom to copy** (built in Phase 47.5, `IF Company Recompute` / `IF Company
Skip`, lines 4690–4697 for node construction and 5060–5069 for wiring) uses
**`_if_bool_expr_node(name, expr, x, y)`** (defined lines 2977–2997), which builds an IF node
testing an arbitrary n8n boolean expression rather than a bare `$json.<field>` lookup:

```python
def _if_bool_expr_node(name, expr, x, y):
    return {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ " + expr + " }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "equals"},
            }],
        }},
        "id": nid("if"), "name": name,
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }
```

A D-04 gate node built this way, e.g. `_if_bool_expr_node("IF Research Errored",
"!!$json.error || !Array.isArray($json.content)", x, y)`, inserted so
`"Claude Web Research"` → `"IF Research Errored"` → (true) a stated-reason terminal /
(false) `"Validate Research Output"`, matches both the CONTEXT.md-specified idiom and the
already-shipped `IF Company Skip` pattern.

**The true-lane cannot wire directly to `Build Response` the way `IF Company Skip` does — its
input row is a different shape.** Confirmed this session by reading `ENRICH_BUILD_RESPONSE`
(`scripts/build_cloud_workflows.py:3956-3970`): `Build Response` does `$input.all().map((item) =>
({ json: { ...item.json, remaining_credits } }))` — it is a pure pass-through-plus-credits node
that assumes the arriving row already carries `action`, `hs_object_id`/company identity, and (for
a gate-skip terminal) `gate.reason`, because those fields were set upstream by `Company Gate`
(`ENRICH_CO_GATE`, confirmed at lines 1862-1888: every row it emits carries `{...row, gate,
action}`) and simply survive, untouched, all the way through `IF Company Skip`'s bare
`$json.action === "skip"` check. **`IF Research Errored`'s true-lane item is the raw HTTP-node
output** — `{"json": {"error": {...}}}` per the folded todo's own quoted shape — which has
**none** of `action`/`hs_object_id`/`gate`, because the `"Claude Web Research"` HTTP node already
replaced `$json` with its own response by the time this gate runs (the exact same "an HTTP hop
replaces the item" fact that makes `Validate Research Output` itself recover its row by node name
rather than trust `$json` — confirmed at `_enrich_validate_research_js`,
`scripts/build_cloud_workflows.py:2360-2362`: `const preHttp = (function () { try { return
$('Build Research Request').all(); } catch (e) { return []; } })();`, using
`research_pre_http_node="Build Research Request"`, confirmed at line 2093). Wiring
`IF Research Errored`'s true lane straight to `Build Response` as originally drafted would
produce a response body that is just `{error: {...}, remaining_credits: [...]}` — technically
observable (better than today's silent success), but missing the company identity and an
`action` value, unlike every other terminal's response shape.

**Corrected recommendation:** insert one small Code node between the true lane and
`Build Response` — call it e.g. `"Build Research Failure Response"` — that recovers the pre-HTTP
row **by the identical idiom `Validate Research Output` already uses** (`$('Build Research
Request').all()`, guarded with the same try/catch, indexed the same way), and returns
`{ ...row, action: "research_failed", gate: { reason: "<the Anthropic error message>" } }` so the
row that reaches `Build Response` has the same shape every other terminal produces. This does
**not** trigger the `ENRICH_CO_GATE`/`nodeAll` sharing trap: `"Build Research Request"` is a node
that exists only inside this one built workflow's own research branch (parameterized per
`cloud=True`/`cloud=False` into two *separate* generated JS strings for the two enrichment
workflow variants — not one JS constant reused verbatim across three deployed workflows the way
`ENRICH_CO_GATE` is), so a bare-by-name read here is exactly as safe as `Validate Research
Output`'s own existing read of the same node. **Not yet built or tested this session — this is a
design recommendation for the plan, not a verified-against-a-live-execution claim**; the offline
node test in Validation Architecture below should assert this exact recovery-and-shape behavior
before the gate is considered done.

**What the error-shaped payload actually looks like on the node's raw HTTP output** (confirmed via
`.planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md`, live exec `11833`):

```json
{"json": {"error": {"message": "400 - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",
\"message\":\"Your credit balance is too low to access the Anthropic API...\"}}", "name": "AxiosError"}}}
```

**Important secondary finding, not in CONTEXT.md's framing, confirmed by reading
`n8n/code/webResearch.js:154–194` this session:** the "Validate Research Output" node's JS
(`researchCandidateFromHttpItem`) **already** guards `!item || item.error || !Array.isArray(item.content)`
and returns an "unmatched" candidate (`matched: false`, `confidence: 0`, `data: {}`) rather than
parsing the error object as research data — so the specific "error object consumed as a
ProviderResult" framing in the folded todo is *not* what the current `webResearch.js` does. What
actually still happens without D-04's gate: an errored research call silently becomes an
"unmatched" candidate that **still flows into `Merge Company`/`Decide Company Action`** exactly
like a genuine no-match research result — indistinguishable from real coverage in the execution
log, and (per `validateResearchOutput`, `n8n/code/webResearch.js:21-64`) `needs_review: true` is
set via the org-type-normalization path, not via any error-specific signal. **The observed live
`lv_revenue_band`/`lv_employee_band` writes on a credit-exhausted run (the todo's headline claim)
must therefore come from a different node in the merge/normalize chain defaulting/estimating those
bands regardless of match status — this was not traced further this session** (see Open Questions).
D-04's gate closes the whole class regardless of that unresolved detail, by refusing to let an
error-shaped payload reach `Validate Research Output` at all — which is the correct, more
defensive fix CONTEXT.md specifies, independent of exactly how the garbage values get written
today.

**`ENRICH_CO_GATE` sharing trap** (CONTEXT.md constraint #7, confirmed via the
`companyRecomputeLaneFlow.test.mjs` test's own header comment, read this session): `ENRICH_CO_GATE`
is shared by three workflows, only one of which has a `Parse HubSpot Event` node feeding it. Any
new `$()` node-name read D-04 or any other Phase-48 code adds must use the repo's `nodeAll`
try/catch idiom (`function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; }
}`, confirmed present at multiple sites e.g. lines 1403 and 1920) and fail closed. D-04's gate as
specified above reads `$json.error`/`$json.content` directly (bare, no node-name lookup) — this
does **not** trigger the `ENRICH_CO_GATE` sharing trap, because it sits immediately downstream of
its own HTTP node with no intervening hop, the same reasoning `IF Company Skip`'s comment gives for
its own bare `$json.action` read (line 4687-4688: "correct HERE and only here: its immediate
upstream is a Code node, with no HTTP hop in between that could have replaced the item" — for D-04
the immediate upstream IS the HTTP node itself, so a bare `$json` read is exactly right).

**Parity rule applicability:** D-04's gate node is pure control flow (routing), not a scoring
predicate — Phase 46's "every engine in one commit" parity rule does not bind it. It only needs to
land in `scripts/build_cloud_workflows.py` (the single source for the CLOUD workflow); there is no
Python-oracle or HubSpot-flow analog of "Claude Web Research" to keep in parity, since the
standalone `src/web_research.py::claude_web_research` (used by the offline driver, not by n8n)
already has its own separate call site with its own `try`/`except` semantics — unaffected by this
gate.

## The research call for Racing NSW

`src/web_research.py` read in full this session. `RESEARCH_SYSTEM` (lines 31–54) is the exact
prompt used by `claude_web_research()` when `USE_MOCK_WEB_RESEARCH` is not `"true"`. **It does
NOT currently constrain `lv_org_type` to the 9-value enum** — its schema fragment reads
`"lv_org_type":<str>` (line 38), an open string, exactly matching the free-text pattern seen in
every one of the 4 already-captured records (`data.lv_org_type` values like "Media company / Web
television broadcaster"). This is confirmed as the root cause of Phase 47's whole "strict enum
gate refused to guess-map free-text output" problem (`remediate_veto_companies.py`'s
`_classify_org_type()`).

**What must change to constrain output to the 9 live options:** replace the open
`"lv_org_type":<str>` schema fragment with an explicit enumerated constraint, e.g.
`"lv_org_type":<one of "governing_body_league"|"content_producer"|"broadcaster"|
"individual_club_team"|"regulator"|"gambling_operator"|"hardware_vendor"|"other"|"unknown">`, and
add a sentence instructing the model to answer `"unknown"` rather than invent a value outside this
set — mirroring the `prefer "unknown"/null over guessing` sentence already present at line 47 for
other fields. **The 9 values are confirmed identical across all three sources checked this
session**: CONTEXT.md's list, `config/hubspot_properties.yaml:344-386`
(`governing_body_league, content_producer, broadcaster, individual_club_team, regulator,
gambling_operator, hardware_vendor, other, unknown`), and the live portal snapshot
`config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json` (`type:
"enumeration"`, `fieldType: "select"`, the same 9 `options`, `updatedAt: "2026-07-30..."`).
`[VERIFIED: config/hubspot_properties.yaml:338-386]` and
`[VERIFIED: config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json]`.

**Claude's Discretion is explicit here** (CONTEXT.md): either (a) edit `RESEARCH_SYSTEM` itself
(shared/production, so this would also change the schema every future call — including Phase 47's
already-completed 17 — sees, though those calls are done and cached; the parity-tracked comment at
line 27–30 notes this prompt is kept "in parity with the production n8n research prompt" — editing
it here does NOT auto-propagate to `_enrich_build_research_request_js`'s n8n twin, which is a
separate literal in `scripts/build_cloud_workflows.py`, so a `RESEARCH_SYSTEM` edit is a
Python-only, dev-oracle-only change unless the planner separately decides to port it into the n8n
prompt too — nothing in CONTEXT.md requires that n8n-side port this phase, since Racing NSW's
research runs through the standalone Python path, not through n8n), or (b) build a narrower
one-off prompt used only for this call, leaving `RESEARCH_SYSTEM` untouched. **Recommendation:**
option (b) is lower-blast-radius and matches D-01's "1 record" framing — a one-off, purpose-built
prompt for a single call is simpler to reason about than a shared-prompt edit whose downstream
effects (the "kept in parity" comment) this session did not fully trace.

## Cost estimation mechanics (COVER-02)

**`estimate_cost()` (`scripts/remediate_veto_companies.py:650-671`) cannot be reused
UNMODIFIED for Phase 48 — its execution model is wrong for this phase's shape, and reporting its
raw output would mis-state the estimate.** `estimate_cost(ids)` charges exactly one
`n8n_executions` per id, on the assumption every id's research AND write happens through the D-18
webhook POST — that was true for Phase 47 (D-08's standalone-Python research is followed by a
webhook POST per pinned record, one n8n execution each). **Phase 48's shape is different and
smaller:** Racing NSW's research is a **direct Anthropic API call via `src/web_research.py`,
costing zero n8n executions** (`claude_web_research()` calls `client.messages.create()` directly —
no HTTP round-trip through n8n at all); the **n8n executions this phase spends are entirely the
D-09 recompute POSTs**, one per record actually *written* (up to 5, not up to 1). Calling
`estimate_cost(["15008671672"])` would under-report (it would say `n8n_executions: 1` for the
research call that in fact costs 0 n8n executions, and say nothing about the up-to-5 recompute
executions); calling it against all 5 ids would over-report the research-call count (it would say
`web_research_calls: 5`, but 4 of the 5 records' research is already paid for and cached in
`47-RESEARCH-RESULTS.json` — zero new calls).

**Recommendation: Phase 48's driver needs its own cost-estimate function**, still produced by
code rather than hand-derived (the same house rule `estimate_cost()` itself follows), reusing
`ANTHROPIC_PER_RECORD_ESTIMATE_USD` (line 647) and `N8N_EXECUTION_BUDGET_MONTH`
(`N8N_EXECUTION_BUDGET_MONTH = 2500`, line 167) as its constants, but modeling the correct shape:

```python
def estimate_phase48_cost(research_ids, written_ids) -> dict:
    """research_ids: ids needing a fresh claude_web_research() call (Racing NSW only, expected
    len 1). written_ids: every id this run will actually PATCH lv_org_type/lv_enrichment_review_
    reason on (up to 5) -- each gets exactly one D-09 recompute POST, one n8n execution."""
    return {
        "web_research_calls": len(research_ids),
        "n8n_executions": len(written_ids),  # recompute POSTs only -- research is direct Anthropic
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "lusha_credits_note": "D-01: offline mapping + one direct research call, no provider waterfall.",
        "anthropic_estimate_usd": round(len(research_ids) * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
    }
```

For the expected shape (`research_ids=["15008671672"]`, `written_ids=` all 5), this reads
`web_research_calls: 1`, `n8n_executions: 5`, `anthropic_estimate_usd: 0.0686` — matching D-01's
own "~$0.07 order-of-magnitude" and D-06's "record cap 5" language exactly, and correctly showing
zero n8n cost for the 4 already-researched records' writes are folded into the same 5
recompute-POST executions, not double-counted as research calls. **`refuse_if_over_budget()`'s
literal refuse-not-truncate logic (unchanged, reused as-is) should be called against this
corrected dict**, not against `estimate_cost()`'s raw output. **The Lusha balance check is still
required by COVER-02's literal wording** ("the
current Lusha balance") even though zero credits will be drawn — `scripts/check_provider_credits.py`
(read this session) is the existing tool: `_check_lusha()` calls the credit endpoint and
`_extract_lusha(raw)` reads `raw["credits"]["remaining"]` — `[VERIFIED: scripts/check_provider_credits.py:67-75]`
`def _extract_lusha(raw): ... credits = raw.get("credits") ... remaining = credits.get("remaining")`.
ZoomInfo's extractor (lines 88-111) needs the JSON:API `Accept: vnd.api+json` header via the
credit registry's `credit["accept"]` value or it 406s (confirmed present in the mint-then-GET flow
at lines 165-179); Apollo's extractor (lines 78-85) degrades to `None` on this account's non-master
key (403, confirmed by the code comment "THIS account's key 403s (non-master)"). None of this
matters for what Phase 48 *spends* (0 provider credits either way), but the driver's cost-estimate
report should still call `check_provider_credits.py`'s output (or a subset) to satisfy COVER-02's
literal "against ... the current Lusha balance" bar, per the `47-COST-ESTIMATE.md` precedent
document's own structure (read this session) — that document is the exact shape COVER-02 wants and
should be copied almost verbatim for `48-COST-ESTIMATE.md`, with the record count changed from 17
to whatever the live re-derivation finds (5, unless the population has moved).

**"Refuse outright, never truncate" implementation:** `refuse_if_over_budget(estimate, ids)`
(lines 674-683) is the existing, directly reusable pattern: it raises `BudgetRefused` when
`estimate["n8n_executions"] > estimate["n8n_budget_month"]`, and otherwise returns `ids`
**completely unmodified** — there is no code path in this function (or anywhere else in the file)
that trims `ids` down to a partial batch. Phase 48's driver should call this same function (or a
byte-identical copy scoped to its own estimate dict shape) before any HubSpot or n8n call, exactly
as `main()` does at lines 941-945. Given the population is 5 records and the n8n budget is 2,500,
this refusal path will not fire in practice — but the code path must exist and be exercised
(even if only by a unit test asserting it raises on a synthetic over-budget estimate), per
COVER-02's literal requirement that a refusal is *possible*, not merely that it never triggers.

## Package Legitimacy Audit

**Not applicable.** This phase adds zero new external packages, in any ecosystem. Every write leg,
research call, and HTTP node reuses existing project code
(`scripts/remediate_veto_companies.py`, `src/web_research.py`, `src/hubspot_client.py`,
`scripts/build_cloud_workflows.py`, `scripts/check_provider_credits.py`,
`scripts/june_run_arm.py`) and already-installed dependencies (`anthropic`, `requests`, `pydantic`
— all present in `requirements.txt` per the project's CLAUDE.md §11.3, unchanged this phase).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cost projection | A hand-derived dollar/execution estimate in prose | A code-produced estimate — reuse `ANTHROPIC_PER_RECORD_ESTIMATE_USD`/`N8N_EXECUTION_BUDGET_MONTH` constants and the "code produces the doc's numbers" pattern, but with Phase 48's own execution model (see "Cost estimation mechanics" — `estimate_cost()` itself is NOT directly reusable, its per-id n8n-execution charge assumes Phase 47's shape) | Phase 47's own house rule ("estimate produced by code, not prose") — the `47-COST-ESTIMATE.md` figures were read from a live call, never hand-derived, specifically so the doc and the function can never silently drift |
| Budget refusal | A manual "if too big, skip some records" loop | `refuse_if_over_budget()`, called against the corrected Phase-48-shaped estimate dict | Truncating silently is the exact failure COVER-02 forbids; the existing function already refuses-whole, never trims |
| Org-type keyword guessing | A regex/keyword mapper from free text to enum | The CONTEXT.md-authored per-record mapping table (D-01/D-05), applied by hand or by a small literal lookup dict | `_classify_org_type()`'s own docstring (lines 283-308) explains exactly why this is unsafe: it already tried deriving org_type from `lv_is_gambling_operator` and found it wrong for 8/17 records — a fresh keyword mapper would repeat that mistake |
| Veto recompute | A second `Decide Company Action`-equivalent, or a direct PATCH to `lv_anti_icp_flag`/`lv_icp_tier` | `post_webhook_event(..., recompute=True)` | Project D-07 (absolute, restated in every phase since 40-05): only `Decide Company Action` may write those fields; a direct PATCH is explicitly forbidden |
| n8n IF-gate construction | A hand-written raw n8n node dict | `_if_bool_expr_node()` / `_if_bool_node()` (`scripts/build_cloud_workflows.py:2959-2997`) | These are the exact builder functions every other IF gate in the file uses (18 call sites found this session); hand-rolling risks a subtly wrong `typeVersion`/`operator` shape that only 400s live |

**Key insight:** almost nothing in this phase should be new code. The correct shape of Phase 48's
own driver script is "import from `scripts/remediate_veto_companies.py`, override the id set and
the arm-key name, keep everything else" — the file's own module docstring calls out that its
non-reused write-leg functions (batch PATCH, webhook POST, settle-and-assert, cost estimate) exist
precisely so a sibling script does not need to re-derive them.

## Architecture Patterns

### System Architecture Diagram

```
[Phase 48 driver script]
   |
   |-- 1. search_records("companies", HAS_PROPERTY/NOT_HAS_PROPERTY filter) --> live population,
   |        stamped with today's date
   |
   |-- 2a. read 47-RESEARCH-RESULTS.json[id] for 4 records (zero network)
   |-- 2b. claude_web_research(Racing NSW record)  --[Anthropic native web_search]--> ProviderResult
   |
   |-- 3. per-record: apply CONTEXT.md mapping table -> lv_org_type (or "unknown" + reason)
   |
   |-- 4. estimate_cost(ids) -> refuse_if_over_budget() [+ check_provider_credits.py for Lusha line]
   |        |
   |        +-- over budget? --> BudgetRefused, no call made
   |        +-- within budget --> continue
   |
   |-- 5. [ARMED WINDOW -- operator-driven]
   |        batch_update_companies([...], dry_run=False)   -- direct HubSpot PATCH: lv_org_type,
   |                                                            lv_enrichment_review_reason,
   |                                                            lv_org_type_verified_at
   |        |
   |        v
   |     post_webhook_event(id, armed=True, recompute=True)  -- D-18 POST
   |        |
   |        v
   |     [n8n Cloud] Webhook -> Parse HubSpot Event -> ... -> Company Gate
   |        -> IF Company Recompute (true) -> Decide Company Action
   |                                             |  (SOLE writer of lv_anti_icp_flag/_reason)
   |                                             v
   |                                        HubSpot Company Update
   |        |
   |        v
   |     settle_veto(id)  -- poll until lv_anti_icp_flag settles
   |
   |-- 6. verify_post_run() -- re-read, confirm no divergence
   |-- 7. disarm both surfaces (driver env flag + june_run_arm.py --disarm), independent re-read
   |-- 8. write run report: before/after per record, actual vs. estimated cost

[separately, no dependency on the above at runtime -- a build-time change]
scripts/build_cloud_workflows.py
   Claude Web Research (HTTP, onError=continueRegularOutput)
        |
        v
   IF Research Errored  [NEW -- D-04]         <- _if_bool_expr_node(...)
        |-- true (error-shaped payload) --> Build Response (stated reason) --> Respond to Webhook
        |-- false --------------------------> Validate Research Output (unchanged downstream)
   |
   rebuild n8n/wf_enrichment_cloud.json --> operator deploy+bounce (Claude may not perform this)
```

### Recommended Project Structure

No new directories. One new driver script at `scripts/` root (naming is Claude's Discretion —
e.g. `scripts/enrich_coverage_companies.py`), following the exact module layout of
`scripts/remediate_veto_companies.py` (imports at top, constants, pin-resolution, cost estimate,
write legs, `main()` with `argparse`). One edit to `scripts/build_cloud_workflows.py` for the D-04
gate. Possibly one edit to `n8n/code/*.js` if the planner also chooses to port the enum constraint
into the n8n-side research prompt (not required — Racing NSW's research runs through the
standalone Python path).

### Anti-Patterns to Avoid

- **Hand-editing `n8n/wf_enrichment_cloud.json`:** forbidden absolutely (project constraint). Every
  workflow change must originate in `scripts/build_cloud_workflows.py` and be rebuilt.
- **Keyword-guessing `lv_org_type` from free text:** already proven unsafe by Phase 47's own
  `_classify_org_type()` design and its gambling-operator-boolean cautionary tale.
- **Treating the driver's own env-gate arm and `june_run_arm.py`'s n8n-side arm as one surface:**
  they are two independent gates guarding two independent write paths (direct HubSpot PATCH vs.
  n8n's `Decide Company Action` → `HubSpot Company Update`); both need arming for D-09's recompute
  leg to actually write.

## Common Pitfalls

### Pitfall 1: Assuming the free-text org-type string in `47-RESEARCH-RESULTS.json` is already an
enum value
**What goes wrong:** a naive script writes `data.lv_org_type` straight to HubSpot.
**Why it happens:** the field name matches the live property name exactly, inviting a pass-through.
**How to avoid:** every write must go through the CONTEXT.md per-record mapping table (a manual
decision, not automated), and be validated against `VALID_ORG_TYPES` before any PATCH call.
**Warning signs:** a HubSpot 400 on the batch PATCH naming `lv_org_type` as the offending property.

### Pitfall 2: n8n `status: "success"` masking a research failure (the folded todo)
**What goes wrong:** a credit-exhausted or otherwise-erroring `Claude Web Research` call returns
`executionStatus: "success"` with zero node-level errors; the error payload is passed downstream
as data.
**Why it happens:** `_http_node()`'s default `onError: "continueRegularOutput"` — deliberate,
documented, and shared by every other provider HTTP node in the file (line 3337-3356's own
docstring explains why write nodes are the deliberate exception).
**How to avoid:** land D-04's gate node before arming; separately, check Anthropic account credit
before opening the armed window (no existing script does this — see Open Questions).
**Warning signs:** an execution whose `runData` for `Claude Web Research` carries `json.error`
rather than `json.content`; judge every run by node-level `runData`, never by execution status.

### Pitfall 3: A client POST timeout being mistaken for a failure
**What goes wrong:** the driver retries a webhook POST after its own client-side timeout fires,
while n8n is still completing the execution server-side — the record gets touched twice.
**Why it happens:** `post_webhook_event()`'s `timeout` parameter is client-side only.
**How to avoid:** the function's default is already 300s (fixed from an earlier 30s bug); never
lower it, and never retry on a timeout without first reading the execution back via
`executions_client` to confirm it actually failed.
**Warning signs:** two settle-and-assert cycles for the same record id in one run.

### Pitfall 4: An empty n8n allowlist silently reporting "armed"
**What goes wrong:** `june_run_arm.py --ids ""` (or a domain list resolving to nothing) arms
successfully and blocks every write, while `HubSpot Company Update` returns `write_blocked`
without an obvious top-level error.
**Why it happens:** an empty allowlist is a valid, "successfully armed" state by design (deny-all
is safe-by-default).
**How to avoid:** assert the allowlist is non-empty AND exactly the intended 5 ids, in the driver,
immediately after arming — never by eyeball.
**Warning signs:** `action: "write_blocked"` in the recompute POST's response, or a 2.4s execution
duration instead of the healthy 10-37s range (CONTEXT.md Trap #6).

### Pitfall 5: `ENRICH_CO_GATE`'s shared-workflow `$()` read throwing on an unrelated workflow
**What goes wrong:** any new `$()` node-name lookup added to a shared code path throws on the two
sibling workflows (`wf_enrichment_local_live`, `wf_scheduled_maintenance_cloud` / SJ-2) that lack
the referenced node.
**Why it happens:** `ENRICH_CO_GATE` code is literally shared across three built workflows.
**How to avoid:** D-04's gate as specified (a bare `$json` read, no `$()` node-name lookup) does
NOT touch this trap. If the planner's implementation instead needs a node-name lookup anywhere in
this phase's changes, it must use the repo's `nodeAll` try/catch idiom and fail closed.
**Warning signs:** SJ-2's daily sweep failing on every row after a rebuild+deploy.

## Code Examples

### The exact D-04 gate insertion (composed from confirmed idioms, not yet written to the repo)

```python
# Source: scripts/build_cloud_workflows.py, existing idioms at lines 2977-2997 (_if_bool_expr_node),
# 4690-4697 / 5060-5069 (IF Company Recompute / IF Company Skip, the gate-with-failure-branch
# pattern), and 2360-2362 (Validate Research Output's own pre-HTTP row recovery by node name --
# the pattern the new failure-response Code node below must copy, per the "corrected
# recommendation" above). Insertion point: between the existing "Claude Web Research" node build
# (lines 4770-4775) and its wiring to "Validate Research Output" (line 5085).

nodes.append(_if_bool_expr_node(
    "IF Research Errored",
    "!!$json.error || !Array.isArray($json.content)",
    csx, cy - 180,  # same row as "Claude Web Research" / "Validate Research Output"
))
nodes.append(code_node("Build Research Failure Response", r"""
// Recovers the pre-HTTP row by node name -- SAME idiom Validate Research Output already uses
// for "Build Research Request" (scripts/build_cloud_workflows.py:2360-2362) -- so the response
// this failure terminal produces carries the same action/hs_object_id/gate shape every other
// Build Response terminal does, instead of a bare Anthropic error blob with no company identity.
const preHttp = (function () {
  try { return $('Build Research Request').all(); } catch (e) { return []; }
})();
return $input.all().map((it, i) => {
  const row = (preHttp[i] && preHttp[i].json) || {};
  const message = (it.json && it.json.error && it.json.error.message) || 'research call failed';
  return { json: { ...row, action: "research_failed", gate: { reason: message } } };
});
""", csx, cy - 260))
# ... wiring, replacing the single existing edge at line 5085:
conns["Claude Web Research"] = {"main": [[{"node": "IF Research Errored", "type": "main", "index": 0}]]}
conns["IF Research Errored"] = {"main": [
    [{"node": "Build Research Failure Response", "type": "main", "index": 0}],  # true: errored
    [{"node": "Validate Research Output", "type": "main", "index": 0}],         # false: unchanged
]}
conns["Build Research Failure Response"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
```

**This exact Code node body is a research-time design sketch, not a verified-working
implementation** — the planner/executor must offline-test it (see Validation Architecture) against
both a genuine `{error:{message:...}}` shape and a malformed/empty item before landing it.

### Reusing the driver's refusal pattern, against a Phase-48-shaped estimate

```python
# Pattern source: scripts/remediate_veto_companies.py:939-945 (main()'s own call sequence) and
# :674-683 (refuse_if_over_budget, reused UNMODIFIED). The estimate dict itself must be
# Phase-48-shaped (see estimate_phase48_cost() above) -- estimate_cost() itself charges one
# n8n_execution per id assuming Phase 47's research-via-webhook shape, which does not hold here.
estimate = estimate_phase48_cost(research_ids=["15008671672"], written_ids=resolved_ids)
print(f"COST ESTIMATE: {json.dumps(estimate, indent=2)}")
try:
    resolved_ids = refuse_if_over_budget(estimate, resolved_ids)  # refuse_if_over_budget itself
                                                                    # is reused verbatim -- it only
                                                                    # reads estimate["n8n_executions"]
                                                                    # / estimate["n8n_budget_month"]
except BudgetRefused as exc:
    print(f"REFUSED: {exc}")
    return 1
```

### The D-09 recompute POST, per written record

```python
# Source: scripts/remediate_veto_companies.py:596-625 (post_webhook_event), CONTEXT.md D-09
post_webhook_event(company_id, armed=True, config=cfg, recompute=True)
settle_veto(company_id)  # or a Phase-48-scoped equivalent poll on lv_anti_icp_flag/lv_org_type
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Strict enum gate silently rejects all free-text `lv_org_type` research output (Phase 47) | An explicit per-record human-authored mapping table (D-01/D-05), applied by the offline pass | Phase 48 (this decision) | Coverage moves from "17/17 blocked by the gate, 13 resolved another way" to "resolved by direct decision for 5 records at n=5, no automated guessing" |
| `RESEARCH_SYSTEM`'s `lv_org_type` schema field is an open string | Needs to become an enum-constrained field for Racing NSW's call (not yet done — this phase's job) | Not yet changed | Prevents Racing NSW's fresh call from producing yet another unmappable free-text value |
| A complete record's veto could never be recomputed on demand | The Phase 47.5 recompute lane (`IF Company Recompute`/`IF Company Skip`) | 2026-08-12 (this morning, per HANDOVER.md) | Directly enables D-09 — writing `lv_org_type` no longer permanently freezes a record's veto |
| `lv_org_type` believed to be free text (multiple stale docs) | Confirmed live `type: enumeration`, `fieldType: select`, 9 options | 2026-08-08 migration, re-confirmed 2026-08-12 doc sweep, re-confirmed again this session | An out-of-vocabulary write 400s the whole batch — every Phase 48 write must validate against the 9-tuple first |

**Deprecated/outdated:**
- `docs/WEB-RESEARCH-SPEC.md:208`'s "lv_org_type is not an enumeration" note — stale, superseded,
  do not cite as current.
- The literal ROADMAP text "full provider waterfall per record" for Phase 48 — explicitly rejected
  by D-01; providers do not return `lv_org_type` at all.

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase. No string is being renamed across
systems; this phase writes new field values to existing, already-created properties on existing
records.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Anthropic account currently has sufficient credit to make Racing NSW's one live research call | "The research call for Racing NSW" / Pitfall 2 | If wrong, D-04's gate (once deployed) correctly prevents a garbage write, but the run still fails to produce Racing NSW's `lv_org_type` — no code in this repo currently pre-checks Anthropic credit before a research call; this is a genuine gap, not something this session found a fix for (see Open Questions) |
| A2 | Naming Phase 48's own driver-side arm-key (e.g. `ALLOW_ENRICH_COVERAGE=true`) is safe to invent fresh rather than reuse `ALLOW_VETO_REMEDIATION` | "The driver to extend" | Low risk — this is explicitly Claude's Discretion per CONTEXT.md; reusing `ALLOW_VETO_REMEDIATION`'s literal name would be confusing (a coverage run is not veto remediation) but functionally harmless if the planner chooses to |
| A3 | `47-COST-ESTIMATE.md`'s document structure is the correct template to copy for `48-COST-ESTIMATE.md` | "Cost estimation mechanics" | Low risk — CONTEXT.md's own canonical_refs names this document as "the ex-ante estimate pattern COVER-02 wants" |

**No claim above concerns a package name, a compliance requirement, or a discrete in-repo value
not directly quoted from a file read this session.** Every enum value, function signature, and
JSON shape cited above was read from the named file:line this session, not recalled from training
data or an earlier phase's summary.

## Open Questions

1. **Where exactly does the credit-exhausted run's `lv_revenue_band`/`lv_employee_band` garbage
   actually originate, if not from `researchCandidateFromHttpItem`'s error handling?**
   - What we know: `researchCandidateFromHttpItem` (`n8n/code/webResearch.js:175-194`) already
     guards `item.error` and returns an unmatched candidate (`matched: false`, `data: {}`) — it
     does not parse the error object as real data.
   - What's unclear: something downstream in `Merge Company`/`Normalize + Score Company` must be
     the actual source of the plausible-looking band values observed live on exec `11833`, since
     an unmatched/`confidence: 0` candidate shouldn't normally win a merge.
   - Recommendation: this does not block Phase 48 planning — D-04's gate closes the class
     regardless of the exact downstream mechanism, by refusing to let the error-shaped payload
     reach `Validate Research Output`/`Merge Company` at all. If the planner wants full root-cause
     clarity before landing the gate, one additional `Read` of `ENRICH_MERGE_CO`'s JS (not done
     this session) would resolve it, but is not required to satisfy D-04's literal instruction.

2. **Is there an existing Anthropic-account credit-balance check anywhere in this repo, reusable
   the way `check_provider_credits.py` covers Lusha/Apollo/ZoomInfo?**
   - What we know: `check_provider_credits.py` covers exactly the three provider APIs (Lusha,
     Apollo, ZoomInfo) — it does not call any Anthropic billing/usage endpoint.
   - What's unclear: whether such an endpoint exists on the Anthropic platform and would be worth
     wiring in before arming (the folded todo suggests it as a possible mitigation but says
     "not scoped anywhere yet").
   - Recommendation: out of scope for Phase 48's stated success criteria (COVER-01/COVER-02 do not
     mention Anthropic billing); leave as a manual operator pre-check ("confirm Anthropic credit
     before arming") rather than new code, consistent with D-06's "declare, don't over-build"
     framing for a 5-record phase.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `HUBSPOT_PRIVATE_APP_TOKEN` | Every HubSpot read/write leg | Not verified this session (`.env` is Read/Bash permission-blocked) — assumed present per every prior phase's successful live work | — | None; the driver's own `_has_credentials()` gate already handles absence gracefully (prints "skipped", returns 0) |
| `ANTHROPIC_API_KEY` | Racing NSW's fresh research call | Same as above | — | `USE_MOCK_WEB_RESEARCH=true` falls back to the fixture, but that is a dev/test-only path, not usable for a real Racing NSW answer |
| n8n Cloud (deployed workflow) | D-04's gate deploy, D-09's recompute POST | Live and reachable (confirmed by Phase 47.5's own executions this same day) | `LV Enrichment (Cloud template)` `950HPb7a1GgSAIyZ` | None — this is the only production enrichment pipeline |
| `node --test` (glob form) | `tests/n8n/*.test.mjs` | Assumed available per CLAUDE.md/CONTEXT.md's own explicit instruction that the glob form works and the directory form is broken on node 24 | — | None needed; use the glob form exactly as documented |
| `.venv/bin/python -m pytest` | Any offline Python test | Assumed available per repeated CONTEXT.md/CLAUDE.md instruction | — | System python lacks deps (documented) |

**Missing dependencies with no fallback:** none identified — this phase reuses only already-proven
live infrastructure.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework (Python) | pytest, via `.venv/bin/python -m pytest` |
| Framework (n8n/JS) | Node's built-in `node:test`, via `node --test tests/n8n/*.test.mjs` (**glob form only** — the directory form `tests/n8n/` is broken on node 24, per CONTEXT.md/CLAUDE.md, restated here as binding) |
| Config file | none dedicated — both suites run via the commands above; no new config needed this phase |
| Quick run command | `.venv/bin/python -m pytest tests/test_<new_module>.py -x` for the new driver's own unit tests; `node --test tests/n8n/researchErrorGateFlow.test.mjs` (or equivalent single new file) for D-04's gate |
| Full suite command | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COVER-01 (mapping correctness) | Each of the 4 already-researched records maps to the exact CONTEXT.md-specified enum value (or `unknown` for Editix) | unit | `.venv/bin/python -m pytest tests/test_<new_module>.py -k mapping -x` | ❌ Wave 0 — new file, following `tests/test_veto_remediation_report.py`'s existing pattern of asserting a classifier function's output against named fixture ids |
| COVER-01 (marker distinguishability) | A record with `lv_org_type="unknown"` also carries a non-empty `lv_enrichment_review_reason`, and this state is provably distinct from a blank `lv_org_type` | unit | same new test file, `-k marker` | ❌ Wave 0 |
| COVER-01 (Racing NSW enum constraint) | The corrected research prompt (or one-off prompt) never returns a value outside `VALID_ORG_TYPES` | unit, offline, against a synthetic/fixture response | `.venv/bin/python -m pytest tests/test_<new_module>.py -k racing_nsw -x` | ❌ Wave 0 |
| COVER-02 (cost estimate, refusal) | `estimate_cost()`/`refuse_if_over_budget()` produce correct numbers for the Phase 48 id set, and `refuse_if_over_budget` genuinely raises on a synthetic over-budget estimate | unit, offline | `.venv/bin/python -m pytest tests/test_<new_module>.py -k budget -x` | ❌ Wave 0 — mirrors existing coverage in the veto-remediation script's own (unread this session, but named in CONTEXT.md's canonical_refs) test suite pattern |
| D-04 (gate node routes an error-shaped payload to `Build Response`) | The committed `wf_enrichment_cloud.json`'s `IF Research Errored` node correctly routes both a genuine `{error:...}` item and a healthy `{content:[...]}` item, by driving the ACTUAL emitted node/expression the same way `tests/n8n/companyRecomputeLaneFlow.test.mjs` already does for `IF Company Recompute`/`IF Company Skip` | node:test, offline, against the committed workflow JSON | `node --test tests/n8n/researchErrorGateFlow.test.mjs` (new file, modeled directly on `companyRecomputeLaneFlow.test.mjs`'s pattern of loading `n8n/wf_enrichment_cloud.json`, faking `$()` node lookups, and evaluating the IF node's real `leftValue` expression via `new Function`) | ❌ Wave 0 |
| RECOMP-lane reuse (D-09, no regression) | The existing acceptance test for the recompute lane stays green after D-04's gate addition (no node renumbering/renaming collision) | node:test, live-dependent for the acceptance bar, offline for the structural guard | `node --test tests/n8n/companyRecomputeLaneFlow.test.mjs` | ✅ exists, must stay green |

### Sampling Rate

- **Per task commit:** the relevant single test file (`-k <marker>` or the single new `.test.mjs`
  file), not the full suite — this phase's changes are narrow and additive.
- **Per wave merge:** full offline suites — `.venv/bin/python -m pytest` and
  `node --test tests/n8n/*.test.mjs` (glob form).
- **Phase gate:** full suite green before `/gsd-verify-work`, PLUS the live-only checks below,
  which no automated test can cover.

### Wave 0 Gaps

- [ ] `tests/test_<new_module>.py` — the new Phase 48 driver's own unit tests (mapping
      correctness, marker semantics, budget refusal) — no file exists yet; naming is the
      planner's call.
- [ ] `tests/n8n/researchErrorGateFlow.test.mjs` — D-04's gate node structural test, modeled on
      `tests/n8n/companyRecomputeLaneFlow.test.mjs`'s pattern.
- [ ] No new pytest/node:test framework install needed — both are already fully wired in this repo.

### Live-only checks (NOT provable by an automated test; require operator action Claude must not
perform)

The following success-criterion facets can only be proven by live evidence artifacts (a run
report, an independent read-back), not by a test, and several require an action this phase's own
constraints forbid Claude from performing:

- **The population re-derivation itself** (a live `search_records` call, stamped with today's
  date) — this is a live HubSpot read; Claude MAY perform reads, but the count/id-list must be
  captured in the run report as evidence, not asserted from memory.
- **The D-04 deploy + bounce** — `DRY_RUN=false AND ALLOW_N8N_DEPLOY=true`, plus deactivate→
  reactivate — **operator-only this phase** (both Phase 47.5 waivers expired). Claude must hand
  this off and wait for operator confirmation; do not attempt to arm this flag under any framing.
- **Both arming ceremonies** (the driver's own env-flag arm for the direct HubSpot PATCH leg, and
  `june_run_arm.py`'s n8n-side allowlist arm for the `HubSpot Company Update` leg) —
  **operator-only this phase**, per the same expired-waiver rule. Claude prepares the dry-run
  payloads and the exact operator invocation string; the operator runs it.
- **Independent disarm re-read for both surfaces** — must be an independent GET/read, not a
  re-read of the stored PUT body, per Trap #3 (CONTEXT.md, restated from Phase 47.5's own
  precedent).
- **The D-09 before/after tier-distribution numbers** — these are live-observed values (a
  `settle_veto`/`settle_tier`-style poll against the real portal); they can be *recorded* in the
  run report but not asserted by a unit test, since they depend on the live scoring pipeline's
  actual state at execution time.
- **A live proof that `IF Research Errored` actually fires on a real, currently-erroring
  Anthropic call** — the offline node test above proves the routing logic is correct against a
  synthetic error-shaped item; it cannot prove the *deployed* workflow behaves identically without
  a live execution, which needs the operator-only deploy+bounce above to exist first.
- **Jam TV `17317850381` must remain vetoed after the `broadcaster` write.** CONTEXT.md's
  `<specifics>`: writing `broadcaster` adds +20 base score and **cannot** clear its veto — its
  veto is geographic (`lv_anti_icp_reason = "Non-ANZ geography"`, region `Other`), the write is
  org-type. The run report's read-back for this record must explicitly confirm the veto is still
  present after the D-09 recompute settles, not merely that the org-type write landed.
- **Waikato `20538284384`'s research flags `lv_is_gambling_operator: true`.** CONTEXT.md's
  `<specifics>`: this must not be mistaken for a veto trigger or an org-type derivation signal —
  gambling is a graduated deduction and `graduated_deductions` is `{}` since Phase 46 D-03, so it
  changes nothing about Waikato's score or tier. The run report should note this explicitly so a
  future reader does not misread the boolean as load-bearing.

## Sources

### Primary (HIGH confidence — read directly this session)

- `.planning/phases/48-enrichment-coverage/48-CONTEXT.md` — full read, the locked decisions this
  research restates and grounds
- `.planning/phases/48-enrichment-coverage/48-HANDOVER.md` — full read
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — full read
- `.planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json` — full read (all 17 entries),
  confirmed the 4 Phase-48-relevant ids and their exact JSON shape
- `scripts/remediate_veto_companies.py` — full read (1045 lines)
- `src/web_research.py` — full read
- `scripts/build_cloud_workflows.py` — targeted reads: lines 760-830, 2930-3000, 3150-3330,
  4650-4820, 4950-5150 (the CLOUD companies branch, `_if_bool_expr_node`, `_http_node`, the
  `IF Company Recompute`/`IF Company Skip` idiom, and the `Claude Web Research` node build +
  wiring)
- `n8n/code/webResearch.js` — full read (`researchCandidateFromHttpItem`, `validateResearchOutput`,
  `toProviderResult`)
- `.planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md` — full read
- `.planning/phases/47-veto-remediation/47-COST-ESTIMATE.md` — full read
- `scripts/check_provider_credits.py` — full read
- `scripts/june_run_arm.py` — targeted read, lines 1-70
- `config/hubspot_properties.yaml` — grep-confirmed `lv_org_type` (lines 338-386) and
  `lv_enrichment_review_reason` (lines 224, 519) both present live
- `config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json` — parsed and
  confirmed `lv_org_type`'s live schema (9 options, `type: enumeration`, `fieldType: select`)
- `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` — targeted read of the
  dated correction/deferral blocks
- `src/icp_scoring.py` — grep-confirmed lines 83 (blank-region → `"unknown"`) and the
  hardware-vendor OR predicate (`if is_hardware_vendor or org_type == "hardware_vendor":`)
- `src/hubspot_client.py` — grep-confirmed `search_records` signature at line 119
- `tests/n8n/companyRecomputeLaneFlow.test.mjs` — read the header/pattern, the model for D-04's
  new test
- `ls tests/n8n/*.test.mjs` — confirmed 54 files exist, glob form works

### Secondary (MEDIUM confidence)

- None — every claim in this document traces to a primary source read this session; no
  WebSearch/Context7 lookups were needed (this is a pure brownfield-repo phase with zero new
  external dependencies).

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Offline mapping pass (D-01/D-05): HIGH — the exact JSON shape and all 4 record ids were
  confirmed by a full read of the source file this session.
- Driver reuse surface: HIGH — every function signature cited was read from the live file this
  session, not recalled.
- D-04 gate node: HIGH for the insertion point, idiom, and builder function (all read this
  session); MEDIUM for the exact downstream root-cause of the folded todo's specific
  `lv_revenue_band` symptom (flagged as an open question, does not block the gate's correctness).
- Racing NSW research prompt change: HIGH for what must change and why; the choice between
  editing `RESEARCH_SYSTEM` vs. a one-off prompt is explicitly left to Claude's Discretion by
  CONTEXT.md, with a recommendation given.
- Cost estimation mechanics: HIGH — `estimate_cost()`/`refuse_if_over_budget()` and
  `check_provider_credits.py` were both read in full this session.
- Validation Architecture: HIGH for what's testable offline (modeled directly on an existing,
  read test file); explicit and honest about which criteria are live-only and operator-gated.

**Research date:** 2026-08-12
**Valid until:** this phase's own population/portal-schema figures are explicitly time-stamped
and must be re-derived live at plan/execution time regardless of this document's age (per
CONTEXT.md's own repeated instruction) — treat any specific record id, count, or enum value in
this document as valid for architecture/pattern purposes indefinitely, but re-verify the
*live population* and *live Anthropic/Lusha balances* at execution time. 7 days for the live
figures, effectively unlimited for the code-structure findings (function signatures, node names,
idioms) barring an intervening phase touching the same files.
