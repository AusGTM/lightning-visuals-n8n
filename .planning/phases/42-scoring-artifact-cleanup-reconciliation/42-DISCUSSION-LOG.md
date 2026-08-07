# Phase 42: Scoring Artifact Cleanup & Reconciliation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-07
**Phase:** 42-Scoring Artifact Cleanup & Reconciliation
**Areas discussed:** Superseded inventory, Reconcile direction, Archive semantics, Reconcile tooling

---

## Pre-discussion scouting

Claude enumerated `config/hubspot_flows/` (14 files: 4 repaired flows before/after, plus
produces-content, gambling, and the two property definitions) and parsed
`config/hubspot_properties.yaml` (22 company / 17 contact properties). Two findings drove
the questioning: ROADMAP SC1's archive list names the live engine, and the yaml is a
partial manifest missing every scoring output and component property.

## Todo cross-reference

| Option | Description | Selected |
|--------|-------------|----------|
| Fold neither | All four stay backlog | ✓ |
| Sweep lookback window | Re-notifies fixed failures | |
| Sweep crontab path | Versioned-path pin breaks sweep | |
| Upload header aliases | UAT 2.2 mapping gap | |

---

## Superseded inventory

| Option | Description | Selected |
|--------|-------------|----------|
| Reinterpret + record | Archive only what's actually orphaned; record supersession in CONTEXT.md | ✓ |
| Amend ROADMAP.md first | Edit SC1 text before planning | |
| Archive as literally written | Would archive the working engine | |

| Option | Description | Selected |
|--------|-------------|----------|
| Live-portal diff | Enumerate live props+flows, cross-reference against actual readers/writers | ✓ |
| Repo-only derivation | Derive from repo artifacts alone | |
| You decide | Claude picks method | |

| Option | Description | Selected |
|--------|-------------|----------|
| Present list, then archive | Full approval gate before any archival | |
| Archive uncontested, ask on doubt | Clear-cut orphans proceed; ambiguous surfaced | ✓ |
| Dry-run only this phase | List + snapshot, archival deferred | |

---

## Reconcile direction

| Option | Description | Selected |
|--------|-------------|----------|
| Full mirror of lv_*/scoring | yaml covers every lv_* and scoring property; natives excluded | ✓ |
| Subset integrity only | Zero drift for the existing 22 only | |
| Every portal property | Full schema incl. HubSpot natives | |

| Option | Description | Selected |
|--------|-------------|----------|
| Live wins, yaml catches up | Portal is reality; no portal mutation from reconciliation | ✓ |
| yaml wins, portal patched | Config declarative; risks clobbering Phase 40 fixes | |
| Case-by-case | Each drift item adjudicated individually | |

| Option | Description | Selected |
|--------|-------------|----------|
| Existence + enum options | Presence and exact enum values; cosmetics reported not blocking | ✓ |
| Existence only | Misses the enum-value defect class | |
| Full field-by-field | Every attribute must match | |

---

## Archive semantics

| Option | Description | Selected |
|--------|-------------|----------|
| HubSpot soft-archive | DELETE = archive; data retained, restorable; snapshot first | ✓ |
| Hide only, keep active | Set hidden, leave live | |
| Snapshot then leave untouched | No portal mutation at all | |

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch JSON to repo, then deactivate | Definition in git, flow disabled, reversible | ✓ |
| Fetch JSON, then delete | Portal object removed | |
| Fetch JSON, leave enabled | Definition archived only | |

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamped under config/ | Snapshots keep existing dest; archives in dated dir under config/hubspot_flows/ | ✓ |
| Phase directory | Everything under .planning/phases/42-*/archive/ | |
| You decide | Claude picks paths | |

---

## Reconcile tooling

| Option | Description | Selected |
|--------|-------------|----------|
| Standing drift-check script | Read-only scripts/ checker, JSON report + exit code, re-runnable | ✓ |
| One-off reconciliation | Manual fix, no reusable tool | |
| Extend snapshot script | --reconcile mode on the existing tool | |

| Option | Description | Selected |
|--------|-------------|----------|
| Claude executes, snapshot-first | Phase 40 D-08 envelope; reversible actions | ✓ |
| Operator-armed | Two-key gate for archive mutations | |
| You decide | Per artifact type | |

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand + pre-change | Same tier as parity full run; not in sweep | ✓ |
| Add to unattended sweep | Sweep reports drift automatically | |
| You decide | Claude picks cadence | |

---

## Claude's Discretion

- Archive directory name/date format
- Drift-report JSON shape and exit-code semantics
- Reference-detection method for orphan derivation
- Cosmetic-drift reporting granularity
- Archive operation ordering

## Deferred Ideas

- All four matched todos stay backlog (sweep lookback, sweep crontab, upload aliases,
  enrichment throughput)
- Adding drift checker to the unattended sweep — declined now, revisit if schema churn rises
