---
created: 2026-09-04T21:00:00.000Z
updated: 2026-09-04
title: an autonomy flag with sensible defaults, so every function can run without human intervention
area: operator-plugin
severity: enhancement
goal: frictionless enrichment (operator, 2026-09-04) — same intent as the rich-enrichment todo
files:

  - operator-claude-plugin/config/operator.local.example.json
  - operator-claude-plugin/scripts/config_gate.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/scripts/n8n_arming.py
  - operator-claude-plugin/skills/*/SKILL.md

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The request

> "Separately it was suggested to set an autonomy flag with sensible defaults, so all
> functions can be run autonomously without human intervention to make enrichment
> frictionless." — operator, 2026-09-04

Same underlying goal as `2026-09-04-phone-is-never-chased-only-accepted.md`: the system
should do the useful thing by default rather than stopping to ask.

## The good news: the safety scaffolding this needs ALREADY EXISTS

This is not a "build autonomy" task. Phase 57 (completed 2026-09-01) built the three things
an unattended run needs in order to be defensible, and Phase 61 built the run machinery:

| Capability | Where |
| --- | --- |
| Per-run ceiling + OK/OVER/UNKNOWN verdict against the monthly allowance | `write_grant.allowance_headroom` / `ceiling_verdict` |
| **Refusal before start** — a CEILING_OVER batch is refused before anything is armed, carrying the refusal arithmetic and an override path | `write_grant.plan_grant` |
| **Post-run proof** — one end-of-run report joining five durable stores plus a per-run audit record | `write_grant.record_audit`, `build_run_report` |
| Run scope, resume, held rows, confidence verdicts | `run_manifest.py`, `run_state.py`, `held_queue.py`, `confidence.py` |
| Headless arm/disarm for the cron path | `scheduled_arm.py`, `n8n_arming.py` |

So the missing piece is the **switch and its defaults**, not the guard rails.

## What this flag would REVERSE — read before planning

**D-61-08's unattended gate is deliberately shut, by a recorded operator decision.** At Phase
57-05's Task 4 phase gate the operator selected **option-a**: deploy the regenerated ingest
workflow, and authorise a **SMALL, operator-supervised** first live batch — explicitly *not*
the first unattended credit-spending batch. Option B (authorising the unattended batch) was
on the table and was not taken.

**The standing fact today: nothing is armed, and the first live unattended, credit-spending
batch has never run.** An autonomy flag is the thing that crosses that line. That is the
operator's call to make — this todo does not re-litigate it — but the plan must present it as
a deliberate reversal of a recorded decision, not as a config convenience that happens to
imply one.

**A hard precondition is already on the record:** authorising the first unattended
credit-spending batch is forbidden while the ceiling sample reads `CEILING_UNKNOWN`. The
monthly allowance is unguarded when unsampleable — a disclosed, not closed, residual. Any
autonomy default must fail closed on `CEILING_UNKNOWN` rather than treating an unreadable
ceiling as headroom.

**RUN-05 is not yet complete:** 57-03's affordable-subset split offer was never built, so a
batch that exceeds the ceiling can today only be refused whole, not trimmed to what fits.
Under supervision that is a conversation; unattended it is a silent no-op unless the flag
accounts for it.

## Two existing authority gates it must reconcile with, never bypass

1. **`allow_write_grants`** (JSON boolean, operator settings file) — authorises the
   INTERACTIVE path only. Deliberately the repo's first exception to "authority gates are
   environment variables", because an operator in Claude Desktop cannot set a shell variable.
2. **`ALLOW_N8N_ARM`** (environment variable, exact string `true`) — the sole authority for
   the headless and cron paths, which have no operator to confirm anything. Operator-only,
   per-shell, **never set by Claude**.

These are not alternatives and the existing note says so: turning on the interactive one does
not turn on unattended writing. An autonomy flag that collapses them into one switch would
erase that distinction — the plan must decide deliberately whether it is a third gate, or a
default-setter that still requires both.

## D-59-06 gets sharper under autonomy, not softer

Revoking a write grant refuses the **next** send; a dispatch already running finishes its
remaining chunks. Today that is disclosed at session start to a human who is watching. With
nobody watching, "revoke" means "stops eventually" and the blast radius between the revoke and
the last chunk is unobserved. Decide explicitly whether autonomy requires chunk-granular
revocation (which D-59-06 declined to build, with its cost stated) or whether the per-run
ceiling is considered sufficient containment.

## "All functions" is not one decision

The functions differ in kind and should not get one flag value:

- **Read-only** (`backend-status`, review-queue read, `loss-reason-report`): autonomy is
  trivially safe; arguably these should never have prompted.
- **Spend, no write** (match/propose lanes): bounded by provider credit, reversible in effect.
- **Write** (ingest, enrich-and-write, review decision apply): irreversible against the CRM,
  and the gates above exist for exactly these.

"Sensible defaults" most likely means per-tier defaults, not a global boolean. Name the tiers
before naming the flag.

## Suggested shape

- A per-tier setting in the operator settings file, defaulting to the CURRENT behaviour, so
  installing an update never silently turns autonomy on for an existing operator.
- Fails closed on `CEILING_UNKNOWN`, on an unread provider balance (D-57-02's tri-state
  honesty requirement: unreadable is `unknown`, never headroom), and on a missing allowance
  key (Phase 57 found that an absent allowance key silently disabled two guards).
- Does not replace `ALLOW_N8N_ARM` for the headless path.
- The end-of-run report becomes mandatory rather than conventional when the flag is on —
  under autonomy it is the only account of what happened.

## Related

- `.planning/todos/pending/2026-09-04-phone-is-never-chased-only-accepted.md` — the same
  frictionless-enrichment goal on the data-completeness axis.
