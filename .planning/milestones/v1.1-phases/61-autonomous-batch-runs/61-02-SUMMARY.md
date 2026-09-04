---
phase: 61-autonomous-batch-runs
plan: "02"
subsystem: identity-resolution
tags: [n8n, hubspot, matchProposal, resolveIdentity, linkedin, identity-resolution]

requires:
  - phase: 36
    provides: "the match-lane cascade (laneOf/summarizeMatch, IF Has Email -> IF Name Searchable) this plan splices a new lane into"
provides:
  - "A `linkedin` match lane: laneOf routes a linkedin-only row to it, `HubSpot Linkedin Search` filters BOTH lv_linkedin_url and native hs_linkedin_url over a written-down variant set, `Adapt Linkedin Search` re-verifies every hit by canonicalized value before reporting a match"
  - "src/identity.py's linkedin branch fixed to search a property that actually exists on the live portal, searching + requesting both properties as two sequential calls unioned by contact id"
  - "operator-claude-plugin's MATCH_LOOKUP_KEYS widened so a LinkedIn URL the operator supplies can reach the backend at all"
affects: [61-03, 61-04, 61-05, 61-06]

actuals:
  tokens: 17685
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Additive splice into an existing IF cascade: new IF/search/adapter row inserted between two existing nodes by re-pointing exactly one edge, with every other node's position/wiring untouched"
    - "Search-variant widening kept OFF the shape-pinned identity_keys object (a sibling row field instead), so a new search input cannot perturb an unrelated exact-shape test"
    - "IN-filter-with-array over EQ-with-scalar for value-shape variance HubSpot's own operator can absorb, reserving JS-side canonicalize-and-compare for variance the filter cannot"

key-files:
  created:
    - tests/n8n/linkedinLaneFlow.test.mjs
  modified:
    - n8n/code/matchProposal.js
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - src/identity.py
    - operator-claude-plugin/scripts/enrichment.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - tests/n8n/matchProposal.test.mjs
    - tests/n8n/parity.test.mjs
    - tests/n8n/rowsEnvelopeContract.test.mjs
    - operator-claude-plugin/tests/test_rows_envelope_contract.py
    - operator-claude-plugin/tests/test_preingest_match.py
    - operator-claude-plugin/tests/test_retry_reuses_dispatch.py
    - tests/test_identity.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "The linkedin arm in summarizeMatch is DEDICATED, never joined to the two-outcome fetch_by_id/email arm (REVIEW-C4) — it reads verified-candidate cardinality (0/1/>1), not existingRecord, so a >1 case can carry candidates rather than silently reading as `none`"
  - "The search variant set (up to 9: canonical host+path crossed with {https,http}x{no-www.,www.}x{no-slash,trailing-slash}, plus the raw input as given) is stored as a SIBLING row field (linkedin_url_variants), not a member of identity_keys, so it cannot perturb bareEventChainFlow.test.mjs's exact-shape pin on identity_keys"
  - "IN over 2 filter groups (one per property), never a variant x property cross-product — REVIEW-C5's bound, made a constant regardless of variant-set growth"
  - "The Python oracle ORs across lv_linkedin_url/hs_linkedin_url by calling hs_search TWICE (the shared search_records seam wraps filters in one filterGroup and cannot express an OR across properties) rather than widening src/hubspot_client.py — the smaller, scoped change over the larger, shared-infrastructure one (REVIEW-C6 cycle-3 residual)"
  - "CONTAINS_TOKEN on a URL-valued property recorded [unknown], deliberately not adopted — EQ/IN's exact-match semantics are provable offline, tokenization semantics are not"

requirements-completed: [INPUT-05]

coverage:
  - id: D1
    description: "A LinkedIn-only row (the exact walk-failure row) routes to a `linkedin` lane, reaches a HubSpot search, and returns a verdict other than `unknown`"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "tests/n8n/linkedinLaneFlow.test.mjs#mixed batch: an email row, a linkedin-only row and a name-only row each produce exactly one item, and the linkedin row is never unknown"
        status: pass
    human_judgment: false
  - id: D2
    description: "The search survives stored-value variance (trailing slash, scheme/host case, query string) without becoming a fuzzy match that can pick the wrong person"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "tests/n8n/linkedinLaneFlow.test.mjs#a stored value differing only in trailing slash still matches the operator's input, through the real adapter"
        status: pass
      - kind: unit
        ref: "tests/n8n/linkedinLaneFlow.test.mjs#a different profile under the same host does NOT match, through the real adapter (false positive here writes to the wrong person)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Python oracle (src/identity.py) searches a property that exists on the live portal and agrees with the n8n lane's native-property coverage"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "tests/test_identity.py::test_no_email_linkedin_found_only_under_native_property_still_matches"
        status: pass
    human_judgment: false
  - id: D4
    description: "linkedin_url crosses the operator-claude-plugin boundary on a rows envelope; phone/jobtitle still do not"
    requirement: INPUT-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_rows_envelope_contract.py::test_the_event_projection_is_match_lookup_keys_not_the_rows_own_keys"
        status: pass
    human_judgment: false

duration: ~90min
completed: 2026-08-30
status: complete
---

# Phase 61 Plan 02: The Linkedin Match Lane, End to End Summary

**A LinkedIn-only row now routes to a dedicated `linkedin` match lane, reaches a HubSpot search that filters on the property that actually exists (both `lv_linkedin_url` and native `hs_linkedin_url`, over a written-down variant set), and comes back with a verified verdict — closing the exact defect that halted walk run 4.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 3
- **Files modified:** 17 (3 generated workflow JSONs + 14 source/test files)

## Accomplishments

- `n8n/code/matchProposal.js`: `laneOf` gained a `linkedin` branch (strong key, ranked
  between `email` and the weak `name` pair per D-61-03); `summarizeMatch` gained a
  DEDICATED three-outcome `linkedin` arm (0/1/>1 verified hits -> none/high/medium),
  correcting the plan's own earlier "join it to the two-outcome arm" instruction
  (REVIEW-C4); new `verifiedLinkedinHits`/`linkedinAgreement` helpers re-verify every hit
  by canonicalized value and reject a contact whose two LinkedIn properties disagree with
  each other (T-61-05).
- `scripts/build_cloud_workflows.py`: additive `IF Linkedin Searchable` -> `HubSpot
  Linkedin Search` -> `Adapt Linkedin Search` row spliced between `IF Has Email` and `IF
  Name Searchable`, moving no existing node's position. The search filters BOTH
  `lv_linkedin_url` and native `hs_linkedin_url` via an `IN` filter over a bounded,
  written-down, test-pinned variant set computed once in `Build Identity` (up to 9
  variants: the canonicalized host+path crossed with scheme/`www.`/trailing-slash, plus
  the raw input as given) — 2 filter groups total, never a variant x property
  cross-product (REVIEW-C5). `MERGE_CONTACTS` now canonicalizes before writing
  `lv_linkedin_url` so stored values converge going forward.
- `src/identity.py`: the oracle's linkedin branch was searching a property
  (`linkedin_url`) that has never existed on the live portal — confirmed via the committed
  live snapshot — so it has never once been reachable live. Fixed to search AND request
  both `lv_linkedin_url` and `hs_linkedin_url`, as two sequential `hs_search` calls (the
  shared search seam can only express one AND'd filterGroup per call) unioned by contact
  id before deciding cardinality — `src/hubspot_client.py` deliberately untouched
  (REVIEW-C6).
- `operator-claude-plugin/scripts/enrichment.py`: `MATCH_LOOKUP_KEYS` widened from four to
  five, admitting `linkedin_url` — the backend lane above is unreachable until the
  operator's own supplied key can leave their machine. Plugin bumped 0.28.6 -> 0.29.0 with
  a CHANGELOG entry in the same commit.

## Task Commits

Each task was committed atomically:

1. **Task 1: The linkedin lane, end to end** - `360e580` (feat)
2. **Task 2: Make the search survive stored-value variance, and fix the oracle's dead filter** - `884ea6c` (feat)
3. **Task 3: Un-freeze MATCH_LOOKUP_KEYS, restate the disclosure boundary, ship the release** - `64cc7d3` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `n8n/code/matchProposal.js` — linkedin lane routing + dedicated 3-outcome tier arm + re-verification helpers
- `scripts/build_cloud_workflows.py` — new IF/search/adapter nodes, wiring, variant-set generation, MERGE_CONTACTS canonicalization, `render_filter` gained `values` (IN operator) support
- `scripts/deploy_n8n_workflows.py` — deviation: registered the new HubSpot node's credential binding
- `src/identity.py` — corrected property names, dual-property union search, written variant set
- `operator-claude-plugin/scripts/enrichment.py` — MATCH_LOOKUP_KEYS widened, boundary comment rewritten
- `operator-claude-plugin/.claude-plugin/plugin.json`, `operator-claude-plugin/CHANGELOG.md` — 0.29.0 release
- `tests/n8n/linkedinLaneFlow.test.mjs` (new) — wiring, adapter, stored-variance, and the decisive mixed-batch test
- `tests/n8n/matchProposal.test.mjs`, `tests/test_identity.py` — new lane/oracle coverage
- `tests/n8n/parity.test.mjs`, `tests/n8n/rowsEnvelopeContract.test.mjs`, `operator-claude-plugin/tests/test_rows_envelope_contract.py`, `operator-claude-plugin/tests/test_preingest_match.py`, `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` — fallout fixes (see Deviations)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json` — regenerated via `scripts/build_cloud_workflows.py`; the other 5 built workflow JSONs are byte-identical (unchanged)

## Decisions Made

- Search-variant widening lives on a sibling row field (`linkedin_url_variants`), not
  inside `identity_keys`, specifically so it cannot perturb `bareEventChainFlow.test.mjs`'s
  pre-existing exact-shape assertion on `identity_keys` — a scope-preserving design choice,
  not a plan requirement.
- `HubSpot Linkedin Search`'s filter is `IN` over 2 groups (one per property) rather than
  `EQ` per variant per property, per REVIEW-C5's bound — the group count is a constant,
  documented beside the node.
- The Python oracle ORs across properties by calling `hs_search` twice rather than
  widening the shared `search_records` client (REVIEW-C6's cycle-3-adjudicated mechanism)
  — the smaller, scoped change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Registered "HubSpot Linkedin Search" in `NODE_CREDENTIAL_MAP`**
- **Found during:** Task 1
- **Issue:** The repo's own `test_fetch_by_id_topology.py`/`test_deploy_credential_binding.py` guards fail any HubSpot-credentialed node absent from `scripts/deploy_n8n_workflows.py`'s `NODE_CREDENTIAL_MAP` — an unmapped node deploys UNBOUND and 401s at runtime.
- **Fix:** Added the one-line map entry in the same commit as the node's creation, per this repo's own stated convention (the seventh time this exact lesson has been applied).
- **Files modified:** `scripts/deploy_n8n_workflows.py`
- **Verification:** `.venv/bin/python -m pytest -q` — full suite green.
- **Committed in:** `360e580` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed the JS/Python identity-parity test after Task 2's oracle fix**
- **Found during:** Task 2's own full-suite verification run
- **Issue:** `tests/n8n/parity.test.mjs`'s `toCanned()` helper translated the JS side's
  semantic `linkedin_url` match-key name to the Python oracle's OLD, dead HubSpot property
  name (`linkedin_url`) — after Task 2 corrected the oracle's filter to `lv_linkedin_url`,
  this cross-language parity test failed (the JS and Python sides genuinely disagreed).
- **Fix:** Updated `toCanned()`'s mapping target to `lv_linkedin_url`, matching the corrected oracle.
- **Files modified:** `tests/n8n/parity.test.mjs`
- **Verification:** `node --test tests/n8n/parity.test.mjs` — 19/19.
- **Committed in:** `884ea6c` (Task 2 commit)

**3. [Rule 1 - Bug] Kept the rows-envelope contract's JS twin in sync after widening MATCH_LOOKUP_KEYS**
- **Found during:** Task 3
- **Issue:** `test_rows_envelope_contract.py`'s pinned `CLIENT_ENVELOPE` literal gained a
  `linkedin_url: None` key (every projected event now carries it). Its JS twin,
  `tests/n8n/rowsEnvelopeContract.test.mjs` (NOT in this task's declared `<files>`),
  carries its OWN hardcoded copy of the same literal, kept in sync only by convention —
  leaving it unchanged would have silently drifted the two contracts apart, exactly the
  documented failure class this pin exists to catch ("a field-name mismatch shipped once
  and killed the whole list lane while both suites stayed green").
- **Fix:** Updated the JS twin's `CLIENT_ENVELOPE` literal and `deriveIdentityKeys` helper
  to match.
- **Files modified:** `tests/n8n/rowsEnvelopeContract.test.mjs`
- **Verification:** `node --test tests/n8n/rowsEnvelopeContract.test.mjs` — 4/4.
- **Committed in:** `64cc7d3` (Task 3 commit)

**4. [Rule 1 - Bug] Updated two "frozen" MATCH_LOOKUP_KEYS guard tests to the new reviewed five-tuple**
- **Found during:** Task 3's own full-suite verification run
- **Issue:** `test_retry_reuses_dispatch.py::test_match_lookup_keys_stays_the_frozen_four`
  and a hardcoded exclusion in `test_preingest_match.py` both asserted the OLD four-member
  tuple and explicitly excluded `linkedin_url` — un-freezing the tuple is this task's own
  stated purpose, so these two tests' literal expectations were the direct, necessary,
  and disclosed consequence of the change, not a scope violation.
- **Fix:** Updated both to assert the new five-tuple (`phone`/`jobtitle` still excluded);
  renamed the first test to `test_match_lookup_keys_stays_the_reviewed_five` to describe
  its actual guarantee (a reviewed, evidence-gated set — not a permanently frozen one).
- **Files modified:** `operator-claude-plugin/tests/test_retry_reuses_dispatch.py`, `operator-claude-plugin/tests/test_preingest_match.py`
- **Verification:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 1725/5 (baseline unchanged).
- **Committed in:** `64cc7d3` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (1 blocking/Rule 3, 3 bug/Rule 1 — all direct, disclosed
consequences of the plan's own stated changes; none introduce scope beyond what the plan
already required).
**Impact on plan:** No scope creep. Two pre-existing test assertions were CHANGED (not
weakened) as the plan's own explicit "un-freeze this tuple" instruction requires — both
now assert a stronger/updated literal, not a looser one. `rtk proxy git --no-pager diff` on
Tasks 1-2's own commits shows zero removed assertions; Task 3's diff shows exactly the two
changes named above.

## Issues Encountered

- HubSpot CRM v3's `IN`/`NOT_IN` operators require a `values` (plural, array) field rather
  than `value` — the existing `_hs_search_json_body_expr` helper only supported `value`.
  Extended `render_filter` additively (a filter with `value` renders byte-identical to
  before; `values` is new) rather than special-casing the one new call site.
- The obvious place to store the LinkedIn search-variant set (`identity_keys`) is
  exact-shape-pinned by an out-of-scope test (`bareEventChainFlow.test.mjs`). Resolved by
  storing it as a sibling row field instead of touching that file at all.

## User Setup Required

None — no external service configuration required. This plan makes zero live n8n,
HubSpot, Anthropic, or provider calls; the backend lane is disarmed/undeployed until a
future plan arms and deploys it.

## Next Phase Readiness

- The tracer slice (D-61-05 CORRECTED, both front-end and backend halves) is complete and
  offline-proven. `operator-claude-plugin`'s next release, once installed, will let a
  LinkedIn-only row actually reach the backend's new lane.
- **Not yet done:** deploying `wf_enrichment_cloud.json` to the live n8n instance and a
  live proof run — this plan is offline-only by its own `<verification>` constraint. A
  future plan (61-03 or later) should deploy, bounce, and prove the lane live against a
  real or test contact, per this repo's `n8n-stored-vs-running-content` lesson (a stored
  read-back proves nothing until a live execution's own `runData` is inspected).
- 61-01 (the async-run spike, `autonomous: false`, checkpointed) has not yet been executed
  this session — it is a sibling wave-1 plan with `depends_on: []`, independent of this one.

## Self-Check: PASSED

All 17 claimed files verified present on disk; all 3 task commit hashes (`360e580`,
`884ea6c`, `64cc7d3`) verified present in `git log --oneline --all`.

---
*Phase: 61-autonomous-batch-runs*
*Completed: 2026-08-30*
