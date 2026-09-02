---
phase: 63-the-unattended-lane-actually-runs-unattended
plan: 03
subsystem: n8n
tags: [judge, escalation, replay, anthropic, offline-evidence, cost-optimization]

# Dependency graph
requires:
  - phase: 58-take-what-the-operator-actually-has
    provides: the judge escalation path (n8n/code/judge.js, config/escalation_policy.yaml) this replay tests against
provides:
  - "An offline replay harness (scripts/replay_judge_models.py) that compares two judge models against real stored n8n judge inputs, verdict by verdict, on the confidence_band-only class specifically"
  - "A committed DROP verdict (63-JUDGE-REPLAY-VERDICT.json) that 63-04's checkpoint reads: the cheaper-model lever (D-63-05) does not ship"
affects: [63-04-the-cheaper-model-if-it-earns-it (reads the verdict), any-future-63-B-revisit]

# Actuals (#2632)
actuals:
  tokens: 12000
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GET-only n8n executions-API replay: extract stored payloads once (cached to a gitignored working dir), then run all model comparison against the cache — no re-touch of n8n during --replay"
    - "Fixed-before-data-seen verdict thresholds (min_corpus, materiality classes) to prevent post-hoc threshold negotiation toward a desired SHIP"

key-files:
  created:
    - scripts/replay_judge_models.py
    - tests/test_replay_judge_models.py
    - .planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-VERDICT.json
    - .planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-REPORT.md
  modified:
    - .gitignore

key-decisions:
  - "Added a module-level load_dotenv() call to replay_judge_models.py (Rule 3 — blocking issue) so the script's own PLAN.md verify commands, which invoke it directly rather than through the repo's dotenv-wrapper one-liner, can see ANTHROPIC_API_KEY/N8N_URL/N8N_API_KEY from .env. Follows the apply_fit_score_formula.py precedent already in the codebase."
  - "Verdict is DROP (material_disagreement + insufficient_corpus), accepted as-is per D-63-06's prohibition on re-running with a relaxed threshold or a different corpus. 63-04 lands 63-A alone; build_cloud_workflows.py and n8n/wf_*.json are untouched."

requirements-completed: [2026-08-04-enrichment-throughput-ceiling]

coverage:
  - id: D1
    description: "End-to-end offline replay path (extraction, dual model call, comparison, verdict, report) proven with an injected call_model and no network access — Task 1's tracer"
    verification:
      - kind: unit
        ref: "tests/test_replay_judge_models.py (18 cases: SHIP/DROP/HARNESS_FAILURE branches, agree/immaterial/material/both_unparseable classification, empty-input and all-raising HARNESS_FAILURE, single-element insufficient_corpus, determinism, source-level write-verb/HubSpot-URL absence guard)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Real corpus extracted from n8n executions (91 scanned, 5 judge inputs, 3 confidence_band-only, contacts lane observed zero) and reasons[] distribution recorded as a D-63-07 by-product"
    verification:
      - kind: other
        ref: ".venv/bin/python scripts/replay_judge_models.py --extract --limit 250 (live run, output captured in this SUMMARY and in the committed report)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Live replay produced a verdict of exactly SHIP or DROP (DROP), committed as 63-JUDGE-REPLAY-VERDICT.json with no raw request body in any row, and a report documenting the material disagreement, the reasons distribution, and the zero-cost lines"
    verification:
      - kind: other
        ref: ".venv/bin/python -c \"...assert d['verdict'] in ('SHIP','DROP'); assert all('judge_request_body' not in r for r in d['rows'])\" (plan's own verify command)"
        status: pass
    human_judgment: false

duration: ~25min (this continuation; Task 1 was completed in a prior session)
completed: 2026-09-02
status: complete
---

# Phase 63 Plan 03: Judge Model Replay Summary

**Offline replay of claude-sonnet-5 vs claude-haiku-4-5 over real stored n8n judge inputs returned DROP — one material `decision` disagreement plus a confidence_band-only corpus of 3 (below the fixed minimum of 10) — so the cheaper-model routing lever (D-63-05) does not ship and 63-04 lands 63-A alone.**

## Performance

- **Duration:** ~25 min for this continuation (Task 2 + the load_dotenv fix); Task 1 (the harness + 18 offline tests) was completed in a prior session and is not re-timed here.
- **Completed:** 2026-09-02T06:14:00Z (approx, last commit)
- **Tasks:** 2 (Task 1 completed by prior agent; Task 2 completed this session)
- **Files modified:** 5 total across the plan (scripts/replay_judge_models.py, tests/test_replay_judge_models.py, .gitignore, 63-JUDGE-REPLAY-VERDICT.json, 63-JUDGE-REPLAY-REPORT.md)

## Accomplishments

- Built `scripts/replay_judge_models.py`: a pure, offline-testable comparison core (`build_report`) with a thin live shell, extracting stored judge inputs from n8n executions (GET only) and replaying them through two Anthropic models with no other network side effects.
- Ran the real replay against executions `11973`–`12069`: 91 executions scanned, 5 judge inputs found (companies-lane only — contacts lane confirmed disarmed/zero as expected), 3 in the `confidence_band`-only class this evidence is about.
- Verdict: **DROP**. One of the three compared inputs (`11975:0`) disagreed materially on `decision` (`accept_research` vs `accept`) despite agreeing on `chosen_value`; the corpus was also below the fixed `min_corpus` of 10. Both reasons are recorded in the committed artifact.
- Committed `63-JUDGE-REPLAY-VERDICT.json` (no raw request bodies, company names, or evidence URLs in any row — T-63-11 verified by test and by inspection) and `63-JUDGE-REPLAY-REPORT.md` with the full corpus provenance, reasons[] distribution (D-63-07 by-product), the material disagreement written out in full, and the zero-cost lines (0 provider credits, 0 HubSpot writes, 0 new n8n executions, 6 Anthropic calls).

## Task Commits

1. **Task 1: End-to-end tracer (harness + 18 offline tests)** - `1db10b6` (feat) — completed by prior agent
2. **Task 2 deviation: load .env at module import** - `a08db55` (fix, Rule 3)
3. **Task 2: Extract real corpus, run live replay, commit verdict** - `16a84ae` (feat)

**Plan metadata:** commit pending (this SUMMARY)

## Files Created/Modified

- `scripts/replay_judge_models.py` - Extraction (`extract_corpus`), selection (`confidence_band_only`), comparison (`build_report`), report writer (`_write_report`), and CLI (`main`). Module-level `load_dotenv()` added this session.
- `tests/test_replay_judge_models.py` - 18 offline unit tests covering every named verdict/classification branch plus source-level write-verb and HubSpot-URL absence guards.
- `.gitignore` - `.judge-replay-corpus/` entry (Task 1).
- `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-VERDICT.json` - Committed machine-readable verdict for 63-04.
- `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-JUDGE-REPLAY-REPORT.md` - Human-readable report with corpus provenance, reasons distribution, material disagreement detail, and cost accounting.

## Decisions Made

- **[Rule 3 - Blocking] Added `load_dotenv()` at module import time.** The prior agent's Task 1 checked `ANTHROPIC_API_KEY`/`N8N_URL`/`N8N_API_KEY` as exported shell variables and found them unset, halting at a precondition it evaluated as unmet. The orchestrator verified those credentials ARE present in `.env` (permission-blocked to Read/cat/grep in this project) via `python-dotenv`, exactly as `scripts/run_scoring_parity.py` documents. Rather than requiring the operator invocation to always route through the repo's `python -c "from dotenv import load_dotenv; load_dotenv(); ..."` wrapper one-liner, this script now calls `load_dotenv()` itself at import time — matching the existing `apply_fit_score_formula.py` precedent — so its own PLAN.md verify commands (`.venv/bin/python scripts/replay_judge_models.py --extract ...`) work as written. Verified: tests still pass (18/18) after the change; the live `--extract` and `--replay` runs both succeeded.
- **DROP accepted as-is, no re-run.** Per D-63-06's explicit prohibition, the DROP verdict (material_disagreement + insufficient_corpus) was not re-run with a relaxed `min_corpus`, a different corpus, or a redefined materiality rule. The thresholds were fixed in Task 1 before this data existed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added module-level `load_dotenv()` call**
- **Found during:** Task 2 (resuming after the precondition-unmet halt)
- **Issue:** `scripts/replay_judge_models.py` read `ANTHROPIC_API_KEY`/`N8N_URL`/`N8N_API_KEY` via bare `os.getenv()`. Those credentials exist only in `.env`, which is permission-blocked to Read/Bash in this project and is not auto-loaded by a direct `python scripts/replay_judge_models.py` invocation — the exact invocation shape the plan's own verify commands use. Without this fix, every `--extract`/`--replay` call would REFUSE.
- **Fix:** Added `from dotenv import load_dotenv; load_dotenv()` immediately after the `sys.path` setup, before any other project import, matching the existing `scripts/apply_fit_score_formula.py` precedent for a module-level (rather than wrapper-invoked) `load_dotenv()`.
- **Files modified:** `scripts/replay_judge_models.py`
- **Verification:** `.venv/bin/python -m pytest tests/test_replay_judge_models.py -q` still 18 passed after the change; live `--extract --limit 250` and `--replay` both succeeded using credentials sourced only from `.env`.
- **Committed in:** `a08db55`

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Necessary for the plan's own verify commands to be runnable as written. No scope creep — no other behavior of the harness was changed.

## Issues Encountered

None beyond the resolved precondition (see `<precondition_resolved>` in the continuation prompt) — the orchestrator's `.env`/`dotenv` check confirmed all three required credentials were available before this session began.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 63-04 has `63-JUDGE-REPLAY-VERDICT.json` to read. Its checkpoint will find `verdict: "DROP"` and, per D-63-06, should proceed with 63-A landing alone — `build_cloud_workflows.py`'s `ANTHROPIC_JUDGE_MODEL` constant and every `n8n/wf_*.json` remain untouched.
- No blockers for 63-04's own scope (deployment of Phase 62 + 63-A's changes, per D-63-08) — this plan's DROP only removes the cheaper-model routing from what gets deployed, it does not block the deploy itself.
- The narrow live window observed (executions `11973`–`12069`, only 91 total, only 5 carrying judge inputs) is worth noting for anyone re-attempting this evidence gathering later: retention or simply low volume bounds how much corpus is available on demand.

---
*Phase: 63-the-unattended-lane-actually-runs-unattended*
*Completed: 2026-09-02*

## Self-Check: PASSED

All key files verified present on disk (`scripts/replay_judge_models.py`, `tests/test_replay_judge_models.py`, `63-JUDGE-REPLAY-VERDICT.json`, `63-JUDGE-REPLAY-REPORT.md`, this SUMMARY). All three commit hashes (`1db10b6`, `a08db55`, `16a84ae`) confirmed present in `git log --oneline --all`. `.venv/bin/python -m pytest tests/test_replay_judge_models.py -q` re-confirmed 18 passed. The plan's own verdict-check command re-ran clean (`verdict DROP`, no `judge_request_body` in any row).
