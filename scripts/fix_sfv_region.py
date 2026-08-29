#!/usr/bin/env python3
"""scripts/fix_sfv_region.py

Phase 58 Plan 05 Task 4 -- the operator-authorized, record-scoped corrective window for
Series Futsal Victoria `283816805830` only (operator ruling 2026-08-26, "Yes, fix it").

Execution 11983 (the operator's own armed walk-session dispatch, 2026-08-26T09:25Z) wrote
a regression onto this ONE company: ZoomInfo matched a US branch and outranked every
Australian source, so `lv_country_region_normalized` flipped AU -> "Other", which fired
the non-ANZ hard veto (`lv_anti_icp_flag="true"`, reason "Non-ANZ geography") and left
`lv_enrichment_status="needs_review"` (with `lv_enrichment_needs_review` set alongside it
by the same Decide-node branch, scripts/build_cloud_workflows.py ~line 3225-3230). This
script corrects exactly that one company, exactly those fields.

TWO LEGS, in this fixed order (Decide reads the region from whatever HubSpot holds at
POST time, so the PATCH must land first):

  1. A direct HubSpot PATCH (this script's own HTTP call, via
     src.hubspot_client.patch_record -- no n8n involved) correcting
     lv_country_region_normalized to "AU" and clearing the two enrichment-status fields
     the regression set.
  2. The Phase 47.5 on-demand recompute POST (CLAUDE.md Section 13.0): a bare D-18 event
     carrying `recompute: true` and NOTHING else -- no `mode`, no `domain`. This is
     deliberate, not an oversight: any other event shape would re-run the provider
     waterfall, and ZoomInfo's US-branch mismatch (the still-open debt this script is
     working around, closed properly in a separate plan 58-06) could re-write "Other"
     straight back over this script's own PATCH. The recompute lane is the only one that
     re-derives the veto from what mergeCompanies never ran, so it cannot re-introduce the
     regression it is being used to clear.

WHAT THIS SCRIPT DOES NOT DO: arm n8n's write-safety allowlist. CLAUDE.md Section 13.0 is
explicit that deriving is free but writing needs a deliberately armed, record-scoped
window (execution 11858 proved this live: `action: "write_blocked"` on an empty
allowlist). That window is opened by the OPERATOR, separately, through the
`operator-claude-plugin` backend-control skill's "enable live writes for a send" / write
grant flow (see operator-claude-plugin/skills/backend-control/SKILL.md) -- never a shell
env var, and never something this script or Claude sets. `--execute` assumes that window
is already open, scoped to hs_object_id `283816805830`, and its own read-back REPORTS
whether the recompute leg's write actually landed (`action` != "write_blocked") or was
blocked (window not open) -- it never claims success from a 200.

Two modes, both offline-safe by default:
    python3 scripts/fix_sfv_region.py --plan
        Prints the exact PATCH payload, the exact webhook event body, and the target URL.
        Makes no network call.
    ALLOW_VETO_REMEDIATION=true python3 scripts/fix_sfv_region.py --execute
        Sends both legs for real, then reads back the five assertion fields.
        ALLOW_VETO_REMEDIATION is operator-only, per-shell, never set by Claude -- same
        arming discipline as scripts/remediate_veto_companies.py and
        scripts/probe_company_propose_mode.py, whose post_webhook_event/build_webhook_event
        this script reuses rather than re-implementing a second event builder or transport.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))  # flat plugin imports, same idiom scripts/june_run_arm.py uses

from src.guards import assert_disjoint  # noqa: E402
from src.hubspot_client import get_record, patch_record  # noqa: E402

from scripts.remediate_veto_companies import (  # noqa: E402
    EXPECTED_PORTAL_ID,
    FORBIDDEN_PROPS,
    NotArmedError,
    SettleFailed,
    _has_credentials,
    _portal_ok,
    build_webhook_event,
    post_webhook_event,
    settle_veto,
)

import config_gate  # noqa: E402

# The ONE company this script will ever touch -- a module constant with no CLI override,
# same discipline as probe_company_propose_mode.py's TARGET_COMPANY_ID. Series Futsal
# Victoria. This is NOT added to remediate_veto_companies.PINNED_COMPANY_ID_ORDER -- that
# list is a different, closed remediation (Phase 47's 17 false-veto records) and stays
# untouched.
TARGET_COMPANY_ID = "283816805830"  # Series Futsal Victoria

REGION_PROPERTY = "lv_country_region_normalized"
CORRECT_REGION = "AU"
STATUS_PROPERTY = "lv_enrichment_status"
CORRECT_STATUS = "complete"
NEEDS_REVIEW_PROPERTY = "lv_enrichment_needs_review"
CORRECT_NEEDS_REVIEW = "false"

# Read back after the armed run -- the four fields the operator's checkpoint names, plus
# the review reason so a lingering explanation is visible even if the flag itself cleared.
ASSERTION_FIELDS = (
    REGION_PROPERTY, "lv_anti_icp_flag", "lv_anti_icp_reason",
    STATUS_PROPERTY, NEEDS_REVIEW_PROPERTY,
)

N8N_EXECUTION_CAP = 2  # 1 for the recompute POST, 1 spare for a re-verify


def build_region_patch() -> dict:
    """The exact PATCH properties this script sends -- region correction plus clearing
    the two enrichment-status fields execution 11983's regression set together (Decide
    Company Action sets lv_enrichment_needs_review="true" in the SAME branch as
    lv_enrichment_status="needs_review", scripts/build_cloud_workflows.py ~3225-3230, so a
    PATCH that clears one without the other leaves the record stuck in the Section 22
    review queue). Never touches lv_anti_icp_flag/lv_anti_icp_reason/any score or tier --
    those are Decide-owned, recomputed by the webhook leg, never PATCHed directly here."""
    props = {
        REGION_PROPERTY: CORRECT_REGION,
        STATUS_PROPERTY: CORRECT_STATUS,
        NEEDS_REVIEW_PROPERTY: CORRECT_NEEDS_REVIEW,
    }
    # D-07 (WR-02 discipline, ac64353): a real, unstrippable check, not `assert` --
    # `assert` is removed entirely under `python -O` / PYTHONOPTIMIZE=1, and what it
    # guards is a live PATCH to a HubSpot portal with no rollback.
    assert_disjoint(props, FORBIDDEN_PROPS, "build_region_patch produced a forbidden derived-field key")
    return props


def build_recompute_event() -> list:
    """The exact D-18 event this script sends -- `recompute: true` and nothing else.
    Delegates entirely to remediate_veto_companies.build_webhook_event; no second event
    builder exists in this script. No `domain` (this company already exists -- the bare
    object-id fetch-by-id lane is what Phase 40-03 proved live) and no `mode` (a `mode`
    value would make this a non-writing propose probe, not the write this script needs)."""
    return build_webhook_event(TARGET_COMPANY_ID, recompute=True)


def _describe_target(config: dict) -> str:
    from scripts.remediate_veto_companies import WEBHOOK_PATH
    return f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{WEBHOOK_PATH}"


def _action_from_response(response_body):
    """response_body may be a dict or a one-item list (Build Response's row shape) --
    return the `action` string either way, or None if it cannot be found."""
    if isinstance(response_body, list):
        response_body = response_body[0] if response_body else None
    if isinstance(response_body, dict):
        return response_body.get("action")
    return None


def _print_plan(patch_props: dict, event: list, config, config_error) -> None:
    print("=== PLAN (dry run -- no network call is made) ===")
    if config_error:
        print(f"note: config could not be loaded ({config_error}); target URL is unresolvable.")
        target = "(unresolvable)"
    else:
        try:
            target = _describe_target(config)
        except Exception as exc:  # noqa: BLE001 -- a bad config shape IS the observation here
            target = f"(unresolvable: {exc})"
    print(f"target company id: {TARGET_COMPANY_ID} (Series Futsal Victoria)")
    print("\n--- leg 1: direct HubSpot PATCH (no n8n involved) ---")
    print(f"PATCH https://api.hubapi.com/crm/v3/objects/companies/{TARGET_COMPANY_ID}")
    print(json.dumps({"properties": patch_props}, indent=2))
    print("\n--- leg 2: n8n recompute POST (needs the operator's record-scoped write window open) ---")
    print(f"POST {target}")
    print(json.dumps(event, indent=2))
    print(
        "\nLive execution needs BOTH: the operator-only shell variable "
        "ALLOW_VETO_REMEDIATION=true (Claude never sets this), AND a record-scoped n8n "
        f"write window already open for hs_object_id {TARGET_COMPANY_ID}, opened through "
        "the operator-claude-plugin backend-control skill's 'enable live writes for a "
        "send' flow -- never a shell env var for that half. Run:\n"
        "  ALLOW_VETO_REMEDIATION=true python3 scripts/fix_sfv_region.py --execute"
    )


def main(
    argv=None,
    config_loader=config_gate.load_config,
    patcher=patch_record,
    reader=get_record,
    poster=post_webhook_event,
    settler=settle_veto,
    has_credentials=_has_credentials,
    portal_ok=_portal_ok,
    env=os.environ,
) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true", help="Print both leg payloads. Makes no network call.")
    group.add_argument(
        "--execute", action="store_true",
        help="Send both legs for real. Needs ALLOW_VETO_REMEDIATION=true in the "
             "OPERATOR's own shell, and the n8n record-scoped write window already open.",
    )
    args = parser.parse_args(argv)

    patch_props = build_region_patch()
    event = build_recompute_event()

    config = {}
    config_error = None
    try:
        config = config_loader()
    except Exception as exc:  # noqa: BLE001 -- an unloadable config IS reportable here
        config_error = str(exc)

    if args.plan:
        _print_plan(patch_props, event, config, config_error)
        return 0

    # --execute
    armed = str(env.get("ALLOW_VETO_REMEDIATION", "false")).lower() == "true"
    if not armed:
        print(
            "REFUSED: ALLOW_VETO_REMEDIATION is not set to true -- nothing was sent. "
            "This is an operator-only, per-shell decision, never made by Claude."
        )
        return 1

    if config_error:
        print(f"REFUSED: config could not be loaded ({config_error}). No network call made.")
        return 1

    if not portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if not has_credentials():
        print("REFUSED: HUBSPOT_PRIVATE_APP_TOKEN must be set to run this script live.")
        return 1

    print(f"=== EXECUTING against {TARGET_COMPANY_ID} (Series Futsal Victoria) ===")

    print("\n--- leg 1: PATCH ---")
    patch_response = patcher("companies", TARGET_COMPANY_ID, patch_props, dry_run=False)
    print(json.dumps(patch_response, indent=2, default=str))

    print("\n--- leg 2: recompute POST ---")
    try:
        response = poster(TARGET_COMPANY_ID, True, config, recompute=True)
    except NotArmedError as exc:
        print(f"REFUSED: {exc}")
        return 1
    try:
        response_body = response.json()
    except Exception:  # noqa: BLE001 -- a non-JSON response body IS the observation here
        response_body = getattr(response, "text", None)
    print(json.dumps(response_body, indent=2, default=str))

    action = _action_from_response(response_body)
    if action == "write_blocked":
        print(
            "\nVETO NOT WRITTEN: the recompute derived the correct output but n8n's "
            f"record-scoped write window for {TARGET_COMPANY_ID} was not open, so nothing "
            "was patched by the Decide node. Open the write window (backend-control "
            "'enable live writes for a send') and re-run --execute."
        )
    elif action is not None:
        print(f"\nrecompute action: {action!r} -- verifying via read-back below.")

    print("\n--- settling lv_anti_icp_flag ---")
    settle_ok = True
    try:
        flag_value, elapsed = settler(TARGET_COMPANY_ID)
        print(f"settled: lv_anti_icp_flag={flag_value!r} after {elapsed:.1f}s")
    except SettleFailed as exc:
        settle_ok = False
        print(f"SETTLE FAILED: {exc}")

    print("\n--- independent read-back ---")
    record = reader("companies", TARGET_COMPANY_ID, list(ASSERTION_FIELDS))
    live = record.get("properties", {})
    print(json.dumps({field: live.get(field) for field in ASSERTION_FIELDS}, indent=2, default=str))

    print(
        f"\ncost actuals vs cap: 1 n8n execution used (cap {N8N_EXECUTION_CAP}), "
        "0 provider credits, 0 Anthropic calls (the recompute lane carries no provider, "
        "research or merge node)."
    )

    return 0 if settle_ok else 1


if __name__ == "__main__":
    sys.exit(main())
