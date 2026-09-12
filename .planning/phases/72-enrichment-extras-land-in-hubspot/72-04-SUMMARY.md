---
phase: 72-enrichment-extras-land-in-hubspot
plan: 04
subsystem: enrichment-merge-engine
tags: [n8n, hubspot, merge-policy, recency, ttl, provenance, python-oracle, phase-46-parity]

requires:
  - phase: 72-02
    provides: source_by_field round-level provenance map on the ingest lane, widened candidate fields
  - phase: 72-03
    provides: enrich-before-ingest, provider_sourced_fields() feeding source_by_field truthfully
provides:
  - A real TTL/recency branch for stale_refreshable fields in all three merge engines (n8n/code/mergeContacts.js, n8n/code/mergeCompanies.js, src/merge_policy.py), replacing the prior blanket "Refresh candidate requires review in MVP." refusal for any non-blank existing value
  - The generalized four-conjunct system-correctable predicate (§17.2.1), now available to stale_refreshable fields (contacts.jobtitle, companies.industry), not just companies.domain/manual_protected
  - The ingest lane's own HubSpot property-history fetch ("HubSpot Contact History"), giving the recency gate a genuine existing-value clock on the one lane this phase can prove live
affects: [72-05, 72-06, 72-07, phase-72-follow-up-history-hop-gap]

actuals:
  tokens: 571000
  tasks: 3
  commits: 6
  # This estimate includes ~1.9MB of generated n8n workflow JSON diff (8 wf_*.json files
  # regenerated across all three tasks) -- the hand-written source diff (JS/Python engines,
  # build_cloud_workflows.py, tests, config) is a small fraction of that raw character count.
  # Comparing directly against the plan's estimateTokens (135000, hand-written-source scale)
  # would understate the true multiplier for any future plan touching this many committed
  # workflow bodies.

tech-stack:
  added: []
  patterns:
    - "opts.now / now= kwarg: a caller-suppliable deterministic clock resolved once per merge call, used for both the TTL comparison and the provenance verified_at stamp -- absent falls back to the real wall clock, byte-identical to every pre-72 call site."
    - "opts.sourceByField[field] (falling back to opts.source) resolves per-FIELD whether a candidate carries an observation time -- csv/human/hubspot/absent never do, only apollo/lusha/zoominfo/claude_web do. Prevents a flat request-level source from making every field's recency comparison inert."
    - "opts.historyByField[field]: the existing value's OWN clock, sourced only from HubSpot's propertiesWithHistory versions[].timestamp (max-scan, order not assumed) -- never a value read off the row itself, which is what makes a backdated CSV column unable to inject a false observation time (T-72-02)."
    - "_ingest_seq row-ordinal stamp: when a lane splits and reconverges through an append-mode Merge (which concatenates lane-0-then-lane-1, not original order), the node upstream of the split stamps an ordinal and the reconvergence point sorts on it before stripping it -- restores original row order for every order-sensitive downstream consumer."

key-files:
  created:
    - tests/n8n/mergeRecencyGate.test.mjs
    - tests/n8n/contactHistoryFlow.test.mjs
  modified:
    - n8n/code/mergeContacts.js
    - n8n/code/mergeCompanies.js
    - src/merge_policy.py
    - config/field_policy.yaml
    - operator-claude-plugin/config/field_policy.yaml
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - tests/test_merge_policy.py
    - tests/test_merge_helpers.py
    - tests/n8n/mergeInputContract.test.mjs
    - tests/n8n/ingestCarryMerge.test.mjs
    - tests/n8n/ingestMixedBatch.test.mjs
    - tests/n8n/ingestTracerFlow.test.mjs
    - tests/n8n/ingestWidenedFieldsFlow.test.mjs
    - tests/n8n/writeGateShape.test.mjs
    - tests/fixtures/companies_jscode_frozen.json

key-decisions:
  - "D-72-06/07/09: the recency predicate lands in all three engines in one commit (Phase 46 parity), keyed on opts.now/opts.historyByField, with per-field (not per-call) resolution of whether a candidate carries an observation time -- an ingest lane whose flat source is 'csv' would otherwise make the whole mechanism permanently inert."
  - "D-72-08: the four §17.2.1 conjuncts generalize unchanged to a second field class (stale_refreshable) rather than gaining a new relaxed variant -- system_correctable_sources added to exactly contacts.jobtitle and companies.industry, companies.domain's [create_seed] list untouched."
  - "Task 3 scope held to the ingest lane only, per the plan's own explicit boundary -- the enrichment lane's contacts branch and the companies branch get no history hop this phase. See 'Design gap for a follow-up plan' below."
  - "Row-order fix (found running this task's own suite, Rule 1): the Contact History split's append-mode reconvergence Merge concatenates its two lanes out of original order. Fixed with a stamp-then-sort ordinal (_ingest_seq) rather than restructuring the topology, per advisor guidance -- production itself is order-agnostic (every downstream hop re-pairs by its own item), but the walker's positional stubs and any order-sensitive future consumer are not, so order is restored anyway."

requirements-completed: [D-72-06, D-72-07, D-72-08, D-72-09]

coverage:
  - id: D1
    description: "A stale_refreshable field's existing value older than stale_after_days is overwritten by a newer provider observation; a value newer than the TTL is not, in all three engines from one shared fixture table."
    requirement: D-72-06
    verification:
      - kind: unit
        ref: "tests/n8n/mergeRecencyGate.test.mjs (21 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_merge_policy.py (35 tests, recency + system-correctable fixtures)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Whether a candidate carries the dispatch clock is resolved per-field from opts.sourceByField, never a value read off the row -- a CSV value carries no observation time and can never win."
    requirement: D-72-07
    verification:
      - kind: unit
        ref: "tests/n8n/mergeRecencyGate.test.mjs (csv-vs-provider fixture pair)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A provenance entry naming a provider on system_correctable_sources, still matching the current value, on a conflict-free row at/above min_confidence, promotes a stale_refreshable field even when not past TTL -- the same four conjuncts as company domain/create_seed, untouched."
    requirement: D-72-08
    verification:
      - kind: unit
        ref: "tests/n8n/mergeRecencyGate.test.mjs (system-correctable suite, 7 tests) + decideCompanyActionCreateSeedProvenance.test.mjs regression"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_merge_policy.py tests/test_field_policy_conformance.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "The ingest lane resolves a matched contact's jobtitle property history through one HTTP hop after identity resolution, joined back to its row by a carry Merge with a sentinel on the net_new lane, feeding Merge Contacts as opts.historyByField -- no Merge on the lane can starve."
    requirement: D-72-09
    verification:
      - kind: unit
        ref: "tests/n8n/contactHistoryFlow.test.mjs (5 tests)"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/*.test.mjs (1139/1139, full ingest-lane regression)"
        status: pass
    human_judgment: false

duration: 240min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 04: Recency Gate + System-Correctable Provenance + Ingest-Lane Property History Summary

**A real TTL/recency gate replaces the blanket "needs review" refusal for stale_refreshable fields in all three merge engines, extends the system-correctable predicate to the pipeline's own provider-written values, and wires HubSpot's own property-history fetch into the ingest lane so the gate has a genuine clock to compare against.**

## Performance

- **Duration:** ~240 min
- **Started:** 2026-09-12T08:19:00+10:00 (per session memory log)
- **Completed:** 2026-09-12T21:02:19+10:00
- **Tasks:** 3
- **Files modified:** 25 (across all 3 tasks; see `git diff --stat 447c4b65~1..HEAD`)

## Accomplishments
- A `stale_refreshable` field (contacts `jobtitle`, 180-day TTL; companies `industry`, 365-day TTL) now genuinely refreshes when its existing value is older than its TTL AND a newer provider observation exists — previously refused unconditionally regardless of age.
- The recency comparison is per-field, not per-call: `opts.sourceByField[field]` (falling back to `opts.source`) decides whether a candidate carries an observation time at all, so the ingest lane's flat `source: "csv"` cannot make every field appear equally (un)trustworthy.
- The §17.2.1 system-correctable predicate — previously scoped to `companies.domain`/`manual_protected` and the `create_seed` source only — now also applies to `stale_refreshable` fields, letting the pipeline's own provider-written value be corrected by a genuinely newer provider observation even before its TTL expires, under the identical four conjuncts.
- The ingest lane fetches HubSpot's own `propertiesWithHistory` for every matched row's refreshable contact fields, giving the recency gate a real "existing value's own clock" on the one lane this phase can prove live end-to-end.
- Fixed a latent Python bug found during Task 2: `deterministic_gate`'s `manual_protected` branch always read the company provenance key regardless of `record.object_type`, which would have made the new contacts arm fail-closed against the wrong property.
- Fixed a genuine row-reordering bug found running Task 3's own test suite: an append-mode Merge reconverging the history-hop split concatenates its lanes out of original order, silently misaligning downstream company-search/association pairing on the walker's positional stubs.

## Task Commits

Each task was committed as a RED/GREEN TDD pair:

1. **Task 1: Recency/TTL gate, all three engines** — `447c4b65` (test, RED) / `02eafef1` (feat, GREEN)
2. **Task 2: Provider-written value becomes correctable** — `5ad51858` (test, RED) / `0ca19248` (feat, GREEN)
3. **Task 3: HubSpot property history reaches the ingest lane** — `0b6f0967` (test, RED) / `254a78b9` (feat, GREEN)

**Plan metadata:** (this commit, following)

## Files Created/Modified
- `n8n/code/mergeContacts.js` — recency gate, system-correctable arm, `historyByField`/`sourceByField` opts, `_ingest_seq`-aware caller (via `scripts/build_cloud_workflows.py`)
- `n8n/code/mergeCompanies.js` — same recency/system-correctable branches, `opts.sourceByField` support added
- `src/merge_policy.py` — Python oracle mirror: `_is_stale`, `_is_system_correctable`, `_provenance_key_for` (object-type-aware, fixes the latent bug above)
- `config/field_policy.yaml` + `operator-claude-plugin/config/field_policy.yaml` — `stale_after_days` and `system_correctable_sources` on `contacts.jobtitle`/`companies.industry`
- `scripts/build_cloud_workflows.py` — `HubSpot Contact History` node, carry Merge, sentinel gate, `_ingest_seq` stamp/sort/strip, `refreshable_contact_props()` import
- `scripts/deploy_n8n_workflows.py` — credential mapping for the new node
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_contact_ingest_local.json` — regenerated (the only two workflows this task's own change touches; `wf_enrichment_*`/`wf_review_decision_cloud`/`wf_scheduled_maintenance_cloud` picked up only the Task 1/2 engine-JS diffs, no topology change)
- `tests/n8n/mergeRecencyGate.test.mjs` (new, 21 tests), `tests/n8n/contactHistoryFlow.test.mjs` (new, 5 tests), `tests/test_merge_policy.py` (+35 tests)
- 8 pre-existing walker test files updated with `HubSpot Contact History` httpStubs sized to each fixture's matched-row count
- `tests/test_merge_helpers.py` — append/combine-merge census updated for the two new Merges this task adds

## Decisions Made
- Recency/system-correctable predicates land in all three engines in one commit each (Phase 46 parity), never split across separate commits per engine.
- The recency mechanism's per-field source resolution (not per-call) was a deliberate design choice from the plan, confirmed necessary before writing Task 3's test: the ingest lane's flat `source: "csv"` would otherwise make the whole TTL mechanism permanently inert.
- Row-order fix implemented as a stamp-then-sort ordinal rather than a topology change (advisor consultation): production is order-agnostic by construction (every downstream hop re-pairs by its own item), so the fix targets the walker's positional-stub fidelity and any future order-sensitive consumer, not a live defect.
- Confirmed (not assumed) that plan 03's `enrich-before-ingest` change reaches `dispatch.py`'s `source_by_field=` kwarg (`operator-claude-plugin/scripts/dispatch.py:129-130`) before writing Task 3's test — the plan named this a blocker-if-false; it is true, so the hop is not dead code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_PROVIDER_SOURCES` const redeclaration across inlined engines**
- **Found during:** Task 1
- **Issue:** Both `mergeCompanies.js` and `mergeContacts.js` declared `const _PROVIDER_SOURCES = new Set([...])` at module scope; both are inlined into a single compiled Code node body (the review decision endpoint), and `const` redeclaration throws `SyntaxError` even in non-strict eval.
- **Fix:** Converted to `function _isProviderSource(name) { ... }` in both files (function declarations can be safely redeclared, an established pattern in this codebase for `_isBlank`/`_gate`/etc.).
- **Files modified:** n8n/code/mergeContacts.js, n8n/code/mergeCompanies.js
- **Verification:** Full node suite green (1127/1127 at the time).
- **Committed in:** 02eafef1 (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Company `industry` test fixtures used unmappable enum strings**
- **Found during:** Task 1
- **Issue:** `mergeCompanies.js` runs `normalizeEnumValue()` on `industry` before the gate's decision is finalized; an unmappable value (made-up "Old Industry"/"New Industry" test strings) forces `decision = "stage_only"` regardless of the gate's own verdict, masking the recency behavior under test.
- **Fix:** Replaced fixtures with valid HubSpot enum values ("Sports"/"Media Production"), verified via a direct `normalizeEnumValue()` probe.
- **Files modified:** tests/n8n/mergeRecencyGate.test.mjs
- **Committed in:** 02eafef1 (Task 1 GREEN commit)

**3. [Rule 1 - Bug] Latent Python provenance-key bug**
- **Found during:** Task 2
- **Issue:** `deterministic_gate`'s `manual_protected` branch always read `COMPANY_PROVENANCE_KEY` regardless of `record.object_type` — would have made the new contacts system-correctable arm fail-closed against the wrong property.
- **Fix:** New `_provenance_key_for(record)` selects `CONTACT_PROVENANCE_KEY` for contacts, `COMPANY_PROVENANCE_KEY` otherwise; used by both the pre-existing `manual_protected` branch and the new `stale_refreshable` arm.
- **Files modified:** src/merge_policy.py
- **Committed in:** 0ca19248 (Task 2 GREEN commit)

**4. [Rule 1 - Bug] Row-reordering across the Contact History split**
- **Found during:** Task 3, running `ingestCarryMerge.test.mjs` after wiring the new hop
- **Issue:** `splice_merge_before`'s append-mode Merge concatenates lane-0-then-lane-1, reordering the four-row batch from `[1,2,3,4]` to `[1,4,2,3]` (matched-lane rows first). This misaligned the walker's positional company-search stubs downstream, producing a `merge_dropped_rows` failure on "Associate Carry Merge" that had not existed before this task's topology change.
- **Fix:** `Resolve Identity` (the single node upstream of the split that sees every row in one run) stamps `_ingest_seq: i`; `MERGE_CONTACTS` sorts on it (`?? 0` guard, a no-op for `build_local()`'s unsplit workflow) and strips it before emitting. Diagnosed via `advisor()` consultation before implementing.
- **Files modified:** scripts/build_cloud_workflows.py
- **Verification:** `node --test tests/n8n/ingestCarryMerge.test.mjs` green; full node suite green (1139/1139).
- **Committed in:** 254a78b9 (Task 3 GREEN commit)

**5. [Rule 3 - Blocking] 12 pre-existing walker tests needed `HubSpot Contact History` stubs**
- **Found during:** Task 3, full-suite regression after adding the new node
- **Issue:** `tests/n8n/writeGateShape.test.mjs` (4 tests), `ingestCarryMerge.test.mjs` (1), `ingestMixedBatch.test.mjs` (4), `ingestTracerFlow.test.mjs` (1), `ingestWidenedFieldsFlow.test.mjs` (4) now reach the new HTTP node on their matched rows and threw "unstubbed HTTP node" — the walker's own documented contract for an HTTP node reached with no stub.
- **Fix:** Added `"HubSpot Contact History"` stubs sized to each fixture's own matched-row count (array or function form matching the existing stub style in each file).
- **Files modified:** tests/n8n/writeGateShape.test.mjs, tests/n8n/ingestCarryMerge.test.mjs, tests/n8n/ingestMixedBatch.test.mjs, tests/n8n/ingestTracerFlow.test.mjs, tests/n8n/ingestWidenedFieldsFlow.test.mjs
- **Committed in:** 254a78b9 (Task 3 GREEN commit)

**6. [Rule 3 - Blocking] `_MERGE_MULTI_PRODUCER_TOLERANT` dual-registration**
- **Found during:** Task 3
- **Issue:** `build_cloud_workflows.py`'s own internal `assert_merge_input_contract` guard refused generation: `Contact History Merge`'s sentinel gate legitimately shares an input with the real matched-lane producer, which requires explicit allowlist registration even though mutually exclusive by construction (D-70-23).
- **Fix:** Added `("LV Contact Ingest (Cloud template)", "Contact History Merge")` to the Python allowlist and mirrored it into `tests/n8n/mergeInputContract.test.mjs`'s own JS-side Map (no cross-language import possible; both must independently agree).
- **Files modified:** scripts/build_cloud_workflows.py, tests/n8n/mergeInputContract.test.mjs
- **Committed in:** 254a78b9 (Task 3 GREEN commit)

**7. [Rule 1 - Bug] Stale merge-census assertion**
- **Found during:** post-implementation full pytest run (Task 3)
- **Issue:** `tests/test_merge_helpers.py::test_ingest_workflow_carries_exactly_one_append_merge_named_ingest_merge_response` hardcoded the exact set of append-mode and combine-mode Merges on the ingest lane; Task 3 legitimately added one of each (`Contact History Merge` append, `HubSpot Contact History Carry Merge` combine).
- **Fix:** Updated both set assertions to include the two new Merges, with a comment explaining why each is a genuine addition (a real two-lane convergence and an HTTP-hop carry, respectively) rather than scope creep.
- **Files modified:** tests/test_merge_helpers.py
- **Committed in:** 254a78b9 (Task 3 GREEN commit)

---

**Total deviations:** 7 auto-fixed (4 Rule 1 bugs, 3 Rule 3 blocking fixes). All within the scope of making Task 1-3's own new code correct and its own test suite pass; no unrelated pre-existing failures were touched (scope boundary respected).
**Impact on plan:** All fixes necessary for correctness of the recency gate, the system-correctable extension, and the ingest-lane history hop. No scope creep — every fix traces to code or tests this plan's own tasks introduced or directly exercise.

## Known Stubs

None. `mergeContacts.js`'s companies-branch equivalent of `opts.rowConflicted` remains unset on the ingest lane (`MERGE_CONTACTS` never computes a row-level conflict set), which makes the contacts system-correctable arm inert in production today — this is a documented, intentional scope boundary (the mechanism is built and tested in all three engines; wiring a real conflict signal into the ingest lane is explicitly out of scope for this plan), not a stub masking incomplete work.

## Design Gap for a Follow-Up Plan (per Task 3's explicit instruction)

The enrichment lane's contacts branch and the companies branch have **no** history hop — only the contact ingest lane does. Company `industry` recency and enrichment-lane contact `jobtitle` recency therefore remain unobservable and behave exactly as they did pre-Phase-72: unknown freshness always resolves to `needs_review`. **Decision the follow-up todo needs:** whether to add the same `propertiesWithHistory` hop to those two lanes, or to accept the pipeline's own `lv_<field>_verified_at` cache keys as a narrower substitute there. Not filed as a `.planning/todos/pending/` entry in this session — should be triaged per CLAUDE.md §31 (kind: `design`, `decision_needed:` the choice above) before this phase's batch closes.

## Issues Encountered

Diagnosing the Task 3 row-reordering bug (`merge_dropped_rows` on "Associate Carry Merge") required an `advisor()` consultation mid-session — the failure appeared only after the new Contact History hop was wired, and the root cause (append-mode Merge concatenation order vs. the walker's positional stubs) was not obvious from the failure's own assertion output alone. Resolved per the advisor's guidance: stamp-then-sort ordinal, confirmed production itself is order-agnostic before implementing (avoiding an unnecessary topology change).

## User Setup Required

None — no external service configuration required. Nothing in this plan deploys, bounces, or arms anything against live n8n Cloud or HubSpot (per the task's own `<reversibility rating="costly">` note: the workflow JSON changes are generated-and-committed only, redeploy is a separate operator action deferred to this phase's end-of-phase UAT).

## Next Phase Readiness
- All three merge engines now share a working recency/TTL branch and system-correctable extension, verified against one shared fixture table (Phase 46 parity evidence).
- The ingest lane's history hop is proven end-to-end via the walker; a real n8n Cloud deploy/bounce and disarmed proof send remain an operator action for this phase's own end-of-phase UAT, not part of this plan.
- The enrichment-lane/companies-branch history gap is a known, named blocker for whichever follow-up plan in this phase (or phase 72's remaining waves) picks up full-lane recency coverage.

## Self-Check: PASSED

All created files verified present on disk (tests/n8n/mergeRecencyGate.test.mjs,
tests/n8n/contactHistoryFlow.test.mjs, this SUMMARY.md). All 6 task commit hashes
(447c4b65, 02eafef1, 5ad51858, 0ca19248, 0b6f0967, 254a78b9) verified present in
`git log --oneline --all`.

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
