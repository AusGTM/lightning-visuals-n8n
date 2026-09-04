# Phase 64: The ladder stops at the best page, not the first - Pattern Map

**Mapped:** 2026-09-05
**Files analyzed:** 3 (2 modified, 1 prose-only)
**Analogs found:** 3 / 3 (all in-repo, same module family)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/suggest_contacts.py` (new function, e.g. `walk_pages`/`extend_walk`) | service (pure orchestration, bounded iteration) | transform (in-memory candidate list -> accumulated selection) | `search_fallback.eligible_after_ladder` (same file family, disposition-vocabulary pattern) + `suggest_contacts.select_people`/`next_candidates` (same module, reused verbatim) | exact (role) |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (step 5, ~line 101, ~line 299) | config/prose (no code) | n/a | its own prior edit history: `agreed_cap` replaced step 3's cap prose (D-62-11/-12) | exact (same repo precedent) |
| `operator-claude-plugin/tests/test_suggest_contacts.py` (new test cases) | test | transform | `test_suggest_contacts.py::test_company_budget_resets_between_two_companies_in_one_round` / `test_next_candidates_threads_this_companys_own_budget` | exact |

**No new file needs to be created.** The walk's stop predicate is new code inside the
existing `suggest_contacts.py`; nothing here justifies a new module (it is not I/O, not a
distinct domain, and every helper it needs already lives in this file or is already
imported — `role_classify`, `url_fallback`).

## Pattern Assignments

### `operator-claude-plugin/scripts/suggest_contacts.py` — new walk function

**Analog 1 — the "score/select" primitive already exists, reuse verbatim:**
`select_people` at `scripts/suggest_contacts.py:176-206`. `len(select_people(...)["selected"])`
**is** D-64-03's page score. Do not write a second scorer.

```python
# scripts/suggest_contacts.py:176-206
def select_people(people, family_list, chosen_families, known_contacts):
    chosen = set(chosen_families or [])
    known_keys = {
        key for key in (_name_key(c) for c in (known_contacts or [])) if key is not None
    }
    selected = []
    dropped = []
    for person in people:
        key = _name_key(person)
        if key is not None and key in known_keys:
            dropped.append({"person": person, "reason": "already_associated"})
            continue
        family = role_classify.classify_title(person.get("jobtitle"), family_list)
        if family is None or family not in chosen:
            dropped.append({"person": person, "reason": "role_not_selected"})
            continue
        selected.append(dict(person, role_family=family))
    return {"selected": selected, "dropped": dropped}
```

**Analog 2 — the dedupe key (D-64-02), reuse verbatim:**
`_name_key` at `scripts/suggest_contacts.py:161-169`. Union-across-pages dedupe is: for each
new page's people, drop any whose `_name_key(person)` already appears in the accumulated
set's keys, before folding them in. Same normalisation (`_normalize_name`, line 172-173)
underneath.

**Analog 3 — the budget seam a bounded walk threads through, unchanged (D-64-09):**
`company_budget` / `next_candidates` at `scripts/suggest_contacts.py:426-449`. The new walk
function does not invent its own counter — it calls `next_candidates(company_row, attempts,
sitemap_urls)` per step, exactly as the caller (SKILL.md step 5) does today, and stops
threading further candidates once `filter_candidates`'s `refused`/`budget_remaining` says so.

```python
# scripts/suggest_contacts.py:436-449
def next_candidates(company_row, attempts, sitemap_urls):
    pasted_url, reason = _ladder_source(company_row)
    if reason:
        raise ValueError(reason)
    return url_fallback.filter_candidates(
        pasted_url, sitemap_urls, already_fetched=company_budget(attempts)
    )
```

**Analog 4 — the closed disposition/"ended" vocabulary pattern (D-64-08):**
`search_fallback.py:67-74` and `eligible_after_ladder` at `search_fallback.py:171-235`. This
is the exact precedent for "a small closed set of named string constants describing how a
bounded process ended, attached to the result, read by a downstream phase rather than acted
on here." Phase 64's `ended` field (`good_enough` / `ladder_exhausted` / `cap_exhausted` /
`refused`) should follow this same shape: module-level string constants, not free text, and a
docstring explaining what "eligible"/terminal means for each value — mirror the
`DISPOSITION_EMPTY = "empty"` / `DISPOSITION_CAP_EXHAUSTED = "cap_exhausted"` /
`DISPOSITION_REFUSED = "refused"` style at `search_fallback.py:70-72`.

```python
# scripts/search_fallback.py:67-74
DISPOSITION_EMPTY = "empty"
DISPOSITION_CAP_EXHAUSTED = "cap_exhausted"
DISPOSITION_REFUSED = "refused"
ELIGIBLE_DISPOSITIONS = (DISPOSITION_EMPTY, DISPOSITION_CAP_EXHAUSTED)
```

**Analog 5 — bounded iteration, no `while` (D-64-12):**
`url_fallback.py:225-238` (`__main__`'s `for _i, _a in enumerate(_rest)` scan) is the repo's
own comment explaining why a `for` loop over a fixed-length list stands in for a `while`
here — cite this reasoning directly; the walk iterates over `discovery_plan`'s
`candidates`/`next_candidates`'s `accepted` list (each bounded by `MAX_FOLLOWUP_FETCHES`),
so a `for` over that list, breaking early when D-64-05's bar clears, is correct and already
the house style.

**Error/refusal handling pattern (D-64-10):** `next_candidates` raises `ValueError` only for
an unbuildable ladder source (line 447-448); a *refused candidate* is never an exception —
it is data (`filter_candidates`'s `refused` list, `search_fallback`'s `DISPOSITION_REFUSED`).
The walk must carry refusals through the same way: as a terminal `ended` value, never
re-worded, never re-raised.

### `operator-claude-plugin/skills/suggest-contacts/SKILL.md`

**Lines to change:** `~101` ("stopping at the first one that yields people") and `~299`
(references the same rule downstream). **Analog for how to replace prose with a code
citation:** this file's own step 3, which was rewritten to cite `agreed_cap()` instead of
carrying the cap rule as prose (D-62-11/-12) — see `scripts/suggest_contacts.py:218-267`'s
docstring: *"promotes `skills/suggest-contacts/SKILL.md` step 3's prose rule to code"*.
Step 5 should be rewritten the same way: replace "stopping at the first one that yields
people" with a citation to the new walk function and its `BAR = max(len(chosen_families),
agreed_cap)` stop rule (D-64-06), plus a one-line statement that pages accumulate (D-64-01)
rather than the winner replacing.

### Tests — `operator-claude-plugin/tests/test_suggest_contacts.py`

**Analog:** `test_company_budget_resets_between_two_companies_in_one_round` (line 248-252)
and `test_next_candidates_threads_this_companys_own_budget` (line 268-278) — small, pure,
table-style assertions on a dict return, no mocking, no fixtures beyond the existing
`_company_row(...)` helper already defined near the top of the test file. New tests for the
walk should follow this exact shape: build `people` lists inline as plain dicts, call the
new function directly, assert on `["ended"]`, `["selected"]`/accumulated people, and
`["scores"]` if surfaced.

**Run command (from CLAUDE.md's own Memory note "Test suite run commands"):**
```bash
.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -q
node --test tests/n8n/*.test.mjs   # unrelated to this phase, glob form only, not dir form
```

**Constraining test, must still pass unmodified:** `tests/test_report_sufficiency.py`'s
`_has_while_loop` scan (line 221-222, enforced at line 236-237) — the new walk function must
be written as a `for` loop over a bounded list, never a `while`.

## Shared Patterns

### Bounded bar/stop predicate as a pure expression
**Source:** D-64-06's `BAR = max(len(chosen_families), agreed_cap)` has no direct code
analog yet (it's new), but its INPUTS are both already-computed values passed into the
existing call sites — `chosen_families` from `role_classify.chosen_families(vocabulary,
labels)` (`scripts/role_classify.py:108-119`) and `agreed_cap(chosen_cap, grant_figures)`
(`scripts/suggest_contacts.py:218-267`, returns a plain `int`). The walk function should
take both as parameters (or the pre-computed bar as one parameter) — never recompute either
internally, mirroring how `next_candidates` never recomputes `company_budget` itself but
takes `attempts` and calls the one existing helper.

### Refusals and terminal states are read off library output, never invented
**Source:** `url_fallback.filter_candidates`'s `refused` list (`scripts/url_fallback.py:143-197`)
and `search_fallback.eligible_after_ladder`'s disposition switch (`scripts/search_fallback.py:171-235`).
**Apply to:** the walk's `ended` field — `refused` and `cap_exhausted` should be read
straight off `next_candidates`'s return (which is `filter_candidates`'s return, verbatim),
never re-derived from a fetch count the walk keeps itself.

### Docstring register: state the decided-against alternatives and the reversibility cost
**Source:** every function in `suggest_contacts.py` (e.g. `agreed_cap`, `select_people`,
`no_candidates`) opens with a paragraph naming what it does NOT do and why. Follow this for
the new walk function — name that it does not enlarge `MAX_FOLLOWUP_FETCHES` (D-64-09) and
does not act on `ended` itself (D-64-08's boundary).

## No Analog Found

None. Every piece this phase needs — scoring, dedupe key, budget threading, refusal
propagation, closed disposition vocabulary, bounded-iteration idiom, and the SKILL.md
prose-to-code precedent — already exists in this same small module family
(`suggest_contacts.py`, `url_fallback.py`, `search_fallback.py`, `role_classify.py`). This
phase is additive within `suggest_contacts.py`: one new pure function plus a SKILL.md
rewrite, no new files.

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/tests/`,
`operator-claude-plugin/skills/suggest-contacts/`
**Files scanned:** `suggest_contacts.py`, `url_fallback.py`, `role_classify.py`,
`search_fallback.py`, `test_suggest_contacts.py`, `test_report_sufficiency.py`, `SKILL.md`
**Pattern extraction date:** 2026-09-05
