---
status: resolved
created: 2026-07-29
found_by: "Phase 19 Task 1's item-16 deployment-drift probe (19-LEDGER.md)"
related: bug-10 (companies-search transport this deployment still runs, but pre-Phase-18)
---

# BUG 26 — live `LV Enrichment` deployment predates Phase 18; `lv_sponsorship_reliant` never populates on the live portal

## Claim

The live n8n Cloud `LV Enrichment (Cloud template)` workflow is running JavaScript that
predates Phase 18. `compute_workflow_diff` in `scripts/deploy_n8n_workflows.py` matches
workflows on `name` only and never compares node content, so a routine `DRY_RUN` diff
reports every existing workflow as an `update` candidate regardless of whether it is
current — it cannot itself answer "is the live deployment current?"

A real content probe settles it: the live `LV Enrichment` node bodies (fetched via
`GET /api/v1/workflows`, list endpoint, `nodes` present so no per-workflow GET fallback was
needed) were serialized and substring-checked for the two Phase-18 producer markers that
exist in the committed `n8n/wf_enrichment_cloud.json`:

- `_personaGroup` (Phase 18's persona-group provider mapper) — **absent live**.
- `_industryText` (Phase 18's industry-code normalizer) — **absent live**.

Both markers are confirmed present in committed git (`Normalize + Score` and
`Normalize + Score Company` nodes). The live jsCode bodies for those same two nodes are
measurably shorter than committed (live `Normalize + Score`: 28078 chars vs committed
30599; live `Normalize + Score Company`: 28563 chars vs committed 31084 — roughly the size
of the missing producer functions).

**Downstream consequence, confirmed live (item 16.6's transport replay):** a `HubSpot
Company Search` request against company `9604614548` (Melbourne Racing Club) returns the
`lv_sponsorship_reliant` property key (it IS in the committed request's `properties` array
— that wiring is old enough to have deployed) but its value is `null`. No live execution
has ever run the code that would populate it, because that code has never been deployed.

## Why this is not a code defect

`n8n/wf_enrichment_cloud.json` (committed) is correct and current — it contains Phase 18's
producers. The gap is entirely in the deployment: whoever last redeployed `LV Enrichment`
did so at some point AFTER the last `STATE.md` snapshot (Contact Ingest 19→21 nodes,
Enrichment 94→97 nodes, Scheduled Maintenance 30→34 nodes; all three flipped
`active=false`→`active=true`; live node counts for all three workflows now match the
CURRENT committed `n8n/wf_*_cloud.json` node counts exactly) but BEFORE Phase 18 landed —
or Phase 18 was simply never redeployed at all. Either way, closing this requires an
operator running the disarmed deploy command, not a code change.

## Scope fence

- No `n8n/`, `scripts/`, `tests/`, or `src/` file needs to change to fix this.
- The fix is purely operational: redeploy the current committed build.
- `19-OPERATOR-RUNBOOK.md` (Phase 19) already documents the armed-window canary for item
  16.9's `company:update` residual; a plain disarmed redeploy (no `ENABLE_BAKED_FLAGS`,
  no write-enabling flags) is a strictly lower-risk operation and can run independently of
  that canary, using the same `scripts/deploy_n8n_workflows.py` invocation with
  `DRY_RUN=false ALLOW_N8N_DEPLOY=true` and no baked-flag overlay.

## Recommended next step (not performed here — read-only re-run scope)

1. Operator runs `DRY_RUN=false ALLOW_N8N_DEPLOY=true python scripts/deploy_n8n_workflows.py`
   (no `ENABLE_BAKED_FLAGS`) to redeploy the current committed build.
2. Read back `LV Enrichment`'s live node bodies and re-confirm `_personaGroup` and
   `_industryText` are now present.
3. Re-run item 16.6's `lv_sponsorship_reliant` transport replay (or a genuine research-gated
   live row) against a research-eligible company to confirm the field actually populates —
   this is the "future live-canary step" Phase 18's own `VERIFICATION.md` already flagged as
   outstanding (see `.planning/STATE.md` Deferred Items, Phase 18 copy-loop row).

## Resolution — 2026-07-29

Operator ran `19-OPERATOR-RUNBOOK.md` Step 0 (disarmed redeploy, dotenv wrapper form):
all three workflows updated with HTTP 200 (`LV Contact Ingest`, `LV Enrichment`,
`LV Scheduled Maintenance`). Post-redeploy read-back (read-only GET of `LV Enrichment`
node bodies):

- `_personaGroup`: PRESENT in `Normalize + Score` and `Normalize + Score Company`.
- `_industryText`: PRESENT in `Normalize + Score` and `Normalize + Score Company`.
- `lv_sponsorship_reliant`: PRESENT in `Build Research Request`, `Decide Company Action`,
  `Merge Company`.
- Write gate: `ALLOW_HUBSPOT_RECORD_WRITES` still baked disabled (no armed node).

Item 16.6's transport replay re-run post-redeploy: HTTP 200, total 1, record `9604614548`
returned, `lv_sponsorship_reliant` key present (value `null` — expected until an armed
research-gated enrichment run populates it; that residual is item 16.9's operator-canary
scope, `19-OPERATOR-RUNBOOK.md` Steps 1–4, still pending).

Ledger rows 16 and 16.6 flipped `human_needed` → `passed` (`19-LEDGER.md`).
