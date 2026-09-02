# Phase 24: Non-Tabular Input Adapters - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 24-non-tabular-input-adapters
**Areas discussed:** Extraction engine, Provenance representation, Ambiguity confirmation, Screenshot overlap dedupe

---

## Extraction engine

| Option | Description | Selected |
|--------|-------------|----------|
| Claude in-session, no API call | Skill instructs Claude to read prose/image and emit canonical rows; Python validates shape and identity. No API cost, no key, native image reading. Quality tracks session model. | ✓ |
| Python script calling the Anthropic API (Haiku) | Mirrors the backend's Haiku classifier pattern — pinned model, versionable prompt, isolated tests. Puts an Anthropic key in the plugin and costs per batch. | |
| Hybrid: in-session for images, API for bulk text | Optimizes each path; two extraction implementations to keep consistent on no-invention. | |

**User's choice:** Claude in-session
**Notes:** Recommended option taken as-is. Accepted trade-off: extraction quality is not pinned to a model version.

---

## Provenance representation

| Option | Description | Selected |
|--------|-------------|----------|
| Preview-only sidecar, stripped before dispatch | Parallel structure rendered as preview columns, dropped from the POST body. Keeps STRUCT-01 exactly true. Does not survive into HubSpot. | ✓ |
| Written to a local audit file per batch | Survives the session for later audit; adds a file surface and a retention question. | |
| Both | Best audit trail, most surface for an adapters phase. | |

**User's choice:** Preview-only sidecar
**Notes:** Recommended option taken as-is.

---

## Ambiguity confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Collected into one list at preview time | All ambiguous cells gather into one "needs your eyes" block; operator resolves in a single reply. One interruption per batch. | ✓ |
| Ambiguous rows held out entirely | Simplest and safest; loses otherwise-good rows with no rescue path. | |
| Per-row prompt as each ambiguity is hit | Most precise, unusable at batch size. | |

**User's choice:** Collected into one list at preview
**Notes:** Recommended option taken as-is. Follow-on rule recorded as D-07: an unresolved ambiguity leaves the value absent rather than guessed.

---

## Screenshot overlap dedupe

| Option | Description | Selected |
|--------|-------------|----------|
| The identity rule already in use | email match, or firstname+lastname+company match — same rule n8n uses. Near-duplicates differing in a truncated field surface as ambiguities. | ✓ |
| Exact match on all populated fields | Never wrongly merges; fails the actual overlap case where one copy is cut off. | |
| Ask the operator when overlap is detected | No wrong merge; turns every scrolled capture into a negotiation. | |

**User's choice:** The identity rule already in use
**Notes:** Recommended option taken as-is. One dedupe concept across client and backend.

---

## Claude's Discretion

- Foreign-JSON key-translation approach and how unmappable keys are reported
- Wording of per-row rejection reasons for identity-rule failures
- Preview layout for provenance columns
- Error taxonomy for unreadable / empty / unsupported input
- Whether the URL adapter summarizes before extracting or extracts directly

## Deferred Ideas

- Persistent provenance / audit archive — raises an unscoped retention question
- Pinned-model extraction — revisit if session-model variance proves unstable
- Company-object ingestion — out of milestone
- Cost estimation for extraction — moot; D-01 makes extraction free of provider and API cost
