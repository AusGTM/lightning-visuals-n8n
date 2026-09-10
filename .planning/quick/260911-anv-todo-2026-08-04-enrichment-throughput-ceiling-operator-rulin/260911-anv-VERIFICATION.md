---
phase: quick-260911-anv
verified: 2026-09-11T08:20:00Z
status: passed
score: 5/5 must-haves verified
covered_files: [".planning/quick/260911-anv-todo-2026-08-04-enrichment-throughput-ceiling-operator-rulin/260911-anv-PLAN.md", ".planning/quick/260911-anv-todo-2026-08-04-enrichment-throughput-ceiling-operator-rulin/260911-anv-SUMMARY.md", ".planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md", "scripts/judge_reason_distribution.py", "tests/test_judge_reason_distribution.py"]
covered_digest: "v1:sha256:9f7054dd8a07b67504c3cdb02ce6bfaa70a940094c231a6006afd2a5f3fe54ac"
behavior_unverified: 0
overrides_applied: 0
---

# Quick 260911-anv: Judge-reason distribution measurement Verification Report

**Item Goal:** Answer the operator's 2026-08-04 throughput-ceiling todo's "measure first"
ruling: (a) confirm `judge_reasons[]` visibility on Judge Gate's downstream row, (b) confirm
the live `max_uses` web-research budget against `WEB_RESEARCH_MAX_SEARCHES=5`, (c) sample the
judge-reason distribution from past executions if reachable read-only — with no builder edit,
no workflow-JSON edit, no deploy, no arming, band bounds unchanged at `[75, 85]`.

**Verified:** 2026-09-11T08:20:00Z
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The todo records, with evidence, that Judge Gate already emits `judge_reasons` on every row it passes downstream — no builder change needed | ✓ VERIFIED | Todo's "(a)" section cites `judge_pass1_block_js` (both targets), `applyCostCap` spread, pass-3 return, `tests/n8n/judge.test.mjs:444`, and frozen runData `exec_12354`. `node --test tests/n8n/judge.test.mjs` — 39/39 pass, including the RO-2 and non-escalating-row assertions. `git diff --stat -- n8n/ scripts/build_cloud_workflows.py` empty — no edit was made to support this claim. |
| 2 | The todo records the `max_uses` baked into committed `n8n/wf_enrichment_cloud.json` and states it is a build-time literal, not a runtime env read | ✓ VERIFIED | `python -c "... assert 'WEB_RESEARCH_MAX_SEARCHES = 5' in n['Build Research Request'] and ... in n['Build Contact Research Request']"` → `ok`. Todo's "(b)" section states the number (5) and the mechanism (`_flag_const(cloud=True)` literal, no `$env` read), matching source. |
| 3 | The todo records either a measured judge-reason distribution or an explicit not-achievable statement plus reason | ✓ VERIFIED | Todo's "(c)" section reports a real GET-only run (89 executions, ids `12264`-`12356`), a genuine zero-escalation result with cause (retention rolled past the last provider-enabled run — confirmed via `research_candidate.matched: false` and `mode: "propose"`/`provider_enabled: false` on sampled rows), the 404 on the plan's named legacy ids, and cites Phase 63's `63-JUDGE-REPLAY-VERDICT.json` as the surviving real-escalation sample in both branches. |
| 4 | `scripts/build_cloud_workflows.py` and every `n8n/wf_*.json` are byte-unchanged by this plan | ✓ VERIFIED | `git diff --stat -- n8n/ scripts/build_cloud_workflows.py` → empty. Node-count/hash check: `len(nodes)==287` and `Judge Gate` jsCode sha256[:16] == `5804fec76c32c600` — both match plan's pinned values. |
| 5 | Escalation confidence band stays `[75, 85]`; RO-2 test stays green | ✓ VERIFIED | `grep -c 'ESCALATION_CONFIDENCE_BAND = \[75, 85\]' n8n/code/escalation.generated.js` → `1`. `pytest tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts -x -q` → 1 passed. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/judge_reason_distribution.py` | GET-only CLI reusing `enrichment_cost_ledger` readers | ✓ VERIFIED | Exists, 231 lines. Imports `_get_execution`, `_list_executions`, `_node_output_items` from `enrichment_cost_ledger`; zero `requests.(post\|put\|patch\|delete)` matches outside comments. `summarize()` handles malformed input (missing node, non-list, non-dict item, missing `data`, absent `judge_reasons`) without raising — read and confirmed line-by-line. |
| `tests/test_judge_reason_distribution.py` | Offline test of `summarize` covering behavior spec | ✓ VERIFIED | Exists, 162 lines. Covers: two runs folded, two-reason row, capped row, unmatched-research row, empty-reasons row, absent-key row, non-dict item, malformed run, both lanes. `pytest tests/test_judge_reason_distribution.py -x -q` → passes (bundled into the 14-pass run above). |
| `.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md` | Dated 2026-09-11 section with (a)/(b)/(c) | ✓ VERIFIED | Frontmatter `updated: 2026-09-11`; body contains "## Measurement 2026-09-11" section with all three sub-answers and a citation to `63-JUDGE-REPLAY-VERDICT.json`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scripts/judge_reason_distribution.py` | `scripts/enrichment_cost_ledger.py` | `from enrichment_cost_ledger import _get_execution, _list_executions, _node_output_items` | ✓ WIRED | Confirmed by direct read of source; no separate n8n HTTP client implemented. |
| `scripts/judge_reason_distribution.py` | `Judge Gate` / `Contact Judge Gate` node output | reads `run_data[node_name]`, folds every run | ✓ WIRED | `summarize()` reads both `COMPANIES_NODE = "Judge Gate"` and `CONTACTS_NODE = "Contact Judge Gate"`, iterating `runs` (a list, folding every run per the v1-can-fire-twice spec). |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `summarize()` unit tests pass | `.venv/bin/python -m pytest tests/test_judge_reason_distribution.py -x -q` | passed | ✓ PASS |
| RO-2 judge-gate test stays green | `.venv/bin/python -m pytest tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts -x -q` | 1 passed | ✓ PASS |
| Node judge test suite green | `node --test tests/n8n/judge.test.mjs` | 39/39 pass | ✓ PASS |
| Full n8n test suite green | `node --test tests/n8n/*.test.mjs` | 1101/1101 pass | ✓ PASS |
| Workflow JSON and builder untouched | `git diff --stat -- n8n/ scripts/build_cloud_workflows.py` | empty | ✓ PASS |
| Node count / Judge Gate hash unchanged | inline python assertion | `287` nodes, hash `5804fec76c32c600` | ✓ PASS |
| No write verbs in new script | `grep -cE 'requests\.(post\|put\|patch\|delete)'` (comments excluded) | `0` | ✓ PASS |
| No debt markers in new files | `grep -nE "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` | no matches | ✓ PASS |

### Requirements Coverage

No formal REQUIREMENTS.md entries map to this quick-batch item (quick tasks are not
roadmap phases). N/A.

### Anti-Patterns Found

None. No debt markers, no stub returns, no hardcoded-empty data flowing to output in
either new file.

### Scope Check

Both commits (`0fe2003c` Task 2, `253a75b5` Task 3) touch exactly the three files declared
in the plan's frontmatter (`scripts/judge_reason_distribution.py`,
`tests/test_judge_reason_distribution.py`,
`.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md`) — confirmed via
`git show --stat` on both. No edit to any sibling item's files
(`operator-claude-plugin/scripts/suggest_contacts.py`, `search_fallback.py`,
`skills/suggest-contacts/SKILL.md`) — untouched, consistent with the environment note.

### Human Verification Required

None. All must-haves are statically/programmatically verifiable and were verified against
the actual codebase (not SUMMARY.md's claims alone) — every test named in the plan's verify
blocks was re-run independently by this verifier and matched the SUMMARY's reported results.

### Gaps Summary

No gaps. All five must-have truths hold, all named tests pass, the workflow/builder diff
is empty, and the band literal is unchanged.

---

_Verified: 2026-09-11T08:20:00Z_
_Verifier: Claude (gsd-verifier)_
