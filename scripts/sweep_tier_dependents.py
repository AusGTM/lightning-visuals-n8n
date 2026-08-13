#!/usr/bin/env python3
"""scripts/sweep_tier_dependents.py

Phase 50 Plan 02 (D-13) -- the read-only, re-runnable portal-dependent sweep for
`lv_icp_tier`. Enumerates every list and every automation flow in the portal and greps
each for a reference to the property, so D-06's archive step (this phase's one
irreversible act) has a knowable blast radius instead of an assumed one.

Two halves, kept in one committed artifact:
  scripted -- Lists API (GET /crm/v3/lists, includeFilters=true) + Automation v4 Flows API
              (GET /automation/v4/flows, then GET .../flows/{id} for each flow's full body).
              Both are scriptable and re-runnable; D-13 requires exactly that so the sweep
              can run again immediately before cutover to catch anything added since.
  manual    -- saved views (companies index page) and reports/dashboards have NO documented
              public HubSpot API (50-RESEARCH.md Q3) and cannot be enumerated here. The
              rendered report always carries a dedicated manual-check section with an
              explicit UNCHECKED placeholder, so a sweep whose manual half was never done is
              visibly incomplete rather than silently reading as clean (D-12).

find_references() matches on the EXACT property-name token, not a prefix -- a blob naming
only `lv_icp_tier_derived` (the new property this phase creates) must never be reported as a
dependent of `lv_icp_tier` (the old one). This is the load-bearing offline-tested case.

Read-only by construction: no `requests.post`, `requests.patch` or `requests.delete` call
site anywhere in this module (enforced by an AST assertion in the test suite, mirroring
scripts/check_schema_drift.py's own GET-only self-description). Re-runnable means a fresh
report every invocation, derived live -- never diffed against a cached prior run as the
source of truth.

Safe to run without credentials (prints "skipped" and exits 0), same idiom as every other
schema-touching script in this repo.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['sweep_tier_dependents.py', '--out', 'PATH/TO/report.md']; \
         runpy.run_path('scripts/sweep_tier_dependents.py', run_name='__main__')"

Usage:
    python scripts/sweep_tier_dependents.py --out PATH
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

TARGET_PROPERTY = "lv_icp_tier"
DEFAULT_OUT = ROOT / ".planning" / "phases" / "50-derived-tier-property" / "50-DEPENDENTS-SWEEP.md"

# Same portal guard as every other schema-touching script -- asserted BEFORE any call.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _assert_no_secrets(text: str) -> None:
    # Copied verbatim from scripts/check_schema_drift.py / scripts/snapshot_hubspot_schema.py.
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or ""
    assert "Authorization" not in text, "serializer leaked the Authorization header"
    if token:
        assert token not in text, "serializer leaked the bearer token value"
    assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text, "serializer leaked the token env var name"


# --- pure functions (offline-testable, no I/O, no environment) -----------------------------

def find_references(blob, property_name: str, _path: str = "$") -> list:
    """Return the JSON paths at which `property_name` appears as an EXACT string value
    anywhere in a nested list/dict structure. Comparison is exact-token equality only -- a
    string that merely contains `property_name` as a prefix of a longer name (e.g.
    "lv_icp_tier_derived" when searching for "lv_icp_tier") is NOT a match. Pure: no
    network, no environment."""
    paths = []
    if isinstance(blob, dict):
        for key, value in blob.items():
            paths.extend(find_references(value, property_name, f"{_path}.{key}"))
    elif isinstance(blob, list):
        for i, item in enumerate(blob):
            paths.extend(find_references(item, property_name, f"{_path}[{i}]"))
    elif isinstance(blob, str):
        if blob == property_name:
            paths.append(_path)
    return paths


def _id_sort_key(rid):
    s = str(rid)
    return (0, int(s)) if s.isdigit() else (1, s)


def render_sweep_markdown(list_findings: list, flow_findings: list, scanned_counts: dict,
                           checked_at: str) -> str:
    """Deterministic markdown -- called twice on the same inputs, returns byte-identical
    strings. `scanned_counts` carries {"lists": N, "flows": M}. Sorted by object type then
    id. Renders an explicit zero-findings statement (carrying the scanned counts) when both
    finding lists are empty, so an empty result is distinguishable from a failed scan.
    Always emits the manual-check section, with its own unchecked placeholder, whether or
    not scripted findings exist -- D-12/D-13's API-blind half is never silently dropped."""
    lists_scanned = scanned_counts.get("lists", 0)
    flows_scanned = scanned_counts.get("flows", 0)

    combined = (
        [{"object_type": "list", **f} for f in list_findings]
        + [{"object_type": "flow", **f} for f in flow_findings]
    )
    combined.sort(key=lambda f: (f["object_type"], _id_sort_key(f["id"])))

    lines = []
    lines.append("# Phase 50 Dependent Sweep -- lv_icp_tier Portal Dependents (D-13)")
    lines.append("")
    lines.append(f"**Scripted sweep run:** {checked_at}")
    lines.append(f"**Lists scanned:** {lists_scanned}")
    lines.append(f"**Flows scanned:** {flows_scanned}")
    lines.append("")
    lines.append(
        "Re-runnable (D-13): every invocation derives this report fresh from a live portal "
        "read -- it is never diffed against a cached prior run as the source of truth."
    )
    lines.append("")

    lines.append("## Scripted Findings (Lists API + Flows API)")
    lines.append("")
    if not combined:
        lines.append(
            f"**NONE.** Zero references to `{TARGET_PROPERTY}` found across "
            f"{lists_scanned} lists and {flows_scanned} flows scanned. This is a genuine "
            "zero-findings result, distinguishable from a failed scan by the scanned "
            "counts stated above."
        )
    else:
        lines.append("| Object Type | ID | Name | JSON Path |")
        lines.append("|---|---|---|---|")
        for f in combined:
            lines.append(f"| {f['object_type']} | {f['id']} | {f['name']} | `{f['path']}` |")
    lines.append("")

    lines.append("## Manual UI Check (API-blind half -- D-12, D-13)")
    lines.append("")
    lines.append(
        "Saved views (companies index page) and reports/dashboards have no documented "
        "public HubSpot API (50-RESEARCH.md Q3) and cannot be enumerated by this script. "
        "D-12 confirms these two dependent classes are known to exist; they must be "
        "checked by a human in the portal UI, dated, and recorded here -- an unfilled "
        "manual half stays visibly UNCHECKED rather than silently passing as clean."
    )
    lines.append("")
    lines.append("- **Saved views (companies index page):** UNCHECKED")
    lines.append("- **Reports / dashboards:** UNCHECKED")
    lines.append("- **checked_at:** _(unfilled -- fill in when the manual check is performed)_")
    lines.append("- **Findings:** _(none recorded yet)_")
    lines.append("")

    return "\n".join(lines)


# --- thin live callers (live-only; not offline-tested, GET only) ---------------------------

def _get_all_lists() -> list:
    """GET /crm/v3/lists, offset-paginated, includeFilters=true so each list's filter-branch
    definition is returned inline -- avoids a second per-list GET. Read-only."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    all_lists = []
    offset = 0
    while True:
        r = requests.get(
            f"{BASE_URL}/crm/v3/lists",
            headers=hs_headers(),
            params={"includeFilters": "true", "offset": offset},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        page = body.get("lists", [])
        all_lists.extend(page)
        if not body.get("hasMore") or not page:
            break
        offset = body.get("offset", offset + len(page))
    return all_lists


def _get_all_flow_summaries() -> list:
    """GET /automation/v4/flows -- summary rows only (id/name/isEnabled), no filter body.
    Mirrors scripts/check_schema_drift.py::_get_live_flows."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    r = requests.get(f"{BASE_URL}/automation/v4/flows", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def _get_flow_body(flow_id: str) -> dict:
    """GET /automation/v4/flows/{flow_id} -- the full body (enrollmentCriteria + actions),
    the only place a property reference can actually live. Mirrors
    scripts/fetch_hubspot_flow.py::fetch_flow's GET half (no strip/archive here)."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    r = requests.get(f"{BASE_URL}/automation/v4/flows/{flow_id}", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _scan_lists():
    lists = _get_all_lists()
    findings = []
    for lst in lists:
        list_id = lst.get("listId") or lst.get("ilsListId") or lst.get("id")
        name = lst.get("name", "(unnamed list)")
        for path in find_references(lst, TARGET_PROPERTY):
            findings.append({"id": str(list_id), "name": name, "path": path})
    return findings, len(lists)


def _scan_flows():
    summaries = _get_all_flow_summaries()
    findings = []
    for summary in summaries:
        flow_id = str(summary.get("id"))
        name = summary.get("name", "(unnamed flow)")
        body = _get_flow_body(flow_id)
        for path in find_references(body, TARGET_PROPERTY):
            findings.append({"id": flow_id, "name": name, "path": path})
    return findings, len(summaries)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                         help="Path to write the sweep markdown report to.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "live dependent sweep.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    list_findings, lists_scanned = _scan_lists()
    flow_findings, flows_scanned = _scan_flows()

    checked_at = datetime.now(timezone.utc).isoformat()
    text = render_sweep_markdown(
        list_findings, flow_findings,
        {"lists": lists_scanned, "flows": flows_scanned},
        checked_at,
    )
    _assert_no_secrets(text)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)

    print(f"wrote {out_path}")
    print(f"lists_scanned={lists_scanned} flows_scanned={flows_scanned} "
          f"list_findings={len(list_findings)} flow_findings={len(flow_findings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
