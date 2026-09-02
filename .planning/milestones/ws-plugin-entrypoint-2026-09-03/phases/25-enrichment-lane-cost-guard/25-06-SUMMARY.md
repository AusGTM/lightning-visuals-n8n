---
phase: 25-enrichment-lane-cost-guard
plan: 06
subsystem: operator-claude-plugin (enrichment lane client — chunking)
tags: [chunking, sequential-dispatch, skip-on-failure, failed-batch, arming-gate]
status: complete

requires:
  - operator-claude-plugin/scripts/enrichment.py (25-04 — build_envelope, dispatch_enrichment, VIEW_REFUSAL)
  - operator-claude-plugin/scripts/dispatch.py (Phase 23 — NotArmedError, DispatchError)
  - operator-claude-plugin/config/operator.local.example.json (25-04 — max_records_per_chunk)
  - tests/test_chunk_ceiling_contract.py (pins client ceiling == backend ENRICH_MAX_LIST_RECORDS)
  - operator-claude-plugin/tests/conftest.py (stub_module_transport_factory, autouse no_network)
provides:
  - chunking.chunk_ceiling(config) -> int          (reads config; NO fallback constant)
  - chunking.plan_chunks(spec, ceiling) -> ChunkPlan
  - chunking.dispatch_plan(plan, providers, armed, config, transport=requests) -> DispatchOutcome
  - chunking.failed_batch(chunks) -> record specification | None
  - chunking.UNKNOWN, ChunkPlan, ChunkResult, DispatchOutcome, ChunkPlanError
affects:
  - 25-07 (preview renders ChunkPlan.chunk_count / row_counts / record_count; REQUIREMENTS rewording)
  - 26 (DISPATCH-04 safe retry re-dispatches DispatchOutcome.failed_batch unmodified)

tech-stack:
  added: []
  patterns:
    - "transport=requests (bare module) called as transport.post(...) — D-33; the
       arming guard's _EXPECTED_SEND_SHAPED allowlist was NOT appended to"
    - "a status-capturing transport wrapper, so a non-2xx with a readable body is a
       failure rather than an invisible success — without editing 25-04's module"

key-files:
  created:
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/tests/test_chunking.py
  modified:
    - .planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md

decisions:
  - "The ceiling is read through chunk_ceiling(config) and has no fallback: an absent
     key raises, naming the key. An AST test forbids the shipped ceiling reappearing in
     chunking.py as a default argument or module constant — a third copy of a number two
     files already carry."
  - "A list plan is one chunk with record_count == the word 'unknown'. The ceiling is not
     applied to it and there is no client-side list paginator — 25-03 refuses, it does not
     chunk."
  - "Failure is defined in one place: non-2xx, transport exception including a timeout
     (D-11b), or an unreadable body. NotArmedError is re-raised rather than recorded as a
     chunk failure — nothing was sent and nothing should be."
  - "The failed batch is ONE record specification build_envelope accepts unmodified, and
     re-plans through plan_chunks like any other batch, so a re-send is a dispatch."

metrics:
  duration: ~40 min
  completed: 2026-07-31
  tasks: 2
  files: 3
  tests_added: 41
---

# Phase 25 Plan 06: Client-Side Chunking Summary

One plan object that the preview renders and dispatch iterates, a ceiling read from config
with no fallback anywhere in the module, a backend-resolved list that stays one request with
an honestly unknown count, and a sequential loop that skips a failing chunk and hands the
failures back as a batch Phase 26 re-sends rather than re-derives — proven against the stub
transport behind the autouse network guard, with nothing leaving the machine.

## Commits

| Commit | Type | What |
|---|---|---|
| `48f4cac` | test | RED — chunk-plan tests (import error: no module named `chunking`) |
| `d958307` | feat | `chunking.py` + the Task-2 half of `test_chunking.py` (41 tests total) |
| `cf50e4c` | docs | four corrections folded into `25-CONTEXT.md` (D-19a, D-20a, D-21, D-22) |

No sibling executor was running. Every commit staged explicit paths, with
`git diff --cached --name-only` printed in the same shell invocation as the commit. No
`git add -A`, no `git add .`, no `git commit -a`. The operator's four in-flight 23-06 files
were not read-modified, staged or committed, and `STATE.md` was **not** touched.

## How the ceiling is read (and that no fallback constant exists)

`chunking.chunk_ceiling(config)` reads `config["max_records_per_chunk"]` and **raises** when
the key is absent, naming the key and saying the ceiling is a timeout bound rather than a
preference. It also raises on a non-integer, a bool, and anything below 1.

**There is no fallback constant in `chunking.py`, and one cannot be added back by accident.**
`test_no_fallback_ceiling_constant_exists_in_the_module` parses the module with `ast`, collects
every integer literal appearing as a function-argument default or a module-level assignment,
reads the shipped ceiling out of `operator.local.example.json`, and fails if the two intersect.
It is deliberately narrower than a source grep: a grep for `2` would fire on a legitimate
`< 1` guard the day the ceiling moves to 1, and a test that goes false-positive gets deleted.

The number stays **PROVISIONAL**. It derives from 36.1 s/record measured 2026-07-31 on
single-record, company-lane runs; the full-waterfall probe (B4) has not run. Nothing in this
plan presents it as measured, and nothing in this plan restates it — `chunking.py` never
mentions the value at all, only where to read it from.

## The plan object

`ChunkPlan(chunks, row_counts, record_count)` with `chunk_count` derived from `len(chunks)`.
`chunks` are record specifications in the exact shape `enrichment.build_envelope` already
takes, so a chunk — and later a failed batch — is **dispatched, not reconstructed**.

| Input | Plan |
|---|---|
| n ids, ceiling c | `ceil(n/c)` chunks, no empty trailing chunk, final chunk holds the remainder |
| `{"list": ..., "object_type": ...}` | **one** chunk carrying the list spec verbatim; `record_count` and the single row count are `UNKNOWN` (the word) |
| `{"view": ...}` | `ViewNotSupportedError` carrying `enrichment.VIEW_REFUSAL` verbatim |
| empty ids / ceiling < 1 / neither ids nor a list | `ChunkPlanError` |

The two assertions that carry the weight are not chunk-count assertions: the concatenation of
every chunk equals the input id sequence **exactly, in order** with no duplicate, and a list
plan's count is the string `unknown` (`not isinstance(record_count, (int, float))`).

`dispatch_plan` iterates `plan.chunks` and has **no splitting path of its own** (T-25-24). A
test hand-builds a `ChunkPlan` whose single chunk holds three ids and asserts it is sent as
one request regardless of any ceiling — a dispatcher that re-split would fail it.

## Arming

`dispatch_plan(plan, providers, armed, config, transport=requests)` — `armed` is positional
with **no default**, and is passed to each `dispatch_enrichment` call rather than captured in a
closure or an attribute. `NotArmedError` is re-raised out of the loop instead of being recorded
as a chunk failure, so a disarmed plan raises on the first chunk with the stub's call log empty
(asserted) rather than "failing" three chunks it never sent.

`test_no_function_in_this_module_gives_armed_a_default` uses **D-18's corrected form** —
`inspect.getmembers(mod, inspect.isfunction)` — not the broken `vars()` walk, which raises
`ValueError: no signature found for builtin type` on this repo's Python 3.14 for any bare
`Exception` subclass. The plan's Task-2 acceptance one-liner carries the broken form; see
Deviations.

## Failure, defined once

| Condition | Recorded as |
|---|---|
| HTTP status outside 2xx | `the backend returned HTTP {status}` |
| transport exception, including a timeout | `the request did not reach the enrichment webhook (a timeout counts here)` |
| response body unreadable where a readable one was expected | `the backend's response was not readable` |
| the chunk could not become a request (`RecordSpecError`) | `this chunk could not be turned into a request` |

A timeout is a failure for the skip rule even though the backend may still be working —
distinguishing the two is Phase 26's job (D-11b). `DEFAULT_TIMEOUT` remains 25-04's 120 s,
deliberately above the ~100 s Cloudflare ceiling, so a ceiling breach normally arrives as the
**backend's** timeout rather than as ours; the client-side timeout path is nonetheless
classified, because a dead endpoint reaches the same branch.

`ChunkResult(index, rows, ok, reason)` carries nothing from the config. A test scripts a
transport exception whose text contains both `n8n_url` and `webhook_secret` and asserts neither
appears in `repr(outcome.results)` (T-25-17).

## The failed batch

`DispatchOutcome.failed_batch` is `None` when nothing failed, so a caller branches on presence
rather than on an empty container. When present it is one record specification: the failed
chunks' ids in **original order**, with no id from a chunk that succeeded (asserted positively
*and* negatively, including the non-adjacent case `["1","2","5","6"]` — a test that only counts
failures passes against a dispatcher that hands back the whole batch).

Two properties make it the D-13 seam rather than a report:

- `enrichment.build_envelope(outcome.failed_batch, providers)` is asserted to produce the exact
  expected envelope **unmodified**;
- `chunking.plan_chunks(outcome.failed_batch, ceiling)` re-plans it into the same chunk shape,
  so a failed set larger than the ceiling is chunked again rather than sent whole.

A failed **list** chunk comes back as the list specification itself, never as a fabricated id
set — the client has no ids for it and must not invent any.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 — missing validation] A non-2xx carrying a readable JSON body was invisible to the loop**

- **Found during:** Task 2, designing the failure classifier.
- **Issue:** `enrichment.dispatch_enrichment` returns the parsed body on a readable response and
  a `{status_code, text}` shim only when `.json()` raises. An HTTP 401/500 whose body parses
  fine therefore returns something a caller cannot tell from a success — a chunk the backend
  refused, recorded as sent. That is precisely the partial-or-failed-read-impersonating-a-healthy-one
  shape this milestone has hit seven times.
- **Fix:** `chunking._StatusCapturingTransport` wraps the caller's transport, records the
  response's `status_code` and whether the body parsed, and classification reads those. Chosen
  over editing `enrichment.py` (outside this plan's declared region) and over inferring failure
  from the returned dict's keys (which would guess).
- **Tests:** `test_a_non_2xx_carrying_a_readable_json_body_is_still_a_failure` fails against a
  dispatcher that classifies on the return value alone.
- **Files modified:** `operator-claude-plugin/scripts/chunking.py`. **Commit:** `d958307`.
  Folded into `25-CONTEXT.md` as **D-22**.

**2. [Rule 1 — documentation bug] `25-CONTEXT.md`'s D-19 still described the FLAT list envelope**

- **Found during:** Task 1, reconciling the plan's key_links against the shipped code.
- **Issue:** D-19 records the client sending `{"providers": [...], "list": "<name>",
  "objectType": "contacts"}`. That shape shipped, passed the backend's `IF List Input` gate (a
  string is non-null) and was then refused by every request — the whole list lane dead with both
  sides' suites green. It was fixed in `13006fa` to the nested `{"list": {"name", "objectType"}}`
  and pinned from both sides, but **CONTEXT was never corrected**, so the next planner reading
  D-19 would have re-introduced it.
- **Fix:** **D-19a** added, stating the correction and that D-19's shape must not be restored.
  D-19 itself left in place — the record of what was believed is what makes the correction
  legible. **Commit:** `cf50e4c`.

### The plan's Task-2 acceptance one-liner is the D-18 form, and is broken

Acceptance criterion 5 of Task 2 is verbatim the `vars(chunking).values()` walk that D-18
records as defective on Python 3.14 — it calls `inspect.signature()` on every callable
*before* filtering on `'armed'`, so it raises `ValueError: no signature found for builtin type`
on `ChunkPlanError`. D-18 explicitly says **"25-06 must not copy the broken form"** into its
criteria; the plan copied it anyway. Not satisfied as written, and no `__init__` boilerplate was
added to an exception class to make a broken check pass. The criterion's **intent** is a
permanent test instead (`test_no_function_in_this_module_gives_armed_a_default`, D-18's
corrected form), which runs on every suite invocation rather than once at plan time. Verified:

```
$ .venv/bin/python -c "import sys,inspect;sys.path.insert(0,'operator-claude-plugin/scripts');import chunking;
p=[f for _n,f in inspect.getmembers(chunking,inspect.isfunction) if inspect.getmodule(f) is chunking and 'armed' in inspect.signature(f).parameters];
assert p and all(inspect.signature(f).parameters['armed'].default is inspect.Parameter.empty for f in p)"    # exits 0
```

### TDD gate compliance

- **Task 1: full RED → GREEN.** `48f4cac` is a genuine failing commit (`ModuleNotFoundError: No
  module named 'chunking'`), followed by `d958307`.
- **Task 2: no separate RED commit.** Its implementation was written into `chunking.py` in the
  same editing pass as Task 1's, so its tests passed on first run. Recorded rather than
  manufactured — re-staging already-passing tests as a retroactive RED commit is theatre, and a
  fabricated gate is worse than a missing one (same call, and same reasoning, as 25-04). Every
  behaviour the RED phase would have pinned is present as a test, including the four the plan
  names explicitly: the empty call log on the disarmed path, the failing middle chunk that does
  not stop the third, the timeout recorded as a failed chunk, and the failed batch excluding
  every successful id.
- No `refactor(...)` commit: none was needed.

## Test counts

Baselines were re-verified by me before writing anything, and matched the brief exactly.

| Suite | Baseline (verified) | Final | Delta | Attribution |
|---|---|---|---|---|
| plugin (`operator-claude-plugin`) | **578** | **619** | +41 | all mine, `test_chunking.py` |
| repo (`.venv/bin/python -m pytest -q`) | **1453 passed, 1 skipped** | **1494 passed, 1 skipped** | +41 | all mine |
| node (`node --test tests/n8n/<file>.test.mjs`, file form, summed) | **506 pass / 0 fail** | **506 pass / 0 fail** | 0 | this plan touches no n8n artifact |

Measured directly: `pytest operator-claude-plugin/tests/test_chunking.py -q` → **41 passed**.
Zero failures in any run. The known `mergeContacts.test.mjs` 1 ms timestamp flake did not fire;
**no test was re-run to obtain a green**, and no wall clock is read twice in anything added here
(the module reads no clock at all).

## Guard status

- **`_EXPECTED_SEND_SHAPED` is byte-identical — the allowlist was not appended to.**
  `shasum -a 256 operator-claude-plugin/tests/test_retry_reuses_dispatch.py` =
  `26bba4f2a7f71401e095846a81abc39119a5e87e48f254cb4f71721d2e2f97ad`, matching the value in the
  brief. `chunking.py` makes **no network call of its own**: it calls
  `enrichment.dispatch_enrichment`, and its transport default is `transport=requests` (the bare
  module, an `ast.Name`) called as `transport.post(...)` / `self._inner.post(...)` — never the
  `requests.post` `ast.Attribute` the guard matches (D-33).
- **No live network call** from any verification. Every dispatch test injects
  `stub_module_transport_factory` behind the autouse `no_network` guard, which was neither
  widened nor bypassed.
- **All 8 `n8n/*.json` disarmed** — `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0**.
  This plan touched no file under `n8n/`.
- **Nothing armed, deployed or activated.** No package installed (T-25-SC holds trivially).
- `git diff --name-only HEAD~3 HEAD` → exactly three files: the two in my region plus
  `25-CONTEXT.md`. Nothing outside `operator-claude-plugin/` except that shared planning surface,
  staged explicitly.

## Known Stubs

None. No placeholder, no hardcoded empty value flowing to a caller, no skipped test, no
unrun `<verify>`.

## Threat Flags

None. No new egress (the only POST is 25-04's already-documented enrichment webhook, called
once per chunk), no new credential surface, no package installed.

## What 25-07 needs to close the phase

1. **Render the plan, do not recompute it.** The preview reads `ChunkPlan.chunk_count`,
   `row_counts` and `record_count` off the object `dispatch_plan` will iterate. For a list the
   two count fields are the string `unknown` — render that word, never `0`, never a guess
   (D-02, D-21).
2. **ROADMAP Phase 25 criterion 2 still needs D-05's rewording** (the shipped default is the full
   waterfall, so saying nothing enables everything). Untouched by 25-04, 25-05 and this plan.
3. **INGEST-04's amendment #7 wording** uses `enrichment.VIEW_REFUSAL` verbatim. `plan_chunks`
   raises the same `ViewNotSupportedError` carrying the same constant, so there are still exactly
   two phrasings-of-record and they are the same object.
4. **Anything quoting the ceiling as settled is over-claiming.** Probe **B4** (full waterfall) has
   not run; the derivation is single-record, company-lane. `chunking.py` states no value, the
   example config carries both notes, and `tests/test_chunk_ceiling_contract.py` fails if the
   provisional label is removed from the config.
5. **The live proof neither 25-03 nor this plan could run** (still owed, needs no write): one
   armed-window POST naming `New Targets.xlsx` (contacts, list id 15, 102 members) should return
   the **oversize refusal**, not a 200 and not a hang. It exercises the nested envelope D-19a
   corrects, end to end, and burns zero provider credits.
6. **`STATE.md` was deliberately not updated** — the operator holds it uncommitted mid-23-06.
   25-07 (or whoever picks it up after the operator commits) owes it the Phase 25 plan-count and
   position update.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/chunking.py` — FOUND
- `operator-claude-plugin/tests/test_chunking.py` — FOUND
- `.planning/.../25-CONTEXT.md` — FOUND (modified)
- commit `48f4cac` — FOUND
- commit `d958307` — FOUND
- commit `cf50e4c` — FOUND
