# Phase 43: Pipeline Scoring Hygiene & Explainability - Research

**Researched:** 2026-08-07
**Domain:** n8n Code-node pure-JS pipeline (HubSpot writer surface) + Python parity/oracle harness + operator-plugin skill (thin HTTP client, no HubSpot credential)
**Confidence:** HIGH — every code-site claim below was read this session (file:line cited, values quoted verbatim); the two live-suite baselines were re-run this session, not copied from STATE.md; the two most important findings are **corrections** to CONTEXT.md's own framing, verified by direct Read against the current working tree.

## Summary

This phase closes four narrow, already-scoped defects. The research below confirms two of CONTEXT.md's framings are **stale relative to the current working tree** and must be corrected before planning, expands the D-07 boolean-writer sweep beyond the two named sites (a live, previously-undocumented exposure on four ICP candidate fields), and resolves PIPE-04's architecture question by direct evidence rather than inference (the plugin has no HubSpot credential — the report cannot be built as plugin-internal code that calls HubSpot directly).

**Primary recommendation:** Treat PIPE-02's `min_confidence` half as **already done** (verify only, do not re-fix); treat PIPE-01/D-07 as covering **six candidate write sites**, not two (`reviewApply.js` clearPatch's second key, plus four ICP boolean candidate fields flowing through `mergeCompanies()`'s untyped pass-through), fixed at two shared coercion points; build PIPE-04's aggregator in repo-root `scripts/` using `src.hubspot_client` (already object-type-generic, no code change needed for a `"deals"` read) and have the plugin skill **shell out via subprocess**, never `import`, to stay inside `operator-claude-plugin/tests/test_no_backend_imports.py`'s ast-based guard.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Boolean-to-string coercion at HubSpot PATCH boundary (PIPE-01) | n8n Code node (pipeline) | — | The write happens in `build_cloud_workflows.py`-generated `jsCode` / `n8n/code/*.js`; HubSpot itself is a dumb string store for booleancheckbox properties |
| Veto-policy hardening (PIPE-02) | n8n Code node (`mergeCompanies.js`) | Python oracle (`config/field_policy.yaml`, uncoupled) | The JS policy object is the actual runtime authority; the Python yaml sibling has no `min_confidence` key at all for these fields and is not read by the pipeline |
| Score breakdown production (PIPE-03) | Python harness (`scripts/run_scoring_parity.py`) | HubSpot (destination property) | `compute_icp_score` is the sole source of the breakdown dict; HubSpot is a write target only, never a compute tier (Phase 40/CONTEXT.md's oracle-only rule) |
| Loss-reason aggregation (PIPE-04) | Python script (repo-root `scripts/`) | Operator-plugin skill (thin invoker) | The plugin has no HubSpot credential (verified below) — it cannot own the query tier; it can only shell out to something that does |

## User Constraints

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Breakdown write is a new opt-in mode on the parity harness (`--write-breakdown`, off by default). Phase 40 D-12's scheduled read-only pass stays genuinely read-only.
- **D-02:** Truncation: drop detail, keep totals. Shed per-component evidence/reason strings first; always retain rubric version, component points, hard vetoes, graduated deductions, and the total; stamp `truncated: true` when shedding occurred. Rejected: bare `json.dumps(...)[:60000]` slice.
- **D-03:** Coverage: the records the harness checks on that invocation only. No portfolio-wide backfill.
- **D-04:** PIPE-04 deliverable is a report built against live truth. Aggregator queries the real Deal API; absent/empty `lv_closed_lost_reason` is stated explicitly with counts, never fabricated. Rejected: creating the Deal property in this phase.
- **D-05:** Report content: rubric-version stamp plus a tier cross-tab — loss reasons cross-tabulated against the lost company's ICP tier/score, stamped with the live rubric version (`lv-icp-v0.1`). Consumption only.
- **D-06:** Surface: an operator-plugin skill. Deliberate override of the milestone's Out-of-Scope fence (plugin changes). Reversibility: costly.
- **D-07:** Scope is every boolean property writer, not just the named flag — covers `lv_enrichment_needs_review`, `lv_icp_needs_review`, and any other boolean-valued HubSpot property write found across `n8n/code/`, `scripts/build_cloud_workflows.py`, and the Python writers, coerced to strings `"true"`/`"false"` at their write sites, following the 36-07 idiom.
- **D-08:** Test form: anchored grep over the generated n8n JSON asserting exactly-string, red-checked against a deliberately broken build, plus a live-gated EQ-filter fixture proving the HubSpot filter actually matches.
- **D-09:** `min_confidence` for veto-class fields in `mergeCompanies.js` is 80, matching Phase 40 D-04's suggestion. CONTEXT.md states "Currently 0" — **research found this framing is stale; see Pitfall 1 below.**
- **D-10:** Proof shape: keep the dead-proof test untouched, add a policy-shape test asserting the policy object itself (non-zero `min_confidence`, coercion present) by inspecting the policy/config, not by driving the path.
- **D-11:** All n8n changes go through `scripts/build_cloud_workflows.py` regeneration — no hand-edits to generated JSON. Deploy stays disarmed; post-build arming grep must read 0; bounce (deactivate→activate) follows any deploy.

### Claude's Discretion
- The exact boolean-writer inventory produced by D-07's sweep and the order fixes land in.
- Breakdown JSON schema details beyond D-02's retained fields.
- Plugin skill name, trigger phrasing, and whether the aggregator lives in `scripts/` with the skill shelling out to it (preferred) or entirely inside the plugin — **research found this is not fully open: the plugin has no HubSpot credential, which functionally forces the repo-root-`scripts/`-plus-shellout shape; see Pitfall 3.**
- Report file naming/location for any committed artifact the skill produces.
- Whether the EQ-filter fixture reuses the disposable-company pattern or an existing test record.

### Deferred Ideas (OUT OF SCOPE)
- Creating `lv_closed_lost_reason` on the Deal object with the CLAUDE.md picklist, and bringing deals under `config/hubspot_properties.yaml` management.
- Portfolio-wide `lv_icp_score_breakdown` backfill.
- Carried from Phases 41/42 (all still backlog): sweep lookback window, sweep crontab versioned path, contact-upload header aliases, enrichment throughput ceiling.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | `lv_enrichment_needs_review` written as STRING "true"/"false" at every writer | Complete writer inventory below (Pitfall 2) — 6 sites found, not 2; single-shared-fix-site analysis for both `reviewApply.js` and the ENRICH_DECIDE_CO_CLOUD/ENRICH_DECIDE_CLOUD coercion loops |
| PIPE-02 | Dormant veto path hardened: real `min_confidence` + string coercion | `min_confidence` is **already 80**, already tested (Pitfall 1) — only the coercion half remains; exact fix-site constraint from D-10 (must be statically greppable, cannot "drive the path") |
| PIPE-03 | `lv_icp_score_breakdown` producer via parity harness `--write-breakdown` | `compute_icp_score`'s exact breakdown shape quoted verbatim; `run_scoring_parity.py`'s zero-existing-CLI-args contract; property type/limit confirmed live-schema-managed |
| PIPE-04 | `lv_closed_lost_reason` consumption report | Deal-object read path needs **zero code change** to `src/hubspot_client.py` (already object-type-generic); plugin has no HubSpot credential (Pitfall 3) — architecture is materially constrained, not fully discretionary; property's live existence is UNVERIFIED (flagged explicitly) |
</phase_requirements>

## Standard Stack

No new external dependencies. This phase is pure modification of existing pure-JS Code-node modules (`n8n/code/*.js`), the Python builder (`scripts/build_cloud_workflows.py`), the existing Python parity harness (`scripts/run_scoring_parity.py`), and one new Python script + one new plugin skill, both built entirely from already-installed packages (`requests`, `pyyaml`, stdlib `json`/`argparse`).

**Installation:** none.

**Version verification:** N/A — no new packages.

## Package Legitimacy Audit

Not applicable — this phase introduces no new external packages in any ecosystem.

## Architecture Patterns

### System Architecture Diagram

```
PIPE-01/02 (write-path hygiene)
  Claude Web Research (HTTP, JSON booleans) ──┐
                                               ▼
  mergeCompanies() candidateRow ──► _gate() ──► canonicalPatch (RAW JS TYPES: bool/string) ──┐
                                                                                              │
  reviewApply()'s clearPatch literal (bool: false) ──────────────────────────────────────────┤
                                                                                              ▼
                              ENRICH_DECIDE_CO_CLOUD / ENRICH_APPLY_REVIEW / REVIEW_BUILD_DECISION
                              properties = {...canonicalPatch, ...clearPatch}
                              [BUG27 loop: joins arrays -> string; NO boolean coercion exists]
                                                                                              │
                                                                                              ▼
                                                    HubSpot Company Update (httpRequest PATCH,
                                                    JSON.stringify verbatim, no further coercion)
                                                                                              │
                                                                                              ▼
                                          HubSpot booleancheckbox property (stores "true"/"false")
                                                                                              │
                                                                                              ▼
                       HubSpot Search API EQ filter {value: "true"} <── (AWAITING_REVIEW_GROUPS,
                                                                          Review Search approved=true)
                                              ^ THIS is the consumer the fix repairs.

PIPE-03 (explainability)
  compute_icp_score(record, patch) ──► ICPScoreResult.breakdown (dict, no "total" key today)
      │
      ▼ (new --write-breakdown flag, opt-in only)
  scripts/run_scoring_parity.py::build_report() loop ──► truncate-shed-detail-first ──►
  patch_record("companies", id, {"lv_icp_score_breakdown": json}) ──► HubSpot textarea property

PIPE-04 (loss-reason consumption)
  HubSpot Deal object (crm/v3/objects/deals/search, closed-lost, lv_closed_lost_reason?)
      │  (hs_primary_associated_company association)
      ▼
  HubSpot Company object (lv_icp_tier, lv_icp_fit_score, lv-icp-v0.1)
      │
      ▼
  NEW repo-root scripts/build_loss_reason_report.py (uses src.hubspot_client — generic,
  no code change needed for object_type="deals")
      │  (subprocess invocation, NEVER a Python `import` — PLUGIN-04 ast guard forbids it)
      ▼
  NEW operator-claude-plugin/skills/<name>/SKILL.md  ──►  docs/reports/YYYY-MM-DD-*.md
```

### Recommended Project Structure

No new directories. Touched files only:
```
n8n/code/reviewApply.js              # PIPE-01 fix site 1 (clearPatch literal)
n8n/code/mergeCompanies.js           # PIPE-02 fix site (coercion, NOT min_confidence — already 80)
scripts/build_cloud_workflows.py     # PIPE-01 fix sites 2-3 (the two BUG27-style loops)
scripts/run_scoring_parity.py        # PIPE-03 (--write-breakdown flag + truncation function)
tests/test_cloud_companies_branch.py # PIPE-01/02 new assertions (existing file, established idiom)
tests/test_scoring_parity.py         # PIPE-03 new assertions (existing file)
scripts/build_loss_reason_report.py  # PIPE-04 NEW — repo-root, uses src.hubspot_client
operator-claude-plugin/skills/<name>/SKILL.md  # PIPE-04 NEW — shells out to the script above
docs/reports/                        # PIPE-04 output convention (existing dir)
```

### Pattern 1: The 36-07 idiom — TWO distinct precedents exist, use the newer one

D-08 names "the 36-07 idiom" but two structurally different test idioms exist in this repo for the exact same class of bug, and the newer one is the closer, more directly reusable template:

**Idiom A (36-07 original, `tests/test_create_payload_identity.py`)** tests the **Python builder source constant** (`import build_cloud_workflows as B; src = B.DECIDE_CLOUD`), not the generated JSON. Four assertions: (1) assignment-target regex `properties\.PROP\s*=` — not a bare substring grep — proves the flag is actually assigned onto the payload variable, not merely mentioned in a comment or a display echo; (2) a **character-index** pin (`src.index(...)`) proving the assignment sits strictly between the `if (action === "create")` and the following `return { json: {`, i.e. inside the guarded block; (3) `src.count(f'properties.{PROP} = "true";') == 1` — exactly-once, guards against a hoisted stamp re-queuing every record on every update; (4) a negative assignment-target assertion for the **unprefixed** spelling, because the prefixed name contains the unprefixed one as a substring so a naive `not in` check passes on broken code. Red-checking here was a **manual, described process step** (36-07-SUMMARY.md: "every new assertion was red-checked individually (moved-above-if, removed entirely, duplicated, and unprefixed-spelling substitution) before being restored") — not an automated red-check artifact in the test file itself.
`[VERIFIED: tests/test_create_payload_identity.py:100-152, .planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-07-SUMMARY.md:107-112]`

**Idiom B (Phase 40, `tests/test_cloud_companies_branch.py::test_decide_company_action_veto_flag_assignment_is_a_quoted_string_literal`)** is the **closer precedent** — same phase family, same PATCH node, fixes the sibling field (`lv_anti_icp_flag`) exactly this way, and it tests the **actual built JSON file** (`n8n/wf_enrichment_cloud.json`, loaded via `_load()` at `tests/test_cloud_companies_branch.py:21-25`), extracting the "Decide Company Action" node's `jsCode`:
```python
code = _decide_company_action_jscode()
assert 'properties.lv_anti_icp_flag = vetoReasons.length > 0 ? "true" : "false";' in code
assert "properties.lv_anti_icp_flag = true;" not in code
assert "properties.lv_anti_icp_flag = false;" not in code
```
`[VERIFIED: tests/test_cloud_companies_branch.py:169-177, quoted verbatim]`
This is the template to replicate for `lv_enrichment_needs_review`/`lv_enrichment_review_approved`: one positive assertion the corrected quoted-string form is present, two negative assertions the bare-boolean form is absent, against the **generated JSON's actual jsCode**, not the Python source. No evidence this specific test was ever "red-checked against a deliberately broken build" as a logged step (unlike 36-07) — its negative assertions ARE the permanent red-check going forward, but the manual once-off verification 36-07 performed should still be done as a plan task step, not assumed inherited.

### Pattern 2: The single-shared-fix-site principle, applied twice

Both PIPE-01 and PIPE-02 have a genuine single shared fix site, confirmed by tracing every consumer:

- **`reviewApply.js`'s `clearPatch` object** (`n8n/code/reviewApply.js:87-93`) is spread, unmodified, into TWO different HubSpot PATCH properties objects: `ENRICH_APPLY_REVIEW`'s `const properties = { ...(result.canonicalPatch || {}), ...(result.clearPatch || {}) };` (`scripts/build_cloud_workflows.py:5500`) AND `buildReviewDecision()`'s approve branch `const properties = { ...canonical, ...applied.clearPatch, [P_PROVENANCE]: provenance.json };` (`n8n/code/reviewDecision.js:297`, itself wrapped by `REVIEW_BUILD_DECISION` at `scripts/build_cloud_workflows.py:6311`). **Fixing the two literal `false` values in `reviewApply.js:89-90` fixes both consumers.** Neither wrapper node has its own coercion loop.
- **`mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY`** (`n8n/code/mergeCompanies.js:34-70`) is the single declared policy every candidate-promotion decision (`_gate()`, `n8n/code/mergeCompanies.js:121-157`) consults. A coercion fix belongs here, not in each of the four calling wrapper nodes that inline this module.

### Anti-Patterns to Avoid
- **Fixing only the two named sites and calling D-07 done.** The candidate-value boolean class (Pitfall 2 below) is real, live-reachable, and undocumented in CONTEXT.md's "known starting points" list.
- **Proving PIPE-02's coercion by calling `mergeCompanies()` with a synthetic veto candidate.** D-10 explicitly forbids "temporarily enabling the path in a fixture" — the existing `test_merge_companies_veto_policy_entries_carry_a_real_min_confidence` (Pitfall 1) proves its property via a static regex over the source text, not by invoking the function. Any coercion fix must be provable the same static way, or D-10 is violated.
- **Assuming the plugin skill can call HubSpot directly.** It has no credential to do so (Pitfall 3).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deal-object HTTP read | A new HubSpot deals client | `src.hubspot_client.get_record("deals", ...)` / `search_records("deals", ...)` | Both functions are already fully generic on `object_type` — no hardcoded `"companies"`/`"contacts"` string anywhere in their URL construction (`src/hubspot_client.py:16-21`, `:119-128`). HubSpot's CRM v3 API uses the identical `/crm/v3/objects/{objectType}/...` shape for every object type. `[VERIFIED: src/hubspot_client.py:16-21,119-128]` |
| Breakdown truncation | A generic JSON-shrinking library | A small hand-written shed-detail-first function (D-02) | The shape is bespoke (shed per-component evidence/reason strings first, keep totals) — no library encodes this priority order, and the function is short enough that a dependency would be net negative |
| Loss-reason report rendering | A reporting/BI library | The existing `docs/reports/` markdown convention (`docs/reports/2026-07-17-dryrun-batch.md` as precedent) | The repo has an established dated-markdown report convention already; a table is a table |

**Key insight:** every piece of "don't-hand-roll" risk in this phase is already solved by existing repo infrastructure — the risk is *not knowing it's already generic/already fixed* (see Pitfalls 1 and 3), not needing new machinery.

## Common Pitfalls

### Pitfall 1: PIPE-02's `min_confidence` is ALREADY 80 — CONTEXT.md's "Currently 0" is stale

**What goes wrong:** A plan that treats D-09 ("min_confidence... Currently 0") at face value will spend a task re-fixing something Phase 40 already fixed, and may accidentally regress the existing test.

**Why it happens:** CONTEXT.md's framing (and the P2 verdict in `PIPELINE-DEFECTS-VALIDATION.md`, written 2026-08-06) describes the code as it stood *before* Phase 40 Plan 03 landed. The current working tree (read this session) shows:
```js
// n8n/code/mergeCompanies.js:60-69
  // 80 (D-04 / P2): these two entries are NOT on a live path after D-01 — the veto is
  // derived directly in ENRICH_DECIDE_CO_CLOUD from already-merged fields, never supplied
  // to mergeCompanies() as a candidate. ...
  lv_anti_icp_flag:        { class: "veto_output",       min_confidence: 80 },
  lv_anti_icp_reason:      { class: "veto_output",       min_confidence: 80 },
```
`[VERIFIED: n8n/code/mergeCompanies.js:60-69, quoted verbatim]`
This matches STATE.md's own decision log: `"[Phase 40-03]: ... DEFAULT_COMPANY_POLICY's veto entries hardened to min_confidence:80 (D-04/P2 closed)."` A permanent regression test for exactly this already exists and passes today:
```python
# tests/test_cloud_companies_branch.py:103-124
def test_merge_companies_veto_policy_entries_carry_a_real_min_confidence():
    ...
    for field in ("lv_anti_icp_flag", "lv_anti_icp_reason"):
        m = re.search(rf'{field}:\s*\{{[^}}]*min_confidence:\s*(-?\d+)', text)
        assert m, f"could not find a min_confidence entry for {field} in mergeCompanies.js"
        assert int(m.group(1)) >= 80, (...)
    assert "min_confidence: 0" not in text, (...)
```
`[VERIFIED: tests/test_cloud_companies_branch.py:103-124, quoted verbatim]`

**How to avoid:** Treat D-09's numeric value as a **verification-only** item ("confirm it's still 80, don't touch it") and scope PIPE-02's real work to the coercion half only (no coercion logic exists anywhere in `mergeCompanies.js` — confirmed by reading the whole 270-line file this session). Extend the *existing* test (line 103) with new assertions for coercion, or add a sibling test in the same file — either satisfies D-10's "extend, don't weaken" instruction, since the min_confidence assertions in the existing test are unaffected either way.

**Warning signs:** A plan task titled "raise min_confidence to 80" or a diff touching lines 68-69 of `mergeCompanies.js` that doesn't also touch the coercion logic — that diff is either redundant or (if it changes the already-correct 80) a regression.

### Pitfall 2: D-07's blast radius is 6 sites, not 2 — 4 previously-undocumented ICP candidate fields carry the identical live defect class

**What goes wrong:** Fixing only `n8n/code/reviewApply.js:89` and `scripts/build_cloud_workflows.py:2788` (the two sites CONTEXT.md names) leaves four other boolean-typed HubSpot properties exposed to the exact same failure mode whenever a research/provider candidate for them is promoted.

**Why it happens:** `lv_produces_content`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` are all `type: bool, fieldType: booleancheckbox` company properties (three confirmed at `config/hubspot_properties.yaml`: `lv_is_hardware_vendor` lines 150-153, `lv_is_gambling_operator` lines 164-167, `lv_sponsorship_reliant` lines 178-181 — `lv_produces_content` itself is **not** present in `config/hubspot_properties.yaml` at all, meaning its live schema type is portal-native/unmanaged by this config and unverified by this session, though CLAUDE.md's design doc and every usage site treats it identically to the other three). None of the four is registered in `n8n/code/hubspotEnums.generated.js`'s `COMPANY_ENUM_PROPERTIES` (confirmed by grep — zero hits for any of the four names). `normalizeEnumValue()` short-circuits for any non-enum-bound property: `if (!isEnumBound(property)) return { ok: true, value, reason: null };` `[VERIFIED: n8n/code/hubspotEnums.js:95-96, quoted verbatim]` — so a candidate's raw type passes through completely unchanged. `mergeCompanies()`'s promote branch then does `canonicalPatch[field] = value;` with **no type coercion of any kind** `[VERIFIED: n8n/code/mergeCompanies.js:240-241, quoted verbatim]`. The upstream source of these values, Claude's web-research JSON response, supplies native JSON booleans per its own documented return-schema contract (`"lv_produces_content": "boolean|null"`), and `n8n/code/webResearch.js` passes them through with only a null-out rule for unevidenced-false, never a type change: `let producesContent = data.lv_produces_content; ... data.lv_produces_content = producesContent;` `[VERIFIED: n8n/code/webResearch.js:39-43, quoted verbatim]`. Finally, the two write sites where `properties = {...merge.canonicalPatch...}` gets finalized before PATCH (`ENRICH_DECIDE_CLOUD` at `scripts/build_cloud_workflows.py:1360` and `ENRICH_DECIDE_CO_CLOUD` at `scripts/build_cloud_workflows.py:2828`) each carry only the BUG-27 array-join loop — confirmed by reading both: `for (const k of Object.keys(properties)) { if (Array.isArray(properties[k])) properties[k] = properties[k].join(";"); }` `[VERIFIED: scripts/build_cloud_workflows.py:2828-2830, quoted verbatim, identical at :1360-1361]` — no boolean branch exists in either.

**Confirmed-already-fixed contrast sites** (do not re-fix, cite as evidence of the correct pattern): `properties.lv_anti_icp_flag = vetoReasons.length > 0 ? "true" : "false";` (`scripts/build_cloud_workflows.py:2783`, D-04/Phase 40); the dedupe-sweep contacts writer `properties: { lv_enrichment_needs_review: "true" }` (`scripts/build_cloud_workflows.py:5480`, already a string); and 36-07's `lv_enrichment_requested = "true"` in `DECIDE_CLOUD` (contacts create branch, already a string).

**Full inventory, per this session's exhaustive grep across `n8n/code/*.js`, `scripts/build_cloud_workflows.py`, and `src/*.py`:**

| Site | Field(s) | Status | Fix mechanism |
|---|---|---|---|
| `n8n/code/reviewApply.js:89-90` | `lv_enrichment_needs_review`, `lv_enrichment_review_approved` | LIVE BUG | Fix the object literal directly — single shared site (Pattern 2) |
| `scripts/build_cloud_workflows.py:2788` | `lv_enrichment_needs_review` | LIVE BUG | `properties.lv_enrichment_needs_review = true;` (companies branch, `ENRICH_DECIDE_CO_CLOUD`) — needs a `"true"`/`"false"` literal or a coercion pass |
| `mergeCompanies()` candidate promotion (`ENRICH_DECIDE_CO_CLOUD` at line 2828, `ENRICH_DECIDE_CLOUD` companies-analog untested for these 4 fields since contacts has no ICP-boolean policy entries — see `DEFAULT_CONTACT_POLICY`, `n8n/code/mergeContacts.js:24-32`, string-only fields) | `lv_produces_content`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` | LIVE BUG (reachable only when a candidate for these fields is actually promoted — happens whenever the research/judge lane's `lv_is_hardware_vendor`/`lv_is_gambling_operator`/`lv_produces_content` survives to a `"promote"` decision) | Extend the BUG-27-style loop at `scripts/build_cloud_workflows.py:2828-2830` to also coerce `typeof properties[k] === "boolean"` → `"true"`/`"false"` string |
| `scripts/build_cloud_workflows.py:2783` | `lv_anti_icp_flag`, `lv_anti_icp_reason` | ALREADY FIXED (Phase 40 D-04) | none — verify only |
| `scripts/build_cloud_workflows.py:5480` | `lv_enrichment_needs_review` (dedupe-sweep, contacts) | ALREADY FIXED | none — verify only |
| `DECIDE_CLOUD` create branch (36-07) | `lv_enrichment_requested` | ALREADY FIXED | none — verify only |
| — | `lv_icp_needs_review` | NO PIPELINE WRITER FOUND | Written only by HubSpot-native workflows (Phase 40's documented Approach C) — nothing to fix in this repo's JS/Python for this specific property name |

`[VERIFIED: exhaustive grep this session: grep -rn "lv_[a-zA-Z_]*\s*[:=]\s*\(true\|false\)\b" across n8n/code/*.js, scripts/build_cloud_workflows.py, src/*.py]`

**How to avoid:** Scope the D-07 sweep task to include the candidate-promotion path, not just the two literal writer sites. The single cleanest fix (consistent with the BUG-27 precedent already in the codebase) is a small boolean-coercion loop alongside the existing array-join loop at both `ENRICH_DECIDE_CLOUD` and `ENRICH_DECIDE_CO_CLOUD`'s properties-finalization points, plus the direct literal fix in `reviewApply.js`.

**Warning signs:** A D-07 sweep whose grep only searches for `lv_enrichment_needs_review`/`lv_icp_needs_review` by name (as CONTEXT.md's own wording could be read to imply) rather than for the general shape "boolean value assigned to any property destined for a HubSpot PATCH."

### Pitfall 3: The plugin has no HubSpot credential — D-06's "entirely inside the plugin" discretion option is not actually available

**What goes wrong:** Planning PIPE-04's aggregator as plugin-internal code that queries HubSpot's Deal API directly will fail at the first live test — there is no HubSpot token anywhere in the plugin's config or credential surface.

**Why it happens:** `operator-claude-plugin/config/operator.local.json` (the plugin's live, gitignored config — confirmed `git check-ignore` this session) holds exactly `n8n_url`, `webhook_secret`, `n8n_api_key`, `stuck_execution_minutes`, `column_mapping_path`, `hubspot_portal_id`. `hubspot_portal_id` is explicitly documented in the example config as "optional — used only to build a clickable record link in the review queue; without it the queue shows the raw record id" `[VERIFIED: operator-claude-plugin/config/operator.local.example.json, line quoted verbatim]` — **not** a credential. Every existing skill's data access goes through the n8n webhook surface, confirmed for `review_queue.py`: `return f"{str(config.get('n8n_url') or '').rstrip('/')}/{QUEUE_PATH}"` `[VERIFIED: operator-claude-plugin/scripts/review_queue.py:75, quoted verbatim]` — never a direct HubSpot API call. Structurally enforced: `operator-claude-plugin/tests/test_no_backend_imports.py` ast-parses every `.py` file under the plugin directory and fails the build if it imports the top-level packages `{"src", "scripts"}` or named modules including `"hubspot_client"`, `"icp_scoring"` `[VERIFIED: operator-claude-plugin/tests/test_no_backend_imports.py:16,20-30, quoted verbatim]` — so even if a HubSpot token existed, the plugin could not legally `import src.hubspot_client` to use it. STATE.md's own memory note confirms this guard is one-directional: `"june_run_arm.py imports operator-claude-plugin/scripts modules directly via sys.path insert -- PLUGIN-04's import guard only forbids plugin-to-backend imports, backend-to-plugin was never scanned"`.

**How to avoid:** Build the aggregator (Deal search, association resolution, tier cross-tab, rubric-version stamp) as a new **repo-root** `scripts/build_loss_reason_report.py`, using `src.hubspot_client` exactly like `scripts/run_scoring_parity.py` does. The plugin skill's SKILL.md then invokes it as a **subprocess** (`python3 scripts/build_loss_reason_report.py`, run from the repo root, or an absolute path if the plugin is installed rather than a repo checkout) — a subprocess call is invisible to `test_no_backend_imports.py`'s `ast`-based import scanner (it only parses `import`/`from` statements), so this stays compliant while giving the report script real `.env`-sourced HubSpot credentials.

**Warning signs:** A plan task that adds `hubspot_private_app_token` (or similar) to `operator-claude-plugin/config/operator.local.example.json`, or a new plugin script that does `import requests` and calls `api.hubapi.com` directly — either is a sign the aggregator has drifted into the wrong tier.

### Pitfall 4: Timing — Phase 41's live arm window may still be open

**What goes wrong:** Deploying Phase 43's regenerated n8n workflows while Phase 41's canary arm window is open silently rebakes write-safety to disarmed, closing the window mid-run without the operator's knowledge.

**Why it happens:** Per STATE.md (read this session): `"Phase 43: CONTEXT.md gathered; planning deliberately held until the canary result lands, because 43 edits mergeCompanies.js and build_cloud_workflows.py — the exact files 41's live run exercises."` and `"THE ARM WINDOW IS OPEN on 66 real records"; scripts/june_run_arm.py --disarm is non-deferrable even if the run is abandoned.` A workflow content deploy is documented elsewhere as always rebaking `ALLOW_HUBSPOT_RECORD_WRITES`/similar constants to their disarmed default (WRITE_SAFETY_DEFAULTS in `scripts/build_cloud_workflows.py`), regardless of intent.
`[VERIFIED: .planning/STATE.md, "Current Position" and "Session" sections, quoted verbatim]`

**How to avoid:** Do not execute Phase 43's deploy step (Task/Wave that runs `scripts/deploy_n8n_workflows.py` or PUTs any built workflow live) until Phase 41 has disarmed (either the canary completes and `scripts/june_run_arm.py --disarm` runs, or the window is otherwise explicitly closed and read-back-confirmed). Offline work (JS edits, builder edits, `pytest`/`node --test` runs, regenerating `n8n/*.json` locally without deploying) is unaffected by this constraint and can proceed regardless of Phase 41's state.

**Warning signs:** Any plan wave that both (a) touches `mergeCompanies.js`/`build_cloud_workflows.py` AND (b) includes a live deploy step, scheduled or ordered before an explicit "confirm Phase 41 disarmed" checkpoint.

### Pitfall 5: The write-behavior of a bare-boolean PATCH to a `booleancheckbox` property is genuinely unknown — the live EQ-filter fixture must establish it empirically

**What goes wrong:** Assuming the live defect's failure mode without proof could lead to under- or over-building the fixture.

**Why it happens:** Static repo analysis proves the *code path* ships a bare JS `true`/`false` in the JSON PATCH body (Pitfall 2), but this session found no evidence anywhere in the repo of what HubSpot's v3 API actually *does* with a bare JSON boolean sent to a `booleancheckbox` property. Three outcomes are all consistent with the evidence gathered:
  1. HubSpot silently coerces the JSON boolean to its internal `"true"`/`"false"` string representation — the current "bug" would then be cosmetic/non-functional for company data, though still worth fixing for consistency and to close the class permanently.
  2. HubSpot stores something the EQ string filter cannot match — the suspected bug, matching the exact mechanism 36-07 fixed for `lv_enrichment_requested`.
  3. HubSpot's v3 validation rejects a non-string value for `booleancheckbox` outright with a 400 — in which case `_hs_http_patch_node`'s documented `on_error=None` hard-fail behavior `[VERIFIED: scripts/build_cloud_workflows.py:5626-5629, "a WRITE node must fail its execution on a rejected PATCH"]` means every affected write would already be failing loudly in n8n execution history, not silently succeeding-but-unfilterable.

**How to avoid:** This is exactly what D-08's live-gated EQ-filter fixture must resolve, not assume. Use the `disposable_company` context manager (`tests/scoring_fixtures.py:85-103`, gated by `RUN_LIVE_PARITY=true`, same portal-assertion discipline as the rest of the parity suite) to: (a) PATCH the property with the pre-fix code path's actual output shape (a bare boolean, via a raw `patch_record` call bypassing the fixed n8n code, to reproduce outcome 1/2/3 directly against the real API) and read back what HubSpot actually stored; (b) separately, after the fix, PATCH with the corrected string and run `search_records("companies", [{"propertyName": "lv_enrichment_needs_review", "operator": "EQ", "value": "true"}], ...)` — the exact filter shape used in `AWAITING_REVIEW_GROUPS` (`scripts/build_cloud_workflows.py:5239-5240`) — asserting the disposable's id appears in results.

**Warning signs:** A fixture that only tests the JS coercion logic in isolation (offline) and never actually calls HubSpot's search API with the EQ filter — that would not discharge D-08's explicit "prove the HubSpot filter actually matches" requirement.

## Code Examples

### PIPE-03: `compute_icp_score`'s exact breakdown shape (verbatim)

```python
# src/icp_scoring.py:49-54 (initial shape) + :58,68,73,77 (components) + :82 (deduction) + :99 (hard_vetoes reassignment)
breakdown = {
    "version": version,
    "components": [],
    "hard_vetoes": [],
    "graduated_deductions": []
}
# ... four appends, identical shape each time:
breakdown["components"].append({"signal": "org_type", "value": org_type, "points": org_points})
breakdown["components"].append({"signal": "produces_content", "value": produces_content, "points": content_points})
breakdown["components"].append({"signal": "geography", "value": region, "points": geo_points})
breakdown["components"].append({"signal": "revenue_band", "value": revenue_band, "points": revenue_points})
# graduated_deductions entries carry NO "value" key (asymmetric with components):
breakdown["graduated_deductions"].append({"signal": "gambling_operator", "points": deduction})
# hard_vetoes is REASSIGNED (not appended) to a flat list of REASON STRINGS, not dicts:
breakdown["hard_vetoes"] = anti_reasons  # e.g. ["Non-ANZ geography", "Hardware/AV/LED vendor, ..."]
```
`[VERIFIED: src/icp_scoring.py:49-54,58,68,73,77,82,99, quoted verbatim]`

**Design implication for D-02's truncation function:** there is **no `"total"` key in `breakdown` today** — the score total lives only on the sibling `ICPScoreResult.score` field (`src/schemas.py:56`), never inside the dict itself. A truncation/serialization function that must "always retain... the total" per D-02 needs to either add a `"total"` key when serializing (pulling `expected.score` from the same `ICPScoreResult` the breakdown came from) or the property write will be missing the one number a human glancing at the JSON needs most. This is a genuine gap in the current shape, not something already handled.

### PIPE-03: `run_scoring_parity.py`'s exact current CLI contract — zero existing flags

```python
# scripts/run_scoring_parity.py:262-264 (main(), full body of arg handling)
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)
    ...
```
`[VERIFIED: scripts/run_scoring_parity.py:262-264, quoted verbatim]`
`--write-breakdown` (D-01) would be the **first** custom flag this script has ever had. `build_report(sample_ids, fetch_fn=fetch_for_parity)` (`scripts/run_scoring_parity.py:155`) is the loop where `expected = expected_for(props)` (`:171`) already computes the full `ICPScoreResult` including `.breakdown` per company, inside the same loop that would need the new conditional write — no restructuring needed, only a new branch. The script currently imports zero write functions from `src.hubspot_client` (`fetch_for_parity` only calls `get_record`, and the module-level docstring states "GET and search calls only — this script never creates, patches, or deletes a company"), confirming D-12's read-only guarantee is real today and that adding `patch_record` must be strictly conditional on the new flag to preserve it.
`[VERIFIED: scripts/run_scoring_parity.py:1-14 module docstring, :155,171, quoted/paraphrased with citation]`

### PIPE-02: the existing policy-shape test to extend (do not touch its passing min_confidence assertions)

```python
# tests/test_cloud_companies_branch.py:103-124, already passing today
def test_merge_companies_veto_policy_entries_carry_a_real_min_confidence():
    text = (ROOT / "n8n" / "code" / "mergeCompanies.js").read_text()
    import re
    for field in ("lv_anti_icp_flag", "lv_anti_icp_reason"):
        m = re.search(rf'{field}:\s*\{{[^}}]*min_confidence:\s*(-?\d+)', text)
        assert m, f"could not find a min_confidence entry for {field} in mergeCompanies.js"
        assert int(m.group(1)) >= 80, (...)
    assert "min_confidence: 0" not in text, (...)
```
`[VERIFIED: tests/test_cloud_companies_branch.py:103-124, quoted verbatim]`
A coercion-presence assertion added to this test (or a sibling in the same file) must, per D-10, inspect the **source text statically** (e.g., regex for a coercion helper call or ternary near the veto-field promotion path) — not call `mergeCompanies()` with a synthetic candidate, which is exactly the "driving the path" D-10 forbids.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `min_confidence: 0` for `lv_anti_icp_flag`/`lv_anti_icp_reason` | `min_confidence: 80` | Phase 40 Plan 03 (D-04) | PIPE-02's stated defect is half-closed already; only coercion remains |
| Plugin same-version reinstall destroyed `operator.local.json`; marketplace clone never auto-refreshed | Both traps fixed as of plugin `v0.7.0` (current: `v0.11.1`) — settings live durably at `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`, survive reinstall and version upgrade automatically | `operator-claude-plugin` v0.7.0 | The install-trap warning in CONTEXT.md's code_context and in this user's global memory notes is **stale** for this plugin's current version — the marketplace-clone-never-auto-fetches trap is real and current (still requires the manual `git fetch --depth=1` + `reset --hard FETCH_HEAD` step, `[VERIFIED: operator-claude-plugin/CHANGELOG.md:615-644]`), but the destructive-reinstall trap is not |

**Deprecated/outdated:**
- The `PIPELINE-DEFECTS-VALIDATION.md` P2 finding ("min_confidence: 0", written 2026-08-06) — superseded by Phase 40 D-04, same day or the day after. Still an accurate description of P4 (boolean-vs-string), which remains open.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lv_closed_lost_reason` actually exists as a live property on the Deal object in portal 22617666 | Environment Availability / PIPE-04 | If it does not exist, `get_record`'s documented no-op-for-unknown-property behavior means the aggregator reads it as simply absent (same code path as "exists but empty") — D-04's report framing already covers this outcome, but the report's language ("0% filled" vs "property not created") should differ, and this phase cannot tell which is true without a live read, which was not performed this session (no credentials available) |
| A2 | HubSpot's native default deal property `closed_lost_reason` (unprefixed, single-line text, distinct from the custom `lv_closed_lost_reason`) exists in this portal and is populated by reps closing deals through the standard UI | PIPE-04's data reality | Sourced from a general HubSpot Knowledge Base web search (`[CITED: HubSpot Community/Knowledge Base search results]`), not this portal's actual schema — could differ if this portal customized or removed the default property |
| A3 | The plugin's outcome for a bare-boolean PATCH against a `booleancheckbox` property (silent coercion / silent filter-mismatch / hard 400) is unknown | Pitfall 5 | If it turns out to be outcome 3 (hard 400), the "live bug" framing changes from "silent filter miss" to "write already failing loudly" — changes the urgency/severity framing but not the fix itself |
| A4 | `lv_produces_content`'s live HubSpot fieldType is `booleancheckbox` like its three sibling ICP flags | Pitfall 2 | It is absent from `config/hubspot_properties.yaml` entirely (unlike the other three), so this session could not confirm its type via the managed config; every code site treats it identically to the other three (boolean comparisons throughout `judge.js`, `webResearch.js`), which is strong circumstantial evidence, but not a direct schema read |

**If this table is empty:** N/A — see above.

## Open Questions

1. **Does `lv_closed_lost_reason` exist live on any Deal in portal 22617666?**
   - What we know: it appears in zero repo code/config (confirmed by exhaustive grep this session); CLAUDE.md documents it as a *proposed* picklist with suggested values; PROJECT.md states "0% filled," which itself presupposes the property exists but has no confirmed live source in this session.
   - What's unclear: whether "0% filled" in PROJECT.md was measured against a live API read or is itself an assumption carried forward from CLAUDE.md's design doc.
   - Recommendation: make a live read (`get_record("deals", <any real closed-lost deal id>, ["lv_closed_lost_reason", "closed_lost_reason"])` or a `crm/v3/properties/deals` schema GET) the **first task** of whichever plan implements PIPE-04, before writing any aggregation logic — this determines whether the report's primary message is "0 of N deals have this filled" or "this property does not exist in this portal."

2. **What association property actually links a closed-lost Deal to its Company in this portal?**
   - What we know: `hs_primary_associated_company` is named in CONTEXT.md as what "the analysis used" — but this session found no code or config in this repo that reads or writes that property name; it is a standard default HubSpot deal property in general, but its exact behavior (single vs. potentially-empty when a deal has multiple associated companies) was not verified live.
   - What's unclear: whether every closed-lost deal in this portal reliably carries this property, or whether some deals need the full Associations v4 API (`crm/v4/objects/deals/{id}/associations/companies`) instead.
   - Recommendation: probe both paths on a handful of real closed-lost deal ids before committing the aggregator's join logic to one or the other.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv` (Python) | All pytest work, `run_scoring_parity.py`, new `build_loss_reason_report.py` | ✓ | confirmed live this session (`.venv/bin/python -m pytest -q` ran clean) | — |
| Node.js | `node --test tests/n8n/*.test.mjs` | ✓ | confirmed live this session (636/636 pass) | — |
| `HUBSPOT_PRIVATE_APP_TOKEN` | Any live/`RUN_LIVE_PARITY=true` work (D-08's fixture, PIPE-04's live read) | ✗ this session (`.env` is Read/Bash permission-blocked per repo convention) | — | Operator runs live-gated steps themselves via the documented `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); ..."` invocation pattern already used by `run_scoring_parity.py`'s own docstring |
| n8n Cloud deploy access | D-11's regeneration + bounce step | Unknown this session — gated by Pitfall 4 (Phase 41 arm-window state) regardless of access | — | Do not deploy until Phase 41 disarms; offline builder/test work is unaffected |

**Missing dependencies with no fallback:** none — every live-gated step already has an established operator-run pattern in this repo.

**Missing dependencies with fallback:** HubSpot credentials (operator runs live steps; this research could not directly verify A1/A2/A3 above as a result — flagged explicitly, not guessed).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, `.venv/bin/python -m pytest`) + Node's built-in `node --test` (no jest/mocha) |
| Config file | none — this repo has no `pytest.ini`/`pyproject.toml` test config (confirmed by `tests/test_scoring_parity.py:44-46`'s own comment: "this repo has no pytest config and every existing gated script... already uses env-var gating, not markers") |
| Quick run command | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py tests/test_scoring_parity.py -q` (targeted) |
| Full suite command | `.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs` + `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Every boolean writer emits `"true"`/`"false"` strings (6-site inventory, Pitfall 2) | unit (offline, anchored grep over generated JSON, Pattern 1 Idiom B) | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py -q` | ✅ file exists, new test functions needed |
| PIPE-01 | HubSpot EQ filter actually matches post-fix | live (gated `RUN_LIVE_PARITY=true`) | `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` (or a new sibling test module using `tests/scoring_fixtures.py`'s `disposable_company`) | ❌ Wave 0 — new live test function |
| PIPE-02 | `min_confidence` stays ≥80 (verify only) | unit, ALREADY EXISTS AND PASSES | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py::test_merge_companies_veto_policy_entries_carry_a_real_min_confidence -q` | ✅ no new work |
| PIPE-02 | Coercion present, provable statically (D-10) | unit (new, source-text regex, no path-driving) | same file, new test function | ❌ Wave 0 |
| PIPE-02 | Dead-path proof stays untouched and passing (D-10) | unit, ALREADY EXISTS | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py::test_company_canonical_patch_never_contains_a_derived_icp_output_field -q` | ✅ no new work, must remain green |
| PIPE-03 | `--write-breakdown` writes truncated, valid-JSON breakdown with total | unit (offline, `build_report` with a stubbed `fetch_fn`) + live (gated) | `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` | ✅ file exists, new offline + live test functions needed |
| PIPE-03 | Read-only default path unaffected (D-01's D-12 guarantee) | unit — assert `patch_record`/write functions are never called when the flag is absent | new test | ❌ Wave 0 |
| PIPE-04 | Report over live truth, empty-dataset-safe (D-04) | unit (offline, stubbed Deal/Company fetch returning zero rows) | new `tests/test_loss_reason_report.py` or plugin-local test | ❌ Wave 0 — new file, new module |
| PIPE-04 | Plugin skill never imports backend code (PLUGIN-04) | unit, ALREADY EXISTS as a repo-wide guard, automatically covers any new plugin file | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_no_backend_imports.py -q` | ✅ no new work, automatically enforces the subprocess-not-import constraint |

### Sampling Rate
- **Per task commit:** targeted file-scoped pytest run for the file(s) touched (e.g. `tests/test_cloud_companies_branch.py -q`)
- **Per wave merge:** full offline suite (`.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs` + plugin suite) — baselines below
- **Phase gate:** full suite green above baseline before `/gsd-verify-work`; arming grep 0; no live deploy until Phase 41 disarmed (Pitfall 4)

**Measured baselines (this session, live-run, not copied from STATE.md):**
- `.venv/bin/python -m pytest -q` → **2362 passed, 118 skipped**
- `node --test tests/n8n/*.test.mjs` → **636 passed, 0 failed**
- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → **1284 passed, 5 skipped**
- `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0** for all 8 generated workflow files

### Wave 0 Gaps
- [ ] New offline test(s) in `tests/test_cloud_companies_branch.py` — PIPE-01's 4 candidate-field coercion sites + `reviewApply.js` clearPatch fix, in the Pattern 1 Idiom B shape
- [ ] New live-gated test(s) (`RUN_LIVE_PARITY=true`, `tests/scoring_fixtures.py`'s `disposable_company`) proving the EQ filter matches post-fix — Pitfall 5's three-way uncertainty must be resolved here
- [ ] New offline test in `tests/test_cloud_companies_branch.py` (or sibling) for PIPE-02's coercion-presence, static/source-text only per D-10
- [ ] New offline + live test(s) in `tests/test_scoring_parity.py` for `--write-breakdown` (valid-JSON-under-truncation, total present, read-only-by-default guard)
- [ ] New `scripts/build_loss_reason_report.py` + a matching offline test file — must work correctly over an empty dataset (D-04's explicit requirement, not an edge case)
- [ ] New plugin skill directory under `operator-claude-plugin/skills/` — `test_no_backend_imports.py` already covers it with zero new setup

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface — this phase touches existing HubSpot private-app-token and n8n-webhook-secret paths only, unchanged |
| V3 Session Management | no | N/A |
| V4 Access Control | yes | The write-safety gate pattern (`ALLOW_HUBSPOT_RECORD_WRITES`/`WRITE_SAFETY_GATE_JS`, unchanged by this phase) and the plugin's PLUGIN-04 import guard (already enforced, Pitfall 3) |
| V5 Input Validation | yes | The boolean/type-coercion fixes ARE input-validation-at-the-boundary work — this phase's core content |
| V6 Cryptography | no | No secrets/crypto touched — `operator.local.json`'s existing gitignore + 0600-permission durable-storage convention (already established, unchanged) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Silent write that never reaches its intended reader (boolean-vs-string EQ-filter mismatch) | Tampering (of intent, not data) / Repudiation (the write "succeeded" but nothing observable changed) | The exact fix this phase makes: type-correct writes at the PATCH boundary, proven live against the real filter, not just offline |
| Plugin credential scope creep (a future skill adding a direct HubSpot token to the plugin) | Elevation of Privilege | `test_no_backend_imports.py`'s ast guard (already in place) + this research's explicit Pitfall 3 finding — a plan must not widen the plugin's credential surface for PIPE-04 |
| Live deploy silently closing an unrelated armed window (Phase 41) | Denial of Service (of the operator's own in-progress canary) | Pitfall 4's explicit ordering constraint |

## Sources

### Primary (HIGH confidence — read directly this session)
- `n8n/code/reviewApply.js`, `n8n/code/mergeCompanies.js`, `n8n/code/reviewDecision.js`, `n8n/code/webResearch.js`, `n8n/code/hubspotEnums.js`, `n8n/code/mergeContacts.js`, `n8n/code/judge.js` (partial) — full read, this session
- `scripts/build_cloud_workflows.py` — targeted reads around lines 1290-1420, 2665-2900, 5220-5540, 5920-5990, 6270-6360; full-file grep for boolean-writer inventory
- `scripts/run_scoring_parity.py` — full read
- `scripts/hubspot_client.py` [sic — `src/hubspot_client.py`] — full read
- `src/icp_scoring.py`, `src/schemas.py` (partial) — full read
- `config/hubspot_properties.yaml`, `config/field_policy.yaml`, `config/icp_scoring.yaml` — targeted reads
- `tests/test_cloud_companies_branch.py`, `tests/test_create_payload_identity.py`, `tests/test_scoring_parity.py`, `tests/scoring_fixtures.py`, `operator-claude-plugin/tests/test_no_backend_imports.py` — full/targeted reads
- `operator-claude-plugin/.claude-plugin/plugin.json`, `operator-claude-plugin/CHANGELOG.md` (release-checklist section), `operator-claude-plugin/config/operator.local.example.json`, `operator-claude-plugin/skills/backend-status/SKILL.md`, `operator-claude-plugin/skills/review-triage/SKILL.md`, `operator-claude-plugin/scripts/review_queue.py` — targeted reads
- `.planning/phases/40-scoring-engine-remediation-notes/PIPELINE-DEFECTS-VALIDATION.md` — full read
- `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-07-SUMMARY.md` — full read
- `.planning/STATE.md`, `.planning/REQUIREMENTS.md` — full/targeted reads
- `.planning/phases/43-pipeline-scoring-hygiene-explainability/43-CONTEXT.md`, `43-DISCUSSION-LOG.md` — full read
- Live command execution this session: `.venv/bin/python -m pytest -q`, `node --test tests/n8n/*.test.mjs`, `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`, `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json`, `git check-ignore -v operator-claude-plugin/config/operator.local.json`

### Secondary (MEDIUM confidence)
- [HubSpot Knowledge Base — default deal properties](https://knowledge.hubspot.com/properties/hubspots-default-deal-properties) — used only to establish that a native `closed_lost_reason` single-line-text property is a HubSpot default, distinct from the custom `lv_closed_lost_reason`; not verified against this portal's actual live schema (Assumption A2)

### Tertiary (LOW confidence)
- None used unlabeled — every claim below MEDIUM confidence is flagged in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, entirely a modification of existing verified code
- Architecture: HIGH — every write-path claim traced end-to-end with file:line citations and live test-run confirmation; the two corrections to CONTEXT.md (Pitfalls 1 and 3) are the highest-confidence findings in this document, each independently confirmed by a passing test or a structural guard already in the repo
- Pitfalls: HIGH for Pitfalls 1-4 (all directly verified); MEDIUM for Pitfall 5 (correctly identifies the uncertainty but cannot resolve it without live credentials — this is honest, not a gap in research diligence)
- PIPE-04 data reality: LOW-MEDIUM — the property's live existence (A1) and the association property's live behavior (Open Question 2) are genuinely unknown without HubSpot API access, which this session did not have

**Research date:** 2026-08-07
**Valid until:** Short — 7 days for the "min_confidence already 80" and "plugin traps already fixed" findings specifically (both are facts about the current working tree / current plugin version that will go stale the moment either changes again); 30 days for the general architecture patterns
