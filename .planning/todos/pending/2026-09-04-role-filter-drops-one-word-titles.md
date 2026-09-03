---
created: 2026-09-04T21:30:00.000Z
updated: 2026-09-04
title: the suggest-contacts role filter selects 0 on any club using one-word titles — the matcher, not the vocabulary
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/role_classify.py
  - operator-claude-plugin/config/role_vocabulary.yaml
  - operator-claude-plugin/scripts/suggest_contacts.py
---

## The defect, proven live

First live `suggest-contacts` round, Brisbane Roar FC (company `285507657175`),
2026-09-04. The discovery ladder worked exactly as designed — 4 of 5 fetches, 3 named
staff found on `/about/contact-us/`. **The role filter then dropped all three:**

| Person | Title on the page | Classified |
| --- | --- | --- |
| Jordan Hayward | Marketing | `None` |
| Joseph Esposito | Media | `None` |
| Emma Hoadley | Sponsorship | `None` |

Net effect: a company whose own website names real staff in exactly the roles the operator
selected yields **0 selected**. Only an operator override rescued the round — and the two
overridden people then enriched cleanly (email from Lusha, on the club's own domain) and
landed as created+associated contacts `350028797423` and `349992218047`. So everything
downstream of the filter was fine; the filter is the whole failure.

## It is the MATCHER, not the vocabulary — do not "fix" it by deriving

`role_classify.classify_title` matches a family member's tokens **contiguously** against the
title's tokens. No shipped member is the single token `marketing`, so a one-word title
cannot match. Measured 2026-09-04 against both vocabularies:

```
curated : 'Marketing' -> None   'Media' -> None   'Sponsorship' -> None
derived : 'Marketing' -> None   'Media' -> None   'Sponsorship' -> None
```

The derived vocabulary's eight families (Director, Chief Executive, Owner, General Manager,
President, Vice President, Manager, Managing Director) are corporate multi-word labels, so
it misses too. **And adopting it is already a REJECTED decision** — quick task 260904-447,
`.planning/decisions/2026-09-04-derived-role-vocabulary-rejected.md`; a live dry run the same
day confirmed it drops 14 curated families, every racing-governance one. Deriving is not the
fix and must not be proposed as one.

## Two candidate fixes, and the trap in each

1. **Add short-form members to the curated vocabulary** — `marketing`, `media`,
   `communications`, `sponsorship`, `commercial`, `operations`, `finance`. Smallest diff,
   no matcher change, and the curated file is the live-proven one.
   *Trap:* a bare token is a much broader net. `Media` under a broadcast family and
   `Marketing` under a marketing family are fine; but check no short form collides across
   two families, since a title matching two families is ambiguity, not a match.
2. **Let the matcher accept a single-token title against a family whose label starts with
   that token** — no vocabulary edit, fixes every club at once.
   *Trap:* it silently widens EVERY existing family's reach at the same time. The
   contiguous-run rule was chosen deliberately; changing it needs its own red-before-green
   evidence that no currently-correct classification flips.

Prefer (1) unless the audit shows the short forms collide.

## Related interaction, worth checking in the same pass

The same round showed enrichment discovering a RICHER title — `Head of Marketing and
Content` — for a person whose page title was the unmatched `Marketing`. That richer string
**does** classify (`-> Head of Marketing`, verified). So a second, cheaper mitigation may
exist: classify against the enriched title rather than only the scraped one. See
`.planning/todos/pending/2026-09-04-phone-is-never-chased-only-accepted.md`, which records
that this richer title and a `seniority` of Director were both discovered and then dropped.

## Test shape

Red first, against the SHIPPED vocabulary: `classify_title("Marketing", families)` returns
a marketing family, `"Media"` returns a broadcast/communications family, and no existing
passing classification changes. Offline, no live calls.
