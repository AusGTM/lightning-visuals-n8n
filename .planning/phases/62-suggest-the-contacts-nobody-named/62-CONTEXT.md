# Phase 62: Suggest the contacts nobody named - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

After a company batch is ingested or enriched, offer the operator people worth enriching at the
companies that have nobody at them — roles chosen **once for the whole batch**, cost priced
**once before it is spent**, and the resulting people **proposed, never auto-created**.

Closes SUGGEST-01, -02, -04, -05. **Amends SUGGEST-03** (see D-62-07).

**Not in this phase:** any people-search / prospecting vendor API (see the re-scope below), any
change to how enrichment or the write path themselves work, and any new grant lane — one session
grant already covers this (D-62-11).

## RE-SCOPE, 2026-09-02 — read before D-62-01..03

The original D-62-01/02 assumed Lusha `/v3/contacts/search-and-enrich` could find people by
company + title. **It cannot, and this was verified twice.** Its request body is
`{"contacts":[{firstName, lastName, companyName, companyDomain, email, linkedinUrl}]}` — a 1:1
resolution of a person you can *already name*. "Search" there means "find this person's contact
details", not "find people matching criteria". `jobTitle` appears in `docs/LUSHA-V3-CONTRACT.md`
**only as a response field** (`results[i].jobTitle.title`), never as a request filter.

Discovery-by-title lives in Lusha's **Prospecting API**, which this project excludes by standing
decision — `.planning/workstreams/milestone/REQUIREMENTS.md:47`: *"Lusha Prospecting / Lookalikes
/ Tables / Decision Makers APIs — net-new acquisition surfaces, not enrichment of existing CRM
records."* That is a **class** exclusion: Apollo `mixed_people/search` and ZoomInfo contact-search
are the same class. Swapping vendors does not escape it.

**Operator decision, 2026-09-02: re-scope discovery to the existing web-research lane.**

**The two stages compose, and that is the whole design.** Web research is good at *naming* people
from a company's own public pages and bad at contact details; the provider waterfall is the
reverse — `search-and-enrich` requires exactly `firstName + lastName + companyName`, which is what
research produces. So:

```
company with zero contacts
  -> web research the company's own pages  (names + job titles, no email)
  -> filter to the operator's chosen roles
  -> named person = firstname+lastname+company = identity group 2 (STRONG)
  -> existing enrich waterfall fills email/phone
  -> synthesised rows -> extraction.py -> match lane -> proposals
```

Precedent, not theory: **UAT 2.4 passed on `0.10.0`** against `https://gctc.com.au/board-of-directors/`
— ordinary fetch returned 0 people, the ladder's rung 1 returned **all 9 directors**, provenance
named the URL actually fetched, and no email was invented for anyone. That is this phase's
discovery step, already built and already in scope.

**15 of the 18 decisions survive unchanged.** Only D-62-01, D-62-02 and D-62-03 are rewritten;
D-62-09, D-62-11, D-62-14 and D-62-17 are amended in place where the cost or provenance unit
changed. Every other decision stands as taken.

### Where the round runs (settled 2026-09-02, third revision)

**In the plugin, as an operator-attended sitting** — not on a schedule, not in the backend.
`web_fetch` exists only on the conversational side; the backend has `web_search` alone.

**This does NOT weaken any SUGGEST requirement, and the phase accounting is unchanged.** The
"300-company unattended round" framing was this document's invention, never the requirement's.
Re-reading the source:

- **SUGGEST-02** asks that the suggestion be *"categorical, not per-record — the operator picks
  roles once and the system applies them across the batch."* A sitting satisfies this exactly:
  roles are chosen once, Claude applies them across the whole company list in one pass. The
  requirement constrains **how the decision is shaped**, not whether a human is present.
- **SUGGEST-01, -04, -05** say nothing about unattended operation. SUGGEST-05 (*"cost shown
  before it is spent"*) is arguably better served with an operator present.

So Phase 62 still **closes SUGGEST-01, -02, -04, -05 and amends only SUGGEST-03** (D-62-07) —
the accounting D-62-07 already stated. No second requirement is amended.

**It also makes the grant coherent rather than strained.** D-62-11 puts the suggestion allowance
in the session grant; the grant *is* a conversational-session concept. Round and grant now live
in the same place instead of the round running somewhere the grant cannot reach.
</domain>

<decisions>
## Implementation Decisions

### Discovery mechanism  *(rewritten 2026-09-02 — see RE-SCOPE above)*

- **D-62-01 (rev 3, 2026-09-02):** Discovery runs **in the plugin (the conversational side),
  sourced from the company's own sitemap**, using the ladder that already exists.

  **Where the fetch runs, and why it is not the backend.** `web_fetch` — the tool that actually
  retrieves a candidate URL — **does not exist anywhere in the n8n backend**. The backend research
  node declares `web_search` only (`web_search_tool_result` blocks in `webResearch.js`). The
  plugin side has `web_fetch`, and it is where UAT 2.4's proven flow already runs.

  **Sitemap-first, and the machinery is already built** — `url_fallback.py` is a pure
  string-building module with *"no HTTP client, no scraping library, no headless browser, no I/O
  of any kind"*:
  - `plan_ladder(url)` already emits `/sitemap.xml` (rung 3) and `/wp-sitemap.xml` (rung 4)
  - `filter_candidates()` is documented as *"the guard on sitemap-derived candidates
    SPECIFICALLY"* — sitemap URLs come out of fetched content, which is attacker-influenceable,
    so nothing is fetched without passing scheme → host → budget checks in that order
  - `MAX_FOLLOWUP_FETCHES = 5` is sized for exactly this: *"four constructed candidates against
    this cap leaves exactly one fetch for a sitemap-derived profile page"*
  - The crawler line is already drawn: *"A sitemap can list thousands of URLs; an uncapped ladder
    is a crawler, and a crawler is explicitly out of scope"*

  **Do not build a conventional-path guesser** (`/about`, `/team`, `/leadership`). It was
  considered and rejected: the sitemap is the site's own declaration of its pages, so reading it
  is evidence where a path list is inference. The ladder already prefers it.

  — **Reversibility:** reversible — the ladder is shared, so a backend `web_fetch` node could
  host the same discovery later without changing the sitemap logic.

  *Superseded:* rev 1 named Lusha `/v3/contacts/search-and-enrich` (cannot filter by title).
  rev 2 said "the existing web-research lane" without distinguishing the three mechanisms that
  phrase covers — see the research amendment; only the plugin-side URL adapter can name people.

- **D-62-02 (rev 2):** **Two stages, one price.** Research names people (no email); the existing
  enrich waterfall then fills contact details for those named people. This is not the
  "find-then-confirm-then-enrich" flow rejected in discussion — there is still **no operator
  confirmation between the stages** (D-62-10 stands). It is one automated round with two
  mechanisms, priced as one decision up front (D-62-14).

  The composition is the point: `search-and-enrich` needs exactly `firstName + lastName +
  companyName`, which is precisely what research yields. The constraint that made Lusha useless
  for discovery is what makes it correct for stage 2.

- **D-62-03 (rev 2):** When research finds nobody at a company, **record "no candidates found"
  and move on**. Unchanged in effect from rev 1, and the fallback question is now moot — there is
  no second discovery provider to fall through to, by design. The ladder's own give-up path
  (`give_up_message`) already reports why it stopped; surface that reason rather than a bare
  count.

  **Do not escalate past a refusal.** If the ladder gives up, or a page is unreachable, that is a
  result to report — not a prompt to try a search engine. Phase 53's walk run 4 recorded the
  principle verbatim: *"escalating past a refusal turns a fence into a suggestion."*

  > **AMENDMENT — quick task 260904-5sd (operator, 2026-09-04). Narrow, not wholesale.**
  >
  > D-5sd-04 amends this decision by SEPARATING two endings it conflated. Only one of them
  > gained a fallback:
  >
  > | Ending | Behaviour after the amendment |
  > | --- | --- |
  > | The site REFUSED — an error code, or a page whose content is an access-denied notice | **Terminates exactly as before.** No search, no second source. Unchanged. |
  > | The crawl COMPLETED and found no persons | **A committed-allowlist search fallback fires** (D-5sd-04). |
  > | The crawl exhausted its own fetch budget | **The fallback fires** (D-5sd-06) — a budget we imposed on ourselves is not a fence the site put up. |
  >
  > **Phase 53's principle SURVIVES INTACT and is not weakened.** *"Escalating past a refusal
  > turns a fence into a suggestion"* still governs the refusal case, and a refusal is still
  > terminal. Overturning the principle wholesale was offered to the operator and **declined**.
  > What changed is that "the ladder found nobody" is now recognised as absence of information
  > rather than as a refusal — those were never the same thing, and D-62-03 rev 2 treated them
  > as one.
  >
  > The distinction is a real, fail-closed, testable branch, not a comment:
  > `search_fallback.eligible_after_ladder(attempts)` reads a closed `disposition` vocabulary
  > (`empty` / `cap_exhausted` / `refused`) recorded on each attempt, and an absent or
  > unrecognised disposition is INELIGIBLE, so a transcription gap can never silently open the
  > search path. Sources are restricted to a committed ranked allowlist (D-5sd-02), and only
  > tier 1 (the company's own host) and tier 2 (LinkedIn) can ever produce a sendable row —
  > a tier-3 industry source is collected and shown but always held (D-5sd-05).

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

- **D-62-09 (amended 2026-09-02):** A suggested person lands with **whatever identity the round
  produces**. **No special-casing for suggested rows** — they are ordinary rows with an ordinary
  identity story.

  What changed under the re-scope, and it is good news: web research reliably yields
  `firstname + lastname + company`, which is **identity group 2 — a strong key**. So a
  research-discovered person resolves through the match lane rather than landing weak, even
  before the stage-2 enrichment adds an email. A name-ONLY row (no company) still routes to the
  weak-key `needs_review` path per D-61-03. `linkedin_url` remains a third identity group
  (Phase 61-03) for anyone whose page links their profile.

  **Planner note:** do not assume "no email ⇒ needs_review". UAT 2.4's 9 directors had no email
  and the walk correctly predicted `needs_review` — but that was a raw extraction with no
  stage-2 enrichment behind it. This phase's stage 2 exists precisely to close that gap.

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

- **D-62-17 (amended 2026-09-02):** Provenance uses the **existing per-field provenance
  mechanism**, not a new `lv_` property marking a contact as suggestion-derived. CLAUDE.md §4.0
  records a long list of properties documented but never created; this deliberately avoids adding
  to it.

  **Two corrections the research surfaced — the planner must not take CLAUDE.md §6/§8 at face
  value here:**
  1. The live mechanism is the **Phase 15 `lv_contact_enrichment_provenance` JSON blob**
     (`n8n/code/mergeContacts.js`), not the per-field `<field>_source` property family §6/§8
     describe. Those §6/§8 property names are largely in the never-created list.
  2. Its `source` is **hardcoded to `"csv"`** at one narrow call site — the `MERGE_CONTACTS`
     constant in `scripts/build_cloud_workflows.py`. A suggestion round's rows are not CSV rows,
     so that hardcode must be parameterised rather than worked around downstream.

  Under the re-scope the value is **`claude_web` for stage-1 fields (name, jobtitle) and the
  provider's own name for stage-2 fields (email, phone)** — a suggested contact legitimately
  carries mixed provenance, which is what a per-field mechanism is for. Research also flagged
  `extraction.py`'s `resolutions.source` as a **separate, closed vocabulary** that is easy to
  conflate with this — check whether it needs a new member before assuming it does.

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

- **D-62-14 (amended 2026-09-02):** The estimate is **worst case, stated plainly as a ceiling**
  that actuals land at or under. This matches `write_grant`'s envelope, which already over-states
  rather than under-states (measured: projected 3 executions for a real 2-record chunk) — the
  safe direction for a budget guard.

  **The re-scope gives the round TWO cost components, and both belong in the one ceiling:**

  | Stage | Unit | Bound |
  |---|---|---|
  | 1 — discovery | page fetches per company | `url_fallback.MAX_FOLLOWUP_FETCHES` = **5**, whole-ladder, already enforced by `filter_candidates`' budget check |
  | 2 — enrich named people | provider credits (Lusha ~1/contact measured) | companies × per-company cap (D-62-12) |

  **Two fetch/search budgets exist and are easy to conflate** (research flagged this):
  `url_fallback.MAX_FOLLOWUP_FETCHES` (page fetches, the one that bounds stage 1) and
  `WEB_RESEARCH_MAX_SEARCHES` (the backend node's `web_search` budget). Both default to 5 and
  they are **different axes**. Stage 1 runs in the plugin, so it is the former.

  No isolated research-only Anthropic cost has ever been measured in this repo — the one rate key
  that would carry it (`company_domain_research`) ships `null` by design. Do not invent a
  per-company dollar figure; bound stage 1 by **fetch count**, which is real and enforced.

  Quote them as one number the operator agrees to, with the split visible. **Do not present the
  provider-credit figure alone** — that was the honest number when discovery was a vendor call
  and is now only half the round. Stage 2's count is bounded by what stage 1 actually found, so
  its ceiling is genuinely a ceiling: fewer people discovered means fewer credits spent, never
  more.

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

### Discovery (stage 1) — the web-research lane
- `operator-claude-plugin/scripts/url_fallback.py` — the host-bound escalation ladder
  (`plan_ladder`, `filter_candidates`, `give_up_message`). This is what returned all 9 directors
  in UAT 2.4. Host-bound **in code**, not by judgement — do not loosen it.
- `operator-claude-plugin/UAT.md` § 2.4 — the passing walk that is this stage's precedent, and
  its provenance discipline (day-job employers present in the bios were deliberately NOT used).
- `src/web_research.py` — the research adapter. **Company-oriented throughout**; read the
  landmine note before assuming it finds people.

### Enrichment (stage 2) — provider contract
- `docs/LUSHA-V3-CONTRACT.md` — the contract of record for Lusha v3. **Read §3 first**: the
  request body is a named-identity resolution, which is why it is stage 2 and not stage 1.
- `n8n/code/lushaRequest.js` — `lushaContactBody` accepts any subset of identity keys;
  `linkedin_url` maps to `contact.linkedinUrl`.
- `.planning/workstreams/milestone/REQUIREMENTS.md:47` — the standing exclusion of
  Prospecting / Lookalikes / Tables / Decision Makers APIs. **Binding on this phase.**

### Provenance
- `n8n/code/mergeContacts.js` — the live `lv_contact_enrichment_provenance` blob (Phase 15).
- `scripts/build_cloud_workflows.py` § `MERGE_CONTACTS` — where `source` is hardcoded `"csv"`.

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
- **Lusha `search-and-enrich` is NOT a discovery endpoint.** It resolves a person you can already
  name. Verified twice against `docs/LUSHA-V3-CONTRACT.md`; `jobTitle` is a response field only.
  The endpoint's NAME is the trap — it cost this phase a full discussion round.
- **People-search/prospecting APIs are excluded by standing decision** across all vendors
  (`.planning/workstreams/milestone/REQUIREMENTS.md:47`). Do not plan a task that calls one.
- **`contactResearch.js` is NOT reusable for discovery either.** It enriches an existing
  contact's jobtitle/seniority. Named because its filename invites the mistake.
- **`src/web_research.py` is company-oriented throughout** (`object_type: companies`). Phase 53's
  FINDING D analysis concluded web search is the weaker instrument for a *person*. That is why
  discovery here reads the company's own pages via the host-bound ladder rather than searching
  the open web for individuals.
- **Do not escalate past a refusal** — `url_fallback.py` is host-bound in code, not by judgement.
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
