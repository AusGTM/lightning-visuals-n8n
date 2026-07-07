---
phase: phase-5
plan: 01
subsystem: contact-normalization
tags: [mvp, contacts, normalizer, phone, email, seniority, fixtures, config]
requires: [src/normalizer.py, src/schemas.py, config/provider_priority.yaml, config/source_registry.yaml, tests/fixtures]
provides: [normalize_phone, normalize_email, normalize_seniority, csv-upload-source, contact-fixtures]
affects: [phase-6-file-loader, phase-7-identity-resolver, phase-8-contact-enrichment]
tech-stack:
  added: [phonenumbers, email-validator]
  patterns: [pure-normalizer-never-raises, offline-email-validation, token-safe-keyword-scan, region-aware-e164]
key-files:
  created: [tests/fixtures/contact_current.json, tests/fixtures/provider_apollo_contact.json, tests/fixtures/provider_lusha_contact.json, tests/fixtures/provider_zoominfo_contact.json, tests/test_contact_normalizer.py]
  modified: [src/normalizer.py, config/provider_priority.yaml, config/source_registry.yaml]
decisions:
  - "normalize_seniority matches short abbreviations (ceo/cto/cro...) as whole word tokens, not substrings (Rule 1 fix): 'Director of Ops' contains the substring 'cto' and would misclassify as c_suite; a regex token split fixes it"
  - "jobtitle has no dispatch branch: normalize_text (the fallback) already trims + collapses whitespace, which is the exact jobtitle normalization; a comment marks this so no future reader re-adds normalize_jobtitle"
  - "normalize_email uses check_deliverability=False so the suite is fully offline (no DNS); result.normalized.lower() lowercases both domain and local part for CRM dedupe"
metrics:
  duration: ~5m
  completed: 2026-07-08
status: complete
---

# Phase 5 Plan 01: Contact Foundation Summary

Extends the already-shipped engine to contacts without building a new subsystem: `src/normalizer.py` gains three pure, offline, never-raising contact-field coercers (phone → E.164, email validate + lowercase, seniority → canonical set) wired into `normalize_field`; the upload/CSV path is registered as a declared merge source; contact fixtures with intentional cross-provider conflict are added — all proven by a 6-test offline file with zero regression to the 42 Milestone 1 company tests (48 passing total).

## Files Created

- `tests/fixtures/contact_current.json` — HubSpotRecord (`object_type=contacts`, id 123): email present (manual_protected demo), jobtitle "Sales Manager" (stale_refreshable conflict demo), phone "" (fill_blank_only demo). Commit `b9eec0e`.
- `tests/fixtures/provider_{apollo,lusha,zoominfo}_contact.json` — ProviderResult fixtures with conflicting jobtitle/seniority (apollo VP vs zoominfo Director) and phone/mobile spread across lusha for Phase 8 merge demos; synthetic data only (example.com, non-real numbers). Commit `b9eec0e`.
- `tests/test_contact_normalizer.py` — offline proof of every normalizer branch (valid/malformed/empty), `normalize_field` dispatch, company no-regression spot check, four-fixture parse. Commit `de5124b`.

## Files Modified

- `src/normalizer.py` — added `normalize_phone` / `normalize_email` / `normalize_seniority`; added phone/mobilephone/email/seniority branches to `normalize_field` before the text fallback. No existing company branch or `provider_to_candidates` touched. Commit `209bcd0`.
- `config/source_registry.yaml` — added `csv` source (type upload, trust_rank 60, can_promote_directly false, declarable-trust note, supported_signals). Commit `07dbbdb`.
- `config/provider_priority.yaml` — reordered contact phone/mobilephone/email to lusha-first (§6.3 specialty); header comment amended to document the exception. Commit `07dbbdb`.

## Key Outputs (per plan)

**normalize_seniority keyword map** (ordered; phrases = substring match, abbrevs = whole-token match):

| canonical  | phrases                                              | token abbrevs                  |
|------------|------------------------------------------------------|--------------------------------|
| vp         | vice president                                       | vp                             |
| c_suite    | chief, president, founder, owner, c-suite            | ceo, cfo, coo, cto, cro, cmo   |
| director   | director                                             | —                              |
| manager    | manager, head of, supervisor                         | head, lead                     |
| individual | account executive, executive, analyst, associate, specialist, coordinator, representative, engineer, consultant | — |

Empty / None / no-match → `unknown`. Every output ∈ {c_suite, vp, director, manager, individual, unknown}.

**provider_priority contact ordering after the lusha reorder:**
- `phone: [lusha, zoominfo, apollo, claude_web]`
- `mobilephone: [lusha, zoominfo, apollo, claude_web]`
- `email: [lusha, apollo, zoominfo, claude_web]`
- `jobtitle` / `linkedin_url` / `seniority` / `persona_group`: `[zoominfo, apollo, lusha, claude_web]` (unchanged)

## Deviations from Plan

**1. [Rule 1 - Bug] `normalize_seniority` abbreviation matching switched from substring to whole-token**
- **Found during:** Task 1 verify. Initial substring scan misclassified `'Director of Ops'` as `c_suite` because the string "dire**cto**r" contains the abbreviation "cto".
- **Fix:** Split the input on non-alphabetic chars into a token set; short abbreviations (ceo/cto/cro...) match token membership, multi-word phrases still match as substrings. Documented inline.
- **Files:** `src/normalizer.py`. Commit `209bcd0`.

Otherwise the plan executed exactly as written. No architectural changes, no auth gates, no new dependencies (phonenumbers + email-validator already pinned/installed).

## Verification

Phase gate (offline, no network, no API key), run from repo root:

```
.venv/bin/python -m pytest tests/test_contact_normalizer.py tests/ -q
→ 48 passed in 0.77s
```

42 Milestone 1 company tests unregressed + 6 new contact tests green. `normalize_email(check_deliverability=False)` guarantees no DNS, so the suite is fully offline.

## Threat Mitigations Applied

- **T-phase5-01 (DoS):** `normalize_phone`/`normalize_email` guard empty/None and catch NumberParseException/EmailNotValidError → None, never raise. Asserted (`'abc'`, `'not-an-email'` → None).
- **T-phase5-02 (Info disclosure):** fixtures are synthetic (example.com, non-real numbers); no real PII in git.
- **T-phase5-03 (Info disclosure):** `check_deliverability=False` → no DNS lookup of contact domains.
- **T-phase5-SC (supply chain):** no new packages installed; deps already vendored.

## Self-Check: PASSED

All 8 artifacts present on disk; all 4 task commits (209bcd0, 07dbbdb, b9eec0e, de5124b) in git history.
