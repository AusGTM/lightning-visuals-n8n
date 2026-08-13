# Phase 49: Re-score Strategy & Reporting - Pattern Map

**Mapped:** 2026-08-13
**Files analyzed:** 8 (2 edited, 6 new)
**Analogs found:** 8 / 8

This phase is reuse-and-extend, not new-technology. RESEARCH.md already quoted every
load-bearing excerpt verbatim with line numbers — this file re-organizes those excerpts by
target file so the planner can assign them directly to plan tasks.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/backfill_seed_company_scores.py` (EDIT: ceiling + new gate fn) | service/driver | batch CRUD | itself (existing file, in-place edit) | exact |
| `scripts/rescore_population.py` (NEW thin wrapper, `--plan` mode) | service/driver (CLI) | batch CRUD + dry-run report | `scripts/remediate_veto_companies.py` (`estimate_cost`, arm gate, CLI shape) | exact |
| `tests/test_backfill_seed_company_scores.py` (EXTEND: exact-set gate coverage) | test | unit/offline | existing file's own current tests (same file) | exact |
| `tests/test_rubric_change_guard.py` (NEW, D-09 guard) | test | unit/offline | `tests/test_companies_factory_frozen.py` (byte/digest-pin idiom) | exact |
| `tests/test_<rescore_driver>.py` (NEW: `--plan` mode, report builder) | test | unit/offline, stubbed fetch | `tests/test_scoring_parity.py` (fixture-based HubSpot-shaped assertions) | role-match |
| `docs/OPERATOR-RESCORE.md` (NEW runbook) | doc | operator procedure | `docs/OPERATOR-VETO-REFRESH.md` | exact |
| `.planning/phases/49-.../49-RESCORE-REPORT.md` (NEW report) | doc | reporting/transform | `scripts/simulate_rubric_weights.py` (`render_markdown`) + `47-COST-ESTIMATE.md`/`48-RUN-REPORT.md` shape | exact |
| Report-builder module (three-point P1/P2/P3 payload + renderer) | service (report) | batch read + transform | `scripts/simulate_rubric_weights.py` (`build_simulation`, `render_markdown`) | role-match |

## Pattern Assignments

### `scripts/backfill_seed_company_scores.py` (service/driver, batch CRUD) — EDIT

**Analog:** itself. Two changes only, per D-03; everything else (`compute_components`,
`build_updates`, `_chunked`, `batch_update_companies` call) is unchanged reuse.

**Constants to edit** (lines 84-87):
```python
DEFAULT_MAX_RECORDS = 10
HARD_CEILING_RECORDS = 25   # -> 100
BATCH_CHUNK_SIZE = 100
```

**Current count-cap gate to keep AND add alongside** (lines 147-151):
```python
def enforce_sample_cap(sample_ids: list) -> bool:
    """True if the sample is at or under the resolved cap. The script refuses (exits
    non-zero) rather than silently truncating -- D-09's scope boundary is enforced here,
    not trusted to the caller."""
    return len(sample_ids) <= _resolved_max_records()
```

**New function to add (does not exist yet)** — same file, same style, called in addition to
(never instead of) `enforce_sample_cap`:
```python
def enforce_exact_population(sample_ids: list, live_ids: list) -> bool:
    """True only if sample_ids == the live-derived HAS_PROPERTY(lv_icp_fit_score) set,
    exactly. A count cap of 100 permits any <=100-record subset; this refuses everything
    except the intended population. Refuse (return False), never truncate — same contract
    as enforce_sample_cap."""
    return set(sample_ids) == set(live_ids)
```

**Two-key arm gate to reuse unchanged** (lines 162-165):
```python
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SCORE_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow
```

**`compute_components()` — copy unchanged, zero edits** (lines 93-117):
```python
def compute_components(props: dict) -> dict:
    canonical = {k: props.get(k) for k in CANONICAL_INPUT_PROPS if props.get(k) not in (None, "")}
    record = HubSpotRecord(object_type="companies", id="0", properties=canonical)
    result = compute_icp_score(record, {})
    by_signal = {c["signal"]: c["points"] for c in result.breakdown["components"]}
    gambling_points = 0
    for deduction in result.breakdown["graduated_deductions"]:
        if deduction["signal"] == "gambling_operator":
            gambling_points = deduction["points"]
    return {
        "org_type_score": by_signal.get("org_type", 0),
        "geography_score": by_signal.get("geography", 0),
        "annual_revenue_score": by_signal.get("revenue_band", 0),
        "produces_content_score": by_signal.get("produces_content", 0),
        "gambling_score": gambling_points,
    }
```

`CANONICAL_INPUT_PROPS` (lines 61-67) and `COMPONENT_PROPS` (lines 72-78) — the whitelist any
write payload must be exactly disjoint-limited to, mirroring `remediate_veto_companies.py`'s
`FORBIDDEN_PROPS.isdisjoint(props)` assertion (line 360 of that file):
```python
CANONICAL_INPUT_PROPS = [
    "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator",
]
COMPONENT_PROPS = [
    "org_type_score", "geography_score", "annual_revenue_score",
    "produces_content_score", "gambling_score",
]
```

---

### `scripts/rescore_population.py` (NEW thin wrapper — `--plan` mode, exact-set gate wiring)

**Analog:** `scripts/remediate_veto_companies.py` for CLI/arm/estimate shape;
`scripts/backfill_seed_company_scores.py` for the write core (imported, not forked).

**Cost/plan-mode shape to mirror** (`remediate_veto_companies.py:650-671`):
```python
def estimate_cost(ids) -> dict:
    n_records = len(ids)
    return {
        "web_research_calls": n_records,
        "n8n_executions": n_records,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "anthropic_estimate_usd": round(n_records * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
    }
```
For this driver's weight branch, the real numbers are `n8n_executions: 0`,
`anthropic_calls: 0`, `provider_credits: 0`, `hubspot_batch_calls: 1` (66 ≤
`BATCH_CHUNK_SIZE=100`) — confirmed by `batch_update_companies`'s signature below never calling
n8n or Anthropic.

**Population definition — reuse verbatim, do not redefine** (`run_scoring_parity.py:149-165`,
byte-identical in intent to `simulate_rubric_weights.py::_select_row_ids`):
```python
def _select_sample_ids() -> list:
    env_ids = os.getenv("PARITY_SAMPLE_IDS", "")
    if env_ids.strip():
        return [i.strip() for i in env_ids.split(",") if i.strip()]
    from src.hubspot_client import search_records
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
        ["lv_icp_fit_score"],
        limit=100,
    )
    return [r["id"] for r in result.get("results", [])]
```

**Batch write primitive — call, do not reimplement** (`src/hubspot_client.py:88-116`):
```python
def batch_update_companies(updates: list[dict], dry_run=True):
    if len(updates) > 100:
        raise ValueError(
            f"batch_update_companies received {len(updates)} updates; HubSpot's batch "
            "update endpoint accepts at most 100 per call. Chunk the caller's list "
            "instead of sending an oversized batch."
        )
    payload = {"inputs": updates}
    if dry_run or not updates:
        print(json.dumps({...}, indent=2, default=str))
        return {"dry_run": True, "payload": payload}
    url = f"{BASE_URL}/crm/v3/objects/companies/batch/update"
    r = requests.post(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
```

**Canary + settle-poll pattern to reuse (D-04)** — `backfill_seed_company_scores.py`'s own
`_settle()` (lines ~252-271, cited by RESEARCH.md's "Don't Hand-Roll" table): poll until two
consecutive reads of `lv_icp_fit_score`/`lv_icp_tier` match, rather than a fixed `time.sleep`.
Use a generous timeout (300s, matching `post_webhook_event`'s Trap-4-corrected default) for the
66-record batch settle, not the single-record 11s figure.

**`.env` load wrapper — copy verbatim for every live invocation** (docstring pattern,
`backfill_seed_company_scores.py:33-38`):
```bash
ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c \
    "from dotenv import load_dotenv; load_dotenv(); import runpy; \
     runpy.run_path('scripts/rescore_population.py', run_name='__main__')"
```

**Do NOT copy into W1:** Phase 48's "both arming surfaces must be armed together" rule.
`ALLOW_SCORE_BACKFILL` alone (no `scripts/june_run_arm.py --domains` n8n allowlist) is correct
here — W1 touches no n8n execution at all (D-05, Pitfall 3).

---

### `docs/OPERATOR-RESCORE.md` (NEW runbook)

**Analog:** `docs/OPERATOR-VETO-REFRESH.md` — copy its voice and structure: plain-language
lead, a numbered "What changed" / procedure section, a dated AMENDMENT block convention for any
future correction, and explicit warnings lifted from measured live executions rather than
theory. Example of the tone and the "measured, not estimated" discipline to match (lines 29-39):
```
- Immediate, not "up to one daily tick".
- **0 provider credits, 0 Anthropic calls, 1 n8n execution** -- no provider, research, judge,
  merge or normalize node is on the lane (measured, executions 11858-11861).
- **Arming is still required to PATCH.** Execution `11858` derived the correct veto and returned
  `action: "write_blocked"` on an empty allowlist. Deriving is free; writing is not.
```
D-08's decision-rule table (weight branch vs veto branch, with measured costs) is the runbook's
Step 1 content — copy it in as literal markdown from CONTEXT.md, not paraphrased.

---

### `.planning/phases/49-.../49-RESCORE-REPORT.md` (NEW report) + report-builder module

**Analog:** `scripts/simulate_rubric_weights.py::render_markdown()` (lines 366-472) and
`build_simulation()` (lines 251-354) — the exact three-column
(`live`/`oracle_current`/`oracle_proposed`) `Counter`-based tier-distribution table shape and
named-row annotation to extend for P1/P2/P3. This is a rendering-shape precedent to extend, not
a function to call directly — the re-score report needs three **live time-series reads**, not
one in-memory simulation, so build a `{"P1": {...}, "P2": {...}, "P3": {...}}` payload from
three separate `_select_sample_ids()`-shaped live reads and feed it through a renderer modeled
on `render_markdown()`.

**Estimate-vs-actual table precedent:** `48-RUN-REPORT.md` § "Cost actuals" / § "Window
accounting" — mirror this section shape for D-05's window declaration vs actual spend.

---

### `tests/test_rubric_change_guard.py` (NEW, D-09 guard)

**Analog:** `tests/test_companies_factory_frozen.py` — the byte/digest-pin-with-explicit-
reviewed-re-baseline idiom. Copy its header convention verbatim in spirit:
```python
# The fixture (tests/fixtures/companies_jscode_frozen.json) is re-baselined ONLY by an
# explicit, reviewed act -- never as a routine "make the test pass" step.
```
Apply the same sentence to `config/icp_scoring.yaml`'s `base_score` table (digest or literal
comparison), with the failure message naming `docs/OPERATOR-RESCORE.md` and the re-score
obligation per D-09. `tests/test_n8n_org_type_absence.py` and
`tests/test_flow_rubric_conformance.py` are the other two precedent files establishing this
"permanent guard test over prose" idiom — read their headers for the same convention, do not
invent a new one.

The literal table to pin (`config/icp_scoring.yaml:5-40`):
```yaml
base_score:
  org_type:
    governing_body_league: 40
    content_producer: 20
    broadcaster: 20
    individual_club_team: 15
    regulator: -20
    gambling_operator: 0
    hardware_vendor: 0
    other: 0
    unknown: 0
  produces_content: {true: 20, false: 0, unknown: 0}
  geography: {ANZ: 10, AU: 10, NZ: 10, non_anz: 0, unknown: 0}
  revenue_band:
    "<1M": 0
    "1-5M": 0
    "5-50M": 10
    "50-500M": 10
    "500-750M": -5
    "750M-1B": -15
    "1B-1.2B": -30
    "1.2B+": -50
    unknown: 0
graduated_deductions: {}
```

---

### Acceptance test precedent for the D-15 Entain transition assertion

**Source:** `tests/test_scoring_parity.py::test_veto_clear_after_correction` (lines 451-498) —
quote and mirror this shape exactly for W2's instrumentation, in particular its `!= "D"`
assertion, never a hard-coded specific tier:
```python
patch_record("companies", company_id, {"lv_country_region_normalized": "AU"}, dry_run=False)
patch_record("companies", company_id, {
    "lv_org_type_verified_at": now_iso_ms(),
    "lv_produces_content_verified_at": now_iso_ms(),
}, dry_run=False)
if wait_until_searchable(VETO_CLEAR_DOMAIN) != 1:
    pytest.fail(...)
trigger_recompute(company_id, VETO_CLEAR_DOMAIN)
settle_until(company_id, "lv_anti_icp_flag", lambda v: v == "false")
settle_until(company_id, "lv_icp_tier", lambda v: v != "D", timeout=300)
cleared = fetch_for_parity(company_id)
assert cleared.get("lv_anti_icp_flag") == "false"
assert cleared.get("lv_anti_icp_reason") in (None, "")
assert cleared.get("lv_icp_tier") != "D"
```

---

## Shared Patterns

### Two-key arm gate (repo-wide idiom)
**Source:** `scripts/backfill_seed_company_scores.py:162-165` (`_writes_allowed`)
**Apply to:** every new write path this phase adds (the re-score wrapper's own arm check).
```python
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SCORE_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow
```

### Refuse-rather-than-truncate
**Source:** `enforce_sample_cap` / the new `enforce_exact_population` (both above).
**Apply to:** any population-size or population-membership check. Return `False` and let the
caller exit non-zero; never silently drop records to fit a cap.

### Portal assertion before any network call
**Source:** repo-wide idiom, confirmed in all four scripts RESEARCH.md read this session.
**Apply to:** every new live-mode entry point.
```python
assert os.getenv("HUBSPOT_PORTAL_ID") == "22617666"  # exact form varies per file's _portal_ok()
```

### `.env` absolute-path load wrapper
**Source:** `scripts/backfill_seed_company_scores.py:33-38` docstring.
**Apply to:** every live-mode operator invocation documented in `docs/OPERATOR-RESCORE.md`.

### Estimate produced by code, not prose
**Source:** `scripts/remediate_veto_companies.py::estimate_cost()` (lines 650-671).
**Apply to:** the `--plan` mode's cost output and `docs/OPERATOR-RESCORE.md`'s cited figures —
the doc must quote a live function call's output, never a hand-typed number.

## No Analog Found

None. Every file this phase touches has a direct, verbatim-quotable analog already in the
repo — this is the intended shape of a reuse-and-extend phase.

## Metadata

**Analog search scope:** `scripts/`, `src/`, `tests/`, `docs/`, `config/` — all already read in
full or in relevant part during RESEARCH.md's session; no new search was needed for this map.
**Files scanned:** 8 primary sources (see RESEARCH.md § Sources — Primary) plus 3 test-header
precedents.
**Pattern extraction date:** 2026-08-13
