# Phase 72: Enrichment extras land in HubSpot - Pattern Map

**Mapped:** 2026-09-12
**Files analyzed:** 12 (files to modify)
**Analogs found:** 12 / 12 (all changes are widenings/extensions of existing code, not new-file creation)

All paths below are verified git-tracked (`git ls-files`). No files in this phase are net-new;
every change is a modification to an existing module, and the "analog" for each is the sibling
lane/engine that already implements the target shape.

## File Classification

| File to Modify | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `config/column_mapping.yaml` | config | transform (CSV header→canonical key) | itself, widened (12-key union) | exact — self-analog |
| `n8n/code/columnMap.js` | utility (n8n Code node) | transform | `config/column_mapping.yaml` (JS mirror) | exact |
| `scripts/build_cloud_workflows.py` (`MERGE_CONTACTS`, ~L395-421) | controller (workflow-JSON generator, candidate assembly) | CRUD (build create/update candidate) | `ENRICH_MERGE` in same file (~L1958-1980) | exact — same generator, sibling wrapper |
| `n8n/code/mergeContacts.js` (`_gate`, `stale_refreshable` branch) | service (deterministic merge/gate) | CRUD (promote/stage/reject decision) | `n8n/code/mergeCompanies.js`'s equivalent branch + `src/merge_policy.py` | exact — Phase 46 parity triplet |
| `n8n/code/mergeCompanies.js` (`_gate`, `_isSystemCorrectable`) | service | CRUD | `mergeContacts.js` (contacts side of same predicate) | exact — Phase 46 parity triplet |
| `src/merge_policy.py` (`deterministic_gate`) | service (Python oracle) | CRUD | the two JS engines above | exact — Phase 46 parity triplet |
| `n8n/code/normalizeProviders.js` (company branches) | transform (per-provider normalizer) | transform | contacts branches of the same file (already produce geo/mobile/seniority) | role-match — same file, sibling object-type branch |
| `operator-claude-plugin/scripts/preingest.py` (`merge_enriched`) | service (pre-dispatch CSV merge) | CRUD (fill-not-overwrite) | itself — existing fill-not-overwrite rule, extended | exact — self-analog |
| `operator-claude-plugin/scripts/extraction.py` (`canonical_props`) | utility (config-derived allowlist) | transform | `preingest.promotable_contact_props()` (identical derivation pattern) | exact |
| `config/field_policy.yaml` | config | — | itself, add company geo/phone classes mirroring contact entries | exact |
| `config/hubspot_properties.yaml` + `scripts/sync_hubspot_properties.py` | config + operator tool (schema migration) | batch (idempotent property create) | `scripts/set_named_account_score_floor.py` (`--plan/--execute/--verify` shape) | role-match |
| `scripts/bounce_n8n_workflows.py` | utility (operator tool) | request-response (n8n API) | `scripts/deploy_n8n_workflows.py`'s existing `--only` flag | exact — same script pair, one has the feature the other lacks |

## Pattern Assignments

### `config/column_mapping.yaml` + `n8n/code/columnMap.js` (config, transform)

**Analog:** each other (YAML is source, JS is the generated/mirrored consumer), pinned by
`tests/n8n/columnMapIdentityParity.test.mjs`.

**Current identity-groups shape** (`config/column_mapping.yaml`):
```yaml
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
    - [linkedin_url]
```
Widen the `aliases:` map the same way — add the header aliases for `mobile→mobilephone`,
`city`, `state`, `country`, `hs_state_code`, `hs_country_region_code`, `seniority`,
`lv_persona_group` (exact diff to be computed at plan time via
`set(promotable_contact_props()) - set(canonical_props())`, per RESEARCH.md Open Question 1).
**Never hardcode the widened list in JS or Python** — both `columnMap.js` and `extraction.py`
read the same YAML at call time.

**Parity-test idiom to extend** (`tests/n8n/columnMapIdentityParity.test.mjs`): drives the JS
module from a Python-oracle subprocess reading the same YAML, never restates values in JS.
Reuse this idiom for a third dimension (field_policy's 12-key list vs both YAML/JS), per
RESEARCH.md's "Don't Hand-Roll" table — do not invent a fourth comparison mechanism.

**LinkedIn naming fork (D-72-04) — resolve inside `merge_enriched`, not the YAML:**
CSV canonical name is `linkedin_url`; waterfall's promotable name is `lv_linkedin_url` — two
different strings. Recommended fix (RESEARCH.md "Fork 1", Option B, smallest diff): a one-entry
alias table inside `preingest.merge_enriched`'s per-field loop —
`{"lv_linkedin_url": "linkedin_url"}` — checked before the `allowed_keys` filter. This changes
zero config files and keeps every existing `row.linkedin_url` read in the ingest lane working.
The lane already correctly maps the `linkedin_url` header to `lv_linkedin_url` for the
CANONICAL write; add `hs_linkedin_url` as a second native property landed alongside it (D-72-04)
at the same write site the lane already uses for `lv_linkedin_url`.

---

### `scripts/build_cloud_workflows.py` — `MERGE_CONTACTS` widening (controller, CRUD)

**Analog:** `ENRICH_MERGE` in the same file — the enrichment lane already builds the exact
widened candidate set this phase asks the ingest lane to match.

**Current (narrow) candidate assembly — the thing to widen** (`MERGE_CONTACTS`, ~L395-421):
```javascript
return $input.all().map((it) => {
  const row = it.json;
  const sourceByField = row.source_by_field || {};
  const candidate = {};
  for (const f of ["email", "firstname", "lastname", "jobtitle", "company"]) {
    if (row[f] != null && String(row[f]).trim() !== "") candidate[f] = row[f];
  }
  if (row.linkedin_url != null && String(row.linkedin_url).trim() !== "") {
    candidate.lv_linkedin_url = row.linkedin_url;
  }
  if (row.phone_normalized) candidate.phone = row.phone_normalized;
  const merged = mergeContacts({}, candidate, undefined,
    { source: "csv", confidence: 80, sourceByField });
  return { json: { ...row, merge: merged } };
});
```

**Pattern to copy — the enrichment lane's already-wide loop** (`ENRICH_MERGE`, ~L1958-1980):
```javascript
const winners = row.scored.winners || {};
const candidate = {};
for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority",
                  "city", "state", "country", "hs_state_code", "hs_country_region_code"]) {
  if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
}
const canonicalWinnerLinkedin = canonicalizeLinkedin(winners.linkedin_url);
if (canonicalWinnerLinkedin) candidate.lv_linkedin_url = canonicalWinnerLinkedin;
if (winners.persona_group != null && String(winners.persona_group).trim() !== "") {
  candidate.lv_persona_group = winners.persona_group;
}
const merged = mergeContacts(row.existingRecord || {}, candidate, undefined,
                             { source: "waterfall", confidence: 85 });
```

**Apply:** widen `MERGE_CONTACTS`'s `for (const f of [...])` loop to the same field list,
reading from `row.*` (CSV-sourced) instead of `winners.*` (waterfall-sourced). No change to
`mergeContacts()` itself is required — it already knows how to gate every one of these fields.
**Never hand-edit `n8n/wf_*.json`** — regenerate via `scripts/build_cloud_workflows.py`.

**Company-side candidate loop** (Merge Company, ~L3796-3860) needs the equivalent widening for
`state`, `hs_state_code`, `hs_country_region_code`, `phone` once producers exist in
`normalizeProviders.js` (see below) — analog is the same file's contacts loop above.

---

### `n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `src/merge_policy.py` — recency/TTL gate (service, CRUD)

**Analog:** each other — Phase 46 parity rule requires any predicate change lands in all
three, one commit.

**Current blanket-refusal gap — identical shape in all three, quote exact, not paraphrase**
(`n8n/code/mergeContacts.js:141-146`; byte-identical in `mergeCompanies.js:217-222` and
`src/merge_policy.py`'s `deterministic_gate` ~L240-249):
```javascript
if (fieldClass === "stale_refreshable") {
  if (_isBlank(currentValue)) {
    return { decision: "promote", reason: "Current value blank and candidate passed threshold." };
  }
  return { decision: "needs_review", reason: "Refresh candidate requires review in MVP." };
}
```
This is a genuinely new build (no TTL/staleness check exists anywhere in the gate today),
budget it as new logic, not a tweak (RESEARCH.md Pitfall 3).

**Pattern to generalize for D-72-08 (system-correctable extended to provider sources)** —
`n8n/code/mergeCompanies.js:167-176`:
```javascript
function _isSystemCorrectable(policy, entry, currentValue, rowConflicted) {
  const sources = policy && policy.system_correctable_sources;
  if (!Array.isArray(sources) || sources.length === 0) return false;
  if (!entry || typeof entry !== "object") return false;
  if (sources.indexOf(entry.source) === -1) return false;
  if (_isBlank(entry.value) || _isBlank(currentValue)) return false;
  if (String(entry.value) !== String(currentValue)) return false;
  return rowConflicted === false;
}
```
This is currently company-only and `manual_protected`-only (backing §17.2.1's `domain`
clause). D-72-08 needs the same four-conjunct shape (provenance entry still matches current
value; no material conflict; source on an allow-list; min_confidence met) generalized to
provider sources on `stale_refreshable`/`system_owned` fields, in all three engines.

**Provenance write sites to extend** (D-72-13, provenance-JSON-only stamping — two DIFFERENT
property keys, do not conflate):
- Contacts: `lv_contact_enrichment_provenance` — write site
  `scripts/build_cloud_workflows.py:450`: `patch.lv_contact_enrichment_provenance = _stableStringify(merge.provenance).slice(0, 60000);`
  Entry shape (`n8n/code/mergeContacts.js:220-224`):
  ```javascript
  const entry = { source: resolvedSource, confidence, verified_at: verifiedAt,
                  validation_status: validationStatus, value };
  if (!_isBlank(evidenceUrl)) entry.evidence_url = evidenceUrl;
  ```
- Companies: `lv_enrichment_provenance` — write site
  `scripts/build_cloud_workflows.py:4277`: `properties.lv_enrichment_provenance = stableStringify(outgoingProvenance).slice(0, 60000);`
- Python oracle constants: `src/merge_policy.py:40-41` —
  `COMPANY_PROVENANCE_KEY = "lv_enrichment_provenance"` / `CONTACT_PROVENANCE_KEY = "lv_contact_enrichment_provenance"`.

**D-72-12 winner/loser-to-`_2`-slot routing** — reuse `choose_best()`/trust-rank sort
(`config/source_registry.yaml`'s `trust_rank`, already used by all three engines' priority-order
sort) — the loser by the SAME sort routes to the `_2` slot instead of being discarded. No new
ranking mechanism (RESEARCH.md "Don't Hand-Roll").

---

### `n8n/code/normalizeProviders.js` — company geo/phone producers (transform)

**Analog:** the contacts branches of the same file, which already produce every one of these
shapes for contacts.

**Contact `city`/`state`/`country` + code producer to mirror** (Lusha branch,
`n8n/code/normalizeProviders.js:330-338`):
```javascript
// city/state/country pushed directly; hs_country_region_code from a dedicated country_iso2
// field; hs_state_code only if the raw value is already code-shaped
```
**Company gap this phase must close (or explicitly accept as a no-producer gap):** company
branches currently push only `country`/`city` (58-05) — no `state`, no `hs_state_code`/
`hs_country_region_code`, no `phone`, no second domain, for any of the three providers. Before
writing producer code, confirm at plan time that a live provider response actually carries
the value (ZoomInfo GTM company enrich requests no `city` outputField either — precedent for a
field simply never being asked for). If no live producer exists, document the gap the same way
the pre-existing company-`domain` gap is documented
(`.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md`) rather than
shipping a policy entry with zero reachable producers.

---

### `operator-claude-plugin/scripts/preingest.py` — `merge_enriched` / `strip_enrichment_extras` (service, CRUD)

**Analog:** itself — the existing fill-not-overwrite rule, extended for D-72-05's CREATE-time
"provider wins except identity" behavior.

**`strip_enrichment_extras` — confirms it becomes a no-op by construction, needs zero edit**
(`operator-claude-plugin/scripts/preingest.py:917-921`):
```python
def strip_enrichment_extras(rows, policy_path=None) -> list[dict]:
    extras = set(promotable_contact_props(policy_path)) - set(extraction.canonical_props())
    return [{k: v for k, v in row.items() if k not in extras} for row in rows]
```
Once `column_mapping.yaml`'s aliases cover the same 12 keys, `extras` is the empty set and this
function is inert — no code change needed here, only the YAML (config-derived-allowlist
pattern, never a restated literal — see below).

**`merge_enriched`'s CREATE-time rule (D-72-05)** needs new logic: provider wins over CSV for
non-identity fields (`email`/`firstname`/`lastname`/`company` stay CSV-supplied), and the CSV
value is recorded in the merge report's existing `conflicts` list (a `MergeResult.conflicts`
tuple already exists per RESEARCH.md "Fork 2" — extend that, do not add a new
`source_values` key to the held-row entry, which would touch the carried-forward
D-71-04/05 held-entry schema).

**Pattern: config-derived allowlist, never a restated literal** — `extraction.canonical_props()`
(`operator-claude-plugin/scripts/extraction.py:162-167`):
```python
def canonical_props(mapping_path=None) -> list[str]:
    data = _load_mapping(mapping_path)
    aliases = dict(data.get("aliases") or {})
    return sorted(set(aliases.values()))
```
Any new field this phase adds must go into `config/field_policy.yaml` and/or
`config/column_mapping.yaml`, never into a Python/JS literal — this is the exact pattern
`promotable_contact_props()` and `refreshable_contact_props()` already follow.

---

### `config/hubspot_properties.yaml` + `scripts/sync_hubspot_properties.py` (config + operator tool, batch)

**Analog:** `scripts/set_named_account_score_floor.py` — the repo's established
`--plan/--execute/--verify` operator-tool shape, and `sync_hubspot_properties.py` itself,
which already IS the idempotent forward-migration tool for exactly this job (property
creation, env-gated, diff-then-create-missing-only).

**Use instead of hand-rolling a new script:** add 3 property declarations to
`config/hubspot_properties.yaml` (`lv_phone_2`, `lv_mobilephone_2` on contacts;
`lv_phone_2` on companies) and run the existing `sync_hubspot_properties.py` — it already
inherits dry-run/portal-guard/idempotency behavior. Gate with the same two-key idiom
(`DRY_RUN=false` AND a dedicated `ALLOW_*` flag) — never reuse `ALLOW_N8N_ARM` for a HubSpot
schema write (a different privilege boundary, per RESEARCH.md Security Domain).

**Before building:** live-verify `hs_additional_emails` (contacts) and `hs_additional_domains`
(companies) writability via `GET /crm/v3/properties/{object}/{prop}` and inspect
`modificationMetadata.readOnlyValue` — both are absent from this repo's 2026-08-26 property
export despite CONTEXT.md's later live-verified claim (RESEARCH.md Pitfall 1, Pitfall 4).
Also confirm `hs_country_region_code` exists on companies at all (absent from both the export
and CONTEXT.md's company-props list) before scoping the company half of D-72-15.

---

### `scripts/bounce_n8n_workflows.py` (utility, request-response)

**Analog:** `scripts/deploy_n8n_workflows.py`, which already has the `--only <filename>` flag
this script lacks (deploy script ~L575).

**Gap:** `bounce_n8n_workflows.py` hardcodes all 5 workflow ids in one `WORKFLOWS` dict
(~L23) and bounces every one unconditionally — no per-workflow selector. D-72-18 scopes
deploy+bounce to `wf_contact_ingest_cloud` only. Mirror the deploy script's existing `--only`
flag onto the bounce script (small, low-risk addition), or explicitly accept "bounce all
five, content diff-clean on four" as the phase's approach and confirm the diff-clean claim by
actually running `scripts/build_cloud_workflows.py` and diffing before bouncing (not by
skipping the regenerate step).

## Shared Patterns

### Config-derived allowlist, never a restated literal
**Source:** `operator-claude-plugin/scripts/extraction.py:162-167` (`canonical_props`),
mirrored by `preingest.promotable_contact_props()`/`refreshable_contact_props()`.
**Apply to:** every file in this phase that reads "which fields are widened" — YAML/JS/Python
must all derive from `config/field_policy.yaml` and `config/column_mapping.yaml` at call time.
Never add a second hardcoded array anywhere (this is exactly the drift class RICH-04's
original bug came from, per `preingest.py`'s own `dropped_property_keys` comment).

### Single shared merge function called from two lanes
**Source:** `mergeContacts()`/`mergeCompanies()`, called from both `MERGE_CONTACTS` (ingest
lane) and `ENRICH_MERGE`/`ENRICH_CO_GATE` (enrichment lane) wrappers in
`scripts/build_cloud_workflows.py`.
**Apply to:** any policy-shape change (new field class, new gate branch — i.e. the recency
fix) belongs in the shared function and benefits both lanes for free. Any change to WHICH
fields a lane offers as candidates belongs in that lane's own wrapper only.

### Phase 46 parity rule (three-engine mirror)
**Source:** `n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `src/merge_policy.py`.
**Apply to:** D-72-06..09 (recency), D-72-08 (system-correctable extension), D-72-12
(winner/loser routing) — any predicate change lands in all three files in one commit, with a
shared fixture/test vector exercised against all three (mirrors
`tests/test_field_policy_conformance.py`'s existing cross-check pattern).

### Disarmed deploy + one backloaded live gate
**Source:** `scripts/deploy_n8n_workflows.py` / `scripts/bounce_n8n_workflows.py`, and the
project memory `backload-human-gates-to-end-of-phase`.
**Apply to:** D-72-17/18 — every write in this phase (property creation, workflow deploy) is
env-gated and dry-run-by-default; the single armed live gate (re-run one held person through
create, read the contact back) is the phase's last task, per operator ruling 2026-09-09.

## No Analog Found

None — every file in this phase modifies existing, git-tracked code with a working sibling
pattern elsewhere in the repo (the enrichment lane for the ingest-lane widening; the contacts
branches of `normalizeProviders.js` for the company producers; `set_named_account_score_floor.py`
for the property-creation tool shape; `deploy_n8n_workflows.py` for the bounce script's missing
flag).

## Open Forks the Planner Must Resolve (not pattern gaps, decision gaps)

1. **`linkedin_url`/`lv_linkedin_url` naming fork** — Option B (rename inside
   `merge_enriched`, one-entry alias table) recommended over Option A (new canonical CSV
   column cascading into `required_identity`). See "column_mapping.yaml" section above.
2. **`source_values` on the held row vs. "held-entry keys ... untouched"** — recommend keeping
   the CSV-vs-provider conflict in the merge report's existing `conflicts` list only, never as
   a new persisted held-row key, to avoid touching the carried-forward D-71-04/05 schema.

## Metadata

**Analog search scope:** `n8n/code/`, `scripts/build_cloud_workflows.py`, `src/merge_policy.py`,
`operator-claude-plugin/scripts/`, `config/`, `tests/n8n/`.
**Files scanned:** 16 (all confirmed git-tracked via `git ls-files`).
**Pattern extraction date:** 2026-09-12
**Note:** Every code excerpt in this document is copied verbatim from 72-RESEARCH.md, which
cites exact file:line ranges read live this session — no additional file reads were needed to
confirm the excerpts themselves; this file adds classification, analog-pairing, and the
"where to copy from" framing RESEARCH.md's structure does not provide directly.
