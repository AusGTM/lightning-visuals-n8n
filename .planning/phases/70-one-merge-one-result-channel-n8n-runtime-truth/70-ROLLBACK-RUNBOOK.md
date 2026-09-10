# D-70-21 — Roll back the live n8n Cloud instance to the pre-Phase-70 workflows

**This is a standalone operator procedure. You do not need to have read any Phase 70 plan
to run it.** Follow the steps in order. Every command is copy-pasteable.

## STOP FIRST — refuse on a dirty working tree

Before doing anything else, run:

```bash
git status --porcelain -- n8n/
```

**If this prints ANYTHING, STOP. Do not proceed.** A non-empty result means someone (an
executor, an in-flight regeneration) has uncommitted changes to `n8n/` in the working
tree right now. Step 2 below overwrites `n8n/*.json` with historical content and Step 6
restores it from `HEAD` — both would destroy that uncommitted work. Get the tree clean
(commit or stash elsewhere, outside this repo's worktree — see CLAUDE.md's
`destructive_git_prohibition` on why `git stash` is unsafe here) before running this
runbook.

## Why this rollback exists

The live enrichment lane's response builder is dead on the Phase 70 JSON. `Build
Response Merge` never fires and `Build Response` never runs; the execution finishes
`success` with zero rows (n8n Cloud executions `12204`, `12205`, `12206`, 2026-09-10).
That is silent data loss, not a hang, so nothing alerts on it. The pre-Phase-70 bodies at
commit `59812be` are the last known-working live state — this runbook restores them so
the enrichment lane works again while the Phase 70 graph defect is fixed offline.

**Nothing in this rollback arms anything.** Every step below is disarmed: both write
flags (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`) stay `"false"` in the
bodies being deployed, and the allowlist (`TEST_RECORD_IDS`, `TEST_RECORD_DOMAINS`) stays
empty. This is proven offline by `tests/test_phase70_rollback_bundle.py` — run it now if
you want to double-check before deploying:

```bash
.venv/bin/python -m pytest tests/test_phase70_rollback_bundle.py -q
```

## The five workflows this rollback touches

| Committed file (checked out at step 2) | Live workflow name | Live workflow id | Pinned node count |
|---|---|---|---|
| `n8n/wf_backend_status_cloud.json` | LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | 17 |
| `n8n/wf_contact_ingest_cloud.json` | LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | 29 |
| `n8n/wf_enrichment_cloud.json` | LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | 123 |
| `n8n/wf_review_decision_cloud.json` | LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | 26 |
| `n8n/wf_scheduled_maintenance_cloud.json` | LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | 39 |

The deploy script (step 3/4) reads whatever bodies currently sit in the repo's `n8n/`
directory and matches each one to its live counterpart **by `name`** (never by id) — this
is why step 2 checks the pre-70 bodies out into the working tree first, and why step 6
restores the working tree afterward: the deploy script has no other way to know which
five bodies to send.

## Step 1 — set n8n credentials in your shell

This runbook needs `N8N_URL` and `N8N_API_KEY` in the environment. If they are already in
your `.env`:

```bash
set -a; source .env; set +a
```

## Step 2 — check the pre-Phase-70 bodies out of the pinned commit

```bash
git checkout 59812be -- \
  n8n/wf_backend_status_cloud.json \
  n8n/wf_contact_ingest_cloud.json \
  n8n/wf_enrichment_cloud.json \
  n8n/wf_review_decision_cloud.json \
  n8n/wf_scheduled_maintenance_cloud.json
```

Verify: `git status --porcelain -- n8n/` should now show all five files as modified (`M`).

**Do not hand-edit any of these five files at any point in this procedure.** They come
from git history verbatim; if something looks wrong, stop and re-derive from commit
`59812be`, never patch in place.

## Step 3 — dry-run diff (zero writes, sanity check)

```bash
.venv/bin/python scripts/deploy_n8n_workflows.py
```

Expect: `Workflows to create: []`, `Workflows to update:` naming all five workflows above,
and a line ending `DRY RUN (default) — no writes will be made.` If instead you see
`skipped (no n8n creds)`, go back to Step 1. If you see `REFUSED: N8N_URL does not match
the expected instance`, stop — you may be pointed at the wrong n8n instance.

## Step 4 — the armed deploy (this is the live write)

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python scripts/deploy_n8n_workflows.py
```

Expect five lines reading `updated workflow <name> (200)`, no `FAILED` lines. This PUTs
the pre-Phase-70 bodies over the five live workflows. **A stored update alone never
reloads a running workflow** — the workflow keeps running whatever graph it loaded at
its last activation until it is bounced. Do not skip Step 5.

## Step 5 — bounce (mandatory) and read back

```bash
.venv/bin/python scripts/bounce_n8n_workflows.py
```

This deactivates then reactivates each of the five workflows (forcing it to reload the
just-deployed body) and prints a table reading back, per workflow: whether it is active,
its live node count vs. the count in the working tree's `n8n/` file (still the pre-70
body at this point — do not run Step 6 before this step), and every
`ALLOW_HUBSPOT_RECORD_WRITES` / `ALLOW_HUBSPOT_CREATE` literal found in its live jsCode.

**What to check in the printed table** (these are the four facts to report back):
- all five rows show `active = True`
- live node counts read exactly `17 / 29 / 123 / 26 / 39` (backend_status / contact_ingest
  / enrichment / review_decision / scheduled_maintenance) and match the "committed nodes"
  column (they will, since the working tree still holds the pre-70 bodies)
- every write-flag column reads `false` (or `[-]`, meaning the flag is not declared in
  that workflow at all — `wf_backend_status_cloud.json` has neither flag)
- the script prints `OK — all active, node counts match, write flags false.` and exits 0

If it prints `MISMATCH` for any row, **stop and report exactly what mismatched** — do not
re-run Step 4 hoping it self-corrects.

## Step 6 — restore the working tree

```bash
git checkout HEAD -- \
  n8n/wf_backend_status_cloud.json \
  n8n/wf_contact_ingest_cloud.json \
  n8n/wf_enrichment_cloud.json \
  n8n/wf_review_decision_cloud.json \
  n8n/wf_scheduled_maintenance_cloud.json
git status --porcelain -- n8n/
```

The second command should print nothing. If it prints anything, something in the repo
outside this runbook changed those files during the rollback — investigate before
committing anything.

## Step 7 — confirm the enrichment lane works again

Send one disarmed enrichment or ingest request through your normal client path and
confirm it returns a non-empty row set (the pre-70 graph's `Build Response` runs on every
request, unlike the dead Phase 70 lane).

## What this rollback does NOT do

It does not fix the Phase 70 graph defect — it reverts past it. The fixed Phase 70 JSON
(once the gap-closure work lands and clears its own gates) is redeployed later, at a
**separate**, later gate — not part of this runbook, and not automatic. Until that
redeploy happens, the live instance intentionally runs the older pre-Phase-70 graph this
runbook restores.
