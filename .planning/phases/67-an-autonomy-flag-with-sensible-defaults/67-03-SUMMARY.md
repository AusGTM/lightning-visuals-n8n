---
phase: 67-an-autonomy-flag-with-sensible-defaults
plan: 03
subsystem: operator-plugin-skills
tags: [autonomy, run_report, record_audit, auto-06, d-67-06, d-67-11, d-67-13, review-57-l5]

# Dependency graph
requires:
  - phase: 67-an-autonomy-flag-with-sensible-defaults
    provides: "67-01's config_gate.autonomy_enabled and 67-02's autonomy read at each
      batch skill's ask-or-proceed switch — this plan builds the end-of-run account
      those rounds now proceed into unattended"
provides:
  - "contact-upload/SKILL.md: a caller-minted run_id (run_state.new_run_id(), before
    the ceiling branch), two run_report.record_audit observations (ceiling+balances
    before the would_be check; disarm in the finally), and one
    run_report.build_run_report call at the end of step 7"
  - "suggest-contacts/SKILL.md: one run_report.build_run_report call at the end of
    step 9, sourced from step 8's reused enrich-before-ingest step-5 dispatch block —
    never a second run_id"
  - "corrected paragraphs at enrich-before-ingest/SKILL.md and enrich-records/SKILL.md:
    contact-upload is no longer claimed 'deliberately NOT a call site' (REVIEW-57-L5
    retired)"
  - "operator-claude-plugin/tests/test_mandatory_report_call_sites.py — the pinned
    call-site contract, plus idempotence and gap-honesty proofs of
    run_report.build_run_report itself"
affects: [67-04]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 8684
  tasks: 3
  commits: 5
  plan_head_before: 54052c9909bd8dc01c5443509150c64067ea4217

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mint-then-pass idiom for a single-shot dispatch: run_state.new_run_id() before
      the branch that decides whether to dispatch at all, then run_id=run_id into
      dispatch.dispatch(...) so dispatch.py's own run_id=None fallback never mints a
      second handle — mirrors enrich-before-ingest's REVIEW-C14 idiom, applied for the
      first time to a single dispatch.dispatch() call rather than a chunked
      chunking.dispatch_plan()."
    - "Reportless branch states its own absence in prose (D-67-13/D-67-07): a branch
      that stops before any dispatch names, in words, why it makes no report call and
      what its account actually is (an audit record, a remainder-queue entry, or a
      per-company line) — never a silent no-op."
    - "RED-by-negation for a pre-existing, unedited production contract: when the
      property under test already holds in code the plan does not touch (run_report.py
      is prohibited from edits), RED is produced by asserting the NEGATION once,
      observing that assertion fail (because the real property holds), then restoring
      — proves the test itself is load-bearing without requiring new production code."

key-files:
  created:
    - operator-claude-plugin/tests/test_mandatory_report_call_sites.py
  modified:
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "contact-upload's build_run_report call sits at the END of step 7 (after the
    existing build_contact_report per-record report and its run-handle paragraph),
    never replacing it — two reports coexist on purpose: step 7's is what the operator
    reads DURING a send they are watching; the new one is the account for a send
    nobody watched."
  - "suggest-contacts sources run_id/outcome/disarm from step 8's REUSED
    enrich-before-ingest step-5 dispatch block rather than minting its own — the plan's
    own load-bearing property (never a second dispatch path, never a second run_id)."
  - "The pre-call ceiling-breach branch (contact-upload) and the empty-round case
    (suggest-contacts) each get a stated, in-prose reason for making NO report call,
    rather than a silent absence — both cite the branch's actual account (an audit
    record + remainder-queue entry, or the round's own per-company lines)."
  - "Task 3's two behavioural tests were proved RED by deliberate negation, not by a
    new implementation: run_report.build_run_report's idempotence and gap-honesty
    already held in the unedited scripts/run_report.py (which this plan is prohibited
    from touching), so RED was produced by asserting the negation of each property
    once, observing that negated assertion itself fail, then restoring the correct
    assertion for GREEN."

requirements-completed: [AUTO-06]

coverage:
  - id: D1
    description: "contact-upload/SKILL.md mints its own run_id before the ceiling
      branch, records the ceiling verdict and grant balances the moment they are
      observed and the disarm result at close, and renders one end-of-run report at
      the end of step 7 from that same run_id"
    requirement: AUTO-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_contact_upload_mints_run_id_once_before_the_would_be_check"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_contact_upload_first_audit_call_runs_before_the_would_be_check_and_carries_ceiling_and_balances"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_contact_upload_second_audit_call_runs_in_the_finally_and_carries_disarm"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_build_run_report_call_args"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pre-call ceiling-breach branch states, in prose, that it makes no
      report call and why (D-67-13) — its audit record, remainder-queue entry, and the
      stated stop are its whole account"
    requirement: AUTO-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_contact_upload_ceiling_breach_branch_states_it_has_no_report_call"
        status: pass
    human_judgment: false
  - id: D3
    description: "suggest-contacts/SKILL.md renders one end-of-run report at the end of
      step 9, sourced from step 8's reused dispatch block, states the empty-round case
      and the revocation bound (D-67-07), and adds no step and no second run handle"
    requirement: AUTO-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_suggest_contacts_run_id_is_sourced_not_minted"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_suggest_contacts_states_the_empty_round_case"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_suggest_contacts_states_the_revocation_bound"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts_composition.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "enrich-before-ingest/SKILL.md and enrich-records/SKILL.md no longer
      claim contact-upload is deliberately excluded from the report (REVIEW-57-L5
      retired); each states the corrected reason (AUTO-06, D-67-11)"
    requirement: AUTO-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_analog_no_longer_claims_contact_upload_is_deliberately_excluded"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_analog_states_the_corrected_reason"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "review-triage and backend-control gain no report call — a checked,
      recorded exclusion (D-67-11, D-67-12), not an omission; run_report.build_run_report
      is idempotent for the same run_id and never raises when every durable store it
      joins is unreadable"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_review_triage_and_backend_control_carry_no_report_call"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_build_run_report_is_idempotent_for_the_same_run_id"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py#test_build_run_report_never_raises_when_every_store_is_unreadable"
        status: pass
    human_judgment: false
  - id: D6
    description: "No plugin script edited (run_report.py, write_grant.py,
      scheduled_arm.py, n8n_arming.py byte-identical to 238d1ab); zero n8n/ diff; the
      sequence-coverage ratchet stayed at MAX_GRANDFATHERED = 0; full plugin suite and
      node harness green"
    verification:
      - kind: other
        ref: "git diff --quiet 238d1ab -- operator-claude-plugin/scripts/scheduled_arm.py operator-claude-plugin/scripts/n8n_arming.py operator-claude-plugin/scripts/write_grant.py operator-claude-plugin/scripts/run_report.py"
        status: pass
      - kind: other
        ref: "git status --porcelain -- n8n/ scripts/build_cloud_workflows.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests/ -q (2747 passed / 5 skipped)"
        status: pass
      - kind: other
        ref: "node --test tests/n8n/*.test.mjs (940 passed)"
        status: pass
    human_judgment: false

# Metrics
duration: ~35min
completed: 2026-09-07
status: complete
---

# Phase 67 Plan 03: An autonomy flag with sensible defaults — the mandatory end-of-run report reaches contact-upload and suggest-contacts Summary

**contact-upload and suggest-contacts now build the same `run_report.build_run_report`
end-of-run account enrich-before-ingest and enrich-records already did, with the two
analog skills' "contact-upload is deliberately NOT a call site" paragraph (REVIEW-57-L5)
retired and rewritten to explain why autonomy breaks that premise.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-09-07 (immediately after 67-02)
- **Completed:** 2026-09-07
- **Tasks:** 3 (Task 1 tracer + Task 2 auto + Task 3 auto, all TDD RED-then-GREEN)
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments
- Task 1 (tracer, TDD): `contact-upload/SKILL.md` step 6 mints `run_id` via
  `run_state.new_run_id()` before the ceiling branch, passes it into
  `dispatch.dispatch(..., run_id=run_id)`, and records two
  `run_report.record_audit` observations (ceiling+balances before the `would_be`
  check; disarm in the `finally`, after `record_dispatch_outcome`) — both wrapped
  against `RunReportError`. The pre-call ceiling-breach branch states, in prose, why
  it makes no report call (D-67-13). Step 7 gains one `run_report.build_run_report`
  fence after the existing per-record report. Both analog skills' retired paragraph is
  rewritten. `test_skill_sequence_coverage.py`'s `COVERED` entry for contact-upload
  grows in the same commit. Tracer feedback gate: auto-mode active, `<verify>`
  re-run and passed — proceeded straight to Task 2 with no checkpoint.
- Task 2 (auto, TDD): `suggest-contacts/SKILL.md` step 9 gains one
  `run_report.build_run_report` fence, sourced from step 8's reused
  `enrich-before-ingest` step-5 dispatch block (never a second `run_id`), states the
  empty-round case and the D-67-07 revocation bound. `test_mandatory_report_call_sites.py`
  widened to a two-entry `TABLE` with parametrized shared assertions plus two
  structural assertions (table size, review-triage/backend-control absence).
- Task 3 (auto, TDD): two behavioural tests drive `run_report.build_run_report`
  directly, proving idempotence (two calls, same `run_id`, equal blocks, neither
  raising) and gap-honesty (every durable store made unreadable still returns a block
  naming every gap, never raising). RED proved by deliberate negation since
  `run_report.py` is prohibited from edits — no new production code needed. Module
  docstring finalized as the artifact of record for D-67-11's scope decision.

## Task Commits

Each task followed RED-then-GREEN (Task 1's RED/GREEN split across two commits per
the plan's own instruction; Task 3 needed only a test commit since production code was
unchanged):

1. **Task 1 RED** — `31264dd` (test) — 15 failed / 5 passed against the unedited
   `contact-upload/SKILL.md` and analog skills; every failure an assertion on the
   planned behavior (missing call sites, retired paragraph still present).
2. **Task 1 GREEN** — `86893e1` (feat) — the `contact-upload`/analog edits and the
   `COVERED` registry update land together; full plugin suite 2732 passed / 5 skipped
   (was 2712/5); `node --test` 940/940 unchanged.
3. **Task 2 RED** — `997a82b` (test) — `TABLE` widened to `suggest-contacts`; 7 failed
   / 26 passed against the unedited `suggest-contacts/SKILL.md`.
4. **Task 2 GREEN** — `bd614dd` (feat) — the `suggest-contacts` edit lands; full
   plugin suite 2745 passed / 5 skipped; `node --test` 940/940 unchanged.
5. **Task 3** — `49c542f` (test) — the two behavioural tests and the finalized module
   docstring; 35 passed in the file (>= 8 required). RED proved by negating each
   assertion once (observed failure), then restoring — see Deviations below for why
   this task produced no GREEN production commit.

No REFACTOR commit at any task — every GREEN implementation was the plan's own
specified minimal edit; nothing to clean up without changing wording the plan pins.

## Files Created/Modified
- `operator-claude-plugin/tests/test_mandatory_report_call_sites.py` (new) — the
  two-entry `TABLE` (`contact-upload`, `suggest-contacts`), parametrized shared
  assertions, per-skill assertions, the two analog-paragraph assertions, two
  structural assertions, and two behavioural tests against
  `run_report.build_run_report` directly
- `operator-claude-plugin/skills/contact-upload/SKILL.md` — step 6: `run_id` mint,
  `balances_at_grant` binding, first `record_audit` call, ceiling-breach-branch
  reportless prose, `run_id=run_id` on `dispatch.dispatch`, second `record_audit`
  call in the `finally`; step 7: the new `build_run_report` fence
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — the corrected
  paragraph (REVIEW-57-L5 retired)
- `operator-claude-plugin/skills/enrich-records/SKILL.md` — the same corrected
  paragraph
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — step 9: the new
  `build_run_report` fence, the empty-round sentence, the revocation-bound sentence
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — contact-upload's
  `COVERED` tuple grows `run_state.new_run_id` and two `run_report.record_audit`
  calls; `MAX_GRANDFATHERED` stays 0

## Decisions Made

See `key-decisions` in the frontmatter above — the mint-then-pass idiom for a
single-shot dispatch, the reportless-branch-states-its-own-absence pattern, and the
RED-by-negation technique used in Task 3 (production code unchanged, run_report.py
prohibited from edits by the plan's own `<prohibitions>`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_normalized()` does not strip backticks, so the ceiling-breach
prose assertion needed the literal backtick-quoted form**
- **Found during:** Task 1, first pytest run of the new GREEN test file
- **Issue:** `test_contact_upload_ceiling_breach_branch_states_it_has_no_report_call`
  asserted `"stops before dispatch.dispatch is ever called"` (no backticks) against
  `_normalized()` output, which collapses whitespace and strips `*`/blockquote markers
  but leaves backticks intact — the actual prose reads `` stops before `dispatch.dispatch`
  is ever called ``, so the assertion failed against my own correct implementation.
- **Fix:** corrected the test's expected string to include the backticks, matching
  `_normalized()`'s actual (documented) behavior.
- **Files modified:** `operator-claude-plugin/tests/test_mandatory_report_call_sites.py`
- **Verification:** re-ran the file; all 20 tests passed
- **Committed in:** `31264dd` (the assertion was corrected before the RED commit, so
  RED itself reflects only the intended failures, not this authoring slip)

---

**Total deviations:** 1 auto-fixed (1 bug, caught before any commit — never shipped).
**Impact on plan:** None — the fix was made during test authoring, before RED was
captured, so no commit ever carried the incorrect assertion.

## Known Stubs

None.

## Threat Flags

None beyond what the plan's own `<threat_model>` already names (T-67-11 through
T-67-15, T-67-SC) — no new surface introduced outside the four skill bodies and the
one test file.

## Issues Encountered

None beyond the deviation above, which was caught and corrected during test authoring
before it ever reached a commit.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

67-04 (the `backend-control/SKILL.md` D-68-04 reversal record) is unblocked. Full
plugin suite green (2747 passed / 5 skipped, up from 2712/5 at 67-02's close) and the
n8n harness green (940 passed, unchanged); `operator-claude-plugin/scripts/` diffs to
exactly `config_gate.py` since `238d1ab` — zero-`n8n/`-diff and
byte-identical-arming-scripts invariants both hold. All four batch skills
(`enrich-before-ingest`, `enrich-records`, `contact-upload`, `suggest-contacts`) now
build the mandatory end-of-run report; `review-triage` and `backend-control` remain
excluded, checked by test rather than assumed.

---
*Phase: 67-an-autonomy-flag-with-sensible-defaults*
*Completed: 2026-09-07*

## Self-Check: PASSED

All key-files (created + modified) confirmed present on disk via `[ -f ]`; all five
task commit hashes (`31264dd`, `86893e1`, `997a82b`, `bd614dd`, `49c542f`) confirmed
present via `git log --oneline --all`.
