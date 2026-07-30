#!/usr/bin/env python3
"""scripts/inventory_org_type_values.py

Phase 21 Task 2 — read-only, paged live inventory of every distinct `lv_org_type` value
currently populated on HubSpot company records (21-RESEARCH.md Assumptions Log A3, Open
Question 3). Every write of `lv_org_type` since Phase 13 is forced through
`src/taxonomy.py`'s `normalize_org_type()`, so any live value that falls outside the 9-key
vocabulary is evidence of a pre-Phase-13 or hand-edited value that would either reject or
silently orphan on the type-conversion PATCH this inventory is the pre-flight gate for.

Read-only throughout: only GET/search calls, no write key, no PATCH, no property mutation —
safe to run in this environment (reads are not classifier-blocked; only armed writes are).

Same idiom as the rest of this migration tooling: env-gated, `_has_credentials()`
skip-to-exit-0, the same portal guard. A non-zero exit here is a FINDING (a stray
out-of-vocabulary value exists), matching this repo's partial-failure convention
(sync_hubspot_properties.py: "a partial migration must not look like success") — never a
crash.

Usage:
    python scripts/inventory_org_type_values.py
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src import taxonomy  # noqa: E402

MIGRATION_DIR = ROOT / "config" / "hubspot_migration"

# Same portal guard as every other schema/migration script in this repo.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# This inventory's own reason for existing: the real property, read-only.
ORG_TYPE_PROPERTY = "lv_org_type"

MAX_SAMPLE_IDS_PER_VALUE = 10
PAGE_LIMIT = 100


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def classify_value(raw_value) -> str:
    """'blank' | 'canonical' | 'synonym' | 'out_of_vocab' — reuses src/taxonomy.py's own
    normalization/lookup, never re-derives the vocabulary. 'synonym' and 'out_of_vocab' are
    kept distinct: a synonym-shaped value is a cheap remediation (already recognized), an
    out-of-vocab value is a genuinely unrecognizable one — collapsing them would hide the
    easy fix."""
    normalized = taxonomy.normalize_key(raw_value)
    if not normalized:
        return "blank"
    canonical = taxonomy._ORG_TYPE_LOOKUP.get(normalized)
    if canonical is None:
        return "out_of_vocab"
    if normalized == taxonomy.normalize_key(canonical):
        return "canonical"
    return "synonym"


def _search_companies_page(after: str | None, limit: int = PAGE_LIMIT) -> dict:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    body = {"filterGroups": [], "properties": [ORG_TYPE_PROPERTY], "limit": limit}
    if after:
        body["after"] = after
    r = requests.post(f"{BASE_URL}/crm/v3/objects/companies/search", headers=hs_headers(),
                       json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def sweep_all_companies() -> tuple:
    """Read-only paged sweep. Returns (records, portal_reported_total) where records is a
    list of {"id": ..., "value": ...} and portal_reported_total is HubSpot's own `total`
    from the first page (independent of our own tally, so a truncated sweep is visible as
    a mismatch rather than silently passing as complete)."""
    records = []
    after = None
    portal_reported_total = None
    while True:
        page = _search_companies_page(after)
        if portal_reported_total is None:
            portal_reported_total = page.get("total")
        for result in page.get("results", []):
            records.append({
                "id": result.get("id"),
                "value": result.get("properties", {}).get(ORG_TYPE_PROPERTY),
            })
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return records, portal_reported_total


def build_inventory(records: list, portal_reported_total) -> dict:
    blank_count = 0
    value_counts: dict = {}
    classification_counts = {"canonical": 0, "synonym": 0, "out_of_vocab": 0, "blank": 0}
    out_of_vocabulary: dict = {}

    for record in records:
        raw = record.get("value")
        kind = classify_value(raw)
        classification_counts[kind] += 1
        if kind == "blank":
            blank_count += 1
            continue
        value_counts[raw] = value_counts.get(raw, 0) + 1
        if kind == "out_of_vocab":
            bucket = out_of_vocabulary.setdefault(raw, {"count": 0, "sample_record_ids": []})
            bucket["count"] += 1
            if len(bucket["sample_record_ids"]) < MAX_SAMPLE_IDS_PER_VALUE:
                bucket["sample_record_ids"].append(record.get("id"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "taxonomy_version": taxonomy.VERSION,
        "total_companies_scanned": len(records),
        "portal_reported_total": portal_reported_total,
        "blank_count": blank_count,
        "classification_counts": classification_counts,
        "value_counts": value_counts,
        "out_of_vocabulary": out_of_vocabulary,
    }


def _write_inventory(inventory: dict, directory: Path = MIGRATION_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"org_type_inventory-{ts}.json"
    path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this inventory.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    records, portal_reported_total = sweep_all_companies()
    inventory = build_inventory(records, portal_reported_total)
    path = _write_inventory(inventory)

    out_of_vocab_count = len(inventory["out_of_vocabulary"])
    print(f"wrote {path}")
    print(f"SUMMARY: scanned {inventory['total_companies_scanned']} companies "
          f"(portal-reported total: {inventory['portal_reported_total']}); "
          f"blank: {inventory['blank_count']}, canonical: {inventory['classification_counts']['canonical']}, "
          f"synonym: {inventory['classification_counts']['synonym']}, "
          f"out-of-vocabulary distinct values: {out_of_vocab_count}.")
    print(f"OUT-OF-VOCABULARY DISTINCT VALUE COUNT: {out_of_vocab_count}")

    if out_of_vocab_count:
        print(f"REMEDIATION OPTIONS: map each stray value to a canonical taxonomy key, or to "
              f"the default ({taxonomy.DEFAULT_ORG_TYPE}), before any type-conversion migration runs.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
