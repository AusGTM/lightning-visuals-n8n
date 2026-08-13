# Phase 49: Re-score Strategy & Reporting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `49-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-08-13
**Phase:** 49-re-score-strategy-reporting
**Areas discussed:** Run mechanics & windows, The reusable procedure, The report (RESCORE-03), Carried-forward items

**Pre-answered before the discussion started** (carried from prior phases, not re-asked): the
re-score mechanism (46-DECISION.md's component-backfill recommendation), the population
definition (66, forced by the shared `HAS_PROPERTY(lv_icp_fit_score)` selection), that veto fields
need no recompute for this particular change, project-level D-07, the expiry of `D-48-01`, the
v0.9 entry distribution, and `venue`'s continued deferral.

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Run mechanics & windows | Cap vs chunking, window count, the stamped-component canary, arming authority | ✓ |
| The reusable procedure | Runbook vs `--plan` mode; whether the veto branch is documented | ✓ |
| The report (RESCORE-03) | Baseline, attribution, delivery surface | ✓ |
| Carried-forward items | Entain, Jam TV, the D→non-D transition proof | ✓ |

**User's choice:** all four.

---

## Todo folding

| Option | Description | Selected |
|--------|-------------|----------|
| Fold none (Recommended) | All four matches score 0.4–0.6; none owned by a component-backfill phase; record as reviewed-not-folded | |
| Fold the research-prompt todo | `2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` — obliges a deploy+bounce and a reviewed fixture re-baseline | ✓ |
| Let me pick | Show the four todos | |

**User's choice:** fold the research-prompt todo (against the recommendation).
**Notes:** The recommendation was fold-none on the grounds that the phase otherwise needs no
deploy. The operator folded it anyway; the deploy it obliges became the single declared
deploy+bounce in D-05. The other three todos are recorded reviewed-not-folded in CONTEXT.md.

---

## Run mechanics & windows

### Q1 — getting past `HARD_CEILING_RECORDS = 25` at n=66

| Option | Description | Selected |
|--------|-------------|----------|
| Raise ceiling + exact-set gate (Recommended) | Ceiling → 100, count cap replaced by a pinned assertion that the sample **is** the live-derived scored population; one invocation, one batch PATCH, one window | ✓ |
| Three ≤25 chunks, no code change | 46-DECISION's option (a); touches no Phase 40 constant, but three invocations is three times the window-count surface Phase 47 already failed on | |
| New dedicated re-score driver | Leaves backfill untouched; most new code, and a second producer of the same five component writes | |

**User's choice:** raise ceiling + exact-set gate.
**Notes:** Selected with the preview showing `HARD_CEILING_RECORDS = 100` and an
`enforce_exact_population(sample_ids, live_ids)` predicate. The framing that carried it: an
exact-set gate is *stronger* than a count cap, not weaker — a count of 25 permits any 25 records.

### Q2 — the unresolved stamped-component edge

| Option | Description | Selected |
|--------|-------------|----------|
| Canary one record first, same window (Recommended) | One `individual_club_team` (5→15), settle, read back, then release the other 65 in the same window; zero extra arm/disarm cycles | ✓ |
| Disposable record first, then the 66 | Strongest isolation; costs create authority, a delete, ~20s index lag, and a leak proof | |
| Proceed on all 66, detect by read-back diff | Fastest; a stamp failure would surface as a 66-record mess and the debugging target would be the phase's own acceptance gate | |

**User's choice:** canary one record first, inside the one window.
**Notes:** 46-DECISION assigned this edge to "Phase 49's own research" and it cannot be settled by
reading anything — HubSpot's default-value stamp is API-inaccessible for reads.

### Q3 — window and deploy declaration

| Option | Description | Selected |
|--------|-------------|----------|
| 2 windows + 1 deploy, W2 conditional (Recommended) | W1 on backfill's own two-key gate (0 n8n executions); W2 conditional on Entain's research; 1 deploy for the folded todo | ✓ |
| 1 window, everything inside it | Fewest ceremonies; arms n8n record-writes for a leg that doesn't need them and would hold a window open across a research call | |
| 1 window; Entain write re-deferred | Tightest; leaves a known-wrong record wrong | |

**User's choice:** 2 windows + 1 deploy, W2 conditional.
**Notes:** The key distinction surfaced here — W1's `ALLOW_SCORE_BACKFILL` is a Python-side gate
on a direct CRM batch call and involves n8n not at all, so Phase 48's "both surfaces armed
together" rule must **not** be copied into W1.

### Q4 — arming authority after `D-48-01` expired

| Option | Description | Selected |
|--------|-------------|----------|
| New scoped waiver `D-49-01`, Phase 49 only (Recommended) | D-48-01's proven terms, re-granted with its own expiry; counterweight stated plainly (it re-grants write authority to Claude) | ✓ |
| Operator arms everything | The rule as written; Phase 48 halted at 4/7 on exactly this checkpoint | |
| Split by blast radius | Operator arms the deploy, Claude the reversible record windows | |

**User's choice:** new scoped waiver `D-49-01`.

---

## The reusable procedure

### Q1 — what form the procedure takes

| Option | Description | Selected |
|--------|-------------|----------|
| Runbook doc + a `--plan` mode (Recommended) | `docs/OPERATOR-RESCORE.md` for reading; `--plan` produces the numbers live so doc and code cannot drift | ✓ |
| Runbook doc only | Cheapest; every figure a hand-copied literal — the mechanism that let COVER-01's "18" go 13 records stale | |
| A `--plan` mode only | Drift-proof but unreachable for a non-technical operator who never opens a terminal | |

**User's choice:** both.

### Q2 — does the procedure cover the veto-predicate branch

| Option | Description | Selected |
|--------|-------------|----------|
| Both branches, with a decision rule up front (Recommended) | Classify the change first; weight branch ~0 executions, veto branch ~66 (2.6% of the allowance), cost measured from executions 11858–11861 | ✓ |
| Weight branch only; veto branch a named gap | Honest about what is exercised; leaves no written answer for the change class 47.5 just shipped | |
| Both branches, and exercise the veto branch too | Proves it end-to-end; spends 2.6% of the month to most likely confirm a no-op | |

**User's choice:** both branches, decision rule first.

### Q3 — what structurally enforces the procedure

| Option | Description | Selected |
|--------|-------------|----------|
| A guard test that fails on an unaccompanied weight change (Recommended) | Pin `base_score`; failure message names the runbook and the obligation; three existing guard-test idioms to copy | ✓ |
| Rely on the parity sweep as the detector | Zero new code; detects after the fact, and v0.8's sweep ships **inert** with no cron installed | |
| Runbook prose only | Cheapest; the exact mechanism that produced stale censuses | |

**User's choice:** a guard test.

### Not asked (offered, declined)

Ordering — that a weight change must land in both engines before the re-score runs, or flow
`4626124224` silently overwrites correct backfilled components on the next input change. The
operator chose "Next area", so it is recorded as Claude's discretion. Phase 46 already landed both
engines with a running-content read-back, so no work is owed this phase.

---

## The report (RESCORE-03)

### Q1 — baseline and series shape

| Option | Description | Selected |
|--------|-------------|----------|
| Three-point series, two fresh live reads (Recommended) | Entry (46-simulation live column) → pre-W1 live read → post-W1 live read; attribution falls out free, reads cost nothing | ✓ |
| Two-point series: entry → post-re-score | Satisfies the literal wording; lumps three different levers into one delta | |
| Reconstruct from committed artifacts only | Fully reproducible from git; the AFTER snapshots are per-cohort and overlap | |

**User's choice:** three-point series.

### Q2 — delivery surface

| Option | Description | Selected |
|--------|-------------|----------|
| Committed markdown + a published Artifact (Recommended) | Durable git record plus a private, forwardable page; also discharges 46-03's deferred D-09 publish | ✓ |
| Committed markdown only | No new surface; a document the operator will never open | |
| Markdown + a HubSpot saved view | In-workflow and live; cannot express before/after, and it is portal work with its own arming | |

**User's choice:** markdown + a published Artifact.
**Notes:** Artifacts are private by default; the link is handed over and sharing is the operator's
call. Content is internal company names, tiers and scores — no personal data.

### Q3 — how far the plain-language layer goes

| Option | Description | Selected |
|--------|-------------|----------|
| Counts + motion consequences + a named-caveats block (Recommended) | Named movers with GTM meaning, plus an explicit "what this does not say" block carrying four known-unproven items | ✓ |
| Counts + motion consequences | Actionable but risks reading as more certain than the evidence | |
| Counts + per-record table, no interpretation | Impossible to overstate; leaves the effect to be inferred, which RESCORE-03 exists to prevent | |

**User's choice:** counts + consequences + caveats.

### Not asked (offered, declined)

The 712-company denominator, and scoring the outcome against PROJECT.md's own
`A:7 B:18 C:17+ D:7` prediction. Operator chose "Next area"; both recorded as Claude's discretion
and folded into CONTEXT.md.

---

## Carried-forward items

### Q1 — how far Entain's mandatory re-examination goes

| Option | Description | Selected |
|--------|-------------|----------|
| Region only (D-V6 scope), content veto recorded untouched (Recommended) | Exactly what the LOCKED decision mandates; Entain stays D either way, but the wrong veto *reason* gets fixed | |
| Both veto inputs — region AND `lv_produces_content` | Region-only spends a write for zero list effect; `false` was never backed by positive evidence of absence; the only path to targetability, and a D→B move would also supply the deferred transition proof | ✓ |
| Read-only — research, record, write nothing | The LOCKED text asks for a recorded re-examination, not necessarily a write | |

**User's choice:** both veto inputs (against the recommendation).
**Notes:** The recommendation was region-only on scope-discipline grounds. The operator took the
wider read, which is defensible on the argument stated in the option itself — a region-only write
cannot move Entain, and `lv_produces_content = false` was never evidenced. This also gives D-15's
transition proof a real vehicle.

### Q2 — sign-off before W2 clears a hard veto

| Option | Description | Selected |
|--------|-------------|----------|
| Operator sign-off on the evidence, no judge pass (Recommended) | Satisfies §21.3 with an actual human; exactly what 47.5 did for the D-V6 flips | |
| Sonnet judge pass, then operator sign-off | Most faithful to §15.1; would be the judge's first live use on a veto decision in this milestone | |
| Config bar only — no human gate | Fastest and fully deterministic; removes the human from a hard-veto clear on a record a human deliberately excluded | ✓ |

**User's choice:** config bar only, no human gate (against the recommendation).
**Notes:** The conflict was stated in the option text — with `CLAUDE.md` §21.3, `CLAUDE.md` §15.1,
and the LOCKED venue decision's own stated risk ("a re-score silently un-vetoes a record a human
deliberately excluded") — and the operator selected it with that in front of them. Recorded in
CONTEXT.md as **D-14, an explicit dated override**, with all three source texts left intact rather
than rewritten (RUBRIC-01's house pattern). What still binds: the driver hard-refuses below
`min_confidence: 85` or a missing evidence URL, and all evidence lands in the run report for
after-the-fact review. This was raised once and reaffirmed by selection; not re-litigated.

### Q3 — the live D → non-D tier transition

| Option | Description | Selected |
|--------|-------------|----------|
| Prove it on Entain if it flips; re-defer with a stated reason if not (Recommended) | Instrument W2 with two independent reads and a settle poll, closing 47.5-03's 5s-apart gap | ✓ |
| Prove it on a disposable record | Deterministic and Entain-independent; costs create authority, a delete, index lag and a leak proof | |
| Re-defer it outright | Honest that no live decision depends on it; would be the third consecutive deferral | |

**User's choice:** prove on Entain if it flips, re-defer with a stated reason if not.
**Notes:** Jam TV `17317850381`'s D-23 veto retention is asserted by plain read in the run report
unconditionally (D-16), along with the portal-wide non-ANZ census (2) and the VETO-03 bar (0).

---

## Claude's Discretion

- Engines-first ordering in the runbook (both engines carry the weight before the re-score runs).
- The 712-company denominator note, and scoring the outcome against PROJECT.md's
  `A:7 B:18 C:17+ D:7` prediction.
- Deploy ordering relative to W1 (independent — the re-score never traverses the research branch).
- Settle timeout and poll interval for the calculated-property chain (~11s measured, Phase 40-07).
- Whether the exact-set gate re-derives at arm time or asserts against a pre-arm snapshot.
- Whether the re-score also settles `lv_icp_score_breakdown` via the existing opt-in
  `--write-breakdown` path.
- Plan/wave decomposition, and where the `--plan` mode lives.

## Deferred Ideas

- `venue` as a 10th `lv_org_type` enum option — the LOCKED file's "Scores in: Phase 49" line is
  moot per its own 2026-08-13 CLOSURE block.
- Exercising the veto branch of the procedure live (66 recompute POSTs, ~2.6% of the allowance).
- `docs/SYSTEM-CONTRACT.md`'s stale boundary-of-responsibility section.
- Installing the sweep cron/launchd schedule (carried from v0.8; the parity sweep is inert today,
  which is part of why the enforcement decision is a test rather than a reliance on the sweep).
- Auditing `lv_produces_content = false` for unevidenced values beyond Entain.

### Not raised by the user

No scope creep occurred. Every area discussed clarified how to implement what the ROADMAP and
the three prior phases already assigned to Phase 49; the two items that grew scope (Entain's
second veto input, the folded todo) were both operator-directed against a narrower
recommendation, and both trace to obligations already recorded in a LOCKED decision or a pending
todo rather than to new capabilities.
