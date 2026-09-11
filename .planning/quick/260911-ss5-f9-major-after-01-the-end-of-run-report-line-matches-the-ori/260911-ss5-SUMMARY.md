---
phase: quick-260911-ss5
plan: 01
subsystem: operator-claude-plugin
tags: [enrichment, hubspot, n8n, end-of-run-report, match-handoff, skill-md]

requires: []
provides:
  - "scripts/match_handoff.py — the plugin's ninth persisted artifact family: the
    matched-id handoff (row_id -> hs_object_id -> confirmed), one durable file per run"
  - "run_report.py: build_run_report's original_row_count keyword renamed to
    enrichment_scope_row_count (hard rename); a new Matched-id handoff section reads
    match_handoff.py; an absent handoff is a named gap only when a scope count was
    supplied"
  - "enrich-before-ingest/SKILL.md: step 7 records the handoff in its own fence; step
    9 passes the renamed keyword"
affects: [enrich-before-ingest, contact-upload, suggest-contacts, enrich-records]

actuals:
  tokens: 12435
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "match_handoff.py mirrors written_records.py's four-state classify_read
      (absent/parseable/anomalous/another_run) rather than match_state.py's
      raise-on-anything-but-parseable contract — this store's only consumer is a
      report, which must degrade to a named gap, never halt"
    - "record_handoff PROJECTS the raw auto_matched entry down to row_id/
      hs_object_id/confirmed before writing — the operator's spreadsheet row never
      reaches disk, but the forbidden-name scan still runs over the RAW payload
      (entry keys, row dict keys, row_id/hs_object_id values) so a caller-supplied
      grant-shaped field is refused even though projection would have dropped it"
    - "a store departs from the sibling ABSENT-is-never-a-gap convention on purpose:
      match_handoff's absence is a named gap ONLY when enrichment_scope_row_count is
      not None, gating the gap to the one lane (enrich-before-ingest) whose step 7
      was supposed to write the file"

key-files:
  created:
    - operator-claude-plugin/scripts/match_handoff.py
    - operator-claude-plugin/tests/test_match_handoff.py
  modified:
    - operator-claude-plugin/scripts/run_report.py
    - operator-claude-plugin/tests/test_run_report.py
    - operator-claude-plugin/tests/test_forbidden_marker_parity.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md

key-decisions:
  - "match_handoff's forbidden-name scan runs over the RAW entries passed to
    record_handoff, not the post-projection three-key shape — a caller passing a
    full auto_matched entry with an extraneous forbidden-shaped field (or a
    forbidden-shaped row_id/hs_object_id) is refused before projection could
    silently drop the evidence of what was asked for."
  - "The row-accounting keyword rename (original_row_count -> 
    enrichment_scope_row_count) is a hard rename with no alias — an alias would be
    exactly the dead flexibility that let the misleading name survive the 2026-09-09
    same-day scope correction in the first place."
  - "Step 7 records the handoff in its OWN new one-call fence, not appended to the
    existing confirmed_ids fence — 260911-ss4 (landed first on this checkout) also
    touches that fence to load persisted state; two one-call fences leave both items
    at zero new documented sequences for test_skill_sequence_coverage.py, rather
    than one two-call fence that only whichever item merges second could claim."

patterns-established:
  - "A ninth durable-store family joins the plugin's forbidden-name-matcher parity
    suite (test_forbidden_marker_parity.py), keeping all nine reimplementations of
    the whole-token guard behaviourally identical against one shared corpus."

requirements-completed: []

coverage:
  - id: D1
    description: "match_handoff.py: record_handoff/load/classify_read round-trips a
      full auto_matched entry to exactly row_id/hs_object_id/confirmed with no
      spreadsheet value on disk; all four classify_read states; a grant-shaped key,
      row_id, hs_object_id, or run_id raises and writes nothing; a Grant-named row
      persists; an empty-list handoff still writes and classifies parseable; the
      pytest-safety guard refuses an unpatched real-directory write; registered as
      the ninth forbidden-name matcher."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_match_handoff.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_forbidden_marker_parity.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_report.py: build_run_report's keyword renamed to
      enrichment_scope_row_count (hard rename, signature probe confirms no
      leftover original_ parameter); every row-accounting line reworded to name
      this run's enrichment scope, never the original batch; a Matched-id handoff
      section renders recorded/empty/absent/unreadable/foreign-run states; an
      absent handoff is a gap only when a scope count was supplied; match_handoff-
      *.json joins the long-TTL prune family."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_report.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "enrich-before-ingest/SKILL.md: step 7 records the handoff in its
      own new one-call fence right after confirmed_ids is computed; step 9 passes
      the renamed keyword with the value unchanged; the F4 comment block is
      corrected and shortened; no new documented call sequence registered."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_mandatory_report_call_sites.py"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-09-11
status: complete
---

# Quick Task 260911-ss5: F9 — the end-of-run report names its scope, and the matched-id handoff survives the process Summary

**`match_handoff.py` persists the matched ids `enrich-before-ingest` hands to `enrich-records`, and `run_report.py`'s row-accounting section now names "this run's enrichment scope" instead of falsely claiming to match "the original batch."**

## Performance

- **Duration:** ~40 min
- **Tasks:** 3 completed
- **Files modified/created:** 6 (2 created, 4 modified)

## Accomplishments

- Built `scripts/match_handoff.py`, the plugin's ninth persisted artifact family:
  `record_handoff`/`load`/`classify_read`/`handoff_path`, one file per run
  (`match_handoff-<run_id>.json`), projecting every entry down to exactly `row_id`,
  `hs_object_id`, and `confirmed` — the operator's spreadsheet row (names, emails,
  phone numbers) never reaches disk. The forbidden-name scan runs over the RAW
  entries before projection, so a caller-supplied grant-shaped field is refused
  even though projection would have quietly dropped it.
- `classify_read` distinguishes all four states (`absent`/`parseable`/`anomalous`/
  `another_run`), mirroring `written_records.classify_read` — this store's only
  consumer is a report, which degrades to a named gap rather than raising, unlike
  `match_state.py`'s raise-on-anything-but-parseable contract.
- Registered `match_handoff` as the ninth module in
  `test_forbidden_marker_parity._KEY_MATCHER_MODULES` and corrected the file's
  docstring/comments to name nine stores.
- Renamed `run_report.build_run_report`'s `original_row_count` keyword to
  `enrichment_scope_row_count` (hard rename, no alias — an alias would have been
  the same dead flexibility that let the misleading name survive the 2026-09-09
  same-day scope correction). Reworded all three row-accounting lines (both
  outcome branches and the `None` branch) to name this run's enrichment scope,
  keeping the "not provided by the caller" substring the existing test pinned.
- Added a `### Matched-id handoff` section (after `### Per-record outcomes`)
  rendering recorded entries as `row_id -> hs_object_id`, an empty-but-present
  handoff as "nothing was handed onward", an absent one as "no matched-id handoff
  was recorded", and an unreadable/foreign-run one pointing at Known gaps. Added a
  scope-note line in the row-accounting section stating how many ids were handed
  onward, so the two numbers add back to the whole batch (F9's own 4-row shape:
  2/2 enrichment scope + 2 handed onward = 4).
- An absent handoff is a named gap ONLY when `enrichment_scope_row_count is not
  None` — gated on the one argument `enrich-before-ingest` alone passes, so
  `contact-upload`/`suggest-contacts`/`enrich-records` never gain a spurious
  `REPORT INCOMPLETE` banner for a file they were never meant to write.
  ANOMALOUS/ANOTHER_RUN still go through the unmodified `_add_gap` sibling
  contract.
- Registered `match_handoff-*.json` in `run_report._PRUNE_LONG_TTL_GLOBS` and both
  parametrized prune-family tests in `test_run_report.py`.
- Rewired `skills/enrich-before-ingest/SKILL.md`: step 7 records the handoff in
  its own new one-call fence (`import match_handoff` /
  `match_handoff.record_handoff(run_id, classified["auto_matched"])`) immediately
  after `confirmed_ids` is computed — deliberately its OWN fence, not appended to
  the neighbouring `confirmed_ids` fence, so this item and the concurrently-landed
  `260911-ss4` (which also edits that fence to load persisted match state) never
  collide on a single fence's `test_skill_sequence_coverage.py` sequence identity.
  Step 9 passes `enrichment_scope_row_count=len(unmatched_rows)` (value unchanged),
  with the F4 comment block corrected and shortened, and one sentence added naming
  the matched-id handoff section as part of what the operator reads.

## Task Commits

Each task was committed atomically:

1. **Task 1: `match_handoff.py` — the matched-id handoff, one durable file per run** - `7b5f2fc9` (feat)
2. **Task 2: The report names the scope it counted, and names the handoff** - `06993b19` (feat)
3. **Task 3: The skill records the handoff and passes the renamed keyword** - `af7b8d59` (feat)

## TDD Evidence

Task 1's RED, observed before `match_handoff.py` existed:

```
ModuleNotFoundError: No module named 'match_handoff'
```

A follow-up RED within Task 1, before the forbidden-name scan was widened to cover
the raw (pre-projection) payload:

```
FAILED test_match_handoff.py::test_a_grant_shaped_key_raises_and_writes_nothing
Failed: DID NOT RAISE MatchHandoffError
```

(a `webhook_secret` key on the raw entry was silently dropped by projection before
the scan ever saw it — fixed by scanning raw entries' own keys, `row_id`/
`hs_object_id` values, and `row` dict keys, before projection runs.)

Task 2's RED, observed against the unedited `run_report.py` (10 failing assertions):

```
FAILED test_run_report.py::test_row_accounting_reports_a_match
FAILED test_run_report.py::test_row_accounting_flags_a_mismatch
FAILED test_run_report.py::test_build_run_report_signature_has_the_renamed_keyword_only
FAILED test_run_report.py::test_handoff_section_renders_recorded_entries_and_a_scope_note
FAILED test_run_report.py::test_handoff_section_states_none_recorded_when_absent_and_no_gap_without_scope
FAILED test_run_report.py::test_absent_handoff_is_a_named_gap_only_when_scope_count_is_supplied
FAILED test_run_report.py::test_empty_but_present_handoff_renders_nothing_handed_onward_with_no_gap
FAILED test_run_report.py::test_a_malformed_handoff_file_is_a_named_gap_regardless_of_scope_count
FAILED test_run_report.py::test_a_foreign_run_handoff_file_is_a_named_gap_regardless_of_scope_count
FAILED test_run_report.py::test_prune_durable_state_deletes_each_long_ttl_family_past_its_ttl[match_handoff-abc.json]
```

Task 3 was `type="auto"` (no `tdd="true"`), verified by running the four named
skill-contract/sequence-coverage/prose/call-site suites plus the standalone
Python probe after editing — all green, no RED phase required by the plan.

## Deviations from Plan

None — plan executed exactly as written, with one intentional wording adaptation
noted below.

**Adaptation, not a deviation:** the plan's own read-first note anticipated the
current file state was already 8 modules (post-`260911-ss4`) and said "correct
that file's docstring to name eight stores" / "eight modules unchanged" — read
literally against `test_forbidden_marker_parity.py`'s CURRENT docstring ("widened
to eight by ... `match_state.py`"), this plan's own addition makes it **nine**,
not eight. Followed the required-reading instruction to trust the current file
over the plan's stale count: docstring now says "all nine stores" /
"widened ... to nine by ... `match_handoff.py`", and both corpus tests pass over
nine modules. This is the plan's own literal intent (its instructions describe
exactly one net-new module beyond whatever the file currently names) applied
against the file as it actually reads today.

## Known Stubs

None.

## Threat Flags

None beyond the plan's own threat model (T-ss5-01 through T-ss5-06, all
`mitigate`, none rated `high`) — no new network endpoint, auth path, or schema
change at a trust boundary was introduced outside what the plan's threat model
already covers.

## Residual Note (CLAUDE.md §31 rule 1 — prose, not a new todo; no test, no recorded hit)

Whether the other three report-calling skills (`contact-upload`,
`suggest-contacts`, `enrich-records`) should also record a handoff of their own
was raised by the plan's own output note. None of the three routes a row through
a match/confirm step the way `enrich-before-ingest` does, so there is currently
nothing analogous for them to hand off — not observed live as a gap, not fixed
here, out of this plan's scope.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/match_handoff.py` — FOUND
- `operator-claude-plugin/tests/test_match_handoff.py` — FOUND
- Commit `7b5f2fc9` — FOUND (`git log --oneline --all | grep 7b5f2fc9`)
- Commit `06993b19` — FOUND (`git log --oneline --all | grep 06993b19`)
- Commit `af7b8d59` — FOUND (`git log --oneline --all | grep af7b8d59`)
- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` — 2948 passed, 5 skipped
- `node --test tests/n8n/*.test.mjs` — 1101 passed, 0 failed (untouched, confirming
  `git diff --stat n8n/` is empty)
- `plugin.json`/`CHANGELOG.md` — untouched (260911-ss7 owns the version bump)
