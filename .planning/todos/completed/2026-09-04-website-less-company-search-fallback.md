---
created: 2026-09-04T00:00:00.000Z
updated: 2026-09-04
title: the web-search fallback never fires for a company with no usable website — arguably the higher-value case
area: operator-claude-plugin
severity: minor
files:

  - operator-claude-plugin/scripts/suggest_contacts.py:143-152
  - operator-claude-plugin/scripts/search_fallback.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The gap

Quick task 260904-5sd added a web-search fallback for a suggestion round whose sitemap
ladder finished without finding a person. It attaches at **one** point: the
`url_fallback.give_up_message` call site inside `suggest_contacts.no_candidates`, which is
where CONTEXT.md locked it.

A company with **no usable website or domain** never reaches that point. It terminates
earlier, at `discovery_plan`'s empty-candidates branch (`suggest_contacts.py:143-152`),
with `_NO_USABLE_WEBSITE_REASON` or a reason naming the unusable recorded value (a
LinkedIn URL, `"unknown"`, a value with no dot). No ladder is ever built, no `attempts`
list is ever produced, and `eligible_after_ladder` is never called.

## Why it needs its own design rather than one more call site

Two things the not-found path has, this path does not:

1. **No `attempts` record.** `eligible_after_ladder`'s whole predicate is the closed
   disposition vocabulary on the ladder's own attempts. There is no ladder here, so
   there is nothing to be eligible or ineligible about. The refusal-vs-not-found
   question does not even arise — but neither does the evidence that it does not.
2. **No tier 1.** `rank_results` computes tier 1 from the company's own host, taken from
   the ladder's pasted URL. A company with no usable website has no own-host to compute
   against, so every result would fall to tier 2 or 3 — and per D-5sd-05 a tier-3 row is
   always held. In practice such a company could only ever produce LinkedIn-sourced
   sendable rows, which is a real design decision to make deliberately, not a fallout to
   discover in production.

## Why it is arguably the higher-value case

A company with no site on record is exactly the one a search could help most: the ladder
has nothing to work with, so today the round reports "no usable website" and moves on
with certainty rather than with a gap. RESEARCH.md §Open Questions 2 made the same
observation.

## Status

**Scoped out deliberately, not missed.** CONTEXT.md attached the fallback to the
`give_up_message` call site and nothing else, and firing at a second, structurally
different terminal is a design question the operator has not been asked.

## What a fix would need to decide

- Whether a company with no recorded website may be searched at all, or whether an
  absent website is itself a signal to skip.
- What stands in for tier 1 when there is no own-host — most likely: nothing does, and
  such a round is LinkedIn-or-held by construction.
- Whether a search-discovered domain may be written back as the company's website, which
  is a canonical write and a different ruling entirely (see the `manual_protected` todo).

## Operator ruling 2026-09-11 (resume session)

**Search, LinkedIn-or-held.** A company with no usable website MAY be searched. There is no
own-host, so no rank 1 exists for such a round; rank 2 (`linkedin.com`) rows may be
sendable, rank 3 rows are always held (D-5sd-05 unchanged). A search-discovered domain is
NEVER written back as the company's website — that is a canonical write and a separate
ruling. Every existing fence holds: `MAX_FALLBACK_SEARCHES` bounds the round, no `while`
loop, a refusal stays terminal.

## Resolved 2026-09-11 (quick task 260911-ao2)

Shipped the ruling above through the SAME cause/re-entry machinery Phase 65 built, rather
than a second call site — one new cause (`CAUSE_NO_LADDER`), one new walk ending
(`WALK_NO_LADDER`), one new keyword on the one eligibility gate (`ladder_built`).

`eligible_after_ladder` (`search_fallback.py`) gained `ladder_built=True`: an empty
`attempts` with `ladder_built=False` is eligible as absence of information; any non-empty
`attempts` alongside it is a contradiction and stays ineligible, so the flag can never
launder a recorded refusal or a recorded ladder into eligibility. `rank_results` needed no
logic change — a falsy `company_url` already makes rank 1 structurally unreachable
(`_host_matches` refuses an empty listed host) — only a docstring naming the consequence.
The CLI gained a bare `--no-ladder` flag threading the same claim through both entry
points.

`suggest_contacts.py` gained `WALK_NO_LADDER` (fifth and last of `WALK_ENDINGS`, never
produced by `walk_pages` itself — only stated by a caller with nothing to walk) and
`CAUSE_NO_LADDER` (seventh of `ROUND_CAUSES`, precedence-ordered immediately after
`CAUSE_UNKNOWN`). `round_outcome`'s `people_count == 0` arm branches on the walk's own
`ended` to pick between the two causes; the re-entry condition admits `CAUSE_NO_LADDER`
under the IDENTICAL routing-vs-terminal rule already governing `CAUSE_NO_PEOPLE_FOUND` —
all four of rows/sendable/held/fallback must be `None` — so a terminal call still cannot
route and no second route exists.

`SKILL.md` step 5's documented block guards the two ladder-only statements
(`next_candidates`, the `accepted` binding) behind `if plan["pasted_url"]:`; the no-ladder
branch initialises the walk already-ended with `WALK_NO_LADDER` so the candidate loop
iterates nothing and no ladder fetch is ever attempted. The `eligible_after_ladder` call
passes `ladder_built=bool(pasted_url)` through. Step 5 prose adds the "may still be
searched" paragraph and a `--no-ladder` CLI example; step 9's cause table gains the
`no_ladder` row.

**Two gates a website-less round still faces, both from prior rulings, unchanged:**
`partition_for_dispatch`'s `company_domains` argument stays required, so without an
operator-supplied domain every row from such a round is held as `company_domain_unknown`
— the honest consequence, documented, not fixed. And a rank-3 row is still always held
regardless of confidence (D-5sd-05).

**Two questions this ruling left explicitly open, still open:** whether a search-discovered
domain may ever be written back as the company's canonical website, and whether one may be
used as an email-relatedness alternate. Both are separate rulings, out of this scope.

Composition test: `tests/test_suggest_contacts_composition.py` drives a website-less
company through the documented loop end to end, both without an operator-supplied domain
(every row held `company_domain_unknown`) and with one (rank-2 sendable, rank-3 held
`search_source_not_strong`). Full plugin suite green throughout.
