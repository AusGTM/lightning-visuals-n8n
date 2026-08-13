# tests/test_build_rescore_report.py
#
# Phase 49 Plan 07 (RESCORE-03). Every case below drives build_report()/render_markdown()
# against small inline fixtures -- no committed snapshot file, no network, no credentials,
# no environment variable. The module under test imports nothing from src.hubspot_client;
# that is asserted directly below rather than only implied by the absence of an import
# error.
import inspect

import scripts.build_rescore_report as build_rescore_report
from scripts.build_rescore_report import build_report, load_p1_point, load_point, render_markdown


def _point(label, population_count, tier_distribution, records):
    """records: dict of id -> (name, tier, score)."""
    return {
        "label": label,
        "derived_at": f"2026-08-1{ord(label[-1]) % 3 + 1}T00:00:00Z",
        "population_count": population_count,
        "tier_distribution": tier_distribution,
        "records": {
            rid: {"id": rid, "name": name, "tier": tier, "score": score}
            for rid, (name, tier, score) in records.items()
        },
    }


# --- Validation: sum-vs-population and zero-population guards ---

def test_distribution_not_summing_to_population_raises_naming_the_point():
    p1 = _point("P1", 2, {"A": 1, "B": 1}, {"1": ("Alpha", "A", 10), "2": ("Beta", "B", 20)})
    p2 = _point("P2", 2, {"A": 1, "B": 0}, {"1": ("Alpha", "A", 10), "2": ("Beta", "B", 20)})  # sums to 1, not 2
    p3 = _point("P3", 2, {"A": 1, "B": 1}, {"1": ("Alpha", "A", 10), "2": ("Beta", "B", 20)})

    try:
        build_report(p1, p2, p3)
        raise AssertionError("expected build_report to raise on a non-summing distribution")
    except ValueError as exc:
        assert "P2" in str(exc)


def test_zero_population_point_raises():
    p1 = _point("P1", 0, {}, {})
    p2 = _point("P2", 1, {"A": 1}, {"1": ("Alpha", "A", 10)})
    p3 = _point("P3", 1, {"A": 1}, {"1": ("Alpha", "A", 10)})

    try:
        build_report(p1, p2, p3)
        raise AssertionError("expected build_report to raise on a zero-population point")
    except ValueError as exc:
        assert "P1" in str(exc)


# --- Movement table: only records whose tier differs ---

def test_movement_table_contains_only_the_moved_record():
    p1 = _point(
        "P1", 2, {"A": 1, "C": 1},
        {"A1": ("Record A", "C", 35), "B1": ("Record B", "A", 80)},
    )
    p2 = _point(
        "P2", 2, {"A": 1, "B": 1},
        {"A1": ("Record A", "B", 45), "B1": ("Record B", "A", 80)},
    )
    p3 = p2  # no further movement for this test

    report = build_report(p1, p2, p3)
    moved_ids = {row["id"] for row in report["movements"]["p1_to_p2"]}
    assert moved_ids == {"A1"}
    assert "B1" not in moved_ids


def test_score_only_change_never_appears_in_a_movement_table():
    p1 = _point("P1", 1, {"D": 1}, {"C1": ("Record C", "D", -70)})
    p2 = _point("P2", 1, {"D": 1}, {"C1": ("Record C", "D", -50)})  # score moved, tier held
    p3 = p2

    report = build_report(p1, p2, p3)
    assert report["movements"]["p1_to_p2"] == []
    score_only_ids = {row["id"] for row in report["score_only"]["p1_to_p2"]}
    assert score_only_ids == {"C1"}


def test_unchanged_score_and_tier_appears_in_neither_table():
    p1 = _point("P1", 1, {"B": 1}, {"X1": ("Record X", "B", 45)})
    p2 = _point("P2", 1, {"B": 1}, {"X1": ("Record X", "B", 45)})
    p3 = p2

    report = build_report(p1, p2, p3)
    assert report["movements"]["p1_to_p2"] == []
    assert report["score_only"]["p1_to_p2"] == []


# --- Integer deltas ---

def test_every_delta_is_an_int():
    p1 = _point(
        "P1", 2, {"C": 1, "D": 1},
        {"A1": ("Record A", "C", 35), "C1": ("Record C", "D", -70)},
    )
    p2 = _point(
        "P2", 2, {"B": 1, "D": 1},
        {"A1": ("Record A", "B", 45), "C1": ("Record C", "D", -50)},
    )
    p3 = p2

    report = build_report(p1, p2, p3)
    all_rows = report["movements"]["p1_to_p2"] + report["score_only"]["p1_to_p2"]
    assert all_rows, "fixture must produce at least one row to be a meaningful assertion"
    for row in all_rows:
        assert isinstance(row["delta"], int)
        assert isinstance(row["from_score"], int)
        assert isinstance(row["to_score"], int)


def test_non_coercible_score_raises_rather_than_defaulting_to_zero():
    # Exercise the same coercion path load_point uses, via a snapshot doc containing a
    # score string that will not coerce to int.
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.json"
        path.write_text(
            json.dumps(
                {
                    "derived_at": "2026-08-13T00:00:00Z",
                    "population_count": 1,
                    "tier_distribution": {"A": 1},
                    "records": [
                        {"id": "1", "name": "Bad", "lv_icp_tier": "A", "lv_icp_fit_score": "not-a-number"}
                    ],
                }
            )
        )
        try:
            load_point(str(path), label="Pbad")
            raise AssertionError("expected load_point to raise on a non-coercible score")
        except ValueError as exc:
            assert "Pbad" in str(exc)


# --- render_markdown: deterministic, byte-identical double render ---

def test_render_markdown_is_byte_identical_across_two_calls():
    p1 = _point("P1", 1, {"C": 1}, {"A1": ("Record A", "C", 35)})
    p2 = _point("P2", 1, {"B": 1}, {"A1": ("Record A", "B", 45)})
    p3 = _point("P3", 1, {"B": 1}, {"A1": ("Record A", "B", 45)})

    report = build_report(p1, p2, p3)
    first = render_markdown(report)
    second = render_markdown(report)
    assert first == second


def test_render_markdown_shows_tiers_in_canonical_order():
    p1 = _point("P1", 4, {"D": 1, "A": 1, "C": 1, "B": 1}, {
        "1": ("R1", "A", 80), "2": ("R2", "B", 55), "3": ("R3", "C", 35), "4": ("R4", "D", 10),
    })
    p2 = p1
    p3 = p1

    report = build_report(p1, p2, p3)
    text = render_markdown(report)
    header_line = next(line for line in text.splitlines() if line.startswith("| Point |"))
    assert header_line.index("A") < header_line.index("B") < header_line.index("C") < header_line.index("D")


# --- load_p1_point: the Phase 46 simulation-capture adapter ---

def test_load_p1_point_adapts_the_simulation_capture_shape():
    import json
    import tempfile
    from pathlib import Path

    doc = {
        "run_metadata": {"checked_at_utc": "2026-08-11T07:59:01Z"},
        "rows": [
            {"company_id": "1", "name": "Alpha", "live_score": "35", "live_tier": "C"},
            {"company_id": "2", "name": "Beta", "live_score": "80", "live_tier": "A"},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p1.json"
        path.write_text(json.dumps(doc))
        point = load_p1_point(str(path), label="P1")

    assert point["population_count"] == 2
    assert point["tier_distribution"] == {"C": 1, "A": 1}
    assert point["records"]["1"]["score"] == 35
    assert isinstance(point["records"]["1"]["score"], int)


# --- Zero-write / zero-import guard ---

def test_module_imports_nothing_from_src_hubspot_client():
    """AST-based, not a source-text grep: the docstring legitimately discusses
    src.hubspot_client (explaining why this module never touches it), so only actual
    import statements are checked."""
    import ast

    tree = ast.parse(inspect.getsource(build_rescore_report))
    imported_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.append(node.module)
    assert not any("hubspot_client" in name for name in imported_names)
