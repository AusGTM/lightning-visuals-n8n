# Phase 62: Suggest the contacts nobody named - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

After a company batch is ingested or enriched, offer the operator people worth enriching at the
companies that have nobody at them — roles chosen **once for the whole batch**, cost priced
**once before it is spent**, and the resulting people **proposed, never auto-created**.

Closes SUGGEST-01, -02, -04, -05. **Amends SUGGEST-03** (see D-62-07).

**Not in this phase:** a second discovery provider (D-62-03), any change to how enrichment or the
write path themselves work, and any new grant lane — one session grant already covers this
(D-62-11).
</domain>

<decisions>
## Implementation Decisions

### Discovery provider

- **D-62-01:** Lusha `/v3/contacts/search-and-enrich` is the discovery provider for this phase.
  It is the **only search endpoint already wired** in the deployed workflow — every other
  provider call is enrich/match on a person you already know (Apollo `/v1/people/match`,
  ZoomInfo `/gtm/data/v1/contacts/enrich`). The adapter is shaped so Apollo/ZoomInfo discovery
  can slot in later without rework. **This deliberately departs from SUGGEST-05's wording**,
  which names Apollo and ZoomInfo as the people-search providers; that wording predates the
  Lusha v3 migration. — **Reversibility:** reversible — a second adapter is additive; nothing
  about the round's shape assumes one provider.

- **D-62-02:** One combined search+enrich call, priced upfront. Discovery is **not** split into
  a find-then-confirm-then-enrich flow. SUGGEST-05's "cost shown before it is spent" is satisfied
  by the upfront estimate (D-62-14), not by a mid-round preview. This matches how Lusha's
  endpoint actually behaves rather than fighting it.

- **D-62-03:** When the provider returns nobody at a company, **record "no candidates found" and
  move on**. A fallback to a second provider is **deferred**, not designed-and-unbuilt — no
  unreachable fallback code ships this phase. (Resolved a conflict in the discussion: a
  no-hits fallback was chosen alongside Lusha-only, which would have had nothing to fall through
  to.)

- **D-62-04:** The candidate company set is **the batch just processed**. Not "every company in
  the portal with no contacts" (unbounded, and includes companies the operator never asked
  about) and not an operator-supplied list. Matches SUGGEST-01's "after companies are ingested or
  enriched" and bounds cost to a set the operator has just seen priced.

### Role vocabulary

- **D-62-05:** Cluster the portal's live `jobtitle` values with **Haiku, cached** — not
  re-clustered per run, and not rule-based normalisation. Free-text jobtitles in a real CRM vary
  in ways keyword rules under-cluster ("Head of Broadcast" vs "Broadcast Manager"), and
  re-clustering every run would make the offered list non-deterministic between rounds. One cheap
  LLM call per refresh. — **Reversibility:** reversible — the cache can be rebuilt by any method
  without changing consumers.

- **D-62-06:** Offer the **top N roles by recurrence**, N fixed and scannable. Directly implements
  SUGGEST-03's "the ones that actually recur".

- **D-62-07:** When the portal is too sparse to evidence a vocabulary, fall back to a generic
  role list **but disclose it plainly as un-evidenced**, so the operator can tell derived roles
  from invented ones.

  **This amends SUGGEST-03**, which reads "not invented and not a generic B2B list". Operator
  decision, taken 2026-09-02 with the conflict stated. **Consequence for phase accounting:**
  Phase 62 closes SUGGEST-01, -02, -04, -05 and **amends** SUGGEST-03 — it does not close
  SUGGEST-01..05 as the ROADMAP currently claims. The requirement text needs updating to permit a
  disclosed generic fallback; the planner must not tick SUGGEST-03 as written.
  — **Reversibility:** costly — SUGGEST-03's text and the ROADMAP's "Closes:" line both change,
  and reverting means removing a fallback operators may have come to rely on.

### How suggestions land

- **D-62-08:** Proposed people enter as **synthesised rows through `extraction.py` / the
  contact-upload ingest lane**. No new lane. This reuses match, held rows and the association
  contract wholesale rather than creating a second implementation of them — the same reasoning
  that made Phase 61-06 Task 1 *refuse* rather than duplicate the association subgraph
  (CLAUDE.md §13.0.1: the rule has exactly ONE operational implementation).
  — **Reversibility:** costly — a later move to a dedicated lane means re-homing the association
  and held-row behaviour this decision deliberately borrows.

- **D-62-09:** A suggested person lands with **whatever identity the provider returns**. If Lusha
  yields an email or `linkedin_url`, the row resolves on a strong key; if only name+company, it
  routes to the weak-key `needs_review` path exactly as any other name-only row does (D-61-03).
  **No special-casing for suggested rows** — they are ordinary rows with an ordinary identity
  story. Note `linkedin_url` became a third identity group in Phase 61-03, so a person with a
  LinkedIn URL and no email is no longer automatically weak.

- **D-62-10:** The **whole round lands as proposals** — no per-person and no per-company
  confirmation. SUGGEST-04's "proposed, never auto-created" is satisfied by the ingest lane's own
  held / `needs_review` gates, not by a second confirmation step. Per-record confirmation would
  reintroduce exactly the scaling complaint SUGGEST-02 exists to remove.

### Trigger and scope of a round

- **D-62-15:** A round is **auto-offered after a batch completes**, unprompted. SUGGEST-01 says
  the system "suggests rather than stopping", which reads as the system raising it rather than
  the operator remembering to ask. The allowance is already priced into the open grant
  (D-62-11), so the offer costs nothing until accepted. No suppression setting this phase.

- **D-62-16:** "A company with no contacts named" means **zero associated contacts** — not "no
  contact matching the chosen roles". Narrowest and cheapest reading, and it matches the
  requirement's own framing: *an enriched company with nobody at it is not a lead*.

- **D-62-17:** Provenance uses the **existing per-field provenance mechanism** (source,
  confidence, verified_at) with `source=lusha`, rather than a new `lv_` property marking a
  contact as suggestion-derived. CLAUDE.md §4.0 records a long list of properties documented but
  never created; this decision deliberately avoids adding to it.

- **D-62-18:** Dedupe is **both** — filter the company's already-known contacts out of role
  targeting before spending, *and* rely on the ingest lane's existing match as the backstop, so a
  person who slips through resolves to an update rather than a create. The pre-filter is the cost
  saving; the match lane is the correctness guarantee.

### Pricing and the cap

- **D-62-11:** **One session grant covers the suggestion round.** Operator correction, 2026-09-02:
  *"a single grant covers the entire session (this would include suggestions)."* Suggestions are
  not a separate spend authority and not a fourth lane. The suggestion cost enters the
  **opening envelope at `plan_grant` as an allowance** (companies × per-company cap) alongside
  the enrichment cost — one number, one yes, nothing re-asked mid-session. Unspent allowance is
  simply not spent.

  Supersedes an earlier framing in this discussion that proposed a separate spend confirmation on
  the grounds that grants authorise writes while discovery only spends credit. That framing was
  wrong for this system: "one grant, one yes" (D-53-05/D-53-06, proved live in walk run 3) is a
  session property, not a writes-only property. — **Reversibility:** one-way — the envelope's
  contents are what the operator agreed to; changing what a grant covers after operators have
  learned the current meaning breaks the consent model Phase 53 established and would require
  re-walking GRANT-01.

- **D-62-12:** **Per-company cap, operator-set, default low (2–3)**, chosen once for the batch and
  shown in the price. Bounds a 300-company round to a predictable number and matches SUGGEST-02's
  pick-once-apply-across-the-batch shape. Not "one per selected role" (cost scales with role count
  in a way the operator does not see at selection time) and not uncapped.

- **D-62-13:** Over ceiling → **reuse Phase 57's `CEILING_OVER` refusal and its existing split
  offer**. `_affordable_record_count` already computes the largest affordable N; nothing new to
  build, and it is behaviour the operator has already seen on write grants.

- **D-62-14:** The estimate is **worst case, stated plainly as a ceiling** that actuals land at or
  under. Lusha bills per contact returned, which is not knowable until the search runs, so
  companies × per-company cap is the honest maximum. This matches `write_grant`'s envelope, which
  already over-states rather than under-states (measured: projected 3 executions for a real
  2-record chunk) — the safe direction for a budget guard.

### Claude's Discretion

None — every question in this discussion was answered explicitly. No "you decide" was selected.

### Reviewed Todos (not folded)

- `2026-08-04-enrichment-throughput-ceiling.md` — matched at 0.2 (keyword "phase" only).
  **Not folded:** already carried by Phase 63 via `resolves_phase: 63`.
- `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — same; already Phase 63's.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/milestones/v1.1-REQUIREMENTS.md` § SUGGEST — SUGGEST-01..05 verbatim. **Read
  D-62-07 first**: SUGGEST-03 is amended by this phase, not closed as written.
- `.planning/milestones/v1.1-ROADMAP.md` § Phase 62 — full scope statement, dependencies,
  and the numbering history (this was an orphaned "59").
- `.planning/ROADMAP.md` § Phase 62 — the active roadmap entry.

### The grant and its cost model
- `operator-claude-plugin/scripts/write_grant.py` — `envelope()` (line 409) builds the cost
  disclosure; `plan_grant()` (892) prices before the yes; `open_grant()` (1122);
  `authorize_send()` (1337) narrows per send; `_affordable_record_count()` (746) is the split
  offer D-62-13 reuses. **Note the live CR-01 fix**: `figures["chunk_ceiling"]` carries the int
  cap, `figures["ceiling"]` the verdict dict — do not re-collide them.
- `.planning/phases/53-operator-openable-write-grant/53-VERIFICATION.md` — GRANT-01's basis and
  the "one grant, one yes" property D-62-11 depends on.
- `.planning/phases/57-ceilings-refusal-before-start-and-post-run-proof/` — `CEILING_OVER`
  refusal-before-start, which D-62-13 reuses rather than reimplements.

### The ingest lane suggestions land through
- `operator-claude-plugin/scripts/extraction.py` — the synthesised-row entry point (D-62-08).
- `config/column_mapping.yaml` § `required_identity` — the three identity groups
  (`email` / `firstname+lastname+company` / `linkedin_url`) that decide whether a suggested
  person resolves or lands `needs_review` (D-62-09).
- `n8n/code/columnMap.js` — the JS mirror of the above; pinned equal by
  `tests/n8n/columnMapIdentityParity.test.mjs` and `columnMapAliasParity.test.mjs`. **Both move
  together or the preview lies about the backend.**
- `CLAUDE.md` §13.0.1 — the contact→company association contract, and why it has exactly one
  implementation (the reason D-62-08 reuses rather than forks).
- `operator-claude-plugin/scripts/held_queue.py` — Phase 61's held-row queue.

### Provider contract
- `docs/LUSHA-V3-CONTRACT.md` — the contract of record for Lusha v3.
- `n8n/code/lushaRequest.js` — `lushaContactBody` accepts any subset of identity keys;
  `linkedin_url` maps to `contact.linkedinUrl`.

### The role-vocabulary pattern
- `scripts/inventory_org_type_values.py` — the named pattern for a read-only, paged live
  inventory of a property's distinct values (SUGGEST-03 cites it explicitly). Read-only, env-gated,
  `_has_credentials()` skip-to-exit-0, portal guard.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`/v3/contacts/search-and-enrich`** — already wired, authenticated and metered in
  `wf_enrichment_cloud.json`. The only discovery-shaped provider call in the system.
- **`write_grant.envelope()` / `_affordable_record_count()`** — the cost disclosure and the
  split offer, both reused verbatim (D-62-13, D-62-14).
- **`extraction.py` + the contact-upload ingest lane** — match, held rows, association
  (D-62-08).
- **`scripts/inventory_org_type_values.py`** — the read-only live-inventory idiom for sampling
  `jobtitle` (D-62-05).

### Established Patterns
- **One implementation of the association rule.** Phase 61-06 Task 1 refused to duplicate it and
  downgraded creates to `review` instead. D-62-08 follows that precedent.
- **Refuse rather than guess.** The system's standing preference; note D-62-07 deliberately
  departs from it for the sparse-portal case, with disclosure as the mitigation.
- **Envelope over-states rather than under-states.** Measured on a real 2-record chunk. D-62-14
  keeps that direction.
- **Provider adapters are enrich-shaped, not search-shaped.** This phase introduces the first
  genuine discovery call; do not assume the existing adapter contract fits.

### Integration Points
- **`plan_grant`'s envelope** gains a suggestion allowance (D-62-11) — the one place the operator
  agrees to the round's cost.
- **Batch completion** is where the round is offered (D-62-15).
- **`extraction.py`'s row intake** is where suggested people enter (D-62-08).
- **Per-field provenance stamping** is where `source=lusha` is recorded (D-62-17).

### Landmines
- **`contactResearch.js` is NOT reusable here.** It enriches an existing contact's
  jobtitle/seniority; it does not discover people. Named because its filename invites the
  mistake.
- **Apollo's key on this portal is not a master key** — `usage_stats` returns 403 and the
  credit check degrades to null. Relevant if Apollo discovery is added later (D-62-01).
- **A full Lusha sweep already exceeds the credit balance** (measured 2026-07-30). A 300-company
  round at 1 credit/contact is a real budget event, which is why D-62-12 caps per company.
- **Never hand-edit `n8n/wf_*.json`** — regenerate via `scripts/build_cloud_workflows.py`.

</code_context>

<specifics>
## Specific Ideas

- **"A single grant covers the entire session (this would include suggestions)."** — operator,
  2026-09-02. The load-bearing correction of this discussion; see D-62-11.
- The sparse-portal generic list must be **visibly labelled as un-evidenced** — the operator
  needs to tell CRM-derived roles from invented ones at a glance (D-62-07).

</specifics>

<deferred>
## Deferred Ideas

- **Apollo and ZoomInfo discovery adapters** — the requirement names them; this phase ships
  Lusha only with the adapter shaped for later addition (D-62-01).
- **No-hits fallback to a second provider** — unreachable until a second discovery adapter
  exists (D-62-03).
- **Two-step discovery (find, confirm, then enrich)** — rejected for this phase in favour of
  Lusha's combined call (D-62-02); revisit if a provider with a separable search appears.
- **"No contact matching the chosen roles" as the candidate rule** — a genuinely more useful
  buying-committee view, deferred as materially more expensive per round (D-62-16).
- **A suppression setting for the auto-offer** — deferred as unneeded surface until an operator
  finds the prompt noisy (D-62-15).
- **A dedicated suggestion-provenance property** — deferred in favour of existing provenance
  fields (D-62-17).

</deferred>

---

*Phase: 62-suggest-the-contacts-nobody-named*
*Context gathered: 2026-09-02*
