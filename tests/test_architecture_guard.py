"""Architecture guard: the deliverable is n8n workflow JSON, not deployed middleware.

Cites docs/WEB-RESEARCH-SPEC.md §0.5 (AR-1..AR-4).

The constraint is "no custom middleware deployed to an IaaS". That is easy to state and
easy to erode — one HTTP Request node pointed at a service we host and the workflows stop
being self-contained. These tests make the erosion mechanical to detect.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
N8N = ROOT / "n8n"

# Workflows intended for n8n Cloud. Everything here must be self-contained.
ACTIVE = [
    "wf_contact_ingest_cloud.json",
    "wf_contact_ingest_local.json",
    "wf_enrichment_cloud.json",
    "wf_enrichment_local.json",
    "wf_enrichment_local_live.json",
]

# Superseded Milestone-2 workflows. These are ONLY a trigger + a POST to the FastAPI
# service in src/service.py — i.e. exactly the middleware pattern AR-1 forbids. They are
# replaced by wf_contact_ingest_*.json and must not reach n8n Cloud. Excluded by name so
# the exemption is explicit and greppable rather than silent.
DEPRECATED_SERVICE_DEPENDENT = [
    "wf_upload_ingest.json",
    "wf_weekly_sweep.json",
]

# Third-party APIs the workflows legitimately consume (AR-2).
ALLOWED_HOSTS = {
    "api.hubapi.com",           # HubSpot CRM
    "api.lusha.com",            # provider
    "api.apollo.io",            # provider
    "api.zoominfo.com",         # provider + GTM OAuth
    "api.anthropic.com",        # Haiku / Sonnet / web_search
    "rapid-email-verifier.fly.dev",  # email verification (contacts branch)
    # Fixture/sample data only — never fetched at runtime.
    "linkedin.com",
    "www.linkedin.com",
}

URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)")


def _hosts_in(workflow_path: Path):
    """Every HTTP host referenced anywhere in a workflow's node parameters."""
    doc = json.loads(workflow_path.read_text())
    found = {}
    for node in doc.get("nodes", []):
        blob = json.dumps(node.get("parameters", {}))
        for host in URL_RE.findall(blob):
            found.setdefault(host, set()).add(node.get("name", "?"))
    return found


@pytest.mark.parametrize("name", ACTIVE)
def test_ar2_no_middleware_hosts(name):
    """AR-2: active workflows may only call third-party APIs we consume.

    A host outside the allowlist means either a new legitimate dependency (add it here,
    deliberately) or middleware creep (the thing this guard exists to catch).
    """
    offenders = {
        host: sorted(nodes)
        for host, nodes in _hosts_in(N8N / name).items()
        if host not in ALLOWED_HOSTS
    }
    assert not offenders, (
        f"{name} references non-allowlisted host(s): {offenders}. "
        "Either add a deliberate entry to ALLOWED_HOSTS, or remove the dependency — "
        "the deliverable is self-contained n8n workflows (spec AR-1/AR-2)."
    )


@pytest.mark.parametrize("name", ACTIVE)
def test_ar1_no_localhost_or_private_service(name):
    """AR-1: nothing may point at a service this project deploys and hosts."""
    bad = [
        host
        for host in _hosts_in(N8N / name)
        if host in {"localhost", "127.0.0.1", "0.0.0.0"}
        or host.startswith("host.docker.internal")
        or host.endswith(".local")
    ]
    assert not bad, f"{name} depends on a self-hosted service: {bad} (spec AR-1)"


@pytest.mark.parametrize("name", DEPRECATED_SERVICE_DEPENDENT)
def test_deprecated_workflows_are_still_the_only_service_callers(name):
    """Pins the known deviation so it cannot silently spread.

    These two ARE service-dependent — that is why they are quarantined. This test asserts
    the deviation still looks exactly as documented in spec §0.5, so if someone "fixes"
    them n8n-natively the exemption gets removed rather than lingering, and if someone
    copies the pattern into an active workflow the AR-1 test above catches it.
    """
    path = N8N / name
    if not path.exists():
        pytest.skip(f"{name} already retired — remove it from the exemption list")
    hosts = _hosts_in(path)
    assert any(h.startswith("host.docker.internal") for h in hosts), (
        f"{name} no longer calls the decision service. If it was ported to be "
        "n8n-native, move it into ACTIVE and drop it from DEPRECATED_SERVICE_DEPENDENT."
    )


def _strip_js_comments(js: str) -> str:
    """Drop // line comments and /* */ blocks.

    Necessary because the inlined Code-node JS legitimately CITES the Python oracle in
    provenance comments ("Mirrors the DETERMINISTIC parts of src/merge_policy.py"). Those
    mentions are documentation, not runtime coupling — matching on the raw text would
    flag every workflow and the guard would be worse than useless.
    """
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


@pytest.mark.parametrize("name", ACTIVE)
def test_ar3_no_runtime_escape_from_n8n(name):
    """AR-3: src/*.py is a dev oracle — no node may shell out or spawn a process.

    Checks real execution primitives, not string mentions.
    """
    doc = json.loads((N8N / name).read_text())

    shell_nodes = [
        n["name"] for n in doc.get("nodes", [])
        if n.get("type", "").endswith(("executeCommand", "ssh"))
    ]
    assert not shell_nodes, (
        f"{name} contains shell-executing node(s): {shell_nodes} — workflows must run "
        "entirely inside n8n (spec AR-1/AR-3)."
    )

    offenders = []
    for node in doc.get("nodes", []):
        code = node.get("parameters", {}).get("jsCode")
        if not code:
            continue
        body = _strip_js_comments(code)
        # These are needles searched FOR in node source, not calls made here — this test
        # never executes workflow code, it only inspects it as text.
        for prim in ("child_process", "execSync(", "spawnSync(", "spawn(", "eval("):
            if prim in body:
                offenders.append((node["name"], prim))
    assert not offenders, (
        f"{name} escapes the n8n sandbox at runtime: {offenders} (spec AR-3)."
    )
