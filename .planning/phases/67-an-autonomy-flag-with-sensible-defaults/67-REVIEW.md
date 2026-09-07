---
phase: 67-an-autonomy-flag-with-sensible-defaults
reviewed: 2026-09-07T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/config/operator.local.example.json
  - operator-claude-plugin/scripts/config_gate.py
  - operator-claude-plugin/skills/backend-control/SKILL.md
  - operator-claude-plugin/skills/contact-upload/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/tests/test_autonomy_levels.py
  - operator-claude-plugin/tests/test_autonomy_switch_prose.py
  - operator-claude-plugin/tests/test_disclosure_audit.py
  - operator-claude-plugin/tests/test_headless_grant_boundary.py
  - operator-claude-plugin/tests/test_mandatory_report_call_sites.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 67: Code Review Report

**Reviewed:** 2026-09-07
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 67 adds a three-level `autonomy` settings object (`read_only` / `spend_no_write` /
`write`) as a pure default-setter layered on top of the pre-existing `allow_write_grants`
and `ALLOW_N8N_ARM` authority gates, and makes the end-of-run report mandatory at all four
batch skills. The diff is almost entirely additive (`config_gate.py`: +51/-0; the four
SKILL.md files carry the same switch-site pattern verbatim; `write_grant.py`,
`n8n_arming.py`, `scheduled_arm.py`, `suggest_contacts.py` are byte-identical to the base
commit, confirmed by empty diffs). All 138 tests in the six required test files pass, and
they exercise real behavior rather than mocks: `test_mandatory_report_call_sites.py`'s two
behavioural tests drive `run_report.build_run_report` directly against a real (tmp-path)
durable-store layout; `test_headless_grant_boundary.py` scans the actual source of
`scheduled_arm.py` and `n8n_arming.py` by AST/substring for every one of the four autonomy
symbol names, not just a happy-path assertion. Every scripts-module symbol referenced from
the SKILL.md code fences (`dispatch.dispatch(..., run_id=)`, `run_state.new_run_id`,
`run_report.record_audit`, `run_report.build_run_report`, `run_report.RunReportError`,
`write_grant.CLOSED_UNHANDLED_ERROR`) exists with the signature the prose claims. Prose is
consistent across the four converted skills — no drift found between the near-identical
switch-site paragraphs. `D-10b`'s "no icp/tier substring" rule holds across all five
touched skills, `MAX_GRANDFATHERED = 0` still holds, and the version bump
(`0.40.0` → `0.41.0`) is present in the same phase alongside the CHANGELOG entry, matching
every claim it makes against the actual diff.

One real defect was found in the core gate function itself (`config_gate.autonomy_enabled`):
an explicit JSON `null` for the whole `autonomy` object is treated identically to the key
being *absent* (reads ON for every level), rather than being caught by the "malformed
parent degrades to OFF" branch that a bare boolean (`{"autonomy": true}`) already is. This
directly contradicts the function's own documented near-miss philosophy ("fail toward
asking, never toward silent proceed") and is not covered by `test_autonomy_levels.py`.

## Critical Issues

### CR-01: `autonomy_enabled` reads an explicit `"autonomy": null` as ON for every level, contradicting its own near-miss-fails-OFF design

**File:** `operator-claude-plugin/scripts/config_gate.py:166-171`

**Issue:** The function's own extensive comments (lines 139-144) state the near-miss rule
in absolute terms: "only the JSON boolean `true`, or the level being absent from a present
`autonomy` object, reads as ON. Every other value... including an explicit `null`... reads
OFF." That rule is enforced correctly for a `null` *level value inside* the object
(`{"autonomy": {"write": null}}` → `False`, pinned by
`test_every_near_miss_level_value_reads_off_not_on`), and for a malformed *non-dict* parent
such as a bare `true` (`{"autonomy": true}` → `False` for every level, pinned by
`test_bare_boolean_parent_reads_every_level_off_and_raises_nothing`).

But an explicit JSON `null` for the **parent itself** — `{"autonomy": null}` — is not caught
by the `isinstance(parent, dict)` malformed-shape check, because the earlier
`if parent is None: return True` branch intercepts it first (Python's `dict.get` returns
`None` for both "key absent" and "key present with value `null`", and the code cannot tell
the two apart once it has called `.get()`). Verified live:

```python
>>> config_gate.autonomy_enabled({'autonomy': None}, 'write')
True    # same as a missing key entirely
>>> config_gate.autonomy_enabled({'autonomy': True}, 'write')
False   # a different malformed shape, correctly caught
```

An admin who hand-edits `operator.local.json` and sets `"autonomy": null` — a plausible way
to try to "unset"/disable the whole feature, and the same shape JSON commonly uses to mean
"turn this off" — gets the *opposite* of that intent: every level silently reads ON, and an
already-authorised round (one where `allow_write_grants` is `true`) proceeds to spend/write
without asking, exactly the behavior the b-malformed-off design was written to prevent for
every other wrong-shape input. This is not a new authority (the function still cannot arm
anything by itself), but it is a documented safety invariant of a phase whose entire purpose
is making autonomous behavior deliberate and reversible, broken for one specific,
foreseeable operator action, with zero test coverage.

**Fix:** Distinguish "key absent" from "key present with value `null`" before deciding, and
route the explicit-`null` case through the same malformed-parent branch a bare boolean
already takes:

```python
def autonomy_enabled(config: dict, level: str) -> bool:
    if level not in AUTONOMY_LEVELS:
        raise ValueError(f"unknown autonomy level: {level!r}. Valid levels: {AUTONOMY_LEVELS}")
    cfg = config or {}
    if AUTONOMY_SETTINGS_KEY not in cfg:
        return True
    parent = cfg[AUTONOMY_SETTINGS_KEY]
    if not isinstance(parent, dict):
        return False  # covers both `{"autonomy": true}` and `{"autonomy": null}`
    return parent.get(level, True) is True
```

Add a test pinning `config_gate.autonomy_enabled({"autonomy": None}, "write") is False`
alongside the existing bare-boolean-parent test.

## Warnings

### WR-01: `read_only` autonomy level is documented as live but has zero call sites

**File:** `operator-claude-plugin/config/operator.local.example.json:25`

**Issue:** The shipped example config's `_autonomy_note` states the three levels govern:
"read_only (backend-status, review-queue reads, loss-reason-report), spend_no_write (the
match and propose lanes...), write (ingest, enrich-and-write, review-decision apply...)."
Grepping every `skills/*/SKILL.md` in the repo for `autonomy_enabled` finds it called only
in `contact-upload`, `enrich-before-ingest`, `enrich-records` (all `"write"`) and
`suggest-contacts` (`"spend_no_write"`). No skill anywhere — including `backend-status`,
`review-triage`, or `loss-reason-report` — ever calls
`config_gate.autonomy_enabled(config, "read_only")`. `test_review_triage_and_backend_control_read_no_autonomy_level`
confirms `review-triage`/`backend-control` call no autonomy level at all (by design,
D-67-12), but nothing in the test suite checks whether `read_only` is wired into the three
skills the example config's own comment names as its governing surface — because it is not
wired into any of them.

Today this is inert rather than actively wrong (an unused level defaults to the same "ON"
answer a caller would get if it weren't consulted at all, since those read-only skills
never pause to ask in the first place), but the shipped comment overclaims present behavior:
an admin who sets `autonomy.read_only: false` expecting `backend-status` or
`loss-reason-report` to start asking first will observe no change, because nothing reads
that key yet.

**Fix:** Either scope the `_autonomy_note`'s `read_only` sentence to say it is reserved for
a later phase (matching how the rest of this file marks not-yet-live behavior elsewhere), or
file the wiring work explicitly rather than leaving the comment as the only record that it's
outstanding.

### WR-02: `suggest-contacts/SKILL.md` reuses the identifier `outcome` for two unrelated values across the same walkthrough

**File:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md:544, 677-688`

**Issue:** Inside the per-company loop, `outcome = suggest_contacts.round_outcome(walk)`
(line 544) binds a per-company routing classification. The new mandatory-report fence added
by this phase (lines 677-688) later reads a bare `outcome` and passes it as
`outcomes=[outcome]` to `run_report.build_run_report` — but by that point `outcome` is
supposed to mean the batch-level *dispatch* outcome (the `outcome = chunking.dispatch_plan(...)`
assignment inside `enrich-before-ingest/SKILL.md`'s step-5 block, which this file's own
comment says is "REUSED... verbatim" for its own step 8). The two meanings are only kept
apart by relying on the per-company loop finishing, and Stage 2's reused dispatch block
running strictly after it and reassigning the same name — nothing in the prose calls out
that the name is being deliberately reused for two different types across scope, and an
executor (human or LLM) skimming step 9 in isolation could easily reach for the per-company
`outcome` instead of the dispatch one, especially since `entry["outcome"]` (a third, related
but distinct value) is also in play a few lines earlier in the same step.

**Fix:** Rename one of the two — e.g. the per-company routing value to
`company_outcome` — so the report step's `outcomes=[outcome]` is unambiguously the dispatch
outcome by construction, not by execution order.

---

_Reviewed: 2026-09-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
