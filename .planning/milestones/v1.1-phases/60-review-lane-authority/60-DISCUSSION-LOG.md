# Phase 60: Review-lane authority - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-01
**Phase:** 60-review-lane-authority
**Areas discussed:** Authority model, Round-trip closure scope, Arm granularity

---

## Authority model

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Admin config key | Mirrors `allow_write_grants`; keeps review as its own separate authority from dispatch grants — 30-01's separation stays intact. | |
| (b) Make review grantable | Fold review into the same standing write_grant flow enrichment/contacts use — reverses the deliberate 30-01 separation. | ✓ |
| (c) Accept the admin deploy | No phase work — document the two-round-trip flow as correct for occasional triage. | |

**User's choice:** (b) Make review grantable

| Option | Description | Selected |
|--------|-------------|----------|
| Review is its own lane, opened separately | Opening an enrichment grant never silently authorizes review approvals. | |
| One grant covers all three lanes together | Opening any grant authorizes enrichment, contacts, AND review in one yes. | ✓ |

**User's choice:** One grant covers all three lanes together

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — same record scoping applies | A grant opened over A/B/C can only approve review decisions on A/B/C. | ✓ |
| No — any flagged record | An open grant authorizes review on any flagged record regardless of the grant's own list. | |

**User's choice:** Yes — same record scoping applies

| Option | Description | Selected |
|--------|-------------|----------|
| Retire ALLOW_REVIEW_SUBMIT — grant is the gate | Grant-authorization replaces the env-var check entirely. | ✓ |
| Keep it as an extra defense layer | Grant AND the env var both required — belt-and-suspenders. | |

**User's choice:** Retire it — the grant is now the gate
**Notes:** Combined, these four answers mean: one grant, covering all three lanes, scoped by the same record-id/domain narrowing dispatch already uses, with `ALLOW_REVIEW_SUBMIT` retired in favor of the grant's own authorization check.

---

## Round-trip closure scope

| Option | Description | Selected |
|--------|-------------|----------|
| Wire it dynamically — close both round trips | Extend `n8n_arming`'s existing overlay mechanism (already supports `ALLOW_HUBSPOT_REVIEW_WRITES` as one of its 5 flags) to review, removing the admin-deploy step entirely. | ✓ |
| Leave the admin-deploy step as-is | Grant becomes the client-side yes; a human still runs a deploy to actually enable the backend write. | |

**User's choice:** Wire it dynamically — close both round trips
**Notes:** Claude flagged that without this, choosing "review is grantable" wouldn't actually remove the friction that mattered most (the deploy step, not the shell-env step).

---

## Arm granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Per-decision — arm, submit, disarm each time | Mirrors how each enrichment SEND already opens its own window under `authorize_send`. | |
| One arm covers a batch of review decisions | Open once, approve/reject several records, disarm at the end. | ✓ |

**User's choice:** One arm covers a batch of review decisions

---

## Claude's Discretion

- Exact mechanism/placement for a `REVIEW_FLAGS`-style constant and the review-specific arm wrapper (new `n8n_arming.py` function vs. a `write_grant.py` call site composing existing primitives directly) — left to whichever produces the smaller diff.
- Whether the batch arm reuses `n8n_arming.armed_window`'s existing exception-safe disarm guarantee as-is, or needs a review-specific variant — expected to carry over unchanged.

## Deferred Ideas

None raised during this discussion. One low-scoring todo match (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`, score 0.2) was reviewed but not folded — already noted as unrelated to this phase's subject in Phase 59's own context.
