---
status: complete
quick_id: 260911-any
phase: quick-260911-any
plan: 01
one_liner: Whole-token forbidden-name matching in all seven durable stores — "Secretary" and "Armidale Jockey Club" now save, every genuine marker still refuses.
requirements-completed: []
tech-stack:
  added: []
  patterns:
    - "camel-break + lowercase + split-on-non-alnum tokenisation, padded and matched as whole ` marker `/` markers `/` markered `/` markering ` runs, reimplemented independently in each of seven store modules (no shared helper, per D-69-01)"
key-files:
  created:
    - operator-claude-plugin/tests/test_forbidden_marker_parity.py
    - .planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md
  modified:
    - operator-claude-plugin/scripts/held_queue.py
    - operator-claude-plugin/scripts/suggestion_declines.py
    - operator-claude-plugin/scripts/run_manifest.py
    - operator-claude-plugin/scripts/run_state.py
    - operator-claude-plugin/scripts/run_report.py
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/scripts/remainder_queue.py
    - operator-claude-plugin/tests/test_suggestion_declines.py
    - operator-claude-plugin/tests/test_held_queue.py
    - .planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md
decisions:
  - "Shipped candidate (2) whole-token matching, not the todo's preferred candidate (1) field-name-only matching — three shipped tests (T-59-02, held_queue:174, run_manifest:112) pin VALUE refusals as load-bearing; dropping value scanning would have reversed all three."
  - "All seven store copies changed in one commit, not the three the todo's own frontmatter names (held_queue, suggestion_declines, run_manifest) — the literal marker list also lives in run_state.py, run_report.py, written_records.py, remainder_queue.py."
  - "No shared helper module introduced — each of the seven copies reimplements _tokenised/_FORBIDDEN_TOKEN_RUNS/_looks_forbidden independently, per D-69-01's anti-DRY discipline, pinned by test_run_report.py's pre-existing `is not` distinct-object assertions."
  - "Known residual left unfixed and recorded as a new pending todo: a firstname literally 'Grant' or a company named 'Token' still refuses (whole-token exact-marker hit) — same yield-leak class as the original bug, not a regression, deliberately out of scope for this fix."
metrics:
  duration: "~35 min"
  completed: "2026-09-11"
actuals:
  tokens: 9500
  tasks: 3
  commits: 3
  plan_head_before: "20f5fbf3"
---

# Quick 260911-any: Forbidden-name markers refuse Secretary and Armidale Summary

Fixed the inherited `_looks_forbidden` raw-substring guard across all seven durable
plugin stores (`held_queue.py`, `suggestion_declines.py`, `run_manifest.py`,
`run_state.py`, `run_report.py`, `written_records.py`, `remainder_queue.py`), which
refused any value merely *containing* one of ten forbidden-name markers — so a jobtitle
of `"Secretary"` tripped `"secret"` and a company named `"Armidale Jockey Club"` tripped
`"arm"`, losing real club committee members and NSW racing bodies from the
suggestion-decline and held-queue stores on every round.

## What changed

Each of the seven copies now tokenises its input (camel-break on `lower→UPPER`
boundaries, lowercase, split on non-alphanumeric runs) into a padded, space-joined
token string, and matches each of the ten `_FORBIDDEN_NAME_MARKERS` — crossed with
inflection suffixes `""`/`"s"`/`"ed"`/`"ing"` — as a whole padded run (`" arm "`,
`" armed "`, `" api key "`, `" api keys "`, …) rather than a raw substring. This lets
`"Secretary"`, `"Armidale Jockey Club"`, `"Armstrong Racing"`, `"pharmacy supplier"`,
`"farm"`, and `"disarmed"` all pass, while `"arm"`, `"armed"`, `"arming"`,
`"webhook_secret"`, `"N8N_API_KEY"`, `"webhookSecret"`, `"apiKey"`, `"credentials"`,
`"permissions"`, `"api_tokens"`, and every marker verbatim still refuse. `run_report.py`
keeps its pre-existing two-set split (`_FORBIDDEN_NAME_MARKERS` for keys,
`_VALUE_MARKERS` excluding `arm`/`webhook` for values) — both sets got the same
token-run treatment, neither set's membership changed. `_FORBIDDEN_NAME_MARKERS` itself
is byte-identical (ten members, same order) in all seven copies; no shared helper
module was introduced — the reimplemented-not-imported discipline (D-69-01) is
deliberate and stays pinned by `test_run_report.py`'s existing distinct-object
assertions.

New `operator-claude-plugin/tests/test_forbidden_marker_parity.py` drives one corpus
(a MUST-PASS list and a MUST-REFUSE list) through all seven modules' matchers by name —
the behavioural drift guard tuple equality alone cannot provide, since a copy left on
the old substring rule would still show an equal tuple.

## Deviations from Plan

None — plan executed exactly as written, including the candidate-(2)-not-(1) decision,
the seven-copies-not-three scope, the no-shared-helper constraint, and the deliberate
Grant/Token residual.

## Known Residual (not a stub — a documented, tracked tradeoff)

A firstname literally `"Grant"` or a company named `"Token"` still refuses under
whole-token matching (it matches a marker verbatim). This is the same yield-leak class
as the original bug, at a much smaller scale, and is **not a regression** — the old
substring matcher refused these too. Recorded as a new pending todo:
`.planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md`.

## Test Results

- RED (Task 1): `test_forbidden_marker_parity.py`, `test_suggestion_declines.py`,
  `test_held_queue.py` — 4 failed, 62 passed (the Secretary/Armidale and parity
  assertions failed as expected against the shipped substring matcher; every
  pre-existing refusal test in the two edited files passed).
- GREEN (Task 2): the same three files plus `test_run_manifest.py`, `test_run_state.py`,
  `test_run_report.py`, `test_written_records.py`, `test_remainder_queue.py` — 365
  passed, 0 failed.
- Must-refuse corpus check: `test_forbidden_marker_parity.py::test_every_key_matcher_refuses_the_must_refuse_corpus`
  and `::test_run_report_key_matcher_passes_and_refuses_the_same_corpus` — both pass,
  covering `webhookSecret`, `N8N_API_KEY`, `api_tokens`, `credentials`, `armed`,
  and all ten markers verbatim across all seven stores.
- Full plugin suite (Task 3): `operator-claude-plugin/tests` — 2882 passed, 5 skipped,
  0 failed.
- Node suite (Task 3): `node --test tests/n8n/*.test.mjs` — 1101 pass, 0 fail.
- `git diff --quiet -- n8n/` — clean (N8N_CLEAN), confirming this change is Python-only.

## Self-Check: PASSED

- `operator-claude-plugin/tests/test_forbidden_marker_parity.py` — FOUND
- `operator-claude-plugin/scripts/held_queue.py` — FOUND, contains `_tokenised`/`_FORBIDDEN_TOKEN_RUNS`
- `.planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md` — FOUND
- `.planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md` — FOUND
- Commit `5b68ad02` (RED tests) — FOUND in `git log`
- Commit `b30e8037` (GREEN implementation) — FOUND in `git log`
- Commit `1b19432c` (todo closure) — FOUND in `git log`
