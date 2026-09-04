# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** — shipped 2026-07-29
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see the v0.5 ledger note in `MILESTONES.md`)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` — shipped 2026-08-04
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 — shipped 2026-08-08
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 — shipped 2026-08-11
- ✅ **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–50 (`milestones/v0.9-ROADMAP.md`, `milestones/v0.9-REQUIREMENTS.md`) — shipped 2026-08-19
- ⏸️ **v1.0 Direct Backfill & Scoring Coverage** — Phases 51–52. Phase 51 complete; **Phase 52 deferred INDEFINITELY** (2026-08-25, reaffirmed 2026-08-30 after its gates were satisfied). Not abandoned — deferred by decision.
- ✅ **v1.1 Unattended Session Runs** — Phases 53–63 (`milestones/v1.1-ROADMAP.md`, `milestones/v1.1-REQUIREMENTS.md`, `milestones/v1.1-phases/`) — shipped 2026-09-04
- 📋 **v1.2 Yield and Friction** — Phases 64–69 (`milestones/v1.2-ROADMAP.md`, `milestones/v1.2-REQUIREMENTS.md`) — **ACTIVE, not started**

## Standing facts

These outlive any single milestone. Read them before planning anything that writes.

- **The first live unattended, credit-spending batch has NOT run, and nothing is armed.** Phase 57 landed the ceilings, refusal-before-start and post-run proof; Phase 61's backend is deployed and disarmed-proven only. At 57-05's Task 4 gate the operator chose a small, *supervised* first live batch — explicitly not the unattended one. D-61-08's unattended gate stays shut until a phase asks and the operator answers (v1.2 `AUTO-04`).
- **The committed `n8n/*.json` is AHEAD of the running n8n Cloud instance** — regenerated and committed without deploying since 2026-09-02 (CLAUDE.md §13.0.2). An in-repo node is not evidence of what n8n is executing.
- **Never hand-edit `n8n/wf_*.json`** — change `n8n/code/*.js` or the builder and re-run `scripts/build_cloud_workflows.py`.

## Phases

<details>
<summary>✅ v1.1 Unattended Session Runs (Phases 53–63) — SHIPPED 2026-09-04 · 10 phases, 62 plans, 162 tasks</summary>

- [x] Phase 51: Backfill pipeline, credit sizing & dry run (3/3) — v1.0 carry-in, archived here
- [x] Phase 53: Operator-openable write grant (4/4) — verified by live operator walk, run 3
- [x] Phase 54: Single-pass armed dispatch (7/7)
- [ ] Phase 55: Async run — submit, poll, resume — **ABSORBED into 61** (D-61-08)
- [ ] Phase 56: The unattended pair pipeline — **ABSORBED into 61** (D-61-08)
- [x] Phase 57: Ceilings, refusal-before-start, and post-run proof (5/5) — completed 2026-09-01
- [x] Phase 58: Take what the operator actually has (6/6)
- [x] Phase 59: Frictionless write path (9/9)
- [x] Phase 60: Review-lane authority (5/5)
- [x] Phase 61: Autonomous batch runs (6/6) — absorbs 55 + 56
- [x] Phase 62: Suggest the contacts nobody named (12/12)
- [x] Phase 63: The unattended lane actually runs unattended (5/5) — 28/28 must-haves

**Closeout type:** override close. Phases 52, 55 and 56 carry no verification and none is
open work — 52 is deferred indefinitely by operator decision, 55 and 56 were absorbed into 61
so that they would *not* be planned separately. 11 open artifacts were acknowledged rather
than resolved at close; they are listed in STATE.md § Deferred Items and 5 of the 8 todos
among them are already scheduled as v1.2 phases.

</details>

### 📋 v1.2 Yield and Friction (Phases 64–69) — ACTIVE

Full detail in `milestones/v1.2-ROADMAP.md`; requirements in `milestones/v1.2-REQUIREMENTS.md`.

Every phase moves the system one direction — **yield more, stop less, without moving any
safety gate.** Seven of the eight source items came from the first two live
`suggest-contacts` rounds (Brisbane Roar FC, The Roma Turf Club), each with a filed todo
carrying its live evidence.

- [ ] Phase 64: The ladder stops at the best page, not the first
- [ ] Phase 65: Round-empty re-entry, keyed on the cause
- [ ] Phase 66: Rich enrichment, not minimum enrichment
- [ ] Phase 67: An autonomy flag with sensible defaults
- [ ] Phase 68: State the price and keep moving
- [ ] Phase 69: Held rows survive the round

**Binding on all six** (`SAFE-01`..`SAFE-05`): no `min_confidence` lowered, no
`fill_blank_only` weakened, no drop path softened; a refusal stays terminal; fetch and search
caps never reset; ceilings stay refusals in code, not prose; D-61-08's unattended gate stays
shut unless `AUTO-04` is explicitly answered.

**Items 1–2 of the operator's priority list are already done as quick tasks, not phases here:**
`260905-rf1` (one-word club titles now classify) and `260905-ad2` (a company may carry more
than one domain).
