# Operator Runbook — Item 16.9 `company:update` armed canary

This runbook closes the one item in the Phase 19 ledger (`19-LEDGER.md`, row 16.9) that an
autonomous executor is prohibited from performing: an ARMED HubSpot write against a live
record. It mirrors the ceremony `17-CANARY-EVIDENCE.md` already proved for the contacts
lane (arm, fire once, read back, restore disarmed, read the deployment back) and reuses the
exact deploy-time overlay mechanism already built for it
(`_OVERLAY_FLAG_SPEC` / `enable_baked_flags()`, `scripts/deploy_n8n_workflows.py`
lines 110-141).

**Do not run this until item 16's deployment-drift finding (`bug-26-enrichment-live-
deployment-behind-git.md`) is closed first** — the live `LV Enrichment` deployment
currently predates Phase 18. A `company:update` canary run against the stale deployment
would prove the wrong artifact. Redeploy the current committed build (step 0 below) before
arming anything.

## Scope

- ONE allowlisted test company (`9604614548` — Melbourne Racing Club, the same standing
  fixture used throughout Milestone 3/4 for read-only checks).
- ONE `company:update` operation — SC-3, the residual the original 16.9 verifier itself
  flagged as not independently re-confirmed.
- `ALLOW_HUBSPOT_CREATE` stays untouched. `company:create` (SC-4) was already
  independently re-confirmed live in the original phase (execution 34); re-arming create
  here adds risk for no verification value.
- Nothing else. No other flag, no other record.

## Command form — `.env` loading

The deploy script reads `N8N_URL`/`N8N_API_KEY` from the process environment and does not
load `.env` itself, so a bare `python scripts/deploy_n8n_workflows.py` from a fresh shell
skips with `skipped (no n8n creds)` (observed live 2026-07-29). Every deploy command below
therefore runs through an in-process `python-dotenv` wrapper (the same pattern
`17-CANARY-EVIDENCE.md` used):

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

- `load_dotenv()` defaults to `override=False`: variables already set in the shell
  (`DRY_RUN=false`, `ALLOW_N8N_DEPLOY=true`, `ENABLE_BAKED_FLAGS=...`) WIN over `.env`
  values. `.env` only fills in what the shell didn't set — the creds. In particular,
  `.env`'s own `DRY_RUN=true` cannot un-arm a shell-set `DRY_RUN=false`, and `.env`'s
  `ALLOW_WEB_RESEARCH`/`ALLOW_SONNET_ESCALATION` (Python-harness lane) stay inert because
  the overlay reads only `ENABLE_BAKED_FLAGS`.
- Run from the repo root (relative `scripts/` path and `.env` discovery both assume it).
- Confirm whose key is in `.env`'s `N8N_API_KEY` before ANY deploy: API-created workflows
  land in the key owner's n8n project. It must be Robert's key (Alex's is retained as
  `N8N_API_KEY_2`) — a wrong key silently deploys into the wrong project (cost a full
  deploy cycle on 2026-07-28).

## Step 0 — Redeploy the current committed build (disarmed)

Closes `bug-26` first, so the canary below exercises Phase-18-current code (including the
`lv_sponsorship_reliant` producer). No write-enabling flag is set at this step — this is a
plain disarmed redeploy.

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

Read back `LV Enrichment`'s live node bodies afterward and confirm `_personaGroup` and
`_industryText` are now both present in the `Normalize + Score` / `Normalize + Score
Company` node bodies (the same check Phase 19 Task 1 ran, now expected to flip from absent
to present).

## Step 1 — Arm

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=9604614548" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

Notes on the exact syntax (read from `_OVERLAY_FLAG_SPEC`/`_requested_overlay_flags()`):

- `ALLOW_HUBSPOT_RECORD_WRITES` is a bare boolean kill switch — write it with no `=value`.
  It rewrites the baked `"false"` literal to `"true"`.
- `TEST_RECORD_IDS=9604614548` supplies the allowlist value. The script refuses to arm any
  write-enabling flag (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`) unless the
  SAME `ENABLE_BAKED_FLAGS` invocation also supplies a non-empty `TEST_RECORD_IDS` and/or
  `TEST_RECORD_DOMAINS` — this is enforced code, not a convention (see
  `_requested_overlay_flags()`'s `refusing to enable HubSpot writes without an allowlist`
  ValueError).
- Multiple ids in one allowlist use `|` as the separator (`TEST_RECORD_IDS=id1|id2`), NOT
  `,` — `,` already separates entries within `ENABLE_BAKED_FLAGS` itself. Not needed for
  this single-record canary, but stated here since a future multi-record canary would need
  it.
- `ALLOW_HUBSPOT_CREATE` is deliberately NOT included. Do not add it.

The deploy's own printed output will confirm the rewrite count
(`ENABLE_BAKED_FLAGS: ALLOW_HUBSPOT_RECORD_WRITES -> "true" rewritten Nx in [...]`) before
any write happens — if that count is 0 for either flag, the script REFUSES and deploys
nothing (a typo or an already-current literal would surface here, not as a silent no-op).

## Step 2 — Fire once, read back

Trigger exactly ONE `company:update`-shaped event for company `9604614548` (e.g. a webhook
event with `enrichment_requested=true` set on that record, or replaying the same event
shape the original 16.9 canary used). Immediately after the execution completes:

1. Read the record back via a search or fetch-by-id call and confirm the updated
   field(s) reflect the write.
2. Confirm NO OTHER record changed — spot-check `lastmodifieddate` on at least one
   neighboring test record (e.g. contact `201`) to confirm it is unchanged.
3. HubSpot search has eventual consistency (~6s-3min propagation). Wait before treating an
   empty/stale read-back as a failure — poll rather than single-shot.

## Step 3 — Disarm

Redeploy the SAME committed build with the write-enabling overlay removed entirely (no
`ENABLE_BAKED_FLAGS` at all — not even an empty one):

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

## Step 4 — Read the deployment back

GET the live `LV Enrichment` workflow's node bodies again and confirm the write-safety
literal is back to its disabled value (`ALLOW_HUBSPOT_RECORD_WRITES` baked as `"false"`).
This is a DISTINCT step from Step 3 — Step 3 redeploys, Step 4 independently confirms the
redeploy actually took by reading the live artifact, not by trusting the deploy script's
own exit code.

## Pass / fail condition and where the outcome is written

- **Pass**: `company:update` wrote the expected field(s) to `9604614548`, no other record
  changed, and the post-disarm read-back confirms `ALLOW_HUBSPOT_RECORD_WRITES` is back to
  disabled.
- **Fail**: any unexpected write, any record outside the allowlist changing, or the
  post-disarm read-back showing writes still armed.

Either way, replace `human_needed` in the 16.9 row of `19-LEDGER.md` with the observed
result (`passed` or `failed`), and record the execution evidence (execution id, HTTP
status, before/after field values) in that row's Evidence cell — the same evidentiary bar
every other row in this ledger already meets.
