# Phase 39: Path Decision & Fit-Score Verification - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver an evidence-backed, in-portal verification of company fit-score availability on
Sales Hub Pro (portal 22617666, ap1), plus a minimal empirical probe of fit-score
recalculation latency, and a recorded path decision — lead-scoring-tool rebuild vs
fix-the-four-workflow-chain-in-place — with rationale. Covers requirement DECIDE-01 only.
No scoring-engine changes, no defect fixes (F1–F10 are Phase 40), no data import (Phase 41).

</domain>

<decisions>
## Implementation Decisions

### Verification Method
- **D-01:** API probe first — Claude probes API-side (score-type property surfaces,
  product/tier introspection, lead-scoring endpoints) before any portal work. Operator does
  the in-portal walkthrough only to confirm what the API can't show (the lead-scoring UI
  itself: Settings → Account & Billing → Products & Add-ons → lead scoring tool).
- **D-02:** Evidence = files + attestation. Screenshots and raw API responses saved under
  `.planning/phases/39-path-decision-fit-score-verification/evidence/`, plus a written
  verification note carrying dates and portal ID (22617666). Must be re-checkable when
  HubSpot changes packaging.

### Recalc-Cadence Probe (in scope for Phase 39)
- **D-03:** If verification shows the lead-scoring tool available, run an empirical probe
  before locking the path: configure one trivial criterion, flip a property on a disposable
  `ZZ-SCORING-TEST-DELETE-ME-*` company **3 times** and take the **median** recalculation
  latency, then tear everything down (same disposable-company pattern as HANDOVER §10
  validation — zero real records touched). Median-of-3 guards against a single noisy sample.
- **D-04:** **The gate is "fires automatically on API-written property changes" — not a
  latency number.** Recalc latency on HubSpot's side is a technical, non-configurable async
  queue (no knob, no SLA, no cost lever), and nothing in the system consumes
  `lv_icp_fit_score` within minutes of a write (consumers are rep views, review queues, GTM
  prioritization; the 15-min n8n poller reads enrichment status, not scoring outputs).
  Probe outcomes: (a) event-driven, minutes-scale → proceed lead-scoring tool; (b)
  event-driven but slow (tens of minutes to ~1 hour) → still proceed, latency recorded in
  39-DECISION.md as evidence; (c) manual-only, does not fire on API writes, or hours+ per
  record → pause and present the measurement to the operator with a recommendation (the
  fix-in-place chain has its own tier-lag defect F7 and may not beat the same bar).
  Outcome (c) matters doubly because DATA-02 (Phase 41: imported companies score
  automatically on landing) depends on API-write-triggered recalc.
  — **Reversibility:** reversible (gate behavior is a written rule; nothing binds until
  39-DECISION.md is signed)

### Path Decision & Fallback
- **D-05:** Preferred path remains the lead-scoring-tool rebuild (operator decision
  2026-08-06, HANDOVER §5), contingent on verification passing both gates: company fit
  scores available on Sales Hub Pro, AND recalc fires automatically on API-written property
  changes (D-04 outcomes a/b).
- **D-06:** Fallback is pre-committed for the availability gate: if company fit scores are
  unavailable on Sales Hub Pro, the path is fix-the-four-workflow-chain-in-place — no second
  decision round. (Recalc pathology — D-04 outcome (c) — is the one case that pauses for
  operator review instead.) Custom equation properties stay rejected (HANDOVER §5: not
  RevOps-editable, formula-fragile). — **Reversibility:** costly —
  Phase 40 plans, the parity harness shape, and the cleanup scope (Phase 42) are all
  path-shaped; reversing after Phase 40 planning means replanning that phase.
- **D-07:** Decision rationale inherits HANDOVER §5's mechanism comparison (lead-scoring
  tool vs equation properties vs workflow chain) by citation; the decision record adds only
  the new verification + latency evidence. No re-argument from scratch.

### Decision Record & Branch
- **D-08:** The path decision lands as a standalone
  `.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md`: verdict,
  evidence links (evidence/ dir), latency measurement, rationale citing HANDOVER §5,
  rejected alternatives. ROADMAP.md/STATE.md get a one-line pointer. Phase 40's planner
  reads one file.
- **D-09:** Branch strategy: merge `feat/v0.6-plugin-entrypoint` → `master` FIRST (branch is
  50 commits ahead, unmerged, and carries the v0.7 planning commits d308b08/1bf2fc3/a59b7ee),
  then cut `feat/v0.7-scoring-remediation` from master. Phase 39 execution artifacts land on
  the new v0.7 branch. — **Reversibility:** one-way — a merge to master publishes v0.6
  history to the mainline; undoing it after further commits requires history rewrite.

### Claude's Discretion
- Exact API endpoints/probe order for availability introspection.
- Evidence file naming and note format inside evidence/.
- Probe criterion choice (any trivial rubric line works; tear down after).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Verification & Decision Evidence
- `HANDOVER-2026-08-06-icp-scoring.md` §5 — the mechanism comparison and the two operator
  decisions (lead-scoring tool preferred; vetoes stay pipeline-owned). §8 — the blocking
  open item this phase resolves (Sales Hub Pro company fit-score availability), the
  undocumented recalc cadence, and the branch question. §9 — portal gotchas (`--account=22617666`,
  ap1 URLs). §10 — how the existing four-workflow chain is broken (fix-in-place scope, F1–F10)
  and the disposable-company validation pattern to reuse for the probe.

### Milestone Framing
- `.planning/REQUIREMENTS.md` — DECIDE-01 wording; out-of-scope fence (rubric weights,
  plugin changes, pipeline-side scoring).
- `.planning/ROADMAP.md` — Phase 39 goal + success criteria; Phase 40 is path-shaped by
  this phase's output.

### Rubric Oracle (context only in this phase; the criteria the chosen path must express)
- `config/icp_scoring.yaml` — rubric of record (lv-icp-v0.1); HANDOVER §5 confirms HubSpot
  enum option values already match it exactly.
- `src/icp_scoring.py` — `compute_icp_score`, the parity oracle Phase 40 will assert against.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Disposable-company validation harness pattern (HANDOVER §10: `ZZ-SCORING-TEST-DELETE-ME-*`
  create/exercise/delete, zero real records) — reuse for the recalc-latency probe.
- `scripts/snapshot_hubspot_schema.py` — schema snapshot before any portal mutation.
- Private app token now carries `automation` scope (granted 2026-08-06) — flows readable via
  `GET /automation/v4/flows/{id}`.

### Established Patterns
- Portal 22617666 on **ap1** — `app-ap1.hubspot.com`; `hs` CLI needs `--account=22617666`.
- `.env` is permission-blocked to Read/Bash — hand the operator a `!` command when a token
  value is needed interactively.
- Legacy `calculation_score` properties are sunset (removed 2026-01-10) — the lead-scoring
  tool is the only supported native mechanism to verify.

### Integration Points
- Phase 40 planning consumes `39-DECISION.md` (path verdict) — everything downstream is
  path-shaped.
- Branch setup (merge v0.6 → master, cut v0.7 branch) precedes Phase 39 execution commits.

</code_context>

<specifics>
## Specific Ideas

- Threshold evolution (recorded for rationale): 1 hour proposed → tightened to 20 min →
  reframed entirely after risk discussion. Final gate is *automatic recalc on API writes*;
  latency is evidence, not a gate. The two distinct HubSpot latencies (criteria-edit
  full-portal bulk recalc, potentially hours, one-time; vs per-record event-driven rescore,
  typically minutes) must be measured and reported separately in the probe.
- Verification click-path to confirm in-portal: Settings → Account & Billing →
  Products & Add-ons, then the lead scoring tool (HANDOVER §8).

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Sweep re-notifies a fixed failure until 100 executions displace it"
  (`2026-08-03-sweep-lookback-has-no-time-window.md`) — operator-plugin/sweep concern,
  outside Phase 39 scoring-path scope.
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep"
  (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`) — same; stays in backlog.

</deferred>

---

*Phase: 39-Path Decision & Fit-Score Verification*
*Context gathered: 2026-08-06*
