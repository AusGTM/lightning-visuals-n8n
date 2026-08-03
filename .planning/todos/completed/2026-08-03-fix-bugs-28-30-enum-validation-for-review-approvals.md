---
created: 2026-08-03T05:10:12.569Z
title: Fix BUGS 28-30: enum validation for review approvals
area: planning
severity: major
files:
  - n8n/code/mergeCompanies.js:33
  - n8n/code/reviewDecision.js
  - n8n/code/taxonomy.generated.js
  - scripts/snapshot_hubspot_schema.py
  - operator-claude-plugin/scripts/review_decision.py:182
  - .planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md
---

## Problem

Found live by RB-9 (30-07, 2026-08-03), workstream `plugin-entrypoint`. Evidence:
`30-07-SUMMARY.md`, HANDOFF §3 BUGS 28-31 (31 already fixed, `cf196d9`).

**BUG 28 — every `industry` approval 400s.** HubSpot's company `industry` is an
enumeration with 148 fixed internal values (LinkedIn-derived). The enrichment
pipeline stages the provider's free-text label — RB-9's live case:
`arts, entertainment, and recreation`, a NAICS-ish sector label with no exact
label match in HubSpot's set — as the review candidate. The approve PATCH gets
HubSpot 400 "Bad request - please check your parameters" (n8n execution 1173,
node `Review Decision Update`). All seven other keys in the approve patch
validate clean; `industry` is the sole cause. No enum-backed canonical field can
ever be approved as built.

**BUG 29 — the preview cannot see BUG 28.** `preview_decision` returned
`outcome: applied` for that impossible write: the dry run computes the patch
without validating against HubSpot's property schema, so the operator is shown,
and asked to approve, a write guaranteed to fail.

**BUG 30 — `unparseable_response` conflates two opposite states.** The review
write gate answers NO body on an allowlist drop (fail-closed, correct) and the
client reports the same `unparseable_response` for a workflow error (a real
fault). OPERATOR-RUNBOOK RB-9 tells the operator that silence "means not on the
allowlist — check TEST_RECORD_IDS before investigating anything else", which
pointed exactly wrong in the live case. Only n8n execution history disambiguates.

## Solution

Decision made 2026-08-03 (operator + agent): **validate-and-refuse, NO full
mapping layer.** Rationale: taxonomies don't align (NAICS vs LinkedIn-derived —
mapping is judgment, not lookup), `industry` feeds no ICP scoring (the `lv_*`
taxonomy does), and raw provider strings survive in the staging fields
(`apollo_industry`, `zoominfo_industry`, …) so refusing promotion loses nothing.

1. Generate an enum-options module from the HubSpot property schema snapshot —
   pattern already in the repo: `taxonomy.generated.js` built from config,
   `scripts/snapshot_hubspot_schema.py` for capture. Values AND labels.
2. Validate enum-bound canonical candidates at staging (`mergeCompanies.js`,
   field policy block at line 33): unmappable values are never offered as
   approvable candidates. The ONLY mapping performed: exact case-insensitive
   label→value match (`Sports` → `SPORTS`) — ~5 lines, no table.
3. Same generated module validates in `reviewDecision.js`'s shared patch path so
   BOTH `dry_run` and apply refuse explicitly, with the invalid value named.
   This kills BUG 29 at the same seam.
4. BUG 30: make the write gate respond an explicit refusal body on an allowlist
   drop instead of dropping the row silently; update the client's
   `unparseable_response` comment (`review_decision.py:182`) and RB-9's
   diagnostic advice in OPERATOR-RUNBOOK.md.
5. Two-sided tests (python + n8n, the "contract held in two places" rule) and a
   disarmed redeploy + bounce of active workflows.

After the fix lands: re-run RB-9 step 8 only. Note record `9604614548` was
cleared manually on 2026-08-03 (reject stands, `industry`=`SPORTS`); a fresh
`needs_review` fixture is needed — one enrichment run against a test company
with a conflicting staged value will produce one.
