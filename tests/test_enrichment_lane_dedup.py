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


# --- Phase 36 Plan 02, Task 3: Enrichment Gate — never burn 3 provider calls on an -----
# --- unmatchable row --------------------------------------------------------------------

def test_enrichment_gate_skips_a_row_with_no_email_no_linkedin_and_no_name_plus_company():
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Enrichment Gate")["parameters"]["jsCode"])
    assert "linkedin_url" in code and "lastName" in code and "companyName" in code, (
        "Enrichment Gate must guard on all three identity keys (email is already read "
        "via REQUIRED/decideAction — the new guard names the other two plus the "
        "email/linkedin/name+company skip predicate)"
    )
    assert re.search(r'action\s*=\s*"skip"', code), (
        "Enrichment Gate's new guard must assign the skip action"
    )


def test_company_gate_does_not_carry_the_same_guard():
    """36-CONTEXT.md §7 step 8 is contacts-only — the companies gate deliberately gets
    NO equivalent rule."""
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Company Gate")["parameters"]["jsCode"])
    assert "lastName" not in code


# --- Phase 36-03, Task 3: refuse an oversize or empty events array whole (D-15/D-22) ----

def test_parse_hubspot_event_refuses_oversize_events_array_whole():
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Parse HubSpot Event")["parameters"]["jsCode"])
    assert re.search(r'outcome:\s*"refused"', code), (
        "Parse HubSpot Event must emit a refused terminating item, never a thrown "
        "exception or a silent partial map"
    )
    assert re.search(r"events\.length\s*>\s*MAX_EVENTS", code), (
        "the ceiling comparison must be strictly greater-than — exactly-at-the-limit "
        "must be accepted, never refused"
    )
    assert not re.search(r"events\.length\s*>=\s*MAX_EVENTS", code), (
        "must never regress to a >= comparison, which would refuse the exactly-at-limit "
        "case PREVIEW-03 requires to be accepted"
    )


def test_parse_hubspot_event_refuses_empty_events_array_too():
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Parse HubSpot Event")["parameters"]["jsCode"])
    assert re.search(r"events\.length\s*===\s*0", code), (
        "an empty events array must be refused with its own reason rather than emitting "
        "zero items into a responseNode webhook (the D-22 Cloudflare 524 hang)"
    )


def test_parse_hubspot_event_ceiling_literals_match_the_two_builder_declarations():
    """Phase 36-06 (37-CONTEXT.md §13 operator ruling) deliberately made this test's
    original premise false: a single ceiling literal named MAX_EVENTS no longer exists.
    The write ceiling's B4 derivation (37.44 s/record full waterfall) does not apply to a
    return-only request, which runs zero provider calls — so the ceiling was split in two.
    This amendment (not a delete, not a silent reword) proves neither literal can drift
    from its single Python declaration, and that the write path specifically did NOT
    widen alongside the new propose path."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import build_cloud_workflows as builder  # noqa: E402

    doc = _load(CLOUD_WF)
    code = _node(doc, "Parse HubSpot Event")["parameters"]["jsCode"]
    assert f"const MAX_WRITE_EVENTS = {builder.ENRICH_MAX_LIST_RECORDS};" in code
    assert f"const MAX_PROPOSE_EVENTS = {builder.ENRICH_MAX_PROPOSE_RECORDS};" in code
    assert builder.ENRICH_MAX_LIST_RECORDS == 2, (
        "the write ceiling must not have widened alongside the new propose ceiling"
    )


def test_parse_hubspot_event_selects_ceiling_by_mode_before_the_size_comparison():
    """The selection must be genuinely mode-driven and must sit before the
    `events.length >` comparison — mirrors 36-04's source-order proof idiom for the
    write guard."""
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Parse HubSpot Event")["parameters"]["jsCode"])
    selection_idx = code.index("isReturnOnly(parsed.mode)")
    comparison_idx = code.index("parsed.events.length >")
    assert selection_idx < comparison_idx, (
        "the mode-driven ceiling selection must appear before the size comparison, "
        "or parsed.mode would not exist yet / the comparison would already be moot"
    )


def test_parse_hubspot_event_declares_exactly_one_return_only_predicate():
    """Exactly ONE isReturnOnly() exists in the node — a hand-rolled second copy is a
    second thing that can drift, and drift here means a typo'd mode writes to HubSpot
    (D-15's fail-safe asymmetry)."""
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Parse HubSpot Event")["parameters"]["jsCode"])
    assert code.count("function isReturnOnly(") == 1
    assert code.count('!== "write"') == 1, (
        "the write-literal comparison that forms isReturnOnly()'s body must occur "
        "exactly once — a second occurrence means a hand-rolled second predicate"
    )


def test_refusal_reaches_build_response_via_the_existing_unsupported_object_type_edge():
    """No new nodes or edges: object_type:"unknown" on the refusal item routes it through
    the pre-existing "IF Object Type Supported" false lane, exactly like a genuine
    unsupported object type does."""
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Parse HubSpot Event")["parameters"]["jsCode"])
    assert code.count('object_type: "unknown"') == 2, (
        "both refusal branches (oversize and empty) must route through the existing "
        "unsupported-object-type false lane"
    )
    conns = doc["connections"]
    assert conns["IF Object Type Supported"]["main"][1][0]["node"] == "Unsupported Object Type"
    assert conns["Unsupported Object Type"]["main"][0][0]["node"] == "Build Response"


# --- Quick task 260904-5a8: Decide Company Action carries the "company" call-site literal ---

def test_decide_company_action_carries_the_company_lane_literal():
    """`Decide Company Action` must call summarizeMatch with the "company" call-site
    literal, never `row.lane` — this branch stamps no `lane` on any row (C1 in
    260904-5a8-PLAN.md's premise_corrections), so `row.lane` would always resolve
    `undefined` and misreport contacts vocabulary about a company row."""
    doc = _load(CLOUD_WF)
    code = _strip_comments(_node(doc, "Decide Company Action")["parameters"]["jsCode"])
    assert 'summarizeMatch({ lane: "company" })' in code
    assert "summarizeMatch({ lane: row.lane })" not in code
