"""The review-decision client: grant-authorization gate, session arm, preview, read-back
(30-06; D-60-04/D-60-07 for the grant-authorization gate).

Every test drives `stub_module_transport_factory` — the module-shaped recorder 28-01
shipped for exactly this transport shape (D-21). No new fixture, no conftest edit.

D-60-04 AMENDMENT (operator, 2026-09-01): this file used to pin an environment kill switch
(`ALLOW_REVIEW_SUBMIT`), armed or left unset per test via two monkeypatch fixtures
(`_no_ambient_env_gate`, `armed_env`). Phase 60 retires that variable entirely; gate 1 is
now grant-authorization (`write_grant.authorize_send`). Every test below that used to arm
the env var now opens a grant via `_open_review_grant()` instead — see that helper's own
docstring for why every test here uses a literal grant shape rather than the full
plan_grant/open_grant round trip. D-60-07's un-doing carve-out (`is_undoing`) is UNCHANGED
and still bypasses gate 1 for a reject.
"""
import pytest

import config_gate
import review_decision
import write_grant


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


def _open_review_grant(record_ids=("789",), workflow_id="wf-review-1", lanes=("review",)):
    """The minimal literal shape `write_grant.covers` (via `authorize_send`) accepts —
    `kind`, `state`, `lanes`, `workflow_ids`, `record_ids`, `record_domains`.

    Built LITERALLY rather than through `write_grant.plan_grant`/`open_grant`: this file's
    job is `review_decision.py`'s own client-side gates, and the grant-PLANNING machinery
    (the settings-key check, lane resolution by name, guardrail A's live read, the several
    transport calls all of that costs) is already exhaustively exercised in
    test_write_grant.py — including the review lane specifically, by Phase 60's tracer.
    Reproducing that transport-stubbing setup here would duplicate coverage for no
    additional guarantee, so every test in this file uses this literal shape. (There is one
    guarantee this DOES skip: that `plan_grant` itself resolves and shapes a grant
    correctly. That guarantee lives in test_write_grant.py, not here.)
    """
    return {
        "kind": write_grant.KIND,
        "state": write_grant.OPEN,
        "lanes": list(lanes),
        "workflow_ids": {lane: workflow_id for lane in lanes},
        "record_ids": list(record_ids),
        "record_domains": [],
        "closed_reason": None,
    }


def _closed_review_grant(record_ids=("789",)):
    grant = _open_review_grant(record_ids=record_ids)
    grant["state"] = write_grant.CLOSED
    grant["closed_reason"] = write_grant.CLOSED_REVOKED
    return grant


@pytest.fixture
def open_review_grant():
    """A grant open over record "789", the id every fixture in this file that needs one
    decides against by default."""
    return _open_review_grant()


# --- gate 1: grant-authorization (D-60-04), replacing ALLOW_REVIEW_SUBMIT -------------

def test_submit_refuses_with_an_empty_call_log_when_there_is_no_grant(
        stub_module_transport_factory):
    """The gate precedes transport construction, so the refusal costs zero HTTP calls —
    not one unsent request, none at all. `grant=None` is the direct successor of "the env
    variable is unset": the same empty-call-log property, now delivered by a missing grant
    rather than a missing shell variable."""
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "Looks right", "Robert",
        review_armed=True, grant=None, transport=transport)

    assert result["available"] is False
    assert result["reason"] == review_decision.GRANT_REFUSAL_REASON
    assert transport.calls == []
    assert transport.mutating_calls == []


def test_the_grant_refusal_names_opening_one_and_never_a_shell_command():
    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "Looks right", "Robert",
        review_armed=True, grant=None)

    assert "write grant" in result["message"]
    # Never a shell command the operator is told to run — the whole point of D-60-04.
    assert "export " not in result["message"]
    assert "ALLOW_REVIEW_SUBMIT" not in result["message"]


@pytest.mark.parametrize("label,grant", [
    ("no_grant", None),
    ("closed_grant", _closed_review_grant()),
    ("wrong_lane", _open_review_grant(lanes=("enrichment",))),
    ("not_a_grant_shape", {"lanes": ["review"], "state": "open"}),   # no "kind"
])
def test_every_grant_state_near_miss_refuses_with_an_empty_call_log(
        label, grant, stub_module_transport_factory):
    """The grant-state near-miss set that replaces the retired env-value near-miss set
    (`""`, `"1"`, `"yes"`, `"TRUE"`, `"True"`): no grant, a CLOSED grant, a grant whose
    `lanes` omits `"review"`, and a dict that is not a grant at all — each refuses with
    `GRANT_REFUSAL_REASON` and an empty transport call log, exactly as every env near-miss
    used to."""
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=grant, transport=transport)

    assert result["reason"] == review_decision.GRANT_REFUSAL_REASON, label
    assert transport.calls == [], label


def test_an_open_grant_covering_the_record_lets_an_approve_through(
        open_review_grant, stub_module_transport_factory):
    """The happy path that replaces `test_only_the_exact_string_true_proceeds`: an open
    grant covering this record, plus the session arm, is what now authorizes an approve."""
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    assert result["available"] is True
    assert len(transport.mutating_calls) == 1


def test_an_unarmed_refusal_restates_the_previewed_write_without_calling_anything(
        open_review_grant, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])
    preview = {"available": True, "would_write": APPROVE_WRITE}

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=False, grant=open_review_grant, preview=preview, transport=transport)

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
    """An unrecognised word is not un-doing (`is_undoing` fails closed), so it still needs
    gate 1 — with no grant, it refuses exactly like an approve would."""
    transport = stub_module_transport_factory([{"outcome": "refused"}])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "dismiss", "r", "Robert",
        review_armed=True, grant=None, transport=transport)

    assert result["reason"] == review_decision.GRANT_REFUSAL_REASON
    assert transport.calls == []


# --- carve-out: the preview is never gated -------------------------------------------

def test_preview_is_unaffected_by_the_grant_gate(stub_module_transport_factory):
    """A dry run writes nothing, and without it the operator cannot see what they are
    being asked to approve. No grant is passed at all — `preview_decision` takes none."""
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

def test_the_request_carries_only_the_six_accepted_keys(
        open_review_grant, stub_module_transport_factory):
    """No field name, no value, no patch: this client cannot tell the endpoint WHAT to
    write, only which record and which decision word (T-30-05)."""
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", 789, "approve", "Looks right", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    body = transport.calls[0]["json"]
    assert set(body) == {"object_type", "record_id", "decision", "reason", "reviewed_by",
                         "dry_run"}
    assert body["record_id"] == "789"
    assert body["reviewed_by"] == "Robert"


def test_an_armed_submit_sends_the_dry_run_flag_false_exactly_once(
        open_review_grant, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    assert transport.verbs == ["post"]
    assert [call["json"]["dry_run"] for call in transport.calls] == [False]


def test_the_secret_travels_in_the_header_and_the_url_never_carries_it(
        open_review_grant, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    call = transport.calls[0]
    assert call["headers"] == {"X-Enrichment-Secret": CONFIG["webhook_secret"]}
    assert CONFIG["webhook_secret"] not in call["url"]
    assert call["url"] == "https://n8n.example/webhook/hubspot/review/decision"


def test_a_missing_reviewer_label_becomes_a_neutral_placeholder_not_an_empty_string(
        open_review_grant, stub_module_transport_factory):
    """The backend writes lv_enrichment_reviewed_by only when the label is non-empty, so
    an empty string would leave the audit trail naming nobody."""
    transport = stub_module_transport_factory([applied_response(), applied_response()])

    for label in (None, "   "):
        review_decision.submit_decision(
            CONFIG, "companies", "789", "approve", "r", label,
            review_armed=True, grant=open_review_grant, transport=transport)

    assert [c["json"]["reviewed_by"] for c in transport.calls] == \
        [review_decision.DEFAULT_REVIEWED_BY] * 2
    assert review_decision.DEFAULT_REVIEWED_BY.strip() != ""


def test_a_decision_without_a_reason_is_still_a_decision(
        open_review_grant, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", None, "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    assert transport.calls[0]["json"]["reason"] == ""


# --- configuration: require_capability RAISES, runtime degrades (D-35) ----------------

def test_a_misconfiguration_raises_before_any_transport_is_constructed(
        open_review_grant, stub_module_transport_factory):
    transport = stub_module_transport_factory([applied_response()])

    with pytest.raises(config_gate.ConfigError) as excinfo:
        review_decision.submit_decision(
            {"n8n_url": "https://n8n.example"}, "companies", "789", "approve", "r",
            "Robert", review_armed=True, grant=open_review_grant, transport=transport)

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
        open_review_grant, stub_module_transport_factory, scripted, reason):
    """None of these raises, and none of them is distinguishable from a rejected write by
    a caller that reads the status alone (D-23, D-35)."""
    transport = stub_module_transport_factory([scripted])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    assert result == {"available": False, "reason": reason, "outcome": None,
                      "message": None, "would_write": None,
                      "verified_properties": None, "verified": None}


def test_an_empty_body_is_reported_as_failed_never_as_a_completed_write(
        open_review_grant, stub_module_transport_factory):
    """An armed-but-not-allowlisted decision returns NO body at all — the write gate drops
    the row and nothing reaches the responder (D-23)."""
    transport = stub_module_transport_factory([(200, ValueError("Expecting value"))])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

    assert review_decision.verify_decision(APPROVE_WRITE, result)["status"] == "failed"


def test_a_dict_response_is_parsed_directly_never_as_body_zero(
        open_review_grant, stub_module_transport_factory):
    """`respondWith: firstIncomingItem` — ONE dict, not an array (D-24)."""
    transport = stub_module_transport_factory([applied_response()])

    result = review_decision.submit_decision(
        CONFIG, "companies", "789", "approve", "r", "Robert",
        review_armed=True, grant=open_review_grant, transport=transport)

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
    """D-30's six outcomes plus `not_allowlisted` (Phase 31 Plan 02, BUG 30), and nothing
    resolves to an unhandled state."""
    assert set(review_decision.OUTCOMES) == {
        "applied", "rejected", "stale", "no_candidate", "not_flagged", "refused",
        "not_allowlisted"}
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
        open_review_grant, stub_module_transport_factory):
    """Arming once does not leave anything behind that a second, unarmed call can read. The
    SAME grant is passed to both calls — this test is about `review_armed` never persisting,
    not about the grant, so gate 1 passes both times and only gate 2 toggles."""
    transport = stub_module_transport_factory([applied_response()])

    review_decision.submit_decision(CONFIG, "companies", "789", "approve", "r", "Robert",
                                    review_armed=True, grant=open_review_grant,
                                    transport=transport)
    second = review_decision.submit_decision(CONFIG, "companies", "789", "approve", "r",
                                             "Robert", review_armed=False,
                                             grant=open_review_grant, transport=transport)

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
