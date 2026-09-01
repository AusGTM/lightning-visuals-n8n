---
phase: 62-suggest-the-contacts-nobody-named
reviewed: 2026-09-01T23:57:27Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - n8n/code/mergeContacts.js
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/config/cost_rates.json
  - operator-claude-plugin/config/role_vocabulary.yaml
  - operator-claude-plugin/scripts/cost_guard.py
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/role_classify.py
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/tests/test_cost_guard_suggestion.py
  - operator-claude-plugin/tests/test_dispatch_multipart.py
  - operator-claude-plugin/tests/test_outcome_contract.py
  - operator-claude-plugin/tests/test_role_vocabulary.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/tests/test_suggest_contacts_composition.py
  - operator-claude-plugin/tests/test_suggest_contacts.py
  - operator-claude-plugin/tests/test_write_grant_suggestion.py
  - scripts/build_cloud_workflows.py
  - scripts/role_vocabulary.py
  - tests/n8n/mergeContacts.test.mjs
  - tests/n8n/outcomeContractFlow.test.mjs
  - tests/n8n/suggestionProvenanceFlow.test.mjs
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 62: Code Review Report

**Reviewed:** 2026-09-01T23:57:27Z
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 62 adds an operator-attended "suggest the contacts nobody named" round: eligibility
scoring, a sitemap-based discovery ladder (reused, not reimplemented), a role-family
filter/dedupe, per-field provenance threaded through `mergeContacts.js` and the generated
n8n workflows, an `envelope()`/`plan_grant()` cost widening for the round's worst-case
ceiling, and a repo-root read-only role-vocabulary inventory script. The code is
carefully cross-referenced against its own prior decisions (D-62-xx), the automated test
suite for the new surface is thorough (96 Python + 38 Node assertions, all reviewed and
run — all green), and the project invariants called out in this review's domain context
(no plugin-side HubSpot credentials, no vendor people-search call, no backend
`web_fetch`, per-field provenance carried at request level, nothing deploying/arming
live writes) all hold under direct inspection.

The one gap that matters: the round's own per-company cap — the number that is supposed
to bound how many people get spent on stage-2 provider enrichment per company — is never
validated at the one function that actually applies it. `suggest_contacts.synthesise_rows`
slices `people[:per_company_cap]` with no type or range check; a `None` cap silently
removes the cap entirely rather than refusing or falling back to a safe default, which
directly contradicts this phase's own explicit design rule ("a cap above the grant's
priced cap is refused, naming the number... it may never spend more"). This is proven
live (not merely inferred) in the Verified section below. Two related, lower-severity
gaps compound it: nothing in code enforces that the operator's chosen cap does not exceed
the grant's already-priced ceiling (that rule exists only as `SKILL.md` prose), and the
new repo-root inventory script that seeds the role vocabulary ships with zero test
coverage of its own pure logic.

## Critical Issues

### CR-01: `suggest_contacts.synthesise_rows` silently removes the per-company cap on a bad argument instead of refusing

**File:** `operator-claude-plugin/scripts/suggest_contacts.py:158-195`
**Issue:** The per-company cap is the mechanism the whole suggestion round relies on to
bound stage-2 provider spend (`SKILL.md` step 3: "the per-company cap, default 2"; step 3
again: "The round may spend LESS than the priced cap; it may never spend more"). It is
applied with a bare Python slice and no validation at all:

```python
def synthesise_rows(company, people, fetched_url, per_company_cap):
    ...
    for person in people[:per_company_cap]:
```

Verified live against the shipped module:

```
cap=None -> 5 rows synthesised (should be capped, is it?)
cap=-1   -> 4 rows synthesised
```

`people[:None]` in Python means "no upper bound at all" — passing `None` (an entirely
plausible failure mode: the orchestrating assistant simply forgetting to thread the cap
it asked the operator for, or a stage upstream returning `None` instead of the chosen
int) does not raise, does not fall back to the documented default of 2, and does not
refuse — it silently uncaps the round, spending stage-2 provider credit on every person
discovered instead of the priced ceiling. A negative cap doesn't raise either; it just
drops the wrong end of the list (`people[:-1]`), which is confusing and unbounded-costwise
equally wrong once `abs(per_company_cap)` exceeds `len(people)`... but the unbounded-`None`
case is the one that actually defeats cost control entirely.

This is a direct violation of the domain rule stated for this phase ("a cap that would be
exceeded must be REFUSED, not silently clamped") — here it isn't even clamped, it's
removed. It is also inconsistent with this same phase's own more defensive code:
`write_grant.envelope()`'s `suggestion_cap` handling explicitly validates
(`isinstance(suggestion_cap, int) and not isinstance(suggestion_cap, bool) and
suggestion_cap > 0`) and falls back to `PRICED_CAP` on anything else — the exact guard
this function is missing.

No existing test exercises `per_company_cap=None` or a negative value;
`test_synthesise_rows_honors_per_company_cap` only proves the happy path (`per_company_cap=2`).

**Fix:**
```python
def synthesise_rows(company, people, fetched_url, per_company_cap):
    if not (isinstance(per_company_cap, int) and not isinstance(per_company_cap, bool)
            and per_company_cap >= 0):
        raise ValueError(
            f"per_company_cap must be a non-negative int, got {per_company_cap!r} — "
            f"refusing rather than silently uncapping or clamping the round's spend."
        )
    ...
    for person in people[:per_company_cap]:
```
Add regression tests for `per_company_cap=None` (must raise, never uncap) and a negative
value (must raise, never truncate from the wrong end).

## Warnings

### WR-01: The operator's chosen per-company cap is never checked against the grant's priced cap in code

**File:** `operator-claude-plugin/scripts/write_grant.py:415-587` (envelope/pricing),
`operator-claude-plugin/scripts/suggest_contacts.py:158-195` (the only place a cap is
actually applied)
**Issue:** `skills/suggest-contacts/SKILL.md` step 3 states the rule plainly: "A cap
above the grant's priced cap is refused, naming the number... The round may spend LESS
than the priced cap; it may never spend more." This is the phase's stated mechanism for
keeping the round's actual spend inside what the operator already agreed to at grant-open.
But that comparison — operator-chosen cap vs. `figures["suggestion_allowance"]["priced_cap"]`
— exists only as instructional text for the assistant to follow; there is no function
anywhere in `write_grant.py`, `cost_guard.py`, or `suggest_contacts.py` that performs it.
Nothing stops a chosen cap of, say, 5 from reaching `synthesise_rows` even though the
grant was priced at 3 — the refusal depends entirely on the LLM orchestrator reading and
obeying the prose correctly, every time, with no code backstop.
**Fix:** Give `suggest_contacts.py` (or `write_grant.py`) a small pure function that
takes the chosen cap and the grant's `suggestion_allowance["priced_cap"]` and returns a
refusal when the chosen cap exceeds it, and call it before `synthesise_rows` runs for any
company in the round — mirroring the hard, code-enforced refusals this same file already
uses elsewhere (e.g. `plan_grant`'s `CEILING_OVER` refusal, `open_grant`'s exact-string
confirmation gate) rather than leaving this one rule as SKILL.md-only.

### WR-02: `scripts/role_vocabulary.py` (new module, Phase 62) has no test coverage of its own logic

**File:** `scripts/role_vocabulary.py:1-229`
**Issue:** This file is new in this phase and is the sole producer of the vocabulary
`role_classify.py` (and therefore the whole round's role filter) reads. None of its pure,
easily-testable functions — `rank_top_families` (drops model-invented members, sorts by
recurrence, truncates to `TOP_N_FAMILIES`), `build_generic_fallback`,
`build_portal_vocabulary`, or the `SPARSE_THRESHOLD` branch in `main()` — has a test
anywhere in the repo (`grep -rl role_vocabulary tests/` and the plugin's test tree both
come back empty). It mirrors `scripts/inventory_org_type_values.py`'s own precedent of
shipping untested (also confirmed empty), so this is a repo-wide convention rather than a
one-off omission — but `rank_top_families`'s defensive "drop any member the model
returned that was not actually in the sampled titles" backstop is exactly the kind of
logic this repo's own testing culture (evidenced everywhere else in this phase) would
normally pin with a unit test.
**Fix:** Add a `tests/test_role_vocabulary.py` (repo root) covering
`rank_top_families` (recurrence ordering, top-N truncation, model-hallucinated-member
drop) and `build_generic_fallback`/`build_portal_vocabulary`'s shape, at minimum.

### WR-03: `cluster_titles` has no retry/repair on invalid JSON, unlike this repo's documented Anthropic-failure policy

**File:** `scripts/role_vocabulary.py:114-130`
**Issue:** `cluster_titles` makes one Haiku call and does `json.loads(text)` with no
try/except and no repair-retry. `CLAUDE.md` section 26.3 ("Anthropic failures") documents
this repo's own policy for exactly this case: "Haiku invalid JSON -> Retry once with
repair prompt." A malformed response (truncation, a stray code fence the regex in
`web_research.py`'s sibling function already defends against, etc.) crashes `main()` with
a raw traceback instead of falling back to the disclosed generic vocabulary the module
already has a builder for (`build_generic_fallback`). Low operational stakes (this is an
offline, admin-run inventory script, not the live enrichment webhook path), but it is a
real deviation from the project's own stated failure-handling contract, and a ready-made
safe fallback already exists one function away.
**Fix:** Wrap the `json.loads` in a try/except that either retries once with a repair
prompt (matching CLAUDE.md's own policy) or falls back to
`build_generic_fallback(distinct_titles_sampled=len(counts))` with a clearly printed
reason, rather than letting the script crash.

## Info

### IN-01: `synthesise_rows`'s negative-cap behavior (`people[:-1]`) is silently the wrong kind of wrong

**File:** `operator-claude-plugin/scripts/suggest_contacts.py:171`
**Issue:** Covered by CR-01's fix, noted separately because it's a distinct failure mode:
a negative `per_company_cap` (e.g. `-1`) doesn't raise or refuse either — Python slicing
interprets it as "all but the last N", so the function silently emits `len(people) - 1`
rows rather than 0 or an error. Once CR-01's validation guard is added this case is
covered for free (a negative value fails the `>= 0` check), so no separate fix is needed
beyond CR-01's.
**Fix:** Subsumed by CR-01.

### IN-02: `test_suggest_contacts_composition.py`'s worked example uses value equality to distinguish held rows from sendable ones

**File:** `operator-claude-plugin/tests/test_suggest_contacts_composition.py:125-143`
(mirrors the identical pattern in `skills/suggest-contacts/SKILL.md`'s own documented
python block, step 8)
**Issue:** Both the test and the (illustrative, non-executed) SKILL.md example determine
whether a record was held or is sendable with `record["row"] not in sendable` — a Python
`in` check over a list of dicts, which is a value-equality test, not an identity test. If
two distinct discovered people ever produced byte-identical row dicts (same
firstname/lastname/jobtitle/company, both still emailless or both later gaining the same
provider-filled fields), this pattern could misclassify one as sendable when it is
actually the held twin, or vice versa. Low real-world likelihood (name collisions with
identical job titles at the same company), and it's documentation/test code rather than
a runtime code path, so this is informational rather than a defect to fix under this
review's scope — flagged so a future implementation of the documented sequence in real
(non-test) orchestration code doesn't inherit the same by-value join.
**Fix:** None required for this review; worth keeping in mind if this documented sequence
is ever promoted into a real Python module — join by a stable row identifier instead of
dict equality at that point.

---

_Reviewed: 2026-09-01T23:57:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
