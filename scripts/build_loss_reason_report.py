#!/usr/bin/env python3
"""scripts/build_loss_reason_report.py

Phase 43 Plan 03 (PIPE-04, D-04/D-05) — the first consumer of the closed-lost feedback
signal. Queries live closed-lost Deals, cross-tabulates their loss reason against the
joined company's ICP tier, stamps the live rubric version, and writes a dated markdown
report under docs/reports/.

Consumption only. This script never mutates a HubSpot record and never opens
config/icp_scoring.yaml for writing — it only reads the rubric version out of it. If a
future change adds a write path here, that is a scope violation of D-04/D-05, not a bug
fix.

Two loss-reason properties are read side by side, on purpose: the custom
`lv_closed_lost_reason` (CLAUDE.md §5.3's proposed picklist) and HubSpot's own native
unprefixed `closed_lost_reason` (reps closing through the standard UI populate that one,
not the custom field). Neither property's live existence was confirmed before this
session had HubSpot credentials — so the report probes the deals property schema for each
one directly and renders three distinct outcomes per property: the property does not
exist in this portal; the property exists and is 0% filled; the property exists and N of
M examined deals have it filled. Collapsing "does not exist" into "0% filled" would be a
fabrication, not a finding, and this script refuses to make that guess.

Company join: `hs_primary_associated_company` first, the Associations v4 endpoint as the
documented fallback for deals where that property is empty. Every deal that carries a
loss reason but cannot be joined to any company lands in an explicit "Unknown" tier
bucket in the cross-tab and in an `unjoined_deal_ids` list — never dropped silently,
which would understate a tier's true loss count.

An empty dataset (zero closed-lost deals, or deals with no loss reason filled yet) is the
expected first-run outcome, not a failure: the report renders correctly, states the zero
counts explicitly, and the script exits 0. Missing credentials is a different case
entirely — it means the script never looked, and must never render a report that reads
like it looked and found nothing. That path prints an explicit skip message and exits
non-zero, before any network call.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    set -a; . ./.env; set +a; .venv/bin/python scripts/build_loss_reason_report.py
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src.hubspot_client import BASE_URL, get_record, hs_headers, search_records  # noqa: E402

# Portal 22617666 (ap1) — asserted before any network call, same discipline as
# scripts/run_scoring_parity.py / tests/scoring_fixtures.py.
EXPECTED_PORTAL_ID = "22617666"

RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
REPORT_DIR = ROOT / "docs" / "reports"

LOSS_REASON_PROP = "lv_closed_lost_reason"
NATIVE_LOSS_REASON_PROP = "closed_lost_reason"
PRIMARY_COMPANY_PROP = "hs_primary_associated_company"


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _rubric_version() -> str:
    with RUBRIC_PATH.open() as f:
        return yaml.safe_load(f).get("version", "unknown")


# --------------------------------------------------------------------------------------
# Live fetch functions. Each one is a thin, injectable seam — build_report() below never
# calls these names directly by import, only through its own default-argument bindings,
# so every offline test can substitute a stub with zero network reachable.
# --------------------------------------------------------------------------------------

def probe_deal_property(property_name: str) -> bool:
    """True if `property_name` exists in the live deals property schema, False if
    HubSpot answers 404 (property was never created in this portal). Any other HTTP
    failure is re-raised — a probe that swallows a 500 as "absent" would silently
    mislabel an outage as a schema fact."""
    url = f"{BASE_URL}/crm/v3/properties/deals/{property_name}"
    r = requests.get(url, headers=hs_headers(), timeout=30)
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


def search_closed_lost_deals() -> list:
    """`hs_is_closed_won`/`hs_is_closed` are HubSpot-computed rollups present on every
    deal regardless of pipeline, so this filter is portal-agnostic — no assumption about
    a specific dealstage internal id or a specific pipeline's stage naming."""
    result = search_records(
        "deals",
        [
            {"propertyName": "hs_is_closed_won", "operator": "EQ", "value": "false"},
            {"propertyName": "hs_is_closed", "operator": "EQ", "value": "true"},
        ],
        ["dealname", LOSS_REASON_PROP, NATIVE_LOSS_REASON_PROP, PRIMARY_COMPANY_PROP],
        limit=100,
    )
    return result.get("results", [])


def fetch_deal_company_associations(deal_id: str) -> list:
    """Associations v4 fallback for a deal whose `hs_primary_associated_company` is
    empty. Returns company ids in HubSpot's own returned order; the join uses the
    first."""
    url = f"{BASE_URL}/crm/v4/objects/deals/{deal_id}/associations/companies"
    r = requests.get(url, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return [str(item["toObjectId"]) for item in r.json().get("results", [])]


def fetch_company_tier(company_id: str):
    """Returns the joined company's properties dict, or None if the read failed — one
    unreadable company must not sink the whole report."""
    try:
        record = get_record("companies", company_id, ["lv_icp_tier", "lv_icp_fit_score"])
    except Exception:  # noqa: BLE001 -- one bad join must not sink the report
        return None
    return record.get("properties", {})


# --------------------------------------------------------------------------------------
# Aggregation core — pure, offline-testable. Every fetch is an injected callable with a
# live default, so calling build_report() with no arguments does the real thing and
# calling it with stubs does none of it.
# --------------------------------------------------------------------------------------

def _tri_state(exists: bool, filled: int) -> str:
    if not exists:
        return "absent"
    if filled == 0:
        return "present_empty"
    return "present_filled"


def _property_verdict(label: str, info: dict, examined: int) -> str:
    if info["state"] == "absent":
        return f"{label} does not exist in this portal."
    if info["state"] == "present_empty":
        return f"{label} exists and is 0% filled (0 of {examined} examined deals)."
    return f"{label} exists and {info['filled']} of {examined} examined deals have it filled."


def build_report(
    probe_fn=probe_deal_property,
    search_deals_fn=search_closed_lost_deals,
    fetch_associations_fn=fetch_deal_company_associations,
    fetch_company_fn=fetch_company_tier,
):
    """Returns (report_dict, exit_code). exit_code is always 0 here — the empty-dataset
    and missing-credentials cases are distinguished by the caller (main()), which only
    reaches this function once credentials and portal are already confirmed. A run that
    could not look never calls this function at all."""
    lv_exists = probe_fn(LOSS_REASON_PROP)
    native_exists = probe_fn(NATIVE_LOSS_REASON_PROP)

    deals = search_deals_fn() or []
    examined = len(deals)

    lv_filled = 0
    native_filled = 0
    joined_primary = 0
    joined_fallback = 0
    unjoined = 0
    unjoined_deal_ids = []
    cross_tab = {}

    for deal in deals:
        props = deal.get("properties") or {}
        lv_reason = props.get(LOSS_REASON_PROP)
        native_reason = props.get(NATIVE_LOSS_REASON_PROP)
        if lv_reason:
            lv_filled += 1
        if native_reason:
            native_filled += 1

        # Prefer the custom picklist; fall back to the native free-text field a rep
        # filled through the standard UI. A deal with neither has nothing to
        # cross-tabulate and is skipped here but still counted in `examined` above.
        reason = lv_reason or native_reason
        if not reason:
            continue

        deal_id = deal.get("id")
        company_id = props.get(PRIMARY_COMPANY_PROP)
        if company_id:
            joined_primary += 1
        else:
            assoc_ids = fetch_associations_fn(deal_id) or []
            if assoc_ids:
                company_id = assoc_ids[0]
                joined_fallback += 1
            else:
                unjoined += 1
                unjoined_deal_ids.append(deal_id)

        if company_id:
            company_props = fetch_company_fn(company_id) or {}
            tier = company_props.get("lv_icp_tier") or "Unknown"
        else:
            tier = "Unknown"

        cross_tab.setdefault(reason, {})
        cross_tab[reason][tier] = cross_tab[reason].get(tier, 0) + 1

    deals_with_reason = sum(sum(tiers.values()) for tiers in cross_tab.values())

    report = {
        "rubric_version": _rubric_version(),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "deals_examined": examined,
        "deals_with_reason": deals_with_reason,
        LOSS_REASON_PROP: {
            "exists": lv_exists,
            "filled": lv_filled,
            "state": _tri_state(lv_exists, lv_filled),
        },
        NATIVE_LOSS_REASON_PROP: {
            "exists": native_exists,
            "filled": native_filled,
            "state": _tri_state(native_exists, native_filled),
        },
        "joined_primary": joined_primary,
        "joined_fallback": joined_fallback,
        "unjoined": unjoined,
        "unjoined_deal_ids": unjoined_deal_ids,
        "cross_tab": cross_tab,
    }

    verdict_parts = [
        f"{examined} closed-lost deal(s) examined.",
        _property_verdict("`lv_closed_lost_reason`", report[LOSS_REASON_PROP], examined),
        _property_verdict("`closed_lost_reason` (native)", report[NATIVE_LOSS_REASON_PROP], examined),
    ]
    if deals_with_reason == 0:
        verdict_parts.append("No closed-lost deal carried a loss reason -- nothing to cross-tabulate yet.")
    verdict_parts.append(
        f"Joined via primary association: {joined_primary}; "
        f"via Associations v4 fallback: {joined_fallback}; unjoined: {unjoined}."
    )
    report["verdict"] = " ".join(verdict_parts)

    return report, 0


def render_report(report: dict) -> str:
    examined = report["deals_examined"]
    lines = [
        "# Loss-Reason Report",
        "",
        f"**Generated (UTC):** {report['checked_at_utc']}  ",
        f"**Rubric version:** {report['rubric_version']}  ",
        f"**Closed-lost deals examined:** {examined}",
        "",
        "## Property status",
        "",
        f"- {_property_verdict('`lv_closed_lost_reason`', report[LOSS_REASON_PROP], examined)}",
        f"- {_property_verdict('`closed_lost_reason` (HubSpot native)', report[NATIVE_LOSS_REASON_PROP], examined)}",
        "",
        "## Deal-to-company join",
        "",
        f"- Joined via primary association (`hs_primary_associated_company`): {report['joined_primary']}",
        f"- Joined via Associations v4 fallback: {report['joined_fallback']}",
        f"- Unjoined (unknown company): {report['unjoined']}",
    ]
    if report["unjoined_deal_ids"]:
        lines.append(f"- Unjoined deal ids: {', '.join(str(i) for i in report['unjoined_deal_ids'])}")
    lines += ["", "## Loss reason x ICP tier", ""]

    if not report["cross_tab"]:
        lines.append(
            "No closed-lost deal carries a loss reason yet -- zero rows to cross-tabulate. "
            "This is the expected first-run outcome, not a failure."
        )
    else:
        tiers = sorted({tier for reasons in report["cross_tab"].values() for tier in reasons})
        lines.append("| Loss reason | " + " | ".join(tiers) + " |")
        lines.append("|---" * (len(tiers) + 1) + "|")
        for reason in sorted(report["cross_tab"]):
            row = [reason] + [str(report["cross_tab"][reason].get(t, 0)) for t in tiers]
            lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## Verdict", "", report["verdict"], ""]
    return "\n".join(lines)


def _write_report(text: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = REPORT_DIR / f"{date_stamp}-loss-reason-report.md"
    path.write_text(text)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to build "
              "this loss-reason report. This run did not look at HubSpot at all -- do not "
              "read this as zero loss reasons found.")
        return 1

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    report, exit_code = build_report()
    text = render_report(report)
    path = _write_report(text)
    print(f"wrote {path}")
    print(report["verdict"])
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
