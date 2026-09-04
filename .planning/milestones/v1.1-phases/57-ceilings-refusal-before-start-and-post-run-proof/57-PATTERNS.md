# Phase 57: Ceilings, refusal-before-start, and post-run proof - Pattern Map

**Mapped:** 2026-08-31
**Files analyzed:** 7 (5 modified, 1 new artifact file, 1 new report surface)
**Analogs found:** 7 / 7 — this phase is pure in-repo wiring; every touched file already has
a close sibling or is itself its own best analog (widened in place).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/write_grant.py` (RUN-05 refusal + `ceiling_breach` producer) | service (grant/authority) | request-response (refuse-with-arithmetic) | `operator-claude-plugin/scripts/n8n_cadence.py::check_budget_floor` | exact — same shape, different budget dimension |
| `operator-claude-plugin/scripts/chunking.py` (mid-run breach hook in `dispatch_plan`) | service (dispatch loop) | batch / event-driven | itself — `dispatch_plan`'s existing per-chunk loop, `D-59-10`'s `written_records_failures` field precedent | exact — extend existing loop, don't invent a second dispatcher |
| `operator-claude-plugin/scripts/written_records.py` (widen `classify_item` vocabulary + add `row_id`) | model / transform (pure classifier) | transform (item → outcome) | itself — `classify_item` widened in place | exact |
| `operator-claude-plugin/scripts/report_enrichment.py` (reconcile `_ACTION_TO_OUTCOME`) | service (report builder) | transform (action → operator-facing word) | `written_records.classify_item` (the vocabulary of record) | role-match — second reader of the same fact, must reconcile not duplicate |
| `operator-claude-plugin/scripts/remainder_queue.py` (NEW, if built beside `held_queue.py`) | model / durable store | file-I/O (atomic write) | `operator-claude-plugin/scripts/held_queue.py` (storage idiom only, not entry schema) + `chunking.failed_batch()` (entry shape) | role-match — same idiom family, deliberately different entry schema |
| AFTER-01 report join (new function/script) | service (report/join) | transform / batch (multi-store join) | `operator-claude-plugin/scripts/report_enrichment.py::build_sync_report` (existing join-and-render shape) | role-match |
| `scripts/prove_ceiling_breach.py` or similar (G-4 ZoomInfo re-probe, disarmed) | utility (disarmed live probe) | request-response (read-only credit check) | `scripts/prove_async_recovery.py` | exact |

## Pattern Assignments

### `operator-claude-plugin/scripts/write_grant.py` (service, request-response refusal)

**Analog:** `operator-claude-plugin/scripts/n8n_cadence.py::check_budget_floor` (lines 452-491)

**Refuse-with-arithmetic pattern (copy this shape exactly — branch order matters):**
```python
# Source: operator-claude-plugin/scripts/n8n_cadence.py:452-491
def check_budget_floor(workflow_id, node_name, interval, config, workflow_items,
                       override=False):
    allowance = _read_positive_float(config, n8n_read.EXECUTION_ALLOWANCE_KEY)
    if allowance is None:
        raise CadenceRefused(
            f"the config key {n8n_read.EXECUTION_ALLOWANCE_KEY!r} is missing, blank or "
            "not a positive number ... so the change is refused rather than guessed at.",
            _BUDGET_SAFE_EXAMPLES)
    # ... requested_cost vs allowance, refuse unless override=True, return arithmetic ...
```
Branch order to replicate for RUN-05: (1) missing/invalid config refuses first, never
overridable; (2) over-budget refuses unless `override=True`, in which case return the
arithmetic with `overridden: True`. This is the ONLY existing "refuse before starting"
precedent in the codebase — do not invent a second refusal shape.

**The consumer already exists, wire only the producer:**
```python
# Source: operator-claude-plugin/scripts/write_grant.py:899-949
def record_send_outcome(grant, outcome, config=None, *, transport=None):
    ...
    if outcome.get("ceiling_breach"):
        return close_grant(updated, CLOSED_CEILING_BREACH)
    # ... guardrail B's own two disarm-failure paths follow ...
```
`CLOSED_CEILING_BREACH = "ceiling_breach"` at `write_grant.py:667`. Verified this session:
`grep -rn "record_send_outcome(" operator-claude-plugin/` → zero production callers, only
`write_grant.py` itself and `test_write_grant.py:1507`. **Do not treat the passing unit
test as evidence the feature is wired** — it exercises the consumer in isolation only.

**The disclosure-not-constraint text being overturned (quote it, don't silently contradict it):**
`write_grant.py:113-154` — D-53-02's verbatim "these figures... do not prevent it" text.
Any new refusal must reference this as the thing it overturns.

**Honest-sampling analog for "what's left this month" (`remaining_allowance_sampled` currently hardcoded `False` at `write_grant.py:261`):**
```python
# Source: operator-claude-plugin/scripts/n8n_read.py:258-381 (signature/return shape)
# executions_in_window(config, window_hours=...) -> {
#     "count_in_window": int, "covers_full_window": bool,
#     "truncated_by_page_cap": bool, "observed_span_hours": float, ...
# }
```
Must check `covers_full_window` before treating `count_in_window` as trustworthy — a
truncated sample (near month-end, `MAX_EXECUTION_PAGES=4` × `EXECUTIONS_WINDOW_PAGE_LIMIT=250`
= 1,000 executions across ALL workflows) under-counts spend. Never read `count_in_window`
without also reading `covers_full_window`.

**Conservative-bias framing to state explicitly in the plan:** `EXECUTIONS_BASIS`
(`chunk_count + record_count`, `write_grant.py:265-270`) is documented to OVER-state
(~3x per P-10, never under-state) — safe direction for a refusal trigger (can only refuse
too early, never let an over-budget batch through). State this as a deliberate, disclosed
bias, not leave it implicit.

---

### `operator-claude-plugin/scripts/chunking.py` (service, mid-run breach hook)

**Analog:** itself — `dispatch_plan`'s existing per-chunk loop, extended with a new
keyword parameter (never named `grant`).

**The hook point (per-chunk loop, excerpted):**
```python
# Source: operator-claude-plugin/scripts/chunking.py:373-444
for index, chunk in enumerate(plan.chunks):
    rows = plan.row_counts[index]
    watcher = _StatusCapturingTransport(transport)
    try:
        envelope = enrichment.build_envelope(chunk, providers)
        body = enrichment.dispatch_enrichment(envelope, armed, config, transport=watcher)
    except NotArmedError:
        raise
    except DispatchError:
        continue          # existing failure path — do not fold a breach into this
    try:
        flushed = written_records.append_chunk(run_id, index, body)
    except written_records.WrittenRecordsError as e:
        flushed = False   # never stops the loop (D-59-10)
    # <-- a running-tally ceiling check reads `body`/`chunk_index` here and can
    #     `break` the for loop — distinct from the existing continue-on-failure paths
```

**Anti-pattern — the pinned-unavailable parameter name:**
```python
# Source: operator-claude-plugin/tests/test_write_grant.py:1455-1463
# test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against asserts:
#   "grant" not in inspect.signature(chunking.dispatch_plan).parameters
```
A new kwarg (e.g. `ceiling=`, `record_send_outcome_cb=`) is fine; a parameter literally
named `grant` fails this test.

**Give the breach stop its own field, do not fold it into existing failure vocabulary
(mirrors `written_records_failures`'s own precedent):**
```python
# Source: operator-claude-plugin/scripts/chunking.py:134-148 (D-59-10 precedent — the
# shape to copy for the new "chunks never attempted due to ceiling" field on DispatchOutcome)
```
A deliberate budget stop must be distinguishable from `ChunkResult(ok=False, reason=...)`
— an unwanted, recovered-from failure. See Common Pitfall 5 in RESEARCH.md.

**`failed_batch()` — the re-sendable shape for the remainder (D-57-04), not a `held_queue` entry:**
```python
# Source: operator-claude-plugin/scripts/chunking.py:494-517
def failed_batch(chunks):
    """The failed chunks as ONE record specification, or None when nothing failed.
    ... already a well-formed enrichment request by construction ..."""
    if not chunks:
        return None
    if len(chunks) == 1 and chunks[0].get("list"):
        return dict(chunks[0])
    if "rows" in chunks[0]:
        rows = [row for chunk in chunks for row in chunk.get("rows", [])]
        ...
        return {"rows": rows, "object_type": chunks[0].get("object_type")}
    record_ids = [rid for chunk in chunks for rid in chunk.get("record_ids", [])]
    ...
    return {"record_ids": record_ids, "object_type": chunks[0].get("object_type")}
```

---

### `operator-claude-plugin/scripts/written_records.py` (model, widen `classify_item`)

**Analog:** itself. Read the module docstring and `classify_item` in full before touching
— this is the single vocabulary of record and every widening must preserve its existing
discipline (fail loud on non-dict, forbidden-name scan, PII exclusion).

**Current three-outcome collapse (to widen per D-57-03's six-outcome table):**
```python
# Source: operator-claude-plugin/scripts/written_records.py:96-182 (verified this session)
WRITE_ACTIONS = frozenset({"update", "enrich", "create"})

_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

def classify_item(item) -> dict:
    if not isinstance(item, dict):
        raise WrittenRecordsError(...)   # fail loud, never silently skip (FINDING 2 discipline)

    action = item.get("action")
    hs_object_id = item.get("hs_object_id") or None
    object_type = item.get("object_type") or "contacts"
    reason = item.get("reason")

    if action in WRITE_ACTIONS:
        if hs_object_id:
            outcome = WRITTEN
        elif action == "create":
            outcome = CREATED_ID_UNKNOWN
        else:
            outcome = NOT_WRITTEN
    else:
        outcome = NOT_WRITTEN

    entry = {
        "object_type": object_type, "action": action, "hs_object_id": hs_object_id,
        "outcome": outcome, "reason": reason,
    }
    for key, value in entry.items():
        if _looks_forbidden(key) or (value is not None and _looks_forbidden(value)):
            raise WrittenRecordsError(...)
    return entry
```

**Verified gap this session: `row_id` is available on the same `item` dict and is
discarded.** `item.get("row_id")` is present per `scripts/build_cloud_workflows.py:1705,3439,4982`
but never read here. AFTER-01's join needs it — add `entry["row_id"] = item.get("row_id")`
in the SAME edit that widens the outcome vocabulary (Common Pitfall 2 in RESEARCH.md).
Old on-disk entries will simply lack the key — degrade gracefully on read, per the module's
own established "missing/malformed → empty, never partial trust" rule already implemented
in `_entries_from_document` (below).

**Degrade-gracefully reader idiom (copy for any new reader of this store):**
```python
# Source: operator-claude-plugin/scripts/written_records.py (verified this session)
def _entries_from_document(document):
    if document is None:
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, list):
        return None
    if any(not isinstance(entry, dict) for entry in entries):
        return None
    return entries
```

**Verified action vocabulary — 10 values, not 9 (grep output this session):**
```
create enrich needs_match_review proposed recompute_refused
research_failed review skip update write_blocked
```
`enrich` has no explicit row in D-57-03's table but IS in `WRITE_ACTIONS` — must map to
`written` (with an id) exactly as `update`/`create` do, not fall through to a default.

**Per-run scoping + glob-and-union reader (the durable-artifact idiom, D-59-09 — load-bearing for this phase's emphasis point 1):**
```python
# Source: operator-claude-plugin/scripts/written_records.py (module docstring + written_records_path)
def written_records_path(run_id) -> Path:
    """... resolved fresh on every call ... D-59-09: keyed by run_id, so two runs never
    resolve to the same path."""
    return durable_paths.resolve_state_path().parent / f"written_records-{run_id}.json"
```
Every consumer globs `written_records*.json` and unions the matches (`load()`) rather than
opening one fixed path — D-59-09's cost is paid on the reader side. Any new store this
phase adds (the remainder queue) that is per-run must follow the identical `<name>-<run_id>.json`
+ glob-union shape, never a single shared file (two real concurrent writers — an operator's
live session and `scheduled_arm.py`'s cron poller — is the reason this rule exists).

---

### `operator-claude-plugin/scripts/report_enrichment.py` (service, reconcile second vocabulary reader)

**Analog:** `written_records.classify_item` (the vocabulary of record this module must agree with).

**Verified this session — this module's OWN vocabulary, independently built, already 6 of 10 values wide and using DIFFERENT words than D-57-03's table for the same actions:**
```python
# Source: operator-claude-plugin/scripts/report_enrichment.py:38-49
_ACTION_TO_OUTCOME = {
    "create": "created",
    "enrich": "enriched",
    "write_blocked": "blocked",
    "skip": "skipped",
    "needs_match_review": "held",
    "proposed": "previewed",
}
SUCCESS_OUTCOMES = {"created", "enriched"}
```
Falls through to `.get(action, "unknown")` for `update`, `review`, `research_failed`,
`recompute_refused` — 4 of 10 backend actions silently render as `"unknown"`, uncovered by
any test (verified: no test in `test_report_enrichment.py` pins these 4 keys). This is a
SECOND, independently-drifted copy of the same fact `written_records.py` encodes — it reads
from a different transport (executions-API `runData`, not the sync dispatch response) so it
cannot simply import `written_records`'s constants, but its word choices (`"blocked"` vs
D-57-03's `"gated"`) must be decided to either match or be explicitly reconciled — **do not
widen one vocabulary and leave the other's words diverging silently.**

**Grep confirms this repo has no OTHER third reader** — `_ACTION_TO_OUTCOME` and
`written_records.classify_item` are the only two places an `action` string is mapped to an
operator-facing word (grep run this session: `ACTION_TO_OUTCOME|WRITE_ACTIONS` across
`operator-claude-plugin/scripts/*.py` and `operator-claude-plugin/skills/*/SKILL.md`
returns exactly these two definitions plus their call sites and one narrative mention in
`enrich-records/SKILL.md:367`). **This satisfies the phase's "one implementation of a rule"
check for the action→outcome mapping specifically: there are exactly TWO, both already
known and both named in RESEARCH.md — the planner does not need to search further for a
third.**

---

### `operator-claude-plugin/scripts/remainder_queue.py` (NEW, model / durable store)

**Storage-idiom analog (reuse verbatim):** `operator-claude-plugin/scripts/durable_paths.py::_atomic_write_0600`
```python
# Source: operator-claude-plugin/scripts/durable_paths.py:57-77
def _atomic_write_0600(path: Path, content: str) -> None:
    """... the final path is either absent, or present, complete, and 0600.
    Pattern: tempfile in the target's OWN directory, chmod 0600, fsync, os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        os.chmod(tmp_name, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    ...
```
Every one of the five existing artifact stores (`artifact_store`, `run_manifest`,
`written_records`, `held_queue`, `run_state`) already uses this — a sixth store should too.

**Entry-shape analog: `chunking.failed_batch()`'s output (above), NOT `held_queue.py`'s
entry schema.** `held_queue.py`'s entries require a `hold_code` from the CLOSED
`confidence.ALL_HOLD_CODES` set and a `resume_fingerprint` computed from a
`preingest.Outcome`'s `.match_tier`/`.candidate_count` — a ceiling-breach row was never
assessed by `confidence.assess()` and has neither. Reuse `held_queue.py`'s file-write idiom
and forbidden-name-scan, never its entry schema.

**Forbidden-name scan — reimplement fresh per module, do not import (deliberate anti-DRY, established convention):**
Every one of `written_records.py`, `held_queue.py`, `run_state.py` carries its OWN copy of
`_FORBIDDEN_NAME_MARKERS`. A new `remainder_queue.py` must do the same — copy the tuple
verbatim, do not `from written_records import _FORBIDDEN_NAME_MARKERS`.

**D-57-05 hard constraint to encode as a test, not just a comment:** the remainder queue
holds WORK specs only (record ids/domains, `failed_batch()`'s shape) — never a grant object
or authority token. A resumed run against a remainder entry, with no grant open, must refuse
the same way any ungranted send does today.

---

### AFTER-01 report join (new function/script)

**Analog:** `operator-claude-plugin/scripts/report_enrichment.py::build_sync_report` (existing
join-and-render shape — read it in full before writing a second one).

**Join keys, verified this session:**
- `written_records` — keyed by `run_id` (file name), entries now carry `row_id` (after the
  widening above).
- `run_state.read_progress` / `run_manifest` — keyed by `run_id` + `row_id`.
- `held_queue` — global file, entries carry their own reason/hold_code, not scoped to one run_id (need a run_id tag on entry or a timestamp-window join — check `held_queue.py`'s entry schema before assuming a direct key).
- the new remainder queue — per-run, same `<name>-<run_id>.json` glob-union shape as `written_records`.

**Test must prove the row_id gap is actually closed, not merely that the function runs:**
a fixture entry with `hs_object_id: None` (a held/blocked row) must still appear in the
joined report keyed by `row_id` — see RESEARCH.md's AFTER-01 test-map row.

---

### Disarmed live-probe (G-4 ZoomInfo re-probe)

**Analog:** `scripts/prove_async_recovery.py` (also `scripts/prove_scale_up_runtime.py` — same family).

**Template shape to copy (per RESEARCH.md's Don't-Hand-Roll table):**
- A dedicated `ALLOW_<NAME>_PROOF` env-var gate, read EXACTLY as `"true"` (never truthy-coerced).
- An instance-URL guard mirroring `deploy_n8n_workflows.py::_instance_ok()`.
- For this probe specifically: no `mode: propose` gate is needed at all — the balance check
  (`Status Credit Request` → `ZoomInfo Usage`) is read-only and already
  `onError: continueRegularOutput` per its own docstring. Simpler than the async/scale-up
  templates: just the env-gate + instance guard + a GET, no write-safety scaffolding needed.

---

## Shared Patterns

### Refuse-with-arithmetic (RUN-05)
**Source:** `operator-claude-plugin/scripts/n8n_cadence.py:452-491` (`check_budget_floor`)
**Apply to:** `write_grant.py`'s new pre-flight refusal.
Branch order: missing/invalid config refuses first (never overridable) → over-budget
refuses unless `override=True` → return arithmetic either way.

### Atomic durable write, 0600, per-run scoping
**Source:** `operator-claude-plugin/scripts/durable_paths.py:57-77` (`_atomic_write_0600`),
`written_records.py::written_records_path` (per-run naming + glob-union reading, D-59-09)
**Apply to:** any new persisted artifact this phase adds (remainder queue).

### Forbidden-name scan, reimplemented per module
**Source:** `written_records.py::_FORBIDDEN_NAME_MARKERS` / `_looks_forbidden`
**Apply to:** every new artifact writer — copy the tuple fresh, never import it.

### Fail loud on shape mismatch, never silently skip
**Source:** `written_records.classify_item`'s non-dict-item `WrittenRecordsError` (FINDING 2 discipline, commit `9e603d6`)
**Apply to:** any new classifier/reader this phase adds.

### Deliberate stop ≠ recovered-from failure — give it its own field
**Source:** `chunking.py:134-148` (`written_records_failures`'s own precedent, D-59-10)
**Apply to:** the mid-run ceiling-breach field on `DispatchOutcome` — must not be folded into `failed_chunks`.

## No Analog Found

None — RESEARCH.md's own "Don't Hand-Roll" table already maps every piece of new machinery
this phase needs to an existing analog. This phase is characterized (by its own research) as
"almost entirely wiring two ends of an existing, tested consumer to a producer that has never
been written" — there is no greenfield surface here.

## One-Implementation-of-a-Rule Check (requested by orchestrator)

Grepped this session for every place in the repo that maps a backend `action` value to an
outcome/label. Exactly TWO surfaces exist, both already identified above and in RESEARCH.md:

1. `operator-claude-plugin/scripts/written_records.py::classify_item` / `WRITE_ACTIONS` — the
   artifact-of-record vocabulary (3 outcomes today, widening to 6 per D-57-03).
2. `operator-claude-plugin/scripts/report_enrichment.py::_ACTION_TO_OUTCOME` — a second,
   independently-built vocabulary (6 of 10 actions mapped, different words: `"blocked"` not
   `"gated"`, `"held"` not `"held"` — coincidentally matches on one word, diverges on others).

No third surface found (grep scope: `operator-claude-plugin/scripts/*.py`,
`operator-claude-plugin/skills/*/SKILL.md`, `n8n/code/*.js`, `scripts/build_cloud_workflows.py`
for any local `action ->` mapping table besides the one that PRODUCES the action value in the
backend itself, which is out of scope — this check is about CLIENT-side readers only, since
the backend is the single producer by construction). The planner must decide explicitly
whether reconciling #2 is in-scope for this phase (RESEARCH.md's Pitfall 3 flags it as a live
discrepancy AFTER-03 should account for) or an explicitly named residual — but must not leave
it unmentioned, per CONTEXT.md's "one implementation of a rule" pattern and the cost §13.0.1
records for silently letting a second copy drift.

## Test Idioms (requested by orchestrator)

- **`stub_module_transport_factory`** — the dispatch harness used to drive a REAL
  `chunking.dispatch_plan()` call rather than a hand-built `DispatchOutcome`. Required for the
  D-57-01 mid-run breach integration test (RESEARCH.md's test map row) and for proving
  `record_send_outcome` is reached from a real dispatch path (Pitfall 1).
- **`_patch_durable_dir`** — the `tmp_path`-based fixture idiom in `test_written_records.py`
  for redirecting durable writes during a test; reuse for AFTER-01's join test and any new
  `remainder_queue.py` test.
- **`RUN_LIVE_PARITY`** ambient-credential guard — `tests/conftest.py` (root, 67 lines,
  Phase 59-02) — gates any test that would hit a real credential/instance; the G-4 ZoomInfo
  live re-probe must respect this guard, not invent a second one.
- **`test_a_revocation_midway_does_not_stop_a_running_dispatch`** (`test_write_grant.py`) — the
  existing 3-chunk-dispatch idiom to mirror for the ceiling-breach integration test: a scripted
  transport that lets the ceiling check detect a breach after chunk N, asserting the loop stops
  early and `record_send_outcome` is actually called (not just accepting the shape).
- **`no_network` / `no_durable_writes`** fixtures in `operator-claude-plugin/tests/conftest.py`
  (639 lines) — the default-safe fixtures every plugin test already runs under; any new test
  touching the remainder queue or the ceiling refusal must not silently bypass these.

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/tests/`,
`operator-claude-plugin/skills/*/SKILL.md`, `scripts/build_cloud_workflows.py`, `n8n/code/*.js`
(grep only, for the vocabulary-surface check).
**Files scanned/read this session:** `write_grant.py` (targeted, RESEARCH.md's own excerpts
reused), `written_records.py` (read in full, 1-220), `report_enrichment.py` (targeted, 30-60),
`durable_paths.py` (targeted, 1-77), `chunking.py` (targeted, 494-517 + RESEARCH.md's 373-444
excerpt), plus two greps for the action→outcome vocabulary surfaces.
**Pattern extraction date:** 2026-08-31
**Note:** RESEARCH.md for this phase already contains verified, line-cited code excerpts for
nearly every pattern above (Pattern 1-4, Code Examples, Don't Hand-Roll table). This PATTERNS.md
reorganizes those by target file for the planner and adds: the `report_enrichment.py` full
excerpt (not fully quoted in RESEARCH.md), the `durable_paths._atomic_write_0600` full body,
`chunking.failed_batch()`'s full body, `written_records.py`'s full `classify_item` +
`_entries_from_document`, and the one-implementation-of-a-rule grep confirmation.
