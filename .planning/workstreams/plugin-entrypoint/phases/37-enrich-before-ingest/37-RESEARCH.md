# Phase 37: Enrich Before Ingest — Research

**Researched:** 2026-08-05
**Domain:** operator-claude-plugin client half of enrich-before-ingest; consumes Phase 36's shipped backend
**Confidence:** HIGH (all claims below are file+line verified this session)

## Summary

37-CONTEXT.md's module delta, AST-guard hole, and existing-file claims (§3/§4/§7/§9) all verify
against current source. **But one load-bearing assumption in §4 does NOT survive contact with what
Phase 36 shipped**: the backend now refuses *any* request to `hubspot/enrichment/event` — match or
enrich, any `mode` — carrying more than `ENRICH_MAX_LIST_RECORDS` (= **2**) events, enforced in
`Parse HubSpot Event` before mode is even read. 37-CONTEXT §4 point 2 explicitly instructs shipping a
**separate, larger** `max_rows_per_match_request` because match "runs two HubSpot searches" and is
cheap. That larger ceiling is unreachable: the shared endpoint hard-refuses the whole request at >2
events regardless of what the client intends to spend. This is a planning-blocking finding — see
`## PHASE 36 SHIPPED-VS-ASSUMED CONTRACT CHECK` below, read first.

The MEDIUM-candidate field shape also differs from §5.3's claim (6 keys, not 7 — no
`lastmodifieddate`, and the id key is `hs_object_id` not `id`). Response field names, tier vocabulary,
and the propose-mode write-guard ordering all verify as assumed.

**Primary recommendation:** Plan `fetch_matches`'s chunk size to reuse the SAME `ENRICH_MAX_LIST_RECORDS`-pinned
ceiling (2) — either literally as `max_records_per_chunk`, or as a second config key
`max_rows_per_match_request` whose value is also 2, with a provenance note pointing at the backend's
shared events-array-size guard (not the waterfall-timing rationale). Do not plan a match ceiling larger
than 2; the backend will refuse it. Everything else in 37-CONTEXT §3/§4/§7/§9 is confirmed accurate —
build against it directly.

## PHASE 36 SHIPPED-VS-ASSUMED CONTRACT CHECK

**Read this first — the client cannot be planned against a contract that isn't what shipped.**

### 1. BLOCKING: the events-array-size ceiling is 2, shared across match and enrich, and NOT mode-gated

`scripts/build_cloud_workflows.py:3489`: `ENRICH_MAX_LIST_RECORDS = 2` (measured 2026-08-03, B4 probe,
37.44s/record full waterfall against ~100s Cloudflare ceiling).

`scripts/build_cloud_workflows.py:3414-3425` (`ENRICH_PARSE_EVENT_CLOUD`, the FIRST node after the
webhook trigger, runs for every request to `hubspot/enrichment/event` regardless of `mode`):

```js
const MAX_EVENTS = __MAX_LIST_RECORDS__;   // = 2
if (parsed.events.length > MAX_EVENTS) {
  return [{ json: {
    outcome: "refused",
    reason: `Request carries ${parsed.events.length} events, more than this backend can ` +
      `enrich in one request — the limit is ${MAX_EVENTS} record(s) per request. ` +
      `Nothing was enriched. Send fewer records per request, in batches of ${MAX_EVENTS} or fewer.`,
    events: [], object_type: "unknown",
  } }];
}
```

This check runs **before `mode` is consulted at all** — there is no mode-based exception. 37-CONTEXT's
own client-side `test_chunk_ceiling_contract.py` (`operator-claude-plugin/tests/test_chunk_ceiling_contract.py`)
already pins the client's `max_records_per_chunk` (also 2, in
`operator-claude-plugin/config/operator.local.example.json`) equal to this same backend constant.

**37-CONTEXT §4 point 2 says:** *"Do not reuse `max_records_per_chunk` for match — it is 2, derived
from the waterfall, and would make a 200-row batch 100 round trips for a call that runs two HubSpot
searches. Ship `max_rows_per_match_request` in `operator.local.example.json` with a measured value..."*

Because there is no separate match-only endpoint (36-CONTEXT.md's entire wire contract is the ONE
webhook, disambiguated only by `mode`), and because `Parse HubSpot Event`'s size guard fires before
`mode` is read, **any `max_rows_per_match_request` greater than 2 will be refused whole by the shipped
backend**, no matter how cheap the match-only call actually is server-side. The premise behind §4 point
2's instruction (match is cheap, so it can carry more rows per request) is real internally, but it
cannot be expressed at the request boundary this backend enforces.

**Recommendation for the planner:** keep `max_rows_per_match_request` as its own config key (separating
match's refusal wording from enrich's, as CONTEXT intends) but set its value to **2**, with a
provenance note naming the actual reason (the shared `Parse HubSpot Event` size guard, not a waterfall
timing measurement), and add a cross-repo pin (mirroring `test_chunk_ceiling_contract.py`) so a future
backend change to `ENRICH_MAX_LIST_RECORDS` cannot silently orphan this key too. Do not plan client
code that assumes a value >2 will ever be accepted server-side.

### 2. Response shape — verified field-by-field

Full per-row response object (`scripts/build_cloud_workflows.py:1341-1350`, `ENRICH_DECIDE_CLOUD`,
plus `remaining_credits` appended at `Build Response`, `:3630-3643`):

```js
{ action, object_type, hs_object_id, gap_flag, row_id, mode, match, properties, remaining_credits }
```

- `action:"proposed"` — CONFIRMED, set unconditionally when `isReturnOnly(row.mode)` is true, strictly
  before the write-safety gate (`:1315-1331`).
- `row_id`/`mode`/`match` echoed — CONFIRMED (`:1346-1348`): `row_id: row.row_id ?? null, mode: row.mode
  ?? null, match: row.match ?? summarizeMatch({ lane: row.lane })`.
- `remaining_credits` — CONFIRMED present, but it is an **array** `[{provider, credits}, ...]` for
  `providers_requested`, attached identically to every item in the batch response, not a single number.
- **`hs_object_id` is the top-level id field name**, not `id` — confirmed at `existingRecord =
  {...properties, hs_object_id: first.id}` (`n8n/code` inlined via `scripts/build_cloud_workflows.py:1162,1165`).

### 3. Tier vocabulary — CONFIRMED matches 37-CONTEXT §6 exactly

`n8n/code/matchProposal.js`'s `summarizeMatch()`: `high` (auto:true, email/fetch_by_id hit), `medium`
(auto:false, name+company hit, candidates array), `none` (searched, no hit), `unknown` (lookup failed
OR no searchable identity at all — "we could not look", never conflated with `none`).

### 4. MISMATCH: MEDIUM candidate fields — 6 keys shipped, not 7; `id` renamed

37-CONTEXT §5.3 states a candidate should carry: `id, firstname, lastname, email, company, jobtitle,
lastmodifieddate` (7 fields).

**Shipped** (`n8n/code/matchProposal.js`, `mediumCandidates()`):

```js
out.push({
  hs_object_id: hit.id,
  firstname: props.firstname != null ? props.firstname : null,
  lastname: props.lastname != null ? props.lastname : null,
  email: props.email != null ? props.email : null,
  jobtitle: props.jobtitle != null ? props.jobtitle : null,
  company: props.company != null ? props.company : null,
});
```

6 keys: `hs_object_id` (not `id`), `firstname`, `lastname`, `email`, `jobtitle`, `company`. **No
`lastmodifieddate`.** This is deliberate per 36-01-SUMMARY.md's decision log: "projects a kept hit to
exactly six named keys... never the full HubSpot properties object — closing T-36-04 (information
disclosure)." The planner must write the client's per-row confirmation render (37-CONTEXT §5.3) against
these 6 fields, using `hs_object_id` as the id key. `lastmodifieddate` is not available from this
endpoint and must be dropped from the plan, or the client must be planned to fetch it separately (not
recommended — adds a second HubSpot round trip 36-CONTEXT never budgeted).

### 5. `needs_match_review` — CONFIRMED shipped, CONFIRMED does not fire on the client's own calls

`scripts/build_cloud_workflows.py:1324-1330`: `action = "needs_match_review"` fires only in the
`else if` branch — i.e., only when `isReturnOnly(mode)` is **false** (mode absent or `"write"`) AND the
row's `match.tier === "medium"`. Since 37's client always calls with `mode:"propose"` (return-only is
always true for it), it will **always** receive `action:"proposed"` for every row, MEDIUM tier included
— it will never see `needs_match_review` in its own responses. `needs_match_review` is a write-path-only
concern (guards a MEDIUM match from auto-creating when mode is absent/write) and needs no handling in
this phase's propose-only client flow. Companies never get this demotion at all (no match lane for
companies, confirmed `36-04-SUMMARY.md`).

### 6. Request envelope — CONFIRMED matches 36-CONTEXT §6

`mode`/`providers`/`events[]` — confirmed read via `parseWebhookBody()` returning `{events, providers,
mode}` (`n8n/code/providerSelection.js`, wired into `ENRICH_PARSE_EVENT_CLOUD`). `row_id` is
client-generated and echoed verbatim, never interpreted server-side (confirmed: it rides the `...event`
spread at `:3460` and is read back only at `Decide Action`/`Decide Company Action`).

Oversize/empty refusal shape — CONFIRMED (`:3414-3434`): a **single terminating item**, not one per row:
`{outcome:"refused", reason, events:[], object_type:"unknown"}`. This item carries **no** `row_id`,
`mode`, `match`, or `action` — it is shaped differently from every normal per-row response. **The
client's `fetch_matches`/`match_batch` must detect this shape (`outcome === "refused"`) and treat the
WHOLE chunk as `unchecked`** (36-CONTEXT's own vocabulary), not attempt to zip it against the chunk's
row_ids.

---

## User Constraints (from CONTEXT.md)

<user_constraints>
### Locked Decisions (37-CONTEXT.md §2, verbatim)

| # | Decision |
|---|---|
| 1 | Match tiers: `email EQ` → HIGH, auto. Else `lastname EQ` + `company CONTAINS_TOKEN` → MEDIUM, **proposed per row**. No hit → enrich. A failed match chunk is `unchecked`, **never** `unmatched`. |
| 2 | **Enriched preview before arming ingestion.** |
| 3 | **Ingest gate: email present, else HELD and reported. No force flag.** The way to send a held row is to give it an email. |
| 4 | **Chunking required** — batch uploads are a certainty. |
| 5 | **Two arming phrases, unchanged.** |
| 6 | **Contacts only.** There is no company canonical set (`column_mapping.yaml` defines seven contact props and one identity rule). Companies are the named upgrade path, not built here. |

### Claude's Discretion

37-CONTEXT.md does not carry a separate "Claude's Discretion" section distinct from the module delta
(§4) and turn sequence (§5) — those ARE the specified design; §12's rejected list marks the explicit
non-discretion boundary. Discretion for this research pass: the exact `max_rows_per_match_request`
provenance-note wording (see mismatch #1 above), and the AST guard's ~10-line implementation shape
(§7 gives the reasoning, not literal code).

### Deferred Ideas (OUT OF SCOPE)

§12 rejected — do not re-propose without new evidence: one combined arming phrase · carrying an arm
across turns · writing the match client module-shaped to slip past the AST guard · one endpoint with a
match/enrich mode flag (puts spend/no-spend on a boolean) · zipping enrichment responses to rows by
position · a "force send anyway" flag · creating a stub HubSpot record so an emailless row gets an id ·
client-side fuzzy matching against a downloaded HubSpot mirror · reusing `max_records_per_chunk` for
match **(see mismatch #1 — the shipped backend forces this number to 2 regardless; only the KEY should
stay separate, not the derivation rationale)** · putting the gate only in the new flow.

Company-object support is out of scope (governing rule §2.6): `config/column_mapping.yaml`'s
`required_identity.any_of` and `aliases` define only contact props (verified below).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-02 | CSV/XLSX read without pre-cleaning headers | `preview.label_headers`'s exact alias lookup (verified §A.8) is the header path `rows_from_table` must reuse — no second mapping authority |
| STRUCT-01 | Rows emitted over canonical contact props only | `extraction.write_dispatch_csv`'s extra-key guard (verified §A.4) is the existing enforcement point; `preingest.py` must produce rows shaped identically |
| STRUCT-02 | Rows failing identity rule separated/reported | `column_mapping.yaml`'s `required_identity.any_of` (verified §A.5) is the rule; `hold_emailless` is the new enforcement point at ingest time (per 37-CONTEXT §4) |
| STRUCT-04 | Never invent values; ambiguous values flagged | `header_suggest.py`/`name_split.py`'s propose-then-confirm precedent (verified §A.6) is the pattern `classify_matches`/`apply_match_decisions` must follow for MEDIUM proposals |
| PREVIEW-01 | Exact payload + row count shown before send | `preview_enrichment.py`'s four-block pure renderer (verified §A.1) extends with a rows-spec branch per 37-CONTEXT §4 point 4 |
| PREVIEW-02 | Cost estimate before approving | `cost_guard.estimate_batch(record_count, object_type, providers, rates)` (verified §A.1) already works over a bare count — no record-id dependency |
| PREVIEW-03 | Batches above configured size chunked | `chunking.plan_chunks`/`chunk_ceiling` (verified §A.2) — needs the `rows` branch and the `key=` param per 37-CONTEXT §4 point 2, ceiling value constrained per mismatch #1 |
| DISPATCH-03 | Disarmed by default, explicit live-write grant | `enrichment.dispatch_enrichment(envelope, armed, config, transport=requests)` (verified §A.3) — `armed` has no default; `fetch_matches` must NOT require arming (§7, verified §B.9) |
</phase_requirements>

---

## A. Existing client code — claim verification

### A.1 `scripts/preview_enrichment.py` — CONFIRMED

- Every function is pure — no `import requests`, no network call anywhere in the module body.
- `records_block()` contains the literal string `"these already exist in HubSpot"` (only on the
  named-IDs branch: `f"**Records:** {count} {object_type}, named by ID. Nothing is structured or "
  f"uploaded — these already exist in HubSpot."`) — CONFIRMED this is the ONE branch needing a rows-spec
  sibling per 37-CONTEXT §4 point 4.
- `cost_guard.estimate_batch(record_count, object_type, providers, rates)` called at
  `preview_enrichment.py` `__main__`: `cost_guard.estimate_batch(_count, _spec.get("object_type"),
  _providers, _table)` — `_count` is `_plan.record_count if isinstance(..., int) else None`, i.e. an
  **integer count**, never a record id. CONFIRMED it already works for rows that are not HubSpot records.
- `__main__` argv handling (current, verbatim): `usage: preview_enrichment.py <spec-json>
  [providers-json]` — takes a JSON **string** in `sys.argv[1]`, not a file path. CONFIRMS 37-CONTEXT §4
  point 4's claim that a file-path fallback branch is a genuine gap to add (200 rows will not fit in argv).

### A.2 `scripts/chunking.py` — CONFIRMED, with one gap noted

- `plan_chunks(spec, ceiling)` — splits `spec["record_ids"]` only today; a `list` spec returns one
  unsplit chunk with `UNKNOWN` count; **no `rows` branch exists yet** (confirms 37-CONTEXT §4 point 2's
  claim this needs adding).
- `chunk_ceiling(config)` — CURRENT signature takes only `config`, no `key` parameter. Reads
  `CEILING_KEY = "max_records_per_chunk"` with **no fallback** — raises `ChunkPlanError` if absent, not
  an int, or `< 1`. CONFIRMS the "no-fallback refusal" claim and confirms the `key=CEILING_KEY` parameter
  37-CONTEXT §4 point 2 wants does not exist yet (must be added).
- `dispatch_plan(plan, providers, armed, config, transport=requests)` — iterates chunks in order, calls
  `enrichment.build_envelope` + `enrichment.dispatch_enrichment` per chunk, catches `DispatchError`/
  `RecordSpecError` per chunk (never `NotArmedError`, which propagates immediately — an unarmed call
  sends nothing at all), returns `DispatchOutcome(results, failed_batch, responses)`.
- `failed_batch(chunks)` — rebuilds one record specification from failed chunks; `record_ids` form only
  today (a `list`-spec single failed chunk passes through as-is). Mirrors what 37-CONTEXT's `match_batch`
  "sequential, skip-a-failing-chunk" needs to mirror per §4.

**Cross-repo pin found:** `operator-claude-plugin/tests/test_chunk_ceiling_contract.py` pins
`operator-claude-plugin/config/operator.local.example.json`'s `max_records_per_chunk` (= **2**) exactly
equal to `scripts/build_cloud_workflows.py`'s `ENRICH_MAX_LIST_RECORDS` (= **2**) — this is the SAME
constant later found (via wire-contract check above) to gate ALL requests to the enrichment webhook,
match included. See `## PHASE 36 SHIPPED-VS-ASSUMED CONTRACT CHECK` item 1.

### A.3 `scripts/enrichment.py` — CONFIRMED

- `build_envelope(spec, providers)` accepts exactly: `{"list": ...}` → nested `{name, objectType}`
  envelope (refused-flat-shape history documented inline, `test_list_envelope_contract.py` +
  `tests/n8n/listEnvelopeContract.test.mjs` pin it byte-identical); `{"record_ids": [...], "object_type":
  ...}` → `events: [{objectId, objectType}, ...]`; `{"view": ...}` → raises `ViewNotSupportedError`.
  Neither form emits `row_id` or lookup keys — this is the WRITE-mode envelope shape; the new `rows` form
  37-CONTEXT §4 point 3 wants (`build_envelope` gains a `rows` branch) does not exist yet.
- `dispatch_enrichment(envelope, armed, config, transport=requests)` — CONFIRMED exact signature.
  `DEFAULT_TIMEOUT = 120` — CONFIRMED, comment states "above the ~100s Cloudflare response ceiling."
  `armed` has no default (raises `NotArmedError` if falsy) — mirrors `dispatch.py` exactly.
- **AST-guard-relevant**: `transport=requests` is the bare MODULE as the default (not `requests.post`
  as an attribute) — see §B.9 below, this is the confirmed hole.

### A.4 `scripts/extraction.py` — `write_dispatch_csv` — CONFIRMED exactly as 37-CONTEXT claims

```python
def write_dispatch_csv(rows, out_path, mapping_path=None) -> None:
    header = canonical_props(mapping_path)
    allowed = set(header)

    for i, row in enumerate(rows):
        extra = sorted(set(row.keys()) - allowed)
        if extra:
            raise ExtractionError(
                "non_canonical_key_in_row",
                f"Row {i} carries key(s) outside the canonical set and cannot be "
                f"written to the dispatch CSV: {extra}",
            )

    out_path = Path(out_path)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        ...
```

CONFIRMED: the guard checks only for EXTRA keys (`row.keys() - allowed`) — there is **no** check for a
missing/blank `email`, so an emailless row (all 7 canonical keys but a blank `email` cell) passes this
guard untouched today. CONFIRMED: the guard loop runs to completion **before** `out_path.open(...)` is
ever called — a refusal leaves disk untouched, matching `header_suggest`'s idiom.

### A.5 `config/column_mapping.yaml` — CONFIRMED

```yaml
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
```

Seven canonical contact props (deduplicated `aliases` values): `email, firstname, lastname, jobtitle,
linkedin_url, phone, company`. No company-object canonical set exists anywhere in this file — CONFIRMS
§2.6's "no company canonical set" claim.

### A.6 `scripts/header_suggest.py` + `scripts/name_split.py` — propose-then-confirm precedent, CONFIRMED

`suggest_headers(headers, rows=None, mapping_path=None)` returns per-header verdicts:
`{"available", "mapped": [...], "suggestions": [{"header","suggestion","score","sample_values"}],
"refusals"/"splittable": [...], "unresolved": [...], "needs_confirmation"}`. Confidence is `score`
(rounded `difflib.SequenceMatcher.ratio()`), never auto-applied. `_sample_values(rows, index)` pulls up
to 3 non-empty stripped cells so "an operator asked to confirm ... without seeing what is in the column
is being asked to rubber-stamp" — this is the load-bearing precedent 37-CONTEXT §5.3 cites for MEDIUM
candidate confirmation (show enough of the candidate to judge it, in the same breath as the question).

`apply_confirmed_corrections(path, confirmed, scratch_dir=SCRATCH_DIR, mapping_path=None)` takes a dict
of ORIGINAL→CONFIRMED value and writes ONLY what was confirmed — the exact shape `apply_match_decisions`
needs to mirror (37-CONTEXT: "applies **only** what the operator resolved").

### A.7 `scripts/config_gate.py` — `CAPABILITY_KEYS` — CONFIRMED

```python
CAPABILITY_KEYS = {
    "contact-upload": ("n8n_url", "webhook_secret"),
    "status": ("n8n_url", "n8n_api_key"),
    "control": ("n8n_url", "n8n_api_key"),
    "review": ("n8n_url", "webhook_secret"),
    "enrichment": ("n8n_url", "webhook_secret"),
    "sweep": ("n8n_url", "n8n_api_key", "webhook_secret"),
}
```

`"enrichment"` uses `("n8n_url", "webhook_secret")` — the new `"match"` row should be byte-identical to
this tuple, added to `_CAPABILITY_DESCRIPTIONS` with its own wording (mirrors the documented rationale:
match POSTs to the SAME endpoint as enrichment but must not print "uploading contacts"/"enriching
records" wording on refusal — it should say something naming the match/lookup step specifically).

### A.8 `scripts/preview.py` — `label_headers`'s exact alias lookup — CONFIRMED

`preview.py:39-44` (`_normalize_header`'s docstring, exact quote):

```python
def _normalize_header(header: str) -> str:
    """Mirror Map Columns' own rule exactly (see config/column_mapping.yaml's own
    comment): strip, collapse internal whitespace, lowercase. Do not improve on this with
    fuzzy matching — a smarter matcher would mislabel a column the backend really does
    map, which is the one thing the preview must never do."""
    return re.sub(r"\s+", " ", header.strip()).lower()
```

The actual exact-key lookup call is `label_headers()` (`~line 113`): `canonical = aliases.get(
_normalize_header(h))` — dict `.get()`, no fuzzy fallback. CONFIRMED: `preingest.rows_from_table` must
call through `preview.label_headers`'s exact lookup only, never a second mapping authority.

---

## B. The AST arming guard — verified precisely

### B.9 `tests/test_retry_reuses_dispatch.py` — the hole, CONFIRMED exactly as 37-CONTEXT describes

`_EXPECTED_SEND_SHAPED = [("backend_status.py", ["fetch_backend_status"]), ("dispatch.py",
["dispatch"])]` — CONFIRMED verbatim.

The guard's matcher, `_is_requests_send_attribute(node)`:

```python
def _is_requests_send_attribute(node) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _SEND_CALL_ATTRS
        and isinstance(node.value, ast.Name)
        and node.value.id == "requests"
    )
```

This matches **only** `requests.post`/`requests.put` as an `ast.Attribute` expression (e.g. a parameter
default `transport=requests.post`, `dispatch.py`'s shape). `enrichment.dispatch_enrichment(envelope,
armed, config, transport=requests)`'s default is the bare `ast.Name` `requests` — not an `ast.Attribute`
— so `_has_send_shaped_transport_default` returns `False` for it. Its body calls `transport.post(...)`,
not `requests.post(...)` directly, so `_calls_requests_send_verb_directly` also returns `False`.
**CONFIRMED: `dispatch_enrichment` is completely invisible to `_send_shaped_function_names` today** —
this is a live, unguarded second send path with no arming-bypass protection from this test.

**Exact AST change needed** (per 37-CONTEXT §7, confirmed sufficient): add a second predicate —
a function whose `transport` parameter DEFAULTS to the bare `ast.Name` `"requests"` (not an attribute)
AND whose body calls `transport.post(...)`/`transport.put(...)` (an `ast.Attribute` where `.value` is an
`ast.Name` matching the parameter's own name, attr in `{"post","put"}`) — OR to state it the way the
existing helpers are already factored: extend `_send_shaped_function_names` with a
`_has_bare_requests_module_transport_default(func_def)` check (mirrors `_has_send_shaped_transport_default`
but tests `isinstance(default, ast.Name) and default.id == "requests"`) combined with a
`_calls_transport_send_verb(func_def)` check (walks the body for `ast.Call` whose `func` is an
`ast.Attribute`, `.attr in _SEND_CALL_ATTRS`, `.value` an `ast.Name` equal to the `transport` param's
own `arg` name). Add `("enrichment.py", ["dispatch_enrichment"])` to `_EXPECTED_SEND_SHAPED` with
reasoning in the same register as the `backend_status.py`/`dispatch.py` entries.

**The new `fetch_matches(chunk, config, transport=requests.post)` in `preingest.py` must be written
attribute-shaped** (`transport=requests.post`, matching `dispatch.py`'s existing shape) so it IS visible
to `_is_requests_send_attribute` and lands on the allowlist deliberately — never module-shaped (§12
rejected list explicitly forbids "writing the match client module-shaped to slip past the AST guard").

### B.10 `tests/test_backend_status_wiring.py` — the "no write node in chain" precedent, CONFIRMED

File lives at repo root `tests/test_backend_status_wiring.py` (not under `operator-claude-plugin/`) —
it asserts against the GENERATED `n8n/wf_backend_status_cloud.json`, not client code:

```python
WRITE_NODE_TYPES = {"n8n-nodes-base.hubspot"}

def test_endpoint_chain_contains_no_write_node():
    """This phase is strictly read-only (T-27-05) — no PATCH, no create, no property
    set. httpRequest search nodes are fine (they read); a native hubspot node performing
    update/create, or an httpRequest node using PATCH/POST against a HubSpot write
    endpoint, would not be."""
    doc = _load_workflow()
    for node in doc["nodes"]:
        assert node.get("type") not in WRITE_NODE_TYPES, (...)
        if node.get("type") == "n8n-nodes-base.httpRequest":
            method = node.get("parameters", {}).get("method", "POST")
            url = node.get("parameters", {}).get("url", "")
            if "hubapi.com" in url and "/search" not in url:
                assert method not in ("PATCH", "PUT"), (...)
```

For Phase 37 this precedent is N/A as a new standalone test: 37 builds no new server-side endpoint (the
match POST reuses `wf_enrichment_cloud.json`, which is NOT read-only — it has real HubSpot
create/update nodes for the write path). 37-CONTEXT §7's "server-half counterpart" instead needs to
assert something narrower: that a `mode:"propose"` request's OWN row-level execution path never reaches
a write node — i.e. pin that `action:"proposed"` routes only through `IF Enrich`'s existing false lane
to `Build Response`, never through `IF Create`/`IF Enrich`'s true lanes into `HubSpot Create`/`HubSpot
Update`. This is closer to `tests/test_write_gate_coverage.py`'s existing style (already covers "IF
Create/IF Enrich cannot match either return-only action string" per 36-04-SUMMARY.md D16) than to
`test_backend_status_wiring.py`'s whole-workflow read-only sweep — that coverage already exists from
Phase 36 and does not need duplicating in Phase 37.

### B.11 `tests/conftest.py` — `no_network` + stub factories, CONFIRMED

Autouse guard (`tests/conftest.py:567-582`):

```python
@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """Any requests.post/request/Session.request call inside a test raises immediately."""
    test_name = request.node.name
    def _blocked(*args, **kwargs):
        raise RuntimeError(f"Network access blocked in test '{test_name}': ...")
    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests, "request", _blocked)
    monkeypatch.setattr(requests.Session, "request", _blocked)
```

`stub_post_transport_factory` fixture returns the `_StubTransport` **class** (attribute/callable-shaped:
`__call__(self, url, headers=None, files=None, timeout=None, **kwargs)`) — matches `dispatch.py`'s and
`enrichment.py`'s call shape (`transport.post(url, headers=..., json=..., timeout=...)` — note actual
callers pass `json=` not shown in the stub's named args, captured via `**kwargs`).

`stub_module_transport_factory` fixture returns `_StubModuleTransport` (module-shaped: has bound
`.get`/`.post`/`.put` methods sharing one `.calls` list and a `.mutating_calls` property). This is the
one to use for `fetch_matches`/`match_batch` tests if `preingest.py` is ever written module-shaped
instead — but per B.9 above, `fetch_matches` should be attribute-shaped
(`transport=requests.post`), so its tests should use `stub_post_transport_factory`, NOT
`stub_module_transport_factory` (that fixture exists for `dispatch_enrichment`-style
`transport=requests` callers, which `fetch_matches` deliberately is not).

### B.12 CLI-as-subprocess harnesses — CONFIRMED, both are direct reuse candidates

`tests/test_config_gate.py::_run_cli(config_json, tmp_path, env=None, durable_config=None,
versions=None, current=None)` — copies `config_gate.py` + `durable_paths.py` into an isolated
`tmp_path/plugin/scripts/`, builds a **literal** subprocess `env` dict (`PATH` + a **fake `HOME`**,
never `{**os.environ}`) so the operator's real config/durable-home path can never leak into a test, runs
`subprocess.run([sys.executable, "config_gate.py"], cwd=root/"scripts", env=run_env)`.

`tests/test_header_suggest.py::_run_header_cli(tmp_path, source_bytes, *confirm_pairs)` —
`shutil.copytree(SCRIPTS_DIR, root/"scripts")` (whole tree, since `header_suggest` imports `preview` →
`preview_enrichment` → `chunking`/`cost_guard`/`enrichment`, so a selective copy dies on `ImportError`),
copies ONLY `column_mapping.yaml` into an isolated `config/` (never the operator's real
`operator.local.json`), runs `subprocess.run([sys.executable, str(root/"scripts"/"header_suggest.py"),
str(source_path), "--confirm", pair, ...])`.

**Both harnesses are the template for a `preingest.py`-CLI test and the new `enrich-before-ingest`
skill-contract test** (37-CONTEXT §9.1): copy the whole `scripts/` tree (since `preingest.py` will
import `chunking`/`enrichment`/`extraction`/`preview_enrichment`), isolate `config/` to only
`column_mapping.yaml` + a synthetic `operator.local.json`, run as a real subprocess with a literal env
dict, never patch in-process.

## C. Gaps left to the planner

### C.13 `skills/contact-upload/SKILL.md` — size and step boundaries, CONFIRMED

File size: `wc -c` → **18758 bytes** (≈18.3 KB) — CONFIRMED matches 37-CONTEXT's "18.3 KB" claim exactly.

Numbered steps (top-level, `^[0-9]+\. \*\*`): **1** (state target), **2** (resolve input file), **2b**
(lettered insert — "Check the headers before you preview", header-suggest/name-split integration; the
"lettered, not renumbered" comment is in-file at line 65), **3** (build/show preview), **4** (ask
approval), **5** (check arming), **6** (dispatch), **7** (report outcome), **8** (re-check on request),
**9** (retry a transport failure), **10** (clean up) — **10 numbered steps + 1 lettered insert (2b),
CONFIRMED exactly.**

Exact headings for the phase's handoff spec (37-CONTEXT §5 step 7: "hand off to `contact-upload` steps
6–10 verbatim for dispatch/report/retry/cleanup"):

- **Step 6** — "Dispatch only once the operator has said the arming phrase this turn." → `python3
  scripts/dispatch.py <path> armed`
- **Step 7** — "Report the outcome — per record, not a bare acceptance." → `report.py`'s
  `sync_response_is_sufficient`/`build_contact_report`, summary-counts-first / failing-rows-in-full /
  successful-rows-conditionally ordering, the `NO_EMAIL`+`ambiguous` permanently-stuck callout.
- **Step 8** — "Re-check, only when the operator asks." → one fetch via `executions_client.py`, never a
  poll loop.
- **Step 9** — "Retry a transport failure — same dispatch, same arming gate." → re-sends only
  `resendable_rows` (tagged `transport_failure`), same `dispatch.py <path> armed` call, no separate retry
  function.
- **Step 10** — "Clean up." → delete scratch artifacts (extraction artifact + step-2b's corrected-header
  copy), whether dispatched or declined.

**Planner directive:** the new `skills/enrich-before-ingest/SKILL.md` should literally instruct "follow
`contact-upload/SKILL.md` steps 6 through 10, unmodified" rather than duplicating their prose — these
five steps' actual mechanics (dispatch call shape, report ordering, retry gate, cleanup rule) are
untouched by Phase 37 and copying them is the second-source-of-truth risk 37-CONTEXT explicitly warns
against elsewhere in this milestone.

### C.14 py↔js envelope-contract analog — CONFIRMED, `listEnvelopeContract.test.mjs` is the shape to mirror

`tests/n8n/listEnvelopeContract.test.mjs` (repo-root `tests/n8n/`, NOT under `operator-claude-plugin/`)
is the existing precedent for §8.6's `rowsEnvelopeContract.test.mjs`:

```js
// EXACTLY what operator-claude-plugin/scripts/enrichment.py::build_envelope emits for
// {"list": "New Targets.xlsx", "object_type": "contacts"} with providers ["lusha"].
// Keep byte-identical with the Python twin.
const CLIENT_ENVELOPE = {
  providers: ["lusha"],
  list: { name: "New Targets.xlsx", objectType: "contacts" },
};
test("the backend ACCEPTS the exact envelope the client emits", () => {
  const out = expandListToEvents({ body: CLIENT_ENVELOPE, listResult, membershipsResult, maxRecords: 2 });
  assert.equal(out.refused, false, ...);
  assert.deepEqual(out.events, [...]);
});
test("the FLAT shape that shipped briefly is refused — this is the regression", () => { ... });
```

Its Python twin is `operator-claude-plugin/tests/test_list_envelope_contract.py`, asserting
`enrichment.build_envelope(...)` PRODUCES exactly the same literal. **This is the D-19 flat-vs-nested
class 37-CONTEXT §8.6 names** — the new `rowsEnvelopeContract.test.mjs` should follow this exact
two-file pattern: one `.mjs` file asserting the backend's row-handling code (whichever function reads
the `rows`/match-lookup envelope server-side — likely inside `ENRICH_PARSE_EVENT_CLOUD`'s
`parseWebhookBody`/event-mapping path, since there is no separate list-expansion-style module for
rows) ACCEPTS the exact literal `preingest.build_rows_spec`/`fetch_matches` will emit, paired with a
`test_rows_envelope_contract.py` asserting the Python side PRODUCES that same literal.

### C.15 `operator.local.example.json` shape — CONFIRMED, exact fields to mirror

Current `max_records_per_chunk` entry (verbatim):

```json
"max_records_per_chunk": 2,
"_max_records_per_chunk_note": "CONFIRMED 2026-08-03 by live probe B4: one full-waterfall record (lusha+apollo+zoominfo) took 37.44 s. Worst case observed 37.44 s, plus 25% headroom = 46.8 s per record, against the roughly 100 s Cloudflare response ceiling on an n8n Cloud webhook. floor(100 / 46.8) = 2. The enrichment workflow has no batching node, so every record in one POST runs the full provider + Haiku + Sonnet chain before the response fires.",
"_max_records_per_chunk_provenance_note": "B4 — the expensive path this ceiling had to survive — ran live 2026-08-03 and confirmed 2. ..."
```

Pattern: a bare numeric key + `_<key>_note` (human-readable measurement) + `_<key>_provenance_note`
(what was/wasn't run, what it can/can't move). `tests/test_chunk_ceiling_contract.py`'s
`test_the_client_ceiling_carries_its_measured_provenance` enforces the note contains no "PROVISIONAL"
and does contain "CONFIRMED" + the measurement figure + the probe name.

**For `max_rows_per_match_request`, per the mismatch found above, ship:**

```json
"max_rows_per_match_request": 2,
"_max_rows_per_match_request_note": "CONFIRMED <date>: forced to 2, identical to max_records_per_chunk, NOT because the match lookup itself is slow (it runs two HubSpot searches, no provider waterfall) but because the backend's Parse HubSpot Event node applies ENRICH_MAX_LIST_RECORDS as a whole-request refusal to every events array regardless of mode (scripts/build_cloud_workflows.py:3414-3425). A larger value here would be refused by the backend on every match POST above 2 rows."
```

— and a cross-repo pin mirroring `test_chunk_ceiling_contract.py` (either extend that same test file
with a second assertion, or a sibling `test_match_ceiling_contract.py`) so a future change to
`ENRICH_MAX_LIST_RECORDS` cannot silently orphan this second key too.

### C.16 Plugin release mechanics — locations only, no action proposed

- Version lives at `operator-claude-plugin/.claude-plugin/plugin.json` (verified: file exists at that
  path in the repo tree; the exact version key was not re-read this session — 37-CONTEXT §9.7 states the
  release checklist: bump `plugin.json` in the SAME commit as the CHANGELOG cut → push → push to master
  → refresh the marketplace clone, "Master is the branch the marketplace reads").
- CHANGELOG lives at `operator-claude-plugin/CHANGELOG.md` (PLUGIN-04's requirement that the client
  "carries its own README and CHANGELOG").
- `scripts/deploy_n8n_workflows.py` is irrelevant to this phase's release (that script deploys n8n
  workflow JSON, not the plugin) — Phase 37 makes no backend/n8n changes, so its release path is purely
  the plugin-version-bump + CHANGELOG + push-to-master + marketplace-clone-refresh sequence, with no
  disarmed-deploy/bounce step (that only applies to Phase 36's backend changes, already shipped).

## Corrected Test Baselines

37-CONTEXT.md §11's numbers are stale (pre-date Phase 36, which landed in this session). Current,
verified baselines to plan against:

```bash
.venv/bin/python -m pytest -q                                   # 1960 passed / 6 skipped (was 1933/6)
node --test tests/n8n/*.test.mjs                                 # 609 pass (was 553; FILE glob only)
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q      # 1052 passed / 5 skipped (unchanged — Phase 36 was backend-only)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json               # 0
```

System python lacks deps — use `.venv/bin/python`. Node directory-form is broken on node 24 — use the
file glob only.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python, `operator-claude-plugin/tests/` + repo-root `tests/`); node:test (`.mjs`, repo-root `tests/n8n/`) |
| Config file | none — repo convention, no `pytest.ini`/`conftest.py`-level plugin config beyond the autouse fixtures |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| Full suite command | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |

### By proof layer

**Direct import (pure-function unit tests, no subprocess, no network):**
`classify_matches`, `apply_match_decisions`, `merge_enriched`, `build_rows_spec`, `rows_from_table`,
`hold_emailless` — all listed as `pure` in 37-CONTEXT §4's module table. These get plain
`import preingest; preingest.classify_matches(...)`-style pytest unit tests, same idiom as
`extraction.py`'s existing `test_extraction_*.py` (dozens of pure-function unit tests already in
`operator-claude-plugin/tests/`). No fixture beyond the autouse `no_network` (which none of these touch
anyway — they take no `transport` argument).

**CLI-subprocess layer (§9.1 — anything the operator experiences):**
- `config_gate.py`'s new `"match"` capability row → extend `tests/test_config_gate.py`'s existing
  `_run_cli` harness with a case naming `"match"`.
- `preview_enrichment.py`'s new rows-spec `records_block` branch and file-path `__main__` fallback →
  a subprocess test mirroring `_run_header_cli`'s pattern (copy `scripts/`, isolate `config/`, run
  `preview_enrichment.py <path-to-spec-file>` as a real subprocess).
- `chunking.py`'s new `rows` branch in `plan_chunks` and `chunk_ceiling(config, key=...)` → extend
  `chunking.py`'s own `__main__` CLI test if one exists, or add a subprocess test alongside
  `test_config_gate.py`'s harness style.
- `fetch_matches`/`match_batch`'s network calls → **direct import with `stub_post_transport_factory`**
  (attribute-shaped, per B.9/B.11), not subprocess — network stubbing needs in-process fixture control
  the subprocess harness does not give.
- `extraction.write_dispatch_csv`'s new raise-on-emailless-row behavior → the existing
  `test_extraction_*.py`-style direct-import test (the flipped test named in §10 of 37-CONTEXT).

**Skill-contract test (§6.3's two-arming-phrases-in-different-turns pin, §8.7's heading-index ordering):**
These are properties of the `skills/enrich-before-ingest/SKILL.md` MARKDOWN document, not runnable code
— pin them the way this repo already pins skill-contract properties: a pytest test that opens the
`.md` file, asserts the ingest-arm section's heading appears strictly after the enriched-preview
section's heading (by finding both headings' string offsets and comparing indices — mirrors
36-04-SUMMARY.md's "ordering-as-safety-property... asserts that ordering by character index" pattern
already used for `_writeSafetyAllows` call ordering), and asserts the two arming phrases ("arm the
enrichment" / "arm the upload") never appear in the SAME numbered step. No existing file does exactly
this for a skill doc yet — new test, same idiom as the code-ordering tests already in this repo.

**Backstop/live (§8.1's 9-directors end-to-end walk):**
Not automatable — requires a live n8n Cloud deploy (already shipped, Phase 36) and a real HubSpot
sandbox walk. This is the RB-style acceptance walk this repo's UAT process already performs (see
`STATE.md`'s references to "RB-9", "RB-7" etc as the pattern) — the planner should schedule this as the
phase's final DoD-1 checkpoint, not a pytest/mjs test.

### DoD → test file mapping

| §8 DoD item | Proof layer | Test file |
|---|---|---|
| 1. 9-directors case walks end-to-end, every row reaching HubSpot carries an email | Backstop/live | manual UAT walk, no automated file |
| 2. Rows waterfall couldn't complete are named/held, `write_dispatch_csv` raises, file not created | Direct import | `operator-claude-plugin/tests/test_extraction_*.py` (new cases; the flipped emailless-row test per §10) |
| 3. Failed match chunk yields `unchecked`, never `unmatched` | Direct import | new `test_preingest_match.py` (or similarly named) — `classify_matches`/`match_batch` unit tests |
| 4. `apply_match_decisions` refuses unproposed-row / not-own-candidate decisions | Direct import | new `test_preingest_match.py` |
| 5. `merge_enriched` joins by id, refuses duplicate id, ignores unknown id | Direct import | new `test_preingest_merge.py` (or same file as #4) |
| 6. Rows envelope pinned byte-identical py↔js | py↔js pair | `tests/n8n/rowsEnvelopeContract.test.mjs` + `operator-claude-plugin/tests/test_rows_envelope_contract.py` (mirrors `listEnvelopeContract.test.mjs` + `test_list_envelope_contract.py`, C.14 above) |
| 7. Two arming phrases, ingest-arm section after enriched-preview by heading index | Skill-contract | new test over `skills/enrich-before-ingest/SKILL.md` (heading-index assertion) |
| 8. Suites green; plugin version bumped same commit as CHANGELOG; pushed; merged to master; marketplace clone refreshed | Backstop/live | manual release checklist, no automated file (per §9.7) |

### py↔js envelope contract (§8.6)

Asserted byte-identically the same way the existing list-envelope contract is: two paired test files,
one per language, each importing the REAL production code (not a copy) and asserting against the SAME
literal JSON fixture embedded in both files' source. Analog: `tests/n8n/listEnvelopeContract.test.mjs`
(imports `n8n/code/listExpansion.js`'s `expandListToEvents`, asserts it ACCEPTS the client's exact
envelope) paired with `operator-claude-plugin/tests/test_list_envelope_contract.py` (imports
`enrichment.build_envelope`, asserts it PRODUCES that same literal). See C.14 for the full pattern this
phase's `rowsEnvelopeContract.test.mjs` should mirror.

## Common Pitfalls

### Pitfall 1: Assuming match can chunk larger than 2 rows per request
**What goes wrong:** A `max_rows_per_match_request` set above 2 causes every match batch above 2 rows to
be refused whole by the backend (`outcome:"refused"`), even though nothing was spent.
**Why it happens:** The backend's events-array-size guard (`ENRICH_MAX_LIST_RECORDS`) is applied in
`Parse HubSpot Event` before `mode` is read — it has no match/write distinction.
**How to avoid:** Set the config value to 2, same as `max_records_per_chunk`. See the shipped-vs-assumed
section above.
**Warning signs:** A live match POST with 3+ rows returns a single `outcome:"refused"` item instead of
per-row match verdicts.

### Pitfall 2: Zipping match responses to rows by position
**What goes wrong:** A response item's absence, reordering, or the whole-batch refusal shape (`outcome:
"refused"`, no `row_id`) silently misaligns rows to verdicts.
**Why it happens:** Assuming the response array is always the same length and order as the request rows.
**How to avoid:** `merge_enriched`/match-response joining must key on `row_id`, never index — 37-CONTEXT
§12 already rejects positional zipping explicitly, and the whole-batch refusal shape (§ mismatch #6
above) makes this doubly necessary: a refused chunk returns ONE item, not N.
**Warning signs:** A chunk of 2 rows producing exactly 1 response item that isn't a refusal.

### Pitfall 3: Rendering MEDIUM candidates with a `lastmodifieddate` column that doesn't exist
**What goes wrong:** A UI/render template built against 37-CONTEXT §5.3's 7-field claim breaks or shows
a blank/`None` column forever.
**Why it happens:** `mediumCandidates()` ships 6 fields, not 7 — no `lastmodifieddate` (see mismatch #4).
**How to avoid:** Plan the confirmation render against exactly `hs_object_id, firstname, lastname,
email, jobtitle, company`.
**Warning signs:** A field always renders empty across every live candidate.

### Pitfall 4: Writing `fetch_matches` module-shaped like `dispatch_enrichment`
**What goes wrong:** The new match POST becomes a second invisible send path the AST guard cannot see,
defeating the entire purpose of extending the guard in this phase.
**Why it happens:** Copy-pasting `dispatch_enrichment`'s `transport=requests` default pattern instead of
`dispatch.py`'s `transport=requests.post` pattern.
**How to avoid:** Write `fetch_matches(chunk, config, transport=requests.post)` — attribute-shaped — so
it lands on the allowlist deliberately (§7, §12 explicitly rejects the module-shaped alternative).
**Warning signs:** `test_exactly_one_module_defines_the_send_shaped_function` (extended per B.9) does not
list `fetch_matches` in its offenders OR its allowlist at all — meaning it's invisible either way.

## Code Examples

### Existing propose-then-confirm precedent (`header_suggest.py`), pattern to mirror for MEDIUM proposals
```python
# Source: operator-claude-plugin/scripts/header_suggest.py, suggest_headers()
result["suggestions"].append({
    "header": h,
    "suggestion": suggestion,
    "score": score,
    "sample_values": sample_values,   # <-- shown IN THE SAME BREATH as the question
})
# apply_confirmed_corrections(path, confirmed, ...) applies ONLY entries present in `confirmed`
```

### Existing cross-repo envelope-contract pin, pattern for `rowsEnvelopeContract.test.mjs`
```js
// Source: tests/n8n/listEnvelopeContract.test.mjs
const CLIENT_ENVELOPE = { providers: ["lusha"], list: { name: "New Targets.xlsx", objectType: "contacts" } };
test("the backend ACCEPTS the exact envelope the client emits", () => {
  const out = expandListToEvents({ body: CLIENT_ENVELOPE, listResult, membershipsResult, maxRecords: 2 });
  assert.equal(out.refused, false, `backend refused the client's own envelope: ${out.reason}`);
});
```

### Existing chunk-ceiling cross-repo pin, pattern for the new match-ceiling pin
```python
# Source: operator-claude-plugin/tests/test_chunk_ceiling_contract.py
def test_the_two_ceilings_agree():
    backend, client = _backend_ceiling(), _client_ceiling()
    assert backend == client, (f"chunk ceiling drift: backend ...={backend} but client ...={client}. ...")
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The new `"match"` capability row in `config_gate.py` needs its own `_CAPABILITY_DESCRIPTIONS` wording distinct from `"enrichment"` | §A.7 | Low — cosmetic refusal-message wording only, easily fixed post-hoc |
| A2 | `CONTAINS_TOKEN` operator semantics are correct against live HubSpot (already flagged `[ASSUMED]` in 36-RESEARCH.md, unresolved by this phase) | Wire contract | Medium — inherited from Phase 36, not introduced here; a wrong semantic yields zero or wrong MEDIUM candidates, never a false auto-match (mediumCandidates re-verifies by value) |
| A3 | `preingest.py`'s pure functions should live in ONE new file rather than split, per 37-CONTEXT §4's module table | §4 (context, not independently re-verified this session beyond confirming none of the 8 functions exist yet) | Low — a planner split into 2 files changes nothing behaviorally |

**Everything else in this document is `[VERIFIED: <path>:<lines>]` — read directly from source this
session, not carried over from 37-CONTEXT.md's own claims without re-checking.**

## Open Questions

1. **Does the match POST need its own capability-gate refusal wording tested at the CLI-subprocess
   layer, or is unit-testing `config_gate.require_capability(cfg, "match")` directly sufficient?**
   - What we know: `contact-upload`/`enrichment` capability refusals ARE tested via `_run_cli` (subprocess).
   - What's unclear: whether 37-CONTEXT's non-negotiable #1 (pin at the layer the operator reaches)
     requires a NEW subprocess case for `"match"` specifically, or whether the existing `_run_cli`
     parametrization already covers any capability name generically.
   - Recommendation: check `test_config_gate.py`'s existing test parametrization before planning a new
     test — it may already be capability-name-agnostic.

2. **Where exactly does the backend's row-handling code live that `rowsEnvelopeContract.test.mjs`
   should import from?** (C.14 flags this as the one piece not fully nailed down — there is no
   separate `n8n/code/rowsExpansion.js`-style module the way `listExpansion.js` exists for lists; the
   `rows`/match envelope is read inline inside `ENRICH_PARSE_EVENT_CLOUD`'s wrapper, not a separately
   inlined pure module.)
   - What we know: `parseWebhookBody()` (in `n8n/code/providerSelection.js`) reads `events`/`providers`/
     `mode` at the envelope level today; there is no dedicated "rows" reader.
   - What's unclear: whether Phase 37's rows form is literally just `events: [{row_id, objectType,
     firstname, lastname, company, email}, ...]` (i.e., the EXISTING `events` array, just carrying
     lookup-key fields instead of `objectId`) — in which case no NEW backend module is needed and
     `rowsEnvelopeContract.test.mjs` should assert against `parseWebhookBody`/`ENRICH_PARSE_EVENT_CLOUD`'s
     existing event-mapping logic — or whether a genuinely new backend shape is expected.
   - Recommendation: re-read 36-CONTEXT.md §6's request example (`{"row_id":"r1","objectType":"contact",
     "firstname":"Jane","lastname":"Doe","company":"GCTC"}`) — this IS just an `events[]` array entry
     with different fields, confirming NO new backend module is needed; `rowsEnvelopeContract.test.mjs`
     should pair with the existing `ENRICH_PARSE_EVENT_CLOUD`/`Build Identity` chain, not a new one.

## Environment Availability

Skipped — this phase modifies only `operator-claude-plugin/` client code and adds no new external tool
dependency. `requests`, `pyyaml`, `openpyxl` etc. are already installed dependencies of the existing
`.venv` (confirmed by the fact that the full pytest baseline of 1960/6 already runs green against them).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | This phase adds no new auth surface — reuses `X-Enrichment-Secret` header via `config_gate`'s existing `"enrichment"`-shaped capability |
| V4 Access Control | Yes | Match POST must be read-only server-side (no write node reachable, per B.10's narrowed test) and unarmed client-side (§7: "The match POST needs no arming — it writes nothing and spends nothing") |
| V5 Input Validation | Yes | `write_dispatch_csv`'s extra-key guard (existing) + the new emailless-row raise (this phase) are the input-validation choke points; `apply_match_decisions`'s refusal of unproposed-row/foreign-candidate decisions is also V5 |
| V6 Cryptography | No | No new secret handling — reuses `webhook_secret` unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Information disclosure via MEDIUM candidate payload | Information Disclosure | `mediumCandidates()` already projects to exactly 6 named keys, never the full HubSpot properties object (36-01-SUMMARY.md's T-36-04 closure) — this phase must not widen that render client-side either |
| Duplicate/second dedupe authority | Tampering (data integrity) | `merge_enriched` and `apply_match_decisions` must refuse rather than guess on unknown/duplicate ids (§8 DoD 4/5) — mirrors the existing "no client-side accepted/sent-row store" AST guard (`test_no_module_defines_or_persists_a_previously_sent_row_store`) |
| Second dispatch/send path bypassing arming | Elevation of Privilege | The AST guard hole (B.9) — must be closed in the SAME phase that introduces `fetch_matches`, not deferred |

## Sources

### Primary (HIGH confidence — direct file read this session)
- `scripts/build_cloud_workflows.py` (repo root) — `ENRICH_MAX_LIST_RECORDS`, `ENRICH_PARSE_EVENT_CLOUD`,
  `ENRICH_DECIDE_CLOUD`, `ENRICH_BUILD_RESPONSE`, `ENRICH_ADAPT_SEARCH` — read directly, line-cited above
- `n8n/code/matchProposal.js` — `laneOf`, `mediumCandidates`, `summarizeMatch`, `isReturnOnly` — read in full
- `operator-claude-plugin/scripts/{preview_enrichment,chunking,enrichment,extraction,preview,
  header_suggest,config_gate}.py` — read in full or near-full
- `operator-claude-plugin/config/{column_mapping.yaml,operator.local.example.json}` — read in full
- `operator-claude-plugin/tests/{test_retry_reuses_dispatch.py,test_chunk_ceiling_contract.py,
  conftest.py,test_config_gate.py,test_header_suggest.py}` — read directly, quoted above
- `tests/test_backend_status_wiring.py`, `tests/n8n/listEnvelopeContract.test.mjs` (repo root) — read directly
- `operator-claude-plugin/skills/contact-upload/SKILL.md` — read in full, byte count confirmed via `wc -c`
- `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-{CONTEXT,01,02,03,04}-SUMMARY.md`
  — read in full, this session's Phase 36 shipped-state ground truth

### Secondary (MEDIUM confidence)
- None — every claim above was checked against the file this session; nothing relied on WebSearch or
  training-data recall for this client-side, same-repo research pass.

## Metadata

**Confidence breakdown:**
- Existing client code claims (§A): HIGH — every function/signature verified by direct Read this session
- AST guard hole (§B.9): HIGH — traced through the exact AST predicates, confirmed the hole logically and by reading the guard's own matcher code
- Shipped-vs-assumed wire contract (top section): HIGH — traced through Phase 36's actual shipped source (`build_cloud_workflows.py`) and all 4 SUMMARY.md files, not just 36-CONTEXT.md's plan
- Validation architecture test-file mapping: MEDIUM — several test files (rowsEnvelopeContract.test.mjs,
  test_preingest_*.py) don't exist yet and are proposed names/locations, not verified paths

**Research date:** 2026-08-05
**Valid until:** Until Phase 37 planning completes — this research is tightly coupled to Phase 36's
just-shipped source and will go stale the moment either side changes again.
