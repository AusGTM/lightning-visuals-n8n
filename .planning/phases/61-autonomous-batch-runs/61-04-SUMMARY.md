---
phase: 61-autonomous-batch-runs
plan: "04"
subsystem: autonomy
tags: [confidence, hold-queue, run-manifest, n8n, outcome-contract, d-61-07]

requires:
  - phase: 61
    provides: "61-01/61-02/61-03's match lanes (fetch_by_id/email/linkedin/name) and the existing run_manifest.py resume machinery this plan builds the confidence gate on top of"
provides:
  - "A per-row outcome contract (outcome_contract_version + five named signals) stamped once at Build Response, the one convergence point every enrichment-lane terminal reaches; preingest.parse_outcome turns a response item into a typed Outcome, failing toward the hold on a missing/unknown signal"
  - "confidence.py: a total, deterministic decision table (confidence.assess) over match tier, provider agreement, material conflicts, and judge adjudication — the confidence self-assessment D-61-07 names as Finding F's missing piece"
  - "held_queue.py: a fourth durable artifact collecting held rows for one end-of-run review, with a per-hold_code resume fingerprint that never re-spends provider credit reaching an identical hold"
  - "run_manifest.py's sixth verdict word (confidence_held), a widened rows_to_resume (held_entries/current_outcomes keyword parameters), run_manifest_path(run_id), and load_scoped()"
  - "enrich-before-ingest/SKILL.md documents the hold-don't-block sequence, reusing step 3's approve/deny/pick/email vocabulary for the single end-of-run review"
affects: [61-05, 61-06]

actuals:
  tokens: 21300
  tasks: 4
  commits: 7

tech-stack:
  added: []
  patterns:
    - "Stamp-at-convergence: a per-terminal field projection that used to die at each terminal's own explicit return object is instead named and normalized ONCE at the shared convergence node (Build Response) every terminal already reaches, rather than duplicated per-terminal"
    - "Per-hold-code fingerprint scoped to the resume-time recompute's own observable signal set, so a comparison whose two sides are produced at different pipeline stages cannot become a structural always-inequality"
    - "Two fields, two consumers: observed_signals (review-facing) and resume_fingerprint (resume-facing) kept structurally separate in the same queue entry, so hashing one for the other's purpose is a type error, not a judgment call"
    - "Widen by keyword-only default-None parameters (rows_to_resume) rather than a second resume rule, so every existing positional caller is byte-for-byte unchanged"

key-files:
  created:
    - operator-claude-plugin/scripts/confidence.py
    - operator-claude-plugin/scripts/held_queue.py
    - operator-claude-plugin/tests/test_outcome_contract.py
    - operator-claude-plugin/tests/test_confidence.py
    - operator-claude-plugin/tests/test_held_queue.py
    - operator-claude-plugin/tests/test_batch_finishes_composition.py
    - tests/n8n/outcomeContractFlow.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/scripts/run_manifest.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_run_manifest.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - n8n/wf_enrichment_cloud.json

key-decisions:
  - "The outcome-contract stamping lives in Build Response (the one node every terminal reaches), not in Decide Action/Decide Company Action individually — but Decide Action's own explicit return object was itself a truncation point for scored/material_conflicts/judge_confidence_by_field, so it needed a small additive carry-forward first (the same paired-carry idiom this file already uses for research_candidate/judge_verdict)."
  - "candidate_count is read from match.candidates.length at the SAME projection point, not re-derived a second way in Python — meaningful only for tier medium by design (high/none/unknown already encode their own cardinality in the tier itself, and summarizeMatch deliberately empties candidates for a high-tier auto-match)."
  - "run_manifest.load() is kept byte-unchanged (still a bare dict) rather than widened to also return the stored run_id, per the plan's own text — a new function, load_scoped(), carries the run-id-and-mismatch behavior instead. This is a deliberate, disclosed adaptation: widening load()'s return shape would have broken every existing caller/test asserting `load(path=...) == verdicts`, and 61-05 (the stated consumer) is not yet written to require the widened shape."
  - "held_queue.py is ONE GLOBAL file (mirroring run_manifest.py's default), never per-run like written_records.py — 'held rows collect into ONE review queue, cleared in a single pass' (D-61-07) reads as a durable backlog across however many runs happen before an operator's review, not a per-run artifact."
  - "The end-of-run review's decision vocabulary is documented as inherited from step 3's numbered table (approve/deny/pick/email), not built as new code in this plan — Task 4's own action text scopes the composition test to the match/confidence/held-queue/manifest sequence, not to a new review-UI implementation."

requirements-completed: [RUN-02, AFTER-02]

coverage:
  - id: D1
    description: "The five confidence-input signals (match tier, verified candidate count, provider agreement, material conflict groups, judge-adjudicated fields) survive the real enrichment lane to Build Response, version-stamped, with absence normalised explicitly rather than left as a missing key"
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#Decide Action + Build Response stamp outcome_contract_version and all five named signals, real jsCode end to end"
        status: pass
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#a row with no enrichment signals carries them as explicit null, never a missing key"
        status: pass
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#Build Response stamps the contract even on the Skip terminal, which bypasses Decide Action entirely"
        status: pass
    human_judgment: false
  - id: D2
    description: "preingest.parse_outcome turns a response item into a typed Outcome, parsing a missing/unknown version or a missing match/candidate_count signal as unparseable rather than a good value"
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_outcome_contract.py::test_a_missing_outcome_contract_version_is_unparseable"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_outcome_contract.py::test_a_row_with_no_enrichment_signals_parses_as_present_with_explicit_nulls"
        status: pass
    human_judgment: false
  - id: D3
    description: "confidence.assess is a total decision table: only a strong-key match with no unadjudicated conflict is confident, an unadjudicated conflict holds regardless of tier, an adjudicated conflict clears the hold, and a vocabulary-drifted signal is held rather than defaulted confident"
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_confidence.py::test_a_high_tier_match_with_an_unadjudicated_conflict_is_held_not_confident"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_confidence.py::test_an_adjudicated_conflict_field_clears_the_hold_and_the_row_is_confident"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_confidence.py::test_a_vocabulary_drifted_tier_falls_to_the_terminal_held_row_not_a_confident_default"
        status: pass
    human_judgment: false
  - id: D4
    description: "A confidence-held row's resume fingerprint hashes only hold_code + match_tier + candidate_count (the signals a zero-credit free match pass can re-derive) and is identical across volatile per-run fields and across present/absent/different enrichment signals — the invariant that makes a resume a no-op for every held row"
    requirement: AFTER-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_fingerprint_is_identical_across_a_changed_timestamp_run_id_and_credit_balance"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_fingerprint_is_identical_whether_enrichment_signals_are_present_absent_or_different"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py::test_an_unadjudicated_conflict_held_row_resumed_against_an_unchanged_free_match_pass_is_excluded_with_zero_provider_calls"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py::test_every_match_stage_hold_code_stays_excluded_on_an_unchanged_resume"
        status: pass
    human_judgment: false
  - id: D5
    description: "The held queue's read path gives a four-way classification (absent/parseable/anomalous/another_run) from a probe over the file, while load() keeps degrading whole to empty on any anomaly rather than raising or partially trusting"
    requirement: AFTER-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_classify_read_on_malformed_json_is_anomalous"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_held_queue.py::test_load_still_degrades_whole_regardless_of_classify_reads_answer"
        status: pass
    human_judgment: false
  - id: D6
    description: "A batch containing an earlier failed chunk and an earlier held row still reaches and processes its final row; both non-completing rows land in the durable queue with reasons, driven through the real match_batch -> parse_outcome -> confidence.assess -> held_queue -> run_manifest sequence with only the transport injected"
    requirement: AFTER-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_batch_finishes_composition.py::test_a_batch_with_a_failed_chunk_and_a_held_row_still_reaches_and_dispatches_its_last_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py::test_no_new_or_orphaned_sequence_exists_in_the_live_corpus"
        status: pass
    human_judgment: false

duration: ~2h
completed: 2026-08-30
status: complete
---

# Phase 61 Plan 04: Confidence, Hold-Don't-Block, and a Sixth Verdict Word Summary

**A deterministic confidence table over signals the pipeline already produces, a durable held-rows queue with a per-hold-code resume fingerprint that never re-spends provider credit, and a batch that reaches its last row whatever any single row does — the concrete answer to Finding F's "no self-assessment of confidence, and therefore no autonomy."**

## Performance

- **Duration:** ~2h
- **Tasks:** 4
- **Files modified:** 16 (7 new files, 9 modified, 1 regenerated workflow JSON)

## Accomplishments

- **Task 1 — the outcome contract.** `Build Response` (the one node every enrichment-lane
  terminal reaches) now stamps `outcome_contract_version: 1` plus five named signals —
  match tier (the existing `match` field), `candidate_count`, `provider_agreement`,
  `material_conflicts`, `judge_adjudicated_fields` — normalizing absence to explicit
  `null` rather than a missing key. `Decide Action`'s own explicit return object was
  the real truncation point for `scored`/`material_conflicts`/`judge_confidence_by_field`
  (they died there before Build Response could ever see them) — fixed with a small,
  additive by-name carry, the same idiom this file already uses for
  `research_candidate`/`judge_verdict`. `preingest.parse_outcome` is the client-side
  parser, failing toward the hold on a missing/unknown version or a missing
  `match`/`candidate_count`. Verified end to end against the real committed jsCode
  (`tests/n8n/outcomeContractFlow.test.mjs`), including the Skip terminal that bypasses
  `Decide Action` entirely. Only `wf_enrichment_cloud.json` changed on regeneration.
- **Task 2 — the confidence table.** `confidence.py`'s `assess()` is a total,
  first-match-wins decision table: an unparseable outcome or an unadjudicated material
  conflict holds regardless of tier; only a strong-key auto-match (tier `high`) with no
  such conflict is confident; unknown/none/ambiguous-medium tiers each get a named
  `hold_code`; the terminal row holds a vocabulary-drifted signal rather than defaulting
  confident (REVIEW-A5). `agreedBy` (provider agreement) is documented and tested as
  corroboration that never rescues a held row and is never itself a hold (REVIEW-C8).
- **Task 3 — the held queue and the sixth verdict word.** `held_queue.py` is a fourth
  durable artifact: an entry separates `observed_signals` (what the review pass shows)
  from `resume_fingerprint` (what `rows_to_resume` compares) — the field cycle-3 review
  found collapsed. The fingerprint hashes only `hold_code` + `match_tier` +
  `candidate_count`, the two signals a zero-credit free match pass can re-derive, so an
  enrichment-stage hold (`HOLD_UNADJUDICATED_CONFLICT`) is never re-spent resuming to the
  identical hold. `classify_read()` gives the review pass a four-way answer
  (absent/parseable/anomalous/another_run) from a fresh file probe, while `load()` keeps
  degrading whole. `run_manifest.py` gained `confidence_held`, a sixth word distinct from
  `held`'s no-email resume rule; `rows_to_resume` widened with two keyword-only
  parameters (`held_entries`, `current_outcomes`, both defaulting to `None`) so every
  existing positional caller is unchanged. `run_manifest_path(run_id)` and
  `load_scoped()` add opt-in per-run scoping without touching `load()`'s existing
  bare-dict return.
- **Task 4 — wired into the run.** `enrich-before-ingest/SKILL.md` documents the real
  sequence (`held_queue.load`/`run_manifest.load`, then per row
  `preingest.parse_outcome` → `confidence.assess`, proceeding with no gate when
  confident or writing a held-queue entry then a `confidence_held` manifest verdict, in
  that order) and reuses step 3's `approve`/`deny`/`pick`/`email:` vocabulary for the
  single end-of-run review — no second decision vocabulary. `test_batch_finishes_composition.py`
  drives that exact sequence through `preingest.match_batch` with only the transport
  injected (a chunk that fails outright, an ambiguous medium-tier row, a strong-key
  auto-match) and asserts the run reaches and processes its final row, with both
  non-completing rows recorded in the durable queue with reasons. Registered in the
  sequence-inventory census with no grandfather entry.

## Task Commits

Each task was committed atomically (Tasks 1-3 are TDD: `test` then `feat`):

1. **Task 1 RED** - `f37d9d8` (test)
2. **Task 1 GREEN** - `5c1288a` (feat)
3. **Task 2 RED** - `10423cf` (test)
4. **Task 2 GREEN** - `c49dbf5` (feat)
5. **Task 3 RED** - `80e70af` (test)
6. **Task 3 GREEN** - `c3c1783` (feat)
7. **Task 4** - `ab8ac74` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `ENRICH_BUILD_RESPONSE` stamps the outcome
  contract; `ENRICH_DECIDE_CLOUD`'s return object carries `scored`/`material_conflicts`/
  `judge_confidence_by_field` forward by name
- `operator-claude-plugin/scripts/preingest.py` — `Outcome`, `UNPARSEABLE_OUTCOME`,
  `parse_outcome`
- `operator-claude-plugin/scripts/confidence.py` (new) — `assess()`, the closed
  `HOLD_*` vocabulary, `ENRICHMENT_STAGE_HOLD_CODES`, `ALL_HOLD_CODES`
- `operator-claude-plugin/scripts/held_queue.py` (new) — `fingerprint()`,
  `build_entry()`, `save()`, `load()`, `classify_read()`
- `operator-claude-plugin/scripts/run_manifest.py` — `CONFIDENCE_HELD`, widened
  `rows_to_resume`, `run_manifest_path()`, `ScopedLoadResult`/`load_scoped()`
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — the hold-don't-block
  subsection within step 5
- `tests/n8n/outcomeContractFlow.test.mjs`,
  `operator-claude-plugin/tests/test_outcome_contract.py`,
  `operator-claude-plugin/tests/test_confidence.py`,
  `operator-claude-plugin/tests/test_held_queue.py`,
  `operator-claude-plugin/tests/test_batch_finishes_composition.py` (all new)
- `operator-claude-plugin/tests/test_run_manifest.py` — sixth-word/fingerprint/
  `run_manifest_path`/`load_scoped` coverage, two pre-existing guard assertions updated
  to the new six-word/six-function reality
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — new sequence
  registered in `COVERED`
- `operator-claude-plugin/.claude-plugin/plugin.json`,
  `operator-claude-plugin/CHANGELOG.md` — 0.30.0 → 0.31.0
- `n8n/wf_enrichment_cloud.json` — regenerated (the only one of eight that changed)

## Decisions Made

- `run_manifest.load()` was kept byte-unchanged rather than widened to also return the
  stored `run_id` (as the plan's prose literally suggests) — a new function,
  `load_scoped()`, carries that behavior instead, since widening `load()`'s return shape
  would have broken every existing caller/test asserting `load(path=...) == verdicts`
  and the stated consumer (61-05) does not yet exist to require the wider shape.
- `held_queue.py` is one global file, not per-run like `written_records.py` — "held rows
  collect into ONE review queue, cleared in a single pass" (D-61-07) reads as a durable
  backlog across runs, not a per-run artifact.
- `candidate_count` is read once, at the Build Response projection point, from
  `match.candidates.length` — never re-derived a second way client-side — and is
  meaningful for tier `medium` only; other tiers already encode their own cardinality in
  the tier itself.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `Decide Action`'s own return object was truncating the enrichment
signals before Build Response could read them**
- **Found during:** Task 1's own flow test
- **Issue:** `ENRICH_DECIDE_CLOUD` builds an explicit `{action, object_type,
  hs_object_id, gap_flag, needs_review, row_id, mode, match, properties}` return object
  — `scored`, `material_conflicts`, and `judge_confidence_by_field` were silently
  dropped there, so a row that went through real enrichment would have reached Build
  Response with those signals already gone, contrary to Task 1's own must-have.
- **Fix:** Added the three fields to `Decide Action`'s return, by name, mirroring this
  file's own existing paired-carry idiom for `research_candidate`/`judge_verdict`.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `node --test tests/n8n/outcomeContractFlow.test.mjs` (the first
  test, which exercises a row with real `scored`/`judge_confidence_by_field`, failed
  before this fix and passed after).
- **Committed in:** `5c1288a` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] The SKILL.md addition tripped the ICP/tier ban across skill bodies**
- **Found during:** Task 4's own full-suite verification run
- **Issue:** `test_report_enrichment.py`'s
  `test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder` bans
  the literal substring `"tier"` anywhere in an operator-facing skill body (this plugin
  must never surface an ICP tier concept) — my prose used "medium-tier proposal" to
  describe an ordinary ambiguous multi-candidate match, an unrelated MATCH concept, and
  collided textually.
- **Fix:** Reworded to "ambiguous, multi-candidate proposal" — no loss of meaning, zero
  occurrences of "tier"/"icp" remain in the file.
- **Files modified:** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`
- **Verification:** `.venv/bin/python -m pytest -q` — full suite green (3481/154).
- **Committed in:** `ab8ac74` (Task 4 commit)

**3. [Rule 2 - Missing critical] `test_run_manifest.py`'s two frozen-shape guard tests
needed updating for the sixth word and the two new public functions**
- **Found during:** Task 3
- **Issue:** `test_allowed_verdicts_holds_five_words_including_unanswered`'s
  `len(...) == 5` assertion and `test_the_module_exposes_no_fourth_verb`'s exact public-
  API set both pin literals the plan's own Task 3 explicitly widens (a sixth verdict
  word; `run_manifest_path`/`load_scoped`).
- **Fix:** Dropped the now-stale count assertion (the six-word coverage lives in a new,
  dedicated test); widened the public-API set to the six actual public names.
- **Files modified:** `operator-claude-plugin/tests/test_run_manifest.py`
- **Verification:** `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_manifest.py -q` — 83/0 green (with `test_held_queue.py` run alongside).
- **Committed in:** `c3c1783` (Task 3 GREEN commit)

---

**Total deviations:** 3 auto-fixed (2 bug/Rule 1, 1 missing-critical/Rule 2) — all direct,
disclosed consequences of the plan's own stated changes; none introduce scope beyond what
the plan already required. `git diff 3adca9f..HEAD -- operator-claude-plugin/tests
tests/n8n | grep -E '^-.*assert '` shows exactly the two lines named in deviation 3 removed
— both explicitly superseded by stronger, wider assertions the plan's own Task 3 requires,
never weakened or deleted without replacement.
**Impact on plan:** No scope creep.

## Issues Encountered

- The plan's own draft python snippet for the hold-don't-block step referenced
  `outcome.responses` (one raw body per chunk) where the skill's real flow already has
  an already-flattened `responses` list built two lines earlier for `merge_enriched` —
  written against the flattened list instead, matching this file's own repeated
  "flatten before merging" lesson (FINDING 2, `53-WALK-RECORD.md`) rather than
  reproducing it.

## User Setup Required

None — no external service configuration required. This plan is entirely offline: a
builder edit + regeneration, four new/widened Python modules, prose documentation, and
tests. Zero live n8n, HubSpot, Anthropic, or provider calls; zero arming.

## Next Phase Readiness

- Requirements `RUN-02` and `AFTER-02` are addressed by this plan's mechanism —
  `confidence.py` + `held_queue.py` + `run_manifest.py`'s sixth word — though the
  end-of-run REVIEW PASS itself (rendering the held queue as a numbered table and
  applying approve/deny/pick decisions against it) is documented in prose but not built
  as new code here; Task 4's own scope was the match/confidence/held-queue/manifest
  composition, not a new review-UI implementation.
- 61-01's run-state/progress substrate decision remains open and un-preempted — this
  plan's held queue is deliberately substrate-independent of it (HIGH-9's disposition).
- Not yet done: a live proof that a real batch run, driven end to end against the live
  n8n instance, actually produces held-queue entries an operator can review. This plan's
  own `<verification>` was offline-only.

## Self-Check: PASSED

All 16 claimed files verified present on disk; all 7 task commit hashes (`f37d9d8`,
`5c1288a`, `10423cf`, `c49dbf5`, `80e70af`, `c3c1783`, `ab8ac74`) verified present in
`git log --oneline --all`.

---
*Phase: 61-autonomous-batch-runs*
*Completed: 2026-08-30*
