# Phase 41: Validation Data Import & End-to-End Proof - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-07
**Phase:** 41-Validation Data Import & End-to-End Proof
**Areas discussed:** Source dataset, Import write path, Record matching, Auto-score proof

---

## Pre-discussion: assertion validation

Operator asked "where did the 66 come from — validate that is a legitimate assertion"
before answering the source-data question. Claude traced it:
`../icp-analysis/enrich.mjs` (2026-06-29, Perplexity `sonar`) →
`../ausgtm-lightningvisuals-data/data/enriched_companies.json` — 66 entries keyed by
HubSpot company ID, confidence 49 high / 16 medium / 1 low. Assertion confirmed accurate;
records are existing CRM companies, not net-new.

## Todo cross-reference

| Option | Description | Selected |
|--------|-------------|----------|
| Fold neither | Keep both in backlog | ✓ |
| Enrichment throughput ceiling | 82% of run is two sequential Anthropic calls | |
| Sweep crontab versioned path | Plugin update silently stops sweep | |

---

## Source dataset

| Option | Description | Selected |
|--------|-------------|----------|
| Import as-is | June provenance stamped, staleness visible | |
| Re-verify the 17 medium/low | Only the weak cohort re-researched | |
| Re-verify all 66 | Fresh Claude web-research pass on everything (~$5 Anthropic) | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic map + exceptions | Static table + curated misfit list (QRIC→regulator) | ✓ |
| Deterministic map only | Pure table, accepts misclassifications | |
| Haiku classify each record | Evidence text through Haiku classifier | |

| Option | Description | Selected |
|--------|-------------|----------|
| 85 / 65 / 40 | high clears all gates incl. produces_content(85) | ✓ |
| 90 / 70 / 50 | Medium clears 70-threshold fields | |
| You decide | Claude anchors to field_policy.yaml at planning | |

| Option | Description | Selected |
|--------|-------------|----------|
| Conflict check | Fresh is truth; disagreement → needs_review | ✓ |
| Fallback only | June used only where fresh research fails | |
| Ignore after re-research | June file historical only | |

---

## Import write path

| Option | Description | Selected |
|--------|-------------|----------|
| Real n8n pipeline | Queue via enrichment_requested; poller does research+merge+PATCH | ✓ |
| Local Python pipeline | main.py path; proves wrong write path for DATA-02 | |
| Standalone import script | Direct PATCH, no LLM lane | |

| Option | Description | Selected |
|--------|-------------|----------|
| scheduled_arm.py windows | Bounded write windows, 2-record chunks, auto-disarm | |
| Manual arm for whole run | Operator arms once, disarms at end | ✓ |
| You decide | Claude picks within operator-arms boundary | |

| Option | Description | Selected |
|--------|-------------|----------|
| Scoring inputs only | Canonical writes for the 9 ICP input fields; firmographics staged | ✓ |
| Full canonical | ALLOW_CANONICAL_WRITES wholesale | |
| You decide | Claude picks allowlist at planning | |

| Option | Description | Selected |
|--------|-------------|----------|
| June data as pseudo-provider | Existing conflict machinery adjudicates | ✓ |
| Pre-flight offline diff | Conflicted records held out of run | |
| Post-run audit diff | Import all, flag disagreements after | |

---

## Record matching

| Option | Description | Selected |
|--------|-------------|----------|
| Re-match by name/domain | Pre-flight resolves IDs; dead ones re-matched; unmatched skipped+reported | ✓ |
| Skip and report | Dead IDs excluded, no re-matching | |
| Fail the run | Any dead ID aborts pre-flight | |

---

## Auto-score proof

| Option | Description | Selected |
|--------|-------------|----------|
| Canary then rest | ~5 records verified end-to-end, then remaining 61 | ✓ |
| All 66 at once | One pass, poller caps chunk it | |
| 49 first, then 17 | High-confidence cohort first | |

| Option | Description | Selected |
|--------|-------------|----------|
| Parity sweep + report | Phase 40 harness over imported population; committed JSON verdict | ✓ |
| Spot-check sample | Manual verification of a handful | |
| You decide | Claude picks evidence artifact | |

| Option | Description | Selected |
|--------|-------------|----------|
| Accept + report counts | Review routing is the system working; triage after | ✓ |
| Cap then pause | Threshold pauses run for operator check | |
| Pre-triage with me | Conflicted records presented before any write | |

---

## Claude's Discretion

- Enum-mapping table content + exception list
- Canary record selection and batch cadence
- Pseudo-provider injection mechanics, name, trust rank
- Run-report format/location
- Pre-flight ID-resolution script shape
- "Scores on landing" latency threshold (anchor to Phase 40 measurements)

## Deferred Ideas

- Enrichment throughput ceiling todo — backlog (operational note kept in CONTEXT.md)
- Sweep crontab versioned-path todo — backlog
