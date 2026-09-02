---
phase: 24-non-tabular-input-adapters
plan: 03
subsystem: infra
tags: [claude-plugin, extraction, skill-prompt, provenance, web-fetch, screenshot]

requires:
  - phase: 24-01
    provides: extraction.py validator (canonical_props(), identity_groups(), has_identity(), load_artifact(), validate(), ExtractionResult, write_dispatch_csv()), the scratch directory
  - phase: 24-02
    provides: dedupe()/overlap-collapse and ambiguity aggregation added to validate() (concurrent sibling plan; landed mid-execution)
provides:
  - "operator-claude-plugin/skills/contact-upload/extraction.md — the bundled, Level-3 extraction
    contract: handoff protocol (write artifact to scratch, run extraction.py, read its JSON), the
    no-invention rule stated once for all four adapters, the artifact schema with two validated
    fenced examples, the canonical 7-prop vocabulary, and the prose/foreign-JSON/URL/screenshot
    adapters with their named empty/unreadable/fetch-failed/nothing-usable outcomes"
  - "operator-claude-plugin/tests/test_extraction_contract.py — the D-13 drift pin: parses both
    fenced example artifacts out of extraction.md and runs them through the real extraction.validate(),
    so the documented schema and the validator's accepted schema cannot silently diverge"
  - "SKILL.md's input-resolution step branches to extraction.md for non-tabular input, and a new
    cleanup step deletes the scratch artifact once a batch ends (D-05)"
  - "README's operator-facing section on the four non-tabular inputs; CHANGELOG's Phase 24 entry"
affects: [25, 26]

tech-stack:
  added: []
  patterns:
    - "extraction.md is instructions FOR Claude, not documentation ABOUT the plugin — imperative
      voice throughout, loaded only when input is not already tabular (Level-3 bundled resource)"
    - "fenced JSON examples in a markdown file are executable documentation: a test parses them
      out with a regex and runs them through the real validator, so a prompt file and a Python
      module stay pinned to one schema without a shared source file"
    - "the no-invention rule is stated once, before any adapter, because it governs all four —
      not repeated per adapter"

key-files:
  created:
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/tests/test_extraction_contract.py
  modified:
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md

key-decisions:
  - "The screenshot adapter's example artifact deliberately carries an EMPTY artifact-level
    ambiguities list — the documented behavior is that Claude reports each image faithfully
    without pre-deciding whether two records are the same person, and the validator's dedupe
    pass (24-02) is what raises the job-title-conflict ambiguity itself. This is the concrete
    illustration of 'merging is the validator's job, not yours to improvise.'"
  - "`url_not_allowed` wording deliberately does not distinguish robots.txt from an admin
    domain block, because the tool's error code genuinely cannot tell them apart — claiming
    either specifically would be inventing a detail the tool never gave (per 24-RESEARCH.md
    question 3)."
  - "Concurrent sibling plans (24-02's dedupe, 26-01's per-record reporting) were both editing
    SKILL.md in the same working tree at the same time. Rather than clobber either side, hunks
    were isolated per-author using `git commit --only -- <pathspec>` (and, once, a hand-built
    blob staged via `git hash-object`/`git update-index --cacheinfo` to recover an entangled
    hunk) so each plan's commit carries exactly its own lines."

requirements-completed: [INGEST-01, INGEST-03, INGEST-05, INGEST-06, INGEST-07]

coverage:
  - id: D1
    description: "Pasted freeform text and a foreign-shaped JSON blob each have a named adapter in extraction.md with a stated provenance locator and named empty/unreadable outcomes"
    requirement: "INGEST-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py#test_first_fenced_example_artifact_is_accepted_by_the_real_validator_with_no_rejects"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py#test_first_fenced_example_carries_the_documented_ambiguity"
        status: pass
    human_judgment: false
  - id: D2
    description: "Foreign-JSON keys with no canonical target are carried onto the row as-is so the validator's existing strip-and-report path surfaces them to the operator — one mechanism, not a second reporting channel (D-12)"
    requirement: "INGEST-03"
    verification:
      - kind: manual_procedural
        ref: "extraction.md 'Adapter: foreign-shaped JSON (INGEST-03)' section, read for wording"
        status: pass
    human_judgment: false
  - id: D3
    description: "A public URL is fetched with the native web_fetch tool only (no HTTP client, no user-agent, no viewport, no authenticated session), and a fetch-failed outcome is worded separately from a fetched-but-nothing-usable outcome"
    requirement: "INGEST-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py#test_extraction_md_states_the_fetch_failed_and_nothing_usable_outcomes_separately"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every adapter has a named empty outcome and a named unreadable/unsupported outcome; no silent zero-row path exists anywhere in extraction.md"
    requirement: "INGEST-06"
    verification:
      - kind: manual_procedural
        ref: "extraction.md — 'Named empty outcome' / 'Named unreadable outcome' call-outs per adapter, plus the closing 'Input this file cannot handle at all' section"
        status: pass
    human_judgment: false
  - id: D5
    description: "Operator-supplied screenshots yield rows whose provenance names the image and region; the plugin never captures a screenshot itself; a scrolled sequence's overlap collapses on the identity rule with the collapse and the resulting ambiguity verified against the real validator (including 24-02's dedupe pass)"
    requirement: "INGEST-07"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py#test_screenshot_example_artifact_collapses_to_one_row_with_one_carried_ambiguity"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py#test_extraction_md_states_the_no_automated_screenshot_capture_fence"
        status: pass
    human_judgment: false
  - id: D6
    description: "extraction.md's documented artifact schema is pinned to extraction.py's real validator via a contract test that parses both fenced examples and runs them through validate() — the drift pin (D-13)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py (9 tests, all passing)"
        status: pass
    human_judgment: false
  - id: D7
    description: "SKILL.md wires the non-tabular branch into the existing preview/approve/arm/dispatch path with no second preview and no second dispatch; a cleanup step deletes the scratch artifact per D-05; README and CHANGELOG document the four adapters for the operator"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py (5 tests, all passing — including the script-path existence check)"
        status: pass
      - kind: manual_procedural
        ref: "SKILL.md steps 2/3/7 (this plan's hunks), README 'Beyond spreadsheets' section, CHANGELOG Unreleased Phase 24 entry"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-31
status: complete
---

# Phase 24 Plan 03: Extraction Skill Body, URL Adapter, Error Taxonomy, Docs Summary

**`extraction.md` is the prompt half of the extraction contract 24-01 built the validation half
of: instructions addressed to Claude (never to a human reader) covering the no-invention rule,
the write-a-file-then-validate handoff, and all four non-tabular adapters — pinned to
`extraction.py`'s real validator by a contract test that runs the file's own fenced JSON
examples through it.**

## Performance

- **Duration:** ~20 min (includes waiting on sibling plan 24-02's dedupe landing in `extraction.py`)
- **Started:** 2026-07-30T21:14:00Z (approx, plan handoff)
- **Completed:** 2026-07-30T21:45:00Z
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `extraction.md` is written as instructions *to* Claude, in the imperative — "you read the
  source and write the rows down," never "the plugin extracts." It states up front that there is
  no Anthropic API call, no API key anywhere in the plugin, and no extraction library (D-01/D-02),
  and that `extraction.py` only validates what Claude already wrote.
- The no-invention rule is stated once, before any adapter, as three concrete instructions (leave
  absent fields out, put unclear values in the ambiguity list, never complete a row just to pass
  the identity check) — governing all four adapters rather than being repeated per adapter, per
  D-03's framing that this is a prompt-and-validation contract, not a code guarantee alone.
- The handoff protocol names the scratch directory (`operator-claude-plugin/scratch/`), the exact
  CLI invocation (`python3 scripts/extraction.py <path>`), and explains *why* a file boundary
  rather than chat-parsed JSON is the only version of the handoff that fails loudly (24-RESEARCH.md
  Pitfall 1).
- Two complete, valid fenced JSON example artifacts are executable documentation, not decoration:
  one for the prose/foreign-JSON case (two records, one ambiguity), one for the screenshot
  overlap case (two records from two images naming the same person via email, disagreeing on a
  truncated `jobtitle`). `test_extraction_contract.py` parses both out of the markdown and runs
  them through the real `extraction.validate()` — the D-13 drift pin. The screenshot example
  specifically demonstrates that Claude does not pre-decide the merge or the conflict: the
  artifact's own `ambiguities` list is empty, and the validator's dedupe pass (24-02, which
  landed in `extraction.py` partway through this plan's execution) is what collapses the two
  records to one accepted row and raises the job-title disagreement itself.
- The URL adapter (INGEST-05) states the `web_fetch` fences as facts the tool structurally
  enforces (no user-agent, no viewport, no authenticated fetch, no anti-bot technique) rather
  than as policy requiring judgement, and gives two separately-worded outcomes: a tool-level
  `url_not_allowed`/etc. failure (translated to plain language, explicitly NOT claiming to
  distinguish a robots.txt block from an admin domain block, since the error code cannot) versus
  a successful-fetch-but-nothing-usable result (most often a client-rendered page the tool
  cannot execute).
- The screenshot adapter (INGEST-07) opens with the boundary most likely to be misread as a
  workaround — the plugin never drives a browser or captures a page itself, and a screenshot is
  not a route past the licensed provider waterfall for LinkedIn-covered fields — before covering
  provenance locators, the ~20-image practical ceiling, and batch-and-merge via the identity rule.
- Ambiguity handling and the closing "input this file cannot handle at all" section are stated
  once, covering all four adapters, per D-06 (one interruption per batch) and INGEST-06 (no
  silent zero-row outcome).
- `SKILL.md`'s input-resolution step (step 2) branches to `extraction.md` for non-tabular input
  and continues at the existing preview step (step 3) with the validator's accepted rows; the
  preview step notes what an extracted batch's preview shows that a spreadsheet's never needs
  (provenance, rejects, dropped keys, one ambiguity block); a new cleanup step deletes the
  scratch artifact once a batch ends, dispatched or declined, per D-05.
- README gains a "Beyond spreadsheets" section for the operator: what the four inputs accept, that
  a row is never completed by guessing, that ambiguities return as one list, and that the plugin
  neither captures screenshots nor logs into sites — LinkedIn-covered fields still come from the
  licensed provider waterfall on the backend. CHANGELOG's Unreleased section gains the Phase 24
  entry; the corresponding Planned-list line is removed so the two sections do not both claim it.
- `REQUIREMENTS.md` marks INGEST-05 and INGEST-07 complete (INGEST-01/03/06 were already marked by
  24-01) and updates their traceability rows to Complete.

## Task Commits

Each task was committed atomically:

1. **Task 1: The extraction contract — handoff, no-invention rule, prose + foreign-JSON adapters** - `3ea9b65` (feat)
2. **Task 2: URL and screenshot adapters, error taxonomy, scope fences** - `174eb78` (feat)
3. **Task 3: Wire adapters into the skill, document for the operator** - `2013d52` (feat)

_Note: Task 3's SKILL.md hunks (the step 2 branch, step 3 preview note, and step 7 cleanup line)
ended up committed under `d8bc409` — a commit authored by the concurrent sibling plan 26-01,
which detected the shared-file collision (both plans were editing `SKILL.md` uncommitted, in the
same working tree, at the same time) and isolated exactly this plan's non-overlapping hunks via
`git add -p` before committing its own step 6/7 report-outcome content separately. This plan's
Task 3 commit (`2013d52`) therefore carries only `README.md` and `CHANGELOG.md` — `SKILL.md`'s
content was already correct and already in history by the time this plan reached that commit.
Verified via `git show HEAD:.../SKILL.md` matching this plan's intended content exactly before
proceeding, and via `git show --stat` on both commits to confirm no cross-contamination in either
direction._

**Plan metadata:** (this commit, alongside SUMMARY.md)

## Files Created/Modified

- `operator-claude-plugin/skills/contact-upload/extraction.md` - the extraction contract: handoff,
  no-invention rule, artifact schema with two validated examples, canonical vocabulary, and the
  prose/foreign-JSON/URL/screenshot adapters with their error taxonomy
- `operator-claude-plugin/tests/test_extraction_contract.py` - 9 tests pinning the documented
  schema to the real validator (D-13)
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - non-tabular branch (step 2), extracted-
  batch preview note (step 3), scratch cleanup (step 7) — landed via sibling commit `d8bc409`, see
  note above
- `operator-claude-plugin/README.md` - "Beyond spreadsheets" operator-facing section
- `operator-claude-plugin/CHANGELOG.md` - Phase 24 Unreleased entry; removed from Planned
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` - INGEST-05/INGEST-07 marked complete

## Decisions Made

- **The screenshot example artifact's `ambiguities` list is empty by design.** The documented
  behavior is that Claude reports each image faithfully and the validator's dedupe pass decides
  whether two records collapse and whether they conflict — the example proves this by showing
  zero artifact-level ambiguities producing one collapse-generated ambiguity after `validate()`.
- **`url_not_allowed` wording states the tool's real limitation rather than inventing a
  distinction.** Both a robots.txt block and an administrator's domain-filter block collapse into
  the same error code; the file says "the site or an administrator declined the fetch" and
  explicitly avoids naming either mechanism specifically.
- **Cross-plan SKILL.md collision resolved via `git commit --only -- <pathspec>` and, once, a
  hand-built git blob** (`git hash-object -w` + `git update-index --cacheinfo`) to recover this
  plan's intended content when a concurrent sibling's in-progress edit had merged into the same
  working-tree file. This kept each plan's commit scoped to its own hunks without discarding
  either side's work.

## Deviations from Plan

None in content — every task's `<action>` was followed as written. One coordination deviation
worth recording: Task 2's screenshot contract-test assertion (exact-one-accepted-row-after-dedupe)
depends on sibling plan 24-02's `dedupe()` landing in `extraction.py`, which the plan's own
execution context flagged as running concurrently. That dependency resolved mid-execution — this
plan waited (via a bounded background poll, not a blocking sleep) rather than weakening the
assertion, since the plan's acceptance criteria explicitly specify the post-dedupe behavior.

## Issues Encountered

`SKILL.md` was being edited uncommitted, in the same working tree, by both this plan and the
concurrent sibling plan 26-01 (per-record outcome reporting) at the same time — a real file-level
collision, not a hypothetical one. Resolved without data loss: this plan's hunks and 26-01's hunk
were isolated and committed separately (see Task Commits note above). No content from either plan
was lost or double-applied; confirmed via `git show --stat` on every commit touching the file and
a final full-file diff comparing HEAD against this plan's intended reconstructed content.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 125 passed, no regressions.
- `.venv/bin/python -m pytest -q` (full repo suite) — 869 passed, 1 skipped.
- `git diff --name-only 22c3058..2013d52 -- . ':!operator-claude-plugin'` confirms nothing outside
  `operator-claude-plugin/` was touched by this plan's three commits.
- Phase 24 is now feature-complete: INGEST-01/03/05/06/07 and STRUCT-01/02/03/04 are all marked
  complete in `REQUIREMENTS.md`. Remaining Phase 24 ROADMAP criteria (if any) should be checked
  against the full three-plan set (24-01, 24-02, 24-03) at phase-close, not per-plan.
- Phase 25/26 (already in flight concurrently per this execution's own observations) can treat
  the non-tabular adapters as a stable input source feeding the same preview/approve/arm/dispatch
  path they already build on.

---
*Phase: 24-non-tabular-input-adapters*
*Completed: 2026-07-31*
