# Offline checks for the web-research adapter: mock contract + the _extract_json parser
# that pulls the model's final JSON out of a native web_search response.
from src.web_research import _extract_json, mock_claude_web_research
from src.schemas import HubSpotRecord


def test_extract_json_plain_fenced_and_embedded():
    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}
    # model wrapped JSON in prose -> still extracted
    assert _extract_json('Here is the result:\n{"a": 1, "b": [2, 3]}\nDone.') == {"a": 1, "b": [2, 3]}


def test_mock_web_research_still_returns_claude_web_contract():
    rec = HubSpotRecord(object_type="companies", id="789", properties={"name": "X"})
    r = mock_claude_web_research(rec)
    assert r.provider == "claude_web"
    assert r.object_type == "companies"
