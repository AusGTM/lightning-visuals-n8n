---
phase: 34-header-mapping-tolerance
plan: 03
status: complete
completed: 2026-08-05
requirements: [INGEST-02, INGEST-06, STRUCT-04, PREVIEW-01]
---

# 34-03 Summary — Half B where the operator reaches it, both halves proven together

## What shipped

**`operator-claude-plugin/skills/contact-upload/SKILL.md` — new step 2b** (`291a561`).
Runs `header_suggest.py` before the first preview and branches on its four lists.
`refusals` are relayed verbatim; `suggestions` are confirmed **one header at a time, each
answered before the next is asked**, with that column's own `sample_values` shown beside
it; a batched yes is stated to be not a confirmation. The returned `corrected_path`
becomes the one path carried to step 3 and everything after, and `--confirm` is always
applied to the ORIGINAL file.

Lettered 2b rather than renumbered — the file cross-references its own step numbers in
eight places. All five cross-references verified byte-unchanged after the insert.
Step 10's cleanup now names the corrected file alongside the extraction artifact.

**`operator-claude-plugin/tests/test_header_correction_e2e.py`** (`9f8d34e`) — 9 tests
walking `22-messy-headers.csv`, the exact file UAT 2.2 failed on, against the repo's real
`config/column_mapping.yaml`.

**`operator-claude-plugin/tests/test_preview_rendering.py`** (`3c5668b`) — 4 appended
cases proving the corrected path is previewed AND sent.

## The measured inversion

| Header | Before this phase | Now |
|---|---|---|
| `E-mail Address` | dropped | → `email` (Half A) |
| `Org.` | dropped | → `company` (Half A) |
| `LinkedIn Profile` | dropped | → `linkedin_url` (Half A) |
| `Position` | → `jobtitle` | unchanged |
| `Ph.` | dropped | suggested → `phone`, operator confirms |
| `Full Name` | dropped | refused, reason named |
| `Notes` | dropped | reported dropped, no guess |

Six of seven dropped before; four now map deterministically, one is suggested, one is
refused honestly, one is reported. After the operator confirms `Ph.`, the re-preview shows
five of seven — the honest remainder, not a claim of total success.

## RED-CHECKS (all performed, all restored, suite green either side)

1. **Removed Half A's three aliases** from `config/column_mapping.yaml` →
   `test_four_headers_now_map_deterministically_where_two_did_before` and
   `test_re_preview_of_the_corrected_file_reports_five_of_seven_mapping` both failed
   (2 failed, 7 passed). Restored; `git status` clean; 9 passed.
2. **Removed `--confirm` from SKILL.md** →
   `test_skill_md_names_the_script_the_confirm_flag_and_the_corrected_artifact` failed
   (1 failed, 8 passed). Restored; 9 passed.
3. **Dispatched the ORIGINAL path while still asserting the corrected bytes** →
   `test_dispatching_the_corrected_path_puts_the_corrected_header_on_the_wire` failed at
   the body assertion (1 failed, 11 passed). Restored; 12 passed.

## Verification

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | **1002 passed, 5 skipped** (960 baseline + 29 from 34-01 + 13 here) |
| `.venv/bin/python -m pytest -q` | **1883 passed, 6 skipped, 1 warning** |
| `node --test tests/n8n/*.test.mjs` | **553 pass, 0 fail** |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | **0** for every file |
| `git status --short` over `tests/samples` + `scratch` | empty |
| `label_headers` on the sample header row | drops exactly `['Full Name', 'Ph.', 'Notes']` |

## Deviations

1. **`build_preview()["header_labels"]` is already the labels list**, not the
   `{"labels": ...}` dict `label_headers()` returns — `preview.py:169` unwraps it. The
   first draft of the re-preview test indexed it as a dict and raised `TypeError`. Fixed
   in the test, not in `preview.py`: the unwrapping is the established shape every
   existing case in `test_preview_rendering.py` already asserts against, and changing it
   would have been fixing a test by making the codebase's premise false.

## Executed inline, not by a subagent

The `gsd-executor` dispatch for this plan was denied by the Claude Code auto-mode
classifier, as was the `deploy_n8n_workflows.py` invocation 34-02 needs. This plan was
executed inline by the orchestrator instead — the workflow's own documented fallback when
`Agent` is unavailable. Task order, commit protocol, and red-check discipline were
followed unchanged.

## Live-dependent assertion — RESOLVED same day

At the time this summary was first written, 34-02's live half had not run and the preview
and the running backend disagreed. **That gap is now closed.** The operator ran the disarmed
deploy, the four active workflows were bounced deactivate→activate (each verified by an
independent second read), and a GET of the live `LV Contact Ingest` workflow's `Map Columns`
node confirms `"e-mail address"`, `"org."` and `"linkedin profile"` are all present in the
running body, with `active: True`. Read-back: `VERDICT: disarmed PASS`. See 34-02-SUMMARY.md.

## Next

34-04: STATE.md amendment #6, UAT 2.2 marked `fixed-awaiting-walk` (never `PASS` — the
operator walks it), CHANGELOG cut and version bump.
