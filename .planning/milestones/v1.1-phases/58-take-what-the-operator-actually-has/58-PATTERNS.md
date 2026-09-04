# Phase 58: Take What the Operator Actually Has - Pattern Map

**Mapped:** 2026-08-26
**Files analyzed:** ~9 (new + modified, per CONTEXT.md/RESEARCH.md's Wave 0 gap list)
**Analogs found:** 9 / 9 (all in-repo; RESEARCH.md already did the analog search — this maps
its findings to concrete excerpts)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/config/company_column_mapping.yaml` (new) | config | CRUD (identity-rule lookup) | `operator-claude-plugin/config/column_mapping.yaml` | exact — same shape, new file |
| `operator-claude-plugin/scripts/extraction.py` (extend) | utility/validator | transform | itself, `canonical_props()`/`identity_groups()` (lines 113-126) | exact — extend in place |
| `operator-claude-plugin/skills/contact-upload/extraction.md` (extend) | config (prose contract) | transform | itself, adapter sections | exact — extend in place |
| `operator-claude-plugin/scripts/company_preingest.py` (new) — domain confirm/decline | service | request-response | `operator-claude-plugin/scripts/preingest.py` `apply_match_decisions`/`DECLINE_MATCH` (lines 349-429) | exact — same shape, new object type |
| `operator-claude-plugin/scripts/enrichment.py::build_envelope` companies branch (extend) | service | request-response | itself (lines 322-367) | exact — extend in place |
| `operator-claude-plugin/config/cost_rates.json` (extend) | config | CRUD | itself (rate entries) | exact — add one entry |
| `operator-claude-plugin/scripts/cost_guard.py` (extend, new declinable-line concept) | service | request-response | itself, `compare()` tri-state discipline | role-match — new mechanism on existing discipline |
| `scripts/build_cloud_workflows.py` — `researchSystemPrompt()`/`required_fields` (conditional, pending Task-1 spike) | config (workflow generator) | request-response | itself, `COMPANIES_TARGET` gap predicate + research payload builder (lines ~2333-2397) | exact — extend in place, IF spike confirms it's needed |
| `n8n/code/webResearch.js::validateResearchOutput` (no change expected — verify only) | transform | transform | itself (lines 21-64) | exact — read-only verification target |

## Pattern Assignments

### `operator-claude-plugin/config/company_column_mapping.yaml` (config, CRUD)

**Analog:** `operator-claude-plugin/config/column_mapping.yaml` (full file, 57 lines)

**Full shape to copy:**
```yaml
# One source of truth for company ingestion:
#   aliases:           lowercased/trimmed source header -> canonical HubSpot company prop
#   required_identity: the reject rule (name alone, per D-58-11)

aliases:
  name: name
  "company name": name
  organization: name
  organisation: name
  domain: domain
  website: domain
  "website url": domain
  country: country
  industry: industry

required_identity:
  any_of:
    - [name]
```
Note: contact mapping's `required_identity.any_of` has two groups (`[email]`,
`[firstname, lastname, company]`); company's per D-58-11 needs only one group, `[name]`.
`identity_groups()`/`has_identity()` (extraction.py:121-143) already handle a single-group
list with no code change — this is a config-only file for the identity rule itself.

---

### `operator-claude-plugin/scripts/extraction.py` (utility/validator, transform)

**Analog:** itself — `canonical_props()`/`identity_groups()` (lines 113-126), `_load_mapping`
signature already takes `mapping_path=None`.

**Reuse point — read mapping path by type, not by hardcoded default:**
```python
def canonical_props(mapping_path=None) -> list[str]:
    """The 7 canonical contact props: the deduplicated VALUES of column_mapping.yaml's
    `aliases` map, in a deterministic (sorted) order. Never a literal in this file."""
    data = _load_mapping(mapping_path)
    aliases = dict(data.get("aliases") or {})
    return sorted(set(aliases.values()))
```
Both `canonical_props()` and `identity_groups()` already accept an explicit
`mapping_path` parameter — this is the existing extension point. Per RESEARCH.md Pitfall 2,
do NOT retrofit a flat multi-type YAML; add a `record_type`/`object_type` discriminator on
the artifact (per adapter row) and call `canonical_props(mapping_path=COMPANY_MAPPING_PATH)`
/ `identity_groups(mapping_path=COMPANY_MAPPING_PATH)` for company rows, keeping
`extraction.py`'s core mechanisms (`dedupe()`, `_compare_identity()`, D-07 contradiction
check — lines 138-338) untouched: RESEARCH.md verified these are identity-group-driven with
no field-name assumption baked in, so they extend to companies with zero rewrite once a
company-scoped `identity_groups()` call is threaded through per-row.

**`_present()`/`has_identity()` — reuse verbatim, no changes** (lines 129-143).

---

### `operator-claude-plugin/scripts/company_preingest.py` (service, request-response — new file)

**Analog:** `operator-claude-plugin/scripts/preingest.py::apply_match_decisions` +
`DECLINE_MATCH` sentinel (lines 349-429).

**Sentinel pattern to copy:**
```python
# The sentinel a `resolved` entry uses to decline a proposal — never a real HubSpot
# object id (the backend's own candidate ids are numeric strings), so it can never
# collide with a genuine candidate.
DECLINE_MATCH = "decline"
```
For the domain-confirm lane, reuse this exact sentinel-value shape for a row's domain
decision (`confirm` / `DECLINE_MATCH` / an operator-typed replacement domain string).

**Validate-then-apply-atomically pattern (the reusable asset, per RESEARCH.md) — copy this
two-pass structure exactly:**
```python
    # Validation pass — every entry in `resolved` is checked against both guards
    # BEFORE anything below is built. ... an entry validated only as it is applied lets
    # an earlier valid entry take effect before a later invalid one is even seen, which
    # is exactly the half-applied set this guards against.
    for row_id, decision in resolved.items():
        entry = proposed_by_id.get(row_id)
        if entry is None:
            raise MatchDecisionError(...)
        if decision == DECLINE_MATCH:
            continue
        candidate_ids = {c.get("hs_object_id") for c in entry.get("candidates", [])}
        if decision not in candidate_ids:
            raise MatchDecisionError(...)

    # Apply pass — reached only once every entry above has passed both guards. Every
    # list below is a FRESH copy; nothing from `classified` is appended to in place.
    ...
```
For the domain-confirm module: candidate set is a single proposed domain per row (not a
HubSpot search's `candidates` list) — the "candidate_ids" guard becomes "is the confirmed
value the SAME value that was proposed, or an explicit operator-typed override that passes
`_clean_domain`". A row absent from `resolved` stays unconfirmed — never defaulted (mirrors
line 361's "never picks a candidate on the operator's behalf"). A declined row falls back to
name-only per D-58-06, exactly as `apply_match_decisions` moves a declined row to
`unmatched` "so it is picked up by enrichment like any other no-match row."

**Pure function discipline (docstring pattern to copy):**
```python
    """... Pure — no I/O, no network. Returns a NEW classification; `classified` and its
    own list/dict values are never mutated in place, so a refused call (raise) leaves the
    caller's own copy exactly as it was."""
```

---

### `operator-claude-plugin/scripts/enrichment.py::build_envelope` companies branch (service, request-response)

**Analog:** itself, lines 322-367 (already exists, 0.16.0-shipped) — extend, don't
reinvent.

**Refusal-names-the-fix pattern (INPUT-04, already implemented — copy this style for new
adapter refusals):**
```python
            if not domain and not name:
                given = str(company.get("domain") or company.get("website") or "").strip()
                raise RecordSpecError(
                    f"{given!r} is a profile page rather than a company's own website, and "
                    f"no company name came with it, so there is nothing to look up. Give "
                    f"the company's name — the backend can match that on its own."
                    if given else
                    "A company was given with neither a name nor a website domain, so "
                    "there is nothing to look up."
                )
```

**`NOT_A_COMPANY_DOMAIN` guard — reuse verbatim, never weaken (D-58-03):**
```python
NOT_A_COMPANY_DOMAIN = frozenset({
    "linkedin.com", "lnkd.in", "facebook.com", "fb.com", "instagram.com", "twitter.com",
    "x.com", "youtube.com", "youtu.be", "tiktok.com", "threads.net", "medium.com",
    "crunchbase.com", "wikipedia.org", "en.wikipedia.org", "bloomberg.com", "zoominfo.com",
    "apollo.io", "abn.business.gov.au", "linktr.ee", "about.me", "sites.google.com",
    "wixsite.com", "squarespace.com", "godaddysites.com",
})
```
Byte-identical to `n8n/code/companyLink.js:47-53` — any change updates both files in one
commit (project convention, per CLAUDE.md §10.3.1 parity rule).

**Mode-passthrough extension point (for the Task-1 spike, D-58-01/D-58-02):** the companies
branch currently builds `event = {"objectType": "companies"}` and conditionally adds
`domain`/`name` (lines 360-365). Per RESEARCH.md, adding `event["mode"] = "propose"` here
(mirroring the `rows` form's `envelope["mode"] = "propose"` at line 265) is the cheapest
lever for "research without writing" — IF the live spike confirms an unrecognized `mode` key
survives to `Decide Company Action` server-side.

---

### `operator-claude-plugin/scripts/cost_guard.py` (service, request-response)

**Analog:** itself — `compare()` tri-state discipline and `config/cost_rates.json`'s rate
entry shape.

**Rate entry shape to copy (`config/cost_rates.json`):**
```json
"claude_web_domain_research": {
  "value": null,
  "unit": "usd_per_company",
  "citation": "no measured rate exists yet — measure live before disclosing as anything but confidence: unknown",
  "confidence": "unknown"
}
```
`value: null` is the existing convention for "genuinely unknown, never render as zero"
(RESEARCH.md, cost_rates.json:1-35) — do not fabricate a number for domain-only research.

**Tri-state discipline to inherit, not reinvent:** readability-before-magnitude in
`compare()` — a domain-research cost line is disclosure-only (no balance-check exists for
Anthropic spend), same posture as the existing GRANT-02 ceiling disclosure.

**New mechanism needed (no existing analog — build per `DECLINE_MATCH`'s sentinel shape):**
a per-row research decision defaulting to `"research"` (D-58-09 default-on) with a
`DECLINE_MATCH`-shaped opt-out value, not a whole-capability admin toggle
(`config_gate.py`'s pattern is the wrong shape here per RESEARCH.md Pitfall/finding).

---

### `scripts/build_cloud_workflows.py` — research prompt/schema extension (config/workflow generator, request-response) — CONDITIONAL on Task-1 spike outcome

**Analog:** itself — `COMPANIES_TARGET` gap predicate and research payload builder.

**Existing schema to extend (no domain field today):**
```python
# required_fields sent to the model — no domain/website field present:
["lv_org_type", "lv_produces_content", "lv_content_type", "lv_is_hardware_vendor",
 "lv_is_gambling_operator", "lv_sponsorship_reliant", "lv_country_region_normalized"]
```
If the spike shows domain research needs a real prompt/schema change (RESEARCH.md's
"Conclusion, stated plainly"): add `domain`/`website` to `required_fields` and to
`researchSystemPrompt()`'s literal schema string, following the exact same
`{"data":{...}}` shape already used for the other seven fields. This requires the standing
build→deploy→bounce→live-disarmed-proof cycle (n8n-stored-vs-running-content.md project
memory) — never a hand-edit of `n8n/wf_*.json`.

---

### `n8n/code/webResearch.js::validateResearchOutput` (transform) — verification only, likely no change

**Analog:** itself, lines 21-64.

**Why no change is likely needed — the wholesale spread already carries an unknown field
through:**
```javascript
const data = { ...(raw.data || {}) };
```
This spreads `raw.data` before the five named-field normalizations run — an added
`domain`/`website` key would survive untouched. Confirm this live in Task 1 rather than
re-deriving it; RESEARCH.md already traced it from source.

---

## Shared Patterns

### No-invention rule (extraction contract)
**Source:** `operator-claude-plugin/skills/contact-upload/extraction.md` lines 10-34
**Apply to:** every new company adapter (bare-name list, search-results screenshot) and any
Claude-side domain proposal (D-58-01) — never fill a blank from world knowledge, ambiguous
values go in the ambiguity list, never invent a value to pass the identity check.

### Validate-then-apply-atomically
**Source:** `operator-claude-plugin/scripts/preingest.py::apply_match_decisions` (lines
349-429)
**Apply to:** the new domain confirm/decline decision-application function — every entry in
the resolved-decisions dict is checked against both guards before ANY decision is applied.

### Domain-cleaning guard parity (Python ↔ JS)
**Source:** `operator-claude-plugin/scripts/enrichment.py::_clean_domain` /
`NOT_A_COMPANY_DOMAIN` (lines 159-194) mirrored in `n8n/code/companyLink.js`
**Apply to:** any new code path that ever assigns a value to a `domain` field — must pass
through `_clean_domain` (Python) or `cleanCompanyDomain` (JS), never a direct assignment
from a LinkedIn/social host.

### Refusal names the fix (INPUT-04)
**Source:** `operator-claude-plugin/scripts/enrichment.py::build_envelope` companies branch,
lines 348-359
**Apply to:** every new adapter's refusal path and the research-declined fallback message.

### Tri-state cost disclosure (readability before magnitude)
**Source:** `operator-claude-plugin/scripts/cost_guard.py::compare()` (lines 212-254)
**Apply to:** the new domain-research envelope line — `unknown`/`insufficient`/`ok`, never a
defaulted number for an unmeasured rate.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Declinable-cost-line mechanism (new concept inside `cost_guard.py`) | service | request-response | RESEARCH.md confirms exhaustive grep found no "strike this line" primitive anywhere in the plugin — design new, modeled on `DECLINE_MATCH`'s sentinel shape, not a config-toggle shape. |
| Live confirmation that an unrecognized `mode` key survives the companies webhook's initial parse to `Decide Company Action` | — | — | Traced from generator source only (RESEARCH.md Tertiary confidence); needs a Task-1 spike against a live disarmed call, not a codebase analog. |

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/config/`,
`operator-claude-plugin/skills/contact-upload/`, `scripts/build_cloud_workflows.py`,
`n8n/code/*.js` — all already fully traced in 58-RESEARCH.md; this file adds concrete
line-cited excerpts for planner consumption rather than re-searching.
**Files scanned:** 9 (all read in full or by targeted range this session; remainder inherited
from RESEARCH.md's prior full reads, cited by line number).
**Pattern extraction date:** 2026-08-26
