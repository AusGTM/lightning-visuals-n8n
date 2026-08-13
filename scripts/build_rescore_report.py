#!/usr/bin/env python3
"""scripts/build_rescore_report.py

Phase 49 Plan 07 (RESCORE-03) -- the three-point report builder and renderer. Consumes only
committed JSON snapshots -- no HubSpot import, no network call, no credentials -- so it is
fully offline-testable and re-runnable. This module imports nothing from src.hubspot_client
and the test suite passes with no environment variables set.

Three points, two free live reads (49-CONTEXT.md D-10):
  P1 -- v0.9 entry, the Phase 46 simulation capture's LIVE column
        (.planning/phases/46-.../46-simulation-20260811.json). This is the only dated
        full-population snapshot predating every write this milestone (v0.9) made: it
        precedes Phase 47's veto clear, Phase 47.5's veto recompute, Phase 48's coverage
        enrichment, and this phase's own weight re-score. Its shape differs from the
        driver's snapshot documents (one row per company with `live_score`/`live_tier`,
        not a `records` list keyed by `lv_icp_tier`) -- load_p1_point() is a dedicated
        adapter for that shape rather than a reshaping of the committed file itself.
  P2 -- pre-re-score, a fresh live read via scripts/rescore_population.py --snapshot,
        taken BEFORE W1 opened (49-P2-SNAPSHOT.json). Captures what Phase 47 + 47.5 + 48
        already did.
  P3 -- post-re-score, the same --snapshot shape, taken AFTER W1 settled
        (49-P3-SNAPSHOT.json). Captures the weight change on the full population.

load_point() reads the P2/P3 --snapshot document shape directly. build_report(p1, p2, p3)
validates each point (a distribution that does not sum to its population count, or a
zero-population point, raises rather than rendering) and builds two movement tables
(P1->P2, P2->P3) plus a separate score-only section per pair -- a record only ever
appears in a movement table when its tier differs between the two points being compared;
a record whose score moved while its tier held is reported in the score-only section
instead, never as a tier movement (this is what keeps a genuinely-vetoed record's score
move under the new weights from being misread as a tier change). Every score/delta value
is coerced through int(); a value that will not coerce raises rather than silently
falling back to a float or a zero. render_markdown(report) is a pure function of its
payload -- called twice on the same payload it returns byte-identical strings.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path, matches sibling scripts in this repo

# Fixed, canonical tier-key order (matches simulate_rubric_weights.py's _dist_row order) so
# two renders of the same data cannot differ in column order. Any tier key not in this list
# (there are none known today) is appended afterwards, sorted, so an unexpected future tier
# name still renders deterministically rather than silently disappearing.
TIER_ORDER = ["A", "B", "C", "D", "Unscored", "Needs Review"]


def _coerce_int(value, context: str) -> int:
    """Coerce a HubSpot-string (or already-int) score to int. Raises loudly, naming what
    failed, rather than falling back to a float or a zero -- scores arrive from HubSpot as
    strings and a value that will not coerce is a data problem, not a formatting one."""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{context}: value {value!r} will not coerce to an integer score"
        ) from exc


def _ordered_tier_items(dist: dict):
    """Canonical tiers first (0 if absent), then any residual key sorted -- so two renders
    of the same distribution dict can never differ in column order."""
    items = [(t, dist.get(t, 0)) for t in TIER_ORDER]
    residual = sorted(k for k in dist if k not in TIER_ORDER)
    items += [(t, dist[t]) for t in residual]
    return items


def load_point(path, label: str) -> dict:
    """Reads a scripts/rescore_population.py --snapshot document (P2/P3's shape) and
    normalises it to the common point shape: label, derived_at, population_count,
    tier_distribution, and records keyed by record id."""
    doc = json.loads(Path(path).read_text())
    records = {}
    for row in doc["records"]:
        rid = row["id"]
        records[rid] = {
            "id": rid,
            "name": row.get("name"),
            "tier": row.get("lv_icp_tier"),
            "score": _coerce_int(
                row.get("lv_icp_fit_score"), f"point '{label}' record {rid} lv_icp_fit_score"
            ),
        }
    return {
        "label": label,
        "derived_at": doc["derived_at"],
        "population_count": doc["population_count"],
        "tier_distribution": doc["tier_distribution"],
        "records": records,
    }


def load_p1_point(path, label: str = "P1") -> dict:
    """Adapter for the Phase 46 simulation capture's shape (see module docstring for why
    this file is P1's source). Its rows carry `company_id`/`live_score`/`live_tier`
    instead of `id`/`lv_icp_fit_score`/`lv_icp_tier`, and it has no top-level
    `population_count`/`tier_distribution` -- both are derived here from its rows rather
    than reshaping the committed file to match the driver's snapshot shape."""
    doc = json.loads(Path(path).read_text())
    rows = doc["rows"]
    records = {}
    dist = Counter()
    for row in rows:
        rid = row["company_id"]
        tier = str(row["live_tier"])
        score = _coerce_int(row.get("live_score"), f"point '{label}' record {rid} live_score")
        records[rid] = {"id": rid, "name": row.get("name"), "tier": tier, "score": score}
        dist[tier] += 1
    return {
        "label": label,
        "derived_at": doc["run_metadata"]["checked_at_utc"],
        "population_count": len(rows),
        "tier_distribution": dict(dist),
        "records": records,
    }


def _validate_point(point: dict) -> None:
    label = point["label"]
    pop = point["population_count"]
    if pop <= 0:
        raise ValueError(f"point '{label}': population_count is {pop}; refusing to render an empty report")
    total = sum(point["tier_distribution"].values())
    if total != pop:
        raise ValueError(
            f"point '{label}': tier_distribution sums to {total}, expected population_count {pop}"
        )


def _id_sort_key(rid: str):
    """Sort numerically when the id is a HubSpot-style all-digit string (real data),
    falling back to the string itself otherwise -- keeps sorting deterministic for
    every record id shape, real or fixture."""
    return (0, int(rid)) if rid.isdigit() else (1, rid)


def _diff_points(from_point: dict, to_point: dict):
    """One record only ever lands in ONE of the two returned lists: a tier movement, or a
    score-only change. A record whose score is unchanged and whose tier is unchanged
    appears in neither. Sorted by record id (numeric) so re-rendering the same inputs is
    deterministic."""
    common_ids = sorted(set(from_point["records"]) & set(to_point["records"]), key=_id_sort_key)
    movements = []
    score_only = []
    for rid in common_ids:
        before = from_point["records"][rid]
        after = to_point["records"][rid]
        delta = after["score"] - before["score"]
        entry = {
            "id": rid,
            "name": after["name"] or before["name"],
            "from_tier": before["tier"],
            "to_tier": after["tier"],
            "from_score": before["score"],
            "to_score": after["score"],
            "delta": delta,
        }
        if before["tier"] != after["tier"]:
            movements.append(entry)
        elif delta != 0:
            score_only.append(entry)
    return movements, score_only


def build_report(p1: dict, p2: dict, p3: dict) -> dict:
    """Validates all three points, then builds two movement tables (P1->P2, P2->P3) and a
    matching pair of score-only sections. Raises on the first invalid point rather than
    partially rendering."""
    for point in (p1, p2, p3):
        _validate_point(point)

    p1_to_p2_movements, p1_to_p2_score_only = _diff_points(p1, p2)
    p2_to_p3_movements, p2_to_p3_score_only = _diff_points(p2, p3)

    return {
        "points": {"p1": p1, "p2": p2, "p3": p3},
        "tier_distribution": {
            "p1": _ordered_tier_items(p1["tier_distribution"]),
            "p2": _ordered_tier_items(p2["tier_distribution"]),
            "p3": _ordered_tier_items(p3["tier_distribution"]),
        },
        "movements": {
            "p1_to_p2": p1_to_p2_movements,
            "p2_to_p3": p2_to_p3_movements,
        },
        "score_only": {
            "p1_to_p2": p1_to_p2_score_only,
            "p2_to_p3": p2_to_p3_score_only,
        },
    }


def _movement_table(rows, from_label: str, to_label: str) -> list:
    lines = [
        f"| Name | HubSpot ID | {from_label} Tier | {to_label} Tier | {from_label} Score | {to_label} Score | Delta |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        name = row["name"] or "(name unavailable)"
        lines.append(
            f"| {name} | {row['id']} | {row['from_tier']} | {row['to_tier']} | "
            f"{row['from_score']} | {row['to_score']} | {row['delta']:+d} |"
        )
    return lines


def render_markdown(report: dict) -> str:
    """Pure function of `report` -- called twice on the same payload it returns
    byte-identical strings. Extends the three-column shape
    scripts/simulate_rubric_weights.py::render_markdown established, from three in-memory
    configs to three live time points."""
    p1, p2, p3 = report["points"]["p1"], report["points"]["p2"], report["points"]["p3"]
    dist = report["tier_distribution"]
    movements = report["movements"]
    score_only = report["score_only"]

    lines = []
    lines.append("# Phase 49 Re-score Report -- Three-Point Tier Distribution")
    lines.append("")
    for label, point in (("P1", p1), ("P2", p2), ("P3", p3)):
        lines.append(
            f"- **{label} ({point['label']}):** derived {point['derived_at']}, "
            f"population {point['population_count']}"
        )
    lines.append("")

    lines.append("## Tier Distribution")
    lines.append("")
    header = " | ".join(t for t, _ in dist["p1"])
    lines.append(f"| Point | {header} |")
    lines.append("|---" * (len(dist["p1"]) + 1) + "|")
    for label, key in (("P1", "p1"), ("P2", "p2"), ("P3", "p3")):
        cells = " | ".join(str(count) for _, count in dist[key])
        lines.append(f"| {label} | {cells} |")
    lines.append("")

    lines.append("## Tier Movements: P1 -> P2")
    lines.append("")
    if movements["p1_to_p2"]:
        lines.extend(_movement_table(movements["p1_to_p2"], "P1", "P2"))
    else:
        lines.append("No tier movements between P1 and P2.")
    lines.append("")

    lines.append("## Tier Movements: P2 -> P3")
    lines.append("")
    if movements["p2_to_p3"]:
        lines.extend(_movement_table(movements["p2_to_p3"], "P2", "P3"))
    else:
        lines.append("No tier movements between P2 and P3.")
    lines.append("")

    lines.append("## Score-Only Changes (tier held, score moved): P1 -> P2")
    lines.append("")
    if score_only["p1_to_p2"]:
        lines.extend(_movement_table(score_only["p1_to_p2"], "P1", "P2"))
    else:
        lines.append("No score-only changes between P1 and P2.")
    lines.append("")

    lines.append("## Score-Only Changes (tier held, score moved): P2 -> P3")
    lines.append("")
    if score_only["p2_to_p3"]:
        lines.extend(_movement_table(score_only["p2_to_p3"], "P2", "P3"))
    else:
        lines.append("No score-only changes between P2 and P3.")
    lines.append("")

    return "\n".join(lines)


def main(argv=None):
    """Thin CLI: load the three committed points and print the rendered markdown to
    stdout (or --out a file). No HubSpot read, no write, no credentials required."""
    parser = argparse.ArgumentParser(description=__doc__)
    default_dir = ROOT / ".planning/phases/49-re-score-strategy-reporting"
    parser.add_argument(
        "--p1",
        default=str(
            ROOT
            / ".planning/phases/46-rubric-decision-simulation-engine-parity/46-simulation-20260811.json"
        ),
    )
    parser.add_argument("--p2", default=str(default_dir / "49-P2-SNAPSHOT.json"))
    parser.add_argument("--p3", default=str(default_dir / "49-P3-SNAPSHOT.json"))
    parser.add_argument("--out", default=None, help="Path to write markdown to. Defaults to stdout.")
    args = parser.parse_args(argv)

    p1 = load_p1_point(args.p1, label="P1")
    p2 = load_point(args.p2, label="P2")
    p3 = load_point(args.p3, label="P3")
    report = build_report(p1, p2, p3)
    text = render_markdown(report)

    if args.out:
        Path(args.out).write_text(text)
        print(f"written to {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
