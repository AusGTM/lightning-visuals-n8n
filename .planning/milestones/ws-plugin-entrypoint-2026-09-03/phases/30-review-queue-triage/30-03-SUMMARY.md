---
phase: 30-review-queue-triage
plan: 03
subsystem: n8n-backend
tags: [n8n, hubspot, review-writeback, non-clobber, provenance, human-audit, contacts, write-safety]

requires:
  - phase: 30
    plan: 02
    provides: "the proven endpoint skeleton — reviewApply/mergeCompanies already inlined in Build Review Decision, both fetches already carrying the full compare-and-set baseline, and the {outcome, message, would_write, verified_properties, verified} response contract"
  - phase: 30
    plan: 01
    provides: "ALLOW_HUBSPOT_REVIEW_WRITES and the `review` branch inside _writeSafetyAllows that both write gates pass"
provides:
  - "the approve path: an approval applies the record's OWN held candidate through reviewApply's compare-and-set and stamps it as a human decision"
  - "buildHumanProvenance({existingJson, applied, reason, verifiedAt}) -> {json, entries, unreadable} — the additive provenance overlay, exported from n8n/code/reviewDecision.js"
  - "D-12 closed: manual_protected / review_required policy classes can never be written by a review decision"
  - "the contacts lane — fetch, gated PATCH, independent read-back — so a dedupe-flagged contact can be rejected from the same endpoint"
  - "the outcome vocabulary 30-06 must handle: rejected | applied | stale | no_candidate | not_flagged | refused (`unsupported` is retired)"
affects:
  - "30-04 (the queue renderer: it must show the operator that a field is protected BEFORE they approve, because the backend now silently withholds those fields and only says so in `message`)"
  - "30-06 (three new outcomes, and `would_write` on an approval is a MULTI-key patch including a JSON blob, not a single reason string)"
  - "30-07 (the armed window now has two write nodes and two lanes; a contact can only be allowlisted by TEST_RECORD_IDS)"

tech-stack:
  added: []
  patterns:
    - "a re-serialized whole-object blob is guarded by an additivity test asserting an untouched entry is deep-equal before and after — not by a spot check on the entry that changed"
    - "an absent key is asserted by key PRESENCE (`\"k\" in obj === false`), never by a string search: a grep cannot tell an absent key from one whose value is null"
    - "when a shared engine's allowlist is membership-based, the CLASS check belongs at the caller that has a reason to care — provided it reads the same policy object, not a second table"

key-files:
  created:
    - tests/n8n/reviewHumanProvenance.test.mjs
  modified:
    - n8n/code/reviewDecision.js
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - scripts/build_cloud_workflows.py
    - n8n/wf_review_decision_cloud.json
    - scripts/deploy_n8n_workflows.py
    - .planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-CONTEXT.md

key-decisions:
  - "D-12's class guard lives in reviewDecision.js, NOT inside reviewApply.js. 30-02's handoff said 'it belongs inside reviewApply'; the plan's own acceptance criterion says `git diff --stat n8n/code/reviewApply.js` must be empty (D-15). The guard wins — and the single-authority rule (D-05/D-07) is satisfied anyway, because the check reads DEFAULT_COMPANY_POLICY's own `class` values, the same object mergeCompanies gates with. There is no second policy table."
  - "A contacts approve NEVER calls reviewApply. Its allowlist is the COMPANY policy's key set, so a contact candidate would have every field dropped as un-allowlisted and would then return the clear patch anyway — de-queueing the record with nothing written, exactly the silent de-queueing REVIEW-05 forbids. Contacts approve resolves to `no_candidate` and says why."
  - "The contacts lane needed THREE credential-bearing nodes, not the two the plan named: a lane without its own read-back reports `verified_properties: null` on a write that actually landed, which D-19 requires the client to call a failure."
  - "The provenance blob is written UNTRUNCATED, unlike the enrichment producer's `.slice(0, 60000)`. A JSON blob cut mid-token is unparseable, so truncating would destroy the audit history on the next approval; an over-long blob is rejected loudly by HubSpot instead."
  - "One shared `Review Extract Record` and one shared `Build Review Decision` serve both object types, rather than the per-lane extract node the plan described. The extract body is resource-independent and this workflow already converges two branches on `Build Review Response`."

metrics:
  duration: ~70 min
  completed: 2026-07-31
status: complete
---

# Phase 30 Plan 03: Approve Path, Human Provenance, Contacts Lane Summary

An approval now applies the record's own held candidate through the existing, tested
non-clobber engine, cannot touch a `manual_protected` field however the candidate was
forged, and leaves a `source: "human"` entry per applied field in the provenance blob
without erasing a single entry belonging to any other field. Contacts can be worked from
the same endpoint. The 15-minute backstop is byte-for-byte untouched.

## What was built

**Task 1 — the approve branch + the human stamp** (`e976ed8` RED, `4550112` GREEN)

`buildReviewDecision({objectType, decision, reason, reviewedBy, row, nowIso})`. Outcomes:

| outcome | when | properties |
|---|---|---|
| `applied` | approve, clean compare-and-set | canonical (class-filtered) + reviewApply's clear patch + the merged provenance blob + reviewed-by |
| `stale` | approve, reviewApply reports drift | `{}` — record stays queued, message names the drifted field(s) |
| `no_candidate` | approve with no / empty / unreadable candidate, or any contact | `{}` |
| `not_flagged` | the row is not in the queue | `{}` |
| `rejected` | reject on a flagged row | exactly `{lv_enrichment_review_reason}` (unchanged from 30-02) |
| `refused` | unknown decision word, missing record, non-string reason | `{}` |

`unsupported` is **retired** — nothing returns it any more. 30-06 must branch on the six
above.

`reviewApply(held, row)` is **imported and called**; there is no second compare-and-set.
A test asserts the module both imports it and contains no staleness comparison of its own,
so a future "just inline the check" edit fails rather than quietly forking the authority.

**The class guard (D-12, T-30-11).** `reviewApply`'s allowlist is
`Object.keys(DEFAULT_COMPANY_POLICY)` — *membership*, so `domain` (class
`manual_protected`) and `annualrevenue` (`review_required`) pass it. The approve branch
drops any field whose class is in `PROTECTED_CLASSES` before building the patch, reading
`DEFAULT_COMPANY_POLICY` itself. Legitimate fields in the same forged candidate still
apply, and the withheld names go into the operator's `message`.

One conservative consequence, stated rather than fixed: the staleness check inside
`reviewApply` still covers the protected fields too, so a drifted `domain` makes the whole
decision stale even though `domain` would have been withheld anyway. Fails closed; left
alone because changing it means editing `reviewApply`.

**`buildHumanProvenance()`**, exported. Parses `lv_enrichment_provenance`, overlays one
entry per applied field, re-serializes with `mergeCompanies.stableStringify` so byte-parity
with `src/merge_policy.py::serialize_provenance` and every other writer of that property
holds. The entry:

```
{ source: "human", confidence: 100, verified_at: <decision time>,
  validation_status: "human_approved", value: <applied value>,
  reason: <operator text>, superseded_source: <what the machine had said, or ""> }
```

`human` / `human_approved` are the registered `config/source_registry.yaml` vocabulary
(trust_rank 100). `reason` and `superseded_source` are the two additive flat keys. There
is **no `verified_by_model`** — the deployed blob has never had one, and the test asserts
its absence by key presence on the built entry, not by grep. An unreadable existing blob
degrades to empty and **says so in the message** rather than throwing or pretending the
history was empty.

`lv_enrichment_reviewed_by` is written only when a non-empty label is supplied — writing
`""` would erase a reviewer HubSpot already holds. `lv_enrichment_reviewed_at` is left to
`reviewApply`'s own clear patch; stamping it twice is how two timestamps start disagreeing.

**Task 2 — the contacts lane** (`5583994`)

```
Parse Review Decision -> Review IF Contacts
  true  -> Review Contact Fetch By Id  ┐
  false -> Review Fetch By Id          ┴-> Review Extract Record
  -> Build Review Decision -> Review IF Dry Run
      true  -> Build Review Response
      false -> Review IF Contact Write
          true  -> Review Contact Decision Update Write Gate -> Review Contact Decision
                   Update -> Review Contact Verify Fetch
          false -> Review Decision Update Write Gate -> Review Decision Update
                   -> Review Verify Fetch
  -> Build Review Response -> Respond Review Decision
```

18 nodes, `"active": false`. Both PATCHes are spliced behind their **own** `review`-action
gate; there is no shared gate, and **no else-branch out of either** (D-23 honoured). Three
new `NODE_CREDENTIAL_MAP` entries. The review-property family is now a single
`_REVIEW_FAMILY` tuple shared by both lanes' property sets, so a decision cannot become
possible on one object type and not the other by drift.

## Deviations from Plan

**1. [plan vs. upstream handoff — the plan wins] the `manual_protected` guard is in `reviewDecision.js`, not inside `reviewApply.js`**

30-02's handoff said the fix "belongs **inside** `reviewApply` so D-05/D-07's
single-authority rule holds". The plan's own acceptance criterion says
`git diff --stat n8n/code/reviewApply.js` is empty (D-15), and the dispatch reinforced it.
These cannot both be satisfied. Resolved in favour of the guard: `reviewApply` is also the
15-minute backstop's engine, and widening it would change that loop's behaviour under a
`git diff` guard that exists precisely to stop that. Single authority is preserved by
construction — the class check reads `DEFAULT_COMPANY_POLICY`'s own `class` values, so
there is still exactly one policy table. **Folded into 30-CONTEXT as D-26.**

**2. [Rule 2 — missing critical functionality] the contacts lane needed a THIRD credential-bearing node**

The plan said "register the two new nodes in `NODE_CREDENTIAL_MAP`" (fetch + PATCH).
Tracing a contacts *rejection* — which does write — showed the companies
`Review Verify Fetch` cannot serve it: it POSTs to the companies search URL, so it would
read a company with that id, or nothing. Without a contacts read-back, a landed contacts
write reaches the responder with `verified_properties: null`, which D-19 requires the
client to report as a **failure**. Added `Review Contact Verify Fetch` and registered all
three. **Folded in as D-28.**

**3. [Rule 1-adjacent — a de-queueing hazard] a contacts approve must not reach `reviewApply` at all**

The plan says a contacts approve "resolves to the `no_candidate` outcome from Task 1 and
writes nothing", and asks that `buildReviewDecision` be taught to consult
`DEFAULT_CONTACT_POLICY`. Tracing what would happen if a contact *did* hold a candidate
JSON: `reviewApply`'s allowlist is the company policy's key set, so every contact field
(`jobtitle`, `phone`, …) is dropped as un-allowlisted, no field is stale, and it returns
its **clear patch** — which would blank the review flags and the candidate while writing
no value. That is the silent de-queueing REVIEW-05 forbids. The contacts branch therefore
returns `no_candidate` before any engine call, and `DEFAULT_CONTACT_POLICY` /
`lv_contact_enrichment_provenance` are **named in the header as what a future contacts
apply engine must use**, rather than imported as unreachable dead code. **Folded in as
D-27.**

**4. [simplification] one shared extract node and one shared decision node, not one per lane**

The plan describes each fetch "feeding its own extract node into a shared decision node".
The extract body is resource-independent (it unwraps a HubSpot search envelope), and this
workflow already converges two branches on `Build Review Response`, so a second copy would
be two copies of one rule. One `Review Extract Record` serves both.

**5. [not a deviation, recorded] the provenance blob is written untruncated**

`ENRICH_DECIDE_CO_CLOUD` writes `stableStringify(provenance).slice(0, 60000)`. This path
deliberately does not: a blob cut mid-token is unparseable, so the next approval would read
it as unreadable and replace the whole history. Over-length is left to fail loudly at
HubSpot instead.

## Contacts: what an operator can and cannot do

- **Reject** — works identically to a company. One property, record stays queued.
- **Approve** — returns `no_candidate` and writes nothing. Correct, not a stub:
  `lv_enrichment_review_candidate_json` has exactly one producer in this repo, the
  **companies** enrichment lane's `Decide Company Action` (verified —
  `scripts/build_cloud_workflows.py:2518` is the only write site).
- **Allowlisting** — a contact carries no `domain`, so `TEST_RECORD_DOMAINS` cannot reach
  one. `TEST_RECORD_IDS` is the only way, and arming with domains alone produces D-23's
  silent no-response. Asserted in both directions and written into the sticky note.
  **30-07's runbook must say this.**

## Verification

**No network call of any kind. Nothing armed, deployed, or activated.**

Disarmed grep, run before staging and again after the final code commit — 0 across all 8:

```
n8n/wf_backend_status_cloud.json:0        n8n/wf_enrichment_local.json:0
n8n/wf_contact_ingest_cloud.json:0        n8n/wf_review_decision_cloud.json:0
n8n/wf_contact_ingest_local.json:0        n8n/wf_scheduled_maintenance_cloud.json:0
n8n/wf_enrichment_cloud.json:0            n8n/wf_enrichment_local_live.json:0
```

Both empty-diff guards, measured across all three commits
(`git diff --stat HEAD~3 HEAD -- <path>`):

| guard | result |
|---|---|
| `n8n/code/reviewApply.js` | **empty** — imported, never forked (D-15) |
| `n8n/wf_scheduled_maintenance_cloud.json` | **empty** — the 15-minute backstop is intact (D-08e) |

`tests/n8n/reviewLoop.test.mjs` passes unedited (7/7), and a new case (h) asserts the
backstop's four nodes are still wired `Review Trigger (15 min)` → `Review Search
(approved=true)` → `Review Extract Rows` → `Apply Review`.

| Suite | Before | After | Attribution |
|---|---|---|---|
| `node --test tests/n8n/*.test.mjs` (file form) | 433 / 0 fail | **458 / 0 fail** | +25, **all mine**: 11 new in `reviewHumanProvenance.test.mjs`, +14 in `reviewDecisionEndpoint.test.mjs` (25 → 39) |
| `.venv/bin/python -m pytest -q` | 1214 passed, 1 skipped | **1214 passed, 1 skipped** | **unchanged, and correctly so** — the review workflow already entered every `wf_*_cloud.json` glob in 30-02, so widening it adds assertions inside existing tests rather than new ones |
| plugin (`python3 -m pytest` in `operator-claude-plugin/`) | 414 | **414** | untouched by this plan |

Baselines matched the dispatch exactly on the first measurement (1214/1, 433, 414); no
sibling executor moved them during this run. **The `407/1` node flake 30-01 logged did not
recur** in any of the ~9 node runs during this plan.

Non-vacuity spot checks rather than trusting the suites:

- both PATCH nodes are fed **only** by their own `Write Gate`, and both gates call
  `_writeSafetyAllows('review', ...)` (asserted directly against the committed JSON);
- the contacts gate denies with `TEST_RECORD_DOMAINS` armed and passes with
  `TEST_RECORD_IDS`, and denies with both dispatch constants armed (D-02, reverse
  direction);
- `(g5)` drives an **approve** through the committed node's own jsCode, not just the
  module, and asserts `domain` is absent from `would_write` there.

**Rebuild is idempotent:** re-running `scripts/build_cloud_workflows.py` left the seven
other workflow JSONs byte-identical; only `wf_review_decision_cloud.json` changed.

## Known Stubs

- **A contacts approve writes nothing** (`no_candidate`). Declared in the plan, and the
  reason is structural rather than unfinished work — see deviation 3. Resolving it means
  building a contacts apply engine (a `reviewApplyContacts` over `DEFAULT_CONTACT_POLICY`
  writing `lv_contact_enrichment_provenance`) **and** a contacts review-candidate producer,
  neither of which exists in this repo. Not scheduled in Phase 30.
- **The contacts fetch does not carry a compare-and-set baseline** (`config/field_policy.yaml`'s
  `contacts` keys), because nothing reads one. A future contacts apply engine must widen
  `REVIEW_CONTACT_PROPERTIES_CSV` in the same derived-from-YAML form the company set uses,
  or every such decision silently reads as stale. Stated at the constant.

## What 30-04 needs to know

1. **Show `manual_protected` / `review_required` BEFORE the operator decides** (D-06). The
   backend now withholds those fields silently apart from a clause in `message`; an
   operator who approves a candidate containing `domain` gets `outcome: applied` and no
   `domain` write. The queue renderer is where that becomes visible in advance.
2. **`would_write` on an approval is a multi-key patch**, one of whose values is a JSON
   blob (`lv_enrichment_provenance`) that can be kilobytes. The exact-write display (D-01)
   should not dump it raw.
3. **Six outcomes, not four** — `applied`, `stale`, `no_candidate` are new and `unsupported`
   is gone. `stale` and `no_candidate` are the two the operator will actually meet.
4. **Contacts render from a different property set** (`REVIEW_CONTACT_PROPERTIES_CSV`):
   identity is `email`/`firstname`/`lastname`/`jobtitle`, and the provenance blob is
   `lv_contact_enrichment_provenance`. There is no `domain` and no candidate JSON.
5. **`scripts/verify_live_write_safety.py` still cannot read this workflow back** —
   unchanged from 30-02's item 8, and there are now *two* write nodes it does not see.

## Self-Check: PASSED

- `n8n/code/reviewDecision.js` — FOUND
- `tests/n8n/reviewHumanProvenance.test.mjs` — FOUND
- `n8n/wf_review_decision_cloud.json` — FOUND (18 nodes, `active: false`)
- `.planning/.../30-03-SUMMARY.md` — FOUND
- commits `e976ed8`, `4550112`, `5583994` — all FOUND in `git log`
- no file deletions in any of the three commits (`git diff --diff-filter=D HEAD~3 HEAD` empty)
