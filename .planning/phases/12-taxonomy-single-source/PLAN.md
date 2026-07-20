---
phase: 12-taxonomy-single-source
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [REQ-taxonomy-single-source, REQ-enum-normalization]
files_modified:
  - src/taxonomy.py
  - scripts/gen_taxonomy_js.py
  - scripts/build_cloud_workflows.py
  - n8n/code/taxonomy.generated.js
  - n8n/code/taxonomy.js
  - n8n/code/mergeCompanies.js
  - tests/fixtures/taxonomy_parity_cases.json
  - tests/test_taxonomy_conformance.py
  - tests/test_web_research_spec.py
  - tests/n8n/parity.test.mjs
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_enrichment_local_live.json

must_haves:
  truths:
    - Adding an org_type to config/taxonomy.yaml and rebuilding propagates to the n8n Merge Company node with no hand edit.
    - Forgetting to rebuild after a taxonomy edit fails a test; it never produces a silent 0-score.
    - normalize_org_type never returns a string outside the vocabulary, for any input.
    - Python and JS normalizers return identical results for every case in the shared table.
  artifacts:
    - src/taxonomy.py
    - scripts/gen_taxonomy_js.py
    - n8n/code/taxonomy.generated.js
    - n8n/code/taxonomy.js
    - tests/fixtures/taxonomy_parity_cases.json
  key_links:
    - config/taxonomy.yaml -> gen_taxonomy_js.py -> n8n/code/taxonomy.generated.js -> mergeCompanies.js -> Merge Company node jsCode
    - config/taxonomy.yaml -> src/taxonomy.py (runtime read, no codegen)
---

# Phase 12 — Taxonomy Single-Source

**Goal:** Adding an `lv_org_type` or `lv_content_type` value is a one-file edit to
`config/taxonomy.yaml` that cannot silently drift.

**Requirements:** REQ-taxonomy-single-source (spec TX-1…TX-9), REQ-enum-normalization
(spec NM-1…NM-6).

**Depends on:** Phase 11. **Reversible:** entirely — pure code + git, no HubSpot writes,
no live API calls in this phase.

---

## Design decisions (made here, not left to the executor)

### D1 — Generate a JS *data* module; do NOT invent new builder machinery

`scripts/build_cloud_workflows.py::inline()` already reads `n8n/code/*.js`, strips
`require(...)` and `module.exports`, and concatenates the result into a Code node. That is
exactly the transport a generated taxonomy needs. So the generator writes an ordinary
module — `n8n/code/taxonomy.generated.js` — and `mergeCompanies.js` `require`s it like any
sibling. `inline("taxonomy.generated.js", "mergeCompanies.js")` does the rest.

Consequences: the same file serves `node --test` (real `require`) and the Code node
(inlined literal), with one definition. No `.replace()` templating, no second escape path.

### D2 — Data is generated, logic is hand-written

`taxonomy.generated.js` carries **only** vocabulary data (canonical keys, synonym maps,
evidence-gated list, defaults, version) behind a DO-NOT-EDIT header.
`n8n/code/taxonomy.js` carries the ~30 lines of normalizer logic and `require`s the
generated data.

Rationale: drift lives in the *data*, never in the logic. Emitting logic from a Python
string literal would make it unreadable and undiffable for zero safety gain.

### D3 — `icp_scoring.yaml` and `field_policy.yaml` stay HAND-WRITTEN and test-guarded

**Decision: do not generate them.** Justification:

- Generation is only necessary where the consumer *physically cannot read the source*.
  That is true of exactly one consumer: the n8n Code node. Python reads
  `config/taxonomy.yaml` at runtime; the two YAMLs are read at runtime by
  `src/icp_scoring.py` and `src/merge_policy.py`.
- Both YAMLs are majority hand-authored config unrelated to the vocabulary
  (`hard_vetoes`, `tier_rules`, `recommended_motion`, ownership classes, thresholds, the
  whole `contacts` block). Partial-file codegen into them is a merge/round-trip problem
  with a real clobber risk, traded for safety that TX-1/TX-2/TX-3 already provide.
- Those three drift guards exist and pass today. A test that fails on drift is the same
  guarantee as generation, at a fraction of the machinery.
- The scores in `icp_scoring.yaml` remain authoritative and numerically untouched
  (constraint 5). `taxonomy.yaml`'s `score:` field mirrors them for the TX-1 assertion; it
  is not a second source.

The one thing missing is a guard that the *generated* file is current — added in Task 2.

### D4 — Only the NM-* xfail markers come off

`tests/test_web_research_spec.py` marks 11 tests `xfail(strict=True)`. This phase
satisfies four of them:

- `test_nm1_nm3_org_type_normalization`
- `test_nm1_never_returns_off_vocabulary`
- `test_nm4_default_sets_needs_review`
- `test_nm5_content_types_drop_unknown_and_dedupe`

Their markers **must** be deleted in the same task that implements them — strict xfail
reports an unexpected pass as a FAILURE, so leaving a marker in place turns the suite red.

The remaining xfails (`OC-1/2/3/4`, `TS-1/2/3`, `AT-2`, `ER-1`) need
`validate_research_output` / `to_provider_result`, which are **Phase 13 scope
(REQ-web-retrieval / REQ-evidence-by-field)**. Do not implement them here, and do not
touch their markers. They will keep xfailing on `AttributeError` once `src/taxonomy.py`
exists — that is the expected state at the end of this phase.

---

## Tasks

### Task 1 — `src/taxonomy.py`: loader + normalizers (NM-1…NM-5)

**Files:** `src/taxonomy.py` (new), `tests/test_web_research_spec.py` (delete 4 markers)

**Action:**

Create `src/taxonomy.py` reading `config/taxonomy.yaml` at import (module-level cache;
mirror the `load_yaml` style already in `src/icp_scoring.py`, relative path from repo root
so it matches how `icp_scoring` already loads its config).

Public surface:

- `normalize_key(raw)` — NM-3 comparison form: `str()`, lowercase, every non-alphanumeric
  character to a space, collapse runs of whitespace, strip. `None`/`""` → `""`.
- `normalize_org_type(raw)` → canonical key or `"unknown"`. NM-2 order: exact canonical key
  (compared in normalized form, so `"Governing Body League"` hits the key) → synonym table
  → default. NM-1: never returns anything outside `org_types`.
- `normalize_org_type_result(raw)` → `{"value": ..., "needs_review": bool}`. NM-4:
  `needs_review` is `True` whenever the result is the default **and** the raw input was
  not already the default — a blank/`None` input also counts as unmapped and reviews.
- `normalize_content_types(list_or_none)` → list of canonical `content_types` keys. NM-5:
  drop unrecognised entries (never pass through), de-duplicate, preserve first-seen order.
  Non-list input → `[]`.
- Exported constants: `TAXONOMY`, `ORG_TYPES`, `CONTENT_TYPES`, `DEFAULT_ORG_TYPE`,
  `DEFAULT_CONTENT_TYPE`, `EVIDENCE_GATED_ORG_TYPES`, `VERSION`. Defaults are read from
  `is_default: true`, never hard-coded — TX-7 guarantees exactly one per vocabulary.

Synonym tables are built by passing every synonym through `normalize_key`, so
`"LED vendor"` and `"led-vendor"` both resolve.

Then delete the four `@unbuilt` markers named in D4 from
`tests/test_web_research_spec.py`. Leave the other seven exactly as they are.

**Acceptance criteria:**

- All 10 parametrized `test_nm1_nm3_org_type_normalization` cases pass, including
  `None`, `""`, `"  GOVERNING  BODY "` and `"completely made up"`.
- `test_nm1_never_returns_off_vocabulary`, `test_nm4_default_sets_needs_review`,
  `test_nm5_content_types_drop_unknown_and_dedupe` pass with no marker.
- The other seven xfails still report `xfailed`, not `failed` and not `xpassed`.
- No change to `src/icp_scoring.py` or any scoring number.

**Verify:**

```bash
.venv/bin/pytest tests/test_web_research_spec.py -q
# expect: 6 passed, 7 xfailed, 0 failed, 0 xpassed
.venv/bin/pytest tests/test_icp_scoring.py tests/test_merge_policy.py -q
```

---

### Task 2 — Generator + generated JS data module + currency guard

**Files:** `scripts/gen_taxonomy_js.py` (new), `n8n/code/taxonomy.generated.js` (new,
generated), `scripts/build_cloud_workflows.py`, `tests/test_taxonomy_conformance.py`

**Action:**

Create `scripts/gen_taxonomy_js.py` exposing `render() -> str` and a `__main__` that writes
`n8n/code/taxonomy.generated.js`. Render with `json.dumps` (per the builder's own ponytail
note — never hand-escape). Emitted content:

- Header comment: `GENERATED FROM config/taxonomy.yaml — DO NOT EDIT`, the taxonomy
  `version`, and the regeneration command.
- `const TAXONOMY_VERSION`, `const ORG_TYPES` (array of canonical keys),
  `const ORG_TYPE_SYNONYMS` (normalized-synonym → canonical map),
  `const EVIDENCE_GATED_ORG_TYPES` (the `requires_evidence: true` set, sorted — this is
  the list that retires TX-4), `const DEFAULT_ORG_TYPE`, `const CONTENT_TYPES`,
  `const CONTENT_TYPE_SYNONYMS`, `const CONTENT_TYPE_IMPLIES` (key → `true|false|null`),
  `const DEFAULT_CONTENT_TYPE`.
- Trailing `module.exports = { ... }` — required by `node --test`, and stripped by
  `strip_module()` on the way into a Code node.
- Synonym keys must be produced by the **same** normalization `src/taxonomy.py` uses, so
  the two maps are keyed identically. Import `normalize_key` from `src.taxonomy` rather
  than re-implementing it; one definition, no parity gap by construction.

Wire it into `scripts/build_cloud_workflows.py`: call the generator at the top of the
build (before any `inline()`), so `python scripts/build_cloud_workflows.py` can never emit
a workflow carrying a stale vocabulary.

Add a currency drift guard to `tests/test_taxonomy_conformance.py`:

```
test_taxonomy_generated_js_is_current  (TX-4 companion)
```

It calls `gen_taxonomy_js.render()` and asserts the string equals the checked-in
`n8n/code/taxonomy.generated.js`, with a failure message naming the regeneration command.
This is the guard that makes D3 sound: the derived artifact that cannot be read at runtime
is the one artifact proven current by test.

**Acceptance criteria:**

- `n8n/code/taxonomy.generated.js` exists, passes `node --check`, and `require()`s cleanly.
- `EVIDENCE_GATED_ORG_TYPES` equals `["content_producer", "gambling_operator",
  "governing_body_league", "hardware_vendor"]` (sorted) — the same set
  `field_policy.yaml` gates, per TX-3.
- Running the generator twice is a no-op (deterministic ordering; no timestamps in the
  output — a timestamp would make the currency test fail on every run).
- Adding a temporary org_type to `config/taxonomy.yaml` makes the currency test FAIL until
  regeneration. Prove this manually, then revert.
- `python scripts/build_cloud_workflows.py` regenerates the JS before inlining.

**Verify:**

```bash
.venv/bin/python scripts/gen_taxonomy_js.py && node --check n8n/code/taxonomy.generated.js
.venv/bin/pytest tests/test_taxonomy_conformance.py -q
git diff --exit-code n8n/code/taxonomy.generated.js   # regeneration is a no-op
```

---

### Task 3 — `mergeCompanies.js` consumes the generated list; TX-4 goes green

**Files:** `n8n/code/mergeCompanies.js`, `scripts/build_cloud_workflows.py`,
`n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`,
`n8n/wf_enrichment_local_live.json`

**Action:**

Before touching anything, snapshot the five builder outputs for the Task-3 regression
proof (`git stash`-free — `HEAD` is the baseline; the working tree must be clean of
workflow edits when this task starts).

In `n8n/code/mergeCompanies.js`:

- Add `const { EVIDENCE_GATED_ORG_TYPES } = require("./taxonomy.generated");` at the top.
  It must match the builder's `_REQUIRE_RE` (`^\s*const\s*\{...\}\s*=\s*require\(`) so
  `strip_module()` removes it — verify by eye against `scripts/build_cloud_workflows.py:26`.
- Replace the hand-typed array at line ~27 with `require_evidence_url_for:
  EVIDENCE_GATED_ORG_TYPES`.
- Update the `DEFAULT_COMPANY_POLICY` header comment: the gated set now derives from
  `config/taxonomy.yaml`, not from `field_policy.yaml` by transcription.

In `scripts/build_cloud_workflows.py`, change `ENRICH_MERGE_CO` to
`inline("taxonomy.generated.js", "mergeCompanies.js")` — generated data first, so the
`const` is defined before `DEFAULT_COMPANY_POLICY` references it.

Regenerate all workflows.

**Non-regression proof (constraint 6).** Phase 11 proved the `_zoom_preamble()` refactor by
showing the contacts `ZoomInfo Enrich` node was byte-identical before and after. Same
standard applies: the **only** node whose `jsCode` may change is `Merge Company`. Every
contacts-branch node must be byte-identical.

**Acceptance criteria:**

- `test_tx4_mergecompanies_has_no_handmaintained_enum` passes — the TX-4 debt carried
  from Phase 11 is retired and `.planning/STATE.md`'s pending todo can be closed.
- Zero literal org_type values remain in `mergeCompanies.js`
  (`grep -c 'governing_body_league' n8n/code/mergeCompanies.js` returns 0).
- The existing `mergeCompanies` cases in `tests/n8n/parity.test.mjs` pass unchanged —
  in particular the `hardware_vendor`-unevidenced-→-`needs_review` case, which now
  exercises the generated list.
- Node-level diff shows exactly one changed node across all five workflows:
  `Merge Company` (present in the three enrichment workflows). Both contact-ingest
  workflows show **no** node change.

**Verify:**

```bash
.venv/bin/python scripts/build_cloud_workflows.py
.venv/bin/pytest tests/test_taxonomy_conformance.py -q
node --test tests/n8n/

.venv/bin/python - <<'PY'
import json, subprocess
FILES = ["n8n/wf_contact_ingest_cloud.json", "n8n/wf_contact_ingest_local.json",
         "n8n/wf_enrichment_cloud.json", "n8n/wf_enrichment_local.json",
         "n8n/wf_enrichment_local_live.json"]
def codes(text):
    return {n["name"]: n.get("parameters", {}).get("jsCode")
            for n in json.loads(text)["nodes"]}
changed = []
for f in FILES:
    old = codes(subprocess.run(["git", "show", f"HEAD:{f}"],
                               capture_output=True, text=True).stdout)
    new = codes(open(f).read())
    changed += [f"{f} :: {k}" for k in new if old.get(k) != new[k]]
print("\n".join(changed) or "NO NODE CHANGED")
assert all(c.endswith(":: Merge Company") for c in changed), changed
print("OK — only Merge Company changed; contacts branch byte-identical")
PY
```

---

### Task 4 — JS normalizer + NM-6 Python/JS parity test

**Files:** `n8n/code/taxonomy.js` (new), `tests/fixtures/taxonomy_parity_cases.json` (new),
`tests/n8n/parity.test.mjs`

**Action:**

Create `n8n/code/taxonomy.js` — hand-written logic over the generated data (D2):

- `require("./taxonomy.generated")` at the top, in `strip_module`-compatible form.
- `normalizeKey(raw)` — must be a character-for-character behavioural match of
  `src.taxonomy.normalize_key`. Non-alphanumeric → space, collapse, trim, lowercase.
  Use `String(raw).replace(/[^a-z0-9]+/gi, " ")` after lowercasing; do **not** use
  `\W`, which keeps `_` and would make `governing_body_league` normalize differently in
  JS than in Python.
- `normalizeOrgType(raw)`, `normalizeOrgTypeResult(raw)`, `normalizeContentTypes(list)` —
  same contracts and same fallback semantics as Task 1.
- `module.exports = { normalizeKey, normalizeOrgType, normalizeOrgTypeResult, normalizeContentTypes }`.

No node consumes this yet — the web-research node lands in Phase 13. It is built now
because NM-6 parity is a Phase 12 success criterion and because building the JS side later,
against a Python side that has drifted, is how parity bugs are born.

Create `tests/fixtures/taxonomy_parity_cases.json` — *the* shared table NM-6 names. Both
languages read this one file; neither carries its own case list. Cover at minimum:

- every canonical `org_types` key, verbatim;
- at least one synonym per org_type that has synonyms;
- NM-3 mangling: `"Governing Body"`, `"governing-body"`, `"  GOVERNING  BODY "`,
  `"LED vendor"`, `"Racing_Club"`;
- misses: `"completely made up"`, `""`, `null`, `"42"`, `"<script>"`,
  `"governing_body_leagueX"`;
- content-type lists including duplicates, synonyms and unrecognised entries.

Add an NM-6 test to `tests/n8n/parity.test.mjs`, following the existing `pyPhone` oracle
pattern (`execFileSync` on `.venv/bin/python`, `cwd: ROOT`). One subprocess call for the
whole table, not one per case. Assert JS output `deepStrictEqual` Python output for
`normalize_org_type`, `normalize_org_type_result` and `normalize_content_types` across
every case.

**Acceptance criteria:**

- `node --test tests/n8n/parity.test.mjs` passes, including the new NM-6 test.
- Deliberately breaking parity (e.g. changing the JS regex to `\W`) makes the NM-6 test
  fail, naming the divergent case. Prove this manually, then revert.
- The parity fixture is read by both sides; no case list is duplicated in either language.
- `node --check n8n/code/taxonomy.js` passes.

**Verify:**

```bash
node --check n8n/code/taxonomy.js
node --test tests/n8n/
```

---

## Phase verification

```bash
.venv/bin/pytest -q                 # expect: 0 failed, 7 xfailed, 0 xpassed
node --test tests/n8n/              # expect: all pass
.venv/bin/python scripts/build_cloud_workflows.py
git diff --exit-code n8n/           # rebuild after a clean build is a no-op
for f in n8n/code/*.js; do node --check "$f" || exit 1; done
```

## Success criteria (ROADMAP Phase 12)

1. `config/taxonomy.yaml` is the only hand-edited vocabulary — Tasks 1–4; scoring config
   and field policy remain hand-written but drift-guarded by TX-1/2/3 per D3, and the one
   artifact that *cannot* be read at runtime (the node literal) is generated and
   currency-tested.
2. `src/taxonomy.py` satisfies NM-1…NM-5 — Task 1; NM-6 — Task 4.
3. Builder generates the JS literal into the Code node; TX-4 green with no hand-maintained
   list in `mergeCompanies.js` — Tasks 2–3.
4. Python and JS agree on every shared case — Task 4.

## Out of scope (Phase 13+)

- `validate_research_output`, `to_provider_result`, `evidence_by_field` — Phase 13.
- Tri-state coercion (TS-1…TS-3) and AT-2/ER-1 — Phase 13. **Leave their xfail markers.**
- HubSpot property options sync for `lv_org_type` / `lv_content_type` — Phase 15
  (the property is `string/text` today; strengthening it to an enumeration is the
  irreversible migration tracked there).
- Any change to `icp_scoring.yaml` scores, `src/icp_scoring.py` behaviour, or the
  contacts branch.

## Output

Write `.planning/phases/12-taxonomy-single-source/12-01-SUMMARY.md` on completion.
Record the TX-4 debt as retired so `.planning/STATE.md`'s pending todo can be cleared.
