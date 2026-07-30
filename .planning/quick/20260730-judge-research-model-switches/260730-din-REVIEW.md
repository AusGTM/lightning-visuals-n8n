---
phase: 260730-din-judge-research-model-switches
reviewed: 2026-07-30T00:00:00Z
depth: quick
files_reviewed: 19
files_reviewed_list:
  - .env.example
  - CLAUDE.md
  - n8n/code/judge.js
  - scripts/build_cloud_workflows.py
  - scripts/deploy_n8n_workflows.py
  - src/validator_sonnet.py
  - src/web_research.py
  - tests/test_builder_flag_parity.py
  - tests/test_deploy_flag_overlay.py
  - tests/test_deploy_write_safety_overlay.py
  - tests/test_enabled_build_invariants.py
  - tests/test_main.py
  - tests/test_service.py
  - tests/test_contact_ingest.py
  - tests/test_e2e_ingest.py
  - tests/n8n/contactResearchChainRowFlow.test.mjs
  - tests/n8n/enabledResearchLaneFlow.test.mjs
  - tests/n8n/researchRequestSponsorshipContract.test.mjs
  - n8n/wf_enrichment_cloud.json (generated artifact, verified for consistency)
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 260730-din: Code Review Report — judge/research model-switch split

**Reviewed:** 2026-07-30
**Depth:** quick
**Files Reviewed:** 19 (17 source/test files + 2 generated JSON workflows sampled for consistency)
**Status:** clean

## Summary

Diff `aac1f9f^..HEAD` (3 commits: feat + 2 test-rename commits) implements the locked
spec exactly: `ANTHROPIC_SONNET_MODEL` split into `ANTHROPIC_RESEARCH_MODEL` /
`ANTHROPIC_JUDGE_MODEL` (both default `claude-sonnet-5`), `ALLOW_SONNET_ESCALATION` →
`ALLOW_JUDGE_ESCALATION` (default flipped `false`→`true`), `MAX_SONNET_VALIDATIONS_PER_RUN`
→ `MAX_JUDGE_VALIDATIONS_PER_RUN` (default raised `10`→`50`), and the now-meaningless
`ALLOW_SONNET_ESCALATION` overlay entry deleted from
`scripts/deploy_n8n_workflows.py::_OVERLAY_FLAG_SPEC`.

Verification performed beyond reading the diff, per the "verify consistency" instruction:

- **`n8n/code/judge.js` comment-only constraint**: confirmed via `git diff --word-diff`
  — both changed lines are inside `//` comments; zero executable-line edits.
- **Old names fully purged**: `grep -rn "ANTHROPIC_SONNET_MODEL\|ALLOW_SONNET_ESCALATION\|MAX_SONNET_VALIDATIONS_PER_RUN"` across `n8n/`, `scripts/`, `src/`, `tests/`, `.env.example`, `CLAUDE.md`, `main.py`, `config/` returns zero matches (only stale `__pycache__` binaries, not source).
- **Generated workflow consistency**: `n8n/wf_enrichment_cloud.json` bakes
  `const ANTHROPIC_RESEARCH_MODEL = "claude-sonnet-5";`,
  `const ANTHROPIC_JUDGE_MODEL = "claude-sonnet-5";`,
  `const ALLOW_JUDGE_ESCALATION = true;`, `const MAX_JUDGE_VALIDATIONS_PER_RUN = 50;`
  in both companies and contacts chains — matches the locked defaults exactly.
  `n8n/wf_enrichment_local_live.json` correctly reads these via
  `($vars && $vars.X) || $env.X || "<default>"` with the same literal defaults, never
  baking a live-mode literal.
- **Frozen fixture regen, not hand-patch**: `tests/fixtures/companies_jscode_frozen.json`
  new/old-name occurrence counts are internally consistent (0 old-name hits, matching
  new-name hits across both `cloud`/`local_live` fixture halves), and
  `tests/test_companies_factory_frozen.py`'s byte-identity assertions (which call
  `build_enrichment_cloud()`/`build_enrichment_local_live()` fresh and compare against
  the fixture) pass — this is a stronger guarantee than diff-reading alone that the
  fixture wasn't hand-edited.
- **Full suite run**: `.venv/bin/python -m pytest` → 601 passed; `node --test
  tests/n8n/*.test.mjs` → 309 passed, 0 failed.
- **Test-rename correctness spot-checked**: `tests/test_deploy_flag_overlay.py`'s
  removed `test_enable_baked_flags_independence_escalation_only` (no longer applicable
  — the flag left the overlayable set) has a structural replacement in
  `tests/test_enabled_build_invariants.py::test_committed_build_judge_escalation_is_always_true`
  + its non-vacuity companion, so the "escalation is armed in the committed build"
  property is still covered, just from the correct angle (committed-armed vs.
  overlay-toggled).
- **Doc/env parity**: `.env.example` and `CLAUDE.md` both carry the new 4-line
  model/flag/cap block with identical values; no stale example left mixing old and new
  names.

No incorrect behavior, security issue, or quality defect found. All reviewed changes
are mechanical renames/splits plus the two explicitly-decided default changes (judge
armed, cap raised), applied consistently across every call site, generated artifact,
and test file in scope.

All reviewed files meet quality standards. No issues found.
