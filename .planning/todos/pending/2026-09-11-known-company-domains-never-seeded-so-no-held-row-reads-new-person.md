---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-11
title: known_company_domains is never seeded by either caller, so no held row reads new_person end to end
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/review-triage/SKILL.md
  - operator-claude-plugin/scripts/held_queue.py
kind: design
decision_needed: >
  `held_queue.classify_facet(entry, known_company_domains)` (quick 260911-w6p) reads
  `new_person` only when the entry's email domain is in the caller-supplied set. Both
  shipped callers seed that set EMPTY: enrich-before-ingest step 6 (`known_company_domains
  = set()`, "nothing confirmed yet this run") and review-triage step 2 (`set()`, "grows
  during this sitting", operator-supplied only). So the F2 ruling's headline case — Jimmy
  Busteed, `jbusteed@australianturfclub.com.au`, ATC `9605284724` already in HubSpot —
  reads `needs_company` on both surfaces today, never `new_person`, and the "create all N"
  ready answer never has a row to offer. Which legitimate source should seed the set
  automatically: (a) enrich-before-ingest step 2's own match-confirmed company domains
  from the same run, (b) a HubSpot companies search by domain at facet time (one read per
  distinct domain, D-61-07 closed vocabulary `hubspot_lookup`), or (c) keep operator
  statement only and change the ruling's headline? (a) is free and already in memory at
  step 6; (b) is the only one that covers review-triage's cold start.
---

## Found at the close of quick batch 260911-w6n (2026-09-11), coordinator verification

Grep on the final tree:

```
operator-claude-plugin/skills/review-triage/SKILL.md:98:   known_company_domains = set()  # grows during this sitting -- see 2c below
operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:869:   known_company_domains = set()  # nothing confirmed yet this run -- w6p's own safe
```

Each item shipped exactly what its plan said. w6p's own summary states the default:
"with no resolved company domains supplied, a usable-email entry reads `needs_company` —
the safe direction, never `new_person` by default". w6q's summary records the
plan-vs-shipped reconciliation (the plan assumed a `company`-column discriminator; the
shipped classifier discriminates on domain existence). Neither w6q nor w6r was asked to
seed the set, so neither did. The mechanism is correct and review-first; the gap is that
nothing populates it without an operator typing a domain in review-triage step 2c.

Not a defect against any single item — a seam between three of them. Ruling needed before
the second-round `contact-upload` UAT CSVs (UAT doc §1d) are run, because that run is the
first chance to observe a `new_person` row live.
