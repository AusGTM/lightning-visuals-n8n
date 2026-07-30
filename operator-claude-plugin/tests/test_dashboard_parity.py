"""The dashboard carries the same data as the text answer (27-05 Task 2, D-09/STATUS-05).

Driven from `test_status_skill.py`'s own fixture mapping rather than a second one of its
own: the two renderers are compared *against one another*, so neither can drift into
being right about its own expectations while disagreeing with the other. A fixture
copied here would go stale the first time 27-04's changed.

The stamp is the other half. It comes from the status mapping, not from the moment of
rendering — a dashboard republished from a cached mapping must say when the data was
gathered, or it is a stale reading wearing a fresh timestamp (T-27-23).
"""
import json
import re

import pytest

import render_dashboard
import render_text
import status
import test_status_skill as fixtures

PAYLOAD_KEYS = ("fetched_at", "workflows", "counts", "providers")


def _both(report):
    """The same mapping through both renderers."""
    return render_dashboard.dashboard_payload(report), render_text.render_report(report)


# --- the stamp -------------------------------------------------------------------------


def test_the_stamp_comes_from_the_mapping_not_from_render_time():
    report = fixtures._report(backend=fixtures._backend())
    report["backend"]["checked_at"] = "2026-01-01T00:00:00.000Z"

    first = render_dashboard.dashboard_payload(report)
    second = render_dashboard.dashboard_payload(report)

    assert first["fetched_at"] == "2026-01-01T00:00:00.000Z"
    assert first["fetched_at"] == second["fetched_at"], (
        "two renders of one mapping must carry one stamp — the stamp is when the data "
        "was fetched, not when the page was drawn")


def test_a_missing_stamp_reads_unknown_rather_than_now():
    report = fixtures._report(backend=fixtures._backend())
    report["backend"]["checked_at"] = status.UNKNOWN

    assert render_dashboard.dashboard_payload(report)["fetched_at"] == status.UNKNOWN


def test_the_rendered_dashboard_shows_the_stamp():
    report = fixtures._report()
    html = render_dashboard.render_dashboard(report)
    assert report["backend"]["checked_at"] in html


# --- parity: every workflow, every count -----------------------------------------------


def test_every_workflow_in_the_text_answer_is_in_the_dashboard():
    report = fixtures._report([
        fixtures._workflow(name="LV Contact Ingest (Cloud template)"),
        fixtures._workflow(workflow_id="wf-2", name="LV Enrichment (Cloud)"),
        fixtures._workflow(workflow_id="wf-3", name="LV Scheduled Maintenance (Cloud)"),
    ])
    payload, text = _both(report)

    names = [entry["name"] for entry in payload["workflows"]]
    assert len(names) == 3
    for name in names:
        assert name in text, name


def test_every_count_appears_in_both_renderings_with_the_same_value():
    report = fixtures._report()
    payload, text = _both(report)
    source = report["backend"]["counts"]

    by_label = {row["label"]: row["value"] for row in payload["counts"]}
    assert len(by_label) == len(render_text.COUNT_LABELS)

    for key, label in render_text.COUNT_LABELS:
        assert by_label[label] == source[key], label
        assert f"{label}: {source[key]}" in text, label


def test_each_workflows_on_off_and_last_run_match_the_text_answer():
    report = fixtures._report([
        fixtures._workflow(active=True),
        fixtures._workflow(workflow_id="wf-2", name="off one", active=False),
    ])
    payload, text = _both(report)

    for entry in payload["workflows"]:
        assert f"Switched {entry['active']}" in text
        assert entry["last_run"] in text
        assert entry["right_now"] in text


def test_provider_balances_appear_in_both_renderings_with_the_same_value():
    report = fixtures._report()
    payload, text = _both(report)

    for row in payload["providers"]:
        assert f"{row['provider']}: {row['credits']} credits remaining" in text


# --- unknown is not blank and not zero --------------------------------------------------


def test_an_unknown_count_is_unknown_in_the_dashboard_and_never_blank_or_zero():
    """STATUS-06 / D-08 on the dashboard surface: a blank cell reads as healthy."""
    report = fixtures._report(backend=status.render_backend_status(
        {"available": False, "reason": "endpoint did not answer", "data": None}))
    payload = render_dashboard.dashboard_payload(report)

    for row in payload["counts"]:
        assert row["value"] == status.UNKNOWN, row
        assert row["value"] != "" and row["value"] != "0"

    html = render_dashboard.render_dashboard(report)
    counts_block = html.split("Records waiting on a human")[1]
    assert not re.search(r">\s*0\s*<", counts_block), counts_block
    assert not re.search(r"<td>\s*</td>", counts_block), "no blank cell may stand in"


def test_an_unknown_provider_balance_is_unknown_not_a_zero_balance():
    report = fixtures._report()
    payload = render_dashboard.dashboard_payload(report)

    apollo = next(row for row in payload["providers"] if row["provider"] == "apollo")
    assert apollo["credits"] == status.UNKNOWN


def test_an_unreadable_workflow_reads_unknown_in_every_field():
    report = fixtures._report([fixtures._workflow(
        name=None, active=None,
        write_safety={"ALLOW_HUBSPOT_CREATE": {"value": None, "nodes": [],
                                               "disagreement": None}},
        last_run=fixtures._last_run(status=None, in_flight=None,
                                    error="could_not_read_executions"))])
    payload, text = _both(report)
    entry = payload["workflows"][0]

    assert entry["name"] == status.UNKNOWN
    assert entry["active"] == status.UNKNOWN
    assert status.UNKNOWN in entry["last_run"]
    assert status.UNKNOWN in " ".join(entry["live_writes"])
    assert "Switched unknown" in text


def test_a_genuine_zero_survives_as_a_zero_in_the_dashboard():
    payload = render_dashboard.dashboard_payload(fixtures._report())
    by_label = {row["label"]: row["value"] for row in payload["counts"]}
    assert by_label["Companies waiting on a review decision"] == "0"


# --- failures ---------------------------------------------------------------------------


def test_a_failed_runs_sentence_and_attribution_are_in_the_dashboard():
    report = fixtures._report([fixtures._workflow(
        last_run=fixtures._last_run(status="error"),
        failure={"available": True, "reason": None,
                 "findings": [fixtures._finding()]})])
    payload, text = _both(report)

    failure = payload["workflows"][0]["failures"][0]
    assert failure["sentence"] == fixtures._finding()["sentence"]
    assert failure["who_can_act"] == "admin"
    assert failure["sentence"] in text
    assert failure["sentence"] in render_dashboard.render_dashboard(report)


def test_an_unrecognised_failure_keeps_its_interpretation_label_and_its_raw_text_apart():
    report = fixtures._report([fixtures._workflow(
        last_run=fixtures._last_run(status="error"),
        failure={"available": True, "reason": None, "findings": [fixtures._finding(
            matched=False, cause=None, is_interpretation=True,
            sentence="This failure signature is not one the plugin recognises.",
            raw="flurble exploded sideways")]})])
    payload = render_dashboard.dashboard_payload(report)

    failure = payload["workflows"][0]["failures"][0]
    assert failure["is_interpretation"] is True
    assert failure["raw"] == "flurble exploded sideways"
    assert failure["raw"] != failure["sentence"]

    html = render_dashboard.render_dashboard(report)
    assert "interpretation" in html.lower()


def test_an_unreadable_failure_detail_reads_unknown_in_the_dashboard():
    report = fixtures._report([fixtures._workflow(
        last_run=fixtures._last_run(status="error"),
        failure={"available": False, "reason": "that execution's detail could not be read",
                 "findings": []})])
    payload = render_dashboard.dashboard_payload(report)

    assert payload["workflows"][0]["failures"] == []
    assert status.UNKNOWN in payload["workflows"][0]["failure_note"]


# --- what the payload must NOT carry -----------------------------------------------------


def test_the_payload_carries_no_configured_credential(fake_config):
    report = fixtures._report()
    rendered = json.dumps(render_dashboard.dashboard_payload(report))
    html = render_dashboard.render_dashboard(report)

    for key in ("webhook_secret", "n8n_api_key"):
        assert fake_config[key] not in rendered
        assert fake_config[key] not in html


def test_values_are_escaped_into_the_html_rather_than_interpolated_raw():
    """Workflow names and raw error text come from n8n. Neither is trusted markup."""
    report = fixtures._report([fixtures._workflow(
        name="<script>alert('x')</script>",
        last_run=fixtures._last_run(status="error"),
        failure={"available": True, "reason": None, "findings": [fixtures._finding(
            is_interpretation=True, raw="<img src=x onerror=alert(1)>")]})])
    html = render_dashboard.render_dashboard(report)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "onerror=alert(1)>" not in html


def test_rendering_is_pure_no_network_and_no_file_read():
    """The store is the skill's to call, not the renderer's — a renderer that reads state
    is a renderer that can publish a stale pointer's data by accident."""
    source = (render_dashboard.__file__ and
              open(render_dashboard.__file__, encoding="utf-8").read())
    for forbidden in ("requests", "artifact_store", "urllib", "socket",
                      "open(", "read_text", "Path("):
        assert forbidden not in source, forbidden


# --- degenerate input --------------------------------------------------------------------


def test_an_empty_mapping_produces_a_payload_that_says_so():
    payload = render_dashboard.dashboard_payload({})

    assert all(key in payload for key in PAYLOAD_KEYS)
    assert payload["notices"], "an empty mapping must say so rather than render blank"
    assert payload["fetched_at"] == status.UNKNOWN

    html = render_dashboard.render_dashboard({})
    assert status.UNKNOWN in html


def test_an_unreadable_workflow_collection_says_unknown_not_no_workflows():
    report = fixtures._report()
    report["workflows"] = {"readable": False, "workflows": []}
    payload = render_dashboard.dashboard_payload(report)

    assert payload["workflows"] == []
    assert any(status.UNKNOWN in notice for notice in payload["notices"])
    assert not any("no workflows at all" in notice for notice in payload["notices"])


def test_a_genuinely_empty_collection_says_there_are_none():
    report = fixtures._report()
    report["workflows"] = {"readable": True, "workflows": []}
    payload = render_dashboard.dashboard_payload(report)

    assert any("no workflows" in notice.lower() for notice in payload["notices"])


@pytest.mark.parametrize("junk", [None, {}, {"workflows": "nope", "backend": 7},
                                  {"workflows": {"readable": True, "workflows": ["x"]}}])
def test_neither_renderer_raises_on_a_junk_mapping(junk):
    assert isinstance(render_dashboard.dashboard_payload(junk), dict)
    assert isinstance(render_dashboard.render_dashboard(junk), str)
    assert isinstance(render_text.render_report(junk), str)


def test_the_dashboard_says_it_only_read():
    html = render_dashboard.render_dashboard(fixtures._report())
    assert "read-only" in html.lower()
