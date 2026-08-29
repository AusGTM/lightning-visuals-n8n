# Phase 61 — Autonomous batch runs — Context

**Renamed 2026-08-30.** Was "Resolve the identity, don't ask for it" — that name described the
TRACER, not the phase. The phase is autonomy (absorbing Phases 55 and 56); identity resolution
is the slice that proves it end to end.

**Gathered:** 2026-08-30
**Status:** Ready for planning
**Trigger:** walk run 4 failed (`53-WALK-RECORD-3.md` FINDING D)

<domain>
## Phase Boundary — RE-SCOPED 2026-08-30 after the walk concluded

**The original boundary (one identity key) is superseded. It is kept at the bottom of this
section because it is now the phase's TRACER, not its scope.**

### What this phase is now

**An operator hands over a batch and gets it back done.** Research, enrichment and ingestion run
**autonomously**; the operator gives consent once for the batch, not once per row; rows the
system is not confident about are **held and collected**, never guessed and never blocking; and
the run is not bounded by a synchronous response window.

**Closes:** INPUT-05, RUN-01, RUN-02, RUN-03, RUN-04, AFTER-02.

### Why it grew — FINDING F

Walk run 4 concluded 2026-08-30 with every individual refusal **correct** and the composition
unusable. Operator's diagnosis, verbatim:

> *"there is no self assessment of confidence, and therefore no autonomy in workflow, it requires
> an operator to walk through each step every single time, if an operator has hundreds of
> contacts to ingest, this means they will need to go through hundreds of research steps, and
> approval gates. That gets away from the point of doing this altogether."*

And the load-bearing argument:

> *"the 3 separate backend services, which DO DO the research enrichment and ingestion ALREADY,
> but they clobber each other - if we keep the non-clobbering aspect while removing the
> autonomous research, enrichment and ingestion parts then this makes a worse system"*

**The plugin's whole reason to exist is non-clobbering.** The three backend services already
perform the work. Keep the non-clobbering and remove the autonomy, and the result is worse than
using the services raw. That is the bar this phase is measured against — not "does a record
land", but "did the operator get a batch back without walking it".

### What was folded in (D-61-08)

This phase absorbs **Phase 55 (async run: submit, poll, resume)** and **Phase 56 (the unattended
pair pipeline)**. Operator decision 2026-08-30: the halting problem and the throughput ceiling
are one piece of work, because both stand between the operator and an unattended run of
hundreds. Neither is useful alone — autonomy that still holds a connection open for 100s per
2-record chunk is not autonomy, and async runs that still ask a question per row are not
unattended.

**Phase 57 (ceilings, refusal-before-start, post-run proof) is NOT folded in** and remains
separate. D-53-02 is explicit that a grant's computed ceiling is *disclosure, not constraint* —
and with autonomy landing here, 57's protective work matters more, not less. **Phase 56's
original gate stands: 56's first live run is gated on 57's ceiling work.** That gate now applies
to this phase.

### The original boundary — now the tracer

An input carrying a **strong identity key** resolves through **match, then enrich**, without the
operator being asked for fields the backend does not need: a contact given only a LinkedIn URL
(or only an email) proceeds — HubSpot match on that key, and where unmatched, licensed-waterfall
enrichment on that same key — with the result **proposed with provenance**.

This is the right tracer because it is the exact row that failed the walk, and it exercises
identity resolution, the waterfall, the proposal surface and the write path in one pass.

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

### D-61-07 — Low confidence HOLDS the row; it never blocks the batch and never guesses
**Operator ruling, 2026-08-30.** The autonomy policy, and the single decision that bounds how bad
a bad run can get:

- **Confident rows proceed autonomously.** No question, no gate, no per-row approval.
- **Unconfident rows are HELD** — not guessed, not written, not asked about mid-run.
- **The batch always finishes.** A held row never stops the rows behind it.
- **Held rows collect into ONE review queue**, cleared in a single pass at the end.

300 contacts becomes one run plus one review, not 300 conversations. This is the shape that
delivers autonomy **while preserving non-clobbering** — the operator explicitly kept the
non-clobbering ("in a non-clobbering way"), so the merge policy is NOT what is being relaxed.

**What IS being relaxed is approval friction and per-row research halts. What is NOT being
relaxed:** the non-clobber merge policy, the write-safety gates, or the post-run account of what
was written. With no HubSpot rollback and ~700 live records, those three are what make autonomy
survivable rather than reckless — they are the reason this can be granted at all.

The phase needs a real **confidence signal** to hang this on. Today there is none — that absence
IS FINDING F. Deciding what confidence means (match-key strength, provider agreement, judge
verdict, or a composite) is core phase work, not a detail.

### D-61-08 — Scope absorbs Phases 55 and 56; 57 stays separate and stays gating
See the Phase Boundary above. Phase 55's spike-first warning carries over verbatim and is the
phase's biggest unknown: **n8n Cloud's execution model, not our code, decides what is possible**
for submit/poll/resume. Spike it before planning tasks around it. Run-state location (n8n static
data, a HubSpot object, or an external store) is an open design question with a different
failure mode per option when n8n restarts mid-run.

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
