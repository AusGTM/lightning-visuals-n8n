---
phase: phase-3
plan: 01
subsystem: enrichment-merge
tags: [enrichment, merge, non-clobber, providers, mvp]
requires: [src/schemas.py, src/icp_scoring.py, config/field_policy.yaml, config/provider_priority.yaml, tests/fixtures]
provides: [build_merge_result, provider_to_candidates, get_mock_provider_waterfall, mock_claude_web_research]
affects: [phase-4-main]
tech-stack:
  patterns: [mock-provider-adapters, deterministic-gate-governance, cheap-first-llm-cascade, non-clobber-merge]
key-files:
  created: [src/providers.py, src/web_research.py, src/normalizer.py, src/classifier_haiku.py, src/validator_sonnet.py, src/merge_policy.py, tests/test_merge_policy.py]
  modified: []
decisions:
  - "choose_best returns [0] (single CandidateValue); §12.8's list form crashes every caller"
  - "FieldDecision.evidence_url narrowed to scalar first-URL; §12.8 passed a list to the frozen Optional[str] schema field"
  - "source_metadata {field}_evidence_url kept as list (Phase 4 serializes); offline classifier stage_only bypassed via monkeypatch to prove promote path"
metrics:
  duration: ~7m
  completed: 2026-07-07
status: complete
---

# Phase 3 Plan 01: Enrichment Pipeline & Non-Clobber Merge Summary

Mock provider/web-research adapters feed a normalizer into a deterministic field-ownership gate plus a Haiku/Sonnet cascade, producing a non-clobber merge that stages provider values, promotes only governance-permitted fields, wires Phase 2's `compute_icp_score`, and stamps full source attribution — proven by a 10-test offline suite.

## Files Created

- `src/providers.py` — `ProviderAdapter` base + Mock Apollo/Lusha/ZoomInfo adapters + `get_mock_provider_waterfall` (§12.2). Commit `f86edfb`.
- `src/web_research.py` — `mock_claude_web_research` / `claude_web_research` (§12.3). Commit `f86edfb`.
- `src/normalizer.py` — `normalize_*` helpers + `provider_to_candidates` (§12.4). Commit `f86edfb`.
- `src/classifier_haiku.py` — `classify_field_with_haiku` with offline stage_only fallback (§12.5). Commit `5a5e34c`.
- `src/validator_sonnet.py` — `validate_conflict_with_sonnet` with conservative needs_review guard (§12.6). Commit `5a5e34c`.
- `src/merge_policy.py` — `deterministic_gate`, `choose_best`, `has_conflict`, `source_metadata`, `build_merge_result` (§12.8, two documented fixes). Commit `5a5e34c`.
- `tests/test_merge_policy.py` — 10-test offline proof (SC1–SC4 + wiring). Commit `318a0dc`.

## Verification

Full-phase proof, run from repo root, no network, no ANTHROPIC_API_KEY:

```
.venv/bin/python -m pytest tests/test_merge_policy.py tests/test_icp_scoring.py tests/test_scaffold.py -q
.................................                                        [100%]
33 passed in 0.65s
```

Offline confirmation (stripped environment — no key, no network):
```
env -i PATH="$PATH" HOME="$HOME" .venv/bin/python -m pytest tests/test_merge_policy.py -q
10 passed in 0.52s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [SPEC-defect fix — mandated] choose_best returned a list instead of one candidate**
- **Found during:** Task 2 (transcription of §12.8)
- **Issue:** §12.8's `choose_best` returned the whole sorted LIST, but every caller treats it as one candidate — `deterministic_gate` does `best.confidence`, `build_merge_result` reads `chosen.normalized_value`. A list has no `.confidence`, so the spec raised AttributeError on the first field with candidates and `build_merge_result` could not run.
- **Fix:** Return the top element `sorted(...)[0] if candidates else None`; sort key unchanged (priority index asc, confidence desc). Inline comment documents the deviation. Mirrors the Phase 2 precedent.
- **File modified:** src/merge_policy.py
- **Commit:** 5a5e34c

**2. [SPEC-defect fix] FieldDecision.evidence_url received a list, not a scalar**
- **Found during:** Task 2 verification (build_merge_result raised pydantic ValidationError)
- **Issue:** §12.8 assigned the `evidence_urls` LIST to `FieldDecision.evidence_url`, but the frozen Phase 1 schema types that field `Optional[str]`. Pydantic v2 rejects a list → `build_merge_result` crashed before returning. Schemas are out of scope for this phase, so the fix belongs in merge_policy.
- **Fix:** Narrow to the first URL (scalar): `chosen.evidence.evidence_urls[0] if ... else None`. Inline comment documents it. This is separate from `source_metadata`'s `{field}_evidence_url`, which stays the full list (plain dict, no validation) exactly as the tests assert and as Phase 4 will serialize.
- **File modified:** src/merge_policy.py
- **Commit:** 5a5e34c

### Transcribed-as-is (deliberately not "fixed")

- `source_metadata` sets `{field}_evidence_url` to the LIST `candidate.evidence.evidence_urls`; SC4 asserts the list form; Phase 4 handles serialization.
- The offline classifier fallback returns `stage_only`, so no firmographic field promotes to canonical offline (only `lv_icp_*` outputs do). The Task 3 tests use `monkeypatch` at the `src.merge_policy` import site to force the promote path deterministically rather than requiring a live key. Net offline `build_merge_result` on the fixture yields tier `Unscored` / status `needs_review` (org_type stays blank when nothing is promoted) — correct conservative behavior.

## Self-Check: PASSED
- src/providers.py: FOUND
- src/web_research.py: FOUND
- src/normalizer.py: FOUND
- src/classifier_haiku.py: FOUND
- src/validator_sonnet.py: FOUND
- src/merge_policy.py: FOUND
- tests/test_merge_policy.py: FOUND
- Commit f86edfb: FOUND
- Commit 5a5e34c: FOUND
- Commit 318a0dc: FOUND
