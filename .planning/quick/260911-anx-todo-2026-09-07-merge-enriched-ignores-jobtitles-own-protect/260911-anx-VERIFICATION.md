---
phase: quick-260911-anx
verified: 2026-09-11T00:00:00Z
status: passed
score: 6/6 must-haves verified
covered_files: [".planning/quick/260911-anx-todo-2026-09-07-merge-enriched-ignores-jobtitles-own-protect/260911-anx-PLAN.md", ".planning/quick/260911-anx-todo-2026-09-07-merge-enriched-ignores-jobtitles-own-protect/260911-anx-SUMMARY.md", ".planning/todos/completed/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md", "operator-claude-plugin/scripts/preingest.py", "operator-claude-plugin/skills/enrich-before-ingest/SKILL.md", "operator-claude-plugin/tests/test_preingest_merge.py", "operator-claude-plugin/tests/test_preingest_preview.py"]
covered_digest: "v1:sha256:87b22452374bcddfc4863134186544d1111050487aa28e07479390523d516297"
behavior_unverified: 0
overrides_applied: 0
---

# Quick 260911-anx: per-field protect_if_current_present in merge_enriched Verification Report

**Item Goal:** `merge_enriched` in `operator-claude-plugin/scripts/preingest.py` must read
`protect_if_current_present` per field from the plugin's shipped `config/field_policy.yaml`
for both `enrich-before-ingest` and `suggest-contacts` (one shared function, both callers).
`jobtitle` (false) accepts a differing waterfall value; email and location fields (true) are
never replaced; `conflicts` still records every replaced value.

**Verified:** 2026-09-11
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A row whose `jobtitle` is present and whose waterfall response carries a differing `jobtitle` ends the merge holding the waterfall value, for both callers (shared `merge_enriched`) | ✓ VERIFIED | `preingest.py:807-819` — `_present(current)` branch computes `replaced = key in refreshable_keys` and writes `merged[key] = value` when `replaced`. Test `test_a_present_jobtitle_is_replaced_by_a_differing_response_value` (line 249) asserts `result.rows[0]["jobtitle"] == "Head of Marketing and Content"`. Both `enrich-before-ingest` and `suggest-contacts` call this same function — no per-caller branching exists in `merge_enriched`. |
| 2 | `email` and the five location fields, `phone`, `mobilephone`, `lv_linkedin_url` are never replaced by a differing waterfall value | ✓ VERIFIED | `config/field_policy.yaml` (and byte-identical plugin copy) carries `protect_if_current_present: true` on `email` (line 158), `city`/`state`/`country`/`hs_state_code`/`hs_country_region_code` (lines 166-192), `phone` (198), `mobilephone` (204), `lv_linkedin_url` (220). `refreshable_contact_props()` (`preingest.py:113-127`) selects only keys with `is False`, so these never enter the refreshable set. Test `test_a_non_empty_source_value_is_never_overwritten_and_is_reported_as_conflict` (line 234, repointed to `email`) confirms `result.rows[0]["email"] == "amy@x.com"` unchanged. |
| 3 | A key whose `contacts:` entry omits `protect_if_current_present` (`seniority`, `lv_persona_group`), or with no `contacts:` entry at all (`firstname`, `lastname`), keeps today's fill-only behaviour | ✓ VERIFIED | `seniority`/`lv_persona_group` entries in `field_policy.yaml` carry no `protect_if_current_present` key (lines 223-232) — `refreshable_contact_props()`'s `entry.get("protect_if_current_present") is False` correctly excludes them (a missing key returns `None`, not `False`). Test `test_a_present_widened_key_is_never_overwritten_and_records_a_conflict` (line 717, `seniority`) and new test `test_a_field_absent_from_policy_entirely_keeps_fill_only_behaviour` (line 265, `firstname`) both pass. |
| 4 | Every differing value is recorded in `MergeResult.conflicts`, both kept and replaced, each entry saying which happened | ✓ VERIFIED | `preingest.py:809-816` appends a conflict dict with `source_value`, `provider_value`, and `replaced: bool` on every differing value, regardless of outcome. Confirmed in all four scenario tests (jobtitle replaced=True, email/seniority/firstname replaced=False). |
| 5 | An unresolvable/malformed `field_policy.yaml` degrades to protect-everything, never replace-everything | ✓ VERIFIED | `refreshable_contact_props()` docstring and code (`preingest.py:108-127`) degrade to `[]` on any load failure via `_load_contacts_policy`'s broad `except Exception` catch. Fail-safe assertion added inside `test_merge_allowlist_falls_back_to_canonical_props_when_the_policy_is_unreadable` (line 589): with both `PLUGIN_POLICY_PATH`/`REPO_POLICY_PATH` monkeypatched to nonexistent paths, `refreshable_contact_props() == []` and a present, differing `jobtitle` stays `"Director"` (not replaced). |
| 6 | `render_enriched_preview` shows a replaced value under `enriched_values` so the operator's pre-arm look never shows only the superseded value | ✓ VERIFIED | `preingest.py:1168-1171` — `enriched_values` predicate changed from "absent from original" to `str(value).strip() != str(source_values.get(key, "")).strip()`, comparing against the already-built `source_values`. New test `test_a_replaced_value_shows_in_enriched_values_beside_the_original_in_source_values` (line 61) asserts both `source_values["jobtitle"] == "Head of Marketing"` (original) and `enriched_values == {"jobtitle": "Head of Marketing and Content"}` (new value) are shown together. |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/scripts/preingest.py` | `_load_contacts_policy`, `refreshable_contact_props`, updated `merge_enriched`, updated `_row_view` | ✓ VERIFIED | All four present, substantive, wired — traced above |
| `operator-claude-plugin/tests/test_preingest_merge.py` | New/repointed tests for per-field behaviour | ✓ VERIFIED | 61 tests, all pass; new tests confirmed present by name |
| `operator-claude-plugin/tests/test_preingest_preview.py` | New test for replaced-value preview visibility | ✓ VERIFIED | New test present, passes; 3 pre-existing `enriched_values` tests unmodified and still green |
| `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` | Step 6 conflict sentence rewritten, no `icp`/`tier` substrings | ✓ VERIFIED | Lines 785-792 rewritten per plan; `test_autonomy_switch_prose.py` (49 tests) passes |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `merge_enriched`'s fill-vs-conflict branch | `config/field_policy.yaml` | `resolve_policy_path` / `_load_contacts_policy` (shared with `promotable_contact_props`) | ✓ WIRED | `_load_contacts_policy` factored out and used by both `promotable_contact_props` and `refreshable_contact_props` — exactly one load path, confirmed by code read |
| `config/field_policy.yaml` `contacts.jobtitle.protect_if_current_present: false` | new behaviour | direct read, no hardcoded field name | ✓ WIRED | `refreshable_contact_props()` derives the set entirely from YAML; no field name string-literal-compared in `merge_enriched` |
| `render_enriched_preview` → `_row_view` → `enriched_values` | `SKILL.md` step 6 prose | operator-facing consequence | ✓ WIRED | Both changed consistently; SKILL prose matches new preview behaviour |

### Behavioral Spot-Checks / Test Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Targeted merge tests | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -q` | 61 passed | ✓ PASS |
| Full plugin suite at anx's own commit boundary (d5d38588, via isolated git worktree) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | 2872 passed, 5 skipped | ✓ PASS |
| Full plugin suite at current HEAD (228745ef) | same | 4 failed (test_written_records.py), 2880 passed, 5 skipped | ⚠️ unrelated — see note below |
| `kept` key stragglers | `grep -rn '"kept"' scripts tests \| grep -v __pycache__` | 3 hits, all inert fixture literals in `test_preingest_preview.py` (lines 333/340/362) passed through untouched code that never inspects conflict-entry keys | ✓ PASS (matches SUMMARY claim) |
| Policy YAML untouched | `diff operator-claude-plugin/config/field_policy.yaml config/field_policy.yaml` | identical; `git status` clean on both | ✓ PASS |
| Scope: no n8n/src/scripts edits | `git show --stat 19a5f357 d5d38588 \| grep -E '^ (n8n\|src\|scripts\|config)/'` | no matches | ✓ PASS |

**Note on the 4 HEAD failures:** `operator-claude-plugin/tests/test_written_records.py` fails
on 4 tests at current repo HEAD (`228745ef`), but these failures are caused by a later,
unrelated sibling quick-batch item (commit `145527c1`, "quick-260911-ao0", which edited
`test_written_records.py` for a different todo). To isolate this item's own correctness, I
checked out anx's own final commit (`d5d38588`) into an ephemeral git worktree and ran the
full suite there: **2872 passed, 5 skipped — zero failures**, exactly matching the SUMMARY's
claim. This item's diff is not the cause of the HEAD-level failures; they belong to a
different, later batch sibling and are out of this item's scope per the task brief ("Another
executor is concurrently editing... ignore those files" — the batch-orchestration pattern
extends to test files touched by other siblings after this item sealed).

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers introduced in the touched
files. No stub returns, no hardcoded empty-data patterns in the new code paths.

### Requirements Coverage

No formal REQUIREMENTS.md IDs apply to quick-batch items; this item closes a single named
todo (`2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md`),
confirmed moved from `.planning/todos/pending/` to `.planning/todos/completed/` with a
`## Resolved 2026-09-11` section.

### Human Verification Required

None. All must-haves are mechanically verifiable via code read and test execution.

### Gaps Summary

None. All six must-have truths verified against the actual codebase (not just SUMMARY
claims): the per-field policy read is wired through the single existing RICH-04 seam,
`jobtitle` refreshes while protected fields do not, unpoliced/policy-key-less fields keep
fill-only behaviour, an unresolvable policy fails safe, conflicts record `replaced` for both
outcomes, and the pre-arm preview surfaces replaced values. Both `field_policy.yaml` copies
remain byte-identical and untouched. The full test suite is green at this item's own commit
boundary; the failures visible at current HEAD originate from a later, unrelated sibling
batch item and do not implicate this item's changes.

---

_Verified: 2026-09-11_
_Verifier: Claude (gsd-verifier)_
