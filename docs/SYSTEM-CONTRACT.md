# Lightning Visuals Enrichment System — Contract

**Status:** approved 2026-07-23
**Purpose of this document:** the agreed statement of what this system is responsible for, and the standard it is evaluated against. Where an implementation decision conflicts with this contract, the contract governs — change the contract deliberately, not by drift.

---

## Mandate

Keep HubSpot's company and contact data accurate, well-sourced, and trustworthy — so the GTM org can treat HubSpot as the canonical source of truth. **The system supplies _facts_; HubSpot and its owners supply _judgment_.**

Companies and contacts are the same job: get the facts right and record where they came from. All go-to-market judgment — ICP score, tier, buyer persona, who to target — lives in HubSpot and may change over time without touching this system.

## Boundary of responsibility

- **In scope:** gathering, reconciling, and writing factual enrichment inputs for companies and contacts, with provenance, on a continuous basis.
- **Out of scope, by design:** computing ICP scores, tiers, or vetoes; deciding buyer personas or who to target; any go-to-market judgment. These live in HubSpot and may change over time without touching this system. (This is the "Approach C" separation of responsibilities: the pipeline writes ICP _inputs_; HubSpot derives all scored _outputs_.)

## How truth is established (the accuracy model)

There is no external oracle of correctness, and there should not be — because truth moves. What is true of a company today may not be true next year. Correctness is therefore defined by _process_, not by matching a frozen answer key:

1. **Consensus first.** When two or more independent paid sources (ZoomInfo, Apollo, Lusha) agree on a value, that is the value.
2. **Web research fills the gaps** the paid sources structurally cannot — organisation type, and whether the company produces broadcast/streaming content — and must cite a source that substantiates the claim.
3. **The judge adjudicates conflict**, grounded in web evidence _and_ the scoring signals (source accuracy, recency, agreement, trust). It decides only what models are good at — identity and classification — never numeric plausibility.
4. **When there is neither consensus nor sufficient evidence, the answer is "unknown"** and the record goes to human review. The system never manufactures a value.

## Commitments the system is evaluated against

1. **Accuracy by process, not oracle.** Every asserted value is either a source consensus, a judge decision on cited evidence, or absent. No value is written that isn't traceable to one of these.
2. **Full provenance.** Every enriched field carries its source, confidence, evidence, and timestamp. Any value can be explained after the fact.
3. **Non-clobber is absolute.** Manually entered data and higher-confidence existing data are never overwritten. Enrichment fills gaps and stages suggestions; it does not destroy human work. _(Cardinal governance rule — zero tolerance.)_
4. **Conservative by the agreed fear ordering.** Wrongly disqualifying a real prospect is the cardinal sin; an honest "unknown" that lands in review is the accepted cost. A negative claim (e.g. "produces no content") requires positive evidence, never mere absence.
5. **Freshness without churn.** Records are kept current through scheduled maintenance, but a value inside its freshness window is trusted, not re-enriched. The system does not burn effort re-litigating settled facts.
6. **Right-sized compute.** Each task uses the cheapest sufficient method — deterministic rules where possible, a fast cheap model for simple classification, a capable model only for genuine conflict or high-risk decisions. Capability is spent only where it changes the outcome.
7. **Coverage.** The system continuously works toward every eligible record having its key inputs resolved _or explicitly marked unknown / in-review_ — no silent gaps. A well-marked unknown counts as covered.
8. **Auditability and reversibility.** Schema and data changes are logged, dry-run-able, and reversible, meeting the higher governance bar of a canonical CRM.
9. **Continuous, low-friction operation.** Three supported triggers — batch (upload to HubSpot, cron catches the blanks), on-demand (per-record flag, picked up by the next scheduled tick — daily since 2026-08-10; for immediate processing use the webhook), reactive (webhook on change). Batch freshness is within one cron interval, not instant.

## How each commitment is checked

- **Accuracy / provenance / non-clobber / conservatism** — automated audits over the pipeline's own records: every written field has a provenance entry; no write overwrote a manual or higher-confidence value; no negative claim lacks a citation; unknowns outnumber guesses at the margin.
- **The closed-won / closed-lost population** serves as an ongoing _regression signal_, not an oracle: customers should read as content-producing; an evidenced "no" on a customer is a red flag surfaced for a human.
- **Freshness / churn** — re-enrichment respects the TTL; a monitored re-research rate that stays bounded.
- **Compute discipline** — structural proof that cheap paths handle the common cases and the capable model fires only on defined triggers.
- **Coverage / operation** — the proportion of eligible records resolved-or-explicitly-unknown, trending up, with no record stuck silently.

## Explicit non-goals

Not a scoring engine. Not a targeting engine. Not a decision-maker. Not a system of record for judgment — only for facts and their provenance.

## Notes on deliberate omissions

- **No numeric accuracy target** (e.g. "95% correct"). With no oracle to measure against, a headline number would be theatre; correctness is defined procedurally above. A numeric target would require a hand-labelled ground-truth set, which the accuracy model deliberately rejects.
- **Coverage (7) and freshness (5) are in mild tension** — "resolve everything" vs "don't churn." Reconciled by defining coverage as _resolved-or-explicitly-unknown_: a well-marked unknown is covered, and is not re-enriched until its freshness window lapses.

---

_Approved 2026-07-23 after an end-to-end walkthrough. Supersedes ad-hoc scope statements scattered across CLAUDE.md and the planning docs where they conflict._
