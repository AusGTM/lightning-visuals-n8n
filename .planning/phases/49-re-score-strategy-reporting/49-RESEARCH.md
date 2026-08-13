# Phase 49: Re-score Strategy & Reporting - Research

**Researched:** 2026-08-13
**Domain:** Internal Python/n8n re-score tooling, HubSpot batch writes, operator reporting — no new technology
**Confidence:** HIGH

## Summary

This is a reuse-and-extend phase, not a new-technology phase. `49-CONTEXT.md` (678 lines) is
already the load-bearing decision record — every mechanism, cost, population, and window shape
is pre-decided (D-01…D-16). This RESEARCH.md's job is to verify the exact code surfaces those
decisions name, cite them with line numbers, and flag anywhere a claim in CONTEXT.md needs a
`[VERIFIED]` vs `[ASSUMED]` distinction for the planner.

Everything CONTEXT.md attributes to `scripts/backfill_seed_company_scores.py`,
`scripts/run_scoring_parity.py`, `scripts/simulate_rubric_weights.py`, and
`scripts/remediate_veto_companies.py` was read directly this session and confirmed accurate,
with three additions the planner needs that CONTEXT.md states but does not quote verbatim:
the exact `_writes_allowed()`/`enforce_sample_cap()` gate shape (currently a **count** cap, D-03
requires converting it to an **exact-set** gate), the exact `compute_components()` /
`build_updates()` contract the D-01 mechanism reuses unchanged, and the acceptance test's actual
assertions (`tests/test_scoring_parity.py::test_veto_clear_after_correction`, lines 451-498).

**Primary recommendation:** Build the re-score driver as a **new thin wrapper module** (not an
edit to `backfill_seed_company_scores.py`'s existing 10/25-record-scoped contract) that imports
`compute_components`/`build_updates`/`_chunked` unchanged, replaces only the sample-cap and
sample-selection functions with an exact-set variant, and reuses `estimate_cost`-style ex-ante
JSON output (mirroring `remediate_veto_companies.py`'s `estimate_cost()`) for the `--plan` mode
D-07 requires. Raise `HARD_CEILING_RECORDS` in the existing module per D-03 rather than forking
the whole file — the module's `compute_components`/`build_updates`/`_chunked`/
`batch_update_companies` call chain needs zero changes for the weight-branch re-score.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Component score computation (5 `*_score` properties) | Python oracle (`src/icp_scoring.py` via `compute_components()`) | — | Single source of truth; HubSpot never computes weights server-side except via flow `4626124224` mirror |
| Batch write of components | HubSpot CRM v3 batch API (`src/hubspot_client.batch_update_companies`) | — | Direct REST call, bypasses n8n entirely for the weight branch |
| Derived score/tier calculation | HubSpot `calculation_equation` property (`lv_icp_fit_score`) + Workflow `4625147345` (WF1) | — | Fires automatically once all 5 components are written; never written directly (Project D-07) |
| Veto derivation (flag/reason) | n8n `Decide Company Action` node (`ENRICH_DECIDE_CO_CLOUD`) | — | Sole writer; only needed for veto-branch re-scores, not this phase's weight change |
| Exact-set population gate | Python driver (arm-time or pre-arm-snapshot, per CONTEXT.md discretion) | — | Enforced in-process before any network call, mirrors `enforce_sample_cap` |
| Cost estimate / budget refusal | Python driver (`estimate_cost`-style function) | — | No live n8n usage endpoint exists; must be computed from known constants |
| Runbook / operator narrative | `docs/OPERATOR-RESCORE.md` (markdown) | `--plan` CLI mode | Doc cites live numbers from code so they cannot drift (D-07) |
| Report / before-after distribution | Committed markdown (`49-RESCORE-REPORT.md`) | Published Artifact | Durable git record + non-technical-operator-reachable surface (D-11) |
| Guard against unaccompanied weight change | pytest (`tests/test_*.py`, D-09) | — | Structural enforcement, not reliance on the (currently inert) parity sweep cron |

## Standard Stack

No new libraries. This phase is 100% reuse of already-installed dependencies:

| Library | Version (confirmed in repo) | Purpose | Source |
|---------|------|---------|--------|
| `requests` | already vendored, used by `src/hubspot_client.py` | HubSpot CRM v3 batch PATCH | `[VERIFIED: src/hubspot_client.py:1-129, read this session]` |
| `PyYAML` | already vendored, used by `src/icp_scoring.py::load_yaml` | Rubric config load | `[VERIFIED: src/icp_scoring.py:1-16, read this session]` |
| `pytest` | already vendored | Guard test + `tests/test_scoring_parity.py` `@live` tier | `[VERIFIED: .venv/bin/python -m pytest is the house invocation, per CLAUDE.md constraints table]` |
| `python-dotenv` | already vendored | `.env` loading via absolute-path wrapper (Read/Bash-blocked) | `[VERIFIED: project memory env-file-permission-blocked.md + backfill script docstring lines 33-36]` |

**No package installs, no version bumps, no new dependencies of any kind.** Skip the Package
Legitimacy Audit protocol entirely — nothing to check.

## Package Legitimacy Audit

**N/A — this phase installs zero external packages.** All code changes extend existing,
already-imported modules (`src.hubspot_client`, `src.icp_scoring`, `scripts.backfill_seed_company_scores`).
No `npm view` / `pip index versions` / `cargo search` check is applicable.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │  operator decides: re-score the population   │
                    └───────────────────┬───────────────────────┘
                                         │
                         reads docs/OPERATOR-RESCORE.md
                                         │
                         runs  driver --plan  (dry, no network)
                                         │
                         ┌───────────────▼────────────────┐
                         │ Step 1: classify the change      │
                         │  did it touch a VETO predicate?  │
                         └───────┬───────────────┬─────────┘
                                 │ NO             │ YES
                     ┌───────────▼─────┐   ┌──────▼──────────────────┐
                     │  WEIGHT BRANCH   │   │  VETO BRANCH (documented,│
                     │  (this phase)    │   │  not exercised, D-08)    │
                     └───────┬──────────┘   └──────────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ re-derive live population (HAS_PROPERTY  │
              │ lv_icp_fit_score search) -- exact-set gate │
              │ vs armed sample                             │
              └──────────────┬──────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ fetch canonical inputs per record      │
              │ (lv_org_type, lv_produces_content,     │
              │  lv_country_region_normalized,         │
              │  lv_revenue_band, lv_is_gambling_operator)│
              └──────────────┬──────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ compute_components() via              │
              │ src.icp_scoring.compute_icp_score()    │
              │ (reads config/icp_scoring.yaml)        │
              └──────────────┬──────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ CANARY: 1 record, PATCH, settle,       │
              │ read back lv_icp_fit_score/_tier (D-04)│
              └──────────────┬──────────────────────┘
                             │ canary OK
              ┌──────────────▼──────────────────────┐
              │ batch_update_companies() -- ONE batch  │
              │ call (66 ≤ BATCH_CHUNK_SIZE=100)       │
              │ writes ONLY the 5 *_score properties   │
              └──────────────┬──────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ HubSpot calculation_equation recomputes│
              │ lv_icp_fit_score -> fires WF1 -> writes │
              │ lv_icp_tier (~11s measured settle time) │
              └──────────────┬──────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ run_scoring_parity.py sweep: live vs   │
              │ oracle -- was RED since caae5d6, now   │
              │ must go GREEN (acceptance anchor)      │
              └──────────────┬──────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │ P1(entry)/P2(pre-W1)/P3(post-W1) three-│
              │ point tier distribution -> report      │
              └──────────────────────────────────────┘
```

### Recommended Project Structure

No new top-level directories. Extend the existing flat `scripts/` layout:

```
scripts/
├── backfill_seed_company_scores.py   # EDIT: HARD_CEILING_RECORDS 25->100, add
│                                      #   enforce_exact_population(sample_ids, live_ids)
│                                      #   alongside (not replacing) enforce_sample_cap
├── <new re-score wrapper, if Claude's discretion favors a thin module>
├── run_scoring_parity.py             # UNCHANGED — acceptance gate, do not edit to pass
├── simulate_rubric_weights.py        # REUSE render_markdown()/build_simulation() shape
│                                      #   for the D-10/D-12 report, do not reinvent
docs/
├── OPERATOR-RESCORE.md               # NEW — runbook doc (D-07), both branches (D-08)
.planning/phases/49-re-score-strategy-reporting/
├── 49-RESCORE-REPORT.md              # NEW — the committed markdown report (D-11)
tests/
├── test_backfill_seed_company_scores.py  # EXTEND — exact-set gate coverage
├── test_<guard>_pinned_rubric.py         # NEW — D-09 guard test
```

### Pattern 1: The two-key arm gate (repo-wide idiom)

**What:** Every write-capable script in this repo gates on `DRY_RUN=false` AND a
phase-scoped boolean env var, checked in a `_writes_allowed()` function, never a bare
`if not dry_run`.

**When to use:** Any new write path this phase's driver adds.

**Example (verbatim, `scripts/backfill_seed_company_scores.py:162-165`):**
```python
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SCORE_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow
```
`[VERIFIED: scripts/backfill_seed_company_scores.py:162-165, read this session]`

### Pattern 2: Refuse-rather-than-truncate sample cap (D-03 must convert this shape)

**What:** The existing cap is a **count** predicate; D-03 requires an **exact-set** predicate.

**Current shape (verbatim, `scripts/backfill_seed_company_scores.py:147-151`):**
```python
def enforce_sample_cap(sample_ids: list) -> bool:
    """True if the sample is at or under the resolved cap. The script refuses (exits
    non-zero) rather than silently truncating -- D-09's scope boundary is enforced here,
    not trusted to the caller."""
    return len(sample_ids) <= _resolved_max_records()
```
`[VERIFIED: scripts/backfill_seed_company_scores.py:147-151, read this session]`

The constants it reads from (verbatim, lines 84-87):
```python
DEFAULT_MAX_RECORDS = 10
HARD_CEILING_RECORDS = 25
BATCH_CHUNK_SIZE = 100
```
`[VERIFIED: scripts/backfill_seed_company_scores.py:84-87, read this session]`

D-03's required new predicate (`enforce_exact_population(sample_ids, live_ids)`) does not
exist yet — the planner's task list must create it, not merely raise `HARD_CEILING_RECORDS`.
Raising the ceiling to 100 alone still permits *any* ≤100-record subset; the exact-set check
is a second, independent function that must run before `_writes_allowed()` is consulted.

### Pattern 3: `compute_components()` — the unchanged reuse core

**Verbatim (`scripts/backfill_seed_company_scores.py:93-117`):**
```python
def compute_components(props: dict) -> dict:
    """Computes the five component scores from a record's canonical inputs, via
    src/icp_scoring.compute_icp_score -- never a second, hand-copied point table. Missing
    or unrecognised inputs contribute 0, mirroring the PROPERTY_DEFAULT_VALUE stamp new
    records get. Only the five CANONICAL_INPUT_PROPS are passed through -- other fields
    (e.g. native `country`) are deliberately excluded so this mirrors the flows' own
    lv_*-only trigger properties (40-05's retarget), not the oracle's broader native-field
    fallback."""
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
`[VERIFIED: scripts/backfill_seed_company_scores.py:93-117, read this session]`

`CANONICAL_INPUT_PROPS` (verbatim, lines 61-67):
```python
CANONICAL_INPUT_PROPS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
    "lv_revenue_band",
    "lv_is_gambling_operator",
]
```
`COMPONENT_PROPS` (verbatim, lines 72-78 — the five, and only five, properties any re-score
write payload may contain):
```python
COMPONENT_PROPS = [
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
]
```
`[VERIFIED: scripts/backfill_seed_company_scores.py:61-78, read this session]`

### Pattern 4: `batch_update_companies()` — the one-call-per-100 write path

**Verbatim (`src/hubspot_client.py:88-116`):**
```python
def batch_update_companies(updates: list[dict], dry_run=True):
    # Phase 40 (40-07, D-10): mirrors patch_record/create_record's dry_run discipline.
    # Two deliberate deviations from create_record's shape, both load-bearing for the
    # backfill caller (Task 2): an empty list short-circuits in BOTH modes (nothing to
    # send, so live mode must not POST an empty batch either), and a >100-entry list
    # raises rather than being sent or silently truncated -- the caller chunks, this
    # helper refuses to guess.
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
`[VERIFIED: src/hubspot_client.py:88-116, read this session]`

**Confirms CONTEXT.md's cost claim exactly**: 66 records ≤ 100 → the re-score is **one**
`batch_update_companies()` call, zero n8n executions, zero Anthropic calls, zero provider
credits (the function makes no n8n or Anthropic call of any kind — it is a direct HubSpot
CRM v3 REST call).

### Pattern 5: `compute_icp_score()` — the two-key OR veto predicate (D-02's "no recompute needed" claim, verified)

**Verbatim (`src/icp_scoring.py:117-128`):**
```python
    # 47.5-C (47.5-C-DECISION.md, or-retroactive): the veto fires on EITHER trigger. ...
    if is_hardware_vendor or org_type == "hardware_vendor":
        anti_icp_flag = True
        anti_reasons.append(cfg["hard_vetoes"]["hardware_vendor"]["reason"])
```
`[VERIFIED: src/icp_scoring.py:117-128, read this session]`

This confirms D-02: none of Phase 46's three weight changes (`base_score.org_type.individual_club_team`,
`base_score.org_type.regulator`, `graduated_deductions.gambling_operator`) intersects any
term this veto block reads (`is_hardware_vendor`, `org_type == "hardware_vendor"`,
`region_key == "non_anz"`, `produces_content is False`). The weight branch genuinely does not
need the n8n pipeline touched.

**`config/icp_scoring.yaml` verbatim confirms the exact weight values D-09's guard test must
pin** (`config/icp_scoring.yaml:5-40`):
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
  produces_content:
    true: 20
    false: 0
    unknown: 0
  geography:
    ANZ: 10
    AU: 10
    NZ: 10
    non_anz: 0
    unknown: 0
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
`[VERIFIED: config/icp_scoring.yaml:5-40, read this session]` — this is the literal table
D-09's guard test pins (by digest or literal comparison). `graduated_deductions: {}` is empty,
confirming CONTEXT.md's claim that the gambling deduction was fully removed (D-03), not merely
zeroed.

### Pattern 6: `estimate_cost()` — the ex-ante cost function shape to mirror for the re-score `--plan` mode

**Verbatim (`scripts/remediate_veto_companies.py:650-671`):**
```python
def estimate_cost(ids) -> dict:
    """D-03/D-20 cost projection over `ids` (the ids about to run) -- a static
    projection, never a live balance check. There is no n8n usage endpoint (project
    memory n8n-execution-budget.md); month-to-date headroom is the operator's own
    confirmation at the arming checkpoint."""
    n_records = len(ids)
    redundant = len(set(ids) & KNOWN_LIKELY_EVIDENCE_GATED_IDS)
    return {
        "web_research_calls": n_records,
        "redundant_research_calls": redundant,
        "n8n_executions": n_records,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "lusha_credits_note": "...",
        "anthropic_estimate_usd": round(n_records * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
        "anthropic_estimate_note": "...",
    }
```
`[VERIFIED: scripts/remediate_veto_companies.py:650-671, read this session]`

`N8N_EXECUTION_BUDGET_MONTH = 2500` `[VERIFIED: scripts/remediate_veto_companies.py:167]`.

The re-score `--plan` mode's own cost function should follow this shape but with the
**weight branch's true numbers**: `n8n_executions: 0`, `anthropic_calls: 0`,
`provider_credits: 0`, `hubspot_batch_calls: 1` — since `compute_components()` +
`batch_update_companies()` never touch n8n or Anthropic. `refuse_if_over_budget()`
(`scripts/remediate_veto_companies.py:674-683`) is the refuse-not-truncate pattern to mirror,
though for the weight branch the budget can never be exceeded (0 executions).

### Pattern 7: `post_webhook_event(..., recompute=True)` — the veto-branch vehicle (documented, not exercised this phase)

**Signature (verbatim, `scripts/remediate_veto_companies.py:596-597`):**
```python
def post_webhook_event(company_id: str, armed, config: dict, transport=requests,
                       recompute: bool = False, domain: str = None, timeout: float = 300):
```
`[VERIFIED: scripts/remediate_veto_companies.py:596-597, read this session]`

`armed` has no default — raises `NotArmedError` before any network call if falsy
(`scripts/remediate_veto_companies.py:611-616`). `timeout` defaults to **300**, not 30 — a
Phase 47 live-discovered correction (Trap 4 in CONTEXT.md's constraints table). This is the
function D-08's runbook cites for the veto branch's cost model (~66 n8n executions, 2.6% of
the monthly allowance) — it is **not called live this phase** per the deferred item, only
documented.

### Pattern 8: `simulate_rubric_weights.py`'s three-column report shape — reuse for RESCORE-03

`build_simulation()` (`scripts/simulate_rubric_weights.py:251-354`) already produces exactly
the shape D-10 asks for: a `tier_distribution` dict with `live`/`oracle_current`/
`oracle_proposed` keys, each a `Counter`-derived dict over `["A","B","C","D","Unscored","Needs Review"]`,
plus a `movement_summary` with `by_org_type` breakdown and named-row detail. `render_markdown()`
(lines 366-472) turns that payload into the exact table format CONTEXT.md's D-10/D-12 wants.
`[VERIFIED: scripts/simulate_rubric_weights.py:251-472, read this session]`

**The re-score report is a different measurement (three *live* reads over time, not one
in-memory simulation), so this pattern is a rendering-shape precedent to extend, not a
function to call directly.** The planner's report driver should build its own
`{"P1": {...}, "P2": {...}, "P3": {...}}` payload (three live `HAS_PROPERTY(lv_icp_fit_score)`
reads at three points in time) and feed it through a `render_markdown()`-shaped renderer
modeled on this file's, not through `build_simulation()` itself (which scores in-memory
configs, not live time-series reads).

### Anti-Patterns to Avoid

- **Forking `backfill_seed_company_scores.py` into a new file.** `compute_components`,
  `build_updates`, `_chunked` need zero changes for the weight branch — only the sample-cap
  predicate and sample-selection function change. A fork is "a second producer of the same
  five component writes" — explicitly rejected in CONTEXT.md D-03.
- **Editing `run_scoring_parity.py` to make the sweep pass.** The sweep is the acceptance
  gate; it must go green because the re-score actually happened, not because its comparison
  logic was loosened. CONTEXT.md's constraints table is explicit: "do not edit the script to pass."
- **Writing `lv_icp_fit_score`/`lv_icp_tier`/`lv_anti_icp_flag`/`lv_anti_icp_reason` directly.**
  `lv_icp_fit_score` is a `calculation_equation` property with `readOnlyValue: true` — a direct
  PATCH attempt would 400 even if attempted (Project-level D-07, held absolutely through three
  prior phases' windows).
- **Trusting the parity sweep as the enforcement mechanism for D-09.** It detects divergence
  *after* it exists — exactly the state this phase closes — and the sweep's cron is confirmed
  not installed (`crontab -l` empty, per PROJECT.md). A guard test is required, not reliance on
  a currently-inert scheduled check.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Component score computation | A second point-lookup table | `compute_components()` → `src.icp_scoring.compute_icp_score()` | Single source of truth against `config/icp_scoring.yaml`; a hand-copied table is exactly the split-brain class Phase 46/47.5's parity rule exists to prevent |
| Batch write to HubSpot | Per-record `patch_record()` loop | `batch_update_companies()` | 66 records fit in one call (`BATCH_CHUNK_SIZE=100`); a loop would spend 66 HTTP round-trips for no benefit and risks partial-failure inconsistency |
| Population definition | A new `search_records` query with different filters | `_select_sample_ids()` / `_select_row_ids()`'s exact `HAS_PROPERTY(lv_icp_fit_score)` shape | CONTEXT.md is explicit: "no second definition of the scored population" — both existing scripts already share one definition by design |
| Cost estimate before a run | A prose paragraph with hand-typed numbers | An `estimate_cost()`-shaped function, called live, printed into the doc | House rule (`47-COST-ESTIMATE.md` precedent): "the doc and the function cannot silently drift" |
| Tier-distribution report rendering | A bespoke markdown template from scratch | `simulate_rubric_weights.py::render_markdown()`'s table shapes as a starting template | Already produces `Counter`-based tier tables and named-row annotation; reinventing risks a subtly different (and unvalidated) table format |
| Settle-poll for calculated properties | A fixed `time.sleep(N)` | `backfill_seed_company_scores.py::_settle()`'s poll-until-stable pattern (lines 252-271) | Already handles the "poll until two consecutive reads match, else timeout" shape; measured ~11s in Phase 40-07 but is not guaranteed constant |

**Key insight:** every write-capable operation this phase needs already has a working,
tested implementation somewhere in `scripts/`. The engineering work is composition (raise a
ceiling, add an exact-set predicate, wire a `--plan` mode, write a guard test) — not new
scoring, writing, or estimating logic.

## Runtime State Inventory

**Not applicable.** This phase is neither a rename, refactor, nor migration. It re-scores
existing HubSpot property values via existing write paths; it does not rename any property,
file, table, or identifier. No stored-data, live-service-config, OS-registered-state,
secrets/env-var, or build-artifact category applies. (Confirmed by reading the phase's own
`<domain>` boundary in CONTEXT.md: "component backfill... reads config directly... never a
second hand-copied table" — an in-place value recompute, not a naming change.)

## Common Pitfalls

### Pitfall 1: Raising `HARD_CEILING_RECORDS` alone does not enforce D-03

**What goes wrong:** A plan that only bumps `HARD_CEILING_RECORDS = 25` to `100` and leaves
`enforce_sample_cap()` unchanged still permits any ≤100-record subset — including a stale
snapshot, a manually-typed 60-record list missing 6 records, or a search result polluted by a
race condition. The acceptance gate (`run_scoring_parity.py`'s sweep) would still show
`real_findings` for any excluded scored record.

**Why it happens:** `enforce_sample_cap` (verbatim above) is a pure count comparison —
`len(sample_ids) <= _resolved_max_records()`. It has no concept of "this must be the *entire*
live-derived set."

**How to avoid:** Add a second, independent predicate — `enforce_exact_population(sample_ids,
live_ids)` — that the driver calls in addition to (not instead of) the count cap, and refuses
non-zero on any mismatch (D-03's language: "the sample must equal the live-derived
`HAS_PROPERTY(lv_icp_fit_score)` id set exactly").

**Warning signs:** A plan task that says "raise the ceiling" without a second task adding the
exact-set assertion.

### Pitfall 2: The stamped-component edge cannot be discovered by code review

**What goes wrong:** Assuming overwriting an already-`PROPERTY_DEFAULT_VALUE`-stamped
component behaves identically to writing a never-set one, without testing it live.

**Why it happens:** HubSpot's `defaultValue`/`PROPERTY_DEFAULT_VALUE` stamp mechanism is
API-inaccessible for reads (confirmed by `PORTAL-FACTS.md`'s three-way probe, cited but not
independently re-verified this session — treating as `[CITED: PORTAL-FACTS.md, prior phase
finding]`). No amount of source reading resolves this; it is a live-only question.

**How to avoid:** D-04's canary — write one record, settle, read back, confirm correctness —
**before** releasing the other 65 in the same window. This is a runtime verification step the
plan's tasks must include explicitly, not something research or planning can pre-resolve.

**Warning signs:** A plan that batches all 66 in one PATCH without a canary step first.

### Pitfall 3: `assert_allowlist_exact`-shaped gates matter even though W1 arms no n8n allowlist

**What goes wrong:** Copying Phase 48's "both arming surfaces must be armed together" rule
into W1, which would widen the blast radius for a write that touches no n8n allowlist at all.

**Why it happens:** Every prior phase's windows (47, 47.5, 48) all involved n8n record-write
allowlists. W1 is architecturally different — `ALLOW_SCORE_BACKFILL` gates a **direct HubSpot
CRM batch call**, with no n8n execution in the path at all.

**How to avoid:** D-05 is explicit: "Do not copy Phase 48's 'both arming surfaces must be
armed together' rule into W1." The Python-side two-key gate (`DRY_RUN=false` +
`ALLOW_SCORE_BACKFILL=true`, mirrored from `_writes_allowed()` above) is sufficient and
correct for W1 alone.

**Warning signs:** A plan task that arms `scripts/june_run_arm.py --domains` for the W1 leg.

### Pitfall 4: The false-green trap in `run_scoring_parity.py`'s comparison logic

**What goes wrong:** Trusting a PASS verdict on a sample that excluded some scored records.

**Why it happens:** `_select_sample_ids()` (verbatim above) defaults to a live
`HAS_PROPERTY(lv_icp_fit_score)` search **or** an explicit `PARITY_SAMPLE_IDS` env override.
If the re-score driver's exact-set gate and the parity sweep's sample selection ever diverge
(e.g. one runs before a record gets its first score, the other after), a real divergence could
be invisible to whichever ran on the stale set.

**How to avoid:** Re-derive the population live, immediately before both W1 and the P2/P3
report reads (D-10 already requires this: "fresh live read before W1 opens" / "fresh live read
after W1 settles"). Never reuse a cached id list across the arm-time gate and the acceptance
sweep within the same session without re-deriving.

**Warning signs:** A plan that hard-codes the 66 ids as a literal list anywhere other than a
committed evidence snapshot (the population must be *re-derived*, per CONTEXT.md's own
instruction: "Re-derive it live and stamp the date anyway").

### Pitfall 5: `.env` is Read/Bash permission-blocked — every live script needs the dotenv wrapper

**What goes wrong:** A plan task that assumes `load_dotenv()` (bare) works, or that `.env` can
be read directly to derive required vars.

**Why it happens:** Documented project memory (`env-file-permission-blocked.md`) and confirmed
in this session's read of `backfill_seed_company_scores.py`'s own docstring (lines 33-38):
`.env` is Read/Bash permission-blocked, and `python-dotenv`'s bare `load_dotenv()` resolves
relative to the **calling file**, not the cwd — with no `conftest.py`, a live pytest run needs
an absolute-path wrapper or every HubSpot read 401s.

**How to avoid:** Every live-mode operator invocation must use the pattern already established
in every existing script's own docstring:
```bash
ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c \
    "from dotenv import load_dotenv; load_dotenv(); import runpy; \
     runpy.run_path('scripts/<driver>.py', run_name='__main__')"
```
`[VERIFIED: scripts/backfill_seed_company_scores.py:33-38, read this session]`

**Warning signs:** A plan task that writes a bare `python scripts/<driver>.py` invocation for
any live-mode step.

## Code Examples

Verified patterns from this session's direct reads (all citations above are re-collected here
for the planner's convenience — no new code beyond what is already quoted in the Architecture
Patterns section):

### Acceptance test — `tests/test_scoring_parity.py::test_veto_clear_after_correction` (lines 451-498)

This is the test D-08's veto-branch decision rule references, and the D-15 transition-proof
mechanism (`settle_until(company_id, "lv_icp_tier", lambda v: v != "D", timeout=300)`) the
Entain W2 instrumentation must mirror:

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
`[VERIFIED: tests/test_scoring_parity.py:451-498, read this session]`

D-15's own required assertion is `≠ D`, never a specific tier — this test's own
`assert cleared.get("lv_icp_tier") != "D"` shape (line 498) is the exact literal precedent to
copy for the Entain W2 instrumentation, not a hard-coded `B`/`C` assertion.

### `_select_sample_ids()` — the population definition, byte-for-byte shared with `simulate_rubric_weights.py::_select_row_ids()`

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
`[VERIFIED: scripts/run_scoring_parity.py:149-165, read this session]` — `limit=100` is
important: at exactly 66 results this never paginates, but a re-score driver's own population
query should use the same `limit=100` (not a smaller default) to avoid a silent truncation if
the scored population grows past the current 66 before this phase executes.

## State of the Art

Not applicable in the conventional sense (no external library/API evolved since a prior
research pass) — but two **internal** "state changed" facts the planner must not treat as
still-open:

| Old state | Current state | When changed | Impact |
|-----------|---------------|---------------|--------|
| Parity sweep at `caae5d6`: green | Parity sweep: RED by design | Phase 46 Plan 04 (`caae5d6`, 2026-08-11) | This is a *deliberately opened* window, not a regression — the plan's headline proof is closing it, not "fixing" a break |
| Hardware veto fired only on `lv_is_hardware_vendor` boolean | Fires on boolean OR `lv_org_type == "hardware_vendor"` | Phase 47.5-C (`f817ec5`, 2026-08-12) | Confirmed live in `src/icp_scoring.py:117-128` this session — D-02's "veto fields need no recompute" claim depends on this predicate being unaffected by the *weight* change, which it is (neither org-type score value nor the hardware string comparison changed) |
| SJ-3 poller cadence documented as 15-minute | Daily (`daysInterval: 1`) | Post-2026-08-09 burn-rate incident | Relevant only if the planner considers the SJ-3/poller path — CONTEXT.md and CLAUDE.md §19.0 both correctly state this is **not** the mechanism this phase uses (D-01 rejects it explicitly) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot's `PROPERTY_DEFAULT_VALUE` stamp is API-inaccessible for reads (cited from `PORTAL-FACTS.md`, not independently re-verified this session — no live API call was made) | Common Pitfalls #2 | If actually readable by some undocumented endpoint, D-04's canary step is still safe (it is strictly stronger than assuming), so risk is low — worst case is an unnecessary canary step, not a wrong one |
| A2 | The ~11s settle time for the calculated-property chain (`lv_icp_fit_score` → `lv_icp_tier`) generalizes from a single Phase 40-07 measurement to a 66-record batch write | Common Pitfalls, Pattern 3 | A batch write firing the calculation on 66 records simultaneously could take materially longer than 11s per record if HubSpot's calculation queue serializes; the `_settle()` helper's `timeout=120` default may need raising for the batch case — plan should treat this as an open verification item, not assume 11s holds at n=66 |
| A3 | `docs/OPERATOR-VETO-REFRESH.md`'s "as-built amendment" block (recompute lane costs 0 credits/0 Anthropic/1 execution) generalizes correctly to describe D-08's veto-branch cost estimate — confirmed by reading the doc directly this session, so this is actually `[VERIFIED]`, not assumed; listed here only to flag that the underlying executions (11858-11861) were not independently re-queried this session | Pattern 7 | Low — this is a documented, cited historical measurement the phase does not need to re-prove (deferred item) |

**If this table is sparse:** most of this phase's factual claims were verified by direct file
reads this session (`[VERIFIED: path:lines]` tags throughout) rather than assumed from training
knowledge, because the entire domain is this repo's own code.

## Open Questions (RESOLVED)

*All three were closed at plan time (2026-08-13). Each recommendation below was adopted; the
plan that adopted it is named inline.*

1. **RESOLVED — Does `enforce_exact_population` re-derive the population at arm time, or assert
   against a pre-arm snapshot?** Adopted: arm-time re-derivation, in plan **49-01**.
   - What we know: CONTEXT.md leaves this as Claude's discretion, with a stated preference for
     arm-time re-derivation.
   - What's unclear: whether a pre-arm snapshot introduces any race risk given the population
     search takes a single `search_records` call (fast, low race window) versus the benefit of
     a snapshot being reviewable before the window opens.
   - Recommendation: arm-time re-derivation, per CONTEXT.md's stated preference and the "Re-derive
     it live and stamp the date anyway" house rule — a snapshot is evidence, never a guarantee.

2. **RESOLVED — Does the settle timeout need raising for a 66-record simultaneous batch write?**
   Adopted: the generous 300s settle timeout, treated as its own verification step, in plan
   **49-05**.
   - What we know: 11s was measured for one record (Phase 40-07).
   - What's unclear: whether HubSpot's calculation-property engine processes 66 simultaneous
     triggers in parallel or serially, and whether `_settle()`'s existing `timeout=120` default
     is suf1ficient at n=66.
   - Recommendation: the plan should treat the settle-poll for the batch as its own verification
     step with a generous timeout (e.g. 300s, matching `post_webhook_event`'s Trap-4-corrected
     read timeout) rather than assuming the single-record figure holds unchanged.

3. **RESOLVED — Where does the `--plan` mode live — on `backfill_seed_company_scores.py`
   directly, or a thin wrapper?** Adopted: the thin wrapper module (`rescore_population.py`),
   in plan **49-01**; `enforce_sample_cap` is left untouched.
   - What we know: CONTEXT.md leaves this as Claude's discretion.
   - What's unclear: whether adding `--plan` to the existing module changes its existing
     10/25-record-scoped Phase 40 contract in a way that could affect other callers
     (`scripts/remediate_veto_companies.py` imports `compute_components` from it directly, per
     line 59 of that file — confirmed this session).
   - Recommendation: a thin wrapper module that imports `compute_components`/`build_updates`/
     `_chunked` from the existing module and adds only the exact-set gate + `--plan` mode is
     lower-risk than editing the shared module's cap/gate functions in place, since
     `remediate_veto_companies.py` already depends on `backfill_seed_company_scores.py`'s
     current shape.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/python` | All Python driver invocations, pytest | ✓ (per project memory `test-suite-run-commands.md`) | — | — |
| `node` (for `node --test`) | `tests/n8n/*.test.mjs` glob-form tests | ✓ | Must use glob form; directory form broken on node 24 per repo-standing constraint | — |
| HubSpot private-app API access | All live reads/writes | ✓ (assumed present; portal `22617666` asserted by every script before any call) | — | — |
| n8n Cloud API access | Only if the veto branch or the folded todo's deploy is exercised | ✓ (assumed present per prior-phase deploys) | — | — |
| Artifact publish capability | D-11's published-Artifact deliverable | Depends on the executing session/orchestrator (Phase 46-03 deferred this exact capability for its own executor) | — | Markdown-only committed report if the executing session lacks Artifact publish, disclosed as a deviation (mirrors 46-03's precedent) |

**Missing dependencies with no fallback:** none identified — this phase's write paths are all
already-proven live mechanisms from prior phases.

**Missing dependencies with fallback:** Artifact publish (see table) — if unavailable, fall
back to markdown-only and disclose per the Phase 46-03 precedent, which is explicitly named in
CONTEXT.md D-11 as "This also discharges 46-03's deferred D-09 shareable-artifact publish."

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + Node's built-in `node --test` (n8n JS) |
| Config file | none dedicated — repo-root `pytest.ini`/`conftest.py` not present for live tests; `.env` loaded via absolute-path wrapper (Common Pitfalls #5) |
| Quick run command | `.venv/bin/python -m pytest -k <new_guard_test_name>` (offline, no network) |
| Full suite command | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` (glob form — directory form broken on node 24) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RESCORE-01 | Exact-set population gate refuses a non-exact sample | unit (offline) | `.venv/bin/python -m pytest tests/test_backfill_seed_company_scores.py -k exact_population -x` | ❌ Wave 0 — new test to add alongside the new gate function |
| RESCORE-01 | `--plan` mode emits live-derived id set, count, chunking, window shape, cost with no writes | unit (offline, stubbed fetch) | new test file, e.g. `tests/test_<rescore_driver>.py -k plan_mode` | ❌ Wave 0 |
| RESCORE-02 | Acceptance anchor — live population sweep exits green after the re-score | live (`@live` tier, network) | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k live -m live` OR the standalone `.venv/bin/python -c "...runpy.run_path('scripts/run_scoring_parity.py'...)"` invocation, checking exit code 0 | ✓ exists (`scripts/run_scoring_parity.py`) — behavior change is in the *data*, not the test |
| RESCORE-02 | D-09 guard: an unaccompanied `base_score` change fails with a message naming the runbook | unit (offline) | new test file, e.g. `tests/test_rubric_change_guard.py -x` | ❌ Wave 0 — this is D-09's headline deliverable |
| RESCORE-03 | Three-point tier distribution report renders correctly from a fixture payload | unit (offline, stubbed fetch) | new test in a report-builder test file | ❌ Wave 0 |
| D-04 (canary) | Single-record PATCH settles and reads back correctly before the batch releases | live (manual/scripted, network) | driver's own `--canary-only` flag or equivalent live-run step, verified by the run report rather than a pytest assertion (mirrors `backfill_seed_company_scores.py`'s existing `_settle()` print-only pattern, which "has no assertion of its own on the result") | N/A — this is a runtime procedure step, not a pytest case |
| D-14 (Entain evidence bar) | Driver hard-refuses below `min_confidence: 85` / missing evidence URL | unit (offline, stubbed research result) | extend `tests/test_remediate_veto_companies.py`-shaped coverage or a new test targeting the same `field_policy.yaml` bar | Partially — `config/field_policy.yaml`'s bar exists and is enforced elsewhere (`build_input_patch` in `remediate_veto_companies.py`); a Phase-49-specific driver reusing that function inherits the guard, else it is Wave 0 |

### Sampling Rate
- **Per task commit:** offline pytest (`-k` selector for the touched test), no network, no HubSpot credentials required.
- **Per wave merge:** full offline suite (`.venv/bin/python -m pytest -m "not live"` or equivalent exclusion) plus `node --test tests/n8n/*.test.mjs`.
- **Phase gate:** the `@live` acceptance anchor (`run_scoring_parity.py`'s population sweep, exit code 0) must be green before `/gsd-verify-work` — this is the phase's own stated acceptance bar, not a generic nyquist convention.

### Wave 0 Gaps
- [ ] `enforce_exact_population(sample_ids, live_ids)` function + its offline unit test — does not exist yet (D-03).
- [ ] `--plan` mode on the re-score driver + its offline unit test with a stubbed fetch — does not exist yet (D-07).
- [ ] D-09's pinned-rubric guard test — does not exist yet, though three precedent test files
      (`tests/test_n8n_org_type_absence.py`, `tests/test_flow_rubric_conformance.py`,
      `tests/test_companies_factory_frozen.py`) establish the "explicit reviewed re-baseline"
      idiom to copy, confirmed by reading their headers this session.
- [ ] The three-point report builder + renderer + its offline unit test — does not exist yet (D-10/D-12).
- [ ] D-04's canary procedure — not a pytest gap; a live runtime step the plan's tasks must include explicitly.

## Security Domain

`security_enforcement` is not set to `false` in `.planning/config.json` (confirmed by reading
the file this session — it contains only `workflow`/`review` keys, no `security_enforcement`
key at all), so treat as enabled per the default rule.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No new auth surface; reuses existing `HUBSPOT_PRIVATE_APP_TOKEN` bearer auth (`src/hubspot_client.py::hs_headers()`) |
| V3 Session Management | No | Stateless REST calls, no session concept |
| V4 Access Control | Partial | Two-key arm gates (`DRY_RUN`/`ALLOW_*`) are the access-control mechanism for write authority — this phase adds one new gate (`enforce_exact_population`) but changes none of the existing token/portal-id checks |
| V5 Input Validation | Yes | `_portal_ok()` asserts `HUBSPOT_PORTAL_ID == "22617666"` before every network call (repo-wide idiom, confirmed in `backfill_seed_company_scores.py`, `run_scoring_parity.py`, `simulate_rubric_weights.py`, `remediate_veto_companies.py` — all read this session); the exact-set population gate is itself an input-validation control |
| V6 Cryptography | No | No cryptographic operation in scope |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Silent-denial write (empty allowlist reports "armed" but writes nothing) | Repudiation | `assert_allowlist_exact`-shaped pre-write assertion (Trap 2 in CONTEXT.md's constraints table) — not directly applicable to W1 (no n8n allowlist involved) but the *principle* (assert the gate is non-empty and exact before trusting "armed") applies equally to the new exact-set population gate |
| Stored-vs-running divergence (PUT does not reload a running n8n workflow) | Tampering (of executed logic vs intended logic) | Bounce + independent read-back with a live execution's own node list (Trap 1) — relevant only if the folded todo's deploy is executed this phase |
| Secret/token leakage in logs | Information Disclosure | `hs_headers()`/webhook secret are never printed by any function read this session (`patch_record`, `batch_update_companies`, `post_webhook_event` all print only the payload, never headers) — confirmed by direct read; any new driver code must preserve this |
| Over-broad write scope (writing more properties than intended) | Tampering | `COMPONENT_PROPS`/`FORBIDDEN_PROPS`-shaped disjointness assertions — `scripts/remediate_veto_companies.py` asserts `FORBIDDEN_PROPS.isdisjoint(props)` before returning a patch (line 360, confirmed this session); the re-score driver's payload-building function should carry an equivalent assertion restricting output to exactly `COMPONENT_PROPS` |

## Sources

### Primary (HIGH confidence — direct file reads this session)
- `scripts/backfill_seed_company_scores.py` (full file, 276 lines) — the re-score mechanism
- `scripts/run_scoring_parity.py` (full file, 466 lines) — the acceptance gate
- `scripts/simulate_rubric_weights.py` (full file, 521 lines) — the report-shape precedent
- `scripts/remediate_veto_companies.py` (partial, ~420 of 1044 lines: header, pin resolution,
  gates, research/patch builders, `post_webhook_event`, `estimate_cost`, `refuse_if_over_budget`)
- `src/hubspot_client.py` (full file, 129 lines) — the write primitives
- `src/icp_scoring.py` (full file, 167 lines) — the oracle, veto predicate
- `config/icp_scoring.yaml` (full file, 84 lines) — the rubric of record D-09 pins
- `docs/OPERATOR-VETO-REFRESH.md` (full file, 220 lines) — the runbook-voice precedent for D-07
- `tests/test_scoring_parity.py` lines 451-511 — the acceptance test and D-15's precedent shape
- `tests/test_n8n_org_type_absence.py`, `tests/test_flow_rubric_conformance.py`,
  `tests/test_companies_factory_frozen.py` (headers, ~25 lines each) — D-09 guard-test idiom
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md` lines 274-338 —
  "Parity red window" and "What Phase 49 owes and what it costs" sections
- `.planning/PROJECT.md` lines 20-119 — entry distribution, 2,500/month allowance, v0.9 goal
- `.planning/ROADMAP.md` lines 318-349 — Phase 49 goal and success criteria
- `.planning/REQUIREMENTS.md` (full file) — RESCORE-01/02/03 text and full traceability table
- `.planning/STATE.md` (full file) — phase history, decisions log
- `.planning/config.json` — confirms `security_enforcement` absent (treat as enabled) and
  `workflow.nyquist_validation` absent (treat as enabled)
- `.planning/phases/49-re-score-strategy-reporting/49-CONTEXT.md` (full file, 678 lines) — the
  primary constraint source, already exceptionally thorough

### Secondary (MEDIUM confidence)
- `PORTAL-FACTS.md`'s default-value-generation finding — cited by CONTEXT.md and the backfill
  script's own docstring, not independently re-verified via a live API call this session

### Tertiary (LOW confidence)
- None — this phase's domain is entirely this repo's own code, and every load-bearing claim
  was checked against a direct file read this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; every import verified present in already-read files
- Architecture: HIGH — every pattern quoted verbatim from a file read this session
- Pitfalls: HIGH — every pitfall traces to a specific CONTEXT.md decision (D-01…D-16) cross-checked
  against the actual code it constrains

**Research date:** 2026-08-13
**Valid until:** Effectively unbounded for the code-shape claims (internal repo, changes only
by deliberate future phases) — but re-verify `config/icp_scoring.yaml`'s literal weights and
`run_scoring_parity.py`'s red/green state immediately before planning execution, since both are
explicitly "live state" this phase is designed to change.
