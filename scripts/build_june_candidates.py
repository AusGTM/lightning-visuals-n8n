#!/usr/bin/env python3
# scripts/build_june_candidates.py
#
# Phase 41 (41-CONTEXT.md D-01..D-03, D-08). Reads the June-2026 ICP validation dataset
# (a sibling repo's build artifact, outside this git root) and emits config/
# june_candidates.json: a mapped candidate table keyed by June-era HubSpot company id,
# consumed by the "Merge Company" n8n Code node as a third `mergeCompanies()` candidate
# source named `june_2026` (scripts/build_cloud_workflows.py's ENRICH_MERGE_CO).
#
# Also writes config/june_candidates_source.json — a verbatim snapshot of whatever
# --source pointed at, plus its sha256 recorded in the output's `_meta` — so the table is
# reproducible from this repo alone (T-41-01) without depending on the sibling repo being
# checked out at run time.
#
# Usage:
#   .venv/bin/python scripts/build_june_candidates.py \
#       [--source ../ausgtm-lightningvisuals-data/data/enriched_companies.json] \
#       [--out config/june_candidates.json]
#
# Re-running with --source config/june_candidates_source.json is idempotent: `rows` is
# byte-identical, only `_meta.generated_at` moves.

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT.parent / "ausgtm-lightningvisuals-data" / "data" / "enriched_companies.json"
DEFAULT_OUT = ROOT / "config" / "june_candidates.json"
SNAPSHOT_PATH = ROOT / "config" / "june_candidates_source.json"

MAPPING_VERSION = "june-2026-v1"

# D-03: categorical June confidence -> numeric confidence, on the same 0-100 scale
# mergeCompanies.js's DEFAULT_COMPANY_POLICY min_confidence thresholds use.
CONFIDENCE_MAP = {"high": 85, "medium": 65, "low": 40}

# D-02: deterministic Perplexity org_type enum -> lv_org_type taxonomy value
# (config/taxonomy.yaml org_types keys — never invent a value not listed there).
ORG_TYPE_MAP = {
    "Team/Club": "individual_club_team",
    "League/Governing-Body": "governing_body_league",
    "Broadcaster/Production": "broadcaster",
    "Other": "other",
    "Non-sports-leisure": "other",
}

# D-02 hand-curated exception list: named ICP misfits from docs/business/icp-scoring.md
# section 4, where the coarse Perplexity enum bucketed a company into the wrong
# lv_org_type. Populated in Task 2 (scripts/build_june_candidates.py EXCEPTIONS dict) —
# left empty here so Task 1's tracer proves the plumbing on the deterministic table alone.
EXCEPTIONS = {}

# hq_country (June's free-text field) -> lv_country_region_normalized enum.
COUNTRY_MAP = {"Australia": "AU", "New Zealand": "NZ"}


def _bool_str(value):
    """HubSpot booleans must be the literal strings "true"/"false" (EQ-filter landmine,
    CLAUDE.md source-of-truth and confirmed live across n8n/code/*.js) — never a JSON
    boolean. Returns None (omit the key) for anything not literally True/False."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return None


def map_row(record):
    """One June record -> one candidate-table row. Omits a key rather than writing
    null/empty string — mergeCompanies()' own _isBlank guard would silently drop it
    anyway, and an omitted key keeps the table readable."""
    row = {"_name": record.get("name")}

    confidence = CONFIDENCE_MAP.get(record.get("confidence"))
    if confidence is not None:
        row["_confidence"] = confidence

    sources = record.get("sources") or []
    first_source = sources[0] if sources else None
    evidence = {}

    record_id = str(record.get("id"))
    exception = EXCEPTIONS.get(record_id)

    org_type = ORG_TYPE_MAP.get(record.get("org_type"), "other")
    if exception and "lv_org_type" in exception:
        org_type = exception["lv_org_type"]
    row["lv_org_type"] = org_type
    if first_source:
        evidence["lv_org_type"] = first_source

    produces = _bool_str(record.get("produces_broadcast_or_streaming_content"))
    if produces is not None:
        row["lv_produces_content"] = produces
        if first_source:
            evidence["lv_produces_content"] = first_source

    hq_country = record.get("hq_country")
    if hq_country:
        row["lv_country_region_normalized"] = COUNTRY_MAP.get(hq_country, "Other")

    if exception:
        for key, value in exception.items():
            if key in ("lv_org_type", "_exception_reason"):
                continue
            row[key] = value
        if "_exception_reason" in exception:
            row["_exception_reason"] = exception["_exception_reason"]

    if evidence:
        row["_evidence"] = evidence

    return row


def build(source_records):
    return {str(record_id): map_row(record) for record_id, record in source_records.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE),
                         help="Path to the June enriched_companies.json dataset")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                         help="Path to write the mapped candidate table")
    args = parser.parse_args()

    source_path = Path(args.source)
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    # Commit a verbatim snapshot unless --source already IS the committed snapshot (the
    # idempotent re-run case) — so the table stays reproducible from this repo alone
    # without ever depending on the sibling repo being checked out at run time (T-41-01).
    if source_path.resolve() != SNAPSHOT_PATH.resolve():
        SNAPSHOT_PATH.write_bytes(source_bytes)

    source_records = json.loads(source_bytes)
    rows = build(source_records)

    out = {
        "_meta": {
            "source_path": args.source,
            "source_sha256": source_sha256,
            "record_count": len(rows),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mapping_version": MAPPING_VERSION,
        },
        "rows": rows,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path} "
          f"({len(rows)} rows, source sha256={source_sha256[:12]}...)")


if __name__ == "__main__":
    main()
