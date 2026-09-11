# Phase 71: A held new person lands in HubSpot with one reply - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-11
**Phase:** 71-a-held-new-person-lands-in-hubspot-with-one-reply
**Areas discussed:** Seed source, On-disk queue, Fold todo

Operator instruction before discussion: "Carry forward previous decisions made. do not relitigate.
only surface open rulings or conflicting rulings to clarify." A first four-area question set was
withdrawn on that instruction; the F2 ruling, D-69-03/04, D-70-11, §13.0.1 and the backloaded-gate
ruling were carried forward without questions. One conflict (D-69-04 keys on `company_id`, which a
`needs_company` row lacks) was resolved by derivation from `required_identity.any_of`, not asked.

---

## Seed source

| Option | Description | Selected |
|--------|-------------|----------|
| Stamp at persist time | Step 6 already knows whether the row's domain is among step-2 confirmed domains or same-run creates; write it on the held entry; both surfaces read the stamp | ✓ |
| Step-2 domains at batch only | Seed only in enrich-before-ingest; review-triage stays operator-statement only | |
| n8n read at facet time | New backend read; conflicts with §13.0.1 unless it reuses companyLink; an execution per lookup | |

**User's choice:** Stamp at persist time (Recommended)
**Notes:** Supersedes w6p's executor choice "nothing writes a confirmed company back into the entry" — executor design, not an operator ruling.

---

## On-disk queue

| Option | Description | Selected |
|--------|-------------|----------|
| Wipe once, re-run UAT | Delete the 4 UAT entries in the gate's clean-up; second-round CSVs repopulate under the new key; no migration code | ✓ |
| Lazy rekey on load | `load()` rekeys legacy row-N entries and dedupes Barry; migration code lives forever for 4 rows | |

**User's choice:** Wipe once, re-run UAT (Recommended)

---

## Fold todo

| Option | Description | Selected |
|--------|-------------|----------|
| Fold | Adjacent residual in held_queue.py's persist path (§31 rule 3); unblocks Grant-named UAT rows | ✓ |
| Defer | Keep as minor todo; UAT keeps avoiding the name | |

**User's choice:** Fold (Recommended)

## Claude's Discretion

- Stamp field name/shape; stable-key normalisation and serialisation; how `classify_read` reports a legacy document.

## Deferred Ideas

- `company-domain-has-no-candidate-source`, `enrichment-throughput-ceiling`, `merge-multi-run-drain-and-grouping-unobserved` — reviewed, not folded (n8n side).
