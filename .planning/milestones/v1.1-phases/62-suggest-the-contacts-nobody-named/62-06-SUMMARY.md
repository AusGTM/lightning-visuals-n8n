---
phase: 62-suggest-the-contacts-nobody-named
plan: 06
subsystem: enrichment
tags: [suggest-contacts, cost-safety, gap-closure, python]

requires:
  - phase: 62-01
    provides: "suggest_contacts.synthesise_rows() -- the sole function that applies the per-company cap, now guarded"
  - phase: 62-03
    provides: "write_grant.envelope()'s figures['suggestion_allowance']['priced_cap'] -- the priced ceiling agreed_cap() checks against"
  - phase: 62-05
    provides: "skills/suggest-contacts/SKILL.md's documented round sequence and its test_skill_sequence_coverage census entry, both amended here"
provides:
  - "suggest_contacts.CapRefused: the exception raised by both enforcement points"
  - "suggest_contacts.agreed_cap(chosen_cap, grant_figures): refuses an operator-chosen cap above the grant's priced ceiling, or a round the grant never priced, naming both numbers"
  - "a hard guard inside synthesise_rows() refusing a non-int/bool/negative per_company_cap at the sole site that applies it"
affects: []

actuals:
  tokens: 5717
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "refuse-never-fallback at spend time, contrasted deliberately with envelope()'s own refuse-and-default-to-PRICED_CAP at grant-open time"
    - "isinstance-excludes-bool guard shape mirrored from write_grant.envelope()'s existing suggestion_cap validation"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_write_grant_suggestion.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json

key-decisions:
  - "agreed_cap() lives in suggest_contacts.py, not write_grant.py -- it reads a plain grant_figures dict and needs no write_grant import, keeping suggest_contacts.py's asserted purity (no HTTP client) intact."
  - "The two validations are deliberately asymmetric and NOT harmonized: synthesise_rows' guard accepts any int >= 0 (0 is legal -- spending nothing), agreed_cap requires 1..priced_cap inclusive (an operator's chosen cap, mirroring envelope()'s own suggestion_cap > 0 check)."
  - "Refuse, never default, at spend time -- the opposite of envelope()'s grant-open-time fallback to PRICED_CAP, because a silent default at spend time would spend against a number the operator never saw."
  - "SKILL.md step 3 stays prose-plus-one-call, not a second python fence, so the sequence-coverage census gains exactly one new identity (agreed_cap inserted into the existing suggest-contacts key) rather than a second registered sequence."

requirements-completed: [SUGGEST-05]

coverage:
  - id: D1
    description: "synthesise_rows() refuses a None, negative, string, or bool per_company_cap at the sole site that applies the cap, instead of uncapping (None -> 5/5) or truncating from the wrong end (-1 -> 4/5); a cap of 0 stays legal and returns no rows"
    requirement: SUGGEST-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_synthesise_rows_refuses_a_none_cap_rather_than_uncapping"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_synthesise_rows_refuses_a_negative_cap_rather_than_truncating_the_wrong_end"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_synthesise_rows_refuses_a_string_cap"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_synthesise_rows_refuses_a_bool_cap"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_synthesise_rows_zero_cap_is_legal_and_returns_no_rows"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_synthesise_rows_honors_per_company_cap"
        status: pass
    human_judgment: false
  - id: D2
    description: "agreed_cap() refuses an operator-chosen cap above the grant's priced_cap, naming both numbers in code -- promoting SKILL.md step 3's prose rule -- and refuses when the grant never priced a suggestion allowance at all; a cap at or below the priced cap returns unchanged"
    requirement: SUGGEST-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_agreed_cap_refuses_a_chosen_cap_above_the_priced_cap_naming_both_numbers"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_agreed_cap_returns_chosen_cap_when_equal_to_priced_cap"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_agreed_cap_refuses_when_suggestion_allowance_is_none"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_agreed_cap_refuses_when_suggestion_allowance_is_absent"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_a_real_envelope_priced_cap_feeds_agreed_cap_and_bounds_synthesise_rows"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_a_real_envelopes_priced_cap_refuses_an_over_priced_chosen_cap"
        status: pass
    human_judgment: false
  - id: D3
    description: "the documented round sequence in SKILL.md passes agreed_cap()'s returned int (never a literal, never chosen_cap directly) as synthesise_rows' cap argument, and that join is driven by a registered composition test so the rule cannot regress back to prose"
    requirement: SUGGEST-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts_composition.py#test_the_documented_round_pipeline_drives_its_real_joins_end_to_end"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts_composition.py#test_a_chosen_cap_above_the_priced_cap_refuses_and_synthesises_no_rows"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py (full suite, suggest-contacts COVERED key)"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-09-02
status: complete
---

# Phase 62 Plan 06: Close the per-company cap gap Summary

**`suggest_contacts.CapRefused` + `suggest_contacts.agreed_cap()`: the per-company cap that bounds a suggestion round's stage-2 provider spend is now validated in code at the sole function that applies it, and an operator-chosen cap above the grant's priced ceiling is refused by a real function instead of by SKILL.md prose alone — closing the gap `62-VERIFICATION.md`/`62-REVIEW.md` independently found and live-reproduced (CR-01/WR-01).**

## Performance

- **Duration:** ~40 min
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- `suggest_contacts.CapRefused` (a `ValueError` subclass) is now raised at both enforcement points, with a docstring naming D-62-12's invariant and stating that a refusal is deliberate, never a clamp or a silent fallback.
- `suggest_contacts.agreed_cap(chosen_cap, grant_figures)` reads `grant_figures["suggestion_allowance"]["priced_cap"]` and refuses (raising `CapRefused`, naming both numbers) when the chosen cap exceeds the priced ceiling, when `chosen_cap` is not a plain int `>= 1`, or when the grant never priced a suggestion allowance at all. It introduces no `write_grant` import — `suggest_contacts.py`'s asserted purity (`test_suggest_contacts_module_is_pure_no_http_client`) is unchanged.
- `synthesise_rows()` now validates `per_company_cap` before any slicing — the two live-reproduced defects (`None` uncapping the round to 5/5 rows, `-1` truncating the wrong end to 4/5) both now raise `CapRefused`. `per_company_cap=0` stays legal and returns `[]` (spending less than the cap is never refused).
- `skills/suggest-contacts/SKILL.md` step 3 now names the code enforcing the refusal, and its one documented python block binds `agreed_cap()`'s return value as the only number the rest of the round spends against.
- `test_skill_sequence_coverage.py`'s `suggest-contacts` COVERED key gained `suggest_contacts.agreed_cap` between `select_people` and `synthesise_rows` (one entry, not a second), and `test_suggest_contacts_composition.py` now drives that join with a real figures dict plus a dedicated refusal-direction test.
- Released as plugin `0.37.0` with a CHANGELOG entry naming CR-01/WR-01.

## Task Commits

Task 1 followed RED (failing test) then GREEN (implementation):

1. **Task 1: Refuse a cap the operator never agreed to** — `09b8c25` (test) → `cb6458d` (feat)
2. **Task 2: Put the refusal in the round the sitting actually runs, and pin it against decay** — `f4f1b2e` (fix: SKILL.md + composition test + census key + CHANGELOG + version bump, one commit per plan's own task grouping)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified

- `operator-claude-plugin/scripts/suggest_contacts.py` — `CapRefused`, `agreed_cap()`, and the guard at the top of `synthesise_rows()`
- `operator-claude-plugin/tests/test_suggest_contacts.py` — regression tests for `None`/`-1`/`"2"`/`True`/`0` caps and `agreed_cap()`'s boundary/refusal behavior
- `operator-claude-plugin/tests/test_write_grant_suggestion.py` — the end-to-end join test: a real `envelope()` figures dict feeding `agreed_cap()` feeding `synthesise_rows()`, plus the refusal direction
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — step 3 names the enforcing code; the documented python block binds `agreed_cap()`'s return value
- `operator-claude-plugin/tests/test_suggest_contacts_composition.py` — the registered composition test now drives the result-consuming `agreed_cap` → `synthesise_rows` join, plus a new over-priced-cap refusal test
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — the `suggest-contacts` COVERED key gained `suggest_contacts.agreed_cap`
- `operator-claude-plugin/CHANGELOG.md` — `[0.37.0]` Fixed entry naming CR-01/WR-01
- `operator-claude-plugin/.claude-plugin/plugin.json` — version `0.36.0` → `0.37.0`

## Decisions Made

- **`agreed_cap` lives in `suggest_contacts.py`, not `write_grant.py`** — it reads a plain `grant_figures` dict, so it needs no `write_grant` import, and keeps the module's asserted no-HTTP-client purity intact. The end-to-end test that feeds a real envelope's figures into it lives in `test_write_grant_suggestion.py`, which already has the `_envelope()`/`HEADROOM` helpers.
- **Deliberate asymmetry, not harmonized:** `synthesise_rows`' guard accepts any int `>= 0` (0 is legal — spending nothing is never refused); `agreed_cap` requires `1..priced_cap` inclusive (an operator's chosen cap, mirroring `envelope()`'s own `suggestion_cap > 0` check). Both exclude `bool` via the same `isinstance(x, int) and not isinstance(x, bool)` shape `write_grant.envelope()` already uses.
- **Refuse, never default, at spend time** — the opposite of `envelope()`'s grant-open-time fallback to `PRICED_CAP`. At grant-open nothing has spent yet, so a safe default is fine; at spend time, defaulting would spend against a cap the operator never saw.
- **SKILL.md step 3 stays prose-plus-one-call** rather than a second fenced python block, so the sequence-coverage ratchet gains exactly one new identity in the existing `suggest-contacts` COVERED key instead of registering a second pipeline needing its own composition test.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This plan touches only local Python source, test, and Markdown files, plus a version bump and a CHANGELOG entry. No HubSpot credentials, no provider credentials, no network calls, nothing armed or deployed.

## Next Phase Readiness

- All three `missing:` items from `62-VERIFICATION.md`'s single failed truth are closed in code: the type/range guard on `per_company_cap`, the chosen-cap-vs-priced-cap comparison function, and regression tests for `None`/negative caps.
- The one `✗ NOT WIRED` key link in `62-VERIFICATION.md` ("operator-chosen `per_company_cap` → grant's priced `suggestion_allowance["priced_cap"]` → code-enforced refusal") is now wired: `agreed_cap()`.
- The three `human_verification` items carried in `62-VERIFICATION.md`'s frontmatter (a real sitemap yielding a usable people page, a real stage-1→stage-2 handoff, and the priced ceiling holding in a live sitting) remain out of this plan's scope by design — irreducibly manual, never claimed here.
- Re-verification of Phase 62 is expected to land `human_needed` (those three manual-only items), not a further `gaps_found` on the cap invariant.
- No blockers. Suites at close: root `.venv/bin/python -m pytest -q` 3929 passed / 154 skipped (>= 3912 baseline, 0 failed); `operator-claude-plugin/tests` 2259 passed / 5 skipped (>= 2242 baseline); `node --test tests/n8n/*.test.mjs` 862 pass / 0 fail (unchanged — this plan touches no n8n code).

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-02*

## Self-Check: PASSED
- FOUND: operator-claude-plugin/scripts/suggest_contacts.py
- FOUND: operator-claude-plugin/tests/test_suggest_contacts.py
- FOUND: operator-claude-plugin/tests/test_write_grant_suggestion.py
- FOUND: operator-claude-plugin/skills/suggest-contacts/SKILL.md
- FOUND: operator-claude-plugin/tests/test_suggest_contacts_composition.py
- FOUND: operator-claude-plugin/tests/test_skill_sequence_coverage.py
- FOUND: operator-claude-plugin/CHANGELOG.md
- FOUND: operator-claude-plugin/.claude-plugin/plugin.json
- FOUND commits 09b8c25, cb6458d, f4f1b2e (all present in `git log --oneline`)
- Re-ran `.venv/bin/python -m pytest -q`: 3929 passed, 154 skipped, 0 failed (>= 3912 baseline)
- Re-ran `.venv/bin/python -m pytest operator-claude-plugin/tests -q`: 2259 passed, 5 skipped, 0 failed (>= 2242 baseline)
- Re-ran `node --test tests/n8n/*.test.mjs`: 862 pass, 0 fail
- Re-ran all task-level acceptance-criteria greps and live-code checks: all pass
