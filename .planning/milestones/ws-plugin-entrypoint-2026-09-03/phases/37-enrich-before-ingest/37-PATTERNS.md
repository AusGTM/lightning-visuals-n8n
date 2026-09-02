# Phase 37: Enrich Before Ingest (client) - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** 9 (1 new module, 5 edits, 1 new skill, 2 new test files/pairs)
**Analogs found:** 9 / 9

Note: 37-RESEARCH.md already did deep source verification with file:line citations and a
"Code Examples" section. This file does not re-derive those findings — it packages them per-target-file
for the planner, adds a few excerpts RESEARCH quoted only partially, and adds the CLI-harness and
stub-transport signatures RESEARCH described but didn't fully quote.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/preingest.py` (rows_from_table, build_rows_spec, classify_matches, apply_match_decisions, merge_enriched, render_enriched_preview — pure) | utility/service | transform | `scripts/header_suggest.py` (propose/confirm) + `scripts/preview.py::label_headers` | exact (role+flow) |
| `scripts/preingest.py::fetch_matches` | service | request-response (network, unarmed) | `scripts/dispatch.py` (attribute-shaped transport, but UNARMED vs dispatch's armed) | role-match |
| `scripts/preingest.py::match_batch` | service | batch (sequential, skip-failing-chunk) | `scripts/chunking.py::dispatch_plan` | exact |
| `skills/enrich-before-ingest/SKILL.md` | skill/doc | request-response (turn sequence) | `skills/contact-upload/SKILL.md` | exact |
| `tests/n8n/rowsEnvelopeContract.test.mjs` + `tests/test_rows_envelope_contract.py` | test (contract pin) | transform | `tests/n8n/listEnvelopeContract.test.mjs` + `tests/test_list_envelope_contract.py` | exact |
| `scripts/extraction.py::hold_emailless` + `write_dispatch_csv` raise | utility (guard) | CRUD (file I/O guard) | `scripts/header_suggest.py::apply_confirmed_corrections` (guard-before-open idiom) | exact |
| `scripts/chunking.py` (`rows` branch, `failed_batch`, `chunk_ceiling(key=)`) | utility/service | batch | itself, `record_ids` branch (existing code in same file) | exact |
| `scripts/enrichment.py::build_envelope` (`rows` form) | service | transform | itself, `list`/`record_ids` branches (existing code in same file) | exact |
| `scripts/preview_enrichment.py` (`records_block` rows branch, `__main__` file-path argv) | utility | transform | itself, existing `records_block` ids branch | exact |
| `scripts/config_gate.py` (`"match"` capability row) | config | CRUD (config lookup) | itself, `"enrichment"` row | exact |
| `tests/test_retry_reuses_dispatch.py` (AST guard extension) | test (AST guard) | transform | itself — extend `_send_shaped_function_names`/`_EXPECTED_SEND_SHAPED` | exact |

## Pattern Assignments

### `scripts/preingest.py` — propose/confirm functions

**Analog:** `scripts/header_suggest.py`

**Module docstring convention** (header_suggest.py:1-18) — state what layer owns the real
decision and what this module must never smuggle in:
```python
"""operator-claude-plugin/scripts/header_suggest.py

Half B of Phase 34: the client SUGGESTS a canonical prop for a header the backend's own
alias table does not recognise, the OPERATOR DECIDES per header, and the backend's
`Map Columns` node still performs the only real mapping.
...
fuzzy logic lives HERE, and only here — never inside preview.label_headers(), whose own
comment (preview.py:39-44) forbids adding fuzzy matching to it
"""
```
`preingest.py` should open the same way: `classify_matches` proposes, the OPERATOR decides
per row, and `rows_from_table` must call through `preview.label_headers`'s exact alias lookup
only (preview.py:39-44's docstring, already quoted in 37-RESEARCH.md §A.8) — never a second
mapping authority or fuzzy fallback.

**Proposal shape** (header_suggest.py `suggest_headers`, per-item form to mirror for
`classify_matches`'s MEDIUM proposals):
```python
result["suggestions"].append({
    "header": h,
    "suggestion": suggestion,
    "score": score,
    "sample_values": sample_values,   # shown IN THE SAME BREATH as the question
})
```
`classify_matches`'s per-row MEDIUM proposal must carry the same "confidence + named reason +
enough to judge it without seeing more" shape — 37-CONTEXT §5.3 requires
`hs_object_id, firstname, lastname, email, jobtitle, company` (6 keys per 37-RESEARCH mismatch
#4, NOT 7, no `lastmodifieddate`) shown alongside the candidate, same register as
`sample_values`.

**Confirmation-application function** (header_suggest.py:196-226,
`apply_confirmed_corrections`) — the exact shape `apply_match_decisions` must follow:
```python
def apply_confirmed_corrections(path, confirmed, scratch_dir=SCRATCH_DIR, mapping_path=None):
    """... `confirmed` maps the ORIGINAL header string to the corrected header string the
    operator approved ... A header absent from `confirmed` passes through untouched.
    ...
    Both guards below run BEFORE any file is opened for writing, so a refused call
    leaves the filesystem untouched.
    """
    props = canonical_props(mapping_path)
    if props is None:
        raise HeaderSuggestError(
            "the backend's alias/mapping config could not be resolved — with no "
            "canonical set to validate a confirmed target against, there is no safe "
            "write."
        )
    bad_targets = sorted(set(confirmed.values()) - set(props))
    if bad_targets:
        raise HeaderSuggestError(...)
```
`apply_match_decisions(classified, resolved)` must mirror: applies ONLY entries present in
`resolved`, raises (does not silently ignore) on a decision naming an unproposed row or a
candidate id not among that row's own candidates (37-CONTEXT §8 DoD 4), nothing applied on
refusal. This is a pure function (no file write), so the "guard before open" idiom becomes
"validate every decision before applying any of them" — same all-or-nothing-on-refusal shape.

---

### `scripts/preingest.py::fetch_matches` — network, unarmed

**Analog:** `scripts/dispatch.py` (attribute-shaped transport default) — **NOT**
`scripts/enrichment.py::dispatch_enrichment` (module-shaped, the AST-guard hole; §12 of
37-CONTEXT explicitly forbids copying that shape here).

Required signature shape (attribute-shaped, visible to `_is_requests_send_attribute`):
```python
def fetch_matches(chunk, config, transport=requests.post):
    ...
    resp = transport(url, headers=..., json=body, timeout=...)
```
Body carries only the lookup keys — AST-pin target: `json=` keys frozen to
`{email, firstname, lastname, company}` (37-CONTEXT §7). No `files=`/`data=`. Unlike
`dispatch.py`, `fetch_matches` takes **no `armed` parameter at all** — the match POST needs no
arming gate (§7: "it writes nothing and spends nothing").

Must detect the whole-batch refusal shape (37-RESEARCH mismatch #6, `Parse HubSpot Event`'s
guard, verified `build_cloud_workflows.py:3414-3434`): a single terminating item
`{"outcome":"refused","reason":...,"events":[],"object_type":"unknown"}` with **no** `row_id`/
`mode`/`match`/`action` — must not be zipped against the chunk's row_ids; the whole chunk
becomes `unchecked`.

---

### `scripts/preingest.py::match_batch`

**Analog:** `scripts/chunking.py::dispatch_plan`

Sequential, skip-a-failing-chunk contract to mirror (module docstring inline in
37-RESEARCH.md §A.2): iterates chunks in order, catches per-chunk errors (never lets one
failure kill the whole batch), returns a result object bundling successes + failures. Chunk
size must reuse `chunk_ceiling(config, key="max_rows_per_match_request")` = **2**
(37-RESEARCH's blocking finding — do not plan a value above 2, the shared backend guard
refuses whole).

---

### `skills/enrich-before-ingest/SKILL.md`

**Analog:** `skills/contact-upload/SKILL.md` (18,758 bytes / ≈18.3 KB, confirmed via `wc -c`;
10 numbered steps + 1 lettered insert `2b`).

Do not duplicate steps 6-10's prose — 37-RESEARCH §C.13 gives the exact headings to
reference by name instead of re-describing:
- **Step 6** — "Dispatch only once the operator has said the arming phrase this turn." →
  `python3 scripts/dispatch.py <path> armed`
- **Step 7** — "Report the outcome — per record, not a bare acceptance."
- **Step 8** — "Re-check, only when the operator asks." → one fetch, never a poll loop.
- **Step 9** — "Retry a transport failure — same dispatch, same arming gate."
- **Step 10** — "Clean up." → delete scratch artifacts.

New skill's turn sequence itself is already fully specified in 37-CONTEXT.md §5 (steps 1-7) —
copy that section's structure directly, this file's job is only to point the planner at the
handoff boundary and the size precedent that argues against folding into contact-upload.

---

### py↔js envelope-contract pair

**Analog:** `tests/n8n/listEnvelopeContract.test.mjs` + `tests/test_list_envelope_contract.py`
(repo root `tests/`, NOT under `operator-claude-plugin/`).

**JS half** (`tests/n8n/listEnvelopeContract.test.mjs`, full pattern to mirror):
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
  assert.equal(out.refused, false, `backend refused the client's own envelope: ${out.reason}`);
  assert.deepEqual(out.events, [...]);
});
test("the FLAT shape that shipped briefly is refused — this is the regression", () => { ... });
```
**Python half** (`test_list_envelope_contract.py`): imports `enrichment.build_envelope`,
asserts it PRODUCES the identical literal the `.mjs` half asserts the backend ACCEPTS.

**For rows**, per 37-RESEARCH Open Question #2 (resolved by re-reading 36-CONTEXT §6): the
rows form is just an `events[]` array entry with lookup-key fields instead of `objectId`
(`{"row_id":"r1","objectType":"contact","firstname":"Jane","lastname":"Doe","company":"GCTC"}`)
— there is **no separate backend module** the way `n8n/code/listExpansion.js` exists for
lists. `rowsEnvelopeContract.test.mjs` should pair with the existing
`ENRICH_PARSE_EVENT_CLOUD`/`parseWebhookBody` event-mapping chain
(`n8n/code/providerSelection.js`), not a new backend module. `test_rows_envelope_contract.py`
asserts `enrichment.build_envelope`'s new `rows` branch produces that same literal.

---

### `scripts/extraction.py` — `hold_emailless` + `write_dispatch_csv` raise

**Analog:** `write_dispatch_csv` itself (existing code, same file) for the guard-before-open
idiom, cross-checked against `header_suggest.py::apply_confirmed_corrections`'s identical
idiom.

**Current guard** (extraction.py, quoted in full in 37-RESEARCH §A.4):
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
Guard loop runs to completion BEFORE `out_path.open(...)` — a refusal leaves disk untouched.
Add a second guard in the same loop (or a preceding pass), same shape: check for a
missing/blank `email` cell, raise `ExtractionError` naming the rule and pointing at
`hold_emailless` as the correct call path, still before `out_path.open()`.

**§10 flips deliberately:** the existing emailless-row round-trip test currently asserts the
row IS written — it now must assert the refusal. Locate and flip that test; do not silence it.

---

### `scripts/chunking.py` — `rows` branch, `key=` param

**Analog:** itself — the existing `record_ids` branch of `plan_chunks` and the existing
`CEILING_KEY = "max_records_per_chunk"` no-fallback read in `chunk_ceiling`
(both quoted/described in 37-RESEARCH §A.2).

```python
# current chunk_ceiling(config) reads CEILING_KEY with no fallback:
#   raises ChunkPlanError if absent, not an int, or < 1
```
Add `key` parameter defaulting to the current constant so match can pass
`key="max_rows_per_match_request"` and get the identical no-fallback-refusal behavior. `rows`
branch in `plan_chunks` splits `spec["rows"]` the same way the existing branch splits
`spec["record_ids"]` — positional/parallel, not a rewrite. `failed_batch()` gains the matching
`rows`-shaped rebuild branch, mirroring its existing `record_ids` rebuild.

---

### `scripts/enrichment.py::build_envelope` — `rows` form

**Analog:** itself — existing `list`/`record_ids` branches (quoted in 37-RESEARCH §A.3):
```python
# build_envelope(spec, providers) accepts exactly:
#   {"list": ...} -> nested {name, objectType} envelope (byte-identical pin via
#                    test_list_envelope_contract.py + listEnvelopeContract.test.mjs)
#   {"record_ids": [...], "object_type": ...} -> events: [{objectId, objectType}, ...]
#   {"view": ...} -> raises ViewNotSupportedError
```
New `rows` branch: `events: [{row_id, objectType, firstname, lastname, company, email}, ...]`
per row (36-CONTEXT §6's request shape) — same dict-comprehension-over-a-list pattern as the
`record_ids` branch, just carrying lookup-key fields instead of `objectId`.
`dispatch_enrichment` itself is untouched (37-CONTEXT §4.3) — no new send path, this phase
only adds an envelope-shaping branch.

---

### `scripts/preview_enrichment.py` — rows `records_block` branch, file-path `__main__`

**Analog:** itself — existing `records_block()` ids branch (37-RESEARCH §A.1):
```python
f"**Records:** {count} {object_type}, named by ID. Nothing is structured or "
f"uploaded — these already exist in HubSpot."
```
New sibling branch for a rows spec must say the opposite explicitly: "these rows are **not**
in HubSpot yet — nothing is created by enriching them" (37-CONTEXT §4.4). `cost_block` /
`providers_block` / `chunks_block` stay untouched — `cost_guard.estimate_batch` already works
over a bare integer count, no record-id dependency (verified §A.1).

Current `__main__` (verbatim, 37-RESEARCH §A.1): `usage: preview_enrichment.py <spec-json>
[providers-json]` — takes a JSON STRING in argv[1]. Add: if `argv[1]` names an existing file
path, read the spec from that file instead (200 rows won't fit in argv) — same
"try-as-path-then-fall-back-to-literal" idiom other CLI scripts in this repo use for argv
robustness; no closer single analog exists in-repo for this specific fallback, treat it as a
small local addition guarded by `Path(argv[1]).exists()`.

---

### `scripts/config_gate.py` — new `"match"` capability row

**Analog:** itself — `"enrichment"` row (37-RESEARCH §A.7, `CAPABILITY_KEYS` quoted in full):
```python
CAPABILITY_KEYS = {
    "contact-upload": ("n8n_url", "webhook_secret"),
    ...
    "enrichment": ("n8n_url", "webhook_secret"),
    "sweep": ("n8n_url", "n8n_api_key", "webhook_secret"),
}
```
Add `"match": ("n8n_url", "webhook_secret")` — byte-identical tuple to `"enrichment"` — plus
its own `_CAPABILITY_DESCRIPTIONS` entry naming the match/lookup step specifically (a refusal
must not print "uploading contacts"/"enriching records" wording).

**CLI-subprocess test harness** (`tests/test_config_gate.py::_run_cli`, full signature +
purpose, quoted in full — this IS the harness for §9.1's operator-reachable-layer pin):
```python
def _run_cli(config_json, tmp_path, env=None, durable_config=None, versions=None, current=None):
    """Run scripts/config_gate.py as the skill runs it — as a real subprocess, against an
    ISOLATED plugin root so the operator's own gitignored config is never read.

    config_gate imports durable_paths, so both modules are copied into the throwaway
    `scripts/` directory ...

    A fake `HOME` (`tmp_path / "home"`) is what redirects `Path.home()`-based resolution
    at the PROCESS boundary, not the Python-object boundary ...
    """
```
Example call site (from `test_cli_still_answers_ok_without_a_webhook_secret_but_says_it_cannot_send`):
```python
proc = _run_cli(fake_config, tmp_path)
assert proc.returncode == 0, proc.stderr
payload = json.loads(proc.stdout)
assert payload["ok"] is True
assert payload["can_send"] is True
assert payload["send_blocked_reason"] is None
```
Extend this same harness with a case naming `"match"` — check first whether the existing
parametrization is already capability-name-agnostic (37-RESEARCH Open Question #1) before
adding a new test.

**`_run_header_cli`** (`tests/test_header_suggest.py::_run_header_cli(tmp_path, source_bytes,
*confirm_pairs)`) is the second harness template — copies the WHOLE `scripts/` tree via
`shutil.copytree` (selective copy dies on `ImportError` since `header_suggest` transitively
imports `preview`→`preview_enrichment`→`chunking`/`cost_guard`/`enrichment`), isolates
`config/` to only `column_mapping.yaml`. This is the template for a `preingest.py`-CLI test
and the skill-contract test — `preingest.py` will import `chunking`/`enrichment`/
`extraction`/`preview_enrichment`, so the whole-tree-copy approach is required, not optional.

---

### `tests/test_retry_reuses_dispatch.py` — AST guard extension

**Analog:** itself.

**Current pinned set** (verbatim):
```python
_EXPECTED_SEND_SHAPED = [("backend_status.py", ["fetch_backend_status"]), ("dispatch.py", ["dispatch"])]
```

**Current matcher** (verbatim — matches only an `ast.Attribute` `requests.post`/`.put`):
```python
def _is_requests_send_attribute(node) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _SEND_CALL_ATTRS
        and isinstance(node.value, ast.Name)
        and node.value.id == "requests"
    )
```

**The hole** (confirmed): `dispatch_enrichment(envelope, armed, config, transport=requests)`'s
default is a bare `ast.Name` `requests`, not an `ast.Attribute` — invisible to this matcher,
and its body calls `transport.post(...)`, not `requests.post(...)` directly, so the
direct-call check also misses it. This is a live, unguarded second send path today.

**Required extension** (~10 lines, per 37-CONTEXT §7 / 37-RESEARCH §B.9): add a predicate for
"transport param defaults to the bare `ast.Name` `requests` AND body calls
`transport.post/.put`" — mirror the existing `_has_send_shaped_transport_default` /
`_calls_requests_send_verb_directly` pair's factoring, name the new ones analogously (e.g.
`_has_bare_requests_module_transport_default` + `_calls_transport_send_verb`). Then:
- Add `("enrichment.py", ["dispatch_enrichment"])` to `_EXPECTED_SEND_SHAPED` (armed, no
  default, the enrichment lane's single send — allowlisted with reasoning in the same register
  as the existing two entries).
- Add `fetch_matches` to the allowlist too, but it is written attribute-shaped
  (`transport=requests.post`) so it's caught by the EXISTING `_is_requests_send_attribute`
  matcher, not the new one — reasoning: "the match POST reads HubSpot search results, writes
  nothing and spends nothing; it is a read wearing a POST's clothes."
- Two keeper tests (new, same file or sibling): match POST passes no `files=`/`data=`; its
  `json=` body keys AST-pinned to `{email, firstname, lastname, company}` only.

**No-network / stub-transport idiom** (`tests/conftest.py`, autouse guard + factories):
```python
@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """Any requests.post/request/Session.request call inside a test raises immediately."""
    ...
    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests, "request", _blocked)
    monkeypatch.setattr(requests.Session, "request", _blocked)

@pytest.fixture
def stub_post_transport_factory():
    """Returns the `_StubTransport` class so a test can script POST responses
    (a 401, a dead endpoint, an unparseable body) rather than the default accepted one."""
    return _StubTransport

@pytest.fixture
def stub_module_transport_factory():
    """Returns `_StubModuleTransport` so a control test can script a whole
    GET -> POST -> PUT -> POST -> GET sequence against one recorder."""
    return _StubModuleTransport
```
`fetch_matches`/`match_batch` tests use `stub_post_transport_factory` (attribute-shaped,
matches `transport=requests.post`'s call signature `transport(url, headers=..., json=...,
timeout=...)`) — NOT `stub_module_transport_factory`, which is for `dispatch_enrichment`-style
bare-module callers.

## Shared Patterns

### Guard-before-open (file I/O safety)
**Source:** `scripts/header_suggest.py::apply_confirmed_corrections` (lines 196-226,
docstring: "Both guards below run BEFORE any file is opened for writing, so a refused call
leaves the filesystem untouched.") — same pattern already live in
`extraction.py::write_dispatch_csv`'s extra-key check.
**Apply to:** `extraction.py`'s new emailless-row check.

### Propose-then-confirm (no auto-apply, confidence + reason + evidence in the same breath)
**Source:** `scripts/header_suggest.py::suggest_headers` (suggestion dict with `sample_values`
shown alongside the question) + `apply_confirmed_corrections` (applies only what's in
`confirmed`, refuses on invalid target).
**Apply to:** `preingest.py::classify_matches` / `apply_match_decisions`.

### Attribute-shaped transport default (AST-guard visibility)
**Source:** `scripts/dispatch.py`'s `transport=requests.post` parameter shape.
**Apply to:** `preingest.py::fetch_matches` — must NOT copy `enrichment.py`'s
`transport=requests` module-shaped default (§12 explicitly forbids this).

### Sequential skip-a-failing-chunk batch iteration
**Source:** `scripts/chunking.py::dispatch_plan`.
**Apply to:** `preingest.py::match_batch`.

### CLI-as-subprocess, isolated plugin root, fake HOME
**Source:** `tests/test_config_gate.py::_run_cli`, `tests/test_header_suggest.py::_run_header_cli`.
**Apply to:** the new `"match"` capability-gate test case, `preview_enrichment.py`'s new
argv/file-path handling test, any test pinning operator-reachable `preingest.py` CLI behavior.

### Byte-identical py<->js envelope contract pair
**Source:** `tests/n8n/listEnvelopeContract.test.mjs` + `tests/test_list_envelope_contract.py`.
**Apply to:** `tests/n8n/rowsEnvelopeContract.test.mjs` + `tests/test_rows_envelope_contract.py`.

## No Analog Found

None — every file in the module delta has a same-repo analog (several are extensions of the
target file's own existing code).

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/tests/`,
`operator-claude-plugin/skills/`, repo-root `tests/n8n/` (envelope-contract pair lives outside
the plugin dir).
**Files scanned:** header_suggest.py, dispatch.py, chunking.py, enrichment.py, extraction.py,
preview.py, preview_enrichment.py, config_gate.py, conftest.py, test_config_gate.py,
test_header_suggest.py, test_retry_reuses_dispatch.py, test_list_envelope_contract.py,
listEnvelopeContract.test.mjs, contact-upload/SKILL.md — plus everything already verified in
37-RESEARCH.md (not re-read where RESEARCH already quoted the needed lines).
**Pattern extraction date:** 2026-08-05
