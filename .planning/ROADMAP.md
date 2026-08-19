# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** (shipped 2026-07-29)
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see Ledger gaps below)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` (shipped 2026-08-04)
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 (shipped 2026-08-08)
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 (shipped 2026-08-11)
- ✅ **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–50, archived (`milestones/v0.9-ROADMAP.md`, `milestones/v0.9-REQUIREMENTS.md`) (shipped 2026-08-19)

## Phases

*No active milestone.* v0.9's phases 46–50 are archived in full at
`milestones/v0.9-ROADMAP.md`. Run `/gsd-new-milestone` to define the next one.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 44. SJ-3 Dispatch Gate, Drain & Cap | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 45. Burn-Rate Alarm | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 46. Rubric Decision, Simulation & Engine Parity | v0.9 | 5/5 | Complete (verified) | 2026-08-11 |
| 47. Veto Remediation | v0.9 | 4/4 | Complete (verified) | 2026-08-12 |
| 47.5. Veto Recompute Path | v0.9 | 6/6 | Complete (verified) | 2026-08-12 |
| 48. Enrichment Coverage | v0.9 | 7/7 | Complete (verified) | 2026-08-13 |
| 49. Re-score Strategy & Reporting | v0.9 | 7/7 | Complete (verified) | 2026-08-13 |
| 50. Derived Tier Property | v0.9 | 6/6 | Complete (verified) | 2026-08-14 |

## Ledger gaps (known)

- **v0.5 has no MILESTONES.md entry and no roadmap/phase archive.** Found during the v0.8 close
  on 2026-08-11: the ledger jumps v0.4 → v0.6 and `milestones/` holds no `v0.5-*` files, yet
  `v0.5.0` exists as a git release tag. v0.5 appears to have shipped without being run through
  `/gsd-complete-milestone`. Not reconstructed at v0.8 close (out of scope) — recorded so it is
  not mistaken for a numbering skip.

- **v0.6 has a MILESTONES.md entry but no roadmap/phase archive** under `milestones/`. Same
  likely cause, lesser impact: the narrative record survives, the phase artifacts were never
  archived under a `v0.6-*` label.
