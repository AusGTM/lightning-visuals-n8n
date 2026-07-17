# src/web_research.py
#
# Claude web-research adapter. Mock path (default) reads a fixture. The live path uses
# the NATIVE Anthropic web-search server tool on the standard Messages API — no separate
# research endpoint or API key; it authenticates with ANTHROPIC_API_KEY like every other
# Anthropic call. See platform.claude.com/docs .../tool-use/web-search-tool.
import json
import os
import re
from pathlib import Path
from .schemas import HubSpotRecord, ProviderResult

FIXTURE_DIR = Path("tests/fixtures")

REQUIRED_FIELDS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_content_type",
    "lv_sponsorship_reliant",
    "lv_is_hardware_vendor",
    "lv_is_gambling_operator",
    "lv_country_region_normalized",
    "lv_has_sports_media_fit",
    "lv_has_broadcast_or_streaming_signals",
]

RESEARCH_SYSTEM = (
    "You are an ICP research analyst. Use web search to research the company, then return "
    "ONLY a single JSON object (no prose, no markdown fences) matching this schema:\n"
    '{"provider":"claude_web","object_type":"companies","matched":<bool>,'
    '"confidence":<int 0-100>,"data":{<the required ICP fields>},'
    '"evidence":{"last_seen":<str|null>,"match_basis":[<str>],'
    '"evidence_urls":[<str>],"evidence_summary":<str>},'
    '"model_trace":{"research_model":"claude-web","classifier_model":null,"validator_model":null}}\n'
    "Prefer \"unknown\"/null over guessing. Include evidence_urls for org_type and content output. "
    "If sources conflict, set confidence below 75 and explain in evidence_summary."
)


def mock_claude_web_research(record: HubSpotRecord) -> ProviderResult:
    return ProviderResult(**json.loads((FIXTURE_DIR / "claude_web_research_company.json").read_text()))


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of the model's final text (tolerate ```fences``` / stray prose)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.MULTILINE).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def claude_web_research(record: HubSpotRecord) -> ProviderResult:
    if os.getenv("USE_MOCK_WEB_RESEARCH", "true").lower() == "true":
        return mock_claude_web_research(record)

    # Native web search: standard Messages API + the web_search server tool. Uses the
    # ambient ANTHROPIC_API_KEY (Anthropic() reads it) — no dedicated endpoint/key.
    from anthropic import Anthropic

    client = Anthropic()
    model = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-5")
    max_uses = int(os.getenv("WEB_RESEARCH_MAX_SEARCHES", "5"))

    props = record.properties
    user_payload = {
        "task": "company_icp_research",
        "company": {
            "name": props.get("name"),
            "domain": props.get("domain"),
            "website": props.get("website"),
            "country": props.get("country"),
            "industry": props.get("industry"),
        },
        "required_fields": REQUIRED_FIELDS,
        "return_only_json": True,
    }

    msg = client.messages.create(
        model=model,
        max_tokens=2000,
        system=RESEARCH_SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        messages=[{"role": "user", "content": json.dumps(user_payload)}],
    )

    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    data = _extract_json(text)
    data.setdefault("provider", "claude_web")
    data.setdefault("object_type", record.object_type)
    return ProviderResult(**data)
