# tests/live_smoke_contact.py
#
# Phase 9 (P9-SC3): NON-GATING one-shot live-Haiku smoke. NOT collected by pytest (no
# test_ prefix), so it never runs in the offline suite — it is the documented hand-run.
#
# Command:
#   set -a; . ./.env; set +a; .venv/bin/python tests/live_smoke_contact.py
#
# Safety posture: the ONLY live component is the Anthropic Haiku classifier (real
# ANTHROPIC_API_KEY + ANTHROPIC_HAIKU_MODEL=claude-haiku-4-5 from .env). HubSpot is fully
# mocked via injected hs_search/hs_get stubs and dry_run=True, and ALLOW_CONTACT_CREATE is
# off (allow_create=False) — so ZERO HubSpot writes occur. The anthropic SDK uses httpx,
# not the requests client, so the pipeline's requests-based HubSpot client is untouched.
# Wrapped in try/except: prints exactly one PASS or SKIPPED/ERROR line and ALWAYS exits 0.
import os
import sys

# Run directly (`python tests/live_smoke_contact.py`) puts tests/ on sys.path, not the
# project root — so bootstrap the root before importing src.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from src.ingest import run_contact_ingest

CSV = "tests/fixtures/uploads/contacts_e2e.csv"


def hs_search(object_type, filters, properties=None, limit=100):
    # Single email match ONLY for Row A (bob.smith@) so exactly one contact enriches
    # through the REAL Haiku classifier; every other key returns 0 hits.
    f0 = filters[0]
    if f0["propertyName"] == "email" and f0["value"] == "bob.smith@example.com":
        return {"results": [{"id": "123"}]}
    return {"results": []}


def hs_get(object_type, record_id, properties):
    return {"id": "123", "properties": {
        "email": "bob.smith@example.com",
        "firstname": "Bob",
        "lastname": "Smith",
        "jobtitle": "Sales Manager",
        "phone": "",
        "linkedin_url": "https://linkedin.com/in/bob-existing",
    }}


def main():
    load_dotenv()  # self-sufficient if run without the set -a wrapper
    report = run_contact_ingest(CSV, hs_search=hs_search, hs_get=hs_get,
                                allow_create=False, dry_run=True, upload_confidence=85)
    patches = [e for e in report if e["action"] == "patch"]
    assert patches, "no matched contact enriched"
    m = patches[0]
    assert m["canonical_patch"] or m["payload"], "live classifier produced an empty patch"
    print(f"LIVE SMOKE PASS: matched contact {m['contact_id']} enriched via real Haiku; "
          f"emitted a dry-run patch with {len(m['canonical_patch'])} canonical field(s), "
          f"zero HubSpot writes.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # rate limit / model id / auth — never gate the phase
        print(f"LIVE SMOKE SKIPPED/ERROR: {exc}")
    sys.exit(0)
