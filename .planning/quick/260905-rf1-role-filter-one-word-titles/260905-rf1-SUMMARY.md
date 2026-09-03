---
quick_id: 260905-rf1
type: execute
status: complete
subsystem: operator-plugin
tags: [role-vocabulary, suggest-contacts, classification, plugin-release]
requires: []
provides:
  - "role_vocabulary.yaml families: Marketing, Media, Sponsorship (ungraded, one bare member each)"
  - "frozen title->label snapshot test pinning append-at-end"
  - "permanent single-token collision guard"
affects:
  - operator-claude-plugin/skills/suggest-contacts
tech-stack:
  added: []
  patterns:
    - "vocabulary-only fix; matcher left untouched"
    - "append-at-end as a load-bearing position, pinned by a frozen snapshot test"
key-files:
  created: []
  modified:
    - operator-claude-plugin/config/role_vocabulary.yaml
    - operator-claude-plugin/tests/test_role_vocabulary.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - .planning/todos/completed/2026-09-04-role-filter-drops-one-word-titles.md
decisions:
  - "Candidate (a) vocabulary-only taken; candidate (b) label-prefix matching measured dead (covers 1 of 3)"
  - "Three families appended at the END, not bolted into existing graded families — every in-place home flips Marketing Director / Media Director"
  - "Only 3 of the todo's 7 short forms added; the other 4 have no live observation"
metrics:
  duration: ~12m
  completed: 2026-09-05
actuals:
  tokens: 5200
  tasks: 3
  commits: 3
---

# Quick Task 260905-rf1: Role Filter Drops One-Word Titles — Summary

Three ungraded families (`Marketing`, `Media`, `Sponsorship`) appended to the shipped curated
role vocabulary so a club that publishes one-word departmental job titles is reachable by a
role selection; the matcher is unchanged, no existing classification moved, and the plugin
ships as `0.39.2`.

## Pre-edit suite baseline

Recorded before touching anything (Task 1 requirement):

```
2431 passed, 5 skipped in 13.66s     # operator-claude-plugin
```

Orchestrator-supplied baselines for the other two: root 4189 passed / 154 skipped;
node 894 pass / 0 fail.

## Task 1 — RED, verbatim

Run without `-x` (the plan's `-x` would have stopped at the first failure and shown `1 failed`,
not the "exactly 3" the done-criterion demands):

```
=========================== short test summary info ============================
FAILED tests/test_role_vocabulary.py::test_shipped_vocabulary_classifies_the_live_one_word_club_titles[Marketing-Marketing-Jordan Hayward]
FAILED tests/test_role_vocabulary.py::test_shipped_vocabulary_classifies_the_live_one_word_club_titles[Media-Media-Joseph Esposito]
FAILED tests/test_role_vocabulary.py::test_shipped_vocabulary_classifies_the_live_one_word_club_titles[Sponsorship-Sponsorship-Emma Hoadley]
3 failed, 45 passed in 0.20s
```

One assertion message in full, to show the failure names the live observation rather than an
invented case:

```
AssertionError: 'Sponsorship' was the page title of Emma Hoadley on Brisbane Roar FC's own
contact page (company 285507657175, measured 2026-09-04); it classified to None, so the role
filter selected 0 of 3 real staff in exactly the roles the operator had asked for
assert None == 'Sponsorship'
```

**Exactly 3 failures, all in group 1.** The 13-row frozen snapshot (group 2) and the collision
guard (group 3) were both GREEN against the unchanged shipped vocabulary — which is what makes
them a valid before/after pin rather than tests written to fit the fix.

Commit: `674ce6f`.

## Task 2 — GREEN

`operator-claude-plugin/config/role_vocabulary.yaml` edited in place: two header lines
(`version: lv-role-vocabulary-v2` → `v3`, `top_n: 17` → `20`) plus a pure append of three
families after `Administration`. `source: generic_fallback` and `evidenced: false` left
unchanged — this is still not a portal-derived list, and D-62-07/SUGGEST-03 depend on that flag
staying honest. Not regenerated from `scripts/role_vocabulary.py` (recorded rejected decision).

`git diff --stat`: `30 insertions(+), 2 deletions(-)`, one file. No existing family touched.

Commit: `e707188`.

## Task 3 — release and todo closure

`plugin.json` `0.39.1` → `0.39.2` with a matching `## [0.39.2] - 2026-09-05` CHANGELOG section
in the same commit. The section records the four things the diff cannot carry: the live defect,
the measured rejection of the label-prefix matcher change, why append-at-end is load-bearing,
and the honest limit. Todo `git mv`'d to `.planning/todos/completed/` with a closing note.

Commit: `8da9bf1`.

## Verification

| Check | Result |
| --- | --- |
| `Marketing` / `Media` / `Sponsorship` classify to their own family | pass |
| All 13 frozen snapshot rows unchanged after the edit | pass |
| `Marketing Director` / `Media Director` still `Board & Committee` | pass |
| No single-token member in two families | pass |
| `role_classify.py` diff | **empty** |
| `n8n/` diff | **empty** |
| Live HubSpot calls / provider credits / n8n executions | **zero** |

### Suites (final, all three)

| Suite | Baseline | After | |
| --- | --- | --- | --- |
| root python | 4189 passed / 154 skipped | **4206 passed / 154 skipped** | +17 (the root run collects the plugin tests) |
| node | 894 pass / 0 fail | **894 pass / 0 fail** | unchanged |
| plugin | 2431 passed / 5 skipped | **2448 passed / 5 skipped** | +17 (3 live + 13 frozen + 1 collision guard) |

All at or above baseline.

## Decisions Made

**Candidate (b) — label-prefix matching — is dead by measurement, not by argument.** Against
the shipped 17-family vocabulary: labels whose first token is `marketing` → `['Marketing
Manager']`; `media` → `[]`; `sponsorship` → `[]`. It covers 1 of the 3 proven-live cases,
would still have needed a vocabulary edit for the other two, and widens every existing
family's reach to buy that third. `role_classify.py` was not touched.

**Append-at-end is load-bearing, not cosmetic.** `classify_title` takes the longest matching
member (strict `>`), so an equal-length tie breaks first-wins by family order. Every graded
marketing/media/broadcast family sits at index 3–7; `Board & Committee` (which owns the bare
member `Director`) sits at index 11. A bare `Marketing` or `Media` member placed in `Head of
Marketing`, `Marketing Manager`, `Head of Broadcast` or `Communications Manager` flips
`Marketing Director` / `Media Director` off `Board & Committee`. Appended at the end, the tie
resolves to the earlier family and nothing moves. The two `... Director` rows in the frozen
snapshot are what pin this — a future reorder now fails loudly.

**Ungraded families, not members in graded ones.** `Head of Marketing` had real live evidence
behind it (enrichment resolved the same person's richer title as `Head of Marketing and
Content`) and was still rejected: it flips `Marketing Director`, and it would label a marketing
coordinator "Head of Marketing" on every other club. Longest-wins already protects the graded
titles — re-measured unchanged after the edit.

**Only 3 of the todo's 7 short forms.** `communications`, `commercial`, `operations`, `finance`
were not added: none was observed live, `communications`/`operations` would tie-flip in their
existing graded families, `commercial`/`finance` have no live evidence at all. One YAML append
away if a later sitting measures them. YAGNI, named.

## The honest limit — what this does NOT do

`suggest_contacts.select_people` admits a person only when the classified label is in the
operator's round-level `chosen_families`. **This fix does not retroactively make the Brisbane
Roar round yield 3.** The UAT does not record which labels the operator ticked for that round,
so what changed is that a selection yielding 3 is now *possible*, where before no selection
could reach that company at all. The operator must tick the new `Marketing` / `Media` /
`Sponsorship` entries, which `offer_block` now lists.

The vocabulary also remains `evidenced: false` / `source: generic_fallback`, so `offer_block`
still opens with the D-62-07 disclosure sentence. Three more generic families is not evidence.

## Out of scope

The second, cheaper mitigation the todo mentions — classifying against the richer *enriched*
title rather than the scraped one — was not done here. It belongs to
`.planning/todos/pending/2026-09-04-phone-is-never-chased-only-accepted.md`, the todo recording
that the enriched title and a `seniority` of Director were both discovered and then dropped.

## Deviations from Plan

One, procedural and non-substantive: the plan's Task 1 verify command carries `-x`, which stops
at the first failure and would have reported `1 failed` rather than letting the "exactly 3
failures, groups 2 and 3 green" done-criterion be observed. RED was captured with the same
command minus `-x`. No plan content changed.

A staging slip, recorded for honesty rather than as a deviation: Task 3 was first committed as
`41ae256`, which captured only the `git mv` — the accompanying `git add` failed on the
now-absent `pending/` path and staged nothing else. Amended to `8da9bf1` with `plugin.json`,
the CHANGELOG section and the todo's closing note. The plan's "same commit" requirement for
the version bump and the CHANGELOG entry holds in `8da9bf1`.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, no new write path, no package install. T-rf1-01's mitigation
(bare members held to three function nouns with a live observation each) and T-rf1-02's
(frozen snapshot + collision guard) both landed as planned; `FORBIDDEN_BARE_GRADE_NOUNS` and
`agreed_cap` are unchanged.

## Self-Check: PASSED

- `operator-claude-plugin/config/role_vocabulary.yaml` — FOUND
- `operator-claude-plugin/tests/test_role_vocabulary.py` — FOUND
- `.planning/todos/completed/2026-09-04-role-filter-drops-one-word-titles.md` — FOUND
- `.planning/todos/pending/2026-09-04-role-filter-drops-one-word-titles.md` — correctly ABSENT
- Commits `674ce6f`, `e707188`, `8da9bf1` — all FOUND in `git log`
