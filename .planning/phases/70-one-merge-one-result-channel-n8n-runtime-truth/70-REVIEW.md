---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
reviewed: 2026-09-10T11:50:22Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - CHANGELOG.md
  - CLAUDE.md
  - n8n/wf_backend_status_cloud.json
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_contact_ingest_local.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_review_decision_cloud.json
  - n8n/wf_scheduled_maintenance_cloud.json
  - operator-claude-plugin/tests/test_control_allowlist_diff.py
  - scripts/bounce_n8n_workflows.py
  - scripts/build_cloud_workflows.py
  - scripts/prove_phase70_runtime.py
  - tests/n8n/executionOrderV1.test.mjs
  - tests/n8n/fixtures/frozen/README.md
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/test_bounce_n8n_workflows.py
  - tests/test_deploy_n8n_workflows.py
  - tests/test_prove_phase70_runtime.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: clean
---

# Phase 70: Code Review Report — Round 3 (gap-closure round 3, plans 70-16..70-18)

**Reviewed:** 2026-09-10T11:50:22Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** clean

## Round context

This is round 3 of code review for Phase 70. Rounds 1 and 2 (see git history: commits up
to `0245011`) are closed — their findings were resolved in earlier commits and are not
re-litigated here. **This report reviews only the delta introduced by commits
`96d5ee4..f5fc69d`** (diff base `0245011c9b02a8aabd7febdce2b02c3a0a55d1b1`), which
implements operator decisions D-70-28..D-70-31: flip `settings.executionOrder` to `"v1"`
on every generated workflow body from one generator constant, make a non-v1 body a
generation-time refusal, restrict the walker's legacy-modelling escape (`allowLegacy`) to
the frozen-fixture fidelity suite only, pin `settings` through both live PUT paths
(deploy script and the plugin's arming path), and make the bounce read-back and the proof
driver's verdict both fail on a non-v1 live reading.

The prior round's REVIEW.md (reviewing commits through `0245011`) has been replaced by
this file per the workflow's instruction; its content is superseded, not preserved
inline — see git history for round 2's findings if needed.

## Summary

This is an unusually well-instrumented change for its size (+2843/-398 across the whole
commit range, but the actual behavioural delta reviewed here is small and mechanically
verifiable). Verified directly, not merely read:

- All 8 generated `n8n/wf_*.json` files changed **settings-only** (`git diff --numstat`:
  every file `3\t1`), each now carrying `"settings": {"executionOrder": "v1"}` in place
  of `"settings": {}`. Node counts are unchanged and match the expected
  287/69/55/43/30/82/10/13 (verified by direct JSON parse, not by trusting the stated
  figures).
- Re-running `scripts/build_cloud_workflows.py` reproduces the committed JSON
  byte-for-byte (`git status` clean after regeneration) — the generator is not drifting
  from what's committed.
- `assert_execution_order_v1` is composed as the outermost of four generation-time
  refusals (`_assert_generation_contracts`), applied at all 8 write sites via
  `_assert_generation_contracts(...)` — confirmed by grep, one call site per workflow,
  matching the workflow count.
- The walker's non-v1 refusal (`tests/n8n/lib/walkWorkflow.mjs`) computes
  `order = wf.settings && wf.settings.executionOrder === "v1" ? "v1" : "legacy"` — a
  missing `settings` key degrades to `"legacy"` and is refused, not silently accepted.
  `allowLegacy` is used at exactly 3 call sites, all inside
  `tests/n8n/walkerEngineFidelity.test.mjs`, confirmed by grep across the whole `tests/n8n/`
  tree.
- `bounce_n8n_workflows.py`'s `_row_ok` reads `(live_body.get("settings") or {}).get(...)`
  — handles a missing `settings` key without raising, and the offline test suite
  explicitly covers both "settings key absent entirely" and "settings present but empty."
- `prove_phase70_runtime.py`'s exit-code change (`if verdict["answer"] is not True`)
  cannot regress the predict-only path: `main()` returns 0 for `--predict-only` in a
  branch that executes and returns *before* the `verdict["answer"]` check is ever
  reached. Traced this directly in the source, not inferred from tests alone.
- The deploy-path preservation tests
  (`test_update_put_payload_carries_settings_value_intact`,
  `test_create_post_payload_carries_settings_value_intact`,
  `test_settings_survive_rebind_bind_and_baked_flag_transforms`) assert
  `captured["json"]["settings"] == {"executionOrder": "v1"}` — value-level equality, not
  merely key presence — and the three upstream transform functions
  (`rebind_subworkflow_refs`, `bind_credentials`, `enable_baked_flags`) all deep-copy via
  `json.loads(json.dumps(workflow))` before mutating only their own concern, so `settings`
  passes through untouched by construction, not by accident.
- The plugin's arming path (`operator-claude-plugin/scripts/n8n_control.py`) refuses any
  PUT where `original["settings"] != modified["settings"]` (`assert_only_allowlisted_change`,
  line 241-242) — settings is never on the allowlist, so an arming rewrite that touched it
  in either direction (value change or key-drop) is a hard refusal, covered by both new
  tests in `test_control_allowlist_diff.py`.
- CLAUDE.md's round-3 delta is careful about its own epistemic status: no row claims v1
  behaviour has been `[observed live]` — the closing note under the platform-facts table
  states this explicitly ("No row in this table claims v1 behaviour has been observed on
  this instance"). The two pre-existing Merge-behaviour rows that were `[observed live]`
  under the legacy engine are annotated as scoped to legacy, not deleted or rewritten —
  their execution ids (`12203`, `12206`) are preserved. New rows cite execution ids
  `12349`-`12353` for the Gate 8 legacy-`addEmptyItem` reproduction and cite source file +
  symbol for both `[documented]` engine-rule rows.
- Full test suites pass: `node --test tests/n8n/*.test.mjs` → 1078/1078; the round's
  targeted Python suites → 94/94; the full `pytest` run → 4721 passed, 154 skipped, 0
  failed.
- `tests/n8n/walkWorkflow.test.mjs`'s re-derived assertions (the F5 collapse case, the
  respond-race case, the paired-item case) are genuine re-derivations from v1's
  pop-order dequeue semantics, with reasoning recorded in comments for each — not values
  silently adjusted to make a red test green.

No Critical or Warning findings. One Info-level observation below.

## Info

### IN-01: Redundant `_flag_values` call in `bounce_n8n_workflows.py`'s row loop

**File:** `scripts/bounce_n8n_workflows.py:85-89`
**Issue:** `main()`'s per-workflow loop calls `_flag_values(live)` directly (to build
`flags_txt` for the printed table) and then calls `_row_ok(live, expected)`, which
internally calls `_flag_values(live_body)` again on the same body. `_flag_values` is a
pure function with no side effects, so this is not a correctness issue — just a doubled
computation per workflow (5 workflows, trivial cost) that a reader has to notice is safe
rather than a genuine hazard.
**Fix:** Compute `flags = _flag_values(live)` once and pass it into `_row_ok(live, expected, flags=flags)`, or have `_row_ok` accept the already-computed `flags` dict as an optional parameter. Not worth a structural change on its own — fine to fold into the next touch of this file.

---

_Reviewed: 2026-09-10T11:50:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
