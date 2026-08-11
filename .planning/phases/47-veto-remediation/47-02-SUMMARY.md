---
phase: 47-veto-remediation
plan: 02
subsystem: planning-docs
tags: [requirements, validation, cost-estimate, api-coverage, documentation-only]
dependency-graph:
  requires:
    - "47-01: scripts/remediate_veto_companies.py (estimate_cost, refuse_if_over_budget, KNOWN_LIKELY_EVIDENCE_GATED_IDS, PINNED_COMPANY_ID_ORDER)"
  provides:
    - "REQUIREMENTS.md COVER-01/COVER-02 traceability amendment (D-02)"
    - "47-VALIDATION.md filled Per-Task Verification Map + discharged Wave 0 items"
    - "47-COST-ESTIMATE.md ex-ante cost projection (D-03/COVER-02)"
    - "COVERAGE.md scoped API coverage matrix"
  affects:
    - "Plan 04 (reports actuals against 47-COST-ESTIMATE.md's row labels; ticks VETO/COVER requirements)"
tech-stack:
  added: []
  patterns:
    - "Dated parenthetical amendment on existing requirement text (RUBRIC-01/03 precedent) rather than minting a new requirement ID"
key-files:
  created:
    - .planning/phases/47-veto-remediation/47-COST-ESTIMATE.md
    - .planning/phases/47-veto-remediation/COVERAGE.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/phases/47-veto-remediation/47-VALIDATION.md
decisions:
  - "COVER-01/COVER-02 Traceability rows retargeted from 'Phase 48' to 'Phase 47 + 48', with a footnote stating neither phase closes them alone (D-02)."
  - "Cost estimate's Anthropic dollar figure reported as a bounded floor (~$1.17 for 17 records), not folding the ~4 redundant second-pass calls into the dollar total, because the $0.0686 canary figure was never measured for that call shape."
  - "nyquist_compliant flipped to true in 47-VALIDATION.md: all 6 Per-Task Verification Map rows now carry either an automated command or an explicit manual-only justification cross-referenced in the Manual-Only Verifications table."
metrics:
  duration: "~35 min"
  completed: 2026-08-11
actuals:
  tokens: 5200
  tasks: 3
  commits: 3
status: complete
---

# Phase 47 Plan 02: Traceability, Cost Estimate, and API Coverage Summary

Landed the paperwork the live veto-remediation run depends on before it happens: a D-02
traceability amendment splitting COVER-01/COVER-02 across Phase 47 and 48, a filled
`47-VALIDATION.md` verification map with every row keyed to a concrete task, an ex-ante cost
estimate sourced directly from `estimate_cost()` in `scripts/remediate_veto_companies.py`, and a
scoped API coverage matrix. No HubSpot, n8n, or Anthropic call was made — documentation only.

## What Was Built

**Task 1 — Traceability amendment + validation map (commit `2736bb4`).**
`.planning/REQUIREMENTS.md`: COVER-01 and COVER-02 Traceability rows changed from `Phase 48` to
`Phase 47 + 48`; a footnote added stating neither phase may close claiming full coverage alone;
dated parentheticals appended to both requirements' text, mirroring the RUBRIC-01/03 amendment
style, naming Racing NSW `15008671672` as the one record left to Phase 48. VETO-01/02/03
checkboxes left unticked — the live run has not happened; Plan 04 owns those ticks.

`.planning/phases/47-veto-remediation/47-VALIDATION.md`: replaced the "Task IDs are filled in by
the planner" placeholder with a `Task` column on the Per-Task Verification Map, keying all 6 rows
to Plan 01 Tasks 1/3, Plan 03 Task 1, or Plan 04 Tasks 1/2/3. All four Wave 0 Requirements
checkboxes flipped to `[x]` with discharge pointers: `settle_and_assert`/`settle_tier`/
`settle_veto` and the never-write guard extension (Plan 01), `scripts/veto_remediation_report.py`
(Plan 03). Confirmed the real never-write assertions are
`test_backfill_never_writes_derived_output_properties` (line 169) and
`test_backfill_build_updates_payload_never_contains_derived_fields` (line 234) in
`tests/test_backfill_seed_company_scores.py` — "T-40-22" is a plan-task label, not a test
identifier, matching the research finding. `nyquist_compliant` set to `true`.

**Task 2 — Ex-ante cost estimate (commit `917e454`).** Created
`.planning/phases/47-veto-remediation/47-COST-ESTIMATE.md`. Rather than hand-deriving figures,
called `estimate_cost(m.PINNED_COMPANY_ID_ORDER)` live and quoted its output directly, so the
document and the code it describes cannot silently drift apart: 17 web-research calls, 4
redundant second-pass calls (Simtech LED, Editix, Jam TV, The Rumble/Pacific Action Sports —
`KNOWN_LIKELY_EVIDENCE_GATED_IDS`), $1.1662 Anthropic floor, at most 17 n8n executions against
the 2,500/month allowance, 0 provider credits. States explicitly that the $0.0686 canary figure
was measured on the n8n Haiku-plus-Sonnet path (not this phase's standalone `claude-sonnet-5` +
native `web_search` path) and that native `web_search` per-search billing is unmeasured. Names
`refuse_if_over_budget` / `BudgetRefused` as the refusal mechanism and states the run is refused
outright, not truncated. Explains why the deployed `Research Trigger Gate` re-fires research on
~4 records (org-type membership check only, no evidence-presence check, `ALLOW_WEB_RESEARCH`
baked true at build time). Ends with an empty Actuals table carrying matching row labels for
Plan 04.

**Task 3 — Scoped API coverage matrix (commit `a9d183f`).** Created
`.planning/phases/47-veto-remediation/COVERAGE.md` with a 13-row `| capability | decision |
reason |` table (7 INTEGRATE, 6 OPT-OUT), scoped to exactly the surfaces this phase's code
touches (`src/hubspot_client.py`, `scripts/check_schema_drift.py`,
`operator-claude-plugin/scripts/enrichment.py`, `operator-claude-plugin/scripts/n8n_arming.py`,
`src/web_research.py`) rather than the full HubSpot/n8n API surface. Every OPT-OUT row carries a
one-line reason (no-new-properties constraint, D-08's provider-free routing, D-18's
webhook-over-subscription choice, D-20's deploy-avoidance, the absent n8n usage endpoint).

## Deviations from Plan

None — plan executed exactly as written. All acceptance-criteria greps and the offline
`.venv/bin/python -m pytest tests/ -x -q` suite (1223 passed, 123 skipped) passed after each
task.

## Self-Check: PASSED

- `.planning/phases/47-veto-remediation/47-COST-ESTIMATE.md` — FOUND
- `.planning/phases/47-veto-remediation/COVERAGE.md` — FOUND
- `.planning/REQUIREMENTS.md`, `.planning/phases/47-veto-remediation/47-VALIDATION.md` — FOUND, modified
- Commit `2736bb4` — FOUND in `git log`
- Commit `917e454` — FOUND in `git log`
- Commit `a9d183f` — FOUND in `git log`
