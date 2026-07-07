# src/web_research.py
#
# Claude web-research adapter. Transcribed from CLAUDE.md §12.3.
# Mock path (default) reads a fixture; the live HTTP branch is transcribed but
# never exercised in this phase (USE_MOCK_WEB_RESEARCH defaults to "true").
import json
import os
from pathlib import Path
import requests
from .schemas import HubSpotRecord, ProviderResult

FIXTURE_DIR = Path("tests/fixtures")


def mock_claude_web_research(record: HubSpotRecord) -> ProviderResult:
    return ProviderResult(**json.loads((FIXTURE_DIR / "claude_web_research_company.json").read_text()))


def claude_web_research(record: HubSpotRecord) -> ProviderResult:
    if os.getenv("USE_MOCK_WEB_RESEARCH", "true").lower() == "true":
        return mock_claude_web_research(record)

    endpoint = os.getenv("CLAUDE_WEB_RESEARCH_ENDPOINT")
    api_key = os.getenv("CLAUDE_WEB_RESEARCH_API_KEY")

    if not endpoint:
        raise RuntimeError("CLAUDE_WEB_RESEARCH_ENDPOINT is not configured")

    payload = {
        "task": "company_icp_research",
        "record": {
            "id": record.id,
            "object_type": record.object_type,
            "name": record.properties.get("name"),
            "domain": record.properties.get("domain"),
            "website": record.properties.get("website"),
            "country": record.properties.get("country"),
            "industry": record.properties.get("industry")
        },
        "required_fields": [
            "lv_org_type",
            "lv_produces_content",
            "lv_content_type",
            "lv_sponsorship_reliant",
            "lv_is_hardware_vendor",
            "lv_is_gambling_operator",
            "lv_country_region_normalized",
            "lv_has_sports_media_fit",
            "lv_has_broadcast_or_streaming_signals"
        ],
        "return_evidence_urls": True,
        "return_only_json": True
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    r = requests.post(endpoint, headers=headers, json=payload, timeout=90)
    r.raise_for_status()
    return ProviderResult(**r.json())
