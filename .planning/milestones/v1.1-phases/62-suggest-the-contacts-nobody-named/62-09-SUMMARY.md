---
phase: 62-suggest-the-contacts-nobody-named
plan: 09
subsystem: enrichment
tags: [role-classification, contact-suggestion, offline-config, tdd]

requires:
  - phase: 62-suggest-the-contacts-nobody-named
    provides: "role_classify.classify_title (exact-label matcher), the shipped role_vocabulary.yaml, select_people/synthesise_rows round pipeline"
provides:
  - "A contiguous-token-run, longest-wins, entity-aware classify_title matcher"
  - "An expanded fallback role_vocabulary.yaml carrying the 17 racing-club governance titles measured live 2026-09-03"
  - "A structural test forbidding bare grade-noun single-token members"
affects: [suggest-contacts, role_classify, role_vocabulary]

actuals:
  tokens: 3202
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Tokenise-then-contiguous-run matching instead of substring/overlap, to prevent a shared trailing word from carrying a false match"
    - "Structural test walking a shipped config file's members, rather than trusting authoring care, to forbid a specific class of over-broad entry"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/role_classify.py
    - operator-claude-plugin/config/role_vocabulary.yaml
    - operator-claude-plugin/tests/test_role_vocabulary.py
    - operator-claude-plugin/tests/test_suggest_contacts.py

key-decisions:
  - "Decision 1 (matching rule): implemented verbatim — html.unescape -> casefold -> & becomes 'and' -> non-alphanumeric becomes space -> split, then contiguous-token-run match, longest wins, tie-break on first seen."
  - "Decision 2 (no bare grade nouns): implemented as a structural test (test_shipped_vocabulary_has_no_bare_grade_noun_members) over the shipped YAML, not by authoring care."
  - "Decision 3 (existing eight families untouched, governance vocabulary added beneath): implemented — CEO/CMO/Head of Broadcast/Head of Marketing/Marketing Manager/Operations Manager/General Manager/Communications Manager are byte-identical and first in the list; nine new families added after them."
  - "Decision 4 (single change point, role_classify.classify_title only): implemented — select_people, load_families, offer_block, chosen_families, DISCLOSURE_SENTENCE and scripts/role_vocabulary.py are all untouched."

requirements-completed: [SUGGEST-02, SUGGEST-03]

coverage:
  - id: D1
    description: "classify_title matches partially (contiguous token run), entity/ampersand/case normalised, longest match wins, order-independent"
    requirement: SUGGEST-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_classify_title_partial_operator_named_cases"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_classify_title_never_sweeps_track_manager_into_general_manager"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_classify_title_longest_match_wins_order_independent"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_classify_title_normalises_entities_ampersand_and_case_together"
        status: pass
    human_judgment: false
  - id: D2
    description: "Shipped fallback vocabulary covers all 17 measured racing-club titles (+ entity spelling) and forbids bare grade-noun members"
    requirement: SUGGEST-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_role_vocabulary.py#test_shipped_vocabulary_covers_every_measured_racing_club_title"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_role_vocabulary.py#test_shipped_vocabulary_has_no_bare_grade_noun_members"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_role_vocabulary.py#test_shipped_vocabulary_loads_and_reports_evidenced_false"
        status: pass
    human_judgment: false

duration: ~8min
completed: 2026-09-04
status: complete
---

# Phase 62 Plan 09: Contiguous-token-run role matcher + measured governance vocabulary Summary

**Replaced `classify_title`'s exact-label-only match with a token-contiguous-run, longest-wins, entity-aware matcher, and expanded the shipped fallback vocabulary from 8 generic corporate roles to 17, adding the racing-club governance titles measured live on 2026-09-03 (43 people named, 2 selected before this change).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-09-04T00:02:31+10:00 (prior commit on branch)
- **Completed:** 2026-09-04T00:09:40+10:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `classify_title` now does contiguous-token-run partial matching (normalising HTML entities, `&`, punctuation, and case identically on both sides) instead of exact-label-only matching, with longest-match-wins tie-breaking that is provably order-independent.
- The over-match trap the operator named — a shared trailing word ("Manager") sweeping unrelated titles together — is structurally impossible: contiguous-run matching means "Track Manager" can never resolve as "General Manager".
- The shipped `role_vocabulary.yaml` now carries 17 families (9 new governance families added beneath the 8 untouched generic ones) covering every one of the 17 job titles measured live across three racing-club board/committee pages, plus the HTML-entity-escaped spelling the portal actually stores.
- A structural test (`test_shipped_vocabulary_has_no_bare_grade_noun_members`) permanently forbids a bare `Manager`/`Officer`/`Executive`/`Assistant`/`Coordinator`/`Supervisor`/`Head`/`Lead` member — the guard that stops a future edit from reintroducing the sweep, rather than relying on the next editor's care.

## TDD Gate Compliance (Task 1)

RED observed BEFORE touching `role_classify.py` (six new tests added to `test_suggest_contacts.py`; four already passed trivially against exact-match members that happened to equal the whole title, two failed as expected):

```
....F..F.............................................................    [100%]
=================================== FAILURES ===================================
_______________ test_classify_title_partial_operator_named_cases _______________
    assert role_classify.classify_title("Secretary Manager", PARTIAL_FAMILY_LIST) == "secretary"
E       AssertionError: assert None == 'secretary'
_____ test_classify_title_normalises_entities_ampersand_and_case_together ______
    assert role_classify.classify_title(title, PARTIAL_FAMILY_LIST) == "finance"
E       AssertionError: assert None == 'finance'
=========================== short test summary info ============================
FAILED operator-claude-plugin/tests/test_suggest_contacts.py::test_classify_title_partial_operator_named_cases
FAILED operator-claude-plugin/tests/test_suggest_contacts.py::test_classify_title_normalises_entities_ampersand_and_case_together
2 failed, 67 passed in 0.22s
```

This is the expected RED shape per the plan: the two genuinely-partial assertions (`"Secretary Manager"` -> `secretary`, and the entity/ampersand-vs-plain spellings all resolving together) fail against the old exact-label matcher, while the over-match negative (`"Track Manager"` -> `track`, not `gm`) and the longest-wins case (`"Vice President"` -> `vice-president`) already passed because those titles happened to be exact members of their own family — not evidence the rule was already right, just that those particular assertions don't exercise partiality on their own. The pre-existing `"Head Chef"` case and blank/`None` contracts were unaffected.

GREEN after the rewrite: `69 passed` (test_suggest_contacts.py + test_role_vocabulary.py + test_suggest_contacts_composition.py together), full plugin suite `2306 passed, 5 skipped` (Task 1) -> `2328 passed, 5 skipped` (after Task 2, count includes concurrently-landed 62-08 tests in the shared checkout).

RED/GREEN gate commits present in git log:
- `9197506` `feat(62-09): contiguous-token-run matcher, longest-wins, entity-aware` — implementation commit, includes the tests that were RED first (single commit per plan's task granularity; the plan's own `<verification>` section states no pre-existing test needed to change, and this plan is `type="tracer" tdd="true"` on Task 1 only, not a plan-level `type: tdd`, so a separate `test(...)` RED commit was not required by the plan's own gate sequence — RED was observed and is quoted above, GREEN follows in the same commit as the fix per the task's own `<verify>` gate).

## Task Commits

Each task was committed atomically:

1. **Task 1: The matcher — partial, entity-aware, longest-wins, and unable to sweep** - `9197506` (feat)
2. **Task 2: The shipped fallback carries the vocabulary the sitting actually measured** - `e401b77` (feat)

_Note: this plan's `type="tracer" tdd="true"` applies to Task 1 only (per-task TDD, not a plan-level `type: tdd`); RED was observed and quoted above before the fix landed in the same commit._

## Files Created/Modified
- `operator-claude-plugin/scripts/role_classify.py` - `_normalize` replaced by `_tokenize` (html.unescape -> casefold -> `&`->`and` -> non-alnum->space -> split) plus `_contains_run`; `classify_title` now finds the longest contiguous-token-run match across all families/members instead of exact-label equality. Docstrings updated to state the new rule and why substring/overlap were rejected.
- `operator-claude-plugin/config/role_vocabulary.yaml` - 9 governance families added beneath the untouched 8 generic ones (Chair, President, Vice President, Board & Committee, Secretary, Treasurer, Track & Facilities, Catering & Events, Administration — 35 members total across 17 families); `version` -> `lv-role-vocabulary-v2`, `built_on` -> `2026-09-04`, `top_n` -> `17`. `evidenced: false`, `source: generic_fallback`, every family's `recurrence: 0`/`evidenced: false` unchanged.
- `operator-claude-plugin/tests/test_role_vocabulary.py` - Added `test_shipped_vocabulary_covers_every_measured_racing_club_title` (parametrised over the 17 measured titles + 1 entity spelling) and `test_shipped_vocabulary_has_no_bare_grade_noun_members` (structural guard over the shipped YAML).
- `operator-claude-plugin/tests/test_suggest_contacts.py` - Added 6 tests against a local `PARTIAL_FAMILY_LIST` fixture (partial cases, over-match negative, longest-wins with reversed order, entity/ampersand normalisation, tail-of-longer-word non-match, unchanged blank/None/no-match contracts).

## Final family list (17 families, 35 members)

| Family | Members | Count |
|---|---|---|
| CEO *(unchanged)* | CEO | 1 |
| CMO *(unchanged)* | CMO | 1 |
| Head of Broadcast *(unchanged)* | Head of Broadcast | 1 |
| Head of Marketing *(unchanged)* | Head of Marketing | 1 |
| Marketing Manager *(unchanged)* | Marketing Manager | 1 |
| Operations Manager *(unchanged)* | Operations Manager | 1 |
| General Manager *(unchanged)* | General Manager | 1 |
| Communications Manager *(unchanged)* | Communications Manager | 1 |
| Chair | Chairman, Chairperson, Deputy Chairman, Vice Chairman | 4 |
| President | President | 1 |
| Vice President | Vice President | 1 |
| Board & Committee | Director, Directors, Board Of Directors, Board Member, Committee Member | 5 |
| Secretary | Secretary, Secretary Manager, Company Secretary, Club Secretary | 4 |
| Treasurer | Treasurer, Finance and Admin Officer, Finance Officer | 3 |
| Track & Facilities | Track Manager, Racecourse Track Curator, Trackwork Supervisor, Racecourse Manager | 4 |
| Catering & Events | Catering Manager, Functions Manager | 2 |
| Administration | Executive Assistant, Office Manager, Administration Officer | 3 |

All 17 measured titles resolve: Chairman, Deputy Chairman, President, Vice President and Vice Chairman all resolve inside their own families (longest-token-run wins, e.g. "Vice President" is 2 tokens and beats the 1-token "President" family); Director / Board Of Directors / Committee member all resolve to Board & Committee; Treasurer / Secretary / Secretary Manager resolve correctly; Track Manager / Racecourse Track Curator / Trackwork Supervisor resolve to Track & Facilities without cross-matching each other's extra tokens; Catering Manager to Catering & Events; Executive Assistant to Administration; Finance & Admin Officer (both the plain and `&amp;`-escaped spellings) to Treasurer.

## Decisions Made

- **Decision 1 (matching rule)** — Implemented verbatim as specified: normalise (`html.unescape` -> casefold -> `&`->`and` -> non-alnum->space -> split) both member and title, then find the contiguous token run with the most tokens across every (family, member) pair; ties break on first-seen (family order, then member order). Proven order-independent by `test_classify_title_longest_match_wins_order_independent`, which asserts the same result against the family list reversed.
- **Decision 2 (no bare grade nouns)** — Implemented as a structural test, not prose. `test_shipped_vocabulary_has_no_bare_grade_noun_members` tokenises every member in the shipped YAML and fails if any single-token member is in `{manager, officer, executive, assistant, coordinator, supervisor, head, lead}`. Confirmed the accepted looseness from the decision (bare `Director`/`Chairman`/`President`/`Treasurer`/`Secretary` also match longer titles containing them, e.g. a hypothetical "Director of Catering") is present but was not one of the 17 measured titles, so it did not need to be exercised by a specific test beyond the existing tail-of-word negative (`Directorate Assistant`, `Directors` as members of a `Director`-only family stay `None`).
- **Decision 3 (existing eight kept verbatim, governance added beneath)** — Implemented; a diff of the first 8 families shows zero byte changes, confirmed by `test_offer_block_evidenced_shows_recurrence_and_omits_disclosure` and `test_the_documented_round_pipeline_drives_its_real_joins_end_to_end` (uses `Head of Broadcast`) both staying green unmodified.
- **Decision 4 (single change point)** — Implemented; `git diff --stat` for this plan touches only `role_classify.py`, `role_vocabulary.yaml`, and the two test files. `scripts/role_vocabulary.py`, `select_people`, `load_families`, `offer_block`, `chosen_families`, `DISCLOSURE_SENTENCE`, and everything under `n8n/` are untouched (confirmed by `git status --porcelain n8n/ scripts/build_cloud_workflows.py scripts/role_vocabulary.py` returning silent).

## Deviations from Plan

None - plan executed exactly as written. Grouping of the 17 measured titles into 9 families followed the plan's suggested grouping essentially verbatim (label names adjusted only for punctuation: `Board & Committee` instead of a slash-delimited `Board/Committee`, to avoid an ambiguous label string — labels are opaque strings compared only for equality in `chosen_families`, never run through the token matcher, so this has no behavioral effect).

## Issues Encountered

The working tree is shared (non-worktree execution, per `gsd-executor-worktrees-break-venv` memory) with the concurrently-running 62-08 plan. `git status` showed unrelated modifications to `test_suggest_contacts_composition.py` and `scripts/uat62_website_survey.py`, and an untracked `scripts/uat62_cluster_probe.py`, none of which this plan's `files_modified` list names or this plan's tasks touched. Verified via `git diff --stat` on this plan's own four files before every commit and staged those four paths explicitly (never `git add -A`), so none of 62-08's concurrent work was pulled into this plan's commits.

## Next Phase Readiness

- G-62-3 is closed: the round's role filter now selects from vocabulary that matches racing-club governance titles, both exactly and partially, without being able to over-match on a shared trailing word.
- G-62-5 (the `scripts/role_vocabulary.py` derivation-script crash) remains open and untouched, as the operator's own sequencing required.
- SUGGEST-03 remains AMENDED (not closed) — the vocabulary is broader but still `evidenced: false`; a future phase deriving the vocabulary from this portal's live `jobtitle` values via `scripts/role_vocabulary.py` (once G-62-5 is fixed) is what would close it.

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-04*

## Self-Check: PASSED

All 4 claimed files exist on disk; both commit hashes (`9197506`, `e401b77`) found in git log.
