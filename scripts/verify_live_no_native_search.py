#!/usr/bin/env python3
"""scripts/verify_live_no_native_search.py

Phase 21 Plan 01 (T-21-06) — read-only live read-back verifier proving the deployed
`LV Scheduled Maintenance (Cloud)` workflow actually serves zero native HubSpot
`search`-operation nodes now that "Dedupe Search (candidate contacts)" has moved onto
the credential-bound httpRequest envelope. This is a DISTINCT step from the redeploy:
the deploy script's exit code says the request succeeded, not that the live artifact is
what was intended — exactly the lesson of Phase 19's BUG 26 deployment-drift finding,
where the live deployment silently predated the committed build while every local
check passed.

Imports `_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from
scripts/deploy_n8n_workflows.py rather than re-implementing auth or URL assembly — one
place owns how this repo talks to the n8n API. Never constructs an `Authorization` or
`api_key` header value of its own.

Sweeps EVERY live workflow returned (not just the target by name), so a stale duplicate
copy of the maintenance workflow sitting in the n8n account cannot hide an offender —
the same "don't trust a single named match" caution `verify_live_lusha_urls.py` does
not need (Lusha nodes only ever live in one workflow) but this check does, since a
native search node could in principle exist under any workflow name.

Prints only counts, node names, types, HTTP methods and URLs — never a credential
value, never a token, and never a node's full body.

Usage:
    python scripts/verify_live_no_native_search.py

Live-only utility, same convention as scripts/deploy_n8n_workflows.py /
scripts/verify_live_lusha_urls.py: when the n8n credentials are absent, prints a skip
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

MAINTENANCE_WORKFLOW_NAME = "LV Scheduled Maintenance (Cloud)"
NATIVE_HUBSPOT_TYPE = "n8n-nodes-base.hubspot"
DEDUPE_SEARCH_NODE_NAME = "Dedupe Search (candidate contacts)"
EXPECTED_DEDUPE_SEARCH_URL_SUFFIX = "/crm/v3/objects/contacts/search"


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _get_live_workflow_detail(workflow_id: str) -> dict:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/workflows/{workflow_id}", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _node_report(node: dict) -> dict:
    params = node.get("parameters", {}) or {}
    report = {"name": node.get("name"), "type": node.get("type")}
    if node.get("type") == "n8n-nodes-base.httpRequest":
        report["method"] = params.get("method")
        report["url"] = params.get("url")
    return report


def _native_search_offenders(workflow: dict) -> list:
    """Every node in `workflow` whose type is the native HubSpot node AND whose
    operation is `search` — the exact shape BUG 10/22/23 (and now this dedupe swap)
    close, one call site at a time."""
    offenders = []
    for node in workflow.get("nodes", []):
        if node.get("type") != NATIVE_HUBSPOT_TYPE:
            continue
        if (node.get("parameters", {}) or {}).get("operation") == "search":
            offenders.append({"workflow": workflow.get("name"), "node": node.get("name")})
    return offenders


def verify(all_workflow_details: list) -> dict:
    """Pure — takes a list of already-fetched full workflow dicts, returns the target
    workflow's node inventory, the sweep-wide offender list, and a pass/fail verdict.
    Kept separate from main() so it's testable without a live call (not unit-tested in
    this plan — this is a live-only utility, same convention as
    scripts/verify_live_lusha_urls.py's own `verify()` — but the separation keeps
    main() itself trivial)."""
    offenders = []
    for wf in all_workflow_details:
        offenders.extend(_native_search_offenders(wf))

    target = next((wf for wf in all_workflow_details if wf.get("name") == MAINTENANCE_WORKFLOW_NAME), None)
    target_inventory = [_node_report(n) for n in target.get("nodes", [])] if target else []

    dedupe_node = next((n for n in target_inventory if n["name"] == DEDUPE_SEARCH_NODE_NAME), None) if target else None
    dedupe_is_httprequest_search = bool(
        dedupe_node
        and dedupe_node.get("type") == "n8n-nodes-base.httpRequest"
        and (dedupe_node.get("url") or "").endswith(EXPECTED_DEDUPE_SEARCH_URL_SUFFIX)
    )

    return {
        "target_found": target is not None,
        "target_inventory": target_inventory,
        "dedupe_is_httprequest_search": dedupe_is_httprequest_search,
        "offenders": offenders,
        "ok": target is not None and not offenders and dedupe_is_httprequest_search,
    }


def main(argv=None) -> int:
    if not _has_n8n():
        print("skipped (no n8n creds): N8N_URL and N8N_API_KEY must both be set to run this verifier.")
        return 0

    live_workflows = _get_live_workflows()
    all_details = [_get_live_workflow_detail(w["id"]) for w in live_workflows]

    result = verify(all_details)

    if not result["target_found"]:
        print(f"FAIL: no live workflow named {MAINTENANCE_WORKFLOW_NAME!r} was found.")
        return 1

    print(f"workflow: {MAINTENANCE_WORKFLOW_NAME!r}")
    print(f"live workflows swept: {len(all_details)}")
    print("node inventory:")
    for n in result["target_inventory"]:
        if n["type"] == "n8n-nodes-base.httpRequest":
            print(f"  {n['name']!r}: type={n['type']} method={n.get('method')} url={n.get('url')}")
        else:
            print(f"  {n['name']!r}: type={n['type']}")

    print(f"'{DEDUPE_SEARCH_NODE_NAME}' is httpRequest search (expected shape): "
          f"{result['dedupe_is_httprequest_search']}")
    print(f"VERDICT: native HubSpot search nodes found across all swept live workflows: "
          f"{len(result['offenders'])}")
    if result["offenders"]:
        for o in result["offenders"]:
            print(f"  offender: workflow={o['workflow']!r} node={o['node']!r}")

    if not result["ok"]:
        print("FAIL: see offenders/inventory above.")
        return 1

    print("PASS: 0 native HubSpot search nodes live, dedupe search node is the expected httpRequest shape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
