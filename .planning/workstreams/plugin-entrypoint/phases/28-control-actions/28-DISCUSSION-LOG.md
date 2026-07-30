# Phase 28: Control Actions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 28-control-actions
**Areas discussed:** Live-write arming, Starting a run, Cadence translation, Reversibility statement

---

## Live-write arming (the conversation-scope contradiction)

| Option | Description | Selected |
|--------|-------------|----------|
| Arm → dispatch → disarm, read-back verified both ways | Flag on only for one operation's span. Scoped tighter than the conversation. Crash mid-operation leaves it armed — visible in status, catchable by Phase 29's sweep. | ✓ |
| Arm for the conversation, disarm on a TTL sweep | Matches CONTROL-04's wording most literally; the lapse depends on Phase 29's sweep running, else the backend stays armed indefinitely. | |
| Never flip n8n — keep Phase 23's client-side flag | Zero mutation risk; only works if an admin leaves n8n's gate permanently armed, moving the real gate out of the operator's view. | |

**User's choice:** Arm → dispatch → disarm, read-back verified
**Notes:** Recommended option taken as-is. The crash window was stated in the option text and is recorded as D-03 with two named mitigations rather than being treated as solved.

---

## Starting a run

| Option | Description | Selected |
|--------|-------------|----------|
| Webhook POST for lanes, n8n API for scheduled scans | Each uses the mechanism it already has; no new trigger surface. Lane starts keep the preview, cost guard, and arming gate. | ✓ |
| n8n API execution trigger for everything | Uniform; bypasses the guards that sit on the dispatch path. | |
| Add a manual-trigger webhook to every workflow | Consistent and client-simple; new backend surface and another entry point per workflow to secure. | |

**User's choice:** Webhook for lanes, n8n API for scheduled scans
**Notes:** Recommended option taken as-is.

---

## Cadence translation

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed vocabulary of allowed cadences | Closed set mapped to known-good cron; anything outside refused. Bounded and testable. | |
| Free-form natural language parsed to cron | Flexible; a misparse silently changes credit burn rate. | ✓ (modified) |

**User's choice:** Free-form natural language parsed to cron — **but interpreted back to the operator in plain language for confirmation before conversion to real cron**.
**Notes:** User-modified. The confirmation step is what makes free-form acceptable: the operator confirms the meaning ("every weekday at 9am and 5pm"), never the syntax. Recorded as D-08/D-09, with D-10 adding that an unconfident parse is refused with examples rather than guessed.

---

## Reversibility statement

| Option | Description | Selected |
|--------|-------------|----------|
| Captured prior state, quoted back | Exact even for unusual prior values; the pre-read is already required for read-back verification, so it is free. | ✓ |
| Generic inverse per action type | Simple and always available; wrong or vague when the prior state wasn't the obvious default. | |

**User's choice:** Captured prior state, quoted back
**Notes:** Recommended option taken as-is.

---

## Claude's Discretion

- Consequence-statement wording per action type
- Confirmation phrasing and how the "what will change" diff is displayed
- How the natural-language cadence parse is performed and rendered back
- Retry posture when read-back verification is inconclusive
- Whether arm/dispatch/disarm is presented as one action or three

## Deferred Ideas

- Unattended detection of a stuck-armed backend — Phase 29 / NOTICE-03
- Arbitrary workflow deployment or node editing — permanent exclusion
- Review-queue writeback gating — Phase 30 / REVIEW-03
- Widening the mutation allowlist — a new requirement, not a planning decision
