# Phase 64: The ladder stops at the best page, not the first - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

A company whose real staff list sits deeper than its first people-bearing page is walked to
that list, within the **unchanged** `MAX_FOLLOWUP_FETCHES` budget. This phase moves the
stop-the-walk decision out of `SKILL.md` prose and into a testable code predicate, and makes
people found across the walked pages accumulate instead of being discarded.

**In scope:** the per-company stage-1 page walk in `suggest_contacts.py` — when it stops,
what it accumulates, and what it reports about how it ended.

**Out of scope:** the search fallback and its eligibility rule (Phase 65), the role matcher
itself (landed as quick 260905-rf1), the email/alternate-domain path (quick 260905-ad2),
stage-2 provider enrichment (Phase 66).

</domain>

<decisions>
## Implementation Decisions

### What the walk produces

- **D-64-01: Union across walked pages, deduped by name.** Every page the walk fetches
  contributes its people to one accumulated set for the company; the role filter runs over
  that union, not over a single winning page. A `/contact` page naming a receptionist and a
  `/board/` page naming nine officers yields ten candidates, and `select_people` decides.
  Rejected: "best page replaces" (discards people the role filter would have taken) and
  "best page + carry held names" (report-only consolation for the same loss).
  — **Reversibility:** costly — the round artifact's shape and every caller that reads
  one page's people per company change with it.

- **D-64-02: Dedupe key is the existing normalised first+last name key.** Reuse
  `suggest_contacts._name_key` — the same conservative, case-folded, whitespace-collapsed
  exact match `select_people` already uses for the D-62-18 known-contact pre-filter. Do not
  introduce a second, looser identity notion for cross-page dedupe; a near-match stays in
  and is resolved downstream, exactly as D-62-18's backstop half already rules.

### What "better" means

- **D-64-03: A page's score is its role-filter hit count.** `score(page) =
  len(select_people(page_people, ...)["selected"])` — people whose `jobtitle` classifies
  into one of the round's chosen families. Not raw people count: a 40-person sales
  directory must not beat a 9-person committee page. This makes "better" a predicate a
  test can assert on, which is the brief's explicit requirement.

- **D-64-04: Scoring runs mid-walk, so `classify_title` is called before the walk ends.**
  The walk cannot defer classification to the end — it needs the hit count to decide whether
  to continue. This is a pure, local, no-I/O call (`role_classify.classify_title`), so it
  costs nothing but ordering.

### When the walk stops

- **D-64-05: Stop on a cumulative "good enough" bar, not on the page just fetched.**
  The bar is measured against the **deduped union of every page walked so far**, not against
  one page in isolation. A club spreading two officers over `/contact` and two over `/about`
  reaches four and stops; it does not walk the full cap because no single page cleared the
  bar on its own.

- **D-64-06: `BAR = max(len(chosen_families), agreed_cap)`.** The bar is the count of role
  families the operator selected for the round, floored at the per-company cap the operator
  already priced and agreed (`suggest_contacts.agreed_cap`). The floor is load-bearing, not
  decoration: without it a round choosing one family would stop on its first hit, which
  reproduces the exact "stop at the first page" defect this phase exists to fix. Both inputs
  are numbers the round already has — no new operator question, no new tunable constant.
  — **Reversibility:** reversible — one expression, one call site.

- **D-64-07: The bar is a stop condition, never a budget.** Not clearing the bar means the
  walk continues until the ladder is exhausted or `MAX_FOLLOWUP_FETCHES` refuses the next
  candidate. Clearing it stops the walk early. Neither branch changes the cap.

### What the walk reports

- **D-64-08: The walk emits why it ended.** The result carries an `ended` reason —
  `good_enough` / `ladder_exhausted` / `cap_exhausted` / `refused` — alongside the accumulated
  people and the per-page scores. This is Phase 64's own output shape, and Phase 65 routes
  its cause-keyed re-entry on it rather than re-deriving cause from the attempts list.
  **Boundary:** 64 emits the reason and nothing more. It does not act on it, does not
  re-enter, and does not touch `search_fallback.eligible_after_ladder`.
  — **Reversibility:** costly — Phase 65 is planned to consume this field.

### Constraints that bind regardless of the above

- **D-64-09: `MAX_FOLLOWUP_FETCHES` is unchanged (5).** Continuing further is spending the
  SAME budget better, never a larger one. No per-page budget, no reset, no second allocation.
- **D-64-10: A refusal stays terminal.** A tool-level refusal or an off-host/scheme refusal
  from `url_fallback.filter_candidates` ends the walk for that company. Accumulating people
  across pages must not become a route around a fence (D-5sd-04 fence principle).
- **D-64-11: `cap_exhausted` remains a terminal, eligible ending** — never a trigger to
  fetch again.
- **D-64-12: No `while` loop in any plugin script.** Enforced by
  `tests/test_report_sufficiency.py::_has_while_loop`. The walk is expressed as bounded
  iteration over a fixed-length candidate list, which is a design constraint, not an
  afterthought.
- **D-64-13: `url_fallback.py` stays the ladder builder, called as a library and never re-implemented** (D-62-01). The canonical-authority `same_host` guard (62-10, G-62-2)
  applies to every candidate the extended walk reaches, unchanged.

### Claude's Discretion

- Where the walk lives — a new pure function in `suggest_contacts.py` versus extending
  `next_candidates`/`company_budget` — and its exact return shape beyond the `ended` field
  named in D-64-08.
- How much of `SKILL.md`'s step 5 prose is replaced versus rewritten to cite the new
  predicate. The prose rule at `SKILL.md:101`/`:299` ("stopping at the first one that yields
  people") must go; how the replacement reads is open.
- Whether per-page scores are surfaced in the round artifact or kept internal to the walk.

### Folded Todos

- **`2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md` (first half only).**
  Its "A SECOND, independent defect" section — `SKILL.md:101`/`:299` stopping at the first
  page that yields people — is this phase in full. The todo's first half (search fallback
  keyed on ladder-empty rather than round-empty) is **Phase 65** and is deliberately NOT
  folded here. The todo stays pending until 65 closes it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief and its milestone frame
- `.planning/todos/pending/2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md` —
  the phase brief. Read the "A SECOND, independent defect" section and the three hard
  constraints. The four-cause table explains why 65 is separate.
- `.planning/ROADMAP.md` § "Phase 64" and § "Binding on all six" — the SAFE-01..05 fence
  that binds every v1.2 phase.
- `.planning/milestones/v1.2-REQUIREMENTS.md` — requirement IDs this phase closes.

### The code this phase changes
- `operator-claude-plugin/scripts/suggest_contacts.py` — `discovery_plan`, `company_budget`,
  `next_candidates`, `select_people`, `_name_key`, `agreed_cap`, `no_candidates`,
  `round_artifact`. The walk's stop rule does not exist here yet; that is the phase.
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` lines ~101 and ~299 — the prose
  rule "stopping at the first one that yields people" that this phase replaces.
- `operator-claude-plugin/scripts/url_fallback.py` — `plan_ladder`, `filter_candidates`,
  `same_host`, `_canonical_authority`, `give_up_message`, `MAX_FOLLOWUP_FETCHES = 5`.
  Called as a library; not modified by this phase.
- `operator-claude-plugin/scripts/role_classify.py` — `classify_title`, `load_families`,
  `chosen_families`. Supplies the score in D-64-03 and one input to the bar in D-64-06.

### Decisions this phase must not disturb
- `operator-claude-plugin/scripts/search_fallback.py` — `eligible_after_ladder`. D-5sd-04's
  refusal fence. Phase 64 changes when the ladder ends, never who may look elsewhere after it.
- `.planning/quick/260904-5sd-sitemap-crawl-fallback-to-client-side-cl/` — D-5sd-04/-06,
  the eligible-ending vocabulary (`cap_exhausted` terminal-but-eligible).
- `.planning/quick/260905-rf1-role-filter-one-word-titles/` — the role matcher fix that
  makes D-64-03's score meaningful (landed; Brisbane Roar's live zero was this).
- `.planning/quick/260905-ad2-company-alternate-domains/` — the alternate-domain set
  (landed; Roma Turf Club's live zero was this, and it is not a walk problem).

### Tests that constrain the implementation
- `operator-claude-plugin/tests/test_report_sufficiency.py::_has_while_loop` — no `while`
  in any plugin script (D-64-12).
- `operator-claude-plugin/tests/test_url_fallback.py` — cap and `same_host` boundaries.
- `operator-claude-plugin/tests/test_cost_guard_suggestion.py` — asserts
  `cost_guard.MAX_FETCHES_PER_COMPANY == url_fallback.MAX_FOLLOWUP_FETCHES` and the
  `7 * MAX_FOLLOWUP_FETCHES` stage-1 ceiling. Both must still hold (D-64-09).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `suggest_contacts._name_key` — the dedupe key D-64-02 reuses verbatim; already the
  identity notion `select_people` uses for the known-contact pre-filter.
- `suggest_contacts.select_people` — already returns `{"selected", "dropped"}`; its
  `len(selected)` IS the page score in D-64-03, no new scoring code needed.
- `suggest_contacts.agreed_cap` — already the operator's priced per-company cap; supplies
  the floor in D-64-06 with no new operator question.
- `suggest_contacts.company_budget(attempts)` / `next_candidates(...)` — already thread a
  per-company `already_fetched` count into `filter_candidates`. The extended walk spends
  through this same seam; it does not need its own counter.
- `url_fallback.filter_candidates` — already refuses on scheme, host, then budget, in that
  order, and returns `refused` entries with reasons. D-64-10/-11's terminal endings are
  readable straight off its output.

### Established Patterns
- **The plugin scripts are pure.** `suggest_contacts.py` has no HTTP client, no model call,
  no filesystem write (62-01). The walk's stop predicate must stay pure — the LLM
  orchestrator performs the `web_fetch` and feeds the page's people back in. The phase moves
  a DECISION into code, not the fetching.
- **Prose rules get promoted to code, not duplicated.** `agreed_cap` promoted `SKILL.md`
  step 3's cap rule (D-62-11/-12); this phase does the same to step 5's stop rule.
- **Refusals are never re-worded.** `next_candidates` returns `filter_candidates`'s result
  verbatim and `no_candidates` returns `give_up_message`'s text verbatim. The walk must
  carry refusal reasons through unchanged.
- **Bounded iteration only** — no `while`, enforced by test.

### Integration Points
- `SKILL.md` step 5 is the caller: it fetches in ladder order and today stops on the first
  people-bearing page. The new predicate is what it consults instead.
- `round_artifact` / `partition_for_dispatch` consume the company's people; the union
  (D-64-01) changes what they receive in volume, not in shape per person.
- Phase 65 consumes D-64-08's `ended` field. Nothing else does yet.

</code_context>

<specifics>
## Specific Ideas

- The live case that defines success: a club whose `/contact` page names one receptionist
  while `/board/` lists the whole committee. Today the walk stops at the receptionist. After
  this phase it reaches `/board/` and both pages' people are in the union.
- The operator's framing throughout: **spend the same budget better.** Every option was
  weighed against whether it enlarges the fetch budget; none does.
- The bar's floor (D-64-06) was added after the plain `len(chosen_families)` rule was shown
  to reproduce the defect on a one-family round. The operator chose the cap floor over a
  fixed constant.

</specifics>

<deferred>
## Deferred Ideas

- **Round-empty re-entry keyed on cause** — Phase 65. Phase 64 emits the `ended` reason;
  acting on it is 65's.
- **Board-shaped URL heuristics** (continue only while an unread `/board/`-shaped candidate
  remains) — considered as a stop rule and not chosen. Noted in case 65 wants a
  candidate-ranking signal.
- **Surfacing per-page scores to the operator's report** — left to Claude's discretion here;
  if it turns out to be operator-facing rather than internal, it belongs with Phase 68's
  disclosure audit.

### Reviewed Todos (not folded)
- `2026-09-04-phone-is-never-chased-only-accepted.md` — Phase 66. Stage-2 enrichment breadth,
  not stage-1 page walking.
- `2026-09-04-autonomy-flag-with-sensible-defaults.md` — Phase 67.
- `2026-09-04-state-the-price-and-keep-moving.md` — Phase 68.
- `2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md` — Phase 69.
- `2026-09-04-company-domain-has-no-candidate-source.md` — n8n merge lane, no v1.2 phase.
  Surfaced by the fuzzy todo matcher on shared keywords only; unrelated to this phase.

</deferred>

---

*Phase: 64-the-ladder-stops-at-the-best-page-not-the-first*
*Context gathered: 2026-09-05*
