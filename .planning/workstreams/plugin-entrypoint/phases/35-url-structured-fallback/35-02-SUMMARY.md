---
phase: 35-url-structured-fallback
plan: 02
subsystem: ingestion
tags: [python, ast, provenance, contract-test, extraction-md, wordpress-rest]

requires:
  - phase: 35-url-structured-fallback
    provides: "35-01's url_fallback.py (plan_ladder, same_host, filter_candidates, give_up_message, MAX_FOLLOWUP_FETCHES) and the rewritten 'Fetched but nothing usable' branch of extraction.md"
provides:
  - "extraction.md's URL adapter: a Provenance locator bullet requiring a ladder-sourced row to name the URL actually fetched (not the pasted URL), a Named empty outcome bullet, an explicit same-host-bound sentence, and a literal cap-quoting phrase ('at most 5 follow-up fetches total')"
  - "extraction.md's screenshot adapter: its provenance sentence reformatted into the same bolded 'Provenance locator' bullet shape the other three adapters use"
  - "tests/test_url_fallback.py: an AST-based import-set guard (root allowlist + granular dotted-forbidden-name check + open()-outside-__main__ check) proving url_fallback.py cannot reach the network, by construction"
  - "tests/test_extraction_contract.py: 7 new contract assertions pinning extraction.md's URL adapter against url_fallback.py by construction (script named, escalation confined to the nothing-usable region, cap parity, same-host bound named, no-same-URL-retry rule named, client-rendered verdict absent from the whole file)"
affects: [35-03-live-walk-and-release]

actuals:
  tokens: 4367
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Structural placement test via a shared region-slicing helper (_url_adapter_regions): splits extraction.md at literal bullet headings once, so every placement assertion reads off one shared slice and a heading rename fails in exactly one place"
    - "AST import-set guard as a root allowlist (coarse, subset check) PLUS a granular dotted-name forbidden set (urllib.request specifically) — the coarse check alone cannot see the difference between urllib.parse and urllib.request since both share the allowlisted root 'urllib'"

key-files:
  created: []
  modified:
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/tests/test_url_fallback.py
    - operator-claude-plugin/tests/test_extraction_contract.py

key-decisions:
  - "The cap-parity test cannot be a bare `str(cap) in text` substring check: extraction.md's URL adapter section also contains the literal requirement ID '(INGEST-06)', so at cap=6 a bare digit search passes by coincidence on an unrelated requirement number rather than on genuine cap-quoting text. Caught live by this plan's own mandated red-check (raise the cap, confirm the test fails) — it didn't fail, which is what surfaced the bug. Fixed by pinning to the literal phrase 'at most {cap} follow-up fetches', with extraction.md's prose amended to actually contain that phrase (it previously only said 'the cap it names', deferring to the CLI's runtime output) and whitespace normalized in the test since markdown line-wraps the phrase across two lines."
  - "The import-set guard is two independent assertions, not one: a coarse root-allowlist subset check ({json, sys, pathlib, urllib}) and a granular exact-dotted-name forbidden check (urllib.request, requests, httpx, selenium, playwright, bs4, subprocess, socket, http.client). Proven live by red-check: `from urllib.request import urlopen` PASSES the coarse check (its root 'urllib' is allowlisted for urllib.parse) and FAILS the granular check by exact name — demonstrating why the granular layer is load-bearing, not redundant."
  - "The screenshot adapter's provenance sentence was reformatted into the same bolded '- **Provenance locator:**' bullet shape the other three adapters use. It previously read as inline prose ('Provenance locator names the image...') with a mid-sentence line wrap that split the words 'Provenance' and 'locator' onto separate lines — invisible to a human reader but meant grep -c 'Provenance locator' undercounted it by one, so the acceptance criterion requiring 4 could not be met without this fix."

requirements-completed: [INGEST-06, STRUCT-03, STRUCT-04]

coverage:
  - id: D1
    description: "A row sourced from a ladder rung (e.g. a wp-json endpoint) is instructed to record the URL that actually returned it in provenance.locator, not the pretty page URL the operator pasted — extraction.md's Provenance locator bullet states this explicitly, with a wp-json example"
    requirement: STRUCT-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_first_fenced_example_artifact_is_accepted_by_the_real_validator_with_no_rejects"
        status: pass
      - kind: other
        ref: "grep -c 'Provenance locator' extraction.md == 4 (one per adapter); grep -n 'actually returned the row' + 'wp-json' both present in the URL adapter's Provenance locator bullet"
        status: pass
    human_judgment: false
  - id: D2
    description: "The AST import-set guard on url_fallback.py: a coarse root-allowlist subset check and an independent granular dotted-name check, together proving the module cannot reach the network by construction (T-35-06)"
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py::test_url_fallback_import_set_is_a_subset_of_the_pure_stdlib_allowlist"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py::test_url_fallback_never_imports_a_named_forbidden_capability"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py::test_url_fallback_calls_open_only_inside_the_main_guard"
        status: pass
    human_judgment: false
  - id: D3
    description: "extraction.md's URL adapter names url_fallback.py only in the 'Fetched but nothing usable' region, never in the 'Fetch failed' (tool-error) region — a structural placement test slicing the file at its two literal bullet headings (T-35-08)"
    requirement: INGEST-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_url_fallback_py_is_named_only_in_the_nothing_usable_region_never_in_tool_error"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_tool_error_region_states_that_branch_ends_there"
        status: pass
    human_judgment: false
  - id: D4
    description: "The cap the operator is quoted in extraction.md ('at most 5 follow-up fetches') is imported from url_fallback.MAX_FOLLOWUP_FETCHES, never typed into the test as a bare literal (T-35-09)"
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_url_adapter_quotes_the_same_cap_url_fallback_enforces"
        status: pass
    human_judgment: false
  - id: D5
    description: "The disproven 'likely a client-rendered page' verdict is absent from extraction.md entirely, checked against the whole file (T-35-10)"
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py::test_client_rendered_verdict_is_nowhere_in_extraction_md"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-05
status: complete
---

# Phase 35 Plan 02: URL Structured-Representation Fallback — Provenance and Contract Pins Summary

**Pinned three fences with tests that fail loudly if a later edit removes them (import-set guard on `url_fallback.py`, structural placement of the escalation instruction, cap parity between prose and code) and made a ladder-sourced row's provenance name the URL it actually came from, not the URL the operator pasted.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3
- **Files modified:** 3 (`extraction.md`, `test_url_fallback.py`, `test_extraction_contract.py`)

## Accomplishments

- `extraction.md`'s URL adapter now carries a **Provenance locator** bullet stating that a row from an escalation rung names the URL that *actually returned it* — in full, with the wp-json example — not the pretty page URL the operator pasted, plus where in that response the row was read. A **Named empty outcome** bullet ties an exhausted ladder to `url_fallback.py`'s give-up message as a named result, per INGEST-06.
- Every one of the four adapters in `extraction.md` now carries a `**Provenance locator:**` bullet in the same bolded shape — the screenshot adapter's was previously unbolded prose with a line wrap splitting the words "Provenance" and "locator" apart, invisible to a reader but making `grep -c 'Provenance locator'` undercount it.
- `url_fallback.py`'s "cannot reach the network" claim is now proven by an AST guard, not a docstring promise: a coarse root-import allowlist (`{json, sys, pathlib, urllib}`) plus an independent granular check on exact dotted names (`urllib.request`, `requests`, `httpx`, `selenium`, `playwright`, `bs4`, `subprocess`, `socket`, `http.client`) — the second layer exists because the first alone cannot distinguish `urllib.parse` (needed, allowed) from `urllib.request` (forbidden, shares the allowlisted root).
- A structural placement test (`_url_adapter_regions`, shared by six assertions) slices `extraction.md`'s URL adapter at its two literal outcome-bullet headings and proves `url_fallback.py` is named only in the "Fetched but nothing usable" region, never in "Fetch failed" — the tool-error branch stays a hard stop.
- The cap the operator is quoted (`MAX_FOLLOWUP_FETCHES`) and the cap enforced in code are checked against each other by importing the constant, never by retyping the number — and a genuine bug in the first draft of that check (a bare digit search passing by coincidence on the unrelated `(INGEST-06)` requirement ID a few lines down) was caught live by the plan's own mandated red-check and fixed.
- The disproven "likely a client-rendered page" verdict is asserted absent from the whole file, not just the section it used to live in.

## Task Commits

Each task committed atomically:

1. **Task 1: Provenance names the URL actually fetched** — `9e13890` (feat)
2. **Task 2: The import-set guard — the exclusions are proven, not promised** — `e52a94d` (test)
3. **Task 3: Contract pins between extraction.md and the module** — `42ff387` (test)

## Files Created/Modified

- `operator-claude-plugin/skills/contact-upload/extraction.md` — URL adapter: Provenance locator bullet, Named empty outcome bullet, same-host-bound sentence, literal cap-quoting phrase. Screenshot adapter: provenance sentence reformatted into a bolded bullet.
- `operator-claude-plugin/tests/test_url_fallback.py` — 3 new tests: the import-set subset guard, the granular dotted-forbidden-name guard, and the `open()`-outside-`__main__` guard.
- `operator-claude-plugin/tests/test_extraction_contract.py` — `_url_adapter_regions()` helper plus 7 new tests: script named by path, escalation confined to the nothing-usable region, tool-error branch states it ends there, cap parity, same-host bound named, no-same-URL-retry rule named, client-rendered verdict absent from the whole file.

## Decisions Made

- **The cap-parity test is pinned to the literal phrase, not a bare digit.** `str(cap) in text` passes at cap=6 by coincidentally matching the unrelated `(INGEST-06)` requirement ID in the same section — proven by the plan's own mandated red-check not failing when it should have. Fixed by asserting `f"at most {cap} follow-up fetches" in normalized_text` (whitespace-normalized, since the phrase wraps across a markdown line break), and by amending `extraction.md`'s prose to actually state the cap number — it previously deferred entirely to the CLI's runtime output.
- **The import-set guard needs two layers, not one.** A root-only allowlist check passes `from urllib.request import urlopen` because `urllib` is legitimately allowlisted for `urllib.parse` — proven live by red-check. The granular dotted-name check catches it by exact name.
- **The screenshot adapter's provenance bullet was reformatted for consistency**, not left as prose — required to reach the `grep -c 'Provenance locator' == 4` acceptance criterion honestly (a coincidental unbolded, line-wrapped mention doesn't count as one of the four).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The first draft of the cap-parity test passed for the wrong reason**
- **Found during:** Task 3's mandated red-check ("change `MAX_FOLLOWUP_FETCHES` to 6 without touching `extraction.md` and confirm the cap-parity test fails").
- **Issue:** `str(url_fallback.MAX_FOLLOWUP_FETCHES) in adapter_text` (the plan's own literal instruction) passed even at cap=6, because the URL adapter section already contains the substring `(INGEST-06)` a few lines below the cap sentence — an accidental digit match, not a genuine cap-quoting check. This is exactly the trap the plan's `<the_trap>` section warned about one layer over (block-index drift); here it showed up as digit-substring drift.
- **Fix:** Rewrote the assertion to require the literal phrase `f"at most {cap} follow-up fetches"` (whitespace-normalized, since markdown wraps it across two lines), and amended `extraction.md`'s prose to genuinely state the cap number rather than deferring to the CLI's runtime output.
- **Files modified:** `operator-claude-plugin/skills/contact-upload/extraction.md`, `operator-claude-plugin/tests/test_extraction_contract.py`
- **Verification:** Re-ran the red-check (cap=6, `extraction.md` untouched) — now fails correctly, naming the expected phrase. Restored to cap=5, suite green.
- **Committed in:** `42ff387`

**2. [Rule 2 - Missing critical functionality] extraction.md never stated the same-host bound in prose**
- **Found during:** Task 3 planning — the plan's own `<behavior>` list for Task 3 requires "The URL adapter section names the same-host bound", but `extraction.md` (before this plan) contained the word "host" nowhere at all; the bound existed only in `url_fallback.py`'s code and docstrings.
- **Issue:** Task 3's `<files>` only lists `test_extraction_contract.py`, so a test asserting this property would have needed a change to `extraction.md` that no task explicitly assigned.
- **Fix:** Added a same-host-bound sentence to `extraction.md`'s URL adapter as part of Task 1's edit (the only task touching that file), then pinned it with `test_url_adapter_states_the_same_host_bound` in Task 3.
- **Files modified:** `operator-claude-plugin/skills/contact-upload/extraction.md`
- **Verification:** `pytest operator-claude-plugin/tests/test_extraction_contract.py -q` — the new same-host test passes.
- **Committed in:** `9e13890` (text), `42ff387` (test)

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2). **Impact on plan:** Both were necessary to reach the plan's own stated acceptance criteria and `<behavior>` requirements honestly; neither touched scope outside this plan's three files.

## Issues Encountered

**`git checkout --` during a red-check restore reverted an uncommitted legitimate edit alongside the intended red-check mutation.** Mid-Task 3, restoring after the placement red-check with `git checkout -- extraction.md` correctly discarded the injected bad sentence but also discarded the not-yet-committed cap-quoting phrase added earlier in the same task (both were uncommitted changes to the same file). Caught immediately by re-running the suite (the cap-parity test failed for the wrong reason — text missing entirely, not a mismatch), and fixed by re-applying the cap-quoting edit before continuing. No commit was made in the intermediate state, so nothing incorrect reached history.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- 35-03 (the live walk + release) can proceed: this plan's contract pins mean any future edit to `extraction.md`'s URL adapter or `url_fallback.py`'s import set will fail the suite loudly rather than silently drift.
- Suites: plugin `1052 passed / 5 skipped` (1042 baseline + 10 new tests), full python `1933 passed / 6 skipped` (1923 baseline + 10), node `553` unchanged, disarmed-artifact gate `0`.
- No blockers.

---
*Phase: 35-url-structured-fallback*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 3 modified files and the SUMMARY confirmed present on disk; all 3 task commit hashes
(`9e13890`, `e52a94d`, `42ff387`) confirmed in git log.
