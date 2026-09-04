---
phase: 64-the-ladder-stops-at-the-best-page-not-the-first
reviewed: 2026-09-04T06:56:41Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/tests/test_suggest_contacts.py
  - operator-claude-plugin/tests/test_suggest_contacts_composition.py
findings:
  critical: 1
  warning: 1
  info: 1
  total: 3
status: issues_found
---

# Phase 64: Code Review Report

**Reviewed:** 2026-09-04T06:56:41Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 64 adds `walk_bar`/`walk_pages` to `suggest_contacts.py` and rewrites the SKILL.md
step-5 prose and step-7 code block to drive them. The two new functions are pure, have no
`while` loop, keep no fetch counter of their own, and are well covered by unit tests for
every documented ending (`good_enough`, `refused`, `cap_exhausted`, `ladder_exhausted`,
`None`) when `walk_pages` is fed a **static** `candidates` dict — which is exactly what
every unit test in `test_suggest_contacts.py` does.

The problem is that the **documented caller sequence in `SKILL.md` step 7 does not feed
`walk_pages` a static `candidates` dict.** It re-derives `candidates` via
`suggest_contacts.next_candidates(...)` after every single fetch, and `next_candidates`
(unmodified `url_fallback.filter_candidates`, correctly out of scope for this phase) returns
a budget-truncated **prefix** of the same URL list on every call, not a "what's left"
view. Feeding that shrinking prefix into `walk_pages`'s "unfetched remainder" check causes
the walk to terminate 2-3 fetches early on any company whose ladder offers 4 or more
same-host candidates — silently leaving the `MAX_FOLLOWUP_FETCHES` budget half-spent and,
worse, telling the operator (via step 9's `ladder_exhausted` -> "read every candidate the
ladder offered") that the whole ladder was read when it demonstrably was not. This is
reproducible today by running the SKILL.md's own documented sequence verbatim against real
`suggest_contacts.py`/`url_fallback.py` code (see CR-01) and directly defeats LADDER-01,
the requirement this phase exists to satisfy, for the common case (a sitemap offering more
candidates than fit comfortably under a shrinking recomputed budget).

A second, related defect: `synthesise_rows`'s single `fetched_url` argument is applied to
every person in a company's `walk["selected"]`, but the whole point of D-64-01's union is
that `selected` can now legitimately span more than one page. The threat model (T-64-05)
asserts this per-person attribution is "preserved... a person from `/board/` is not
attributed to `/contact`" — that claim does not hold once a walk spans two pages.

No import changes, no `while` loop, and no `n8n/` diff — those invariants hold.

## Critical Issues

### CR-01: The documented per-company walk loop re-derives `candidates` inside the loop, causing `walk_pages` to declare the ladder exhausted 2-3 fetches before the real `MAX_FOLLOWUP_FETCHES` budget or candidate list is spent

**File:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md:360-378` (the step-7 code
block), interacting with `operator-claude-plugin/scripts/suggest_contacts.py:238-385`
(`walk_pages`, specifically the "unfetched" computation at lines 366-376) and the unmodified
`operator-claude-plugin/scripts/url_fallback.py::filter_candidates`.

**Issue:**

The documented per-company loop is:

```python
pages, attempts = [], []
candidates = suggest_contacts.next_candidates(eligible_company, attempts, sitemap_urls)   # line 361
walk = {"people": [], "selected": [], "ended": None}
for candidate_url in candidates["accepted"]:                                              # line 363
    pages.append({...}); attempts.append({...})
    walk = suggest_contacts.walk_pages(
        pages, candidates, bar, vocabulary["families"], chosen_families, known_contacts)  # line 370
    if walk["ended"] is not None:
        break
    candidates = suggest_contacts.next_candidates(eligible_company, attempts, sitemap_urls)  # line 375
```

Two things are wrong with this, together:

1. The `for candidate_url in candidates["accepted"]:` loop (line 363) binds to the list
   object returned at line 361 **once**, at loop start — reassigning `candidates` at line
   375 has no effect on which URLs actually get fetched (standard Python `for` semantics).
   So this reassignment is not "advancing" the walk to new candidates; its only observable
   effect is on the `candidates` argument passed into the **next** `walk_pages` call.
2. `url_fallback.filter_candidates` (called by `next_candidates`, and correctly untouched
   by this phase) does not track *which specific URLs* have already been fetched — only a
   *count* (`already_fetched`). Each call re-filters the *same* `sitemap_urls` list from
   the front and returns `accepted = urls[:budget_remaining]`, where
   `budget_remaining = max(5 - already_fetched, 0)`. As `attempts` grows by one per real
   fetch, `budget_remaining` shrinks, so **each successive call returns a shorter prefix of
   the same list** — never new URLs further down the list, and, critically, sooner or later
   a prefix that **no longer contains URLs already walked**, at which point
   `walk_pages`'s "unfetched = candidates["accepted"] minus walked" (lines 366-376 of
   `suggest_contacts.py`) reads as empty even though real, unfetched, originally-accepted
   candidates exist and real budget remains unspent.

Reproduction, using only the shipped, unmodified functions (`next_candidates`, `walk_pages`
from `suggest_contacts.py`), run for a company whose ladder offers 5 same-host candidate
URLs (well within `MAX_FOLLOWUP_FETCHES=5`, so this is not a budget question):

```python
import suggest_contacts as sc
company_row = {"row_id": "c1", "name": "X", "website": "https://x.example/contact"}
sitemap_urls = [f"https://x.example/u{i}" for i in range(1, 6)]  # 5 URLs, == the budget
family_list = [{"label": "board", "members": ["Director"]}]
bar = sc.walk_bar(["board"], 3)

pages, attempts = [], []
candidates = sc.next_candidates(company_row, attempts, sitemap_urls)
walk = {"ended": None}
i = 0
for url in list(candidates["accepted"]):
    i += 1
    pages.append({"url": url, "people": [{"firstname": f"P{i}", "lastname": "X", "jobtitle": "nobody"}]})
    attempts.append({"url": url, "outcome": "ok", "disposition": "empty"})
    walk = sc.walk_pages(pages, candidates, bar, family_list, ["board"], known_contacts=[])
    if walk["ended"] is not None:
        break
    candidates = sc.next_candidates(company_row, attempts, sitemap_urls)

print(i, walk["ended"])   # -> 3 ladder_exhausted
```

Output: `3 ladder_exhausted` — the walk stops after 3 fetches, reports `ladder_exhausted`
(step 9 renders this to the operator as **"read every candidate the ladder offered"**), and
never fetches URLs 4 and 5, even though all 5 were originally accepted and none of the
`MAX_FOLLOWUP_FETCHES=5` budget was spent on anything else. This is not an edge case: the
same run with 3, 4, 5, or 10 candidate URLs all stop at exactly 3 (verified). Any company
whose sitemap-derived ladder offers **4 or more** same-host candidates — the realistic case
this phase's own docstring motivates ("a sitemap can list thousands of URLs") — silently
loses its last 1-2 fetches, which is exactly where a `/board/`-style page is likely to sit
in ladder order if it wasn't rung 1-3.

By contrast, `walk_pages` itself is correct: `test_walk_pages_does_not_count_an_already_walked_url_as_remaining`
proves the "unfetched" computation works correctly **when `candidates` is a single, static
snapshot reused across the whole walk** — which is exactly what every existing unit test
does, and exactly what the SKILL.md orchestration does *not* do. No test in either test
file drives the real per-fetch `next_candidates` re-invocation loop with a growing
`attempts` list against more than 2 accepted URLs (`test_suggest_contacts_composition.py`
calls `next_candidates` twice per company at lines 168/171, but always with
`sitemap_urls=[]`, so `accepted` is always empty and the bug never has a chance to
manifest), which is how this shipped with the full suite green (2422+ passed).

This directly undermines LADDER-01 ("the walk continues past the first people-bearing page
when a better candidate remains, under the same fetch budget") for the common case, and
makes step 9's `ladder_exhausted` -> "read every candidate the ladder offered" a false
statement to the operator in that same common case.

**Fix:**

Do not re-derive `candidates` inside the per-company loop. Compute it once, before the
loop starts (as it already is, on line 361), and reuse that same dict for every
`walk_pages` call for this company — exactly what `test_walk_pages_does_not_count_an_already_walked_url_as_remaining`
already assumes and what `walk_pages`'s own "unfetched" logic is designed for:

```python
pages, attempts = [], []
candidates = suggest_contacts.next_candidates(eligible_company, attempts, sitemap_urls)
walk = {"people": [], "selected": [], "ended": None}
for candidate_url in candidates["accepted"]:
    pages.append({...}); attempts.append({...})
    walk = suggest_contacts.walk_pages(
        pages, candidates, bar, vocabulary["families"], chosen_families, known_contacts)
    if walk["ended"] is not None:
        break
    # candidates is NOT re-derived here -- the walk's own `people`/`pages` accounting
    # against the ORIGINAL accepted list is what makes "unfetched" correct.
```

If the intent behind the re-derivation was to let `sitemap_urls` grow mid-walk (e.g. new
URLs discovered from a fetched sitemap page), that needs a different mechanism — appending
newly discovered URLs to the same list does not fix the prefix-truncation problem, since
`filter_candidates` still returns `urls[:budget_remaining]` from the front on every call.
At minimum, add an integration-style test that drives the real loop (real
`next_candidates` re-invocation or its removal) over a fixture with >= 4 same-host
candidate URLs and asserts the walk actually reaches candidate 4/5 before terminating —
none of the current tests would have caught this.

## Warnings

### WR-01: A synthesised row's provenance `locator` no longer names the page a person actually came from once a walk spans more than one page

**File:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md:377`
(`fetched_url = pages[-1]["url"] if pages else plan.get("pasted_url")`), consumed by
`operator-claude-plugin/scripts/suggest_contacts.py:449-543` (`synthesise_rows`, which takes
a single `fetched_url` and stamps it as `provenance.locator` for every row in the call).

**Issue:** D-64-01 makes it routine for `walk["selected"]` to contain people drawn from
more than one fetched page (a receptionist from `/contact` plus officers from `/board/`).
`synthesise_rows` still accepts exactly one `fetched_url` string and applies it uniformly
to every person passed in. The documented caller sets that one locator to
`pages[-1]["url"]` — the **last** page fetched — so any selected person who actually came
from an earlier page (e.g. the receptionist from `/contact`, if their title happened to
match a chosen family) is stamped with the `/board/` page as their source, not the page
they were actually found on.

This directly contradicts the phase's own threat-model claim, T-64-05: *"`synthesise_rows`
already stamps the URL actually fetched as each record's provenance locator, and Task 3
preserves that semantics under the union... A person from `/board/` is not attributed to
`/contact`. No change needed."* That claim was true under the old one-page-per-company
model; it is not preserved under the new union model, because `synthesise_rows`'s
single-locator-per-call signature was never changed to carry a per-person locator. It also
gets actively worse if the walk ends via a refusal: `pages[-1]` can then be the **refused**
page (which contributed zero people), so every selected person from earlier, successfully
fetched pages would be attributed to a page that yielded nothing.

**Fix:** Either (a) change `synthesise_rows` to accept a per-person locator (each person
already carries, or could carry, the URL of the page it was folded from, since
`walk_pages` knows this at fold time), or (b) if the operator/report use of this field
tolerates "last page fetched for this company" as an approximation, say so explicitly in
the docstring/threat-model instead of the current unconditional claim, and drop the
`pages[-1]` fallback to a refused page specifically (fall back to the last page that
actually contributed to `walk["selected"]` instead).

## Info

### IN-01: No integration test exercises the real, documented per-company fetch loop end to end

**File:** `operator-claude-plugin/tests/test_suggest_contacts.py`,
`operator-claude-plugin/tests/test_suggest_contacts_composition.py`

**Issue:** Every `walk_pages` test constructs `pages` and `candidates` by hand and passes a
single, static `candidates` dict, which is correct for unit-testing `walk_pages` in
isolation but never exercises the caller loop documented in SKILL.md step 7 (the loop that
re-derives `candidates` via repeated `next_candidates` calls). The one composition test
that does call `next_candidates` twice (`test_suggest_contacts_composition.py:168,171`)
uses `sitemap_urls=[]` both times, so `accepted` is always empty and the interaction never
gets a chance to fail. This gap is what let CR-01 ship with the full suite green.

**Fix:** Add a test (in `test_suggest_contacts_composition.py`, alongside the existing
"drives the real joins end to end" tests) that follows the SKILL.md step-7 loop verbatim —
including the `candidates = suggest_contacts.next_candidates(...)` line inside the loop, or
its removal per CR-01's fix — over a fixture with `sitemap_urls` carrying 4+ same-host
URLs, and asserts how many of them actually get walked before `ended` is set.

---

_Reviewed: 2026-09-04T06:56:41Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
