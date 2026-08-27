"""tests/test_validator_sonnet.py

Pins the checkpoint-round-3 fix: src.validator_sonnet.validate_conflict_with_sonnet must
NOT pass an explicit `temperature` to messages.create(). claude-sonnet-5 (the
ANTHROPIC_JUDGE_MODEL default) rejects a non-default temperature with a 400 (confirmed via
the claude-api skill's sampling-parameters table) -- the old `temperature=0` would have
been a live 400 the first time this function's live branch actually ran against that
default model. Offline only: the fake Anthropic client below never makes a network call.
"""
import json

import src.validator_sonnet as validator_sonnet
from src.schemas import HubSpotRecord


class _FakeMessages:
    def __init__(self, captured):
        self._captured = captured

    def create(self, **kwargs):
        self._captured.update(kwargs)

        class _Block:
            # Every real SDK content block carries a `type`; the module filters on it
            # so a leading ThinkingBlock cannot be mistaken for the text. A stub without
            # `type` is unfaithful to the SDK, not a looser contract.
            type = "text"
            text = json.dumps({
                "decision": "promote",
                "chosen_provider": "claude_web",
                "chosen_value": True,
                "confidence": 90,
                "reason": "test",
                "validation_status": "sonnet_validated",
                "evidence_url": "https://example.com/evidence",
                "evidence_summary": "test",
            })

        class _Response:
            content = [_Block()]

        return _Response()


class _FakeAnthropic:
    def __init__(self, api_key=None):
        self.captured = {}
        self.messages = _FakeMessages(self.captured)


def test_validate_conflict_with_sonnet_never_passes_temperature(monkeypatch):
    monkeypatch.setenv("ALLOW_JUDGE_ESCALATION", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-offline-test")
    fake_client_holder = {}
    class _CapturingFakeAnthropic(_FakeAnthropic):
        def __init__(self, api_key=None):
            super().__init__(api_key=api_key)
            fake_client_holder["client"] = self
    monkeypatch.setattr(validator_sonnet, "Anthropic", _CapturingFakeAnthropic)

    record = HubSpotRecord(object_type="companies", id="1", properties={})
    result = validator_sonnet.validate_conflict_with_sonnet(
        record=record,
        field="lv_produces_content",
        current_value=None,
        candidates=[],
        haiku_result={"decision": "needs_review"},
        policy={"min_confidence": 85, "require_evidence_url": True},
    )

    assert result["decision"] == "promote"
    assert result["chosen_value"] is True
    assert "temperature" not in fake_client_holder["client"].captured
    assert "top_p" not in fake_client_holder["client"].captured
    assert "top_k" not in fake_client_holder["client"].captured


def test_validate_conflict_with_sonnet_disabled_never_calls_the_client(monkeypatch):
    # ALLOW_JUDGE_ESCALATION=false must short-circuit before any Anthropic client is
    # constructed -- the conservative needs_review fallback, no network call.
    monkeypatch.setenv("ALLOW_JUDGE_ESCALATION", "false")

    def _boom(*args, **kwargs):
        raise AssertionError("Anthropic client must not be constructed when escalation is disabled")

    monkeypatch.setattr(validator_sonnet, "Anthropic", _boom)

    result = validator_sonnet.validate_conflict_with_sonnet(
        record={"id": "1"}, field="lv_produces_content", current_value=None,
        candidates=[], haiku_result={}, policy={},
    )
    assert result["decision"] == "needs_review"
    assert result["validation_status"] == "human_review_required"
