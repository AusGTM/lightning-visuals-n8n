# Phase 18: Normalization & Copy-Loop Fixes - Pattern Map

**Mapped:** 2026-07-29
**Files analyzed:** 3 source files (+2 generated artifacts, not hand-edited)
**Analogs found:** 3 / 3 — all analogs are same-file/adjacent-line precedents (this phase edits
existing modules in place; no new modules are created)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `n8n/code/normalizeProviders.js` (`zoominfoCandidates`, ~296-304; defensively `lushaCandidates`, ~187-188) | transform (pure JS normalizer) | transform | same file, `apolloCandidates`'s existing `industry` push (~line 224, flat `0.6` accuracy, text passthrough) — same function shape, correct text-only behavior already | exact (same file, same function family) |
| `scripts/build_cloud_workflows.py` — `ENRICH_MERGE_CO` researchData loop (~2311-2319) | service (Python code-generator emitting a JS wrapper) | CRUD-style field copy / transform | same loop, unchanged — literally add one string to the existing array | exact |
| `scripts/build_cloud_workflows.py` — `ENRICH_MERGE` candidate loop (~959-965) | service (Python code-generator emitting a JS wrapper) | CRUD-style field copy / transform | the adjacent `linkedin_url` → `lv_linkedin_url` `if`-block immediately above (lines 963-965) | exact |
| `tests/n8n/enrichment.test.mjs` (existing pinned "71" assertion, ~350-354) | test | transform verification | itself — collateral update, not a new pattern | n/a (in-place edit) |
| `tests/n8n/<new NORM-01 waterfall test>` | test | transform verification | `n8n/code/scoreEnrichment.js` usage in `tests/n8n/enrichment.test.mjs` (existing `scoreCandidates()` calls) | role-match |
| `tests/n8n/<new COPY-01 compiled-body test>` | test | request-response (compiled Code-node body) | `tests/n8n/mergeCompanyStaleTimestamp.test.mjs` (full file — the `runMergeCompany()` harness + row-fixture shape) | exact |
| `tests/n8n/<new COPY-02 compiled-body test>` | test | request-response (compiled Code-node body) | `tests/n8n/contactResearchChainRowFlow.test.mjs` (row-flow harness targeting `"Merge Winners"`) | exact |
| `tests/fixtures/companies_jscode_frozen.json` (`"Merge Company"` entries, cloud + local_live) | config (frozen fixture) | batch (byte-identity pin) | `tests/test_companies_factory_frozen.py`'s existing re-baseline mechanism, precedent-executed in Phase 16.3 | exact |
| `tests/fixtures/<new COPY-01 PRE-fix prefix fixture>.json` | config (write-once snapshot) | batch | `tests/fixtures/merge_company_prefix_jscode.json` (Phase 16.3's PRE-fix snapshot, same pattern) | exact |
| `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json` | config (generated build artifact) | batch (regenerate, don't hand-edit) | themselves — `python scripts/build_cloud_workflows.py` is the only writer | n/a |

## Pattern Assignments

### `n8n/code/normalizeProviders.js` (transform, `zoominfoCandidates`)

**Analog:** same file, `apolloCandidates()`'s industry handling (~line 224) — already correctly
pushes free text, never a numeric code; this is the "already does it right" sibling to copy the
spirit from, though the concrete fix is a new small helper, not a line-for-line copy.

**Current buggy code** (lines 296-304, to be replaced):
```javascript
const naics0 = (raw.naicsCodes || [])[0];
const naics = naics0 && typeof naics0 === "object" ? naics0.id : naics0;
const pi = Array.isArray(raw.primaryIndustry) ? raw.primaryIndustry[0] : raw.primaryIndustry;
_push(out, "industry", src, naics || pi, naics ? String(naics) : _norm(pi), 0.6, recency);
```

**Same-shape hazard in `lushaCandidates()`** (lines 187-188, defensive fix, same helper):
```javascript
const naics = (co.naicsCodes || [])[0];
_push(out, "industry", src, naics || co.mainIndustry, naics ? String(naics) : _norm(co.mainIndustry), 0.6, updated);
```

**Recommended fix shape** (from RESEARCH.md, verbatim — add near top of file, use in both
`zoominfoCandidates` and `lushaCandidates`):
```javascript
// Prefer human-readable industry text over a raw NAICS code; a numeric code alone is
// never a valid `industry` text value (NORM-01).
function _industryText(naicsEntry, textFallback) {
  if (naicsEntry && typeof naicsEntry === "object" && naicsEntry.name) {
    return { raw: naicsEntry.name, key: _norm(naicsEntry.name) };
  }
  const fallback = Array.isArray(textFallback) ? textFallback[0] : textFallback;
  if (fallback) return { raw: fallback, key: _norm(fallback) };
  return null; // bare numeric code, no name, no fallback text -> skip, don't fabricate
}
```
Call site replaces the `_push(...)` line: compute `_industryText(naics0, raw.primaryIndustry)`,
skip the `_push` entirely when it returns `null` (no candidate emitted rather than a numeric
string), else `_push(out, "industry", src, result.raw, result.key, 0.6, recency)`.

**`_push` / `_norm` helper contract** (already in file, unchanged — read, don't reinvent):
`_push(out, field, source, rawValue, normalizedValue, accuracy, recencyDate)` appends a candidate;
`_norm(v)` lowercases/trims text, returns `null` for null/undefined. Reuse both as-is.

**Waterfall trust mechanism to test against** (`n8n/code/scoreEnrichment.js`):
```javascript
// DEFAULT_TRUST (line ~21)
const DEFAULT_TRUST = { zoominfo: 0.85, lusha: 0.8, apollo: 0.75 };
```
The new test must call `scoreCandidates()` with BOTH providers' `industry` candidates present
(ZoomInfo's fixed fixture `tests/fixtures/enrichment/zoominfo_live_company.json` +  a constructed
Apollo raw shape `{ organization: { industry: "media production" } }`) and assert the winning
`industry` value is never all-digits.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_MERGE_CO` (COPY-01)

**Analog:** the loop itself — this is a pure "add one array entry" fix, no cross-file pattern
needed.

**Current code** (lines 2311-2319, current array to extend):
```javascript
const researchData = {};
for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
                 "lv_is_hardware_vendor", "lv_is_gambling_operator"]) {
  const v = rc.data && rc.data[f];
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
  researchData[f] = v;
}
```

**Fix:** append `"lv_sponsorship_reliant"` to the array literal. No other line changes; the
existing tri-state-null/blank-skip guard already applies uniformly.

**Field policy already correct, no edit needed** — `n8n/code/mergeCompanies.js` line 43:
```javascript
DEFAULT_COMPANY_POLICY.lv_sponsorship_reliant = { class: "system_owned", min_confidence: 70 }
```

**Frozen fixture consequence:** `"Merge Company"` is one of `FROZEN_NODE_NAMES` in
`tests/test_companies_factory_frozen.py`, pinned against `tests/fixtures/companies_jscode_frozen.json`
(both `cloud` and `local_live`). Follow the Phase 16.3 procedure exactly:
1. Capture PRE-fix compiled body as a new write-once fixture (mirror
   `tests/fixtures/merge_company_prefix_jscode.json`'s pattern/naming).
2. Make the source edit.
3. Rebuild, confirm ONLY `"Merge Company"` differs.
4. Re-baseline `companies_jscode_frozen.json`'s `"Merge Company"` entries as an isolated, reviewed
   commit.

**Test harness to copy verbatim** — `tests/n8n/mergeCompanyStaleTimestamp.test.mjs` (full file
read; reuse `runMergeCompany()` and the row-fixture shape):
```javascript
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
Row fixture pattern (adapt `research_candidate.data` to include `lv_sponsorship_reliant`):
```javascript
{
  identity_keys: { domain: "exampleco.example" },
  existingRecord: { domain: "exampleco.example", name: "Example Co" },
  scored: { best: {}, winners: {}, sourcesByField: {} },
  research_candidate: {
    matched: true,
    confidence: 90,
    data: { lv_sponsorship_reliant: true },
    evidence_by_field: {},
  },
}
```
Load the PRE fixture the same way the precedent does (`.cloud["Merge Company"]` from the new
prefix JSON) and the POST body live from `n8n/wf_enrichment_cloud.json`, asserting the diff is
exactly the new field.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_MERGE` (COPY-02)

**Analog:** the immediately-adjacent `linkedin_url` block (lines 963-965) — copy this exact
`if`-block shape, do NOT add to the `for (const f of [...])` array above it.

**Current code** (lines 959-965, `linkedin_url` block is the pattern to mirror):
```javascript
const candidate = {};
for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority"]) {
  if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
}
if (winners.linkedin_url != null && String(winners.linkedin_url).trim() !== "") {
  candidate.lv_linkedin_url = winners.linkedin_url;
}
```

**Fix — add a fourth block, dot-property access only:**
```javascript
if (winners.persona_group != null && String(winners.persona_group).trim() !== "") {
  candidate.lv_persona_group = winners.persona_group;
}
```

**CRITICAL guard (must not regress)** — `tests/test_architecture_guard.py` lines 234-247,
`test_pn1_build_script_never_writes_a_bare_linkedin_or_persona_property_key`, regex
`r'"(linkedin_url|persona_group)"'` forbids ANY bare-quoted occurrence of either string in
`build_cloud_workflows.py`. The `if (winners.x != null...)` dot-access form (exactly as above)
does not match; adding `"persona_group"` to the `for (const f of [...])` array literal WOULD
match and fail this guard.

**Field policy already correct, no edit needed** — `n8n/code/mergeContacts.js` line 31:
```javascript
DEFAULT_CONTACT_POLICY.lv_persona_group = { class: "system_owned", min_confidence: 75 }
```

**Not frozen** — `"Merge Winners"` is not in `FROZEN_NODE_NAMES`; no fixture re-baseline needed,
just the standard rebuild + `git diff --quiet n8n/` determinism check.

**Test harness to copy** — `tests/n8n/contactResearchChainRowFlow.test.mjs`'s row-flow style
(same `new Function(...)` mechanism as the companies harness above, targeting the `"Merge
Winners"` node's compiled jsCode from `n8n/wf_enrichment_cloud.json` instead of `"Merge Company"`).
Row fixture needs `scored.winners.persona_group` set directly (per RESEARCH.md, this is the exact
"candidate source" the wrapper loop reads — no live provider traceability required for the test).

---

## Shared Patterns

### Compiled-node-body differential testing (load-bearing for all three fixes' tests)
**Source:** `tests/n8n/mergeCompanyStaleTimestamp.test.mjs` (full file)
**Apply to:** All three new tests (NORM-01 waterfall test, COPY-01, COPY-02)
Rule: execute the ACTUAL jsCode string shipped inside the committed workflow JSON via
`new Function(...)`, not the pure `mergeCompanies()`/`mergeContacts()` function in isolation —
the bug lives in the Python-generated wrapper, so a pure-function-level test proves nothing about
these regressions (see RESEARCH.md "Anti-Patterns to Avoid").

### Blank/tri-state guard convention
**Source:** `scripts/build_cloud_workflows.py` both loops (ENRICH_MERGE_CO / ENRICH_MERGE)
**Apply to:** Any new copy-loop entry
```javascript
if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
// or, contacts style:
if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
```
Always reuse one of these two existing null/blank forms; never introduce a third variant.

### Rebuild-and-verify-determinism cycle
**Source:** RESEARCH.md "Common Pitfalls" #1 and #2, Phase 16.3 precedent
**Apply to:** Both COPY-01 and COPY-02
```bash
python scripts/build_cloud_workflows.py   # after every source edit
git diff --stat n8n/                      # confirm expected files changed
python scripts/build_cloud_workflows.py   # run again
git diff --quiet n8n/                     # zero diff = deterministic
```

## No Analog Found

None — every touched file/loop has a direct, exact in-repo analog (either the adjacent working
code in the same loop, or a directly-precedented test harness from Phase 16.3). This phase's
whole shape is "copy the working sibling pattern," so no RESEARCH.md-only pattern is needed
anywhere.

## Metadata

**Analog search scope:** `n8n/code/*.js`, `scripts/build_cloud_workflows.py`, `tests/n8n/*.test.mjs`,
`tests/test_companies_factory_frozen.py`, `tests/test_architecture_guard.py`
**Files scanned:** 6 (targeted reads, all overlapping with RESEARCH.md's own cited line ranges;
confirmed current-line-number accuracy via direct `sed`/`Read` this session)
**Pattern extraction date:** 2026-07-29
