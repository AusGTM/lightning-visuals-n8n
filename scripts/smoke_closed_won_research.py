#!/usr/bin/env python3
"""scripts/smoke_closed_won_research.py

Phase 13 Task 4b — non-gating, env-gated, READ-ONLY live smoke.

Closed-won HubSpot accounts are ground truth for `lv_produces_content=true` (they
bought the product). Any researched `false` on one is a detected false-negative on the
one field that fires the ICP hard veto (config/icp_scoring.yaml hard_vetoes.no_content) —
worth a human look before the pipeline would otherwise disqualify a real customer.

NOT imported by any pytest test. NOT run with credentials by the executor — only the
no-credentials skip path (exit 0) is exercised automatically; a human runs this with real
keys as an operator tool for the pilot.

Zero HubSpot writes: GET/search only.

Usage:
    python scripts/smoke_closed_won_research.py [--limit N]
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")) and bool(os.getenv("ANTHROPIC_API_KEY"))


def _deal_company_ids(hs_headers, base_url, deal_id):
    """v4 associations: {"results": [{"toObjectId": <company id>, ...}]}."""
    import requests
    url = f"{base_url}/crm/v4/objects/deals/{deal_id}/associations/companies"
    r = requests.get(url, headers=hs_headers, timeout=30)
    r.raise_for_status()
    return [str(x["toObjectId"]) for x in r.json().get("results", [])]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10,
                         help="Max companies to research this run (default 10).")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN and ANTHROPIC_API_KEY "
              "must both be set to run this live smoke.")
        return 0

    # ponytail: setdefault() is a no-op here — the documented run command sources .env
    # first (USE_MOCK_WEB_RESEARCH=true), which already occupies the key. Must assign
    # directly to actually force live mode; setdefault silently left every "live" run
    # hitting the mock fixture (identical data, no evidence_by_field) for every company.
    os.environ["USE_MOCK_WEB_RESEARCH"] = "false"  # live research, not the fixture

    from src import hubspot_client as hs
    from src.web_research import claude_web_research
    from src.taxonomy import validate_research_output
    from src.schemas import HubSpotRecord

    max_per_run = int(os.getenv("MAX_WEB_RESEARCH_PER_RUN", "10"))
    limit = max(0, min(args.limit, max_per_run))
    if limit == 0:
        print("skipped (limit/MAX_WEB_RESEARCH_PER_RUN resolved to 0)")
        return 0

    deals = hs.search_records(
        "deals",
        [{"propertyName": "dealstage", "operator": "EQ", "value": "closedwon"}],
        ["dealname", "dealstage"],
        limit=100,
    )

    seen_ids, company_ids = set(), []
    for deal in deals.get("results", []):
        for cid in _deal_company_ids(hs.hs_headers(), hs.BASE_URL, deal["id"]):
            if cid not in seen_ids:
                seen_ids.add(cid)
                company_ids.append(cid)

    seen_domains, companies = set(), []
    for cid in company_ids:
        rec = hs.get_record("companies", cid, ["name", "domain", "website", "country", "industry"])
        props = rec.get("properties") or {}
        domain = (props.get("domain") or "").strip().lower()
        if not domain or domain in seen_domains:
            continue  # dedupe to companies with a usable domain (multiple deals -> same company)
        seen_domains.add(domain)
        companies.append(rec)
        if len(companies) >= limit:
            break

    if not companies:
        print("No closed-won companies with a usable domain found.")
        return 0

    counts = {"true": 0, "null": 0, "false": 0, "unmatched": 0}
    evidenced_false = []

    for rec in companies:
        props = rec.get("properties") or {}
        record = HubSpotRecord(object_type="companies", id=str(rec["id"]), properties=props)
        result = claude_web_research(record)  # dev oracle, USE_MOCK_WEB_RESEARCH=false -> real API
        validated = validate_research_output({
            "data": result.data,
            "evidence_by_field": result.evidence_by_field,
            "matched": result.matched,
            "confidence": result.confidence,
        })

        name = props.get("name") or "(unnamed)"
        domain = props.get("domain") or "(no domain)"
        pc = validated["data"].get("lv_produces_content")
        evidence_url = validated["evidence_by_field"].get("lv_produces_content") or "-"

        if not validated["matched"]:
            counts["unmatched"] += 1
            print(f"{name} | {domain} | lv_produces_content=UNMATCHED | evidence={evidence_url}")
            continue

        if pc is True:
            counts["true"] += 1
        elif pc is False:
            counts["false"] += 1
            evidenced_false.append((name, domain, evidence_url))  # unevidenced false can't occur post-TS-2
        else:
            counts["null"] += 1
        print(f"{name} | {domain} | lv_produces_content={pc} | evidence={evidence_url}")

    print(f"\nSummary: true={counts['true']} null={counts['null']} false={counts['false']} "
          f"unmatched={counts['unmatched']} (of {len(companies)} closed-won companies)")

    if evidenced_false:
        print("\nRED FLAG: evidenced FALSE on a closed-won company (fires the hard veto) — human look:")
        for name, domain, url in evidenced_false:
            print(f"  {name} ({domain}) -> {url}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
