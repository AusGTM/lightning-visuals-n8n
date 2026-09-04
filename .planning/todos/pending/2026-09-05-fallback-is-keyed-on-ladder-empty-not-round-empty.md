---
created: 2026-09-05T00:10:00.000Z
updated: 2026-09-05
title: the search fallback fires on LADDER-empty, but the operator's intent is ROUND-empty — and the ladder stops at the first page that yields anyone, not the best
area: operator-plugin
severity: major
files:

  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/scripts/search_fallback.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The gap

> "Shouldn't it loop back to the ladder if the ultimate result is nothing? Until it exhausts
> the bottom rung web_search and then it can return nothing." — operator, 2026-09-05

D-5sd-04 defines the eligible ending as *"the crawl COMPLETED and found no persons"* —
**ladder**-level. `eligible_after_ladder(attempts)` reads only the ladder's own attempt
dispositions. The operator's intent is **round**-level: nothing usable reached the far end.

Both live rounds ended with zero sendable rows and the fallback never became eligible,
because in both the ladder itself succeeded.

## A SECOND, independent defect found while confirming this

`SKILL.md:101` and `:299`: the ladder stops *"at the first one that yields people."* **First,
not best.** A club whose contact page names one receptionist, while `/board/` lists the whole
committee, stops at the receptionist and never reads `/board/`. This is not about search at
all, and it is arguably the more valuable of the two fixes.

## Where a loop-back would NOT have helped — read before designing a blanket retry

Neither observed round would have been rescued by re-entering the ladder or by searching. A
naive "retry until search is exhausted" buys nothing on the two real cases and spends fetches
and Lusha credits to reach the same zero.

| Round | Ladder result | Why zero | Would loop-back/search help? |
| --- | --- | --- | --- |
| Brisbane Roar | 3 real staff, right page | role matcher returned `None` for `Marketing` / `Media` / `Sponsorship` | **No.** Search re-finds the same people with the same titles; the same matcher drops them again. Fix is the matcher. |
| Roma Turf Club | 16 real committee members, right page | one row had no email; the other's waterfall email was a different Craig Smith at `thehartford.com` | **No.** Search cannot produce a club-domain email — the WATERFALL supplies emails, not the ladder. Fix is the alternate-domain set. |

## So the fix is re-entry keyed on the CAUSE, not a blanket retry

- **No people found at all** -> search fallback. Today's rule; correct, keep.
- **People found, none classified** -> the matcher, not more fetching.
  `2026-09-04-role-filter-drops-one-word-titles.md`.
- **People found, all held on email** -> the alternate-domain set, not more fetching.
  `2026-09-04-a-company-can-have-more-than-one-domain.md`.
- **People found but thin** (fewer than the cap, or a page that yielded one name where the
  sitemap still lists an unread `/board/`-shaped candidate) -> **continue the ladder.** This
  is the case the "first, not best" defect above creates, and the only one where more
  fetching is the right answer.

A single `round_empty` boolean would collapse these four into one and would spend on the two
where spending cannot help. Design the re-entry to name its cause.

## Three hard constraints on any implementation

1. **A refusal stays terminal.** D-5sd-04's fence principle survives whatever re-entry is
   built: re-entering must re-check dispositions, and a ladder containing a `refused` attempt
   must never reach the search path by a second route. The order-free refusal check is already
   pinned by test; a re-entry that bypasses `eligible_after_ladder` would bypass that too.
2. **The caps do not reset.** `MAX_FOLLOWUP_FETCHES` and `MAX_FALLBACK_SEARCHES` bound the
   WHOLE round for a company, not one pass. A loop-back that re-budgets is an unbounded crawl
   wearing a bounded one's name. `cap_exhausted` must stay a terminal, eligible ending — not a
   trigger to try again.
3. **It cannot literally be a loop.** No plugin script may contain a `while` loop, enforced by
   `tests/test_report_sufficiency.py::_has_while_loop` over every script including these.
   Re-entry must be expressed as a bounded, non-looping construct (a fixed-length pass list, or
   a single second pass), which is a constraint on the design, not an afterthought.

## Why this also explains the UAT

`260904-QUICK-UAT.md` test 8 is skipped after TWO live attempts, both because the ladder
succeeded. On this segment — AU sporting clubs, which reliably publish a committee or contact
page — ladder-empty is rare while round-empty is common. Keying the fallback on the rarer event
is why the code path has never run outside its offline tests.
