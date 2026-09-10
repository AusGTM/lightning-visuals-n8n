---
phase: quick-260911-anw
plan: 01
subsystem: operator-claude-plugin
tags: [suggest-contacts, provenance, walk, tdd]
status: complete
dependency-graph:
  requires: []
  provides:
    - "walk_pages folds a per-person source_url onto each admitted person, stamped at the admit site"
    - "synthesise_rows resolves a per-person locator (person.source_url, fetched_url fallback)"
  affects:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
tech-stack:
  added: []
  patterns:
    - "stamp provenance at the one site that knows the fact (the fold's admit site), never reconstruct it downstream"
key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - .planning/todos/completed/2026-09-04-walk-provenance-locator-names-last-page-only.md
decisions:
  - "Stamp source_url on a COPY of the person at walk_pages' admit site (dict(person, source_url=...)), never mutate the caller's pages list, since pages is re-walked on every ladder-growth call."
  - "Resolve the locator inside synthesise_rows' per-record loop ({**provenance, locator: person.get(source_url) or fetched_url}), keeping fetched_url as the fallback for any person the walk never folded (search-fallback branch, hand-built dicts)."
  - "No new walk_pages return key: source_url rides each person, so the six-key return contract (D-64-11) is untouched."
actuals:
  tokens: 32000
  tasks: 2
  commits: 2
  plan_head_before: 253a75b5
metrics:
  duration: "~25 minutes"
  completed: 2026-09-11
---

# Quick 260911-anw: Walk provenance locator names last page only Summary

Attributed a synthesised contact row's provenance locator to the page the person was
actually found on, instead of whatever page a company's multi-page walk happened to
fetch last (`64-REVIEW.md` § WR-01).

## What changed

**`walk_pages`** (`operator-claude-plugin/scripts/suggest_contacts.py`): at the fold's
admit site — inside the per-page loop, after the `seen_keys` dedupe `continue` — each
newly admitted person is now appended as `dict(person, source_url=page.get("url"))`, a
copy carrying that page's own URL. A copy, never a mutation: `pages` belongs to the
caller and is re-walked on every subsequent call as the ladder grows, so mutating it in
place would rewrite history each pass. Stamping at the admit site (post-dedupe) is what
makes a duplicate name keep its first-sighting page. The refusal check already breaks
before a refused page's people are touched, so a refused page's URL can never reach this
line. No new top-level return key — the return stays exactly six keys
(`people`/`selected`/`dropped`/`scores`/`ended`/`bar`), and no change was needed to
`select_people` (it already returns `dict(person, role_family=family)`, a copy that
carries every key through, including the new `source_url`).

**`synthesise_rows`**: resolves the locator per person inside the record loop —
`person.get("source_url") or fetched_url` — rather than building one global `provenance`
dict reused for every row. `fetched_url` remains the required positional and the locator
for any person carrying no `source_url` (the search-fallback path, and every existing
call site that hand-builds person dicts). The row itself is untouched: `source_url` rides
the person, never a row key, so the canonical-key assertion and `write_dispatch_csv`'s
own refusal are unaffected.

**`SKILL.md`**: step 7's `fetched_url = pages[-1]["url"] if pages else
plan.get("pasted_url")` is now `fetched_url = plan.get("pasted_url")` with a comment
naming it the fallback locator only — the `pages[-1]` expression the finding names is
gone from the file. Step 6's synthesise paragraph now says each row's locator is the
page THAT PERSON was found on, not "the URL actually fetched ... never the page the
operator originally pasted". The fallback-branch comment at the bottom of step 7 (sibling
item 260911-ao2's edit zone) was left byte-identical.

**Todo**: `git mv`'d from `.planning/todos/pending/` to `.planning/todos/completed/`
with a resolution note naming the seam used and the pinning tests. `resolves_phase`
stays `null` per the todo's own instruction (a quick task is not a phase).

## Deviations from Plan

None — plan executed exactly as written, including the TDD RED-first order on Task A's
three new tests (all three failed against the last-page defect before the fix, both
pre-existing regression-guard assertions — the six-key set and the no-`source_url`
fallback — passed unmodified throughout).

## Residual (recorded, not chased — out of this todo's scope)

The search-fallback branch still stamps a single `fetched_url` per company when more
than one accepted URL is fetched for that company. The todo named the ladder walk only;
this shape was named explicitly in the plan's objective as deliberately not fixed here.

## Test results observed

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py operator-claude-plugin/tests/test_suggest_contacts_composition.py -q` → 190 passed (Task A).
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` → 2869 passed, 5 skipped (Task B, full plugin suite — includes the no-`while`-loop guard and SKILL call-sequence coverage tests).
- `git status --porcelain n8n/ scripts/` → empty (no n8n diff, no workflow regeneration).

## Self-Check: PASSED

- `operator-claude-plugin/scripts/suggest_contacts.py` — FOUND, modified as described.
- `operator-claude-plugin/tests/test_suggest_contacts.py` — FOUND, three new tests present and passing.
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — FOUND, `pages[-1]` absent, `plan.get("pasted_url")` present.
- `.planning/todos/completed/2026-09-04-walk-provenance-locator-names-last-page-only.md` — FOUND.
- `.planning/todos/pending/2026-09-04-walk-provenance-locator-names-last-page-only.md` — MISSING (expected, moved).
- Commit `1d4b5cef` — FOUND in `git log`.
- Commit `901825c1` — FOUND in `git log`.
