---
phase: 23-walking-skeleton-plugin-shell-tabular-dispatch
plan: 05
subsystem: infra
tags: [claude-plugin, preview, skill, documentation]

requires:
  - phase: 23-04
    provides: config_gate.py, tabular.py, dispatch.py, plugin.json, SKILL.md placeholder preview step
provides:
  - "operator-claude-plugin/scripts/preview.py — label_headers(), build_preview(): adaptive, display-only preview reading config/column_mapping.yaml as a read-only lookup, never a transform"
  - "operator-claude-plugin/skills/contact-upload/SKILL.md step 3 — the real preview replacing the 23-04 marker"
  - "operator-claude-plugin/README.md — one-time setup, giving it a file, and preview/approve/arm sections; stale 'planned, not yet implemented' status and admin-provisioned wording corrected"
  - ".planning/workstreams/plugin-entrypoint/REQUIREMENTS.md — PLUGIN-02 reworded to match D-05 (operator self-setup)"
affects: [23-06, 24]

tech-stack:
  added: []
  patterns:
    - "Preview computed as structured data (dict), never pre-rendered markdown — the
      skill owns rendering (markdown table by default, Artifact on request), matching
      D-09's one-rendering-convention intent"
    - "Header normalization reimplemented locally in preview.py (strip, collapse
      whitespace, lowercase) rather than importing the backend's mapper — mirrors the
      documented rule exactly instead of improving on it, per D-07 and the
      no-fuzzy-matching research pitfall"

key-files:
  created:
    - operator-claude-plugin/scripts/preview.py
    - operator-claude-plugin/tests/test_preview_rendering.py
  modified:
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md

key-decisions:
  - "build_preview() also reports outgoing_bytes (via tabular.to_csv_bytes(path)) as an
    addition beyond the plan's literal ask, so the approval step can describe the actual
    wire payload size, not just row count — matches the plan action text's own framing
    ('the outgoing byte count or row count alongside')."
  - "Mapping-file resolution order implemented exactly as specified: explicit
    mapping_path argument, then repo config/column_mapping.yaml relative to the plugin
    root, then unavailable (labels flagged null, never guessed)."
  - "Fixed two stale README passages beyond the plan's literal three-section ask: the
    top-of-file 'Status: planned, not yet implemented' banner (contradicted the setup
    instructions being added) and the Operator-model bullet asserting the operator
    'never handles a secret' (the exact PLUGIN-02 conflict D-05 already flagged, just in
    a second file). Left uncorrected, both would have reintroduced the same
    admin-provisioned/self-setup contradiction Task 3 exists to resolve, one file over."

requirements-completed: [PREVIEW-01, PREVIEW-04, PLUGIN-02]

coverage:
  - id: D1
    description: "label_headers() maps a source header to its canonical prop via config/column_mapping.yaml, case-insensitively and whitespace-collapsed, matching Map Columns' own documented rule; an unrecognized header is reported dropped"
    requirement: "PREVIEW-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_label_headers_maps_known_alias_case_insensitively_and_whitespace_collapsed"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_label_headers_reports_unknown_header_as_dropped"
        status: pass
    human_judgment: false
  - id: D2
    description: "build_preview() renders every row for a small batch and the first-10/last-3/fill-rate view for a >20-row batch, reporting dropped headers and canonical props no header maps to"
    requirement: "PREVIEW-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_build_preview_small_batch_returns_every_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_build_preview_large_batch_returns_leading_10_trailing_3_and_fill_rates"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_build_preview_reports_dropped_headers_and_unmapped_canonical_props"
        status: pass
    human_judgment: false
  - id: D3
    description: "build_preview() mutates nothing (source file bytes identical before/after), performs no network call, and degrades gracefully (flags labels unavailable rather than guessing) when the mapping file is absent"
    requirement: "PREVIEW-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_build_preview_mutates_nothing_source_bytes_identical"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_build_preview_performs_no_network_call"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_build_preview_with_mapping_absent_still_returns_headers_rows_and_counts"
        status: pass
    human_judgment: false
  - id: D4
    description: "SKILL.md step 3 drives the real preview.py, renders as a markdown table by default (Artifact on request), and states the decline path sends nothing; README documents one-time setup, file handoff, and preview/approve/arm meaning so an operator can self-serve from the README alone"
    requirement: "PREVIEW-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py#test_skill_body_references_only_scripts_that_exist_on_disk"
        status: pass
      - kind: manual
        ref: "grep -c preview operator-claude-plugin/skills/contact-upload/SKILL.md (>=1); grep -c operator.local.example.json operator-claude-plugin/README.md (>=1)"
        status: pass
    human_judgment: false
  - id: D5
    description: "PLUGIN-02 reworded to describe operator self-setup from the tracked example file (D-05), replacing the admin-provisioned / operator-never-handles-a-secret wording it conflicted with; traceability totals unchanged"
    requirement: "PLUGIN-02"
    verification:
      - kind: manual
        ref: "grep -c PLUGIN-02 .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md; grep -c 'Coverage: **49 / 49**' .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md (both >=1)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-31
status: complete
---

# Phase 23 Plan 05: Adaptive Preview, Skill Wording, Operator Docs, PLUGIN-02 Reconciliation Summary

**`preview.py`'s `label_headers()`/`build_preview()` give the operator, before any byte is sent, the row count, the source-header-to-canonical-prop labelling (mirroring `Map Columns`' own case-insensitive/whitespace-collapsed rule as a read-only lookup, never a transform), and — above a 20-row threshold — first-10/last-3 sample rows with per-column fill rates; the skill and README now teach the real preview and one-time setup end to end, and PLUGIN-02's wording finally matches the operator-self-setup decision it was written against.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3
- **Files created:** 2 (`preview.py`, its test file)
- **Files modified:** 4 (`SKILL.md`, `README.md`, `CHANGELOG.md`, `REQUIREMENTS.md`)

## Accomplishments

- `preview.py` exposes `label_headers(headers, mapping_path)` and
  `build_preview(path, mapping_path=None)`, both pure/read-only: no network call, no file
  mutation (asserted by byte-identity test), and the mapping YAML is consulted only to
  label — never to transform a row headed for the wire.
- Mapping-file resolution follows the plan's exact order: explicit `mapping_path`
  argument → repo's `config/column_mapping.yaml` relative to plugin root → unavailable
  (labels flagged `None`, never guessed).
- Adaptive scope (D-08) implemented exactly: ≤20 rows returns every row under
  `sample_rows`; above that, `sample_rows.leading` (10) / `.trailing` (3), plus
  `fill_rates` per source column — including dropped ones, since a column the backend
  drops is exactly what the operator needs to notice.
- `build_preview()` also reports `outgoing_bytes` (from `tabular.to_csv_bytes`) alongside
  `row_count`, so the approval step can describe the actual payload rather than an
  approximation.
- SKILL.md's step 3 replaces the 23-04 `PREVIEW-STEP-OWNER` marker with the real preview
  invocation and rendering instructions: markdown table by default, Artifact only on
  request, dropped headers and unmapped canonical props called out explicitly, decline
  path stated as free.
- README gains three new operator-facing sections (one-time setup, giving it a file,
  what the preview/approve/arm mean) and two stale passages are corrected: the top banner
  ("planned, not yet implemented" → "one lane implemented") and the Operator-model bullet
  that asserted the operator "never handles a secret," which directly conflicted with the
  setup section being added in the same file.
- PLUGIN-02 in REQUIREMENTS.md reworded to state what D-05 actually decided — operator
  self-setup from the tracked example file — while preserving every part that still
  binds (nothing committed, no secret displayed back, provider/HubSpot credentials stay
  in n8n). Traceability totals (`49 / 49`) unchanged.

## Task Commits

1. **Task 1: Adaptive preview with display-only column labelling** - `803b662` (feat)
2. **Task 2: Skill preview/approve/arming wording and operator documentation** - `26e18e1` (docs)
3. **Task 3: Reconcile PLUGIN-02's wording with the operator-self-setup decision** - `854caf8` (docs)

## Files Created/Modified

- `operator-claude-plugin/scripts/preview.py` - `label_headers()`, `build_preview()`, `__main__` JSON CLI
- `operator-claude-plugin/tests/test_preview_rendering.py` - 8 tests covering labelling, adaptive scope, fill rates, byte-identity, no-network, mapping-absent degradation
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - step 3 rewritten to drive the real preview
- `operator-claude-plugin/README.md` - status banner, operator-model wording, three new sections, corrected Layout tree
- `operator-claude-plugin/CHANGELOG.md` - phase 23 entry added under Unreleased/Added, removed from Planned
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` - PLUGIN-02 reworded

## Decisions Made

- **`outgoing_bytes` added to the preview payload.** Not explicitly named as a required
  field in `<behavior>`, but the plan's action text asks for "the outgoing byte count or
  row count alongside" the preview — implemented via the same `tabular.to_csv_bytes()`
  the dispatch path itself uses, so the number reported is the exact wire size, not an
  estimate.
- **Two README passages fixed beyond the plan's literal three-section instruction.** The
  top-of-file status banner and the Operator-model "never handles a secret" bullet both
  pre-dated D-05 and directly contradicted the setup instructions this plan adds in the
  same file. Leaving them would have reproduced, in README.md, the exact
  admin-provisioned/self-setup contradiction Task 3 exists to fix in REQUIREMENTS.md —
  documented here as a deviation (Rule 1: fixing a factually-broken statement) rather
  than left unaddressed.
- **Layout section rewritten with the real file tree** rather than left listing only
  README/CHANGELOG, since it now actively contradicted the setup section that tells the
  operator exactly which files exist and what they do.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] README status banner and Operator-model bullet contradicted the setup section being added**
- **Found during:** Task 2, while reading the existing README before extending it
- **Issue:** The banner said "Status: planned, not yet implemented" and the
  Operator-model bullet said "Configuration is admin-provisioned... The operator never
  sees, pastes, or handles a secret" — both false since 23-04 shipped the implementation
  and D-05 moved config setup to the operator. Left as-is, the new one-time-setup section
  this task adds would have directly contradicted text three paragraphs above it in the
  same file.
- **Fix:** Updated the banner to reflect phase 23 as implemented, and reworded the
  Operator-model bullets to describe the one-time setup exception explicitly rather than
  asserting a blanket "no secrets, ever, admin-provisioned" claim that no longer held.
- **Files modified:** `operator-claude-plugin/README.md`
- **Verification:** Full plugin test suite still green (`test_plugin_manifest.py` does
  not assert on README prose, so no test regression risk; reviewed by inspection).
- **Committed in:** `26e18e1` (Task 2 commit)

---

**Total deviations:** 1 (Rule 1 auto-fix, documentation-only, no code or test surface
affected).
**Impact on plan:** None beyond the stated fix — no scope creep, no backend file touched,
no test behavior changed.

## Issues Encountered

None.

## User Setup Required

None — this plan's own deliverable *is* the one-time setup documentation. No external
service configuration was performed or required to execute this plan.

## Next Phase Readiness

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 41 passed (33 baseline +
  8 new preview tests), no regressions.
- `.venv/bin/python -m pytest -q` (full repo suite) — 749 passed (up from 741 at the end
  of 23-04), no regressions.
- `git diff --name-only bb72388..HEAD` (this phase's full commit range) touches no file
  under `n8n/`, `config/`, `src/`, or `scripts/` — confirmed by direct check, not just
  asserted.
- Phase 23's five success criteria (operator can see what will be sent/dropped before
  approving; declining leaves no side effect beyond a file read; plugin contains exactly
  one mapper's worth of logic — none) are now backed by both code and documentation.
- PLUGIN-02's checkbox/traceability-status flip (Pending → Complete) is left to the
  executor's standard `requirements mark-complete` state-update step, per this plan's
  `requirements:` frontmatter listing `PLUGIN-02` as completed by this plan — not
  hand-edited here to avoid duplicating that step's job.
- Backend D-15/D-16/D-16a's `allow_create` fix (flagged outstanding in `23-04-SUMMARY.md`)
  remains outstanding and out of this plan's scope; still needed before the phase can
  demonstrate its full end-to-end flow per `23-CONTEXT.md` D-18.

---
*Phase: 23-walking-skeleton-plugin-shell-tabular-dispatch*
*Completed: 2026-07-31*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
