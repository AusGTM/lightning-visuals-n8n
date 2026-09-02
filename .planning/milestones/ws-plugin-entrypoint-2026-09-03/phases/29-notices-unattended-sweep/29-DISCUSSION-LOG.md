# Phase 29: Notices & Unattended Sweep - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 29-notices-unattended-sweep
**Areas discussed:** Sweep host, In-session watch bound

---

## Sweep host

| Option | Description | Selected |
|--------|-------------|----------|
| Claude scheduled routine reusing the plugin's read paths | Runs Phase 27's read surface on a cadence and pushes a notification. Read-only by construction. Notice lands where the operator already is. Depends on scheduled agents being available. | ✓ |
| n8n Schedule Trigger workflow that emails or Slacks | Machinery already exists in-repo; n8n cannot push into a Claude conversation, so the notice arrives in a different channel from where the operator would act. | |
| OS-level cron running a script | Platform-independent; needs an always-on machine and an admin install, against the milestone's no-scripts posture. | |

**User's choice:** Claude scheduled routine
**Notes:** Recommended option taken as-is. Availability of scheduled agents on the operator's account recorded as D-04 — an early verification task, not an assumption.

---

## In-session watch bound

| Option | Description | Selected |
|--------|-------------|----------|
| Admin-config value with a sane default | Default tuned to observed run times, raisable for a slow backend. The right bound is empirical and no batch-timing data exists yet. | ✓ |
| Fixed time bound in code | Nothing to misconfigure; useless if the backend gets slower than the constant. | |
| Bounded by poll count | Predictable cost; operators experience time, not polls. | |

**User's choice:** Admin-config value with a sane default
**Notes:** Recommended option taken as-is. D-06 shares the measurement task with Phase 25's chunk-size sizing rather than duplicating it.

---

## Claude's Discretion

- Sweep cadence default and configurability
- Notification wording and grouping when several conditions fire together
- Review-backlog threshold default
- Backoff schedule within the in-session watch
- Whether the watch reports incrementally as chunks settle or once at the end

## Deferred Ideas

- Unattended ingestion — permanently deferred by REQUIREMENTS.md
- Automatic action on findings — notices point at Phase 28's controls; a human decides
- Alternative sweep hosts — revisit only if D-04's availability check fails
- Per-condition notification channels
