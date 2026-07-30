"""The conversational answer and the skill that gives it (27-04 Task 3).

D-09: text is this surface's default form. The properties asserted here are the ones that
make the text honest rather than pretty — a null reads as `unknown` and never as a zero or
a blank, a wedged run states the threshold it was judged against, a recognised failure
carries no status code or stack, and an unrecognised one keeps its raw text visibly apart
from the interpretation.
"""
import re
from pathlib import Path

import yaml

import render_text
import status

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PLUGIN_ROOT / "skills" / "backend-status" / "SKILL.md"

TRACEBACK_MARKERS = ("Traceback", "  File \"", "raise ", ".py\", line")


def _last_run(**overrides):
    base = {"execution_id": "e-1", "status": "success", "started_at": None,
            "stopped_at": None, "never_run": False, "in_flight": False,
            "running_for_minutes": None, "stuck": False,
            "stuck_threshold_minutes": 15, "error": None}
    base.update(overrides)
    return base


def _workflow(**overrides):
    base = {
        "workflow_id": "wf-1",
        "name": "LV Contact Ingest (Cloud template)",
        "active": True,
        "write_safety": {
            "ALLOW_HUBSPOT_RECORD_WRITES": {"value": "false", "nodes": ["Decide Action"],
                                            "disagreement": None},
            "ALLOW_HUBSPOT_CREATE": {"value": "false", "nodes": ["Decide Action"],
                                     "disagreement": None},
        },
        "last_run": _last_run(),
        "in_flight": False,
    }
    base.update(overrides)
    return base


def _report(workflows=None, backend=None):
    return {
        "workflows": {"readable": True,
                      "workflows": [_workflow()] if workflows is None else workflows},
        "backend": backend if backend is not None else _backend(),
    }


def _backend(counts=None, available=True):
    return {
        "available": available,
        "reason": None,
        "counts": counts if counts is not None else {
            "companies_requested_unresolved": "3",
            "companies_awaiting_review": "0",
            "contacts_requested_unresolved": "unknown",
            "contacts_awaiting_review": "7",
        },
        "credential_health": ["lusha — answering", "apollo — refused (http_403)"],
        "balances": [{"provider": "lusha", "credits": "412"},
                     {"provider": "apollo", "credits": "unknown"}],
        "checked_at": "2026-07-31T00:00:00.000Z",
    }


# --- per workflow: on/off, live writes, last run, in flight ---------------------------


def test_the_answer_carries_on_off_live_writes_last_run_and_in_flight():
    text = render_text.render_report(_report())

    assert "LV Contact Ingest (Cloud template)" in text
    assert "Switched on" in text
    assert "ALLOW_HUBSPOT_CREATE off" in text
    assert "Last run: success" in text
    assert "nothing running" in text


def test_an_off_workflow_reads_off_not_blank():
    text = render_text.render_report(_report([_workflow(active=False)]))
    assert "Switched off" in text


def test_an_unreadable_workflow_reads_unknown_for_every_field():
    text = render_text.render_report(_report([_workflow(
        name=None, active=None,
        write_safety={"ALLOW_HUBSPOT_CREATE": {"value": None, "nodes": [],
                                               "disagreement": None}},
        last_run=_last_run(status=None, in_flight=None, error="could_not_read_executions"))]))

    assert "Switched unknown" in text
    assert "ALLOW_HUBSPOT_CREATE unknown" in text
    assert "Last run: unknown" in text


def test_a_write_safety_disagreement_reads_unknown_rather_than_a_guess():
    text = render_text.render_report(_report([_workflow(write_safety={
        "ALLOW_HUBSPOT_CREATE": {"value": None, "nodes": ["A", "B"],
                                 "disagreement": [{"node": "A", "value": "true"},
                                                  {"node": "B", "value": "false"}]}})]))
    assert "the declaring nodes disagree" in text


def test_a_never_run_workflow_says_so_rather_than_reading_unknown():
    text = render_text.render_report(_report([_workflow(
        last_run=_last_run(status=None, never_run=True))]))
    assert "never" in text.lower()


def test_an_unreadable_workflow_collection_is_unknown_not_an_empty_answer():
    report = _report()
    report["workflows"] = {"readable": False, "workflows": []}
    text = render_text.render_report(report)

    assert "unknown" in text
    assert "no workflows at all" not in text


# --- stuck: the age and the threshold, in the same sentence ---------------------------


def test_a_stuck_run_states_its_elapsed_time_and_the_threshold_together():
    text = render_text.render_report(_report([_workflow(
        in_flight=True,
        last_run=_last_run(status="running", in_flight=True, running_for_minutes=42.4,
                           stuck=True, stuck_threshold_minutes=15))]))

    sentence = next(line for line in text.splitlines() if line.startswith("Right now:"))
    assert "42" in sentence and "15" in sentence


def test_a_run_under_the_threshold_reads_as_running_not_wedged():
    text = render_text.render_report(_report([_workflow(
        in_flight=True,
        last_run=_last_run(status="running", in_flight=True, running_for_minutes=4.0,
                           stuck=False))]))
    assert "wedged mark is 15 minutes" in text


def test_an_unknown_age_run_says_the_age_is_unknown_and_does_not_call_it_wedged():
    text = render_text.render_report(_report([_workflow(
        in_flight=True,
        last_run=_last_run(status="running", in_flight=True, running_for_minutes=None,
                           stuck=None))]))

    sentence = next(line for line in text.splitlines() if line.startswith("Right now:"))
    assert "unknown" in sentence
    assert "wedged" in sentence  # names the mark it could NOT be judged against


# --- failure rendering ----------------------------------------------------------------


def _finding(**overrides):
    base = {"node": "Lusha Enrich", "level": "item", "count": 1, "matched": True,
            "cause": "expired_credential",
            "sentence": "The saved login for one of the connected services was rejected, "
                        "so nothing could be looked up until it is renewed.",
            "who_can_fix": "admin", "is_interpretation": False,
            "raw": "401 Unauthorized"}
    base.update(overrides)
    return base


def test_a_failed_run_renders_its_translated_sentence_and_its_attribution():
    text = render_text.render_report(_report([_workflow(
        last_run=_last_run(status="error"),
        failure={"available": True, "reason": None, "findings": [_finding()]})]))

    assert "The saved login for one of the connected services was rejected" in text
    assert "who can act: admin" in text


def test_a_rendered_failed_run_carries_no_status_code_and_no_traceback():
    text = render_text.render_report(_report([_workflow(
        last_run=_last_run(status="error"),
        failure={"available": True, "reason": None, "findings": [_finding()]})]))

    block = text.split("Why it failed:")[1].split("## ")[0]
    assert not re.search(r"\b\d{3}\b", block), block
    for marker in TRACEBACK_MARKERS:
        assert marker not in block
    assert "Lusha Enrich" not in block


def test_an_unrecognised_failure_keeps_its_label_and_its_raw_text_apart():
    text = render_text.render_report(_report([_workflow(
        last_run=_last_run(status="error"),
        failure={"available": True, "reason": None, "findings": [_finding(
            matched=False, cause=None, is_interpretation=True,
            sentence="This failure signature is not one the plugin recognises.",
            raw="flurble exploded sideways")]})]))

    assert "interpretation:" in text
    assert "raw error text: flurble exploded sideways" in text
    lines = text.splitlines()
    assert lines.index("    interpretation: This failure signature is not one the "
                       "plugin recognises.") < lines.index(
        "    raw error text: flurble exploded sideways")


def test_a_repeated_failure_reads_as_one_problem_with_a_count():
    text = render_text.render_report(_report([_workflow(
        last_run=_last_run(status="error"),
        failure={"available": True, "reason": None,
                 "findings": [_finding(count=100)]})]))
    assert "seen 100 times" in text


def test_an_unreadable_failure_detail_reads_unknown():
    text = render_text.render_report(_report([_workflow(
        last_run=_last_run(status="error"),
        failure={"available": False, "reason": "that execution's detail could not be read",
                 "findings": []})]))
    assert "Why it failed: unknown" in text


# --- records waiting on a human -------------------------------------------------------


def test_the_answer_carries_queued_and_review_counts_for_both_object_types():
    text = render_text.render_report(_report())

    assert "Companies queued for enrichment: 3" in text
    assert "Contacts queued for enrichment: unknown" in text
    assert "Companies waiting on a review decision: 0" in text
    assert "Contacts waiting on a review decision: 7" in text


def test_a_null_count_renders_as_unknown_and_never_as_a_zero():
    """STATUS-06. A backend that answered nothing at all must not read as a healthy,
    empty queue — the counts section carries no standing-in zero."""
    report = _report(backend=status.render_backend_status(
        {"available": False, "reason": "endpoint did not answer", "data": None}))
    text = render_text.render_report(report)

    section = text.split("## Records waiting on a human")[1].split("## ")[0]
    assert section.count("unknown") >= 4
    assert not re.search(r": 0\b", section), section


def test_a_genuine_zero_survives_as_a_zero():
    text = render_text.render_report(_report())
    assert "Companies waiting on a review decision: 0" in text


def test_provider_balances_and_credential_health_are_reported():
    text = render_text.render_report(_report())

    assert "lusha: 412 credits remaining" in text
    assert "apollo: unknown credits remaining" in text
    assert "apollo — refused (http_403)" in text


def test_the_rendered_text_contains_no_configured_credential(fake_config):
    text = render_text.render_report(_report())
    for key in ("webhook_secret", "n8n_api_key"):
        assert fake_config[key] not in text


def test_the_answer_says_plainly_that_nothing_was_changed():
    text = render_text.render_report(_report())
    assert "read-only" in text.lower()


def test_render_report_never_raises_on_a_junk_mapping():
    for junk in (None, {}, {"workflows": "nope", "backend": 7}):
        assert isinstance(render_text.render_report(junk), str)


# --- the detail read stays gated ------------------------------------------------------


def test_attach_failures_fetches_detail_only_for_a_run_that_failed(
        fake_config, stub_get_transport_factory):
    report = _report([
        _workflow(name="healthy", last_run=_last_run(status="success", execution_id="e-1")),
        _workflow(name="broken", last_run=_last_run(status="error", execution_id="e-2")),
        _workflow(name="running", last_run=_last_run(status="running", execution_id="e-3")),
    ])
    transport = stub_get_transport_factory([
        {"id": "e-2", "data": {"resultData": {"runData": {
            "HubSpot Create": [{"error": {"message": "400 Bad Request"}}]}}}},
    ])
    render_text.attach_failures(fake_config, report, transport=transport)

    assert len(transport.calls) == 1
    assert transport.calls[0]["url"].endswith("/api/v1/executions/e-2")
    entries = {e["name"]: e for e in report["workflows"]["workflows"]}
    assert "failure" not in entries["healthy"]
    assert entries["broken"]["failure"]["findings"][0]["cause"] == "malformed_record"


def test_attach_failures_degrades_when_the_detail_read_fails(fake_config,
                                                             stub_get_transport_factory):
    report = _report([_workflow(last_run=_last_run(status="error", execution_id="e-2"))])
    render_text.attach_failures(
        fake_config, report, transport=stub_get_transport_factory([(500, {})]))

    failure = report["workflows"]["workflows"][0]["failure"]
    assert failure["available"] is False
    assert failure["findings"] == []


# --- the skill file itself ------------------------------------------------------------


def _frontmatter() -> dict:
    text = SKILL_PATH.read_text()
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    _, frontmatter, _ = text.split("---", 2)
    return yaml.safe_load(frontmatter)


def test_the_skill_parses_as_frontmatter_plus_body():
    frontmatter = _frontmatter()
    assert frontmatter["name"] == "backend-status"
    assert frontmatter["description"]


def test_the_description_fires_on_the_natural_phrasings():
    description = _frontmatter()["description"].lower()
    for phrase in ("what the backend is doing", "running", "stuck",
                   "waiting", "credit"):
        assert phrase in description, phrase


def test_the_skill_is_reachable_as_a_slash_command_with_no_commands_directory():
    assert "/operator-claude-plugin:backend-status" in SKILL_PATH.read_text()
    assert not (PLUGIN_ROOT / "commands").exists(), (
        "a plugin skill is already both auto-triggered and slash-invocable (D-14b)")


def test_every_script_path_named_in_the_skill_body_exists_on_disk():
    referenced = set(re.findall(r"scripts/(\w+\.py)", SKILL_PATH.read_text()))
    assert referenced, "expected the skill body to name at least one script"
    for script in referenced:
        assert (PLUGIN_ROOT / "scripts" / script).exists(), script


def test_the_skill_states_that_it_only_reads():
    """T-27-19: an operator who believes this surface can act is the harm to prevent."""
    body = SKILL_PATH.read_text().lower()
    assert "reads. it changes nothing" in body
    assert "writes to no hubspot record" in body


def test_the_skill_leaves_an_explicit_marker_for_the_dashboard_step():
    """27-05 should be an edit, not a rewrite."""
    assert "27-05 DASHBOARD STEP" in SKILL_PATH.read_text()
