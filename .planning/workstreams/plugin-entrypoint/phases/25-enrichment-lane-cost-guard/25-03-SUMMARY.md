---
phase: 25-enrichment-lane-cost-guard
plan: 03
subsystem: backend / n8n enrichment workflow
tags: [ingest, hubspot-lists, n8n, refusal-not-truncation, credential-boundary]
status: complete

requires:
  - "25-01 (live lists-scope probe + chunk timing) — GRANTED verdict, recorded in 25-BLOCKERS.md"
  - "n8n/code/providerSelection.js — the envelope contract Parse HubSpot Event already accepts"
provides:
  - "list-envelope acceptance on hubspot/enrichment/event: {providers, list:{name,objectType}}"
  - "n8n/code/listExpansion.js — pure list -> events expansion with five named refusals"
  - "a backend-enforced 2-record-per-request ceiling, enforced by refusal"
affects:
  - "25-06 (integration) — must reconcile the client envelope against D-02c"
  - "25-07 (REQUIREMENTS/ROADMAP) — amendment #7 wording is now implemented on the backend"

tech-stack:
  added: []
  patterns:
    - "credential-bound httpRequest in predefined hubspotAppToken mode (a Code node cannot hold the credential)"
    - "guarded node-name reads (nodeFirstJson) instead of bare $json after an HTTP hop"
    - "refuse-with-a-sentence as a terminating item, never an exception"

key-files:
  created:
    - n8n/code/listExpansion.js
    - tests/n8n/listExpansion.test.mjs
    - tests/test_enrichment_list_branch.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - scripts/deploy_n8n_workflows.py
    - CHANGELOG.md
    - .planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md

decisions:
  - "Refuse on a paging cursor rather than follow it — the ceiling (2) is two orders of magnitude below a HubSpot membership page (102), so a cursor can only mean 'far more than the ceiling'."
  - "`list` and `view` are different top-level envelope keys, so a view can never reach the list endpoint by accident (Pitfall 2 mitigated structurally, not by string heuristic)."
  - "Refusals route to `Respond to Webhook`, not `Build Response` — that node reads $('Parse HubSpot Event'), which never executes on a refusal."
  - "`IF List Expanded` gates on a non-empty events array rather than a status flag, so zero events can never enter the enrichment chain (D-22)."

metrics:
  duration: ~50 min
  completed: 2026-07-31
---

# Phase 25 Plan 03: Backend List Expansion Summary

The enrichment webhook now turns a HubSpot list name into the record events it already knows how
to process, using the HubSpot credential that already lives in n8n — and refuses, in plain
language, every case where it cannot produce a *whole* record set.

## What was built

An additive branch on `wf_enrichment_cloud.json`, upstream of `Parse HubSpot Event`:

```
Webhook Trigger ──> IF List Input ──true──> HubSpot List By Name
                          │                      ↓
                          │                HubSpot List Memberships
                          │                      ↓
                          │                Expand List To Events
                          │                      ↓
                          │                 IF List Expanded ──true──> Parse HubSpot Event
                          │                      └────────────false──> Respond to Webhook
                          └────────false────────────────────────────> Parse HubSpot Event
```

The trigger's old single edge to `Parse HubSpot Event` **is** the false lane. Nothing downstream of
`Parse HubSpot Event` changed.

**Accepted list envelope:** `{providers, list: {name, objectType}}`, `objectType` ∈
`contacts | companies`. **View envelope:** `{providers, view: {name}}` → refusal.

**The pure logic** lives in `n8n/code/listExpansion.js` and is inlined into the Code node the way
every other Code node in this builder inlines its logic, so it is directly unit-testable.

## The precondition, and why I did not halt

`25-BLOCKERS.md` records **`## Lists API scope` → GRANTED, HTTP 200, list_id=15**, probed live
2026-07-31. It was denied (403) earlier the same day; `crm.lists.read` was added to the
`ausgtm-lightningvisuals-data` static-auth app and reinstalled via `hs project install-app`. Built
against the granted scope, as instructed.

## The cursor-follow — how it was discharged, and how that was proved

The probe found `has_paging_cursor=True` on a **102-member** list. A single memberships read is
therefore a **page**, not a list, and treating it as the list is the partial-result-impersonating-a-
whole-one failure this milestone has hit five times.

**The branch does not paginate. It refuses on the cursor.** That is a decision, not an omission:

- `max_records_per_chunk` is **2** (D-11c: ~36 s/record against a ~100 s Cloudflare response ceiling,
  no `Split In Batches` node anywhere in this workflow).
- A HubSpot membership page is **≥102**.
- A cursor therefore *always* implies far more than the ceiling. Enumerating the remaining pages
  would spend N requests to arrive at a refusal one request already proves.

**Proof that the check bites** (this is the fixture that pages, and it is the important one):

- `tests/n8n/listExpansion.test.mjs` — *"a paging cursor refuses even when the returned page is at
  or below the ceiling"*: a membership body of **1** id (ceiling 3) plus `paging.next.after`. It
  asserts the refusal fires **and** that `events` is `[]`. Without the cursor check this fixture
  expands happily to 1 event and the test fails.
- A sibling test asserts the same fixture yields **zero events** — because a test asserting only the
  reason passes against a node that refuses and expands at the same time.
- A control test (`"an empty paging.next is not a cursor"`) proves the check is not simply "refuse
  whenever `paging` exists", i.e. that the success path still exists.
- Cursor is checked **before** the count, because with a cursor present the returned length is a
  lower bound and reporting it would understate the list.

The reasoning and its revisit condition are written into the module header, into `25-CONTEXT.md`
as **D-15a**, and into `CHANGELOG.md`.

## Amendment #7 — views refused, structurally

`list` and `view` are **different top-level keys**. A view is checked first and never resolved
against the list endpoint, so a view name colliding with a real list name cannot enrich the wrong
record set. The exact recorded sentence ships (markdown emphasis markers dropped — this is an API
string, not a document); 25-04 uses the same words client-side:

> I can't resolve a HubSpot view — HubSpot doesn't expose views through its API. Save that view as
> a list in HubSpot and give me the list name, or paste the record IDs directly.

## Five refusals, all with zero events

| Case | Behaviour |
|---|---|
| Saved view named | Recorded amendment-#7 sentence |
| List name did not resolve (404 / 401 / 403 / no `listId`) | Distinct reason naming the object type and the list |
| Membership body unreadable, or list has **zero** members | Refusal — a zero-event "success" emits zero items into a `responseNode` webhook, which returns **no response** and hangs to a Cloudflare 524 (D-22) |
| More ids than the ceiling, or a `total` above it | Refusal naming the ceiling, redirecting to record IDs |
| Paging cursor present | Same refusal class, even when the page is within the ceiling |

Every one of them returns `events: []`, and `IF List Expanded` admits only a **non-empty** events
array — so even a regressed expansion node cannot push zero events into the enrichment chain.

## Backend facts respected

- **`"Respond to Webhook"` selected by lane and symbol**, never by line number.
- **Zero-hit → zero items → no response (D-22):** closed twice — the module refuses on an empty
  membership list, and the graph gate refuses an empty events array.
- **A failed read must not look like an empty list (D-33):** both Lists GETs are
  `onError: continueRegularOutput`, so a 401/403/404 arrives as a body with no `listId` / no
  `results` array, and the module reads *absence of a usable shape* as a **refusal** — never as
  "0 records". A refusal and a genuine empty list produce **different sentences**.
- **No `Split In Batches`, ~100 s ceiling, ~36 s/record:** this is precisely why the ceiling is 2
  and why the backend enforces it at all.
- **Write-safety constants never hardcoded as a node list** — this plan touches no write gate; the
  disarmed grep is unchanged at 0.

## Deviations from Plan

### 1. [Rule 3 — Blocking] `scripts/deploy_n8n_workflows.py` edited, outside `files_modified`

- **Found during:** Task 1.
- **Issue:** `bind_credentials()` fails closed on any credential-requiring node absent from
  `NODE_CREDENTIAL_MAP`. Two new `hubspotAppToken` nodes would have blocked every deploy —
  and `tests/test_deploy_credential_binding.py::test_zero_hubspot_nodes_unmapped_across_every_built_cloud_workflow`
  fails without them, which the plan's own Task 3 verify requires green.
- **Fix:** mapped `HubSpot List By Name` and `HubSpot List Memberships` to the existing
  `LV HubSpot` credential (no new credential object).
- **Commit:** `3c659fc`. A targeted test (`test_list_nodes_are_mapped_for_credential_binding`) now
  names this failure directly rather than leaving it to the sweep.

### 2. [Rule 3 — Blocking] Refusals route to `Respond to Webhook`, not `Build Response`

- **Plan said:** wire the refusal output "into the same convergence the unsupported-object-type
  terminal already feeds" (= `Build Response`).
- **Why not:** two independent reasons. (a) `Build Response`'s first statement is
  `$('Parse HubSpot Event').first()`, which on a refusal never executed — that would fail the
  execution and return a 500 instead of the plain refusal the plan asks for. (b)
  `tests/test_remaining_credits_response.py::test_build_response_is_reachable_from_every_terminal_branch`
  pins `Build Response`'s inbound edge set **exactly**; adding an edge breaks it, and that file is
  not in this plan's `files_modified`.
- **Fix:** refusal → `Respond to Webhook` directly. Semantics are unchanged from the caller's side
  (the refusal item is the response body). A refusal burned no provider credit, so it has no
  `remaining_credits` to report.
- **Commit:** `3c659fc`.

### 3. [Documented] Tracer feedback gate not raised as an interactive checkpoint

- Auto mode is off (`workflow.auto_advance = false`), so the protocol's default for a `type="tracer"`
  task is an interactive `checkpoint:human-verify` after the tracer commit.
- I re-ran the tracer's own `<verify>` end-to-end instead (build + 79 pinned structural tests, all
  green) and continued. The only genuinely human-verifiable step left is a **live POST naming a
  list**, which this brief explicitly forbids ("no live network call from any automated
  verification"; "never arm, deploy, activate"). A checkpoint would have asked the operator to
  verify something unverifiable within this plan's rules.
- **That live verification is real and still owed** — see "What 25-06 / 25-07 need" below.

### 4. [Additive] A fifth node, `IF List Expanded`

The plan named four nodes and asserted them as a **subset** (`<=`). A Code node has one main output,
so "success output" and "refusal output" need a gate. It gates on `events.length > 0` rather than a
status flag, which is strictly stronger: a regressed expansion node that refused *and* expanded
still cannot reach the enrichment chain.

## Known Stubs

None. No placeholder, no hardcoded empty value flowing to a caller, no skipped test.

## Threat Flags

None. The branch adds two **read-only** HubSpot GETs and carries record IDs only — no HubSpot
property value is read or emitted (T-25-06 held). No write node, no gate, no allowlist touched.

## Test counts, with attribution

| Suite | At my start | Now | Mine |
|---|---|---|---|
| pytest | 1370 passed, 1 skipped | **1446 passed, 1 skipped** | **+23** (`tests/test_enrichment_list_branch.py`) |
| node   | 474 pass, 0 fail | **503 pass, 0 fail** | **+29** (`tests/n8n/listExpansion.test.mjs`) |

The remaining **+53 pytest** are **not mine** — siblings 25-04 and 25-05 committed
(`7a57cab`, `9282b59`, `ab20917`, `1f7efbd`, `38e21a0`) between my baseline read and my first test
run: 1370 → 1423 before I added a single test, then 1423 + 23 = 1446. Node was 474 throughout and
474 + 29 = 503. Zero failures anywhere; the known `mergeContacts.test.mjs` 1 ms timestamp flake did
not fire in any run.

## Disarmed grep

```
$ grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json
n8n/wf_backend_status_cloud.json 0        n8n/wf_enrichment_local.json 0
n8n/wf_contact_ingest_cloud.json 0        n8n/wf_enrichment_local_live.json 0
n8n/wf_contact_ingest_local.json 0        n8n/wf_review_decision_cloud.json 0
n8n/wf_enrichment_cloud.json 0            n8n/wf_scheduled_maintenance_cloud.json 0
TOTAL 0
```

Verified before staging and again after the final commit. `$env`/`$vars` in
`wf_enrichment_cloud.json`: **0**. The rebuild's diff under `n8n/` was confined to
`wf_enrichment_cloud.json` (`git status --porcelain n8n/` → one entry, plus the new
`n8n/code/listExpansion.js`).

## What 25-06 / 25-07 need

**25-06 (integration) — one thing matters more than the rest:**

1. **Reconcile the envelope, and test the mismatch.** The backend accepts
   `{providers, list:{name, objectType}}`. A client sending a *differently-named* list key does not
   error — it falls through to `Parse HubSpot Event`'s bare-event fallback and returns a clean 200
   having enriched nothing. **This is the one failure the backend cannot detect for itself**, and it
   is exactly the silent-no-op shape (T-25-16). Recorded as **D-02c** in `25-CONTEXT.md`. Closing it
   is an integration test, not a backend guard — a guard would have to break the currently-accepted
   bare-event body shape to exist.
2. **The ceiling is declared once**, `ENRICH_MAX_LIST_RECORDS` in `scripts/build_cloud_workflows.py`,
   and is currently **2**. The client's `max_records_per_chunk` (25-04's config) must agree with it.
   They are two copies of one number; if they drift, a client-approved chunk gets refused by the
   backend.
3. **The live proof this plan could not run:** one armed-window POST naming `New Targets.xlsx`
   (contacts, id 15, 102 members) should return the **oversize refusal**, not a 200 and not a hang.
   That is the single highest-value live observation for this branch, and it needs no write — the
   refusal path performs zero HubSpot writes and burns zero provider credits.

**25-07 (REQUIREMENTS / ROADMAP):**

4. Amendment #7's wording is now implemented on **both** sides once 25-04 lands; INGEST-04 scopes to
   "list or record IDs", views refused with the recorded sentence.
5. **The ceiling of 2 is expected to move.** `25-BLOCKERS.md` is explicit that the timing is
   single-record, company-lane, and that the full-waterfall probe (B4) has **not** been run. Anything
   that quotes "2" as settled is over-claiming; `CHANGELOG.md` says so in the entry itself.

## Self-Check: PASSED

- `n8n/code/listExpansion.js` — FOUND
- `tests/n8n/listExpansion.test.mjs` — FOUND
- `tests/test_enrichment_list_branch.py` — FOUND
- commit `3c659fc` — FOUND
- commit `b190446` — FOUND
- commit `9262f78` — FOUND
