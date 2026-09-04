# Phase 66: Rich enrichment, not minimum enrichment - Pattern Map

**Mapped:** 2026-09-05
**Files analyzed:** 5 (all MODIFIED, no new files — this phase is pure widening of existing lanes)
**Analogs found:** 5 / 5 (every file changed is its own best analog — the pattern to copy is
an existing sibling block/branch in the SAME file, not a different file)

## File Classification

| Modified File | Role | Data Flow | Closest Analog (same-file sibling unless noted) | Match Quality |
|---|---|---|---|---|
| `scripts/build_cloud_workflows.py` (`ENRICH_GATE`'s `REQUIRED`, contacts, ~line 1292) | config/generator (wrapper constant) | batch/transform | `ENRICH_CO_GATE`'s `REQUIRED` (line 2261) — sibling gate, same shape, different field list | exact |
| `scripts/build_cloud_workflows.py` (`ENRICH_CO_GATE`'s `REQUIRED`, companies, ~line 2261) | config/generator (wrapper constant) | batch/transform | `CONFLICT_WATCH`/`MATERIAL_CONFLICT_GROUPS` wrapper-constant pattern (line 2966) | role-match |
| `n8n/code/normalizeProviders.js` (`apolloCandidates` + `zoominfoCandidates` contacts branches — new `lv_linkedin_url` push) | transform/normalizer | request-response (pure function over provider JSON) | the existing `jobtitle`/`seniority` `_push` calls immediately above, in the same two functions | exact |
| `config/field_policy.yaml` (`contacts` block — no new keys, just widened `REQUIRED` consumption) | config | CRUD (declarative policy read by two merge engines) | `lv_linkedin_url` entry already present (lines ~213-218) — the template for any new key | exact |
| `n8n/code/mergeContacts.js` (`DEFAULT_CONTACT_POLICY`) | service (pure merge/decision function) | CRUD (non-clobber merge) | its own existing 12-key table — already complete, no new keys needed | exact |

**No new files are created in this phase.** D-66-01/02/04 are all widen-in-place changes to
five files that already exist and already carry 11 of 12 the field producers. The "closest
analog" for each change is a sibling block inside the same file, which is why this table
points at line numbers rather than a different file.

## Pattern Assignments

### `scripts/build_cloud_workflows.py` — contacts `ENRICH_GATE` (line ~1292)

**Analog:** `ENRICH_CO_GATE` (companies gate, line ~2261) — proves the "wrapper holds the
list, module stays frozen" pattern generalizes across both lanes; also proves each gate is
free to carry its own `POLICY` (TTL) map independent of `REQUIRED`'s length.

**Current state to widen** (`scripts/build_cloud_workflows.py:1292`):
```javascript
const REQUIRED = ["email", "jobtitle", "mobilephone"];
const POLICY = { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } };
```

**Target shape per D-66-01** — all 12 `config/field_policy.yaml` `contacts` keys:
```javascript
const REQUIRED = [
  "city", "country", "email", "hs_country_region_code", "hs_state_code", "jobtitle",
  "lv_linkedin_url", "lv_persona_group", "mobilephone", "phone", "seniority", "state",
];
const POLICY = { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } };
```
`POLICY` stays as-is per D-66-09 — no new `stale_after_days` entries; only `jobtitle` and
`mobilephone` currently carry a TTL and D-66-09 explicitly forbids adding one to `phone`.

**Downstream coupling to prove/trace** (D-66-03, D-66-10's `lushaContactBody` note): `REQUIRED`
feeds `gate.missingFields` (via the frozen `enrichmentGate.js`, not shown here — do not
hand-edit it), which `ENRICH_BUILD_REQUESTS` (line ~2003) reads directly:
```javascript
const missingFields = (row.gate && row.gate.missingFields) || [];
const lusha_body = lushaContactEnrichByIdBody(storedContactId, missingFields)
    || lushaContactBody(id, missingFields);
```
Widening `REQUIRED` widens Lusha's reveal list automatically — no separate change needed
there, but the plan must state that this is why 3→12 changes Lusha's request body, and that
D-66-01's cost claim (flat per-contact billing) is what makes that safe.

**Regeneration is mandatory** (D-66-10): after editing the Python constant, run the builder to
regenerate `n8n/wf_*.json`. Never hand-edit the committed JSON.

---

### `scripts/build_cloud_workflows.py` — companies `ENRICH_CO_GATE` (line ~2261)

**Analog:** the contacts `REQUIRED` above (post-widening), and `config/field_policy.yaml`'s
`companies` block (14 keys: `domain`, `industry`, `numberofemployees`, `annualrevenue`,
`lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `country`, `city`,
`lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_sponsorship_reliant`,
`lv_is_hardware_vendor`, `lv_is_gambling_operator`, plus the two `veto_output`/`score_output`
fields `lv_anti_icp_flag`/`lv_anti_icp_reason` which are RECOMPUTED, never chased — exclude
those two from `REQUIRED`, same reasoning as `lv_icp_fit_score` never appearing in a contacts
`REQUIRED` list).

**Current state** (`scripts/build_cloud_workflows.py:2261`):
```javascript
const REQUIRED = ["lv_org_type", "lv_produces_content"];
const POLICY = {
  lv_org_type: { stale_after_days: 180 },
  lv_produces_content: { stale_after_days: 180 },
};
```
Widen `REQUIRED` to the promotable, non-`score_output`/`veto_output` companies keys. **Must
not disturb** (D-66-04, "must not be disturbed" list): the `RECOMPUTE_REQUESTED` /
`IF Company Recompute` wiring immediately below this block (§13.0 as-built delta) and
`MATERIAL_CONFLICT_GROUPS`/`CONFLICT_WATCH` (line 2966, in `ENRICH_MERGE_CO`/`Judge Gate`,
a different node entirely) — widening the gate's `REQUIRED` list is orthogonal to, and must
not touch, the conflict-watch lists.

---

### `n8n/code/normalizeProviders.js` — `apolloCandidates` contacts branch (D-66-02)

**Analog:** the immediately-adjacent `jobtitle`/`seniority`/`persona_group` pushes in the
same function (`n8n/code/normalizeProviders.js:405-409`):
```javascript
_push(out, "jobtitle", src, person.title, _norm(person.title), 0.6, updated);
_push(out, "seniority", src, person.seniority, _norm(person.seniority), 0.6, updated);
const persona = _personaGroup(person.departments);
_push(out, "persona_group", src, persona, _norm(persona), 0.6, updated);
```

**`_push` signature to reuse** (`n8n/code/normalizeProviders.js:171-174`):
```javascript
function _push(out, field, source, value, normalizedValue, accuracy, recencyDate) {
  if (value === null || value === undefined || value === "") return;
  out.push({ field, source, value, normalizedValue, accuracy: _clamp01(accuracy), recencyDate: recencyDate || null });
}
```

**Field key to push under (D-66-03 — load-bearing):** `"lv_linkedin_url"` — NOT
`"linkedin_url"`. `mergeContacts.js`'s `DEFAULT_CONTACT_POLICY` and `config/field_policy.yaml`
`contacts:` both key it `lv_linkedin_url`; `linkedin_url` is a DIFFERENT, unrelated spelling
used only by `required_identity.any_of`/`columnMap.js` for the identity-matching seam
(`config/column_mapping.yaml:35-38`, `n8n/code/columnMap.js:32`). Pushing under `linkedin_url`
by mistake is a silent no-op at merge — no error, nothing logs it.

**Conservative-normalizer precedent to copy** (`_codeShaped`, `n8n/code/normalizeProviders.js:42-51`)
— the existing "only emit a candidate if it's already shaped right, never coerce" model. Write
the new normalizer in the same spirit: force `https`, lowercase host, strip query/trailing
slash, refuse a non-`linkedin.com` host, return `null` (never a malformed URL) on failure —
`_push` already treats `null`/`""`/`undefined` as "no candidate," so a refusing normalizer
needs no extra guard at the call site (compare `_industryText`'s and `_personaGroup`'s own
"return null rather than fabricate," lines 181-215).

**Where the raw value lives (must confirm live shape before writing the normalizer):**
- Apollo: `person.linkedin_url` (CLAUDE.md §8.1 names `apollo_linkedin_url` as the staging
  field this pipeline already writes — confirms the raw response carries it under Apollo's
  own `linkedin_url` key on the person object, same flat-vs-`person`-nested duality as
  `person.email`/`person.title` already handled at the top of this branch).
- ZoomInfo: likely `raw.linkedInUrl` or similar camelCase — verify against a live GTM
  contacts/enrich response the same way `country`/`city`/`state` were probe-verified
  (`n8n/code/normalizeProviders.js:478-489` comment names the probe script
  `scripts/probe_zoominfo_location_fields.mjs`, the precedent for probing a new
  outputField before trusting its shape) and confirm `linkedin` (or the correct field name)
  is already in `ZOOM_OUTPUT_FIELDS` (`scripts/build_cloud_workflows.py:1848`/`4114`) —
  if absent, it must be ADDED there or ZoomInfo will never return the value at all.

**Lusha is out of scope for this push** per the CONTEXT: only Apollo and ZoomInfo are named
as returning a LinkedIn URL (D-66-02); Lusha's contacts branch (`n8n/code/normalizeProviders.js:271-374`)
needs no new push unless a live sample later proves otherwise.

---

### `config/field_policy.yaml` — `contacts` block

**No new key required.** `lv_linkedin_url` (lines ~213-218) already exists at
`fill_blank_only` / `min_confidence: 85` / `protect_if_current_present: true` — this is
purely a "verify, do not touch" file for this phase. Use its existing shape as the template
if the plan needs to reference the target policy for any of the 12 fields:
```yaml
lv_linkedin_url:
  class: fill_blank_only
  promote_to_canonical: true
  min_confidence: 85
  protect_if_current_present: true
```

---

### `n8n/code/mergeContacts.js` — `DEFAULT_CONTACT_POLICY`

**No new key required** — already carries all 12 keys (lines 47-59), including
`lv_linkedin_url: { class: "fill_blank_only", min_confidence: 85 }`. Confirm this table and
`config/field_policy.yaml`'s `contacts` block stay in parity (same discipline as the
`system_correctable_sources`/`DEFAULT_COMPANY_POLICY` parity note at
`config/field_policy.yaml:16-19`, enforced by `tests/test_field_policy_conformance.py`) — if
that conformance test exists for contacts too, it is the regression gate for this file; if it
does not, the plan should note the gap rather than invent a new test file speculatively.

---

## Shared Patterns

### The wrapper-constant / frozen-module split
**Source:** `scripts/build_cloud_workflows.py` — `ENRICH_GATE`'s `REQUIRED` (contacts) and
`ENRICH_CO_GATE`'s `REQUIRED` (companies), and separately `CONFLICT_WATCH`/
`MATERIAL_CONFLICT_GROUPS` (line 2966).
**Apply to:** both `REQUIRED` edits in this phase.
```javascript
// The wrapper (builder) owns the list. The inlined module (n8n/code/enrichmentGate.js) is
// frozen and contains no REQUIRED constant at all — same shape CONFLICT_WATCH uses for the
// companies conflict-watch list.
const REQUIRED = [ /* ...full field_policy.yaml key list... */ ];
```
Never move this list into `n8n/code/enrichmentGate.js` — that module is shared/frozen and the
CONTEXT explicitly calls this out (D-66-10).

### Regenerate, never hand-edit
**Source:** every `n8n/wf_*.json` file, `scripts/build_cloud_workflows.py` module docstring.
**Apply to:** both gate edits and the normalizeProviders.js edit — all three land in the
Python source, then `python scripts/build_cloud_workflows.py` (or the project's documented
build invocation) regenerates the committed JSON. Committing hand-edited JSON is the single
most repeated prohibition in this codebase (CLAUDE.md §13.0.2, §13.0.3, this file's own
CONTEXT §"Established Patterns").

### Phase 46 parity rule — checked, not applicable here
**Source:** `src/judge.py`'s `JUDGE_OUTPUT_REQUIRED` is the only Python-side `REQUIRED`-shaped
constant found; it is unrelated (judge output keys, not a chased-field gate list). No Python
oracle carries an equivalent contacts/companies gate `REQUIRED` list — `grep -rn "REQUIRED\s*="
src/*.py` returns only `judge.py`. **The plan should state this explicitly**: there is nothing
in `src/` to move in the same commit for D-66-01/D-66-02, so the Phase 46 parity rule is
satisfied vacuously for this specific change (D-66-10 asks to "check," and the check comes up
empty).

### Deliberate-drop comment style
**Source:** `n8n/code/normalizeProviders.js:400-401` (Apollo phone loop):
```javascript
const norm = normalizePhone(p.sanitized_number, region);
if (!norm) continue; // null-drop: un-normalizable phone never reaches HubSpot
```
**Apply to:** the new LinkedIn normalizer's refusal branch — comment the non-`linkedin.com`-host
refusal the same way, so it reads as intentional rather than as a bug to "fix" later.

## No Analog Found

None. Every file this phase touches already contains the pattern to extend (a sibling
`_push` call, a sibling `REQUIRED` array, an existing policy-table row). This is a widening
phase, not a new-construction phase — RESEARCH.md was correctly skipped for this reason.

## Test Analogs

- `node --test tests/n8n/*.test.mjs` (glob form only — the bare-directory form is broken on
  Node 24, per repo-wide standing note). Closest existing test files to extend/mirror:
  - `tests/n8n/enrichmentGate.test.mjs` — gate `REQUIRED`/`missingFields` behavior; the file
    to extend when `REQUIRED` widens (assert the new fields appear in `missingFields` when
    blank, and that `lushaContactBody`'s reveal list grows accordingly).
  - `tests/n8n/normalizeProviders.test.mjs` — the file to extend with an
    Apollo/ZoomInfo-linkedin fixture case, mirroring however the existing jobtitle/seniority
    cases are asserted.
  - `tests/n8n/providerConflict.test.mjs` and `tests/n8n/materialConflictNoVetoFlip.test.mjs` —
    regression proof that widening `ENRICH_CO_GATE`'s `REQUIRED` does NOT touch
    `CONFLICT_WATCH`/`MATERIAL_CONFLICT_GROUPS` behavior (D-66-04's "must not disturb").
- `.venv/bin/python -m pytest` for anything touching `config/field_policy.yaml` or
  `src/merge_policy.py` parity, though this phase's D-66-10 check found no Python-side
  `REQUIRED` list to update — the Python suite here is a regression check, not an edit target.

## Metadata

**Analog search scope:** `scripts/build_cloud_workflows.py`, `n8n/code/normalizeProviders.js`,
`n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `n8n/code/providerConflict.js`,
`config/field_policy.yaml`, `config/column_mapping.yaml`, `n8n/code/columnMap.js`, `src/*.py`,
`tests/n8n/*.test.mjs`.
**Files scanned:** 10 (grep + targeted Read; no full-file loads over ~600 lines, non-overlapping
ranges throughout).
**Pattern extraction date:** 2026-09-05
