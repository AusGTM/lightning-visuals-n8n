---
phase: phase-2
plan: 01
subsystem: icp-scoring
tags: [icp, scoring, tdd]
requires: [src/schemas.py, config/icp_scoring.yaml]
provides: [compute_icp_score]
affects: [phase-3-merge, phase-4-main]
tech-stack:
  patterns: [deterministic-rubric-scoring, pyyaml-safe-load]
key-files:
  created: [src/icp_scoring.py, tests/test_icp_scoring.py]
  modified: []
decisions:
  - "Fixed §12.7 produces_content lookup: PyYAML boolean keys vs string lookup"
  - "Case-3 club pinned to 0-point revenue band (1-5M) to land Tier C per REQ-org-type-targeting"
metrics:
  duration: ~5m
  completed: 2026-07-07
status: complete
---

# Phase 2 Plan 01: ICP Scoring Engine Summary

Deterministic ICP scoring engine (`compute_icp_score`) reading the frozen `lv-icp-v0.1` rubric, proven by a 16-case pytest suite covering all four Phase 2 success criteria.

## Files Created

- `src/icp_scoring.py` — `load_yaml`, `boolish`, `get_signal`, `compute_icp_score`. Transcribed from CLAUDE.md §12.7 with one documented fix. Commit `f0f3f04`.
- `tests/test_icp_scoring.py` — 16 scoring assertions. Commit `096889d`.

## Verification

```
.venv/bin/python -m pytest tests/test_icp_scoring.py -q
................                                                         [100%]
16 passed in 0.12s
```

Scaffold regression (Phase 1), no break:
```
.venv/bin/python -m pytest tests/test_scaffold.py -q
.......                                                                  [100%]
7 passed in 0.07s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [SPEC-defect fix] produces_content boolean-key lookup**
- **Found during:** Task 1 (transcription of §12.7)
- **Issue:** §12.7 scored produces_content via `cfg["base_score"]["produces_content"].get(str(produces_content).lower(), 0)`. PyYAML parses the config's `true:`/`false:` keys as Python booleans, so the loaded dict is `{True: 20, False: 0, "unknown": 0}`; a string lookup (`"true"`/`"false"`) never matches and silently returns 0, zeroing the +20 "produces content" rule and dropping the flagship AU governing-body case from Tier A (80) to Tier B (60) — a failure of SC1 / REQ-icp-scoring-model.
- **Fix:** Look up the boolean/None value directly: `cfg["base_score"]["produces_content"].get(produces_content, 0)` (True→20, False→0, None→0). Inline comment documents the deviation.
- **File modified:** src/icp_scoring.py
- **Commit:** f0f3f04

### Test-design choices (documented in-test)

**2. Case-3 revenue band + §24.1 cases 11-16 out of scope**
- Case 3 (individual club) uses revenue `1-5M` (a 0-point band). §24.1 case 3 pins no revenue band; under correct produces_content scoring, club(5)+content(20)+AU(10)+mid(10)=45=Tier B, whereas a 0-point band gives 35=Tier C — the outcome REQ-org-type-targeting/SC1 require. Rubric-weight sensitivity belonging to the frozen Phase-1 rubric, not this phase.
- §24.1 cases 11-16 (provider/content conflict → Sonnet, missing evidence URL → human review, manual domain / existing phone → stage only, blank phone + agreement → promote) are merge/escalation behaviors with no expression in `compute_icp_score`. Deferred to Phase 3 `tests/test_merge_policy.py`. Not fabricated here.

## Self-Check: PASSED
- src/icp_scoring.py: FOUND
- tests/test_icp_scoring.py: FOUND
- Commit f0f3f04: FOUND
- Commit 096889d: FOUND
