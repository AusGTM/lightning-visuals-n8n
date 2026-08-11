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

Task 2 (Plan 01) populates PROPOSED_OVERRIDES with only D-01 (individual_club_team -> 15)
and proves the path on one record. Plan 02 adds D-02/D-03, real row selection
(_select_row_ids), a markdown report (render_markdown), and CLI flags (--ids, --out-dir).
"""
import copy
import os
from pathlib import Path

from src.icp_scoring import compute_icp_score, load_yaml
from src.schemas import HubSpotRecord
from tests.scoring_fixtures import fetch_for_parity

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"

# Portal 22617666 (ap1) -- hard-coded, no env override, asserted before any network call
# (T-46-02, the repo-standard guard every other script here follows: run_scoring_parity.py,
# tests/scoring_fixtures.py).
EXPECTED_PORTAL_ID = "22617666"

# The single auditable statement of every weight this simulation proposes: (dotted config
# path, value) pairs, applied in order by build_proposed_cfg. value=None means "delete
# this key" (Plan 04's D-03 gambling-deduction removal will use that shape). Task 2
# populates only D-01; Plan 02 adds D-02/D-03. No second weight table exists anywhere else
# in this file or this repo.
PROPOSED_OVERRIDES = [
    ("base_score.org_type.individual_club_team", 15),
]


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
    """Deep-copies current_cfg and applies every PROPOSED_OVERRIDES entry. Never writes
    to disk, and never mutates current_cfg -- callers may safely reuse the same
    current_cfg object across multiple build_proposed_cfg calls."""
    proposed = copy.deepcopy(current_cfg)
    for dotted_path, value in PROPOSED_OVERRIDES:
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


def main(ids=None, fetch_fn=fetch_for_parity, current_cfg=None, proposed_cfg=None):
    """The simulation's batch entry point. GET-only: fetch_fn is the only outbound call
    this function ever makes, invoked exactly once per id in ids -- no write-capable
    call is reachable from here (RUBRIC-02/D-08, proven by
    tests/test_simulate_rubric_weights.py's zero-write tests). Zero-rows false-green
    guard (D-13's shape, mirroring run_scoring_parity.py): an empty/missing ids list
    produces a loud failure verdict, never a silent "nothing changed".

    Plan 02 wraps this with real row selection (_select_row_ids) and a CLI
    (--ids/--out-dir); Task 2 drives it directly with an explicit ids list.

    Returns (report_dict, exit_code).
    """
    if not ids:
        return {
            "rows": [],
            "verdict": ("FAIL: zero rows simulated -- no ids requested. A run that "
                        "checked nothing must never look like a run that found nothing "
                        "wrong."),
        }, 1

    current_cfg = current_cfg or load_yaml(str(RUBRIC_PATH))
    proposed_cfg = proposed_cfg or build_proposed_cfg(current_cfg)

    rows = []
    for company_id in ids:
        props = fetch_fn(company_id)
        row = {"company_id": company_id}
        row.update(simulate_row(props, current_cfg, proposed_cfg))
        rows.append(row)

    return {"rows": rows, "verdict": f"OK: {len(rows)} row(s) simulated."}, 0


if __name__ == "__main__":
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run "
              "this simulation.")
    elif not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
    else:
        print("scripts/simulate_rubric_weights.py has no row-selection CLI yet "
              "(Plan 02) -- call main(ids=[...]) directly for now.")
