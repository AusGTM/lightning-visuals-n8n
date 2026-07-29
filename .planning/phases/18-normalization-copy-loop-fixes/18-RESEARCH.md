# Phase 18: Normalization & Copy-Loop Fixes - Research

**Researched:** 2026-07-29
**Domain:** Pure-JS n8n Code-node data normalization / non-clobber merge wrapper logic (no live calls)
**Confidence:** HIGH — every claim below is a direct file:line read of this repo, not external research

## Summary

All three fixes are small, mechanical, and fully diagnosable from the codebase already — no
external library, framework, or API research is needed for this phase. This is a "read the exact
code, make the smallest correct edit, prove it with a compiled-node-body test" phase.

**NORM-01** lives entirely in `n8n/code/normalizeProviders.js`'s `zoominfoCandidates()` (lines
296-304): when ZoomInfo returns `naicsCodes` as live-shape objects (`{id, name}`), the code takes
`naicsCodes[0].id` (a bare numeric string like `"71"`) as the `industry` field's
`normalizedValue`, discarding the already-present, human-readable `naicsCodes[0].name`
(`"Arts, Entertainment, and Recreation"`) and the free-text `primaryIndustry` fallback. That
numeric string then wins the cross-provider "waterfall" scorer (`scoreEnrichment.js`) purely on
the ZoomInfo source-trust constant (0.85 vs Apollo's 0.75) whenever accuracy/recency/agreement
tie — which they structurally do for `industry`, since neither provider gets a per-field
accuracy grade (both hardcoded to `0.6`) and cross-provider text never agrees. The minimal,
root-cause fix is to stop ever emitting a bare-numeric-code string as the `industry`
`normalizedValue` — prefer the NAICS `.name` text (already in the same API response), falling
back to `primaryIndustry`/`mainIndustry` text, never the raw code. This single change satisfies
both roadmap criteria (1: never a numeric code; 2: never wins purely on source-trust, because
there is no numeric code left to win with).

**COPY-01** and **COPY-02** are both literal single-field omissions from two field-name arrays
that already do exactly this kind of copy for every other field: `ENRICH_MERGE_CO`'s
`researchData` loop (`scripts/build_cloud_workflows.py:2312-2313`) is missing
`"lv_sponsorship_reliant"`; `ENRICH_MERGE`'s candidate loop (`scripts/build_cloud_workflows.py:
960-965`) is missing a `persona_group` -> `lv_persona_group` block mirroring the adjacent
`linkedin_url` -> `lv_linkedin_url` block immediately above it. **Neither field is currently ever
produced by any live provider mapper or the Claude web-research prompt** — `lv_sponsorship_reliant`
is absent from the companies research prompt's `required_fields`/return schema, and
`persona_group` is absent from every provider mapper in `normalizeProviders.js` and from the
contacts research prompt (jobtitle/seniority only). This means the fix genuinely stops the
property from being "permanently empty" only in the sense that the copy path now EXISTS; making
either field ever receive a real live value is a separate, out-of-fence question the plan should
flag rather than silently also solve (see Open Questions).

**Primary recommendation:** Fix NORM-01 with a small shared industry-value helper in
`normalizeProviders.js` (used by both `zoominfoCandidates` and, defensively, `lushaCandidates`,
which has the identical latent hazard). Fix COPY-01/COPY-02 by literally copying the adjacent
working pattern (add one array entry; add one four-line block) and prove each with a
compiled-node-body test using the exact harness precedent from Phase 16.3
(`tests/n8n/mergeCompanyStaleTimestamp.test.mjs`). Expect to re-baseline
`tests/fixtures/companies_jscode_frozen.json`'s `"Merge Company"` entry for COPY-01 only —
`"Merge Winners"` (contacts) and `"Normalize + Score Company"` (NORM-01) are NOT byte-identity
pinned anywhere in the test suite.

## User Constraints

No CONTEXT.md exists for this phase (not run through `/gsd-discuss-phase`). Proceed from
ROADMAP.md's Phase 18 section (ratified success criteria) and REQUIREMENTS.md (NORM-01/COPY-01/
COPY-02), both quoted in full below as the binding scope.

### Phase 18 Success Criteria (ROADMAP.md, verbatim)

1. A numeric provider industry code (ZoomInfo's `"71"`) never survives normalization unchanged —
   reproduced from execution 19's real conflict (Apollo's `"media production"` vs ZoomInfo's
   `"71"`) with a red-before-green test.
2. That same numeric code never wins the waterfall over provider text by confidence/priority
   ordering alone — the fix is proven against the same execution-19 shape, not just a synthetic
   case.
3. `lv_sponsorship_reliant` is copied from its candidate source (`build_cloud_workflows.py`
   `ENRICH_MERGE_CO` researchData loop) into the companies merge call — a test proves the property
   populates from a real candidate instead of staying empty.
4. `persona_group`/`lv_persona_group` is copied from its candidate source (`ENRICH_MERGE` winners
   loop) into the contacts merge call — a test proves the property populates from a real candidate
   instead of staying empty.
5. The offline suite (baseline — see Environment Availability below for the ACTUAL current count)
   is green with zero regressions, and the workflow builder is deterministic (rebuild twice, no
   diff).

### Requirements (REQUIREMENTS.md, verbatim)

- **NORM-01**: A numeric provider industry code (ZoomInfo's `"71"`) never survives normalization
  unchanged and never wins the waterfall over provider text (Apollo's `"media production"` lost to
  `"71"` in execution 19).
- **COPY-01**: `lv_sponsorship_reliant` is copied from its candidate source (`build_cloud_workflows.py`
  ENRICH_MERGE_CO researchData loop) into the companies merge call — the property stops being
  permanently empty.
- **COPY-02**: `persona_group`/`lv_persona_group` is copied from its candidate source (ENRICH_MERGE
  winners loop) into the contacts merge call — the property stops being permanently empty.

### Discretion (no CONTEXT.md — planner/discuss-phase should confirm)

Not locked by any prior decision. Flagged for planner judgement / a possible `/gsd-discuss-phase`
follow-up:

- Whether to ALSO extend the Claude web-research prompt schemas so `lv_sponsorship_reliant` and
  `persona_group` can ever receive a REAL live value (currently neither field has any producer at
  all — see Open Questions). ROADMAP's success criteria only require the copy-loop wiring, not the
  producer.
- Whether to apply the NORM-01 fix defensively to `lushaCandidates()` too (same numeric-object
  hazard, never observed live, no fixture proves it either way).

### Deferred (out of scope, do not touch)

- HubSpot-side `lv_icp_fit_score`/`lv_icp_tier` formula (still `1+1` placeholder) — Approach C,
  explicitly downstream.
- `lv_org_type` text->enumeration type change — one-way door, deliberately not performed.
- `lv_country_region_normalized` field-policy gap — flagged, not resolved.
- `src/merge_policy.py:279-287` unconditional cache-write — Python harness lane only, its own
  decision.
- Phase 19's `VERIFY-01` (six `/gsd-verify-work` re-runs) — not this phase.

## Project Constraints (from CLAUDE.md)

The repo-root `CLAUDE.md` is the full HubSpot/n8n system spec; most of it (property schemas,
ICP scoring rubric, phased rollout) predates and sits above Milestone 4's debt-cleanup scope. The
directives actually load-bearing for Phase 18's edits:

- **§17.2 "Non-Clobber Merge Algorithm" promotion rules** — a candidate only promotes when it
  "passes validation" and meets its field's confidence threshold; this phase must not weaken any
  existing gate to make a field populate (e.g. must not lower `lv_sponsorship_reliant`'s or
  `lv_persona_group`'s `min_confidence`/class to force a value through — both already have a
  correct `system_owned` policy, only the copy-loop wiring is missing).
- **§21 "Safety Gates"** — `ALLOW_CANONICAL_WRITES` / write-gate discipline is unrelated to this
  phase's actual runtime effect (the fix changes what CAN reach `canonicalPatch`, not whether a
  write gate is bypassed) — no safety-gate config should be touched.
- **§26.2 "Web research failures" / skip-not-retry** — `webResearch.js`'s existing "never throw,
  demote to unmatched" contract must be preserved; the NORM-01 fix and both copy-loop fixes are
  pure data-shape edits and must not introduce a new throw path into any Code node (this repo's
  established `continueRegularOutput` convention would surface it as a broken item, not a
  visible failure — see Common Pitfalls precedent bugs of this exact class).
- **General "Don't Hand-Roll" spirit (§9, §17)** — governance/field-policy classes already exist
  for both target fields; do not introduce a parallel/ad-hoc promotion path.

No CLAUDE.md directive conflicts with any planned fix in this phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Provider-response -> candidate normalization (industry NAICS handling) | n8n Code node (`normalizeProviders.js`) | — | Pure JS, no HubSpot/API call; runs inside the "Normalize + Score Company" node body |
| Cross-provider best-of-breed scoring (waterfall) | n8n Code node (`scoreEnrichment.js`) | — | Consumes normalized candidates only; NORM-01 fix upstream removes the bad input, no change needed here |
| Non-clobber merge / field-policy gate | n8n Code node (`mergeCompanies.js` / `mergeContacts.js`) | — | Frozen pure functions; COPY-01/COPY-02 do NOT touch these — they touch the wrapper code around them |
| Merge-call wrapper (candidate field selection) | `scripts/build_cloud_workflows.py` (Python, generates JS) | n8n Code node (compiled output) | This is where COPY-01/COPY-02 actually live — Python string templates that emit the "Merge Company"/"Merge Winners" node bodies |
| Build artifact regeneration | Build script + committed JSON | — | Any wrapper edit requires `python scripts/build_cloud_workflows.py` re-run + commit of `n8n/wf_enrichment_cloud.json` / `wf_enrichment_local_live.json` |

No browser/frontend/database tier involvement — this phase is 100% backend orchestration-layer
JS/Python.

## Standard Stack

No new dependencies. This phase edits existing pure-JS modules and a Python code-generator only.

### Core (existing, unchanged versions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js `node:test` | built-in | Existing JS unit/row-flow test runner (`node --test tests/n8n/*.test.mjs`) | Already the project convention; zero new deps |
| pytest | already pinned in repo | Existing Python test runner | Already the project convention |

**Installation:** None — no new packages for this phase.

**Version verification:** N/A — no new packages.

## Package Legitimacy Audit

Not applicable — this phase installs zero external packages.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Compiled-node-body "does the wrapper actually copy field X" proof | A new test harness / new mocking framework | The existing `new Function(...)` harness pattern from `tests/n8n/mergeCompanyStaleTimestamp.test.mjs` / `tests/n8n/researchChainRowFlow.test.mjs` / `tests/n8n/contactResearchChainRowFlow.test.mjs` | Already proven, already reads the REAL committed `n8n/wf_enrichment_cloud.json` jsCode, zero new infra |
| "Which text to prefer for industry" | A new taxonomy/vocabulary table | The NAICS record's own `.name` field (already present in every live `naicsCodes` entry) and the existing `primaryIndustry`/`mainIndustry` fallback already read elsewhere in the same function | Root-cause fix using data already in the payload — no new mapping table to maintain |
| "Copy field X from candidate to merge call" | A generic/config-driven copy-loop refactor | Literally copy the adjacent working line for `linkedin_url`/other array entries | The two loops are 4-8 lines each; refactoring them into something generic is unrequested scope for a 1-line-per-field fix |

**Key insight:** every fix in this phase is "add one array element" or "swap which already-present
field is read" — resist the urge to refactor either loop into something more general; that is
strictly more surface area for a phase whose whole selling point is "provable without any live
call" via a tiny diff.

## NORM-01 — Root Cause, Exact Location, and Fix Shape

### Exact location

`n8n/code/normalizeProviders.js`, `zoominfoCandidates()`, lines 296-304 (companies branch):

```js
// Live GTM naicsCodes are OBJECTS ({id,name}, most-general first); the flat fixtures
// are bare code strings. String(obj) would have staged "[object Object]" as industry.
const naics0 = (raw.naicsCodes || [])[0];
const naics = naics0 && typeof naics0 === "object" ? naics0.id : naics0;
// primaryIndustry is an array in the live response (["Hospitality", "Sports Teams ..."]).
const pi = Array.isArray(raw.primaryIndustry) ? raw.primaryIndustry[0] : raw.primaryIndustry;
_push(out, "industry", src, naics || pi, naics ? String(naics) : _norm(pi), 0.6, recency);
```

`naicsCodes[0]` is the MOST GENERAL (top-level, 2-digit) NAICS sector code per the file's own
comment — e.g. `"71"` = "Arts, Entertainment, and Recreation". The live-recorded fixture
`tests/fixtures/enrichment/zoominfo_live_company.json` (Racing NSW, real GTM response) proves the
SAME object also carries `"name":"Arts, Entertainment, and Recreation"` right next to `"id":"71"`
— the human-readable text is already in the payload and is simply discarded in favor of the code.

### Why the code wins the waterfall (mechanism, `scoreEnrichment.js`)

`scoreCandidates()` computes `score = wA·A + wR·R + wG·G + wT·T` per candidate. For `industry`:
- **A (accuracy)**: both Apollo and ZoomInfo push `industry` at a flat, ungraded `0.6`
  (`normalizeProviders.js:224` and `:304`) — always tied.
- **R (recency)**: with no differentiating `recencyDate`, both fall to the neutral `0.5` default
  — usually tied.
- **G (agreement)**: a numeric code vs a text string can never `_eq()` a competitor's text — always
  `0` for both, since they never agree with each other, only tied.
- **T (source trust)**: `DEFAULT_TRUST = { zoominfo: 0.85, lusha: 0.8, apollo: 0.75 }`
  (`scoreEnrichment.js:21`) — ZoomInfo's constant is structurally 0.10 higher than Apollo's, and
  with A/R/G tied, T alone decides `_beats()`'s primary `score` comparison, then its own explicit
  tie-break also re-checks trust (`scoreEnrichment.js:115-120`).

So ZoomInfo wins ANY `industry` disagreement today purely on the static per-source trust constant
— never on the actual quality of the value. This is confirmed, not inferred: `.planning/debug/
bug-17-lusha-company-400.md`'s "Related observation" section documents the exact live outcome
(ZoomInfo `"71"` beat Apollo `"media production"`).

### Recommended minimal fix

Add a tiny shared helper (used by both provider mappers, closing the SAME latent hazard in
`lushaCandidates()` too — see below) that never returns a bare numeric string as an industry
value:

```js
// Prefer human-readable industry text over a raw NAICS code; a numeric code alone is
// never a valid `industry` text value (NORM-01).
function _industryText(naicsEntry, textFallback) {
  if (naicsEntry && typeof naicsEntry === "object" && naicsEntry.name) {
    return { raw: naicsEntry.name, key: _norm(naicsEntry.name) };
  }
  const fallback = Array.isArray(textFallback) ? textFallback[0] : textFallback;
  if (fallback) return { raw: fallback, key: _norm(fallback) };
  // A bare numeric/string NAICS code with no name and no text fallback: still push the
  // code as `value` for audit, but the field is a numeric code — do not stage it as a
  // trustworthy industry TEXT candidate at all (skip pushing rather than fabricate text).
  return null;
}
```

Then in `zoominfoCandidates()`, replace the industry `_push` call with the helper's result
(pushing nothing when it returns `null` so the numeric code never becomes a candidate at all —
this satisfies both criterion 1, since no numeric value ever reaches `normalizedValue`, and
criterion 2, since a field with zero ZoomInfo candidates cannot win any waterfall comparison by
trust alone). Apply the identical fix to `lushaCandidates()`'s `industry` push
(lines 187-188), which has the SAME `naics ? String(naics) : _norm(co.mainIndustry)` shape and
would silently produce `"[object Object]"` (not merely a numeric code) if Lusha ever returns
naicsCodes as `{id,name}` objects — no live fixture proves this either way, so treat it as a
"same-class defensive fix," not a new discovered live bug.

**This is a JS-only fix.** Research question 6 (does the Python lane share this hazard) is
answered NO: `src/normalizer.py` / `src/providers.py` / `config/field_policy.yaml` have an
`industry` field-policy ENTRY but no Python code ever computes an `industry` candidate value or
runs a waterfall scorer — the Milestone-1 Python MVP's mock-provider pipeline never modeled this
data shape. `grep -n "industry" src/*.py` returns zero hits outside `classifier_haiku.py`/
`web_research.py`'s read-only property list. No parity test is needed; do not add one.

### Reproducing the execution-19 shape for the red test

No committed fixture captures Apollo's actual "media production" live response (`.planning/debug/
bug-17-lusha-company-400.md` records the value narratively, not as JSON). The closest real shape:

- **ZoomInfo side**: use the ALREADY-COMMITTED, real, live-recorded
  `tests/fixtures/enrichment/zoominfo_live_company.json` (Racing NSW) as-is — its `naicsCodes[0]`
  is exactly `{"id":"71","name":"Arts, Entertainment, and Recreation"}`, the real execution-19
  shape.
- **Apollo side**: no live fixture exists. Construct a minimal Apollo raw-shape object using the
  documented live value (`organization.industry: "media production"`, per the bug ticket) in the
  same shape `apolloCandidates()` already reads (`(raw.person && raw.person.organization) ||
  raw.organization || raw.org || raw`) — e.g. `{ organization: { industry: "media production" } }`.
  This is real, previously-observed production data; it was simply never fixture-ized. Flag this
  construction inline in the test comment (mirrors this repo's existing convention of citing the
  live-observed source, e.g. `zoominfo_live_company.json`'s header comments).

### Existing test that will need updating (not just a new one)

`tests/n8n/enrichment.test.mjs:350-354` currently PINS the buggy value as expected:

```js
test("toCandidates: ZoomInfo live naicsCodes are objects, not code strings", () => {
  // String({id,name}) would have staged "[object Object]" as the industry.
  const c = toCandidates("zoominfo", zoomLiveCo, "companies");
  assert.equal(find(c, "industry", "zoominfo").normalizedValue, "71");
});
```

Its actual INTENT (per the comment) is "object-shape naics doesn't stage `[object Object]`," not
"the numeric code is correct" — so update this assertion's expected value to match the fix
(e.g. `"arts, entertainment, and recreation"` if the helper pushes a candidate, or assert ZERO
zoominfo industry candidates for this fixture if the helper decides to skip since `.name` IS
present — the helper above always finds `.name` for this exact fixture, so expect the humanized
text, not an absence). This existing test is NOT itself the required "red-before-green" test — it
is a collateral update the fix will break unless changed in the same commit.

## COPY-01 — `lv_sponsorship_reliant` (Companies)

### Exact location

`scripts/build_cloud_workflows.py`, inside `ENRICH_MERGE_CO` (the companies "Merge Company" node
body factory), lines 2311-2319:

```js
const researchData = {};
for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
                 "lv_is_hardware_vendor", "lv_is_gambling_operator"]) {
  const v = rc.data && rc.data[f];
  // tri-state null (TS-2 coercion) / blank -> skip, so mergeCompanies' own _isBlank
  // check has nothing to write; an evidenced false is NOT blank and flows through.
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
  researchData[f] = v;
}
```

**Fix:** add `"lv_sponsorship_reliant"` to that array. Nothing else in the loop needs to change —
the same tri-state-null / blank-skip logic already applies uniformly to every field in the array.

### Field policy is already correct — no config change needed

`n8n/code/mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY.lv_sponsorship_reliant` is already
`{ class: "system_owned", min_confidence: 70 }` (line 43) — no `require_evidence_url` gate, so it
will promote on confidence alone once it reaches the merge call. `config/field_policy.yaml` and
`config/provider_priority.yaml` already declare it too. This is purely a wrapper-loop omission,
confirmed by three independent Phase-15 sources (`15-01-PLAN.md:155`, `15-01-SUMMARY.md:255`,
`STATE.md` Blockers/Concerns "two latent copy-loop bugs").

### The candidate source does not currently exist upstream — flag, don't silently also fix

`rc.data.lv_sponsorship_reliant` will be `undefined` for every real research response TODAY: the
companies research prompt's `required_fields` and JSON return-schema
(`scripts/build_cloud_workflows.py` `COMPANIES_TARGET.research_payload_body_js` /
`research_system_prompt_fn_js`, lines ~1832-1854) list only `lv_org_type`, `lv_produces_content`,
`lv_content_type`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` — never
`lv_sponsorship_reliant`. `validateResearchOutput()` (`n8n/code/webResearch.js`) DOES spread
`raw.data` through untouched for any key it doesn't specifically validate, so an LLM that
spontaneously includes `lv_sponsorship_reliant` in its JSON (not requested, not guaranteed) would
still flow through — but there is no reliable production path that ever asks for it. **The
roadmap's success criterion 3 only requires the copy-loop wiring** ("a test proves the property
populates from a real candidate instead of staying empty") — the test can and should construct a
`research_candidate.data.lv_sponsorship_reliant` value directly (this is exactly how the existing
precedent test `mergeCompanyStaleTimestamp.test.mjs` constructs its `research_candidate` fixture,
line 69-75) without needing the prompt to actually request it live. Flag the prompt-schema gap as
an Open Question for the planner rather than silently expanding scope to fix it in the same phase.

### This node IS frozen — plan for a bounded re-baseline

`"Merge Company"` is one of the 7 `FROZEN_NODE_NAMES` in `tests/test_companies_factory_frozen.py`,
pinned byte-identical against `tests/fixtures/companies_jscode_frozen.json` (both `cloud` and
`local_live` variants). Editing `ENRICH_MERGE_CO` WILL break this guard by design — this is
IDENTICAL to Phase 16.3's situation (`mergeCompanyStaleTimestamp.test.mjs`'s own docstring: "The
fixture ... is re-baselined ONLY by an explicit, reviewed act — never as a routine 'make the test
pass' step"). Phase 16.3's exact procedure (from `STATE.md` Phase 16.3-01 entry):

1. Capture the PRE-fix compiled node body as a permanent, write-once "red evidence" fixture
   (mirror `tests/fixtures/merge_company_prefix_jscode.json`'s pattern — a NEW file, e.g.
   `tests/fixtures/merge_company_norm_copy_prefix_jscode.json`, or reuse/extend the existing one if
   its purpose generalizes cleanly).
2. Make the source edit.
3. Rebuild (`python scripts/build_cloud_workflows.py`), confirm EXACTLY the expected node(s)
   differ (Phase 16.3 checked "14 {variant,node} pairs, exactly 2 differ — both `Merge Company`").
   For this phase, expect `"Merge Company"` to differ (COPY-01); `"Normalize + Score Company"` is
   NOT in the frozen list so its NORM-01 diff needs no re-baseline there.
4. Re-baseline `tests/fixtures/companies_jscode_frozen.json`'s `"Merge Company"` entries (cloud +
   local_live) as its OWN isolated commit, with the diff inspected and bounded before writing.

## COPY-02 — `persona_group`/`lv_persona_group` (Contacts)

### Exact location

`scripts/build_cloud_workflows.py`, inside `ENRICH_MERGE` (the contacts "Merge Winners" node body
factory), lines 959-965 — the EXACT sibling pattern already exists for `linkedin_url` immediately
below the array:

```js
const candidate = {};
for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority"]) {
  if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
}
if (winners.linkedin_url != null && String(winners.linkedin_url).trim() !== "") {
  candidate.lv_linkedin_url = winners.linkedin_url;
}
```

**Fix:** add a fourth block mirroring the `linkedin_url` one exactly:

```js
if (winners.persona_group != null && String(winners.persona_group).trim() !== "") {
  candidate.lv_persona_group = winners.persona_group;
}
```

`n8n/code/mergeContacts.js`'s `DEFAULT_CONTACT_POLICY.lv_persona_group` is already
`{ class: "system_owned", min_confidence: 75 }` (line 31) — no evidence gate, so it promotes on
confidence alone. `config/field_policy.yaml` / `config/provider_priority.yaml` already declare it
(PN-1 rename already landed Phase 15). Purely a wrapper-loop omission, same three-source
confirmation as COPY-01 (`15-01-SUMMARY.md:255-256`, `RESEARCH.md:499` of Phase 15,
`STATE.md` Blockers/Concerns).

### CRITICAL: must not write a bare quoted `"persona_group"` string literal

`tests/test_architecture_guard.py::test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key`
(line 234-247) asserts `scripts/build_cloud_workflows.py` contains **zero** occurrences of the
literal quoted strings `"linkedin_url"` or `"persona_group"` anywhere in the file (regex
`r'"(linkedin_url|persona_group)"'`). Property ACCESS (`winners.persona_group`,
`candidate.lv_persona_group = ...`) is unquoted attribute syntax and does NOT match this regex —
confirmed by the fact that the existing, currently-passing `linkedin_url` block above uses the
exact same unquoted-property-access style. **Write the fix using dot-property access exactly like
the `linkedin_url` block, never as a `for (const f of [..., "persona_group"])` array-string
entry** (unlike the `lv_org_type` etc. arrays elsewhere, which are for HubSpot-native field names —
`persona_group` is explicitly NOT one, per PN-1). This guard test would immediately fail-red on a
naive `for (const f of [...]) candidate[f] = winners[f]`-style implementation that used a quoted
`"persona_group"` array entry — use the `if (winners.x != null ...) candidate.lv_x = winners.x;`
form instead.

### The candidate source does not currently exist upstream — flag, don't silently also fix

`winners.persona_group` will be `undefined` for every real webhook row TODAY: NO provider mapper
in `normalizeProviders.js` (`lushaCandidates`/`apolloCandidates`/`zoominfoCandidates`) ever emits a
`persona_group` field, and the contacts research prompt (`CONTACTS_TARGET.research_payload_body_js`,
`scripts/build_cloud_workflows.py` ~line 1950) only ever researches `jobtitle`/`seniority` — never
persona_group. This is a pure "declared-but-never-produced" field, exactly as `15-01-SUMMARY.md`
and `RESEARCH.md:499` (Phase 15) describe it. As with COPY-01, the red/green test should construct
a `scored.winners.persona_group` value directly in the test fixture (this is the "candidate
source" the wrapper loop reads — a plain JS object key, not necessarily traceable to a live
provider). Flag "no producer exists" as an Open Question rather than expanding scope to add one.

### This node is NOT frozen — simpler to land than COPY-01

`"Merge Winners"` does not appear in `tests/test_companies_factory_frozen.py`'s
`FROZEN_NODE_NAMES` (that list is companies-only) and no other test in the suite pins its exact
jsCode text byte-for-byte (confirmed: `grep` for `"Merge Winners"` across `tests/*.py` and
`tests/n8n/*.mjs` returns only topology/reachability/row-flow assertions, e.g.
`test_cloud_contacts_branch.py`'s `assert "Merge Winners" in reachable`, never a jsCode string
compare). No fixture re-baseline is required for this fix — only the standard rebuild +
`git diff --quiet n8n/` determinism check.

## Architecture Patterns

### System Architecture Diagram (data flow through the touched nodes only)

```
Webhook row (company or contact)
        |
        v
[Provider HTTP calls: Lusha / Apollo / ZoomInfo]  (unchanged this phase)
        |
        v
"Normalize + Score (Company)"  <- normalizeProviders.js: toCandidates()   [NORM-01 lands here]
   (industry candidate no longer a bare numeric code)
        |
        v
"Normalize + Score (Company)"  <- scoreEnrichment.js: scoreCandidates()  (UNCHANGED —
   the fix upstream removes the bad input; no scoring-logic edit needed)
        |
        v
[optional: Research Trigger Gate -> Build Research Request -> HTTP -> Validate Research Output]
   (unchanged this phase — rc.data may or may not carry lv_sponsorship_reliant / persona_group,
   depending on the Open Question resolution)
        |
        v
"Merge Company" / "Merge Winners"  <- build_cloud_workflows.py wrapper   [COPY-01 / COPY-02 land here]
   (candidate-field-selection loop now includes lv_sponsorship_reliant / lv_persona_group)
        |
        v
mergeCompanies() / mergeContacts()  (frozen pure functions — UNCHANGED)
        |
        v
canonicalPatch -> Decide (Company) Action -> HubSpot PATCH (dry-run echo or gated live write)
```

### Recommended Project Structure (files touched, no new files needed for source)

```
n8n/code/normalizeProviders.js       # NORM-01: industry-text helper, applied in zoominfoCandidates
                                      # (+ defensively in lushaCandidates)
scripts/build_cloud_workflows.py     # COPY-01: ENRICH_MERGE_CO researchData loop (+1 array entry)
                                      # COPY-02: ENRICH_MERGE candidate loop (+1 if-block, dot access)
n8n/wf_enrichment_cloud.json         # regenerated (not hand-edited) after every source change
n8n/wf_enrichment_local_live.json    # regenerated (not hand-edited) after every source change
tests/n8n/enrichment.test.mjs        # UPDATE the existing pinned "71" assertion (collateral)
tests/n8n/<new file or extend existing>   # NORM-01 red-before-green test (waterfall-level)
tests/n8n/mergeCompanyStaleTimestamp.test.mjs-style new test  # COPY-01 compiled-body red/green
tests/n8n/contactResearchChainRowFlow.test.mjs-style new test # COPY-02 compiled-body red/green
tests/fixtures/companies_jscode_frozen.json   # RE-BASELINE "Merge Company" entries (COPY-01 only)
tests/fixtures/<new prefix fixture>.json      # write-once PRE-fix snapshot for the COPY-01 re-baseline
```

### Pattern: Compiled-node-body differential test (the load-bearing pattern for this whole phase)

**What:** Execute the ACTUAL jsCode string that ships inside the committed workflow JSON (not the
pure `mergeCompanies()`/`mergeContacts()` function in isolation) via `new Function(...)`, feeding
it a realistic `$input.all()` row, and assert on the returned `merge` object.

**When to use:** Any time the fix lives in the `build_cloud_workflows.py` WRAPPER code around a
frozen pure module (COPY-01, COPY-02) — a pure-function-level unit test would not catch a wrapper
bug, since the wrapper is what's broken, not `mergeCompanies()`/`mergeContacts()` themselves.

**Example (adapt directly from the Phase 16.3 precedent):**
```js
// Source: tests/n8n/mergeCompanyStaleTimestamp.test.mjs (existing, in this repo)
function runMergeCompany(jsCode, row) {
  const $input = { all: () => [{ json: row }], get item() { return { json: row }; } };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, row, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}
```

### Anti-Patterns to Avoid

- **Testing only the pure function, not the wrapper:** `mergeCompanies.test.mjs` /
  `mergeContacts.test.mjs` already prove the pure functions correctly promote any field with a
  matching policy entry — that is NOT what's broken. The bug is that the WRAPPER never builds a
  `candidate`/`researchData` object containing the field in the first place. A red test that calls
  `mergeCompanies()` directly with a hand-built `{lv_sponsorship_reliant: true}` candidate would
  pass on both the PRE-fix and POST-fix code and prove nothing about this bug.
- **Fixing NORM-01 by hardcoding `"71"` as a special case:** the correct fix generalizes to any
  NAICS code, not just the one observed in execution 19 — a hardcoded string comparison would be
  a symptom patch, not a root-cause fix, and would not survive the next numeric code ZoomInfo
  returns for a different company.
- **Silently also wiring the research prompt to request `lv_sponsorship_reliant`/`persona_group`:**
  out of the roadmap's stated success criteria; flag as an Open Question instead (see below) —
  expanding scope here also means touching MORE frozen/pinned surface (the research prompt string
  and `required_fields` array) than the phase's stated fence covers.

## Common Pitfalls

### Pitfall 1: Editing a frozen node body without re-baselining in its own commit
**What goes wrong:** `tests/test_companies_factory_frozen.py` fails immediately and confusingly
after the COPY-01 edit if the fixture isn't updated in the same change.
**Why it happens:** `ENRICH_MERGE_CO` produces the `"Merge Company"` node, one of 7 pinned nodes.
**How to avoid:** Follow the Phase 16.3 procedure exactly (capture PRE-fix body as a permanent
fixture -> make the edit -> rebuild -> confirm ONLY the expected node(s) differ -> re-baseline in
an isolated, reviewed commit).
**Warning signs:** `test_companies_cloud_jscode_is_byte_identical_to_frozen_fixture` /
`_local_live_` failing with a diff confined to `"Merge Company"`.

### Pitfall 2: Forgetting to regenerate the committed workflow JSON
**What goes wrong:** `test_committed_wf_enrichment_cloud_json_is_current` /
`_local_live_json_is_current` fail — the committed artifact is stale vs. a fresh build.
**Why it happens:** Editing `scripts/build_cloud_workflows.py` only changes the SOURCE of the
generator; `n8n/wf_enrichment_cloud.json` and `n8n/wf_enrichment_local_live.json` are checked-in
build OUTPUTS that must be regenerated and committed.
**How to avoid:** Always run `python scripts/build_cloud_workflows.py` after any source edit, then
`git diff --stat n8n/` to confirm the expected files changed, then run it a SECOND time and confirm
`git diff --quiet n8n/` (zero diff) for the determinism criterion.
**Warning signs:** Any `test_*_is_current` test failing.

### Pitfall 3: Writing the persona_group copy as a quoted array-string entry
**What goes wrong:** `test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key`
fails.
**Why it happens:** The natural-looking refactor — adding `"persona_group"` to the existing
`for (const f of ["email", "mobilephone", ...])` array — introduces a literal quoted
`"persona_group"` string, which this architecture guard specifically forbids (PN-1 rename
discipline).
**How to avoid:** Use the unquoted dot-property-access `if`-block form, copied verbatim from the
existing `linkedin_url` block's style.
**Warning signs:** `test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key`
failing with `bare quoted canonical field key(s) found: ['persona_group']`.

### Pitfall 4: Treating the existing `enrichment.test.mjs:353` "71" assertion as passing evidence
**What goes wrong:** Assuming the offline suite is currently "green" on this exact scenario means
nothing needs fixing, or conversely believing the NORM-01 fix is done once that one assertion is
updated.
**Why it happens:** That test currently PINS the bug's output as correct (its actual purpose was
proving the naicsCodes-object-shape parse doesn't crash into `"[object Object]"`, not endorsing
the numeric code) — it will need its expected value changed as a matter of course, in the SAME
commit as the fix, and is not itself suffient proof that criterion 1/2 are satisfied (it doesn't
test against Apollo's competing text at all).
**How to avoid:** Add a NEW test that runs `scoreCandidates()` over BOTH providers' candidates
together (the actual waterfall scenario) and asserts the ZoomInfo `industry` value never contains
only digits, in addition to updating the existing single-provider assertion.

## Package Legitimacy Audit

Not applicable — zero new packages this phase.

## Runtime State Inventory

Not applicable — this phase is not a rename/refactor/migration of existing identifiers. No
datastore keys, live-service configs, OS-registered state, secrets, or build artifacts carry
either `industry`/`lv_sponsorship_reliant`/`persona_group` as an identifier that would need
migrating; these are ordinary field-value/logic bugs, not naming changes. **Nothing found in this
category** — verified by grep across `config/`, `n8n/`, `scripts/`, `src/`; no external service
(n8n Cloud workflow content, HubSpot property definitions) needs anything beyond the normal
redeploy-and-rebuild cycle already covered by "Common Pitfalls" above. The two affected HubSpot
properties (`lv_sponsorship_reliant`, `lv_persona_group`) already exist live in the portal (Phase
15 manifest) — this phase writes to them for the first time, it does not create or rename them.

## Code Examples

### NORM-01 — industry text preference (adapt into `normalizeProviders.js`)
```js
// Source: this repo, n8n/code/normalizeProviders.js:296-304 (current, to be replaced)
const naics0 = (raw.naicsCodes || [])[0];
const naics = naics0 && typeof naics0 === "object" ? naics0.id : naics0;
const pi = Array.isArray(raw.primaryIndustry) ? raw.primaryIndustry[0] : raw.primaryIndustry;
_push(out, "industry", src, naics || pi, naics ? String(naics) : _norm(pi), 0.6, recency);
```

### COPY-01 — companies researchData loop (adapt into `ENRICH_MERGE_CO`)
```js
// Source: this repo, scripts/build_cloud_workflows.py:2311-2319 (current array, add one entry)
const researchData = {};
for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
                 "lv_is_hardware_vendor", "lv_is_gambling_operator", "lv_sponsorship_reliant"]) {
  const v = rc.data && rc.data[f];
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
  researchData[f] = v;
}
```

### COPY-02 — contacts candidate loop (adapt into `ENRICH_MERGE`, mirroring the linkedin_url block)
```js
// Source: this repo, scripts/build_cloud_workflows.py:963-965 (existing linkedin_url block,
// pattern to copy for persona_group)
if (winners.linkedin_url != null && String(winners.linkedin_url).trim() !== "") {
  candidate.lv_linkedin_url = winners.linkedin_url;
}
if (winners.persona_group != null && String(winners.persona_group).trim() !== "") {
  candidate.lv_persona_group = winners.persona_group;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| ZoomInfo industry = raw NAICS `.id` | ZoomInfo industry = NAICS `.name` (fallback `primaryIndustry`) | This phase | Industry text becomes human-readable and comparable to Apollo/Lusha free text |
| Companies research candidate copies 5 fields | Copies 6 fields (+ `lv_sponsorship_reliant`) | This phase | Property can populate once a producer exists (still needs the Open Question resolved) |
| Contacts candidate loop copies email/mobilephone/phone/jobtitle/seniority/linkedin_url | + `persona_group` -> `lv_persona_group` | This phase | Property can populate once a producer exists (still needs the Open Question resolved) |

**Deprecated/outdated:** none — no library or API version changes in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact text "media production" was Apollo's live `organization.industry` value in execution 19 (sourced from `.planning/debug/bug-17-lusha-company-400.md` prose, no JSON fixture exists) | NORM-01 "Reproducing the execution-19 shape" | If the planner wants byte-exact reproduction and this narrative detail is imprecise, the red test's Apollo fixture value may not perfectly match the historical run — low risk, since the mechanism (numeric vs text, trust-tiebreak) is independently verified from code, not from this one string |
| A2 | Neither `lv_sponsorship_reliant` nor `persona_group` currently has ANY live producer (verified by exhaustive grep of `normalizeProviders.js` and both research prompts) — flagged as an Open Question rather than assumed silently fixable in-phase | COPY-01, COPY-02 "candidate source does not currently exist upstream" | If a producer DOES exist somewhere not found by this grep (e.g. a config-driven mapping this research missed), the fix is still correct but the "why is it still empty live" diagnosis would be incomplete — re-grep before closing the phase if this surfaces |

## Open Questions

1. **Should this phase also wire a producer for `lv_sponsorship_reliant` / `persona_group`, or is the copy-loop fix alone sufficient to close COPY-01/COPY-02?**
   - What we know: ROADMAP's stated success criteria (3, 4) only require the copy-loop wiring,
     provable with a constructed candidate in a test — they do not require a live model/provider to
     ever emit the value.
   - What's unclear: whether "the property stops being permanently empty" (REQUIREMENTS.md wording)
     is meant literally (i.e., it should start receiving REAL live values, which needs a prompt/
     provider-mapper change) or just architecturally (the copy path now exists, ready for whenever
     a producer is added).
   - Recommendation: land the copy-loop fix only (matches the ROADMAP Detail's framing of this as
     one of three "small, localized, offline-provable" fixes); record the missing-producer gap as a
     new deferred item in STATE.md (same pattern as the existing "two latent copy-loop bugs" entry
     this phase is closing), explicitly naming it so it isn't lost a second time.

2. **Should the NORM-01 fix also touch `lushaCandidates()`'s identical-shape hazard?**
   - What we know: the code shape (`naics ? String(naics) : _norm(...)`) is byte-identical to the
     ZoomInfo bug; no live fixture proves Lusha ever returns NAICS as `{id,name}` objects (only bare
     strings, per the committed `lusha_company.json` fixture and the debug docs).
   - What's unclear: whether fixing it "for free" (same helper, same diff) is within this phase's
     fence, or whether ROADMAP's explicit "ZoomInfo's `'71'`" framing means Lusha is out of scope.
   - Recommendation: fix it in the same pass using the same shared helper (near-zero extra diff,
     same root cause, avoids planting a twin bug that gets its own debug ticket later) — but keep it
     as a clearly-labeled "defensive, not live-observed" fix in the commit/plan, not conflated with
     the criterion-1/2 proof (which must center on the real ZoomInfo/Apollo conflict).

## Environment Availability

Not applicable in the usual external-dependency sense (no new CLI/service/runtime needed), but the
ROADMAP's own stated baseline is STALE and should be corrected before planning proceeds:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/python -m pytest` | Full pytest suite | Yes | — | — |
| `node --test tests/n8n/*.test.mjs` | Full node test suite | Yes | — | — |

**Actual current baseline (measured 2026-07-29, this research session): 596 pytest / 285 node —
NOT the "587 pytest + node baseline" cited in ROADMAP.md's Milestone-4 overview and Phase-18
criterion 5.** The 587 figure predates Phase 17's execution (Phase 17 added tests as part of the
BUG 23 fix). Criterion 5 ("zero regressions") should be checked against 596/285, not 587 — the
planner should set the plan's target baseline explicitly to avoid a false "regression" read if the
count differs from the stale roadmap text.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, config-free) + Node's built-in `node:test` (JS) |
| Config file | none — `pytest.ini`/config absent; node uses CLI globs directly |
| Quick run command | `.venv/bin/python -m pytest tests/test_architecture_guard.py tests/test_companies_factory_frozen.py -q` (targeted) or `node --test tests/n8n/enrichment.test.mjs -q` (targeted) |
| Full suite command | `.venv/bin/python -m pytest -q` and `node --test tests/n8n/*.test.mjs` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NORM-01 (criterion 1) | ZoomInfo `"71"`-shape naics never survives as a bare numeric `industry` normalizedValue | unit (JS) | `node --test tests/n8n/enrichment.test.mjs` (update existing pinned assertion) | ✅ exists, needs edit |
| NORM-01 (criterion 2) | The numeric code never wins the waterfall over Apollo text via trust-tiebreak alone, reproduced with both providers' real-shape candidates scored together | unit (JS), NEW | new test in `tests/n8n/enrichment.test.mjs` or a new `tests/n8n/industryNormalization.test.mjs` calling `toCandidates()` for both providers + `scoreCandidates()` | ❌ Wave 0 |
| COPY-01 (criterion 3) | `lv_sponsorship_reliant` reaches `canonicalPatch` via the compiled `"Merge Company"` node body when `research_candidate.data.lv_sponsorship_reliant` is present | row-flow / compiled-body (JS), NEW | new test mirroring `tests/n8n/mergeCompanyStaleTimestamp.test.mjs`'s `runMergeCompany()` harness | ❌ Wave 0 |
| COPY-02 (criterion 4) | `lv_persona_group` reaches `canonicalPatch` via the compiled `"Merge Winners"` node body when `scored.winners.persona_group` is present | row-flow / compiled-body (JS), NEW | new test mirroring `tests/n8n/contactResearchChainRowFlow.test.mjs`'s row-flow harness, targeting `"Merge Winners"` | ❌ Wave 0 |
| Criterion 5 (regression) | Full offline suite green, builder deterministic | integration | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` then `python scripts/build_cloud_workflows.py` (x2) `&& git diff --quiet n8n/` | ✅ commands exist |
| Architecture guard (implicit, must not regress) | `scripts/build_cloud_workflows.py` never contains a bare quoted `"persona_group"`/`"linkedin_url"` string | unit (Python) | `.venv/bin/python -m pytest tests/test_architecture_guard.py -q` | ✅ exists |
| Frozen fixture guard (implicit, must be intentionally updated for COPY-01) | Companies chain jsCode byte-identity | unit (Python) | `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` | ✅ exists, fixture needs a bounded, isolated re-baseline commit |

### Sampling Rate
- **Per task commit:** the targeted command for whichever fix that task lands (see table above).
- **Per wave merge:** `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs`.
- **Phase gate:** full suite green (596 pytest / 285 node, or whatever the actual count is at plan
  time — do not silently accept a lower count) + `python scripts/build_cloud_workflows.py` run
  twice with `git diff --quiet n8n/` passing both times, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] New JS test proving NORM-01 criterion 2 (both-providers-scored-together, real shapes) —
      no existing test scores Apollo + ZoomInfo industry candidates against each other.
- [ ] New JS test proving COPY-01 via the compiled `"Merge Company"` body (row-flow/compiled-body
      style, not a pure-function call) — the closest existing precedent
      (`mergeCompanyStaleTimestamp.test.mjs`) proves a DIFFERENT bug and needs to be adapted, not
      reused directly.
- [ ] New JS test proving COPY-02 via the compiled `"Merge Winners"` body — no existing test drives
      that specific node's compiled jsCode with a `persona_group` winner.
- [ ] A write-once PRE-fix jsCode snapshot fixture for the COPY-01 re-baseline (mirrors
      `tests/fixtures/merge_company_prefix_jscode.json`'s established pattern) — needs to be
      captured from the CURRENT (pre-this-phase) `"Merge Company"` body before any edit lands.

## Security Domain

`security_enforcement` status: not found as an explicit key in `.planning/config.json` in this
repo (absent = enabled per the instruction default) — however, this phase's actual attack surface
is negligible: it edits pure data-transformation logic with no new input parsing, no new
trust-boundary crossing, and no new external call. Included for completeness, not because
meaningful new risk exists.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No auth surface touched |
| V3 Session Management | No | No session surface touched |
| V4 Access Control | No | No access-control surface touched |
| V5 Input Validation | Marginal | The `_industryText()` helper and the two copy-loop `if`-blocks already null/blank-check every value before use, matching the existing codebase convention (`_isBlank`, `!= null && String(...).trim() !== ""`) — no new unvalidated input path introduced |
| V6 Cryptography | No | Not touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| A permissive `winners`/`researchData` copy silently promoting an attacker/LLM-controlled string straight to a HubSpot canonical property | Tampering | Already mitigated upstream by `mergeCompanies`/`mergeContacts`'s field-policy gate (`min_confidence`, `require_evidence_url`) — this phase does not change that gate, only which fields REACH it; both `lv_sponsorship_reliant` and `lv_persona_group` are `system_owned` with no evidence requirement, same as several existing fields already copied through this exact loop (e.g. `seniority`), so no new class of risk is introduced |

## Sources

### Primary (HIGH confidence — direct repo reads this session)
- `n8n/code/normalizeProviders.js` (full read) — NORM-01 root cause
- `n8n/code/scoreEnrichment.js` (full read) — waterfall trust-tiebreak mechanism
- `n8n/code/mergeCompanies.js` (full read) — companies field policy, frozen-function contract
- `n8n/code/mergeContacts.js` (lines 1-50) — contacts field policy, PN-1 rename precedent
- `n8n/code/webResearch.js` (full read) — research candidate validation/spread behavior
- `scripts/build_cloud_workflows.py` (targeted reads: 900-1010, 1800-1870, 1940-1980, 2243-2360) —
  ENRICH_MERGE / ENRICH_MERGE_CO wrapper bodies, research prompt schemas, EnrichTarget configs
- `tests/test_companies_factory_frozen.py` (full read) — frozen-node re-baseline mechanism
- `tests/test_architecture_guard.py` (lines 200-270) — PN-1 bare-key guard, exact regex
- `tests/n8n/mergeCompanyStaleTimestamp.test.mjs` (full read) — compiled-node-body test precedent
- `tests/n8n/enrichment.test.mjs` (lines 300-368) — existing pinned "71" assertion
- `tests/fixtures/enrichment/zoominfo_live_company.json` — real live NAICS-object shape
- `.planning/debug/bug-17-lusha-company-400.md` (full read) — execution-19 conflict narrative
- Live command run this session: `.venv/bin/python -m pytest -q` -> 596 passed;
  `node --test tests/n8n/*.test.mjs` -> 285 passed (actual current baseline, corrects stale
  ROADMAP text)

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — phase scope,
  requirement wording, prior-phase decision log (all internal project docs, not external)

### Tertiary (LOW confidence)
- None — no external/web sources were needed for this phase; it is entirely internal-codebase
  research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new stack, existing tooling only, verified by running both suites live.
- Architecture: HIGH — every claimed file:line was read directly this session, not inferred.
- Pitfalls: HIGH — sourced from this repo's own prior-phase precedent (Phase 16.3) for the
  identical class of frozen-fixture re-baseline problem.

**Research date:** 2026-07-29
**Valid until:** Until the next edit to `scripts/build_cloud_workflows.py`, `normalizeProviders.js`,
`mergeCompanies.js`, or `mergeContacts.js` — this research is a snapshot of exact current code, not
a stable external API; treat as valid for the immediate next planning session only (not a 30-day
window).
