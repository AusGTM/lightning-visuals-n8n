"""tests/test_role_vocabulary_derivation.py

Quick task 260904-39r (closes G-62-5 in .planning/phases/62-.../62-UAT.md).

Offline-only. No HubSpot read, no Anthropic call, no credential -- tests/conftest.py's
autouse `no_ambient_credentials` fixture already strips both guarded env vars for every
test in this module; the `anthropic.Anthropic` class itself is monkeypatched to a fake
that never opens a socket.

Fixture disclosure (tests/fixtures/role_vocabulary_truncated_response.txt): this is a
SHAPE-FAITHFUL RECONSTRUCTION of the response measured live during the Phase 62 UAT
sitting (G-62-5), not the byte-exact live capture -- the probe script that produced the
original (`scripts/uat62_cluster_probe.py`) was untracked and was deleted by plan 62-10,
so the original bytes are unrecoverable. It reproduces every marker `62-UAT.md` § G-62-5
actually measured: opens with a ```json fence, never closes it, contains several
well-formed families of plausible racing/media job titles, and terminates mid-object with
the exact tail `"Senior Stipendiary Steward"\\n      ]\\n    },\\n    {`.
"""
import json
import sys
from pathlib import Path

import anthropic
import pytest
import yaml

import scripts.role_vocabulary as role_vocabulary

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "role_vocabulary_truncated_response.txt"
TRUNCATED_TEXT = FIXTURE_PATH.read_text()


# --------------------------------------------------------------------------------------
# Fake Anthropic client plumbing. cluster_titles() does `from anthropic import Anthropic`
# inside the function body, so patching the attribute on the `anthropic` MODULE is what
# takes effect -- the local import re-reads `anthropic.Anthropic` on every call.
# --------------------------------------------------------------------------------------

class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_FakeBlock(text)]
        self.stop_reason = stop_reason


class _FakeMessages:
    """Returns queued responses in order, one per `.create()` call. Records every call's
    kwargs so a test can assert what was actually sent (D-1's head-only assertion)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeMessages.create() called more times than responses queued")
        return self._responses.pop(0)


def _fake_anthropic_class(responses):
    """Factory returning a class usable as `anthropic.Anthropic` -- constructed with no
    args (as cluster_titles does), exposing `.messages` (a _FakeMessages queue)."""
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages(list(responses))
    return _FakeClient


class _RaisingAnthropicClient:
    """Construction itself raises -- used to prove a code path never even tries to build
    a real client (D-62-07's sparse-path guarantee)."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("Anthropic() must not be constructed on this path")


# ============================== Task 1 ==============================

def test_truncated_response_raises_named_error_not_jsondecodeerror(monkeypatch):
    fake_cls = _fake_anthropic_class([_FakeMessage(TRUNCATED_TEXT, stop_reason="max_tokens")])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    with pytest.raises(role_vocabulary.RoleVocabularyDerivationError) as excinfo:
        role_vocabulary.cluster_titles(["Track Manager", "Broadcast Manager"])

    message = str(excinfo.value)
    assert "max_tokens" in message
    assert "2" in message  # number of titles sent
    assert str(role_vocabulary.MAX_TOKENS) in message


def test_fenced_but_complete_response_parses(monkeypatch):
    complete_json = json.dumps({
        "families": [
            {"label": "Broadcast", "members": ["Broadcast Manager", "Broadcast Technician"]},
        ]
    })
    fenced = f"```json\n{complete_json}\n```"
    fake_cls = _fake_anthropic_class([_FakeMessage(fenced, stop_reason="end_turn")])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    families = role_vocabulary.cluster_titles(["Broadcast Manager", "Broadcast Technician"])

    assert families == [{"label": "Broadcast", "members": ["Broadcast Manager", "Broadcast Technician"]}]


def test_complete_unparseable_response_triggers_one_repair_call_that_succeeds(monkeypatch):
    garbage = "not json at all, sorry"
    complete_json = json.dumps({"families": [{"label": "Ops", "members": ["Ops Manager"]}]})
    fake_cls = _fake_anthropic_class([
        _FakeMessage(garbage, stop_reason="end_turn"),
        _FakeMessage(complete_json, stop_reason="end_turn"),
    ])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    families = role_vocabulary.cluster_titles(["Ops Manager"])

    assert families == [{"label": "Ops", "members": ["Ops Manager"]}]


def test_repair_response_itself_truncated_raises_named_error(monkeypatch):
    garbage = "not json at all, sorry"
    fake_cls = _fake_anthropic_class([
        _FakeMessage(garbage, stop_reason="end_turn"),
        _FakeMessage(TRUNCATED_TEXT, stop_reason="max_tokens"),
    ])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    with pytest.raises(role_vocabulary.RoleVocabularyDerivationError) as excinfo:
        role_vocabulary.cluster_titles(["Ops Manager"])

    assert not isinstance(excinfo.value, json.JSONDecodeError)
    assert "max_tokens" in str(excinfo.value)


def test_two_unparseable_responses_raise_named_error(monkeypatch):
    fake_cls = _fake_anthropic_class([
        _FakeMessage("garbage one", stop_reason="end_turn"),
        _FakeMessage("garbage two", stop_reason="end_turn"),
    ])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    with pytest.raises(role_vocabulary.RoleVocabularyDerivationError):
        role_vocabulary.cluster_titles(["Ops Manager"])

