---
phase: quick-260911-ss7
plan: 01
subsystem: operator-claude-plugin
tags: [cost-model, lusha, cost-rates, changelog, release]

requires: [260911-ss4, 260911-ss5, 260911-ss6]
provides:
  - "operator-claude-plugin/config/cost_rates.json: lusha_contacts_first_time_enrich
    raised to 7 (measured worst case, n8n execution 12372, 2026-09-11), a ceiling
    every operator-facing price (preview_enrichment cost block, write_grant envelope,
    suggest-contacts stage-2 line) now quotes from the same rate table"
  - "docs/LUSHA-V3-CONTRACT.md: new §7.1 dated amendment recording the 12372
    observation with evidence and a labelled hypothesis; A3 verdict row and the
    §11 cost-lever bullet amended in place, not deleted; §1 status header points
    at the amendment"
  - "operator-claude-plugin/.claude-plugin/plugin.json 0.46.0, CHANGELOG.md one
    new section naming F1/F9/F10/F11"
affects: [preview_enrichment, write_grant, suggest-contacts, enrichment_cost_ledger]

actuals:
  tokens: 4350
  tasks: 3
  commits: 3
  plan_head_before: b47d2296c63ab6b7367b66ae25b5092cfdb6bd7a

tech-stack:
  added: []
  patterns:
    - "one dated constant, not a rate-learning mechanism — the plan's explicit
      out-of-scope boundary; no code reads creditsCharged off a run"
    - "measured_on stays fixed while the new observation's date rides only the
      one rate entry's own citation, so the file-level staleness disclosure keeps
      over-stating rather than under-stating every other rate's age"

key-files:
  created: []
  modified:
    - operator-claude-plugin/config/cost_rates.json
    - operator-claude-plugin/tests/test_cost_guard.py
    - operator-claude-plugin/tests/test_cost_guard_suggestion.py
    - docs/LUSHA-V3-CONTRACT.md
    - scripts/enrichment_cost_ledger.py
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md

key-decisions:
  - "The rate is quoted as a measured worst-case CEILING (confidence field says so
    verbatim, since confidence renders to the operator unmodified and is never
    branched on in code) — never as a flat per-contact invoice. No A/B exists yet
    at first-time-call granularity for reveal width; §7.1 names that as an open
    question rather than resolving it."
  - "docs/LUSHA-V3-CONTRACT.md's A3 row and its cost-lever bullet are amended
    IN PLACE (original text kept, amendment appended), per the repo's as-built-delta
    convention — never silently overwritten, so a reader who stops at the original
    line still gets the caveat rather than a stale unqualified claim."
  - "scripts/build_cloud_workflows.py lines 6571/6607-6608 are named in the doc
    amendment as now citing an incomplete (not wrong) §6 claim, but left unedited —
    a comment-only fix there is backend scope under the regeneration-parity rule."

patterns-established: []

requirements-completed: []

coverage:
  - id: D1
    description: "cost_rates.json lusha_contacts_first_time_enrich raised 1 -> 7;
      RED observed on the rate-table value assertion, the 10-contact estimate,
      and a new ceiling test before the JSON changed; all green after; companies
      rate, stored-id zero, apollo null, and measured_on unchanged; suggestion-line
      sibling literal also updated."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard_suggestion.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/LUSHA-V3-CONTRACT.md records the 12372 observation with
      evidence, labels the reveal-width cause a hypothesis with what is missing
      named, amends A3 and the cost-lever bullet in place, and points at the
      amendment from §1; scripts/enrichment_cost_ledger.py's ESTIMATES entry and
      operator.local.example.json's cost note match the new figure and citation."
    requirement: null
    verification:
      - kind: unit
        ref: "tests/test_enrichment_cost_ledger.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/"
        status: pass
    human_judgment: false
  - id: D3
    description: "plugin.json reads 0.46.0; CHANGELOG.md carries exactly one new
      ## [0.46.0] section naming F1, F9, F10, F11 in operator terms, derived from
      the three sibling SUMMARYs plus this plan; ## [Unreleased] still present
      and empty above it; version and CHANGELOG land in the same commit."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-09-11
status: complete
---

# Quick Task 260911-ss7: F10 — cost model, grant pricing and preview enrichment pricing Summary

**Lusha's first-time contacts rate moved from a flat 1 credit to a measured worst-case
ceiling of 7 (n8n execution 12372, 2026-09-11), the contract of record now carries the
observation with its evidence and an explicitly hypothetical cause, and plugin 0.46.0
ships with one CHANGELOG section naming F1/F9/F10/F11.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3 completed
- **Files modified:** 8 (0 created, 8 modified)

## Accomplishments

- Raised `lusha_contacts_first_time_enrich` in `operator-claude-plugin/config/cost_rates.json`
  from `1` to `7`, rewriting its `citation` to carry both measurements (the 2026-07-30
  no-reveal probe and the 2026-09-11 execution-12372 reveal-inclusive call) and its
  `confidence` to name the number a measured worst case rather than a flat price — the
  field that renders to the operator verbatim. `measured_on` stayed at `2026-07-30`
  deliberately; the new date lives only in this one entry's citation.
- Added a new ceiling test (`test_the_first_time_contacts_rate_is_a_ceiling_over_every_observed_charge`)
  pinning that the rate stays `>=` the largest observed charge (7) and strictly `>` the
  stored-id re-enrich rate (0), naming execution 12372 in its docstring.
- Both RED assertions were observed failing (`1 == 7`, `10 == 70`) before the JSON changed;
  a third existing literal in `test_cost_guard_suggestion.py` (`assert contact_rate == 1`)
  was found and updated the same way — a redundant literal check, not a direction assertion,
  so updating it does not weaken the ceiling relationship the sibling assertions on the same
  line already assert dynamically.
- Recorded the observation in `docs/LUSHA-V3-CONTRACT.md`: a new dated §7.1 subsection
  (mirroring §3.1's convention) with the evidence (execution 12372's `billing.creditsCharged`
  7/0, balance 3860 → 3853), what made the 2026-07-30 probes' 1-credit figure a different
  request shape (no `reveal` key at all — confirmed by reading `scripts/probe_lusha_v3.py`'s
  P1 shape-D and T2b bodies directly), the reveal-width explanation stated as a hypothesis
  (plausible from §6's sticker prices summing to 7; not isolated because the reveal value
  is derived from the backend's `REVEAL_MAP` rather than read off 12372's own runData), and
  a named open question (a first-time reveal-width A/B, unspent). The §10 A3 row and the
  §11 cost-lever bullet are amended in place — original text kept, an `AMENDED 2026-09-11`
  clause scoping each to the stored-id lane. §1's status header now points at §7.1.
  `scripts/build_cloud_workflows.py` lines 6571/6607-6608 are named as citing an now-
  incomplete §6 claim, deliberately left unedited (backend/regeneration-parity scope).
- Updated `scripts/enrichment_cost_ledger.py`'s `lusha_contacts_first_time_enrich` ESTIMATES
  entry (value 1→7, citation naming the §7.1 amendment) and
  `operator-claude-plugin/config/operator.local.example.json`'s cost note to the same
  worst-case figure, dated — leaving the companies figure, stored-id zero, ZoomInfo,
  Apollo-unknown, and Anthropic clauses untouched. `README.md` left untouched (it quotes
  no number).
- Cut plugin `0.46.0`: one `## [0.46.0] - 2026-09-11` CHANGELOG section under
  `## [Unreleased]`, with a preamble naming the batch (`260911-ss4`/`ss5`/`ss6`/`ss7`) and
  one bolded bullet per finding (F1, F9 under `### Fixed`; F10, F11 under `### Changed`),
  each in operator terms and each derived from its sibling SUMMARY (never invented).
  `plugin.json`'s `version` bumped in the same commit.

## Task Commits

Each task was committed atomically:

1. **Task 1: raise the Lusha first-time contacts rate to the observed 7** - `f078df7c` (feat)
2. **Task 2: record the observation in the contract of record, and level the two prose copies** - `9a77be28` (docs)
3. **Task 3: cut plugin 0.46.0 with one CHANGELOG section naming F1/F9/F10/F11** - `058ee899` (feat)

## TDD Evidence

Task 1's RED, observed before `cost_rates.json` changed:

```
FAILED test_load_rates_returns_version_measurement_date_and_rates
    assert rates["rates"]["lusha_contacts_first_time_enrich"]["value"] == 7
E   assert 1 == 7

FAILED test_the_first_time_contacts_rate_is_a_ceiling_over_every_observed_charge
    assert first_time >= largest_observed_charge
E   assert 1 >= 7

FAILED test_a_contacts_batch_with_lusha_uses_the_contact_rate
    assert estimate["provider_credits"]["lusha"]["credits"] == 70
E   assert 10 == 70
```

All three green after the JSON edit; one further sibling literal
(`test_cost_guard_suggestion.py::test_stage2_credit_ceiling_equals_companies_times_cap_times_contact_rate`'s
`assert contact_rate == 1`) found by the full-suite run and updated to `== 7` — a redundant
literal, not a direction assertion (the relationship assertions on the same test already
read `contact_rate` dynamically).

## Deviations from Plan

None — plan executed exactly as written. Task 2's action anticipated one additional
sibling-literal fix outside its own file list (`test_cost_guard_suggestion.py`), which
Task 1's own `<action>` instruction already covered ("Fix any further assertion that
priced contacts x Lusha at 1 by updating its expected number") — applied there, in Task 1,
not deferred.

## Known Stubs

None.

## Threat Flags

None beyond the plan's own threat model (T-ss7-01 through T-ss7-05, all `mitigate` or
`accept`, none escalated) — no new network endpoint, auth path, or schema change at a
trust boundary was introduced.

## Self-Check: PASSED

- `operator-claude-plugin/config/cost_rates.json` — FOUND, `lusha_contacts_first_time_enrich.value` == 7
- `docs/LUSHA-V3-CONTRACT.md` — FOUND, §7.1 present, A3 row and cost-lever bullet amended
- `scripts/enrichment_cost_ledger.py` — FOUND, ESTIMATES entry == 7
- `operator-claude-plugin/.claude-plugin/plugin.json` — FOUND, version == 0.46.0
- `operator-claude-plugin/CHANGELOG.md` — FOUND, exactly one `## [0.46.0]` section
- Commit `f078df7c` — FOUND (`git log --oneline --all | grep f078df7c`)
- Commit `9a77be28` — FOUND (`git log --oneline --all | grep 9a77be28`)
- Commit `058ee899` — FOUND (`git log --oneline --all | grep 058ee899`)
- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` — 2953 passed, 5 skipped
  (baseline was 2952 passed, 5 skipped; +1 new ceiling test)
- `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q` — 43 passed
- `git diff --stat -- n8n/ src/ scripts/build_cloud_workflows.py` — EMPTY
- `scripts/todo_triage.py --since b47d2296` — `counts: {} | debt (defect): 0`, no
  untriaged todo created
