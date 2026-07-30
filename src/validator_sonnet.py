# src/validator_sonnet.py
#
# Sonnet conflict validator. Transcribed from CLAUDE.md §12.6.
# Guard returns a conservative needs_review with no network call when Sonnet
# escalation is disabled or no key is present; the live branch is not exercised here.
import json
import os
from anthropic import Anthropic
from .classifier_haiku import _parse_json

SYSTEM_PROMPT = """
You are a senior CRM data validation and ICP reasoning analyst.
Return only valid JSON.
Use only provided evidence.
Do not invent sources.
Your job is to resolve conflicting enrichment data and identify whether a field is safe to promote, should be staged, rejected, or requires human review.
Be especially cautious with anti-ICP, no-content, hardware vendor, gambling operator, and org-type decisions.
"""


def validate_conflict_with_sonnet(record, field, current_value, candidates, haiku_result, policy):
    allow = os.getenv("ALLOW_JUDGE_ESCALATION", "true").lower() == "true"
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_JUDGE_MODEL", "claude-sonnet-5")

    if not allow or not api_key:
        return {
            "decision": "needs_review",
            "chosen_provider": None,
            "chosen_value": None,
            "confidence": 50,
            "reason": "Sonnet escalation disabled or unavailable; conservative needs_review.",
            "validation_status": "human_review_required"
        }

    client = Anthropic(api_key=api_key)

    payload = {
        "task": "validate_conflicting_icp_or_enrichment_field",
        "record": record.model_dump(),
        "field": field,
        "current_value": current_value,
        "policy": policy,
        "candidates": [c.model_dump() for c in candidates],
        "haiku_result": haiku_result,
        "required_json_schema": {
            "decision": "promote|stage_only|reject|needs_review",
            "chosen_provider": "string|null",
            "chosen_value": "any|null",
            "confidence": "integer 0-100",
            "reason": "short explanation",
            "validation_status": "sonnet_validated|conflicting|human_review_required|rejected",
            "evidence_url": "string|null",
            "evidence_summary": "string|null"
        }
    }

    msg = client.messages.create(
        model=model,
        max_tokens=1200,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload)}]
    )

    # SPEC-defect fix (§12.6): SDK returns content as a list of blocks, not `.text`.
    return _parse_json(msg.content[0].text)
