---
phase: 58-take-what-the-operator-actually-has
fixed_at: 2026-08-26T00:00:00Z
review_path: .planning/phases/58-take-what-the-operator-actually-has/58-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 58: Code Review Fix Report

**Fixed at:** 2026-08-26T00:00:00Z
**Source review:** .planning/phases/58-take-what-the-operator-actually-has/58-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (1 Critical, 2 Warning) — IN-01 out of scope per fix_context
  ("Critical + Warning findings; skip Info unless trivially safe" — IN-01 requires a design
  decision between raising and documenting, not a trivially safe one-liner, so it was left
  for the operator).
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: Mixed-batch companies-first reassembly defeats the D-07 no-invention guard

**Files modified:** `operator-claude-plugin/scripts/extraction.py`,
`operator-claude-plugin/tests/test_company_extraction.py`
**Commit:** `5e22393`
**Applied fix:** Every pre-flight `accepted` entry in `validate()` is now tagged with its
raw `records` index (`_raw_index`; carried through a dedupe merge as `_raw_indices` listing
every contributing raw index). After the per-type split/dedupe/companies-first reassembly, a
`raw_to_final` lookup is built from `deduped_accepted` and every artifact-supplied
ambiguity's `record_index` (and `other_record_index`, if present) is translated through it
before the D-07 contradiction pass runs — the same treatment dedupe-generated ambiguities
already received. An ambiguity whose raw index does not resolve to any surviving row is
dropped rather than guessed at. The internal `_raw_index`/`_raw_indices` bookkeeping keys are
stripped before an entry can reach `ExtractionResult.accepted`.

Added `test_mixed_batch_ambiguity_on_a_contact_survives_companies_first_reassembly`
(the review's exact repro: contact ambiguity, company record ordered first) and
`test_mixed_batch_ambiguity_on_a_company_survives_contacts_first_input_order` (the inverse
ordering), both asserting the contradicting row is rejected with a D-07 reason, and that no
`_raw_index`/`_raw_indices` keys leak into `accepted`.

### WR-01: `cost_guard.research_line()` returns a non-JSON-serializable `set`

**Files modified:** `operator-claude-plugin/scripts/cost_guard.py`,
`operator-claude-plugin/tests/test_cost_guard.py`,
`operator-claude-plugin/tests/test_company_research_envelope.py`
**Commit:** `d9b7510`
**Applied fix:** `research_line()`'s `row_ids` is now
`sorted((row.get("row_id") for row in rows), key=lambda v: (v is None, v))` instead of a
Python `set` — deterministic and JSON-serializable, with a `None` row_id sorted safely to
the end instead of raising a `TypeError` on a mixed `str`/`None` comparison. Updated the
three pre-existing assertions in `test_company_research_envelope.py` that compared
`row_ids` to a set literal; added `test_research_line_result_is_json_serializable_with_sorted_row_ids`
and `test_research_line_tolerates_a_missing_row_id_without_raising` to `test_cost_guard.py`.

### WR-02: Malformed `record_type` is silently coerced to `"contacts"` with a misleading rejection reason

**Files modified:** `operator-claude-plugin/scripts/extraction.py`,
`operator-claude-plugin/tests/test_company_extraction.py`
**Commit:** `5e22393` (landed in the same commit as CR-01 — both edits touched adjacent
lines of `validate()`'s per-record pre-flight before the first commit was made in this run,
so they were not split into two separate commits the way the atomic-per-finding convention
otherwise calls for; noted here rather than silently deviating from it)
**Applied fix:** `validate()` now rejects a present-but-unrecognized `record_type` by name —
`"unrecognized record_type {value!r}: expected 'companies' or 'contacts' (or omit the key
for a contact)"` — before it can fall through to the contact lane's identity check, following
the `n8n/code`'s `normalizeObjectType` precedent the finding cites. An absent `record_type`
key is unaffected and still defaults to `"contacts"` (backwards compatibility, pinned by the
existing `test_extraction_contract_backwards_compat_pin_absent_record_type_routes_to_contacts`).
Added `test_unrecognized_record_type_is_rejected_by_name_not_silently_coerced` asserting a
near-miss spelling (`"Companies"`) is rejected naming `record_type`, never the
contact-oriented "needs email/firstname+lastname+company" message.

## Skipped Issues

None in scope — all 3 Critical/Warning findings were fixed. IN-01 (a duplicate `row_id`
silently taking the last entry in `company_domain.apply_domain_decisions`) is Info-tier and
out of this run's scope per `fix_context`; the review itself notes it as low-likelihood given
the documented `row_id`-minting contract elsewhere in the plugin.

## Verification

Both required suites were run from the main checkout directly (`workflow.use_worktrees` is
`false` in `.planning/config.json` for this repo, so no isolated review-fix worktree was
created for this run — edits and commits landed straight on `master`):

- `operator-claude-plugin` suite alone: 1606 passed, 5 skipped.
- Repo-wide (`.venv/bin/python -m pytest operator-claude-plugin/tests/ tests/ -q`): 3203
  passed, 154 skipped, 4 failed — the 4 failures are the pre-existing/known
  `tests/test_merge_policy.py` failures called out in `fix_context` as deferred and not
  attributable to this fix (`test_sc3_e2e_promote_forced_still_protects_manual`,
  `test_sc4_full_source_attribution`, `test_sc4b_cache_key_not_stamped_unless_promoted`,
  `test_integ_wires_icp_scorer` — all fail on an unrelated `ThinkingBlock` object has no
  attribute `text` pydantic/anthropic-SDK error, nothing touched by this fix).
- Node (`node --test tests/n8n/*.test.mjs`): 772 passed, 0 failed.

No `n8n/wf_*.json` file was touched — all three fixes are plugin-Python-side only, as
`fix_context` anticipated; no workflow rebuild is needed.

---

_Fixed: 2026-08-26T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
