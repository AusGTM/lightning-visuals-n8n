# Phase 20: Lusha v3 Migration - Pattern Map

**Mapped:** 2026-07-30
**Files analyzed:** 6 (all existing files — this phase has no wholly-new files, it is a
localized modify-in-place migration per RESEARCH.md's Summary)
**Analogs found:** 6 / 6 (all in-repo — the strongest analog for every touched file is the
ZoomInfo GTM v2→v3-style migration already completed in this same codebase, Phase 12-13)

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/build_cloud_workflows.py` (Lusha CLOUD request builders, 6 call sites) | request-builder (Python string-constant emitting n8n HTTP node params) | request-response (GET→POST body swap) | ZoomInfo GTM POST builders in the **same file** (`_zoom_split_enrich_contacts_js`, `_zoom_split_enrich_companies_js`, `ENRICH_ZOOMINFO_CACHED`) | exact — same file, same GET→POST JSON:API migration shape, same author conventions |
| `scripts/build_cloud_workflows.py` (`_http_node` call sites for Lusha) | controller / node-factory caller | request-response | Apollo's existing `_http_node(..., auth="header", json_body=...)` call site (same file, lines ~3619+) | exact — same auth style (`header`, not Bearer), same JSON-body-via-expression pattern |
| `n8n/code/normalizeProviders.js` (`lushaCandidates()` v3 branch) | transform / envelope-adapter | transform | `_zoomRecord()` in the **same file** (envelope-unwrap isolated ahead of unchanged field-extraction logic) | exact — this is the explicit pattern RESEARCH.md names to mirror |
| `scripts/dryrun_batch.mjs` (`lusha(id)` function) | utility / harness | request-response | Same file's own function, being modified in place; no separate analog needed | exact (self) |
| `config/hubspot_properties.yaml` (2 new staging properties) | config / schema | CRUD (schema definition, synced via script) | `lv_enrichment_reviewed_by` entries (companies ~line 250-255, contacts ~line 407-412) | exact — RESEARCH.md already quotes the copy-paste shape |
| `tests/n8n/lushaRequestContract.test.mjs` + `tests/test_cloud_companies_branch.py` (Lusha-specific cases) | test | request-response (contract-pinning) | Sibling ZoomInfo contract tests / the file's own prior version (pre-migration) | exact — same test file, same pinning technique (evaluate real committed node expression via `new Function`) |

## Pattern Assignments

### `scripts/build_cloud_workflows.py` — Lusha contacts CLOUD node (GET→POST swap)

**Analog:** ZoomInfo GTM's own v2(REST GET)→v3(JSON:API POST) migration, same file,
`_zoom_split_enrich_contacts_js` (lines 2989-3036) and the original single-node
`ENRICH_ZOOMINFO_CACHED` (lines 1310-1318).

**Current Lusha v2 CLOUD node being replaced** (lines 3604-3615):
```python
lusha = _http_node("Lusha Enrich", "https://api.lusha.com/v2/person", px, y - 80,
                   auth="header",  # credential header, e.g. api_key: <LUSHA_API_KEY>
                   json_body=(
                       "={{ (() => { "
                       "const id = $('Enrichment Gate').item.json.identity_keys || {}; "
                       "const c = { contactId: \"1\" }; "
                       "if (id.email) c.email = id.email; "
                       "if (id.linkedin_url) c.linkedinUrl = id.linkedin_url; "
                       "return JSON.stringify({ contacts: (c.email || c.linkedinUrl) ? [c] : [] }); "
                       "})() }}"
                   ))
```
Note this v2 CLOUD node is **already POST** (body-based, not GET) — unlike the companies
lane. Only URL, path, and body shape need to change for v3, not the HTTP verb; keep using
`_http_node(..., auth="header", json_body=...)` unchanged as the node-factory call shape.

**ZoomInfo's analogous "rename fields entering a JSON:API-style body, isolate the mapping
in one small function" pattern** (`toMatchPersonInput`, lines 2998-3005):
```javascript
function toMatchPersonInput(id) {
  const m = {};
  if (id && id.email) m.emailAddress = id.email;   // rename email -> emailAddress
  if (id && id.firstName) m.firstName = id.firstName;
  if (id && id.lastName) m.lastName = id.lastName;
  if (id && id.companyName) m.companyName = id.companyName;
  return m;
}
function hasZoomKey(m) { return !!(m.emailAddress || (m.firstName && m.lastName && m.companyName)); }
```
Copy this shape for a `toLushaContactBody(id, reveal)` (or inline-arrow, matching the
existing Lusha style) that: (1) builds the v3 identity object with whatever field names the
live probe confirms, (2) derives `reveal` from `gate.missingFields` via the fixed allow-list
in RESEARCH.md §"Selective reveal design", (3) skips the call (empty candidate/`null` payload,
`{ json: { skipped: "..." } }`) when no usable identity key exists — mirroring
`hasZoomKey`/BUG-17's "empty body still 400s, so skip explicitly" lesson.

**Header-auth (not Bearer) call-site shape to preserve** — copy from Apollo's own POST
`_http_node` call (same file, ~3619-3624), since Lusha (unlike ZoomInfo) stays on static
`api_key` header auth, never Bearer/OAuth:
```python
apollo = _http_node("Apollo Match", "https://api.apollo.io/v1/people/match", px + 220, y - 80,
                    auth="header",  # credential header, e.g. X-Api-Key: <APOLLO_API_KEY>
                    json_body=("={{ JSON.stringify({ "
                               "email: $('Enrichment Gate').item.json.identity_keys.email, "
                               ...
```
Do NOT copy ZoomInfo's split-code-node/Bearer-mint topology (`_zoom_split_gate_js` /
`_zoom_split_cache_js` / Mint HTTP node) — that exists solely because ZoomInfo needs
OAuth client-credentials token minting on Cloud. Lusha's `api_key` header auth needs none of
that; the single `_http_node(auth="header", ...)` call site is the complete pattern.

---

### `scripts/build_cloud_workflows.py` — Lusha companies CLOUD node (GET→POST verb change)

**Analog:** Same file, the `_http_node`'s own `method="GET"` branch comment (lines 2893-2899)
documents exactly the bug class this migration must not repeat:
```python
elif method == "GET" and json_body is None:
    # BUG 17: a GET provider call carries its identity in the URL, not a body. The
    # default `{{ JSON.stringify($json.identity_keys) }}` body below is what made
    # Lusha Company POST an identity object at an endpoint that only accepts
    # `?domain=`. No other call site passes method="GET", so this branch is new
    # ground, not a behaviour change.
    pass
```
This is the **live bug this migration reverses**: today `Lusha Company` (line 3822-3826) is
`method="GET"` with a URL-encoded query. v3 flips it back to `method="POST"` (the default —
simply omit `method="GET"` and pass `json_body=...` instead of a URL query, exactly like the
contacts node above) with a JSON body carrying `domain`/whatever field the live probe confirms.
Current node to replace:
```python
lusha_co = _http_node("Lusha Company",
                      "={{ $('Build Company Requests').item.json.lusha_company_url }}",
                      cx, cy, "GET", auth="header")
```
Companies-lane `reveal[]` is explicitly **out of scope per RESEARCH.md Pitfall 4** unless
the live probe finds a companies-lane reveal-gated model — default to no `reveal` field on
this lane's body.

---

### `n8n/code/normalizeProviders.js` — `lushaCandidates()` v3 envelope branch

**Analog:** `_zoomRecord()` in the same file (lines 272-289) — the exact "isolate an
envelope-unwrap adapter ahead of unchanged field-extraction logic" pattern RESEARCH.md names.

```javascript
function _zoomRecord(raw) {
  if (!raw || typeof raw !== "object") return raw || {};
  let rec = raw;
  if (Array.isArray(raw.data)) rec = raw.data[0] || {};
  else if (raw.data && typeof raw.data === "object" && raw.data.attributes) rec = raw.data;
  if (rec && rec.attributes) {
    return { ...rec.attributes, id: rec.id,
      matchStatus: (rec.meta && rec.meta.matchStatus) || rec.attributes.matchStatus };
  }
  const r = raw.data != null ? raw.data : raw;
  if (Array.isArray(r)) return r[0] || {};
  if (r && Array.isArray(r.result)) {
    const first = r.result[0];
    if (first && Array.isArray(first.data)) return first.data[0] || {};
    return first || {};
  }
  return r;
}
```

Existing `lushaCandidates()` envelope-detection to extend (lines 163-229), specifically the
top-of-function unwrap block (172-178) that this migration must add a v3 branch to, ahead of
the unchanged field-extraction logic below it:
```javascript
let raw = rawResponse || {};
if (raw.contacts && typeof raw.contacts === "object") {
  const entry = Object.values(raw.contacts)[0];
  raw = (entry && !entry.error && entry.data) || {};
} else if (raw.contact && raw.contact.data) {
  raw = raw.contact.data;
}
```
Add a v3-shape branch (detected by a distinguishing key such as top-level `contactId` or a
`has`/`canReveal` array — confirm exact key against the live probe) that normalizes v3's
envelope into the SAME intermediate `raw` shape (`emailAddresses`/`phoneNumbers`/`jobTitle`
for contacts; `company`-nested firmographics for companies) the existing extraction logic
below already consumes — do not touch the extraction logic itself (lines 181-227), matching
`zoominfoCandidates()`'s own precedent of calling `_zoomRecord()` once and then running
unchanged extraction (line 294: `const raw = _zoomRecord(rawResponse) || {};`).

**New `lusha_contact_id`/`lusha_company_id` extraction** — add as a plain `_push(...)`-style
candidate emission (or a direct field on the returned candidate set, per how the merge layer
expects to read it) inside the same v3 branch, since RESEARCH.md's `_push` helper (used
throughout this file for every other field) is the existing "how a new field enters the
candidate stream" pattern — no new emission mechanism needed.

---

### `scripts/dryrun_batch.mjs` — `lusha(id)` harness function

**Analog:** the function's own current implementation (self — being modified in place, no
external analog needed beyond mirroring the request-shape change already made in
`build_cloud_workflows.py`'s contacts builder above). Lines 64-76, current v2 GET + `api_key`
header — swap to POST v3 body using the identical `toLushaContactBody`-style mapping the
CLOUD builder above introduces, so the harness and the CLOUD node never drift (RESEARCH.md
explicitly calls out this file as contacts-lane-only; no company-lane function exists or is
requested here).

---

### `config/hubspot_properties.yaml` — `lusha_contact_id` / `lusha_company_id`

**Analog:** `lv_enrichment_reviewed_by` (companies ~250-255, contacts ~407-412) — RESEARCH.md
already extracted the exact copy-paste shape:
```yaml
- name: lusha_contact_id      # or lusha_company_id under companies:
  label: Lusha Contact Id     # or Lusha Company Id
  type: string
  fieldType: text
  groupName: lv_enrichment_contacts   # lv_enrichment for companies
  options: []
```
No new tooling: `scripts/sync_hubspot_properties.py` already implements dry-run-by-default
diff + two-key live-write gate (`DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true`).

---

### Test files — contract-pinning pattern

**Analog:** the files' own pre-migration versions, using the established technique of
evaluating the real committed node expression via `new Function` (already how
`tests/n8n/lushaRequestContract.test.mjs` pins the v2 body) — same technique, new expected
v3 shape. `tests/test_cloud_companies_branch.py`'s existing `test_lusha_company_uses_the_live_get_contract_and_sends_no_body`
inverts to assert POST + JSON body instead of GET + no body — same test-file location, same
assertion style (read the built node's `parameters.method`/`parameters.jsonBody` directly).

## Shared Patterns

### Header auth (not Bearer) for provider HTTP nodes
**Source:** `_http_node(..., auth="header", ...)` call sites for Lusha and Apollo
(`scripts/build_cloud_workflows.py`, e.g. lines 3604-3625)
**Apply to:** Both new Lusha v3 CLOUD/LOCAL-LIVE nodes — do not introduce ZoomInfo's
Bearer-mint split-node topology; Lusha's auth model is unchanged by this migration
(RESEARCH.md Locked Decision + Assumption A5).

### GET-body-mismatch bug class (BUG 17)
**Source:** `_http_node`'s `method == "GET" and json_body is None` branch comment,
`scripts/build_cloud_workflows.py:2893-2899`
**Apply to:** Every one of the 6 migration call sites — after changing method/URL/body,
manually inspect the raw HTTP response status/body against a live credential (RESEARCH.md
Pitfall 2); do not trust `onError: continueRegularOutput`'s "workflow executed" as evidence
of a correct request shape.

### Envelope-adapter isolation ahead of unchanged field-extraction logic
**Source:** `_zoomRecord()`, `n8n/code/normalizeProviders.js:272-289`
**Apply to:** `lushaCandidates()`'s new v3 branch — confine all v3-specific parsing to a
small adapter that normalizes into the existing intermediate `raw` shape; never rewrite the
field-extraction logic other tests/consumers depend on.

### Fixed allow-list mapping for security-sensitive request fields
**Source:** RESEARCH.md's own Security Domain section (V5 Input Validation) — no direct
code precedent since this is new logic, but the pattern to follow is the same discipline
already used for `normalizeEmailBasic`/`normalizePhoneAU` (deterministic functions, no
passthrough of raw untrusted input)
**Apply to:** The `reveal[]` derivation function — build from `{email: "emails", mobilephone: "phones"}`
literal map only, never from raw `gate.missingFields` strings passed through unchecked.

## No Analog Found

None — every touched file already has a directly-analogous in-repo pattern from the
ZoomInfo GTM v2 migration (Phase 12-13) or its own prior version to modify in place.

## Metadata

**Analog search scope:** `scripts/build_cloud_workflows.py`, `n8n/code/normalizeProviders.js`,
`scripts/dryrun_batch.mjs`, `config/hubspot_properties.yaml`, `tests/n8n/lushaRequestContract.test.mjs`,
`tests/test_cloud_companies_branch.py` — all read directly in this session.
**Files scanned:** 6 (all files RESEARCH.md's Codebase Map names as touched)
**Pattern extraction date:** 2026-07-30
