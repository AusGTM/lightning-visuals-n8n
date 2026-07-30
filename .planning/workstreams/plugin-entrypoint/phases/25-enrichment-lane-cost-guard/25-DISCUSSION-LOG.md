# Phase 25: Enrichment Lane & Cost Guard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 25-enrichment-lane-cost-guard
**Areas discussed:** Record naming/resolution, Provider selection, Cost rate source, Chunking

---

## Record naming and resolution

| Option | Description | Selected |
|--------|-------------|----------|
| n8n resolves it | Plugin passes the identifier through; n8n expands list/view → record IDs with its HubSpot credential. Keeps the credential boundary. Requires n8n-side work. | ✓ |
| Plugin gets a read-only HubSpot token | Client could show a resolved count pre-preview; breaks the credential boundary. | |
| Record IDs only this phase | Smallest build; leaves INGEST-04 partly unmet. | |

**User's choice:** n8n resolves it
**Notes:** Recommended option taken as-is. Consequence recorded as D-02 — no client-side record count for list/view inputs.

---

## Provider selection

| Option | Description | Selected |
|--------|-------------|----------|
| Stated per batch, default none | Silence enables nothing; matches criterion 2 literally. | |
| Admin config default, overridable per batch | Less repetition; a permissive default becomes silent credit burn. | ✓ (modified) |
| Always the full waterfall unless excluded | Best match rates; inverts the requirement's opt-in semantics. | |

**User's choice:** Admin config default, overridable per batch — **with the shipped default set to the full waterfall**. The committed example config must explicitly acknowledge the credit-burn implications and state that full waterfall, a selected cohort, or none are all valid, and that any can be overridden per batch.
**Notes:** Chosen with the conflict stated. This effectively merges options 2 and 3 and **amends Phase 25 success criterion 2** ("with no selection stated, no provider is enabled and no credits burn"). Recorded as D-05, the milestone's second accepted requirement amendment. Mitigation is the documented example config plus D-06's mandatory display of the resolved selection in every preview.

---

## Cost rate source

| Option | Description | Selected |
|--------|-------------|----------|
| Versioned rate table in the plugin, stamped with measurement date | Seeded from repo's measured actuals; plugin-local so PLUGIN-04 holds; staleness visible. | ✓ |
| Served by the n8n status endpoint with balances | One fetch for rates and balances; puts rate-keeping in the backend. | |
| Read the repo's cost-ledger docs at runtime | Always current; couples client to backend doc paths — the coupling that broke during today's workstream reorg. | |

**User's choice:** Versioned rate table in the plugin
**Notes:** Recommended option taken as-is.

---

## Chunking

| Option | Description | Selected |
|--------|-------------|----------|
| Client splits, sends sequentially, stops on first failure | Clean boundary for retry. | |
| Client splits, sends sequentially, **skips failures, presents them as a separate batch** | Run completes; failed chunks come back as a re-sendable unit. | ✓ |
| Client splits, sends all chunks in parallel | Faster; ambiguous partial state on failure. | |
| One POST carrying a chunk plan, n8n splits | Client stays simple; more backend work. | |

**User's choice:** Client splits, sends sequentially, skips failures, presents them as a separate batch
**Notes:** User-issued correction to the originally-recommended stop-on-first-failure. Recorded as D-12/D-13. The failed set being a *batch* rather than an error list is what makes Phase 26's safe retry a re-dispatch rather than a reconstruction.

---

## Claude's Discretion

- Chunk size threshold default and where it is configured
- Rate-table file format and date-stamp representation
- Preview layout for the cost block
- Enrichment POST envelope details beyond what `Parse HubSpot Event` requires
- Internal shape of the credit-only status endpoint, provided "unknown" stays distinct from zero

## Deferred Ideas

- ROADMAP Phase 25 criterion 2 rewording — required by D-05
- Full backend health surface — Phase 27
- Retry execution on the failed-chunk batch — Phase 26
- Resolved record count for list/view inputs — blocked by the credential boundary
- Parallel chunk dispatch — rejected in favour of sequential-with-skip
