"""The review-decision client: env kill switch, session arm, preview, read-back (30-06).

Every test drives `stub_module_transport_factory` — the module-shaped recorder 28-01
shipped for exactly this transport shape (D-21). No new fixture, no conftest edit.
"""
import pytest

import config_gate
import review_decision


CONFIG = {"n8n_url": "https://n8n.example", "webhook_secret": "placeholder-not-a-secret"}

# The multi-key patch an APPROVAL produces (D-30): class-filtered canonical fields, the
# clear patch, and the provenance blob.
APPROVE_WRITE = {
    "lv_org_type": "governing_body_league",
    "lv_enrichment_needs_review": "false",
    "lv_enrichment_review_approved": "false",
    "lv_enrichment_provenance": '{"lv_org_type":{"source":"human"}}',
}

# A REJECTION's patch is exactly one key — the reason. The record stays queued (D-10).
REJECT_WRITE = {"lv_enrichment_review_reason": "Wrong org type; they only host events."}


def applied_response(verified_properties=APPROVE_WRITE, verified=True):
    return {"outcome": "applied", "message": "Applied 1 field.",
            "would_write": APPROVE_WRITE,
            "verified_properties": verified_properties, "verified": verified}


def dry_run_response(would_write=APPROVE_WRITE):
    return {"outcome": "applied", "message": "Dry run — nothing written.",
            "would_write": would_write, "verified_properties": None, "verified": None}


@pytest.fixture(autouse=True)
def _no_ambient_env_gate(monkeypatch):
    """The kill switch starts CLOSED in every test, so a test that needs it open must say
    so — and a machine that happens to export it cannot turn these assertions green."""
    monkeypatch.delenv(review_decision.SUBMIT_ENV_VAR, raising=False)


@pytest.fixture
def armed_env(monkeypatch):
    monkeypatch.setenv(review_decision.SUBMIT_ENV_VAR, "true")


# --- the env kill switch: ALLOW_REVIEW_SUBMIT (D-16, Phase 28 D-34) -------------------

def test_submit_refuses_with_an_empty_call_log_when_the_variable_is_unset(
        stub_module_transport_factory):
    """The gate precedes transport construction, so the refusal costs zero HTTP calls —
    not one unsent request, none at all."""
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "Looks right", "Robert",
        review_armed=True, transport=transport)

    assert result["available"] is False
    assert result["reason"] == "submit_not_enabled"
    assert transport.calls == []
    assert transport.mutating_calls == []


def test_the_env_refusal_names_the_variable_and_says_an_admin_sets_it():
    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "Looks right", "Robert", review_armed=True)

    assert "ALLOW_REVIEW_SUBMIT" in result["message"]
    assert "administrator" in result["message"]
    # Never a shell command the operator is told to run.
    assert "export " not in result["message"]


@pytest.mark.parametrize("value", ["", "1", "yes", "TRUE", "True", "true ", " true"])
def test_every_near_miss_value_refuses(monkeypatch, value, stub_module_transport_factory):
    """Semantics identical to ALLOW_N8N_ARM / ALLOW_N8N_PROBE: only the exact string
    `true` proceeds. A divergence between the two gates is itself the defect (D-16)."""
    monkeypatch.setenv(review_decision.SUBMIT_ENV_VAR, value)
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    assert review_decision.submit_enabled() is False
    assert result["reason"] == "submit_not_enabled"
    assert transport.calls == []


def test_only_the_exact_string_true_proceeds(monkeypatch, stub_module_transport_factory):
    monkeypatch.setenv(review_decision.SUBMIT_ENV_VAR, "true")
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    assert review_decision.submit_enabled() is True
    assert result["available"] is True
    assert len(transport.mutating_calls) == 1


def test_an_unarmed_refusal_restates_the_previewed_write_without_calling_anything(
        armed_env, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])
    preview = {"available": True, "would_write": APPROVE_WRITE}

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=False, preview=preview, transport=transport)

    assert result["reason"] == "not_armed"
    assert result["would_write"] == APPROVE_WRITE
    assert transport.calls == []


# --- carve-out (c): the kill switch gates SUBMITTING only, never an un-doing path ------

def test_rejecting_proceeds_with_the_variable_unset(stub_module_transport_factory):
    """A rejection records a reason and leaves the record in the queue. A kill switch that
    blocked it would strand a record mid-decision — the mirror of the stranded-armed-backend
    failure ALLOW_N8N_ARM's disarm carve-out exists to avoid (D-16 (c), D-10)."""
    transport = stub_module_transport_factory([
        {"outcome": "rejected", "message": "Reason recorded; record stays queued.",
         "would_write": REJECT_WRITE, "verified_properties": REJECT_WRITE, "verified": True},
    ])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "reject", REJECT_WRITE["lv_enrichment_review_reason"],
        "Robert", review_armed=True, transport=transport)

    assert result["available"] is True
    assert result["outcome"] == "rejected"
    assert transport.calls[0]["json"]["dry_run"] is False
    assert review_decision.verify_decision(REJECT_WRITE, result)["status"] == "verified"


def test_a_rejection_still_needs_the_session_arm(stub_module_transport_factory):
    """The env carve-out is not a carve-out from the conversation's own permission: a
    rejection writes to HubSpot, so D-03 still applies to it."""
    transport = stub_module_transport_factory([{"outcome": "rejected"}])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "reject", "r", "Robert",
        review_armed=False, transport=transport)

    assert result["reason"] == "not_armed"
    assert transport.mutating_calls == []


def test_is_undoing_recognises_only_reject_and_fails_closed_on_anything_else():
    assert review_decision.is_undoing("reject") is True
    assert review_decision.is_undoing(" REJECT ") is True
    assert review_decision.is_undoing("approve") is False
    # An unrecognised word is NOT treated as un-doing — the gate fails closed.
    for word in ("dismiss", "clear", "", None, 7, "re-queue"):
        assert review_decision.is_undoing(word) is False


def test_an_unknown_decision_word_is_still_gated(stub_module_transport_factory):
    transport = stub_module_transport_factory([{"outcome": "refused"}])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "dismiss", "r", "Robert",
        review_armed=True, transport=transport)

    assert result["reason"] == "submit_not_enabled"
    assert transport.calls == []


# --- carve-out: the preview is never gated -------------------------------------------

def test_preview_is_unaffected_by_the_env_variable(stub_module_transport_factory):
    """A dry run writes nothing, and without it the operator cannot see what they are
    being asked to approve."""
    transport = stub_module_transport_factory([dry_run_response()])

    result = review_decision.preview_decision(
        CONFIG, "companies", "789", "approve", "Looks right", transport=transport)

    assert result["available"] is True
    assert result["would_write"] == APPROVE_WRITE
    assert transport.calls[0]["json"]["dry_run"] is True
    assert len(transport.calls) == 1


def test_preview_is_unaffected_by_the_session_arm(stub_module_transport_factory):
    transport = stub_module_transport_factory([dry_run_response()])

    result = review_decision.preview_decision(
        CONFIG, "companies", "789", "approve", "r", transport=transport)

    assert result["available"] is True


# --- the request the endpoint reads --------------------------------------------------

def test_the_request_carries_only_the_six_accepted_keys(armed_env,
                                                        stub_module_transport_factory):
    """No field name, no value, no patch: this client cannot tell the endpoint WHAT to
    write, only which record and which decision word (T-30-05)."""
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", 789, "approve", "Looks right", "Robert",
        review_armed=True, transport=transport)

    body = transport.calls[0]["json"]
    assert set(body) == {"object_type", "record_id", "decision", "reason", "reviewed_by",
                         "dry_run"}
    assert body["record_id"] == "789"
    assert body["reviewed_by"] == "Robert"


def test_an_armed_submit_sends_the_dry_run_flag_false_exactly_once(
        armed_env, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    assert transport.verbs == ["post"]
    assert [call["json"]["dry_run"] for call in transport.calls] == [False]


def test_the_secret_travels_in_the_header_and_the_url_never_carries_it(
        armed_env, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    call = transport.calls[0]
    assert call["headers"] == {"X-Enrichment-Secret": CONFIG["webhook_secret"]}
    assert CONFIG["webhook_secret"] not in call["url"]
    assert call["url"] == "https://n8n.example/webhook/hubspot/review/decision"


def test_a_missing_reviewer_label_becomes_a_neutral_placeholder_not_an_empty_string(
        armed_env, stub_module_transport_factory):
    """The backend writes lv_enrichment_reviewed_by only when the label is non-empty, so
    an empty string would leave the audit trail naming nobody."""
    transport = stub_module_transport_factory([applied_response(), applied_response()])

    for label in (None, "   "):
        review_decision.submit_decision(
            CONFIG, "companies", "789", "approve", "r", label,
            review_armed=True, transport=transport)

    assert [c["json"]["reviewed_by"] for c in transport.calls] == \
        [review_decision.DEFAULT_REVIEWED_BY] * 2
    assert review_decision.DEFAULT_REVIEWED_BY.strip() != ""


def test_a_decision_without_a_reason_is_still_a_decision(armed_env,
                                                         stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", None, "Robert",
        review_armed=True, transport=transport)

    assert transport.calls[0]["json"]["reason"] == ""


# --- configuration: require_capability RAISES, runtime degrades (D-35) ----------------

def test_a_misconfiguration_raises_before_any_transport_is_constructed(
        armed_env, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    with pytest.raises(config_gate.ConfigError) as excinfo:
        review_decision.submit_decision(
            {"n8n_url": "https://n8n.example"}, "companies", "789", "approve", "r",
            "Robert", review_armed=True, transport=transport)

    assert "webhook_secret" in str(excinfo.value)
    assert CONFIG["webhook_secret"] not in str(excinfo.value)
    assert transport.calls == []


@pytest.mark.parametrize("scripted,reason", [
    (RuntimeError("connection reset"), "endpoint_unreachable"),
    ((401, {"error": "unauthorized"}), "http_401"),
    ((200, ValueError("no body")), "unparseable_response"),
    ((200, [{"outcome": "applied"}]), "unrecognized_response_shape"),
])
def test_every_runtime_failure_degrades_to_a_named_reason(
        armed_env, stub_module_transport_factory, scripted, reason):
    """None of these raises, and none of them is distinguishable from a rejected write by
    a caller that reads the status alone (D-23, D-35)."""
    transport = stub_module_transport_factory([scripted])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    assert result == {"available": False, "reason": reason, "outcome": None,
                      "message": None, "would_write": None,
                      "verified_properties": None, "verified": None}


def test_an_empty_body_is_reported_as_failed_never_as_a_completed_write(
        armed_env, stub_module_transport_factory):
    """An armed-but-not-allowlisted decision returns NO body at all — the write gate drops
    the row and nothing reaches the responder (D-23)."""
    transport = stub_module_transport_factory([(200, ValueError("Expecting value"))])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    assert review_decision.verify_decision(APPROVE_WRITE, result)["status"] == "failed"


def test_a_dict_response_is_parsed_directly_never_as_body_zero(
        armed_env, stub_module_transport_factory):
    """`respondWith: firstIncomingItem` — ONE dict, not an array (D-24)."""
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, transport=transport)

    assert result["outcome"] == "applied"
    assert result["would_write"] == APPROVE_WRITE


# --- read-back verification (D-19, Phase 28 D-14) ------------------------------------

def test_matching_refetched_properties_report_verified():
    result = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "applied", "message": "ok",
        "would_write": APPROVE_WRITE, "verified_properties": dict(APPROVE_WRITE),
        "verified": True})

    assert result["status"] == "verified"
    assert result["mismatched"] == []


def test_a_2xx_whose_refetched_properties_disagree_reports_failed_and_names_the_key():
    """The verdict comes from the comparison, never from a status code."""
    drifted = dict(APPROVE_WRITE, lv_org_type="broadcaster")

    result = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "applied", "message": "Applied 1 field.",
        "would_write": APPROVE_WRITE, "verified_properties": drifted, "verified": True})

    assert result["status"] == "failed"
    assert result["mismatched"] == ["lv_org_type"]
    assert "lv_org_type" in result["message"]


def test_an_approved_key_missing_from_the_refetch_reports_failed_and_names_it():
    partial = {k: v for k, v in APPROVE_WRITE.items() if k != "lv_enrichment_provenance"}

    result = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "applied", "message": "ok",
        "would_write": APPROVE_WRITE, "verified_properties": partial, "verified": True})

    assert result["status"] == "failed"
    assert result["mismatched"] == ["lv_enrichment_provenance"]


@pytest.mark.parametrize("verified_properties", [None, "", [], 0])
def test_a_written_decision_without_a_usable_refetch_reports_failed(verified_properties):
    """An unverifiable write is not a verified one — and the response's own `verified: true`
    is never the authority (D-19)."""
    result = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "applied", "message": "ok",
        "would_write": APPROVE_WRITE, "verified_properties": verified_properties,
        "verified": True})

    assert result["status"] == "failed"
    assert "read back" in result["message"]


def test_the_response_self_reported_verified_flag_is_never_trusted():
    """`verified: false` on a genuinely matching refetch still reads as verified, and
    `verified: true` on a mismatching one does not — the client re-derives it."""
    matching = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "applied", "would_write": APPROVE_WRITE,
        "verified_properties": dict(APPROVE_WRITE), "verified": False})
    mismatching = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "applied", "would_write": APPROVE_WRITE,
        "verified_properties": dict(APPROVE_WRITE, lv_org_type="other"), "verified": True})

    assert matching["status"] == "verified"
    assert mismatching["status"] == "failed"


def test_values_are_compared_stringwise_because_hubspot_stores_every_property_as_a_string():
    result = review_decision.verify_decision(
        {"lv_enrichment_needs_review": False, "lv_icp_fit_score": 55},
        {"available": True, "outcome": "applied",
         "would_write": {"lv_enrichment_needs_review": False, "lv_icp_fit_score": 55},
         "verified_properties": {"lv_enrichment_needs_review": False,
                                 "lv_icp_fit_score": 55},
         "verified": True})

    assert result["status"] == "verified"


@pytest.mark.parametrize("outcome", review_decision.NON_WRITING_OUTCOMES)
def test_every_non_writing_outcome_is_surfaced_verbatim_not_translated_into_success(outcome):
    """stale / no_candidate / not_flagged / refused each wrote nothing, and the operator is
    told so in the endpoint's own words (D-30)."""
    result = review_decision.verify_decision({}, {
        "available": True, "outcome": outcome, "message": f"backend says: {outcome}",
        "would_write": {}, "verified_properties": None, "verified": None})

    assert result["status"] == "not_written"
    assert result["outcome"] == outcome
    assert result["message"] == f"backend says: {outcome}"


def test_every_endpoint_outcome_has_a_handling_branch():
    """All six of D-30's outcomes, and nothing resolves to an unhandled state."""
    assert set(review_decision.OUTCOMES) == {
        "applied", "rejected", "stale", "no_candidate", "not_flagged", "refused"}
    assert "unsupported" not in review_decision.OUTCOMES

    for outcome in review_decision.OUTCOMES:
        response = {"available": True, "outcome": outcome, "message": "m",
                    "would_write": APPROVE_WRITE,
                    "verified_properties": dict(APPROVE_WRITE), "verified": True}
        assert review_decision.verify_decision(APPROVE_WRITE, response)["status"] in (
            "verified", "failed", "not_written")


def test_an_outcome_this_client_does_not_recognise_reports_failed():
    result = review_decision.verify_decision(APPROVE_WRITE, {
        "available": True, "outcome": "unsupported", "message": "m",
        "would_write": APPROVE_WRITE, "verified_properties": dict(APPROVE_WRITE),
        "verified": True})

    assert result["status"] == "failed"


def test_an_unavailable_response_reports_failed_and_never_verified():
    result = review_decision.verify_decision(
        APPROVE_WRITE,
        {"available": False, "reason": "endpoint_unreachable", "outcome": None,
         "message": None, "would_write": None, "verified_properties": None,
         "verified": None})

    assert result["status"] == "failed"
    assert "endpoint_unreachable" in result["message"]


def test_a_writing_outcome_with_nothing_approved_reports_failed():
    result = review_decision.verify_decision({}, {
        "available": True, "outcome": "applied", "message": "m", "would_write": {},
        "verified_properties": {}, "verified": True})

    assert result["status"] == "failed"


# --- nothing persists ----------------------------------------------------------------

def test_no_module_level_state_persists_an_arm_between_two_calls(
        armed_env, stub_module_transport_factory):
    """Arming once does not leave anything behind that a second, unarmed call can read."""
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(CONFIG, "companies", "789", "approve", "r", "Robert",
                                    review_armed=True, transport=transport)
    second = review_decision.submit_decision(CONFIG, "companies", "789", "approve", "r",
                                             "Robert", review_armed=False,
                                             transport=transport)

    assert second["reason"] == "not_armed"
    assert len(transport.mutating_calls) == 1


def test_review_armed_is_a_parameter_and_never_a_module_level_or_file_backed_value():
    import ast
    import pathlib

    source = pathlib.Path(review_decision.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    module_level_names = [
        target.id
        for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    ]
    assert "review_armed" not in module_level_names
    assert not hasattr(review_decision, "review_armed")

    # No arm may reach disk in either direction. (`json.dump(` is the file-writing form;
    # `json.dumps` printing to stdout is not a persistence path.)
    for forbidden in ("open(", "Path(", "json.dump(", "write_text", "read_text"):
        assert forbidden not in source
