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

# Phase 13: kept in parity with the production n8n research prompt (Task 3 point 4) — this
# dev-oracle prompt is not itself executed by any test, but the two must not drift (RESEARCH
# "State of the Art"). Now requires entity_resolution + per-field evidence_by_field, matching
# what validate_research_output/to_provider_result (src/taxonomy.py) actually consume.
RESEARCH_SYSTEM = (
    "You are an ICP research analyst. Use web search to research the company across three "
    "query intents: identity (<name> <domain> about), content (<name> watch live | broadcast "
    "| streaming), and size (<name> annual report revenue — only when a revenue band is not "
    "already known). Then return ONLY a single JSON object (no prose, no markdown fences) "
    "matching this schema:\n"
    '{"provider":"claude_web","object_type":"companies","matched":<bool>,'
    '"confidence":<int 0-100>,"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,'
    '"lv_content_type":[<str>],"lv_is_hardware_vendor":<bool|null>,'
    '"lv_is_gambling_operator":<bool|null>},'
    '"evidence_by_field":{"<field>":"<url>"},'
    '"entity_resolution":{"represents":"group|subsidiary|franchise_outlet|single_entity|unknown",'
    '"likely_revenue_band":<str|null>,"notes":<str>},'
    '"evidence":{"last_seen":<str|null>,"match_basis":[<str>],'
    '"evidence_urls":[<str>],"evidence_summary":<str>},'
    '"model_trace":{"research_model":"claude-web","classifier_model":null,"validator_model":null}}\n'
    "Prefer \"unknown\"/null over guessing — an absent search result is NOT evidence of "
    "absence. Cite a supporting URL in evidence_by_field for every field you set in data, "
    "keyed by that exact field name. First-party domains are preferred for identity and "
    "content; reputable secondary sources are fine for size. If sources conflict, set "
    "confidence below 75 and explain in evidence_summary. lv_is_hardware_vendor and "
    "lv_is_gambling_operator are hard-veto inputs — answer null unless a cited source "
    "directly supports the classification."
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
        # ponytail: 2000 truncated live responses (stop_reason=max_tokens) before
        # evidence_by_field ever got written — claude-sonnet-5's extended thinking alone
        # eats ~1000-1300 tokens on this prompt. 4096 leaves ~45% headroom over the
        # largest observed complete response (2829 total). Bump further if it recurs.
        max_tokens=4096,
        system=RESEARCH_SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        messages=[{"role": "user", "content": json.dumps(user_payload)}],
    )

    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    data = _extract_json(text)
    data.setdefault("provider", "claude_web")
    data.setdefault("object_type", record.object_type)
    return ProviderResult(**data)
