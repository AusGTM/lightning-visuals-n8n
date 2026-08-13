# Phase 50: Derived Tier Property - Pattern Map

**Mapped:** 2026-08-13
**Files analyzed:** 9 (5 new scripts/tests, 4 modified config/artifact files)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tests/test_tier_formula_pin.py` | test | transform (offline pin) | `tests/test_rubric_change_guard.py` | exact |
| `scripts/check_tier_null_propagation.py` | utility/script | file-I/O + live probe (create/PATCH/archive) | `scripts/rollback_property_migration.py` + `scripts/derive_orphan_candidates.py` (archive/404 verify) + `scripts/sync_hubspot_properties.py` (two-key gate) | role-match (composite) |
| `scripts/check_tier_derived_parity.py` | utility/script | batch/CRUD (read-only compare) | `scripts/rescore_population.py` (population selection) + `scripts/build_rescore_report.py` (evidence artifact) | role-match |
| `scripts/sweep_tier_dependents.py` | utility/script | batch (read-only API enumeration) | `scripts/check_hubspot_list_scope.py` (Lists API) + `scripts/fetch_hubspot_flow.py` (Flows API) | role-match |
| `scripts/check_schema_drift.py` (MODIFY) | utility/script | transform (comparator) | itself — edit `DO_NOT_ARCHIVE_*` structures in place | exact (self) |
| `config/hubspot_properties.yaml` (MODIFY) | config | declarative | itself, `lv_icp_fit_score` declaration as template | exact (self) |
| `config/hubspot_flows/lv_icp_tier_derived-property.{before,after}.json` (ADD) | config/snapshot | file-I/O | `config/hubspot_flows/lv_icp_fit_score-property.after.json` | exact |
| `config/hubspot_flows/4625147345-wf1-set-icp-tier.{before,after}.json` (MODIFY — refresh `.after.json`) | config/snapshot | file-I/O | `scripts/fetch_hubspot_flow.py::archive_flow` (before/after snapshot convention) | exact |
| `.planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md` (ADD) | doc/evidence artifact | transform (report render) | `.planning/phases/49-re-score-strategy-reporting/49-RESCORE-REPORT.md` + `scripts/build_rescore_report.py` | exact |

## Pattern Assignments

### `tests/test_tier_formula_pin.py` (test, offline pin)

**Analog:** `tests/test_rubric_change_guard.py` (full file read; 162 lines)

**Structure to copy verbatim (adapt the pinned literal + comparison target):**
- Module docstring names the phase/decision id, states *why* re-baselining requires a real action (here: re-running D-07's parity gate, not merely editing the literal), and states "Offline only: no network, no HubSpot credentials."
- `ROOT`/`RUBRIC_PATH` constants via `Path(__file__).resolve().parent.parent`.
- A `PINNED_*` module-level dict literal — for Phase 50 this pins the derived `calculationFormula` string (or its parsed ladder) against `config/icp_scoring.yaml`'s `tier_rules` (lines 55-83 per RESEARCH.md, quoted below), not the base_score weights.
- `_diff_keys(pinned, actual)` — key-by-key diff helper, "so the failure message can name exactly what moved."
- `assert_rubric_pinned(config)` → rename `assert_tier_formula_pinned(...)`, raising `AssertionError` listing offending keys plus a pointer to the re-verification obligation (here: re-run `scripts/check_tier_derived_parity.py`, not `docs/OPERATOR-RESCORE.md`).
- Three tests: `test_pinned_*_matches_current_config` (passes today), `test_mutated_*_fails_the_guard` (parametrized mutation cases proving the guard has teeth), `test_failure_message_names_*` (asserts the raised message contains the pointer).

**tier_rules source of truth to pin against** [VERIFIED: `config/icp_scoring.yaml:55-83`, quoted in RESEARCH.md]:
```yaml
tier_rules:
  A: { min_score: 70, max_score: 999, requires_no_hard_veto: true }
  B: { min_score: 40, max_score: 69, requires_no_hard_veto: true }
  C: { min_score: 15, max_score: 39, requires_no_hard_veto: true }
  D: { hard_veto: true }
  Unscored: { missing_required_inputs: true }
```

**The accepted ladder to pin as the formula literal** [SETTLED: `.planning/TIER-DERIVATION-SPIKE-2026-08-13.md`, Round 2, quoted verbatim in RESEARCH.md Pattern 1]:
```
if coalesce(lv_anti_icp_flag, 0) = 1 then "D"
elseif lv_icp_fit_score >= 70 then "A"
elseif lv_icp_fit_score >= 40 then "B"
elseif lv_icp_fit_score >= 15 then "C"
else "Unscored"
```
(D-04 may force `coalesce(lv_icp_fit_score, -1)` in place of the bare reference — the test must pin whichever variant D-05's live probe settles on, and should be written so the literal is easy to swap once that answer is known.)

---

### `scripts/check_tier_null_propagation.py` (D-05's fresh two-key-gated live probe)

**Analogs (composite — no single existing file matches all three needs):**

**1. Two-key write gate** — `scripts/sync_hubspot_properties.py` lines 1-58 (module docstring + `_writes_allowed()`):
```python
# Same idiom as scripts/snapshot_hubspot_schema.py / src/hubspot_client.py: env-gated,
# dry-run-by-default, `_has_credentials()` skip-to-exit-0. This is the FIRST schema-mutating
# script in the repo, so it uses a stronger TWO-KEY write gate than hubspot_client's single
# DRY_RUN gate: a POST is refused unless BOTH DRY_RUN=false AND
# ALLOW_HUBSPOT_PROPERTY_WRITES=true.

def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow
```
Per D-05, this script needs its **own** allow-key (not `ALLOW_HUBSPOT_PROPERTY_WRITES`, which is scoped to `sync_hubspot_properties.py`'s migration) — e.g. `ALLOW_TIER_NULL_PROBE=true`, mirroring the naming convention `ALLOW_VETO_REMEDIATION` / `ALLOW_SCORE_BACKFILL` already establish (one allow-key per script, named for what it does).

**2. Dotenv-invocation docstring (verbatim boilerplate — `.env` is Read/Bash permission-blocked)** [from `scripts/rescore_population.py` docstring, same idiom in `scripts/check_schema_drift.py`]:
```
`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    ALLOW_TIER_NULL_PROBE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/check_tier_null_propagation.py', run_name='__main__')"
```
(`scripts/check_schema_drift.py`'s variant additionally shows the `sys.argv` pre-seed idiom for scripts that take `--out`/other flags — copy that shape if the probe needs argparse flags.)

**3. Create-disposable → PATCH → archive-in-`finally` → verify-gone-by-404 teardown** — composite of:

`scripts/rollback_property_migration.py:120-133` (404-tolerant GET + archive call):
```python
def _get_property_live(object_type: str, name: str):
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}", headers=hs_headers(), timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def _archive_property_live(object_type: str, name: str) -> int:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.delete(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}", headers=hs_headers(), timeout=30)
    return r.status_code
```
Use `_get_property_live(...) is None` as the "verified gone by 404 re-read" check the probe must perform after archiving both disposables (the disposable calculated property AND the disposable numeric property AND the disposable company record, per RESEARCH.md Q4's minimal test).

`scripts/derive_orphan_candidates.py:290-330` (`archive_property`) — the belt-and-braces re-check-immediately-before-mutation pattern and the "define the guard rails before the DELETE, not just before the loop" discipline; also demonstrates writing the pre-archive definition to a dated archive dir before deleting, which the probe should do for its disposable property/company for auditability even though they're throwaway.

`scripts/fetch_hubspot_flow.py:86` (`archive_flow`) — before/after snapshot pairing convention if the probe wants to log its disposable property's state; not required here since this is genuinely disposable, but useful if D-17 item 4's evidence artifact should reference the probe's own result.

**Minimal test steps this script performs** [RESEARCH.md Q4, exact]:
1. Create disposable calculated string property (accepted 7/7 ladder formula, referencing a disposable numeric property standing in for `lv_icp_fit_score`).
2. Create a disposable company with that numeric property left null (never set, not zero).
3. Read the calculated property back: blank → null propagates through untaken branch → ship `coalesce(..., -1)` (D-04); `"Unscored"` → uncoalesced (D-03) works.
4. Archive both disposables in a `finally` block; verify gone via `_get_property_live(...) is None` / company re-GET 404.
5. **No company record from the live population is touched** — this script only ever creates/deletes disposables it created itself in the same run.

---

### `scripts/check_tier_derived_parity.py` (D-07's gate — diffs derived vs WF1 across all 66)

**Analog:** `scripts/rescore_population.py` lines 1-40 (module docstring shape: population re-derived live every invocation, never trusted from a stale local snapshot) + `scripts/build_rescore_report.py` (evidence-artifact renderer, D-17 item 4's "evidence artifact, not a test" framing).

**Population selection pattern to copy** — `select_scored_population()`-equivalent, re-derived live every run via the same `HAS_PROPERTY(lv_icp_fit_score)` search shape `run_scoring_parity.py` / `simulate_rubric_weights.py` / `rescore_population.py` already share. This script performs a batch READ (never a write — D-16 declares zero company write windows), comparing `lv_icp_tier` (live) against `lv_icp_tier_derived` (live, once created) per company, and separately flags the 4 known stuck IDs (`9605273630`, `9604738976`, `17696004613`, `19100977027` — RESEARCH.md Code Examples table) as the one class **expected** to mismatch (`C` vs `B`).

**Output shape** — model on `scripts/build_rescore_report.py`'s renderer: consumes committed/live-read data, produces a deterministic markdown report (sorted by record id per Phase 49's ordering-edge test), written to `50-TIER-PARITY-EVIDENCE.md`. This is explicitly **not** a pytest assertion (D-17 item 4) — it's evidence, matching `49-RESCORE-REPORT.md`'s role.

---

### `scripts/sweep_tier_dependents.py` (D-13's read-only, re-runnable dependent sweep)

**Analogs:**
- `scripts/check_hubspot_list_scope.py` — Lists API calls: `GET {BASE}/crm/v3/lists/object-type-id/{...}` and `GET {BASE}/crm/v3/lists/{list_id}/memberships`. Reuse for enumerating company lists and grepping filter branches for `lv_icp_tier`.
- `scripts/fetch_hubspot_flow.py` — Flows API enumeration/snapshot pattern (`GET /automation/v4/flows`, batch read), same convention already used for `config/hubspot_flows/*.json` snapshots. Grep flow bodies for `lv_icp_tier` references.

**Structure:** read-only, no `requests.{post,patch,delete}` calls anywhere (mirrors `check_schema_drift.py`'s own "GET only" self-description and build-time grep enforcement). Must be re-runnable (D-13) — output a fresh report each invocation, never diffed against a cached prior run as the source of truth. Must also emit a place for the **manual, UI-only** findings (saved views, reports/dashboards — no public API, RESEARCH.md Q3) to be logged alongside the scripted results, since D-13's artifact needs both halves in one place.

---

### `scripts/check_schema_drift.py` (MODIFY — Pitfall 2's `DO_NOT_ARCHIVE_*` edit)

**This is a self-edit, not a new-file/analog situation.** Exact current structures to modify [VERIFIED: `scripts/check_schema_drift.py:68-91`]:

```python
DO_NOT_ARCHIVE_COMPANY_PROPERTIES = frozenset({
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
    "lv_icp_fit_score",
    "lv_icp_tier",              # <-- must be removed once lv_icp_tier is archived (D-06)
    "lv_anti_icp_flag",
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
})

DO_NOT_ARCHIVE_FLOW_IDS = {
    "4626124224": "org-type-score",
    "4626722240": "geography-score",
    "4626722237": "annual-revenue-score",
    "4625147345": "wf1-set-icp-tier",   # <-- flips is_enabled=False once WF1 is switched off (D-08)
    "4634822079": "produces-content-score",
    "4634822085": "gambling-score",
}
```

And the `ok` computation that currently cannot express "kept but deliberately off" [VERIFIED: lines ~231-246]:
```python
def _compute_do_not_archive(live_companies_by_name: dict, live_flows_by_id: dict) -> dict:
    properties = [
        {"name": name, "live": name in live_companies_by_name}
        for name in sorted(DO_NOT_ARCHIVE_COMPANY_PROPERTIES)
    ]
    flows = []
    for flow_id, slug in DO_NOT_ARCHIVE_FLOW_IDS.items():
        live_flow = live_flows_by_id.get(flow_id)
        flows.append({
            "id": flow_id,
            "slug": slug,
            "live": live_flow is not None,
            "is_enabled": bool(live_flow.get("isEnabled")) if live_flow else False,
        })
    ok = all(p["live"] for p in properties) and all(f["live"] and f["is_enabled"] for f in flows)
    return {"properties": properties, "flows": flows, "ok": ok}
```
`exit_code_for()` [lines ~219-228] returns `2` whenever `report["do_not_archive"]["ok"]` is `False` — the phase's own successful D-06/D-08 steps must not trip this. **This edit must land in the same commit as the archive/disable actions** (Pitfall 2 in RESEARCH.md) — remove `"lv_icp_tier"` from the frozenset, and either remove `"4625147345"` from the flow dict or give the `f["is_enabled"]` conjunction a third state ("deliberately off, not missing") so a kept-but-disabled WF1 doesn't read as damage. `ACCEPTED_DIVERGENCES` (lines ~119-136, the `PARITY-01-tier-label` entry) is the existing convention for exactly this kind of "known, documented, non-failing divergence" annotation — likely reusable for documenting the retired-property state too.

---

### `config/hubspot_properties.yaml` (MODIFY, declaration ~line 408) + snapshot files

**Analog / literal template:** `config/hubspot_flows/lv_icp_fit_score-property.after.json` (full file) [VERIFIED, quoted in RESEARCH.md Pattern 2]:
```json
{
  "calculated": true,
  "calculationFormula": "org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)",
  "fieldType": "calculation_equation",
  "formField": false,
  "groupName": "companyinformation",
  "hasUniqueValue": false,
  "label": "ICP Fit Score",
  "modificationMetadata": {
    "archivable": true,
    "readOnlyDefinition": false,
    "readOnlyValue": true
  },
  "name": "lv_icp_fit_score",
  "type": "number"
}
```
For `lv_icp_tier_derived`: mirror every field except `type` (`string`, not `number`) and `calculationFormula` (Pattern 1's ladder above). `groupName: companyinformation` matches the existing `lv_icp_tier` declaration's group. `modificationMetadata` is response-only — do not set it in the create request (RESEARCH.md A1).

**Snapshot convention** — `config/hubspot_flows/{name}-property.{before,after}.json` pairing already established for `lv_icp_tier-property.*.json` and `lv_icp_fit_score-property.after.json`; create `lv_icp_tier_derived-property.before.json` (absent/empty — property doesn't exist yet) and `.after.json` (post-create live read-back), and refresh `lv_icp_tier-property.after.json` once archived, and `4625147345-wf1-set-icp-tier.after.json` once `isEnabled` flips to `false` (`scripts/fetch_hubspot_flow.py::archive_flow` is the existing tool that produces these snapshots for flows).

---

### `.planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md` (D-17 item 4)

**Analog:** `.planning/phases/49-re-score-strategy-reporting/49-RESCORE-REPORT.md`, built by `scripts/build_rescore_report.py`, per plan `49-07-PLAN.md`'s `must_haves.truths`:
- Distributions must sum exactly to the population count recorded alongside them (renderer raises rather than silently renders on mismatch).
- Sort deterministically by record id for reproducible re-renders.
- State up front what fraction of the portal the population represents.
- Carry an explicit "what this does not say" limits block.
- D-19 calls for reusing this exact three-point-distribution report format for the operator-facing before/after tier census (pre-registered expectation: identical distribution except 4 records C→B — a distribution differing anywhere else is itself the defect signal, same "report as a test" posture `49-07`'s objective states).

## Shared Patterns

### Dotenv-wrapper invocation (verbatim, for every new script here)

`.env` is Read/Bash permission-blocked; every script's docstring/usage section ends with this exact idiom [from `scripts/check_schema_drift.py` and `scripts/rescore_population.py`]:
```
`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['{script_name}.py', '--out', 'PATH/TO/report.json']; \
         runpy.run_path('scripts/{script_name}.py', run_name='__main__')"
```
For an armed script (`check_tier_null_propagation.py`), prefix the env vars before `.venv/bin/python`, matching `rescore_population.py`'s `ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c ...` shape.

### Two-key write gate (D-05, D-16)

Every script in this repo that can mutate HubSpot gates on `DRY_RUN=false` (repo-wide) AND its own dedicated allow-key (`ALLOW_HUBSPOT_PROPERTY_WRITES`, `ALLOW_VETO_REMEDIATION`, `ALLOW_SCORE_BACKFILL`, ...). `check_tier_null_propagation.py` needs its own new key, e.g. `ALLOW_TIER_NULL_PROBE`. Source: `scripts/sync_hubspot_properties.py::_writes_allowed()`, `scripts/remediate_veto_companies.py` lines 250-251.

### Portal guard (asserted before any call)

Every schema-touching script asserts the expected portal id first:
```python
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")
def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID
```
[VERIFIED: `scripts/check_schema_drift.py:63,67`; `scripts/sync_hubspot_properties.py:41,46`]

### No-secrets-leaked assertion

Reused verbatim across schema-touching scripts:
```python
def _assert_no_secrets(text: str) -> None:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or ""
    assert "Authorization" not in text, "serializer leaked the Authorization header"
    if token:
        assert token not in text, "serializer leaked the bearer token value"
    assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text, "serializer leaked the token env var name"
```
[VERIFIED: `scripts/check_schema_drift.py:143-148`, itself copied from `scripts/snapshot_hubspot_schema.py:78-83`] — apply anywhere a script writes live-read property/flow JSON to a committed snapshot file.

### No-credentials-skip-to-exit-0

Every schema-touching script checks `_has_credentials()` first and prints "skipped"/exits 0 rather than failing when `HUBSPOT_PRIVATE_APP_TOKEN` is absent — same idiom across `snapshot_hubspot_schema.py`, `sync_hubspot_properties.py`, `check_schema_drift.py`, `fetch_hubspot_flow.py`. Apply to all four new scripts.

### Arm/disarm write-window helper

`scripts/scheduled_arm.py` and `scripts/june_run_arm.py` are the repo's existing armed-write-window helpers (bounded write windows, e.g. Phase 40's 2-record chunk cap). **Not directly reused here** — D-16 declares zero company write windows for the happy path, and D-05's probe writes only disposable, self-created records/properties, not population records, so it does not need the arm/disarm cap machinery `june_run_arm.py` provides. Only relevant if D-18's rollback drill's perturb-then-restore double-write is ever exercised (an emergency-path deviation, not this phase's normal execution).

## No Analog Found

None — every file in the known list has at least a role-match analog in the existing codebase.

## Metadata

**Analog search scope:** `scripts/`, `tests/`, `config/hubspot_properties.yaml`, `config/hubspot_flows/`, `.planning/phases/49-re-score-strategy-reporting/`, `.planning/phases/47.5-veto-recompute-path/`
**Files scanned:** ~20 (read fully or via targeted grep: `test_rubric_change_guard.py`, `check_schema_drift.py`, `sync_hubspot_properties.py`, `remediate_veto_companies.py`, `rescore_population.py`, `build_rescore_report.py` docstring, `rollback_property_migration.py`, `derive_orphan_candidates.py`, `fetch_hubspot_flow.py`, `check_hubspot_list_scope.py`, `49-07-PLAN.md`)
**Pattern extraction date:** 2026-08-13
