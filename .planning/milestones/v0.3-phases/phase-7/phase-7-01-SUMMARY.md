---
phase: phase-7
plan: 01
subsystem: identity-dedupe-resolver
tags: [identity, dedupe, classification, milestone-2, safety]
requires: [phase-6-01]
provides: [resolve_identity, resolve_batch, IdentityResult, canonicalize_linkedin]
affects: [phase-8]
tech-stack:
  added: []
  patterns: [injected-dependency, pure-deterministic-classifier, conservative-default-to-review]
key-files:
  created: [src/identity.py, tests/test_identity.py]
  modified: [src/schemas.py]
decisions:
  - "No-email row is NEVER net_new (hard safety rule) — routes to ambiguous/review"
  - "Confident match only on a single hit of a strong key (email OR linkedin_url)"
  - "Weak keys (phone+lastname, name+company) can only ever produce ambiguous"
  - "HubSpot search injected (default search_records) so classification is offline-testable"
metrics:
  duration: ~8m
  completed: 2026-07-08
status: complete
---

# Phase 7 Plan 01: Identity / Dedupe Resolver Summary

Conservative, pure, offline-testable identity classifier that labels each accepted Phase-6 row as `match` / `net_new` / `ambiguous` BEFORE any write, encoding the Milestone-2 policy "auto-match only on email/LinkedIn; no-email never auto-creates; ambiguous -> review".

## What was built

- **`src/schemas.py`** — appended `IdentityResult(outcome: Literal["match","net_new","ambiguous"], contact_id: Optional[str]=None, match_key: Optional[str]=None, candidate_ids: List[str]=[], reason: str)`, matching existing model style, no new imports.
- **`src/identity.py`** — `resolve_identity(row, hs_search=search_records)` implementing the strict ordered algorithm, plus `resolve_batch`, `canonicalize_linkedin`, and a private `_search_ids` parser.
- **`tests/test_identity.py`** — 12 offline tests, canned-dict mock search, every outcome asserted.

## resolve_identity key order + exact net_new condition

Strict order: **email → linkedin_url → phone+lastname → firstname+lastname+company**.

- email single hit → `match` (contact_id set, match_key="email")
- email >1 hit → `ambiguous` (match_key="email", all ids in candidate_ids)
- **email 0 hits → `net_new`** — the ONLY route to net_new: a valid email present AND email search returns zero hits (reason "valid email, no existing match")
- no valid email → linkedin single/multi hit → match/ambiguous; else fall through
- weak keys: any non-empty hit → `ambiguous` (never match, never net_new)
- **HARD RULE** (dedicated inline comment + dedicated test): no valid email AND no confident match AND no weak-key candidate → `ambiguous`, reason "no email, insufficient identity". A no-email row can NEVER become net_new.

## LinkedIn canonicalization rule

`canonicalize_linkedin`: None on falsy/blank; prefix `https://` when no `//`; lowercase scheme + host; strip a single trailing slash from path; drop query/fragment. Path case preserved (e.g. `/in/Alice` stays). Yields a deterministic EQ-search key.

## Mock-search stub shape (tests)

`make_search(canned)` returns `hs_search(object_type, filters, properties, limit=100)` that keys off `filters[0]["propertyName"]`, returns the mapped `{"results":[...],"total":N}` (default zero hits), and records every call on `hs_search.calls`. Pure canned dicts — no requests, no token, no network. An injection test asserts `len(s.calls) >= 1` proving the injected search (not the real `search_records`) was used.

## HARD RULE test confirmation

`test_no_email_no_hits_is_ambiguous_never_net_new` exists, is dedicated to the core safety property (with a naming comment), and passes — asserts outcome `ambiguous`, `!= net_new`, reason "no email, insufficient identity". `test_invalid_email_takes_no_email_path_and_is_ambiguous` covers the mangled-email → no-email path.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

`.venv/bin/python -m pytest tests/test_identity.py tests/ -q` → **64 passed** offline (52 Milestone-1/2 baseline + 12 new), no network, no HUBSPOT token. Zero regression.

## Boundary honored

Classification only. No create, no PATCH, no real HubSpot call, no main.py wiring — those remain Phase 8.

## Commits

- 7780266 feat(phase-7-01): add IdentityResult schema
- 383ca94 feat(phase-7-01): add resolve_identity ordered dedupe resolver
- 6af20ee test(phase-7-01): offline proof of every identity outcome

## Self-Check: PASSED

All artifacts present on disk (src/schemas.py, src/identity.py, tests/test_identity.py, this SUMMARY); all three task commits present in git history.
