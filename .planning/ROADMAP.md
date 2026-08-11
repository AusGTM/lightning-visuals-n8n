# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** (shipped 2026-07-29)
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see Ledger gaps below)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` (shipped 2026-08-04)
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 (shipped 2026-08-08)
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 (shipped 2026-08-11)
- 📋 **v0.9** — next milestone, not yet defined

## Phases

<details>
<summary>✅ v0.8 Execution Budget Safety (Phases 44–45) — SHIPPED 2026-08-11</summary>

- [x] Phase 44: SJ-3 Dispatch Gate, Drain & Cap (3/3 plans) — completed 2026-08-10, verified
- [x] Phase 45: Burn-Rate Alarm (3/3 plans) — completed 2026-08-10, verified

Full detail: `milestones/v0.8-ROADMAP.md` · Phase artifacts: `milestones/v0.8-phases/`
Requirements: `milestones/v0.8-REQUIREMENTS.md` (15/15 complete)

</details>

<details>
<summary>✅ Earlier milestones — archived</summary>

Phase-level detail for shipped milestones lives in the archives rather than here, to keep this
file constant-size:

| Milestone | Roadmap archive | Phase artifacts |
|---|---|---|
| v0.8 Execution Budget Safety | `milestones/v0.8-ROADMAP.md` | `milestones/v0.8-phases/` |
| v0.7 HubSpot Scoring Engine Remediation | `milestones/v0.7-ROADMAP.md` | `milestones/v0.7-phases/` |
| v0.4 Reachability & Verification Debt | `milestones/v0.4-ROADMAP.md` | `milestones/v0.4-phases/` |
| v0.3 | `milestones/v0.3-ROADMAP.md` | `milestones/v0.3-phases/` |

</details>

### 📋 v0.9 (not yet defined)

Run `/gsd-new-milestone` to define requirements and phases. Phase numbering continues the repo's
global sequence — Phase 45 was the last consumed, so v0.9 starts at Phase 46.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 44. SJ-3 Dispatch Gate, Drain & Cap | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 45. Burn-Rate Alarm | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |

## Ledger gaps (known)

- **v0.5 has no MILESTONES.md entry and no roadmap/phase archive.** Found during the v0.8 close
  on 2026-08-11: the ledger jumps v0.4 → v0.6 and `milestones/` holds no `v0.5-*` files, yet
  `v0.5.0` exists as a git release tag. v0.5 appears to have shipped without being run through
  `/gsd-complete-milestone`. Not reconstructed at v0.8 close (out of scope) — recorded so it is
  not mistaken for a numbering skip.
- **v0.6 has a MILESTONES.md entry but no roadmap/phase archive** under `milestones/`. Same
  likely cause, lesser impact: the narrative record survives, the phase artifacts were never
  archived under a `v0.6-*` label.
