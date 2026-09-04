---
created: 2026-09-04T22:00:00.000Z
updated: 2026-09-04
title: state the price and keep moving — stop halting for approval on a disclosure
area: operator-plugin
severity: enhancement
goal: frictionless enrichment (operator, 2026-09-04); wanted as DEFAULT, not gated on the autonomy flag
files:

  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/scripts/write_grant.py

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The request

> "I also want to stop Claude from stopping and requiring approval when disclosing price.
> Just state and keep moving (set this to default behaviour even without autonomy flag),
> approval is default, the operator can interrupt if they wish." — operator, 2026-09-04,
> after the Roma Turf Club round halted at its price line.

## There are TWO stops in that flow and only one is a disclosure — do not conflate them

`suggest-contacts/SKILL.md` step 4 already branches:

- **A grant IS open** — "Show the suggestion allowance already sitting in the open grant's
  envelope (`figures["suggestion_allowance"]["line"]`) … state plainly that this is a
  worst-case ceiling and that actuals land at or under it." **Disclosure, no stop. The
  requested behaviour is ALREADY the spec on this branch.**
- **No grant is open** — follow `enrich-before-ingest/SKILL.md` step 5's two-phase ask
  verbatim: *"disarmed is the default, say so plainly, then ask for this round by naming what
  it will do. An affirmative answering that question — 'yes', 'go ahead', 'do it' — **arms
  this run and nothing else**; anything ambiguous is not consent."*

The Roma round took the second branch. So "Arm this round? Reply yes" was **not** a
confirmation of a price the operator had just read — it was the consent that authorises the
provider spend and the write. Removing it does not make a disclosure non-blocking; it arms a
run with no affirmative.

## The real friction, and it is not the ask

The Brisbane Roar round was invoked as `285507657175 - grant approved for session`, and the
session still correctly reported **no machine grant open** — a phrase in an argument string
is not a grant. So the operator intended a session grant, did not get one, and consequently
hit the per-round ask that a grant exists precisely to avoid.

**That points at the fix that gives the operator what they want without dissolving consent:
make opening a real session/batch grant the easy, obvious first move.** One consent point per
BATCH, then every round inside it takes the already-silent branch. `allow_write_grants` is
already `true` in this operator's config and the grant envelope already carries
`figures["suggestion_allowance"]`, so the machinery exists; what is missing is the ergonomics
of opening one.

## Two readings the planner must put to the operator

1. **Narrow (recommended).** Keep the no-grant ask exactly as-is, and make the granted path
   frictionless — easier grant opening, and an audit that no *other* disclosure in these
   skills has drifted into a blocking question. Delivers the stated outcome; nothing about
   consent changes.
2. **Broad, as literally worded.** Make "approval is default" true on the no-grant branch
   too: state what the round will do, then proceed unless interrupted. This is implicit
   consent for provider spend and CRM writes. It is a coherent position for an operator who
   is present and watching — which is exactly the case the operator described — but it is
   NOT the same claim as unattended autonomy and must not be implemented in a way that also
   loosens the unattended path. See
   `.planning/todos/pending/2026-09-04-autonomy-flag-with-sensible-defaults.md`, and note
   D-61-08's unattended gate is shut by a recorded decision.

If (2) is chosen, two properties must survive because they are what make an interrupt
meaningful:

- **The ceiling still binds.** `CapRefused` (a cap above the grant's priced cap) and the
  per-run ceiling refusal stay in code, not prose. "Proceed unless interrupted" must never
  become "proceed past a refusal".
- **D-59-06 still holds and gets sharper.** An interrupt refuses the NEXT send; a dispatch
  already running finishes its chunks. If approval is implicit, the window between the
  operator reading the line and deciding to interrupt is a window in which spend may already
  have started. Decide explicitly whether the disclosure must precede the first spend by
  some real interval, or whether the ceiling alone is the containment.

## Audit to run either way

Sweep all skills for disclosures that halt but should not. A statement of fact the operator
cannot act on differently is not a decision point, and each one costs a round trip:

- price/ceiling lines on a granted round
- "backend is disarmed" status statements
- provenance and source summaries
- post-run reports

Distinguish these from genuine decision points (roles, cap, arming, a held-row adjudication),
which stay.
