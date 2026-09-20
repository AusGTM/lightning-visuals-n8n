---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
plan: 06
subsystem: exit-uat
tags: [n8n-deploy, recompute-proof, runbook, as-built-delta, todo-triage]

# Dependency graph
requires:
  - phase: 75-05
    provides: lv_icp_scoring_version live, 16-option region enum, flow 4626722240 on regions.home
  - phase: 75-03
    provides: the version stamp, ALLOW_HUBSPOT_RECOMPUTE_WRITES, the version-stale reroute
provides:
  - live n8n Cloud on the Phase 75 bodies (4 cloud workflows deployed disarmed, bounced)
  - two zero-cost recompute proofs (executions 12682, 12683) with pre-stated expectations
  - docs/OPERATOR-RESCORE.md D-75-14 bump-sweep and D-75-17 flag-flip procedures
  - CLAUDE.md §10.3.3 Phase 75 as-built delta (+ §4.0/§5.2/§10.1/§10.3/§13.0.2/§21.1 notes)
  - two triaged todos (Other-stamped re-enrich design; SJ-2 backstop question)
affects: []

# Actuals (#2632)
actuals:
  tokens: 0
  tasks: 4
  commits: 5
plan_head_before: b7a6ddde

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operator-run live window with expectations committed BEFORE the send (T-75-28)"
    - "Frozen-fixture evidence: derived verdicts read from redacted runData, never from the ack"

key-files:
  created:
    - .planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-DEPLOY-RECORD.md
    - .planning/phases/75-config-driven-region-whitelist-and-scoring-version-staleness/75-UAT.md
    - tests/n8n/fixtures/frozen/exec_12682.runData.json
    - tests/n8n/fixtures/frozen/exec_12683.runData.json
    - .planning/todos/pending/2026-09-20-other-stamped-records-cannot-be-rescued-by-recompute.md
  modified:
    - CLAUDE.md
    - docs/OPERATOR-RESCORE.md
    - .planning/todos/pending/2026-09-20-sj2-version-stale-backstop-is-armed-only.md (renamed from plan 03's file)

key-decisions:
  - "Operator selected proceed at the blocking-human gate; every live call (deploy, bounce, two
    POSTs, freezes, searches) was run by the operator from the ! shell — the subagents cannot
    read .env. Orchestrator drove the plan inline, verifying from artefacts."
  - "Proof (b) used an Other-stamped company (Jam TV 17317850381): no EU/UK/Unknown-stamped
    company exists live (search totals 0/0/0)."
  - "Only the 4 regenerated cloud bodies were deployed (--only per file); backend-status and
    suggest-discovery bodies are byte-unchanged this phase and were left alone."
  - "Plan 03's SJ-2 todo was RENAMED to plan 06's filename rather than duplicated — one todo."
  - "Other-stamped fork resolved as RE-ENRICH (two answers on one record; geography_score
    reads the stored property). Sized: 5 Other-stamped, 4 with a home-market country; flip
    count by recompute alone 0."

requirements-completed: []

coverage:
  - id: D-75-14
    description: "bump-sweep procedure exists as runbook text"
    verification:
      - kind: doc
        ref: "docs/OPERATOR-RESCORE.md § 2026-09-20 amendment (a)"
        status: pass
  - id: D-75-17
    description: "flag-flip procedure exists; flip NOT performed; flag reads false live"
    verification:
      - kind: live
        ref: "75-DEPLOY-RECORD.md bounce table, ALLOW_HUBSPOT_RECOMPUTE_WRITES=false on all four"
        status: pass
  - id: D-75-01
    description: "renamed reason string derived live"
    verification:
      - kind: live
        ref: "exec_12683.runData.json Decide Company Action: lv_anti_icp_reason == 'Outside target regions'"
        status: pass
  - id: D-75-05
    description: "flip count sized before any armed sweep"
    verification:
      - kind: live
        ref: "75-UAT.md § Task 2 — Other 5, legacy-reason vetoed 5, vetoed 20, flip-by-recompute 0"
        status: pass
---

# Plan 75-06 Summary — Exit UAT

- **Completed:** 2026-09-20
- **Tasks:** 4 (Task 0 decision + 3)

## Accomplishments

- **Task 1:** 4 cloud bodies deployed DISARMED (`--only`, dry then live, all 200) and bounced
  (`bounce_exit=0`; 289/43/101/55 live = committed; `v1`; every flag `false` incl. the fourth).
  Two recompute POSTs: `9604614548` (AU) → no geography reason, flag `false`; `17317850381`
  (`Other`) → exactly `Outside target regions`, flag `true`; both `write_blocked`, both stamped
  `lv-icp-v0.2`; executions `12682`/`12683`; 0 provider/research/judge nodes; watch clean;
  records byte-unchanged on re-read. Fixtures frozen + redacted (guards 13/13).
- **Task 2:** sizing (Other 5; 4 rescuable by re-enrichment only; legacy-reason vetoed 5; vetoed
  20; flip-by-recompute 0); fork resolved RE-ENRICH; two todos triaged; runbook amended with
  D-75-14 and D-75-17 procedures (`grep -c` 4 / 2).
- **Task 3:** CLAUDE.md §10.3.3 as-built delta with tags, stale spots corrected (§4.0, §5.2,
  §10.1, §10.3, §13.0.2, §21.1); UAT closed with per-criterion evidence and an empty findings
  list; ROADMAP ticked; final suite green.

## Final suite

`.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → **5210 passed, 160 skipped, 0
failed**. `node --test tests/n8n/*.test.mjs` → **1350 pass, 0 fail**.
`.venv/bin/python scripts/todo_triage.py` → exit 0 (12 pending: 6 question, 5 design, 1 defect).
`build_cloud_workflows.py` re-run → `git status --porcelain -- n8n/` empty.

## Task Commits

| Task | Commit | Message |
| --- | --- | --- |
| 1 | `7c0da22d` | test(75-06): state the two recompute-proof expectations before sending |
| 1 | `1e7c5224` | test(75-06): disarmed deploy record, two zero-cost recompute proofs, two new frozen fixtures |
| 2/3 | `8eed381e` | docs(75-06): Phase 75 as-built delta in CLAUDE.md, bump-sweep and flag-flip runbook, SJ-2 todo renamed |
| 2 | `340eeeab` | docs(75-06): size the Other-stamped population, resolve the fork as re-enrich, close the UAT |

## Deviations from Plan

1. **Operator ran every live command** (D-75-10 fallback, same as plan 05).
2. **SJ-2 todo renamed, not duplicated** — plan 03 had already filed the same question under a
   different filename; plan 06's acceptance criterion names the new file, which now exists.
3. **Proof (b) company** — `EU` was the plan's first choice; none exists live. `Other` (a known
   non-home code) is the correct class and was used.
4. **Four bodies deployed, not two** — the plan's "deploy any other body the regeneration
   moved" clause covered contact-ingest and review-decision.

## Issues Encountered

None. No FINDING raised.

## Next Phase Readiness

Phase 75 exit criteria met and evidenced. Nothing armed. The D-75-17 flip and the first
supervised bump sweep are operator procedures in `docs/OPERATOR-RESCORE.md`, outside this phase.

## Self-Check: PASSED
