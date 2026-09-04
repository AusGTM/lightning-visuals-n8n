# Phase 62: Suggest the contacts nobody named - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-02
**Phase:** 62-suggest-the-contacts-nobody-named
**Areas discussed:** Discovery provider, Role vocabulary, How suggestions land, Pricing and the cap, plus a follow-up round on trigger / scope / provenance / dedupe

---

## Pre-discussion scouting finding

Before any question was asked, the built workflow was scanned for provider endpoints. Result:
**every deployed provider call is enrich/match, not discovery.**

| Provider | Deployed endpoint | Shape |
|---|---|---|
| Apollo | `/v1/organizations/enrich`, `/v1/people/match` | match a known person |
| ZoomInfo | `/gtm/data/v1/contacts/enrich`, `/companies/enrich` | enrich a known contact |
| Lusha | `/v3/contacts/search-and-enrich`, `/v3/companies/search-and-enrich` | **search** |

This reframed the first area: SUGGEST-05 names Apollo and ZoomInfo, but Lusha is the provider
whose search endpoint is already wired and already paying.

---

## Discovery provider

| Option | Description | Selected |
|--------|-------------|----------|
| Lusha search-and-enrich | Already wired, authenticated, metered. Zero new adapter surface. Contradicts the requirement's wording. | |
| Apollo mixed_people/search | What SUGGEST-05 literally names. New adapter; Apollo key already known-limited (403 on usage_stats). | |
| Lusha now, others later | Ship on Lusha; shape the adapter so others slot in without rework. | ✓ |

**User's choice:** Lusha now, others later.

| Option | Description | Selected |
|--------|-------------|----------|
| One call, priced upfront | Accept the combined search+enrich call; SUGGEST-05 satisfied by the upfront estimate. | ✓ |
| Two-step, confirm names first | Show who was found before paying to enrich. Truer to "proposed", may not be possible on a combined endpoint. | |
| You decide | Let research determine whether the endpoint can be split. | |

**User's choice:** One call, priced upfront.

| Option | Description | Selected |
|--------|-------------|----------|
| Record and move on | Mark "no candidates found", continue. | |
| Fall through to another provider | Waterfall on no-hits. | ✓ (later reversed) |
| Flag for web research | Escalate to the Claude web-research lane. | |

**User's choice:** Fall through to another provider — **later reversed**, see the conflict below.

| Option | Description | Selected |
|--------|-------------|----------|
| The batch just processed | Bounded to a set the operator just saw priced. | ✓ |
| Any company with no contacts | Broader, unbounded. | |
| Operator names a list | Most explicit, most typing. | |

**User's choice:** The batch just processed.

**Conflict raised by Claude:** "Lusha now, others later" and "fall through to another provider"
are incompatible — with only Lusha built, there is no second provider to fall through to, so the
fallback would be unreachable code.

| Option | Description | Selected |
|--------|-------------|----------|
| Defer fallback to later | Lusha-only; record no-hits and move on; adapter shaped for later. | ✓ |
| Build ZoomInfo discovery too | Make the fallback real; genuine new provider-contract work. | |
| Fall through to web research | Reuse the existing lane; company-oriented, weak for finding a person. | |

**User's choice:** Defer fallback to later.

---

## Role vocabulary

| Option | Description | Selected |
|--------|-------------|----------|
| Haiku clusters, cached | Handles messy free-text titles; one cheap call per refresh. | ✓ |
| Deterministic normalisation | No LLM, fully testable; under-clusters long-tail titles. | |
| Haiku every run | Always current; non-deterministic between runs. | |

**User's choice:** Haiku clusters, cached.

| Option | Description | Selected |
|--------|-------------|----------|
| Top N by recurrence | Evidenced, scannable fixed count. | ✓ |
| All above a threshold | Adapts to portal shape; unpredictable list length. | |
| You decide | Let research pick a cutoff from the real distribution. | |

**User's choice:** Top N by recurrence.

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse and say why | Honest refusal; matches project preference. | |
| Fall back to a generic list | SUGGEST-03 explicitly rules this out. | ✓ |
| Let the operator type roles | Always works; drops the evidence property. | |

**User's choice:** Fall back to a generic list.

**Conflict raised by Claude:** this contradicts SUGGEST-03 ("not invented and not a generic B2B
list"), and if it stands the phase closes 4 of 5 SUGGEST requirements and amends the fifth —
different from its stated purpose.

| Option | Description | Selected |
|--------|-------------|----------|
| Generic list, but disclosed | Keep the fallback, label it un-evidenced, amend SUGGEST-03. | ✓ |
| Generic list, no caveat | Simplest; evidence property silently dropped. | |
| Revert to refusing | SUGGEST-03 stays closeable as written. | |

**User's choice:** Generic list, but disclosed.
**Notes:** Recorded in CONTEXT.md as D-62-07 with the phase-accounting consequence spelled out —
the planner must not tick SUGGEST-03 as written.

---

## How suggestions land

| Option | Description | Selected |
|--------|-------------|----------|
| Synthesised rows into extraction | Reuses match, held rows, association wholesale. | ✓ |
| New suggestion lane | Tailored control; creates a second association implementation. | |
| You decide | Let research confirm extraction.py can accept synthesised rows. | |

**User's choice:** Synthesised rows into extraction.

| Option | Description | Selected |
|--------|-------------|----------|
| Whatever the provider returns | No special-casing; name-only routes to needs_review as normal. | ✓ |
| Require strong identity | Clean queue; discards people the operator paid for. | |
| Always hold for review | Safest; floods the queue. | |

**User's choice:** Whatever the provider returns.

| Option | Description | Selected |
|--------|-------------|----------|
| Whole round lands as proposals | One decision; lane's own gates satisfy SUGGEST-04. | ✓ |
| Per-person confirmation | Max control; unusable at 300 companies. | |
| Per-company confirmation | Middle ground; same scaling complaint. | |

**User's choice:** Whole round lands as proposals.

---

## Pricing and the cap

**First attempt at this area was rejected by the user**, who corrected a premise rather than
picking an option.

Claude had asked what authorises the spend, offering "its own spend confirmation" as recommended
on the reasoning that grants authorise *writes* while a suggestion round only spends *credit*.

**Operator correction, verbatim:** *"The grant has already been conflated in earlier stages. As I
mentioned a single grant covers the entire session (this would include suggestions)."*

The premise was wrong: "one grant, one yes" (D-53-05/D-53-06, proved live in walk run 3) is a
session property, not a writes-only property. The area was re-asked around the real remaining
question — *when* the round's cost enters an already-open grant, given SUGGEST-01 fires only
after companies come back enriched.

| Option | Description | Selected |
|--------|-------------|----------|
| Priced at open, as an allowance | Envelope carries a suggestion allowance; one number, one yes. | ✓ |
| Re-disclosed inside the open grant | Cost shown when about to be spent; second disclosure mid-session. | |
| You decide | Let research check whether the envelope can carry a conditional allowance. | |

**User's choice:** Priced at open, as an allowance.

| Option | Description | Selected |
|--------|-------------|----------|
| Operator sets a cap, default low | Default 2-3, chosen once, shown in the price. | ✓ |
| One per selected role | Cost scales with role count, invisibly at selection time. | |
| Everyone the provider returns | Unbounded; against SUGGEST-05. | |

**User's choice:** Operator sets a cap, default low.

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse, offer a split | Reuse Phase 57 CEILING_OVER + `_affordable_record_count`. | ✓ |
| Refuse only | Discards a split calculation that already works. | |
| Warn and proceed | Contradicts refusal-before-start. | |

**User's choice:** Refuse, offer a split.

| Option | Description | Selected |
|--------|-------------|----------|
| Worst case, stated as a ceiling | Honest about the unknown; matches envelope's over-stating direction. | ✓ |
| Expected case from measured rates | Under-states when coverage is good — wrong direction for a guard. | |
| Both, ceiling emphasised | More informative, more to read at decision time. | |

**User's choice:** Worst case, stated as a ceiling.

---

## Trigger, scope, provenance, dedupe

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-offered after a batch | System raises it; matches "suggests rather than stopping". | ✓ |
| Operator asks explicitly | No unsolicited prompts; dead end whenever forgotten. | |
| Auto-offered, suppressible | More surface, a new settings key. | |

**User's choice:** Auto-offered after a batch.

| Option | Description | Selected |
|--------|-------------|----------|
| Zero associated contacts | Narrowest, cheapest; matches "nobody at it". | ✓ |
| None matching chosen roles | Better buying-committee view; sharply larger candidate set. | |
| Operator picks per round | Flexible; one more choice in a flow meant to be role-selection only. | |

**User's choice:** Zero associated contacts.

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing provenance fields | source=lusha via the existing per-field mechanism. | ✓ |
| Dedicated suggestion property | Queryable; adds to §4.0's documented-but-never-created list. | |
| Only in the run artifact | Zero HubSpot surface; origin invisible in the CRM. | |

**User's choice:** Reuse existing provenance fields.

| Option | Description | Selected |
|--------|-------------|----------|
| The ingest lane's existing match | No new dedupe logic. | |
| Pre-filter before spending | Saves credit; needs to know who they are before the search returns them. | |
| Both | Pre-filter for cost, match lane as backstop. | ✓ |

**User's choice:** Both.

---

## Claude's Discretion

None. Every question was answered explicitly; no "you decide" option was selected in any area.

## Deferred Ideas

- Apollo and ZoomInfo discovery adapters
- No-hits fallback to a second provider
- Two-step discovery (find, confirm, then enrich)
- "No contact matching the chosen roles" as the candidate rule
- A suppression setting for the auto-offer
- A dedicated suggestion-provenance property

## Todos reviewed, not folded

- `2026-08-04-enrichment-throughput-ceiling.md` — matched 0.2 (keyword "phase"); already Phase 63's
- `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — same
