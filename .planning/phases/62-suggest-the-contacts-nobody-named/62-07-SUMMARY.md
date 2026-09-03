---
phase: 62-suggest-the-contacts-nobody-named
plan: 07
subsystem: contact-enrichment
tags: [suggest-contacts, url-fallback, url-normalization, hubspot-crm-properties, gap-closure]

requires:
  - phase: 62-suggest-the-contacts-nobody-named
    provides: "suggest_contacts.py's discovery_plan/next_candidates and url_fallback.py's plan_ladder/filter_candidates ladder, built in plans 62-01 through 62-06"
provides:
  - "One shared seam helper (_ladder_source) in suggest_contacts.py, used by both discovery_plan and next_candidates, that normalises a CRM website/domain into a host-bound URL before either call site hands it to url_fallback"
  - "url_fallback.plan_ladder and .filter_candidates refuse a host-less input with ValueError naming it, instead of silently building an authority-less candidate"
  - "Bare-domain regression fixtures in both test files, closing the gap that let this ship broken (every prior fixture was scheme-bearing)"
  - "0.38.1 released with a matching CHANGELOG entry and SKILL.md prose"
affects: ["62-UAT (unblocks UAT tests 2 and 3, both blocked_by: prior-phase on G-62-1)"]

actuals:
  tokens: 4600
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Normalise a CRM property at the seam that knows it came from a CRM field, not inside a module written for an operator-pasted URL — one helper, both call sites, never duplicated (D-62-01 lineage)."
    - "A validity guard (enrichment._clean_domain) reused as a boolean test only, never as the value that gets built — its normalized return value is not what downstream code should bind to."

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/scripts/url_fallback.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_url_fallback.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json

key-decisions:
  - "Decision 1 (where): one private helper (_ladder_source) in suggest_contacts.py, called by BOTH discovery_plan and next_candidates — implemented exactly as specified, no drift."
  - "Decision 2 (host rule): guard-then-prefix, never rebuild — scheme added only when absent; www., case, path and query preserved byte-for-byte. Implemented exactly as the plan's table."
  - "Decision 3 (scope): no redirect following, no host-variant retry — url_fallback.py gained one guard and zero I/O. Implemented exactly as specified."

requirements-completed: [SUGGEST-01, SUGGEST-02, SUGGEST-04, SUGGEST-05]

coverage:
  - id: D1
    description: "A bare-domain company (e.g. bunburyturfclub.com.au) reaches a host-bound, fetchable ladder through discovery_plan"
    requirement: SUGGEST-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_bare_domain_discovery_plan_is_host_bound_and_sitemap_only"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_bare_domain_discovery_plan_candidates_have_no_empty_authority"
        status: pass
    human_judgment: false
  - id: D2
    description: "The SECOND broken call site — next_candidates accepts a same-host sitemap URL for a bare-domain company instead of refusing it off-host"
    requirement: SUGGEST-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_next_candidates_second_call_site_accepts_a_same_host_sitemap_url_for_a_bare_domain"
        status: pass
    human_judgment: false
  - id: D3
    description: "www. prefix survives verbatim; scheme-bearing values (including the WordPress-REST acceptance case) are a byte-identical no-op"
    requirement: SUGGEST-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_bare_domain_with_www_prefix_survives_verbatim"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_scheme_bearing_website_is_a_byte_identical_no_op"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_scheme_bearing_wordpress_url_still_leads_with_its_rest_rung"
        status: pass
    human_judgment: false
  - id: D4
    description: "A recorded value that cannot be a company's own site (social/profile host, or dotless) yields zero candidates with a reason naming it, in both discovery_plan and next_candidates"
    requirement: SUGGEST-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_unusable_recorded_value_takes_the_documented_no_candidates_path"
        status: pass
    human_judgment: false
  - id: D5
    description: "url_fallback.plan_ladder and .filter_candidates refuse a host-less input loudly at both public entry points, including the CLI layer"
    requirement: SUGGEST-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py::test_plan_ladder_refuses_a_bare_domain_naming_the_offending_value"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py::test_filter_candidates_refuses_a_bare_domain_pasted_url_naming_the_offending_value"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_url_fallback.py::test_cli_reports_a_bare_domain_refusal_the_same_way_as_any_other_failure"
        status: pass
    human_judgment: false
  - id: D6
    description: "Zero n8n change, and a released client (0.38.1) with matching CHANGELOG"
    requirement: SUGGEST-05
    verification:
      - kind: other
        ref: "git status --porcelain n8n/ scripts/build_cloud_workflows.py (silent)"
        status: pass
      - kind: other
        ref: "node --test tests/n8n/*.test.mjs (867 passed)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-03
status: complete
---

# Phase 62 Plan 07: Bare-domain suggestion-round fix Summary

**A CRM-recorded bare domain (`bunburyturfclub.com.au`) now reaches a real, host-bound fetch ladder through both `discovery_plan` and `next_candidates`, closing the gap that made 83.5% of this portal's companies-with-a-website report "no people page" when the real problem was a malformed URL.**

## Performance

- **Duration:** 25 min
- **Tasks:** 3/3 completed
- **Files modified:** 7

## Accomplishments

- Added one private seam helper (`_ladder_source`) to `suggest_contacts.py`, used by both `discovery_plan` and `next_candidates` — the two call sites that fed HubSpot's schemeless `website`/`domain` straight into `url_fallback`, which assumed an operator-pasted URL.
- The host rule is exactly Decision 2's table: `https://` prefixed only when the recorded value has no scheme; `www.`, case, path and query preserved byte-for-byte; `enrichment._clean_domain` reused as a boolean validity guard only (never as the built host).
- Added a loud `ValueError` guard to both `url_fallback.plan_ladder` and `.filter_candidates` for a host-less input — a defence for a future third caller, since after this plan neither `suggest_contacts` call site can ever reach it.
- Added bare-domain regression fixtures to both test files — the class of fixture the whole suite lacked, which is exactly why this defect shipped and passed CI.
- Released `0.38.1` with a matching CHANGELOG entry and prose-only SKILL.md guidance; proved (not assumed) zero `n8n/` change.

## Task Commits

Each task was committed atomically:

1. **Task 1: One seam helper — a bare-domain company reaches a fetchable, host-bound ladder end to end** - `8c45946` (fix, tdd — RED then GREEN in one commit per the tracer-task convention; RED evidence below)
2. **Task 2: url_fallback refuses a host-less input loudly, at both public entry points** - `f5fd69a` (fix, tdd — RED then GREEN in one commit; RED evidence below)
3. **Task 3: Release it, and prove the n8n lane was never touched** - `2d99cfa` (release/docs)

_Note: per-task RED and GREEN test edits and implementation landed in a single commit per task (the RED tests were written and observed failing before the implementation was written in the same working-tree pass, then committed together) — the RED output is reproduced below rather than split into a separate commit, since the tests and the fix they exercise share one file each._

## Observed RED Evidence (required by <tdd_requirement>)

**Task 1**, before the `_ladder_source` fix existed, running the new bare-domain tests:

```
FAILED test_bare_domain_discovery_plan_is_host_bound_and_sitemap_only
FAILED test_bare_domain_discovery_plan_candidates_have_no_empty_authority
FAILED test_bare_domain_with_www_prefix_survives_verbatim
FAILED test_next_candidates_second_call_site_accepts_a_same_host_sitemap_url_for_a_bare_domain
FAILED test_unusable_recorded_value_takes_the_documented_no_candidates_path[linkedin.com/company/futsal-australia]
FAILED test_unusable_recorded_value_takes_the_documented_no_candidates_path[unknown]
6 failed, 6 passed, 38 deselected
```

The signature match the planner's own pre-run: `discovery_plan`'s host-bound test failed with
`assert [{'url': 'https:///wp-json/...'}] == []`-shaped diffs — the empty-authority
(`https:///...`) signature named in the plan. The 6 tests that passed unmodified were the
no-op-proof and no-website cases, which the pre-fix code already satisfied by construction
(scheme-bearing input untouched; no-website path unchanged) — expected, not a finding.

**Task 2**, before the `_require_authority` guard existed, running the new host-less-refusal
tests:

```
FAILED test_plan_ladder_refuses_a_bare_domain_naming_the_offending_value (DID NOT RAISE ValueError)
FAILED test_filter_candidates_refuses_a_bare_domain_pasted_url_naming_the_offending_value (DID NOT RAISE ValueError)
FAILED test_plan_ladder_refuses_an_empty_string (DID NOT RAISE ValueError)
FAILED test_plan_ladder_refuses_none (TypeError: a bytes-like object is required, not 'str' — NOT the ValueError expected)
FAILED test_cli_reports_a_bare_domain_refusal_the_same_way_as_any_other_failure (returncode 0, not 1)
5 failed, 23 deselected
```

A finding worth recording: `plan_ladder(None)` did not merely succeed silently — it raised the
WRONG exception type (`TypeError` inside `slug_of`, from `urlsplit(None)`), which the CLI's
broad `except Exception` still caught and reported as `ok: false`, exit 1 (matching CLI
behavior at the module boundary) but which the in-process function itself did not raise as a
clean, callable-facing `ValueError`. The new guard fixes both the silent-empty-netloc case
(the gap's actual live impact) and this latent `TypeError` case in the same change.

## Files Created/Modified

- `operator-claude-plugin/scripts/suggest_contacts.py` — added `_ladder_source(company_row)`; rewired `discovery_plan` and `next_candidates` to call it
- `operator-claude-plugin/scripts/url_fallback.py` — added `_require_authority(pasted_url)`, called first in `plan_ladder` and `filter_candidates`
- `operator-claude-plugin/tests/test_suggest_contacts.py` — 12 new bare-domain/unusable-value/no-op regression tests
- `operator-claude-plugin/tests/test_url_fallback.py` — 5 new host-less-refusal tests (including the CLI layer)
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — prose added to step 5 only; the fenced python block `test_skill_sequence_coverage.py` pins is untouched
- `operator-claude-plugin/CHANGELOG.md` — new `0.38.1` section (`Fixed` + `Changed`)
- `operator-claude-plugin/.claude-plugin/plugin.json` — version `0.38.0` → `0.38.1`

## Decisions Made

All three decisions recorded in `62-07-PLAN.md` were implemented exactly as specified, with no
amendment:

- **Decision 1 (where the normalisation lives):** one private helper (`_ladder_source`) in
  `suggest_contacts.py`, called by both `discovery_plan` and `next_candidates`. `url_fallback.py`
  gained no normalisation logic — only the loud refusal guard (Decision 1b confirmed unchanged:
  `contact-upload`'s CLI adapter needed no doc change).
- **Decision 2 (the host rule):** guard-then-prefix, never rebuild. Implemented as: read
  `website` then `domain` (no fall-through); `enrichment._clean_domain` used as a boolean test
  only (its stripped return value is never the built host); scheme prefixed only when the
  recorded value has none, case-insensitive check on `http://`/`https://`; `www.`, case, path,
  query preserved verbatim.
- **Decision 3 (scope):** no redirect following, no host-variant retry, no I/O added to
  `url_fallback.py` — the guard is pure string inspection (`urlsplit(...).netloc`), consistent
  with the module's no-I/O-by-construction property that `62-VALIDATION.md`'s manual-verification
  row 1 depends on.

## Deviations from Plan

None — plan executed exactly as written. One incidental finding recorded above (Task 2's RED
evidence): `plan_ladder(None)` previously raised `TypeError` rather than failing silently or
cleanly; the new guard normalises this to the same `ValueError` path as every other host-less
input, which is a strict improvement and squarely inside Task 2's scope (both `plan_ladder("")`
and `plan_ladder(None)` were explicit behavior-list items).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

**What this unblocks:** UAT tests 2 and 3 in `62-UAT.md`, both `blocked_by: prior-phase` on
`G-62-1`, can now be attempted. Per the plan's own framing, the acceptance bar is not the unit
tests above (already green) — it is a **live operator sitting**, explicitly NOT run as part of
this plan (no `web_fetch`, no arming, no HubSpot write, no provider credit spent here). That
sitting is the operator's supervised walk and belongs in the UAT re-run.

**Blockers/concerns:** None identified. The whole plugin test suite (2300 passed, 5 skipped) and
the whole n8n suite (867 passed) are green; `git status --porcelain n8n/
scripts/build_cloud_workflows.py` is silent, confirming the zero-backend-change claim rather than
asserting it.

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-03*
