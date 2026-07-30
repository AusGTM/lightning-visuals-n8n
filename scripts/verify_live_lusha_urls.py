#!/usr/bin/env python3
"""scripts/verify_live_lusha_urls.py

Phase 20 Plan 05 (T-20-11) — read-only live read-back verifier proving the deployed
`LV Enrichment (Cloud template)` workflow actually serves the v3 Lusha URLs and that
none of the retired v2 URLs remain. This is a DISTINCT step from the redeploy: the
deploy script's exit code says the request succeeded, not that the live artifact is
what was intended — exactly the lesson of Phase 19's BUG 26 deployment-drift finding,
where the live deployment silently predated the committed build while every local
check passed.

Imports `_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from
scripts/deploy_n8n_workflows.py rather than re-implementing auth or URL assembly — one
place owns how this repo talks to the n8n API. Never constructs an `Authorization` or
`api_key` header value of its own.

Prints only counts, node names, HTTP methods and URLs — never a credential value,
never a token, and never a node's full body.

Usage:
    python scripts/verify_live_lusha_urls.py

Live-only utility, same convention as scripts/deploy_n8n_workflows.py /
scripts/check_provider_credits.py: when the n8n credentials are absent, prints a skip
banner and exits 0 with zero HTTP calls. Lives in scripts/ with no `test_` prefix, so
pytest never collects it.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_n8n_workflows import _base_url, _n8n_headers, _get_live_workflows  # noqa: E402

ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"

# Built from parts, not written as a literal — mirrors
# tests/test_provider_gate_topology.py's own construction of the same pattern.
RETIRED_LUSHA_MAJOR_VERSION_PREFIX = "api.lusha.com/" + "v" + "2/"
LUSHA_V3_CONTACTS_URL = "https://api.lusha.com/v3/contacts/search-and-enrich"
LUSHA_V3_COMPANIES_URL = "https://api.lusha.com/v3/companies/search-and-enrich"
LUSHA_V3_USAGE_URL = "https://api.lusha.com/v3/account/usage"

# The two provider data nodes this migration rewired to v3 (per lane) — the "no v2, has
# both v3 endpoints" claim is about these. "Lusha Usage" is deliberately reported
# separately below: it is a GET credit-check node (scripts/provider_registry.py), so it
# is never expected to be POST/body-carrying like the two data nodes are.
LUSHA_PROVIDER_NODE_NAMES = ("Lusha Enrich", "Lusha Company")


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _get_live_workflow_detail(workflow_id: str) -> dict:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/workflows/{workflow_id}", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _find_live_enrichment_workflow():
    """Matches on `name`, same idiom as deploy_n8n_workflows.compute_workflow_diff — n8n
    assigns `id` server-side. The list endpoint's entries are then re-fetched by id for
    the full node detail this verifier needs."""
    workflows = _get_live_workflows()
    match = next((w for w in workflows if w.get("name") == ENRICHMENT_WORKFLOW_NAME), None)
    if match is None:
        return None
    return _get_live_workflow_detail(match["id"])


def _lusha_named_nodes(nodes: list) -> list:
    return [n for n in nodes if "Lusha" in (n.get("name") or "")]


def verify(workflow: dict) -> dict:
    """Pure — takes an already-fetched workflow dict, returns counts + a per-node report
    + a pass/fail verdict. Kept separate from main() so it's testable without a live
    call (not unit-tested in this plan — this is a live-only utility, same convention as
    scripts/check_provider_credits.py's extractors — but the separation keeps main()
    itself trivial)."""
    text = json.dumps(workflow)
    counts = {
        "retired_v2": text.count(RETIRED_LUSHA_MAJOR_VERSION_PREFIX),
        "v3_contacts": text.count(LUSHA_V3_CONTACTS_URL),
        "v3_companies": text.count(LUSHA_V3_COMPANIES_URL),
        "v3_usage": text.count(LUSHA_V3_USAGE_URL),
    }
    node_reports = []
    for node in _lusha_named_nodes(workflow.get("nodes", [])):
        params = node.get("parameters", {}) or {}
        node_reports.append({
            "name": node.get("name"),
            "method": params.get("method"),
            "url": params.get("url"),
            "has_body": bool(params.get("jsonBody")),
        })
    ok = (
        counts["retired_v2"] == 0
        and counts["v3_contacts"] >= 1
        and counts["v3_companies"] >= 1
    )
    return {"counts": counts, "nodes": node_reports, "ok": ok}


def main(argv=None) -> int:
    if not _has_n8n():
        print("skipped (no n8n creds): the n8n URL and API key must both be set to run this verifier.")
        return 0

    workflow = _find_live_enrichment_workflow()
    if workflow is None:
        print(f"FAIL: no live workflow named {ENRICHMENT_WORKFLOW_NAME!r} was found.")
        return 1

    result = verify(workflow)
    print(f"workflow: {ENRICHMENT_WORKFLOW_NAME!r}")
    print(f"retired v2 URL occurrences: {result['counts']['retired_v2']}")
    print(f"v3 contacts search-and-enrich occurrences: {result['counts']['v3_contacts']}")
    print(f"v3 companies search-and-enrich occurrences: {result['counts']['v3_companies']}")
    print(f"v3 account usage occurrences: {result['counts']['v3_usage']}")
    for n in result["nodes"]:
        tag = "provider-data" if n["name"] in LUSHA_PROVIDER_NODE_NAMES else "other"
        print(f"node {n['name']!r} ({tag}): method={n['method']} url={n['url']} body_present={n['has_body']}")

    if result["counts"]["retired_v2"] != 0:
        print("FAIL: a retired Lusha v2 URL is present in the live deployment.")
        return 1
    if result["counts"]["v3_contacts"] < 1 or result["counts"]["v3_companies"] < 1:
        print("FAIL: a v3 search-and-enrich endpoint is missing from the live deployment.")
        return 1

    print("PASS: v3 URLs are live, zero retired v2 URLs remain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
