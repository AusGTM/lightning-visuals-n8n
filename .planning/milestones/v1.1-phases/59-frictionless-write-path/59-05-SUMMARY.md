---
phase: 59-frictionless-write-path
plan: 05
subsystem: operator-claude-plugin (ingest lane) + planning artifacts
tags: [D-59-08, extraction, identity-gate, provenance, gate-inventory]
dependency-graph:
  requires:
    - "59-04 (plan sequencing — no functional dependency)"
    - "Phase 58's company_domain.py (resolve/confirm/decline precedent, reused not reinvented)"
  provides:
    - "extraction.RESOLUTION_SOURCES (closed vocabulary)"
    - "extraction.ExtractionResult.resolvable"
    - "extraction artifact record key `resolutions` (optional)"
    - "preview.build_extracted_preview's `resolvable` key"
    - ".planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md"
  affects:
    - "59-06 (owns GATE-02..06 — enrichment.py's identity gaps, write_grant.py's FINDING-1 empty-record-set refusal)"
tech-stack:
  added: []
  patterns:
    - "resolve-then-propose, never resolve-then-silently-fill (company_domain.py precedent, widened)"
    - "closed-vocabulary provenance enforced at construction, not by convention (T-59-20 anti-laundering)"
    - "additive classification alongside an unchanged rejection (T-59-22, no existing reader's behaviour changes)"
key-files:
  created:
    - .planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md
    - operator-claude-plugin/tests/test_extraction_resolvable.py
  modified:
    - operator-claude-plugin/scripts/extraction.py
    - operator-claude-plugin/scripts/preview.py
    - operator-claude-plugin/tests/test_no_invention_structural.py
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
decisions:
  - "Gate-selection tie-break: when two identity groups tie on missing-field count, the group with MORE fields already present wins — not raw list order — so a firstname+lastname-only contact row reports 'missing company' rather than 'missing email' (both are 1-field-away, but company is the group the operator has already given more information toward)."
  - "resolutions validated BEFORE the identity check, as a record-level key (never a row key), so the canonical-prop strip never touches it and a record naming an illegitimate source or an absent-value field is rejected before reaching the identity gate at all."
  - "resolvable computed against the RAW artifact index (same as rejected), never remapped through the per-type dedupe/reassembly the way ambiguities are — it is reported against the record as originally written."
metrics:
  duration: ~50min
  completed: 2026-08-28
status: complete
actuals:
  tokens: 11733
  tasks: 3
  commits: 3
---

# Phase 59 Plan 05: Gate inventory + identity gate resolve-and-propose Summary

Inventoried all 16 operator-facing refuse-and-stop gates across ingest/enrichment/grant/
preingest/chunking/config and converted the one D-59-08's ruling was actually taken at —
`extraction.py`'s identity gate — from refuse-and-stop into refuse-and-classify-as-proposable,
with a closed-vocabulary anti-laundering control on any Claude-resolved value.

## What Was Built

**Task 1 — Gate inventory.** `.planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md`
decides 16 gates: 1 `CONVERT` owned by this plan (`extraction.py`'s identity gate), 5
`CONVERT` named as candidates for 59-06 (`enrichment.py`'s people/companies identity gaps,
`write_grant.py`'s empty-record-set refusal — FINDING 1 of the Phase 53 walk), 2
`ALREADY-CONVERTED` (`company_domain.py`, preingest's `unmatched` bucket), and 8
`NOT-APPLICABLE` rows each carrying the phrase "no legitimate resolution source" — malformed
input, empty batches, admin-only config values (`config_gate.ConfigError` stated explicitly as
the canonical case), file-integrity write guards (`name_split.py`), and security allowlists
(`header_suggest.py`). Zero difficulty dismissals. `Unplanned items` is empty and says why.

**Task 2 — The identity gate conversion.**
- `extraction.ExtractionResult` gains `resolvable` (default `[]`), ADDITIVE to `rejected` — the
  existing `rejected.append(...)` at the identity-gate branch is untouched; a
  `resolvable.append(...)` runs alongside it. Every existing reader (`preview.py`, the CLI)
  sees exactly what it saw before this change.
- Each `resolvable` entry: `{"index", "record_type", "missing", "reason"}`. `missing` is
  computed from the record type's own `identity_groups()` (never a hardcoded field list),
  picking the group with fewest absent fields; ties are broken toward the group with more
  fields already present (see Decisions above).
- `extraction.RESOLUTION_SOURCES` — a frozenset of exactly `hubspot_lookup`,
  `operator_statement`, `provider_result`, `same_row_derivation`. A record's optional
  `resolutions` key (a record-level list, never a row key) is validated BEFORE the identity
  check: not-a-list, a non-dict entry, a `field` the cleaned row does not actually carry a
  value for, or a `source` outside `RESOLUTION_SOURCES` — any of these rejects the whole
  record, naming the offending value. A validated `resolutions` list carries through onto the
  `accepted` entry (empty list, not a missing key, when absent) and merges across `dedupe()`
  the same way `provenance` already does — concatenated, never dropped.
- D-07's contradiction pass is untouched: a resolved field an ambiguity also names still
  rejects the record. Verified by a dedicated test.
- `preview.build_extracted_preview` returns `resolvable` via `getattr(result, "resolvable", [])`
  — preserves the documented duck-typing contract for a shim carrying only the four original
  attributes.
- `test_no_invention_structural.py`'s structural guarantee is EXTENDED (4 new forbidden
  substrings — `fill_identity`, `apply_resolution`, `confirm_resolution`, `resolve_identity`)
  covering the resolution surface, never relaxed — the original 4 substrings are unchanged. A
  new test pins `RESOLUTION_SOURCES` as a closed set and that an unrecognized source rejects.
- 8 new tests in `test_extraction_resolvable.py`, one per `<behavior>` bullet.

**Task 3 — extraction.md amendment, SKILL.md, release.**
- Both no-invention passages amended with the same recorded-edit discipline D-53-05 used: the
  sentence *"Never fill a gap to make a row satisfy the identity rule"* and passage 2's
  "never invented" clause survive VERBATIM. The "rejected with a stated reason is the correct
  outcome" clause in each is rewritten — rejection is now the last resort after a
  resolve-and-propose attempt — with a dated `D-59-08, operator, 2026-08-28` note stating what
  the clause used to say and why it changed. No pinning test existed for the retired wording
  (confirmed by the same grep RESEARCH.md ran).
- `SKILL.md:198-215` extended to document the new `resolvable` preview group alongside the
  rejected rows, dropped keys and ambiguity block, keeping the "presented once, never one
  interruption per row" discipline.
- `plugin.json` `0.23.0` → `0.24.0`; CHANGELOG entry names D-59-08, the gate inventory, the
  new surface, and states plainly the no-invention rule was not relaxed, plus what this
  release does NOT convert (GATE-02..06, pointed at 59-06).

## Deviations from Plan

None — plan executed exactly as written. One implementation detail not spelled out by the
plan (the tie-break rule for selecting which identity group's `missing` fields to report when
two groups tie on missing-count) was decided during Task 2 to match the plan's own worked
example (a firstname+lastname-only contact row reporting "missing company") — recorded above
under Decisions, not a deviation from any stated behavior.

## Known Stubs

None. 59-06 is explicitly out of scope for this plan (named in the gate inventory and the
CHANGELOG as unconverted, not silently dropped).

## Threat Flags

None beyond what the plan's own `<threat_model>` already named (T-59-20 through T-59-25, all
mitigated as designed — see the plan file for the register).

## Self-Check: PASSED

- `.planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md` — FOUND
- `operator-claude-plugin/tests/test_extraction_resolvable.py` — FOUND
- Commit `b27859e` (gate inventory) — FOUND in `git log --oneline`
- Commit `c1ba32a` (extraction.py/preview.py conversion) — FOUND in `git log --oneline`
- Commit `af9f569` (extraction.md/SKILL.md/release) — FOUND in `git log --oneline`
- `operator-claude-plugin/tests -q`: 1669 passed, 5 skipped
- Root suite `-q`: 3276 passed, 154 skipped (was 3267/154 before this plan)
- `test_no_invention_structural.py -x`: 7 passed
