#!/usr/bin/env python3
"""scripts/uat62_eligibility_read.py

Read-only helper for the Phase 62 UAT sitting. Reads `num_associated_contacts` (the
property `suggest_contacts.eligibility` keys off) plus website/domain for the companies
the review sitting just processed, and renders the plugin's OWN tri-state verdict rather
than re-deriving one here.

Writes nothing, spends no provider credit, and runs no n8n execution — a plain HubSpot
batch read. Needs HUBSPOT_PRIVATE_APP_TOKEN in the environment (source .env first).

    set -a; source .env; set +a; .venv/bin/python scripts/uat62_eligibility_read.py
"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "operator-claude-plugin", "scripts"))
import suggest_contacts  # noqa: E402

# The batch this sitting treats as "just processed": the two racing clubs approved
# through the review lane earlier today. D-62-04 scopes a round to a real batch, never
# to an arbitrary operator-supplied list, so these are named here rather than searched for.
BATCH = [
    ("9604738976", "Bunbury Turf Club"),
    ("9604787229", "The Alice Springs Turf Club"),
]

PROPS = ["name", "domain", "website", "num_associated_contacts"]


def main():
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set. "
              "Run: set -a; source .env; set +a")
        return 1

    resp = requests.post(
        "https://api.hubapi.com/crm/v3/objects/companies/batch/read",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"properties": PROPS, "inputs": [{"id": cid} for cid, _ in BATCH]},
        timeout=60,
    )
    print(f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:400])
        return 1

    rows = []
    for result in resp.json().get("results", []):
        p = result.get("properties", {})
        rows.append({
            "row_id": result.get("id"),
            "name": p.get("name"),
            "domain": p.get("domain"),
            "website": p.get("website"),
            "num_associated_contacts": p.get("num_associated_contacts"),
        })

    verdicts = {v["row_id"]: v for v in suggest_contacts.eligibility(rows)}

    print("\nEligibility (plugin's own suggest_contacts.eligibility, not re-derived here):\n")
    for row in rows:
        v = verdicts[row["row_id"]]
        print(f"  {row['row_id']}  {row['name']}")
        print(f"      website/domain          : {row['website'] or row['domain']}")
        print(f"      num_associated_contacts : {row['num_associated_contacts']!r}")
        print(f"      VERDICT                 : {v['verdict']}  ({v['reason']})")

        plan = suggest_contacts.discovery_plan(row)
        print(f"      ladder host             : {plan.get('host')}")
        print(f"      ladder cap              : {plan.get('cap')}")
        for c in (plan.get("candidates") or [])[:6]:
            print(f"        - {c}")
        for note in (plan.get("notes") or []):
            print(f"        note: {note}")
        print()

    print(json.dumps({"rows": rows, "verdicts": list(verdicts.values())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
