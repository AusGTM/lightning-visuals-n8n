---
phase: 65-round-empty-re-entry-keyed-on-the-cause
verified: 2026-09-07T01:15:00Z
status: passed
score: 38/38 must-haves verified
covered_files: [".planning/REQUIREMENTS.md", ".planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-01-PLAN.md", ".planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-01-SUMMARY.md", ".planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-02-PLAN.md", ".planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-02-SUMMARY.md", ".planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-REVIEW.md", ".planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-REVIEW-FIX.md", ".planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md", "operator-claude-plugin/config/field_policy.yaml", "operator-claude-plugin/scripts/preingest.py", "operator-claude-plugin/scripts/suggest_contacts.py", "operator-claude-plugin/skills/enrich-before-ingest/SKILL.md", "operator-claude-plugin/skills/suggest-contacts/SKILL.md", "operator-claude-plugin/tests/test_preingest_merge.py", "operator-claude-plugin/tests/test_skill_sequence_coverage.py", "operator-claude-plugin/tests/test_suggest_contacts.py", "operator-claude-plugin/tests/test_suggest_contacts_composition.py"]
covered_digest: "v1:sha256:9164124922aafca543953ac10d981bbca717e25109417659a0a5df46148bbe23"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 38/38
  gaps_closed:
    - "CR-01 (post-review defect, not part of the original 38 must-haves): an all-companies-empty round no longer crashes with an uncaught preingest.RowSpecError before any cause is reported"
  gaps_remaining: []
  regressions: []
---

# Phase 65: Round-empty re-entry, keyed on the cause — Verification Report (Re-verification)

**Phase Goal:** a round that ends with nothing usable does not stop because an intermediate
stage reported success.
**Verified:** 2026-09-07T01:15:00Z
**Status:** passed
**Re-verification:** Yes — after code-review fix CR-01 (commit `67d3f1a`)

## What Changed Since the Previous Verification

The previous verification (2026-09-07T00:46:42Z, 38/38 passed) preceded a code review
(`65-REVIEW.md`) that found one critical defect, CR-01: the documented per-batch pipeline in
`operator-claude-plugin/skills/suggest-contacts/SKILL.md` called
`suggest_contacts.mint_row_ids(records)` unconditionally on the whole batch's accumulated
`records`. When every company in a round finds nobody (an empty page walk AND an ineligible or
unsuccessful search fallback for every company — including the ordinary one-company invocation),
`records` stays `[]`, and `mint_row_ids([]) -> preingest.build_rows_spec([])` raises
`preingest.RowSpecError` by design. This crash happened *before* the terminal classify loop that
Phase 65 Task 2 built to name each company's cause, and the earlier per-company *routing* call's
own already-computed outcome was discarded (never written onto the `rounds.append({...})` dict).
The net effect: the exact scenario `round_outcome` exists to explain (`CAUSE_NO_PEOPLE_FOUND`,
listed first in `ROUND_CAUSES`) produced an unhandled crash instead of a reported cause — a
regression against the phase's own goal.

Fix commit `67d3f1a` (`fix(65): CR-01 keep the routing-call outcome and guard the empty-batch
mint`) applied both of the review's compatible options in `SKILL.md`'s documented pipeline only:

1. Each `rounds.append({...})` entry now carries `"outcome": outcome` — the routing call's own
   result — from the moment it is built, so a company's cause survives even if the terminal
   classify loop is never reached.
2. The whole mint/dispatch/terminal-classify block (`mint_row_ids` through
   `extraction.validate`) is now guarded on `if records:`, so an all-companies-empty batch never
   calls `mint_row_ids([])` at all.

The fix touched exactly two files: `operator-claude-plugin/skills/suggest-contacts/SKILL.md`
(58 insertions, 38 deletions — structural re-indent plus the two changes above, no new call
targets) and `operator-claude-plugin/tests/test_suggest_contacts_composition.py` (one new test,
90 lines added). `git show 67d3f1a --stat` confirms no other file was touched — in particular
neither `suggest_contacts.py` nor `preingest.py` (where `round_outcome` and `mint_row_ids`/
`build_rows_spec` themselves live) changed at all in this commit.

## Re-verification of the Fix

| Check | Command / Evidence | Result |
|---|---|---|
| Fix commit exists and matches the review-fix's own description | `git show 67d3f1a --stat` | 2 files changed: `SKILL.md` (+58/-38), `test_suggest_contacts_composition.py` (+90) |
| `rounds.append({...})` now carries the routing call's `outcome` | direct read of `SKILL.md` diff | `"outcome": outcome,` present at the append site, with an explanatory comment naming CR-01 |
| Mint/dispatch/terminal-classify block guarded on `if records:` | direct read of `SKILL.md` diff | `if records:` wraps `mint_row_ids` through the `extraction.validate` loop; comment names CR-01 and explains why an empty batch never reaches it |
| Two `round_outcome` call sites still present (routing + terminal) | `grep -n "round_outcome(" .../suggest-contacts/SKILL.md` | lines 424 and 508 — still exactly two |
| New composition test exists and passes | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py -k never_crashes_when_every_company_finds_nobody -v` | 1 passed — drives two companies, both `people: []`, both ladders `refused`; asserts no `RowSpecError`, `records == []`, and both `rounds[]` entries carry `cause == CAUSE_NO_PEOPLE_FOUND` / `reentry == REENTRY_SEARCH_FALLBACK` |
| Pre-existing sibling test (duplicate-row-id `RowSpecError` branch) unaffected | `pytest -k test_mint_row_ids_propagates_row_spec_error_for_a_row_that_already_has_one` | 1 passed |
| Full composition file green | `pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py -q` | 15 passed |
| `test_skill_sequence_coverage.py` unmodified by the fix, still green | `git show 67d3f1a --stat` (file absent from the fix's changed-file list); `pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` | 11 passed; `round_outcome` still named exactly twice in the suggest-contacts tuple (lines 398, 405) — the AST-based sequence parser records every call regardless of the enclosing `if`, so wrapping the block changed nothing about the recorded tuple |
| Full plugin suite | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | **2565 passed, 5 skipped** (was 2564/5 before the fix — count grew by exactly the one new test, matching `65-REVIEW-FIX.md`'s own claim) |
| No `while` loop introduced anywhere in plugin scripts (D-65-13/LADDER-04) | AST walk over every `operator-claude-plugin/scripts/*.py` | only pre-existing `watch.py:306,467` (both untouched by this phase — `git diff --stat becba5747..HEAD -- .../watch.py` empty) |
| No debt markers introduced by the fix | `git show 67d3f1a \| grep -nE "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` | no match |
| Cap/budget logic untouched by the fix | `git show 67d3f1a -- SKILL.md \| grep -iE "cap\|budget"` | no match — the fix is purely a persistence/guard change, no cap semantics touched |
| `search_fallback.py`, `confidence.py`, `n8n/` still untouched since phase start | `git diff --stat becba5747..HEAD -- <those paths>` | empty for all |
| `suggest_contacts.py`/`preingest.py` untouched by the fix commit itself | `git show 67d3f1a --stat` | absent from the changed-file list — `round_outcome`'s purity (no I/O, no module-level mutable state) and `merge_enriched`'s allowlist logic are unchanged from the previously-verified state |
| REQUIREMENTS.md checkbox states unchanged | `sed -n '40,50p' .planning/REQUIREMENTS.md` | LADDER-03 `[x]`, LADDER-04 `[x]`, LADDER-05 `[ ]` (deliberate disposition, unchanged), RICH-04 `[x]` |

**Conclusion on CR-01:** the fix closes the defect as described. The all-companies-empty round
(the phase's own worst case, and an ordinary single-company invocation that finds nobody) now
completes without raising, and every company's line carries a `CAUSE_NO_PEOPLE_FOUND` /
`REENTRY_SEARCH_FALLBACK` outcome instead of crashing before any cause is ever reported. This
was not one of the original 38 must-haves (it is a review-found regression in the *composition*
of already-verified pieces, not a failure of any individual must-have's own truth), so it does
not change the 38/38 score — but it directly restores the phase goal ("a round that ends with
nothing usable does not stop because an intermediate stage reported success") for the specific
path the review found broken.

## Goal Achievement (Re-checked)

Every one of the 38 must-have truths from the initial verification was re-checked against
current file content (not copied). All 38 still hold; none regressed as a side effect of the
CR-01 fix.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-65-01: `round_outcome` is the ONE place a cause is named; SKILL.md consults it, no prose cause of its own | ✓ VERIFIED | `suggest_contacts.py` defines `round_outcome`; `grep -c "if not people"` on SKILL.md = 0; two call sites (lines 424, 508 post-fix) both read `outcome["cause"]`/`outcome["reentry"]` |
| 2 | D-65-02: fixed precedence unknown>no_people_found>none_classified>all_held_on_email>people_thin>proposed | ✓ VERIFIED | `ROUND_CAUSES` tuple unchanged (file untouched by fix); `test_round_outcome_precedence_is_fixed_when_causes_mix` passes |
| 3 | D-65-03: unreadable input -> unknown/none/named reason, never raises | ✓ VERIFIED | `suggest_contacts.py` unchanged by fix; malformed-input tests pass |
| 4 | D-65-04/LADDER-05: `no_people_found` is the ONLY cause with `reentry: search_fallback`, routes through unmodified `eligible_after_ladder` | ✓ VERIFIED | `git diff --stat becba5747..HEAD -- .../search_fallback.py` empty; new composition test drives real `eligible_after_ladder` and asserts the routing |
| 5 | D-65-05: below-bar selected -> `people_thin`/`reentry: none` | ✓ VERIFIED | unchanged; test passes |
| 6 | D-65-06: zero selected -> `none_classified`, breakdown separates drop reasons | ✓ VERIFIED | unchanged; test passes |
| 7 | D-65-07: zero sendable + >=1 held -> `all_held_on_email` | ✓ VERIFIED | unchanged; test passes |
| 8 | D-65-08/LADDER-04: exactly two straight-line call sites; any of rows/sendable/held/fallback -> `reentry: none` | ✓ VERIFIED | SKILL.md:424 (routing) and :508 (terminal, post-fix line numbers); sequence-coverage tuple still names `round_outcome` exactly twice |
| 9 | D-65-09: no `round_empty` boolean, no unconditional retry, `reentry` is `search_fallback` for exactly one of six | ✓ VERIFIED | `grep -n round_empty` = 0 matches; `ROUND_REENTRIES` unchanged |
| 10 | D-65-10/SAFE-02: refused ladder never reaches `rank_results`, classifier duplicates no refusal check | ✓ VERIFIED | `round_outcome` body unchanged by fix; refusal test passes |
| 11 | D-65-11/SAFE-03: SAME `attempts` threaded; `company_budget` never decreases across second pass | ✓ VERIFIED | budget test passes; fix touches no budget logic |
| 12 | D-65-12: `cap_exhausted` never produces `reentry: search_fallback` | ✓ VERIFIED | precedence logic unchanged by fix |
| 13 | D-65-13/LADDER-04: no plugin script contains `while` | ✓ VERIFIED | AST walk confirms only pre-existing untouched `watch.py` |
| 14-19 | LADDER-03 boundary/empty/encoding/precision/idempotency/concurrency | ✓ VERIFIED | `suggest_contacts.py` unmodified by the fix; all cited tests re-run, pass |
| 20 | LADDER-04 adjacency: two call sites, no loop between, sequence tuple names `round_outcome` exactly twice | ✓ VERIFIED | confirmed post-fix at lines 424/508; `test_skill_sequence_coverage.py` (unmodified by the fix commit) passes, 11 passed |
| 21 | LADDER-04 empty: no page fetched -> routing call returns no_people_found, `eligible_after_ladder([])` refuses | ✓ VERIFIED | new composition test drives this exact path for real and asserts it |
| 22 | LADDER-04 ordering: routing precedes fallback eligibility check; terminal precedes `extraction.validate`; `round_artifact` sink | ✓ VERIFIED | order preserved post-fix — the `if records:` guard wraps a contiguous suffix of the block, it does not reorder any call |
| 23 | LADDER-05 boundary: `walk['people']==[]` exact and only trigger | ✓ VERIFIED | unchanged in `suggest_contacts.py` |
| 24 | LADDER-05 precision (backstop): fallback's own budget integer, `round_outcome` computes no budget constant | ✓ VERIFIED | unchanged; test passes |
| 25 | LADDER-05 disposition (backstop, orchestrator ruling 2, Option A) | ✓ VERIFIED (disposition confirmed) | `.planning/REQUIREMENTS.md` line 47 still `[ ]`; LADDER-03/04/RICH-04 still `[x]` — the required disposition is unchanged by the fix |
| 26-38 | RICH-04 family: allowlist union, boundary, adjacency, empty, ordering, precision, idempotency, concurrency, SAFE-01 pin, strip_enrichment_extras, held/remainder path, both callers traced, jobtitle-todo not built | ✓ VERIFIED (all 13) | `preingest.py` and `field_policy.yaml` untouched by the CR-01 fix commit (`git show 67d3f1a --stat` — neither file listed); `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -q` re-run, all pass; pending todo file still present with no `resolves_phase` key |

**Score:** 38/38 truths verified (0 present-but-behavior-unverified) — unchanged from the
initial verification. CR-01's fix is tracked separately above as the re-verification's specific
subject, not folded into or double-counted against this score.

### Required Artifacts (Re-checked)

All ten artifacts from the initial verification were re-checked; all still VERIFIED. The two
artifacts the fix touched:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` | step 7 routes on `outcome["reentry"]`, step 9 reads `outcome`; CR-01: mint/dispatch/terminal-classify guarded on `if records:`, routing outcome persisted | ✓ VERIFIED | both CR-01 changes present and correctly placed; no `if not people` cause decision reintroduced; step 9 still reads `entry["outcome"]` |
| `operator-claude-plugin/tests/test_suggest_contacts_composition.py` | extended pipeline test + 4 new composition tests (initial) + 1 CR-01 regression test | ✓ VERIFIED | 15 tests total (was 14), all pass |

The remaining eight artifacts (`suggest_contacts.py`, `test_suggest_contacts.py`,
`test_skill_sequence_coverage.py`, `preingest.py`, `field_policy.yaml`,
`enrich-before-ingest/SKILL.md`, `test_preingest_merge.py`, the pending todo) are untouched by
the CR-01 fix commit and were re-confirmed present/substantive/wired by direct inspection —
unchanged from the initial verification's findings.

### Key Link Verification (Re-checked)

All eight key links from the initial verification re-checked; all still WIRED. The routing-call
link gained one property: the routing call's `outcome` now also flows directly onto the
`rounds[]` entry (not only used transiently to decide the fallback branch) — confirmed by direct
read of the `rounds.append({...})` diff.

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `walk_pages` return | `round_outcome(walk)` routing call | direct call, SKILL.md:424 | ✓ WIRED | confirmed post-fix |
| routing `round_outcome` result | `rounds[]` entry's `"outcome"` key (NEW since CR-01) | `rounds.append({..., "outcome": outcome})` | ✓ WIRED | confirmed by diff read; this is the link CR-01 added |
| routing `round_outcome` | `search_fallback.eligible_after_ladder(attempts)` | `outcome["reentry"]` guard | ✓ WIRED | unchanged |
| `partition_for_dispatch` + `hold_weak_sources` (sendable, held) | terminal `round_outcome(...)` (now inside `if records:`) | SKILL.md terminal loop | ✓ WIRED | guard does not break the link — it only skips the whole sub-block when there is nothing to mint |
| `select_people` fallback return | `fallback=` terminal call | `fallback_selection` name | ✓ WIRED | unchanged |
| `config/field_policy.yaml` `contacts:` | `preingest.promotable_contact_props()` | YAML read | ✓ WIRED | unchanged, file untouched by fix |
| `merge_enriched` merged rows | dispatch chain to `write_dispatch_csv` | SKILL.md step 7 | ✓ WIRED | unchanged, file untouched by fix |
| `merge_enriched` merged rows | `rejoin_enriched` -> `partition_for_dispatch` -> `extraction.validate` | suggest-contacts step 7/8 | ✓ WIRED | unchanged |

### Behavioral Spot-Checks (Re-run)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full plugin suite green, count matches fix's own claim | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | `2565 passed, 5 skipped` | ✓ PASS |
| CR-01 regression test passes | `pytest .../test_suggest_contacts_composition.py -k never_crashes_when_every_company_finds_nobody -v` | 1 passed | ✓ PASS |
| No-`while` guard | `pytest .../test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status -q` | 1 passed | ✓ PASS |
| Sequence-coverage ratchet still green | `pytest .../test_skill_sequence_coverage.py -q` | 11 passed | ✓ PASS |
| `round_outcome` still named exactly twice in SKILL.md | `grep -n "round_outcome(" .../suggest-contacts/SKILL.md` | lines 424, 508 | ✓ PASS |
| `preingest.py`/`config/field_policy.yaml` test suite still green (untouched by fix) | `pytest .../test_preingest_merge.py -q` | all pass | ✓ PASS |
| `search_fallback.py`/`confidence.py`/n8n untouched since phase baseline | `git diff --stat becba5747..HEAD -- <paths>` | empty | ✓ PASS |
| No debt marker introduced by the fix commit | `git show 67d3f1a \| grep -nE "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` | no match | ✓ PASS |

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` files exist for this plugin (unchanged from
initial verification).

### Requirements Coverage (Re-checked)

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| LADDER-03 | 65-01 | A round that ends with nothing usable re-enters, naming the CAUSE of the zero | ✓ SATISFIED | all boundary/empty/encoding/precision/idempotency truths re-verified; REQUIREMENTS.md `[x]`; CR-01 fix specifically restores this for the all-empty case |
| LADDER-04 | 65-01 | Re-entry expressed without a `while` loop | ✓ SATISFIED | no-while guard re-run, passes; two straight-line call sites confirmed post-fix; REQUIREMENTS.md `[x]` |
| LADDER-05 | 65-01 | The search fallback becomes reachable in a real round | ◐ DELIBERATELY NOT SATISFIED (by design, this phase) | unchanged disposition — wiring proven offline, live reachability opportunistic per orchestrator ruling 2; REQUIREMENTS.md correctly shows `[ ]` |
| RICH-04 | 65-02 | `merge_enriched`'s keep/replace rule for a CREATE row audited as its own seam | ✓ SATISFIED | unchanged, `preingest.py`/`field_policy.yaml` untouched by the fix; REQUIREMENTS.md `[x]` |

No orphaned requirements: `grep -E "Phase 65" .planning/REQUIREMENTS.md` shows no additional IDs.

### Anti-Patterns Found

None in the fix. `git show 67d3f1a | grep -nE "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` returns no
match. The fix adds no stub, no empty handler, no hardcoded-empty prop — it adds a real
persistence assignment and a real conditional guard, both exercised by the new passing test.

### Prohibitions Check (Re-checked)

Both plans' `must_haves.prohibitions` blocks (19 items) remain `status: kept`,
`verification: explicit`. Re-spot-checked the ones most relevant to a control-flow fix:

- No `while` in plugin scripts — confirmed (AST walk + test run).
- `search_fallback.py`, `confidence.py`, `n8n/` unmodified — confirmed (`git diff --stat` empty).
- `round_outcome`'s purity (no module-level mutable state, no I/O) — confirmed unchanged
  (`suggest_contacts.py` absent from the fix commit's changed-file list).
- At most one re-entry per company, terminal call always `reentry: none` — confirmed unchanged
  (fix touches no precedence/reentry logic, only persistence/guarding of the existing calls).
- Caps/budget never reset — confirmed (`grep -iE "cap|budget"` over the fix's diff returns no
  match; the fix is a pure control-flow/persistence change).

All prohibitions hold. None flagged by the fix.

### Human Verification Required

None. The CR-01 fix and all 38 must-haves resolve to VERIFIED via direct codebase evidence
(source diff reading, running the actual test suite including the new regression test). LADDER-05
remains the one pre-dispositioned backstop item, confirmed to match its required state exactly as
in the initial verification.

### Gaps Summary

None. The code-review-found defect (CR-01) is closed: the documented pipeline no longer crashes
on an all-companies-empty round, and every company's line carries a reported cause instead. No
must-have regressed as a side effect — the fix is scoped to exactly the two files the review-fix
report claims, and every other artifact and key link this phase depends on is byte-for-byte
unchanged since the initial (passed) verification. The full plugin suite count (2565 passed, 5
skipped) matches the fix report's own claim exactly.

---
*Verified: 2026-09-07T01:15:00Z*
*Verifier: Claude (gsd-verifier)*
