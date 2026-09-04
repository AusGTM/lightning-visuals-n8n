# Phase 58: Take What the Operator Actually Has - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-26
**Phase:** 58-take-what-the-operator-actually-has
**Areas discussed:** Who researches the domain, Confirm-before-write shape, Research cost consent, Company extraction contract

---

## Pre-discussion scope question

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to Phase 54 | Keep 58 pure input-flexibility; review-clearing rides with single-pass dispatch | ✓ |
| Fold into 58 | 58 grows a review-lane workstream for contact flags | |
| Own quick task | Bounded quick task before/alongside 58 | |

**User's choice:** Defer to Phase 54 (contact review-flag clearing gap)

---

## Who researches the domain

| Option | Description | Selected |
|--------|-------------|----------|
| Claude proposes, backend verifies | Claude proposes free/instant, marked unverified; backend research node verifies only where needed | ✓ |
| Backend research node only | Every missing domain through Claude Web Research node (~$ per company) | |
| Claude in-conversation only | No backend research call at all | |

**User's choice:** Claude proposes, backend verifies (recommended)

Follow-ups:
- **Verification trigger:** Operator confirm substitutes for backend verification (vs always-verify, confidence-gated) — selected recommended.
- **Profile URL:** Yes, input only — URL seeds research, never becomes a domain (vs name-only seeding) — selected recommended.

---

## Confirm-before-write shape

| Option | Description | Selected |
|--------|-------------|----------|
| Batch table, per-row control | One table, per-row pick/deny, one scoped approve | ✓ |
| Per-company confirm | One at a time — the "incredibly halting" pattern | |
| Confirm only the doubtful | Confident proposals silent unless objected | |

**User's choice:** Batch table, per-row control (recommended)

Follow-ups:
- **Evidence per row:** Source + one-line reason (vs full evidence block, domain only) — selected recommended.
- **Denied row fate:** Fall back to name-only / accept-by-name; operator may type correct domain (vs hold, drop) — selected recommended.
- **Operator-typed domain:** Syntax/NOT_A_COMPANY_DOMAIN guard only, no research pass (vs verify like a proposal) — selected recommended.

---

## Research cost consent

| Option | Description | Selected |
|--------|-------------|----------|
| Own line, named rows | Envelope line "domain research: N × ~$Y", names which rows, declinable | ✓ |
| Folded into Anthropic total | Merged, declinable thing invisible | |

**User's choice:** Own line, named rows (recommended)

Follow-ups:
- **Declined-research fate:** Name-only fallback, same path as denied proposal (vs held, ask per batch) — selected recommended.
- **Default:** Default-on, declinable (vs opt-in only) — selected recommended.

---

## Company extraction contract

| Option | Description | Selected |
|--------|-------------|----------|
| Name alone | A company name is enough; domain researched when absent | ✓ |
| Name + one corroborator | Rejects bare name lists | |

**User's choice:** Name alone (recommended)

Follow-ups:
- **Fields:** Enrichment seeds only (country/industry/website URL) (vs name+domain only, everything visible) — selected recommended.
- **Mixed input:** One extraction pass, both lanes, companies-first preserved (vs company-only this phase) — selected recommended.
- **Source types (multi-select):** All four (paste/JSON/URL/screenshot) + bare name list + search-results screenshot — all selected.

## Claude's Discretion

- Table rendering, confirm-question wording, "check it" phrasing (bound by VOCAB-01..03)
- Confidence heuristic for when Claude declines to propose and routes to backend research
- Ambiguous-name handling (extend existing two-matches-is-ambiguity rule)

## Deferred Ideas

- Contact review-flag clearing lane → Phase 54 (operator ruling this session)
