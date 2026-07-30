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
    # Phase 25 Plan 02 (D-14) — `wf_backend_status_cloud.json`'s trigger. Binds the SAME
    # shared webhook-secret credential the enrichment trigger binds ("LV Enrichment
    # Webhook") — one operator secret works against both endpoints, no new provisioning.
    # Every provider probe node in that workflow reuses a name already mapped above.
    "Status Webhook Trigger": {"cred_type": "httpHeaderAuth", "cred_name": "LV Enrichment Webhook"},
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


# Phase 16.5 Task 1, widened as prep for the Phase 16.7 write-path canary — the
# deploy-time overlay's closed target set.
# `MAX_WEB_RESEARCH_PER_RUN` / `MAX_JUDGE_VALIDATIONS_PER_RUN` / `ANTHROPIC_RESEARCH_MODEL`
# / `ANTHROPIC_JUDGE_MODEL` are also CONFIG_FLAG_DEFAULTS entries but would let an
# open-ended mechanism widen cost caps or swap models — "enabling one thing must not
# widen anything else" has to be structural, not a convention, so a name outside this
# table is a ValueError, never a silent no-op. `ALLOW_JUDGE_ESCALATION` and
# `ALLOW_WEB_RESEARCH` are ALSO excluded on purpose (quick-260730-din, quick-260730-fij):
# both now default to `true` at build time, so the overlay — which only ever widens
# disabled->enabled — has no meaningful entry for either; the emergency-off path is
# editing CONFIG_FLAG_DEFAULTS + rebuild + disarmed redeploy.
# Deliberately NOT imported from build_cloud_workflows — that module runs
# taxonomy/escalation codegen at import time and writes into n8n/code/; a deploy script
# must never carry that side effect. tests/test_enabled_build_invariants.py pins this
# table against CONFIG_FLAG_DEFAULTS / WRITE_SAFETY_DEFAULTS from a TEST, which may
# import freely — including each entry's disabled literal, so a change to how the builder
# bakes a constant cannot silently make the exact-literal rewrite below stop matching.
#
# Each entry: name -> (disabled_literal, default_enabled_literal, takes_value)
#   disabled_literal        the EXACT JS literal the builder bakes for the safe default.
#                           `_flag_const(..., cloud=True)` emits a BARE boolean;
#                           `_write_safety_const()` emits a JSON STRING — hence both forms.
#   default_enabled_literal what a bare `NAME` request rewrites to. None => a value is
#                           mandatory (an allowlist with no value is meaningless).
#   takes_value             whether `NAME=VALUE` is accepted; the value is rendered with
#                           json.dumps, so it is always a quoted JS string literal.
_OVERLAY_FLAG_SPEC = {
    # Write-safety constants. Overlayable so the write-path canary can arm ONE record
    # without a rebuild, and guarded below: writes cannot be enabled unless the same
    # invocation also supplies a non-empty allowlist.
    "ALLOW_HUBSPOT_RECORD_WRITES": ('"false"', '"true"', False),
    "ALLOW_HUBSPOT_CREATE":        ('"false"', '"true"', False),
    "TEST_RECORD_IDS":             ('""', None, True),
    "TEST_RECORD_DOMAINS":         ('""', None, True),
}
_OVERLAYABLE_FLAGS = frozenset(_OVERLAY_FLAG_SPEC)
_WRITE_ENABLING_FLAGS = frozenset({"ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"})
_ALLOWLIST_FLAGS = frozenset({"TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"})
# `,` already separates ENTRIES in ENABLE_BAKED_FLAGS, so a multi-id allowlist value
# uses `|` and is rendered back to the comma-separated form `_writeSafetyAllows()` splits
# on. No HubSpot object id or domain contains either character.
_ALLOWLIST_VALUE_RE = re.compile(r"[A-Za-z0-9._-]+(?:\|[A-Za-z0-9._-]+)*")


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


def rebind_subworkflow_refs(workflow: dict, live_by_name: dict) -> dict:
    """Pure, deep-copying, fail-closed — same shape as bind_credentials(). BUG 20
    (found live 2026-07-29, first-ever activation attempt of LV Scheduled Maintenance):
    the builder bakes executeWorkflow nodes with the LOCAL template id
    (`LVenrichmentCloud01`), but n8n assigns its own server-side id on create and this
    deploy matches workflows by NAME — so the reference points at an id that has never
    existed on the server, and activation 400s with "references workflow ... which is
    not published". The node's `cachedResultName` carries the referenced workflow's NAME,
    which is the one identifier stable across both sides; rewrite the id from a fresh
    live name->id map. A referenced name with no live workflow fails the deploy closed
    (deploy the referenced workflow first; the idempotent re-run then resolves it)."""
    wf = json.loads(json.dumps(workflow))  # deep copy, stdlib only
    for node in wf.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.executeWorkflow":
            continue
        ref = node.get("parameters", {}).get("workflowId")
        if not isinstance(ref, dict):
            continue
        target_name = ref.get("cachedResultName")
        live = live_by_name.get(target_name)
        if live is None:
            raise ValueError(
                f"cannot deploy {wf.get('name')!r}: node {node.get('name')!r} references "
                f"sub-workflow {target_name!r}, which does not exist on the instance yet. "
                f"Deploy the referenced workflow first, then re-run (idempotent)."
            )
        ref["value"] = live["id"]
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
        if flag not in _OVERLAY_FLAG_SPEC:
            raise ValueError(
                f"cannot enable {flag!r}: not in the overlayable set "
                f"{sorted(_OVERLAYABLE_FLAGS)}. Cost caps and model names are never "
                f"overlayable."
            )

    # A bare sequence of names keeps working (every pre-16.7 caller passes one) and means
    # "each flag's default enabled literal"; a mapping carries an explicit target literal.
    if isinstance(flags, dict):
        targets = dict(flags)
    else:
        targets = {}
        for flag in flags:
            default_enabled = _OVERLAY_FLAG_SPEC[flag][1]
            if default_enabled is None:
                raise ValueError(
                    f"{flag} requires an explicit target value; pass a "
                    f"{{flag: literal}} mapping rather than a bare name"
                )
            targets[flag] = default_enabled

    wf = json.loads(json.dumps(workflow))  # deep copy, stdlib only — mirrors bind_credentials
    counts = {flag: 0 for flag in targets}

    for node in wf.get("nodes", []):
        js_code = node.get("parameters", {}).get("jsCode")
        if not isinstance(js_code, str):
            continue
        for flag, target_literal in targets.items():
            disabled_decl = f"const {flag} = {_OVERLAY_FLAG_SPEC[flag][0]};"
            enabled_decl = f"const {flag} = {target_literal};"
            occurrences = js_code.count(disabled_decl)
            if occurrences:
                js_code = js_code.replace(disabled_decl, enabled_decl)
                counts[flag] += occurrences
        node["parameters"]["jsCode"] = js_code

    # Fail-closed re-scan: any requested flag whose declaration (in ANY spacing/literal
    # form) still fails to read the target literal means the exact-literal replace above
    # could not reach it — raise rather than return a workflow that deploys disabled.
    # Scanned per-node over the raw jsCode, not over json.dumps(wf), so a JSON-string
    # literal's quotes are compared as written rather than in their escaped form.
    for flag, target_literal in targets.items():
        decl_re = re.compile(rf"const\s+{re.escape(flag)}\s*=\s*([^;]+);")
        for node in wf.get("nodes", []):
            js_code = node.get("parameters", {}).get("jsCode")
            if not isinstance(js_code, str):
                continue
            for match in decl_re.finditer(js_code):
                literal = match.group(1)
                if literal != target_literal:
                    raise ValueError(
                        f"cannot enable {flag!r} in {wf.get('name')!r}: a declaration "
                        f"still carries literal {literal!r} after rewrite. Nothing was "
                        f"deployed."
                    )

    return wf, counts


def _requested_overlay_flags() -> dict:
    """The operator-visibility flag. Reads `ENABLE_BAKED_FLAGS` — a comma-separated list
    of constant names to enable — NEVER the flags' own names. This repo's `.env` already
    defines `ALLOW_WEB_RESEARCH`/`ALLOW_JUDGE_ESCALATION` for the Python harness lane; had
    the overlay read either name, a routine deploy from a developer machine with that
    `.env` sourced would have armed production silently — precisely the
    ambient-environment failure CONTEXT rejected. `ENABLE_BAKED_FLAGS` cannot collide with
    either, and because its VALUE is the explicit list of constants to flip, the
    enablement is legible in the command that performs it. Unset or empty yields an empty
    list, so a plain deploy can never arm anything. A name outside _OVERLAYABLE_FLAGS
    raises rather than silently enabling nothing, so a typo refuses the deploy instead of
    no-op'ing. There is no remaining non-write-safety overlay target — both web research
    (quick-260730-fij) and judge escalation (quick-260730-din) are now armed at build time
    and are not overlayable at all.

    An entry is either a bare `NAME` (rewrites to that flag's default enabled literal) or
    `NAME=VALUE` for the allowlist constants, whose point is a value rather than a flip.
    VALUE is rendered with json.dumps, so it always lands as a quoted JS string literal
    and can never inject arbitrary JS. Returns an ordered {name: target_literal} mapping.
    """
    raw = os.getenv("ENABLE_BAKED_FLAGS", "")
    entries = [n.strip() for n in raw.split(",") if n.strip()]
    requested = {}
    for entry in entries:
        name, sep, value = entry.partition("=")
        name = name.strip()
        if name not in _OVERLAY_FLAG_SPEC:
            raise ValueError(
                f"ENABLE_BAKED_FLAGS names unknown flag {name!r}; permitted: "
                f"{sorted(_OVERLAYABLE_FLAGS)}"
            )
        disabled_literal, default_enabled, takes_value = _OVERLAY_FLAG_SPEC[name]
        if sep:
            if not takes_value:
                raise ValueError(
                    f"{name} is a boolean kill switch and takes no value; write it bare "
                    f"as {name!r}, not {entry!r}"
                )
            candidate = value.strip()
            # Allowlist values are HubSpot object ids and domains — nothing else. The
            # charset is enforced rather than merely escaped because the fail-closed
            # re-scan's declaration regex terminates at the first `;`, so a value
            # containing one would split a declaration it then could not verify. A
            # narrow charset removes that class outright instead of widening the parser.
            if not _ALLOWLIST_VALUE_RE.fullmatch(candidate):
                raise ValueError(
                    f"{name} value {candidate!r} is not a plain id/domain list: only "
                    f"letters, digits, '.', '-', '_' and ',' separators are permitted"
                )
            target = json.dumps(candidate.replace("|", ","))
        else:
            if default_enabled is None:
                raise ValueError(
                    f"{name} requires an explicit value ({name}=<value>) — enabling it "
                    f"bare would leave the allowlist empty, which denies everything and "
                    f"makes the request a silent no-op"
                )
            target = default_enabled
        if target == disabled_literal:
            raise ValueError(
                f"{name} was requested with the DISABLED literal {target} — that is a "
                f"no-op dressed as an enablement; omit the flag instead"
            )
        requested[name] = target

    # Fail-safe: writes may not be armed without an allowlist in the SAME invocation.
    # `_writeSafetyAllows()` denies everything on an empty allowlist, so this cannot
    # currently cause a write — it exists so that stops being true by accident.
    if requested.keys() & _WRITE_ENABLING_FLAGS:
        allowlisted = {f for f in requested.keys() & _ALLOWLIST_FLAGS if requested[f] != '""'}
        if not allowlisted:
            raise ValueError(
                "refusing to enable HubSpot writes without an allowlist: name "
                "TEST_RECORD_IDS=<id[,id]> and/or TEST_RECORD_DOMAINS=<domain> in the "
                "same ENABLE_BAKED_FLAGS request"
            )
    if "ALLOW_HUBSPOT_CREATE" in requested and "ALLOW_HUBSPOT_RECORD_WRITES" not in requested:
        raise ValueError(
            "ALLOW_HUBSPOT_CREATE has no effect unless ALLOW_HUBSPOT_RECORD_WRITES is "
            "enabled in the same request — the gate checks record-writes first"
        )
    return requested


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
            print(f"ENABLE_BAKED_FLAGS: {flag} -> {requested_flags[flag]} rewritten "
                  f"{total_counts[flag]}x in {rewritten_in[flag]}")

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
    live_by_name = {w["name"]: w for w in live_workflows}
    failures = []

    for wf in diff["create"]:
        try:
            bound = bind_credentials(rebind_subworkflow_refs(wf, live_by_name), name_to_id)
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
            bound = bind_credentials(rebind_subworkflow_refs(u["body"], live_by_name), name_to_id)
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
