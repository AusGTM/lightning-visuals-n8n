# Phase 39: Path Decision & Fit-Score Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 39-Path Decision & Fit-Score Verification
**Areas discussed:** Verification method, Fallback path, Decision record, Recalc-cadence probe

---

## Verification Method

| Option | Description | Selected |
|--------|-------------|----------|
| API probe first | Claude probes API-side; operator portal walkthrough only for what API can't show | ✓ |
| Operator manual walkthrough | Claude writes click-path + evidence checklist; operator drives | |
| Claude-in-Chrome assisted | Claude drives portal in operator's Chrome session | |

**User's choice:** API probe first
**Notes:** Cheap, scriptable, evidence re-runnable.

| Option | Description | Selected |
|--------|-------------|----------|
| Files + attestation | Screenshots/API responses in evidence/ + dated written note with portal ID | ✓ |
| Written record only | Dated attestation, no artifacts | |

**User's choice:** Files + attestation

---

## Fallback Path

| Option | Description | Selected |
|--------|-------------|----------|
| Fix-in-place | Pre-commit fallback to fixing four-workflow chain | ✓ |
| Custom equation properties | Rejected in HANDOVER §5 (not RevOps-editable, formula-fragile) | |
| Decide only if needed | Second decision round if verification fails | |

**User's choice:** Fix-in-place (pre-committed for the availability gate)

| Option | Description | Selected |
|--------|-------------|----------|
| Inherit handover §5 | Decision record cites existing mechanism comparison, adds only new evidence | ✓ |
| Fresh comparison | Re-argue three mechanisms from scratch | |

**User's choice:** Inherit handover §5

---

## Decision Record

| Option | Description | Selected |
|--------|-------------|----------|
| DECISION.md in phase dir | Standalone 39-DECISION.md: verdict, evidence, rationale, rejected alternatives | ✓ |
| Inside CONTEXT/REQUIREMENTS | Fold into existing docs | |

**User's choice:** DECISION.md in phase dir

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh v0.7 branch from master | Initially recommended | |
| Stay on current branch | | |
| Branch from v0.6 tip | (revised round) carries planning docs, drags plugin history | |
| Merge v0.6 first | Merge feat/v0.6-plugin-entrypoint → master, cut v0.7 branch from master | ✓ |

**User's choice:** Merge v0.6 first
**Notes:** User interrupted to ask whether v0.6 was merged; check showed 50 commits ahead,
unmerged, with v0.7 planning commits on the v0.6 branch — initial "fresh branch from master"
answer was revised in a second round.

---

## Recalc-Cadence Probe

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal probe in 39 | Configure trivial criterion, flip property on disposable company, measure, tear down | ✓ |
| Defer to Phase 40 | Path decided on availability alone | |

**User's choice:** Minimal probe in 39

Threshold sub-decision evolved across three rounds:
1. Options were "operator re-decides above ~15 min" vs "pre-commit 1-hour threshold" —
   user picked pre-commit, then tightened the ceiling to **20 minutes** at the wrap-up check.
2. User asked for the risks of a hard 20m auto-fallback (noisy single sample; fallback chain
   has its own F7 tier-lag; probe ≠ steady state; no HubSpot SLA; operational need weaker
   than the threshold implies). User: "this needs to be tested to validate whether 20m is an
   appropriate threshold" → 20m demoted to working hypothesis, median-of-3 measurement.
3. User asked whether the limitation is technical or scheduling/cost. Analysis: HubSpot-side
   recalc is a technical, non-configurable async queue (no cost lever); nothing downstream
   consumes the score within minutes. Final reframe applied: **gate = fires automatically on
   API-written property changes**; latency recorded as evidence; manual-only / no-fire /
   hours+ pauses for operator review with recommendation.

---

## Claude's Discretion

- Exact API endpoints/probe order for availability introspection
- Evidence file naming and note format
- Probe criterion choice

## Deferred Ideas

- None new. Two backlog todos reviewed and not folded (sweep lookback window; sweep crontab
  version pin) — operator-plugin concerns, out of phase scope.
