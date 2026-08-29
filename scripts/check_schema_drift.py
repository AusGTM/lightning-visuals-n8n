#!/usr/bin/env python3
"""scripts/check_schema_drift.py

Phase 42 Plan 01 (D-10) — the standing, re-runnable schema-drift checker.

Read-only: GET only, no write path of any kind (Task 1's acceptance criteria greps the
source for any non-GET `requests` verb and fails the build if one is present). This is
what keeps D-05's no-portal-mutation guarantee true for the whole reconciliation half of
Phase 42 -- archival (a separate, gated activity) is Plan 03's job, never this script's.

Compares `config/hubspot_properties.yaml` against the live portal for every property in
D04_COMPANY_PROPERTY_SCOPE (companies) union the yaml's own declared names (both object
types), at D-06 depth: existence + enum option value sets. Labels/displayOrder/description
are cosmetic (reported, never a failure). In the same run it also live-verifies D-01's
do-not-archive invariant -- the eleven company properties and six automation flows the
live scoring engine depends on -- and fails with a DEDICATED exit code (2) if any of them
is missing or disabled, distinct from ordinary drift (exit 1). This distinction matters:
exit 2 means the scoring engine itself is damaged, a materially more urgent condition than
a stale config file.

`39-DECISION.md:107-112` is STALE, SUPERSEDED PROSE. Read literally it points an executor
back at archiving `org_type_score`/`geography_score`/`annual_revenue_score`/the calculated
`lv_icp_fit_score` as if they were the pre-fix-in-place "1 + 1 placeholder" retirement set
from `REQ-retire-calc-placeholder`. There never was a separate placeholder property --
the formula was edited in place on the same `lv_icp_fit_score` record
(createdAt 2026-07-17, updatedAt 2026-08-06, same object). `42-CONTEXT.md` D-01 is the
authoritative correction: those artifacts, plus the four repaired flows and two flows
added in Phase 40, are the LIVE ENGINE and are never archived by anything in Phase 42.

Cadence (D-12): on-demand, and before/after any schema change -- the same tier as the
Phase 40 parity full run. Deliberately NOT wired into the unattended sweep: schema drifts
rarely, and the sweep budget is better spent elsewhere.

Safe to run without credentials (prints "skipped" and exits 0), same idiom as every other
schema-touching script in this repo (`scripts/snapshot_hubspot_schema.py`,
`scripts/sync_hubspot_properties.py`, `scripts/fetch_hubspot_flow.py`).

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['check_schema_drift.py', '--out', 'PATH/TO/report.json']; \
         runpy.run_path('scripts/check_schema_drift.py', run_name='__main__')"

Usage:
    python scripts/check_schema_drift.py --out PATH
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src.guards import assert_no_secrets  # noqa: E402

CONFIG_PATH = ROOT / "config" / "hubspot_properties.yaml"

# Same portal guard as every other schema-touching script -- asserted BEFORE any call.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# D-01 (42-CONTEXT.md) -- the live scoring engine's company properties. NEVER archived by
# anything in Phase 42. `39-DECISION.md:107-112` is superseded prose that, read literally,
# points the other way; this frozenset is the machine-checked correction.
#
# Phase 50 Plan 06 (D-20/T-50-31): lv_anti_icp_flag_num added -- archiving it would
# silently disable lv_icp_tier_derived's veto branch again (calculation_equation reads
# only numeric properties, so the mirror is the ONLY readable veto signal). Postdates the
# committed phase42-pre baseline snapshot (2026-08-13), so
# test_do_not_archive_company_properties_appear_in_committed_snapshot carves it out of
# that one assertion by name rather than failing on a property that could not have existed
# in a Phase 42 snapshot.
DO_NOT_ARCHIVE_COMPANY_PROPERTIES = frozenset({
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
    "lv_icp_fit_score",
    "lv_anti_icp_flag",
    "lv_anti_icp_flag_num",
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
})

# D-01 -- the five remaining live company scoring flows. Mirrors
# scripts/fetch_hubspot_flow.py's FLOW_SLUGS mapping minus 4625147345 (WF1), which moved to
# RETIRED_FLOW_IDS below in Phase 50 Plan 05 (D-08).
DO_NOT_ARCHIVE_FLOW_IDS = {
    "4626124224": "org-type-score",
    "4626722240": "geography-score",
    "4626722237": "annual-revenue-score",
    "4634822079": "produces-content-score",
    "4634822085": "gambling-score",
}

# Phase 50 Plan 05 (D-08, D-17 item 2; superseded by D-24) -- ORIGINAL invariant (D-08):
# lv_icp_tier archived, WF1 switched off but its DEFINITION kept, never deleted -- a flow
# moved here carried "kept but deliberately off" (live AND disabled) as its damage
# condition, distinct from DO_NOT_ARCHIVE_FLOW_IDS' "live and enabled".
#
# D-24 (operator, 2026-08-14) OVERRODE D-08: `DELETE /crm/v3/properties/companies/
# lv_icp_tier` refused with CANNOT_DELETE_PROPERTY_IN_USE while ANY workflow action --
# including a disabled one -- still referenced the property. The only way to unblock the
# archive without editing WF1's actions (which would forfeit the proven one-action
# rollback) was to delete WF1 entirely. The operator chose deletion explicitly, with the
# stated consequence that rollback becomes rebuild-from-JSON
# (`config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json` -> `POST
# /automation/v4/flows`) rather than flipping one switch. So the invariant for a name in
# this dict is now the OPPOSITE of the original: NOT live is the healthy state (deleted,
# as intended); live at all -- enabled OR disabled -- is damage, because it would mean the
# delete did not take or the flow was somehow recreated at this exact id. The dict is kept
# (not deleted) as the historical/rebuild-source record of which flow id this refers to.
RETIRED_FLOW_IDS = {
    "4625147345": "wf1-set-icp-tier",
}

# D-04's full-mirror scope for companies: the eleven do-not-archive names minus the one
# that's out of D-04's own list (lv_country_region_normalized), plus the five ICP-metadata
# names the superseded local-MVP design (CLAUDE.md §5.2/§12) specifies but that have no
# live-creation evidence anywhere in the repo (RESEARCH.md "Reconciliation Gap"). This is
# an EXPLICIT NAME LIST, never a prefix regex -- F4: the repo's only pre-existing reference
# detector (tests/test_hubspot_schema_coverage.py:33, `PROPERTY_RE`) matches only
# `lv_`/`enrichment_`-prefixed names and structurally CANNOT match the five `*_score`
# names. A comparator built by copying that regex would classify the live engine as
# unreferenced and mark it archive-eligible -- exactly what D-01 forbids.
D04_COMPANY_PROPERTY_SCOPE = frozenset(
    (DO_NOT_ARCHIVE_COMPANY_PROPERTIES - {"lv_country_region_normalized"})
    | {
        "lv_icp_confidence",
        "lv_recommended_motion",
        "lv_icp_scored_at",
        "lv_icp_scoring_version",
        "lv_named_account_score_floor",
    }
)

# F5 -- known, deliberately-accepted divergences. Reported in every drift report; NEVER
# contribute to exit_code_for's result (they are documentation carried alongside the
# comparator's own findings, not part of the classify_property state machine).
ACCEPTED_DIVERGENCES = [
    {
        "id": "PARITY-01-tier-label",
        "property": "lv_icp_tier_derived",
        "description": (
            "lv_icp_tier_derived's calculated ladder carries five labels (A, B, C, D, "
            "Unscored) -- deliberately mirroring the retired lv_icp_tier enum's five values "
            "(D-09), not the six recommended_motion labels config/icp_scoring.yaml's "
            "recommended_motion map names. That map additionally names a sixth label, 'Needs "
            "Review', which the derived ladder does not produce. Originally deferred in "
            "Phase 40 (40-06-SUMMARY.md, F8/ENGINE-07) against the old enum; Phase 50 (D-09) "
            "deliberately carried the same divergence into the derived property rather than "
            "adding the sixth label alongside the mechanism change, to keep the derivation "
            "change attributable to the mechanism, not a smuggled rubric change. Still a "
            "documented, accepted divergence -- not a defect."
        ),
    },
]

# The statuses classify_property() may return, in the exact precedence order they are
# evaluated when both a declared (yaml) and live (portal) entry exist.
_FAILURE_STATUSES = {"enum_mismatch", "type_mismatch", "missing_from_yaml", "fabricated_entry"}
_COSMETIC_FIELDS = ("label", "displayOrder", "description")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _assert_no_secrets(text: str) -> None:
    # Thin wrapper -- delegates to src.guards.assert_no_secrets, the single
    # implementation this check was previously copy-pasted verbatim across six files
    # (WR-02 discipline: a bare `assert` is stripped entirely under `python -O` /
    # PYTHONOPTIMIZE=1). Kept as a named wrapper so this module's own call sites are
    # unchanged.
    assert_no_secrets(text)


def _options_values(options) -> set:
    # D-06's exact comparison depth -- reused verbatim from
    # scripts/sync_hubspot_properties.py:68-69 rather than reinvented. The live API's extra
    # per-option `description` key is deliberately not part of this comparison; D-06 scopes
    # enum comparison to option `value` sets only.
    return {str(o.get("value")) for o in (options or [])}


def _cosmetic_diff(declared: dict, live: dict) -> bool:
    for field in _COSMETIC_FIELDS:
        if field in declared and declared.get(field) != live.get(field):
            return True
    return False


def classify_property(name: str, declared: dict | None, live: dict | None) -> str:
    """Pure, offline-testable. No network. See module docstring / plan for the full state
    machine; evaluated in this exact precedence order when both sides exist."""
    if live is not None and declared is not None:
        if _options_values(declared.get("options")) != _options_values(live.get("options")):
            return "enum_mismatch"
        if declared.get("type") != live.get("type") or declared.get("fieldType") != live.get("fieldType"):
            return "type_mismatch"
        if _cosmetic_diff(declared, live):
            return "cosmetic_only"
        return "in_sync"

    if live is not None and declared is None:
        return "missing_from_yaml"

    if live is None and declared is not None:
        # F2 guard: a yaml entry for a property the portal does not have. This is exactly
        # what fabricating an entry from the superseded CLAUDE.md design list would produce.
        return "fabricated_entry"

    # Neither live nor declared. Only reachable for names Phase 42's comparator scope pulls
    # in independently of the yaml (D04_COMPANY_PROPERTY_SCOPE) -- the five design-only
    # names that were never implemented live.
    return "documented_gap"


def _detail_for(status: str, declared: dict | None, live: dict | None) -> str:
    if status == "in_sync":
        return "yaml and live agree"
    if status == "cosmetic_only":
        return "only label/displayOrder/description differ (not a failure per D-06)"
    if status == "enum_mismatch":
        d = sorted(_options_values(declared.get("options"))) if declared else []
        l = sorted(_options_values(live.get("options"))) if live else []
        return f"enum value sets differ -- yaml={d} live={l}"
    if status == "type_mismatch":
        yaml_pair = (declared.get("type"), declared.get("fieldType")) if declared else (None, None)
        live_pair = (live.get("type"), live.get("fieldType")) if live else (None, None)
        return f"type/fieldType differ -- yaml={yaml_pair} live={live_pair}"
    if status == "missing_from_yaml":
        return "live property is not declared in config/hubspot_properties.yaml"
    if status == "fabricated_entry":
        return "declared in yaml but absent live -- F2 guard, this is a hard failure"
    if status == "documented_gap":
        return ("design-only name (superseded local-MVP design, CLAUDE.md), never "
                "implemented live -- reported, not a failure, not a signal to create anything")
    return ""


def exit_code_for(report: dict) -> int:
    """Pure, offline-testable. 2 if the do-not-archive invariant is violated (the live
    scoring engine itself is damaged -- a distinct, more urgent condition than drift). 1 if
    any in-scope property carries a failure status. 0 otherwise -- cosmetic_only,
    documented_gap, and anything in accepted_divergences never contribute a non-zero code."""
    if not report["do_not_archive"]["ok"]:
        return 2
    if any(p["status"] in _FAILURE_STATUSES for p in report["properties"]):
        return 1
    return 0


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
    retired_flows = []
    for flow_id, slug in RETIRED_FLOW_IDS.items():
        live_flow = live_flows_by_id.get(flow_id)
        retired_flows.append({
            "id": flow_id,
            "slug": slug,
            "live": live_flow is not None,
            "is_enabled": bool(live_flow.get("isEnabled")) if live_flow else False,
        })
    ok = (
        all(p["live"] for p in properties)
        and all(f["live"] and f["is_enabled"] for f in flows)
        # D-24: a retired flow's healthy state is DELETED (not live at all) -- the
        # opposite of the original D-08 "live and disabled" invariant. See
        # RETIRED_FLOW_IDS' module comment.
        and all(not rf["live"] for rf in retired_flows)
    )
    return {"properties": properties, "flows": flows, "retired_flows": retired_flows, "ok": ok}


def build_report(desired: dict, live_companies: list, live_contacts: list, live_flows: list,
                  portal_id: str | None) -> dict:
    live_companies_by_name = {p["name"]: p for p in live_companies}
    live_contacts_by_name = {p["name"]: p for p in live_contacts}
    live_flows_by_id = {str(f.get("id")): f for f in live_flows}

    declared_companies_by_name = {p["name"]: p for p in desired.get("companies", {}).get("properties", [])}
    declared_contacts_by_name = {p["name"]: p for p in desired.get("contacts", {}).get("properties", [])}

    do_not_archive = _compute_do_not_archive(live_companies_by_name, live_flows_by_id)

    properties_report = []
    summary: dict = defaultdict(int)

    # Comparator scope: every property declared in the yaml, UNION D04_COMPANY_PROPERTY_SCOPE
    # on companies only. Contacts have no D-04 scope extension. Native HubSpot fields
    # (name, domain, country, annualrevenue, numberofemployees) and anything else the live
    # API marks hubspotDefined stay out of scope simply because they are never in either set.
    scoped = (
        ("companies", declared_companies_by_name, live_companies_by_name, D04_COMPANY_PROPERTY_SCOPE),
        ("contacts", declared_contacts_by_name, live_contacts_by_name, frozenset()),
    )

    for object_type, declared_by_name, live_by_name, extra_scope in scoped:
        names = sorted(set(declared_by_name) | extra_scope)
        for name in names:
            declared = declared_by_name.get(name)
            live = live_by_name.get(name)
            status = classify_property(name, declared, live)
            summary[status] += 1
            properties_report.append({
                "name": name,
                "object_type": object_type,
                "status": status,
                "declared": declared,
                "live": live,
                "detail": _detail_for(status, declared, live),
            })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portal_id": portal_id,
        "scope": {
            "object_types": ["companies", "contacts"],
            "property_count": len(properties_report),
        },
        "do_not_archive": do_not_archive,
        "properties": properties_report,
        "accepted_divergences": ACCEPTED_DIVERGENCES,
        "summary": dict(summary),
    }
    report["exit_code"] = exit_code_for(report)
    return report


def _get_live_properties(object_type: str) -> list:
    """Mirrors scripts/sync_hubspot_properties.py:101-106. A sanity floor of 100 guards
    against a silently truncated or paginated response reading as 'everything is in sync'
    (this endpoint has never been observed to paginate in this repo, but a floor costs
    nothing and catches the failure mode that matters)."""
    import requests
    from src.hubspot_client import hs_headers, BASE_URL

    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])
    assert len(results) >= 100, (
        f"live {object_type} property count ({len(results)}) is below the sanity floor of "
        "100 -- a truncated or paginated response must never be read as zero drift"
    )
    return results


def _get_live_flows() -> list:
    """GET /automation/v4/flows -- no wrapper exists yet for this call generically (Phase 40
    hand-rolled it); mirrors _get_live_properties' requests/hs_headers/BASE_URL idiom."""
    import requests
    from src.hubspot_client import hs_headers, BASE_URL

    r = requests.get(f"{BASE_URL}/automation/v4/flows", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True,
                         help="Path to write the JSON drift report to. No default -- this "
                              "is a standing tool and must not hardcode a phase directory.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "live drift check.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    desired = yaml.safe_load(CONFIG_PATH.read_text())
    live_companies = _get_live_properties("companies")
    live_contacts = _get_live_properties("contacts")
    live_flows = _get_live_flows()

    report = build_report(desired, live_companies, live_contacts, live_flows,
                           os.getenv("HUBSPOT_PORTAL_ID"))

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    _assert_no_secrets(text)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)

    print(f"wrote {out_path}")
    print(f"summary: {report['summary']} | do_not_archive.ok={report['do_not_archive']['ok']} "
          f"| exit_code={report['exit_code']}")

    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
