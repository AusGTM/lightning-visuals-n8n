---
phase: 30-review-queue-triage
plan: 02
subsystem: n8n-backend
tags: [n8n, hubspot, review-writeback, write-safety, read-back-verification, webhook, tracer]

requires:
  - phase: 30
    plan: 01
    provides: "ALLOW_HUBSPOT_REVIEW_WRITES and the `review` branch inside _writeSafetyAllows that this plan's write gate passes"
  - phase: 28
    plan: 01
    provides: "D-13/D-14 confirm-then-verify — an accepted response is never evidence, which is why the refetch node exists"
provides:
  - "hubspot/review/decision — a synchronous, headerAuth'd review-decision endpoint in its own Cloud workflow, committed inactive and disarmed"
  - "n8n/code/reviewDecision.js — buildReviewDecision({decision, reason, reviewedBy, row, nowIso}) -> {properties, outcome, message}"
  - "the response contract 30-06 consumes: {outcome, message, would_write, verified_properties, verified}, verified_properties null on dry-run and on every non-writing outcome"
  - "Review Verify Fetch — an INDEPENDENT post-PATCH refetch, the first read-back in this repo that is not the write's own echo"
affects:
  - "30-03 (adds approve + contacts onto this proven skeleton; reviewApply/mergeCompanies are already inlined in Build Review Decision)"
  - "30-06 (verify_decision reads this contract; see D-23/D-24 for the two shapes it must handle)"
  - "30-07 (the armed window fires against this workflow, which verify_live_write_safety.py does NOT currently read back)"

tech-stack:
  added: []
  patterns:
    - "a synchronous webhook lane must emit exactly one item on a zero-hit search — the scheduled lanes' zero-items-means-nothing-to-do adapter hangs a responseNode webhook (D-22)"
    - "read-back verification is a SECOND read of the record, issued after the write, on the write branch only; the write's own 200 body is never the evidence"
    - "the routing boolean an IF switches on is `caller asked for a write AND there is a write to perform`, so every non-writing outcome reaches the responder without passing the write gate"

key-files:
  created:
    - n8n/code/reviewDecision.js
    - n8n/wf_review_decision_cloud.json
    - tests/n8n/reviewDecisionEndpoint.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - tests/test_architecture_guard.py
    - .planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-CONTEXT.md

key-decisions:
  - "A rejection's patch has exactly one key. Not 'one key plus a reviewed-at for the audit trail' — stamping reviewed-at on a rejection is the first step of the silent de-queueing REVIEW-05 forbids, and the audit record of a rejection is the reason text itself plus the record still being in the queue."
  - "Review Verify Fetch requests the SAME property set as the pre-write fetch (review family + every config/field_policy.yaml `companies` key), so verified_properties can always cover any would_write key, including the canonical fields 30-03's approve path will write."
  - "The policy field list is DERIVED from config/field_policy.yaml at build time, never re-typed. A policy field added later and not refetched would come back undefined and read to reviewApply's compare-and-set as a manual edit, silently turning every such decision stale."
  - "`verified` is computed but is explicitly not the authority — the client re-derives it. Nothing in the node ever defaults it to true, so an unreadable read-back reports null and 30-06 reports failure."
  - "The write gate dropping a row produces NO response at all (D-23). A structured 'gate denied' reply was rejected: an else-branch out of the gate is a path around the write gate, and 'every write node sits directly behind a gate' is the one property test_write_gate_coverage.py exists to guarantee."
  - "STATE.md / ROADMAP.md / REQUIREMENTS.md were NOT touched, by explicit dispatch instruction (an operator holds STATE.md uncommitted mid-23-06). REVIEW-03/REVIEW-05 are a six-plan chain and are not complete at 30-02."

metrics:
  duration: ~55 min
  completed: 2026-07-31
status: complete
---

# Phase 30 Plan 02: Synchronous Review-Decision Endpoint Summary

`hubspot/review/decision` now takes one operator decision end to end — authenticated POST,
live refetch, decision, gated PATCH, **independent re-read**, one response shape — and a
rejection reaches HubSpot as exactly one property write that leaves the record in the queue.

## What was built

**Task 1 — `n8n/code/reviewDecision.js`** (`224561e` RED, `9470f03` GREEN)

`buildReviewDecision({decision, reason, reviewedBy, row, nowIso}) -> {properties, outcome,
message}`. Pure, no I/O, no throw path, requires nothing outside `n8n/code/`. Outcomes:

| outcome | when | properties |
|---|---|---|
| `rejected` | `reject` on a flagged row | exactly `{lv_enrichment_review_reason: <text>}` |
| `not_flagged` | row carries neither review flag and no held candidate | `{}` |
| `unsupported` | `approve` (30-03 replaces this branch) | `{}` |
| `refused` | unknown decision word, missing record, non-string reason | `{}` |

`reviewedBy` / `nowIso` are accepted and deliberately unused — they belong to 30-03's
approve path, which stamps `lv_enrichment_reviewed_by` / `_at`. A rejection stamps neither,
never clears `lv_enrichment_needs_review` or `lv_icp_needs_review`, and never blanks
`lv_enrichment_review_candidate_json` (D-10). Asserted by **key count** and by explicit
key-**absence**, not by string search — writing a flag as `false` and omitting it are
indistinguishable to a grep and opposite to HubSpot.

Reason handling per D-09: absent/null reads as `""` and still produces a decision; a
wrong-typed reason is refused rather than silently emptied; over-length is truncated at
60000, never refused.

**Task 2 — `n8n/wf_review_decision_cloud.json`** (`1089923`)

```
Review Decision Webhook (POST, headerAuth, responseNode)
  -> Parse Review Decision
  -> Review Fetch By Id            (_hs_http_search_node, hs_object_id EQ)
  -> Review Extract Record
  -> Build Review Decision         (inlines mergeCompanies + reviewApply + reviewDecision)
  -> Review IF Dry Run
       true  -> Build Review Response
       false -> Review Decision Update Write Gate -> Review Decision Update (PATCH)
                -> Review Verify Fetch -> Build Review Response
  -> Respond Review Decision
```

12 nodes. `"active": false`. The single write node is gated with
`splice_write_gates(..., {"Review Decision Update": "review"})`, so it is authorised by
`ALLOW_HUBSPOT_REVIEW_WRITES` plus the shared `TEST_RECORD_*` allowlist and by **neither**
dispatch constant. Four new credential-bearing nodes registered in `NODE_CREDENTIAL_MAP`;
the workflow added to `tests/test_architecture_guard.py`'s `ACTIVE` deployable set.

`Parse Review Decision` reads **six keys and nothing else** — `object_type`, `record_id`,
`decision`, `reason`, `reviewed_by`, `dry_run`. `dry_run` defaults to `true` when absent or
non-boolean; `record_id` is coerced digits-only or `null`. There is no path from the request
body into the patch: the value written always comes from the record's own refetched state.

## The response contract, field by field (D-19)

Both branches route through `Build Review Response`, so the client sees one shape:

| field | dry-run branch / non-writing outcome | write branch |
|---|---|---|
| `outcome` | `rejected` \| `not_flagged` \| `unsupported` \| `refused` | `rejected` |
| `message` | human-readable string, always present | same |
| `would_write` | the exact patch the backend computed (`{}` when nothing to write) | same patch, which was applied |
| `verified_properties` | **`null`** | the **refetched** record's values for exactly the `would_write` keys — or `null` if the refetch returned no row |
| `verified` | **`null`** | key-by-key `String(...)` comparison of `would_write` against `verified_properties`; `null` wherever `verified_properties` is |

`verified_properties` comes from `Review Verify Fetch` — a **second** `_hs_http_search_node`
issued after the PATCH, same `hs_object_id` filter, same property set. Never HubSpot's PATCH
echo: the echo is the same response, so comparing a write to it proves the request was
well-formed and nothing else (Phase 28 D-14). The node sits on the write branch **only**, so
a dry run never pays for it. Nothing ever defaults `verified` to `true` — a written decision
arriving with `verified_properties` null is a failure for 30-06 to report.

**Task 3 — flow tests** (`8c8a92d`)

25 cases in `tests/n8n/reviewDecisionEndpoint.test.mjs`, all reading jsCode out of the
committed workflow JSON and running it through `new Function` (the repo's existing idiom).
No network call anywhere.

| case | proves |
|---|---|
| (a) | `dry_run` absent → previews exactly the review-reason property, gate never fed |
| (a2) | a non-writing outcome routes to the response even with `dry_run: false` |
| (b) | committed/disarmed gate → 0 items |
| (c) | **only** `ALLOW_HUBSPOT_REVIEW_WRITES` armed + matching allowlist → 1 item |
| (c2) | review armed with an **empty** allowlist → still 0 (inherited, correct, asserted) |
| (d) | the two dispatch constants armed instead → 0 items |
| (e) | injected `properties`/`field`/`value` keys leave the patch byte-identical |
| (f1–f5) | all five contract keys on every branch, including refetch-found-nothing → `null` |

(b) and (c) differ only in which constant is armed, so the pair fails the moment the review
gate starts reading a dispatch constant — the reverse-direction proof 30-01 could not yet
make. (c) also carries the row-carry assertion: `built.domain` survives the spread, because
a gate reading a field its lane does not emit has cost this repo two armed windows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — missing critical functionality] `ENRICH_EXTRACT_SEARCH_ROWS` would have hung the webhook on a not-found record**

- **Found during:** Task 2, tracing the not-found path the plan's own "a missing record →
  refused" behaviour implies.
- **Issue:** the shared adapter ends `return rows.map(...)` — **zero items on a zero-hit
  search**. On the four scheduled branches that correctly means "nothing to do". On this
  lane it means nothing reaches `Respond Review Decision`, and the caller waits out the
  ~100s Cloudflare ceiling instead of being told the record was not found. Every bad
  `record_id`, every deleted record, every 401 on the fetch would have hit it.
- **Fix:** `REVIEW_EXTRACT_RECORD` — the same envelope handling plus a
  `{hs_object_id: null, record_found: false}` marker on zero hits, which
  `buildReviewDecision` turns into `refused`. The shared constant is untouched.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Commit:** `1089923` · **Recorded as D-22.**

**2. [Rule 2 — missing critical functionality] a record flagged only by `lv_icp_needs_review` would have been un-adjudicable**

- **Found during:** Task 1, writing the `not_flagged` cases.
- **Issue:** the plan's predicate is "needs-review flag falsy **and** candidate JSON empty".
  Taken literally, a record flagged solely by `lv_icp_needs_review` — a legitimate queue
  member, since `wf_backend_status_cloud`'s `AWAITING_REVIEW_GROUPS` ORs the two flags —
  is refused as not-in-the-queue, and the operator can never reject it. Compounding it:
  HubSpot returns booleancheckbox values as the **strings** `"true"`/`"false"`, so a bare
  truthiness test reads `"false"` as flagged.
- **Fix:** flagged = `lv_enrichment_needs_review` truthy **or** `lv_icp_needs_review` truthy
  **or** a held candidate other than `""`/`"[]"`, with a `_truthy()` that normalises the
  string form. Named test case for the ICP-only row.
- **Files modified:** `n8n/code/reviewDecision.js`, `tests/n8n/reviewDecisionEndpoint.test.mjs`
- **Commit:** `9470f03` · **Recorded as D-25.**

### Deliberate departures from the plan's wording

- **`respondWith: firstIncomingItem`**, not the `allIncomingItems` the two existing
  responders use. One decision is adjudicated per request, so the client gets the contract
  object rather than a one-element array. **Recorded as D-24** — 30-06 parses a dict.
- **The policy field list is derived from `config/field_policy.yaml`** rather than hand-typed
  (one new `import yaml` in the builder). The plan said "every `DEFAULT_COMPANY_POLICY`
  field name"; typing them would drift, and a policy field that is not refetched reads to
  reviewApply's compare-and-set as a manual edit.
- **`Review IF Dry Run` switches on a routing boolean**, not a bare echo of the request:
  `!(parsed.dry_run === false && hasWrite)`. The plan requires that an empty `properties`
  reach the response without touching the write gate, and an IF on the raw request value
  cannot express that.

### Not a deviation, but worth recording

- **Every re-derived line citation in the plan was accurate.** `4113` (the enrichment
  `Respond to Webhook`, correctly disambiguated from `3401`/`3533`), `4714`, `4842`, `4882`,
  `3921`, `5010`, `5403`; `deploy_n8n_workflows.py:45-115`;
  `test_architecture_guard.py:18-45`. Nothing needed re-derivation by symbol.
- **`reviewApply.js` and `wf_scheduled_maintenance_cloud.json`'s review lane are untouched**
  — `git diff` on both is empty across this plan's four commits. The 15-minute backstop's
  contract is unchanged (D-08d/D-15), and `tests/n8n/reviewLoop.test.mjs` passes untouched.

## Known Stubs

- `decision: "approve"` returns `outcome: "unsupported"` with an empty patch, by design —
  the plan's own scope split. 30-03 replaces that branch by routing approve through
  `reviewApply` (already inlined in `Build Review Decision`, so it is a wrapper edit).
- `object_type: "contacts"` is refused with "only company records are served by this
  endpoint yet". 30-03 adds the contacts lane. Both are declared in the plan, not silent.

## Verification

**No network call of any kind. Nothing armed, deployed, or activated.**

Disarmed grep, run before staging and again after the final code commit:

```
n8n/wf_backend_status_cloud.json:0        n8n/wf_enrichment_local.json:0
n8n/wf_contact_ingest_cloud.json:0        n8n/wf_review_decision_cloud.json:0
n8n/wf_contact_ingest_local.json:0        n8n/wf_scheduled_maintenance_cloud.json:0
n8n/wf_enrichment_cloud.json:0            n8n/wf_enrichment_local_live.json:0
```

| Suite | Before | After |
|---|---|---|
| `node --test tests/n8n/*.test.mjs` | 408 pass / 0 fail | **433 pass / 0 fail** (+25, all mine) |
| `.venv/bin/python -m pytest -q` | 1165 passed, 1 skipped | **1214 passed, 1 skipped** |
| plugin suite | not run (owned by the concurrent 29-02) | not run |

**The pytest delta is NOT all mine, and the baseline moved under me.** The concurrent 29-02
executor committed three times during this plan (`ac333af`, `0937b05`, `0e7e527`) and held
`scripts/enrichment_cost_ledger.py` modified. Measured sequence: 1165 (start, with 29-02's
then-uncommitted `test_sweep_fixtures.py` ignored) → 1177 → 1191 → 1214. **22 of the
collected tests match `review_decision`** — this plan's contribution is those, via the new
workflow entering the `wf_*_cloud.json` globs in `test_architecture_guard`,
`test_write_gate_coverage`, `test_row_carry`, `test_deploy_credential_binding`,
`test_hubspot_node_auth` and `test_node_name_uniqueness`. The rest of the +49 is 29-02's.

**The node count is unambiguous: 408 → 433, +25, exactly this plan's new test file.** The
`407/1` flake 30-01 logged did **not** recur in any of the ~6 node runs during this plan.

**Rebuild is idempotent:** re-running `scripts/build_cloud_workflows.py` after the change
left the seven pre-existing workflow JSONs byte-identical (`git status` showed only the new
file untracked).

**One pre-existing test-isolation quirk, not introduced here and not fixed here:**
`.venv/bin/python -m pytest tests/test_write_gate_coverage.py` **alone** fails with
`ModuleNotFoundError: No module named 'gen_taxonomy_js'` at `build_cloud_workflows.py`'s
own bare sibling import. `scripts/` reaches `sys.path` only via another test module, so the
file passes in the full suite and in any run that includes e.g.
`tests/test_enabled_build_invariants.py`. The failing import line is untouched by this plan
(the `import yaml` added above it resolves fine). Out of scope — logged, not chased.

## What 30-03 needs to know

1. **The skeleton is proved; you are adding branches, not plumbing.** `mergeCompanies.js`,
   `reviewApply.js` and `reviewDecision.js` are **already inlined** in `Build Review
   Decision`, unused on this plan's branches precisely so approve is a wrapper edit. Route
   approve through `reviewApply(row.lv_enrichment_review_candidate_json, row)` — do not
   fork its compare-and-set (D-08d/D-15).
2. **`Review Fetch By Id` already requests the full compare-and-set baseline** — the review
   family plus every `config/field_policy.yaml` `companies` key, derived not typed. You do
   not need to widen it, and you must not narrow it.
3. **`Review Verify Fetch` requests that same set**, so `verified_properties` already covers
   the canonical fields approve will promote. Adding a written property needs no change to
   the verify node.
4. **D-12's hole is still open.** `reviewApply`'s allowlist is
   `Object.keys(DEFAULT_COMPANY_POLICY)` — **membership, not the class check** — so `domain`
   (`manual_protected`) would pass it. Nothing in 30-02 touches that, because 30-02 never
   calls `reviewApply`. Closing it is yours, and it belongs **inside** `reviewApply` so
   D-05/D-07's single-authority rule holds.
5. **Contacts routing:** `Build Review Decision` currently refuses `object_type: "contacts"`
   outright, and `Review Fetch By Id` / `Review Verify Fetch` / `Review Decision Update` are
   all hardcoded to the company resource. A contacts lane needs its own three nodes (the
   contact provenance blob is `lv_contact_enrichment_provenance`, a different property), and
   **each new credential-bearing node must be added to `NODE_CREDENTIAL_MAP`** — an unmapped
   one deploys unbound and 401s only at activation.
6. **Do not add an else-branch out of the write gate** (D-23). If you need the operator to
   learn that the allowlist denied the row, that is a client-side timeout/empty-body case,
   not a workflow topology change.
7. **Arming syntax, unchanged from 30-01:**
   `ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_REVIEW_WRITES,TEST_RECORD_IDS=<id>"`. The bare flag is
   refused; an empty allowlist denies everything while reporting success (asserted by case
   c2, not a bug).
8. **`scripts/verify_live_write_safety.py` still cannot read this workflow back** — it
   hardcodes `LV Enrichment (Cloud template)` and two `Decide*` node names, so it inspects
   **no node in `wf_review_decision_cloud.json`**. 30-07's armed window needs an
   all-workflow read-only scan, exactly as 23-06's runbook was forced to improvise.

## Self-Check: PASSED

- `n8n/code/reviewDecision.js` — FOUND
- `n8n/wf_review_decision_cloud.json` — FOUND
- `tests/n8n/reviewDecisionEndpoint.test.mjs` — FOUND
- `.planning/.../30-02-SUMMARY.md` — FOUND
- commits `224561e`, `9470f03`, `1089923`, `8c8a92d` — all FOUND in `git log`
- no file deletions in any of the four commits (`git diff --diff-filter=D HEAD~4 HEAD` empty)
