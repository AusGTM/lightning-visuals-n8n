---
phase: 62-suggest-the-contacts-nobody-named
reviewed: 2026-09-02T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/tests/test_suggest_contacts.py
  - operator-claude-plugin/tests/test_write_grant_suggestion.py
  - operator-claude-plugin/tests/test_suggest_contacts_composition.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 62 Gap-Closure Review: CR-01 / WR-01

**Reviewed:** 2026-09-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found (one Info-level residual noted; no Critical or Warning findings)

## Verdict

**CR-01: CLOSED.**
**WR-01: CLOSED.**

Both are closed by execution-verified evidence, not just by reading the diff. Commits
`09b8c25` (failing tests first), `cb6458d` (the fix), and `f4f1b2e` (SKILL.md binding +
ratchet + release) do what their messages claim.

## Summary

`synthesise_rows()` now validates `per_company_cap` at the top of the function — the sole
site in the codebase that slices a discovered-people list against a cap — and raises
`suggest_contacts.CapRefused` for anything that is not a plain non-negative `int` (bools
excluded via the `isinstance(x, int) and not isinstance(x, bool)` idiom). `agreed_cap()` is
new: it reads `grant_figures["suggestion_allowance"]["priced_cap"]` and refuses a
`chosen_cap` that is malformed, non-positive, or exceeds the priced ceiling, returning the
chosen cap unchanged otherwise. `SKILL.md` step 3 and step 8's documented code block now
route through `agreed_cap()`'s **return value** (a variable, `per_company_cap`), not a
literal, before calling `synthesise_rows()`. That exact dataflow is exercised by a live
composition test (`test_the_documented_round_pipeline_drives_its_real_joins_end_to_end`,
`test_a_chosen_cap_above_the_priced_cap_refuses_and_synthesises_no_rows`) and by an
end-to-end join against a real `write_grant.envelope()` figures dict
(`test_a_real_envelope_priced_cap_feeds_agreed_cap_and_bounds_synthesise_rows`,
`test_a_real_envelopes_priced_cap_refuses_an_over_priced_chosen_cap`).

## Answering the four verification questions

**1. Can `synthesise_rows` still be reached with `per_company_cap=None` (or negative,
string, bool) and produce rows instead of raising?**

No. Direct-execution probe (not just reading the guard) against a live 5-person fixture:

```
CAP None      -> REFUSED: per_company_cap must be a non-negative int, got None ...
CAP -1        -> REFUSED: per_company_cap must be a non-negative int, got -1 ...
CAP '2'       -> REFUSED: per_company_cap must be a non-negative int, got '2' ...
CAP True      -> REFUSED: per_company_cap must be a non-negative int, got True ...
CAP False     -> REFUSED: per_company_cap must be a non-negative int, got False ...
CAP 1.5       -> REFUSED: per_company_cap must be a non-negative int, got 1.5 ...
CAP []        -> REFUSED: per_company_cap must be a non-negative int, got [] ...
CAP {}        -> REFUSED: per_company_cap must be a non-negative int, got {} ...
CAP inf       -> REFUSED: per_company_cap must be a non-negative int, got inf ...
CAP 1000000000 -> ACCEPTED, rows: 5   (a valid, huge int — see the residual finding below)
```

Every type-confusion input the original CR-01 exploited (`None` → unbounded slice, `-1` →
wrong-end truncation) now refuses. `1e9` "accepts" because it is a legitimate non-negative
int by `synthesise_rows`'s own contract — bounding it against the priced ceiling is
`agreed_cap()`'s job, not `synthesise_rows`'s (see residual finding).

**2. Does `agreed_cap(chosen_cap, grant_figures)` actually refuse a chosen cap above
`priced_cap`, and what does it do with a malformed or unpriced grant dict?**

Yes, and it degrades safely on every malformed shape tried:

```
chosen=2, priced_cap=3            -> ACCEPTED 2
chosen=5, priced_cap=3            -> REFUSED (names both 3 and 5)
figures={"suggestion_allowance": None}   -> REFUSED (never priced)
figures={}                               -> REFUSED (never priced)
figures=None                             -> REFUSED (never priced)
priced_cap=None                          -> REFUSED
priced_cap="3"  (string)                 -> REFUSED
priced_cap=-3                            -> REFUSED
priced_cap=0                             -> REFUSED
suggestion_allowance="not_a_dict"        -> REFUSED
priced_cap=True (bool)                   -> REFUSED
chosen_cap=0                             -> REFUSED ("must be a positive int")
chosen_cap=None                          -> REFUSED
chosen_cap=True                          -> REFUSED
chosen_cap=3.0 (float, numerically equal)-> REFUSED
```

No malformed grant dict or malformed chosen cap slips through to an accepted spend. This
also closes WR-01 as originally reported: the priced-cap comparison now exists in code
(`agreed_cap`), not only as SKILL.md prose.

**3. Is `0` still accepted by `synthesise_rows` while `agreed_cap` requires `1..priced_cap`
— is that boundary split coherent, or does it leave a hole?**

Coherent; no hole. `agreed_cap()` never returns `0` — it raises for any `chosen_cap < 1`.
So `0` reaches `synthesise_rows` only via a direct call that bypasses `agreed_cap()`
entirely, and there it can only **under**-spend (`people[:0]` → `[]`, an empty result,
matching D-62-12's "may spend less" clause). The split is asymmetric but one-directional in
the safe direction: an operator who explicitly asks for a cap of `0` at the `agreed_cap()`
seam gets a verbatim refusal ("must be a positive int") rather than a silent do-nothing
round — a minor UX rough edge, not a defect, and not a path to over-spend.

**4. Is there any other path that reaches the cap slice, or any other truncation site the
guard does not cover?**

Confirmed `synthesise_rows` is still the sole site. `grep -rn "per_company_cap\|people\["
scripts/*.py` (excluding `suggest_contacts.py` itself) turns up exactly two other hits, both
on a different axis:

- `chunking.py:267` — `people[start:start + ceiling]`, chunk-size batching for dispatch
  (an unrelated slice — batches an already-decided record list for HTTP chunking, never
  applies the per-company suggestion cap).
- `cost_guard.py:295` — `stage2_contact_ceiling = count * per_company_cap`, a
  multiplication for the grant-open worst-case price disclosure (`write_grant.envelope()`'s
  `suggestion_allowance` line). It never touches an actual person list and never truncates
  anything; it is priced against `PRICED_CAP` (3) by default or a validated positive int,
  always at grant-open time before the operator has chosen a round-level cap.

Neither is a second truncation site for the actual discovered-people list.

## Info

### IN-01: The economic ceiling binds only at the documented seam, not at the Python call boundary

**File:** `operator-claude-plugin/scripts/suggest_contacts.py:216-240` (also
`skills/suggest-contacts/SKILL.md:71-81, 166-172`, `tests/test_skill_sequence_coverage.py`)

**Issue:** `synthesise_rows()` accepts *any* non-negative `int` for `per_company_cap` — the
`10**9` probe above proves it. Nothing at the Python level forces a caller to route through
`agreed_cap()` first; the priced-cap comparison lives only in `agreed_cap()`, and
`suggest_contacts.py` deliberately carries no `write_grant` import (module-purity decision,
locked at plan time — `agreed_cap()` takes a plain dict specifically so this module never
needs to know about `write_grant`). So the ceiling on real spend is enforced by
documentation plus tests, not by a runtime invariant `synthesise_rows` itself can check.

This is not CR-01 reopened — CR-01's two concrete failure modes (`None` silently uncapping,
`-1` truncating from the wrong end) are both now refused unconditionally, verified above by
direct execution. This is a narrower, structurally-accepted residual: given the production
caller is an LLM orchestrator reading SKILL.md prose at runtime (per this review's own
domain context), a session that skips or misreads step 3 and calls `synthesise_rows`
directly with a hand-picked large cap would not be stopped by any code in this diff.

Currently, the binding *is* genuine where it's tested: SKILL.md's documented block assigns
`per_company_cap = suggest_contacts.agreed_cap(chosen_cap, figures)` and passes that
variable (not `chosen_cap`, not a literal) into `synthesise_rows(...)`, and
`test_the_documented_round_pipeline_drives_its_real_joins_end_to_end` /
`test_a_real_envelope_priced_cap_feeds_agreed_cap_and_bounds_synthesise_rows` execute that
exact dataflow against a real `envelope()` figures dict. But the mechanism pinning this
against future drift — `test_skill_sequence_coverage.py`'s ratchet — only extracts and
compares the **ordered sequence of `module.function` call names** found in a SKILL.md code
block (`parse_calls`, an AST walk keyed on function names only). It does not check that the
argument passed to `synthesise_rows` is the same variable that `agreed_cap` returned. A
future SKILL.md edit that kept `agreed_cap(...)` appearing before `synthesise_rows(...)` in
source order, but rewired the second call to pass `chosen_cap` (or a hardcoded literal)
instead of `agreed_cap()`'s return value, would still satisfy the ratchet's call-sequence
check — the composition test pins its own hand-written code's dataflow, not the SKILL.md
text's dataflow, so it would not catch that specific drift either.

**Fix:** No code change required to close this review's stated scope (CR-01/WR-01 are
closed). If tightened further, options in increasing strength: (a) extend
`test_skill_sequence_coverage.py`'s AST walk to also assert that the argument expression
passed to `synthesise_rows`'s `per_company_cap` parameter is the same `Name` node that
`agreed_cap`'s call was assigned to, closing the "call order preserved, dataflow rewired"
gap; or (b) accept this as a documented, permanent residual of the module-purity decision
(D-62-11/D-62-12) and record it in `suggest_contacts.py`'s or `SKILL.md`'s own commentary
so a future reader does not mistake the current test coverage for a runtime guarantee.

## Evidence

- Full plugin suite: `2259 passed, 5 skipped` (`.venv/bin/python -m pytest
  operator-claude-plugin/tests -q`).
- Targeted CR-01/WR-01 files: `66 passed` (`test_suggest_contacts.py`,
  `test_write_grant_suggestion.py`, `test_suggest_contacts_composition.py`,
  `test_skill_sequence_coverage.py`).
- Direct-execution probes against `synthesise_rows` and `agreed_cap` (both reproduced
  above), run outside the test suite to defeat the guard independently of what the tests
  already assert.
- `grep -n "^import\|^from" scripts/suggest_contacts.py` confirms no `write_grant` import
  (module purity holds).
- `grep -rn "synthesise_rows\|per_company_cap\|people\["
  operator-claude-plugin/scripts/*.py` confirms `synthesise_rows` is the sole truncation
  site for the discovered-people list.
- `.claude-plugin/plugin.json` version (`0.37.0`) and `CHANGELOG.md`'s `[0.37.0]` entry are
  present, in the same commit (`f4f1b2e`), and accurately describe what shipped.

---

_Reviewed: 2026-09-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
