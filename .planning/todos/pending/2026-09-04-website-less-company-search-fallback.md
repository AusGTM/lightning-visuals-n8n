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
