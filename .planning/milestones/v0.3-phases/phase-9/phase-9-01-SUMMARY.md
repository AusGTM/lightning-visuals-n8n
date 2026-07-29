---
phase: phase-9
plan: 01
subsystem: functional-e2e-tests-dedupe-sweep
tags: [contacts, ingest, dedupe, sweep, e2e, tests, milestone-2, safety]
requires: [phase-6-01, phase-7-01, phase-8-01]
provides: [dedupe_sweep, SweepReport, contacts_e2e-fixture, e2e-ingest-proof, live-haiku-smoke]
affects: [phase-10]
tech-stack:
  added: []
  patterns: [normalize-before-compare, pure-injected-list, value-routed-search-stub, hermetic-offline-tests, non-gating-live-smoke, plain-dict-findings]
key-files:
  created: [src/sweep.py, tests/test_sweep.py, tests/fixtures/uploads/contacts_e2e.csv, tests/test_e2e_ingest.py, tests/live_smoke_contact.py]
  modified: [src/schemas.py]
decisions:
  - "dedupe_sweep compares NORMALIZED keys only (normalize_email/normalize_phone/canonicalize_linkedin) — raw-string compare would miss the '0412...' vs '+61412...' phone dup"
  - "SweepReport findings are plain JSON-serializable dicts (ingest.py report style); no per-finding sub-models (Phase-10 transport, YAGNI)"
  - "to_review_ids is a sorted-unique LIST with set semantics — a real set is neither ordered nor JSON-serializable"
  - "E2E hs_search is VALUE-routed (not call-counted); the same alice@ value returns [] on both resolve and pre-create recheck, so the net_new create proceeds without a counter"
  - "live smoke self-bootstraps project root on sys.path so the documented `python tests/live_smoke_contact.py` command works from tests/"
metrics:
  duration: ~15m
  completed: 2026-07-08
status: complete
---

# Phase 9 Plan 01: Functional + E2E Tests & Dedupe Sweep Summary

Proves the whole Milestone-2 contact-ingestion behavior end to end on one realistic multi-row file (every path at once), adds the weekly dedupe/mangled maintenance sweep (CLAUDE.md §13.4 Workflow D) as a pure classify-only function, and confirms the full suite stays green offline plus one non-gating live-Haiku smoke. No new dependencies, no production wiring (n8n is Phase 10).

## What was built

- **`src/sweep.py`** — `dedupe_sweep(records: list[dict]) -> SweepReport`. Groups on NORMALIZED email/phone/linkedin keys (reuses `normalize_email`/`normalize_phone`/`canonicalize_linkedin`), ≥2 ids per key → duplicate finding; per-record mangled detection flags non-empty raw email/phone that normalizes to `None`. Pure, offline, injected in-memory list; classify-only (flags to needs_review, never writes). Phone dedup keys on the `phone` property only (mobilephone out of scope this phase).
- **`SweepReport` in `src/schemas.py`** — `duplicates`/`mangled` (plain dict lists), `duplicate_count`/`mangled_count`, `to_review_ids` (sorted-unique list, set semantics).
- **`tests/test_sweep.py`** — 5 offline tests on an inline record list: exact duplicate groups, exact mangled findings, counts, sorted-unique `to_review_ids` union, determinism, and clean-record exclusion.
- **`tests/fixtures/uploads/contacts_e2e.csv`** — 5 rows, one per path (match+enrich, net-new create, ambiguous weak-key, no-email→never-create, rejected-at-load).
- **`tests/test_e2e_ingest.py`** — 4 offline tests driving `run_contact_ingest` once through all five paths with a value-routed `hs_search` + injected `hs_get`, monkeypatched `classify_field_with_haiku`, and raise-on-call `requests.*` sentinels.
- **`tests/live_smoke_contact.py`** — standalone (not pytest-collected) non-gating live-Haiku one-shot.

## The load-bearing proofs

- **Phone normalize-before-compare (P9-SC2):** `test_phone_dup_proves_normalize_before_compare` asserts raw `"+61412345678"` (id 3) and raw `"0412 345 678"` (id 4) collapse to a SINGLE `{key_type:"phone", key_value:"+61412345678", ids:["3","4"]}` group. A raw-string compare fails this — normalization is load-bearing, not incidental. **PASSES.**
- **Email manual_protected on enrich (P9-SC1):** `test_match_row_field_invariants` asserts `"csv_email" in payload` (staged) but `"email" not in canonical_patch` and `"email" not in payload` — email is never a bare canonical write from an upload. Alongside: blank `phone` filled (fill_blank_only), conflicting `jobtitle` withheld (stale_refreshable→needs_review), present `linkedin_url` never clobbered (fill_blank_only staged as `csv_linkedin_url`). **PASSES.**
- **Bounded writes:** exactly ONE create total; Row D (no email) asserted to NEVER create; create writes `email == "alice@example.com"` as the new record's identity.

## Verification

- `.venv/bin/python -m pytest tests/ -q` → **78 passed** offline (69 baseline + 5 `test_sweep.py` + 4 `test_e2e_ingest.py`), zero network, no HUBSPOT token, no ANTHROPIC key. Zero regression.
- Live smoke (real ANTHROPIC key, HubSpot mocked, dry_run, allow_create=False):
  `LIVE SMOKE PASS: matched contact 123 enriched via real Haiku; emitted a dry-run patch with 2 canonical field(s), zero HubSpot writes.` — exit 0, non-gating. The `api.hubapi.com` URL appears only in the dry-run printed payload preview; no real HubSpot call fired (anthropic SDK uses httpx, not the requests HubSpot client).

## Deviations from Plan

- **[Rule 3 - blocking issue] live smoke sys.path bootstrap.** The documented command `python tests/live_smoke_contact.py` runs with `tests/` (not the project root) on `sys.path`, so `from src.ingest import ...` raised `ModuleNotFoundError` and the script exited non-zero before the try/except. Fixed by inserting the project root into `sys.path` at the top of the script (commit 10f1f54). Without this the non-gating smoke could not run at all. No behavior change to any offline test.
- Commit scope tags use `(09-01)` rather than the prior phases' `(phase-N-01)` form — cosmetic only, not amended.

## Commits

- 90c6eb9 test(09-01): add failing dedupe/mangled sweep proof (RED)
- 5304f51 feat(09-01): dedupe/mangled sweep + SweepReport schema (GREEN)
- 9ad1226 test(09-01): multi-row E2E ingestion matrix
- b992257 test(09-01): non-gating live-Haiku contact smoke
- 10f1f54 fix(09-01): bootstrap project root on sys.path in live smoke

## TDD Gate Compliance

Task 1 followed RED→GREEN: `test(09-01)` failing-test commit (90c6eb9, `ModuleNotFoundError: No module named 'src.sweep'`) precedes the `feat(09-01)` implementation (5304f51). No REFACTOR needed.

## Self-Check: PASSED

All artifacts present on disk (src/sweep.py, SweepReport in src/schemas.py, tests/test_sweep.py, tests/fixtures/uploads/contacts_e2e.csv, tests/test_e2e_ingest.py, tests/live_smoke_contact.py, this SUMMARY); all five commits present in git history.
