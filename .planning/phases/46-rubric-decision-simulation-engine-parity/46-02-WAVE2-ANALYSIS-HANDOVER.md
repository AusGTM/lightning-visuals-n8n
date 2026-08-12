# Wave 2 (46-02) implementation analysis — handover

**Author:** advisory session (not the executing session). Peer session `uds:/tmp/cc-socks/58001.sock`
owns Phase 46 execution and received this same content by message on 2026-08-11.
**Not a GSD artifact.** Advisory only — 46-02-PLAN.md remains the contract.

## Session state

- Repo untouched by this session. `git status` at handover: ` M .DS_Store`, `?? .gsd/` (both
  pre-existing). No commits, no code edits.
- Last repo commit: `aa7622e docs(46-01): complete rubric decision foundations plan`.
- Wave 1 (46-01) is sealed and committed. Wave 2 is **not started** — no code written.
- Scratchpad copy of this analysis:
  `/private/tmp/claude-501/-Users-robertli-Desktop-consulting-lightning-visuals-lv-n8n-poc/1231a34a-9e0f-4ba2-ac65-c64e428eb1df/scratchpad/wave2-impl-analysis.md`

## Filename / task mapping

Plan file is `46-02-PLAN.md` (not `46-PLAN-02.md`). It has **2 tasks**, not 4:

| Peer's framing | Plan's task |
| --- | --- |
| 1 row selection, 2 markdown report, 3 CLI | Task 1 (all code + tests) |
| 4 live simulation | Task 2 (live run + commit report) |

Anchor the summary to the plan's numbering.

## Files read to produce this

`46-02-PLAN.md`, `46-PATTERNS.md`, `scripts/simulate_rubric_weights.py` (147 lines),
`scripts/run_scoring_parity.py`, `tests/scoring_fixtures.py`,
`tests/test_simulate_rubric_weights.py`, `src/icp_scoring.py`.

## Hard constraints — tests go red if violated

1. **Five forbidden tokens** anywhere in `scripts/simulate_rubric_weights.py`'s source text,
   docstrings/comments/string literals included: `patch_record`, `create_record`,
   `delete_record`, `batch_update_companies` (static text scan in
   `test_zero_write_static_scan_finds_no_write_import`) plus `june_candidates` (plan
   acceptance criterion). A comment saying "we deliberately do not read june_candidates.json"
   fails the grep.
2. **Fetch exactly once per id, in order.** Plan 01's behavioural stub asserts `calls == ids`.
   All four scorings per row (oracle-current, proposed@15, @10, @20) must reuse ONE fetched
   props dict. A per-scenario refetch loop breaks a test that may not be changed.
3. **`main()` signature and return shape are frozen**: `main(ids, fetch_fn, current_cfg,
   proposed_cfg) -> (report, exit_code)` with `report["rows"]` a list. Delegate to
   `build_simulation`; pass the richer payload through under the same keys. Add a separate
   `cli(argv=None) -> int` for argparse; `sys.exit(cli())` in `__main__`.
4. `git diff config/icp_scoring.yaml` stays empty through this wave.

## Task 1 — row selection

`_select_row_ids()` mirrors `run_scoring_parity.py:149-165` on semantics: explicit id list
first (env `SIMULATE_ROW_IDS` or `--ids`), else
`search_records("companies", [{propertyName: "lv_icp_fit_score", operator: "HAS_PROPERTY"}], [...], limit=100)`,
with `from src.hubspot_client import search_records` imported **locally** so unit callers never
pull it.

**Deviation to record:** request `["name", "lv_icp_fit_score"]` in the search properties and
return `(ids, name_map)`. `fetch_for_parity` returns only the `FIT_SCORE_PROPS` slice and
`name` is not in it; the plan forbids adding to that list, so the search response is the only
compliant source of company names — and it costs zero extra calls. Selection semantics
unchanged, only the return shape. On the `--ids` path there is no search, so names are blank —
"name where available" permits this.

Cross-check only:
`.planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/41-final-population.json`
is a dict keyed by company id → `set(json.keys())`. Carry both counts + the symmetric
difference as a finding field. Never a source.

## Task 1 — overrides / scenarios

```python
def _overrides_for(club_weight):
    return [
        ("base_score.org_type.individual_club_team", club_weight),  # D-01
        ("base_score.org_type.regulator", -20),                     # D-02 direct weight
        ("graduated_deductions.gambling_operator", None),           # D-03 delete key
    ]

PROPOSED_OVERRIDES = _overrides_for(15)
SCENARIOS = [club_weight 10, 15, 20]  # nothing else differs
```

D-02 is a direct negative weight in the existing `base_score.org_type` map, **not** a new
`graduated_deductions` key. `_set_dotted(value=None)` pops the leaf, so D-03 adds no key.
`src/icp_scoring.py:101` already `.get`-chains the gambling lookup, so a deleted key scores 0
and appends no breakdown entry — Plan 01 already tests both directions.

Arithmetic verified against `src/icp_scoring.py`:

- regulator + AU + content + 1-5M: `-20 + 20 + 10 + 0 = 10` → **Unscored** (below the C floor
  of 15; no Needs-Review downgrade because `org_type` is known and content is not None)
- gambling AU governing body 5-50M: 60 → **80** (+20)
- club AU content 1-5M: 35/C today; **30/C @10, 45/B @15, 40/B @20** — the Tier-B-floor
  sensitivity the operator needs before sign-off

## Task 1 — build_simulation + D-10 flags

`build_simulation(ids, fetch_fn, current_cfg, scenarios, name_map=None, crosscheck_ids=None)`
returns a payload carrying: `run_utc`, `portal_id`, `proposed_overrides` (literal, as applied),
`rows` (company_id, name, lv_org_type, flags[], live_score/tier, oracle_current_score/tier,
oracle_proposed_score/tier, sensitivity{club-10, club-20}), `distribution` per scenario,
`movement`{changed, by_org_type}, `row_set_finding`{live_count, snapshot_count, only_live,
only_snapshot}, `verdict`.

Flags — both derived from properties already in `FIT_SCORE_PROPS`; add nothing to that list:

- `blank_org_type` — `lv_org_type` missing or empty
- `false_veto` — `str(props.get("lv_anti_icp_flag")) == "true"` AND `"non-anz" in
  (lv_anti_icp_reason or "").lower()` AND `lv_country_region_normalized` blank/None.
  Use the **string** `"true"` in stubs — HubSpot returns everything as strings
  (`run_scoring_parity.py:209 _flag_matches`).

Zero rows → failure verdict + exit 1, carried through `build_simulation` (Plan 01's guard
currently lives in `main`).

## Task 2 — render_markdown(payload)

Bake every prose obligation into the template so the live run inherits it; do not leave these
as Task-2 authoring steps:

1. Header: UTC timestamp, portal `22617666`, actual row count. If the count is not 66, say so
   prominently and never call it "the 66".
2. Plain-language paragraph explaining what the three score columns mean.
3. Row-set cross-check stated explicitly, including the sets-match-exactly case.
4. Per-company table with a visible flag column — flags in the table, not a footnote.
5. Fixed D-10 statement: flagged rows shown as-is, no projected column; the 17 false-veto rows
   are Phase 47's scope, the 18 blank-org_type rows are Phase 48's.
6. D-06 supersession note: the direct-weight shape for D-02 resolves CONTEXT.md's "Claude's
   Discretion" bullet and supersedes D-06's "new engine logic" framing (Open Q5).
7. Tier distributions (live / oracle-current / proposed) plus sensitivity tier counts @10, @20.
8. Movement summary broken down by `lv_org_type`.

Write it so Phase 49's RESCORE-03 before/after lifts straight out.

`_write_report(payload, out_dir)` → `46-simulation-{YYYYMMDD}.json`, following
`run_scoring_parity.py:413-420` (mkdir parents, UTC date stamp, `json.dump(indent=2,
default=str)`).

## Task 3 — CLI

`cli(argv=None) -> int`: `--ids` comma-separated (env `SIMULATE_ROW_IDS` as the alternate),
`--out-dir` defaulting to the phase dir, credential + portal guards before any call (portal
mismatch → refuse, exit 1, no API call made).

## Test contracts — tests/test_simulate_rubric_weights.py

Deliberately change (the test's own docstring says Plan 02 does this):

- `test_proposed_overrides_carries_only_d01_this_task` → rename, assert all three entries
- `test_blank_org_type_contributes_zero_under_both_rubrics` — assertion still passes; fix the
  now-stale docstring line "the proposed rubric only reweights individual_club_team"

Preserve byte-identical: the three zero-write tests, the write-capable enumeration pin, the
two-positional-arg compat test.

Add:

1. three-column separation preserved when the oracle disagrees with the live tier (false-veto shape)
2. blank-`lv_org_type` row flagged AND scores 0 org-type points under both rubrics
3. regulator row → 10 / Unscored under proposed
4. gambling row → +20 under proposed
5. empty row set → failure verdict + non-zero exit
6. row-set divergence finding populated when stub ids differ from the cross-check list
7. fetch called exactly once per id despite four scorings

Verify: `.venv/bin/python -m pytest tests/test_simulate_rubric_weights.py -q`, then
`.venv/bin/python -m pytest -q`.

## Task 4 — live run

Precondition: token present AND `HUBSPOT_PORTAL_ID == 22617666` after `load_dotenv()`.
`.env` is Read/Bash permission-blocked, so drive it as:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; \
  runpy.run_path('scripts/simulate_rubric_weights.py', run_name='__main__')"
```

No arming flag exists and none should be invented — the run is read-only. On credential or
portal failure: HALT and surface the blocker. Do **not** fall back to
`41-final-population.json` or the June snapshot.

## Resuming

1. Confirm the peer session's Wave 2 progress before writing code — it may already be mid-Task 1.
2. If starting fresh: `/gsd-execute-phase 46` or execute `46-02-PLAN.md` directly.
3. This file is advisory. Delete it once 46-02-SUMMARY.md lands, or leave it as review context.
