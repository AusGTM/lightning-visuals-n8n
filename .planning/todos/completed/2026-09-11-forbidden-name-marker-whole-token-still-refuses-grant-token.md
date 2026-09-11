---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-12
title: Whole-token forbidden-name matching still refuses a person named Grant or a company named Token
area: operator-plugin
severity: minor
files:
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/scripts/run_manifest.py
  - operator-claude-plugin/scripts/run_state.py
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/remainder_queue.py
kind: defect
evidence: operator-claude-plugin/tests/test_forbidden_marker_parity.py (Grant/Token recorded as still-refused); no live row has hit it yet
---

## Found during quick 260911-any (2026-09-11), while closing the Secretary/Armidale todo

Whole-token matching (quick 260911-any, all seven `_looks_forbidden` copies) fixed the
substring false positives — `"Secretary"` and `"Armidale Jockey Club"` now save — but a
value that IS one of the ten markers verbatim, as a whole word, still refuses. A person
whose firstname is literally `"Grant"`, or a company named `"Token"`, still trips the
`"grant"` / `"token"` marker and is refused rather than stored.

Not a regression: the old raw-substring matcher refused these too (and far more besides).
Same yield-leak class as the original todo, at a smaller scale — genuinely rare names
rather than a common committee title. Recorded rather than chased in 260911-any per that
plan's decisions ("Known residual, deliberately not fixed... do not widen scope to chase
it").

## Fix

The original todo's candidate (1) — match markers as whole tokens on the FIELD NAME only,
never on values — is the fix, if the tradeoff is ever worth it: a grant or secret smuggled
into a persisted entry arrives under a telling key, not as the word "Grant" in a firstname
cell or "Token" in a company name. 260911-any's own decisions record explicitly rejected
this for now because three shipped tests pin VALUE refusals as load-bearing
(`test_written_records.py` T-59-02, `test_held_queue.py:174`
`"n8n_api_key=super-secret"`, `test_run_manifest.py:112` the verdict `"armed"`) — dropping
value scanning reverses all three. A fix here has to keep those three passing while
exempting a bare marker-shaped VALUE from refusal, which is a different (and more
involved) change than 260911-any's whole-token matching pass.

Test shape: offline; a row with firstname `"Grant"` or company `"Token"` saves in all
seven stores; the three value-refusal regression tests above stay red for their existing
fixtures.

## Update 2026-09-11 (quick 260911-w6o, F2-1)

`held_queue.py`'s `row` payload no longer scans VALUES at all -- only key names (see
`held_queue._first_forbidden_key` and `save()`'s call site). A held row for a person
named Grant Dewsbury now persists through this one store, because
`held_queue.ROW_FIELD_ALLOWLIST` already filters `row` to a closed, enumerated tuple
before the scan runs, so a forbidden-shaped KEY can never reach `row` through
`build_entry` at all -- the value scan's only live effect there was refusing legitimate
values (a person's own name, a company's own name, an email), which is exactly the
class this todo describes. `held_queue`'s own `observed_signals`, `reason`, and
`row_id` scans are UNCHANGED (still key-and-value). The other six stores named in this
todo's `files:` list (`suggestion_declines.py`, `run_manifest.py`, `run_state.py`,
`run_report.py`, `written_records.py`, `remainder_queue.py`) are untouched by this
change and still refuse a bare marker-shaped value verbatim. This todo stays open for
those six.

## Resolved by Phase 71 (2026-09-12) — closed for two identity-keyed stores only

Closed by **D-71-01..05** (the same rekey that gave `held_queue.py` a stable, group-prefixed
identity key created the surface this fix applies to) and **D-69-01**'s own anti-DRY
discipline (nine deliberate reimplementations of the forbidden-marker check, pinned
behaviourally identical — not by import — by `test_forbidden_marker_parity.py`).

**Factual correction first, since it changes what "closed" can mean here.**
71-CONTEXT.md's Folded Todos note says every store this todo lists takes "the same fix
through the shared matcher." **There is no shared matcher.** Each store reimplements
`_looks_forbidden`-shaped logic independently by design (D-69-01), so the fix in this phase
lands at CALL SITES, one store at a time — never in a matcher all nine share — and
`test_forbidden_marker_parity.py` is unmodified and green throughout.

**What actually closed, and where:**

- **`held_queue.py`** (plan 01, Task 2) — `save()`'s entries-map key check now exempts a key
  that IS one of `identity_keys(entry["row"])` from the forbidden-marker scan; any other
  marker-shaped key (e.g. `webhook_secret`) is still refused. `_looks_forbidden()` itself is
  untouched.
- **`suggestion_declines.py`** (plan 01, Task 3) — the identical exemption applied to
  `entry_key(company_id, row)`, closing an ALREADY-LIVE production defect this todo's own body
  named: a decline for a person named "Grant" had always tripped the whole-token marker and
  refused to save, independent of this phase's own rekey.

The defect this fix closes can only fire in a store whose KEY or allowlisted row payload is
DERIVED from a person's or company's own name. That is exactly these two stores. The fold's
scope is these two, not all nine (or six remaining) the original `files:` list named.

**`written_records.py` — deliberately left unchanged, the accepted won't-fix, stated here
rather than as a successor todo.** `written_records.py` still scans a written record's
property VALUES and can still refuse a person named Grant. This is left alone on purpose:
`test_written_records.py`'s **T-59-02** pins that value refusal as load-bearing regression
coverage, and narrowing it is a separate judgement call with its own regression cost that this
phase's own scope does not cover. Per CLAUDE.md §31 rule 1 ("a residual with no test and no
recorded hit is a sentence in the SUMMARY, not a todo") this is recorded as the accepted
disposition inside this completed note — **no successor todo is opened for it.**

The remaining five stores this todo originally named — `run_manifest.py`, `run_state.py`,
`run_report.py`, `remainder_queue.py`, and the not-originally-listed
`match_state.py`/`match_handoff.py` — are not touched by this phase and were never candidates
for this fix: none of them keys or allowlists a value derived from a person's or company's own
name (`run_manifest`/`run_state` key on a system-minted `row_id` and a closed verdict
vocabulary; `run_report` already splits its own key and value matchers; `remainder_queue` is
already key-only; `match_state`/`match_handoff` key on a run id). Their forbidden-marker
behaviour is unrelated to what this todo describes and stays exactly as it was before this
phase.

**Covering tests** (by nodeid, from the 71-01 SUMMARY `coverage:` block):
- `operator-claude-plugin/tests/test_held_queue.py#test_save_refuses_a_key_that_is_marker_shaped_and_not_the_entrys_own_identity`
- `operator-claude-plugin/tests/test_forbidden_marker_parity.py` (unmodified, green)
- `operator-claude-plugin/tests/test_suggestion_declines.py#test_a_decline_for_grant_dewsbury_persists`
