---
phase: 30-review-queue-triage
plan: 04
subsystem: n8n-backend
tags: [n8n, hubspot, review-queue, read-only, reachability, provenance, contacts]

requires:
  - phase: 30
    plan: 03
    provides: "the review workflow with both lanes built, the shared _REVIEW_FAMILY property tuple, REVIEW_CONTACT_PROPERTIES_CSV, and the six-outcome decision contract the queue feeds"
  - phase: 27
    plan: 01
    provides: "AWAITING_REVIEW_GROUPS — the awaiting-review predicate the status surface COUNTS with, now hoisted to module level and shared"
provides:
  - "hubspot/review/queue — one authenticated POST returns the flagged backlog with each record's stored conflict detail, no HubSpot credential client-side"
  - "the queue envelope contract 30-05 renders: {object_type, search_ok, total, returned, rows}"
  - "a structural guarantee, tested: no write node is reachable from the queue webhook, and the queue and decision branches share no node"
  - "REVIEW_QUEUE_PROPERTIES_CSV (companies) — identity + review family + provenance blob + ICP narrative"
  - "dynamic `limit` support in _hs_search_json_body_expr, so a clamped page size can be read from a parse node"
affects:
  - "30-05 (reads `.rows` off ONE envelope, not body[0] and not one item per record; must report search_ok:false as a failure; must treat a contact as candidate-less by emptiness, not key absence)"
  - "30-06 (the queue's per-record payload is the input the decision preview renders against)"

tech-stack:
  added: []
  patterns:
    - "a synchronous webhook lane over a HubSpot search emits exactly ONE item, always — a row-per-item adapter returns nothing on a zero-hit search and the caller hangs to the Cloudflare ceiling (D-22)"
    - "a predicate two surfaces disagree about is a lie to the operator: the count and the list share one module-level constant rather than two copies"
    - "onError: continueRegularOutput makes a failed search look like an empty result — an adapter over it must distinguish `no hits` from `never read`"

key-files:
  created:
    - tests/n8n/reviewQueueEndpoint.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_review_decision_cloud.json
    - scripts/deploy_n8n_workflows.py
    - .planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-CONTEXT.md

key-decisions:
  - "The response is ONE envelope, not one item per record. Forced by two committed facts, not chosen: D-22 (zero items on a zero-hit search reaches no responder and hangs the caller ~100s) and D-24 (`firstIncomingItem` would return the first record and drop the rest). An empty queue is this phase's normal end state, so the zero-hit case is the common one."
  - "`search_ok` was added beyond the plan. HubSpot search nodes run `onError: continueRegularOutput`, so a 401 arrives as an item with no `results` array — rendered as an envelope it reads `0 flagged records` and tells the operator their backlog is clear when it was never read."
  - "AWAITING_REVIEW_GROUPS was hoisted from inside build_backend_status_cloud() to module level and is now shared by Phase 27's count and this list. Two copies of the flagged predicate would let the number the operator is told and the set they are handed disagree, with no way to tell which lied."
  - "Both lanes use the same predicate, including contacts — the plan asked for ICP-flag ORing on companies only, but Phase 27 counts contacts with both flags too, and the count/list agreement is the property worth having."
  - "The companies queue set is NOT REVIEW_DECISION_PROPERTIES_CSV. That set carries every field_policy.yaml `companies` key as reviewApply's compare-and-set baseline; the queue compares nothing (the held candidate carries its own current and proposed values), so fetching the baseline for up to 100 records would be payload nobody reads."

metrics:
  duration: ~55 min
  completed: 2026-07-31
status: complete
---

# Phase 30 Plan 04: The Review Queue Read Summary

One authenticated POST to `hubspot/review/queue` now returns the flagged backlog with each
record's held candidate decisions, provenance blob, machine-written review reason and ICP
narrative — for companies or contacts, with the whole queue's total alongside the page, and
with no node on the path capable of writing.

## What was built

**Task 1 — the queue branch** (`1c90c8c`)

A second webhook on `wf_review_decision_cloud.json`, on its own row, with its own responder
and no node shared with the decision branch:

```
Review Queue Webhook (POST hubspot/review/queue, headerAuth, responseNode)
  -> Parse Review Queue Request
  -> Review Queue IF Contacts
       true  -> Review Queue Contact Search ┐
       false -> Review Queue Search         ┴-> Review Queue Rows -> Respond Review Queue
```

26 nodes total, `"active": false`. Three `NODE_CREDENTIAL_MAP` entries (the webhook on the
shared `LV Enrichment Webhook` secret, the two searches on `LV HubSpot`).

**The response contract 30-05 consumes** — one object, always:

```
{ object_type, search_ok, total, returned, rows: [ {...stored properties, hs_object_id} ] }
```

| key | meaning |
|---|---|
| `total` | the whole backlog, from the search envelope |
| `returned` | this page — `total > returned` means truncated, never "queue empty" |
| `search_ok` | `false` when the item was not a search result at all (see below) |
| `rows` | the stored properties verbatim; nothing parsed, nothing recomputed (D-11) |

**Companies rows** carry `name`, `domain`, the seven-property `lv_` review family,
`lv_enrichment_provenance`, and the ICP narrative `lv_icp_tier`, `lv_icp_fit_score`,
`lv_icp_score_breakdown`, `lv_anti_icp_reason` (the live names, from the portal schema
baseline — `config/hubspot_properties.yaml` does not declare the ICP outputs because they
predate it). **Contacts rows** reuse `REVIEW_CONTACT_PROPERTIES_CSV` unchanged: `email`,
`firstname`, `lastname`, `jobtitle`, the same review family, and
`lv_contact_enrichment_provenance`. No `domain` on a contact (D-29).

**The caller cannot say what is read.** `Parse Review Queue Request` accepts exactly
`object_type` (anything but `"contacts"` reads as companies) and `limit` (clamped to
HubSpot search's own maximum of 100; `0`, negative, non-numeric and absent all read as the
maximum, because a silent zero-length page is indistinguishable from an empty queue). The
filters and property lists are baked. `_hs_search_json_body_expr` gained expression support
for `limit` — one call to the existing `render_value`, byte-identical for every int caller.

**Task 2 — the read-only proof** (`44f72fb`)

`tests/n8n/reviewQueueEndpoint.test.mjs`, 16 tests over the committed JSON:

- a forward reachability walk from `Review Queue Webhook` asserts no reachable node is a
  HubSpot-mutating node, transcribing `tests/test_write_gate_coverage.py::_is_write_node`
  so the two definitions cannot drift apart;
- a companion test asserts the workflow's two write nodes *are* recognised as writes, so
  the guard cannot pass vacuously — verified non-vacuous by hand as well: adding an edge
  from `Review Queue Rows` to `Review Decision Update` makes the walk find it;
- the two branches share **no** node (28 D-14 — a responder fed by two request paths
  returns one caller the other's body);
- the committed nodes' own jsCode is executed through the repo's `new Function` harness:
  candidate JSON and provenance compared by **strict string equality** (any parse-and-
  reserialize fails), empty queue answers with zero rows and a zero total, a failed search
  reports `search_ok: false`, limit clamping in nine directions, `object_type` defaulting.

## Deviations from Plan

**1. [D-22/D-24 forced — the plan's shape could not work] one envelope item, not one item per row**

The plan says `Review Queue Rows` should carry the envelope's total "onto every emitted
row". Two committed facts rule that out: `rows.map(...)` emits **zero** items on a zero-hit
search, which on a `responseNode` webhook means the caller hangs to the ~100s Cloudflare
ceiling (D-22) — and an empty queue is this phase's *normal* end state, not an edge case;
and `Respond Review Queue` is `firstIncomingItem` (D-24), so a per-row emission would return
one record and drop the rest. The node emits exactly one envelope, always. **Folded in as
D-32.**

**2. [Rule 2 — missing critical functionality] `search_ok`, not in the plan**

HubSpot search nodes are built `onError: continueRegularOutput`. A 401, a 429 or a
malformed response therefore arrives at the adapter as an item with no `results` array,
which as an envelope renders `total: 0, rows: []` — an operator told their backlog is clear
when it was never read. One boolean distinguishes "no hits" from "never read". **Folded in
as D-33.**

**3. [reuse over the plan's asymmetry] both lanes OR both review flags, via one shared constant**

The plan has the companies search add the ICP-flag group and the contacts search filter on
the enrichment flag alone. Phase 27's status surface already counts *both* object types with
both flags (`AWAITING_REVIEW_GROUPS`). A queue whose predicate is narrower than the count's
would hand the operator fewer records than the number they were shown, with nothing to say
which was wrong. The constant was hoisted from inside `build_backend_status_cloud()` to
module level and is now the single definition both use; the status workflow JSON is
byte-unchanged.

**4. [correction to 30-03's handoff] contacts DO request the candidate-JSON property**

30-03 told 30-04 that contacts render with "no candidate JSON". True of the content, not of
the property list — the key belongs to `_REVIEW_FAMILY`, the tuple both lanes deliberately
share, and HubSpot returns `""`. The test asserting its absence failed and the *test* was
wrong. 30-05 must treat a contact as candidate-less by emptiness, not by key absence.
**Folded in as D-34.**

## What the queue does NOT claim

Deliberate, because of **D-31 (open)**. The workflow's new sticky note states that the
`manual_protected` / `review_required` class filter belongs to the **decision endpoint**,
and says in the same breath that it does **not** describe the 15-minute `Apply Review`
backstop, which still allowlists by key. No queue-side copy anywhere claims protected fields
are protected in general. `n8n/code/reviewApply.js` was not touched.

The queue also does not compute which fields a decision would withhold — it returns the
candidate JSON verbatim, and 30-05 reads `config/field_policy.yaml` client-side (D-06/D-07)
to show the operator a protected field **before** they approve. That is the whole reason the
strings pass through unparsed.

## Verification

**No network call of any kind. Nothing armed, deployed, or activated.**

Disarmed grep, run before staging and again after the final code commit — 0 across all 8
`n8n/*.json`:

```
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json   ->  0 matches
```

Empty-diff guards, measured across both code commits (`git diff --stat HEAD~2 HEAD -- <path>`):

| guard | result |
|---|---|
| `n8n/code/reviewApply.js` | **empty** — D-15/D-31 intact, the backstop's engine untouched |
| `n8n/wf_scheduled_maintenance_cloud.json` | **empty** — the 15-minute backstop is intact (D-08e) |

Rebuild is idempotent and scoped: re-running `scripts/build_cloud_workflows.py` leaves the
seven other workflow JSONs byte-identical; only `wf_review_decision_cloud.json` changed, and
its three deleted lines are node-id counter shifts, nothing else.

| Suite | Before | After | Attribution |
|---|---|---|---|
| `.venv/bin/python -m pytest -q` | 1214 passed, 1 skipped | **1214 passed, 1 skipped** | **unchanged, correctly** — the review workflow already entered every `wf_*_cloud.json` glob in 30-02, so a new branch widens assertions inside existing tests rather than adding cases |
| `node --test tests/n8n/*.test.mjs` (file form) | 458 / 0 fail | **474 / 0 fail** | +16, **all mine**, all in `reviewQueueEndpoint.test.mjs` |
| plugin (`python3 -m pytest` in `operator-claude-plugin/`) | 414 | **414** | untouched by this plan |

Baselines matched the dispatch exactly on first measurement (1214/1, 458, 414). No sibling
executor moved them. **No flake of any kind was seen** across ~8 node runs — no `407/1`, and
no 1 ms timestamp mismatch; this plan introduces no wall-clock assertion, so it cannot join
that class.

**One pre-existing quirk worth recording, not caused by this plan:** the plan's `<verify>`
line runs `tests/test_write_gate_coverage.py` in a *narrow selection*, and in that form it
fails with `ModuleNotFoundError: No module named 'gen_taxonomy_js'` — `scripts/` reaches
`sys.path` only via another test module's `sys.path.insert`, so the failure is
collection-order, not behaviour. Adding any path-inserting module (e.g.
`tests/test_builder_flag_parity.py`) to the same selection makes all 170 pass, and the full
suite passes unconditionally. Verified against the unmodified guard logic.

## Known Stubs

None. The queue reads what exists; there is no placeholder value, no empty return wired to
a UI, and no unfinished branch.

## What 30-05 needs to know

1. **Parse ONE dict with a `rows` array** — not `body[0]`, not one item per record. The
   contract is `{object_type, search_ok, total, returned, rows}`.
2. **`search_ok: false` is a FAILURE, never an empty queue.** Same rule D-19 sets for a
   written decision arriving with `verified_properties: null`.
3. **`total` vs `returned`** is how you tell the operator a page is a page. Say the number
   out loud; a shorter page than the total is the normal case at `limit` defaults.
4. **`lv_enrichment_review_candidate_json` and the provenance blob arrive as raw strings.**
   Parsing is yours. The provenance blob is one JSON object per record and can be
   kilobytes — do not dump it raw at the operator.
5. **Show `manual_protected` / `review_required` BEFORE the operator decides** (D-06), by
   reading `config/field_policy.yaml` client-side against the candidate's field names. Scope
   any wording about protection to the decision endpoint — **D-31 is open**, and the
   15-minute backstop does not enforce the class filter.
6. **A contact is candidate-less by EMPTINESS, not key absence** (D-34), renders from
   `email`/`firstname`/`lastname`/`jobtitle` + `lv_contact_enrichment_provenance`, has no
   `domain`, and can only ever be *rejected* (an approve returns `no_candidate`, D-27).
7. **`hs_object_id` is on every row** — that is what becomes the HubSpot record link.

## Self-Check: PASSED

- `tests/n8n/reviewQueueEndpoint.test.mjs` — FOUND
- `n8n/wf_review_decision_cloud.json` — FOUND (26 nodes, two webhooks, `active: false`)
- `scripts/build_cloud_workflows.py`, `scripts/deploy_n8n_workflows.py` — FOUND
- `.planning/.../30-04-SUMMARY.md` — FOUND
- commits `1c90c8c`, `44f72fb` — both FOUND in `git log`
- no file deletions in either commit (`git diff --diff-filter=D HEAD~2 HEAD` empty)
