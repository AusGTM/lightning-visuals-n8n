---
quick_id: 260904-5sd
type: execute
status: complete
subsystem: operator-claude-plugin
tags: [suggest-contacts, web-search-fallback, source-allowlist, send-gate, d-62-03-amendment]

requires:
  - operator-claude-plugin/scripts/url_fallback.py (_canonical_authority, the ladder it falls back from)
  - operator-claude-plugin/scripts/suggest_contacts.py (synthesise_rows, partition_for_dispatch)
  - operator-claude-plugin/scripts/role_classify.py (the shipped-config loader idiom)
provides:
  - operator-claude-plugin/scripts/search_fallback.py (eligible_after_ladder / rank_results / hold_weak_sources + a two-verb CLI)
  - operator-claude-plugin/config/source_allowlist.yaml (the committed ranked source list)
  - suggest_contacts.synthesise_rows(..., source_tier=N) -> provenance.source_tier
affects:
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md (steps 5, 8, 9)
  - .planning/phases/62-suggest-the-contacts-nobody-named/62-CONTEXT.md (D-62-03 amended)

tech-stack:
  added: []          # no package installed; PyYAML was already a shipped dependency
  patterns:
    - "model does the I/O, Python decides: the model writes a scratch JSON, a pure CLI reads it (the url_fallback.py --filter idiom)"
    - "shipped-config loader mirroring role_classify.load_families: path param, yaml imported inside the function, a named error rather than an empty list"
    - "label-boundary host matching (host == listed or host.endswith('.' + listed)) — the suffix trap, both directions"
    - "fail-closed closed vocabulary: only an affirmative value opens a path"

key-files:
  created:
    - operator-claude-plugin/scripts/search_fallback.py
    - operator-claude-plugin/config/source_allowlist.yaml
    - operator-claude-plugin/tests/test_search_fallback.py
    - .planning/todos/pending/2026-09-04-website-less-company-search-fallback.md
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - .planning/phases/62-suggest-the-contacts-nobody-named/62-CONTEXT.md

decisions:
  - "The tier rides provenance, never the row — synthesise_rows asserts canonical row keys and write_dispatch_csv raises on a non-canonical one, the same constraint that forced source_by_field to be request-level."
  - "hold_weak_sources is a SECOND records-level pass; partition_for_dispatch is byte-identical, keeping its required company_domains argument and its suffix-trap refusal."
  - "Operator-facing prose says 'rank', not 'tier' — a shipped D-10b guard reserves that word for the ICP tier. The guard was not widened."
  - "A mis-stamped provenance fails OPEN (passes as a ladder row) rather than holding every existing round; stated in the docstring rather than hidden."

metrics:
  duration: ~50 min
  completed: 2026-09-04

actuals:
  tokens: 25519      # chars/4 over the realized diff, base 385ced4..HEAD
  tasks: 3
  commits: 6
---

# Quick Task 260904-5sd: Sitemap-crawl fallback to client-side Claude web search — Summary

When the sitemap ladder finishes without finding a person, the suggestion round may now search
the web — but only for the two endings that are absence of information rather than a fence, only
across a committed ranked allowlist, and only a company's own host or LinkedIn can produce a
sendable row.

## What was built

**`scripts/search_fallback.py`** — three pure decisions and a two-verb CLI, in a module of its
own because a search result is off-host by definition and cannot live behind `url_fallback.py`'s
`same_host` property:

| Function | Decides |
| --- | --- |
| `eligible_after_ladder(attempts)` | May the round look anywhere else at all? Fail-closed over the `empty` / `cap_exhausted` / `refused` vocabulary. |
| `rank_results(results, company_url)` | Which of the search's URLs may be fetched, and what is each source's claim worth? Rank 1 own host, 2 LinkedIn, 3 allowlist, 4 = rejection. |
| `hold_weak_sources(records, sendable, held)` | May a person found that way be SENT, or only shown? |

**`config/source_allowlist.yaml`** — LinkedIn alone at rank 2; 17 `[ASSUMED]` racing/sport
bodies and trade outlets at rank 3, each with its one-line justification. Rank 1 is computed per
company and is never listed; rank 4 is the absence of a match.

**The seam** — `synthesise_rows` gained `source_tier=None`. Omitted (every existing call site) the
provenance is byte-identical; passed, the record declares `input: "suggest_contacts_web_search"`
and its own tier, which is the only thing `hold_weak_sources` reads.

**SKILL.md** — the narrowed refusal rule, a three-row disposition transcription table, the
`cap_exhausted` instruction (without it D-5sd-06 has no source and never fires), the fallback's
two CLI verbs, and a fifth `reason_code` group in the step-9 report.

## The truths, and where each is pinned

| Truth | Pinned by |
| --- | --- |
| A `refused` disposition anywhere never reaches the search path | `test_search_fallback.py::test_a_refusal_after_an_empty_rung_...` + `..._before_an_empty_rung_...` (order-free), and at the composition level by the refused company in `test_the_documented_round_pipeline_drives_its_real_joins_end_to_end` |
| Clean-but-empty AND cap-exhausted both reach it | `test_a_single_empty_attempt_is_eligible`, `test_a_single_cap_exhausted_attempt_is_eligible`, `test_empty_rungs_ending_in_cap_exhaustion_are_eligible` |
| An unknown/absent/unreadable disposition is INELIGIBLE, never a raise | `test_an_unknown_disposition_value_is_ineligible`, `test_an_attempt_with_no_disposition_key_is_ineligible_and_does_not_raise` |
| An empty `attempts` list is INELIGIBLE, saying nothing establishes the crawl completed | `test_an_empty_attempt_list_is_ineligible_because_nothing_establishes_the_crawl_ran` |
| Only rank 1/2 can be sendable; rank 3 is always held with its URL in the reason | `test_a_tier_three_search_record_is_held_with_its_source_url_in_the_reason` |
| The two gates are independent and BOTH must hold | `test_suggest_contacts.py::test_the_tier_gate_and_the_waterfall_gate_are_independent_and_both_must_hold` — the same person, the same successful merge, the same related-domain email: sendable at rank 2, held at rank 3 |
| A host on no rank is REJECTED, naming it | `test_a_host_on_no_tier_is_rejected_with_a_reason_naming_it`, and at the composition level by company `tier2-1`'s two search results — the unlisted host rejected alongside the accepted LinkedIn one |
| Suffix trap, both directions | `test_a_linkedin_suffix_trap_host_is_rejected`, `test_a_company_host_suffix_trap_is_rejected_too`, `test_a_real_subdomain_of_the_companys_host_is_tier_one` |
| A ladder-sourced record's behaviour is byte-identical | `test_a_ladder_sourced_record_is_passed_through_untouched`, `test_a_ladder_sourced_record_passes_the_new_gate_unchanged`, `test_synthesise_rows_without_a_source_tier_is_byte_identical_to_today` |
| `partition_for_dispatch` keeps `company_domains` and its suffix-trap refusal | its SIGNATURE by the plan's own assertion; its BEHAVIOUR by `test_a_ladder_sourced_record_passes_the_new_gate_unchanged` and by every pre-existing `partition_for_dispatch` test passing unmodified — no test of it was touched |
| Suites at/above baseline; `n8n/` zero diff | see Verification |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] D-10b's shipped guard bans the substring "tier" from every skill body**

- **Found during:** Task 3, on the first full-suite run
- **Issue:** `tests/test_report_enrichment.py::test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder` scans every file under `skills/` for `icp` or `tier`, case-insensitively. In this system "tier" means the ICP tier and the plugin must never show one (D-10b). The plan's source-*tier* vocabulary collides with it by name only — the concepts are unrelated.
- **Fix:** the guard was **not** widened (its own docstring says the single exemption is by name and "not a general allowance for any future skill"). `skills/suggest-contacts/SKILL.md` now says **rank** throughout — prose, comments, and the block's fifth argument, passed positionally as `source_rank`. The internal vocabulary (`source_tier`, `STRONG_TIERS`, `provenance.source_tier`) is unchanged, exactly as the plan specifies, because none of it is operator-facing.
- **Also applied, same spirit:** `hold_weak_sources`'s hold reason lands in the operator's step-9 report, so its prose says "source rank 3" rather than "tier 3". A comment in the module records why the two vocabularies differ, so a reviewer does not "fix" the apparent inconsistency.
- **Files modified:** `skills/suggest-contacts/SKILL.md`, `scripts/search_fallback.py`
- **Commit:** `b0417cd`

**2. [Rule 1 - Bug] `source_tier=1.0` was accepted**

- **Found during:** Task 2, by the parametrised refusal test
- **Issue:** `1.0 in (1, 2, 3)` is `True` in Python, so a float slipped through the membership check and landed a non-int tier in `provenance`, which `hold_weak_sources`'s `isinstance(tier, int)` would then read as unreadable — a silent downgrade to held, two modules away from the mistake.
- **Fix:** an explicit `isinstance(source_tier, int)` check ahead of the membership test, so the refusal names the value at the site that received it.
- **Commit:** `d2cb70d`

**3. [Rule 1 - Bug] the documented block bound `source_rank` only on the search path**

- **Found during:** the final review pass over Task 3's own output
- **Issue:** `source_rank` was assigned only inside the `if not people and verdict["eligible"]:` branch, so a model following step 8's block literally for a company whose ladder DID find people would pass an unbound name to `synthesise_rows`. The same block also called `eligible_after_ladder(attempts)` unconditionally — asking whether to escalate past a ladder that had not given up.
- **Fix:** `source_rank = None` initialised before the branch (which is the byte-identical ladder-provenance case), and the eligibility call nested under `if not people:`. `parse_calls` records calls wherever they sit, so the derived `COVERED` tuple is unchanged — re-derived and confirmed rather than assumed.
- **Files modified:** `skills/suggest-contacts/SKILL.md`
- **Commit:** `245a327`

### Not a deviation, recorded for clarity

`.planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md` is modified in the
working tree by something outside this task (grounding notes appended to an unrelated todo). It
was left untouched and uncommitted, per the scope boundary.

## Verification

| # | Check | Result |
| --- | --- | --- |
| 1 | Plugin suite | **2430 passed, 5 skipped** (baseline 2365/5; +65 are this task's own) |
| 2 | Root suite | **4178 passed, 154 skipped** (baseline 4113/154; +65, the same plugin tests) |
| 3 | Node suite | **870 pass, 0 fail** — untouched |
| 4 | `git diff -- n8n/` | empty |
| 5 | `plugin.json` / `CHANGELOG.md` diff | empty — the version cut happens at a later documentation sweep |
| 6 | `role_vocabulary.yaml`, `62-UAT.md`, `62-VERIFICATION.md` | untouched |

Offline throughout: no HubSpot call, no Anthropic call, no provider credit, no n8n deploy, no
arming. The autouse `no_network` guard is satisfied by construction — `search_fallback.py` holds
no HTTP client and its import set is AST-pinned — not by a mock.

## Known Stubs

None. Two limits are stated rather than stubbed, both of the same transcription class and both
recorded in the code that carries them:

- **Transcription fidelity is not verifiable offline.** The scratch JSON is the model's own
  record of what a search returned. Mitigation, not a fix: the ranker reads the URL **host** and
  nothing else, so a snippet can never become a row field, and a fabricated URL simply fails to
  fetch or yields nobody (`rank_results`' docstring).
- **A mis-stamped provenance fails OPEN.** A search-sourced record whose provenance is not
  stamped passes as a ladder record. Failing the other way would hold every ladder row in every
  round (`hold_weak_sources`' docstring; threat register T-5sd-06, disposition `accept`).

## Threat Flags

None. Every mitigation in the plan's register landed: T-5sd-01 (label-boundary matching, both
traps pinned), T-5sd-02 (fail-closed disposition), T-5sd-03 (host-only ranking, SKILL.md rule),
T-5sd-04 (independent gates, `partition_for_dispatch` untouched), T-5sd-05 (allowlist + cap).
T-5sd-06 and T-5sd-SC were `accept` dispositions and remain so; no package was installed.

## Follow-ups filed

- `.planning/todos/pending/2026-09-04-website-less-company-search-fallback.md` — a company with
  no usable website terminates at `discovery_plan`'s empty-candidates branch and never reaches
  the attachment point, and has no rank 1 to compute against. Arguably the higher-value case;
  scoped out deliberately, not missed.

## Self-Check: PASSED

All created files exist on disk; all five commit hashes (`56476de`, `627a72f`, `1f50af7`,
`d2cb70d`, `b0417cd`, `245a327`) are present in `git log`.
