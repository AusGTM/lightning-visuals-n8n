---
phase: phase-4
plan: 01
subsystem: dry-run-writeback
tags: [mvp, dry-run, safety-gates, hubspot, writeback, patch]
requires: [src/schemas.py, src/merge_policy.py, src/providers.py, src/web_research.py, src/normalizer.py, tests/fixtures]
provides: [patch_record, get_record, search_records, run_local_mvp]
affects: [n8n-production-workflows]
tech-stack:
  patterns: [dry-run-sentinel, env-flag-safety-gates, side-effect-free-import, return-for-testability]
key-files:
  created: [src/hubspot_client.py, main.py, tests/test_main.py]
  modified: []
decisions:
  - "load_dotenv() moved into __main__ guard (Deviation 1): keeps `import main` side-effect-free so the hermetic suite never leaks ANTHROPIC_API_KEY into a live Haiku call"
  - "run_local_mvp() returns the assembled patch dict (Deviation 2): tests assert on the dict, not parsed stdout"
  - "test _source assertion excludes the status key enrichment_primary_source (Rule 1 test-correctness): it is part of status_patch, not staging metadata"
metrics:
  duration: ~10m
  completed: 2026-07-07
status: complete
---

# Phase 4 Plan 01: Dry-Run PATCH Output & Safety Gates Summary

Wires Phases 1–3 into an end-to-end local run (`main.run_local_mvp`) that prints the four sections and the exact HubSpot PATCH it would send, honours the env-flag safety gates (promote only `lv_icp_*` to canonical, stage firmographics), and performs zero live HubSpot writes via a dry-run sentinel in `patch_record` — proven by a 38-test offline suite that asserts `requests.patch` is never called.

## Files Created

- `src/hubspot_client.py` — CLAUDE.md §12.9 verbatim: `BASE_URL`, `hs_headers`, `get_record`, `patch_record`, `search_records`. `patch_record(dry_run=True)` prints only the payload dict (never the token) and returns `{"dry_run": True, "payload": {...}}` without touching `requests.patch`. Commit `047c0c5`.
- `main.py` — CLAUDE.md §12.10 `run_local_mvp` with two flagged deviations (below). Assembles the flag-gated patch, prints the four sections, calls `patch_record(dry_run=DRY_RUN)`. Commit `745c68e`.
- `tests/test_main.py` — offline deterministic SC1/SC2/SC3 proof; classifier monkeypatched at the `src.merge_policy` import site, `ANTHROPIC_API_KEY` stripped, `requests.patch` replaced by a raising sentinel. Commit `ae86b37`.

## Deviations from Plan

Both deviations were mandated by the plan (`<action>` of Task 2) and applied with inline comments.

**1. [Plan-mandated] `load_dotenv()` moved into the `__main__` guard**
- Rationale: a real `.env` with `ANTHROPIC_API_KEY` exists. Module-level `load_dotenv()` (as in §12.10) would leak the key on `import main`, firing a live Haiku call inside the hermetic suite (`test_merge_policy.test_integ_wires_icp_scorer` runs the classifier unmonkeypatched). Loading only under `__main__` keeps `import main` side-effect-free; Proof B's CLI still loads the real `.env`.
- Files: `main.py`. Commit `745c68e`.

**2. [Plan-mandated] `run_local_mvp()` returns the assembled patch dict**
- Rationale: lets Proof A assert on the dict deterministically instead of parsing stdout.
- Files: `main.py`. Commit `745c68e`.

**3. [Rule 1 - test correctness] `_source` assertion excludes `enrichment_primary_source`**
- Found during: Task 3 first suite run (`test_sc3_staging_flag_toggles` failed `assert not True`).
- Issue: the plan's literal wording ("no key ends with `_source`") collides with `enrichment_primary_source`, which lives in `status_patch` and is always present regardless of `ALLOW_STAGING_WRITES`.
- Fix: assert `[k for k in patch if k.endswith("_source") and k != "enrichment_primary_source"] == []` — precisely tests that metadata staging keys (`{field}_source`) are withheld, which is the real intent.
- Files: `tests/test_main.py`. Commit `ae86b37`.

## Proof A (the gate) — PASSED

`.venv/bin/python -m pytest tests/ -q` with `ANTHROPIC_API_KEY` stripped:

```
38 passed in 0.67s
```

Full suite green offline: `test_scaffold` + `test_icp_scoring` + `test_merge_policy` + `test_main`. No network, no key required. `requests.patch` sentinel confirms zero HubSpot writes at runtime.

## Proof B (live smoke, non-gating) — ERRORED (captured, does NOT fail the phase)

Command: `set -a; . ./.env; set +a; DRY_RUN=true ALLOW_CANONICAL_WRITES=false .venv/bin/python main.py`

Result: the run reached the live Haiku classifier and failed with a model-not-found before any HubSpot call:

```
anthropic.NotFoundError: Error code: 404 - {'type': 'error', 'error':
{'type': 'not_found_error', 'message': 'model: claude-3-5-haiku-latest'}}
```

- Cause: `.env` sets `ANTHROPIC_HAIKU_MODEL=claude-3-5-haiku-latest`, which this account/endpoint does not resolve (the SDK also warned `ANTHROPIC_API_KEY takes precedence over profile/federation auto-discovery`). This is a config/model-access issue, exactly the class the plan pre-declared as non-gating; `.env` is user-controlled and out of scope for this phase.
- **Zero HubSpot HTTP writes reached HubSpot.** The traceback shows the crash occurred in `build_merge_result` (`main.py:45`, the Haiku classifier), which runs *before* `patch_record` (`main.py:88`) is ever called. No PATCH was assembled or sent.

### Representative emitted PATCH (offline deterministic run, `promote_fake` classifier)

Since Proof B produced no payload, this is the emitted PATCH from the offline pipeline (same flags: `DRY_RUN=true`, `ALLOW_STAGING_WRITES=true`, `ALLOW_CANONICAL_WRITES=false`, `ALLOW_ICP_SCORE_WRITES=true`). No secrets appear in the payload.

- `lv_icp_tier`: **A**  (`lv_icp_fit_score`: 70, `lv_icp_confidence`: 85, `lv_icp_scoring_version`: lv-icp-v0.1)
- `lv_icp_score_breakdown`: org_type=40, produces_content=20, geography(AU)=10, revenue_band(unknown)=0; no hard vetoes.
- Staging keys present (21): `apollo_*`, `zoominfo_*`, `claude_web_*` (e.g. `zoominfo_lv_revenue_band`, `claude_web_lv_org_type`) plus `{field}_source` metadata.
- Status: `enrichment_status=needs_review`, `enrichment_last_sources=apollo,claude_web,zoominfo`, `enrichment_validation_path=haiku_plus_sonnet`.
- Withheld from canonical (SC2 confirmed): `domain`=False, `annualrevenue`=False, `lv_org_type`=False.

## Threat Mitigations Applied

- **T-phase4-01 (Tampering, write path):** `DRY_RUN=true` everywhere; `patch_record` returns the sentinel before `requests.patch`; the suite's raising sentinel proves `requests.patch` is never called. `DRY_RUN` never set to false; live writeback out of scope.
- **T-phase4-02 (Info disclosure):** `patch_record` prints only the payload dict, never `hs_headers`/token. This SUMMARY contains no secret values; `.env` confirmed gitignored (`git check-ignore .env` → ignored).
- **T-phase4-03 (Cost DoS):** Proof B ran once on a single fixture company; the offline gate needs no key.

## Success Criteria

- SC1 ✅ — four print sections asserted (`test_sc1_prints_four_sections`).
- SC2 ✅ — only `lv_icp_*` promoted to canonical, firmographics staged, no bare `domain`/`annualrevenue`/`lv_org_type` (`test_sc2_promotes_only_icp_stages_firmographics`); no live write (sentinel).
- SC3 ✅ — `ALLOW_STAGING_WRITES` / `ALLOW_CANONICAL_WRITES` / `DRY_RUN` toggles behave as documented (`test_sc3_*`).
- Gate ✅ — `pytest tests/ -q` green offline (38 passed).

## Self-Check: PASSED

- Files exist: `src/hubspot_client.py`, `main.py`, `tests/test_main.py` — all present.
- Commits exist: `047c0c5`, `745c68e`, `ae86b37` — all in `git log`.
