#!/usr/bin/env python3
"""scripts/uat62_website_survey.py

Read-only diagnostic for the Phase 62 UAT. Two questions in one pass:

  1. How many companies would `suggest_contacts.discovery_plan` build a BROKEN ladder for?
     `url_fallback.plan_ladder` is named for a *pasted URL* and needs a scheme; HubSpot's
     `website`/`domain` properties routinely hold a bare domain. Without a scheme,
     `urlsplit` puts everything in `path`, `host` comes back empty, and every candidate
     is an unfetchable `https:///...`. This counts how often that happens live.

  2. Which companies are actually ELIGIBLE for a suggestion round
     (`num_associated_contacts == 0`), so the operator has a real batch to choose from.

This is a diagnostic read to inform the operator's batch choice — it is deliberately NOT
the round's scope. D-62-04 scopes a round to a batch that was just processed, never to
"every company in the portal with no contacts", and nothing here selects a round.

Writes nothing, spends no provider credit, runs no n8n execution.

    set -a; source .env; set +a; .venv/bin/python scripts/uat62_website_survey.py
"""
import os
import sys
from urllib.parse import urlsplit

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "operator-claude-plugin", "scripts"))
import suggest_contacts  # noqa: E402

PROPS = ["name", "domain", "website", "num_associated_contacts"]


def has_scheme(value):
    return bool(value) and bool(urlsplit(value).netloc)


def main():
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set. "
              "Run: set -a; source .env; set +a")
        return 1
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    rows, after = [], None
    while True:
        payload = {"properties": PROPS, "limit": 100}
        if after:
            payload["after"] = after
        r = requests.post("https://api.hubapi.com/crm/v3/objects/companies/search",
                          headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            print(f"HTTP {r.status_code}: {r.text[:300]}")
            return 1
        body = r.json()
        for res in body.get("results", []):
            p = res.get("properties", {})
            rows.append({
                "row_id": res.get("id"),
                "name": p.get("name"),
                "domain": p.get("domain"),
                "website": p.get("website"),
                "num_associated_contacts": p.get("num_associated_contacts"),
            })
        after = (body.get("paging") or {}).get("next", {}).get("after")
        if not after:
            break

    print(f"companies read: {len(rows)}\n")

    # --- question 1: how many would build a broken ladder ---
    with_site = [r for r in rows if (r["website"] or r["domain"])]
    bare = [r for r in with_site if not has_scheme(r["website"] or r["domain"])]
    print("=== ladder input health (the defect) ===")
    print(f"  companies with a website/domain : {len(with_site)}")
    print(f"  of those, BARE (no scheme)      : {len(bare)}"
          f"   -> discovery_plan builds https:/// candidates for these")
    print(f"  of those, usable (has scheme)   : {len(with_site) - len(bare)}")
    if with_site:
        pct = 100.0 * len(bare) / len(with_site)
        print(f"  broken share                    : {pct:.1f}%")

    # --- question 2: who is eligible ---
    verdicts = {v["row_id"]: v for v in suggest_contacts.eligibility(rows)}
    eligible = [r for r in rows if verdicts[r["row_id"]]["verdict"] == "eligible"]
    unknown = [r for r in rows if verdicts[r["row_id"]]["verdict"] == "unknown"]
    print("\n=== eligibility across the portal (diagnostic only, NOT a round scope) ===")
    print(f"  eligible (0 associated contacts): {len(eligible)}")
    print(f"  unknown (count unreadable)      : {len(unknown)}")

    usable = [r for r in eligible if has_scheme(r["website"] or r["domain"])]
    print(f"  eligible AND scheme-bearing     : {len(usable)}"
          f"   <- the only ones a round could fetch today")

    print("\n  first 15 eligible companies:")
    for r in eligible[:15]:
        site = r["website"] or r["domain"] or "(none)"
        flag = "ok    " if has_scheme(site) else "BARE  "
        print(f"    {flag} {r['row_id']:>14}  {(r['name'] or '')[:38]:38}  {site}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
