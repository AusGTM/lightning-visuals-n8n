---
quick_id: 260911-any
phase: quick-260911-any
plan: 01
wave: 1
type: execute
depends_on: ["260911-ao0"]
files_modified:
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/scripts/run_manifest.py
  - operator-claude-plugin/scripts/run_state.py
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/remainder_queue.py
  - operator-claude-plugin/tests/test_suggestion_declines.py
  - operator-claude-plugin/tests/test_held_queue.py
  - operator-claude-plugin/tests/test_forbidden_marker_parity.py
  - .planning/todos/pending/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md
  - .planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md
autonomous: true

must_haves:
  truths:
    - A suggestion-decline entry whose jobtitle is "Secretary" and whose company is "Armidale Jockey Club" saves and loads back unchanged.
    - A held-queue entry naming "Armidale Jockey Club" and a reason mentioning the club Secretary saves.
    - Every marker still refuses in its own right — key `webhook_secret`, key `n8n_api_key`, key/value `armed_row`, verdict `armed`, value `n8n_api_key=super-secret`, value `bad webhook_secret configured` all still raise and write nothing.
    - Plural and inflected forms still refuse — `credentials`, `permissions`, `api_tokens`, `arming`, and camelCase `webhookSecret`.
    - All seven store copies answer the same corpus identically — no copy is left on the substring rule.
  artifacts:
    - operator-claude-plugin/tests/test_forbidden_marker_parity.py
    - operator-claude-plugin/scripts/suggestion_declines.py
    - operator-claude-plugin/scripts/held_queue.py
    - .planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md
  key_links:
    - "_FORBIDDEN_TOKEN_RUNS is derived from the UNCHANGED ten-marker _FORBIDDEN_NAME_MARKERS tuple in each copy — the tuple stays the single enumerated source, so test_remainder_queue's ten-markers-not-nine test and test_run_report's per-marker parametrize stay green."
    - "test_forbidden_marker_parity.py runs one corpus through all seven modules' matchers by name — the behavioural drift guard the todo asked for; tuple equality alone cannot detect a copy left on substring matching."
    - "run_report keeps its two-set split: _FORBIDDEN_NAME_MARKERS for keys, _VALUE_MARKERS (no arm/webhook) for values — both get the token treatment, neither set changes membership."
---

<objective>
Stop the inherited forbidden-name guard refusing real club data. `_looks_forbidden` matches its
ten markers as raw substrings, so `"Secretary"` trips `"secret"` and `"Armidale Jockey Club"` trips
`"arm"` — every Secretary in every suggestion round is lost from the decline store.

Purpose: close todo `2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale` (major) with
the smallest change that keeps the guard's intent.
Output: whole-token matching in all seven store copies, one commit, with a behavioural parity test.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/todos/pending/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md
@operator-claude-plugin/scripts/held_queue.py
@operator-claude-plugin/scripts/suggestion_declines.py
@operator-claude-plugin/scripts/run_report.py
@operator-claude-plugin/scripts/remainder_queue.py
</context>

<decisions>
**Candidate (2), not the todo's preferred (1).** The todo prefers "match on FIELD NAMES only, never
on values". That is neither smaller nor safer here: three shipped tests pin VALUE refusals as
load-bearing (`test_written_records.py:248` T-59-02 `"bad webhook_secret configured"`,
`test_held_queue.py:174` `"n8n_api_key=super-secret"`, `test_run_manifest.py:112` the verdict
`"armed"`), and dropping value scanning would reverse all three across seven modules. Whole-token
matching fixes both reported false positives while keeping every one of those refusals.

**Seven copies, not the todo's three.** The todo's frontmatter names `suggestion_declines`,
`held_queue`, `run_manifest`; the literal list also lives in `run_state.py`, `run_report.py`,
`written_records.py`, `remainder_queue.py`. All seven change in one commit.

**No shared helper.** The reimplemented-not-imported discipline is deliberate (D-69-01,
`held_queue.py`'s own docstring, `remainder_queue.py:34-40`) and pinned by
`test_run_report.py:117-118`, which asserts the tuples are distinct objects. Do NOT extract a
module. Duplicate the matcher seven times; the new parity test is what stops drift.

**No plugin version bump, no CHANGELOG entry.** Five sibling batch items also touch this plugin;
a per-item bump collides. Release is batch-level.

**Known residual, deliberately not fixed:** a person whose firstname is `Grant` still refuses
(whole token, exact marker). Not a regression — substring refused it too — but it is the same
yield-leak class. Record it as a follow-up todo in Task 3, do not widen scope to chase it.
</decisions>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — Secretary and Armidale must save, everything forbidden must still refuse</name>
  <files>operator-claude-plugin/tests/test_suggestion_declines.py, operator-claude-plugin/tests/test_held_queue.py, operator-claude-plugin/tests/test_forbidden_marker_parity.py</files>
  <read_first>operator-claude-plugin/tests/test_suggestion_declines.py lines 425-450, operator-claude-plugin/scripts/suggestion_declines.py lines 60-200, operator-claude-plugin/scripts/held_queue.py lines 95-215, operator-claude-plugin/scripts/run_report.py lines 85-140</read_first>
  <behavior>
    - `test_suggestion_declines.py`: REPLACE `test_a_real_company_name_containing_a_forbidden_marker_is_refused_not_dropped` (line 433) — it pins exactly the behaviour being removed. Its replacement builds an entry with jobtitle `"Secretary"` and company `"Armidale Jockey Club"`, asserts `first_refusal` returns `None`, `save` writes, and `load` returns the entry with both strings intact.
    - `test_suggestion_declines.py`: COMPANION test keeping the `unstorable` reporting path load-bearing — an entry whose `provenance` carries a key named `grant` (or a `row` value `"n8n_api_key=super-secret"`) still returns a `first_refusal` sentence and `save` raises with nothing written.
    - `test_held_queue.py`: a held entry whose `row["company"]` is `"Armidale Jockey Club"` and whose `reason` mentions "the club Secretary" saves and loads back — this exercises both the allowlisted-row scan and the free-text `reason` scan.
    - NEW `test_forbidden_marker_parity.py`: one corpus, run through every one of the seven modules' matchers by name (`held_queue`, `suggestion_declines`, `run_manifest`, `run_state`, `written_records`, `remainder_queue` expose `_looks_forbidden`; `run_report` exposes `_looks_forbidden_key` — handle it by name, and check its `_looks_forbidden_value` separately since `arm`/`webhook` are exempt there by design). MUST-PASS members: `Secretary`, `Armidale Jockey Club`, `Armstrong Racing`, `pharmacy supplier`, `farm`, `disarmed`, `The Roma Turf Club`. MUST-REFUSE members: `arm`, `armed`, `arming`, `armed_row`, `webhook_secret`, `n8n_api_key`, `N8N_API_KEY`, `webhookSecret`, `apiKey`, `credentials`, `permissions`, `api_tokens`, `passwords`, `grants`, `op-grant-123`, plus each of the ten markers verbatim.
    - `test_forbidden_marker_parity.py`: also assert the seven `_FORBIDDEN_NAME_MARKERS` tuples are EQUAL by value while remaining distinct objects (the existing `is not` assertions in `test_run_report.py:116-118` stay untouched).
    - Fix the now-false prose in `test_suggestion_declines.py:34` (its docstring claims the fixture avoids a marker SUBSTRING).
  </behavior>
  <action>Write the tests only — no `scripts/` edit in this task. The parity file imports the seven modules directly (`scripts/` is on `sys.path` per `tests/conftest.py`) and drives their matchers; do not import a shared helper, there is none and there must not be one. Expect RED: the Secretary/Armidale cases and the whole parity corpus fail against the shipped substring matcher, which is the proof the guard really is the cause.</action>
  <verify>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -m pytest operator-claude-plugin/tests/test_forbidden_marker_parity.py operator-claude-plugin/tests/test_suggestion_declines.py operator-claude-plugin/tests/test_held_queue.py -q</automated>
  </verify>
  <done>The three files run and FAIL on the Secretary/Armidale and parity assertions; every pre-existing refusal test in the two edited files still passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — whole-token matching in all seven copies</name>
  <files>operator-claude-plugin/scripts/held_queue.py, operator-claude-plugin/scripts/suggestion_declines.py, operator-claude-plugin/scripts/run_manifest.py, operator-claude-plugin/scripts/run_state.py, operator-claude-plugin/scripts/run_report.py, operator-claude-plugin/scripts/written_records.py, operator-claude-plugin/scripts/remainder_queue.py</files>
  <read_first>operator-claude-plugin/scripts/run_report.py lines 85-140 (the only copy with a second, value-only marker set), operator-claude-plugin/scripts/remainder_queue.py lines 28-50 and 105-130</read_first>
  <behavior>
    - `_looks_forbidden("Secretary")` and `_looks_forbidden("Armidale Jockey Club")` are `False` in all seven copies.
    - `_looks_forbidden` is `True` for each of the ten markers verbatim, for snake_case compounds (`webhook_secret`, `n8n_api_key`, `armed_row_1`), for SHOUTING case (`N8N_API_KEY`, `ALLOW_N8N_ARM`), for camelCase (`webhookSecret`), and for inflected forms (`armed`, `arming`, `credentials`, `permissions`, `api_tokens`).
    - `_FORBIDDEN_NAME_MARKERS` still has exactly ten members, same order, in all seven copies.
  </behavior>
  <action>In each of the seven modules, leave `_FORBIDDEN_NAME_MARKERS` byte-identical and replace the body of `_looks_forbidden` (in `run_report.py`: both `_looks_forbidden_key` and `_looks_forbidden_value`) with a token-run match. Add `import re` to each module (stdlib, so `test_no_backend_imports.py`'s requirements check is unaffected).

Per copy, module level, defined BEFORE the derived runs tuple: a `_CAMEL_BREAK` pattern `(?<=[a-z0-9])(?=[A-Z])` and a `_NON_TOKEN` pattern `[^a-z0-9]+`; a `_tokenised(value)` helper that camel-breaks `str(value)`, lowercases it, splits on `_NON_TOKEN`, drops empties, and returns the tokens joined by single spaces with one leading and one trailing space; and `_FORBIDDEN_TOKEN_RUNS`, a tuple built from `_FORBIDDEN_NAME_MARKERS` crossed with the inflection suffixes `""`, `"s"`, `"ed"`, `"ing"` — each entry is `_tokenised(marker)` with its trailing space stripped, the suffix appended, then one trailing space (so `api_key` yields the runs ` api key ` and ` api keys `). `_looks_forbidden(value)` returns whether any run is a substring of `_tokenised(value)`. The padding is what makes it whole-token: ` arm ` is not in ` armidale `, ` secret ` is not in ` secretary `, but ` armed ` is in ` armed row `.

Note the ordering constraint: `_tokenised` must be defined above `_FORBIDDEN_TOKEN_RUNS`, which must be defined above `_looks_forbidden`. `run_report.py` needs a SECOND runs tuple derived from its `_VALUE_MARKERS` (which deliberately drops `arm` and `webhook`); do not change either set's membership. `remainder_queue.py` keeps its keys-only scan position — only the matcher changes.

Update the comments that now describe the old rule, and only those: `run_manifest.py:112-119` ("Deliberately broad substrings … also catches 'armed', 'disarm', 'arming'" — `armed`/`arming` are still caught by the inflection runs, `disarm` no longer is, and `test_run_report.py:93` already pins `disarmed` as legitimate vocabulary); `suggestion_declines.py:39-44` (the whole ponytail block is obsolete — drop the Armidale rationale, keep the sentence explaining why `first_refusal` stays PUBLIC); `remainder_queue.py:34-40` ("matched as plain substrings, so 'arm' matches Armstrong, Armidale, and pharmacy" — now false; the keys-only design and its REVIEW-57-M2 rationale stay); `written_records.py:390` (calls `_looks_forbidden` "a substring check"); `run_report.py:87-89` and `held_queue.py`'s docstring if either states substring semantics. Leave every other line of prose alone.</action>
  <verify>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -m pytest operator-claude-plugin/tests/test_forbidden_marker_parity.py operator-claude-plugin/tests/test_suggestion_declines.py operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_run_manifest.py operator-claude-plugin/tests/test_run_state.py operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_remainder_queue.py -q</automated>
  </verify>
  <done>All eight files pass. Task 1's RED assertions are GREEN, and every pre-existing refusal test across the seven stores still passes unmodified.</done>
</task>

<task type="auto">
  <name>Task 3: full suites, todo closure, follow-up todo</name>
  <files>.planning/todos/pending/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md, .planning/todos/completed/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md</files>
  <action>Run the whole plugin suite and the node suite, and confirm no `n8n/` JSON moved (this change is Python-only; a diff there means something unrelated was picked up).

`git mv` the todo from `pending/` to `completed/`, bump its `updated:` key to 2026-09-11, and append a short "Fixed 2026-09-11 (quick 260911-any)" section naming: candidate (2) rather than the preferred (1) and why (value refusals T-59-02 / `held_queue:174` / `run_manifest:112` would have been reversed); that all SEVEN copies changed, not the three the todo's frontmatter lists; and that `test_forbidden_marker_parity.py` is the drift guard.

Write ONE new pending todo (severity minor, area operator-plugin) recording the residual: a person whose firstname is literally `Grant` — or a company named `Token` — still refuses, because the marker matches as a whole token. Name the store files and note that the todo's own candidate (1) (field names only) is the fix if it ever becomes worth the value-refusal tradeoff.</action>
  <verify>
    <automated>cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc && .venv/bin/python -m pytest operator-claude-plugin/tests -q && node --test tests/n8n/*.test.mjs 2>&1 | tail -5 && git diff --quiet -- n8n/ && echo N8N_CLEAN</automated>
  </verify>
  <done>`operator-claude-plugin/tests` passes with zero failures; `node --test tests/n8n/*.test.mjs` passes 0 fail; `N8N_CLEAN` prints; the todo is in `completed/` with its resolution note; one new pending todo records the `Grant`/`Token` residual.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| in-memory entry -> durable JSON on disk | the forbidden-name guard is the last check before a run's data is persisted where a LATER run can read it back |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-any-01 | Information Disclosure | the seven stores' `_looks_forbidden` | medium | mitigate | Narrowing substring -> whole-token deliberately lets `tokenizer`, `disarm*`, `Armstrong` and `Armidale` through. Kept: the ten markers verbatim, snake_case and SHOUTING compounds, camelCase (`_CAMEL_BREAK`), plurals and `-ed`/`-ing` (the inflection runs), and VALUE scanning in every store that had it (T-59-02 preserved). Cross-store behavioural parity test is the drift guard. |
| T-any-02 | Tampering | seven duplicated copies | medium | mitigate | A copy left on the old rule is invisible to a tuple-equality check — `test_forbidden_marker_parity.py` drives all seven matchers over one corpus, so a missed copy fails loudly. |
| T-any-03 | Information Disclosure | firstname `Grant`, company `Token` | low | accept | Still refused (a whole-token marker hit). Same yield-leak class as the todo, not a regression; recorded as a follow-up todo in Task 3 rather than widening this change. |
</threat_model>

<success_criteria>
- "Secretary" and "Armidale Jockey Club" persist in `suggestion_declines` and `held_queue`.
- Every marker, compound, camelCase and inflected form still refuses in all seven copies.
- `_FORBIDDEN_NAME_MARKERS` unchanged (ten members) in all seven; no shared helper introduced.
- Plugin suite green, node suite green, zero `n8n/` diff, no plugin version bump.
- Todo moved to `completed/` with a resolution note; residual recorded as a new pending todo.
</success_criteria>

<output>
One commit. No SUMMARY file — quick-batch item.
</output>
