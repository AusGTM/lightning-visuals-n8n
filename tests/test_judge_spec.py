"""Acceptance tests for Phase 14 (Judge Wiring), docs/WEB-RESEARCH-SPEC.md §8.

Spec-first: each test cites a requirement ID by name in its name/docstring, following
tests/test_web_research_spec.py's convention.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load_workflow(name: str) -> dict:
    return json.loads((ROOT / "n8n" / name).read_text())


def _node_by_name(doc: dict, name: str) -> dict:
    for n in doc["nodes"]:
        if n["name"] == name:
            return n
    raise AssertionError(f"node {name!r} not found in workflow")


def _reachable(doc: dict, start_name: str) -> set:
    """BFS over the connections map: node names reachable from start_name (exclusive)."""
    conns = doc.get("connections", {})
    seen = set()
    frontier = [start_name]
    while frontier:
        cur = frontier.pop()
        for output in (conns.get(cur, {}).get("main") or []):
            for edge in output:
                nxt = edge["node"]
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
    return seen


def test_jg1_confidence_band_matches_spec():
    """JG-1: spec §8 states escalation confidence in 75-85, inclusive both ends."""
    from src.judge import ESCALATION_CONFIDENCE_BAND

    assert ESCALATION_CONFIDENCE_BAND == [75, 85]


def test_jg3_judge_minimum_is_80():
    """JG-3: a judge verdict below confidence 80 never promotes."""
    from src.judge import JUDGE_MIN_CONFIDENCE

    assert JUDGE_MIN_CONFIDENCE == 80


def test_escalation_generated_js_is_current():
    """The Code-node threshold literal (n8n cannot read config/escalation_policy.yaml at
    runtime, spec AR-4) must be exactly what the generator would emit right now. A stale
    checked-in file after a YAML edit is the drift this test exists to catch."""
    import gen_escalation_js

    checked_in = (ROOT / "n8n" / "code" / "escalation.generated.js").read_text()
    assert gen_escalation_js.render() == checked_in, (
        "n8n/code/escalation.generated.js is stale. Regenerate with: "
        ".venv/bin/python scripts/gen_escalation_js.py"
    )


def _block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def test_prompt_parity_vendor_flags():
    """Criterion 5 drift check (did not exist before this phase): the production
    research prompt (scripts/build_cloud_workflows.py's ENRICH_BUILD_RESEARCH_REQUEST)
    and the dev-oracle prompt (src/web_research.py's RESEARCH_SYSTEM) are independently
    hand-written and must not drift (Pitfall 4) — both must request
    lv_is_hardware_vendor / lv_is_gambling_operator."""
    web_research_src = (ROOT / "src" / "web_research.py").read_text()
    research_system_block = _block(web_research_src, "RESEARCH_SYSTEM = (", "\ndef mock_claude_web_research")

    builder_src = (ROOT / "scripts" / "build_cloud_workflows.py").read_text()
    build_request_block = _block(
        builder_src, "ENRICH_BUILD_RESEARCH_REQUEST = inline", "\nENRICH_VALIDATE_RESEARCH ="
    )

    for field in ("lv_is_hardware_vendor", "lv_is_gambling_operator"):
        assert field in research_system_block, (
            f"{field} missing from src/web_research.py's RESEARCH_SYSTEM"
        )
        assert field in build_request_block, (
            f"{field} missing from scripts/build_cloud_workflows.py's ENRICH_BUILD_RESEARCH_REQUEST"
        )


def test_jg5_supertech_hardware_veto_independent_of_jg4():
    """JG-5 (offline dev-oracle rubric proof, Approach C): src/icp_scoring.py's existing
    hardware-vendor hard veto fires for Supertech Electronics whether lv_produces_content
    is the un-demoted false positive (True) or the JG-4-demoted value (None). This
    exercises the UNCHANGED src/icp_scoring.py as a dev oracle only (AR-3) — it asserts
    nothing about any n8n write path; no veto is computed in production JS (Approach C).

    DISCOVERED GAP (documented, not silently patched — Task 1's Do-Not list forbids
    touching src/icp_scoring.py in this plan): the veto SIGNAL (`anti_icp_flag` +
    `anti_icp_reason`, the two fields Approach C's internal routing actually reads) is
    empirically independent of lv_produces_content in both branches, proven below.
    The `tier` LABEL is not, in the None branch only: icp_scoring.py's pre-existing
    confidence-downgrade block (lines ~115-119) unconditionally rewrites `tier` to
    "Needs Review"/"Unscored" whenever `lv_produces_content is None`, WITHOUT checking
    whether `anti_icp_flag` already fired — a precedence bug that predates this phase
    (present before Task 1 touched this file at all; reproduced against the unmodified
    module). Per the plan's own instruction ("if it passes in only one [branch], the
    veto is not independent and the plan's premise is wrong; stop and report"), this is
    reported here rather than force-asserted or silently fixed. See 14-01-SUMMARY.md
    "Deviations" for the one-line fix this would take and the recommendation to get
    explicit sign-off before applying it (icp_scoring.py is shared by other pinned
    score/tier assertions in tests/test_icp_scoring.py and tests/test_web_research_spec.py).
    """
    from src.icp_scoring import compute_icp_score
    from src.schemas import HubSpotRecord

    base_props = {
        "name": "Supertech Electronics",
        "domain": "www.supertech-electronics.com.au",
        "lv_org_type": "hardware_vendor",
        "lv_country_region_normalized": "AU",
        "lv_is_hardware_vendor": True,
    }

    # (lv_produces_content, expected exact tier or None to accept the documented-gap set)
    cases = [(True, "D"), (None, None)]

    for produces_content, expected_tier in cases:
        rec = HubSpotRecord(
            object_type="companies", id="supertech-1",
            properties={**base_props, "lv_produces_content": produces_content},
        )
        result = compute_icp_score(rec, {})
        # The veto SIGNAL fires independently of lv_produces_content in BOTH branches —
        # this is the claim Approach C's internal routing actually relies on.
        assert result.anti_icp_flag is True, (
            f"hardware-vendor veto must fire independently of lv_produces_content={produces_content!r}"
        )
        assert "hardware" in (result.anti_icp_reason or "").lower()

        if expected_tier is not None:
            assert result.tier == expected_tier
        else:
            # Documented gap: tier LABEL is downgraded by the confidence-downgrade block
            # despite anti_icp_flag already True. Assert the actual (buggy but pre-existing)
            # behavior explicitly so a future fix to icp_scoring.py's precedence flips this
            # to "D" and this assertion is the one that then needs updating — not a silent
            # pass either way.
            assert result.tier in ("Needs Review", "Unscored"), (
                f"expected the documented pre-existing tier-downgrade gap, got {result.tier!r}"
            )


def test_ro2_judge_gate_cannot_see_size_conflicts():
    """RO-2 (structural, not documentary): the Judge Gate node's jsCode must contain
    neither the size-disagreement array identifier nor the watch-list constant name, AND
    the Judge Gate node must be a graph ancestor of Merge Company (never the reverse) —
    the size array is computed INSIDE Merge Company's own wrapper, downstream of where
    this gate runs, so a node upstream of it structurally cannot reference it."""
    doc = _load_workflow("wf_enrichment_local_live.json")
    judge_gate = _node_by_name(doc, "Judge Gate")
    js_code = judge_gate["parameters"]["jsCode"]

    assert not re.search(r"row\.conflicts", js_code), (
        "RO-2: Judge Gate must not reference the downstream size-disagreement array "
        "(row.conflicts is computed inside Merge Company, not here)"
    )
    assert "CONFLICT_WATCH" not in js_code, (
        "RO-2: Judge Gate must not reference the downstream size watch-list constant"
    )

    downstream_of_judge_gate = _reachable(doc, "Judge Gate")
    assert "Merge Company" in downstream_of_judge_gate, (
        "RO-2: Judge Gate must be a graph ancestor of Merge Company"
    )
    downstream_of_merge_company = _reachable(doc, "Merge Company")
    assert "Judge Gate" not in downstream_of_merge_company, (
        "RO-2: Merge Company must never be able to reach back to Judge Gate"
    )


def test_jg2_judge_call_declares_no_search_tool():
    """JG-2/Pitfall 5: the judge reasons over evidence already retrieved — it must never
    declare the web_search tool (that would re-research inside the judge, doubling cost
    and contradicting RO-1's spirit)."""
    doc = _load_workflow("wf_enrichment_local_live.json")
    build_judge_request = _node_by_name(doc, "Build Judge Request")
    js_code = build_judge_request["parameters"]["jsCode"]
    assert "web_search" not in js_code


def test_ar2_judge_call_host():
    """AR-2: the Judge Call node's host must be the already-allowlisted api.anthropic.com
    (tests/test_architecture_guard.py covers this generically; asserted here too so a
    host typo in this phase's own new node fails loudly in this phase's own test file)."""
    doc = _load_workflow("wf_enrichment_local_live.json")
    judge_call = _node_by_name(doc, "Judge Call")
    url = judge_call["parameters"]["url"]
    assert "api.anthropic.com" in url
