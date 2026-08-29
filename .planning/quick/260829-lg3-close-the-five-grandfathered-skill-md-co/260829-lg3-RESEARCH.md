# Quick Task 260829-lg3: close the five grandfathered SKILL.md sequences — Research

**Researched:** 2026-08-29
**Domain:** internal test-composition archaeology (operator-claude-plugin)
**Confidence:** HIGH — every claim below is `[VERIFIED: file:line]` from this session's `Read`s.

## User Constraints (from CONTEXT.md)

- Close all 5 `GRANDFATHERED_UNCOVERED` entries in
  `operator-claude-plugin/tests/test_skill_sequence_coverage.py` with real composition tests;
  move each to `COVERED` with its covering nodeid; `MAX_GRANDFATHERED` → `0`.
- Entries #1 (`contact-upload`) + #4 (`enrich-before-ingest`) share an **identical call tuple**
  → one test, one nodeid, both `COVERED` entries point at it.
- Grouping: (1) #1+#4 authorize→armed_window→dispatch chain, (2) #3+#7 the waterfall
  resolve_providers→plan_chunks/chunk_ceiling→authorize→armed_window→dispatch_plan(+merge_enriched
  for enrich-before-ingest only), (3) #2 chunk_ceiling's real return → plan_chunks →
  match_batch→classify_matches.
- No live n8n/HubSpot/Anthropic/provider calls. Stub transports throughout.
- Do not edit any `skills/*/SKILL.md`.
- A fixture may stand in for `config_gate.load_config` — the staleness guard
  (`test_every_covered_nodeid_resolves_to_a_real_test_mentioning_the_sequences_sink`,
  `test_skill_sequence_coverage.py:458-473`) checks only the **sink**'s bare function name.
- Test command: `.venv/bin/python -m pytest operator-claude-plugin/tests -q`.

---

## Chain A — #1 (contact-upload) + #4 (enrich-before-ingest)

Registry tuple (`test_skill_sequence_coverage.py:210-227, 262-274`):
`config_gate.load_config → write_grant.authorize_send → write_grant.authorize_ungranted_send →
n8n_arming.armed_window → dispatch.dispatch`

### Ground-truth source blocks (both skills, byte-identical shape)

- `skills/contact-upload/SKILL.md:288-310` and `skills/enrich-before-ingest/SKILL.md:401-423`
  are the two real blocks. Both do: `cfg = config_gate.load_config()` → `decision =
  authorize_send(grant,...) if grant is not None else authorize_ungranted_send(cfg,...)` → `if
  not decision["armed"]: stop` → `with armed_window(decision["workflow_id"], ids, domains,
  allow_create, cfg, grant=decision["grant"]): result = dispatch.dispatch(path, True, cfg)`.
  Both use `lane="contacts"`, `object_type="contacts"`. **The covering test does not need to
  match `lane="contacts"` literally** — the registry identity is the function-name tuple only;
  reusing `lane="enrichment"` (below) is a valid simplification that avoids building a second
  contacts-named workflow fixture.

### (a) Signatures

- `config_gate.load_config(path=None, allow_migration=True) -> dict`
  (`scripts/config_gate.py:131`). Per CONTEXT, a fixture (`fake_config`/`granting_config`) may
  stand in.
- `write_grant.authorize_send(grant, *, lane, record_ids, record_domains) -> dict`
  (`scripts/write_grant.py:729`). Pure — no config, no transport. `grant=None` → `armed=False,
  refusal=None` (ordinary per-send path, unchanged). Returns
  `{armed, workflow_id, grant, refusal, detail}`.
- `write_grant.authorize_ungranted_send(config, *, lane, object_type, record_ids,
  record_domains, allow_create, label, providers=None, transport=None, preflight=None,
  today=None) -> dict` (`scripts/write_grant.py:792`). Composes `plan_grant()` +
  `open_grant(proposal, "yes", config)`. Same 5-key return shape as `authorize_send`.
- `n8n_arming.armed_window(workflow_id, record_ids, record_domains, allow_create, config,
  transport=None, grant=None)` (`scripts/n8n_arming.py:475-513`) — a context manager class.
  `__enter__` calls `arm_for_dispatch(...)`, raising `ArmingRefused` if the outcome isn't
  `ARMED`; `__exit__` always calls `disarm(...)` (even on an exception in the body) and raises
  `DisarmFailed` if the disarm didn't verify. Exposes `.arm_result` / `.disarm_result` after use.
- `dispatch.dispatch(file_path, armed, config, transport=requests.post, *, run_id=None) ->
  dict` (`scripts/dispatch.py:58-118`, current post-bug_004/D-59-10 shape). `armed` has **no
  default** — a caller that omits it gets `TypeError` (`dispatch.py:4-6`,
  `tests/test_dispatch_multipart.py:58-59`). Returns
  `{"body": <raw response>, "run_id": <str>, "written_records_failures": [...]}`
  (`dispatch.py:114-118`). Flushes via `written_records.append_chunk(run_id, 0, body)` inline
  (`dispatch.py:104-112`) — this is the D-59-10/bug_004 behaviour the CONTEXT explicitly names
  as the API to use. Tests already exercising this exact shape:
  `tests/test_dispatch_multipart.py::test_armed_dispatch_calls_the_stub_exactly_once_with_the_deployed_contract`
  (asserts `result["run_id"]`, `result["written_records_failures"] == []`, line 73-95) and
  `::test_run_id_defaults_to_a_fresh_generated_value_when_omitted` (line 237).

### (b) Nearest existing test to copy from

`tests/test_write_grant.py::test_authorize_ungranted_send_arms_with_the_same_guardrails_a_standing_grant_gets`
(lines 296-328) is **exactly** one call short of closing this chain: it builds a
`stub_module_transport_factory([...13 scripted responses...])`, calls
`write_grant.authorize_ungranted_send(granting_config, lane="enrichment",
object_type="companies", record_ids=[RECORD_ID], record_domains=[], allow_create=False,
label="this send", transport=transport)`, asserts `decision["armed"] is True`, then opens
`with n8n_arming.armed_window(decision["workflow_id"], [RECORD_ID], [], False, granting_config,
transport=transport, grant=decision["grant"]) as window: pass` — **body is `pass`**. Extending
that `pass` into a `dispatch.dispatch(...)` call (with a *second*, plain-callable stub — see
Gotcha 1) closes the "ungranted branch" half.

For the "grant-present `authorize_send` branch" half named in the registry's reason
(`test_skill_sequence_coverage.py:222-226`), copy the `_open()` helper
(`tests/test_write_grant.py:108-111`, itself composing `write_grant.plan_grant` +
`write_grant.open_grant` exactly like the tracer test at lines 116-141) to build a **standing**
open grant first, then call `write_grant.authorize_send(grant, lane="enrichment",
record_ids=[RECORD_ID], record_domains=[])` and feed *that* decision into a second
`armed_window` + `dispatch.dispatch`.

`test_authorize_ungranted_send_returns_the_same_shape_authorize_send_does`
(`tests/test_write_grant.py:398-415`) calls both authorize functions but chains neither into
`armed_window` — confirms the registry's own claim; not itself extensible into a chain because
its `authorize_send(None, ...)` call is `grant=None` (the "no grant, ordinary per-send path"
branch, which returns `armed=False` and cannot reach `dispatch.dispatch`). Use `_open()`-built
grant instead, as above.

### (c) What `armed_window` needs to open in a test

- Authority: with a `grant`, `_arm_gate` (`scripts/n8n_arming.py:203-256`) checks ONLY
  `config_gate.write_grants_enabled(config)` (must be `is True`, not truthy) and
  `grant["state"] == "open"` — **`ALLOW_N8N_ARM` is never read on the grant path.** The
  existing tracer test's `_clean_arm_env` autouse fixture (`test_write_grant.py:78-82`,
  file-scoped) is defensive, not load-bearing, for this chain.
- Network: `arm_for_dispatch`/`disarm` both go through the `transport` argument only
  (`n8n_read.get_workflow(..., transport=transport.get)`, `n8n_control.apply_mutation(...,
  transport=transport)`) — a **module-shaped** transport (`.get`/`.post`/`.put`), i.e.
  `stub_module_transport_factory` (`_StubModuleTransport`, `tests/conftest.py:213-247`). No
  real HTTP is reachable; `no_network` (autouse, `conftest.py:587-604`) would raise if it were.
- The existing tracer's 13-entry scripted list (workflow-list resolve → guardrail-A read → 5
  arm-mutation reads/writes → arm-verification read → 6 disarm reads/writes) is proven to open
  and cleanly close one window; reuse it verbatim per window opened (need a **fresh**
  `stub_module_transport_factory([...])` instance per `armed_window`, since each is a stateful
  queue popped in order — `_StubModuleTransport.__init__`, `conftest.py:228-230`).

### (d) `conftest.py` constraints

- `no_durable_writes` (autouse, `tests/conftest.py:607-638`) already redirects
  `written_records.written_records_path` into `tmp_path / "durable-state"` for **every** test,
  unconditionally, unless a test patches `resolve_state_path` itself first. **No extra
  monkeypatching is needed** for `dispatch.dispatch`'s inline `append_chunk` call in this chain
  — this is the fixture named in the CONTEXT's "prior defect was test-state pollution" note
  (bug_001, `conftest.py:13-20`).
- `no_network` (autouse, `conftest.py:587-604`) patches `requests.post/request` and
  `Session.request` to raise — any real call, if one ever leaked through, fails loudly.
- `stub_module_transport_factory` (`conftest.py:259-263`) and `stub_transport`/
  `stub_post_transport_factory` (`conftest.py:157-167`) are the two seams; see Gotcha 1 — they
  are NOT interchangeable.

### (e) Gotchas

1. **Two incompatible transport shapes, both needed in the same test.**
   `armed_window(..., transport=X)` needs `X.get/.post/.put` (module-shaped —
   `_StubModuleTransport`). `dispatch.dispatch(..., transport=Y)` calls `Y(url, headers=,
   files=, timeout=)` **directly as a callable** (`dispatch.py:80`) — a module-shaped stub has
   no `__call__` and would raise `TypeError: '_StubModuleTransport' object is not callable`.
   Use `stub_transport` (plain `_StubTransport`, `conftest.py:135-160`) for the `dispatch.dispatch`
   call, a *separate* `stub_module_transport_factory(...)` instance for `armed_window`. This is
   exactly how the existing, already-passing
   `tests/test_chunking.py::test_enrichment_and_contacts_writes_from_the_same_run_share_one_file`
   (line 846-868) does it for the analogous `dispatch_plan`/`dispatch` pairing (uses
   `stub_module_transport_factory()` for `dispatch_plan` and `stub_post_transport_factory([...])`
   for `dispatch`).
2. **`dispatch.dispatch` needs `n8n_url` + `webhook_secret` in config**
   (`config_gate.require_capability(cfg, "contact-upload")`, `CAPABILITY_KEYS["contact-upload"]
   = ("n8n_url", "webhook_secret")`, `config_gate.py:58`) — `fake_config`/`granting_config`
   already satisfy this (`conftest.py:91-104`); no real `operator.local.json` is ever touched.
3. **`armed_window`'s body exception path still disarms.** If the test calls
   `dispatch.dispatch(path, False, cfg, ...)` by mistake (wrong `armed` bool),
   `NotArmedError` propagates through the `with` body; `__exit__` still runs `disarm` and, if
   the disarm itself succeeds, re-raises the original `NotArmedError` (`n8n_arming.py:513`,
   `return False`). Pass `armed=True` (or thread `decision["armed"]`, which is `True` on the
   armed path) explicitly.
4. **One `armed_window`/one scripted transport = one use.** A second `with armed_window(...)`
   in the same test body needs its *own* fresh `stub_module_transport_factory([...])` — the
   first one's response queue is already drained.
5. **Honesty-bar note (no action needed, just don't over-build):** `config_gate.load_config`
   need not literally be called; the honesty rule only requires the **sink**
   (`dispatch.dispatch`, per `_test_function_source`/`sink_function` check,
   `test_skill_sequence_coverage.py:458-473`) to appear in the covering test's own source, and
   it will, verbatim.

### Recommended shape (both entries, one nodeid)

One test function driving BOTH the `authorize_send` (grant-present) branch and the
`authorize_ungranted_send` (no standing grant) branch, each ending in its own
`armed_window(...)`-scoped `dispatch.dispatch(...)` call — mirroring
`test_authorize_ungranted_send_arms_with_the_same_guardrails_a_standing_grant_gets`'s tracer
shape twice, with the plain `stub_transport` swapped in for the dispatch half each time.

---

## Chain B — #3 + #7 (the enrichment waterfall)

Registry tuples (`test_skill_sequence_coverage.py:228-243` — enrich-before-ingest w/
`merge_enriched`; `test_skill_sequence_coverage.py:276-291` — enrich-records, no
`merge_enriched`):
`config_gate.load_config → enrichment.resolve_providers → chunking.plan_chunks →
chunking.chunk_ceiling → write_grant.authorize_send → write_grant.authorize_ungranted_send →
n8n_arming.armed_window → chunking.dispatch_plan [→ preingest.merge_enriched, enrich-before-ingest only]`

### Ground-truth source block

`skills/enrich-before-ingest/SKILL.md:291-325` is the literal source for #3 — copy its shape
directly:
```python
cfg = config_gate.load_config()
providers = enrichment.resolve_providers(<override or None>, cfg)
plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))
decision = (authorize_send(...) if grant is not None else authorize_ungranted_send(...))
with n8n_arming.armed_window(decision["workflow_id"], ids, domains, allow_create, cfg,
                             grant=decision["grant"]):
    outcome = chunking.dispatch_plan(plan, providers, True, cfg)
responses = []
for body in outcome.responses:
    responses.extend(body if isinstance(body, list) else [body])
merge_report = preingest.merge_enriched(unmatched_rows, responses)
```
#7 (`enrich-records`) is the identical prefix minus the final `merge_enriched` call — confirmed
by its shorter tuple (no `preingest.merge_enriched` member).

### (a) Signatures

- `enrichment.resolve_providers(override, config) -> list` (`scripts/enrichment.py:133-175`).
  Pure. `override=None` reads `config[DEFAULT_PROVIDER_SELECTION_KEY]` or defaults to
  `FULL_WATERFALL`.
- `chunking.chunk_ceiling(config, key=CEILING_KEY) -> int` (`scripts/chunking.py:155-178`,
  `CEILING_KEY = "max_records_per_chunk"`, line 54). Raises `ChunkPlanError` if the key is
  absent/non-int/<1 — no fallback, by design.
- `chunking.plan_chunks(spec, ceiling) -> ChunkPlan` (`scripts/chunking.py:181-275`). Pure.
  `spec = {"record_ids": [...], "object_type": ...}` (or `"rows"`/`"people"`/`"companies"`/
  `"list"`/`"view"` — see body for the other branches).
- `chunking.dispatch_plan(plan, providers, armed, config, transport=requests, *, run_id=None)
  -> DispatchOutcome` (`scripts/chunking.py:315-417`). **`plan` — `plan_chunks`'s literal
  return value — flows in with NO transform** (`plan.chunks` is iterated directly, line 344).
  `transport` must be **module-shaped** (`.post`, wrapped internally by
  `_StatusCapturingTransport`, line 289-302) — same shape as `armed_window`'s transport, i.e.
  `stub_module_transport_factory()` works for BOTH here (unlike Chain A/dispatch.dispatch).
  Returns `DispatchOutcome(results, failed_batch, responses, run_id,
  written_records_failures)` — `.responses` is **one raw body per chunk**, needing the
  flatten idiom quoted verbatim in the SKILL.md block above
  (`DispatchOutcome` docstring, `chunking.py:115-125`) before it can feed `merge_enriched`.
- `preingest.merge_enriched(rows, responses) -> MergeResult` (`scripts/preingest.py:483-591`).
  Pure. `responses` **must already be flat** — a non-dict item raises `MergeError`
  (`preingest.py:98-107`'s existing pin is the exact regression test for passing
  `dispatch_plan(...).responses` straight through unflattened).

### (b) Nearest existing tests to copy from

- `tests/test_chunking.py::test_enrichment_and_contacts_writes_from_the_same_run_share_one_file`
  (line 846-868) — the *only* existing test chaining `plan_chunks → dispatch_plan` with a real
  stub transport. Uses a **literal `PROVIDERS = ["zoominfo", "lusha"]`** (line 320, module
  constant) instead of `enrichment.resolve_providers(...)`, and injects the transport directly
  with no `authorize_send`/`armed_window` layer at all — exactly the gap the registry names.
  `spec(count)` helper (line 35-36): `{"record_ids": ids(count), "object_type": "companies"}`.
- `tests/test_run_manifest.py::test_a_resume_re_requests_only_rows_that_still_needed_work`
  (line 435-473) — the model for the `rows`-spec / match side, and for #7's dispatch shape once
  adapted to `dispatch_plan` instead of `match_batch` (see Chain C for its literal-ceiling
  detail).
- `tests/test_preingest_merge.py` (whole file) — every `merge_enriched` test hand-builds
  `rows`/`responses` via `preingest.build_rows_spec` and a local `_response(row_id, properties)`
  helper (`tests/test_preingest_merge.py:32-37`) — none drives the dispatch/authorization
  layer, confirming the registry's claim verbatim.

### (c)/(d) same as Chain A

Same `armed_window` requirements and same autouse-fixture guarantees apply — no repeat needed.
One new fact: `dispatch_plan`'s transport IS module-shaped, so (unlike Chain A) **one
`stub_module_transport_factory` instance could in principle serve both `armed_window` and
`dispatch_plan`** — but they are still logically separate calls against separate endpoints
(workflow arm/disarm vs. the enrichment webhook POST) and the existing model test
(`test_chunking.py:846-868`) uses two *separate* instances (`enrich_transport` for
`dispatch_plan`, no `armed_window` at all in that test). Recommend keeping them separate to
avoid one queue's response shapes leaking into the other's expectations.

### (e) Gotchas specific to Chain B

1. **`dispatch_plan`'s per-chunk POST body is what feeds `merge_enriched` after flattening —
   script it as a JSON array**, e.g. a stub response `[{"row_id": "row-1", "properties": {...},
   ...}, ...]`, so `responses.extend(body if isinstance(body, list) else [body])` yields flat
   per-row dicts `merge_enriched` accepts.
2. **`resolve_providers`'s result is a plain list of strings** (e.g. `["zoominfo", "lusha"]`)
   — it is NOT wrapped or transformed before reaching `dispatch_plan`'s `providers` argument;
   `enrichment.build_envelope(chunk, providers)` (called inside `dispatch_plan`, line 348)
   consumes it directly.
3. **`chunk_ceiling(cfg)` with no `key=` reads `max_records_per_chunk`** (the *write* ceiling,
   value `2` in `config/operator.local.example.json`) — this is the correct ceiling for Chain
   B's `dispatch_plan` path (distinct from Chain C's `max_rows_per_match_request` match
   ceiling). Do not reuse Chain C's ceiling key here.
4. **`enrich-records` (#7) has no rows/merge step** — its spec should stay `record_ids`-shaped
   (not `rows`), since `enrich-records` operates on records already in HubSpot, not on a
   pre-ingest CSV; confirmed by the shorter registry tuple omitting `preingest.merge_enriched`.
5. Reuse Chain A's `authorize_send`/`authorize_ungranted_send` branch pair here too — the
   registry tuple lists BOTH names, so the covering test must call both, exactly as in Chain A.

---

## Chain C — #2 (enrich-before-ingest match ceiling)

Registry tuple (`test_skill_sequence_coverage.py:228-243`, listed a second time — this is a
*different* identity from Chain B's #3 despite sharing a skill name, per the file's own
set-equality-over-tuples design):
`config_gate.load_config → chunking.plan_chunks → chunking.chunk_ceiling → preingest.match_batch
→ preingest.classify_matches`

### Ground-truth source block

`skills/enrich-before-ingest/SKILL.md:114-123` — the literal source:
```python
cfg = config_gate.load_config()
plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))
outcome = preingest.match_batch(plan, cfg)
classified = preingest.classify_matches(
    spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids,
)
```

### (a) Signatures

- `chunking.chunk_ceiling(config, key="max_rows_per_match_request")` — same function as Chain
  B, different `key`. `config/operator.local.example.json` sets `max_rows_per_match_request:
  20` vs. `max_records_per_chunk: 2` — confirmed by the existing
  `test_chunk_ceiling_reads_the_match_key_and_it_is_larger_than_the_write_ceiling`
  (`tests/test_chunking.py:106-110`), which is the exact pattern to copy for getting a **real**
  (non-literal) ceiling: `config = json.loads(CONFIG_EXAMPLE.read_text())` where
  `CONFIG_EXAMPLE = Path(__file__).resolve().parent.parent / "config" /
  "operator.local.example.json"` (`test_chunking.py:26-28`).
- `preingest.build_rows_spec(rows) -> {"rows": [...], "object_type": "contacts"}`
  (`scripts/preingest.py:51-84`). Mints `row_id` as `row-1`, `row-2`, ... — refuses a row that
  already carries one.
- `preingest.match_batch(plan, config, transport=requests.post) -> MatchOutcome`
  (`scripts/preingest.py:181-233`). **Attribute-shaped** transport (bare callable, like
  `dispatch.dispatch`'s — NOT module-shaped), per its own docstring
  (`preingest.py:103-108`). Needs `config_gate.require_capability(config, "match")` internally
  (`CAPABILITY_KEYS["match"] = ("n8n_url", "webhook_secret")`) via `fetch_matches`.
- `preingest.classify_matches(rows, response, unchecked_row_ids=None) -> dict`
  (`scripts/preingest.py:236-...`). Pure. `response` is `outcome.responses` (already flat — one
  item per row, `match_batch` does its own per-chunk extend, `preingest.py:226`), NOT the
  per-chunk-wrapped shape `dispatch_plan.responses` has — no extra flatten needed here, unlike
  Chain B.

### (b) Nearest existing test to copy from

`tests/test_run_manifest.py::test_a_resume_re_requests_only_rows_that_still_needed_work`
(line 435-473) is the exact skeleton, with **one literal to fix**: `plan =
chunking.plan_chunks(spec, ceiling=5)` (line 441, a bare int) must become
`chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))`
fed by the real example config. Helpers to reuse verbatim: `_match_item(row_id, tier,
hs_object_id=None)` (`tests/test_run_manifest.py:415-422` — builds one match response item)
and `stub_post_transport_factory` (attribute-shaped, matches `match_batch`'s transport
contract exactly).

`tests/test_chunking.py::test_chunk_ceiling_reads_the_match_key_and_it_is_larger_than_the_write_ceiling`
(line 106-110) is the isolated-ceiling test named in the registry's own reason
(`test_skill_sequence_coverage.py:238-240`) — it must stay as-is (it's a legitimate unit test,
not being replaced); the new composition test is additive.

### (c)/(d) N/A for this chain

No `armed_window` involved — `match_batch`/`fetch_matches` take no `armed` parameter at all
(`preingest.py:181-186, 110-113`: match search burns no provider credit and writes nothing, "no
arming" by design). `no_durable_writes`/`no_network` still apply automatically but nothing in
this chain touches either durable state or real network beyond the stubbed transport.

### (e) Gotchas specific to Chain C

1. **`config/operator.local.example.json`'s `n8n_url`/`webhook_secret` are literal placeholder
   strings** (`"https://<your-subdomain>.n8n.cloud"`, `"<ask your admin — ...>"`,
   `config/operator.local.example.json:2-3`) — truthy, so `require_capability`'s presence check
   passes, but do NOT feed this config into `config_gate.load_config`'s URL-format validator if
   you call it for real (it would pass anyway, `https://` prefix is present) — simplest is to
   **merge** the two real ceiling keys from the example file into `fake_config` (which already
   has clean placeholder-free `n8n_url`/`webhook_secret` — `conftest.py:91-104`), e.g.
   `cfg = {**fake_config, "max_rows_per_match_request": 20}` sourced from
   `json.loads(CONFIG_EXAMPLE.read_text())["max_rows_per_match_request"]`, keeping the "real
   return value flows through `chunk_ceiling`" honesty property without touching a placeholder
   URL.
2. **`match_batch`'s chunk-row-id extraction reads `row["row_id"]` off `chunk.get("rows", [])`**
   (`preingest.py:209`) — the `spec` fed to `plan_chunks` for this chain MUST be the `"rows"`
   shape from `build_rows_spec`, never `"record_ids"` (Chain B/A's shape) — `plan_chunks`'s
   `"rows"` branch (`chunking.py:204-220`) is the one that applies here.
3. **`match_batch` and `dispatch_plan` use different transport shapes** — do not reuse a
   `stub_module_transport_factory()` here; `match_batch` needs `stub_post_transport_factory`
   (attribute-shaped), exactly what `test_run_manifest.py`'s existing tests already use.

---

## Shared Constraints & Gotchas (all three chains)

1. **Two stub-transport families exist and are NOT interchangeable:**
   - **Module-shaped** (`.get`/`.post`/`.put`, one shared `.calls` list) —
     `stub_module_transport_factory` → `_StubModuleTransport` (`conftest.py:213-263`). Needed by:
     `n8n_arming.armed_window`/`arm_for_dispatch`/`disarm`, `write_grant.plan_grant`/
     `open_grant`, `chunking.dispatch_plan`.
   - **Plain callable** (`transport(url, ...)` directly) — `stub_transport` /
     `stub_post_transport_factory` → `_StubTransport` (`conftest.py:135-167`). Needed by:
     `dispatch.dispatch`, `preingest.fetch_matches`/`match_batch`.
   Mixing them up produces a `TypeError` at collection/run time, not a subtle behavioural bug —
   cheap to catch, but worth flagging up front so the executor doesn't burn a cycle on it.
2. **Autouse fixtures need no test-local action**: `no_network` blocks any real
   `requests.post/request`/`Session.request`; `no_durable_writes` redirects
   `written_records.written_records_path` into `tmp_path` for every test automatically
   (`conftest.py:587-638`). No new test in this task needs to patch either — every call in all
   three chains already goes through an explicit stub transport, and no test needs to write to
   `run_manifest`/`written_records` durable paths directly (they're incidental side effects of
   `dispatch`/`dispatch_plan`, already covered by the autouse redirect).
3. **`plan_chunks`'s return feeds `dispatch_plan` with zero transform** (`plan.chunks` iterated
   directly) — but its return does **not** feed `merge_enriched`/`classify_matches` directly;
   those need the intermediate flatten (Chain B) or come pre-flattened via `match_batch`
   (Chain C) — do not assume one flattening rule serves both call sites.
4. **`authorize_ungranted_send` vs. `authorize_send` are not mutually exclusive within one test
   run** — nothing stops calling both in the same test body against independent state (a fresh
   standing grant for one, no grant/a fresh single-use grant for the other); they are pure /
   composition functions with no shared global. The registry tuple requires **both** names to
   appear, so both chains (A and B) must call both.
5. **`.venv/bin/python -m pytest operator-claude-plugin/tests -q`** is the only sanctioned test
   command (bare `python` lacks `openpyxl`/`pytest`/etc. — confirmed present in
   `tests/conftest.py:29-31`'s imports). Baseline: 1721 passed / 5 skipped.
6. **Repo bookkeeping rule**, independent of test content: any commit touching
   `operator-claude-plugin/` must bump `.claude-plugin/plugin.json`'s version (currently
   `"0.28.3"`, `.claude-plugin/plugin.json:4`) and add a `CHANGELOG.md` entry in the same
   commit.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Reusing `lane="enrichment"` (instead of the SKILL.md's literal `lane="contacts"`) in Chain A's covering test still satisfies the registry, since identity is the function-name tuple only, not argument values. | Chain A ground-truth note | Low — verified by reading the registry's identity construction (`sequences_in`/`parse_calls`, lines 95-138) which extracts only `module.function` names, never argument values. |
| A2 | `chunk_ceiling(cfg)`'s no-`key` call in Chain B should use `max_records_per_chunk` (not the match key) since that's the value `dispatch_plan`'s write path is bounded by. | Chain B Gotcha 3 | Low — directly stated in `chunk_ceiling`'s own docstring and confirmed by the SKILL.md block using bare `chunking.chunk_ceiling(cfg)` (no `key=`) at line 296. |

No table entries are `[ASSUMED]` in the stronger sense (untraceable to a session `Read`) — every
claim above cites a `file:line` opened this session.

## Metadata

**Confidence breakdown:** all three chains — HIGH. Every function signature, test fixture, and
SKILL.md block cited was opened and quoted this session; no web research or training-only claims
were used (this is an internal-codebase-only task, no external packages).

**Research date:** 2026-08-29. **Valid until:** this repo's next SKILL.md edit under any of the
three skills touched, or the next `dispatch.py`/`chunking.py`/`write_grant.py`/`preingest.py`
signature change — whichever comes first.
