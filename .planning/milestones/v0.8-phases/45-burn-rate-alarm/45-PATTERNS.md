# Phase 45: Burn-Rate Alarm - Pattern Map

**Mapped:** 2026-08-10
**Files analyzed:** 7 (2 new/extended conditions, 1 windowed-read change, 1 cadence floor,
1 config plumbing, 1 example config, 1 drift test)
**Analogs found:** 7 / 7 — every touch point has a direct in-repo analog; no RESEARCH.md
needed.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/sweep_conditions.py` (new `check_burn_rate` fn + `BURN_RATE`/`BURN_RATE_NOT_CONFIGURED` condition constants) | pure classifier (condition function) | transform (already-fetched data → fired-condition dicts) | `check_review_backlog` / `check_quota_and_credentials` in same file | exact |
| `operator-claude-plugin/scripts/sweep_read.py` (`gather` widened to pass a time-windowed executions read + allowance config through) | gather/I-O layer | request-response (GET) | existing `gather()` — same file, same function, extend not duplicate | exact |
| `operator-claude-plugin/scripts/n8n_read.py` (new windowed `recent_executions`-family read replacing/augmenting `EXECUTIONS_PAGE_LIMIT = 100`) | data-access utility | request-response (GET, paginated) | `recent_executions()` (same file, line 214) — this file already owns the fixed-page read being replaced | exact |
| `operator-claude-plugin/scripts/n8n_cadence.py` (`parse_cadence`/`set_cadence` budget-floor check + override phrase) | validation/guard function | event-driven (operator phrase → refuse-or-mutate) | `CadenceRefused` raise sites already in this file (`_set_interval_in_place`, `set_cadence`) | exact |
| `operator-claude-plugin/scripts/config_gate.py` (no new capability row per D-05 — only doc/comment touch, if any) | config validator | request-response | `CAPABILITY_KEYS` / `_CAPABILITY_DESCRIPTIONS` dicts, same file | exact (deliberately NOT extended — see Shared Patterns) |
| `operator-claude-plugin/config/operator.local.example.json` (new `n8n_monthly_execution_allowance` key + `_..._note`) | config | config | existing keys in same file, e.g. `stuck_execution_minutes`, `max_records_per_chunk` | exact |
| `tests/test_execution_budget_drift.py` (new — drift test D-04) | test | batch (static file comparison) | `tests/test_execution_budget.py` (same repo, same budget file, direct-index pattern) | exact |

## Pattern Assignments

### `operator-claude-plugin/scripts/sweep_conditions.py` — `check_burn_rate` (new condition)

**Analog:** `check_review_backlog` (lines 256-279) for the "threshold + configurable
parameter + reason string" shape, and `check_quota_and_credentials`/`classify_quota`
(lines 132-230) for the "explicit not-a-boolean outcome, never silently false" shape used
for D-05's not-configured state.

**Module-level constant pattern** (mirror lines 57-68, `DEFAULT_QUOTA_FLOOR` /
`DEFAULT_REVIEW_BACKLOG_THRESHOLD`):
```python
# Fire when rate x 30d > allowance x threshold. 1.0 default: the idle floor is ~95/month
# (~4% of a 2,500/month plan), so any real anomaly clears this by an order of magnitude —
# the key exists for tightening later, not because 1.0 is marginal (D-06).
DEFAULT_BURN_RATE_THRESHOLD = 1.0

BURN_RATE = "burn_rate_alarm"
BURN_RATE_NOT_CONFIGURED = "burn_rate_not_configured"
```

**Condition function shape to copy** (mirror `check_review_backlog`, lines 256-279 —
threshold comparison, unreadable input skips rather than defaults to zero, reason string
states the numbers):
```python
def check_review_backlog(counts, threshold=DEFAULT_REVIEW_BACKLOG_THRESHOLD):
    counts = counts or {}
    companies = counts.get("companies_awaiting_review")
    contacts = counts.get("contacts_awaiting_review")
    if companies is None or contacts is None:
        return []
    total = companies + contacts
    if total <= threshold:
        return []
    return [{
        "condition": REVIEW_BACKLOG,
        "reason": (
            f"{total} records are waiting for human review (companies {companies}, "
            f"contacts {contacts}) — past the {threshold}-record point where the queue "
            f"counts as backed up"),
    }]
```
`check_burn_rate` should follow this exactly: take the windowed execution count + observed
span (from `sweep_read.gather`'s widened `executions` dict) and the allowance (from
config, per D-04), compute `rate x 30d` vs `allowance x threshold`, and return `[]` when
under. D-05's condition-level "not configured" notice is the `"not_configured"` branch of
`classify_quota` (lines 132-162) copied in shape: a distinct fired condition
(`BURN_RATE_NOT_CONFIGURED`) rather than a swallowed no-op, so the sweep's other
conditions still run per D-05 (config_gate's `sweep` row is NOT touched).

**Reason-string voice** (mirror lines 96-101, 216-219, 275-278 — numbers first, named
threshold, no jargon):
```python
"reason": (
    f"a run of {summary.get('workflow_name') or 'an unnamed workflow'} "
    f"has been going for about "
    f"{round(summary.get('running_for_minutes') or 0)} minutes — past "
    f"the {summary.get('stuck_threshold_minutes')}-minute point where a "
    f"run counts as wedged"),
```
Apply the same "N per hour, spanning M (labelled if truncated by pruning), projecting to
P over 30 days against an allowance of A" phrasing D-01/D-02's notice text calls for.

**Wire-in point** (mirror `evaluate()`, lines 391-416 — gate on `executions.get("available")`
same as `check_stuck`/`check_failed_run`):
```python
if executions.get("available"):
    summaries = executions.get("summaries")
    fired.extend(check_stuck(summaries))
    fired.extend(check_failed_run(summaries))
    fired.extend(check_stuck_armed(gathered.get("workflows"), summaries))
    # burn-rate condition goes here, reading gathered["executions"] windowed span +
    # gathered.get("execution_budget") (or wherever D-04's allowance lands) — config-
    # missing fires BURN_RATE_NOT_CONFIGURED, not a silent skip (D-05).
```

---

### `operator-claude-plugin/scripts/sweep_read.py` — windowed executions gather

**Analog:** `gather()` itself (lines 52-113) — same function, no new module. The
maintenance-execution-id extraction loop (lines 77-89) already walks `raw` (the executions
page) computing derived state per item; the time-window filter is the same shape of walk,
just filtering by `startedAt` instead of matching workflow name.

**Contract to preserve** (module docstring, lines 17-19): `available: False` still means
"could not tell", never "nothing there" — a windowed read that finds zero executions
inside the window is `available: True, summaries: []`, distinct from the page failing to
fetch at all.

**Reads must funnel through the same one I/O module** — no new `import requests` site
elsewhere; the time-windowed read is still issued from `n8n_read` (see below) and consumed
here, keeping `sweep_read.py` "the ONLY module in the sweep graph that performs I/O"
(docstring line 3) and `test_sweep_read_only.py`'s import-graph guard intact.

---

### `operator-claude-plugin/scripts/n8n_read.py` — time-windowed executions read (D-08)

**Analog:** `recent_executions()` (lines 214-227) — the exact function whose fixed
`EXECUTIONS_PAGE_LIMIT` this phase replaces/augments.

**Current fixed-page shape to extend, not throw away** (lines 44-47, 214-227):
```python
# One bounded page. n8n's documented max is 250; this is a status read on operator
# demand, not a poll loop. A workflow missing from the page gets its own filtered read
# rather than being reported never-run from an absence in it.
EXECUTIONS_PAGE_LIMIT = 100

def recent_executions(config: dict, transport=requests.get, limit: int = EXECUTIONS_PAGE_LIMIT):
    """One bounded page of recent executions across every workflow, newest first.

    `None` is unreadable, `[]` is "read fine, nothing there". This page is a shortcut for
    the common case, never a history: a workflow absent from it is not thereby never-run,
    and the caller owes it a filtered read of its own.
    """
    body = _get_json(config, f"{_base_url(config)}/api/v1/executions",
                     {"limit": limit}, transport)
    if body is None:
        return None
    data = body.get("data")
    return data if isinstance(data, list) else None
```
D-08's fix: n8n's executions API has no server-side time filter parameter usable here —
the windowing has to happen client-side by walking pages (or the existing single page) and
filtering on `startedAt`/`stoppedAt` against `now - window`, stopping once items fall
outside the window (the list is newest-first, confirmed by the maintenance-lookup comment
at sweep_read.py:84-85). Keep the `None`-unreadable / `[]`-empty contract; add a
`window_hours` (or similar) parameter alongside `limit`, defaulting sanely, following the
`stuck_threshold_minutes()` pattern (lines 107-115) for a configurable-with-documented-
default value:
```python
def stuck_threshold_minutes(config: dict):
    """Minutes a run may be in flight before it reads as wedged. Configuration first,
    documented default when absent, unparseable or non-positive — a status read must not
    fail because a config value was typed wrong."""
    try:
        value = float((config or {}).get("stuck_execution_minutes"))
    except (TypeError, ValueError):
        return DEFAULT_STUCK_MINUTES
    return value if value > 0 else DEFAULT_STUCK_MINUTES
```
`elapsed_minutes()` (lines 118-133) is the reusable age-computation the window filter
should call, not reimplement.

**Also fixes the "unnamed workflow" secondary** (D-08's folded finding): `workflowId` →
name is already resolved for the maintenance lookup in `sweep_read.gather` (lines 80-82,
`workflow_data.get("name")`) — the same `list_workflows` result already fetched at
`sweep_read.py:101` should backfill every summary's `workflow_name`, not just the
maintenance one, removing the `"an unnamed workflow"` fallback text at
`sweep_conditions.py:97,111,250` where a name is actually resolvable.

---

### `operator-claude-plugin/scripts/n8n_cadence.py` — budget floor (D-09/D-10)

**Analog:** `_set_interval_in_place` / `set_cadence`'s existing `CadenceRefused` sites
(lines 341-359, 439-482) — the floor check is one more refusal gate in the same style,
landing inside `parse_cadence`/`set_cadence` per the canonical refs, before any PUT is
composed.

**Refusal voice to copy exactly** (module docstring lines 16-18; live example at lines
267-270):
```python
raise CadenceRefused(
    f"I could not confidently work out what {str(phrase).strip()!r} means as a "
    f"schedule, and I would rather ask than guess — a misread schedule changes how "
    f"often the backend spends money.")
```
Numbers-first refusal style (this IS the D-09 register the phase context quotes — "every
15 minutes is 2,880 fires a month against a 2,500/month plan" is literally
`tests/test_execution_budget.py`'s `TICKS_PER_MONTH` arithmetic surfaced as prose). Reuse
`TICKS_PER_MONTH`-style conversion (test file lines 25-31) inside `n8n_cadence.py` (or
import if hoisted) — do not recompute the 30-day-month arithmetic a third time.

**`CadenceRefused` shape to reuse unmodified** (lines 55-62):
```python
class CadenceRefused(Exception):
    """A phrase that could not be interpreted confidently. Carries examples, because a
    refusal without a way forward is just a dead end."""
    def __init__(self, reason, examples=None):
        self.reason = reason
        self.examples = list(examples) if examples else list(_EXAMPLES[:3])
        super().__init__(f"{reason} Try one of: {'; '.join(self.examples)}.")
```
D-10's override is a **single-shot parameter threaded through the one call**, not a new
exception subclass or shared helper (explicit instruction: "must not generalise the
pattern — no shared override helper other gates could adopt"). Land it as a plain
parameter on `set_cadence`/`parse_cadence` (e.g. `override_budget_floor: bool = False`)
checked only at that call site, restating the consequence in the same refusal-adjacent
prose when the override is taken, mirroring how `set_cadence` already restates the *prior*
cadence in plain language (module docstring line 440: "Re-time ONE scheduled job, with the
prior cadence quoted back in plain language").

**Where the floor computation slots in** — before `_set_interval_in_place` mutates
anything (lines 341-345 is the existing pre-mutation guard shape):
```python
def _set_interval_in_place(workflow, node_name, interval):
    if not isinstance(interval, list) or not interval:
        raise CadenceRefused("a schedule needs at least one interval entry.")
    for entry in interval:
        if not isinstance(entry, dict) or entry.get("field") not in SUPPORTED_FIELDS:
            raise CadenceRefused(...)
```
D-09's "sums across all five triggers" requirement means the floor check needs the
workflow's OTHER schedule triggers' current intervals too (already readable via
`schedule_trigger_nodes` + `read_cadence`, lines 65-94) — not just the one being changed —
summed against `config/execution_budget.yaml`'s allowance (read the same way D-04 wires it
into the sweep, not a second parallel config path).

---

### `operator-claude-plugin/scripts/config_gate.py` — deliberately NOT extended

**Analog:** `CAPABILITY_KEYS["sweep"]` (line 67) stays exactly as committed — D-05 is
explicit that the allowance key must NOT join this row: "Adding the key to `config_gate`'s
`sweep` capability row was rejected: a stuck lock must not go unreported because a budget
key is absent." No code change expected here beyond possibly a comment if the planner
wants to document the rejection inline (optional, not required by any decision).

---

### `operator-claude-plugin/config/operator.local.example.json` — new allowance key

**Analog:** any of the existing scalar keys with a `_..._note` sibling, e.g.
`stuck_execution_minutes` (bare value, no note — for a simple threshold) or
`max_records_per_chunk` + `_max_records_per_chunk_note` (value + provenance note, for a
value with a measured/derived rationale):
```json
"stuck_execution_minutes": 15,
```
```json
"max_records_per_chunk": 2,
"_max_records_per_chunk_note": "CONFIRMED 2026-08-03 by live probe B4: ...",
```
`n8n_monthly_execution_allowance` should follow the noted-value shape since D-04 gives it
a specific provenance (must equal `config/execution_budget.yaml`'s
`monthly_execution_allowance`, currently `2500`) — the note text should say plainly that
this value must match that file and why (the drift test, next section, enforces it
mechanically; the note is what a human editing this file by hand sees).

---

### `tests/test_execution_budget_drift.py` — new drift test (D-04)

**Analog:** `tests/test_execution_budget.py` in full (already read above) — same repo,
same budget file, same "read the committed artifact directly, never import a computed
constant" philosophy stated in its own header comment:
```python
# Everything is re-derived from the committed artifacts (n8n/wf_*_cloud.json) plus
# config/execution_budget.yaml — never imported from the builder's computed constants,
# mirroring tests/test_field_policy_conformance.py: a test that imports the number the
# builder baked cannot see the builder and the config disagreeing.
```
**Direct-index-on-missing-key pattern to copy** (lines 39-42):
```python
budget = yaml.safe_load((ROOT / "config" / "execution_budget.yaml").read_text())
# Direct indexing on purpose — a missing config key must fail, not default (T-44-07).
allowance = budget["monthly_execution_allowance"]
```
The new drift test does the mirror-image comparison: load
`operator-claude-plugin/config/operator.local.example.json` (`json.loads`, not `yaml`),
direct-index `n8n_monthly_execution_allowance`, direct-index
`config/execution_budget.yaml`'s `monthly_execution_allowance`, assert equality by value
(not string vs int — watch for JSON int vs YAML int type match). Keep it a single
assertion test, same file layout style (module docstring stating the incident/rationale,
`ROOT = Path(__file__).resolve().parent.parent`).

---

## Shared Patterns

### Pure-function / no-I/O boundary for new conditions
**Source:** `sweep_conditions.py` module docstring, lines 1-4: "Pure functions over
already-fetched data (29-03). No I/O, no clock, no client — the import-graph guard depends
on this module staying that way."
**Apply to:** `check_burn_rate` — must not call `n8n_read`/`requests` itself; the windowed
executions data and the allowance value both arrive pre-fetched via `sweep_read.gather`'s
return dict, same as every existing condition function.

### Read-only sweep enforcement
**Source:** `sweep_read.py` docstring line 3 + `tests/test_sweep_read_only.py`
(referenced, not re-read — canonical_refs names it explicitly as the test that must stay
green and that binds the sweep to zero new write paths).
**Apply to:** any new gather code in `sweep_read.py` for the windowed read — must go
through `n8n_read`'s existing GET-only surface, no new transport import.

### Refusal/notice voice: numbers first, named threshold, way forward, who-can-fix
**Source:** `n8n_cadence.CadenceRefused` (lines 55-62, 267-270) and
`sweep_conditions`'s reason strings (lines 96-101, 216-219, 275-278) and
`sweep_notify._who_line` (lines 42-43).
**Apply to:** the burn-rate condition's `reason` string, the cadence floor's refusal, and
D-05's not-configured notice — all three must name the exact key/number, never just say
"budget exceeded" or "not configured" without specifics.

### Configurable-value-with-documented-default parameter shape
**Source:** `DEFAULT_QUOTA_FLOOR`, `DEFAULT_REVIEW_BACKLOG_THRESHOLD`
(`sweep_conditions.py` lines 57-68), `DEFAULT_STUCK_MINUTES`/`stuck_threshold_minutes()`
(`n8n_read.py` lines 39-42, 107-115).
**Apply to:** `DEFAULT_BURN_RATE_THRESHOLD` (D-06) — module-level constant with a comment
justifying the default, read from config with a safe fallback on missing/unparseable
value, never raising out of a status/condition read.

## No Analog Found

None — every file this phase touches already has a directly analogous function or test in
the same module/repo (this phase is explicitly framed as extending existing modules, not
introducing new ones).

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/` (sweep_conditions.py,
sweep_read.py, n8n_read.py, n8n_cadence.py, config_gate.py, sweep_entry.py,
sweep_notify.py), `operator-claude-plugin/config/operator.local.example.json`,
`config/execution_budget.yaml`, `tests/test_execution_budget.py`.
**Files scanned:** 9 read in full or targeted range; no file exceeded 500 lines so no
grep-first strategy was needed.
**Pattern extraction date:** 2026-08-10
