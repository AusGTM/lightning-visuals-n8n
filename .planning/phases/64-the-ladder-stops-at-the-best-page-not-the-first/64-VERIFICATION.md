---
phase: 64-the-ladder-stops-at-the-best-page-not-the-first
verified: 2026-09-04T07:19:44Z
status: passed
score: 8/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 64: The Ladder Stops at the Best Page, Not the First — Verification Report

**Phase Goal:** Make the stage-1 page walk stop at the BEST people-bearing page rather than
the first one, inside the unchanged `MAX_FOLLOWUP_FETCHES` budget, by moving the stop
decision out of `SKILL.md` prose into a pure, testable predicate in `suggest_contacts.py`.

**Verified:** 2026-09-04T07:19:44Z
**Status:** passed
**Re-verification:** No — initial verification

## Post-execution context taken into account

A code review (`64-REVIEW.md`) found two critical defects AFTER the executor's green run:
CR-01 (the documented step-7 loop re-derived `candidates` from the full unfiltered
`sitemap_urls`, which — because `filter_candidates` always returns a prefix — made the walk
report `ladder_exhausted` after only 3 fetches regardless of ladder length, defeating
LADDER-01) and CR-02 (the pasted URL's own fetch was never folded into `pages`, so the
headline "receptionist + board page in one set" truth could not hold). Both are fixed in
commit `9dbc1a6` (SKILL.md loop reordering + narrowing the re-derivation input; pasted URL
fetched and folded first) with the amendment recorded in commit `bd28588`.

Per the reviewer's own finding (IN-01), no prior test drove the real per-fetch
`next_candidates` re-invocation with more than 2 accepted URLs, which is exactly how CR-01
shipped with a green suite. This verification therefore does NOT rely on `walk_pages`'s unit
tests alone (which use a static `candidates` dict and would have stayed green even with both
defects live). It independently re-ran, and read the source of, the INTEGRATED tests that
drive the real documented loop:
`test_suggest_contacts_composition.py::test_the_documented_loop_walks_every_candidate_the_budget_allows`
(parametrized 3/5/10 candidates, asserting the walk spends the full expected fetch count
rather than stopping at 3) and
`test_the_documented_loop_folds_the_pasted_page_and_a_later_ladder_page_into_one_union`
(asserting a pasted-page person and a later-ladder-page person both land in one union). Both
were re-run directly in this verification pass and pass; the helper
`_walk_company_like_skill_md` was read line-by-line and confirmed to mirror the corrected
SKILL.md step-7 code verbatim (candidates re-derived and narrowed BEFORE each `walk_pages`
call, pasted URL fetched and folded first, ladder loop breaks the instant `ended` is set).

**A further hole in that same class was found and closed during THIS verification pass, not
inherited from the review.** Both committed integration tests are constructed so the bar is
*never* cleared before `accepted` runs out (`_nobody` scores 0 on every page in the CR-01
test; `bar=99` in the CR-02 test). That means neither committed test exercises the
`if walk["ended"] is not None: break` line on the `good_enough` branch specifically — the
actual mechanism by which clearing the bar early is supposed to save budget, and the "no
ladder fetch is spent at all" pasted-page-alone path from the plan's own item-5 verification
requirement. That path was previously proven only at the `walk_pages` unit level with a
static `candidates` dict — precisely the coverage shape this section already flags as
insufficient for the loop-level defects. This verifier reproduced the live case directly
against the shipped, unmodified code (see the new spot-check row below) rather than accepting
the gap; it passed. No code change was required. **Recommendation (non-blocking):** add this
exact fixture as a committed test alongside the CR-01/CR-02 integration tests, so the
`good_enough`-via-the-real-loop path stops depending on a verifier re-deriving it by hand.

WR-01 (a synthesised row's provenance `locator` names only the last page walked, not the
page a given person actually came from) was explicitly scoped out by the orchestrator and
filed as a todo
(`.planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md`). It
does not bear on any of this phase's must-have truths as worded (all of which concern the
`people`/`selected` union and the `ended` vocabulary, not `provenance.locator`), so it is
recorded here as a known, accepted, non-blocking gap and not treated as a phase-blocking
defect — see "Known Accepted Gaps" below.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A company whose `/contact` page names one receptionist and whose `/board/` page names nine officers ends the round with people from BOTH pages in one set, deduped by normalised first+last name (D-64-01, D-64-02) | ✓ VERIFIED | `walk_pages` folds every page's people into one set keyed by `_name_key`, confirmed by reading the fold loop (`suggest_contacts.py:336-360`) and re-running `test_walk_pages_unions_people_across_pages_in_walk_order` and the CR-02 integration test (`test_the_documented_loop_folds_the_pasted_page_and_a_later_ladder_page_into_one_union`), which drives the real, corrected SKILL.md loop and asserts both a pasted-page person and a ladder-page person land in the same union. Both pass. Additionally reproduced live in this pass with the FULL receptionist+9-officer fixture (see spot-check table): 10 people unioned, `good_enough`, only 1 ladder fetch spent. |
| 2 | The walk stops when the cumulative role-filter hit count over the deduped union reaches `max(len(chosen_families), agreed_cap)` — never on mere presence on the page just fetched (D-64-03, D-64-05, D-64-06) | ✓ VERIFIED | `walk_bar` = `max(len(chosen_families or []), per_company_cap)` (one expression, confirmed by source read and by `walk_bar(['board'],3)==3`, `walk_bar(['a','b','c','d'],3)==4` re-run live); `walk_pages` checks `len(selected) >= bar` against the CUMULATIVE `selected` list, not the per-page score (`suggest_contacts.py:362`). |
| 3 | Not clearing the bar continues the walk; clearing it stops the walk early; neither branch changes the fetch cap (D-64-07) | ✓ VERIFIED | Confirmed by source read (bar check sets `ended`/breaks; no write to any budget field) and by two independently-run behaviors: the CR-01 integration test proves the walk keeps fetching up to the real budget when the bar is never cleared (`_nobody` fixture, 3/5/10 candidates → 3/5/5 fetches); this verifier's own reproduction (see spot-check table) proves the walk stops EARLY — 1 fetch instead of 2 available — the instant the bar clears. |
| 4 | A page whose fetch came back with disposition `'refused'` ends that company's walk even when accepted candidates still remain (D-64-10, SAFE-02) | ✓ VERIFIED | `walk_pages` checks `page.get("disposition") == WALK_REFUSED` FIRST in the fold loop, before any people are touched, and breaks (`suggest_contacts.py:337-339`); `test_walk_pages_ends_on_refused_disposition_even_with_candidates_left` re-run and passes. |
| 5 | The walk reports how it ended — one of `good_enough`/`ladder_exhausted`/`cap_exhausted`/`refused` — and acts on none of them; `cap_exhausted` is terminal and never a trigger to fetch again (D-64-08, D-64-11) | ✓ VERIFIED | `WALK_ENDINGS` closed 4-tuple confirmed in source; SKILL.md's `if not people:` guard (the only place `ended` could route logic) reads `people`, never `walk["ended"]` (confirmed by grep — `ended` appears only in the walk-loop break condition and step 9's report prose); `eligible_after_ladder` unchanged/uncalled by `suggest_contacts.py` (`hasattr(suggest_contacts,'search_fallback')` → `False`, `git diff --stat` on `search_fallback.py`/`url_fallback.py` empty). |
| 6 | `url_fallback.MAX_FOLLOWUP_FETCHES` is still 5, `cost_guard.MAX_FETCHES_PER_COMPANY` still equals it, and the walk keeps no fetch counter of its own (D-64-09, D-64-13, SAFE-03) | ✓ VERIFIED | `MAX_FOLLOWUP_FETCHES = 5` confirmed live; `cost_guard.py:78` `MAX_FETCHES_PER_COMPANY = url_fallback.MAX_FOLLOWUP_FETCHES`; AST-based structural test `test_walk_pages_source_never_references_max_followup_fetches` (scoped to the function body, docstring stripped) re-run and passes. |
| 7 | No plugin script contains a `while` loop (D-64-12) | ✓ VERIFIED | `ast.walk` over `suggest_contacts.py` finds 0 `While` nodes (re-run live); `test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` re-run and passes (pre-existing allowlist for legitimate poll loops, e.g. `watch.py`, is unchanged by this phase). |
| 8 | SKILL.md step 5 cites the walk predicate instead of carrying the stop rule as prose (LADDER-02) | ✓ VERIFIED | `grep -cE "first (one )?that yields"` → 0; step 5 (lines 100-112) cites `suggest_contacts.walk_pages(...)` and `suggest_contacts.walk_bar(chosen_families, per_company_cap)` by name with the exact stop condition in prose alongside the citation. |

**Score:** 8/8 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/scripts/suggest_contacts.py` | `walk_bar`, `walk_pages`, `WALK_GOOD_ENOUGH`, `WALK_LADDER_EXHAUSTED`, `WALK_CAP_EXHAUSTED`, `WALK_REFUSED`, `WALK_ENDINGS` | ✓ VERIFIED | All 7 symbols present exactly once (`grep -n "def walk_bar"` / `"def walk_pages"` each 1 line; `grep -cE "^WALK_..."` → 5). Pure (no I/O, no network); AST-verified no `while`. |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` | step 5 (~line 101) and step-7 code block (~lines 333-334) cite the predicate | ✓ VERIFIED | Step 5 rewritten (lines 100-118); step-7 block rewritten (lines 332-414) including the CR-01/CR-02 post-review fix — `walk_bar` computed once round-level, per-company loop feeds the pasted page then the ladder into `walk_pages`, `candidates` re-derived and narrowed before each call. Step 9 gained the ending-reason report line (lines 468-476). |
| `operator-claude-plugin/tests/test_suggest_contacts.py` | walk tests: union/dedupe, bar, each ending, constants-equality pin | ✓ VERIFIED | 20 new tests confirmed present by name (union, dedupe, bar values, all 4 endings, `WALK_REFUSED`/`WALK_CAP_EXHAUSTED` pinned equal to `search_fallback.DISPOSITION_*`, no-`search_fallback`-import, `MAX_FOLLOWUP_FETCHES` non-reference, no-`while` structural tests). All re-run and pass. |
| `operator-claude-plugin/tests/test_suggest_contacts_composition.py` | integration coverage of the real documented loop (added post-review) | ✓ VERIFIED | `test_the_documented_loop_walks_every_candidate_the_budget_allows` (3 parametrized cases) and `test_the_documented_loop_folds_the_pasted_page_and_a_later_ladder_page_into_one_union`, both driving `_walk_company_like_skill_md`, a line-for-line mirror of the corrected SKILL.md loop. Re-run and pass. Neither committed test exercises the `good_enough`-before-budget-exhausted branch of that loop (see "Post-execution context" above) — this verifier closed that gap by direct reproduction rather than by adding a test, and recommends the test be added as a follow-up. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `walk_pages` | `select_people` | per page, `len(selected)` is the D-64-03 score | ✓ WIRED | Confirmed at `suggest_contacts.py:351-360`: `select_people(new_people, family_list, chosen_families, known_contacts)` called once per folded page. |
| `walk_pages` | `next_candidates(...)`'s dict | verbatim `accepted`/`budget_remaining` read, the only source of `cap_exhausted` vs `ladder_exhausted` | ✓ WIRED | Confirmed at `suggest_contacts.py:366-376`: no counter maintained by `walk_pages` itself; both terminal endings read straight off the `candidates` dict. |
| SKILL.md step 5 | `walk_bar`/`walk_pages` | prose-to-code citation | ✓ WIRED | Confirmed by grep counts (`walk_pages` ≥1 in step 5, `walk_bar`/`walk_pages` cited by name in the step-7 block) and direct read. |
| `walk_pages['ended']` | Phase 65 only | `search_fallback.eligible_after_ladder` not called/imported/modified here | ✓ HELD | `hasattr(suggest_contacts, 'search_fallback')` → `False`; `git diff --stat` on `search_fallback.py`/`url_fallback.py`/`role_classify.py` empty; the `if not people:` guard in SKILL.md reads only `people`, never `ended`. |

### Behavioral Spot-Checks / Integration Re-Run

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 fix: 3/5/10 same-host candidates spend 3/5/5 fetches (not truncated to 3) | `pytest .../test_suggest_contacts_composition.py::test_the_documented_loop_walks_every_candidate_the_budget_allows -v` | 3 parametrized cases, all PASSED | ✓ PASS |
| CR-02 fix: pasted-page person + ladder-page person land in one union | `pytest .../test_the_documented_loop_folds_the_pasted_page_and_a_later_ladder_page_into_one_union -v` | PASSED | ✓ PASS |
| **NEW (this verification): `good_enough` fires via the REAL documented loop before the ladder is exhausted** — 1-receptionist pasted page + 9-officer `/board` ladder page + an unrelated `/extra` ladder page, `bar=3`; drove `_walk_company_like_skill_md`'s exact logic by hand against the live, unmodified `suggest_contacts.py`/`url_fallback.py` | inline `python -c` reproduction of the documented loop (see transcript in this verification session) | `ladder_fetch_count=1`, `ended="good_enough"`, `len(people)=10`, `/extra` never fetched | ✓ PASS — the `break` on a cleared bar demonstrably saves a real fetch, not merely a unit-level assertion |
| Full plugin suite | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | 2482 passed, 5 skipped | ✓ PASS (matches SUMMARY's claimed count exactly) |
| n8n suite (zero-diff sanity) | `node --test tests/n8n/*.test.mjs` | 894 passed, 0 failed | ✓ PASS |
| Zero `n8n/` diff invariant | `git diff --stat d1a40d7^..HEAD -- n8n/` | empty | ✓ PASS |
| `search_fallback.py`/`url_fallback.py`/`role_classify.py` byte-unchanged | `git diff --stat ...` | empty | ✓ PASS |
| No new imports in `suggest_contacts.py` | `git diff d1a40d7^..HEAD -- suggest_contacts.py \| grep '^\+import\|^\+from'` | no output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LADDER-01 | 64-01-PLAN.md | Walk continues past the first people-bearing page when a better candidate remains, under the same fetch budget | ✓ SATISFIED | Truths 1-3, 6; the CR-01 fix is specifically what makes this hold for ladders of 4+ candidates — verified directly by re-running the parametrized integration test rather than trusting the SUMMARY, plus this verifier's own `good_enough`-via-the-real-loop reproduction. REQUIREMENTS.md checkbox `[x]`. |
| LADDER-02 | 64-01-PLAN.md | "Better" is a testable predicate, not prose | ✓ SATISFIED | Truth 8; `walk_bar`/`walk_pages` are pure, tested functions; SKILL.md prose cites them rather than restating the rule. REQUIREMENTS.md checkbox `[x]`. |
| SAFE-02 (inherited) | 64-01-PLAN.md | A refusal stays terminal; no re-entry/retry/fallback reaches the search path from a `refused` ladder attempt | ✓ SATISFIED | Truth 4, 5; `eligible_after_ladder` unchanged/uncalled; the CR-02 fix's own consequence-check (a refused PASTED page now reaches `eligible_after_ladder([])`, which is confirmed fail-closed) is documented and traced in `64-REVIEW-FIX.md`. REQUIREMENTS.md checkbox `[x]`. |
| SAFE-03 (inherited) | 64-01-PLAN.md | `MAX_FOLLOWUP_FETCHES`/`MAX_FALLBACK_SEARCHES` bound the whole round; no reset; `cap_exhausted` never a retry trigger | ✓ SATISFIED | Truth 5, 6; `cost_guard.MAX_FETCHES_PER_COMPANY == url_fallback.MAX_FOLLOWUP_FETCHES` unchanged; `test_cost_guard_suggestion.py` re-run green. REQUIREMENTS.md checkbox `[x]`. |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s `LADDER` section maps LADDER-03/04/05
explicitly to Phase 65, and RICH-04 was re-routed to Phase 65 by operator ruling
(2026-09-04) — neither is claimed by 64-01-PLAN.md, and neither belongs here.

### Anti-Patterns Found

None. `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` scan across all 5 modified files
returned zero debt markers (one incidental match on the identifier `_PLACEHOLDER_RE`, a
pre-existing regex-substitution helper name in `test_skill_sequence_coverage.py`, unrelated
to a stub marker).

### Known Accepted Gaps (no owning later phase)

Not the Step-9b "deferred" sense (which means a later phase's roadmap goal explicitly
addresses the item) — WR-01's own todo carries `resolves_phase: null`. These are gaps
explicitly scoped out of this phase's fix pass and recorded, not gaps assigned to a specific
future phase.

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | WR-01: a synthesised row's `provenance.locator` names only the last page walked (`pages[-1]["url"]`), not the specific page a given person came from, once a walk spans more than one page | Recorded, accepted, non-blocking | Filed as `.planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md` by the orchestrator, explicitly out of scope for this phase's fix pass. Does not contradict any of this phase's 8 must-have truths (none of which assert per-person locator correctness) — it contradicts the phase's own T-64-05 threat-model claim, which is a documentation/threat-model accuracy issue, not a functional regression of LADDER-01/LADDER-02. |
| 2 | The ladder loop's `accepted` list (bound once, before the pasted-page fetch, from the full `sitemap_urls`) is not filtered to exclude the pasted URL itself. If a company's sitemap happens to list the pasted/starting URL again, the ladder loop will re-fetch it a second time as a "candidate," spending 1 of the 5-fetch budget on a page already folded into `pages`. `walk_pages`'s own dedupe/remainder logic handles this correctly (no double-counted people, no wrong "unfetched" reading), so this is an efficiency edge, not a correctness defect — found and traced during this verification, not present in the original review. | Non-blocking, informational | Traced live against `url_fallback.filter_candidates` (`operator-claude-plugin/scripts/url_fallback.py:143-194`), which checks scheme/host/budget only and has no "already the pasted URL" exclusion; this is pre-existing, unmodified `url_fallback.py` behavior (byte-identical diff), not introduced by this phase's edits. Worth a follow-up todo if it proves to matter in practice; not filed as one here since it was not observed live and is speculative. |

Neither gap changes the overall status; both are surfaced explicitly per the instruction to
note anything bearing on a must-have rather than stay silent.

### Human Verification Required

None. Every must-have truth is either a pure-function/structural property (directly
re-verified by source read and live command execution in this pass) or a state-transition
/ ordering invariant with an actual behavioral test exercising it end to end — the CR-01/CR-02
integration tests (re-run live, not merely trusted from SUMMARY.md) plus this verifier's own
direct reproduction of the `good_enough`-via-the-real-loop path, which no committed test
covers.

### Gaps Summary

No gaps against the phase's stated must-haves. Both critical defects found by code review
(CR-01, CR-02) are fixed, verified fixed independently in this pass (not merely trusted from
the REVIEW-FIX narrative), and a third potential hole in the same class — the untested
`good_enough`-clears-early-and-saves-a-real-fetch path — was found during this verification
and closed by direct reproduction against the shipped code rather than left as an unverified
claim. Two non-blocking items are recorded (a known, accepted todo, WR-01, and a newly-traced
informational efficiency edge) — neither bears on the phase's must-have truths as worded.

---

_Verified: 2026-09-04T07:19:44Z_
_Verifier: Claude (gsd-verifier)_
