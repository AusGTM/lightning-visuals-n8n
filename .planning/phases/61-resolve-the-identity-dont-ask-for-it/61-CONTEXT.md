# Phase 61 — Resolve the identity, don't ask for it — Context

**Gathered:** 2026-08-30
**Status:** Ready for planning
**Trigger:** walk run 4 failed (`53-WALK-RECORD-3.md` FINDING D)

<domain>
## Phase Boundary

An input carrying a **strong identity key** resolves through **match, then enrich**, without the
operator being asked for fields the backend does not need.

Concretely: a contact given only a LinkedIn URL (or only an email) proceeds — HubSpot match on
that key, and where unmatched, licensed-waterfall enrichment on that same key — with the result
**proposed with provenance** for operator confirmation.

**Closes:** INPUT-05.

</domain>

<decisions>
## Operator rulings — LOCKED (2026-08-30)

These are recorded verbatim-in-substance because the root cause of this phase existing is a
ruling that was given verbally and never written down. Do not re-litigate them.

### D-61-01 — Best effort is the default, not the exception
> *"we are prioritising speed and efficiency, and relying on the plugin to propose best effort
> completion using the services n8n gives it in the backend"*

The operator explicitly rejects a posture where **"every ingestion creates an exception"**. A
refusal for missing identity is correct only when **no** strong key is present. Asking the
operator for a field the backend does not need is the defect this phase removes.

### D-61-02 — No-invention is NOT loosened
The verbatim no-invention sentence in `extraction.md` stays exactly as written, and stays on the
do-not-simplify list. Nothing in this phase invents a value.

The distinction this phase draws, which had been collapsed into one rule:
- **Inventing** — producing a field value from nothing, or from a slug/URL/prior knowledge.
  Still forbidden. STRUCT-04 unchanged.
- **Resolving** — the operator supplies a key, a licensed provider returns a sourced value, the
  operator confirms it. Never was invention, and must stop being treated as such.

A searched-and-sourced value carries provenance; an invented one cannot. That is the test.

### D-61-03 — Strong keys only
In scope: **LinkedIn URL, email.** Both are already strong match keys in
`n8n/code/resolveIdentity.js`.

Out of scope: name-only rows. They keep routing through the existing `name_company` weak-key →
`needs_review` path. A wrongly matched person is worse than an unmatched one, and this phase must
not turn a weak key into a confident write.

### D-61-04 — The waterfall, not web search, for a person
The operator asked for "web search". For a **person** that is the weaker instrument:
`claude_web` research is company-oriented (`object_type: companies` throughout
`src/web_research.py`). The mechanism here is the **licensed provider waterfall keyed on
`linkedin_url`** — already built, already paid for, more reliable.

This is a deliberate substitution of mechanism, not a narrowing of the operator's intent. If the
waterfall misses, that is when a research fallback becomes worth discussing — not before.

### D-61-05 — CORRECTED 2026-08-30: front-end AND a small backend change, together

**The original text of this decision was wrong and is retained below, struck, because the
correction is the single most important thing a planner must not miss.**

> ~~**This is a front-end contract fix.** No new backend capability is required. Both operations
> the plugin refused already exist: HubSpot match by `linkedin_url`
> (`n8n/code/resolveIdentity.js:76-78`) and Lusha v3 enrich by LinkedIn URL
> (`n8n/code/lushaRequest.js:79-91`).~~

**What the research actually found** (`61-RESEARCH.md`):

| Capability | Reality | Work needed |
| --- | --- | --- |
| Lusha v3 enrich by LinkedIn URL | **Real and live.** `lushaRequest.js:79-98` accepts a body carrying `linkedinUrl` alone | None |
| HubSpot match by `linkedin_url` | **DEAD ON THE LIVE PATH.** `resolveIdentity.js:76-90`'s linkedin branch is real code that nothing reaches: the bulk-CSV ingest lane's `ADAPT_SEARCH_RESULTS` builds `searchResultsByKey.email` ONLY, and the match lane's `matchProposal.js::laneOf()` never reads `linkedin_url` — its HubSpot Search node filters `email EQ` only | **New match lane + search node** |
| The plugin's own match client | Filters the key out before it is ever sent — `enrichment.py:71`'s frozen `MATCH_LOOKUP_KEYS = (email, firstname, lastname, company)` | **Un-freeze the tuple** |

**The trap this closes.** Fixing only the front-end identity gate **reproduces the failure in a
new shape**: the row passes extraction, then dead-ends permanently in the `unchecked` /
"could not look" bucket, because nothing downstream can search by that key. That is a worse
outcome than today's honest refusal — it fails later, more quietly, after the operator thinks it
worked.

**Both halves land together or the phase does not deliver.**

**How this error was made, recorded so it is not repeated.** The original D-61-05 was written by
reading `resolveIdentity.js` and asserting the deployed behaviour from it, without tracing
whether any live lane reaches that branch. That is the same documented-vs-actual mistake this
phase exists to fix. On this repo, **source containing a capability is not evidence the deployed
path uses it** — the same lesson as CLAUDE.md's as-built delta blocks and
`n8n-stored-vs-running-content` (a stored read-back proves nothing).

### D-61-06 — The identity rule is duplicated in five places; they move in lockstep
Research found the "email OR firstname+lastname+company" rule restated in **five** independent
sites — two YAML configs, `extraction.py`'s Python gate plus its hardcoded reason string,
`columnMap.js`'s hand-written JS reimplementation, and `extraction.md`'s prose — with **no test
pinning parity between the YAML and the JS**. Any change edits all five in one commit, and the
phase should leave a parity test behind so the next divergence fails loudly rather than silently.

### Claude's Discretion
- Where the contract change lands (`extraction.md`'s identity rule, the ingest lane's gate, or
  both) — follow the evidence.
- **Unverified, must be checked before it is relied on:** research flagged a possible live
  property-name discrepancy, `linkedin_url` vs `lv_linkedin_url`, and could NOT verify it (no
  live calls permitted). Re-list the live portal before writing to or filtering on either name.
  CLAUDE.md §4.0's rule applies: treat §4/§5's tables as roadmap, not inventory.
- Whether the proposal surface reuses D-59-08's existing resolvable-proposal mechanism (it
  already proposes for a missing company) rather than adding a second one. **Strongly prefer
  reuse** — a second proposal mechanism is the kind of duplication this codebase keeps paying for.
- Cost disclosure shape for an enrich the operator did not explicitly request per-row.

</decisions>

<specifics>
## What must not break

- **Provider credit is real money.** Enriching on a wrong key spends for nothing. The gate before
  spending stays; this phase changes what counts as *enough identity to proceed*, never whether
  the operator is asked before credit is spent.
- **`extraction.md`'s no-invention sentence** — do-not-simplify list, D-61-02.
- **The `name_company` weak-key → `needs_review` route** — D-61-03.
- **The per-send armed-window narrowing** and every write-safety gate — untouched; this phase is
  upstream of any write.
- **`operator-claude-plugin/tests/test_skill_sequence_coverage.py`** — if a documented `SKILL.md`
  python block changes, its call tuple changes and the census set-equality fails. Expect to
  update the registry deliberately, and note that `GRANDFATHERED_UNCOVERED` is now empty with
  `MAX_GRANDFATHERED = 0`: any new documented sequence needs a real composition test, not a
  grandfather entry.

## The failure to reproduce

`https://www.linkedin.com/in/robert-cavallucci-14698741/`, no other fields. Today the plugin
stops and asks for a company. After this phase it should match-or-enrich on the URL and propose
what it found.

LinkedIn itself returns **HTTP 999** to the fetch tool (anti-bot). That is expected and must stay
handled as a tool-level refusal — the fix is not to get the page, it is to stop needing it.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD-3.md` — FINDING D, the
  evidence this phase exists.
- `.planning/milestones/v1.1-REQUIREMENTS.md` § INPUT-05.
- `n8n/code/resolveIdentity.js`, `n8n/code/lushaRequest.js` — the machinery already present.
- `operator-claude-plugin/skills/contact-upload/extraction.md` — the contract to change, and the
  no-invention sentence to leave alone.
- `docs/LUSHA-V3-CONTRACT.md` §3 — the confirmed identity properties.

</canonical_refs>
