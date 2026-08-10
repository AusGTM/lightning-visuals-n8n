# Phase 44: SJ-3 Dispatch Gate, Drain & Cap - Research

**Researched:** 2026-08-10
**Domain:** n8n Cloud workflow builder internals (`scripts/build_cloud_workflows.py`), HubSpot
custom-property schema, write-safety gate architecture
**Confidence:** HIGH on all code-grounded findings below (every claim was read from source this
session); MEDIUM/LOW flagged inline where the finding is about n8n platform behavior not
directly testable offline.

## Summary

This phase adds three behaviours to the existing SJ-3 lane in `build_scheduled_maintenance_cloud`
(`scripts/build_cloud_workflows.py:5809-5827`). All three are additive around code that already
exists and is already tested; none require a new dependency. The two hardest problems are not
"how do I write the gate/drain/cap logic" — the repo already has the exact primitives
(`_writeSafetyAllows`, `_hs_update_set_property`, YAML-config-at-build-time) — the two hardest
problems are (1) **`lv_enrichment_status` is a closed HubSpot enumeration** with six fixed options,
none named for "drained," which puts D-08's "no schema change needed" claim in tension with
DRAIN-02's literal "exactly one key" wording (see Flagged Conflict below), and (2) **the write-safety
overlay/arm system is copied verbatim across three separate files** (`scripts/deploy_n8n_workflows.py`,
`operator-claude-plugin/scripts/n8n_arming.py`, `scripts/verify_live_write_safety.py`'s imports), each
pinned by its own parity test with a hardcoded 5-name set — this is the mechanism WINDOWS.md #2 warns
about, and the safe way through it (matching the codebase's own precedent for
`ALLOW_JUDGE_ESCALATION`/`ALLOW_WEB_RESEARCH`, which already default `true`) is to **not** add D-05's
new authority to that overlay/arm system at all.

**Primary recommendation:** Add the drain's new write authority as a plain new key in
`WRITE_SAFETY_DEFAULTS` (`build_cloud_workflows.py:908-914`) with value `"true"`, gate the drain's
HubSpot write with a small standalone inline check (not a new branch inside `_writeSafetyAllows`,
and not routed through `splice_write_gates`/`_write_gate_js`, both of which hardcode the
`_writeSafetyAllows` name), and deliberately keep it **out of** `_OVERLAY_FLAG_SPEC`
(`deploy_n8n_workflows.py:180-193`), `n8n_arming.OVERLAY_DISABLED_LITERALS`
(`n8n_arming.py:46-52`), and `verify_live_write_safety.CHECKED_CONSTANTS` (derived from the former,
`verify_live_write_safety.py:79`) — exactly how `ALLOW_JUDGE_ESCALATION`/`ALLOW_WEB_RESEARCH` are
already excluded for the identical reason (`deploy_n8n_workflows.py:160-164`, quoted in full below).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GATE-01 | Gate-closed tick dispatches 0, costs 1 execution not 1+N | Q1 finding: `executeWorkflow` "each" mode receives 0 items when its feeder emits `[]`, and the codebase's own documented n8n behavior (`build_cloud_workflows.py:4131-4133`, `:4178-4179`) is that a zero-item feed makes the downstream node not run at all. Returning `[]` from the new gate node is sufficient for the *cost* half of GATE-01 with no IF node needed. |
| GATE-02 | Gate-closed tick reports a distinct, non-error outcome | Q1/Q6 finding: because a 0-item node does not run, "chain stops" also means nothing downstream records the outcome — GATE-02 requires an explicit second output path off the gate node that always emits, independent of dispatch count. |
| GATE-03 | Gate-open tick's dispatch is unchanged (no reorder/swallow) | Q3 finding: `tests/n8n/sjPredicates.test.mjs` is the established pattern for this kind of test — reads the *built* `n8n/wf_scheduled_maintenance_cloud.json` and asserts on node/connection shape, never evaluates jsCode. |
| DRAIN-01 | Declined records get `lv_enrichment_requested` cleared | `_hs_update_set_property` (`build_cloud_workflows.py:5862-5873`) is the exact existing helper, already used by `SJ-1 Set Requested` for the inverse write. |
| DRAIN-02 | Drain write path writes exactly one key | **See Flagged Conflict** — this literal requirement is in tension with D-08/D-13 wanting `lv_enrichment_status` written too. |
| DRAIN-03 | Drained record distinguishable from enriched/hand-cleared | Q7 finding: `lv_enrichment_status` is a closed enum (`config/hubspot_properties.yaml:308-337`) with an unused value, `skipped`, available for this purpose without a property migration — *if* DRAIN-02 permits writing it. |
| CAP-01 | Cap derived from allowance × cadence, not hardcoded | Q5 finding: the builder already reads `config/*.yaml` at import time (`build_cloud_workflows.py:23`, `:6121`) — direct precedent for D-11's new allowance key. |
| CAP-02 | Capped tick logs found vs. dispatched | Q6 finding: no existing n8n-side "found vs dispatched" telemetry pattern exists; `backfill_seed_company_scores.py`'s cap (`scripts/backfill_seed_company_scores.py:85,144,216-221`) is a **refuse-entirely** pattern, not a **truncate-and-continue** pattern — CAP-02 needs the latter, so this precedent only supports the "no silent caps" *spirit*, not the mechanism. |
| CAP-03 | Test fails if shipped schedule's monthly floor exceeds a configured share | No existing test computes this; genuinely new test infrastructure, informed by `_schedule_trigger`'s own documented arithmetic (`build_cloud_workflows.py:5525-5534`). |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-record dispatch permission (gate) | n8n Code node (orchestration) | — | Must run inside the same execution as the search, before the executeWorkflow fan-out — this is n8n's own tier, not HubSpot's. |
| Drain write (`lv_enrichment_requested=false`) | n8n Code/HubSpot node → HubSpot CRM | — | The write itself lands in HubSpot (control-plane property), but the decision of *which* records to drain is computed in n8n from the same tick's gate output. |
| Cap arithmetic (allowance × cadence × share) | Python build script (`build_cloud_workflows.py`) | `config/*.yaml` | Computed once at build time, baked into the Code node as a literal — matches every other `WRITE_SAFETY_DEFAULTS`/`CONFIG_FLAG_DEFAULTS` constant in this builder. Never computed at n8n runtime. |
| Structured outcome visibility | n8n execution data (ephemeral) + HubSpot `lv_enrichment_status` (durable) | — | D-13's own two-places design — this phase does not introduce a new tier, it reuses the two that already exist. |

## Project Constraints (from CLAUDE.md)

- §21 "Safety Gates" (`CLAUDE.md:3024-3068`) is the **original design-doc** naming convention
  (`ALLOW_CANONICAL_WRITES`, `MAX_RECORDS_PER_SCHEDULED_RUN`, etc.) — the *actual implemented*
  gate uses different, evolved names (`ALLOW_HUBSPOT_RECORD_WRITES`,
  `ALLOW_HUBSPOT_REVIEW_WRITES`, `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS`) defined and enforced
  in `_writeSafetyAllows` (`build_cloud_workflows.py:930-947`). CONTEXT.md's pointer to "CLAUDE.md
  §21" is citing the *pattern* (exact-string `"true"` comparison, gate is the caller's job, no
  silent default-allow), not literal flag names — do not search the code for `ALLOW_CANONICAL_WRITES`,
  it does not exist there.
- "Avoid HubSpot workflow custom-code actions... all complex orchestration belongs outside
  HubSpot in n8n" (`CLAUDE.md:60-68`) — consistent with this phase: all three behaviours land in
  the n8n builder, none in a HubSpot-native automation.

## Findings by Research Question

### Q1 — Code node output into `executeWorkflow` "each" mode; does 0 rows cost 0 sub-executions?

`SJ-3 Dispatch To Enrichment` is built by `_execute_workflow_node`
(`build_cloud_workflows.py:5744-5751`), which hardcodes `"mode": "each"` — one sub-execution per
input item, confirming the "1 + N" framing in GATE-01/the roadmap is literally "1 tick + N
per-item sub-executions."

The codebase does not contain a live-tested assertion of "0 items in -> 0 sub-executions," but it
does contain the project's own settled understanding of n8n's zero-item semantics, established
across two prior bug investigations and cited three times:

- `build_cloud_workflows.py:4129-4133` (IF List Expanded): *"Gates on the EVENTS THEMSELVES...
  Zero events therefore can never reach the enrichment chain — which also closes D-22 (zero items
  into a responseNode webhook = no response at all, and a ~100s hang until Cloudflare 524s)."*
- `build_cloud_workflows.py:4178-4179` (HubSpot Search, BUG 23/Phase 17.01): *"zero hits -> zero
  items -> chain stops, execution 22."*
- `build_cloud_workflows.py:4213-4216`: *"same zero-items-on-zero-hits hazard as the sibling
  search above."*

`[CITED: project's own code comments, established via live execution 22]` — a node that receives
zero input items does not run, and nothing downstream of it runs either ("chain stops"). This is
consistent with n8n's documented platform behavior (a node with 0 input items is skipped/grayed
in the execution view) `[ASSUMED: general n8n platform knowledge, not independently reverified
this session]`.

**Consequence for the plan:** if the new SJ-3 gate Code node returns `[]` when every row is
declined, `SJ-3 Build Dispatch Event` and `SJ-3 Dispatch To Enrichment` simply do not run — 0
sub-executions, satisfying GATE-01's cost bound with no IF node required for that half of the
requirement.

**But this creates a second problem for GATE-02.** D-13 requires the tick's own execution data to
carry a structured outcome ("found N, permitted M, declined N−M, capped K") even on a fully
gate-closed tick. If the *only* thing downstream of the gate is the dispatch chain, and that chain
never runs on `[]`, then a fully-closed tick has **no node in its execution data that recorded
anything** — which is precisely the "indistinguishable from failure/nothing to do" outcome
GATE-02 forbids. The plan needs an explicit second path off the gate (or the search/extract
nodes) that runs unconditionally and carries the summary — e.g., a Set/NoOp node fed directly by
the gate's own output (which DOES run, since it receives whatever `SJ-3 Extract Rows` produced,
even if extract rows found 0 or N rows) rather than something fed only through the
dispatch-permitted branch. This is an architectural decision for the plan, not something this
research should preempt — but the "returning `[]` alone is not enough for GATE-02" conclusion is a
hard finding, not a suggestion.

### Q2 — Does `_writeSafetyAllows` need `domain` on SJ-3's search, and does SJ-3's search currently request it?

Read directly (`build_cloud_workflows.py:5817-5824`):

```python
sj3_search = _hs_http_search_node(
    "SJ-3 Search (requested poller)", "company", x, y,
    filter_groups=[[
        {"propertyName": "lv_enrichment_requested", "operator": "EQ", "value": "true"},
        {"propertyName": "lv_enrichment_status", "operator": "NEQ", "value": "running"},
    ]],
    properties_csv="hs_object_id,lv_enrichment_requested,lv_enrichment_status")
```

Confirmed: **no `domain` in this properties list**, unlike SJ-1's search
(`build_cloud_workflows.py:5871-5878`, `properties_csv="hs_object_id,domain,lv_org_type,..."`)
which carries the explicit comment: *"BUG 24: `domain` requested so this lane's write gate can
be satisfied by TEST_RECORD_DOMAINS at all"* — and SJ-2's search
(`build_cloud_workflows.py:5905-5912`) repeats the identical comment.

`_writeSafetyAllows(action, hsObjectId, domain)` (`build_cloud_workflows.py:930-947`) checks
`hsObjectId` against `TEST_RECORD_IDS` OR `domain` against `TEST_RECORD_DOMAINS` — either alone
is sufficient. So a per-record gate keyed only on `TEST_RECORD_IDS` (id-based allowlisting) works
today without a search change, but any armed window scoped by **domain** (e.g. an operator arming
`TEST_RECORD_DOMAINS` rather than a specific set of ids — this is exactly the shape
`operator-claude-plugin/scripts/n8n_arming.py`'s `arm_for_dispatch` supports, taking both
`record_ids` and `record_domains` as independent parameters,
`n8n_arming.py:264`) would be **structurally unable to pass the gate for SJ-3-originated rows**,
because `domain` is never in the row. This exactly mirrors BUG 24, which was found and fixed for
SJ-1/SJ-2/Review Search but never applied to SJ-3 because SJ-3 never wrote anything before this
phase.

**Finding: `domain` must be added to SJ-3's `properties_csv`** for D-01's per-record gate to
behave correctly under a domain-scoped armed window, following the exact precedent at
`build_cloud_workflows.py:5876-5877` (SJ-1) and `:5910-5911` (SJ-2). This is a one-line change to
an existing, already-tested node (`tests/n8n/sjPredicates.test.mjs:64-75` currently pins SJ-3's
search to exactly `hs_object_id,lv_enrichment_requested,lv_enrichment_status` — no test currently
asserts on `properties_csv`'s value directly, only on `filterGroups`, so adding `domain` will not
break that test, but the plan should update/extend it the way `sjPredicates.test.mjs` already
covers SJ-1/SJ-2's `domain`-bearing searches — it currently does not assert on SJ-1/SJ-2's
`properties_csv` either, only on `filterGroups` and terminal-node shape, so there is no existing
regression guard for this property list at all; the plan should decide whether to add one).

### Q3 — How do the existing n8n Code-node tests exercise a built workflow?

Two distinct, established patterns, confirmed by reading three test files in full this session:

1. **Structural assertion on the built JSON** (`tests/n8n/sjPredicates.test.mjs`, all of it read).
   Loads `n8n/wf_scheduled_maintenance_cloud.json` from disk (built artifact, not hand-derived),
   finds nodes by name, and asserts on `node.parameters.jsCode` via `assert.match(..., /regex/)`
   or on `node.parameters.jsonBody` via a small hand-rolled filter-group extractor
   (`sjPredicates.test.mjs:37-58`), and on `wf.connections[...]` for wiring/reachability. It
   **never evaluates the jsCode** — no `eval`, `new Function`, or `vm` anywhere in this file or in
   `reviewLoop.test.mjs`/`reviewDecisionEndpoint.test.mjs` (grepped, zero matches). Example
   assertion style directly reusable for GATE-03: `sjPredicates.test.mjs:64-75` pins the exact
   filter-group shape of a search node; the same style pins the gate node's presence/wiring.

2. **Direct import-and-call of a pure JS module** (`tests/n8n/reviewLoop.test.mjs`, all of it
   read). When the underlying logic is non-trivial (branching, multiple outcomes), it lives as a
   real CommonJS module under `n8n/code/*.js` (e.g. `reviewApply.js`, `mergeCompanies.js`,
   `dedupeSweep.js`, `enrichmentGate.js` — 26 files, `n8n/code/` listing), is `require()`'d
   directly in the test via `createRequire(import.meta.url)`
   (`reviewLoop.test.mjs:14-19`), and is called and asserted on as ordinary JS — full branch
   coverage, no n8n runtime involved. The module is then embedded into the Code node's `jsCode`
   verbatim via the builder's `inline(...)` helper (used throughout `build_cloud_workflows.py`,
   e.g. `ENRICH_APPLY_REVIEW = inline("taxonomy.generated.js", ..., "reviewApply.js") + r"""...n8n
   wrapper..."""`, `build_cloud_workflows.py:5695-5698`). A second, separate structural test then
   confirms the module actually got wired into the built workflow (`reviewLoop.test.mjs:117-153`,
   the "Workflow wiring" section) — this two-layer pattern (pure-JS unit test + built-workflow
   wiring test) is the one to follow for anything with real branching logic.

**`_writeSafetyAllows` itself is NOT a separate `n8n/code/*.js` module** — it's a string constant
assembled inline in Python (`WRITE_SAFETY_GATE_JS`, `build_cloud_workflows.py:927-949`) and tested
only via pattern 1 (regex on the built jsCode: `sjPredicates.test.mjs:170`,
`assert.match(gate.parameters.jsCode, /_writeSafetyAllows/)`). There is no existing offline unit
test that actually *executes* `_writeSafetyAllows`'s branching logic in Node — its correctness is
tested only by the Python-side `WRITE_SAFETY_DEFAULTS` dict tests and by regex presence checks.

**Consequence for the plan:** GATE-03 (gate-open dispatch unchanged) and DRAIN-02/CAP-02 (real
branching logic — permit/decline, cap arithmetic, found-vs-dispatched telemetry) are the kind of
logic this repo's own convention says belongs in a real `n8n/code/*.js` module with a direct-import
test (pattern 2), not just a jsCode regex (pattern 1). GATE-01's "does the dispatch chain still
fire" and the wiring itself are pattern-1 territory (built-JSON structural assertions, following
`sjPredicates.test.mjs` line-for-line).

### Q4 — Mechanism for a new write-safety constant; exact tests that would break

`WRITE_SAFETY_DEFAULTS` is Cloud-write-only and deliberately kept separate from the
parity-guarded `CONFIG_FLAG_DEFAULTS` (`build_cloud_workflows.py:894-914`, comment block quoted
in full: *"SEPARATE from CONFIG_FLAG_DEFAULTS (parity-guarded...) — these are Cloud-write-only..."*).
Both dicts already exist and are read from three independent copies across two packages — this is
the exact mechanism WINDOWS.md #2 references:

1. **`scripts/build_cloud_workflows.py`** — `WRITE_SAFETY_DEFAULTS` (`:908-914`, the source of
   truth) and `WRITE_SAFETY_GATE_JS` (`:927-949`, which bakes **every** key in
   `WRITE_SAFETY_DEFAULTS` as a `const` — `"\n".join(_write_safety_const(k) for k in
   WRITE_SAFETY_DEFAULTS)`, `:928`). Because this blob is embedded verbatim into every gated write
   node (`splice_write_gates`/`_write_gate_js`, `:5738-5807`) and both `ENRICH_DECIDE_CLOUD`/
   `ENRICH_DECIDE_CO_CLOUD`, **any new key added here is automatically declared in every existing
   gate node's jsCode**, whether that gate cares about the new key or not.

2. **`scripts/deploy_n8n_workflows.py`** — `_OVERLAY_FLAG_SPEC` (`:180-193`), a **separately
   hardcoded** 5-entry dict `{name: (disabled_literal, enabled_literal, takes_value)}`,
   deliberately NOT derived from `WRITE_SAFETY_DEFAULTS` by import (comment,
   `:165-170`: *"Deliberately NOT imported from build_cloud_workflows — that module runs
   taxonomy/escalation codegen at import time and writes into n8n/code/; a deploy script must
   never carry that side effect."*). This is the deploy-time arming overlay
   (`ENABLE_BAKED_FLAGS`), used to arm one record without a full rebuild.

   **Directly relevant precedent, quoted in full (`deploy_n8n_workflows.py:160-164`):**
   *"`ALLOW_JUDGE_ESCALATION` and `ALLOW_WEB_RESEARCH` are ALSO excluded on purpose
   (quick-260730-din, quick-260730-fij): both now default to `true` at build time, so the overlay
   — which only ever widens disabled->enabled — has no meaningful entry for either; the
   emergency-off path is editing CONFIG_FLAG_DEFAULTS + rebuild + disarmed redeploy."*
   This is the exact situation D-05's new authority is in: it defaults `true`, so the
   disabled->enabled overlay has nothing to arm.

3. **`operator-claude-plugin/scripts/n8n_arming.py`** — a **third, independently hardcoded copy**,
   `OVERLAY_DISABLED_LITERALS` (`:46-52`) and `WRITE_ENABLING_FLAGS` (`:54-56`), copied verbatim
   from `_OVERLAY_FLAG_SPEC` per the module's own comment (`:25-28`, `:36-38`) because PLUGIN-04
   forbids importing across the client/backend boundary.

4. **`scripts/verify_live_write_safety.py`** — imports `_OVERLAY_FLAG_SPEC` directly (it's a
   backend-side script, no PLUGIN-04 boundary) and derives `CHECKED_CONSTANTS = tuple(
   _OVERLAY_FLAG_SPEC.keys())` (`:79`) and `BOOLEAN_CONSTANTS` (`:87`, everything in
   `CHECKED_CONSTANTS` that isn't an allowlist name). Its `verify()` function's `"disarmed"`
   branch **hardcodes the requirement that every name in `BOOLEAN_CONSTANTS` reads `"false"`**
   (`:214-217`: `if flag in c and c[flag] != "false": reasons.append(...)`) — there is no per-flag
   "safe value" concept; every boolean this script tracks is assumed disabled == `"false"`.

**Tests that assert on the current 5-name set and would need attention (enumerated by reading
each file, not estimated):**

- `tests/test_enabled_build_invariants.py::test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults`
  (`:206-229`) — **strict equality** `assert deploy._OVERLAYABLE_FLAGS == {5 hardcoded names}`
  (`:223-229`). Breaks *only if* the new authority is added to `_OVERLAY_FLAG_SPEC`. Stays green if
  it is not (matching the `ALLOW_JUDGE_ESCALATION`/`ALLOW_WEB_RESEARCH` precedent).
- `operator-claude-plugin/tests/test_control_flag_parity.py::test_the_overlayable_names_match_the_deploy_scripts_table`
  (read directly, `:40-52`) — text-diffs `_OVERLAY_FLAG_SPEC` against `n8n_arming.OVERLAY_DISABLED_LITERALS`.
  Same condition: breaks only if the new authority enters the overlay table on one side and not
  the other.
- `tests/test_write_gate_coverage.py::test_every_write_node_sits_behind_a_write_safety_gate`
  (`:79-106`, parametrized per `wf_*_cloud.json`) — **this one WILL break regardless of the overlay
  decision**, if the drain's write node is built via `_hs_update_set_property` (the precedent
  DECISIONS.md names) and gated by anything other than a jsCode blob containing the literal
  substring `"_writeSafetyAllows"`. The walker (`_all_paths_cross_a_gate`, `:50-64`) treats a node
  as "gating" **only** if `"_writeSafetyAllows" in _js(wf, name)` (`:56`) — a new, differently-named
  guard function (which D-05's own authority requires, since D-06 says the drain must skip the
  `TEST_RECORD_*` allowlist check that `_writeSafetyAllows` always applies) will not match this
  string and the test will report the drain write node as ungated. **This is a real, specific,
  predictable break** — not a maybe. The plan must either (a) deliberately extend this test's
  gate-detection heuristic as a reviewed act, or (b) find a way for the drain's gate check to
  genuinely reuse `_writeSafetyAllows`'s name while still skipping its allowlist branch (harder,
  risks entangling two authorities the decisions explicitly want kept separate).
- `tests/test_write_gate_coverage.py::test_every_cloud_workflow_with_a_write_declares_the_safety_constants`
  and `::test_committed_write_safety_constants_are_all_disabled` (`:109-144`) — both iterate
  `WRITE_SAFETY_DEFAULTS` directly and derive their expected literal *from the dict itself*, not a
  hardcoded `"false"`. Read closely: `disabled = json.dumps(json.dumps(value))[1:-1]` (`:140`) is
  computed **from `WRITE_SAFETY_DEFAULTS[const]`**, so a new key defaulting `"true"` produces
  `disabled == '"true"'` and the test still passes — it is verifying "committed matches declared
  default," not literally "everything is false." **These do not break**, but the second test's
  name (`test_committed_write_safety_constants_are_all_disabled`) becomes misleading once one
  entry is true-by-default; worth a renaming/comment note in the plan, not a functional fix.

**Net conclusion for D-05's mechanism:** the only test in the whole set that is *guaranteed* to
need a real code change (not just staying out of a table) is
`test_write_gate_coverage.py::test_every_write_node_sits_behind_a_write_safety_gate`, because its
gate-detection is a hardcoded string match on `_writeSafetyAllows`, and D-05/D-06 require a
genuinely different, non-allowlist-consulting check.

### Q5 — Does the builder already read `config/*.yaml`, and how do tests read the same file?

Yes, directly confirmed. `build_cloud_workflows.py:23` — `import yaml` — and
`build_cloud_workflows.py:6120-6121`:

```python
_COMPANY_POLICY_FIELDS = tuple(sorted(
    yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["companies"]))
```

`ROOT = Path(__file__).resolve().parent.parent` (`build_cloud_workflows.py:25`). This is a
module-level (build-time) read, used to derive a Python constant baked into the built workflow —
the identical shape D-11 needs for the plan allowance.

The matching test-side pattern, confirmed by reading `tests/test_field_policy_conformance.py:31`,
is byte-identical: `yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["companies"]`
— the test re-derives the same value from the same file rather than importing the builder's
constant, so a drift between "what the builder baked" and "what the config actually says" is
directly visible.

**No existing `config/*.yaml` file is a natural home for a monthly execution-allowance number** —
the current inventory (`column_mapping.yaml`, `escalation_policy.yaml`, `field_policy.yaml`,
`hubspot_properties.yaml`, `icp_scoring.yaml`, `provider_priority.yaml`, `source_registry.yaml`,
`taxonomy.yaml`) is entirely enrichment/scoring config; a new file (e.g.
`config/execution_budget.yaml`) is the more consistent choice than shoehorning it into an
unrelated existing file, but this is a naming choice for the plan, not dictated by any existing
convention either way.

### Q6 — Structured-outcome emission pattern in this codebase

No existing Code node in `build_cloud_workflows.py` emits a distinct summary/telemetry item
alongside a per-row item stream without disturbing the row flow — grepped for
`summary`/`telemetry`/`outcome`/`found.*dispatched` across the builder, no hits beyond
unrelated per-row `gap_flag` fields. `gap_flag` (e.g. `build_cloud_workflows.py:1026,1042`) is the
closest existing convention for a Code node annotating its own decision onto each row (not a
separate summary item), used downstream by IF nodes (`row.gap_flag === true`,
`:1265,1284,1372,2702,2850`) — a workable pattern for a *per-row* "declined/permitted/capped"
annotation, but not for a *tick-level* aggregate.

The CAP-02/"no silent caps" precedent CONTEXT.md cites — `backfill_seed_company_scores.py`'s
25-record guard — was read in full (`:80-85`, `:139-144`, `:197-227`). It is a **refuse-entirely**
pattern: `enforce_sample_cap()` returns a bool, and `main()` prints a `REFUSED:` message and exits
1 if the resolved sample exceeds the ceiling (`:216-221`) — it never truncates and continues. This
differs structurally from what CAP-02 needs (dispatch up to the cap, log the difference, continue
— not refuse the whole tick). The precedent supports the *spirit* ("a cap must never silently do
less work than it looks like it did") but not the *mechanism*; the plan needs new machinery here,
not a reusable function.

### Q7 — `lv_enrichment_status` enum values (definitive)

Read directly from `config/hubspot_properties.yaml:308-337` (companies) — the contacts mirror at
`:603-618`+ carries the identical option set. Verbatim:

```yaml
  - name: lv_enrichment_status
    label: LV Enrichment Status
    type: enumeration
    fieldType: select
    groupName: lv_enrichment
    options:
    - label: Queued
      value: queued
      displayOrder: 0
      hidden: false
    - label: Running
      value: running
      displayOrder: 1
      hidden: false
    - label: Complete
      value: complete
      displayOrder: 2
      hidden: false
    - label: Failed
      value: failed
      displayOrder: 3
      hidden: false
    - label: Needs Review
      value: needs_review
      displayOrder: 4
      hidden: false
    - label: Skipped
      value: skipped
      displayOrder: 5
      hidden: false
```

**This IS a closed enumeration** — six fixed options: `queued`, `running`, `complete`, `failed`,
`needs_review`, `skipped`. HubSpot enumeration properties reject a value not in the options list
(the project's own prior history confirms this cost: Phase 40-06 had to PATCH a fifth option
(`Unscored`) onto `lv_icp_tier` before a new value could ever be written, per STATE.md's Phase
40-06 decision entry). **D-08's claim of "no property migration" is only true if the drain writes
one of these six existing values** — it cannot invent a new string like `"drained"` without first
extending the enum (a live property PATCH, exactly the kind of migration D-08 says this phase does
not need).

Of the six, only two are ever actually **written** anywhere in the current pipeline (grepped
`lv_enrichment_status` across `build_cloud_workflows.py`): `"needs_review"`
(`:2797`) and `"complete"` (`:2802`), both inside `ENRICH_DECIDE_CO_CLOUD`'s outcome-stamping
logic (`:2725` area). `queued`, `running`, `failed`, and **`skipped`** are defined in the schema
but currently **unused** by any writer in this repo. `skipped` is therefore free of any existing
semantic collision and is the best-fit candidate for the drain's provenance stamp, satisfying
"Claude's Discretion... the exact `lv_enrichment_status` value written by the drain" left open in
CONTEXT.md.

Note also: SJ-3's own search filter (`NEQ "running"`, `build_cloud_workflows.py:5822`) means the
drain does not need to change `lv_enrichment_status` for the *poller itself* to stop re-matching a
drained record — clearing `lv_enrichment_requested` alone already removes it from SJ-3's `EQ
"true"` filter. A `lv_enrichment_status` write is purely for DRAIN-03's human/downstream
distinguishability, not for the poller's own re-match logic.

### Flagged Conflict — DRAIN-02 vs. D-08/D-13 (requires planner resolution, not silently redesigned)

**REQUIREMENTS.md, DRAIN-02, verbatim:** *"The drain write path is narrow by construction — it can
write exactly `lv_enrichment_requested=\"false\"` and nothing else, on records it just declined."*

**44-CONTEXT.md, D-07, verbatim:** *"the drain may write only `lv_enrichment_requested`, only the
literal `\"false\"`, only to record ids the gate declined in the same tick, and it stamps
provenance. A test asserts the emitted patch has exactly one key."*

**44-CONTEXT.md, D-08, verbatim:** *"Drain provenance reuses the existing `lv_enrichment_status`
property rather than adding a new one... A drained record is therefore distinguishable from an
enriched one and from a hand-cleared one (DRAIN-03)."*

**44-CONTEXT.md, D-13, verbatim:** *"the gate-closed outcome is observable in two places: a
structured outcome in the tick's execution data..., and the drained records' `lv_enrichment_status`."*

These four statements are not simultaneously satisfiable as literally written. DRAIN-02 and D-07's
own test ("exactly one key") say the drain's HubSpot PATCH body contains only
`lv_enrichment_requested`. D-08 and D-13 say the *same* drain write is what stamps
`lv_enrichment_status` as the DRAIN-03 provenance signal — a second key. If the "exactly one key"
test is taken literally, DRAIN-03 cannot be satisfied through `lv_enrichment_status` at all (the
drain structurally cannot write it), which contradicts D-08's own stated mechanism.

This research did not find a way to reconcile these from the code alone — it is a decision
conflict inside the locked-decisions text itself, not a code fact. Two readings the planner should
choose between explicitly (not decided here):

- **Reading A:** DRAIN-02/D-07's "exactly one key" scopes only the *allowlist-gated, declined-set*
  write (the part write-safety cares about — which records, what value); `lv_enrichment_status` is
  a second, ungated bookkeeping field in the *same* PATCH request, analogous to how other lanes'
  status-patches already bundle a gated data field with adjacent bookkeeping keys
  (`build_cloud_workflows.py:2797-2802`'s `ENRICH_DECIDE_CO_CLOUD` writes `lv_enrichment_status`
  alongside other fields in one patch). The "one key" test would then assert on the *set of
  declined-record ids the write touches*, not literally `Object.keys(patch).length === 1`.
- **Reading B:** Take "exactly one key" literally. `lv_enrichment_status` is written by a
  *separate* mechanism (a second PATCH, or DRAIN-03 is satisfied by *absence* of
  completion evidence — no `last_enriched_at`, no score fields — rather than a new explicit status
  value). D-08's "reuses the existing property" framing would then need to be revisited or dropped.

### Q8 — Deploy/bounce sequencing

Confirmed by reading `scripts/deploy_n8n_workflows.py` directly:

- Two-key gate: `DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true` (`_writes_allowed()`,
  `:222-225`).
- **Activation is explicitly out of scope for this script**: *"Activation (POST .../activate) is
  a separate operator-runbook step, not performed by this script."* (`:25`). There is no
  `deactivate`/`activate`/`bounce` call anywhere in `deploy_n8n_workflows.py` (grepped, zero
  matches for those three tokens beyond the docstring line quoted). The deactivate→PUT→activate
  bounce CONTEXT.md references is therefore a manual operator step outside this script — the plan
  must call it out as a post-deploy runbook action, not something the deploy script itself
  performs.
- **"A content deploy rebakes write-safety to disarmed"** is grounded, not asserted blind: the
  committed `n8n/*.json` artifacts always carry `WRITE_SAFETY_DEFAULTS`'s disabled values (proven
  by `test_write_gate_coverage.py::test_committed_write_safety_constants_are_all_disabled`,
  `:127-144`, which fails the build if a committed literal ever diverges from the declared
  default). `enable_baked_flags()`'s arming overlay (`deploy_n8n_workflows.py:356-…`) is applied
  **per invocation** via the `ENABLE_BAKED_FLAGS` env var at deploy time — it is never persisted
  back into the committed source. So a subsequent plain `deploy_n8n_workflows.py` run (without
  `ENABLE_BAKED_FLAGS` set) necessarily pushes the disarmed committed JSON, overwriting whatever
  live-armed state existed. This confirms CONTEXT.md's warning: **deploying this phase's changes
  while any window is armed (e.g., mid-`scheduled_arm.py` cycle) silently closes that window as a
  side effect of the same PUT** — sequencing must ensure no arm window is open before this phase's
  deploy, and the plan should not assume an armed state survives the deploy needed to ship the
  gate/drain/cap changes.

## Code Examples

Verified patterns from this repo, all read directly this session:

### Existing per-record write-safety gate (reuse verbatim per D-02, for the GATE check only)
```python
# Source: scripts/build_cloud_workflows.py:930-947 — _writeSafetyAllows body
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

### Existing single-property write helper (reuse verbatim per D-07's structural precedent)
```python
# Source: scripts/build_cloud_workflows.py:5862-5873 — _hs_update_set_property, used by
# "SJ-1 Set Requested" to set lv_enrichment_requested="true"; the drain needs the same
# helper with value_literal="false".
def _hs_update_set_property(name, resource, x, y, property_name, value_literal="true"):
    id_key = "contactId" if resource == "contact" else "companyId"
    return {
        "parameters": {"resource": resource, "operation": "update",
                       id_key: "={{ $json.hs_object_id }}",
                       "updateFields": {"customPropertiesUi": {"customPropertiesValues": [
                           {"property": property_name, "value": value_literal},
                       ]}}},
        "id": nid("hu"), "name": name,
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x, y],
    }
```

### Existing config-YAML-at-build-time pattern (reuse for D-11's allowance key)
```python
# Source: scripts/build_cloud_workflows.py:6120-6121
_COMPANY_POLICY_FIELDS = tuple(sorted(
    yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["companies"]))
# Test-side mirror, Source: tests/test_field_policy_conformance.py:31 — identical read,
# never imports the builder's derived constant, so drift is directly visible.
```

### Existing built-workflow structural test pattern (reuse for GATE-03/wiring tests)
```javascript
// Source: tests/n8n/sjPredicates.test.mjs:64-84 (abbreviated)
test("SJ-3: single AND'd group of lv_enrichment_requested=true + lv_enrichment_status!=running", () => {
  const wf = loadWorkflow(); // reads n8n/wf_scheduled_maintenance_cloud.json from disk
  const node = findNode(wf, "SJ-3 Search (requested poller)");
  const groups = filterGroups(node); // regex-extracts filter groups from jsonBody
  assert.equal(groups.length, 1, "SJ-3 predicate is a single AND'd group, not OR'd groups");
});
```

## Common Pitfalls

### Pitfall 1: Adding the new authority to the overlay/arm system by habit
**What goes wrong:** Following D-02's "reuse verbatim" instinct too broadly and adding the new
drain authority to `_OVERLAY_FLAG_SPEC` because that's "where write-safety constants go."
**Why it happens:** Every *other* write-safety constant in this repo is overlayable/armable, so it
looks like the consistent move.
**How to avoid:** The new authority is structurally different — it defaults `true`, so there is
nothing to arm. The codebase already has a name for this shape (`ALLOW_JUDGE_ESCALATION`,
`ALLOW_WEB_RESEARCH`) and an explicit, on-the-record reason both are excluded from the overlay
(`deploy_n8n_workflows.py:160-164`). Follow that precedent.
**Warning signs:** `test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults` or
`test_control_flag_parity.py` failing on a 6th name.

### Pitfall 2: Gating the drain write with `splice_write_gates`/`_write_gate_js`
**What goes wrong:** `_write_gate_js(action)` (`build_cloud_workflows.py:5747-5772`) always emits
`WRITE_SAFETY_GATE_JS + a filter calling _writeSafetyAllows(action, ...)`, and that function
*always* runs the `TEST_RECORD_*` allowlist check (`:941-946`, unconditional after the
action-specific branch) — which D-06 explicitly forbids for the drain.
**Why it happens:** `splice_write_gates` is the one-line, well-tested way every other write node
in this file gets gated, so it's the path of least resistance.
**How to avoid:** Build the drain's gate as its own small standalone check reading only the new
constant, not through `splice_write_gates`.
**Warning signs:** A drained record silently requires `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` to
be non-empty to drain at all — exactly the failure mode D-05/D-06 exist to prevent (an
allowlisted drain clearing only records that were never stuck).

### Pitfall 3: Assuming `test_write_gate_coverage.py` will "just pass" because the write is gated
**What goes wrong:** The drain write node genuinely is behind a real, correct gate — but
`test_write_gate_coverage.py::test_every_write_node_sits_behind_a_write_safety_gate`'s walker only
recognizes gating by searching node jsCode for the literal substring `_writeSafetyAllows`
(`:56`). A correctly-designed, differently-named guard function will be reported as "ungated."
**Why it happens:** The test's gate-detection is a string match, not a semantic check.
**How to avoid:** Treat this test file as something the plan must deliberately, visibly extend
(new marker string or widened detection), not something that will pass by construction.
**Warning signs:** CI red on `tests/test_write_gate_coverage.py` for
`wf_scheduled_maintenance_cloud.json` specifically.

### Pitfall 4: Writing a `lv_enrichment_status` value outside the six enum options
**What goes wrong:** Choosing a self-descriptive string like `"drained"` or `"queue_cleared"` for
the provenance stamp. HubSpot rejects (or the PATCH request 400s on) an enumeration value not in
the property's `options` list.
**Why it happens:** D-08's own language ("reuses the existing property") reads as license to write
any value, when it actually constrains the plan to the six values already defined.
**How to avoid:** Use `skipped` (currently unused anywhere in the pipeline) or otherwise confirm
whatever value is chosen is one of `queued|running|complete|failed|needs_review|skipped`.
**Warning signs:** A live PATCH test failing with a HubSpot validation error on
`lv_enrichment_status`.

### Pitfall 5: Believing "returning `[]` from the gate" alone satisfies GATE-02
**What goes wrong:** GATE-01 (cost) is satisfied by returning `[]` (dispatch chain doesn't run),
but GATE-02 (visible, non-error outcome) is NOT, because nothing downstream of a 0-item node runs
either — so a fully gate-closed tick's execution data would show nothing.
**How to avoid:** The gate node needs an explicit second output path that runs regardless of
dispatch count (see Q1 finding).

## Environment Availability

Not applicable — this phase adds no new external dependency, service, or CLI tool. All work is
inside the existing Python build script, existing n8n Cloud instance, and existing HubSpot
private-app credential, all already provisioned and exercised by the current test suite (2427
pytest / 636 node:test passing per CONTEXT.md's canonical refs — not re-run this session, per the
`<verification_protocol>` this is the planner/executor's job, not research's).

## Package Legitimacy Audit

Not applicable — no new package is introduced by this phase in any ecosystem.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | n8n's `executeWorkflow` "each" mode genuinely produces 0 live sub-executions (not 1 execution with 0 iterations) when its feeder node emits 0 items — inferred from this repo's own documented "zero items -> chain stops" precedent, not independently re-verified against n8n's current platform docs this session. | Q1 / GATE-01 | If wrong, GATE-01's "costs exactly 1, never 1+N" could still be violated even with a correctly-filtering gate; the plan should include a live/logged check of a genuinely gate-closed tick's actual execution count before declaring GATE-01 met, not just trust the code-comment precedent. |
| A2 | `skipped` is the best-fit unused enum value for the drain's provenance stamp. | Q7 / DRAIN-03 | Low risk — grounded directly in a full read of `config/hubspot_properties.yaml` and a full grep of all writers of `lv_enrichment_status`; but this is a recommendation, not a locked decision (CONTEXT.md leaves the exact value to planning). |

## Open Questions

1. **DRAIN-02 vs. D-08/D-13 conflict (see Flagged Conflict above).**
   - What we know: the literal requirement text and the literal decision text describe
     incompatible PATCH shapes.
   - What's unclear: which reading the operator intends.
   - Recommendation: the plan should surface this explicitly to the user/planner before writing
     the DRAIN-02 test, rather than picking silently — a "one key" test that's actually checking
     something narrower than literal `Object.keys().length === 1` needs to say so in its own
     docstring, the same way every other test in this codebase documents what it actually pins.

2. **How does GATE-02's structured outcome actually reach execution data on a fully gate-closed
   tick, given 0-item chains don't run?**
   - What we know: the gate node itself runs (it receives whatever `SJ-3 Extract Rows` produced).
   - What's unclear: the exact node shape that captures the summary regardless of dispatch count —
     a second output branch, a Set/NoOp node fed directly from the gate, or something else.
   - Recommendation: this is a legitimate design decision for the plan, informed by but not
     resolved by this research.

## Sources

### Primary (HIGH confidence — read directly this session)
- `scripts/build_cloud_workflows.py` (multiple regions: `:23-25`, `:835-950`, `:4120-4220`,
  `:5400-5900`, `:5744-5800`, `:6095-6180`, `:6700-6730`)
- `scripts/deploy_n8n_workflows.py` (`:150-370`, `:600-602`)
- `scripts/verify_live_write_safety.py` (full file)
- `operator-claude-plugin/scripts/n8n_arming.py` (`:1-90`, `:180-310`)
- `scripts/backfill_seed_company_scores.py` (`:70-230`)
- `config/hubspot_properties.yaml` (`:300-350`, `:600-620`)
- `config/field_policy.yaml` (`:1-30`)
- `tests/n8n/sjPredicates.test.mjs` (full file)
- `tests/n8n/reviewLoop.test.mjs` (full file)
- `tests/test_write_gate_coverage.py` (full file)
- `tests/test_enabled_build_invariants.py` (`:190-229`)
- `operator-claude-plugin/tests/test_control_flag_parity.py` (`:1-52`)
- `tests/test_field_policy_conformance.py` (`:31`)
- `CLAUDE.md` (`:3024-3068`, §21)
- `.planning/phases/44-sj-3-dispatch-gate-drain-cap/44-CONTEXT.md`, `.planning/REQUIREMENTS.md`,
  `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/WINDOWS.md` (all full-read this
  session)

### Secondary (MEDIUM confidence)
- n8n `executeWorkflow` "each"-mode zero-item behavior — grounded in this repo's own code comments
  (which cite live execution numbers, e.g. "execution 22") rather than n8n's own current published
  docs, which were not fetched this session.

### Tertiary (LOW confidence)
- None used as the basis for any recommendation above without a HIGH/MEDIUM-confidence
  corroborating code citation.

## Metadata

**Confidence breakdown:**
- Write-safety mechanism (Q2, Q4, Q8): HIGH — every claim traced to a specific file:line read
  this session, including the exact tests that would break.
- HubSpot enum / DRAIN-02 conflict (Q7): HIGH on the enum facts; the conflict itself is a fact
  about the decision text, not a code fact, and is presented as a flag, not a resolution.
- n8n platform zero-item behavior (Q1): MEDIUM — grounded in this repo's own settled
  understanding (three independent citations across two bug investigations) but not
  independently re-verified against current n8n documentation this session.
- Test-pattern conventions (Q3): HIGH — read three full test files.

**Research date:** 2026-08-10
**Valid until:** Tied to `scripts/build_cloud_workflows.py`/`scripts/deploy_n8n_workflows.py`/
`operator-claude-plugin/scripts/n8n_arming.py` staying at their current commit — any change to
`WRITE_SAFETY_DEFAULTS`, `_OVERLAY_FLAG_SPEC`, or `lv_enrichment_status`'s enum options
invalidates the relevant section immediately, not on a time basis.
