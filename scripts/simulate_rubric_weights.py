#!/usr/bin/env python3
"""scripts/simulate_rubric_weights.py

Phase 46 Plan 01 (RUBRIC-02) -- the read-only, in-memory rubric simulation. Scores each
requested company under BOTH the current on-disk rubric (config/icp_scoring.yaml) and a
proposed rubric that exists only in memory (PROPOSED_OVERRIDES applied via
build_proposed_cfg), and reports three columns per company: the live HubSpot
lv_icp_fit_score/lv_icp_tier, the oracle-under-current-config score/tier (the control),
and the oracle-under-proposed-config score/tier (the effect being measured). Three
columns, not two -- the oracle already carries the blank-region veto fix live HubSpot
does not, so a two-column report would misattribute Phase 47's veto fix to this phase's
weight change.

RUBRIC-02 / D-08: this script writes NOTHING to any HubSpot record. It imports no
write-capable src.hubspot_client function -- structurally, not just by docstring claim
(tests/test_simulate_rubric_weights.py's zero-write tests enumerate the write-capable
function set and enforce this two ways: a static source scan and a behavioural stub run).
Contrast with scripts/run_scoring_parity.py's own opt-in --write-breakdown path, which
this script does not replicate.

Read path is fetch_for_parity, imported from tests/scoring_fixtures.py -- no second fetch
loop, and no new property added to FIT_SCORE_PROPS.

Plan 01 Task 2 populated PROPOSED_OVERRIDES with only D-01 (individual_club_team -> 15)
and proved the path on one record. Plan 02 (this revision) adds:
  - D-02 (regulator -> -20, a DIRECT base_score.org_type weight per 46-RESEARCH.md Open
    Question 5's live-executed finding -- not a new graduated_deductions key, superseding
    46-CONTEXT.md D-06's "new engine logic" framing)
  - D-03 (graduated_deductions.gambling_operator deleted outright)
  - SCENARIOS: the primary scenario (club weight 15, byte-identical to PROPOSED_OVERRIDES)
    plus two club-weight-only sensitivity scenarios (10 and 20), so the operator sees how
    close the Tier B floor (40) sits before sign-off
  - _select_row_ids: the live HAS_PROPERTY(lv_icp_fit_score) query, mirroring
    scripts/run_scoring_parity.py::_select_sample_ids exactly -- no second definition of
    "the scored population"
  - a row-set cross-check against the committed
    .planning/milestones/v0.7-phases/41-validation-data-import-end-to-end-proof/
    41-final-population.json snapshot (reference only, per D-08 -- never the simulation's
    source of record data; the June-dated candidate research snapshot named elsewhere in
    this phase's docs is never read by this script at all, under any name)
  - build_simulation / render_markdown / _write_report: the full RUBRIC-02 payload, the
    D-09 markdown deliverable, and its JSON twin
  - D-10 row-level annotation (blank_org_type, false_veto) derived only from properties
    already in tests/scoring_fixtures.py::FIT_SCORE_PROPS

`main()` is kept, unchanged in call shape, as a thin wrapper over build_simulation so
Plan 01 Task 3's zero-write proof (tests/test_simulate_rubric_weights.py) needs no edits.
"""
import argparse
import copy
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`tests.*` imports resolve
                                # regardless of invocation cwd (matches run_scoring_parity.py)

from src.icp_scoring import compute_icp_score, load_yaml  # noqa: E402
from src.schemas import HubSpotRecord  # noqa: E402
from tests.scoring_fixtures import fetch_for_parity  # noqa: E402

RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
DEFAULT_REPORT_DIR = ROOT / ".planning" / "phases" / "46-rubric-decision-simulation-engine-parity"

# 41-final-population.json -- Phase 41's live 66-company snapshot. Cross-check reference
# ONLY (RESEARCH.md Open Q1/Q2) -- never the simulation's row-set source (that is always
# _select_row_ids' live HAS_PROPERTY search or an explicit --ids/env override).
CROSS_CHECK_POPULATION_PATH = (
    ROOT / ".planning" / "milestones" / "v0.7-phases"
    / "41-validation-data-import-end-to-end-proof" / "41-final-population.json"
)

# Portal 22617666 (ap1) -- hard-coded, no env override, asserted before any network call
# (T-46-02, the repo-standard guard every other script here follows: run_scoring_parity.py,
# tests/scoring_fixtures.py).
EXPECTED_PORTAL_ID = "22617666"

# The single auditable statement of every weight this simulation proposes: (dotted config
# path, value) pairs, applied in order by build_proposed_cfg. value=None means "delete
# this key". D-01 (club->15), D-02 (regulator->-20, direct weight -- see module docstring),
# D-03 (gambling deduction deleted). No second weight table exists anywhere else in this
# file or this repo.
PROPOSED_OVERRIDES = [
    ("base_score.org_type.individual_club_team", 15),
    ("base_score.org_type.regulator", -20),
    ("graduated_deductions.gambling_operator", None),
]

# D-01's own sensitivity ask: the club weight is the only axis that varies across
# scenarios. club_15 is the primary -- byte-identical to build_proposed_cfg's output.
# club_10/club_20 are sensitivity-only (tier reported, not a third full score table).
SCENARIOS = [
    {"name": "club_10", "club_weight": 10},
    {"name": "club_15", "club_weight": 15},
    {"name": "club_20", "club_weight": 20},
]
PRIMARY_SCENARIO_NAME = "club_15"

# config/icp_scoring.yaml hard_vetoes.non_anz.reason -- the literal string the oracle
# (and, historically, the live pipeline) writes to lv_anti_icp_reason for a non-ANZ veto.
NON_ANZ_VETO_REASON = "Non-ANZ geography"


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _set_dotted(cfg: dict, dotted_path: str, value) -> None:
    """Applies one PROPOSED_OVERRIDES entry to cfg in place. value=None deletes the leaf
    key instead of setting it."""
    parts = dotted_path.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node[part]
    leaf = parts[-1]
    if value is None:
        node.pop(leaf, None)
    else:
        node[leaf] = value


def build_proposed_cfg(current_cfg: dict) -> dict:
    """Deep-copies current_cfg and applies every PROPOSED_OVERRIDES entry (the primary
    scenario, club weight 15). Never writes to disk, and never mutates current_cfg --
    callers may safely reuse the same current_cfg object across multiple calls."""
    proposed = copy.deepcopy(current_cfg)
    for dotted_path, value in PROPOSED_OVERRIDES:
        _set_dotted(proposed, dotted_path, value)
    return proposed


def build_scenario_cfg(current_cfg: dict, club_weight: int) -> dict:
    """Deep-copies current_cfg and applies every PROPOSED_OVERRIDES entry, except the
    individual_club_team weight is set to club_weight instead of PROPOSED_OVERRIDES' own
    value. build_scenario_cfg(cfg, 15) is byte-identical to build_proposed_cfg(cfg) --
    SCENARIOS' three entries differ only in this one value."""
    proposed = copy.deepcopy(current_cfg)
    for dotted_path, value in PROPOSED_OVERRIDES:
        if dotted_path == "base_score.org_type.individual_club_team":
            value = club_weight
        _set_dotted(proposed, dotted_path, value)
    return proposed


def simulate_row(props: dict, current_cfg: dict, proposed_cfg: dict) -> dict:
    """Builds a HubSpotRecord (object_type="companies", placeholder id -- the id is
    irrelevant to compute_icp_score's scoring logic, same precedent as
    tests/scoring_fixtures.py::expected_for) from a fetched property dict, scores it
    under both cfgs, and returns the three-column comparison row."""
    record = HubSpotRecord(object_type="companies", id="0", properties=props)
    current = compute_icp_score(record, {}, cfg=current_cfg)
    proposed = compute_icp_score(record, {}, cfg=proposed_cfg)
    return {
        "live_score": props.get("lv_icp_fit_score"),
        "live_tier": props.get("lv_icp_tier"),
        "oracle_current_score": current.score,
        "oracle_current_tier": current.tier,
        "oracle_proposed_score": proposed.score,
        "oracle_proposed_tier": proposed.tier,
    }


def _row_flags(props: dict) -> list:
    """D-10: annotate a row that would otherwise misread as a genuine Tier D outcome or a
    genuine unknown. Both flags are derived only from live properties already in
    tests/scoring_fixtures.py::FIT_SCORE_PROPS -- no new property added.

    blank_org_type: lv_org_type is absent/empty.
    false_veto: lv_anti_icp_flag is true, lv_anti_icp_reason names the non-ANZ veto, and
    lv_country_region_normalized is blank -- the blank-region-fires-non-anz-veto shape
    src/icp_scoring.py's region_raw fix (this phase's oracle) no longer reproduces, but
    live HubSpot's historical write still carries.
    """
    flags = []
    if not props.get("lv_org_type"):
        flags.append("blank_org_type")
    if (
        str(props.get("lv_anti_icp_flag")) == "true"
        and NON_ANZ_VETO_REASON in (props.get("lv_anti_icp_reason") or "")
        and not props.get("lv_country_region_normalized")
    ):
        flags.append("false_veto")
    return flags


def _load_cross_check_names() -> dict:
    """41-final-population.json, read once -- cross-check reference only (see module
    docstring). Returns {company_id: name}; render_markdown uses this for "name where
    available" since FIT_SCORE_PROPS carries no `name` property and this script does not
    add one (no second live call per row, no new property on the shared fetch path).
    Missing file returns {} rather than raising -- a stale/moved snapshot degrades the
    report's naming and cross-check finding, it does not block the simulation itself."""
    if not CROSS_CHECK_POPULATION_PATH.exists():
        return {}
    with CROSS_CHECK_POPULATION_PATH.open() as f:
        data = json.load(f)
    return {company_id: rec.get("name") for company_id, rec in data.items()}


def _row_set_finding(live_ids, cross_check_names: dict) -> dict:
    """Symmetric-difference finding between the live-selected row set and the committed
    41-final-population.json snapshot -- recorded always, never silently reconciled, per
    this plan's must_haves."""
    live_set = set(live_ids)
    cross_check_set = set(cross_check_names.keys())
    only_live = sorted(live_set - cross_check_set)
    only_cross_check = sorted(cross_check_set - live_set)
    return {
        "live_count": len(live_set),
        "cross_check_count": len(cross_check_set),
        "matches_exactly": live_set == cross_check_set,
        "symmetric_difference_count": len(only_live) + len(only_cross_check),
        "only_in_live": only_live,
        "only_in_cross_check": only_cross_check,
    }


def _select_row_ids(explicit_ids=None) -> list:
    """Mirrors scripts/run_scoring_parity.py::_select_sample_ids exactly (RESEARCH.md Open
    Question 1): an explicit override first (explicit_ids, or the SIMULATION_ROW_IDS env
    var), otherwise the live HAS_PROPERTY(lv_icp_fit_score) company search, limit=100.
    Never a second definition of "the scored population". search_records is imported
    locally so a pure-unit call never needs src.hubspot_client at all when an override is
    supplied."""
    if explicit_ids:
        return list(explicit_ids)

    env_ids = os.getenv("SIMULATION_ROW_IDS", "")
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


def build_simulation(ids, fetch_fn=fetch_for_parity, current_cfg=None, scenarios=None):
    """The full RUBRIC-02 payload. One row per id carrying the three live/oracle-current/
    oracle-proposed columns, the club-weight sensitivity tiers (10/20), and the D-10
    flags; a tier-distribution summary (live, oracle-current, oracle-proposed primary);
    a separate sensitivity tier-count distribution (club_10/club_20); the row-set
    divergence finding against 41-final-population.json; a movement summary (rows that
    change tier oracle-current -> oracle-proposed, broken down by lv_org_type); and run
    metadata (UTC timestamp, portal id, the literal PROPOSED_OVERRIDES as applied).

    Zero-row false-green guard (D-13's shape, mirroring run_scoring_parity.py): an empty/
    missing ids list produces a loud failure verdict, never a silent "nothing changed".

    Returns (payload, exit_code).
    """
    if not ids:
        return {
            "rows": [],
            "verdict": ("FAIL: zero rows simulated -- no ids requested. A run that "
                        "checked nothing must never look like a run that found nothing "
                        "changed."),
        }, 1

    scenarios = scenarios if scenarios is not None else SCENARIOS
    current_cfg = current_cfg or load_yaml(str(RUBRIC_PATH))
    scenario_cfgs = {s["name"]: build_scenario_cfg(current_cfg, s["club_weight"]) for s in scenarios}
    primary_cfg = scenario_cfgs[PRIMARY_SCENARIO_NAME]

    cross_check_names = _load_cross_check_names()
    row_set_finding = _row_set_finding(ids, cross_check_names)

    rows = []
    live_tiers = Counter()
    oracle_current_tiers = Counter()
    oracle_proposed_tiers = Counter()
    sensitivity_tier_counters = {
        s["name"]: Counter() for s in scenarios if s["name"] != PRIMARY_SCENARIO_NAME
    }
    movement_by_org_type = {}
    changed_count = 0

    for company_id in ids:
        props = fetch_fn(company_id)
        row = {
            "company_id": company_id,
            "name": cross_check_names.get(company_id),
            "lv_org_type": props.get("lv_org_type"),
            "flags": _row_flags(props),
        }
        row.update(simulate_row(props, current_cfg, primary_cfg))

        sensitivity_tiers = {}
        for s in scenarios:
            if s["name"] == PRIMARY_SCENARIO_NAME:
                continue
            result = compute_icp_score(
                HubSpotRecord(object_type="companies", id="0", properties=props),
                {},
                cfg=scenario_cfgs[s["name"]],
            )
            sensitivity_tiers[s["name"]] = result.tier
            sensitivity_tier_counters[s["name"]][result.tier] += 1
        row["sensitivity_tiers"] = sensitivity_tiers

        live_tiers[str(row["live_tier"])] += 1
        oracle_current_tiers[row["oracle_current_tier"]] += 1
        oracle_proposed_tiers[row["oracle_proposed_tier"]] += 1

        org_type_key = row["lv_org_type"] or "unknown"
        bucket = movement_by_org_type.setdefault(org_type_key, {"changed": 0, "unchanged": 0})
        changed = row["oracle_current_tier"] != row["oracle_proposed_tier"]
        if changed:
            bucket["changed"] += 1
            changed_count += 1
        else:
            bucket["unchanged"] += 1

        rows.append(row)

    payload = {
        "run_metadata": {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "portal_id": EXPECTED_PORTAL_ID,
            "proposed_overrides": [{"path": p, "value": v} for p, v in PROPOSED_OVERRIDES],
            "scenarios": scenarios,
        },
        "rows": rows,
        "tier_distribution": {
            "live": dict(live_tiers),
            "oracle_current": dict(oracle_current_tiers),
            "oracle_proposed": dict(oracle_proposed_tiers),
        },
        "sensitivity_tier_distribution": {
            name: dict(counter) for name, counter in sensitivity_tier_counters.items()
        },
        "movement_summary": {
            "total_rows": len(rows),
            "changed_tier_count": changed_count,
            "unchanged_tier_count": len(rows) - changed_count,
            "by_org_type": movement_by_org_type,
        },
        "row_set_finding": row_set_finding,
        "verdict": f"OK: {len(rows)} row(s) simulated.",
    }
    return payload, 0


def main(ids=None, fetch_fn=fetch_for_parity, current_cfg=None):
    """Retained from Plan 01 Task 2/3 with an unchanged call shape -- a thin wrapper over
    build_simulation so Plan 01 Task 3's zero-write proof
    (tests/test_simulate_rubric_weights.py) needs no edits. Prefer build_simulation
    directly for new code; this name exists for that backward-compatibility reason only.
    """
    return build_simulation(ids, fetch_fn=fetch_fn, current_cfg=current_cfg)


def render_markdown(payload: dict) -> str:
    """The D-09 deliverable: a header (UTC timestamp, portal id, row count, the row-set
    cross-check finding stated explicitly even when it matches exactly, and one
    plain-language paragraph explaining the three score columns and why flagged rows are
    not genuine outcomes), a tier-distribution summary, a sensitivity tier-count table
    for the 10/20 club-weight scenarios, a movement summary, and a per-company table with
    D-10 flags visible in the table itself. Written so Phase 49's RESCORE-03 before/after
    can be lifted from it directly."""
    meta = payload["run_metadata"]
    rows = payload["rows"]
    finding = payload["row_set_finding"]
    dist = payload["tier_distribution"]
    sens_dist = payload["sensitivity_tier_distribution"]
    movement = payload["movement_summary"]

    lines = []
    lines.append("# Phase 46 Rubric Simulation Report")
    lines.append("")
    lines.append(f"- **Run (UTC):** {meta['checked_at_utc']}")
    lines.append(f"- **Portal:** {meta['portal_id']}")
    lines.append(f"- **Rows simulated:** {len(rows)}")
    match_note = "sets match exactly" if finding["matches_exactly"] else "sets differ"
    lines.append(
        "- **Row-set cross-check vs `41-final-population.json`:** "
        f"live={finding['live_count']}, cross-check={finding['cross_check_count']}, "
        f"symmetric difference={finding['symmetric_difference_count']} ({match_note})"
    )
    if finding["only_in_live"]:
        lines.append(f"  - Only in live: {', '.join(finding['only_in_live'])}")
    if finding["only_in_cross_check"]:
        lines.append(f"  - Only in cross-check: {', '.join(finding['only_in_cross_check'])}")
    lines.append("")
    lines.append(
        "This report shows, per company, three numbers: what HubSpot's live score/tier "
        "says today (**Live**), what the scoring oracle computes from that same live data "
        "under today's rubric (**Oracle-Current**, the control), and what the oracle would "
        "compute under the proposed rubric change (**Oracle-Proposed**, the effect being "
        "measured). Rows flagged `blank_org_type` or `false_veto` are shown exactly as "
        "HubSpot holds them today, with no projected or speculative column -- they read as "
        "Tier D or unknown for reasons unrelated to this weight change (Phase 47 clears the "
        "17 false vetoes, Phase 48 enriches the 18 blank org types) and must not be misread "
        "as genuine outcomes of the proposed change."
    )
    lines.append("")
    lines.append("**Applied overrides (never written to `config/icp_scoring.yaml` in this wave):**")
    for entry in meta["proposed_overrides"]:
        lines.append(f"- `{entry['path']}` -> `{entry['value']}`")
    lines.append("")

    lines.append("## Tier Distribution")
    lines.append("")
    lines.append("| Scenario | A | B | C | D | Unscored | Needs Review |")
    lines.append("|---|---|---|---|---|---|---|")

    def _dist_row(label, counts):
        cells = " | ".join(str(counts.get(t, 0)) for t in ["A", "B", "C", "D", "Unscored", "Needs Review"])
        return f"| {label} | {cells} |"

    lines.append(_dist_row("Live (HubSpot today)", dist["live"]))
    lines.append(_dist_row("Oracle -- current rubric", dist["oracle_current"]))
    lines.append(_dist_row("Oracle -- proposed rubric (club=15)", dist["oracle_proposed"]))
    lines.append("")

    lines.append("## Sensitivity (club weight 10 / 20)")
    lines.append("")
    lines.append("| Scenario | A | B | C | D | Unscored | Needs Review |")
    lines.append("|---|---|---|---|---|---|---|")
    for name in sorted(sens_dist.keys()):
        lines.append(_dist_row(f"Oracle -- proposed ({name})", sens_dist[name]))
    lines.append("")

    lines.append("## Movement Summary (Oracle-Current -> Oracle-Proposed, primary scenario)")
    lines.append("")
    lines.append(f"- Rows that change tier: {movement['changed_tier_count']} of {movement['total_rows']}")
    lines.append(f"- Rows unchanged: {movement['unchanged_tier_count']}")
    lines.append("")
    lines.append("| lv_org_type | changed | unchanged |")
    lines.append("|---|---|---|")
    for org_type, counts in sorted(movement["by_org_type"].items()):
        lines.append(f"| {org_type} | {counts['changed']} | {counts['unchanged']} |")
    lines.append("")

    lines.append("## Per-Company Detail")
    lines.append("")
    lines.append(
        "| Name | HubSpot ID | lv_org_type | Flags | Live Score/Tier | "
        "Oracle-Current Score/Tier | Oracle-Proposed Score/Tier | Sens. club=10 | Sens. club=20 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        name = row.get("name") or "(name unavailable)"
        flags = ", ".join(row["flags"]) if row["flags"] else ""
        live_score = row.get("live_score") if row.get("live_score") is not None else "(none)"
        live_tier = row.get("live_tier") if row.get("live_tier") is not None else "(none)"
        sens10 = row["sensitivity_tiers"].get("club_10", "(n/a)")
        sens20 = row["sensitivity_tiers"].get("club_20", "(n/a)")
        lines.append(
            f"| {name} | {row['company_id']} | {row['lv_org_type'] or '(blank)'} | {flags} | "
            f"{live_score}/{live_tier} | "
            f"{row['oracle_current_score']}/{row['oracle_current_tier']} | "
            f"{row['oracle_proposed_score']}/{row['oracle_proposed_tier']} | "
            f"{sens10} | {sens20} |"
        )
    lines.append("")
    lines.append(f"**Verdict:** {payload['verdict']}")
    lines.append("")
    return "\n".join(lines)


def _write_report(payload: dict, out_dir: Path = None) -> Path:
    report_dir = out_dir or Path(os.getenv("SIMULATION_REPORT_DIR", str(DEFAULT_REPORT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = report_dir / f"46-simulation-{date_stamp}.json"
    with path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def cli_main(argv=None) -> int:
    """The operator-facing entry point: --ids / --out-dir, live row selection when --ids
    is not given, and the markdown + JSON report write. Kept separate from main() (Plan
    01 Task 3's zero-write test call shape) to avoid a signature collision."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", help="Comma-separated company ids to simulate (overrides the live search).")
    parser.add_argument("--out-dir", help="Directory to write 46-SIMULATION-REPORT.md and its JSON twin to.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run "
              "this simulation.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    explicit_ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
    ids = _select_row_ids(explicit_ids)
    payload, exit_code = build_simulation(ids)

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "46-SIMULATION-REPORT.md"
    md_path.write_text(render_markdown(payload))
    json_path = _write_report(payload, out_dir=out_dir)

    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    print(payload["verdict"])
    return exit_code


if __name__ == "__main__":
    sys.exit(cli_main())
