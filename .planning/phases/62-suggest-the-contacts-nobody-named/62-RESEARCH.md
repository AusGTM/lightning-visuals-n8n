# Phase 62: Suggest the contacts nobody named - Research

**Researched:** 2026-09-02
**Amended:** 2026-09-02 — re-scope amendment (discovery mechanism rewritten; see
`§ RE-SCOPE AMENDMENT` below, inserted after the original Summary). The original research pass's
finding that vendor people-search is out of scope stands and is load-bearing; only the
DISCOVERY-MECHANISM sections that assumed Lusha as the discovery provider are superseded, marked
inline where they occur rather than deleted.
**Domain:** Web-research-driven contact discovery (operator-claude-plugin's URL-fetch escalation
ladder, `web_search`-backed research nodes), layered onto the existing HubSpot enrichment/ingest
pipeline (n8n Cloud + operator-claude-plugin)
**Confidence:** MEDIUM — the ingest-lane and grant-lane mechanics are HIGH confidence (live-probed
contracts, read source) and are UNCHANGED by the re-scope. The re-scoped discovery premise
(D-62-01/02/03 rev 2) is itself a NEW finding of this amendment pass: HIGH confidence that the
named mechanism (`url_fallback.py` + the INGEST-05 URL adapter) is real and does what UAT 2.4
showed, but also HIGH confidence that it has no programmatic or batch entry point — which again
forces a premise question back to the operator before PLAN.md can be written faithfully to
D-62-04/11/12/14/15 as currently worded.

<user_constraints>
## User Constraints (from CONTEXT.md)

**RE-SCOPE, 2026-09-02 (read first):** the original D-62-01/02 assumed Lusha
`/v3/contacts/search-and-enrich` could find people by company + title. It cannot (verified twice,
see the now-superseded `§ Research Priority 1` below). Discovery-by-title lives only in Lusha's
Prospecting API, excluded by standing decision
(`.planning/workstreams/milestone/REQUIREMENTS.md:47`) as a **class** exclusion covering every
vendor's people-search/prospecting surface. Operator decision, 2026-09-02: re-scope discovery to
the **existing web-research lane** reading a company's own public pages, composed with the
existing enrich waterfall as stage 2. Precedent: UAT 2.4 (`0.10.0`, `gctc.com.au/board-of-directors/`)
returned all 9 directors via the escalation ladder. **15 of 18 decisions survive unchanged; only
D-62-01/02/03 are rewritten, and D-62-09/11/14/17 are amended in place.**

### Locked Decisions

**Discovery mechanism (rewritten rev 2):** D-62-01 rev 2 (discovery is the existing web-research
lane reading the company's own public pages via `operator-claude-plugin/scripts/url_fallback.py`'s
host-bound escalation ladder — not a vendor people-search API; superseded rev 1 named Lusha
`search-and-enrich`) · D-62-02 rev 2 (two stages, one price: research names people with no email;
the existing enrich waterfall fills contact details for those named people; still no operator
confirmation between the two stages, D-62-10 stands) · D-62-03 rev 2 (no candidates found is
recorded and the round moves on; the ladder's own give-up message supplies the reason; do not
escalate past a refusal — Phase 53 walk run 4: "escalating past a refusal turns a fence into a
suggestion") · D-62-04 (candidate company set is the batch just processed, not the whole portal and
not an operator-supplied list — unchanged).

**Role vocabulary:** D-62-05 (cluster live `jobtitle` values with Haiku, cached, not re-clustered
per run) · D-62-06 (offer the top N roles by recurrence, N fixed) · D-62-07 (sparse-portal fallback
to a disclosed, un-evidenced generic role list — **amends SUGGEST-03**, does not close it as
written) — unchanged by the re-scope.

**How suggestions land:** D-62-08 (proposed people enter as synthesised rows through
`extraction.py`/the contact-upload ingest lane — no new lane, unchanged) · D-62-09 (amended
2026-09-02: a suggested person lands with whatever identity the ROUND produces, no special-casing —
under the re-scope, web research reliably yields firstname+lastname+company, identity group 2, a
STRONG key, so a research-discovered person resolves through match rather than landing weak even
before stage-2 enrichment adds an email; a name-only row with no company still routes to weak-key
`needs_review` per D-61-03) · D-62-10 (the whole round lands as proposals, no per-person/per-company
confirmation — unchanged).

**Trigger and scope:** D-62-15 (a round is auto-offered after a batch completes, unprompted, no
suppression setting this phase) · D-62-16 ("no contacts named" means zero associated contacts, not
"no contact matching the chosen roles") · D-62-17 (amended 2026-09-02: provenance uses the existing
`lv_contact_enrichment_provenance` JSON blob — CLAUDE.md §6/§8's flat per-field properties are
largely never-created; `mergeContacts.js`'s `opts.source` hook is hardcoded `"csv"` at ONE call site,
`MERGE_CONTACTS` in `scripts/build_cloud_workflows.py`, which must be parameterised; under the
re-scope the value is `claude_web` for stage-1 fields (name, jobtitle) and the provider's own name
for stage-2 fields (email, phone) — a suggested contact legitimately carries MIXED provenance;
`extraction.py`'s `resolutions.source` is flagged as a separate, closed vocabulary easy to conflate
with this) · D-62-18 (dedupe is both a pre-filter and reliance on the ingest lane's existing match as
backstop — unchanged).

**Pricing and the cap:** D-62-11 (amended 2026-09-02: one session grant covers the ENTIRE session
including suggestions — operator's own words, "a single grant covers the entire session (this would
include suggestions)" — supersedes an earlier framing that proposed a separate spend confirmation on
the grounds that grants authorise writes while discovery only spends credit; the suggestion cost
enters `plan_grant`'s opening envelope as an allowance, one number, one yes) · D-62-12 (per-company
cap, operator-set, default low 2-3, chosen once for the batch — unchanged) · D-62-13 (over ceiling
reuses Phase 57's `CEILING_OVER` refusal and split offer — unchanged) · D-62-14 (amended 2026-09-02:
the estimate is worst case, stated plainly as a ceiling; the re-scope gives the round TWO cost
components in ONE ceiling — stage 1 research: Anthropic tokens + `web_search` uses, bound by
companies × `WEB_RESEARCH_MAX_SEARCHES` (5) plus the ladder's own fetch cap; stage 2 enrich: provider
credits, bound by companies × the D-62-12 per-company cap, itself bounded by what stage 1 actually
found — do not present the provider-credit figure alone, that was honest when discovery was a vendor
call and is now only half the round).

Full text and reversibility notes: `.planning/phases/62-suggest-the-contacts-nobody-named/62-CONTEXT.md`.

### Claude's Discretion

None — every question in the discussion was answered explicitly. No "you decide" was selected.

### Deferred Ideas (OUT OF SCOPE)

- Apollo and ZoomInfo discovery adapters — the requirement names them; this phase ships Lusha only
  for stage 2 enrichment, adapter shaped for later addition (D-62-01).
- No-hits fallback to a second provider — unreachable until a second discovery adapter exists
  (D-62-03).
- Two-step discovery with an operator confirmation between stages — rejected; the two stages compose
  in one automated round, still no per-stage confirmation (D-62-02 rev 2).
- "No contact matching the chosen roles" as the candidate rule — deferred as materially more
  expensive per round (D-62-16).
- A suppression setting for the auto-offer — deferred as unneeded surface until an operator finds
  the prompt noisy (D-62-15).
- A dedicated suggestion-provenance property — deferred in favour of existing provenance fields
  (D-62-17).
- A second discovery provider generally, any vendor people-search/prospecting API from any vendor,
  any change to how enrichment or the write path themselves work, and any new grant lane — per the
  Phase Boundary in CONTEXT.md.

**Note on this amendment pass:** `§ RE-SCOPE AMENDMENT` below (inserted after the original Summary)
reports that D-62-01/02/03 rev 2, as literally written, name a real, working mechanism
(`url_fallback.py` + INGEST-05, proven by UAT 2.4) that nonetheless has no programmatic or batch
entry point — a different premise gap from the original pass's, one layer down. This is surfaced as
a finding for the operator to re-decide, per this agent's mandate — it is not this document
overriding the lock.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SUGGEST-01 | After companies are ingested/enriched with no contacts named, the system suggests contacts worth enriching rather than stopping. | D-62-15's client-side "batch complete" hook (`run_state.py`'s `done` verdict) names where the unprompted offer fires; D-62-16's zero-associated-contacts check names the read. Both researched below. |
| SUGGEST-02 | For a bulk company list, the suggestion is categorical (roles picked once, applied across the batch), not per-record. | D-62-06/D-62-12 (top-N roles, per-company cap chosen once) reuse `write_grant`'s existing pick-once-apply-across-batch shape — researched under "the rest of the priorities." |
| SUGGEST-03 | **AMENDED, not closed** — see D-62-07 in CONTEXT.md. The role vocabulary is derived from the portal's own `jobtitle` values, with a disclosed generic fallback permitted when the portal is too sparse. Do not tick as originally written ("not invented and not a generic B2B list" — no exception). | `scripts/inventory_org_type_values.py`'s read-only paged-inventory idiom, confirmed reusable for `jobtitle` on contacts; the Haiku-clustering step (D-62-05) is new work with no in-repo precedent. Researched below. |
| SUGGEST-04 | Suggested contacts are proposed, never auto-created — they land through the existing pre-ingest path (match, held rows, association contract). | Priority 3 (this document) confirms `extraction.py`'s real entry point (`validate()` on an in-memory dict) accepts synthesised rows with the identity contract unchanged — no special-casing needed for D-62-08/09/10. |
| SUGGEST-05 | The cost of a suggestion round is shown before it is spent — priced as one decision, not discovered mid-run. | D-62-11/13/14 reuse `write_grant.envelope()`/`plan_grant()`/`_affordable_record_count()` verbatim — confirmed live-in-repo under "the rest of the priorities." **Caveat:** the per-company cap arithmetic these decisions price assumes a search-shaped provider call; Priority 1's finding means this pricing must be re-derived once Open Question 1 is resolved. |

**Amendment note (2026-09-02):** SUGGEST-01/SUGGEST-05's support above was written for the original
Lusha-discovery premise. Under the re-scope, SUGGEST-01's "the batch just processed" and SUGGEST-05's
"priced as one decision" both depend on Open Question 1's amended sub-question (operator-attended vs.
backend-automated) — see `§ RE-SCOPE AMENDMENT` above. SUGGEST-02/03/04's support is unaffected: role
vocabulary, the ingest-lane landing contract, and the proposed-not-created guarantee do not depend on
which discovery mechanism supplies the rows.

</phase_requirements>

## Summary

The three research-gate unknowns are resolved. The headline: **D-62-01/D-62-02 are unimplementable
as written.** The Lusha endpoint this repo has wired (`POST /v3/contacts/search-and-enrich`) is a
1:1 known-identity **resolution/enrichment** call — you already have to know the person's name,
email, or LinkedIn URL to call it. It has no mechanism to return "the people at company X who hold
title Y" when no such person is named. That capability is a genuinely different Lusha product line
(the **Prospecting API**, `docs.lusha.com/apis/openapi/prospecting-search-and-enrich`), which this
project's own standing decision declares **out of scope** (`.planning/workstreams/milestone/REQUIREMENTS.md`
§ Out of Scope: "Lusha Prospecting / Lookalikes / Tables / Decision Makers APIs — net-new
acquisition surfaces, not enrichment of existing CRM records"; `20-RESEARCH.md` Pitfall 1 names
exactly this conflation as a known trap). This is not a coding problem the planner can route around
inside Phase 62 — it is a premise problem the operator needs to re-decide.

Everything downstream of that premise researches cleanly: the ingest lane
(`extraction.py`/`column_mapping.yaml`/`n8n/code/columnMap.js`) accepts a programmatically
synthesised row with no file-upload assumption baked into its real entry point (`validate()`
takes a plain in-memory dict); the grant/ceiling machinery
(`write_grant.envelope()`/`plan_grant()`/`_affordable_record_count()`) already carries everything
D-62-11/12/13/14 ask for, needing only an added allowance line, not new mechanism; and the
per-field provenance D-62-17 wants to reuse is real and reusable, but is NOT the flat
`{field}_source` properties CLAUDE.md §6/§8 describe — those were never built (§4.0's running
theme). The as-built mechanism is the Phase 15 `lv_contact_enrichment_provenance` JSON blob,
written by `mergeContacts.js`, which already accepts a `source` override — it is hardcoded to
`"csv"` at the one call site (`scripts/build_cloud_workflows.py`'s `MERGE_CONTACTS` constant,
consumed by both `build_local()` and `build_cloud()`), a small, well-scoped change.

**Primary recommendation (original pass, now historical):** Before writing PLAN.md, take the
D-62-01/D-62-02 finding back to the operator with the two forward options below (§ Open Questions).
**The operator did exactly this and re-scoped discovery** — see `§ RE-SCOPE AMENDMENT` immediately
below for what changed and what this amendment pass found about the NEW mechanism. Everything else
in this document — the ingest-lane reuse contract, the grant/ceiling reuse, the provenance
mechanism, the role-vocabulary sampling idiom — was ready for planning regardless of which
discovery option was picked, and remains ready now; only the discovery-mechanism sections
(originally Priority 1, and Priority 2's framing) are superseded.

---

## RE-SCOPE AMENDMENT (2026-09-02)

**Read this section before planning. It supersedes `§ Research Priority 1` below (kept, marked
superseded, not deleted — its finding that vendor discovery is closed remains load-bearing) and
answers CONTEXT.md's re-scoped D-62-01/02/03 (rev 2).**

### Headline

**The mechanism D-62-01 rev 2 names is real, and UAT 2.4's result is real — but it is a
per-conversation, operator-in-the-loop tool, not a batch/backend capability, and nothing in this
repo currently drives it across a company list unattended.** This is a different premise problem
from the original pass's (which was "the named provider cannot do this at all"); here, the named
mechanism CAN name people from a page, but only when a human supplies the starting page URL and
approves every escalation step, one company at a time, inside a live conversation. D-62-04's
"candidate company set is the batch just processed" and D-62-12's "a 300-company round" (CONTEXT.md's
own words) describe a scale this mechanism was never built to run at without an operator personally
handling each company's starting URL.

Three genuinely different "web research" mechanisms exist in this repo, easy to conflate under one
phrase ("the existing web-research lane") because CONTEXT.md's canonical refs and this section both
use that phrase loosely. Naming them precisely is the first job of this amendment:

| Mechanism | Where | Invocation | Input | Output | Can it name people? |
|---|---|---|---|---|---|
| (a) URL-fetch escalation ladder | `operator-claude-plugin/scripts/url_fallback.py` + `extraction.md`'s INGEST-05 adapter | Conversational only — Claude's own `web_fetch` tool, driven by prose instructions in a live plugin skill session | An operator-pasted starting URL; every escalation candidate operator-approved | Canonical `extraction.py` rows (firstname/lastname/jobtitle/company), written by Claude's own reading | **Yes — this is what UAT 2.4 proved** |
| (b) Company web research | `src/web_research.py`, `n8n/code/webResearch.js`, the "Claude Web Research HTTP Request" node (companies branch, `wf_enrichment_cloud.json`) | Programmatic — one Anthropic Messages API call per company, `web_search` server tool, deployed in n8n Cloud | Company name + domain | Company ICP fields only (`lv_org_type`, `lv_produces_content`, ...) | **No — no slot for a person's name anywhere in its schema** |
| (c) Contact web research | `n8n/code/contactResearch.js`, the "Contact Web Research HTTP node" (contacts branch, same workflow) | Programmatic — same shape as (b) | An ALREADY-NAMED contact (firstName/lastName/company) | `jobtitle` + `seniority` for that one named person | **No — consumes a name, never produces one** |

Only (a) can do what D-62-01 rev 2 asks. Only (b)/(c) are backend-batchable. No mechanism is both.

### Amendment Research Priority 1 — Invocation and batchability of the web-research lane

`[VERIFIED: operator-claude-plugin/scripts/url_fallback.py, read in full this session]` The module
is a pure string-builder — `plan_ladder`, `same_host`, `filter_candidates`, `give_up_message` — with
a module docstring stating plainly: *"`web_fetch` is a model-invoked SERVER tool — this module does
not and cannot call it. Everything here builds strings and nothing else: no HTTP client, no
scraping library, no headless browser, no I/O of any kind."* Confirmed by grep across the whole repo
(`grep -rn "url_fallback"`): its **only** caller anywhere is
`operator-claude-plugin/skills/contact-upload/extraction.md`'s prose instructions for the INGEST-05
URL adapter. There is no Python function that imports `url_fallback` and loops it over a list of
companies — the `__main__` CLI exists to be invoked by Claude, mid-conversation, one URL at a time.

`[VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:215-287, read in full this
session]` The INGEST-05 adapter's own words make the consent boundary explicit, not incidental:

> "The operator pastes the URL. That is also what makes the fetch possible at all — the tool only
> fetches a URL that has already appeared in the conversation; you cannot construct one yourself."

> "Fetch only the candidates the operator approves, in the order shown, stopping at the first one
> that yields people."

Every escalation rung — not just the starting URL — requires an operator decision before Claude may
fetch it. `MAX_FOLLOWUP_FETCHES = 5` bounds the WHOLE ladder (not per rung, not per company); UAT
2.4 spent 1 of 5. `filter_candidates()` takes `already_fetched` as a caller-tracked integer — nothing
in the module persists a budget across companies or across turns; Claude in-conversation is the only
thing keeping count.

`[VERIFIED: operator-claude-plugin/skills/backend-sweep/SKILL.md, read in full this session]` The
plugin's ONLY cron-invocable skill is `backend-sweep`, and it is read-only by explicit contract:
*"This skill reads. It changes nothing, ever... nothing this skill reaches has a code path to a
mutation."* There is no unattended path in this plugin that could paste a URL, approve a candidate,
or drive `web_fetch` across a company list without a human present turn-by-turn. (Project memory,
not independently re-verified this session, corroborates from the other direction: headless
`claude -p` invocations do not authenticate under cron and fail silently — the sweep design already
had to work around exactly this gap for a read-only skill.)

`[VERIFIED: n8n/code/webResearch.js, read in full this session]` Mechanism (b)'s entire validation
contract (`validateResearchOutput`, `toProviderResult`) operates on `data.lv_org_type`,
`data.lv_produces_content`, `data.lv_content_type`, `data.lv_country_region_normalized` — company
ICP fields exclusively. No field for a person's name exists anywhere in the schema, the system
prompt (`RESEARCH_SYSTEM` in `src/web_research.py`, and its n8n-inlined twin,
`scripts/build_cloud_workflows.py`'s companies "Build Research Request" node), or the request body.

`[VERIFIED: n8n/code/contactResearch.js, read in full this session]` Mechanism (c)'s output is
hard-limited: `const CONTACT_RESEARCH_FIELDS = ["jobtitle", "seniority"];` — and its own request
body (`scripts/build_cloud_workflows.py`'s contacts "Build Research Request" node) requires
`id.contactName || row.contactName || [id.firstName, id.lastName].filter(Boolean).join(" ")` — a
name must already be present to call it. Its system prompt tells the model to *"prefer the
company's own team/about/leadership page,"* confirming the underlying `web_search` capability CAN
locate such a page — but this deployed node never surfaces anyone beyond the one person it was told
to research. `[VERIFIED, quoted verbatim, corroborating this exact landmine]`
`operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (read in full this session) states it
explicitly for a related case: *"that adapter is company-oriented (`object_type: companies`
throughout `src/web_research.py`) and would be answering a different question about a different
kind of subject entirely."*

### Amendment Research Priority 2 — Company → page URL (the highest-risk unknown, as flagged)

`[VERIFIED — negative result]` No helper anywhere in `operator-claude-plugin/scripts/` or `src/`
turns a bare company `website`/`domain` into a candidate team/board/leadership page URL. Grepped for
`leadership`, `/team`, `board-of-directors`, `/about-us`, `guess.*url`, `candidate.*page` — zero
source-code hits. `plan_ladder()` itself needs an already-specific page URL to build from (it derives
WordPress-REST and sitemap rungs from the PASTED URL's own path slug and host) — it has no rung that
starts from a homepage and proposes a subpage.

UAT 2.4's precedent gave Claude the exact page — `https://gctc.com.au/board-of-directors/` — supplied
directly by the human operator, not derived from anything HubSpot stores. A company's `website`
property (CLAUDE.md §18.4 lists it among the standard company fetch fields, `[CITED]`) is at best a
homepage domain; resolving from there to whichever specific subpage lists the leadership team
(`/board-of-directors/`, `/about/team`, `/leadership`, `/who-we-are`, or nothing published at all) is
a distinct, unaddressed problem.

The closest built precedent for the ADJACENT, EASIER problem — finding a company's own domain from
its name, not finding a subpage of a known domain — is explicitly, deliberately UNBUILT.
`[VERIFIED: operator-claude-plugin/scripts/company_domain.py:154-175, read this session]`
`needs_research()`'s own docstring: *"Pure -- no I/O, no network, no research call. This only names
the rows; pricing them is `cost_guard.research_line`'s job, and actually researching them is neither
function's job."* Its priced rate key, `company_domain_research`
(`operator-claude-plugin/config/cost_rates.json`), is `null`: *"No measured rate exists for backend
domain research (Phase 58, D-58-08/09)... must be measured on its own before it is disclosed as
anything but unmeasured -- do not scale another rate to fill this in."* If the strictly easier
sibling problem (domain-for-a-name) has no wired research call after being explicitly scoped for it
in Phase 58, the harder problem (subpage-for-a-known-domain, then people-on-that-subpage) has none
either — confirmed absent by the negative grep above, not merely by analogy.

**Conclusion:** there is no reliable, already-built path from a HubSpot company record to a
candidate team/board/leadership page URL. Absent that, D-62-04's "the batch just processed" cannot
become a set of stage-1 starting points without a human supplying one per company.

### Amendment Research Priority 3 — the stage-1 → stage-2 handoff

Confirmed unchanged and clean: under mechanism (a), Claude reads page content directly and writes
`firstname`/`lastname`/`jobtitle`/`company` straight into the canonical `extraction.py` row shape
the ORIGINAL Priority 3 below already fully documents (record shape, `canonical_props()`, the three
identity groups) — that finding stands entirely, independent of which discovery mechanism supplies
the rows.

`[VERIFIED — negative result]` The "per-row splitter added in plugin 0.9.0, amendment 6a"
(`name_split.py`, `propose_split`/`apply_name_split`) is scoped to the CSV/XLSX "Full Name" COLUMN
adapter (INGEST-02) only — grepped for `name_split`/`splitter`/`amendment 6a` across
`extraction.md`: zero hits outside the CSV-header context (UAT 2.2's "Maria Jane Santos"
middle-name-vs-surname case). The URL adapter (INGEST-05) never invokes it and has no comparable
gap: Claude supplies firstname/lastname by its own reading judgment while extracting the row, the
same way it does for the pasted-freeform-text adapter (INGEST-01) — UAT 2.4's 9 directors are the
live proof this already works without a splitter.

`[VERIFIED — negative result]` No existing composition of "research → enrich" for PEOPLE exists to
copy. `enrich-before-ingest/SKILL.md` (read in full this session) is the closest analogous
composition (match → enrichment waterfall → preview → ingest) and its own text explicitly REFUSES to
substitute web research for a missing waterfall match on a person — the exact quote above
("a different kind of subject entirely"). Phase 62's stage-1 → stage-2 composition is genuinely new
wiring. What IS directly reusable from `enrich-before-ingest` for STAGE 2 specifically, once stage
1's rows exist: `enrichment.resolve_providers`, `chunking.dispatch_plan`/`chunking.plan_chunks`,
`preingest.merge_enriched`, `confidence.assess`, `held_queue` — the entire waterfall-dispatch-and-hold
machinery, unmodified.

### Amendment Research Priority 4 — cost

`[VERIFIED: src/web_research.py:128; scripts/build_cloud_workflows.py generated node bodies (both
companies and contacts "Build Research Request" nodes), read this session]` `WEB_RESEARCH_MAX_SEARCHES`
is read via `os.getenv("WEB_RESEARCH_MAX_SEARCHES", "5")` in the local Python oracle, and is a
hardcoded literal `5` (`const WEB_RESEARCH_MAX_SEARCHES = 5;`) inside both generated n8n Code node
bodies deployed in `wf_enrichment_cloud.json`. It bounds `web_search` tool `max_uses` per Messages API
call — **a different budget axis from `url_fallback.py`'s `MAX_FOLLOWUP_FETCHES`** (`web_fetch`
escalation rungs). Both happen to default to 5; do not conflate them when deriving D-62-14's ceiling
— a plan that writes "5 fetches" when it means "5 searches," or vice versa, prices the wrong axis.

`[VERIFIED: operator-claude-plugin/config/cost_rates.json, read in full this session]` No isolated
"cost of one research-only call" has been measured anywhere in this repo. `anthropic_usd_per_record`
= `0.068624` USD/record is explicitly the ALL-IN chain — *"full provider + Haiku research + Sonnet
judge chain"* — measured on Phase 22 canary executions 332/337, not isolated to a `web_search` call.
The one rate key that would isolate a research-only call, `company_domain_research`, ships `null`
with the file's own instruction not to substitute another rate for it. That instruction applies with
equal force here: **do not scale `anthropic_usd_per_record` to price a Phase 62 discovery call** —
price it as a new, separately-measured rate key, shipped `null` until a live probe measures it,
following this file's own established convention.

Tangential but material: the same file's judge-model rate entries are tagged *"measured, time-bound
— intro pricing expires 2026-08-31, re-check after that date"* — today is 2026-09-02. Not this
phase's defect to fix, but any Phase 62 ceiling should not silently inherit that now-expired figure
without flagging it.

Lusha stage-2 credit rate is unchanged from the original pass and stands:
`lusha_contacts_first_time_enrich` = 1 credit/contact `[VERIFIED: cost_rates.json;
docs/LUSHA-V3-CONTRACT.md §7-8]`.

**A directly reusable two-component pricing SHAPE already exists, from a sibling feature.**
`[VERIFIED: operator-claude-plugin/scripts/cost_guard.py:115-215, read in full this session]`
`estimate_batch()` prices the provider-credit component; `research_line()` prices a SEPARATE,
honestly-tri-state (`no_rows`/`unmeasured`/`measured`) domain-research-cost line for the exact
"never render an unmeasured rate as $0" discipline D-62-14 asks for — built for D-58-08/09, a
different call on a different subject. Recommend the planner parallel `research_line()`'s shape for
the Phase 62 stage-1 cost line rather than inventing a new one, with a NEW rate key (not
`company_domain_research`, which prices a different research call) shipped `null` until measured.

### Amendment Research Priority 5 — the role filter / matcher

`[VERIFIED — negative result]` No clustering or classification module exists for `jobtitle` values
anywhere in `scripts/`, `operator-claude-plugin/scripts/`, or `n8n/code/` — grepped `cluster` across
all three, no relevant hit. The only comparable pattern in the codebase, `ORG_TYPE_SYNONYMS`
(`n8n/code/taxonomy.generated.js`), is a keyword-literal map, not clustering, and is exactly the
pattern D-62-05's own rationale rejects ("keyword rules under-cluster").

This is genuinely TWO matching problems, and CONTEXT.md's D-62-05/06 address only the first:

1. **Offline (D-62-05/06's scope):** cluster the WHOLE portal's existing `jobtitle` values into
   families, cached, to build the operator-facing "top N roles" menu.
2. **Online, per suggestion round (unaddressed by any D-62 decision):** classify a NEWLY DISCOVERED,
   freshly-extracted page title — a string that may never have appeared in the CRM before — against
   the family list the operator already chose from (1).

Nothing in CONTEXT.md speaks to (2) at all. **Recommendation for the planner:** design (2) as a
single classification call — "given this jobtitle string and this fixed family list, which family
(or none)" — reusing (1)'s cached family definitions as the classification target, rather than a
second independent clustering pipeline; mirror the one-vocabulary-two-access-modes pattern
`taxonomy.py`/`taxonomy.generated.js` already use for `lv_org_type` (one definitions block, consumed
by both a build-time and a runtime path). Flag it in the plan as a distinct module from (1)'s
clustering script — clustering and classification are different operations even sharing a
vocabulary, and conflating them risks exactly the "second implementation of the same rule" this
priority was asked to watch for.

### Amendment Research Priority 6 — does the re-scoped design work as written?

**No, not as an automated "round" at the scale CONTEXT.md's own prose describes ("a 300-company
round," "auto-offered... unprompted," priced "as one number the operator agrees to").** The chain
the re-scope specifies —

```
company with zero contacts -> web research the company's own pages (names + job titles, no email)
  -> filter to chosen roles -> named person = strong identity -> enrich waterfall fills email/phone
  -> extraction.py -> match lane -> proposals
```

— names mechanism (a) for its first arrow, and (a):

1. needs a human to supply the STARTING page URL per company (Priority 2: no derivation path
   exists), and
2. needs a human to APPROVE every escalation candidate (Priority 1, quoted verbatim), and
3. has no programmatic entry point and no unattended/cron path (Priority 1).

None of this is a defect — it is Phase 35's deliberate consent-boundary design, and matches the same
"escalating past a refusal turns a fence into a suggestion" principle CONTEXT.md itself cites for
D-62-03. But "the existing web-research lane," as CONTEXT.md's canonical refs and precedent both use
the phrase, names a proven-but-manual, per-company, human-attended tool — not the automated,
backend-batchable capability D-62-04/11/12/14/15's language implies. The mechanisms that ARE
backend-batchable, (b) and (c), cannot name a person at all.

**This is not this phase's authority to resolve** — the same posture the original research pass
took, which the operator then used to produce this very re-scope. Two honest ways forward for the
next `/gsd-discuss-phase` pass:

**(a) Scope the round to operator attention, not company count.** Accept that a "round" is bounded
by how many companies a human is willing to hand a starting URL to, in one sitting — plausibly
single-to-low-double-digits, not 300 — and that D-62-02/14's "one price, quoted once" covers stage
2's provider-credit cost only, since stage 1 spends no provider/Anthropic budget but spends operator
TIME proportional to N, which nothing in D-62-11..15 currently discloses or bounds.

**(b) Build a genuinely programmatic stage-1 discovery step.** Extend the `web_search`-backed
pattern (c) already gestures at ("prefer the company's own team/about/leadership page") into a NEW
research schema that returns a LIST of `{name, jobtitle, evidence_url}` per company, query-driven
from company name/domain rather than an operator-pasted URL — real, scoped, new work (a new n8n Code
node + HTTP request + validator, mirroring `webResearch.js`/`contactResearch.js`'s existing shape),
not "already built" as CONTEXT.md's RE-SCOPE section frames UAT 2.4. It needs its own consent-boundary
decision (it removes the operator-paste/approve gate Phase 35 deliberately built) and its own
currently-unmeasured cost line, following `company_domain_research`'s "ship null until probed"
convention.

**Recommendation:** return this finding to the operator (checkpoint or `/gsd-discuss-phase`
re-entry) before planning proceeds — the same move the original pass made for the vendor-discovery
premise, one layer down.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Role vocabulary derivation (cluster live `jobtitle` values) | API/Backend (offline script) | — | `scripts/inventory_org_type_values.py`-style read-only paged HubSpot inventory + one cached Haiku call; not a runtime n8n node |
| Company candidate-set selection ("the batch just processed") | Client (operator-claude-plugin) | API/Backend | The batch is already in the client's `run_state`/manifest; no new HubSpot query needed |
| "Zero associated contacts" check | API/Backend (HubSpot v4 associations read) | Client | One read per company; cheapest as a batched read alongside the batch's own company fetch |
| Discovery call (person search by company+role) | **BLOCKED — no tier currently owns this** | — | See Summary: the wired provider has no discovery mode; this is the premise gap |
| Suggested-row intake (match, held rows, association) | API/Backend (n8n Cloud ingest lane) | Client (extraction.py pre-flight) | D-62-08: reuse `extraction.py` + `wf_contact_ingest_cloud`, the ONE implementation of the association rule (CLAUDE.md §13.0.1) |
| Cost disclosure and grant | Client (operator-claude-plugin `write_grant.py`) | — | D-62-11: one session-grant envelope, not a new lane |
| Per-field provenance stamping | API/Backend (n8n `Merge Contacts` node -> `lv_contact_enrichment_provenance`) | — | D-62-17: existing Phase 15 mechanism, `source` override needed |

## Package Legitimacy Audit

Not applicable — this phase installs no new external packages. Every dependency (Lusha API,
`extraction.py`, `write_grant.py`, `mergeContacts.js`) already exists in the codebase.

---

## Research Priority 1 — Does Lusha `/v3/contacts/search-and-enrich` support a title/role filter?

> **SUPERSEDED as a discovery-mechanism recommendation — see `§ RE-SCOPE AMENDMENT` above.** The
> operator has already re-scoped discovery away from Lusha entirely (D-62-01 rev 2). **Kept in
> full, not deleted: the underlying finding — Lusha's Enrichment API cannot discover an unnamed
> person by title, and vendor people-search/prospecting is out of scope by standing decision — is
> exactly why the re-scope happened, and remains load-bearing** for stage 2 (this endpoint is still
> the correct, in-scope tool for RESOLVING a person research has already named) and for ruling out
> any future temptation to route discovery back through a vendor API.

**Verdict: NO. `[VERIFIED: docs/LUSHA-V3-CONTRACT.md §3, live-probed 2026-07-30 and 2026-08-30]`**

The contract of record for this endpoint — every claim in it confirmed against a live
`api.lusha.com` response, not inferred — enumerates the **complete, closed** set of accepted
identity properties for the contacts lane's request body:

> `firstName`, `lastName`, `companyName`, `companyDomain`, `email`, `linkedinUrl` — and nothing
> else. An unrecognised property 400s outright: `contacts.0.property notARealProperty should not
> exist` (§3, "Every attempted property, accepted or rejected" table). The synthetic v2-style
> `contactId` index key is also rejected the same way.

No `title`/`jobTitle`/`role` key was ever probed and accepted. This is an **absence**, not a
tested-and-refused parameter — per the provenance rules, that keeps the specific claim "there is
no title parameter" one notch short of `[VERIFIED]` on its own. Three converging lines of evidence
close the gap to a practical certainty, but the fully rigorous confirmation needs one more probe
(named below, not run — this research is read-only):

1. **`[VERIFIED]` The response shape is 1:1, not 1:many.** §4 of the contract: "v3 is a flat
   `results` array, positionally aligned with the request's `contacts` array (single-item in this
   waterfall's usage pattern...)." One identity object in, at most one result out. A company+role
   discovery call structurally needs the opposite shape — one company in, N candidate people out —
   which this endpoint's own documented response contract cannot produce regardless of what
   request fields it accepted.
2. **`[CITED: docs/LUSHA-V3-CONTRACT.md; 20-RESEARCH.md Pitfall 1]`** This project's own prior
   research (Phase 20, the v3 migration) already named and rejected exactly this conflation:
   *"Conflating the Enrichment API with the Prospecting API... `POST /prospecting/contact/enrich`
   ...LOOKS structurally similar and shares vocabulary (`reveal`, `canReveal`, `contactId`) with
   the Enrichment API, but is a CLAUDE.md-declared **out-of-scope** surface."* The standing
   `.planning/workstreams/milestone/REQUIREMENTS.md` § Out of Scope entry: *"Lusha Prospecting /
   Lookalikes / Tables / Decision Makers APIs — net-new acquisition surfaces, not enrichment of
   existing CRM records."*
3. **`[CITED: WebSearch, docs.lusha.com]`** Lusha's own public documentation places job
   title/seniority/department filtering under a distinct **Prospecting API** product
   (`docs.lusha.com/apis/openapi/prospecting-search-and-enrich`, with its own `Search Contacts`
   sub-page), while the **Contact Search and Enrich** page (`docs.lusha.com/apis/openapi/contact-search-and-enrich`
   — the endpoint this repo actually calls) is described as resolving "identifiers like email,
   LinkedIn URL, name, company name, or domain" — an identity-resolution description, not a filter
   description. (`docs.lusha.com` is a JS-rendered SPA that WebFetch could not render byte-exact;
   this is WebSearch-snippet corroboration, not a fetched page — hence `[CITED]`, not `[VERIFIED]`,
   consistent with how `LUSHA-V3-CONTRACT.md` itself treats WebSearch-only findings.)

**The falsification step that would make this fully `[VERIFIED]`, named for whoever runs the next
live probe (not run in this session — read-only research):** extend
`scripts/probe_lusha_v3.py`'s P9 idiom (a probe that costs 0 credits because a 400/`NOT_FOUND`
never bills) with two more shapes:
- `{"contacts":[{"companyName":"X","companyDomain":"x.example","jobTitle":"CEO"}]}` — expect a 400
  `property jobTitle should not exist`, which would close this to `[VERIFIED]`. A 200 would be the
  refutation this whole finding rests on not having happened.
- `{"contacts":[{"companyName":"X","companyDomain":"x.example"}]}` (company identity only, no
  person name) — never probed either. Expect either a 400 (company-only is not a valid contact
  identity) or a 200 with `resultsReturned: 1` for a SPECIFIC arbitrary match (confirming 1:1, not
  bulk) rather than a list.

**Consequence for D-62-01/D-62-02:** both decisions assume this endpoint "can take company + title
and return people." It cannot take a title at all, and even company-only would return at most one
arbitrarily-matched result, not a candidate list. D-62-01's own reversibility note calls itself
"reversible — a second adapter is additive," but the deeper problem isn't "which adapter" — it's
that **no currently-in-scope adapter can discover an unnamed person by role**, because the one
provider explicitly scoped for this phase does not offer that capability at all, and the provider
line that does (Prospecting) is explicitly out of scope by a decision this phase does not have
authority to reverse on its own (see § Open Questions for the two ways forward).

---

## Research Priority 2 — Credit behaviour when a search returns fewer people than the cap

> **Framing superseded — see `§ RE-SCOPE AMENDMENT` above and its Priority 4.** This section's
> "for the endpoint actually wired" premise (Lusha `search-and-enrich` as discovery) no longer
> applies; discovery is now the web-research lane, not a Lusha call, so there is no "search returns
> fewer than the cap" case on this endpoint to worry about at all. **The billing facts below still
> stand and are exactly what prices D-62-14's stage-2 component** (Lusha resolving a
> research-named person is still a real, in-scope call) — kept for that reason, not as a discovery
> analysis.

**Verdict: for the endpoint actually wired, this question is largely moot — but the underlying
billing facts are answered and still needed for D-62-14's estimate wording, and the real open
question moves to the Prospecting API's unknown pricing.**

`[VERIFIED: docs/LUSHA-V3-CONTRACT.md §4, §9]` The contacts `search-and-enrich` endpoint bills
**per request item, not per field revealed, and not on a miss**:

- A match: `billing.creditsCharged: 1` (first-time identity), `0` for a stored-`id` re-enrich
  (§8, 4/4 live calls confirmed free).
- A miss: `billing: {"creditsCharged": 0, "resultsReturned": 0}` inside a `200` — "Every-item error,
  outer 200" — a `results[i].error.code: "NOT_FOUND"` per §9, not a request-level failure and not
  billed.
- Selective `reveal[]` field count does not change the charge (§6, A3 REFUTED) — cost is driven by
  identity-search-vs-stored-id, never by which fields are asked for.

Because this endpoint is called **once per known identity, never once per (company, cap)**, there
is no "search returns fewer than the cap" case to measure for it — you cannot ask it for "up to 3
people at company X"; you can only ask it to resolve a specific person you already named. D-62-14's
"worst case = companies × per-company cap" framing is the right *direction* (over-state, never
under-state, matching the `write_grant` envelope's measured behaviour: a real 2-record chunk
projected 3 executions, never fewer) — but the number it should be pricing is presently unclear,
because it depends entirely on which discovery mechanism the operator picks under § Open
Questions.

**If the operator reopens the Prospecting API decision** (Priority 1's option a): that endpoint's
billing model is **`[ASSUMED]` — genuinely unprobed by this repo.** Lusha's public docs distinguish
"search" credits (returning a preview list) from "reveal" credits (unlocking a specific person's
contact fields) for that product line, structurally similar to but not necessarily priced like the
Enrichment API's two-step flow measured in §7 of the contract. This would need its own live-probe
session (mirroring `probe_lusha_v3.py`'s pattern) before any per-company cap could be priced with
the same confidence D-62-14 currently claims for the wrong endpoint.

## Research Priority 3 — Can `extraction.py` accept synthesised rows without loosening identity?

**Verdict: YES, cleanly. `[VERIFIED: operator-claude-plugin/scripts/extraction.py, read this session]`**

The file-based `__main__` CLI (`load_artifact(path)` -> `validate(artifact)`) is a thin
convenience wrapper, not the module's real contract. `validate(artifact: dict, mapping_path=None)`
operates on a plain in-memory Python dict — `operator-claude-plugin/scripts/preingest.py` already
imports and calls sibling `extraction` functions directly as a library (`extraction.hold_emailless`,
`extraction.canonical_props()`), confirming this is the module's normal consumption pattern, not
just a CLI. A Phase 62 caller can build `{"records": [...]}` in memory from Lusha's response and
call `extraction.validate()` directly — no file upload is structurally required.

**Exact shape each synthesised record must carry**, confirmed by reading `validate()`'s per-record
pre-flight (`operator-claude-plugin/scripts/extraction.py:560-602`):

```json
{
  "record_type": "contacts",
  "row": {
    "firstname": "...", "lastname": "...", "company": "...",
    "jobtitle": "...", "email": "...", "linkedin_url": "..."
  },
  "provenance": {"input": "lusha_search_and_enrich", "locator": "<company id or domain>"}
}
```

- `record_type` is optional, defaults to `"contacts"` — correct for this phase, no explicit value
  needed.
- `row` keys must be in the **canonical prop set** (`extraction.canonical_props()`, derived from
  `config/column_mapping.yaml`'s `aliases` values: `email`, `firstname`, `lastname`, `jobtitle`,
  `linkedin_url`, `phone`, `company`, `company_id`) — anything else is stripped and reported in
  `dropped_keys`, never silently kept.
- `provenance.input` and `provenance.locator` must both be non-blank or the whole record rejects
  with `"record has no provenance, or provenance is missing which input or which span/locator
  produced it"` (line 597) — a suggested row needs SOME locator string; `"lusha:<company_id>"` is a
  reasonable literal.
- `resolutions` (optional) is a **separate, narrower mechanism** — see the Pitfall below.

**Identity contract applies unchanged** — `[VERIFIED: config/column_mapping.yaml:60-64, read this
session]`:

```yaml
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
    - [linkedin_url]
```

D-62-09's "no special-casing for suggested rows" holds structurally: `has_identity()` is called on
the cleaned row with these same three groups regardless of where the row came from. A Lusha match
that returns only `firstName`+`lastName`+`company` (no email/LinkedIn) resolves via group 2 exactly
like a CSV row would; a match with `linkedinUrl` resolves via group 3 (the third identity group,
added Phase 61-03, per CLAUDE.md §13.0.2). A match returning only a job title and no name/email/
LinkedIn — plausible if Lusha's response schema ever supplies a title without personal identifiers,
though the contract's contacts response (§4) always includes `firstName`/`lastName` when it
matches at all — fails identity and routes to the standing weak-key `needs_review` path, same as
any other row.

### Pitfall: two provenance mechanisms, easy to conflate

`extraction.py`'s optional `resolutions` list is validated against a **closed vocabulary**
(`[VERIFIED: operator-claude-plugin/scripts/resolution_sources.py:26-31, read this session]`):

```python
RESOLUTION_SOURCES = frozenset({
    "hubspot_lookup",
    "operator_statement",
    "provider_result",
    "same_row_derivation",
})
```

`"lusha"` is not a member of this set — a `resolutions` entry naming `source: "lusha"` would be
**rejected outright** (`extraction.py:651-664`, `"...names source 'lusha', which is outside the
closed set..."`). This vocabulary answers a different question ("how was a missing IDENTITY field
resolved before the row reached extraction") from D-62-17's question ("what stamps the CRM's
per-field provenance after the row is written"). If Phase 62 needs to record `resolutions` at all
(it does not have to — the field is optional), the correct value is `"provider_result"`, never
`"lusha"`.

> **Standing under the re-scope, unchanged.** This whole Priority 3 finding is about
> `extraction.py`'s row contract, not about which mechanism supplies the row's values — it applies
> identically whether a row comes from Lusha (original pass) or from web research (re-scope). See
> `§ RE-SCOPE AMENDMENT`'s own Priority 3 above for the re-scope-specific addition (no name-split
> gap; no existing research→enrich composition to copy).

---

## The rest of the priorities, researched

### `write_grant.envelope()` / `plan_grant()` — carrying a suggestion allowance (D-62-11)

`[VERIFIED: operator-claude-plugin/scripts/write_grant.py, read this session]`

- `envelope(config, *, object_type, record_ids, record_domains, providers, transport, today,
  headroom)` at line 409 builds the GRANT-02 disclosure block. It already prices a record count ×
  provider set via `cost_guard.estimate_batch()` and folds in the sampled monthly execution
  ceiling. Adding a suggestion allowance means widening the figures this function assembles — e.g.
  treating "companies eligible for a suggestion round" as an additional weighted contributor to
  `record_count` or a sibling figure disclosed alongside it — not a new code path.
- **The CR-01 key-collision fix is confirmed exactly as CONTEXT.md describes** — read live at
  `write_grant.py:455-461`:
  > "CR-01 fix (Phase 60 review): this used to share the name `ceiling` with the sampled-allowance
  > verdict dict assigned below, so `figures["chunk_ceiling"]` ended up holding the verdict dict
  > instead of this int, and the GRANT-02 disclosure rendered a dict repr where a record count
  > belongs. Kept as its own name so the two meanings... can never collide again."

  Confirmed by grep: `figures["chunk_ceiling"]` is read as an int at line 579 (`"at most
  {figures['chunk_ceiling']} record(s)"`); `figures["ceiling"]` is read as the verdict dict at line
  1037 (`ceiling = figures["ceiling"]`). **Do not reuse either key name for a new suggestion
  figure** — pick a third name (e.g. `figures["suggestion_allowance"]`).
- `plan_grant()` (line 892) is the actual refusal/split-offer site — see next section.

### Phase 57's `CEILING_OVER` refusal + `_affordable_record_count()` split offer (D-62-13)

`[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1034-1080, read this session]`

`plan_grant()` already contains the complete mechanism: on `CEILING_OVER`, it calls
`split_for_allowance()` (line 1050), which internally calls `_affordable_record_count(total,
ceiling, remaining)` (line 746) — a linear scan (deliberately not a `while` loop, per this repo's
own AST guard forbidding `while` outside `watch.py`) that finds the largest N whose
`ceil(N/ceiling) + N` execution cost fits under the sampled remaining monthly allowance, pinned by
a monotonicity test (`test_affordable_record_count_cost_is_monotonic_over_a_range_of_n`). The
refusal text at line 1071 ("`{record_count}` record(s) would fit this run, with the
`{record_count - record_ceiling_per_run}` remainder...") is the exact split-offer language D-62-13
wants reused. **Nothing new to build here** — a suggestion round that pushes the batch over ceiling
gets the identical refusal-with-split-offer an enrichment batch gets today, provided the
suggestion allowance is folded into the SAME `record_count`/figures this function already prices
(see previous section) rather than tracked as a second parallel figure that this refusal logic
never sees.

### `scripts/inventory_org_type_values.py` — the read-only sampling idiom (D-62-05)

`[VERIFIED: scripts/inventory_org_type_values.py, read this session]`

The named pattern: `_has_credentials()` (checks `HUBSPOT_PRIVATE_APP_TOKEN`) skip-to-exit-0 ->
`_portal_ok()` (checks `HUBSPOT_PORTAL_ID` against a hardcoded `EXPECTED_PORTAL_ID` env-overridable
guard) -> paged `POST /crm/v3/objects/{object}/search` with an empty filter group and
`properties: [the one property]`, `limit: 100`, following `paging.next.after` -> per-value
classification against a known vocabulary. For `jobtitle` on **contacts** (not companies), the same
skeleton applies with `properties: ["jobtitle"]` against `crm/v3/objects/contacts/search` — the one
structural difference is the classification step: `inventory_org_type_values.py` classifies
against `src/taxonomy.py`'s static 9-key vocabulary (`classify_value()`), but `jobtitle` has no
equivalent static taxonomy to classify against — that's precisely what D-62-05's Haiku clustering
step replaces. **Recommendation, not deep research:** cache the cluster result as a committed
artifact rebuilt by a script invocation, mirroring `config/taxonomy.yaml`'s precedent (a
config file the code reads, not a runtime computation) — this satisfies D-62-05's "cached... not
re-clustered per run" requirement with a pattern this codebase already uses elsewhere.

### Per-field provenance stamping (D-62-17)

`[VERIFIED: n8n/code/mergeContacts.js:1-28, 174; scripts/build_cloud_workflows.py:275-293,
730, 766, 877, read this session]`

CLAUDE.md §6/§8's flat `{field}_source`/`{field}_confidence`/`{field}_evidence_url`/... properties
were **never built for contacts** — this is the same "documented but never created" pattern §4.0
already names for other properties. The actual, live mechanism is Phase 15's single JSON blob:

> "PROVENANCE MODEL (Phase 15): per-field metadata/staging is ONE provenance object keyed by field
> (`{source, confidence, verified_at, validation_status, value}`), not flat
> `{field}_source`/`{provider}_{field}` properties. The caller... serializes it ONCE via
> `stableStringify()` into `lv_contact_enrichment_provenance`..." (`mergeContacts.js:23-27`)

`mergeContacts(existing, candidate, cacheHint, opts)` accepts `opts.source` (line 174: `const
source = (opts && opts.source) || "csv";`) — this IS the reusable hook D-62-17 needs; it already
supports a caller-supplied source string, it is simply never called with one today. The one call
site that matters for this phase is the ingest lane's `MERGE_CONTACTS` n8n-wrapper code
(`scripts/build_cloud_workflows.py:275-293`), which hardcodes:

```js
const merged = mergeContacts({}, candidate, undefined, { source: "csv", confidence: 80 });
```

This exact string constant (`MERGE_CONTACTS`) is registered as the `"Merge Contacts"` node in
**both** `build_local()` (line 730, the offline dry-run template) and `build_cloud()` (line 766
defines the function, line 877 registers the node) — `build_cloud()` is what emits the deployed
`wf_contact_ingest_cloud.json`. **The change D-62-17 needs is narrow and confined to this one
constant:** derive `source` from a value the row itself carries (e.g. a `row.origin` field the
suggestion-synthesiser sets to `"lusha"`, read here instead of the hardcoded literal) rather than
always defaulting to `"csv"`. Both `build_local()` and `build_cloud()` pick up the change
automatically since they share the one constant — consistent with this codebase's "one
implementation" pattern (CLAUDE.md §13.0.1) and this phase's own D-62-08 reasoning.

**`confidence: 80`** is also hardcoded in the same call and would need the same treatment if a
suggested row's confidence should differ from a CSV upload's assumed 80 — not required by any
D-62 decision, flagged for the planner's awareness only.

### "Batch just completed" hook (D-62-15)

`[CITED: operator-claude-plugin/scripts/run_state.py:89, read this session]` — There is no
n8n-side "batch complete" webhook or workflow event; the architecture is async-submit-and-poll
(CLAUDE.md §13.0.2's `async_ack`), so completion is a **client-side** fact, not a backend one.
`run_state.py` derives a `done` status per row from verdicts in `{MATCHED, ENRICHED}`; a batch is
"complete" when every row in the client's manifest reaches one of those terminal verdicts. The
natural hook for D-62-15's unprompted offer is therefore **in the conversational skill layer**
(`operator-claude-plugin/skills/contact-upload/`, `enrich-records/`, or wherever the plugin already
polls run-state to completion) — after the poll loop observes all rows `done`, before ending that
turn, raise the suggestion offer. This is a skill/prompt-flow change, not a new backend mechanism.

### "Zero associated contacts" check (D-62-16)

Not independently probed live this session (read-only constraint). `[ASSUMED — standard HubSpot
CRM v4 associations read, mirrors a write path this repo already uses live.]` CLAUDE.md §13.0.1
confirms the live WRITE path: `PUT /crm/v4/objects/contacts/{id}/associations/default/companies/{id}`.
The read-only mirror in the same API family, `GET
/crm/v4/objects/companies/{company_id}/associations/contacts`, is the standard way to enumerate a
company's associated contacts and would return an empty `results` array for "nobody named." This
needs one read per company in the batch (or a single batch-associations read if HubSpot's v4 API
offers one — not confirmed this session). Flagged for a `checkpoint:human-verify` or a cheap
disarmed live probe before the plan locks this as the mechanism, since it was not independently
confirmed against `api.hubapi.com` in this research pass.

---

## Common Pitfalls

### Pitfall 1: Treating "search" in the endpoint's name as evidence it searches
**What goes wrong:** `POST /v3/contacts/search-and-enrich` reads as a search endpoint from its
name alone, and D-62-01's own text calls it "the discovery provider." The verb in the endpoint
name describes Lusha's own internal two-step process (search their database, then enrich the
match) collapsed into one call — not a capability to search FOR someone you cannot name.
**Why it happens:** the name is genuinely misleading relative to what CLAUDE.md/this repo means by
"discovery" (finding people you don't know exist).
**How to avoid:** read the request/response contract's identity-object shape, not the endpoint
name, before assuming a capability. Priority 1 above is written to make this check reusable.
**Warning signs:** a design that assumes a company-only or role-only request body against this
endpoint.

### Pitfall 2: Conflating `extraction.py`'s two provenance mechanisms
Covered in full under Priority 3 above. `resolutions.source` (closed vocab: `hubspot_lookup`,
`operator_statement`, `provider_result`, `same_row_derivation`) is not the same field as
`mergeContacts.js`'s `opts.source` (free string, feeds `lv_contact_enrichment_provenance`). A
planner reaching for "stamp source=lusha" needs the SECOND mechanism, and must not add `"lusha"`
to the first vocabulary to make it fit.

### Pitfall 3: Assuming CLAUDE.md §6/§8's flat provenance properties exist
They don't, for contacts, per Phase 15's own comment in `mergeContacts.js`. Writing a plan task
that PATCHes `jobtitle_enriched_source` etc. would silently write to a property HubSpot has never
had defined (same failure class as §4.0's `enrichment_requested` vs `lv_enrichment_requested`) —
use `lv_contact_enrichment_provenance` instead.

### Pitfall 4: Pricing the suggestion round against the wrong endpoint's economics
D-62-12/14's "per-company cap" and "companies × cap" ceiling framing was written assuming a
search-shaped call. Whatever mechanism the operator picks under § Open Questions, re-derive the
ceiling formula against THAT mechanism's actual request/response shape (1:1 vs 1:N) before reusing
D-62-14's arithmetic verbatim.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Lusha's Enrichment API request body has no `jobTitle`/`title`/`role` parameter — inferred from a closed, live-confirmed allow-list that never included it, not from a direct probe of that specific key. | Priority 1 | Low — three converging lines of evidence (1:1 response shape, this project's own Phase 20 pitfall writeup, Lusha's own docs placing role filters under a different product) all point the same way; the named falsification probe would close this to `[VERIFIED]` at zero credit cost. |
| A2 | Lusha's Prospecting API billing model (search credits vs. reveal credits, per-result cost) is unknown to this repo. | Priority 2 | Medium — if the operator reopens the Prospecting decision (§ Open Questions option a), D-62-14's cost-ceiling formula cannot be trusted until this is live-probed; a plan that reuses D-62-14's arithmetic for the Prospecting API without re-probing could under-price the round. |
| A3 | `GET /crm/v4/objects/companies/{id}/associations/contacts` is the correct read-only mirror of the write path CLAUDE.md §13.0.1 confirms live; not independently probed this session. | D-62-16 / "the rest of the priorities" | Low-Medium — a wrong endpoint name would surface immediately as a 404 in a disarmed dry run, before any write risk; still worth a `checkpoint:human-verify` before locking it into a task. |
| A4 | A company-only Lusha identity body (`companyName`+`companyDomain`, no person name) either 400s or returns exactly one arbitrarily-matched result — inferred from the 1:1 response-array-alignment description, never directly probed. | Priority 1 | Low — feeds the same falsification probe named in Priority 1; matters only if someone considers "company-only search" as a workaround, which this document already argues against on response-shape grounds alone. |
| A5 | Project memory's claim that headless `claude -p` invocations fail to authenticate under cron was not independently re-verified this session (the source file could not be located on disk this session); treated as corroborating context only. | RE-SCOPE AMENDMENT, Priority 1 | Low — even without this corroboration, the `backend-sweep` read-only contract (independently read and verified this session) is sufficient on its own to establish "no unattended write/fetch path exists in this plugin." |
| A6 | HubSpot's company `website` property is assumed reliably populated enough to attempt a homepage-only starting point, based on CLAUDE.md §18.4 listing it among the standard fetch fields — not independently confirmed against a live portal read this session. | RE-SCOPE AMENDMENT, Priority 2 | Low — this assumption is not load-bearing for the Priority 2 finding either way: even a perfectly reliable `website` value only yields a homepage, and the finding is that no mechanism turns a homepage into the correct leadership subpage. |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **RESOLVED (2026-09-02), replaced by a new question one layer down.** Original Open Question 1
   asked which discovery mechanism to build against. The operator answered it: web research
   (D-62-01 rev 2). This amendment's `§ RE-SCOPE AMENDMENT` (Priority 6) found the ANSWER itself now
   has an open sub-question:

   **Does Phase 62's "round" mean operator-attended (bounded by human time, per company) or
   backend-automated (bounded only by cost, per CONTEXT.md's "300-company round" language) — and if
   automated, is a net-new programmatic discovery step (Amendment Priority 6, option (b)) in scope
   for this phase, or is that phase-boundary-violating "new provider surface" territory the Phase
   Boundary in CONTEXT.md already excludes?**
   - What we know: mechanism (a) — the one D-62-01 rev 2 actually names and the one UAT 2.4 proved —
     is real but requires an operator-supplied starting URL and operator-approved escalation per
     company, with no batch or unattended entry point anywhere in this repo (Amendment Priorities
     1-2). Mechanisms (b)/(c) are backend-batchable but cannot name people at all.
   - What's unclear: whether "auto-offered... unprompted" (D-62-15) and "a 300-company round"
     (D-62-12's own framing in CONTEXT.md) were written with mechanism (a)'s actual constraints in
     mind, or whether the operator believed a backend-automated capability already existed because
     UAT 2.4's success READ as more general than it is.
   - Recommendation: return this finding to the operator (checkpoint or `/gsd-discuss-phase`
     re-entry) before planning proceeds, exactly as Open Question 1 originally recommended for the
     first premise gap. Do not let the planner silently pick option (a) or (b) from Amendment
     Priority 6 — this is the same class of explicit, disclosed operator decision D-62-07 modelled
     for SUGGEST-03.

2. **Does the v4 associations API support a batched "which of these N companies have zero
   contacts" read, or does it require N individual calls?**
   - What we know: the per-company GET exists and is the standard mechanism (A3 above).
   - What's unclear: whether HubSpot's batch associations read (`POST
     /crm/v4/associations/{fromObjectType}/{toObjectType}/batch/read`) is more efficient for a
     300-company batch than 300 individual GETs — relevant to D-62-11's cost/execution accounting
     if this read happens inside an n8n Cloud execution (counts toward the 2.5K/month budget) vs.
     client-side (does not).
   - Recommendation: a one-line probe question for whoever plans the task, not deep research —
     name both options in the plan and let the plan-checker or the operator pick based on the
     batch-size economics at plan time.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (Python) | pytest |
| Framework (n8n JS) | Node's built-in `node:test` |
| Config file | none dedicated — `pytest.ini`/`pyproject.toml` at repo root; n8n JS tests are plain `.test.mjs` files under `tests/n8n/` |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py operator-claude-plugin/tests/test_write_grant.py -x` |
| Full suite command | `.venv/bin/python -m pytest && node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24, per project memory `test-suite-run-commands.md`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUGGEST-01 | Round offered after batch completes | integration (client-side skill flow) | none yet — depends on which skill hosts the offer | ❌ Wave 0 |
| SUGGEST-02 | Roles chosen once, applied across batch | unit | new test alongside role-vocabulary module | ❌ Wave 0 |
| SUGGEST-03 (amended) | Role vocabulary derived from live `jobtitle`, with disclosed generic fallback | unit + a disarmed live-inventory dry run (mirrors `inventory_org_type_values.py`'s own pattern — no committed automated test for a live HubSpot read) | `.venv/bin/python -m pytest <new role-vocab test file>` | ❌ Wave 0 |
| SUGGEST-04 | Suggestions proposed, never auto-created | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py` (existing identity/hold-row contract, reused not modified) | ✅ exists |
| SUGGEST-05 | Cost shown before spent | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_surface.py` | ✅ exists |
| D-62-17 | `source=lusha` provenance stamped | unit (n8n) | `node --test tests/n8n/mergeContacts.test.mjs` — needs a new case for a non-`"csv"` source once `MERGE_CONTACTS`'s hardcode is parameterised | ✅ file exists, ❌ new case |

### Sampling Rate
- **Per task commit:** the quick run command above (scoped to the files the task touched).
- **Per wave merge:** the full suite command above.
- **Phase gate:** full suite green before `/gsd-verify-work`, plus the disarmed-dry-run discipline
  every prior phase in this repo has used for any n8n redeploy (never arm/deploy inside research or
  planning).

### Wave 0 Gaps
- [ ] A test file for the role-vocabulary clustering module (covers SUGGEST-02/SUGGEST-03) — does
      not exist yet; no clustering module exists yet either.
- [ ] A test case in `tests/n8n/mergeContacts.test.mjs` (or a new file) asserting `MERGE_CONTACTS`'s
      n8n-wrapper reads `source` from the row rather than hardcoding `"csv"`, once that change
      lands (D-62-17).
- [ ] An offline oracle test for the synthesised-row shape entering `extraction.validate()` directly
      (bypassing `load_artifact`) — `operator-claude-plugin/tests/test_extraction_contract.py`
      already exercises `validate()` on hand-built dicts, so this is very likely additive test
      cases in that existing file, not a new file.
- [ ] No test scaffolding needed for the discovery-provider question until § Open Questions #1 is
      resolved — do not build tests against a mechanism that has not been chosen.
- [ ] (Amendment) A test file for the ONLINE role-classification module (Amendment Priority 5's
      item (2): matching a freshly-extracted page title against the cached family list) — distinct
      from the offline clustering module's own test file above; does not exist yet, no module
      exists yet either.
- [ ] (Amendment) If the operator picks Amendment Priority 6's option (b), a new rate key in
      `operator-claude-plugin/config/cost_rates.json` (shipped `null`) plus a `cost_guard.py`
      pricing function paralleling `research_line()`'s tri-state shape — neither exists yet.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Lusha `api_key` header auth already established; no new auth surface |
| V3 Session Management | no | n/a — this phase adds no session concept beyond the existing write-grant session |
| V4 Access Control | yes | The existing write-grant / arming gates (`ALLOW_HUBSPOT_CREATE`, `n8n_arming`) already gate any write this phase's proposals could produce — D-62-10's "no per-record confirmation" relies on the ingest lane's EXISTING held/needs_review gates, not a new access-control surface |
| V5 Input Validation | yes | `extraction.py`'s canonical-prop allowlist + identity-group check (already reused, not built new) |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A synthesised row smuggling a non-canonical key onto a HubSpot write | Tampering | `extraction.py`'s existing `dropped_keys` strip (STRUCT-01, already enforced, reused not rebuilt) |
| A synthesised row bypassing the email gate to reach a silent no-write | Tampering / DoS-on-data-quality | `hold_emailless()`, already enforced |
| Cost blowout from an unbounded suggestion round | Denial of Service (budget) | D-62-12's operator-set per-company cap + D-62-11's folding into the existing session-grant ceiling machinery (`plan_grant`/`CEILING_OVER`), both already researched above as reusable, not new |
| PII in a suggested-row provenance/log trail | Information Disclosure | Follow the same PII-redaction discipline `docs/LUSHA-V3-CONTRACT.md`'s own redaction note establishes (threat T-20-03) for any new fixture or log this phase's tests add |

## Sources

### Primary (HIGH confidence)
- `docs/LUSHA-V3-CONTRACT.md` — live-probed 2026-07-30 / 2026-08-30 contract of record for the
  Lusha v3 Enrichment API (contacts and companies lanes, billing model, error shapes).
- `n8n/code/lushaRequest.js` — the current request-body builders, read this session.
- `operator-claude-plugin/scripts/extraction.py` — read this session, lines 117-950 covering
  `ExtractionResult`, `identity_groups`, `has_identity`, `validate()`'s per-record pre-flight,
  `hold_emailless`, `write_dispatch_csv`, and the `__main__` CLI wrapper.
- `config/column_mapping.yaml` — read this session, `aliases` and `required_identity.any_of`.
- `operator-claude-plugin/scripts/resolution_sources.py` — read this session, `RESOLUTION_SOURCES`.
- `n8n/code/mergeContacts.js` — read this session, lines 1-100+174, the Phase 15 provenance model
  and `opts.source` hook.
- `scripts/build_cloud_workflows.py` — read this session, `MERGE_CONTACTS` constant (lines
  275-293) and its two registration sites (`build_local()` line 730, `build_cloud()` lines
  766/877).
- `operator-claude-plugin/scripts/write_grant.py` — read this session, `envelope()` (409),
  `plan_grant()` (892), `_affordable_record_count()` (746), the CR-01 comment (455-461) and its
  confirmed key usage (579, 1037).
- `scripts/inventory_org_type_values.py` — read this session, the full read-only inventory idiom.
- `operator-claude-plugin/scripts/run_state.py` — read this session, the `done`/verdict status
  model (line 89).

### Primary, added by the RE-SCOPE AMENDMENT (HIGH confidence)
- `operator-claude-plugin/scripts/url_fallback.py` — read in full this session; `plan_ladder`,
  `same_host`, `filter_candidates`, `give_up_message`, `MAX_FOLLOWUP_FETCHES`, the module docstring
  stating it cannot call `web_fetch` itself.
- `operator-claude-plugin/skills/contact-upload/extraction.md` — read in full (lines 1-320+) this
  session; the INGEST-05 URL adapter's operator-paste/approve contract, quoted verbatim.
- `operator-claude-plugin/skills/backend-sweep/SKILL.md` — read in full this session; the
  read-only, no-mutation contract confirming no unattended path exists.
- `operator-claude-plugin/UAT.md` — read this session (sessions 0-5), especially 2.4 (the GCTC
  board-of-directors walk) and 2.2 (the `name_split.py`/amendment 6a provenance).
- `src/web_research.py` — read in full this session; the company-only `REQUIRED_FIELDS`,
  `RESEARCH_SYSTEM` prompt, and `WEB_RESEARCH_MAX_SEARCHES` env read.
- `n8n/code/webResearch.js` — read in full this session; `validateResearchOutput`/
  `toProviderResult`'s company-ICP-only schema.
- `n8n/code/contactResearch.js` — read in full this session; `CONTACT_RESEARCH_FIELDS =
  ["jobtitle", "seniority"]` and the name-required request shape.
- `scripts/build_cloud_workflows.py` — read the generated companies/contacts "Build Research
  Request" node bodies this session (~lines 1009, 1877, 2751-2758), confirming
  `WEB_RESEARCH_MAX_SEARCHES = 5` is deployed identically in both.
- `operator-claude-plugin/scripts/company_domain.py` — read `needs_research()`/`decline_research()`
  this session (lines 140-200); the explicit "actually researching them is neither function's job"
  admission for the adjacent, easier, still-unbuilt domain-research problem.
- `operator-claude-plugin/config/cost_rates.json` — read in full this session; `anthropic_usd_per_record`
  (0.068624, all-in chain, not research-isolated), `company_domain_research` (null, unmeasured), and
  the judge-model intro-pricing expiry note.
- `operator-claude-plugin/scripts/cost_guard.py` — read in full this session; `estimate_batch()`,
  `research_line()`'s tri-state pricing shape, `RESEARCH_RATE_KEY`.
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — read in full this session; the
  closest analogous research/enrich composition, confirmed entirely conversational and confirmed to
  explicitly refuse substituting company-oriented research for a person.

### Secondary (MEDIUM confidence)
- `.planning/workstreams/milestone/phases/20-lusha-v3-migration/20-RESEARCH.md` — Pitfall 1
  (Enrichment vs. Prospecting API conflation), read this session.
- `.planning/workstreams/milestone/REQUIREMENTS.md` § Out of Scope — the standing Prospecting-API
  exclusion, read this session.
- WebSearch results for `docs.lusha.com`'s Contact Search and Enrich vs. Prospecting Search and
  Enrich product pages — corroborating but not independently fetched (the docs site is a
  JS-rendered SPA; WebFetch could not render it, matching `LUSHA-V3-CONTRACT.md`'s own note about
  this limitation).

### Tertiary (LOW confidence)
- A4/A3 in the Assumptions Log (company-only Lusha identity behaviour; the exact v4 associations
  read endpoint) — inferred from adjacent live-confirmed evidence, not independently probed this
  session.

## Metadata

**Confidence breakdown:**
- Original provider-capability finding (Priority 1, now historical): HIGH — convergent,
  tool-confirmed, multi-source evidence; superseded as a discovery recommendation, load-bearing for
  ruling out vendor discovery permanently.
- Ingest-lane reuse contract (Priority 3, D-62-08/09): HIGH — read directly from source this
  session, including the exact record shape and rejection messages; confirmed to apply unchanged
  under the re-scope.
- Grant/ceiling reuse (D-62-11/13): HIGH for the mechanism; the actual cost NUMBERS (D-62-14) remain
  MEDIUM-LOW — the re-scope's two-component ceiling has one component (stage 2, Lusha) HIGH
  confidence and one component (stage 1, research) with NO measured rate at all (Amendment
  Priority 4), and the whole ceiling's premise depends on Open Question 1's new sub-question.
- Provenance mechanism (D-62-17): HIGH — read directly from source, including the exact call site
  needing a change; unaffected by the re-scope beyond the `source` value now being mixed rather
  than a single literal.
- Role-vocabulary sampling idiom (D-62-05): HIGH for the offline-clustering pattern; the
  Haiku-clustering step itself, and the SEPARATE online-classification step Amendment Priority 5
  surfaces, are both new work with no precedent to verify against.
- **Re-scoped discovery mechanism (D-62-01/02/03 rev 2, this amendment): HIGH confidence that
  mechanism (a) is real and does what UAT 2.4 showed; HIGH confidence that it has no
  programmatic/batch entry point (Amendment Priorities 1-2, both confirmed by direct source read and
  by a negative grep across the whole repo, not by absence-of-evidence reasoning alone).** This is
  the load-bearing new finding of this amendment pass.

**Research date:** 2026-09-02
**Amended:** 2026-09-02
**Valid until:** 14 days — this research is gated on a NEW operator decision (Open Question 1,
amended): whether a "round" is operator-attended or backend-automated, and if automated, whether
building a net-new programmatic discovery step is in this phase's scope. Once that decision lands,
re-derive D-62-14's stage-1 cost ceiling against whichever mechanism is actually chosen — nothing in
this document prices mechanism (b)-style discovery, because it does not yet exist.
