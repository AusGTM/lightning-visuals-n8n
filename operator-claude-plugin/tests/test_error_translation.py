"""The deterministic half of failure-cause translation (27-02 Task 1, STATUS-02).

Covers the matching path only: the four causes STATUS-02 names, each reachable by cause
name, each rendering one plain sentence with an attribution of who can act on it. The
unmatched branch's guarantees live in test_error_guardrail.py — deliberately a separate
file, because that behaviour is the one a later edit is most likely to erode quietly.
"""
import error_table

ADMIN = "admin"
OPERATOR = "operator"

# One realistic message per seeded cause, in the vocabulary each surface actually produces.
SAMPLES = {
    "expired_credential": "HubSpot request failed: 401 Unauthorized - invalid credentials",
    "rate_limit": "Lusha responded 429 Too Many Requests, retry later",
    "exhausted_quota": "ZoomInfo GTM: insufficient credits remaining for this account",
    "malformed_record": (
        "HubSpot Create failed: 400 Bad Request - Property values were not valid"
    ),
}


def test_authentication_rejection_translates_to_expired_credential():
    result = error_table.translate(SAMPLES["expired_credential"])
    assert result["matched"] is True
    assert result["cause"] == "expired_credential"
    assert result["who_can_fix"] == ADMIN
    assert result["is_interpretation"] is False


def test_too_many_requests_translates_to_rate_limit_and_says_it_clears():
    result = error_table.translate(SAMPLES["rate_limit"])
    assert result["cause"] == "rate_limit"
    assert result["who_can_fix"] == ADMIN
    assert "clears on its own" in result["sentence"]


def test_quota_exhaustion_translates_to_exhausted_quota():
    result = error_table.translate(SAMPLES["exhausted_quota"])
    assert result["cause"] == "exhausted_quota"
    assert result["who_can_fix"] == ADMIN


def test_record_rejected_by_the_crm_is_the_operators_to_fix():
    result = error_table.translate(SAMPLES["malformed_record"])
    assert result["cause"] == "malformed_record"
    # The row came from the operator, so they are the one who can correct it.
    assert result["who_can_fix"] == OPERATOR


def test_all_four_named_causes_are_reachable():
    reached = {error_table.translate(text)["cause"] for text in SAMPLES.values()}
    assert reached == set(SAMPLES)


def test_every_seeded_sentence_is_one_plain_sentence():
    for entry in error_table.TABLE:
        sentence = entry.sentence
        assert sentence.endswith("."), sentence
        assert sentence.count(".") == 1, sentence
        assert "!" not in sentence and "?" not in sentence, sentence
        # No bare status code, no traceback marker (STATUS-02).
        assert not any(ch.isdigit() for ch in sentence), sentence
        assert "Traceback" not in sentence, sentence
        assert "    at " not in sentence, sentence
        assert "\n" not in sentence, sentence


def test_matching_is_case_insensitive_and_works_on_a_substring():
    noisy = (
        "Node 'Lusha Enrich' errored at 2026-07-31T04:00:00Z :: "
        "TOO MANY REQUESTS :: see execution log"
    )
    assert error_table.translate(noisy)["cause"] == "rate_limit"


def test_the_same_input_always_returns_the_same_entry():
    text = SAMPLES["exhausted_quota"]
    assert error_table.translate(text) == error_table.translate(text)


def test_the_first_matching_entry_wins_and_the_order_is_explicit():
    causes = [entry.cause for entry in error_table.TABLE]
    assert causes.index("expired_credential") < causes.index("exhausted_quota")
    both = "401 Unauthorized: your credit balance is exhausted"
    assert error_table.translate(both)["cause"] == "expired_credential"


def test_null_empty_and_non_string_inputs_return_unmatched_rather_than_raising():
    for bad in (None, "", "   ", 42, {"message": "boom"}, ["boom"]):
        result = error_table.translate(bad)
        assert result["matched"] is False
        assert result["cause"] is None
        assert result["who_can_fix"] == ADMIN
