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

### D-61-05 — This is a front-end contract fix
No new backend capability is required. Both operations the plugin refused already exist:

| Capability | Evidence | Needs a company? |
| --- | --- | --- |
| HubSpot match by `linkedin_url` | `n8n/code/resolveIdentity.js:76-78` — strong key, same tier as email | No |
| Lusha v3 enrich by LinkedIn URL | `n8n/code/lushaRequest.js:79-91` — `lushaContactBody` accepts any subset; `linkedinUrl` at line 83; only a wholly empty set skips | No |

The blocker is the ingest/extraction front-end rule requiring email OR
firstname+lastname+company before proceeding.

### Claude's Discretion
- Where the contract change lands (`extraction.md`'s identity rule, the ingest lane's gate, or
  both) — follow the evidence.
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
