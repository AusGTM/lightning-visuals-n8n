---
phase: 73-ga-fix-list-from-stress-attempt-2
plan: 03
subsystem: n8n-companies-branch-identity-and-refusal
tags: [n8n, hubspot, company-search, domain-variants, freemail, review-outcome]

requires:
  - phase: 73-ga-fix-list-from-stress-attempt-2
    provides: "73-01/73-02's frozen-runData discipline and TDD gate conventions (unrelated code paths, same phase)"
provides:
  - "domain_variants: the companies branch matches domain with operator IN over [bare, www.bare] in one search, on all three domain-search sites (cloud, local-live, ingest) — the three live F-B7 duplicates (Racing Victoria, Wyong, Canberra RC) can no longer recur"
  - "the .invalid sentinel (folded F-B4): a no-domain row's search values array is never empty, so a name-only row gets a clean zero-hit 200 instead of a 400 mislabelled as lookup_failed"
  - "honest name-only outcomes (D-73-22): a name-only row whose exact-name search misses or hits more than once becomes review, never create or skip, with a reason naming the outcome, the missing domain, and the remedy"
  - "two-hit domain preference (D-73-20): an IN search returning both stored forms of one company resolves to the bare-domain hit (results[0] otherwise), with both ids named in the row's reason"
  - "freemail refusal in both engines (D-73-08/D-73-09): the backend refuses a create whose domain is a member of the authoritative FREEMAIL_DOMAINS set (extracted verbatim from n8n/code/companyLink.js at build time), and the plugin's domain confirm/decline lane refuses the same set before any send"
affects: [enrichment-companies-branch, contact-ingest-company-link, enrich-records-companies-preview]

actuals:
  tokens: 10959
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "extract_js_const(module, name): regex-extracts ONE top-level `const NAME = ...;` statement verbatim from a Wave-A JS module, for splicing a single shared constant into a Code node that has no business inlining that module's other, unrelated exports — the alternative to inline()'ing a whole module just to reach one constant"
    - "A sibling row field (domain_variants), never inside identity_keys — mirrors the linkedin_url_variants precedent so neither addition can perturb a test pinning identity_keys' own exact shape"
    - "A freemail/profile-page predicate is computed BEFORE a create-seed block runs, never after — a refused create must never seed the very value (or its provenance) it is about to be refused for"

key-files:
  created:
    - tests/n8n/companyDomainVariants.test.mjs
    - tests/n8n/companyNameOnlyOutcome.test.mjs
    - tests/n8n/companyFreemailRefusal.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - operator-claude-plugin/scripts/company_domain.py
    - operator-claude-plugin/tests/test_company_extraction.py
    - tests/test_bug10_company_search_transport.py
    - tests/test_cloud_write_path.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_contact_ingest_cloud.json

key-decisions:
  - "domain_variants lives in ENRICH_BUILD_CO_IDENTITY as a sibling row field (identical placement discipline to linkedin_url_variants), computed from the already-cleaned domain: [bare, 'www.'+bare], or exactly the RFC 2606 '.invalid' sentinel when there is none — never []."
  - "The D-73-22 review conversion and the D-73-20 domain-match note both live in 'Company Gate' (ENRICH_CO_GATE), beside the sibling lookup_failed/recompute overrides, rather than in 'Decide Company Action' — 'Decide Company Action' already forwards row.gate.reason unchanged (Phase 70 Plan 03 D-70-07), so both reasons reach Build Response through the one existing path with no second wiring."
  - "Override ordering inside Company Gate is lookup_failed -> recompute remap -> name-only (gated on action still being 'create') — a genuine transport error and a recompute_refused verdict are both left untouched rather than being reclassified into a name-only review."
  - "The backend freemail refusal is computed BEFORE the pre-existing create-seed block in 'Decide Company Action', not after — the original placement point (beside 'let action = row.action;') seeded the freemail domain into properties.domain unconditionally before the refusal could suppress it, caught by the test 'no seeded domain on a refused create' before this reorder."
  - "A new extract_js_const() build helper regex-extracts ONLY the FREEMAIL_DOMAINS statement from n8n/code/companyLink.js, never inline()'s that whole module into 'Decide Company Action' — its other exports (cleanCompanyDomain/companyDomainForRow/emailDomain) are ingest-lane-specific and would be dead weight plus a needless second collision surface."
  - "The plugin fix lands in company_domain.py's _validate_decision (factored into a shared _guard_domain helper), not enrichment.py's build_envelope companies branch — SESSION-2026-09-15.md's domain table ('row 34 researched', 'row 35 declined', 'row 36 gmail passed through') confirms the live F-B3 row travelled the confirm/decline lane company_domain.py owns, not the bare extraction.py CSV path. The bare extraction.py -> build_envelope path therefore stays client-side unrefused for a freemail domain (backend-covered only) — the threat register already classes the plugin refusal as advisory, so this is one sentence here, not a new todo."
  - "wf_enrichment_local_live.json legitimately produced no diff for Task 3: its own companies decide node (ENRICH_DECIDE_CO_LOCAL) is a dry-run echo with no write or refuse logic at all and never references FREEMAIL_DOMAINS — the plan's files_modified list named it defensively, not as a guaranteed diff."

requirements-completed: [F-B7, F-B4, F-B3]

coverage:
  - id: D1
    description: "One IN search over a never-empty [bare, www.bare] domain variant pair, on all three domain-search sites (cloud companies branch, local-live sibling, ingest company-link search)"
    requirement: F-B7
    verification:
      - kind: unit
        ref: "tests/n8n/companyDomainVariants.test.mjs (8 tests: variant pair, www-stripped, sentinel, live www.-stored resolution, IN-not-EQ filter shape, no-empty-values)"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/companyDomainVariants.test.mjs tests/n8n/companyAssociationFlow.test.mjs tests/n8n/companyNameFallbackFlow.test.mjs tests/n8n/ingestCarryMerge.test.mjs -> 23 passed / 0 failed"
        status: pass
    human_judgment: false
  - id: D2
    description: "A no-domain row never sends an empty filter value and never reads as a failed lookup (folded F-B4)"
    requirement: F-B4
    verification:
      - kind: unit
        ref: "tests/n8n/companyDomainVariants.test.mjs::a no-domain row's clean zero-hit search is never mislabelled a failed lookup (F-B4)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every name-only failure shape (zero-hit, many-hit) is review with a reason naming the outcome, the missing domain, and the remedy; the one-hit and transport-failure shapes are unaffected"
    requirement: F-B4
    verification:
      - kind: unit
        ref: "tests/n8n/companyNameOnlyOutcome.test.mjs (6 tests covering all four shapes plus the domain-present precedent)"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/companyNameOnlyOutcome.test.mjs tests/n8n/companyNameFallbackFlow.test.mjs tests/n8n/enrichmentMixedBatch.test.mjs -> 18 passed / 0 failed"
        status: pass
    human_judgment: false
  - id: D4
    description: "A two-hit domain IN search resolves to one record (preferring the bare form) and never routes to review, with both ids named in the reason"
    requirement: F-B7
    verification:
      - kind: unit
        ref: "tests/n8n/companyNameOnlyOutcome.test.mjs::a two-hit domain IN search resolves to one record, preferring the bare-domain hit, naming both ids -- never a review"
        status: pass
    human_judgment: false
  - id: D5
    description: "Freemail is refused in both engines (backend Decide Company Action; plugin company_domain.py's confirm/decline lane), from the one authoritative FREEMAIL_DOMAINS set"
    requirement: F-B3
    verification:
      - kind: unit
        ref: "tests/n8n/companyFreemailRefusal.test.mjs (5 tests, iterating the real FREEMAIL_DOMAINS set) + node --test tests/n8n/companyFreemailRefusal.test.mjs tests/n8n/companyLink.test.mjs -> 16 passed / 0 failed"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py (4 new tests) + .venv/bin/python -m pytest -k 'freemail or domain' operator-claude-plugin/tests/test_company_extraction.py -> 4 passed / 0 failed"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-15
status: complete
---

# Phase 73 Plan 03: Companies branch identity match, name-only outcomes, and freemail refusal Summary

**The companies branch now matches a domain in both its portal storage forms (bare and www.-prefixed) in one IN search, never sends HubSpot an empty filter value, converts an unresolved name-only row into an explicit review with a next-step reason instead of a silent create or a mislabelled skip, and refuses a freemail domain as a company identity in both the backend decision node and the plugin's confirm/decline preview.**

## Performance
- **Duration:** ~55 min
- **Started:** 2026-09-15 (first commit `a4d24833`)
- **Completed:** 2026-09-15 (last commit `4f699d03`)
- **Tasks:** 3/3
- **Files modified:** 11 (3 new test files, 5 modified code/test files, 3 regenerated workflow JSONs)

## Accomplishments
- **Task 1 (F-B7 + folded F-B4 sentinel):** `ENRICH_BUILD_CO_IDENTITY` computes `domain_variants` (`[bare, "www."+bare]`, or exactly the `.invalid` sentinel when there is no domain — never `[]`). All three domain-search sites (the cloud companies branch's `HubSpot Company Search`, the local-live sibling body `HS_CO_SEARCH_BODY_EXPR`, and the ingest lane's `BUILD_COMPANY_LINK`/`CO_LINK_DOMAIN_SEARCH_BODY`) switched from `operator: "EQ"` to `operator: "IN"` over that pair, one search per row. RED observed first (8 tests, 2 pass / 6 fail against the pre-fix committed workflow — quoted below).
- **Task 2 (D-73-22 + D-73-20):** `Adapt Company Name Search` now stamps `name_search_outcome`/`name_search_hit_count` for a name-only row and stamps `lookup_failed` on a genuine transport error (rather than silently swallowing it); `Company Gate` converts a name-only zero-hit or many-hit outcome into `review` (never `create`, never `skip`) with a reason naming the failure shape, the missing domain, and the remedy, ordered after the pre-existing `lookup_failed` and recompute overrides so neither is reclassified. `Adapt Company Search` now prefers the bare-domain hit when an IN search returns both stored forms of one company, and `Company Gate` surfaces both ids in the reason. RED observed first (6 tests, 2 pass / 4 fail).
- **Task 3 (F-B3, D-73-08/D-73-09):** a new `extract_js_const()` build helper regex-extracts `FREEMAIL_DOMAINS` verbatim from `n8n/code/companyLink.js` and splices it into `Decide Company Action`, which now refuses a create whose domain is freemail (`review`, reason `"freemail domain — supply the real website"`), computed *before* the pre-existing create-seed block so a refused create never seeds the domain it is being refused for. `company_domain.py`'s `_validate_decision` gained a shared `_guard_domain` helper (also de-duplicating the two previously-identical profile-page checks) that additionally refuses a freemail domain, reusing `enrichment.FREEMAIL_DOMAINS` — no new set. RED observed first (backend: 3 pass / 2 fail; plugin: 4 pass / 2 fail).
- Two pre-existing Python tests (`test_bug10_company_search_transport.py`, `test_cloud_write_path.py`) still pinned the pre-Task-1 `EQ` filter shape — caught by this task's own full-suite run (not by Task 1's narrower `<verify>` block) and fixed in a dedicated `fix(73-03)` commit.
- Full regeneration after every commit produced zero stray diff outside `n8n/wf_*.json`; every regenerated body reads disarmed (`ALLOW_* = "false"` throughout).

## Task Commits
1. **Task 1 (RED):** `a4d24833` (test) — `tests/n8n/companyDomainVariants.test.mjs`
2. **Task 1 (GREEN):** `2d20fb3c` (feat) — domain_variants + IN search on all three sites
3. **Task 2 (RED):** `0f7fc0e8` (test) — `tests/n8n/companyNameOnlyOutcome.test.mjs`
4. **Task 2 (GREEN):** `3b2d4657` (feat) — name-only review outcomes + two-hit domain preference
5. **Deviation fix:** `9c070561` (fix) — two stale Python transport-test assertions
6. **Task 3 (RED):** `f80a073e` (test) — `tests/n8n/companyFreemailRefusal.test.mjs` + plugin test extension
7. **Task 3 (GREEN):** `4f699d03` (feat) — freemail refusal in both engines

## RED Evidence (quoted per acceptance criteria)

**Task 1**, `node --test tests/n8n/companyDomainVariants.test.mjs` against the pre-fix workflow:
```
ℹ tests 8
ℹ pass 2
ℹ fail 6
```
Failures: `EQ` !== `IN`; a no-domain row's `filter.values` was `undefined` (not the sentinel array); the www.-stored record's `hs_object_id` was `undefined` (never resolved from a bare-domain request).

**Task 2**, `node --test tests/n8n/companyNameOnlyOutcome.test.mjs` against the pre-fix workflow:
```
ℹ tests 6
ℹ pass 2
ℹ fail 4
```
Failures: zero-hit and many-hit name-only rows still resolved to `create`, no `name_search_outcome` stamped; a transport error on the name search was silently swallowed (no `lookup_failed`); a two-hit domain search had no preference or note.

**Task 3**, backend (`node --test tests/n8n/companyFreemailRefusal.test.mjs`): `tests 5 / pass 3 / fail 2` (every freemail domain still created; `gmail.com` specifically still created). Plugin (`.venv/bin/python -m pytest -k 'freemail or domain' operator-claude-plugin/tests/test_company_extraction.py`): `2 failed, 4 passed` — `DID NOT RAISE DomainDecisionError` for both the confirm and correction freemail cases.

## Files Created/Modified
- `scripts/build_cloud_workflows.py` — `domain_variants` computation, IN filters on three search sites, name-only outcome stamping and gate override, two-hit domain preference, `extract_js_const()` helper, freemail refusal in `Decide Company Action`
- `operator-claude-plugin/scripts/company_domain.py` — `_guard_domain` helper (profile-page + freemail checks), reused by both the confirm and correction branches
- `operator-claude-plugin/tests/test_company_extraction.py` — 4 new freemail tests against the confirm/decline lane
- `tests/test_bug10_company_search_transport.py`, `tests/test_cloud_write_path.py` — updated to assert `IN`/`domain_variants` instead of the retired `EQ`/`identity_keys.domain` shape
- `tests/n8n/companyDomainVariants.test.mjs`, `tests/n8n/companyNameOnlyOutcome.test.mjs`, `tests/n8n/companyFreemailRefusal.test.mjs` — new test files
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_contact_ingest_cloud.json` — regenerated

## Decisions Made
See `key-decisions` in frontmatter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two Python transport tests still pinned the pre-Task-1 EQ filter shape**
- **Found during:** Task 3's full-suite verification run (`.venv/bin/python -m pytest tests/ operator-claude-plugin/tests/`)
- **Issue:** `test_bug10_company_search_transport.py::test_company_search_node_body_preserves_the_original_filter_semantics` and `test_cloud_write_path.py::test_hubspot_search_filters_use_the_correct_identity_property` both asserted `operator: "EQ"` over `$json.identity_keys.domain` on the `"HubSpot Company Search"` node's `jsonBody` — the exact shape Task 1's D-73-06 fix replaced with `IN` over `$json.domain_variants`. Missed at Task 1's own commit because its `<verify>` block ran only the node suite, not the full Python suite.
- **Fix:** Updated both assertions to expect `operator: "IN"` and `$json.domain_variants`, with a comment pointing at `tests/n8n/companyDomainVariants.test.mjs` for the full behavioural pin.
- **Files modified:** `tests/test_bug10_company_search_transport.py`, `tests/test_cloud_write_path.py`
- **Verification:** `.venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/` → 4961 passed / 154 skipped (0 failed)
- **Commit:** `9c070561`

**Total deviations:** 1
**Impact:** None on scope or behaviour — a test-only correction to keep the suite honest about Task 1's own intended change.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness

73-03 is complete. F-B7, the folded F-B4, and F-B3 are closed. `wf_enrichment_local_live.json` was touched by Tasks 1 and 2 (shared `ENRICH_BUILD_CO_IDENTITY`/`ENRICH_CO_GATE`/`ENRICH_ADAPT_CO_SEARCH`/`ENRICH_ADAPT_CO_NAME_SEARCH` constants) but not Task 3 (its own decide node, `ENRICH_DECIDE_CO_LOCAL`, is a dry-run echo that never references `FREEMAIL_DOMAINS`) — this is expected and documented, not a gap. Remaining phase 73 findings (F-A6, F-A5, F-E1 done in 73-02, F-B5 done in 73-01, F-B6, and the rest of the F-A1/A2/B1 cost-envelope work) are separate plans' scope. Nothing is armed, deployed, or bounced from this session — the operator's end-of-phase gate (D-73-18) still owns that.

## Self-Check: PASSED

---
*Phase: 73-ga-fix-list-from-stress-attempt-2*
*Completed: 2026-09-15*
