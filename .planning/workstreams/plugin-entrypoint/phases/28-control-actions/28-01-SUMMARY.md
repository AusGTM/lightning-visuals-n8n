---
phase: 28-control-actions
plan: 01
subsystem: operator-claude-plugin
tags: [n8n-api, mutation, control, verification, allowlist, transport-seam]
requires:
  - n8n_read.get_workflow (27-01)
  - config_gate.require_capability (27-03)
provides:
  - n8n_control.set_active
  - n8n_control.apply_mutation
  - n8n_control.assert_only_allowlisted_change
  - n8n_control.put_body
  - n8n_control.MutationResult
  - n8n_control.MutationRefused
  - config_gate capability "control"
  - conftest fixture stub_module_transport_factory
affects:
  - 28-02 (live probe), 28-03 (arming), 28-04 (cadence), 28-05 (operator surface)
tech-stack:
  added: []
  patterns:
    - module-shaped injectable transport (transport=requests, called as transport.get/.post/.put)
    - structural pre-flight diff as a refusal, not a convention
    - verdict from an independent read, never from a status code
key-files:
  created:
    - operator-claude-plugin/scripts/n8n_control.py
    - operator-claude-plugin/tests/test_control_pipeline.py
    - operator-claude-plugin/tests/test_control_allowlist_diff.py
    - operator-claude-plugin/tests/test_control_verify_reporting.py
  modified:
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_transport_guard.py
    - operator-claude-plugin/tests/test_status_unknown.py
decisions:
  - "apply_mutation's verify_fn is required with no default — a narrow caller-supplied reader, never a whole-body comparison"
  - "The deactivate/activate bracket is skipped entirely when the workflow was already off"
  - "A refusal's enforceable invariant is zero MUTATING calls, not zero calls — the always-fetch-fresh GET precedes it"
metrics:
  duration: ~35 min
  completed: 2026-07-31
status: complete
requirements: [CONTROL-02, CONTROL-05, CONTROL-06, CONTROL-07]
---

# Phase 28 Plan 01: Control-Action Mutation Pipeline Summary

One mutation pipeline — capture prior state, refuse anything outside the allowlist before
touching the network, mutate inside a prior-active-restoring bracket, then decide the verdict
from a *separate* read — proven end to end on CONTROL-02's workflow on/off toggle.

## What was built

`operator-claude-plugin/scripts/n8n_control.py`, the milestone's only backend-mutating module:

| Function | What it does |
|---|---|
| `set_active(workflow_id, desired_active, config, transport)` | GET prior state → bodyless POST to `/activate` or `/deactivate` → **separate** GET → verdict from that fetched `active` field |
| `put_body(workflow)` | Filters to `(name, nodes, connections, settings)`; every other top-level key is a 400 from n8n, not a silent strip |
| `assert_only_allowlisted_change(original, modified, allowed_node_names)` | Raises `MutationRefused` naming the specific node or top-level key that differed |
| `apply_mutation(workflow_id, mutate_fn, allowed_node_names, config, *, verify_fn, transport)` | Fetch fresh → deep-copy → mutate → **refuse before any network call** → deactivate → PUT → restore *prior* active state → independent read-back |
| `MutationResult` | `action, prior, requested, observed, verdict, reversal, detail` + `.verified` |

`config_gate.CAPABILITY_KEYS` gained one row: `"control": ("n8n_url", "n8n_api_key")` — the same
two keys `"status"` needs, kept a separate row so "may read but must not mutate" stays expressible.
28-05 calls `require_capability(cfg, "control")` at the surface.

### The verdict rule, in one place

`_verdict(requested, observed)` is the only function in the module that can produce `VERIFIED`, and
it does so only when an independently fetched value is non-`None` and equals the requested one. Every
other outcome — a non-2xx, a raising transport, an unreadable read-back, a read-back still showing
the old value — is `FAILED` with a `detail` naming observed-vs-requested. A structural test asserts
every `MutationResult(...)` construction site takes its verdict from either the `FAILED` constant or
`_verdict`'s own return, so a branch the behavioural matrix does not reach still cannot be optimistic.

## Reuse, not rebuild

- **No `fetch_workflow`.** `n8n_read.get_workflow(config, workflow_id, transport)` (27-01) is the
  same GET, same header, same `None`-on-every-failure contract — which feeds the `failed` verdict
  directly. Asserted by test, and `grep -c "def read_write_safety\|def fetch_workflow"` returns 0.
- **No second write-safety reader or declaration regex** (D-26).
- **No import of `deploy_n8n_workflows.py`.** The four-key tuple is copied verbatim with a source
  comment and held in parity by a test that reads the deploy script as **text** (PLUGIN-04 intact).

## The transport seam (D-28 / D-33) — what 28-02, 28-03, 28-04 inherit

`transport` defaults to the **bare `requests` module**, and every call goes through
`transport.get` / `transport.post` / `transport.put`. The send verbs are fetched by name off the
transport (`getattr(transport, verb)`), never named as attributes of the `requests` module, so
`test_retry_reuses_dispatch.py`'s AST guard is **satisfied rather than widened**.

**`_EXPECTED_SEND_SHAPED` is byte-identical to before this plan** — `git diff` on that whole file is
empty, verified after every commit.

A module-shaped recorder was the missing piece D-33 predicted. New in `conftest.py`:

```
stub_module_transport_factory  ->  _StubModuleTransport(responses=None)
    .get(url, headers, params, timeout)     ─┐
    .post(url, headers, json, timeout)       ├─ one shared, ordered `calls` list
    .put(url, headers, json, timeout)       ─┘
    .verbs           -> ["get", "post", "put", ...]
    .mutating_calls  -> post/put entries only
```

Scripted entries reuse the existing `_as_response` vocabulary (bare payload = 200,
`(status, payload)` pair, or an `Exception` raised as a transport failure). **Two things 28-02/03/04
must get right:**

1. **Hand `n8n_read` `transport.get`, not `transport`** — `_get_json` *calls* what it is given.
   `n8n_control` does this at all three read sites; copy the call, not the parameter.
2. **Assert `transport.mutating_calls == []` for refusals, never `len(calls) == 0`** — see the
   deviation below.

Expected call sequences, for writing later tests against:

| Case | Sequence |
|---|---|
| `set_active` (any) | `get, post, get` |
| `apply_mutation`, workflow was **active** | `get, post(deactivate), put, post(activate), get` |
| `apply_mutation`, workflow was **inactive** | `get, put, get` |
| refusal | `get` only |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Plan defect] "A refusal makes ZERO network calls" is self-contradictory**

- **Found during:** Task 2
- **Issue:** The plan requires `apply_mutation` to always fetch fresh and never accept a cached
  workflow (T-28-06), *and* requires the recording transport's call log to be empty after a refusal.
  The refusal cannot be computed without that fetch, so the two cannot both hold.
- **Fix:** Implemented the invariant the threat register actually needs — a refusal makes no
  **mutating** call. The recorder exposes `mutating_calls`; the test asserts
  `transport.mutating_calls == []` **and** `transport.verbs == ["get"]`, which is strictly more
  specific than the plan's wording (it also proves no *second* read happened).
- **Files:** `tests/test_control_allowlist_diff.py`, `tests/conftest.py`
- **Commit:** `6305335`

**2. [Rule 3 — Blocking] Adding a `CAPABILITY_KEYS` row broke two assertions outside `files_modified`**

- **Found during:** Task 1
- **Issue:** `tests/test_status_unknown.py` pins the exact capability set twice. Adding `"control"`
  failed both. Correct behaviour, stale assertions — but the file is not in the plan's
  `files_modified`.
- **Fix:** Both assertions now compare sets including `"control"`. Two lines, no coverage lost.
- **Files:** `operator-claude-plugin/tests/test_status_unknown.py`
- **Commit:** `b215a8e`

**3. [Rule 1 — Bug] `_quote` backslash-escaped the quotes inside a JS flag literal**

- **Found during:** Task 3
- **Issue:** `json.dumps` turned `const ALLOW_HUBSPOT_RECORD_WRITES = "true";` into
  `"const ALLOW_HUBSPOT_RECORD_WRITES = \\"true\\";"` inside the operator-facing `detail` sentence.
- **Fix:** String values pass through unescaped (still length-capped); non-strings still go through
  `json.dumps`.
- **Commit:** `dd49124`

**4. [Design, within Claude's discretion] `verify_fn` is required, and the bracket skips both calls
when the workflow was already off**

- The plan says `apply_mutation` should "hand the fetched object to the caller's verdict check".
  Made concrete as a required keyword-only `verify_fn` with **no default** (mirroring `dispatch()`'s
  no-default `armed`), because a whole-body default comparison would fail on n8n's server-side
  normalization and would then get loosened — which is how status-code optimism returns.
- Deactivating an already-inactive workflow is a pointless mutating call, and re-activating it is
  the exact side effect D-24 forbids. Both calls are skipped when `prior_active` is false.

All four are folded into `28-CONTEXT.md` as **D-35** (D-34 was taken by a concurrent operator commit,
`2c8790a`, mid-execution).

### TDD note

Tasks 2 and 3 are marked `tdd="true"`, but Task 1's `<action>` said "Create `n8n_control.py`" and the
module was written whole there, so Tasks 2 and 3's implementations pre-existed their tests — no
genuine RED phase was possible. Rather than delete and retype working committed code, the RED gate's
actual guarantee (the tests are not vacuous) was obtained by **mutation testing**. Four mutants, each
restored immediately after:

| Mutant | Result |
|---|---|
| `assert_only_allowlisted_change` short-circuited to a no-op | **8 failed** |
| `put_body` returns the workflow unfiltered | **3 failed** |
| `_restore_active` activates unconditionally (blind activate) | **3 failed** |
| `_verdict`'s comparison short-circuited to always-`VERIFIED` | **2 failed** (5 across the full set) |

Every guard this plan ships is proven to bite.

## Threat mitigations applied

| Threat | Where |
|---|---|
| T-28-01 tampering via the outgoing body | `assert_only_allowlisted_change` runs before any network call; refusal test asserts an empty mutating-call log |
| T-28-02 repudiation via an optimistic verdict | `_verdict` is the single source of `VERIFIED`; a 15-case matrix plus an AST check on every construction site |
| T-28-03 EoP via blind reactivation | `_restore_active` returns early when `prior_active` is false; tested |
| T-28-04 tampering via the test suite | `requests.put` and `requests.get` now asserted to raise inside a test |
| T-28-06 stale in-session copy | `apply_mutation` takes no workflow argument; asserted by signature introspection |
| T-28-30 guard widened to fit this phase | `git diff` on `test_retry_reuses_dispatch.py` is empty |

## Safety posture

- **Nothing was exercised live.** No arm, no deploy, no activation, no live PUT, no HubSpot call.
  Every network path in this plan ran against the in-process recorder.
- `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0 across all artifacts**, unchanged.
- No n8n workflow JSON was touched by this plan.

## Test counts

| Suite | Before | After | Δ |
|---|---|---|---|
| `pytest -q` (repo root, includes the plugin's) | 1117 passed, 1 skipped | **1163 passed, 1 skipped** | +46 |
| plugin suite (`operator-claude-plugin/`) | 354 passed | **400 passed** | +46 |
| `node --test tests/n8n/*.test.mjs` | 404 tests / 404 pass | **404 tests / 404 pass** | 0 |

Node was **404, not the handoff's 400** — the four extra are the Apollo sentinel tests another branch
added; no node file was touched by this plan. One flaky node failure was observed on a first run
(`mergeContacts.test.mjs:67`, a 1-millisecond `lv_jobtitle_verified_at` timestamp mismatch inside a
`deepStrictEqual`) and did not reproduce on two subsequent runs. **Pre-existing, unrelated to this
plan, logged to `deferred-items.md`.**

## Verification performed

```
grep -c "def read_write_safety\|def fetch_workflow" .../n8n_control.py      -> 0
grep -vE '^\s*#' .../n8n_control.py | grep -cE 'transport\s*=\s*requests\.(post|put)'  -> 0
grep -nE 'requests\.(put|post|get)\(' .../n8n_control.py                   -> no output
grep -n 'os.getenv\|os.environ' .../n8n_control.py                         -> no output
git diff --stat .../test_retry_reuses_dispatch.py                          -> empty
python3 -c "... put_body(wf_enrichment_cloud.json) == 4 keys"              -> exit 0
```

## What 28-02 / 28-03 / 28-04 need from this

- Import `n8n_control`; do **not** write a second fetcher, a second PUT filter, or a second diff.
- Take `transport=requests` (bare module) — appending to `_EXPECTED_SEND_SHAPED` is forbidden and,
  after this plan, unnecessary: `getattr(transport, verb)(...)` is the shape that passes.
- Use `stub_module_transport_factory` for every recording-transport criterion in the phase.
- Call `apply_mutation` with a **narrow** `verify_fn`: `n8n_arming` should pass a reader built on
  `n8n_read.read_write_safety`; `n8n_cadence` should pass a Schedule-Trigger reader.
- **Open for 28-05:** D-34's uniform `ALLOW_*` rule landed mid-execution and names `ALLOW_N8N_ARM`
  for `n8n_arming`. Whether `n8n_control`'s mutating entry points need an `ALLOW_N8N_CONTROL` peer is
  a surface decision 28-01 deliberately did not make.

## Self-Check: PASSED

Files verified present: `n8n_control.py`, `test_control_pipeline.py`,
`test_control_allowlist_diff.py`, `test_control_verify_reporting.py`.
Commits verified in `git log`: `b215a8e`, `6305335`, `dd49124`.
