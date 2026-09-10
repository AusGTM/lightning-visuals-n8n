---
phase: quick-260911-ao1
item: 260911-ao1-todo-2026-09-11-merge-input-contract-allows-many-producers-p
verified: 2026-09-11T00:00:00Z
status: passed
score: 8/8 must-haves verified
covered_files:
  - scripts/build_cloud_workflows.py
  - tests/n8n/mergeInputContract.test.mjs
  - .planning/todos/completed/2026-09-11-merge-input-contract-allows-many-producers-per-input.md
  - .planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md
  - .planning/quick/260911-ao1-todo-2026-09-11-merge-input-contract-allows-many-producers-p/260911-ao1-PLAN.md
  - .planning/quick/260911-ao1-todo-2026-09-11-merge-input-contract-allows-many-producers-p/260911-ao1-SUMMARY.md
covered_digest: "v1:sha256:6480ab76afa0d0e3f1f0a4340f38817255550bb0b23eba009e39a264d16ecd55"
behavior_unverified: 0
overrides_applied: 0
---

# Quick Task 260911-ao1 Verification: Merge-Input Contract Rule 5

**Goal:** Close the operator's Option A ruling — `assert_merge_input_contract` gains rule 5
(default-refuse a multi-producer Merge input, admit by named/reasoned allowlist), mirrored
in `tests/n8n/mergeInputContract.test.mjs`, zero `n8n/` JSON diff, todo closed with
MN-01/NF-MJ-01 carried forward still open.

**Verified:** 2026-09-11
**Status:** passed

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Rule 5 refuses a multi-producer Merge input unless the (workflow body name, Merge name) pair is on `_MERGE_MULTI_PRODUCER_TOLERANT` | ✓ VERIFIED | `scripts/build_cloud_workflows.py:11418-11422`; synthetic off-list two-producer Merge raises `ValueError` naming the Merge (`RULE5_FIRES_ON_SYNTHETIC` reproduced live) |
| 2 | Allowlist keyed on (workflow body `wf["name"]`, Merge node name), following `_SELF_DISPATCH_EXEMPTIONS`/WR-08 keying discipline | ✓ VERIFIED | `_MERGE_MULTI_PRODUCER_TOLERANT` dict keys are 2-tuples of exactly that shape (`scripts/build_cloud_workflows.py:11238-11344`); comment at 11228-11231 states the precedent explicitly |
| 3 | `Decide Company Action Merge` on the allowlist with the operator's 2026-09-11 marker-filter reason | ✓ VERIFIED | `scripts/build_cloud_workflows.py:11240-11244` — reason cites executions 12354/12355/12356 and `walkerEngineFidelityV1.test.mjs` |
| 4 | `Collect Credits` admitted citing the mutual-exclusivity proof in `creditsSummaryUnderV1.test.mjs` | ✓ VERIFIED | `scripts/build_cloud_workflows.py:11247-11252` |
| 5 | Rule 5 is provably live: empty allowlist raises for all violating workflows; synthetic off-list Merge raises | ✓ VERIFIED | Reproduced independently — direct loop over all 8 committed JSON with allowlist emptied recovers exactly 16 pairs across 4 workflows (`wf_contact_ingest_cloud`, `wf_enrichment_cloud`, `wf_enrichment_local_live`, `wf_review_decision_cloud`), byte-identical to the SUMMARY's quoted RED and to the shipped allowlist keys; synthetic-Merge check reproduced `RULE5_FIRES_ON_SYNTHETIC` |
| 6 | `mergeInputContract.test.mjs` mirrors rule 5 and pins the allowlist as EXACTLY the census in both directions | ✓ VERIFIED | `tests/n8n/mergeInputContract.test.mjs:86-150` (`MULTI_PRODUCER_TOLERANT`), `:190-204` (`multiProducer` bucket), `:244-278` (census test, independent connections walk); `node --test tests/n8n/mergeInputContract.test.mjs` → 19/19 pass |
| 7 | Regenerating every `n8n/wf_*.json` through the builder produces zero diff | ✓ VERIFIED | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` → `ZERO_JSON_DIFF`; `git diff --stat` across the 3 task commits touches only `scripts/build_cloud_workflows.py`, `tests/n8n/mergeInputContract.test.mjs`, and the 2 todo paths — no `n8n/` file appears in any commit |
| 8 | MN-01 and NF-MJ-01 remain open, carried into their own pending todo, not closed | ✓ VERIFIED | `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` carries both verbatim (`grep -q MN-01`/`NF-MJ-01` both hit); old pending todo path no longer exists (`git mv`-renamed, history preserved via `git log --follow`); completed todo's "Resolved 2026-09-11" section states "MN-01 and NF-MJ-01 are NOT closed by this task" |

**Score:** 8/8 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/build_cloud_workflows.py` | rule 5 + `_MERGE_MULTI_PRODUCER_TOLERANT` (16 entries), docstring rewritten | ✓ VERIFIED | Confirmed 16 entries via direct import; docstring rule 5 text present at line ~11369-11377; old "Deliberately NOT enforced" paragraph absent (grep returns nothing) |
| `tests/n8n/mergeInputContract.test.mjs` | mirrored allowlist, `multiProducer` bucket, exact-both-directions census test, header rewritten | ✓ VERIFIED | All present; header paragraph at lines 36-56 documents rule 5 and supersedes the old "do not tighten" instruction |
| `.planning/todos/completed/2026-09-11-merge-input-contract-allows-many-producers-per-input.md` | Resolved section | ✓ VERIFIED | Present, accurately summarizes the change, explicitly notes MN-01/NF-MJ-01 not closed |
| `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` | new todo carrying both open questions verbatim | ✓ VERIFIED | Present, both questions carried in full with correct provenance note |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `_assert_generation_contracts` | `assert_merge_input_contract` | composition point | ✓ WIRED | Unchanged per scope fence; `main()` write sites untouched (diff confined to lines 11225-11431, the `assert_merge_input_contract` region and its preceding allowlist constant) |
| Python allowlist | JS `MULTI_PRODUCER_TOLERANT` | manual mirror, pinned by census test | ✓ WIRED | Both independently recompute the same 16-pair set from the committed JSON's connections graph (verified by direct re-execution of both code paths in this verification session) and match each other and the plan's stated census exactly |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Builder regenerates all 8 workflows with zero diff | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` | `ZERO_JSON_DIFF` | ✓ PASS |
| Allowlist holds exactly 16 entries | direct Python import + `len(...) == 16` assert | passes silently (no AssertionError) | ✓ PASS |
| Synthetic off-list two-producer Merge raises `ValueError` naming the Merge | direct call to `assert_merge_input_contract` on synthetic workflow dict | `RULE5_FIRES_ON_SYNTHETIC` | ✓ PASS |
| Empty-allowlist RED over all 8 committed JSON recovers exactly the 16-pair census | re-executed independently in this verification session (not copy-pasted from SUMMARY) | 16 pairs, byte-identical to SUMMARY's claimed set | ✓ PASS |
| `mergeInputContract.test.mjs` full suite | `node --test tests/n8n/mergeInputContract.test.mjs` | 19/19 pass | ✓ PASS |
| Full n8n node test suite | `node --test tests/n8n/*.test.mjs` | 1101/1101 pass | ✓ PASS |
| No forbidden safety-claim words in the 14 census-only reasons | scripted scan for "safe"/"harmless"/"proven" excluding the negated "not a proof of safety" phrasing | 0 flags (all 14 use the negation phrase only) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MIC-01 | Task 1 | rule 5 + allowlist, RED first, zero JSON diff | ✓ SATISFIED | reproduced independently above |
| MIC-02 | Task 2 | rule 5 mirrored in JS test, RED first | ✓ SATISFIED | reproduced independently above |
| MIC-03 | Task 3 | todo closed, MN-01/NF-MJ-01 carried forward | ✓ SATISFIED | reproduced independently above |

### Anti-Patterns Found

None. Scanned the diff region (lines 11225-11431 of `scripts/build_cloud_workflows.py`, and all of `tests/n8n/mergeInputContract.test.mjs`) for TODO/FIXME/XXX/placeholder markers — none found. No self-authored "safe"/"harmless"/"proven" acceptance claims among the 14 census-only entries (checked programmatically; the two exceptions, `Decide Company Action Merge` and `Collect Credits`, are the two families the plan explicitly permits to cite real evidence, and both cite specific tests/executions rather than asserting safety unsupported).

### Human Verification Required

None. All must-haves are statically/structurally checkable and were independently reproduced against the live codebase in this verification session (not merely re-read from the SUMMARY).

### Gaps Summary

No gaps. Every plan must-have was independently re-derived from the codebase (not trusted from SUMMARY.md's claims):
- The 16-entry census was recomputed twice, independently, from the raw committed JSON connections graphs (once via the Python builder's own function with the allowlist emptied, once via a from-scratch reimplementation of the walk) — both produced the identical 16-pair set that appears in the shipped allowlist.
- `git diff --quiet -- n8n/` was re-run after a fresh regeneration in this session, confirming zero graph change.
- The full node test suite (1101 tests) was re-run and passed, including `creditsSummaryUnderV1.test.mjs` and `walkerEngineFidelityV1.test.mjs`.
- The scope fence (only `assert_merge_input_contract` + its allowlist constant touched) was confirmed by inspecting the actual diff hunks of the task-1 commit — no jsCode, connection, or `main()` line changed.
- The todo carry-forward was confirmed by grepping the actual file content for MN-01/NF-MJ-01, and confirming the old pending path no longer exists while `git log --follow` shows continuous history (proving `git mv`, not delete+recreate).
- No deploy, bounce, or arm occurred: no commit touches any `n8n/` file, and no deploy/arm script was invoked in this task's commits.

---

_Verified: 2026-09-11_
_Verifier: Claude (gsd-verifier)_
