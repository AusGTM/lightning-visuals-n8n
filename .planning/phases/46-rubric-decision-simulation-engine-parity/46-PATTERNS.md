# Phase 46: Rubric Decision, Simulation & Engine Parity - Pattern Map

**Mapped:** 2026-08-11
**Files analyzed:** 12
**Analogs found:** 11 / 12

RESEARCH.md already corrected the file set materially: there are **two** live scoring
engines for org-type weights (Python oracle + HubSpot flow `4626124224`), not three — the
n8n "JS port" carries no weight table. Treat `n8n/wf_enrichment_cloud.json` as **not
modified** in this phase (a static absence-guard test may be *added*, but nothing there is
edited). This file list reflects that correction.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `config/icp_scoring.yaml` | config | pure-value table | itself (edit in place) | n/a — direct edit |
| `src/icp_scoring.py` (`compute_icp_score` `cfg=None` param + gambling KeyError fix) | pure-function | transform (record→score) | itself (edit in place) | n/a — direct edit |
| `scripts/simulate_rubric_weights.py` (CREATE) | script | reads-only, batch report | `scripts/run_scoring_parity.py` | exact (same fetch/portal-guard/report shape, different comparison) |
| `tests/test_simulate_rubric_weights.py` (CREATE) | test | no-write assertion | `tests/test_scoring_parity.py` (offline tier, `build_report` unit tests) | role-match |
| `tests/test_icp_scoring.py` (MODIFY: 2 literal asserts) | test | unit, pure-function | itself | n/a — direct edit |
| `tests/test_scoring_parity.py` (MODIFY: 3 sites) | test | unit + live fixture-driven | itself | n/a — direct edit |
| `tests/scoring_fixtures.py` | pure-function / fixture | read-only live fetch + oracle call | itself — reused unmodified as import, no edit expected unless `expected_for` needs a `cfg` passthrough | n/a — likely no edit |
| `tests/test_flow_rubric_conformance.py` (MODIFY: `test_gambling_flow_matches_rubric`) | test | offline, config↔archive parity | itself | n/a — direct edit |
| `config/hubspot_flows/4626124224-org-type-score.after.json` (MODIFY via live PUT + re-archive) | config (HubSpot flow archive) | writes-to-HubSpot (flow definition, not record data) | `scripts/fetch_hubspot_flow.py` / `scripts/put_hubspot_flow.py` + `PORTAL-FACTS.md` protocol | exact — identical edit already done once to this exact flow in Phase 40 |
| `config/hubspot_flows/gambling-score.after.json` (MODIFY via live PUT + re-archive) | config (HubSpot flow archive) | writes-to-HubSpot (flow definition) | same PUT protocol as above | exact |
| `46-DECISION.md` (CREATE) | decision-record | n/a | `.planning/milestones/v0.7-phases/39-path-decision-fit-score-verification/39-DECISION.md` | exact — explicit precedent named in CONTEXT.md D-05 |
| simulation report markdown under `.planning/phases/46-.../` (CREATE, published as artifact) | doc / generated report | reads-only, output artifact | `scripts/run_scoring_parity.py::_write_report` (JSON verdict pattern) for shape; content is new | partial — shape reusable, content net-new |
| Docs: `docs/business/icp-scoring.md`, `CLAUDE.md` §10.1/§10.3, `.planning/intel/constraints.md`, `.planning/intel/requirements.md`, `docs/WEB-RESEARCH-SPEC.md` (MODIFY, prose) | doc | n/a | itself (hand-maintained prose, no generator) | n/a — direct edit, D-13's target list is exhaustive already |

## Pattern Assignments

### `config/icp_scoring.yaml` (config, pure-value table)

Direct edit, no analog needed. Exact lines to change (read this session):

```yaml
# lines 6-14 today
base_score:
  org_type:
    governing_body_league: 40
    content_producer: 20
    broadcaster: 20
    individual_club_team: 5      # -> 15 (D-01)
    regulator: 5                 # -> -20 (D-02, per Research Open Q5: direct weight edit,
                                  #   NOT a new graduated_deductions key)
    gambling_operator: 0
    hardware_vendor: 0
    other: 0
    unknown: 0
```

```yaml
# graduated_deductions block — remove the gambling_operator key entirely (D-03)
graduated_deductions:
  gambling_operator: -20   # DELETE this line/key
```

Note: RESEARCH.md's Open Question 5 finding overrides CONTEXT.md D-06's "new engine
logic" framing — D-02's regulator deduction is a **direct negative base_score.org_type
value**, not a new `graduated_deductions` key. This is a corrected instruction the planner
must follow over the literal CONTEXT.md text.

---

### `src/icp_scoring.py::compute_icp_score` (pure-function, transform)

**Current signature** (line 34):
```python
def compute_icp_score(record: HubSpotRecord, candidate_patch: dict) -> ICPScoreResult:
    cfg = load_yaml("config/icp_scoring.yaml")
```

**Required surgical change 1 — `cfg=None` override param** (enables the simulation to
score the same record twice under two weight tables in one process, per RESEARCH.md's
primary recommendation):
```python
def compute_icp_score(record: HubSpotRecord, candidate_patch: dict, cfg: dict = None) -> ICPScoreResult:
    cfg = cfg or load_yaml("config/icp_scoring.yaml")
```
Additive, backward-compatible — every existing 2-positional-arg call site (including
`tests/scoring_fixtures.py::expected_for`) is untouched.

**Required surgical change 2 — remove the unconditional gambling key lookup** (lines
89-92, D-03's `KeyError` bug, verified by direct execution in RESEARCH.md):
```python
# CURRENT (line 89-92) — KeyErrors the instant graduated_deductions.gambling_operator
# is deleted from config, for ANY company with lv_is_gambling_operator=true:
    if is_gambling_operator:
        deduction = cfg["graduated_deductions"]["gambling_operator"]
        score += deduction
        breakdown["graduated_deductions"].append({"signal": "gambling_operator", "points": deduction})
```
Fix: delete this `if is_gambling_operator:` block entirely (D-03 removes the deduction
outright — gambling contributes 0, same as any other non-scored boolean). Do this in the
**same commit** as the config-key deletion (Pitfall 3 in RESEARCH.md) — never split across
two tasks.

---

### `scripts/simulate_rubric_weights.py` (CREATE — script, reads-only)

**Analog:** `scripts/run_scoring_parity.py` (465 lines, read in full)

Copy these concrete patterns verbatim in shape (adapt names/comparison logic):

**Portal guard + credentials guard** (lines 53-56, 136-141):
```python
EXPECTED_PORTAL_ID = "22617666"

def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))

def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID
```

**Sample-ID selection — the authoritative "the 66" query** (lines 149-165, `_select_sample_ids`):
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
Reuse this exact query (per RESEARCH.md Open Question 1) as the simulation's row set —
do not invent a second definition of "the scored population." Diff the result against
`.planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-final-population.json`'s
66 IDs and record any divergence as a finding, not silently.

**Read path — reuse the shared fixture, do not build a new fetch loop:**
```python
from tests.scoring_fixtures import fetch_for_parity
props = fetch_for_parity(company_id)   # GET-only, FIT_SCORE_PROPS slice
```

**The two-scores-per-company core (net-new logic, no analog — this is the simulation's
actual job)**, built on the `cfg=None` extension:
```python
from src.icp_scoring import compute_icp_score
from src.schemas import HubSpotRecord

record = HubSpotRecord(object_type="companies", id=company_id, properties=props)
before = compute_icp_score(record, {})                 # current live weights (cfg=None)
after = compute_icp_score(record, {}, cfg=proposed_cfg) # proposed weights, never written to disk
```

**Zero-write proof — this script must NEVER import a write function.** Contrast with
`run_scoring_parity.py`'s own opt-in write path (`--write-breakdown` → `patch_record`,
lines 344-351) — the simulation script must have **no** `patch_record` / `create_record`
/ `batch_update_companies` import reachable anywhere, satisfying D-08 and RUBRIC-02
structurally, not just by docstring claim.

**Report-emit pattern** (lines 413-420, `_write_report`):
```python
def _write_report(report: dict) -> Path:
    report_dir = Path(os.getenv("PARITY_REPORT_DIR", str(DEFAULT_REPORT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = report_dir / f"parity-report-{date_stamp}.json"
    with path.open("w") as f:
        json.dump(report, f, indent=2, default=str)
    return path
```
Adapt to also emit the D-09 markdown (per-company before/after score+tier, tier-distribution
summary, D-10 annotation flags for the 17 false-veto / 18 blank-org_type rows) — the JSON
verdict shape is reusable scaffolding, the markdown content is net-new per D-09.

**False-green guard pattern** (lines 366-372) — worth carrying into the simulation's own
verdict, though the simulation isn't a pass/fail sweep the way parity is:
```python
if assertions_executed == 0:
    verdict = "FAIL: zero assertions executed. ..."
    exit_code = 1
```

---

### `tests/test_simulate_rubric_weights.py` (CREATE — the RUBRIC-02 no-write test)

**Analog:** `tests/test_scoring_parity.py`'s offline tier — `build_report()` called
directly with a stubbed `fetch_fn`, no network reachable (pattern demonstrated by
`run_scoring_parity.py`'s own `build_report(sample_ids, fetch_fn=fetch_for_parity, ...)`
signature, lines 267-268, designed exactly for this kind of offline unit test).

Concrete assertion shape to copy: a static/import-based no-write proof, per RESEARCH.md's
Wave 0 gap note ("new test asserting the simulation script's HTTP layer is GET-only / no
`patch_record`/`batch_update_companies` import reachable") — e.g. inspect
`simulate_rubric_weights.__dict__` / module source for absence of those names, or run the
simulation against a stubbed `fetch_fn` and assert no write-capable function object is
ever invoked.

---

### `tests/test_icp_scoring.py` (MODIFY — 2 literal sites, verified by direct execution in RESEARCH.md)

Analog: itself. Exact fixes:
```python
# line ~48-59, test_case_3_au_individual_club_tier_c
# current: individual_club_team + 1-5M revenue -> asserts score == 35, tier == "C"
# under D-01: score becomes 45, tier becomes "B" — update literals, consider renaming
# _tier_c -> _tier_b or adding a sibling case.
```
```python
# line ~93
# current: assert {"signal": "gambling_operator", "points": -20} in r.breakdown["graduated_deductions"]
# under D-03: this entry no longer exists at all (deduction block removed) — update/remove.
```

---

### `tests/test_scoring_parity.py` (MODIFY — 3 sites, per RESEARCH.md's Rule 1 Fallout table)

| Site | Fix |
|---|---|
| lines 553-575, `test_run_scoring_parity_classifies_needs_review_as_documented_divergence` | literal stub `"lv_icp_fit_score": "15"` → `"25"` (individual_club_team AU no-revenue-band case moves 15→25 under D-01) |
| lines 134-144, `test_gambling_deducts_20_without_veto_offline` | rewrite to assert gambling contributes 0, or delete if the concept is retired (currently reads `CFG["graduated_deductions"]["gambling_operator"]`, which will `KeyError` at collection time once the key is gone) |
| lines 341-358 (+ alias `test_f9_gambling_conflation` line 511-514) | `assert props.get("gambling_score") == "-20"` → `== "0"` once flow `4634822085` is edited |

**Safe, no fallout** (do not touch): `test_org_type_sweep_offline_matches_config`,
`test_engine_06_org_type_sweep_offline`, `test_org_type_sweep` (live) — all
fixture-driven off `ORG_TYPE_POINTS = CFG["base_score"]["org_type"]`, self-updating.
`test_blank_region_is_not_vetoed_offline` (lines 191-213) stays green — recomputed score
under D-01 is 35, still inside the C band (15-39).

---

### `tests/test_flow_rubric_conformance.py::test_gambling_flow_matches_rubric` (MODIFY — lines 165-190)

**Analog:** itself + its sibling `test_org_type_flow_matches_rubric` (lines 111-135,
**needs zero changes** — self-updating off `load_rubric()["base_score"]["org_type"]`).

Current code that will `KeyError` once `graduated_deductions.gambling_operator` is
deleted:
```python
rubric_deduction = load_rubric()["graduated_deductions"]["gambling_operator"]
scores = extract_true_default_scores(flow, "lv_is_gambling_operator")
assert scores["true"] == rubric_deduction, (...)
assert scores["__default__"] == 0, (...)
```
Rewrite to assert **both** branches score 0 directly (no longer reads from a removed
config key) — this test's job becomes "the gambling flow writes zero on both branches,"
matching D-03's edit to `config/hubspot_flows/gambling-score.after.json`.

`test_org_type_flow_matches_rubric` is the pattern to mirror for confirming the org-type
flow's `regulator` branch reads `-20` post-edit — no test-code change needed there, it
already asserts `points == rubric_org_type[branch_value]` for every branch.

---

### HubSpot flow edits (`config/hubspot_flows/4626124224-org-type-score.after.json`, `gambling-score.after.json`)

**Analog / protocol:** `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`
— documents the exact prior live edit of the **same** `regulator`/`gambling_operator`
branches on the same flow (mutating `"0"` → `"5"` and `"-20"` → `"0"` respectively, per
RESEARCH.md Open Question 5). Tooling: `scripts/fetch_hubspot_flow.py` (archive-before) /
`scripts/put_hubspot_flow.py` (two-key-gated PUT). Protocol order: disable → edit →
PUT → enable → validate → **read-back the running (not merely stored) content** → confirm
→ re-archive as `.after.json`. A bare PUT never reloads a running workflow (memory note
`n8n-stored-vs-running-content` — same failure class applies to Automation v4 flows per
D-12/Pitfall 4).

**Data flow classification:** this is a **write-to-HubSpot** operation, but it writes
flow *definitions*, not record data — distinct from D-08's "simulation writes nothing to
any HubSpot record" constraint, which governs `scripts/simulate_rubric_weights.py` only.
Do not conflate the two.

---

### `46-DECISION.md` (CREATE — decision-record)

**Analog:** `.planning/milestones/v0.7-phases/39-path-decision-fit-score-verification/39-DECISION.md`
(181 lines, read in full). Section structure to replicate exactly (per RESEARCH.md's
explicit mapping):

1. **Verdict** — decided value(s), decision date, portal id.
2. **How the verdict was reached** — per-weight, evidence vs. override.
3. **Rationale** — cites `docs/business/icp-scoring.md` without re-deriving it; states
   explicitly where the decision overrides the evidence (D-14).
4. **Rejected alternatives** — weight values not chosen (10/20/30 for club; the
   graduated-deductions-key shape for regulator, per Open Q5).
5. **What this shapes downstream** — forward pointers to Phase 47/48/49.
6. **Assumptions carried into the verdict** — include the Open-Question-1/2 live-recheck
   caveat explicitly (population snapshot is dated, decision record is dated).
7. **Re-check procedure** — how a future phase re-verifies this decision.
8. **Process note** — any deviation from the plan's literal task order, recorded honestly.
9. **Evidence index** — table of every supporting artifact, including the simulation's
   committed markdown output and the parity-report JSON.

`39-DECISION.md` also models D-14's required tone: states its override plainly without
editing the superseded evidence out of the record — copy that voice, not just the section
headers.

---

## Shared Patterns

### Portal-ID guard before any network call
**Source:** `scripts/run_scoring_parity.py:53-56, 140-141`, `tests/scoring_fixtures.py:24, 73-74`
**Apply to:** `scripts/simulate_rubric_weights.py` and any script touching live HubSpot data.
```python
EXPECTED_PORTAL_ID = "22617666"  # hard-coded, no env override
def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID
```

### Shared oracle-comparison building block
**Source:** `tests/scoring_fixtures.py::fetch_for_parity` / `expected_for`
**Apply to:** Both `scripts/simulate_rubric_weights.py` and any test needing "what does
the oracle say about this live record." Do not re-implement a fetch/compute loop — import
these two functions directly, same as `run_scoring_parity.py` already does.

### False-green / zero-assertions guard
**Source:** `scripts/run_scoring_parity.py:366-372` (`assertions_executed == 0` → FAIL)
**Apply to:** The simulation's own verdict output — a run with an empty sample must never
silently look like "nothing changed."

### Flow-edit protocol (disable → edit → PUT → enable → validate → read-back running → re-archive)
**Source:** `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`
**Apply to:** Both `4626124224-org-type-score` and `gambling-score` flow edits. Never
treat a green `test_flow_rubric_conformance.py` (which reads the committed archive, never
GETs the portal) as proof the live flow was actually updated — that test proves
config↔archive agreement only (Pitfall 4).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Simulation markdown report content (per-company before/after + D-10 annotation) | doc / generated artifact | reads-only output | No prior "before/after simulation report" exists in this repo (RESEARCH.md's "Don't Hand-Roll" table confirms — searched `.planning/` exhaustively). Shape can borrow `run_scoring_parity.py`'s JSON-report scaffolding, but the markdown content and the D-10 flagging logic are net-new. Recommend scoping the "publish as artifact" half of D-09 as a `checkpoint:human` task, not a script (no prior art for a coded publish step). |

## Metadata

**Analog search scope:** `scripts/`, `src/`, `tests/`, `config/`, `.planning/milestones/v0.7-phases/`
**Files scanned:** ~15 (all named directly in RESEARCH.md's Sources section, cross-read this session)
**Pattern extraction date:** 2026-08-11
