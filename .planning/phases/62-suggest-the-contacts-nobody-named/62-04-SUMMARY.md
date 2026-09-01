---
phase: 62-suggest-the-contacts-nobody-named
plan: 04
subsystem: enrichment
tags: [provenance, mergeContacts, n8n-code-nodes, outcome-contract, hubspot-search, dispatch]

requires:
  - phase: 62-01
    provides: "suggest_contacts.py's eligibility()/CONTACT_COUNT_PROPERTY, the D-62-16 consumer this plan's num_associated_contacts wiring feeds"
provides:
  - "mergeContacts.js: opts.sourceByField (per-field provenance override, mirrors confidenceByField)"
  - "MERGE_CONTACTS wrapper: a round-level source map read from the request envelope by node name (Set Config), never off the row"
  - "dispatch.py: keyword-only source_by_field, one extra multipart form field, no new send-shaped function"
  - "HubSpot company search (both cloud and local-live builders) requests num_associated_contacts; Adapt Company Search carries it top-level; Build Response projects it explicitly (null vs 0)"
  - "OUTCOME_CONTRACT_VERSION 1 -> 2 in both the n8n producer and the preingest.py consumer (widened, not moved)"
affects: [62-05]

actuals:
  tokens: 8100
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "request-level flag idiom (CLAUDE.md 13.0.2): source_by_field joins recompute/async_ack/scale_up as a fourth envelope-level, never-row-level opt-in"
    - "try/catch node lookup -> {} fallback (ENRICH_BUILD_RESPONSE's nodeAll idiom), reused for the new Set Config read"
    - "widen-not-move a version allowlist when the producer and consumer of a versioned contract ship in the same repo but deploy independently"

key-files:
  created:
    - tests/n8n/suggestionProvenanceFlow.test.mjs
  modified:
    - n8n/code/mergeContacts.js
    - scripts/build_cloud_workflows.py
    - operator-claude-plugin/scripts/dispatch.py
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_dispatch_multipart.py
    - operator-claude-plugin/tests/test_outcome_contract.py
    - tests/n8n/mergeContacts.test.mjs
    - tests/n8n/outcomeContractFlow.test.mjs
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json

key-decisions:
  - "sourceByField resolves into BOTH the provenance entry's source and the decisions row's source_provider (never just one), mirroring confidenceByField's existing dual-write so the two can never disagree"
  - "the round-level source map is read by node NAME ('Set Config'), never off the row -- D-16b already established that a row-seeded value does not survive Extract From File's fresh-item re-parse"
  - "num_associated_contacts is carried on the row as a TOP-LEVEL key, never nested only inside existingRecord -- this repo has a recorded suspicion that HTTP hops strip existingRecord on the companies research lane"
  - "OUTCOME_CONTRACT_VERSION's Python-side allowlist was WIDENED to {1, 2}, not moved to {2} -- the currently-deployed backend still stamps 1 until an operator deploys this regenerated (undeployed) JSON, and the client must parse correctly regardless of deploy order"

patterns-established:
  - "Pattern 1: a versioned wire contract that ships from both ends of one repo gets its consumer-side allowlist widened, never replaced, whenever the producer bumps -- deploy order between repo halves is never guaranteed"

requirements-completed: [SUGGEST-01, SUGGEST-04]

coverage:
  - id: D1
    description: "A suggested contact's lv_contact_enrichment_provenance shows claude_web for the fields web research named and the provider's own name for the fields the waterfall filled -- mixed provenance on the existing Phase 15 mechanism, no new lv_ property (D-62-17)"
    requirement: SUGGEST-01
    verification:
      - kind: unit
        ref: "tests/n8n/mergeContacts.test.mjs#mergeContacts: sourceByField overrides the flat source for named fields only, both in provenance and decisions"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#a suggested row's provenance carries claude_web for the fields research named and the waterfall's own source for email/phone, from one map present on 'Set Config'"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#the source map arrives as a JSON string on the multipart form field (dispatch.py's filename=None shape) and still parses"
        status: pass
    human_judgment: false
  - id: D2
    description: "A CSV upload's provenance is byte-identical to today's -- the csv default survives untouched for every existing caller when the source map is absent or the node it lives on does not exist"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeContacts.test.mjs#mergeContacts: omitting sourceByField entirely is byte-identical to the pre-port shape (modulo verified_at)"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#with no source map present, every field's provenance reads the flat csv source"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#with no 'Set Config' node at all (the local template's own shape) the read fails closed to {}"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py#test_dispatch_with_source_by_field_none_produces_a_byte_identical_files_dict"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py#test_exactly_one_module_defines_the_send_shaped_function"
        status: pass
    human_judgment: false
  - id: D3
    description: "A company's associated-contact count reaches the plugin from the batch it just ran, so 'zero contacts named' is answerable without a new endpoint and without a per-company associations call (D-62-16)"
    requirement: SUGGEST-04
    verification:
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#the 'HubSpot Company Search' node's body requests num_associated_contacts alongside the properties the lane already asks for"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#Adapt Company Search: a search hit reporting 0 carries the row-level num_associated_contacts as the number 0, distinguishable from null"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#Build Response stamps a real zero count as the number 0, distinguishable from null"
        status: pass
    human_judgment: false
  - id: D4
    description: "Absence of the count is stamped explicitly as null, never a missing key, so an unread count and a real zero can never look alike"
    requirement: SUGGEST-04
    verification:
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#Adapt Company Search: a lookup_failed row carries num_associated_contacts as explicit null, never a missing key"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#Adapt Company Search: a zero-hit search (no error, empty results) also stamps null"
        status: pass
      - kind: unit
        ref: "tests/n8n/suggestionProvenanceFlow.test.mjs#Build Response stamps num_associated_contacts on the response, present as explicit null when the row does not carry one"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_outcome_contract.py#test_version_2_also_parses_num_associated_contacts_read_separately_not_through_outcome"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-02
status: complete
---

# Phase 62 Plan 04: Per-field provenance and the associated-contact count Summary

**`sourceByField` mirrors `confidenceByField` on the Phase 15 provenance blob, wired through a round-level envelope flag (never a row column); `num_associated_contacts` rides HubSpot's own read-only rollup onto the enrichment response, with a client-side outcome-contract version widened to accept both the deployed and the regenerated producer.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-09-01T22:00:00Z (approx)
- **Completed:** 2026-09-01T22:59:41Z
- **Tasks:** 2
- **Files modified:** 15 (1 created, 14 modified — 6 of the 14 are regenerated `n8n/wf_*.json` build outputs)

## Accomplishments
- `mergeContacts.js` gained `opts.sourceByField`, resolved into both the provenance entry's `source` and the decisions row's `source_provider` so the recorded and chosen source can never disagree — absent opts stay byte-identical to every existing caller.
- The `MERGE_CONTACTS` n8n wrapper (shared by `build_local()`/`build_cloud()`) reads a round-level source map from the request envelope by node name (`Set Config`, the node before `Extract From File` that still spreads the webhook body), try/catch → `{}` on any failure or absent node — the exact `nodeAll`-style guard `ENRICH_BUILD_RESPONSE` already uses.
- `dispatch.py` gained a keyword-only `source_by_field` that adds ONE multipart form field (`filename=None`, so it lands on `$json.body`, not `$binary`) to the existing `files` dict — no `data=` kwarg, no second send-shaped function (the D-33 allowlist test passes unmodified).
- `num_associated_contacts` — a native, read-only HubSpot rollup — was added to BOTH property-list constants that feed the companies-branch search (`HS_CO_SEARCH_BODY_EXPR` for `build_enrichment_local_live()`, and `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`, the constant `build_enrichment_cloud()` — the actually-deployed workflow — really uses). `Adapt Company Search` carries it as a top-level, coerced-to-number row key, explicit `null` on failure or a zero-hit search. `Build Response` projects it onto every terminal.
- `OUTCOME_CONTRACT_VERSION` bumped 1 → 2 in the n8n producer (additive field only); `preingest.py`'s consumer-side allowlist was WIDENED to `{1, 2}`, not moved, because the currently-deployed backend still stamps 1 until an operator deploys this regenerated (undeployed) JSON.
- All five affected `n8n/wf_*.json` regenerated via `scripts/build_cloud_workflows.py`; none hand-edited. Nothing deployed or armed.

## Task Commits

Each task followed RED (failing test) then GREEN (implementation):

1. **Task 1: Per-field provenance — sourceByField, the sender, and the one csv hardcode** — `66173ba` (test) → `050b8a3` (feat)
2. **Task 2: num_associated_contacts on the company search and on the response** — `6d104bc` (test) → `210ec34` (feat)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `n8n/code/mergeContacts.js` — `opts.sourceByField`, resolved into both the provenance entry and the decisions row
- `scripts/build_cloud_workflows.py` — `MERGE_CONTACTS`'s envelope read, `HS_CO_SEARCH_BODY_EXPR`/`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` additions, `ENRICH_ADAPT_CO_SEARCH`'s top-level coercion, `ENRICH_BUILD_RESPONSE`'s projection + version bump
- `operator-claude-plugin/scripts/dispatch.py` — `source_by_field` keyword-only multipart part
- `operator-claude-plugin/scripts/preingest.py` — widened `_KNOWN_OUTCOME_CONTRACT_VERSIONS` to `{1, 2}` (deviation, see below)
- `operator-claude-plugin/tests/test_dispatch_multipart.py` — two new dispatch tests for the multipart contract
- `operator-claude-plugin/tests/test_outcome_contract.py` — unknown-version probe moved to `999`, version-2-parses case added (deviation)
- `tests/n8n/mergeContacts.test.mjs` — two new `sourceByField` cases
- `tests/n8n/suggestionProvenanceFlow.test.mjs` — new file, 10 cases driving the real committed jsCode in both affected workflow JSONs
- `tests/n8n/outcomeContractFlow.test.mjs` — three hardcoded `outcome_contract_version` assertions moved 1 → 2 (deviation)
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_contact_ingest_local.json`, `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_review_decision_cloud.json` — regenerated

## Decisions Made
- **`sourceByField` writes to both destinations, never just one** — the provenance entry's `source` and the decisions row's `source_provider` are resolved from the identical expression, so a future caller reading either can never see a disagreement (mirrors `confidenceByField`'s existing dual-write, which this plan's read_first named explicitly).
- **Two property-list constants needed the new property, not one** — the plan's own read_first pointed only at `HS_CO_SEARCH_BODY_EXPR`, but that constant is used exclusively by `build_enrichment_local_live()`. The workflow the acceptance criteria actually greps (`n8n/wf_enrichment_cloud.json`) is built by `build_enrichment_cloud()`, which feeds its "HubSpot Company Search" node from a genuinely separate constant, `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`. Both were updated; this mirrors the WR-01/VETO-01 precedent already documented at that constant's definition (a property missing from one of two live property lists has bitten this repo before).
- **The version bump's client-side companion fix was added despite not being in Task 2's `<files>` list** — bumping `OUTCOME_CONTRACT_VERSION` per the plan's explicit instruction would otherwise arm a parse-rejection landmine in `preingest.py`, the first-party consumer in the same repo: every enrichment response would parse as `UNPARSEABLE_OUTCOME` the moment this regenerated JSON is deployed. Widening (not moving) the allowlist to `{1, 2}` keeps both deploy orders (backend deployed first, or plugin updated first) correct.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Widened preingest.py's OUTCOME_CONTRACT_VERSION allowlist, plus its own and a sibling test file's assertions**
- **Found during:** Task 2, after bumping `scripts/build_cloud_workflows.py`'s `OUTCOME_CONTRACT_VERSION` per the plan's explicit acceptance criterion
- **Issue:** `operator-claude-plugin/scripts/preingest.py` carries its OWN, independent `OUTCOME_CONTRACT_VERSION = 1` / `_KNOWN_OUTCOME_CONTRACT_VERSIONS = frozenset({1})` — the client-side half of the SAME wire contract. Left unchanged, the plugin would treat every response from a deployed Phase-62 backend as unparseable (`UNPARSEABLE_OUTCOME`), silently breaking match-tier/confidence/hold routing for every enrichment call. This was not in Task 2's `<files>` list.
- **Fix:** Widened (not moved) `_KNOWN_OUTCOME_CONTRACT_VERSIONS` to `{1, 2}` — correct for either deploy order, since this plan does not deploy the regenerated JSON. Updated `test_outcome_contract.py` (moved its "unknown version" probe from the value `2`, which is no longer unknown, to `999`; added a case proving version 2 parses) and `tests/n8n/outcomeContractFlow.test.mjs` (its three hardcoded `outcome_contract_version` assertions, which drive the real committed jsCode and would otherwise fail against the regenerated JSON).
- **Files modified:** `operator-claude-plugin/scripts/preingest.py`, `operator-claude-plugin/tests/test_outcome_contract.py`, `tests/n8n/outcomeContractFlow.test.mjs`
- **Verification:** `.venv/bin/python -m pytest -q` (3879 passed, 154 skipped, 0 failed) and `node --test tests/n8n/*.test.mjs` (862 pass, 0 fail)
- **Committed in:** `6d104bc` (test), `210ec34` (feat)

**2. [Rule 3 - Blocking] Added num_associated_contacts to ENRICH_COMPANY_SEARCH_PROPERTIES_CSV, not only HS_CO_SEARCH_BODY_EXPR**
- **Found during:** Task 2
- **Issue:** The plan's `<action>` and read_first named only `HS_CO_SEARCH_BODY_EXPR`. Tracing the actual node registration showed `build_enrichment_cloud()` — the builder for `n8n/wf_enrichment_cloud.json`, the file the acceptance criteria greps — feeds its "HubSpot Company Search" node from `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` instead. Editing only `HS_CO_SEARCH_BODY_EXPR` would have satisfied none of Task 2's `n8n/wf_enrichment_cloud.json`-scoped acceptance criteria.
- **Fix:** Added `num_associated_contacts` to both constants.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `grep -c "num_associated_contacts" n8n/wf_enrichment_cloud.json` returns 5 (≥ 2 required)
- **Committed in:** `210ec34`

**3. [Rule 3 - Blocking] Added dispatch.py multipart-contract tests to test_dispatch_multipart.py, not listed in Task 1's `<files>`**
- **Found during:** Task 1
- **Issue:** Task 1's acceptance criteria explicitly require "a test asserts `dispatch(..., source_by_field=None)` produces a `files` dict identical to today's, and `dispatch(..., source_by_field={...})` adds exactly one extra multipart part with no `data=` kwarg" — but no test file for this was listed in Task 1's `<files>`, and the plan's `<verify>` command already names `test_dispatch_multipart.py`.
- **Fix:** Added the two tests to the existing `operator-claude-plugin/tests/test_dispatch_multipart.py`, which already houses every other `dispatch()` multipart-contract test.
- **Files modified:** `operator-claude-plugin/tests/test_dispatch_multipart.py`
- **Verification:** `.venv/bin/python -m pytest operator-claude-plugin/tests/test_retry_reuses_dispatch.py operator-claude-plugin/tests/test_dispatch_multipart.py -q` — 35 passed
- **Committed in:** `050b8a3`

---

**Total deviations:** 3 auto-fixed (all Rule 3 — blocking issues that would have left the plan's own explicit acceptance criteria unmet, or a wire contract's client half silently broken by this plan's own producer-side change).
**Impact on plan:** All three were necessary consequences of the plan's own explicit instructions (bump the version, add the property, prove the multipart contract) surfacing a wider blast radius than the plan's `<files>` lists named. No scope creep beyond what completing the stated tasks correctly required.

## Issues Encountered
None — both tasks completed on the first implementation pass; the RED phase of every task genuinely failed for the expected reason before the GREEN implementation was applied (verified via `git stash` isolating implementation changes from test-only changes, per task).

## User Setup Required
None — no external service configuration required. This plan touches only local source files, JS/Python test files, and regenerated (never deployed) workflow JSON. No HubSpot credentials, no provider credentials, no network calls.

## Next Phase Readiness
- The Phase 15 provenance mechanism now supports mixed per-field sources for a suggestion round, and the request-level `source_by_field` flag joins `recompute`/`async_ack`/`scale_up` on the same envelope idiom (CLAUDE.md §13.0.2) — ready for 62-05 to populate it from the actual stage-1/stage-2 sitting.
- `num_associated_contacts` reaches the plugin through the SAME batch response `suggest_contacts.eligibility()` (plan 62-01) already reads — no new endpoint, no new HubSpot property, no per-company associations call. 62-05 can wire the sitting's company batch straight into `eligibility()` without any further backend change.
- Nothing is deployed or armed. A future deploy of the regenerated `n8n/wf_enrichment_cloud.json`/`n8n/wf_contact_ingest_cloud.json`/etc. is a separate, explicit operator action, unchanged from this phase's stated scope.
- No blockers.

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-02*

## Self-Check: PASSED
