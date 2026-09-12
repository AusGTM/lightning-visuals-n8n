---
phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply
fixed_at: 2026-09-12T00:00:00Z
review_path: .planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 71: Code Review Fix Report

**Fixed at:** 2026-09-12
**Source review:** .planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02 — `critical_and_warning` scope; IN-01 excluded, Info-level)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-02: `held_queue.identity_keys()` hardcodes the identity groups instead of reading `config/column_mapping.yaml`, with no parity test

**Files modified:** `operator-claude-plugin/scripts/held_queue.py`, `operator-claude-plugin/tests/test_held_queue_identity_parity.py` (new)
**Commit:** `63ad6e6a`
**Applied fix:** `identity_keys()` now derives the identity-group order from
`extraction.identity_groups()` — the same `config/column_mapping.yaml` loader
`extraction.py` itself uses — via a function-scoped import (the same import-cycle
constraint that already applied to the existing `suggest_contacts` import: `extraction`
imports `preview` at its own module level before `identity_groups` is defined, so a
module-level import here would break `import extraction`). Each YAML group is matched
against a closed set of known shapes (email / name+company / linkedin); an unrecognized
group now raises `ValueError` loudly instead of being silently skipped, satisfying the
review's "future YAML change fails loudly here instead of silently" requirement. Added
`test_held_queue_identity_parity.py`, a YAML-driven parity test mirroring
`tests/n8n/columnMapIdentityParity.test.mjs`'s intent: it builds a row per YAML group,
asserts each produces a key, asserts a row satisfying no group produces no keys, and
asserts key order/prefixes track the YAML's own group order — so a group added later
(the same kind of change Phase 61-03 made once) is covered automatically.

### WR-01: `company_spec` is claimed resumable across a fresh process but has no persistence path

**Files modified:** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`, `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py`
**Commit:** `b7d738b6`
**Applied fix:** Chose the review's second offered remedy (rewrite the guidance to
state the degradation) over persisting `company_spec` through `match_state` — persisting
it would have required widening `match_state.py`'s carefully closed, validated document
schema (`CLASSIFICATION_FIELD`'s exact-five-key check) for a value only ever consumed
within the same conversation turn it is minted in, a larger and riskier surface than the
actual defect warranted. Rewrote every `company_spec` use site (steps 2, 3, and 5) to
state plainly that `company_spec` is an in-conversation Python variable only, never
persisted to `match_state` or anywhere else durable, and that a fresh process must pass
`company_spec=None` to `preingest.confirmed_company_domains` — naming the accepted,
bounded degradation: a held row whose only confirming signal was the company-row
confirm-table answer reads `needs_company` instead of `new_person` until that table is
answered again in the current process, while a row confirmed via a matched contact's own
email domain (persisted through `classified`) is unaffected. Added three pins to
`test_enrich_before_ingest_skill_contract.py`, mirroring
`test_step_2_binds_and_prints_match_run_id_then_saves`'s shape, asserting the
non-persistence statement, the `company_spec=None` fallback, and the named degradation
are present at steps 2, 3, and 5, and that the old misleading sentence WR-01 quoted
verbatim is gone.

## Verification

Ran `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/`
after each fix (main checkout — `workflow.use_worktrees` is `false` in
`.planning/config.json`, so no isolated worktree was created; edits and commits landed
directly on `master`, reproducible from this tree as-is):

- Baseline: 3032 passed, 5 skipped
- After WR-02: 3035 passed, 5 skipped (+3 new)
- After WR-01: 3038 passed, 5 skipped (+3 new)

`test_skill_sequence_coverage.py` passed unmodified throughout (SKILL.md edits only
added comment lines inside existing code fences — no call sequence changed).

## Skipped Issues

None — both in-scope findings were fixed.

---

_Fixed: 2026-09-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
