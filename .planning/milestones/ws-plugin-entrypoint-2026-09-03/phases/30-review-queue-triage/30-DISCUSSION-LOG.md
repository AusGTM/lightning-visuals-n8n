# Phase 30: Review-Queue Triage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 30-review-queue-triage
**Areas discussed:** Review writeback gate, Non-clobber enforcement

---

## Review writeback gate

| Option | Description | Selected |
|--------|-------------|----------|
| Session-scoped arm, plus exact-write display per decision | Arm once per session; every decision still shows its exact property write. Matches REVIEW-03's "session-scoped" wording while keeping per-decision visibility. | ✓ |
| Confirm each decision individually, no session arm | Tightest gate; ten reviews become ten confirmations plus ten arming steps, pushing the operator back to the HubSpot UI. | |
| Reuse Phase 28's arm → act → disarm cycle | One arming mechanism plugin-wide; REVIEW-03 explicitly wants this gate separate from dispatch arming. | |

**User's choice:** Session-scoped arm + per-decision exact-write display
**Notes:** Recommended option taken as-is. D-02 records that this gate is independent of dispatch arming in both directions.

---

## Non-clobber enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Backend enforces; client reads field_policy.yaml display-only | Single source of truth in the n8n-side review endpoint; client reads the config only to SHOW that a value is protected, same pattern as Phase 23 D-07. | ✓ |
| Backend enforces, client shows nothing | Zero coupling; operator discovers protection only after their decision silently fails. | |
| Client refuses locally as well | Fails fast; creates a second policy authority that can drift. | |

**User's choice:** Backend enforces, client displays
**Notes:** Recommended option taken as-is. D-07 explicitly forbids local refusal.

---

## Claude's Discretion

- Queue ordering and how many conflicts are shown at once
- Conflict-presentation and exact-write-display wording
- How the operator's reason is elicited
- Chat vs Artifact for the queue
- Batch resolution of records sharing one conflict shape

## Deferred Ideas

- General CRM editing from the plugin — explicit exclusion
- Write-back of corrections beyond review decisions — Future Requirements
- Automated conflict resolution — out of scope by definition
- Rubric revision from accumulated review decisions
