# tests/test_enrichment_lane_dedup.py
#
# Phase 36 Plan 01, Task 1 — Finding A (36-CONTEXT.md §5A). `Adapt Search` and
# `Adapt Fetch By Id` both used to open with the unfiltered
# `const rows = $('Build Identity').all();` and index-align against their own HTTP
# node. Safe only while every batch was homogeneous — a mixed-lane batch (one row with
# an email, one without) would have both adapters emit BOTH rows into `Enrichment Gate`:
# duplicated provider calls, double credit burn, duplicate response items.
#
# This is a structural guard over the COMMITTED, regenerated `n8n/*.json` — the fix
# lives in `scripts/build_cloud_workflows.py`; this file proves the built artifact
# carries it, mirroring tests/test_fetch_by_id_topology.py's `_strip_comments` idiom so
# a comment merely naming a token cannot satisfy the guard.
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WF = ROOT / "n8n" / "wf_enrichment_cloud.json"
LOCAL_LIVE_WF = ROOT / "n8n" / "wf_enrichment_local_live.json"


def _load(path):
    return json.loads(path.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _strip_comments(js: str) -> str:
    """Drop lines whose trimmed form starts with `//` — a comment naming a token must not
    satisfy a structural guard that is supposed to prove the CODE does something (mirrors
    tests/test_fetch_by_id_topology.py's helper of the same name)."""
    return "\n".join(line for line in js.split("\n") if not line.strip().startswith("//"))


# --- Build Identity stamps `lane` via laneOf -------------------------------------------

def test_build_identity_stamps_lane_via_laneof():
    doc = _load(CLOUD_WF)
    code = _node(doc, "Build Identity")["parameters"]["jsCode"]
    assert "laneOf(" in code
    assert re.search(r"\blane\s*:", code), "Build Identity must assign a `lane:` field on the row"


# --- Adapt Search filters to its own lane BEFORE index-aligning ------------------------

def test_adapt_search_filters_to_email_lane_before_indexing():
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Adapt Search")["parameters"]["jsCode"])
    assert 'lane === "email"' in code
    # The unfiltered read must be GONE, not merely supplemented — a stray unfiltered
    # `$('Build Identity').all();` (immediately terminated, no `.filter(`) proves the
    # duplication bug is still live even if a filtered read also exists somewhere else.
    assert not re.search(r"\$\('Build Identity'\)\.all\(\)\s*;", code), (
        "Adapt Search must not carry an unfiltered $('Build Identity').all() read"
    )


def test_adapt_fetch_by_id_filters_to_fetch_by_id_lane_before_indexing():
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Adapt Fetch By Id")["parameters"]["jsCode"])
    assert 'lane === "fetch_by_id"' in code
    assert not re.search(r"\$\('Build Identity'\)\.all\(\)\s*;", code), (
        "Adapt Fetch By Id must not carry an unfiltered $('Build Identity').all() read"
    )


# --- the shared ENRICH_ADAPT_SEARCH constant also reaches LOCAL-LIVE -------------------

def test_local_live_adapt_search_carries_the_same_lane_filter():
    doc = _load(LOCAL_LIVE_WF)
    code = _strip_comments(_node(doc, "Adapt Search")["parameters"]["jsCode"])
    assert 'lane === "email"' in code
    assert not re.search(r"\$\('Build Identity'\)\.all\(\)\s*;", code)


# --- Phase 36 Plan 02, Task 2: Adapt Name Search — a proposal, never an auto-match ------

def test_adapt_name_search_exists_and_calls_mediumcandidates_and_summarizematch():
    doc = _load(CLOUD_WF)
    node = _node(doc, "Adapt Name Search")
    assert node["type"] == "n8n-nodes-base.code"
    code = node["parameters"]["jsCode"]
    assert 'lane === "name"' in code
    assert "mediumCandidates" in code
    assert "summarizeMatch" in code


def test_adapt_name_search_never_assigns_a_non_empty_existingrecord_on_the_success_path():
    """The success-path `existingRecord` assignment must be the empty-object literal —
    a MEDIUM candidate is a PROPOSAL (36-CONTEXT.md §6: tier "medium" carries
    `auto: false`), never an auto-matched update target."""
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Adapt Name Search")["parameters"]["jsCode"])
    assignments = re.findall(r"existingRecord:\s*(\{\}|[^,}]+)", code)
    assert assignments, "no existingRecord assignment found at all"
    assert all(a.strip() == "{}" for a in assignments), (
        f"Adapt Name Search must only ever assign the empty-object literal to "
        f"existingRecord, found: {assignments}"
    )


def test_all_three_contact_adapters_stamp_a_match_verdict():
    """Every lane stamps a `match` verdict onto its row, so a tier reaches the response
    for every lane including the unsearchable one (36-CONTEXT.md §7 step 1)."""
    doc = _load(CLOUD_WF)
    for name in ("Adapt Search", "Adapt Fetch By Id", "Adapt Name Search"):
        code = _node(doc, name)["parameters"]["jsCode"]
        assert "summarizeMatch" in code, f"{name} must call summarizeMatch"
