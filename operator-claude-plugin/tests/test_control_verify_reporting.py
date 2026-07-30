"""Task 3 — the reporting layer fails closed, and the PUT body filter cannot silently
desync from the deploy script.

A `GET`-after-`PUT` that only checks for a 200 reports "verified" in the good case AND in
the stuck-stale case (28-RESEARCH.md Pitfall 1). Those are different claims and this file
exists to keep them apart: a verdict is only ever `verified` when an INDEPENDENTLY fetched
value equals the requested one (D-14, D-17, T-28-02).
"""
import ast
import re
from pathlib import Path

import pytest

import n8n_control

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_SCRIPT = PLUGIN_ROOT.parent / "scripts" / "deploy_n8n_workflows.py"

FLAG_OFF = 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'
FLAG_ON = 'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'
ALLOWED = {"Decide Action"}


def _workflow(active=False, flag=FLAG_OFF):
    return {
        "id": "wf-1", "name": "LV Contact Ingest (Cloud template)", "active": active,
        "nodes": [{"name": "Decide Action", "type": "n8n-nodes-base.code",
                   "parameters": {"jsCode": flag}}],
        "connections": {}, "settings": {},
    }


def _flag(workflow):
    for node in (workflow or {}).get("nodes", []):
        if node.get("name") == "Decide Action":
            return node["parameters"]["jsCode"]
    return None


def _arm(workflow):
    for node in workflow["nodes"]:
        if node["name"] == "Decide Action":
            node["parameters"]["jsCode"] = FLAG_ON


# --- the stale read-back ---------------------------------------------------------------------


def test_an_all_200_sequence_whose_readback_is_stale_is_failed(
        fake_config, stub_module_transport_factory):
    """Every status code below is 200. The flag in the read-back is still the old one.
    This is the exact case a status-code-optimistic implementation calls verified."""
    transport = stub_module_transport_factory([
        _workflow(), {}, _workflow(),  # fetch, PUT (200), read-back STILL showing FLAG_OFF
    ])

    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert FLAG_ON in result.detail, "the detail must name what was requested"
    assert FLAG_OFF in result.detail, "the detail must name what was observed"


def test_set_active_reports_the_observed_and_requested_values_in_its_detail(
        fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(active=False), _workflow(active=True), _workflow(active=False),
    ])
    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)
    assert result.verdict == n8n_control.FAILED
    assert "true" in result.detail and "false" in result.detail


# --- non-2xx and transport failure ------------------------------------------------------------


def test_a_non_2xx_on_the_put_fabricates_no_readback_verdict(
        fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow(), (400, {"message": "bad"})])

    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert result.observed is None
    assert "400" in result.detail
    assert transport.verbs == ["get", "put"], "no read-back is attempted after a failed PUT"


def test_a_connection_error_mid_sequence_is_failed_not_a_traceback(
        fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(), ConnectionError("connection reset by peer"),
    ])

    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert result.detail


def test_a_connection_error_detail_never_echoes_the_transport_exception_text(
        fake_config, stub_module_transport_factory):
    """A transport exception's text can carry request headers, and those carry the API
    key. Report the shape of the failure, not its text."""
    transport = stub_module_transport_factory([
        _workflow(), ConnectionError(f"X-N8N-API-KEY: {fake_config['n8n_api_key']}"),
    ])
    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)
    assert fake_config["n8n_api_key"] not in (result.detail or "")


def test_a_connection_error_on_set_actives_activate_is_failed(
        fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow(), ConnectionError("down")])
    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)
    assert result.verdict == n8n_control.FAILED
    assert result.detail


# --- no verdict-producing path is status-code optimistic --------------------------------------


def _verdict_producing_sequences():
    """Every distinguishable outcome shape both entry points can produce, as
    (label, callable) — a matrix rather than one happy path, so a future refactor that
    reintroduces status-code optimism on ANY branch is caught by this file."""
    armed = _workflow(flag=FLAG_ON)
    armed_active = _workflow(active=True, flag=FLAG_ON)
    return [
        ("set_active happy", [_workflow(), _workflow(active=True), _workflow(active=True)],
         lambda cfg, t: n8n_control.set_active("wf-1", True, cfg, transport=t)),
        ("set_active stale", [_workflow(), _workflow(active=True), _workflow()],
         lambda cfg, t: n8n_control.set_active("wf-1", True, cfg, transport=t)),
        ("set_active post 500", [_workflow(), (500, {})],
         lambda cfg, t: n8n_control.set_active("wf-1", True, cfg, transport=t)),
        ("set_active unreadable readback", [_workflow(), _workflow(active=True), (503, {})],
         lambda cfg, t: n8n_control.set_active("wf-1", True, cfg, transport=t)),
        ("set_active unreadable prefetch", [(401, {})],
         lambda cfg, t: n8n_control.set_active("wf-1", True, cfg, transport=t)),
        ("set_active raising", [_workflow(), ConnectionError("x")],
         lambda cfg, t: n8n_control.set_active("wf-1", True, cfg, transport=t)),
        ("apply happy inactive", [_workflow(), {}, armed],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply happy active", [_workflow(active=True), {}, {}, {}, armed_active],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply stale", [_workflow(), {}, _workflow()],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply put 400", [_workflow(), (400, {})],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply deactivate 500", [_workflow(active=True), (500, {})],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply reactivate 500", [_workflow(active=True), {}, {}, (500, {})],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply unreadable readback", [_workflow(), {}, (503, {})],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply unreadable prefetch", [(500, {})],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
        ("apply raising", [_workflow(), ConnectionError("x")],
         lambda cfg, t: n8n_control.apply_mutation("wf-1", _arm, ALLOWED, cfg,
                                                   verify_fn=_flag, transport=t)),
    ]


def test_no_verdict_producing_path_returns_verified_without_a_matching_readback(
        fake_config, stub_module_transport_factory):
    verified_seen = 0
    for label, responses, call in _verdict_producing_sequences():
        result = call(fake_config, stub_module_transport_factory(responses))
        assert result.verdict in (n8n_control.VERIFIED, n8n_control.FAILED), label
        if result.verdict == n8n_control.VERIFIED:
            verified_seen += 1
            assert result.observed is not None, label
            assert result.observed == result.requested, label
        else:
            assert result.detail, f"{label}: a failure with no detail is unactionable"
    assert verified_seen >= 2, "the matrix has gone vacuous — no path reaches verified"


def test_every_mutationresult_takes_its_verdict_from_the_one_comparison():
    """Structural, not behavioural: every `MutationResult(...)` in the module is
    constructed with either the FAILED constant or the `verdict` name that only
    `_verdict()` can produce. A literal "verified" appearing at a construction site is
    status-code optimism sneaking back in, and this catches it without needing a test that
    happens to exercise that branch."""
    tree = ast.parse(Path(n8n_control.__file__).read_text(encoding="utf-8"))
    sites = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "MutationResult"]
    assert sites, "no MutationResult construction found — this guard has gone vacuous"
    for site in sites:
        verdict_arg = site.args[4]
        assert isinstance(verdict_arg, ast.Name) and verdict_arg.id in {"FAILED", "verdict"}, (
            f"a MutationResult at line {site.lineno} sets its verdict from "
            f"{ast.dump(verdict_arg)} rather than from _verdict()'s comparison"
        )


# --- the four-key parity pin ------------------------------------------------------------------


_FILTER_RE = re.compile(r"def _update_workflow_live.*?if k in \(([^)]*)\)", re.DOTALL)


def _deploy_filter_keys(text: str) -> set:
    """The key tuple `_update_workflow_live` filters to, read as TEXT.

    Reading rather than importing is what keeps test_no_backend_imports.py's client/backend
    boundary intact (PLUGIN-04) while still failing loudly if an admin widens or narrows
    the deploy script's filter without the plugin following.
    """
    match = _FILTER_RE.search(text)
    assert match, "_update_workflow_live's key filter is no longer recognizable — re-derive it"
    return set(ast.literal_eval(f"({match.group(1)})"))


def test_the_put_body_filter_matches_the_deploy_scripts():
    assert _deploy_filter_keys(DEPLOY_SCRIPT.read_text(encoding="utf-8")) == set(
        n8n_control.PUT_BODY_KEYS)


def test_the_parity_pin_bites_when_the_deploy_filter_is_narrowed():
    """Non-vacuity: the pin above must actually fail on a desync, not just pass."""
    tampered = DEPLOY_SCRIPT.read_text(encoding="utf-8").replace(
        '("name", "nodes", "connections", "settings")', '("name", "nodes", "connections")')
    assert _deploy_filter_keys(tampered) != set(n8n_control.PUT_BODY_KEYS)


def test_the_plugin_does_not_import_the_deploy_script():
    tree = ast.parse(Path(n8n_control.__file__).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    imported |= {str(node.module) for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.module}
    assert not any(name.startswith(("deploy_n8n_workflows", "scripts")) for name in imported), (
        f"the four-key filter is held by the pin test above, never by an import: {imported}"
    )


# --- credentials come from the config, never the shell ------------------------------------------


def test_the_control_module_never_reads_a_shell_credential():
    """A guard reading os.getenv("N8N_URL") while the request authenticates from
    config/operator.local.json is a guard that cannot fire (D-29)."""
    source = Path(n8n_control.__file__).read_text(encoding="utf-8")
    for forbidden in ("os.getenv", "os.environ", "N8N_API_KEY\"", "N8N_URL\""):
        assert forbidden not in source, f"{forbidden} in n8n_control.py"


@pytest.mark.parametrize("workflow_id", ["wf-1", "wf-2"])
def test_every_url_is_built_from_the_configured_base(workflow_id, fake_config,
                                                     stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow(), {}, _workflow(active=True)])
    n8n_control.set_active(workflow_id, True, fake_config, transport=transport)
    for call in transport.calls:
        assert call["url"].startswith(fake_config["n8n_url"])
        assert workflow_id in call["url"]
