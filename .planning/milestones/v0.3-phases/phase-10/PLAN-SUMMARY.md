---
phase: phase-10
plan: "01"
subsystem: n8n-replica
tags: [fastapi, n8n, docker, decision-service, dry-run]
requires: [run_contact_ingest, dedupe_sweep, hubspot_client]
provides: [decision-service, n8n-workflow-templates, replica-proof]
affects: [requirements.txt, src/service.py]
tech-stack:
  added: [fastapi>=0.115.0, uvicorn>=0.30.0, httpx>=0.27.0]
  patterns: [thin-http-wrapper, in-service-safe-stubs, hard-dry-run]
key-files:
  created:
    - src/service.py
    - tests/test_service.py
    - n8n/wf_upload_ingest.json
    - n8n/wf_weekly_sweep.json
    - scripts/n8n_replica_test.sh
  modified:
    - requirements.txt
decisions:
  - "Decision service is a THIN FastAPI wrapper over run_contact_ingest + dedupe_sweep — zero scoring/merge/dedupe logic reimplemented (P10-SC1)."
  - "dry_run hard-coded True in /ingest (never body-parameterized); HubSpot search/get are in-service SAFE STUBS; allow_create defaults False — no live write possible (P10-SC3)."
  - "Weekly-sweep workflow carries BOTH a scheduleTrigger (production shape, CLAUDE.md §13.4) AND a manualTrigger — n8n v2.4.4 `n8n execute --id` rejects schedule-only workflows as start nodes."
  - "Headless `n8n execute` needs its own task broker; the running main instance holds 5679 in the shared container netns, so the exec uses N8N_RUNNERS_BROKER_PORT=5699 + N8N_RUNNERS_ENABLED=false."
metrics:
  duration: ~35m
  completed: 2026-07-08
status: complete
---

# Phase 10 Plan 01: n8n Template & Local Server Replica Summary

A thin FastAPI decision service (`GET /health`, `POST /ingest`, `POST /sweep`) wraps the
existing `run_contact_ingest` + `dedupe_sweep` Python verbatim, and two importable n8n
v2.4.4 workflow templates drive it from the already-running local Docker n8n — proving the
production-shaped `trigger → set → decision service → dry-run writeback` path with zero live
HubSpot writes and `ALLOW_CONTACT_CREATE` off by default.

## What shipped

- **src/service.py** — FastAPI `app`. `/ingest` calls `run_contact_ingest(path,
  hs_search=stub, hs_get=stub, allow_create=body.allow_create, dry_run=True)` with in-service
  value-routed HubSpot stubs (copied from `tests/test_e2e_ingest.py`); `dry_run` is hard-True,
  `allow_create` defaults False, and the module never calls `load_dotenv` at import (no live
  Haiku, no token leak). `/sweep` calls `dedupe_sweep(records).model_dump()`.
- **tests/test_service.py** — 5 offline hermetic tests (FastAPI TestClient): health, ingest
  dry-run PATCH + create-gate honored, gate flips under allow_create=True, sweep
  duplicate/mangled findings, zero-network sentinel.
- **n8n/wf_upload_ingest.json** — manualTrigger → Set{path, allow_create:false} → httpRequest
  POST `http://host.docker.internal:8088/ingest`.
- **n8n/wf_weekly_sweep.json** — scheduleTrigger (weekly) + manualTrigger → Set{records} →
  httpRequest POST `.../sweep`.
- **scripts/n8n_replica_test.sh** — starts uvicorn (ANTHROPIC key unset), polls /health,
  imports + executes both workflows, asserts the outputs, tears down uvicorn via EXIT trap,
  prints PASS/FAIL.

## Proofs

**Offline gate (authoritative, zero network):**
```
.venv/bin/python -m pytest tests/ -q   ->  83 passed  (78 baseline + 5 new service tests)
.venv/bin/python -c "import src.service"  ->  import ok (no side effect / no network)
```

**Integration proof — `bash scripts/n8n_replica_test.sh` → PASS, exit 0.**
Both workflows imported into the running `n8n` container (v2.4.4) and executed via
`n8n execute --id --rawOutput`. Real execution output (from n8n runData → service response):

Ingest (`POST /ingest`, allow_create=false — every path, dry-run, NO create leaked):
```json
[
 {"row_index": 4, "outcome": "rejected",  "action": "skip",  "reason": "no identity key"},
 {"row_index": 0, "outcome": "match",     "action": "patch", "contact_id": "123"},
 {"row_index": 1, "outcome": "net_new",   "action": "review", "reason": "ALLOW_CONTACT_CREATE is off; staged for review"},
 {"row_index": 2, "outcome": "ambiguous", "action": "review", "reason": "weak-key match requires review"},
 {"row_index": 3, "outcome": "ambiguous", "action": "review", "reason": "no email, insufficient identity"}
]
```
The match row (row 0) carries a full dry-run PATCH body — staging (`csv_email`, `csv_phone`,
`csv_linkedin_url`, …), per-field source metadata (`*_source`, `*_confidence`,
`*_validation_status`, …), and status (`enrichment_status`, `last_enrichment_run_id`, …) — with
NO canonical `email`/`jobtitle`/`linkedin_url` write (non-clobber honored). No live HubSpot call.

Sweep (`POST /sweep`, weekly workflow):
```json
{
 "duplicates": [{"key_type": "email", "key_value": "dup@example.com", "ids": ["c1", "c2"]}],
 "mangled":    [{"id": "c3", "field": "phone", "raw": "not a phone", "reason": "unparseable phone"}],
 "duplicate_count": 1,
 "mangled_count": 1,
 "to_review_ids": ["c1", "c2", "c3"]
}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Weekly-sweep workflow needed a manualTrigger to run headless**
- **Found during:** Task 3 (first sweep execute)
- **Issue:** `n8n execute --id` on the schedule-only workflow failed with "Missing node to
  start execution / Please make sure the workflow you're calling contains an Execute Workflow
  Trigger node." The plan (Task 3) assumed `n8n execute --id` runs schedule-trigger workflows
  from their trigger; in v2.4.4 it does not.
- **Fix:** Added an `n8n-nodes-base.manualTrigger` alongside the retained `scheduleTrigger`
  (both wired into the Set node). The scheduleTrigger keeps the production shape (CLAUDE.md
  §13.4 weekly sweep); the manualTrigger gives the headless CLI a valid start node. The
  upload-ingest workflow already used a manualTrigger and needed no change.
- **Files modified:** n8n/wf_weekly_sweep.json
- **Commit:** af5c0e5

**2. [Rule 3 - Blocking issue] Headless `n8n execute` collided with the running instance's task broker**
- **Found during:** Task 3 (first execute)
- **Issue:** `n8n execute` spins up its own task broker on default port 5679, which the running
  main n8n instance already holds in the shared container network namespace ("Task Broker's
  port 5679 is already in use").
- **Fix:** The script runs the exec with `-e N8N_RUNNERS_BROKER_PORT=5699 -e
  N8N_RUNNERS_ENABLED=false`, moving the exec's broker to a free in-container port and
  disabling runners (core nodes run in-process). Documented in the script header.
- **Files modified:** scripts/n8n_replica_test.sh
- **Commit:** c34d60a

**3. [Rule 1 - Data correctness] Workflow sweep records used `.test` emails that fail validation**
- **Found during:** Task 3 (first successful sweep run: duplicate_count=0, mangled_count=4)
- **Issue:** `dup@lv.test` etc. fail `normalize_email` (invalid TLD), so both dup emails
  normalized to None (no duplicate group) and all three were flagged mangled — the opposite of
  the intended demonstration.
- **Fix:** Switched the workflow's Set-node records to `example.com` domains (matching the
  offline test), yielding duplicate_count=1 + mangled_count=1 as intended.
- **Files modified:** n8n/wf_weekly_sweep.json
- **Commit:** af5c0e5

### Additive note
- `httpx>=0.27.0` added to requirements.txt (FastAPI TestClient dependency; already present in
  the venv). Not a logic dependency.

## Idempotency note
Both workflow JSONs carry a pinned top-level `id` (`LVuploadIngest01`, `LVweeklySweep001`) so
`n8n import:workflow` upserts (updates in place) on re-run and the script executes by known id.
An earlier auto-id import created two stray duplicate copies in the container DB; this n8n build
has no `delete:workflow` CLI, so they remain harmlessly and are never referenced by the script.

## Self-Check: PASSED
- FOUND: src/service.py, tests/test_service.py, n8n/wf_upload_ingest.json,
  n8n/wf_weekly_sweep.json, scripts/n8n_replica_test.sh
- FOUND commits: fa96484 (Task 1), af5c0e5 (Task 2), c34d60a (Task 3)
- 83 tests pass offline; replica script prints PASS with exit 0.
