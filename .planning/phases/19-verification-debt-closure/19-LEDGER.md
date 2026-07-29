# Phase 19 Verification Debt Ledger

## Header

**No literal v0.3 "goal ledger" file exists anywhere in this repository.** `19-RESEARCH.md`
proved this exhaustively (repo-wide grep for the phrase "goal ledger" + `git log -S"goal ledger"
--all --oneline`, both exhaustive across history). The six items below are `19-RESEARCH.md`'s
evidence-based reconstruction — **Assumption A1** — not a transcription of a pre-existing
enumeration: the one v0.3 phase with zero `/gsd-verify-work` history (Phase 11) plus the exactly
five v0.3 phases whose `VERIFICATION.md` required a documented `## Resolution` section to reach
`passed` (15.5, 16, 16.4, 16.6, 16.9). This is a defensible, corroborated inference (exact count
match, all five Resolutions dated the same day as the archive commit), **not a proven fact**.

**Measured suite floor (this phase, before any check ran):**

- pytest: **596 passed** (`.venv/bin/python -m pytest -q`)
- node: **309 passed / 0 failed** (`node --test tests/n8n/*.test.mjs`)

Neither of the two stale figures in circulation (596/309 orchestrator-reported, 596/285
ROADMAP.md self-reported) was trusted — this is the number measured live at the start of this
phase and is the floor every later re-measurement in this phase must meet or exceed.

**Probe decisions (from `19-01-PLAN.md`'s `<objective>`, reproduced here):**

- **P-EMPTY** — a re-run that turns out moot is recorded `passed` with the superseding evidence
  named in its Evidence cell. It is never removed from the table and never becomes a bare
  citation of the 2026-07-29 verdict. Six rows in, six rows out.
- **P-ORDER** — the table lists all six in stable phase order (11, 15.5, 16, 16.4, 16.6, 16.9),
  which is also increasing risk (offline → live read-only → human-gated). Execution order
  matches, with one exception: item 16's deployment-drift probe ran FIRST (Task 1) because its
  result changes how 16.4/16.6/16.9 must be interpreted.
- **P-ADJ** — overlapping items (16.4/16.6 both search companies; 16.6/16.9 both touch the
  company write-lane surface) stay separate rows with separate outcomes and separate evidence.
  One HTTP response may satisfy two rows; the rows are never merged and neither cites the other
  as its own evidence.

## Ledger

| Item | What it verifies | Original verdict + artifact path | Method | Outcome | Evidence | Defect captured at |
|------|-------------------|-----------------------------------|--------|---------|----------|---------------------|
| 11 | Companies sibling branch, `mergeCompanies.js` non-clobber merge, three provider unit/shape defects, cross-provider size-conflict detector withholds promotion, numbered web-research spec, TX-4 taxonomy debt | Never run through `/gsd-verify-work` (no `VERIFICATION.md`/`UAT.md` exists) — `.planning/milestones/v0.3-phases/phase-11/phase-11-01-SUMMARY.md` | offline — targeted test re-runs + code inspection against current source | pending | — | — |
| 15.5 | A/R/G/T candidate scoring stays parallel through the judge; composite score never feeds `mergeCompanies`' promotion gate; self-confirmation guard on unprovenanced priors; TA-4/TS-1 recency test is non-tautological | `human_needed` → `passed` — `.planning/milestones/v0.3-phases/15.5-tiered-candidate-adjudication/15.5-VERIFICATION.md` `## Finding 1` + `## Resolution — 2026-07-29` | offline — targeted test re-run + test-title inspection against current source | pending | — | — |
| 16 | SJ-1/SJ-2/SJ-3 scheduled workflows fire, dedupe sweep wiring, §22.2 human review loop closes on a real record; workflows remain active + credential-bound | `human_needed` → `passed` — `.planning/milestones/v0.3-phases/16-scheduled-workflows-review-surface/16-VERIFICATION.md` `## Human Verification Required` + `## Resolution — 2026-07-29` | live, read-only — `DRY_RUN` unset (default true) / `ALLOW_N8N_DEPLOY` unset invocation of `scripts/deploy_n8n_workflows.py main()`, plus a live GET of `LV Enrichment`'s node bodies | human_needed | Part A (deployment inventory, `main([])` with no write flags set): `Workflows to create: []`; `Workflows to update: ['LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Scheduled Maintenance (Cloud)']`; `DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_N8N_DEPLOY=true to deploy.` — all three workflows exist live (empty create list), consistent with a prior deploy. Part B (drift probe, settles RESEARCH Open Question 2 / Assumption A2): `compute_workflow_diff` matches on `name` only and cannot itself answer whether Phase 18's rebuild was redeployed, so a real content probe was run — live `LV Enrichment (Cloud template)` nodes fetched via the list endpoint (`nodes` was present, not omitted, so no per-workflow GET fallback was needed) and serialized. **`_personaGroup`: ABSENT from live. `_industryText`: ABSENT from live.** Both markers ARE present in the committed `n8n/wf_enrichment_cloud.json` (`Normalize + Score` and `Normalize + Score Company` node bodies, confirmed by direct grep and jsCode-length comparison: live `Normalize + Score` jsCode is 28078 chars vs committed 30599; live `Normalize + Score Company` jsCode is 28563 chars vs committed 31084 — a ~2500-char gap matching the missing Phase-18 producer functions). **Conclusion: the live deployment predates Phase 18 — the deployed code is behind git.** Part C (active/bound-node inventory, from the same live fetch): `LV Contact Ingest (Cloud template)` — active=true, nodes=21, bound=4; `LV Enrichment (Cloud template)` — active=true, nodes=97, bound=22; `LV Scheduled Maintenance (Cloud)` — active=true, nodes=34, bound=9. Compared against `STATE.md`'s last-recorded Session Continuity state (Contact Ingest 19/4 active=false, Enrichment 94/22 active=false, Scheduled Maintenance 30/9 active=false): all three workflows are now **active=true** (were false), and node counts grew by 2/3/4 respectively while bound-credential counts stayed identical — consistent with at least one intermediate redeploy/activation between that STATE.md snapshot and now (live node counts for all three workflows now match the current committed `n8n/wf_*_cloud.json` node counts exactly: 21/97/34), but that intermediate redeploy did NOT include Phase 18's JS content changes. Recorded `human_needed` (not `failed`) because the finding is a data-freshness gap in the live deployment, not a code defect — closing it requires an operator redeploy, which this executor is prohibited from performing (arming a real `DRY_RUN=false ALLOW_N8N_DEPLOY=true` deploy is outside a read-only re-run's scope and this task's own prohibitions). | `.planning/debug/bug-24-enrichment-live-deployment-behind-git.md` |
| 16.4 | `hs_object_id EQ <id>` filterable on both `contacts` and `companies` CRM v3 search; a systemic filterability failure (400) is distinguishable from a legitimate zero-result response (200, `total:0`) | `human_needed` → `passed` — `.planning/milestones/v0.3-phases/16.4-fetch-by-objectid/16.4-VERIFICATION.md` `## Human Verification Required` + `## Resolution — 2026-07-29` | live, read-only — three `POST /crm/v3/objects/{type}/search` calls against portal `22617666` | pending | — | — |
| 16.6 | All `company:search`-shaped nodes return real records live via the credential-bound `httpRequest` transport (BUG 10 fix); Phase 18's new `lv_sponsorship_reliant` field survives the same transport | `gaps_found` → `passed` — `.planning/milestones/v0.3-phases/16.6-companies-search-transport-fix/16.6-VERIFICATION.md` `## Gaps Summary` + `## Resolution — 2026-07-29` | live, read-only — replay of the `Company Search` node's committed `jsonBody` (literal-substituted) against the live search API | pending | — | — |
| 16.9 | `company:create` and `company:update` write correctly to HubSpot, including Phase 18's new company payload fields | `gaps_found` → `passed` (SC-3 residual) — `.planning/milestones/v0.3-phases/16.9-create-path-fix-and-company-writes/16.9-VERIFICATION.md` `## Gaps Summary` + `## Resolution — 2026-07-29` | live write — operator only | pending | — | — |

## Footer (re-measured after Task 3, before this phase closes)

pending — filled by Task 3 after all six rows close.
