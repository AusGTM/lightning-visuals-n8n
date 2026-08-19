#!/usr/bin/env python3
"""scripts/veto_remediation_report.py

Phase 47 Plan 03 (VETO-01, COVER-01, COVER-02) -- the per-ID before/after assertion
47-VALIDATION.md's Wave 0 list says does not exist. `scripts/run_scoring_parity.py`
samples the wider population, not this 17-record cohort, so it cannot serve.

Read-only, always: from `src.hubspot_client` this module imports only `get_record` and
`search_records` -- no write helper of any kind is imported or called anywhere in this
file. The 17 pinned ids, their fixed order, and the scoring oracle are declared once in
`scripts.remediate_veto_companies` and imported here, never restated.

Two responsibilities live in this one module:
  - Task 1: `snapshot`/`predict`/`diff`/`classify` -- the per-ID before/after cohort
    report, so VETO-01's outcome is asserted per record rather than eyeballed in bulk.
  - Task 2: `live_property_names`/`missing_property_names` -- the live
    property-existence guard `scripts.remediate_veto_companies.main()` runs before any
    write branch. The HTTP call itself is delegated to
    `scripts.check_schema_drift._get_live_properties` -- this module never issues a
    second properties-listing call of its own.

`.env` is Read/Bash permission-blocked this session -- the operator invocation for a
live before-snapshot is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/veto_remediation_report.py', run_name='__main__')" \
        --mode before --out .planning/phases/47-veto-remediation/47-BEFORE.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.hubspot_client import get_record, search_records  # noqa: E402,F401
from src.icp_scoring import load_yaml  # noqa: E402
from scripts.remediate_veto_companies import (  # noqa: E402
    EXPECTED_PORTAL_ID,
    PINNED_COMPANY_ID_ORDER,
    PinRefused,
    _has_credentials,
    _portal_ok,
    expected_score_and_tier,
    resolve_pinned_ids,
)

# The 8 observed properties per row (VETO-01/COVER-01's per-id before/after cohort
# report). Includes the four derived read-only fields (lv_icp_fit_score,
# lv_icp_tier_derived — repointed 2026-08-19 from the lv_icp_tier Phase 50 archived,
# lv_anti_icp_flag, lv_anti_icp_reason) this phase never writes, and both VETO-03
# acceptance-search property names (lv_anti_icp_reason, lv_country_region_normalized).
OBSERVED_PROPS = (
    "name",
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
    "lv_icp_fit_score",
    "lv_icp_tier_derived",
    "lv_anti_icp_flag",
    "lv_anti_icp_reason",
)


def _non_anz_reason() -> str:
    """The non-ANZ hard-veto reason string, read from config/icp_scoring.yaml -- never
    restated as a local literal (mirrors remediate_veto_companies.settle_veto)."""
    cfg = load_yaml("config/icp_scoring.yaml")
    return cfg["hard_vetoes"]["non_anz"]["reason"]


# --- Task 1: per-ID before/after cohort report ----------------------------------------

def snapshot(ids, reader=get_record):
    """Pure read: one row per id, in PINNED_COMPANY_ID_ORDER order, carrying the eight
    OBSERVED_PROPS plus the id. With `reader` injected, no write helper is imported or
    called by this function -- `requests.post` is never touched."""
    order = {cid: i for i, cid in enumerate(PINNED_COMPANY_ID_ORDER)}
    ordered_ids = sorted(ids, key=lambda cid: order.get(cid, len(order)))
    rows = []
    for company_id in ordered_ids:
        record = reader("companies", company_id, list(OBSERVED_PROPS))
        props = record.get("properties", {})
        row = {"id": company_id}
        for prop in OBSERVED_PROPS:
            row[prop] = props.get(prop)
        rows.append(row)
    return rows


def predict(row, candidate_inputs):
    """The score/tier the record would reach given `candidate_inputs` (the researched
    values a run would write) overlaid on `row`'s existing properties, via
    `expected_score_and_tier` -- never a second, hand-copied scoring call. Writes
    nothing."""
    merged = {k: v for k, v in row.items() if k != "id"}
    merged.update(candidate_inputs or {})
    return expected_score_and_tier(merged)


# D-23 (2026-08-12): Jam TV is the ITALIAN broadcaster jamtv.it. Its non-ANZ veto is
# CORRECT and Phase 47 deliberately preserved it, writing lv_country_region_normalized
# = "Other" so the record also falls outside VETO-03's blank-region search. Phase 46
# mislabelled it `false_veto` only because that field was blank, and blank means
# never-determined, not determined-to-be-ANZ.
#
# Without this exemption `classify` returns `still_non_anz` for the one record required
# to be in exactly that state, and `--mode after` REFUSES on a correct end state -- a
# false failure for anyone re-running the report after Phase 47. Keyed by id, not by
# reason text, because the reason is genuinely the non-ANZ one.
TRUE_NON_ANZ_VETO_IDS = frozenset({"17317850381"})  # Jam TV (IT) -- D-23


def classify(row) -> str:
    """`cleared` | `residual_other_veto` | `correct_non_anz` | `still_non_anz`, from a
    single row's lv_anti_icp_flag/lv_anti_icp_reason. `still_non_anz` is the only failing
    classification -- `residual_other_veto` covers a legitimate different hard veto, and
    `correct_non_anz` covers a D-23 record whose non-ANZ veto is true (see
    TRUE_NON_ANZ_VETO_IDS)."""
    flag = row.get("lv_anti_icp_flag")
    if flag != "true":
        return "cleared"
    reason = row.get("lv_anti_icp_reason") or ""
    if _non_anz_reason() in reason:
        if str(row.get("id")) in TRUE_NON_ANZ_VETO_IDS:
            return "correct_non_anz"
        return "still_non_anz"
    return "residual_other_veto"


def diff(before_rows, after_rows) -> dict:
    """Per-id record of which OBSERVED_PROPS changed between before_rows and
    after_rows, plus `classify(after_row)`. An id present on only one side is reported
    explicitly (present_before/present_after flags, classification None) rather than
    silently dropped."""
    before_by_id = {r["id"]: r for r in before_rows}
    after_by_id = {r["id"]: r for r in after_rows}
    all_ids = sorted(set(before_by_id) | set(after_by_id))

    result = {}
    for company_id in all_ids:
        before_row = before_by_id.get(company_id)
        after_row = after_by_id.get(company_id)
        if before_row is None or after_row is None:
            result[company_id] = {
                "present_before": before_row is not None,
                "present_after": after_row is not None,
                "changed": None,
                "classification": None,
            }
            continue
        changed = {
            prop: {"before": before_row.get(prop), "after": after_row.get(prop)}
            for prop in OBSERVED_PROPS
            if before_row.get(prop) != after_row.get(prop)
        }
        result[company_id] = {
            "present_before": True,
            "present_after": True,
            "changed": changed,
            "classification": classify(after_row),
        }
    return result


# --- Task 2: live property-existence guard ---------------------------------------------

def live_property_names(object_type="companies", lister=None):
    """The set of property names the portal actually has for `object_type`. Delegates
    the HTTP call to `scripts.check_schema_drift._get_live_properties` (lazy-imported to
    avoid importing that module's own dependency chain at module load) rather than
    issuing a second properties-listing call of its own. `lister` is injectable so
    offline tests need no network."""
    if lister is None:
        from scripts.check_schema_drift import _get_live_properties as lister
    results = lister(object_type)
    return {p["name"] for p in results}


def missing_property_names(payload_keys, live_names) -> list:
    """The sorted set of `payload_keys` absent from `live_names` -- CLAUDE.md §4.0's
    guard: a name declared in a design table is not necessarily a name the portal has."""
    return sorted(set(payload_keys) - set(live_names))


# --- main -------------------------------------------------------------------------------

def _parse_ids_csv(raw: str) -> list:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("before", "after", "diff"), default="before",
                         help="before/after: read-only snapshot of the pinned ids. diff: "
                              "compare two previously-written snapshot files.")
    parser.add_argument("--out", default=None, help="Path to write the resulting JSON to.")
    parser.add_argument("--before", default=None, help="Path to a before-snapshot JSON (diff mode).")
    parser.add_argument("--after", default=None, help="Path to an after-snapshot JSON (diff mode).")
    parser.add_argument("--ids", default="", help="Comma-separated pinned ids; defaults to all 17.")
    return parser


def _write_out(path, payload):
    if path:
        Path(path).write_text(json.dumps(payload, indent=2, default=str))


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.mode == "diff":
        if not args.before or not args.after:
            print("REFUSED: --mode diff requires both --before and --after. No call made.")
            return 1
        before_rows = json.loads(Path(args.before).read_text())
        after_rows = json.loads(Path(args.after).read_text())
        result = diff(before_rows, after_rows)
        print(json.dumps(result, indent=2, default=str))
        _write_out(args.out, result)
        failing = any(
            not entry["present_before"] or not entry["present_after"]
            or entry["classification"] == "still_non_anz"
            for entry in result.values()
        )
        return 1 if failing else 0

    # before / after: read-only live snapshot.
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this script.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    requested = _parse_ids_csv(args.ids) or list(PINNED_COMPANY_ID_ORDER)
    try:
        resolved_ids = resolve_pinned_ids(requested)
    except PinRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    rows = snapshot(resolved_ids)
    print(json.dumps(rows, indent=2, default=str))
    _write_out(args.out, rows)

    if args.mode == "after":
        failing_ids = [r["id"] for r in rows if classify(r) == "still_non_anz"]
        if failing_ids:
            print(f"REFUSED: {len(failing_ids)} record(s) still classify still_non_anz "
                  f"after remediation: {failing_ids}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
