# Phase 68: State the price and keep moving - Pattern Map

**Mapped:** 2026-09-07
**Files analyzed:** 13 (5 scripts, 6 SKILL.md, 3 tests — one file, `test_report_sufficiency.py`, is a shared constraint not a per-file target; `test_watch_bound_fallback.py`/`test_watch_settle_reporting.py` are prior-art analogs, not edit targets)
**Analogs found:** 13 / 13 — this phase is unusual: every file to be touched already has its own closest analog living inside the SAME file (the pattern to copy is "the existing sibling branch/function next to the one you're adding"), because RESEARCH.md already did file:line-level analog discovery. This document restates that discovery in PATTERNS.md's required shape and adds the git-tracked-source gate check.

**Tracked-source gate:** all 13 paths below verified via `git ls-files -- <path>` this session — every one prints (tracked). None are gitignored mirrors; there is no `.gsd/capabilities/` involvement in this repo's plugin layout. Safe to name directly.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/watch.py` (add `pre_spend_pause`) | utility (DI'd wall-clock helper) | event-driven (bounded wait) | same file's `poll_until_settled` (lines 292-313) + `watch` (343-359) | exact — same file, same DI idiom |
| `operator-claude-plugin/scripts/write_grant.py` (implicit-open branch calling existing `plan_grant`/`envelope`) | service (grant arithmetic + arming) | CRUD (mint/read a grant envelope) | same file's existing `enrich-records`-style call at `envelope(..., suggestion_companies=N, suggestion_cap=None)` (415-447) and `plan_grant`'s `CEILING_OVER`-only refusal (1096-1118) | exact — reuse, no new function needed |
| `operator-claude-plugin/scripts/suggest_contacts.py` (`agreed_cap`/`CapRefused` — verify untouched) | service (cap validation, refusal) | request-response (validate a chosen cap against a priced ceiling) | itself, lines 420-464 — this file is the "don't touch" analog: confirm the diff does NOT modify `CapRefused`'s raise conditions | exact (regression-fence, not a new-code analog) |
| `operator-claude-plugin/scripts/scheduled_arm.py` (no code change — new test asserts its import list) | controller (headless/cron entrypoint) | batch | itself, import list lines 74-82 — analog is "what NOT to add" (no `write_grant` import) | exact |
| `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` step 5 (289-296) + step 7 (655-665) | prose contract (consent ask → statement) | request-response → event-driven (statement-and-proceed) | itself — this file IS the source-of-truth quoted verbatim by `suggest-contacts` step 4; the analog for "how to phrase a statement that used to be a stop" is `backend-status/SKILL.md:149-152` ("Re-check only when the operator asks... does not watch the backend; it answers a question when asked") | exact for the target shape, cross-file for phrasing tone |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` step 4 (61-92) | prose contract (two-branch ask) | request-response | itself — the GRANTED branch (already disclosure-without-stop) is the literal analog the no-grant branch must be edited to match | exact |
| `operator-claude-plugin/skills/enrich-records/SKILL.md` steps 5-6 (184-236) | prose contract | request-response | `enrich-before-ingest/SKILL.md` step 5 (the shape it already copies) | exact |
| `operator-claude-plugin/skills/contact-upload/SKILL.md` (grant-vs-no-grant ask ~230+, and the D-59-06 restatement at 266-268) | prose contract | request-response | `enrich-before-ingest/SKILL.md` step 5/step 7 pairing | role-match (independent phrasing, same shape — treat as in-scope-by-analogy per RESEARCH.md Assumption A2) |
| `operator-claude-plugin/skills/backend-control/SKILL.md` (95-115, "Opening a write grant" + D-59-06 restatement) | prose contract (the direct grant command D-68-07 wants surfaced) | request-response | itself — this command already exists; other skills should point at it inline rather than re-implement it | exact (the analog IS the target; no new command) |
| `operator-claude-plugin/skills/review-triage/SKILL.md` (212-231) | prose contract | request-response (per-record decision, unchanged) | itself — explicit self-exemption already in prose: "This per-record ritual is unchanged by the grant" | exact — do-not-touch analog |
| `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` (`ENRICHMENT_CONSENT`/`INGEST_CONSENT`, `_normalized()`, lines 53-54 + docstring's VOCAB-05/D-59-07/09 update history) | test (SKILL.md-prose contract pin) | request-response (string/structural assertions) | itself — this file's own prior rewrite history (VOCAB-05) is the analog for HOW to update a pinned constant when the underlying prose changes | exact |
| `operator-claude-plugin/tests/test_skill_sequence_coverage.py` (`COVERED`/`NOT_A_PIPELINE`/`GRANDFATHERED_UNCOVERED` maps, `MAX_GRANDFATHERED = 0`, lines 187, 411, 421-428) | test (call-sequence ratchet) | batch (static extraction across all SKILL.md files) | itself — any new `python` fence sequence (e.g. `write_grant.plan_grant(...)` in a previously grant-less branch, or a new `watch.pre_spend_pause(...)` call) must be registered here in the same commit | exact |
| `operator-claude-plugin/tests/test_report_sufficiency.py` (`_POLL_LOOP_ALLOWED = {"watch.py"}`, `_imports_forbidden_module`/`_calls_sleep`/`_has_while_loop`, lines 193-242) | test (no-sleep/no-while/no-time-import ratchet) | batch (AST-walk every `scripts/*.py` except `watch.py`) | itself — this is the CONSTRAINT the new `watch.py` function must satisfy; do not add `import time`/`sleep(...)`/`while` to any other script | exact (constraint, not a code target) |

## Pattern Assignments

### `operator-claude-plugin/scripts/watch.py` — new `pre_spend_pause` function

**Analog:** same file, `poll_until_settled` (lines 292-313) and `watch`'s wiring of it (343, 356)

**DI pattern to copy** (`watch.py:292-296`, `343`, `356`):
```python
def poll_until_settled(read_once, bound_seconds, run_handle, *, now, sleep,
                        backoff_schedule=BACKOFF_SCHEDULE_SECONDS, lane="enrichment",
                        **settled_report_kwargs):
    """... `now` and `sleep` are both injected so a test drives the bound boundary
    from either side without a real clock ever running — production supplies
    `time.monotonic`/`time.sleep`, a test supplies a fake ..."""

def watch(config, run_handle, *, lane="enrichment", record_count=None,
          pre_dispatch_balances=None, get_transport=requests.get,
          now=None, sleep=None):
    ...
    return poll_until_settled(
        read_once, bound_seconds, run_handle,
        now=now or time.monotonic, sleep=sleep or time.sleep,
        ...
    )
```

**What to write, matching this exact shape:**
```python
PRE_SPEND_PAUSE_SECONDS = 7  # within D-68-05's 5-10s band; Claude's Discretion on exact value

def pre_spend_pause(seconds=PRE_SPEND_PAUSE_SECONDS, *, sleep=None):
    """A real, once-per-round wall-clock pause (D-68-05) immediately before the first
    credit-spending call of a batch, so the window between the operator reading the
    stated line and reacting is a window that actually exists. `sleep` is injected —
    production supplies `time.sleep`, a test supplies a fake — mirroring
    `poll_until_settled`'s `now=`/`sleep=` DI pattern above."""
    (sleep or time.sleep)(seconds)
```

`watch.py` is the ONLY plugin script exempt from `_POLL_LOOP_ALLOWED` (`test_report_sufficiency.py:193`) — this function must live here, never in `write_grant.py`, `suggest_contacts.py`, or any new module. Invoke via `python3 scripts/watch.py --pre-spend-pause` (or an equivalent small entrypoint) from a SKILL.md Bash tool call — never a literal `sleep N` Bash instruction (harness risk, Constraint B in RESEARCH.md).

---

### `operator-claude-plugin/scripts/write_grant.py` — implicit-open branch

**Analog:** same file's existing explicit-grant call already used by `enrich-records/SKILL.md` step 5

**Exact call shape to reuse** (`write_grant.py:415-447`, quoted in RESEARCH.md):
```python
def envelope(config, *, object_type, record_ids, record_domains, providers,
             transport=None, today=None, headroom=None,
             suggestion_companies=None, suggestion_cap=None):
    """`suggestion_companies=None` (default, D-62-11): the whole suggestion-allowance
    branch is skipped ... A non-negative int prices a suggestion round's worst-case
    ceiling (`cost_guard.suggestion_line`) at `suggestion_cap` (or `PRICED_CAP`
    when omitted — the sitting has not chosen a cap yet at grant-open) ..."""
```

D-68-03's implicit open should call `plan_grant(config, lanes=[...], object_type="companies", ..., suggestion_companies=<batch's own company count>)` — the IDENTICAL call `enrich-records/SKILL.md` step 5 already makes for the explicit path. No new function, no new pricing arithmetic.

**Refusal fence to leave untouched** (`write_grant.py:1117-1118`):
```python
ceiling = figures["ceiling"]
if ceiling["verdict"] == CEILING_OVER and not override:
    # ... only this branch refuses; CEILING_UNKNOWN and CEILING_OK both proceed
```
`CEILING_UNKNOWN` proceeds today (D-57-02) — the implicit-open path inherits this unchanged (D-68-10 confirms: Option A, no Phase-68-only fence). The pre-spend stated line must name the unsampled ceiling in words when this verdict is `CEILING_UNKNOWN`.

---

### `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` step 5 (289-296) and step 7 (655-665) — source-of-truth ask → statement

**Analog for tone:** `backend-status/SKILL.md:149-152` (already ships the D-68-09 posture):
```
Re-check only when the operator asks... This skill does not watch the backend;
it answers a question when asked.
```

**Pinned phrases that must survive** (`test_enrich_before_ingest_skill_contract.py:53-54`):
```python
ENRICHMENT_CONSENT = "arms this run and nothing else"
INGEST_CONSENT = "arms this write and nothing else"
```
If D-68-01 restructures the no-grant ask, these two constants (or their replacement statement-phrases) must change in the SAME commit as the SKILL.md edit, per the module's own documented update discipline (VOCAB-05, 2026-08-25 — see its docstring for the precedent of how a prior phrase rewrite was pinned).

**Propagation sites requiring the same-commit edit** (three `grep` hits, RESEARCH.md "Verbatim-Quote Propagation Sites"):
- `enrich-before-ingest/SKILL.md:290` — "arms this run and nothing else"
- `enrich-before-ingest/SKILL.md:659` — "arms this write and nothing else"
- `suggest-contacts/SKILL.md:92` — cross-reference + paraphrase, not a literal quote, but must track the source

Independently-phrased (not test-pinned by the same file, but same VOCAB-05 shape, update together per RESEARCH.md Assumption A2):
- `contact-upload/SKILL.md:246` — "arms this send and nothing else"
- `enrich-records/SKILL.md:214-215` — "arms this send and nothing else"

---

### `operator-claude-plugin/skills/suggest-contacts/SKILL.md` step 4 (61-92) — no-grant branch converts to match the granted branch

**Analog:** the file's OWN granted branch, already correct per spec (disclosure-without-stop) — copy its tone into the no-grant branch rather than inventing new prose.

**Refusal that must stay a hard stop, never softened** (`suggest_contacts.py:420-464`):
```python
# agreed_cap raises CapRefused when:
#   - grant_figures["suggestion_allowance"]["priced_cap"] is missing/non-positive
#   - chosen_cap is not a positive int
#   - chosen_cap > priced_cap
# "never clamps, never defaults"
```
D-68-02: the cap CHOICE itself stays a genuine ask (role/cap selection); only the arming consequence attached to it changes tone.

---

### `operator-claude-plugin/skills/backend-control/SKILL.md` (95-109) — the direct grant command D-68-07 surfaces

**Analog:** itself — the command already exists, quoted verbatim:
```
**Opening a write grant** — the same shape one step larger: one action, one confirmation,
for a whole named batch instead of one send. `write_grant.plan_grant(...)` composes the
proposal and `write_grant.open_grant(proposal, "yes", config)` opens it; only the exact
string `yes` proceeds, exactly as `execute_action` does. Show the operator the envelope as
arithmetic before the yes...
```
D-68-07's fix is discoverability: other skills' entry points (`enrich-records` step 5, `enrich-before-ingest` step 1/5, `suggest-contacts` step 4's no-grant branch) should inline-offer this SAME action rather than re-implement grant-opening. No new script or function.

---

### `operator-claude-plugin/skills/review-triage/SKILL.md` (212-231) — do-not-touch analog

**Analog:** itself — the skill already states its own exemption:
```
"This per-record ritual is unchanged by the grant"
"what changed underneath it is only the authority, never the act."
```
Confirmed out of scope; the audit should record this as a verified non-change, not revisit it.

---

### Test files — pattern to extend, not replace

**`test_enrich_before_ingest_skill_contract.py`** — extend using its own `_normalized()` idiom and pinned-constant-update discipline (its docstring records prior updates for VOCAB-05, D-59-07/09 — follow the same "update the constant + note why" shape).

**`test_skill_sequence_coverage.py`** — `MAX_GRANDFATHERED = 0` (line 428). Any new/changed `python` fence call sequence (adding `write_grant.plan_grant(...)` to a previously grant-less branch, adding `watch.pre_spend_pause(...)` to a dispatch sequence) MUST be added to `COVERED` or `NOT_A_PIPELINE` in the same commit or the suite fails outright.

**New test needed (Wave 0 gap, no existing file to extend):** `operator-claude-plugin/tests/test_watch.py` (checked: only `test_watch_bound_fallback.py` and `test_watch_settle_reporting.py` exist, neither is a general `test_watch.py`) — pattern to copy is `test_watch_bound_fallback.py`'s style of driving `watch.py`'s DI'd functions with a fake `sleep`:
```python
def test_pre_spend_pause_seconds_in_band():
    assert 5 <= watch.PRE_SPEND_PAUSE_SECONDS <= 10

def test_pre_spend_pause_calls_injected_sleep_once():
    calls = []
    watch.pre_spend_pause(sleep=calls.append)
    assert calls == [watch.PRE_SPEND_PAUSE_SECONDS]
```

**New structural test needed (Wave 0 gap):** mirror `test_report_sufficiency.py`'s AST-walk style to pin Question 3's finding — `scheduled_arm.py` imports no `write_grant`:
```python
import ast
tree = ast.parse(Path("operator-claude-plugin/scripts/scheduled_arm.py").read_text())
imported_names = {n.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for n in node.names}
assert "write_grant" not in imported_names
```

## Shared Patterns

### No `time`/`sleep`/`while` outside `watch.py`
**Source:** `operator-claude-plugin/tests/test_report_sufficiency.py:193-242`
**Apply to:** every `scripts/*.py` file this phase touches EXCEPT `watch.py`
```python
_POLL_LOOP_ALLOWED = {"watch.py"}
# _imports_forbidden_module, _calls_sleep, _has_while_loop are pure AST-walk checks —
# origin-agnostic: any function literally named "sleep", any "import time"/"import sched",
# any "while" loop anywhere in a non-exempt script fails this test.
```

### DI'd clock/sleep idiom
**Source:** `operator-claude-plugin/scripts/watch.py:292-296, 343, 356`
**Apply to:** the new `pre_spend_pause` function — `now`/`sleep` (or just `sleep` here, no bound-checking needed) as keyword-only, defaulting to the real `time` function, overridable by a test.

### Verbatim-quote-propagates-by-quotation
**Source:** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (source of truth) → `suggest-contacts/SKILL.md:92` (quoting site)
**Apply to:** any edit to the two-phase ask's wording — must land in the source file, its quoting sites, and the pinned test constants, in the same commit.

### `MAX_GRANDFATHERED = 0` sequence ratchet
**Source:** `operator-claude-plugin/tests/test_skill_sequence_coverage.py:428`
**Apply to:** any SKILL.md edit that adds/changes a fenced `python` call sequence — register in `COVERED`/`NOT_A_PIPELINE` same commit, no exceptions.

### Refusal stays in code, never prose
**Source:** `suggest_contacts.py:420-464` (`CapRefused`), `write_grant.py:1117-1118` (`CEILING_OVER`)
**Apply to:** every SKILL.md prose edit in this phase — D-68-06 forbids "proceed unless interrupted" from ever becoming "proceed past a refusal." No diff in this phase should touch either raise condition.

## No Analog Found

None — every file in scope has either a same-file sibling pattern or an existing cross-file exact match (per RESEARCH.md's own file:line audit). The two Wave-0 test gaps (`test_watch.py`, the `scheduled_arm.py` import-boundary test) have close structural analogs (`test_watch_bound_fallback.py`, `test_report_sufficiency.py`'s AST-walk) even though no file with those exact names exists yet.

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/skills/*/SKILL.md`, `operator-claude-plugin/tests/`
**Files scanned:** 13 target files + 2 test-analog files (`test_watch_bound_fallback.py`, `test_watch_settle_reporting.py`) + 1 tone-analog (`backend-status/SKILL.md`)
**Pattern extraction date:** 2026-09-07
**Source:** this document restates and cross-checks `.planning/phases/68-state-the-price-and-keep-moving/68-RESEARCH.md`'s file:line evidence (already HIGH confidence, verified this session) rather than re-deriving it independently — RESEARCH.md's "Don't Hand-Roll" table and "Architectural Responsibility Map" are the primary source for every analog above.
