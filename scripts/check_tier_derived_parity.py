#!/usr/bin/env python3
"""scripts/check_tier_derived_parity.py

Phase 50 Plan 01 (D-07's gate, D-17 item 4's evidence renderer) -- read-only comparator
between the old `lv_icp_tier` enum and the new `lv_icp_tier_derived` calculated property.
Never issues a write of any kind (no `requests.{post,patch,delete}` call anywhere in this
module) -- this is D-16's zero-company-write-window guarantee for the whole comparison
half of the phase.

Phase 50 Plan 03 (this task's own additions, D-17 item 4 / D-19): the default mode now
wraps the parity table in `render_evidence_markdown()` -- a "denominator" line stating
what fraction of the portal the scored population represents, an explicit cross-reference
of the 4 known stuck records to their WINDOWS.md ids (9-12), and a "what this does not
say" limits block, matching 49-RESCORE-REPORT.md's conventions. A new `--census` mode
renders D-19's operator-facing before/after tier census (lv_icp_tier vs
lv_icp_tier_derived) into the SAME artifact, reusing scripts/build_rescore_report.py's
own point-validation/diff/movement-table machinery rather than writing a second one --
appending to `--out` if it already exists (the default run's own output), so one file
carries both the D-07 verdict and the D-19 census.

Re-derives the scored population live on every invocation via
scripts/rescore_population.py::select_scored_population() (the same
`HAS_PROPERTY(lv_icp_fit_score)` search shape run_scoring_parity.py /
simulate_rubric_weights.py already share) -- never trusts a stale local snapshot. `--ids`
restricts the run to named records (the tracer task's own use).

The 4 known stuck records (WINDOWS.md ids 9-12) are the ONE class of expected mismatch:
`lv_icp_tier` stuck at "C" while `lv_icp_tier_derived` correctly reads "B". Any other
divergence is a defect, not a rounding difference.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['check_tier_derived_parity.py', '--out', 'PATH/TO/report.md']; \
         runpy.run_path('scripts/check_tier_derived_parity.py', run_name='__main__')"

Usage:
    python scripts/check_tier_derived_parity.py [--ids ID1,ID2,...] [--out PATH]
    python scripts/check_tier_derived_parity.py --census [--out PATH]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

NULL_PROBE_PATH = ROOT / ".planning" / "phases" / "50-derived-tier-property" / "50-NULL-PROBE.json"

# WINDOWS.md ids 9-12 -- the 4 stuck records, hard-coded per the plan (RESEARCH.md Code
# Examples): score already correct at 45, tier stuck at "C" instead of "B".
KNOWN_STUCK_IDS = frozenset({
    "9605273630", "9604738976", "17696004613", "19100977027",
})

# Cross-reference from record id to its WINDOWS.md ledger id -- so the evidence artifact
# can name the exact ledger entry each expected-mismatch row corresponds to, not just say
# "known exceptions" generically (D-07's gate must encode the 4 by id, not by phrase).
KNOWN_STUCK_WINDOWS_IDS = {
    "9605273630": 9,
    "9604738976": 10,
    "17696004613": 11,
    "19100977027": 12,
}

# A blank/None tier is counted under this literal key rather than dropped -- matches
# scripts/rescore_population.py's own BLANK_TIER_KEY convention. Not expected to appear in
# the scored population's "before" (lv_icp_tier) distribution (every scored company has
# been graded by WF1 at least once), but a blank must never silently vanish if it does.
BLANK_TIER_KEY = "Unscored-or-blank"

FETCH_PROPS = [
    "name", "lv_icp_tier", "lv_icp_tier_derived", "lv_icp_fit_score", "lv_anti_icp_flag",
    "lv_anti_icp_flag_num",
]


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id_sort_key(rid: str):
    # Same numeric-first sort as scripts/build_rescore_report.py::_id_sort_key -- keeps
    # rendering deterministic for real HubSpot ids and any non-digit fixture id alike.
    return (0, int(rid)) if rid.isdigit() else (1, rid)


# --- pure functions pinned by tests/test_tier_derived_tools.py -------------------------

def classify_row(record_id, live_tier, derived_tier, known_stuck_ids) -> str:
    """"expected_mismatch" only for a known stuck id whose live tier is "C" and derived
    tier is "B" -- the one class D-07's gate accepts. A known stuck id landing anywhere
    else (including a live-tier match) is a "defect": the fix the phase exists to prove
    did not happen. Any other id: "match" when the two tiers agree, "defect" otherwise."""
    if record_id in known_stuck_ids:
        if live_tier == "C" and derived_tier == "B":
            return "expected_mismatch"
        return "defect"
    return "match" if live_tier == derived_tier else "defect"


def render_parity_markdown(rows, population_count) -> str:
    """Pure function of (rows, population_count) -- called twice on the same inputs
    returns byte-identical strings. Raises on an empty population (never renders "zero
    mismatches" as a clean pass for nothing) and raises when the row count and the
    recorded population count disagree."""
    if population_count <= 0:
        raise ValueError(
            f"population_count is {population_count}; refusing to render an empty parity "
            "report as a clean pass"
        )
    if len(rows) != population_count:
        raise ValueError(
            f"row count ({len(rows)}) does not match the recorded population_count "
            f"({population_count})"
        )

    ordered = sorted(rows, key=lambda r: _id_sort_key(r["record_id"]))
    match = sum(1 for r in ordered if r["classification"] == "match")
    expected_mismatch = sum(1 for r in ordered if r["classification"] == "expected_mismatch")
    defect = sum(1 for r in ordered if r["classification"] == "defect")

    lines = [
        "# lv_icp_tier vs lv_icp_tier_derived -- Parity Report",
        "",
        f"- population: {population_count}",
        f"- match: {match}",
        f"- expected_mismatch: {expected_mismatch}",
        f"- defect: {defect}",
        "",
        "| Record ID | Name | lv_icp_tier | lv_icp_tier_derived | Fit Score | Anti-ICP Flag | Classification |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ordered:
        lines.append(
            f"| {r['record_id']} | {r.get('name') or '(name unavailable)'} | "
            f"{r['live_tier']} | {r['derived_tier']} | {r.get('fit_score')} | "
            f"{r.get('anti_icp_flag')} | {r['classification']} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_rows(records, known_stuck_ids=KNOWN_STUCK_IDS) -> list:
    rows = []
    for r in records:
        rid = r["id"]
        live_tier = r.get("lv_icp_tier")
        derived = r.get("lv_icp_tier_derived")
        rows.append({
            "record_id": rid,
            "name": r.get("name"),
            "live_tier": live_tier,
            "derived_tier": derived,
            "fit_score": r.get("lv_icp_fit_score"),
            "anti_icp_flag": r.get("lv_anti_icp_flag"),
            "anti_icp_flag_num": r.get("lv_anti_icp_flag_num"),
            "classification": classify_row(rid, live_tier, derived, known_stuck_ids),
        })
    return rows


# --- Phase 50 Plan 06 (D-20): population-level mirror-agreement check -------------------

def mirror_disagrees(flag, num) -> bool:
    """True only when lv_anti_icp_flag's "set-ness" (flag == "true", exactly) differs from
    lv_anti_icp_flag_num's "set-ness" (parses to 1 -- None/"" guarded BEFORE any numeric
    coercion, never crash on a blank mirror). Flag false-or-unset with a null mirror is
    the normal, un-backfilled state for most of the population and is NOT a divergence;
    flag true with a null/non-1 mirror IS the dangerous state this check exists to catch,
    and a mirror of 1 on a false/unset flag is equally a divergence (the two must always
    describe the same veto)."""
    flag_is_true = flag == "true"
    num_is_one = False
    if num is not None and str(num) != "":
        try:
            num_is_one = int(float(num)) == 1
        except (TypeError, ValueError):
            num_is_one = False
    return flag_is_true != num_is_one


def render_mirror_section(rows) -> str:
    """Lists every row where mirror_disagrees() is True. Pure function of rows -- called
    twice on the same input returns byte-identical strings. Issues no HubSpot call of any
    kind (this script's own D-16 zero-write guarantee stays load-bearing)."""
    divergent = [
        r for r in rows
        if mirror_disagrees(r.get("anti_icp_flag"), r.get("anti_icp_flag_num"))
    ]

    lines = [
        "## Numeric Mirror Agreement -- lv_anti_icp_flag vs lv_anti_icp_flag_num (D-20)",
        "",
    ]
    if not divergent:
        lines.append(
            "**No divergence found.** Every live record's `lv_anti_icp_flag` and its "
            "numeric mirror `lv_anti_icp_flag_num` agree. A `false`/unset flag paired "
            "with a null mirror is the normal, un-backfilled state (most of the "
            "population has never had the mirror written) and is correctly NOT reported "
            "as a divergence."
        )
    else:
        lines.append(
            f"**DEFECT: {len(divergent)} record(s) where `lv_anti_icp_flag` and "
            "`lv_anti_icp_flag_num` disagree.** A `true` flag with a null/non-1 mirror "
            "means the record's veto is invisible to `lv_icp_tier_derived`'s formula; a "
            "`1` mirror on a `false`/unset flag means a mirror was written for a record "
            "that should not carry it."
        )
        lines.append("")
        lines.append("| Record ID | Name | lv_anti_icp_flag | lv_anti_icp_flag_num |")
        lines.append("|---|---|---|---|")
        for r in sorted(divergent, key=lambda r: _id_sort_key(r["record_id"])):
            lines.append(
                f"| {r['record_id']} | {r.get('name') or '(name unavailable)'} | "
                f"{r.get('anti_icp_flag')} | {r.get('anti_icp_flag_num')} |"
            )
    return "\n".join(lines) + "\n"


# --- Task 2 (D-17 item 4): the evidence-artifact wrapper around render_parity_markdown ---

def render_evidence_markdown(rows, population_count, total_companies, checked_at) -> str:
    """Wraps render_parity_markdown's table with the "denominator" framing, an explicit
    WINDOWS.md cross-reference for the 4 known stuck records, an explicit pass/fail
    verdict naming any defect rows, and a "what this does not say" limits block --
    matching 49-RESCORE-REPORT.md's conventions (D-17 item 4). Does not alter
    render_parity_markdown's own pinned output; Plan 01's tests exercise that function
    unchanged. Pure function of its arguments -- called twice on the same inputs returns
    byte-identical strings, same guarantee render_parity_markdown itself carries."""
    if total_companies:
        pct = round(100 * population_count / total_companies, 1)
        denominator = (
            f"**Only {population_count} of {total_companies} companies in the portal "
            f"carry a score ({pct}% of the portal).** Every row below describes that "
            f"{population_count}-company fraction -- re-derived live at {checked_at} via "
            "`HAS_PROPERTY(lv_icp_fit_score)`, never a stale snapshot."
        )
    else:
        denominator = (
            f"Population: {population_count} companies, re-derived live at {checked_at} "
            "via `HAS_PROPERTY(lv_icp_fit_score)` -- never a stale snapshot."
        )

    table = render_parity_markdown(rows, population_count)

    stuck_present = sorted(
        (r for r in rows if r["record_id"] in KNOWN_STUCK_WINDOWS_IDS),
        key=lambda r: _id_sort_key(r["record_id"]),
    )
    cross_ref_lines = [
        "## Known stuck records -- WINDOWS.md cross-reference (D-07)",
        "",
        "Each is verified by read-back and by nothing else -- no PATCH, no event, no "
        "enrolment, no workflow run (D-10). D-16 declares zero company write windows for "
        "this phase; any company write appearing anywhere in this artifact's own "
        "derivation would be a disclosed deviation requiring justification, not a "
        "budgeted allowance.",
        "",
        "| Record ID | Name | WINDOWS.md id | lv_icp_tier | lv_icp_tier_derived | Classification |",
        "|---|---|---|---|---|---|",
    ]
    for r in stuck_present:
        cross_ref_lines.append(
            f"| {r['record_id']} | {r.get('name') or '(name unavailable)'} | "
            f"{KNOWN_STUCK_WINDOWS_IDS[r['record_id']]} | {r['live_tier']} | "
            f"{r['derived_tier']} | {r['classification']} |"
        )
    if len(stuck_present) < len(KNOWN_STUCK_WINDOWS_IDS):
        missing = sorted(set(KNOWN_STUCK_WINDOWS_IDS) - {r["record_id"] for r in stuck_present})
        cross_ref_lines.append("")
        cross_ref_lines.append(
            f"**DEFECT: {len(missing)} known stuck record(s) not present in this run's "
            f"population: {missing}.** D-07's gate cannot be evaluated as passing when a "
            "known stuck record has dropped out of the live scored population."
        )
    cross_ref = "\n".join(cross_ref_lines)

    defects = [r for r in rows if r["classification"] == "defect"]
    if defects and len(stuck_present) == len(KNOWN_STUCK_WINDOWS_IDS):
        offenders = ", ".join(
            f"{r['record_id']} ({r.get('name') or 'name unavailable'})"
            for r in sorted(defects, key=lambda r: _id_sort_key(r["record_id"]))
        )
        verdict = (
            f"## D-07 VERDICT: FAIL -- {len(defects)} defect row(s): {offenders}. "
            "A mismatch outside the 4 known stuck ids is a defect, not a rounding "
            "difference; D-06/D-08 stay gated until this is zero."
        )
    elif defects:
        verdict = (
            "## D-07 VERDICT: FAIL -- see the missing-known-stuck-record defect above."
        )
    else:
        verdict = (
            "## D-07 VERDICT: PASS -- zero defect rows; all 4 known stuck records read "
            "the expected mismatch (live C, derived B)."
        )

    limits = "\n".join([
        "## What this does not say",
        "",
        "- **This gate is a snapshot, not a monitor.** The population is re-derived live "
        "on every invocation and never trusted from a stale local capture; a re-run "
        "against a changed live population may produce a different result.",
        "- **The 4 expected-mismatch rows are the ONLY accepted divergence class.** Any "
        "other row classified `defect` means D-07's gate has failed, not that a rounding "
        "difference occurred.",
        "- **This artifact does not itself retire `lv_icp_tier` or switch off WF1** "
        "(4625147345). D-06/D-08 remain gated on a human decision downstream of this "
        "evidence (Plan 04's checkpoint), not on this report alone.",
        "- **The D-16 zero-write claim is this script's own guarantee, not an external "
        "audit.** `scripts/check_tier_derived_parity.py` issues no "
        "`requests.{post,patch,delete}` call anywhere in this module; the claim is "
        "verifiable by reading the module, not merely asserted here.",
    ])

    mirror_section = render_mirror_section(rows)

    return "\n\n".join([denominator, table, cross_ref, verdict, mirror_section, limits]) + "\n"


# --- Task 3 (D-19): the operator-facing before/after tier census -------------------------

def build_census_points(rows: list) -> tuple:
    """rows: parity rows (as returned by build_rows). Builds (before, after) point dicts
    in scripts/build_rescore_report.py's own shape -- {label, population_count,
    tier_distribution, records} -- so render_census_markdown can hand them straight to
    that module's _validate_point/_diff_points without re-deriving those invariants here.
    "Before" reads lv_icp_tier; "after" reads lv_icp_tier_derived; both come from the SAME
    rows (fetched in one live run), so they cannot drift apart. Raises via
    scripts.build_rescore_report._coerce_int if a fit score will not coerce to an int --
    never silently drops or zeroes a bad value."""
    import scripts.build_rescore_report as rescore_report

    ordered = sorted(rows, key=lambda r: _id_sort_key(r["record_id"]))
    before_records, after_records = {}, {}
    before_dist, after_dist = {}, {}
    for r in ordered:
        rid = r["record_id"]
        score = rescore_report._coerce_int(r.get("fit_score"), f"census record {rid} fit_score")
        before_tier = r["live_tier"] if r["live_tier"] is not None else BLANK_TIER_KEY
        after_tier = r["derived_tier"] if r["derived_tier"] is not None else BLANK_TIER_KEY
        before_records[rid] = {"id": rid, "name": r.get("name"), "tier": before_tier, "score": score}
        after_records[rid] = {"id": rid, "name": r.get("name"), "tier": after_tier, "score": score}
        before_dist[before_tier] = before_dist.get(before_tier, 0) + 1
        after_dist[after_tier] = after_dist.get(after_tier, 0) + 1

    n = len(ordered)
    before_point = {
        "label": "Before (lv_icp_tier)", "population_count": n,
        "tier_distribution": before_dist, "records": before_records,
    }
    after_point = {
        "label": "After (lv_icp_tier_derived)", "population_count": n,
        "tier_distribution": after_dist, "records": after_records,
    }
    return before_point, after_point


def _union_tier_order(dist_a: dict, dist_b: dict, canonical_order: list) -> list:
    order = [t for t in canonical_order if t in dist_a or t in dist_b]
    residual = sorted(k for k in (set(dist_a) | set(dist_b)) if k not in canonical_order)
    return order + residual


def render_census_markdown(before_point, after_point, never_scored_count, null_variant, checked_at) -> str:
    """Reuses scripts/build_rescore_report.py's own point-validation, diff, and
    movement-table machinery (D-19: "reuse the three-point distribution renderer rather
    than writing a second one") collapsed to the two-point before/after shape D-19 asks
    for. Raises on an empty population or a distribution that does not sum to its stated
    population count via that module's own _validate_point -- never silently renders a
    clean pass on bad input. Pure function of its arguments."""
    import scripts.build_rescore_report as rescore_report

    rescore_report._validate_point(before_point)
    rescore_report._validate_point(after_point)
    movements, score_only = rescore_report._diff_points(before_point, after_point)

    expected_ids = sorted(KNOWN_STUCK_IDS, key=_id_sort_key)
    actual_movement_ids = sorted((m["id"] for m in movements), key=_id_sort_key)
    matches_expectation = (
        actual_movement_ids == expected_ids
        and all(m["from_tier"] == "C" and m["to_tier"] == "B" for m in movements)
    )

    lines = ["## Operator-Facing Result: Before/After Tier Census (D-19)", ""]
    lines.append(
        f"- **Before** ({before_point['label']}) and **after** ({after_point['label']}) "
        f"are read live in the SAME run ({checked_at}) against the same "
        f"{before_point['population_count']}-company scored population, so the two "
        "distributions cannot drift apart from each other."
    )
    lines.append(
        "- **Pre-registered expectation (D-19), stated before this run's result was "
        f"known:** identical distribution except the 4 known stuck records "
        f"({', '.join(expected_ids)}) moving C -> B. Any other movement is a defect "
        "signal, not a narrative to explain."
    )
    lines.append("")

    order = _union_tier_order(
        before_point["tier_distribution"], after_point["tier_distribution"],
        rescore_report.TIER_ORDER,
    )
    lines.append("### Tier Distribution")
    lines.append("")
    lines.append("| Point | " + " | ".join(order) + " |")
    lines.append("|---" * (len(order) + 1) + "|")
    for label, dist in (("Before", before_point["tier_distribution"]),
                         ("After", after_point["tier_distribution"])):
        cells = " | ".join(str(dist.get(t, 0)) for t in order)
        lines.append(f"| {label} | {cells} |")
    lines.append("")

    lines.append("### Tier Movements: Before -> After")
    lines.append("")
    if movements:
        lines.extend(rescore_report._movement_table(
            sorted(movements, key=lambda m: _id_sort_key(m["id"])), "Before", "After",
        ))
    else:
        lines.append("No tier movements between Before and After.")
    lines.append("")

    lines.append(
        "**Census matches the pre-registered expectation.**" if matches_expectation else
        "**DEFECT: the census diverges from the pre-registered expectation -- see the "
        "movement table above for exactly which row(s) moved unexpectedly.**"
    )
    lines.append("")

    # Severity callout: a vetoed record (Before tier D) that no longer reads D After is
    # not just "a defect row" -- it means lv_icp_tier_derived is actively LESS safe than
    # the stale enum for that record (a workable score-based tier instead of the correct
    # hard exclusion). Named explicitly, with examples, so this consequence is visible to
    # anyone reading only this artifact -- not left implicit in a table cell.
    d_to_other = [m for m in movements if m["from_tier"] == "D" and m["to_tier"] != "D"]
    if d_to_other:
        examples = ", ".join(
            f"{m['name']} ({m['id']})"
            for m in sorted(d_to_other, key=lambda m: _id_sort_key(m["id"]))[:2]
        )
        lines.append(
            f"**SEVERITY: `lv_icp_tier_derived` is currently WORSE than the stale enum "
            f"for vetoed records.** {len(d_to_other)} of {len(movements)} unexpected "
            f"movements are records correctly excluded on `lv_icp_tier` (Tier D) that "
            f"read a workable score-based tier on `lv_icp_tier_derived` instead -- e.g. "
            f"{examples}. `lv_icp_tier_derived` must NOT be treated as authoritative for "
            "vetoed records until the veto guard is fixed and re-proven; D-06/D-08 stay "
            "blocked on this."
        )
        lines.append("")

    lines.append("### Never-scored population (D-04 disclosure)")
    lines.append("")
    if null_variant == "coalesced_minus_one":
        lines.append(
            "D-04's forced fallback fired (50-NULL-PROBE.json: "
            "`settled_variant=coalesced_minus_one`). A live "
            "`NOT_HAS_PROPERTY(lv_icp_fit_score)` count found "
            f"**{never_scored_count} never-enriched companies**, each now reading "
            '`lv_icp_tier_derived="Unscored"` where `lv_icp_tier` stays blank. This is a '
            "disclosed, deliberate consequence of the forced coalesce fallback (Phase 49 "
            "unmet-truth style), not a surprise -- it is a SEPARATE population from the "
            f"{before_point['population_count']}-company scored fraction above and is not "
            "folded into either distribution table."
        )
    elif null_variant == "uncoalesced":
        lines.append(
            "D-03's preferred uncoalesced variant shipped (50-NULL-PROBE.json: "
            "`settled_variant=uncoalesced`). Never-scored companies keep today's blank "
            "tier on `lv_icp_tier_derived`; the count of blank-tier companies is "
            "unchanged."
        )
    else:
        lines.append(
            f"Unrecognized settled_variant {null_variant!r} in 50-NULL-PROBE.json -- "
            "cannot state which disclosure applies without re-checking the probe result."
        )
    lines.append("")

    lines.append("### What this does not say")
    lines.append("")
    lines.append(
        "- **This census is a snapshot of one live run, not a monitor.** Both "
        "distributions are re-derived live in this same invocation; a later run against "
        "a changed population may differ."
    )
    lines.append(
        "- **The never-scored count above is informational, not part of the movement "
        "verdict.** It is a disclosed side effect of the formula's null-handling "
        "variant, not a tier movement within the scored population being compared."
    )

    return "\n".join(lines) + "\n"


def _append_or_write(path: Path, text: str) -> None:
    """--census's own output joins whatever the default parity run already wrote to the
    same --out path, rather than overwriting it -- so one file carries both the D-07
    verdict (Task 2) and the D-19 census (Task 3). Writes fresh if the path does not yet
    exist (e.g. the verify block's own throwaway --out path)."""
    if path.exists() and path.read_text().strip():
        existing = path.read_text().rstrip("\n")
        path.write_text(existing + "\n\n---\n\n" + text)
    else:
        path.write_text(text)


# --- live reads (read-only; D-16) -------------------------------------------------------

def _fetch_records(ids: list) -> list:
    from src.hubspot_client import get_record
    return [{"id": i, **get_record("companies", i, FETCH_PROPS)["properties"]} for i in ids]


def _count_total_companies() -> int:
    from src.hubspot_client import search_records
    result = search_records("companies", [], ["name"], limit=1)
    return result.get("total", 0)


def _count_never_scored_companies() -> int:
    from src.hubspot_client import search_records
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
        ["name"],
        limit=1,
    )
    return result.get("total", 0)


def _read_settled_variant() -> str:
    doc = json.loads(NULL_PROBE_PATH.read_text())
    return doc["settled_variant"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", default=None,
                         help="Comma-separated company ids; restricts the run instead of "
                              "re-deriving the full live scored population.")
    parser.add_argument("--out", default=None,
                         help="Path to write the markdown report to. Defaults to stdout.")
    parser.add_argument("--census", action="store_true",
                         help="Render D-19's before/after tier census (lv_icp_tier vs "
                              "lv_icp_tier_derived) instead of the row-level D-07 parity "
                              "gate. Appends to --out if it already exists, so one file "
                              "carries both the parity verdict and the census.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "parity check.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    from scripts.rescore_population import select_scored_population

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    else:
        ids = select_scored_population()

    if not ids:
        print("REFUSED: no ids to check (empty --ids or empty live population).")
        return 1

    records = _fetch_records(ids)
    rows = build_rows(records)
    checked_at = _now_iso()

    if args.census:
        before_point, after_point = build_census_points(rows)
        never_scored_count = _count_never_scored_companies()
        null_variant = _read_settled_variant()
        text = render_census_markdown(
            before_point, after_point, never_scored_count, null_variant, checked_at,
        )
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            _append_or_write(out_path, text)
            print(f"census written to {out_path}")
        else:
            print(text)
        return 0

    total_companies = _count_total_companies()
    text = render_evidence_markdown(rows, len(rows), total_companies, checked_at)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        print(f"wrote {out_path}")
    else:
        print(text)

    defects = [r for r in rows if r["classification"] == "defect"]
    expected = [r for r in rows if r["classification"] == "expected_mismatch"]
    print(f"population={len(rows)} match={len(rows) - len(defects) - len(expected)} "
          f"expected_mismatch={len(expected)} defect={len(defects)}")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
