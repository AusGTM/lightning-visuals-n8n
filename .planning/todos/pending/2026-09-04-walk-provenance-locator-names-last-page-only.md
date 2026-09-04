---
created: 2026-09-04
resolves_phase: null
source: 64-REVIEW.md WR-01
severity: warning
---

# A synthesised row's provenance locator names the last page fetched, not the page the person came from

## What

`suggest-contacts/SKILL.md` step 7 computes a single `fetched_url = pages[-1]["url"]` per
company and passes that one value into `synthesise_rows` for every person in the company's
unioned `walk["selected"]` list. Once phase 64 made the walk span more than one page, a
person found on the pasted `/contact` page is attributed to whatever page happened to be
fetched last (e.g. `/board/`).

## Why it matters

Phase 64's own threat model claims (T-64-05) that per-person page attribution is preserved
across a multi-page walk. It is not. The provenance `locator` written to HubSpot is
therefore wrong for every person who was not found on the final page of the walk — the
common case for exactly the receptionist-plus-board scenario the phase exists to serve.

## Why it was not fixed in phase 64

Fixing it properly requires either:

- extending `walk_pages`' return shape to carry a per-person source URL — but the phase's
  must-have artifact list pins that return to exactly six keys
  (`people`, `selected`, `dropped`, `scores`, `ended`, `bar`); or
- calling `synthesise_rows` once per page instead of once per company, which changes the
  documented step-7 sequence again.

Both are design changes beyond a review fix. Deferred deliberately rather than improvised.

## Where to pick it up

- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — the `fetched_url` line in step 7
- `operator-claude-plugin/scripts/suggest_contacts.py` — `walk_pages`' `scores` list already
  carries per-page `url`, and the fold already knows which page each newly-admitted person
  came from; a `source_url` on each admitted person is the smallest available seam
- Full finding text: `.planning/phases/64-the-ladder-stops-at-the-best-page-not-the-first/64-REVIEW.md` § WR-01

Set `resolves_phase` when a phase actually takes this on. Do not tag it speculatively —
`close_phase_todos` closes on the key alone.
