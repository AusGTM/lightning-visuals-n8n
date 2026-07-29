---
phase: phase-8
plan: 01
subsystem: contact-enrichment-net-new-create
tags: [contacts, ingest, merge, net-new-create, milestone-2, safety]
requires: [phase-6-01, phase-7-01]
provides: [create_record, row_to_provider_result, precreate_email_recheck, run_contact_ingest, main-ingest-cli]
affects: [phase-9, phase-10]
tech-stack:
  added: []
  patterns: [injected-dependency, reuse-existing-merge-engine, gated-dry-run-first, caller-checked-safety-gate, plain-dict-report]
key-files:
  created: [src/ingest.py, tests/test_contact_ingest.py]
  modified: [src/hubspot_client.py, main.py, .env.example]
decisions:
  - "Upload row is just another enrichment SOURCE (csv) through the SAME build_merge_result engine — no second merge engine"
  - "email is manual_protected on ENRICH (never canonical from csv) but written as identity on CREATE (create bypasses merge)"
  - "create_record dry_run short-circuits before requests.post; ALLOW_CONTACT_CREATE checked by CALLER, not client (§21)"
  - "precreate_email_recheck re-runs email EQ immediately before create; any hit downgrades net_new to review"
  - "csv upload_confidence default 80 (not the brief's 60) so contacts thresholds (75-95) actually exercise promote/needs_review"
metrics:
  duration: ~10m
  completed: 2026-07-08
status: complete
---

# Phase 8 Plan 01: Contact Enrichment & Net-New Create Summary

Wires `object_type=contacts` through the existing Milestone-1 pipeline end to end in dry-run: an uploaded file row becomes a `csv`-sourced candidate set that either PATCHes a matched contact through the unchanged non-clobber merge engine, or drives a gated, recheck-guarded net-new create. Zero live writes; the company demo is untouched.

## What was built

- **`src/hubspot_client.py`** — added `create_record(object_type, properties, dry_run=True)` mirroring `patch_record` exactly: `dry_run` prints a POST preview (payload dict only, never the token) and returns `{"dry_run": True, "payload": {...}}` WITHOUT touching `requests`; the live branch POSTs to `/crm/v3/objects/{type}`. The `ALLOW_CONTACT_CREATE` gate is deliberately NOT read here — it is the caller's job (§21).
- **`.env.example`** — added `ALLOW_CONTACT_CREATE=false` beside the other `ALLOW_*` gates (default off).
- **`src/ingest.py`** — `row_to_provider_result` (row → `csv` ProviderResult), `precreate_email_recheck` (email-EQ recheck → id list), and `run_contact_ingest` (batch runner routing match→patch, net_new→create/review, ambiguous→review, reject→skip). HubSpot fns injected for offline tests.
- **`main.py`** — `--ingest <path>` branch under `__main__` (reads `DRY_RUN` + `ALLOW_CONTACT_CREATE` from env, prints the per-row report + an action-count summary); bare `python main.py` still runs `run_local_mvp` unchanged; `import main` stays side-effect-free.
- **`tests/test_contact_ingest.py`** — 5 offline functional tests driving `tests/fixtures/uploads/contacts.csv`.

## Both directions of email handling (the load-bearing correctness claim)

- **ENRICH (match):** `email` is `manual_protected` (min_confidence 95) — the deterministic gate reverts it to stage/needs_review even though `promote_fake` promotes everything upstream, so it NEVER appears in `canonical_patch` or as a bare canonical key. Test asserts `"email" not in canonical_patch` and `"email" not in payload`, while `csv_email` IS present as a staged provider-namespaced value.
- **NET-NEW (create):** create bypasses the merge policy — nothing to protect on a record that does not exist yet — so `email` IS written as the new record's identity. Test asserts `created payload properties["email"] == "alice@example.com"`.

Both assertions pass in the same suite.

## Merge-class behavior proven on the matched row

- `phone` (fill_blank_only, blank in the fetched contact) → promoted, present in `canonical_patch`.
- `jobtitle` (stale_refreshable, present in the fetched contact) → `needs_review`, withheld from `canonical_patch`.
- match path REUSES `build_merge_result`; contacts skip ICP at the merge engine's `object_type == "companies"` guard — no second engine written.

## Net-new gates (both enforced)

- `precreate_email_recheck` returns ids → `action="review"`, reason "dup found on pre-create recheck", NO create (test flips 0-hits→hit on the second email call for the same row to prove it).
- `allow_create=False` → `action="review"`, reason "ALLOW_CONTACT_CREATE is off", NO create.
- create fires ONLY when the recheck is clear AND `allow_create=True`.

## Offline test stub shape

`make_search(email_seq, other)` returns `hs_search(object_type, filters, properties=None, limit=100)` that consumes `email_seq` one results-list per email-EQ call (so resolve→net_new can flip to recheck→dup), and returns 0 hits for non-email keys so a no-email row lands ambiguous. `make_get` returns a contact with blank `phone` + present `jobtitle`/`email`. `classify_field_with_haiku` is monkeypatched at the `src.merge_policy` import site; `requests.get/post/patch` are autouse sentinels that raise if hit; `HUBSPOT_PRIVATE_APP_TOKEN` + `ANTHROPIC_API_KEY` deleted in-test.

## Deviations from Plan

None — plan executed exactly as written. (The `csv` confidence default of 80 vs the CLAUDE.md brief's example 60 is a pre-declared deviation documented in the plan action and carried as a `# ponytail:` note in `row_to_provider_result`; it is required for any contacts field to clear its 75-95 threshold.)

## Verification

- `.venv/bin/python -m pytest tests/test_contact_ingest.py tests/ -q` → **69 passed** offline (64 Milestone-1/2 baseline + 5 new), no network, no HUBSPOT token, no ANTHROPIC key. Zero regression.
- `run_local_mvp()` returns the assembled patch dict offline (company demo intact); `import main` is side-effect-free.

## Commits

- c0bd0bf feat(phase-8-01): gated dry-run create_record on HubSpot client
- bc3da15 feat(phase-8-01): contact ingest — row->csv candidate, recheck guard, batch runner
- ad1745c feat(phase-8-01): main --ingest entrypoint + offline contact-ingest proof

## Self-Check: PASSED

All artifacts present on disk (src/hubspot_client.py, src/ingest.py, main.py, .env.example, tests/test_contact_ingest.py, this SUMMARY); all three task commits present in git history.
