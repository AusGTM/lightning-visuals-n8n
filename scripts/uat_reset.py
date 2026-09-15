#!/usr/bin/env python3
"""Reset a UAT stress session: restorable-delete the HubSpot records it created.

Three protections, all on by default:

1. **Marker match for contacts.** A contact is a candidate only if its email local-part
   starts with ``uat.`` or its ``lv_linkedin_url`` slug starts with ``uat-`` (the shape the
   stress CSVs use) — OR it was created at/after ``--since`` AND is associated with a
   company this run created (suggest-contacts creates real people at those companies).
2. **Snapshot for companies.** ``--snapshot`` records, BEFORE the run, which domains from
   the companies CSV already exist in the portal. A company is a candidate only if its
   domain is in the CSV, it is NOT in the snapshot, and its ``createdate`` >= ``--since``.
   Pre-existing companies (ATC, HRNSW, ...) are therefore never touched even though the
   CSV names them.
3. **Dry run unless told otherwise.** Nothing is deleted without ``--execute`` AND
   ``ALLOW_UAT_RESET=true`` in the environment. Every DELETE's status is printed and the
   whole plan is written to a JSON report next to the CSV.

Credentials: ``HUBSPOT_PRIVATE_APP_TOKEN`` from the environment only (run as
``set -a; . ./.env; set +a; python3 scripts/uat_reset.py ...``). The token is never printed.

Usage:
  python3 scripts/uat_reset.py --snapshot  --companies-csv <path>            # before the run
  python3 scripts/uat_reset.py --companies-csv <path> --since 2026-09-14T00:00:00Z          # dry run
  ALLOW_UAT_RESET=true python3 scripts/uat_reset.py --companies-csv <path> --since ... --execute
  python3 scripts/uat_reset.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.hubapi.com"
PAUSE = 0.15  # seconds between calls — HubSpot private-app burst limit is 100/10s
CONTACT_PROPS = ["email", "firstname", "lastname", "lv_linkedin_url", "createdate", "associatedcompanyid"]
COMPANY_PROPS = ["name", "domain", "createdate", "num_associated_contacts"]
FREEMAIL = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "bigpond.com"}


# ---------------------------------------------------------------- pure helpers (self-tested)
def normalize_domain(raw: str) -> str:
    """'HTTPS://WWW.Vrc.com.au/' -> 'vrc.com.au'; a LinkedIn/facebook page or freemail -> ''."""
    d = (raw or "").strip().lower()
    d = re.sub(r"^[a-z]+://", "", d)
    d = d.split("/", 1)[0].split("?", 1)[0]
    d = re.sub(r"^www\.", "", d)
    if not d or "." not in d or d in FREEMAIL:
        return ""
    if d.endswith(("linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com")):
        return ""
    return d


def is_uat_contact(props: dict) -> bool:
    email = (props.get("email") or "").strip().lower()
    local = email.split("@", 1)[0] if "@" in email else ""
    li = (props.get("lv_linkedin_url") or "").strip().lower()
    return local.startswith("uat.") or "/in/uat-" in li or li.endswith("uat-") or "uat-" in li.rsplit("/", 1)[-1]


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if v.isdigit():  # epoch ms
        return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc)
    return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)


def created_since(props: dict, since: datetime | None) -> bool:
    if since is None:
        return False
    created = parse_ts(props.get("createdate"))
    return created is not None and created >= since


def csv_domains(path: Path) -> list[str]:
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        col = next((h for h in reader.fieldnames or [] if h.strip().lower() in ("website", "domain", "url")), None)
        if col is None:
            raise SystemExit(f"{path}: no Website/domain column in {reader.fieldnames}")
        seen, out = set(), []
        for row in reader:
            d = normalize_domain(row.get(col, ""))
            if d and d not in seen:
                seen.add(d)
                out.append(d)
        return out


# ---------------------------------------------------------------- HubSpot calls
def _headers():
    tok = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN")
    if not tok:
        raise SystemExit("HUBSPOT_PRIVATE_APP_TOKEN not set — run with: set -a; . ./.env; set +a; python3 scripts/uat_reset.py ...")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _req(method, url, **kw):
    import requests  # local import keeps --self-test dependency-free

    time.sleep(PAUSE)
    r = requests.request(method, url, headers=_headers(), timeout=30, **kw)
    if r.status_code == 429:
        time.sleep(10)
        r = requests.request(method, url, headers=_headers(), timeout=30, **kw)
    return r


def search(object_type: str, filters: list[dict], props: list[str]) -> list[dict]:
    out, after = [], None
    while True:
        body = {"filterGroups": [{"filters": filters}], "properties": props, "limit": 100}
        if after:
            body["after"] = after
        r = _req("POST", f"{BASE}/crm/v3/objects/{object_type}/search", json=body)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("results", []))
        after = (data.get("paging") or {}).get("next", {}).get("after")
        if not after:
            return out


def company_by_domain(domain: str) -> list[dict]:
    return search("companies", [{"propertyName": "domain", "operator": "EQ", "value": domain}], COMPANY_PROPS)


def contacts_for_company(company_id: str) -> list[dict]:
    r = _req("GET", f"{BASE}/crm/v4/objects/companies/{company_id}/associations/contacts?limit=500")
    r.raise_for_status()
    ids = [str(x["toObjectId"]) for x in r.json().get("results", [])]
    if not ids:
        return []
    r = _req("POST", f"{BASE}/crm/v3/objects/contacts/batch/read",
             json={"properties": CONTACT_PROPS, "inputs": [{"id": i} for i in ids]})
    r.raise_for_status()
    return r.json().get("results", [])


def delete(object_type: str, record_id: str) -> int:
    return _req("DELETE", f"{BASE}/crm/v3/objects/{object_type}/{record_id}").status_code


# ---------------------------------------------------------------- modes
def do_snapshot(domains: list[str], snap_path: Path) -> None:
    existing = {}
    for d in domains:
        hits = company_by_domain(d)
        if hits:
            existing[d] = [{"id": h["id"], "name": h["properties"].get("name")} for h in hits]
    snap = {"taken_at": datetime.now(timezone.utc).isoformat(), "domains_checked": domains, "existing": existing}
    snap_path.write_text(json.dumps(snap, indent=2))
    print(f"snapshot: {len(existing)}/{len(domains)} domains already exist -> {snap_path}")
    for d, hits in existing.items():
        print(f"  protected  {d}  {[h['id'] for h in hits]}")


def company_by_id(company_id: str) -> dict | None:
    r = _req("GET", f"{BASE}/crm/v3/objects/companies/{company_id}?properties={','.join(COMPANY_PROPS)}")
    return r.json() if r.status_code == 200 else None


def build_plan(domains: list[str], snapshot: dict, since: datetime | None, extra_company_ids=()) -> dict:
    plan = {"companies": [], "contacts": [], "skipped": []}
    protected = set(snapshot.get("existing", {}))
    protected_ids = {h["id"] for hits in snapshot.get("existing", {}).values() for h in hits}
    seen_contacts = set()

    # 1. marker-matched contacts (fictitious rows)
    for flt in ([{"propertyName": "email", "operator": "CONTAINS_TOKEN", "value": "uat*"}],
                [{"propertyName": "lv_linkedin_url", "operator": "CONTAINS_TOKEN", "value": "uat*"}]):
        for c in search("contacts", flt, CONTACT_PROPS):
            if c["id"] in seen_contacts:
                continue
            if is_uat_contact(c["properties"]):
                seen_contacts.add(c["id"])
                plan["contacts"].append({"id": c["id"], "email": c["properties"].get("email"),
                                         "reason": "uat marker"})

    # 2. companies created by the run
    for d in domains:
        if d in protected:
            plan["skipped"].append({"domain": d, "reason": "pre-existing (snapshot)"})
            continue
        for co in company_by_domain(d):
            p = co["properties"]
            if not created_since(p, since):
                plan["skipped"].append({"domain": d, "id": co["id"], "reason": "createdate before --since (or no --since)"})
                continue
            plan["companies"].append({"id": co["id"], "domain": d, "name": p.get("name"), "createdate": p.get("createdate")})
            # 3. real people suggest-contacts attached to a run-created company
            for c in contacts_for_company(co["id"]):
                if c["id"] in seen_contacts:
                    continue
                if created_since(c["properties"], since):
                    seen_contacts.add(c["id"])
                    plan["contacts"].append({"id": c["id"], "email": c["properties"].get("email"),
                                             "reason": f"created since --since, associated to run company {co['id']}"})
                else:
                    plan["skipped"].append({"contact": c["id"], "reason": "associated but predates --since"})
    # 4. explicitly named companies (domain rule cannot reach them) — same createdate guard
    for cid in extra_company_ids:
        if cid in protected_ids or any(c["id"] == cid for c in plan["companies"]):
            continue
        co = company_by_id(cid)
        if not co:
            plan["skipped"].append({"id": cid, "reason": "not found"})
            continue
        p = co["properties"]
        if not created_since(p, since):
            plan["skipped"].append({"id": cid, "reason": "createdate before --since"})
            continue
        plan["companies"].append({"id": cid, "domain": p.get("domain"), "name": p.get("name"),
                                  "createdate": p.get("createdate"), "reason": "--extra-company-id"})
        for c in contacts_for_company(cid):
            if c["id"] not in seen_contacts and created_since(c["properties"], since):
                seen_contacts.add(c["id"])
                plan["contacts"].append({"id": c["id"], "email": c["properties"].get("email"),
                                         "reason": f"created since --since, associated to run company {cid}"})
    return plan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--companies-csv", type=Path, help="the companies stress CSV (Website column)")
    ap.add_argument("--since", help="ISO timestamp — only records created at/after this are candidates")
    ap.add_argument("--snapshot", action="store_true", help="record pre-existing companies, then exit")
    ap.add_argument("--snapshot-file", type=Path, help="default: <csv dir>/uat-reset-snapshot.json")
    ap.add_argument("--extra-company-id", action="append", default=[],
                    help="a company id created by the run that the domain rule cannot reach (e.g. one filed under a freemail domain); repeatable; still subject to --since")
    ap.add_argument("--execute", action="store_true", help="actually DELETE (also needs ALLOW_UAT_RESET=true)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()
    if not a.companies_csv:
        ap.error("--companies-csv is required")
    domains = csv_domains(a.companies_csv)
    snap_path = a.snapshot_file or a.companies_csv.with_name("uat-reset-snapshot.json")

    if a.snapshot:
        do_snapshot(domains, snap_path)
        return 0

    if not snap_path.exists():
        print(f"REFUSED: no snapshot at {snap_path}. Run --snapshot BEFORE the UAT so pre-existing companies are protected.")
        return 2
    snapshot = json.loads(snap_path.read_text())
    since = parse_ts(a.since) if a.since else parse_ts(snapshot.get("taken_at"))
    if since is None:
        print("REFUSED: no --since and the snapshot carries no taken_at.")
        return 2

    plan = build_plan(domains, snapshot, since, extra_company_ids=a.extra_company_id)
    print(f"plan: {len(plan['contacts'])} contacts, {len(plan['companies'])} companies to delete; {len(plan['skipped'])} skipped")
    for c in plan["contacts"]:
        print(f"  contact  {c['id']:>14}  {c.get('email') or '-':45}  {c['reason']}")
    for co in plan["companies"]:
        print(f"  company  {co['id']:>14}  {co['domain']:45}  {co.get('name')}")

    report = {"since": since.isoformat(), "snapshot": str(snap_path), "plan": plan, "executed": False, "results": []}
    if a.execute:
        if os.environ.get("ALLOW_UAT_RESET") != "true":
            print("REFUSED: --execute needs ALLOW_UAT_RESET=true in the environment.")
            return 2
        report["executed"] = True
        for c in plan["contacts"]:  # contacts first, then companies
            code = delete("contacts", c["id"])
            report["results"].append({"contacts": c["id"], "status": code})
            print(f"  DELETE contacts/{c['id']} -> {code}")
        for co in plan["companies"]:
            code = delete("companies", co["id"])
            report["results"].append({"companies": co["id"], "status": code})
            print(f"  DELETE companies/{co['id']} -> {code}")
        bad = [r for r in report["results"] if r["status"] != 204]
        print(f"done: {len(report['results']) - len(bad)} deleted (204), {len(bad)} failed")
    else:
        print("dry run — nothing deleted. Re-run with --execute and ALLOW_UAT_RESET=true.")

    out = a.companies_csv.with_name(f"uat-reset-report-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"report -> {out}")
    return 0 if not report["executed"] or all(r["status"] == 204 for r in report["results"]) else 1


def self_test() -> int:
    assert normalize_domain("HTTPS://WWW.Vrc.com.au/") == "vrc.com.au"
    assert normalize_domain("WWW.THEVALLEY.COM.AU") == "thevalley.com.au"
    assert normalize_domain("https://www.linkedin.com/company/illawarra-turf-club/") == ""
    assert normalize_domain("gmail.com") == ""
    assert normalize_domain("") == "" and normalize_domain("nodot") == ""
    assert is_uat_contact({"email": "uat.priya.whitcombe@australianturfclub.com.au"})
    assert is_uat_contact({"email": "UAT.PRIYA.WHITCOMBE@X.COM"})
    assert is_uat_contact({"email": "", "lv_linkedin_url": "https://www.linkedin.com/in/uat-otis-vellacott"})
    assert not is_uat_contact({"email": "ctelfer@australianturfclub.com.au", "lv_linkedin_url": ""})
    assert not is_uat_contact({"email": "situated@x.com"})  # 'uat' inside a word is not a marker
    since = parse_ts("2026-09-14T00:00:00Z")
    assert created_since({"createdate": "2026-09-14T03:00:00.000Z"}, since)
    assert not created_since({"createdate": "2026-09-13T23:59:59.000Z"}, since)
    assert created_since({"createdate": str(int(since.timestamp() * 1000) + 1)}, since)  # epoch ms form
    assert not created_since({"createdate": "2026-09-15T00:00:00Z"}, None)
    print("self-test ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
