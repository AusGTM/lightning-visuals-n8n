# Quick Task 260904-5sd — Discussion Context

**Task:** when the sitemap-based website crawl cannot find persons for suggest-contacts, fall
back to client-side Claude web search results, with priority given to authoritative and
industry websites and LinkedIn.

**Discussion held:** 2026-09-04, operator present. The three decisions below are **LOCKED** —
downstream agents implement them and do not revisit them.

---

## Grounding established before the questions were asked

- `operator-claude-plugin/scripts/url_fallback.py`'s entire safety property is **same-host**:
  "every candidate URL is on the pasted URL's own host (`same_host`), and the number of
  follow-up fetches across the WHOLE ladder is bounded by one named constant
  (`MAX_FOLLOWUP_FETCHES`)". It performs **no I/O of any kind** — it builds strings, which is
  what satisfies the autouse `no_network` guard in `tests/conftest.py` by construction rather
  than by a mock.
- **A web-search result is off-host by definition**, so this feature CANNOT live inside
  `url_fallback.py` without destroying that property. It needs its own module and its own
  boundary.
- `web_search` is used **nowhere** in the plugin today. `skills/suggest-contacts/SKILL.md`
  uses the native `web_fetch` server tool only (lines 98, 126).
- The current terminal state when the ladder finds nothing is
  `url_fallback.give_up_message(pasted_url, attempts)`, called at
  `scripts/suggest_contacts.py:416`. That call site is where the fallback attaches.

---

## D-5sd-01 — Disposition: sendable if a strong source agrees AND enrichment validates

**Decision:** a search-sourced person MAY become sendable — it is not unconditionally held —
but only when **both** hold:

1. the result comes from a **strong source** per the D-5sd-02 ranking, and
2. it is **validated through the existing enrichment machinery** (the Lusha
   search-and-enrich waterfall), which is the operator's stated mechanism: *"can be validated
   using the enrichment machinery e.g. Lusha"*.

A weaker source, or a person the waterfall cannot confirm, is **held**, not sent.

**Why:** a person on the company's own site is self-attested; a person found by search is a
third-party claim and can be the wrong person of that name — the `craig.smith@thehartford.com`
case that drove G-62-7. Source rank alone is not enough to promote such a claim, so the
existing waterfall is what earns it the right to send.

**How to apply:** the existing G-62-7 email-domain relatedness rule and the emailless hold
still apply on top — this decision ADDS a gate, it never removes one. Do not weaken
`partition_for_dispatch`'s required `company_domains` argument or its suffix-trap refusal.
Note the standing gating boundary from quick task 260904-5a8: `match.tier` is what
`preingest.py` → `confidence.py` → `held_queue.py` gate on, so anything this task writes into
a match verdict changes send-vs-hold behaviour and must be deliberate.

## D-5sd-02 — Source priority: an explicit ranked allowlist, curated and committed

**Decision:** the priority rule is an **explicit ranked allowlist in committed config**,
following the `FREEMAIL_DOMAINS` precedent (a committed list, mirrored where needed, pinned by
a parity test). Ranking, highest first:

1. the company's own host
2. LinkedIn
3. a named list of racing/sport industry bodies and known industry media
4. everything else — **rejected, not merely ranked last**

**Why:** deterministic, unit-testable offline against the `no_network` guard, and reviewable
in a diff. Model-judged classification was considered and rejected because it is not
reproducible and cannot be pinned by an offline test. Accepted cost: the list needs occasional
curation.

**How to apply:** rejection of an unlisted source is part of the rule, not an oversight — an
unknown domain contributes nothing. Keep the list in config, not hard-coded in a function.

## D-5sd-03 — Cost: not priced into the SUGGEST-05 ceiling, but still bounded

**Decision:** client-side Claude web search spends no provider credit and no separately-billed
API tokens, so it is **not priced into the per-company ceiling**. It is still **bounded by a
named cap on the number of searches**, mirroring `MAX_FOLLOWUP_FETCHES`.

**Why:** operator's call — the search happens in their own Claude session, so pricing it would
quote a cost that is not incurred.

**How to apply:** SUGGEST-05's invariant ("a round may spend LESS than the priced cap; it may
never spend more") continues to hold for everything it currently covers — this decision does
not widen the ceiling, it declares searches outside it. Any provider credit the D-5sd-01
validation step spends (Lusha) is NOT free and remains inside the existing priced ceiling —
do not let the "free" ruling leak onto the enrichment call it triggers.

## D-5sd-04 — This task AMENDS D-62-03, and does so narrowly: not-found only, never a refusal

**This task overturns a prior recorded decision, deliberately and with authority.** The
attachment point's own docstring at `operator-claude-plugin/scripts/suggest_contacts.py:410-412`
currently reads: *"There is no second-source branch and no search-engine fallback here."*
D-62-03 (rev 2, `62-CONTEXT.md:129-137`) is the decision behind it, and its rationale is a
PRINCIPLE rather than a scope cut:

> **Do not escalate past a refusal.** If the ladder gives up, or a page is unreachable, that is
> a result to report — not a prompt to try a search engine. Phase 53's walk run 4 recorded the
> principle verbatim: *"escalating past a refusal turns a fence into a suggestion."*

**Decision (operator, 2026-09-04):** D-62-03 conflated two different endings. They are now
separated, and only one of them gets the fallback:

| Ending | Behaviour |
| --- | --- |
| The crawl COMPLETED and found no persons — no people page, or the sitemap listed nothing usable | **Search fallback fires.** This is absence of information, not a fence. |
| The site REFUSED — 403, 401, `robots.txt` disallow, an explicit block, or otherwise unreachable | **Terminates exactly as today.** No search, no second source. The fence stays a fence. |

**Why:** the operator's directive asks for the not-found case specifically ("if sitemap based
website crawl **cannot find persons**"). Phase 53's principle is about routing around a site
that told us no, and it survives this change intact — a refusal is still terminal. Overturning
the principle wholesale was offered and declined.

**How to apply:** the refusal-vs-not-found distinction must be a real, testable branch, not a
comment — a test should prove a simulated 403/robots-disallow does NOT reach the search path
while a clean-but-empty crawl does. Update the `suggest_contacts.py:410-412` docstring: it
cites D-62-03 by name, so leaving it unchanged would make the code contradict its own recorded
decision. Record the amendment where D-62-03 lives, rather than silently diverging from it.

## D-5sd-05 — "Strong source" stops at tier 2: own-host and LinkedIn only

**Decision (operator, 2026-09-04):** in D-5sd-01's promote gate, only **tier 1 (the company's
own host)** and **tier 2 (LinkedIn)** qualify as a strong source. A **tier-3** industry-body or
industry-media result is still collected, still ranked, still shown — but it is **always held
for the operator**, never sendable, however confidently the waterfall validates it. Tier 4 is
rejected outright per D-5sd-02 and never reaches this gate at all.

**Why:** industry sites frequently name people **historically** — a committee list from 2019, a
race-day programme, an archived media release. The person can be entirely real and the Lusha
validation entirely successful, and the claim can still be stale: validating that a person
exists does not prove they still hold that role at that company. Tier 1 and tier 2 are
self-attested and current in a way a third-party mention is not.

**How to apply:** tier-3 results are valuable and must NOT be discarded — the hold pile is
where they belong, with the source URL in the reason so the operator can judge. Do not
"upgrade" a tier-3 result on the strength of a waterfall confirmation; the confirmation and
the tier are independent conditions and BOTH must hold for sendable.

## D-5sd-06 — Cap exhaustion is a not-found ending, so the fallback fires

**Decision (operator, 2026-09-04):** D-5sd-04's table named two endings; there is a third.
When the crawl neither found persons nor was refused, but simply **exhausted its fetch budget**
(`MAX_FOLLOWUP_FETCHES`), the search fallback **fires** — cap exhaustion is treated as
not-found.

**Why:** hitting the cap is a budget limit we imposed on ourselves, not a fence the site put
up. Nobody refused us; we stopped looking. That is materially closer to "found nothing" than
to "told no", so Phase 53's fence principle is not engaged.

**How to apply:** this makes THREE dispositions the `eligible_after_ladder` predicate must
separate — refused (ineligible), empty (eligible), cap-exhausted (eligible) — not two. Keep the
predicate **fail-closed**: an `attempts` entry whose disposition is unknown or absent must be
treated as INELIGIBLE, so a transcription gap can never silently open the search path.
