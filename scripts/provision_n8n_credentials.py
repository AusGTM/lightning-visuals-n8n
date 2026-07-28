#!/usr/bin/env python3
"""scripts/provision_n8n_credentials.py

Phase 16 Task 1 — provision the n8n Cloud credentials the built Cloud workflows bind
to, via the n8n Public API.

Same idiom as scripts/sync_hubspot_properties.py / scripts/deploy_n8n_workflows.py:
env-gated, dry-run-by-default, `_has_n8n()` skip-to-exit-0, a two-key write gate
(DRY_RUN=false AND ALLOW_N8N_DEPLOY=true).

CREATE-IF-MISSING ONLY (never update-in-place): n8n never returns a credential's `data`
back on GET, so there is nothing to diff against — rotating a secret is a manual
delete+recreate operator action, not something this script attempts.

Six provider/CRM secrets map to five credential objects (ZoomInfo holds both client id +
secret in one credential), plus a 7th credential (Task 6) for the Cloud webhook's shared-
secret gate — six credential objects total. For each, the schema at
`GET /api/v1/credentials/schema/{type}` is introspected once and the field names this
script is about to send are checked against it before POSTing — a differing type name /
400 / 404 aborts that one credential with a clean banner, not a stack trace.

NEVER prints a secret value — only credential names and HTTP status codes.

Usage:
    python scripts/provision_n8n_credentials.py          # dry-run (default, zero writes)
    DRY_RUN=false ALLOW_N8N_DEPLOY=true \
        python scripts/provision_n8n_credentials.py       # live create-if-missing

Output: writes the credential name->id map (names + ids only, never secret values) to
`.n8n_credential_ids.json` (gitignored) so deploy_n8n_workflows.py's `bind_credentials`
can resolve node credentials without a second interactive step.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CRED_ID_MAP_PATH = ROOT / ".n8n_credential_ids.json"


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _instance_ok() -> bool:
    """Same no-fail-open wrong-instance guard as deploy_n8n_workflows.py."""
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


# --- the 6 secrets across ~5 credential objects ------------------------------------
#
# ZoomInfo's credential `type` — Task 2 decision: split-code-node (credential-bound HTTP
# Mint node + secret-free cache/gate/enrich Code nodes), NOT native OAuth2. The Mint node
# (scripts/build_cloud_workflows.py::_zoom_mint_node) is bound to a generic Basic Auth
# credential holding client_id (user) : client_secret (password) — n8n injects the Basic
# auth header from this credential; the ZoomInfo token endpoint accepts it directly
# (no separate Authorization header literal anywhere in the built workflow).
ZOOMINFO_CREDENTIAL_TYPE = "httpBasicAuth"


def _hubspot_data() -> dict:
    # Field name is `appToken`, NOT `accessToken` — confirmed by live schema introspection
    # against n8n Cloud 2026-07-28 (GET /api/v1/credentials/schema/hubspotAppToken returns
    # properties {appToken, allowedHttpRequestDomains, allowedDomains}). The original
    # `accessToken` guess was caught by this script's own schema-mismatch guard, which
    # aborted the credential rather than creating an unusable one — the guard working as
    # designed on the first live provisioning run.
    return {"appToken": os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")}


def _lusha_data() -> dict:
    return {"name": "api_key", "value": os.getenv("LUSHA_API_KEY")}


def _apollo_data() -> dict:
    return {"name": "X-Api-Key", "value": os.getenv("APOLLO_API_KEY")}


def _anthropic_data() -> dict:
    return {"name": "x-api-key", "value": os.getenv("ANTHROPIC_API_KEY")}


def _zoominfo_data() -> dict:
    # n8n's generic httpBasicAuth credential schema is {user, password} — the Mint HTTP
    # node's Basic auth header is built FROM this credential (client_id:client_secret
    # base64), never inlined as a header literal.
    return {
        "user": os.getenv("ZOOMINFO_CLIENT_ID"),
        "password": os.getenv("ZOOMINFO_CLIENT_SECRET"),
    }


def _webhook_secret_data() -> dict:
    # Task 6 (review #7, CLAUDE.md §18.1) — a 7th secret, separate from the 6 provider/
    # CRM secrets above: the Cloud webhook's shared-secret gate. Bound to the Webhook
    # Trigger node's native Header Auth (n8n-nodes-base.webhook, authentication=
    # "headerAuth") — never read by a Code node, never $env/$vars.
    return {"name": "X-Enrichment-Secret", "value": os.getenv("N8N_ENRICHMENT_WEBHOOK_SECRET")}


CREDENTIAL_MANIFEST = [
    {"name": "LV HubSpot", "type": "hubspotAppToken", "data_fn": _hubspot_data},
    {"name": "LV Lusha", "type": "httpHeaderAuth", "data_fn": _lusha_data},
    {"name": "LV Apollo", "type": "httpHeaderAuth", "data_fn": _apollo_data},
    {"name": "LV Anthropic", "type": "httpHeaderAuth", "data_fn": _anthropic_data},
    {"name": "LV ZoomInfo", "type": ZOOMINFO_CREDENTIAL_TYPE, "data_fn": _zoominfo_data},
    {"name": "LV Enrichment Webhook", "type": "httpHeaderAuth", "data_fn": _webhook_secret_data},
]


def _get_live_credentials() -> list:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/credentials", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def _get_credential_schema(cred_type: str) -> dict:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/credentials/schema/{cred_type}",
                      headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _schema_matches(cred_type: str, data: dict) -> bool:
    """Introspect the credential type's schema and assert the field names this script is
    about to send match, before POSTing. A differing type / 400 / 404 aborts gracefully
    with a clean banner — never a stack trace."""
    import requests
    try:
        schema = _get_credential_schema(cred_type)
    except requests.RequestException as exc:
        print(f"WARNING: could not introspect schema for credential type {cred_type!r} ({exc}); "
              "aborting this credential — not created.")
        return False
    props = schema.get("properties", {})
    if not isinstance(props, dict) or not props:
        # Some credential types return a schema shape this script doesn't recognize;
        # proceed rather than block on an assertion this script can't evaluate.
        return True
    expected_fields = set(props.keys())
    sent_fields = set(data.keys())
    if not sent_fields <= expected_fields:
        print(f"WARNING: credential type {cred_type!r} schema fields {sorted(expected_fields)} "
              f"do not match the fields this script would send {sorted(sent_fields)}; "
              "aborting this credential — not created.")
        return False
    return True


def _create_credential_live(name: str, cred_type: str, data: dict):
    import requests
    body = {"name": name, "type": cred_type, "data": data}  # NEVER printed/logged
    r = requests.post(f"{_base_url()}/api/v1/credentials", headers=_n8n_headers(),
                       json=body, timeout=30)
    return r.status_code


def write_credential_id_map(id_map: dict, path: Path = CRED_ID_MAP_PATH) -> Path:
    """Names + ids only — asserted by the caller never to include secret data."""
    path.write_text(json.dumps(id_map, indent=2, sort_keys=True) + "\n")
    return path


def provision(manifest: list, live_writes: bool) -> tuple:
    """Returns (id_map, failures). id_map holds every manifest entry already-existing
    live or freshly created this run (names + ids only). failures is a list of
    (name, reason) tuples for entries this run could not resolve."""
    live_by_name = {c["name"]: c["id"] for c in _get_live_credentials()} if _has_n8n() else {}

    id_map = {}
    failures = []
    for entry in manifest:
        name, cred_type = entry["name"], entry["type"]

        if cred_type is None:
            print(f"skipping {name!r}: credential type pending the Task 2 ZoomInfo decision.")
            continue

        if name in live_by_name:
            id_map[name] = live_by_name[name]
            print(f"found existing credential {name!r} (create-if-missing — no update).")
            continue

        if not live_writes:
            print(f"would create credential {name!r} (type={cred_type}).")
            continue

        data = entry["data_fn"]()
        if any(v in (None, "") for v in data.values()):
            failures.append((name, "one or more required secret env vars are unset"))
            print(f"FAILED to prepare credential {name!r}: required env var(s) unset.")
            continue

        if not _schema_matches(cred_type, data):
            failures.append((name, "schema introspection mismatch"))
            continue

        status = _create_credential_live(name, cred_type, data)
        if status in (200, 201):
            print(f"created credential {name!r} ({status})")
        else:
            failures.append((name, status))
            print(f"FAILED to create credential {name!r} ({status})")

    if live_writes:
        fresh_by_name = {c["name"]: c["id"] for c in _get_live_credentials()}
        for entry in manifest:
            if entry["type"] is not None and entry["name"] in fresh_by_name:
                id_map[entry["name"]] = fresh_by_name[entry["name"]]

    return id_map, failures


def main(argv=None) -> int:
    if not _has_n8n():
        print("skipped (no n8n creds): N8N_URL and N8N_API_KEY must both be set to run "
              "credential provisioning.")
        return 0

    if not _instance_ok():
        print("REFUSED: N8N_URL does not match the expected instance. Set N8N_EXPECTED_URL to "
              "pin it, or use a genuine *.n8n.cloud host. No API call made.")
        return 1

    live_writes = _writes_allowed()
    if not live_writes:
        print("DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_N8N_DEPLOY=true to create.")

    id_map, failures = provision(CREDENTIAL_MANIFEST, live_writes)

    if id_map:
        path = write_credential_id_map(id_map)
        print(f"credential id map: {path}")

    if failures:
        print(f"\nPARTIAL FAILURE — {len(failures)} credential(s) not provisioned:")
        for name, reason in failures:
            print(f"  {name}: {reason}")
        print("Re-run after fixing; creation is create-if-missing so successes are not repeated.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
