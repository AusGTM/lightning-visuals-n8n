# src/classifier_haiku.py
#
# Haiku cheap-classifier. Transcribed from CLAUDE.md §12.5.
# Offline fallback (no ANTHROPIC_API_KEY) returns a conservative stage_only with
# no network call; the live Anthropic branch is transcribed but not exercised here.
import json
import os
import re
from anthropic import Anthropic


def _response_text(msg):
    # `msg.content` is a LIST OF BLOCKS, and the first one is not necessarily the
    # text. A model with extended thinking on returns a ThinkingBlock first, which
    # has no `.text` -- indexing [0] blindly raises AttributeError against every
    # current model. Join the text blocks and ignore the rest. Same idiom as
    # `web_research.py` and CLAUDE.md §12.3. Shared here because `validator_sonnet`
    # already imports from this module and had the identical defect.
    return "".join(
        b.text for b in msg.content if getattr(b, "type", None) == "text"
    )


def _parse_json(text):
    # Models occasionally wrap JSON in prose or ```json fences; extract the object.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


SYSTEM_PROMPT = """
You are a deterministic CRM and ICP data classifier.
Return only valid JSON.
Do not invent facts.
Use only the provided candidate values and evidence.
Prefer non-clobbering behavior.
Manual CRM values are authoritative unless blank, stale, system-owned, or low-confidence.
For ICP fields, classify conservatively and flag uncertainty.
"""


def classify_field_with_haiku(record, field, current_value, candidates, policy):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5")

    if not api_key:
        return {
            "decision": "stage_only",
            "confidence": 50,
            "reason": "No Anthropic API key configured; conservative fallback."
        }

    client = Anthropic(api_key=api_key)

    payload = {
        "record": {
            "object_type": record.object_type,
            "id": record.id,
            "selected_properties": {
                "name": record.properties.get("name"),
                "domain": record.properties.get("domain"),
                "website": record.properties.get("website"),
                "country": record.properties.get("country"),
                "industry": record.properties.get("industry")
            }
        },
        "field": field,
        "current_value": current_value,
        "policy": policy,
        "candidates": [c.model_dump() for c in candidates],
        "allowed_decisions": ["promote", "stage_only", "reject", "needs_review"],
        "required_json_schema": {
            "decision": "promote|stage_only|reject|needs_review",
            "chosen_provider": "string|null",
            "chosen_value": "any|null",
            "confidence": "integer 0-100",
            "reason": "short explanation",
            "requires_sonnet_validation": "boolean"
        }
    }

    msg = client.messages.create(
        model=model,
        max_tokens=700,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload)}]
    )

    # SPEC-defect fix (§12.5): SDK returns content as a list of blocks, not `.text`.
    return _parse_json(_response_text(msg))
