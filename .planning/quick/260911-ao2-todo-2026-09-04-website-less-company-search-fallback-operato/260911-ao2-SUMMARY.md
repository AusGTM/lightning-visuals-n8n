---
phase: quick-260911-ao2
plan: 01
subsystem: operator-claude-plugin
tags: [suggest-contacts, search-fallback, tdd]
status: complete
dependency-graph:
  requires:
    - "260911-anw: walk_pages folds source_url onto admitted people, synthesise_rows resolves per-person locator"
  provides:
    - "eligible_after_ladder(attempts, ladder_built=True) admits a website-less company as absence of information, refuses any non-empty attempts alongside ladder_built=False as a contradiction"
    - "rank_results docstring names rank 1 as structurally unreachable with no company_url (no logic change)"
    - "search_fallback.py CLI --no-ladder flag threads the same claim through --eligible and --rank"
    - "WALK_NO_LADDER (5th WALK_ENDINGS member) and CAUSE_NO_LADDER (7th ROUND_CAUSES member, precedence-ordered after CAUSE_UNKNOWN) enter round_outcome's existing cause/re-entry machinery under the identical routing-vs-terminal rule"
    - "SKILL.md step 5's documented block guards next_candidates/accepted behind plan[\"pasted_url\"], initialising an already-ended WALK_NO_LADDER walk on the no-ladder branch"
    - "the pending/2026-09-04-website-less-company-search-fallback.md todo closed to completed/"
  affects:
    - operator-claude-plugin/scripts/search_fallback.py
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
tech-stack:
  added: []
  patterns:
    - "a new terminal enters an EXISTING cause/re-entry machine via one new cause + one new caller-stated ending, never a second call site or a second gate"
key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/search_fallback.py
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_search_fallback.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - .planning/todos/completed/2026-09-04-website-less-company-search-fallback.md
decisions:
  - "ladder_built defaults True so every existing eligible_after_ladder caller and test is byte-identical; the contradiction check (non-empty attempts + ladder_built=False) refuses uniformly regardless of what the impossible attempt records, so the flag can never launder a recorded refusal or a recorded ladder into eligibility."
  - "rank_results needed NO logic change for a falsy company_url -- _host_matches already refuses an empty listed host, so rank 1 was already structurally unreachable. Only a docstring paragraph was added naming the consequence."
  - "WALK_NO_LADDER is stated by the CALLER, never produced by walk_pages itself -- pinned by a dedicated regression test over an empty pages/accepted invocation."
  - "CAUSE_NO_LADDER enters round_outcome's existing people_count==0 branch and the existing routing-vs-terminal rule verbatim (all four of rows/sendable/held/fallback None), rather than a parallel gate or a second call site -- one router for every terminal."
actuals:
  tokens: 10392
  tasks: 3
  commits: 3
  plan_head_before: 228745ef
metrics:
  duration: "~25 minutes"
  completed: 2026-09-11
---

# Quick 260911-ao2: Website-less company search fallback Summary

A company with no usable website on record now reaches the web-search fallback through the
same cause/re-entry machinery every other suggestion round uses, produces no rank-1 result by
construction (LinkedIn-or-held), and writes no discovered domain anywhere.

## What changed

**`search_fallback.py`** gained a `ladder_built=True` keyword on `eligible_after_ladder`. When
falsy, an empty `attempts` list is eligible ("absence of information, not a fence" — operator
ruling 2026-09-11); any non-empty (or non-list) `attempts` alongside it is a CONTRADICTION
(attempts cannot exist without a ladder) and stays ineligible, closing the one path a recorded
refusal could otherwise be laundered through. `rank_results` needed no logic change — a falsy
`company_url` already makes rank 1 structurally unreachable (`_host_matches` refuses an empty
listed host) — only a docstring paragraph naming the consequence. The `__main__` CLI gained a
bare `--no-ladder` flag: `--eligible` passes its negation through as `ladder_built`; `--rank`
relaxes its `--company-url` requirement only when the flag is present, passing `None` through
in that case.

**`suggest_contacts.py`** gained `WALK_NO_LADDER` (fifth and last of `WALK_ENDINGS` — never
produced by `walk_pages` itself, only stated by a caller with nothing to walk) and
`CAUSE_NO_LADDER` (seventh of `ROUND_CAUSES`, precedence-ordered immediately after
`CAUSE_UNKNOWN`). `round_outcome`'s `people_count == 0` arm branches on the walk's own `ended`
to pick between `CAUSE_NO_LADDER` and `CAUSE_NO_PEOPLE_FOUND`; the re-entry condition admits
`CAUSE_NO_LADDER` under the IDENTICAL routing-vs-terminal rule already governing
`CAUSE_NO_PEOPLE_FOUND` — all four of `rows`/`sendable`/`held`/`fallback` must be `None` — so a
terminal call still cannot route and no second route exists. `walk_pages` itself is untouched.

**`SKILL.md`** step 5's documented block guards the two ladder-only statements
(`next_candidates`, the `accepted` binding) behind `if plan["pasted_url"]:`; the no-ladder
branch initialises the walk already-ended with `WALK_NO_LADDER` so the candidate loop iterates
nothing and no ladder fetch is ever attempted. The `eligible_after_ladder` call now passes
`ladder_built=bool(pasted_url)` through. Step 5 prose gains a paragraph naming the operator
ruling with a `--no-ladder` CLI example; step 9's operator-words cause table gains the
`no_ladder` row. No `module.function(...)` call was added to the documented block — the
sequence-coverage registry (`tests/test_skill_sequence_coverage.py`) needed no edit.

**Todo**: `git mv`'d from `pending/` to `completed/` with a resolution section naming what
shipped, the two gates a website-less round still faces unchanged
(`partition_for_dispatch`'s required `company_domains`, D-5sd-05's rank-3 hold), and the two
questions the ruling left explicitly open (domain write-back, email-relatedness alternate).

## Deviations from Plan

None — plan executed exactly as written, including RED-first TDD on Tasks 1 and 2 (every new
test observed failing against the unmodified module before the code change, confirmed via
explicit `TypeError`/assertion failures in the terminal output).

## Test results observed

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_search_fallback.py operator-claude-plugin/tests/test_report_sufficiency.py -q` → 71 passed (Task 1).
- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -q` → 176 passed (Task 2).
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` → 2903 passed, 5 skipped (Task 3, full plugin suite).
- `git diff --stat operator-claude-plugin/tests/test_skill_sequence_coverage.py` → empty.
- `git diff --stat n8n/ scripts/` → empty.
- `git diff operator-claude-plugin/.claude-plugin/plugin.json operator-claude-plugin/CHANGELOG.md` → empty.

## Self-Check: PASSED

- FOUND: operator-claude-plugin/scripts/search_fallback.py (ladder_built keyword present)
- FOUND: operator-claude-plugin/scripts/suggest_contacts.py (WALK_NO_LADDER, CAUSE_NO_LADDER present)
- FOUND: operator-claude-plugin/skills/suggest-contacts/SKILL.md (no-ladder branch present)
- FOUND: .planning/todos/completed/2026-09-04-website-less-company-search-fallback.md
- MISSING: .planning/todos/pending/2026-09-04-website-less-company-search-fallback.md (correctly absent — moved)
- FOUND commit e50604bc (Task 1), 5702b6a7 (Task 2), 20363788 (Task 3) in `git log --oneline`
