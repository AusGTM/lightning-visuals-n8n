# Phase 27: Backend Status Surface - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 27-backend-status-surface
**Areas discussed:** Status assembly split, Error translation, Reporting scope

---

## Status assembly split

| Option | Description | Selected |
|--------|-------------|----------|
| Split by credential boundary | Client reads /api/v1/workflows and /executions directly; n8n endpoint supplies only credential-gated facts (provider balances, HubSpot lock/review counts, credential health). | ✓ |
| One n8n endpoint returns everything | Single call and shape; duplicates data the client can read and needs a backend edit per status change. | |
| Client reads what it can, endpoint fills gaps | Maximum client autonomy; blurs ownership and makes unknown-vs-zero harder to keep straight. | |

**User's choice:** Split by credential boundary
**Notes:** Recommended option taken as-is.

---

## Error translation (STATUS-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Static signature table, unknowns fall through honestly | Deterministic and testable; unmatched errors say so and name the admin. | |
| Claude interprets each error in-session | Handles novel errors; non-deterministic on a who-can-fix-it surface. | |
| Table first, Claude for anything unmatched | Best coverage; the fallthrough is where a wrong guess is most likely and least detectable. | ✓ |

**User's choice:** Table first, Claude for anything unmatched
**Notes:** Chosen with the risk stated in the option text. Mitigation recorded as **D-05**: an unmatched error must be labelled as an interpretation rather than a known cause, must show the raw error text, and must default the who-can-fix-it attribution to "an admin" rather than telling the operator they can fix something unrecognized. D-06 adds that repeatedly-seen signatures get promoted into the static table.

---

## Reporting scope

| Option | Description | Selected |
|--------|-------------|----------|
| Everything the n8n API key can see | Truthful by construction; new workflows appear without a config edit. | ✓ |
| Allowlist in admin config | Focused, no noise; a new or renamed workflow goes silently unreported. | |

**User's choice:** Everything the API key can see
**Notes:** Recommended option taken as-is.

---

## Claude's Discretion

- Conversational status layout and grouping
- Dashboard Artifact design, provided it carries the same data and a fetch-time stamp
- Initial error-signature table contents beyond the four causes criterion 2 names
- How "in flight" is determined from the executions API
- Internal shape of the generalized status endpoint

## Deferred Ideas

- Mutating anything — Phase 28
- Unprompted notification — Phase 29 / NOTICE-03
- Review-queue detail and resolution — Phase 30
- Ongoing promotion of fallback-interpreted errors into the static table
