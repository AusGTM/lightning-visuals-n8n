---
phase: quick-260911-any
verified: 2026-09-11T00:00:00Z
status: passed
score: 5/5 must-haves verified
covered_files: [".planning/quick/260911-any-todo-2026-09-08-forbidden-name-markers-refuse-secretary-and/260911-any-PLAN.md", ".planning/quick/260911-any-todo-2026-09-08-forbidden-name-markers-refuse-secretary-and/260911-any-SUMMARY.md", ".planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md", ".planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md", "operator-claude-plugin/scripts/held_queue.py", "operator-claude-plugin/scripts/remainder_queue.py", "operator-claude-plugin/scripts/run_manifest.py", "operator-claude-plugin/scripts/run_report.py", "operator-claude-plugin/scripts/run_state.py", "operator-claude-plugin/scripts/suggestion_declines.py", "operator-claude-plugin/scripts/written_records.py", "operator-claude-plugin/tests/test_forbidden_marker_parity.py", "operator-claude-plugin/tests/test_held_queue.py", "operator-claude-plugin/tests/test_suggestion_declines.py"]
covered_digest: "v1:sha256:20fb3ed7a303ca5e42c0549cd061b9b6891d53c601301852006f54a5439623f9"
behavior_unverified: 0
overrides_applied: 0
---

# Quick 260911-any: Forbidden-name markers refuse Secretary and Armidale — Verification Report

**Item Goal:** Fix the inherited forbidden-name substring guard so real club data
("Secretary", "Armidale") no longer false-trips, while the original forbidden tokens
still refuse — smallest fix that keeps the guard's intent (word-boundary / whole-token
matching, not substring).

**Verified:** 2026-09-11
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A suggestion-decline entry with jobtitle "Secretary" and company "Armidale Jockey Club" saves and loads back unchanged | ✓ VERIFIED | `test_suggestion_declines.py::test_a_secretary_at_armidale_jockey_club_saves_and_loads_back_unchanged` PASSED (run directly); exercises the real `save`/`load` round-trip through JSON on disk, not just the matcher |
| 2 | A held-queue entry naming "Armidale Jockey Club" with a reason mentioning "the club Secretary" saves | ✓ VERIFIED | `test_held_queue.py::test_a_held_armidale_jockey_club_entry_saves_and_loads_back_unchanged` PASSED (run directly) |
| 3 | Every genuine marker still refuses in its own right (`webhook_secret`, `n8n_api_key`, `armed_row`, verdict `armed`, `n8n_api_key=super-secret`, `bad webhook_secret configured`) | ✓ VERIFIED | Independently re-ran adversarial corpus against all seven imported modules (not reimplemented copies) — all True as expected; the three cited regression tests (`test_held_queue.py::test_save_refuses_an_arming_shaped_value_inside_observed_signals`, `test_run_manifest.py::test_save_refuses_an_arming_shaped_verdict_and_writes_nothing`, `test_written_records.py::test_a_value_naming_a_secret_refuses_rather_than_persisting` for T-59-02) all PASS |
| 4 | Plural/inflected forms still refuse (`credentials`, `permissions`, `api_tokens`, `arming`, camelCase `webhookSecret`) | ✓ VERIFIED | Directly probed `_looks_forbidden`/`_looks_forbidden_key` in all seven modules for this corpus — all True |
| 5 | All seven store copies answer the same corpus identically — no copy left on the substring rule | ✓ VERIFIED | Ran identical 10-string adversarial corpus (webhookSecret, N8N_API_KEY, api_tokens, credentials, armed, x-enrichment-secret, Secretary, Armidale, Armstrong, pharmacy) against all seven imported modules' matchers side-by-side — results identical across all seven except `run_report`'s value-scan for "armed" (documented, deliberate: `_VALUE_MARKERS` excludes `arm`/`webhook` by design, pre-existing behaviour unchanged by this fix) |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/tests/test_forbidden_marker_parity.py` | New drift-guard test file | ✓ VERIFIED | Exists, 116 lines, 5 test functions covering must-pass/must-refuse corpora across all 7 modules plus tuple-equality/distinct-object pin |
| `operator-claude-plugin/scripts/suggestion_declines.py` | Whole-token matcher | ✓ VERIFIED | `_CAMEL_BREAK`, `_NON_TOKEN`, `_tokenised`, `_FORBIDDEN_TOKEN_RUNS`, `_looks_forbidden` present; substring rule replaced |
| `operator-claude-plugin/scripts/held_queue.py` | Whole-token matcher | ✓ VERIFIED | Same structure confirmed present |
| `.planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md` | Todo closed with resolution note | ✓ VERIFIED | File exists in `completed/`, no longer in `pending/`; resolution note accurately documents candidate (2) vs todo's preferred (1), seven-copy scope, and the parity-test drift guard |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `_FORBIDDEN_TOKEN_RUNS` | unchanged `_FORBIDDEN_NAME_MARKERS` tuple | derived, not replacing, the ten-marker source | ✓ WIRED | Confirmed all 7 tuples byte-identical (`("arm", "secret", "api_key", "apikey", "token", "credential", "password", "grant", "permission", "webhook")`), 10 members, same order, in all seven files |
| `test_forbidden_marker_parity.py` | seven modules' matchers | imports and calls by name | ✓ WIRED | Verified imports (`held_queue`, `suggestion_declines`, `run_manifest`, `run_state`, `run_report` [`_looks_forbidden_key`/`_looks_forbidden_value`], `written_records`, `remainder_queue`) all resolve and are exercised |
| `run_report.py` | two-set split (`_FORBIDDEN_NAME_MARKERS` for keys, `_VALUE_MARKERS` for values) | both get token-run treatment, membership unchanged | ✓ WIRED | `_VALUE_MARKERS = tuple(m for m in _FORBIDDEN_NAME_MARKERS if m not in ("arm", "webhook"))` unchanged; `_VALUE_TOKEN_RUNS = _token_runs(_VALUE_MARKERS)` added; `_looks_forbidden_value("disarmed")` is False, `_looks_forbidden_value("secret")` is True — confirmed by direct test run |

### Independent Adversarial Probe

Ran the following corpus directly against the actual shipped, imported modules (not
reimplemented test code) across `held_queue`, `suggestion_declines`, `run_manifest`,
`run_state`, `run_report` (both key and value matchers), `written_records`,
`remainder_queue`:

| Input | Expected | All 7 result | Notes |
|-------|----------|---------------|-------|
| `webhookSecret` | refuse | True everywhere | camelCase compound |
| `N8N_API_KEY` | refuse | True everywhere | SHOUTING snake_case |
| `api_tokens` | refuse | True everywhere | plural inflection |
| `credentials` | refuse | True everywhere | plural inflection |
| `armed` | refuse | True everywhere except `run_report` value-scan (False, by design — `arm` excluded from `_VALUE_MARKERS`) | documented divergence, pre-existing |
| `x-enrichment-secret` | refuse | True everywhere | hyphenated compound |
| `Secretary` | pass | False everywhere | the reported bug |
| `Armidale` | pass | False everywhere | the reported bug |
| `Armstrong` | pass | False everywhere | adjacent false-positive risk |
| `pharmacy` | pass | False everywhere | adjacent false-positive risk |
| `Grant` (residual) | refuse | True everywhere | documented, tracked residual — not a regression |
| `Token` (residual) | refuse | True everywhere | documented, tracked residual — not a regression |

All seven copies answered identically on every input. No copy was found still on the
raw-substring rule.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Secretary/Armidale save+load round-trip (suggestion_declines) | `pytest test_suggestion_declines.py::test_a_secretary_at_armidale_jockey_club_saves_and_loads_back_unchanged` | 1 passed | ✓ PASS |
| Secretary/Armidale save+load round-trip (held_queue) | `pytest test_held_queue.py::test_a_held_armidale_jockey_club_entry_saves_and_loads_back_unchanged` | 1 passed | ✓ PASS |
| Value-refusal regressions (T-59-02, held_queue:174, run_manifest:112) still red for their fixtures | targeted pytest run of the 3 named tests | 2 of 3 confirmed directly + T-59-02 confirmed present and asserted in full-suite run | ✓ PASS |
| Full seven-module targeted test run | `pytest test_forbidden_marker_parity.py test_suggestion_declines.py test_held_queue.py test_run_manifest.py test_run_state.py test_run_report.py test_written_records.py test_remainder_queue.py -q` | 365 passed | ✓ PASS |
| Full plugin suite | `pytest operator-claude-plugin/tests -q` | 2887 passed, 5 skipped, 3 failed | ⚠️ see note below |
| Node suite | `node --test tests/n8n/*.test.mjs` | 1101 pass, 0 fail | ✓ PASS |
| n8n/ dirty check | `git diff --quiet -- n8n/` | clean (N8N_CLEAN) | ✓ PASS |

**Note on the 3 plugin-suite failures:** all three are in `operator-claude-plugin/tests/test_search_fallback.py`
(`test_no_ladder_and_no_attempts_is_eligible_as_absence_of_information`,
`test_no_ladder_with_a_refused_attempt_is_a_contradiction_and_ineligible`,
`test_no_ladder_with_an_empty_attempt_is_also_a_contradiction_and_ineligible`), which
calls `eligible_after_ladder(..., ladder_built=False)` — a signature mismatch against
`search_fallback.py`. Confirmed via `git status`: `test_search_fallback.py` has an
uncommitted, in-progress modification (`M` in working tree) from the concurrently
running executor explicitly flagged in this verification's instructions as
"editing suggest_contacts.py, search_fallback.py and skills/suggest-contacts/SKILL.md
— ignore those files." Not caused by, or related to, this item's changes (no file this
item touches is imported by `search_fallback.py` or `test_search_fallback.py`). The
SUMMARY.md's claim of "2882 passed, 5 skipped, 0 failed" reflects a suite snapshot taken
before the concurrent executor's uncommitted edit landed; this is a timing artifact of
the shared worktree, not a discrepancy in this item's own work.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers in any of the seven
modified `scripts/` files. The one deliberately unfixed edge case (`Grant`/`Token` whole-
word residual) is documented in-line via the new pending todo, not left as a silent gap.

### Requirements Coverage

No formal REQUIREMENTS.md IDs are declared for this quick-batch item (`requirements-completed: []`
in SUMMARY frontmatter) — this is a quick task closing a standalone todo, not phase work.

### Human Verification Required

None.

### Gaps Summary

None. All five must-have truths verified directly by independently exercising the
shipped code (both save/load round-trips and matcher-level adversarial probing across
all seven store copies), not by trusting SUMMARY.md's narrative. The one pre-existing
unrelated failure (`test_search_fallback.py`, concurrent executor's in-progress edit)
is out of this item's scope per explicit verification instructions and does not affect
the goal achievement determination.

---

_Verified: 2026-09-11_
_Verifier: Claude (gsd-verifier)_
