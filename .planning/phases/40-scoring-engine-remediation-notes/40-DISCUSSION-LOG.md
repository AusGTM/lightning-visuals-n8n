# Phase 40: Scoring Engine, Veto & Parity Remediation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 40-scoring-engine-remediation-notes
**Areas discussed:** Veto ownership mechanics, Remediation surface, Backfill for the 712, Parity harness shape

---

## Todo Cross-Reference

4 keyword-matched todos presented (sweep lookback, sweep crontab pin, enrichment
throughput, UAT header aliases). **User's choice:** Fold none — all outside
scoring-engine scope. Recorded as reviewed-not-folded in CONTEXT.md `<deferred>`.

---

## Veto Ownership Mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| n8n pipeline only | Honors §5 decision 2; wire flag+reason into merge/decide path; delete Geography flow's veto branch; requires P2/P4 fixed first | ✓ |
| HubSpot workflows own it | Symmetric set/clear branches in workflows; covers manual edits; contradicts §5 decision 2 | |
| Hybrid | Two writers, clobber risk, precedence rule needed | |

| Option | Description | Selected |
|--------|-------------|----------|
| Stale until next enrichment | Single writer; operator forces refresh via lv_enrichment_requested="true" | ✓ |
| HubSpot workflow enqueues re-enrich | Auto-set enrichment_requested on veto-input change | |
| Recompute veto on any n8n touch | Every pipeline write path recomputes | |

| Option | Description | Selected |
|--------|-------------|----------|
| Unscored — follow oracle | Matches ENGINE-07 + compute_icp_score | ✓ (after conflict surfaced) |
| C floor | Diverges from oracle | |
| Keep D — amend requirements | User's initial pick; would amend ENGINE-07/ROADMAP SC3/oracle | initially chosen, reversed |

**Notes:** User first answered "Keep grade D" via clarification message. The conflict
with locked ENGINE-07, ROADMAP Phase 40 success criterion 3, and the parity oracle was
presented explicitly; user then confirmed "Unscored — follow oracle."

| Option | Description | Selected |
|--------|-------------|----------|
| Real threshold + string coercion | min_confidence ~80 + boolean→"true"/"false" (36-07 pattern) | ✓ |
| Bypass merge policy entirely | Compute veto deterministically in Decide Company Action | |
| You decide | Claude picks during planning | |

---

## Remediation Surface

| Option | Description | Selected |
|--------|-------------|----------|
| API-driven, JSON in repo | Fetch/fix/PUT via automation v4; versioned; portal fallback | ✓ |
| Portal UI hand-edit | Fast, unversioned | |
| Delete and recreate via API | Clean but new flow IDs | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep components, add one | produces_content_score property + mapper + formula term; 5 components | ✓ |
| Consolidate into fewer flows | Full rebuild, bigger blast radius | |

| Option | Description | Selected |
|--------|-------------|----------|
| Disable, edit, validate, re-enable | Disposable-company validation between; no half-fixed flow fires live | ✓ |
| Edit live, validate after | Faster, riskier | |
| You decide | Per-flow choice | |

| Option | Description | Selected |
|--------|-------------|----------|
| Armed/disarmed scripts | 39-03 probe convention | |
| Claude executes directly in-session | Faster iteration; D-07 protocol is the safety envelope | ✓ |
| Operator runs commands by hand | Max control, slowest | |

---

## Backfill for the 712

| Option | Description | Selected |
|--------|-------------|----------|
| Mechanism in 40, mass run in 41 | Prove on small sample (doubles as PARITY-01 real-record sample) | ✓ |
| Full backfill in 40 | Mass-Unscored until enriched | |
| Out of scope entirely | Wholly deferred | |

| Option | Description | Selected |
|--------|-------------|----------|
| Batch-seed component scores | Batch PATCH the four *_score components per current inputs; mirrors PROPERTY_DEFAULT_VALUE | ✓ |
| Property poke to re-enroll | Unverified same-value re-enrollment behavior | |
| Enqueue enrichment for all | Burns provider credits + Anthropic per record | |

---

## Parity Harness Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest with live marker | Single layer, assertion-native | |
| Standalone script + JSON report | Probe-script convention | |
| Both layers | Pytest for fixtures/regressions + script wrapper for scheduled/report use | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Two-tier: scheduled read-only + on-demand full | Cheap sample drift check on sweep cadence; full disposable run on demand | ✓ |
| On-demand only | Drift guard degrades to manual audit | |
| Full run scheduled | Unattended record creation every fire | |

| Option | Description | Selected |
|--------|-------------|----------|
| Split: offline n8n + live HubSpot | Each owner tested where it lives | |
| Live end-to-end only | Full enrichment runs on disposables, assert final flag/tier; Anthropic cost accepted | ✓ |
| You decide | Per-case choice | |

---

## Claude's Discretion

- `lv_anti_icp_reason` string format (derive from config hard-veto reasons)
- Exact veto min_confidence value (~80 suggested)
- Revenue-branch boundary encoding in flow JSON
- Real-record sample size/selection for PARITY-01
- Flow-JSON repo storage location + snapshot naming
- Backfill batch sizes / rate handling

## Deferred Ideas

None new — four reviewed-not-folded todos listed in CONTEXT.md `<deferred>`.
