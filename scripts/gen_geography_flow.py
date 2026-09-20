#!/usr/bin/env python3
"""scripts/gen_geography_flow.py

Phase 75 Plan 04 (D-75-09) — regenerates the ONE branch of HubSpot flow 4626722240's
committed body (config/hubspot_flows/4626722240-geography-score.after.json) from
config/icp_scoring.yaml's regions.home, via the single loader
src/icp_scoring.py::regions_home() -- no second YAML parser (Phase 46 parity precedent,
mirrors scripts/gen_escalation_js.py's own header discipline). The flow body is never
hand-edited; this script is the only writer of the committed file.

Run directly to (re)write the checked-in file:
    .venv/bin/python scripts/gen_geography_flow.py

Regenerating the file does not touch the live portal -- pushing the result live with
scripts/put_hubspot_flow.py is a later plan's job (D-75-10).

Planner note (recorded per D-75-09/D-75-11's own instruction): HubSpot re-evaluates this
flow only when lv_country_region_normalized CHANGES on a record (shouldReEnroll: true,
event-based on that property -- see the committed body's own enrollmentCriteria). The PUT
alone re-scores nothing; an existing record only gains its new geography_score when its
region is next (re)written. This is why geography_score is excluded from this phase's
recompute proof.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.icp_scoring import regions_home  # noqa: E402

FLOW_PATH = ROOT / "config" / "hubspot_flows" / "4626722240-geography-score.after.json"
TARGET_PROPERTY = "lv_country_region_normalized"
TARGET_OPERATOR = "IS_EQUAL_TO"


def _find_geography_filters(node) -> list:
    """Recursively walk a HubSpot flow body and collect every filter dict whose
    `property` is TARGET_PROPERTY and whose `operation.operator` is TARGET_OPERATOR.
    Returns the matching dicts BY REFERENCE (mutating one mutates the body in place).
    Reused by scripts/check_schema_drift.py's live comparator (D-75-11b) -- one walker,
    not two."""
    found = []
    if isinstance(node, dict):
        if (
            node.get("property") == TARGET_PROPERTY
            and isinstance(node.get("operation"), dict)
            and node["operation"].get("operator") == TARGET_OPERATOR
        ):
            found.append(node)
        for value in node.values():
            found.extend(_find_geography_filters(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_geography_filters(item))
    return found


def render(body: dict) -> dict:
    """Replaces the geography branch's `operation.values` in place with
    list(regions_home()) and returns the same body object (idempotent: re-running on an
    already-current body is a no-op diff). Raises AssertionError if the target filter
    cannot be located unambiguously -- a flow body that grew a second geography branch (or
    lost its only one) must fail the build, not be silently half-updated."""
    matches = _find_geography_filters(body)
    assert len(matches) == 1, (
        f"expected exactly one filter on {TARGET_PROPERTY!r} with operator "
        f"{TARGET_OPERATOR!r}, found {len(matches)} -- refusing to guess which branch to "
        f"rewrite (D-75-09)"
    )
    matches[0]["operation"]["values"] = list(regions_home())
    return body


def main() -> int:
    body = json.loads(FLOW_PATH.read_text())
    render(body)
    # Preserve the file's existing formatting convention exactly (verified round-trip):
    # indent=2, sort_keys=True, no trailing newline -- matches
    # scripts/fetch_hubspot_flow.py's own archive_flow() writer.
    FLOW_PATH.write_text(json.dumps(body, indent=2, sort_keys=True))
    print(f"wrote {FLOW_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
