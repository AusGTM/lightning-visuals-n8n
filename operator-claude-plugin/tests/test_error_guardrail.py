"""D-05's guardrail on the unmatched branch (27-02 Task 2).

Deliberately a separate file from test_error_translation.py: this is the behaviour a
later edit is most likely to erode quietly, and a wrong "you can fix this" on a status
surface causes a real-world wrong action. The three required properties — labelled as an
interpretation, raw text shown, attribution defaulted to an admin — plus redaction of
credential-shaped material (T-27-06) and a bound on raw length (T-27-08).
"""
import re

import error_table

# Varied failure text the table does not (and should not) recognise. Deliberately none of
# them carry an auth / rate / quota / rejected-record signature.
UNRECOGNISED = [
    "ECONNRESET while talking to the upstream host",
    "socket hang up",
    "Cannot read properties of undefined (reading 'json')",
    "The workflow was cancelled by a user",
    "Unexpected end of JSON input",
    "getaddrinfo ENOTFOUND some-host.example",
    "Workflow execution stopped at node 'Merge Contacts'",
    "Error: connect ETIMEDOUT",
    "self signed certificate in certificate chain",
    "n8n encountered an unknown problem while running the node",
    "Execution was harvested after the instance restarted",
    "TypeError: items.map is not a function",
]


def test_an_unmatched_text_is_labelled_as_an_interpretation():
    result = error_table.translate(UNRECOGNISED[0])
    assert result["matched"] is False
    assert result["is_interpretation"] is True


def test_an_unmatched_result_carries_non_empty_raw_text():
    for text in UNRECOGNISED:
        assert error_table.translate(text)["raw"]


def test_the_unmatched_sentence_names_no_cause_from_the_table():
    sentence = error_table.translate(UNRECOGNISED[1])["sentence"].lower()
    for entry in error_table.TABLE:
        for word in entry.cause.split("_"):
            assert not re.search(rf"\b{word}\b", sentence), word
        assert entry.sentence not in sentence


def test_no_unrecognised_failure_is_ever_blamed_on_the_operator():
    """The sweep. If this ever fails, someone gave the unmatched branch an override."""
    blamed = [
        text
        for text in UNRECOGNISED
        if error_table.translate(text)["who_can_fix"] != error_table.ADMIN
    ]
    assert len(UNRECOGNISED) >= 10
    assert blamed == []


def test_the_admin_attribution_has_no_override_parameter():
    # translate() takes exactly one argument: there is no seam through which a caller
    # could pass a different attribution for an unrecognised failure.
    import inspect

    assert list(inspect.signature(error_table.translate).parameters) == ["text"]


def test_a_bearer_value_is_redacted_from_the_raw_text():
    secret = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    raw = error_table.translate(f"Request failed with Bearer {secret} upstream")["raw"]
    assert secret not in raw
    assert error_table.REDACTED in raw


def test_an_authorization_header_line_is_redacted():
    line = "sent X-N8N-API-KEY: n8n_api_9f8c7b6a5d4e3f2a1b0c9d8e7f6a5b4c to the host"
    raw = error_table.translate(line)["raw"]
    assert "n8n_api_9f8c7b6a5d4e3f2a1b0c9d8e7f6a5b4c" not in raw
    assert error_table.REDACTED in raw


def test_a_bare_key_shaped_token_is_redacted():
    token = "pat-na1-0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a"
    raw = error_table.translate(f"token {token} was rejected by the host")["raw"]
    assert token not in raw
    assert error_table.REDACTED in raw


def test_redaction_leaves_the_surrounding_message_readable():
    text = (
        "Request to https://fake-tenant.n8n.cloud failed, header was "
        "Authorization: Bearer sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx, upstream closed"
    )
    raw = error_table.translate(text)["raw"]
    assert raw != text
    assert "Request to https://fake-tenant.n8n.cloud failed" in raw
    assert "upstream closed" in raw


def test_a_very_long_raw_text_is_truncated_with_an_explicit_marker():
    long_text = "the upstream host closed the connection unexpectedly " * 200
    raw = error_table.translate(long_text)["raw"]
    assert len(raw) <= error_table.MAX_RAW_CHARS + len(error_table.TRUNCATION_MARKER)
    assert raw.endswith(error_table.TRUNCATION_MARKER)


def test_a_matched_result_is_redacted_too():
    """The guardrail belongs to translate(), not to the unmatched branch's caller."""
    secret = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    result = error_table.translate(f"401 Unauthorized, Bearer {secret}")
    assert result["cause"] == "expired_credential"
    assert secret not in result["raw"]
