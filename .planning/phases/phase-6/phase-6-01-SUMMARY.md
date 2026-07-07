---
phase: phase-6
plan: 01
subsystem: file-ingestion
status: complete
tags: [ingestion, csv, xlsx, json, column-mapping, openpyxl]
requires: [phase-5-01]
provides: [ingest_file, IngestBatch, load_rows, column_mapping.yaml]
affects: [phase-7, phase-8]
tech-stack:
  added: ["openpyxl>=3.1.2"]
  patterns: [extension-dispatch, config-driven-alias-table, per-row-try-except]
key-files:
  created:
    - src/file_loader.py
    - src/column_mapper.py
    - config/column_mapping.yaml
    - tests/fixtures/uploads/contacts.csv
    - tests/fixtures/uploads/contacts.json
    - tests/test_file_loader.py
  modified:
    - src/schemas.py
    - requirements.txt
    - tests/test_scaffold.py
decisions:
  - "openpyxl>=3.1.2 approved as the only new dep (stdlib covers csv/tsv/json; no pandas)"
  - "contacts.xlsx generated in-test via openpyxl (no committed binary; deterministic)"
  - "ingest_file row_index is 0-based over data rows (header excluded by load_rows)"
metrics:
  completed: 2026-07-08
  tasks: 5
  files: 9
---

# Phase 6 Plan 01: File Loader & Column Mapper Summary

One extension-dispatched interface (`load_rows`) turns CSV/TSV/JSON/XLSX uploads into a common `list[dict]`; `ingest_file` maps arbitrary headers to the 7 canonical HubSpot contact props and splits rows into a typed `IngestBatch` (accepted + structured rejects) — parse + map + reject-malformed only, no value normalization.

## What was built

- **src/file_loader.py** — `load_rows(path)` dispatches on `Path(path).suffix.lower()`: `.csv/.tsv` → `csv.DictReader` (encoding `utf-8-sig`, BOM-safe), `.json` → stdlib json (top-level list OR `{"contacts":[...]}`/`{"rows":[...]}`), `.xlsx/.xls` → openpyxl (`read_only=True, data_only=True`; header row → keys; blank cell → `""`). Unsupported extension raises `ValueError`. Plus `ingest_file(path) -> IngestBatch` (load → map → identity-split, per-row try/except).
- **src/column_mapper.py** — `map_row(raw_row, mapping)`: case-insensitive, whitespace-collapsed header lookup against the alias table; unmapped columns dropped; non-string keys (csv restkey `None`, xlsx blank header) skipped.
- **config/column_mapping.yaml** — single source of truth: `aliases:` (7 canonical props incl. identity self-mapping) + `required_identity: {any_of: [[email], [firstname, lastname, company]]}`.
- **src/schemas.py** — appended `RejectedRow` (row_index + reason + raw) and `IngestBatch` (rows + rejects).
- **Fixtures + test** — `contacts.csv` (UTF-8 BOM, aliased headers, unmapped `Notes` col, missing-identity row) and `contacts.json`; `contacts.xlsx` generated in-test. 4 offline tests prove same-rows-across-formats, no-identity reject, BOM parse, unsupported-extension raise.

### openpyxl pin
Approved and installed: `openpyxl>=3.1.2` (resolved to 3.1.5). Only transitive dep is `et-xmlfile`.

### column_mapping.yaml alias table
`email` ← email, "email address", "e-mail"; `firstname` ← firstname, "first name", fname, "given name"; `lastname` ← lastname, "last name", surname; `jobtitle` ← jobtitle, "job title", title, position; `linkedin_url` ← linkedin_url, linkedin, "linkedin url", li; `phone` ← phone, mobile, tel; `company` ← company, organization, organisation, account.
`required_identity.any_of = [[email], [firstname, lastname, company]]`.

## Deviations from Plan

**1. [Rule 3 - Blocking] Bumped scaffold config-count guard 5 → 6**
- **Found during:** Task 5 (phase gate)
- **Issue:** `tests/test_scaffold.py::test_configs_load` asserts exactly 5 config YAMLs; adding `config/column_mapping.yaml` (a required Phase 6 artifact) made 6, failing the assertion.
- **Fix:** Updated the assertion to `== 6` and added `assert "aliases" in cfg["column_mapping.yaml"]`. This is a direct, expected consequence of adding the mandated config file, not a scope change to source_registry/field_policy (both untouched).
- **Files modified:** tests/test_scaffold.py
- **Commit:** cdf1616

## Verification

`.venv/bin/python -m pytest tests/test_file_loader.py tests/ -q` → **52 passed** offline (no network, no API key). Baseline was 48 (Milestone 1 + 2); +4 new file-loader tests, zero regression.

## Commits

- 1618aaa feat(phase-6-01): add openpyxl + load_rows extension dispatch
- 42eda76 feat(phase-6-01): add column_mapping.yaml + map_row header remap
- 8295f98 feat(phase-6-01): add IngestBatch/RejectedRow + ingest_file entrypoint
- cdf1616 test(phase-6-01): add upload fixtures + offline file-loader proof

## Self-Check: PASSED
- src/file_loader.py, src/column_mapper.py, config/column_mapping.yaml, src/schemas.py, tests/fixtures/uploads/contacts.csv, tests/fixtures/uploads/contacts.json, tests/test_file_loader.py — all present.
- Commits 1618aaa, 42eda76, 8295f98, cdf1616 — all in git log.
