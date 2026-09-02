---
phase: 27-backend-status-surface
plan: 02
subsystem: operator-claude-plugin
tags: [plugin, status, error-translation, guardrail, redaction]

requires: []
provides:
  - "operator-claude-plugin/scripts/error_table.py — TABLE (ordered signature entries), translate(text), ADMIN/OPERATOR attribution constants, REDACTED/TRUNCATION_MARKER/MAX_RAW_CHARS"
  - "A deterministic, stdlib-only translation of the four STATUS-02 causes into one plain sentence plus who can act"
  - "D-05's unmatched-branch guardrail: interpretation flag, redacted+bounded raw text, unconditional admin attribution"
affects: [27-04 (per-node error reading translates through this table), 27-05 (renders the result)]

tech-stack:
  added: []
  patterns:
    - "The guardrail is a property of the function, not of the caller — translate() takes exactly one parameter, so no caller can pass an override that blames the operator for an unknown failure"
    - "Matching runs on the original text; the returned raw is always redacted and length-bounded, on the matched path as well as the unmatched one"
    - "Free-text case-insensitive regex matching, never a field lookup — 27-RESEARCH.md A4 warns the n8n error field shapes are doc-cited, not observed live in this instance"

key-files:
  created:
    - operator-claude-plugin/scripts/error_table.py
    - operator-claude-plugin/tests/test_error_translation.py
    - operator-claude-plugin/tests/test_error_guardrail.py
  modified: []

key-decisions:
  - "One table entry per cause, with the pattern as an alternation regex rather than one entry per vocabulary variant — keeps D-06's 'promotion is appending one entry and nothing else' literally true, with no registry, class hierarchy or plugin mechanism."
  - "Order is explicit and load-bearing: authentication is checked before quota, so a message carrying both ('401 Unauthorized: your credit balance is exhausted') reads as the credential problem — the one that blocks every provider rather than one balance. Asserted by test, not left incidental."
  - "Redaction and truncation are applied on the matched path too, not only the unmatched one (a strengthening beyond the plan's wording — see Deviations). A 401's raw text is the single most likely place for an echoed Authorization header to appear."
  - "translate() never raises. A null, empty or non-string input returns the unmatched result with raw set to a non-empty placeholder, so the D-05 'raw is non-empty' property holds universally rather than only for real error text."
  - "Attribution values are the machine-checkable constants ADMIN/OPERATOR rather than prose, so the never-blame-the-operator sweep is an equality check that cannot pass on a reworded sentence."

requirements-completed: [STATUS-02]

coverage:
  - id: D1
    description: "Each of the four STATUS-02 causes (expired credential, rate limit, exhausted quota, malformed record) is reachable by cause name from a realistic message, with the right attribution — admin for the three credential/balance-shaped ones, operator for the CRM-rejected record"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_translation.py::test_authentication_rejection_translates_to_expired_credential, ::test_too_many_requests_translates_to_rate_limit_and_says_it_clears, ::test_quota_exhaustion_translates_to_exhausted_quota, ::test_record_rejected_by_the_crm_is_the_operators_to_fix, ::test_all_four_named_causes_are_reachable"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every seeded sentence is exactly one sentence carrying no digit, no traceback marker and no newline — STATUS-02's 'never a bare status code or stack trace' as a property over the whole table, so a future promoted entry inherits the check"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_translation.py::test_every_seeded_sentence_is_one_plain_sentence"
        status: pass
    human_judgment: false
  - id: D3
    description: "Matching is case-insensitive, works on a substring of noisy node/timestamp-laden text, is deterministic, and the first matching entry wins in an explicit order"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_translation.py::test_matching_is_case_insensitive_and_works_on_a_substring, ::test_the_same_input_always_returns_the_same_entry, ::test_the_first_matching_entry_wins_and_the_order_is_explicit"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-05 property (a): an unmatched failure is labelled as an interpretation and its sentence names no cause from the table"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_guardrail.py::test_an_unmatched_text_is_labelled_as_an_interpretation, ::test_the_unmatched_sentence_names_no_cause_from_the_table"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-05 property (b): an unmatched result carries non-empty raw text alongside its sentence"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_guardrail.py::test_an_unmatched_result_carries_non_empty_raw_text"
        status: pass
    human_judgment: false
  - id: D6
    description: "D-05 property (c) / T-27-07: across a sweep of 12 varied unrecognized inputs the operator attribution is returned zero times, and translate() exposes no override parameter through which a caller could change it"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_guardrail.py::test_no_unrecognised_failure_is_ever_blamed_on_the_operator, ::test_the_admin_attribution_has_no_override_parameter"
        status: pass
    human_judgment: false
  - id: D7
    description: "T-27-06: bearer values, credential header lines and bare key-shaped tokens are each replaced with a placeholder in the returned raw text, on the matched path as well as the unmatched one, while the surrounding message stays readable"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_guardrail.py::test_a_bearer_value_is_redacted_from_the_raw_text, ::test_an_authorization_header_line_is_redacted, ::test_a_bare_key_shaped_token_is_redacted, ::test_redaction_leaves_the_surrounding_message_readable, ::test_a_matched_result_is_redacted_too"
        status: pass
    human_judgment: false
  - id: D8
    description: "T-27-08: raw text is truncated to a bounded length with an explicit marker, so a multi-kilobyte payload cannot flood the conversation"
    requirement: STATUS-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_error_guardrail.py::test_a_very_long_raw_text_is_truncated_with_an_explicit_marker"
        status: pass
    human_judgment: false
  - id: D9
    description: "The module is a pure lookup: standard library only, no network call and no file read anywhere in it"
    requirement: STATUS-02
    verification:
      - kind: command
        ref: "AST walk over error_table.py asserting its import set == {'re'}; the plugin suite's autouse no_network guard covers both test files"
        status: pass
    human_judgment: false

duration: 28min
completed: 2026-07-31
status: complete
---

# Phase 27 Plan 02: Failure-cause translation table and its guardrail Summary

**A stdlib-only lookup that turns a failure message into one plain sentence plus who can act on it, and an unmatched branch that is provably honest: labelled as an interpretation, raw text redacted and length-bounded, and blamed on an admin every time — never on the operator.**

## Performance

- **Duration:** ~28 min
- **Completed:** 2026-07-31
- **Tasks:** 2 completed (both TDD: RED then GREEN)
- **Files modified:** 3 (3 created, 0 modified)

## Accomplishments

- `operator-claude-plugin/scripts/error_table.py`: an ordered four-entry `TABLE` plus `translate(text)`. Each entry carries exactly four fields — pattern, cause, sentence, attribution — so D-06's promotion path is literally "append one `_Entry`". No registry, no class hierarchy, no plugin mechanism.
- All four causes STATUS-02 names are seeded and reachable, matching on the vocabulary each surface actually produces (`401/unauthorized/invalid credential`, `429/too many requests/rate limit`, `402/quota/insufficient credits`, `400/bad request/property values were not valid`) rather than on a numeric code alone. The three credential- and balance-shaped causes attribute to an admin; the CRM-rejected record attributes to the operator, because the row came from their file.
- Sentences are written for a non-technical reader and constrained by a property test over the whole table: exactly one terminal full stop, no digit anywhere, no traceback marker, no newline. A future promoted entry inherits that check for free.
- D-05's guardrail lives inside `translate()` and takes no parameter, so a caller that forgets the rule cannot produce a wrong "you can fix this". Proven by a 12-input sweep plus a signature check asserting `translate` has exactly one parameter.
- Redaction (`Bearer …`, `Authorization:`/`X-N8N-API-KEY:`/`api-key:` header lines, and bare 20-plus-character opaque tokens) and a 600-character bound with a `… [truncated]` marker are applied to the returned raw text on every path. The surrounding message survives — a blanked string is useless to the admin who has to act on it.
- Matching runs against the original text while the returned raw is the sanitised copy, so redaction can never change which entry matches.

## Task Commits

1. **Task 1: The static signature table and the matching path** — `0d64099` (test, RED) → `8fe93ec` (feat, GREEN)
2. **Task 2: The unmatched-branch guardrail** — `6c6e58b` (test, RED) → `afde9ad` (feat, GREEN)

RED was genuine in both cases: Task 1's RED failed at collection (module absent); Task 2's RED failed 6 of 11 (redaction and truncation absent, the three D-05 properties already satisfied by Task 1's unmatched branch by construction).

## Files Created/Modified

- `operator-claude-plugin/scripts/error_table.py` — the ordered table, `translate()`, `_sanitise()` (redaction + truncation), `ADMIN`/`OPERATOR`/`REDACTED`/`TRUNCATION_MARKER`/`MAX_RAW_CHARS`
- `operator-claude-plugin/tests/test_error_translation.py` — 10 tests, the matching path
- `operator-claude-plugin/tests/test_error_guardrail.py` — 11 tests, D-05's three properties, the never-blame-the-operator sweep, per-shape redaction, the length bound

## Decisions Made

- **One entry per cause, alternation regex as the pattern.** The alternative — one entry per vocabulary variant — would have made the table 15 rows for 4 causes and made "which entry wins" harder to reason about. One row per cause keeps the order assertion meaningful.
- **Attribution as constants, not prose.** `ADMIN = "admin"` / `OPERATOR = "operator"` means the sweep is an equality check. Had the attribution been a sentence, a reworded sentence would silently pass a sweep that greps for "operator".
- **`raw` is never empty.** A null/empty/non-string input yields `"(no error text was supplied)"`. This keeps D-05's "raw is non-empty" property universal rather than conditional on the input being real error text.

## Deviations from Plan

### Auto-fixed / strengthened

**1. [Rule 2 — missing critical functionality] Redaction and truncation applied on the matched path, not only the unmatched one**
- **Found during:** Task 2, writing the guardrail.
- **Issue:** The plan's action text scopes redaction to the unmatched branch ("Add a redaction step applied to the raw text before it is returned", within the on-no-match paragraph). But `translate()` returns `raw` on the matched path too — and the single most likely place for an echoed `Authorization` header is precisely a `401` message, which *does* match the table. Scoping redaction to the unmatched branch would have left T-27-06 open on the highest-risk input.
- **Fix:** `_sanitise()` runs before the table scan's return, so every path returns redacted, bounded raw text. Matching still runs against the original string, so redaction cannot alter which entry wins.
- **Files modified:** `operator-claude-plugin/scripts/error_table.py`
- **Verification:** `test_error_guardrail.py::test_a_matched_result_is_redacted_too` asserts a `401 … Bearer <secret>` input both matches `expired_credential` and returns the secret redacted.
- **Committed in:** `afde9ad`

This is a widening of a mitigation, not a change of design — D-05's properties are unchanged and no test was weakened. It is recorded here rather than folded into `27-CONTEXT.md` because it contradicts nothing in the phase's decisions; D-05 states what the unmatched branch must do, not that the matched branch may leak.

**Total deviations:** 1, a strengthening.

## Plan/reality mismatches

None. Every fact the plan relies on held:
- 27-RESEARCH.md A4's warning (error field shapes doc-cited, not observed live) is honored — the matcher works purely off free text and depends on no field being present, so a wrong field-name assumption in 27-04 cannot break translation.
- D-04a's scope note held: only `malformed_record` is observable from run status today; the other three are seeded and waiting for 27-04's per-node reading. Nothing here presumes 27-04's shape.
- `27-CONTEXT.md` needed no amendment from this plan.

## Known Stubs

None. No placeholder, no TODO, no hardcoded empty value flowing to a rendering surface. The Claude fallback that consumes the unmatched result is 27-04/27-05's work by design (D-04), not a stub left here.

## Test counts

| Suite | Before | After | Delta |
|---|---|---|---|
| `.venv/bin/python -m pytest -q` (repo) | 919 passed, 1 skipped | 940 passed, 1 skipped | +21 (exactly this plan's tests) |
| `node --test tests/n8n/*.test.mjs` | 400 pass, 0 fail | 400 pass, 0 fail | 0 (untouched) |
| plugin suite (`operator-claude-plugin/`) | 156 passed | 177 passed | +21 |

No regression. All 21 new tests are this plan's.

## Safety invariants

- No write flag armed, no deploy, no activation, no live HubSpot/n8n call. `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0 everywhere.
- `git diff --name-only 86dfeb5..HEAD` shows exactly three files, all inside `operator-claude-plugin/` and all within this plan's declared region. No sibling file (27-03 owns `n8n_read.py`, `backend_status.py`, `status.py`, `config_gate.py`, `conftest.py` and its tests) was staged or committed — checked with `git status --porcelain` before each of the four commits.
- `error_table.py` imports `re` and nothing else (AST-verified), so `test_no_backend_imports.py` remains trivially satisfied. No `__init__.py` added under `tests/`.
- The autouse `no_network` guard was left untouched.

## Issues Encountered

None.

## User Setup Required

None — pure Python module plus tests, no config, no credential, no deploy.

## Next Phase Readiness

- 27-04 can translate a per-node error blob by handing its message text straight to `error_table.translate()`; the return mapping already carries everything a renderer needs (`matched`, `cause`, `sentence`, `who_can_fix`, `is_interpretation`, `raw`).
- 27-05 renders `sentence` as the lead and `raw` as the detail; `raw` is already safe to show — redacted and bounded.
- D-06's growth path is open: appending one `_Entry` to `TABLE` promotes a fallback-learned signature, and the one-sentence property test applies to it automatically.

---
*Phase: 27-backend-status-surface*
*Completed: 2026-07-31*

## Self-Check: PASSED
All three created files exist on disk; all four task commit hashes (`0d64099`, `8fe93ec`, `6c6e58b`, `afde9ad`) verified present in `git log`.
