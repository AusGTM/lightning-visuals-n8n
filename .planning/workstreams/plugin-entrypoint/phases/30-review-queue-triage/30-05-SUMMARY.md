---
phase: 30-review-queue-triage
plan: 05
subsystem: operator-plugin
tags: [plugin, review-queue, rendering, field-policy, config-gate, display-only]

requires:
  - phase: 30
    plan: 04
    provides: "hubspot/review/queue and its one-envelope response contract {object_type, search_ok, total, returned, rows}"
  - phase: 28
    plan: 01
    provides: "stub_module_transport_factory / _StubModuleTransport — the module-shaped transport recorder D-17's shape requires"
  - phase: 23
    plan: 05
    provides: "the display-only config-lookup pattern (D-07) and config_gate's capability table"
provides:
  - "operator-claude-plugin/scripts/review_queue.py — fetch_queue, policy_class, record_link, render_queue"
  - "config_gate's `review` capability row (n8n_url + webhook_secret), separate from contact-upload"
  - "the fetch contract 30-06 mirrors: require_capability RAISES, every runtime failure degrades to {available: False, reason}"
  - "two optional config keys: hubspot_portal_id and field_policy_path"
affects:
  - "30-06 (submits a decision against the records this renders; must reuse the same two-failure-mode split and the same PROTECTED scoping)"
  - "30-07 (the operator runbook demonstrates this rendering)"

tech-stack:
  added: []
  patterns:
    - "a read client's transport parameter defaults to the BARE requests module and calls transport.post(...), so no new function becomes send-shaped (D-17)"
    - "a config read to EXPLAIN is never read to DECIDE — the class is a label, never a branch (D-06/D-07)"
    - "a failure that renders as an empty result is the phase's recurring defect shape: search_ok:false, verified_properties:null, an empty body"

key-files:
  created:
    - operator-claude-plugin/scripts/review_queue.py
    - operator-claude-plugin/tests/test_review_queue.py
  modified:
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/tests/test_status_unknown.py
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/README.md
    - .planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-CONTEXT.md

key-decisions:
  - "`review` is its own CAPABILITY_KEYS row, not a reuse of contact-upload: a config that may read the review queue is not thereby one that may upload contacts (D-18)."
  - "fetch_queue splits its failure modes — require_capability raises ConfigError for a misconfiguration, everything at runtime degrades to {available: False, reason}. A raise for a 401 would teach the operator less than a reason; an empty rows list for one would be a lie (D-33). Folded in as D-35."
  - "The page-level PROTECTED explanation is emitted only when a field on that page is actually marked, and it names the review-decision endpoint — the 15-minute backstop does not apply the class filter while D-31 is open. Folded in as D-36."
  - "The provenance blob is fetched but never rendered: kilobyte-scale, and the held candidate already carries source/confidence/reason/evidence per field."
  - "_EXPECTED_SEND_SHAPED was not touched. The transport is the bare requests module, so the guard never fired and there was nothing to allowlist."

metrics:
  duration: ~50 min
  completed: 2026-07-31
status: complete
---

# Phase 30 Plan 05: Rendering the Review Queue Summary

The plugin can now read the flagged backlog through one authenticated POST and render it as
something a non-technical operator can adjudicate — what the CRM holds, what the pipeline
proposes, who proposed it, how sure it was, why it was held back, the evidence link, and a
HubSpot link — with protected fields marked *before* any decision is offered, and with the
protection claim scoped to the path that actually enforces it.

## What was built

**Task 1 — capability, fetch, lookup, link** (`c6c4819`, `7ca7568`)

`config_gate.CAPABILITY_KEYS` gained `"review": ("n8n_url", "webhook_secret")` plus its
`_CAPABILITY_DESCRIPTIONS` row. A separate row, not a reuse of `contact-upload` — the same
call 28 D-29 made splitting `control` from `status`, so a review-only config stays
expressible by withholding a row (D-18). `tests/test_status_unknown.py`'s two pinned
capability-set assertions were widened; the second (`{"status", "control"}` for a config
with no `webhook_secret`) is unchanged in content and was re-checked rather than assumed —
`review` needs that secret too.

`operator-claude-plugin/scripts/review_queue.py`:

| function | contract |
|---|---|
| `fetch_queue(config, object_type, limit=None, transport=requests)` | one POST to `webhook/hubspot/review/queue`, `X-Enrichment-Secret` header; returns `{available, reason, object_type, total, returned, rows}` |
| `policy_class(object_type, field, policy_path=None)` | the ownership class from `config/field_policy.yaml`, or `None`. **Display only** |
| `record_link(object_type, record_id, portal_id)` | the HubSpot URL, or `None` — never a partial URL |
| `held_decisions(row)` | the candidate JSON parsed from its raw string; `[]` for empty *or* unparseable |
| `render_queue(rows, total, policy_lookup, link_lookup)` | the whole page as markdown; **no I/O** |

**The transport is the bare `requests` module, called as `transport.post(...)`** (D-17,
Phase 28 D-28/D-33). This was the plan's known trap: mirroring `dispatch.py`'s
`transport=requests.post` would have made `fetch_queue` a new send-shaped function,
`test_retry_reuses_dispatch.py` would have gone red, and the reachable-looking fix —
appending to `_EXPECTED_SEND_SHAPED` — weakens the guard standing between a client path and
`dispatch()`'s no-default `armed` parameter. The guard never fired. `conftest.py` needed no
edit either (D-21): `stub_module_transport_factory` already existed for exactly this shape.

**Task 2 — the rendering** (`7ca7568`)

Per record: name (or email, or `Record <id>`), the HubSpot link or the raw id plus what is
missing, the machine-written flag reason, then one block per held decision in plain
language. A candidate-less record — every contact, every dedupe flag — renders its reason
and says there is nothing to approve, only a reason to record. The ICP narrative trails
where a company has one.

Two things the rendering states rather than implies:

- **Protected fields.** A held decision naming a `manual_protected` / `review_required`
  field is marked inline, and the page carries one sentence explaining what that means —
  **scoped to the review-decision endpoint**, because D-31 is open and the 15-minute
  backstop allowlists by key presence, leaving `domain` and `annualrevenue` writable on the
  documented approve path. No unscoped protection claim is made anywhere.
- **The single source.** *"The full provider-by-provider disagreement is computed during
  scoring and never stored, so a single source named here is not evidence that the providers
  agreed"* (D-08f).

## Deviations from Plan

**1. [Rule 2 — missing critical functionality] `fetch_queue` returns an availability
envelope, not bare rows**

The plan says the fetch "returns the parsed rows plus the queue total". That describes the
success path only, and this endpoint's failures are precisely the ones that impersonate an
empty queue: `search_ok: false` (D-33), a 401, a dead endpoint, an unparseable body. The
shipped shape mirrors `backend_status.fetch_backend_status` — `require_capability` raises
`ConfigError` for a misconfiguration (before any transport is constructed), and every
runtime failure degrades to `{available: False, reason, rows: [], total: None}`. **Folded in
as D-35**, because 30-06 must use the same split for `verified_properties: null` and the
empty-body case D-23 describes.

**2. [presentation, recorded so it is not undone] the PROTECTED explanation is conditional**

The page-level sentence explaining what PROTECTED means is emitted only when a field on the
page is actually marked. An unearned protection sentence on every page trains the operator
to skip the one that matters. **Folded in as D-36**, along with the decision not to render
the provenance blob (kilobyte-scale; the candidate already carries source, confidence,
reason and evidence per field).

**No `conftest.py` edit, no `test_retry_reuses_dispatch.py` edit, no `reviewApply.js` edit,
no file outside `operator-claude-plugin/` except this phase's own planning docs.**

## Verification

**No network call of any kind. Nothing armed, deployed, or activated.** Every test runs
under the autouse `no_network` guard; the fetch tests drive `stub_module_transport_factory`.

Disarmed grep, after the final code commit — 0 across all 8 `n8n/*.json`:

```
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json   ->  0 matches
```

Empty-diff guards:

| guard | result |
|---|---|
| `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` | **byte-identical to HEAD** (sha256 `26bba4f2…f97ad` both sides) — `_EXPECTED_SEND_SHAPED` still holds exactly its two entries |
| `operator-claude-plugin/tests/conftest.py` | **empty** — D-21, the fixture already existed |
| `n8n/code/reviewApply.js` | **empty** — D-15/D-31 intact, the backstop untouched |
| file deletions across both commits | **none** |

| Suite | Before | After | Attribution |
|---|---|---|---|
| `.venv/bin/python -m pytest -q` (repo root) | 1214 passed, 1 skipped | **1242 passed, 1 skipped** | +28, **all mine** — the root suite collects the plugin's tests too, so this is the same 28 as the row below |
| `node --test tests/n8n/*.test.mjs` (file form) | 474 / 0 fail | **474 / 0 fail** | unchanged, correctly — this plan touches no n8n artifact |
| plugin (`python3 -m pytest` in `operator-claude-plugin/`) | 414 | **442** | +28, **all mine**, all in `test_review_queue.py` |

Baselines matched the dispatch exactly on first measurement (1214/1, 474, 414). No sibling
executor moved them.

**Flake:** none observed. The `mergeContacts.test.mjs` 1 ms timestamp shape did not fire
across two full node runs, and this plan adds no wall-clock assertion of its own, so it
cannot join that class. It was left unfixed: it is outside this plan's `files_modified` and
outside `operator-claude-plugin/`, and no run needed a re-run to reach green.

**Pre-existing quirk, not caused by this plan:** `tests/test_write_gate_coverage.py` fails
in isolation with `ModuleNotFoundError: gen_taxonomy_js` (collection-order, `scripts/`
reaches `sys.path` only via another module's insert). It passes in the full suite. Not
touched.

## Known Stubs

None. Every function returns real data or a named reason; there is no placeholder value and
no unwired branch.

## What 30-06 needs to know

1. **Reuse D-35's two-failure-mode split.** `require_capability` raises; everything at
   runtime degrades to `{available: False, reason}`. A caller that only checks `rows == []`
   reads `search_ok: false`, a 401 and a dead endpoint as "nothing needs review". The same
   shape covers D-19's `verified_properties: null` and D-23's empty body.
2. **`review_queue.policy_class` is the display lookup — import it, do not write a second
   one.** It is display-only by construction and by docstring; a decision preview that
   branches on the returned class becomes the second policy authority D-07 forbids.
3. **Scope every protection sentence to the review-decision endpoint** (D-31 is open). The
   wording that passes the guard is in `review_queue._PROTECTED_DISCLOSURE`; reuse it rather
   than paraphrasing it looser.
4. **`review_queue.held_decisions(row)`** already parses the candidate JSON and returns `[]`
   for empty *and* unparseable — a contact is candidate-less by emptiness (D-34).
5. **`ALLOW_REVIEW_SUBMIT` is yours, and 30-05 introduced neither gate.** It is the
   plugin-side operator env var (D-16); `ALLOW_HUBSPOT_REVIEW_WRITES` is the backend baked
   constant read inside n8n. Different layers, both required.
6. **The transport rule carries over verbatim:** bare `requests` module,
   `transport.post(...)`, and `_EXPECTED_SEND_SHAPED` stays at two entries.
7. **`review` is now a real capability row** — `require_capability(cfg, "review")` works and
   `usable_capabilities` returns four names; anything pinning the old three-name set will
   fail, as `test_status_unknown.py` did.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/review_queue.py` — FOUND
- `operator-claude-plugin/tests/test_review_queue.py` — FOUND
- `operator-claude-plugin/scripts/config_gate.py` (`review` row) — FOUND
- `operator-claude-plugin/config/operator.local.example.json` (both new keys) — FOUND
- `operator-claude-plugin/README.md` (both keys documented) — FOUND
- commits `c6c4819`, `7ca7568` — both FOUND in `git log`
- no file deletions in either commit
