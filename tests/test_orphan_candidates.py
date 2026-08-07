# tests/test_orphan_candidates.py
#
# Phase 42 Plan 03 Task 1 — offline safety tests for scripts/derive_orphan_candidates.py.
# Pure pytest: no network, no credentials, no monkeypatched HTTP. classify_candidate() and
# classify_flow() are pure functions written precisely so this is possible.
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from derive_orphan_candidates import (  # noqa: E402
    DISPOSABLE_PROVENANCE_PATTERNS,
    EXECUTABLE_SURFACE_GLOBS,
    NON_EXECUTABLE_NODE_TYPES,
    archive_property,
    classify_candidate,
    classify_flow,
    _has_disposable_provenance,
    _iter_executable_files,
    _iter_test_files,
    _strip_sticky_notes,
)
from check_schema_drift import (  # noqa: E402
    DO_NOT_ARCHIVE_COMPANY_PROPERTIES,
    DO_NOT_ARCHIVE_FLOW_IDS,
)

EMPTY_REFS = {"executable": [], "test": []}


# --- F4 regression guard: the do-not-archive set must never reach an archivable verdict ---

def test_do_not_archive_properties_classify_protected_even_with_empty_refs():
    """F4 regression guard. The repo's only pre-existing reference detector
    (tests/test_hubspot_schema_coverage.py PROPERTY_RE) uses a `lv_`/`enrichment_`
    namespace-prefix regex that structurally cannot match the five `*_score` component
    names. A detector built by copying that pattern would classify the live scoring engine
    as unreferenced and hand it to the archival path. Proving `protected` fires against an
    EMPTY reference set is the point: protection must never depend on the scan finding
    anything."""
    for name in DO_NOT_ARCHIVE_COMPANY_PROPERTIES:
        assert classify_candidate(name, EMPTY_REFS, formulas=[], declared_names=set()) == "protected", name


def test_do_not_archive_flow_ids_classify_protected_regardless_of_object_type_or_refs():
    for flow_id in DO_NOT_ARCHIVE_FLOW_IDS:
        flow = {"id": flow_id, "objectTypeId": "0-3", "name": "irrelevant", "isEnabled": False}
        assert classify_flow(flow, EMPTY_REFS) == "protected"


# --- formula-substring protection --------------------------------------------------------

def test_formula_substring_classifies_protected():
    """Whether HubSpot rejects archiving a formula-referenced property is untested and
    unknown in this portal, and the fit-score formula blanks entirely rather than treating
    a missing term as zero -- this gate exists so that question never has to be answered
    live. A name whose ONLY occurrence anywhere is inside a supplied `calculationFormula`
    string must still classify protected."""
    result = classify_candidate(
        "a_term", EMPTY_REFS, formulas=["a_term + b_term"], declared_names=set()
    )
    assert result == "protected"


def test_declared_in_yaml_classifies_protected():
    """A property declared in config/hubspot_properties.yaml is by definition not an
    orphan (42-02's expanded manifest is the secondary protection oracle)."""
    result = classify_candidate(
        "some_declared_prop", EMPTY_REFS, formulas=[], declared_names={"some_declared_prop"}
    )
    assert result == "protected"


# --- archival refusal ---------------------------------------------------------------------

def test_archive_property_refuses_protected():
    """Classification and mutation are gated independently on purpose."""
    try:
        archive_property("companies", "org_type_score", "protected")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_archive_property_refuses_referenced():
    try:
        archive_property("companies", "some_prop", "referenced")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_archive_property_refuses_ambiguous():
    try:
        archive_property("companies", "some_prop", "ambiguous")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_archive_property_refuses_a_do_not_archive_name_even_if_mislabeled_uncontested():
    """The independent second gate: even if classification were somehow wrong, the
    do-not-archive name check re-fires immediately before any DELETE call is made."""
    try:
        archive_property("companies", "geography_score", "uncontested_orphan")
        assert False, "expected ValueError"
    except ValueError:
        pass


# --- fail-safe default: ambiguous, never uncontested_orphan, by default -------------------

def test_zero_refs_no_disposable_match_is_ambiguous_not_orphan():
    result = classify_candidate("some_unknown_prop", EMPTY_REFS, formulas=[], declared_names=set())
    assert result == "ambiguous"


def test_disposable_provenance_zero_refs_is_uncontested_orphan():
    result = classify_candidate(
        "lv__phase99_made_up_probe", EMPTY_REFS, formulas=[], declared_names=set()
    )
    assert result == "uncontested_orphan"


def test_trailing_probe_suffix_zero_refs_is_uncontested_orphan():
    result = classify_candidate("some_disposable_probe", EMPTY_REFS, formulas=[], declared_names=set())
    assert result == "uncontested_orphan"


def test_test_only_reference_blocks_uncontested_orphan_classification():
    """A property referenced only by a test assertion has not been shown to do anything
    live, but it is also not safely archivable -- it makes the item ambiguous, never
    uncontested, even when its name otherwise matches a disposable pattern."""
    refs = {"executable": [], "test": ["tests/test_something.py"]}
    result = classify_candidate("lv__phase99_probe", refs, formulas=[], declared_names=set())
    assert result == "ambiguous"


def test_executable_reference_classifies_referenced():
    refs = {"executable": ["scripts/something.py"], "test": []}
    result = classify_candidate("some_prop", refs, formulas=[], declared_names=set())
    assert result == "referenced"


def test_disposable_provenance_patterns_has_at_least_two_entries():
    assert len(DISPOSABLE_PROVENANCE_PATTERNS) >= 2
    assert _has_disposable_provenance("lv__phase21_org_type_probe")
    assert not _has_disposable_provenance("lv_org_type")


# --- flow classification -------------------------------------------------------------------

def test_non_company_flow_classifies_out_of_scope():
    flow = {"id": "999999", "objectTypeId": "0-1", "name": "contact flow", "isEnabled": True}
    assert classify_flow(flow, EMPTY_REFS) == "out_of_scope"


def test_company_flow_with_disposable_name_and_zero_refs_is_uncontested_orphan():
    flow = {"id": "999999", "objectTypeId": "0-2", "name": "ZZ-SCORING-TEST-DELETE-ME-leftover", "isEnabled": True}
    assert classify_flow(flow, EMPTY_REFS) == "uncontested_orphan"


def test_company_flow_with_no_disposable_match_is_ambiguous():
    flow = {"id": "999999", "objectTypeId": "0-2", "name": "some other flow", "isEnabled": True}
    assert classify_flow(flow, EMPTY_REFS) == "ambiguous"


# --- false-positive guard 1: sticky notes are not references ------------------------------

def test_sticky_note_prose_is_stripped_before_scan():
    """The other half of non-vacuity: the exclusion must actually exclude. A note naming a
    property must not survive into the scanned text, or the tool would report documentation
    as a reference -- precisely the trap that would make 39-DECISION.md's superseded
    sentence look like an endorsement of archiving the live engine."""
    doc = {
        "nodes": [
            {
                "id": "note", "name": "Sticky Note", "type": "n8n-nodes-base.stickyNote",
                "parameters": {"content": "org_type_score is never referenced here."},
            },
            {
                "id": "real", "name": "Real Node", "type": "n8n-nodes-base.code",
                "parameters": {"jsCode": "return [];"},
            },
        ]
    }
    stripped = _strip_sticky_notes(doc)
    node_types = {n["type"] for n in stripped["nodes"]}
    assert NON_EXECUTABLE_NODE_TYPES.isdisjoint(node_types)
    assert "org_type_score" not in json.dumps(stripped)


def test_strip_sticky_notes_is_a_noop_for_non_workflow_docs():
    """HubSpot flow JSON uses `actions`, not `nodes` -- confirms the helper does not touch
    (or crash on) a doc shape that never carries a `nodes` list."""
    doc = {"actions": [], "id": "123", "objectTypeId": "0-2"}
    assert _strip_sticky_notes(doc) == doc


# --- false-positive guard 2: .planning/ and markdown are excluded from every surface -------

def test_planning_and_markdown_excluded_from_executable_surfaces():
    for path in _iter_executable_files():
        assert ".planning" not in path.parts, path
        assert path.suffix != ".md", path


def test_planning_and_markdown_excluded_from_test_surfaces():
    for path in _iter_test_files():
        assert ".planning" not in path.parts, path
        assert path.suffix != ".md", path


def test_executable_surface_globs_do_not_target_planning_or_markdown():
    for pattern in EXECUTABLE_SURFACE_GLOBS:
        assert not pattern.startswith(".planning")
        assert not pattern.endswith(".md")


# --- self-reference guard ------------------------------------------------------------------

def test_this_tool_and_its_own_test_file_are_excluded_from_the_scan():
    """The tool's own source and its own test file are never counted as a reference to
    anything -- otherwise every DISPOSABLE_PROVENANCE_PATTERNS regex literal defined here
    would register as a 'reference' to the very names it exists to classify."""
    scanned = {str(p.relative_to(ROOT)) for p in _iter_executable_files()}
    assert "scripts/derive_orphan_candidates.py" not in scanned
    scanned_tests = {str(p.relative_to(ROOT)) for p in _iter_test_files()}
    assert "tests/test_orphan_candidates.py" not in scanned_tests
