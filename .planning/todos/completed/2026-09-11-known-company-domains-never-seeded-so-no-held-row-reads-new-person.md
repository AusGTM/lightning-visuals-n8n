---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-12
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

## Resolved by Phase 71 (2026-09-12)

Closed by **D-71-01..03** (option (a), stamped at persist time — not (b)'s per-facet HubSpot
lookup, and not (c)'s "keep it operator-only"): the seed is written onto the held entry itself
at `enrich-before-ingest` step 5 persist time, once, so `classify_facet` never needs a caller
to have supplied anything at read time.

- **`preingest.confirmed_company_domains(classified, company_spec=None)`** (plan 02, Task 2)
  folds step 2's own `auto_matched` rows (including a step-3-confirmed row moved into that
  bucket) and an optional company-row confirm-table spec into a `domain -> source` map, both
  words members of `held_queue.COMPANY_KNOWN_SOURCES` (`step2_match` / `step2_company_row`).
  Zero new lookups — this is exactly option (a), collecting what step 2 already knows in
  memory, plus the company-row fallback the open question's option (b) would otherwise have
  had to cover with a live HubSpot read.
- **`held_queue.build_entry(..., company_known=None)`** (plan 01, Task 2) accepts the optional
  `{"domain","source"}` stamp; `enrich-before-ingest` step 5's persist fence stamps it onto
  every held entry from the merged row's own cleaned email domain looked up in
  `confirmed_domains`.
- **`held_queue.stamped_domains(entries)`** (plan 01) is the one derivation both surfaces fold
  the stamp into `known_company_domains` through — `enrich-before-ingest` step 6 and
  `review-triage` step 2b now read `held_queue.stamped_domains(held_entries)` instead of a
  hardcoded `set()`. `classify_facet()` itself is byte-for-byte unchanged; only what feeds its
  `known_company_domains` argument changed.

This closes the cold-start half of the original question too: `review-triage`'s read never
needs the operator to have said anything in-conversation, because the stamp already lives on
the entry on disk.

**Covering tests** (by nodeid, from the 71-01/71-02 SUMMARY `coverage:` blocks):
- `operator-claude-plugin/tests/test_held_queue.py#test_company_known_stamp_round_trips_through_save_and_load`
- `operator-claude-plugin/tests/test_held_queue.py#test_stamped_domains_collects_only_present_valid_stamps`
- `operator-claude-plugin/tests/test_preingest_match.py#test_an_auto_matched_rows_own_email_domain_is_confirmed_under_step2_match`
- `operator-claude-plugin/tests/test_preingest_match.py#test_a_step_3_confirmed_row_moved_into_auto_matched_contributes_identically`
- `operator-claude-plugin/tests/test_preingest_match.py#test_every_confirmed_company_domains_value_is_a_member_of_company_known_sources`
- `operator-claude-plugin/tests/test_preingest_match.py#test_when_both_sources_name_the_same_domain_the_company_row_word_wins`
- `operator-claude-plugin/tests/test_held_facet_render_composition.py#test_step_6_fence_loads_the_queue_and_facets_what_it_loaded_not_a_dict_literal`
- `operator-claude-plugin/tests/test_review_triage_facets.py#test_one_held_new_person_end_to_end_read_render_create_confirm_mark`
