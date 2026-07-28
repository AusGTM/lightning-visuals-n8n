#!/usr/bin/env python3
"""scripts/deploy_n8n_workflows.py

Phase 16 Task 1 — deploy the built `n8n/wf_*.json` workflows to n8n Cloud via the
Public API.

Same idiom as scripts/sync_hubspot_properties.py: env-gated, dry-run-by-default,
`_has_n8n()` skip-to-exit-0, a two-key write gate (DRY_RUN=false AND
ALLOW_N8N_DEPLOY=true), idempotent diff re-derived from a fresh GET every run (never
local state).

Usage:
    python scripts/deploy_n8n_workflows.py          # dry-run diff (default, zero writes)
    DRY_RUN=false ALLOW_N8N_DEPLOY=true \
        python scripts/deploy_n8n_workflows.py       # live create/update

CREDENTIAL BINDING (review consensus #1): the built Cloud workflow JSONs carry zero
`credentials` blocks, so importing them unchanged would leave every node unbound. Before
POST/PUT, `bind_credentials()` attaches a per-node top-level `credentials` object,
resolved from a static node-name -> credential-name map (NODE_CREDENTIAL_MAP, below) and
the credential name->id map `provision_n8n_credentials.py` writes to
`.n8n_credential_ids.json` (gitignored). A node whose mapped credential name has no
resolvable id fails the deploy closed rather than importing an unbound node.

Activation (POST .../activate) is a separate operator-runbook step, not performed here —
n8n creates new workflows inactive by default.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

N8N_DIR = ROOT / "n8n"
CRED_ID_MAP_PATH = ROOT / ".n8n_credential_ids.json"

# node name -> {cred_type: <n8n credential type key used in the node's top-level
# "credentials" block>, cred_name: <name provision_n8n_credentials.py provisions it under>}.
# Lusha/Apollo/Anthropic all share the httpHeaderAuth generic credential TYPE but are three
# DIFFERENT credential objects — disambiguated here by node name, not by type (review #1).
NODE_CREDENTIAL_MAP = {
    # Task 6: the shared-secret webhook gate (CLAUDE.md §18.1) is the Webhook Trigger
    # node's OWN native Header Auth, bound to this credential — never a Code node.
    "Webhook Trigger": {"cred_type": "httpHeaderAuth", "cred_name": "LV Enrichment Webhook"},
    "HubSpot Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    # Phase 16.4 Task 1 (gpt #9 lesson repeated deliberately): the new fetch-by-objectId
    # search node — an unmapped HubSpot node deploys UNBOUND and silently 401s at runtime.
    "HubSpot Fetch By Id": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Create": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Update": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Company Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    # Phase 16.4 Task 2: companies mirror of "HubSpot Fetch By Id" above.
    "HubSpot Company Fetch By Id": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Company Create": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Company Update": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "Lusha Enrich": {"cred_type": "httpHeaderAuth", "cred_name": "LV Lusha"},
    "Lusha Company": {"cred_type": "httpHeaderAuth", "cred_name": "LV Lusha"},
    "Apollo Match": {"cred_type": "httpHeaderAuth", "cred_name": "LV Apollo"},
    "Apollo Org": {"cred_type": "httpHeaderAuth", "cred_name": "LV Apollo"},
    "Claude Web Research": {"cred_type": "httpHeaderAuth", "cred_name": "LV Anthropic"},
    "Judge Call": {"cred_type": "httpHeaderAuth", "cred_name": "LV Anthropic"},
    # Phase 16.2 Task 2 (gpt #9/C2 lesson) — the contacts research->judge mirror's two
    # anthropic HTTP nodes, reusing the SAME "LV Anthropic" credential (no new credential
    # object). An unmapped anthropic node would deploy UNBOUND -> 401 -> silent research
    # failure, exactly the C2 lesson from the companies branch.
    "Contact Web Research": {"cred_type": "httpHeaderAuth", "cred_name": "LV Anthropic"},
    "Contact Judge Call": {"cred_type": "httpHeaderAuth", "cred_name": "LV Anthropic"},
    # ZoomInfo (Task 2 decision: split-code-node) — the Mint HTTP node is the ONLY node
    # that ever touches client_id/client_secret, via this generic Basic Auth credential.
    # The Token Gate/Cache Token/Enrich Code nodes are secret-free and need no binding.
    "ZoomInfo Mint": {"cred_type": "httpBasicAuth", "cred_name": "LV ZoomInfo"},
    "ZoomInfo Mint Company": {"cred_type": "httpBasicAuth", "cred_name": "LV ZoomInfo"},
    # Phase 16.1 Plan 02 (reviews C2) — the single-item credit-reporting branch's HTTP
    # nodes, reusing the SAME provisioned credentials above (no new credential object).
    # "ZoomInfo Usage" (the secret-free Bearer-only GET following the mint) needs no
    # binding, like the existing ZoomInfo Enrich/ZoomInfo Company Code nodes.
    "Lusha Usage": {"cred_type": "httpHeaderAuth", "cred_name": "LV Lusha"},
    "Apollo Usage": {"cred_type": "httpHeaderAuth", "cred_name": "LV Apollo"},
    "ZoomInfo Usage Mint": {"cred_type": "httpBasicAuth", "cred_name": "LV ZoomInfo"},
    # Quick task 2026-07-28 — pre-activation blocker: these 10 hubspot nodes were absent
    # from the map entirely, so `mapping is None: continue` deployed them UNBOUND with no
    # error, 401-ing only at runtime. Confirmed live against the built wf_*_cloud.json.
    # wf_contact_ingest_cloud.json (1 node):
    "HubSpot Search by Email": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    # wf_scheduled_maintenance_cloud.json (9 nodes):
    "SJ-3 Search (requested poller)": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "SJ-1 Search (input-gap scan)": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "SJ-1 Set Requested": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "SJ-2 Search (stale refresh)": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "SJ-2 Set Requested": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "Dedupe Search (candidate contacts)": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "Dedupe Set Needs Review": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "Review Search (approved=true)": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "Review Apply Update": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
}


# Phase 16.5 Task 1 — the deploy-time research/escalation overlay's closed target set.
# ONLY the two boolean kill switches `_flag_const(..., cloud=True)` bakes as bare-boolean
# JS literals. `MAX_WEB_RESEARCH_PER_RUN` / `MAX_SONNET_VALIDATIONS_PER_RUN` /
# `ANTHROPIC_SONNET_MODEL` are also CONFIG_FLAG_DEFAULTS entries but would let an
# open-ended mechanism widen cost caps or swap models — "enabling research must not widen
# anything else" has to be structural, not a convention, so a name outside this set is a
# ValueError, never a silent no-op. Deliberately NOT imported from build_cloud_workflows —
# that module runs taxonomy/escalation codegen at import time and writes into n8n/code/;
# a deploy script must never carry that side effect. tests/test_enabled_build_invariants.py
# pins this set as a subset of CONFIG_FLAG_DEFAULTS from a TEST, which may import freely.
_OVERLAYABLE_FLAGS = frozenset({"ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"})


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _instance_ok() -> bool:
    """Wrong-instance guard (review consensus #4) — must NOT fail open. If
    N8N_EXPECTED_URL is set, N8N_URL must equal it exactly. If unset, refuse unless
    N8N_URL's host genuinely ends with `.n8n.cloud` — an unset/unrecognized URL refuses,
    it never defaults to "ok"."""
    url = os.getenv("N8N_URL", "")
    expected = os.getenv("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_N8N_DEPLOY", "false").lower() == "true"
    return (not dry_run) and allow


def _base_url() -> str:
    return os.getenv("N8N_URL", "").rstrip("/")


def _n8n_headers() -> dict:
    return {"X-N8N-API-KEY": os.getenv("N8N_API_KEY", ""), "Content-Type": "application/json"}


def _load_local_workflows() -> list:
    # Deploy ONLY the Cloud-targeted workflows (wf_*_cloud.json). The other top-level
    # wf_*.json files are docker-replica fixtures that legitimately keep $env/$vars
    # (AR-4) and would import as broken/unbound nodes on n8n Cloud.
    return [json.loads(p.read_text()) for p in sorted(N8N_DIR.glob("wf_*_cloud.json"))]


def _get_live_workflows() -> list:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/workflows", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def _load_credential_id_map(path: Path = CRED_ID_MAP_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def compute_workflow_diff(local_workflows: list, live_workflows: list) -> dict:
    """Match on the workflow's top-level `name` — n8n assigns `id` server-side, so
    matching on the local JSON's internal id would never find an existing live workflow.
    Re-derive from a FRESH `live_workflows` (a fresh GET) every call, never from local
    state, so a re-run after a mid-batch failure picks up exactly where it left off."""
    live_by_name = {w["name"]: w for w in live_workflows}
    create, update = [], []
    for wf in local_workflows:
        live = live_by_name.get(wf["name"])
        if live is None:
            create.append(wf)
        else:
            update.append({"id": live["id"], "body": wf})
    return {"create": create, "update": update}


# n8n httpRequest node `parameters.authentication` values that mean "this node carries a
# credential". Non-credential-bearing httpRequest nodes (the repo's secret-free
# Bearer-only nodes, e.g. "ZoomInfo Usage" — a Code node, not even httpRequest — reusing a
# token minted upstream) have authentication unset/"none" and must keep deploying unbound.
_CREDENTIAL_BEARING_HTTP_AUTH_MODES = {"genericCredentialType", "predefinedCredentialType"}


def _node_requires_credential(node: dict) -> bool:
    """Scoped by node type — never a blanket "every node needs a credential". Code, IF,
    Set, NoOp, Merge, Schedule Trigger, etc. never require one and always pass through."""
    node_type = node.get("type")
    if node_type == "n8n-nodes-base.hubspot":
        return True
    if node_type == "n8n-nodes-base.httpRequest":
        auth = node.get("parameters", {}).get("authentication")
        return auth in _CREDENTIAL_BEARING_HTTP_AUTH_MODES
    if node_type == "n8n-nodes-base.webhook":
        # The Cloud webhook's native Header Auth gate (CLAUDE.md §18.1) — "none"/unset
        # means the node has no auth configured and needs no credential.
        auth = node.get("parameters", {}).get("authentication")
        return bool(auth) and auth != "none"
    return False


def bind_credentials(workflow: dict, name_to_id: dict, node_cred_map: dict = None) -> dict:
    """Pure function. Returns a NEW workflow dict with each mapped node's top-level
    `credentials` block attached. Fails closed two ways: (1) a mapped node's credential
    name has no resolvable id in `name_to_id`, or (2) a node whose TYPE requires a
    credential (hubspot; httpRequest/webhook with credential-bearing auth) is absent from
    `node_cred_map` entirely — never emits an unbound node that would 401 at runtime."""
    node_cred_map = NODE_CREDENTIAL_MAP if node_cred_map is None else node_cred_map
    wf = json.loads(json.dumps(workflow))  # deep copy, stdlib only
    for node in wf.get("nodes", []):
        mapping = node_cred_map.get(node.get("name"))
        if mapping is None:
            if _node_requires_credential(node):
                raise ValueError(
                    f"cannot deploy {wf.get('name')!r}: node {node.get('name')!r} "
                    f"(type {node.get('type')!r}) requires a credential but has no "
                    f"NODE_CREDENTIAL_MAP entry. Add it to NODE_CREDENTIAL_MAP."
                )
            continue
        cred_name = mapping["cred_name"]
        cred_id = name_to_id.get(cred_name)
        if cred_id is None:
            raise ValueError(
                f"cannot deploy {wf.get('name')!r}: node {node['name']!r} needs credential "
                f"{cred_name!r}, which is not in the provisioned name->id map "
                f"({CRED_ID_MAP_PATH.name}). Run provision_n8n_credentials.py first."
            )
        node["credentials"] = {mapping["cred_type"]: {"id": cred_id, "name": cred_name}}
    return wf


def enable_baked_flags(workflow: dict, flags) -> tuple:
    """Pure, deep-copying, fails-closed deploy-time overlay — same shape as
    bind_credentials() above, applied at the same point in flight. Returns a NEW
    workflow dict (input is never mutated) plus a {flag: rewrite_count} map. A returned
    count of zero for a given workflow is NOT an error here (two of the three cloud
    workflows legitimately declare neither flag) — rejecting a zero total across the
    WHOLE deploy set is the caller's (main()'s) responsibility.

    Rejects any name outside _OVERLAYABLE_FLAGS with a ValueError. For each requested
    flag, replaces the EXACT literal disabled declaration `_flag_const(..., cloud=True)`
    emits (`const NAME = false;`, a bare boolean — never regex-loose) with the enabled
    form, in every node's `parameters.jsCode`. Then — the point of this function — the
    fail-closed check: re-scans the SERIALIZED result for every `const NAME = <literal>;`
    declaration (a looser regex than the replace step, so a spacing or numeric-literal
    drift the exact replace could not reach still gets caught) and raises if any
    surviving declaration of a requested flag carries anything but the enabled literal.
    A workflow that deploys silently disabled while reporting success is the exact
    false-success this design exists to prevent.
    """
    for flag in flags:
        if flag not in _OVERLAYABLE_FLAGS:
            raise ValueError(
                f"cannot enable {flag!r}: not in the overlayable set "
                f"{sorted(_OVERLAYABLE_FLAGS)}. Cost caps, model names and write-safety "
                f"constants are never overlayable."
            )

    wf = json.loads(json.dumps(workflow))  # deep copy, stdlib only — mirrors bind_credentials
    counts = {flag: 0 for flag in flags}

    for node in wf.get("nodes", []):
        js_code = node.get("parameters", {}).get("jsCode")
        if not isinstance(js_code, str):
            continue
        for flag in flags:
            disabled_decl = f"const {flag} = false;"
            enabled_decl = f"const {flag} = true;"
            occurrences = js_code.count(disabled_decl)
            if occurrences:
                js_code = js_code.replace(disabled_decl, enabled_decl)
                counts[flag] += occurrences
        node["parameters"]["jsCode"] = js_code

    # Fail-closed re-scan: any requested flag whose declaration (in ANY spacing/literal
    # form) still fails to read the enabled boolean means the exact-literal replace above
    # could not reach it — raise rather than return a workflow that deploys disabled.
    serialized = json.dumps(wf)
    for flag in flags:
        decl_re = re.compile(rf"const\s+{re.escape(flag)}\s*=\s*([^;]+);")
        for match in decl_re.finditer(serialized):
            literal = match.group(1)
            if literal != "true":
                raise ValueError(
                    f"cannot enable {flag!r} in {wf.get('name')!r}: a declaration still "
                    f"carries literal {literal!r} after rewrite. Nothing was deployed."
                )

    return wf, counts


def _requested_overlay_flags() -> list:
    """The operator-visibility flag. Reads `ENABLE_BAKED_FLAGS` — a comma-separated list
    of constant names to enable — NEVER the flags' own names. This repo's `.env` already
    defines `ALLOW_WEB_RESEARCH` and `ALLOW_SONNET_ESCALATION` for the Python harness
    lane; had the overlay read those names, a routine deploy from a developer machine
    with that `.env` sourced would have armed production silently — precisely the
    ambient-environment failure CONTEXT rejected. `ENABLE_BAKED_FLAGS` cannot collide with
    it, and because its VALUE is the explicit list of constants to flip, the enablement is
    legible in the command that performs it. Unset or empty yields an empty list, so a
    plain deploy can never arm anything. A name outside _OVERLAYABLE_FLAGS raises rather
    than silently enabling nothing, so a typo refuses the deploy instead of no-op'ing.
    """
    raw = os.getenv("ENABLE_BAKED_FLAGS", "")
    names = [n.strip() for n in raw.split(",") if n.strip()]
    for name in names:
        if name not in _OVERLAYABLE_FLAGS:
            raise ValueError(
                f"ENABLE_BAKED_FLAGS names unknown flag {name!r}; permitted: "
                f"{sorted(_OVERLAYABLE_FLAGS)}"
            )
    return names


def _create_workflow_live(body: dict):
    import requests
    payload = {k: v for k, v in body.items() if k in ("name", "nodes", "connections", "settings")}
    r = requests.post(f"{_base_url()}/api/v1/workflows", headers=_n8n_headers(), json=payload, timeout=30)
    return r.status_code, r


def _update_workflow_live(workflow_id: str, body: dict):
    import requests
    payload = {k: v for k, v in body.items() if k in ("name", "nodes", "connections", "settings")}
    r = requests.put(f"{_base_url()}/api/v1/workflows/{workflow_id}", headers=_n8n_headers(),
                      json=payload, timeout=30)
    return r.status_code, r


def main(argv=None) -> int:
    if not _has_n8n():
        print("skipped (no n8n creds): N8N_URL and N8N_API_KEY must both be set to run this deploy.")
        return 0

    if not _instance_ok():
        print("REFUSED: N8N_URL does not match the expected instance. Set N8N_EXPECTED_URL to pin "
              "it, or use a genuine *.n8n.cloud host. No API call made.")
        return 1

    local_workflows = _load_local_workflows()
    live_workflows = _get_live_workflows()
    diff = compute_workflow_diff(local_workflows, live_workflows)

    print(f"Workflows to create: {[w['name'] for w in diff['create']]}")
    print(f"Workflows to update: {[u['body']['name'] for u in diff['update']]}")

    # Phase 16.5 Task 1 — the deploy-time research/escalation overlay. Sits ABOVE the
    # write gate so a dry run reports exactly what a live run would arm, and refuses
    # (zero HTTP calls made) before credentials are even loaded. An empty request leaves
    # every existing caller and test's control flow untouched.
    try:
        requested_flags = _requested_overlay_flags()
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1

    if requested_flags:
        total_counts = {flag: 0 for flag in requested_flags}
        rewritten_in = {flag: [] for flag in requested_flags}
        try:
            new_create = []
            for wf in diff["create"]:
                new_wf, counts = enable_baked_flags(wf, requested_flags)
                for flag, n in counts.items():
                    total_counts[flag] += n
                    if n:
                        rewritten_in[flag].append(wf["name"])
                new_create.append(new_wf)
            diff["create"] = new_create

            new_update = []
            for u in diff["update"]:
                new_body, counts = enable_baked_flags(u["body"], requested_flags)
                for flag, n in counts.items():
                    total_counts[flag] += n
                    if n:
                        rewritten_in[flag].append(u["body"]["name"])
                new_update.append({"id": u["id"], "body": new_body})
            diff["update"] = new_update
        except ValueError as exc:
            print(f"REFUSED: {exc}")
            return 1

        for flag in requested_flags:
            print(f"ENABLE_BAKED_FLAGS: {flag} rewritten {total_counts[flag]}x "
                  f"in {rewritten_in[flag]}")

        zero_flags = [flag for flag in requested_flags if total_counts[flag] == 0]
        if zero_flags:
            print(f"REFUSED: requested flag(s) {zero_flags} matched zero declarations "
                  f"across the entire deploy set — nothing was deployed.")
            return 1

    if not _writes_allowed():
        print("DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_N8N_DEPLOY=true to deploy.")
        return 0

    name_to_id = _load_credential_id_map()
    failures = []

    for wf in diff["create"]:
        try:
            bound = bind_credentials(wf, name_to_id)
        except ValueError as exc:
            failures.append(("create", wf["name"], str(exc)))
            continue
        status, _ = _create_workflow_live(bound)
        if status in (200, 201):
            print(f"created workflow {wf['name']} ({status})")
        else:
            failures.append(("create", wf["name"], status))
            print(f"FAILED to create workflow {wf['name']} ({status})")

    for u in diff["update"]:
        name = u["body"]["name"]
        try:
            bound = bind_credentials(u["body"], name_to_id)
        except ValueError as exc:
            failures.append(("update", name, str(exc)))
            continue
        status, _ = _update_workflow_live(u["id"], bound)
        if status == 200:
            print(f"updated workflow {name} ({status})")
        else:
            failures.append(("update", name, status))
            print(f"FAILED to update workflow {name} ({status})")

    # Activation is a deliberate separate operator-runbook step — not performed here.
    if failures:
        print(f"\nPARTIAL FAILURE — {len(failures)} item(s) not deployed:")
        for kind, name, detail in failures:
            print(f"  {kind} {name}: {detail}")
        print("Re-run after fixing; a re-run re-diffs against a fresh GET so it is idempotent.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
