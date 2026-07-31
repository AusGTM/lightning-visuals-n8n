"""Review-queue fetch, display-only policy lookup, record link and rendering (30-05).

The queue payload lives here as a local fixture rather than in conftest.py: 30-06 renders
against the decision endpoint's response, not this one, so a shared fixture would be a
seam nobody else uses.
"""
import json

import pytest

import config_gate
import review_queue


COMPANY_DECISIONS = [
    {
        "field": "lv_org_type",
        "current_value": "",
        "chosen_value": "governing_body_league",
        "source_provider": "claude_web",
        "decision": "needs_review",
        "confidence": 78,
        "reason": "Best confidence 78 below threshold 80.",
        "validation_status": "llm_classified",
        "evidence_url": "https://exampleracing.example/about",
        "verified_at": "2026-07-30T02:00:00Z",
    },
    {
        # `domain` is manual_protected in config/field_policy.yaml — the field D-31 shows
        # the 15-minute backstop would still write, which is why the label is scoped.
        "field": "domain",
        "current_value": "exampleracing.example",
        "chosen_value": "example-racing.com",
        "source_provider": "zoominfo",
        "decision": "needs_review",
        "confidence": 83,
        "reason": "Field is manual_protected.",
        "validation_status": "provider_only",
        "evidence_url": None,
        "verified_at": "2026-07-30T02:00:00Z",
    },
]


def company_row():
    return {
        "hs_object_id": "789",
        "name": "Example Racing League",
        "domain": "exampleracing.example",
        "lv_enrichment_needs_review": "true",
        "lv_icp_needs_review": "false",
        "lv_enrichment_review_reason": "lv_org_type: below threshold; domain: protected",
        "lv_enrichment_review_candidate_json": json.dumps(COMPANY_DECISIONS),
        "lv_enrichment_review_approved": "",
        "lv_enrichment_reviewed_by": "",
        "lv_enrichment_reviewed_at": "",
        "lv_enrichment_provenance": '{"lv_org_type": {"source": "claude_web"}}',
        "lv_icp_tier": "B",
        "lv_icp_fit_score": "55",
        "lv_icp_score_breakdown": "{}",
        "lv_anti_icp_reason": "",
    }


def contact_row():
    """A dedupe-flagged contact: the candidate key IS present and IS empty (D-34)."""
    return {
        "hs_object_id": "4242",
        "email": "amy@example.com",
        "firstname": "Amy",
        "lastname": "Adams",
        "jobtitle": "Head of Broadcast",
        "lv_enrichment_needs_review": "true",
        "lv_icp_needs_review": "false",
        "lv_enrichment_review_reason": "Possible duplicate of contact 4199",
        "lv_enrichment_review_candidate_json": "",
        "lv_contact_enrichment_provenance": "",
    }


def queue_envelope(rows=None, total=None, object_type="companies", search_ok=True):
    rows = [company_row()] if rows is None else rows
    return {
        "object_type": object_type,
        "search_ok": search_ok,
        "total": len(rows) if total is None else total,
        "returned": len(rows),
        "rows": rows,
    }


def policy_lookup(object_type="companies"):
    return lambda field: review_queue.policy_class(object_type, field)


def link_lookup(portal_id, object_type="companies"):
    return lambda row: review_queue.record_link(object_type, row.get("hs_object_id"),
                                                portal_id)


# --- fetch -----------------------------------------------------------------------------

def test_fetch_posts_to_the_queue_path_with_the_auth_header(fake_config,
                                                            stub_module_transport_factory):
    transport = stub_module_transport_factory([queue_envelope()])
    result = review_queue.fetch_queue(fake_config, "companies", transport=transport)

    assert transport.verbs == ["post"]
    call = transport.calls[0]
    assert call["url"] == "https://fake-tenant.n8n.cloud/webhook/hubspot/review/queue"
    assert call["headers"]["X-Enrichment-Secret"] == fake_config["webhook_secret"]
    assert call["json"] == {"object_type": "companies"}
    assert result["available"] is True
    assert result["returned"] == 1


def test_fetch_never_returns_or_renders_the_secret(fake_config,
                                                   stub_module_transport_factory):
    transport = stub_module_transport_factory([queue_envelope()])
    result = review_queue.fetch_queue(fake_config, "companies", transport=transport)
    rendered = review_queue.render_queue(result["rows"], result["total"],
                                         policy_lookup(), link_lookup("55550000"))
    assert fake_config["webhook_secret"] not in json.dumps(result)
    assert fake_config["webhook_secret"] not in rendered


def test_fetch_sends_the_limit_only_when_one_is_asked_for(fake_config,
                                                          stub_module_transport_factory):
    transport = stub_module_transport_factory([queue_envelope(), queue_envelope()])
    review_queue.fetch_queue(fake_config, "contacts", limit=5, transport=transport)
    review_queue.fetch_queue(fake_config, "contacts", transport=transport)
    assert transport.calls[0]["json"] == {"object_type": "contacts", "limit": 5}
    assert "limit" not in transport.calls[1]["json"]


def test_a_failed_search_is_a_failure_not_an_empty_queue(fake_config,
                                                         stub_module_transport_factory):
    """D-33: search nodes run onError:continueRegularOutput, so a 401 arrives as a 200
    with search_ok false. Rendering that as `0 flagged` tells the operator their backlog is
    clear when it was never read."""
    transport = stub_module_transport_factory(
        [queue_envelope(rows=[], total=0, search_ok=False)])
    result = review_queue.fetch_queue(fake_config, "companies", transport=transport)
    assert result["available"] is False
    assert result["reason"] == "hubspot_search_did_not_run"


def test_a_genuinely_empty_queue_is_available(fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([queue_envelope(rows=[], total=0)])
    result = review_queue.fetch_queue(fake_config, "companies", transport=transport)
    assert result == {"available": True, "reason": None, "object_type": "companies",
                      "total": 0, "returned": 0, "rows": []}


@pytest.mark.parametrize("scripted,reason", [
    ((401, {}), "http_401"),
    (RuntimeError("connection refused to https://x with header Secret: abc"),
     "endpoint_unreachable"),
    ((200, ValueError("not json")), "unparseable_response"),
    ([{"hs_object_id": "1"}], "unrecognized_response_shape"),
])
def test_every_failure_mode_degrades_with_a_reason(fake_config,
                                                   stub_module_transport_factory,
                                                   scripted, reason):
    transport = stub_module_transport_factory([scripted])
    result = review_queue.fetch_queue(fake_config, "companies", transport=transport)
    assert result["available"] is False and result["reason"] == reason
    assert result["rows"] == []


def test_the_queue_refuses_before_any_transport_call_when_the_secret_is_missing(
        fake_config, stub_module_transport_factory):
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    transport = stub_module_transport_factory([queue_envelope()])
    with pytest.raises(config_gate.ConfigError) as exc:
        review_queue.fetch_queue(cfg, "companies", transport=transport)
    assert "webhook_secret" in str(exc.value)
    assert transport.calls == []


def test_review_is_its_own_capability_row_not_a_fallback(fake_config):
    """A row was ADDED; an unknown name must still raise ValueError, or the gate would be
    silently answering for capabilities nobody declared (D-18)."""
    config_gate.require_capability(fake_config, "review")
    assert config_gate.CAPABILITY_KEYS["review"] == ("n8n_url", "webhook_secret")
    with pytest.raises(ValueError):
        config_gate.require_capability(fake_config, "review-queue")


# --- display-only policy lookup ---------------------------------------------------------

def test_policy_class_reports_the_protected_class_and_none_for_an_unknown_field():
    assert review_queue.policy_class("companies", "domain") == "manual_protected"
    assert review_queue.policy_class("companies", "annualrevenue") == "review_required"
    assert review_queue.policy_class("companies", "lv_org_type") == "system_owned"
    assert review_queue.policy_class("companies", "not_a_field_at_all") is None
    assert review_queue.policy_class("widgets", "domain") is None


def test_a_missing_policy_file_costs_the_label_and_nothing_else(tmp_path):
    absent = tmp_path / "no-such-policy.yaml"
    assert review_queue.policy_class("companies", "domain", policy_path=absent) is None
    rendered = review_queue.render_queue(
        [company_row()], 1,
        lambda field: review_queue.policy_class("companies", field, policy_path=absent),
        link_lookup(None))
    # The record still renders in full — the client never refuses locally (D-07).
    assert "domain" in rendered and "PROTECTED" not in rendered


# --- record link ------------------------------------------------------------------------

def test_record_link_builds_a_hubspot_url_per_object_type():
    assert review_queue.record_link("companies", "789", "55550000") == (
        "https://app.hubspot.com/contacts/55550000/record/0-2/789")
    assert review_queue.record_link("contacts", "4242", "55550000") == (
        "https://app.hubspot.com/contacts/55550000/record/0-1/4242")


@pytest.mark.parametrize("object_type,record_id,portal_id", [
    ("companies", "789", None),
    ("companies", "789", ""),
    ("companies", None, "55550000"),
    ("deals", "789", "55550000"),
])
def test_record_link_is_none_never_a_partial_url(object_type, record_id, portal_id):
    assert review_queue.record_link(object_type, record_id, portal_id) is None


# --- rendering --------------------------------------------------------------------------

def test_a_protected_field_is_marked_and_a_system_owned_one_is_not():
    rendered = review_queue.render_queue([company_row()], 1, policy_lookup(),
                                         link_lookup("55550000"))
    protected_line = next(line for line in rendered.splitlines()
                          if line.startswith("- **domain**"))
    org_type_line = next(line for line in rendered.splitlines()
                         if line.startswith("- **lv_org_type**"))
    assert "PROTECTED (manual_protected)" in protected_line
    assert "PROTECTED" not in org_type_line


def test_the_protection_claim_is_scoped_to_the_decision_endpoint():
    """D-31 is OPEN: the 15-minute backstop allowlists by key and would still write
    `domain`. An unscoped claim here would be false."""
    rendered = review_queue.render_queue([company_row()], 1, policy_lookup(),
                                         link_lookup("55550000"))
    assert "review-decision endpoint" in rendered
    assert "15-minute sweep which does not apply this check" in rendered


def test_the_rendering_discloses_that_it_shows_the_resolved_source():
    rendered = review_queue.render_queue([company_row()], 1, policy_lookup(),
                                         link_lookup("55550000"))
    assert "never stored" in rendered
    assert "not evidence that the providers agreed" in rendered


def test_a_record_renders_current_proposed_source_confidence_reason_and_evidence():
    rendered = review_queue.render_queue([company_row()], 1, policy_lookup(),
                                         link_lookup("55550000"))
    assert "HubSpot holds now: (blank)" in rendered          # present but empty
    assert "The pipeline wants to set: governing_body_league" in rendered
    assert "Proposed by: claude_web, confidence 78" in rendered
    assert "Held back because: Best confidence 78 below threshold 80." in rendered
    assert "Evidence: https://exampleracing.example/about" in rendered
    assert "https://app.hubspot.com/contacts/55550000/record/0-2/789" in rendered
    assert "ICP tier B (score 55)" in rendered


def test_a_record_without_a_portal_id_shows_the_raw_id_and_names_what_is_missing():
    rendered = review_queue.render_queue([company_row()], 1, policy_lookup(),
                                         link_lookup(None))
    assert "HubSpot record id 789" in rendered
    assert "hubspot_portal_id" in rendered
    assert "app.hubspot.com" not in rendered


def test_a_candidate_less_contact_renders_a_reason_only_block():
    """Empty string, not a missing key (D-34)."""
    row = contact_row()
    assert row["lv_enrichment_review_candidate_json"] == ""
    rendered = review_queue.render_queue([row], 1, policy_lookup("contacts"),
                                         link_lookup("55550000", "contacts"))
    assert "amy@example.com" in rendered
    assert "Possible duplicate of contact 4199" in rendered
    assert "no stored candidate to approve, only a reason to record" in rendered


def test_an_unparseable_candidate_renders_as_nothing_to_approve():
    row = company_row()
    row["lv_enrichment_review_candidate_json"] = "{not json"
    rendered = review_queue.render_queue([row], 1, policy_lookup(), link_lookup(None))
    assert "no stored candidate to approve" in rendered


def test_an_empty_queue_renders_as_nothing_to_review_not_an_empty_string():
    rendered = review_queue.render_queue([], 0, policy_lookup(), link_lookup(None))
    assert rendered.strip()
    assert "the queue is empty" in rendered


def test_a_truncated_page_says_so_and_a_full_one_does_not():
    truncated = review_queue.render_queue([company_row()], 12, policy_lookup(),
                                          link_lookup(None))
    assert "12 records are flagged; the 1 below are this page" in truncated

    full = review_queue.render_queue([company_row()], 1, policy_lookup(), link_lookup(None))
    assert "1 flagged, all shown below" in full
    assert "this page" not in full


def test_render_queue_performs_no_io(monkeypatch):
    """Injected lookups only — a render that reached the network or the disk would make the
    autouse guard the only thing standing between a display path and a request."""
    def _blocked(*args, **kwargs):
        raise AssertionError("render_queue performed I/O")

    monkeypatch.setattr(review_queue, "_load_policy", _blocked)
    rendered = review_queue.render_queue([company_row()], 1, lambda field: None,
                                         lambda row: None)
    assert "Example Racing League" in rendered
