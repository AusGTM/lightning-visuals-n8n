#!/usr/bin/env python3
"""scripts/probe_org_type_migration.py

Phase 21 Task 1 — disposable-property probe ladder settling Open Questions 1 and 2 of
21-RESEARCH.md: does HubSpot allow converting a NON-EMPTY property's type from text to
enumeration in place, what happens to the existing value, whether an out-of-vocabulary
write is rejected after conversion, whether the reverse conversion is permitted (the cheap
rollback), and whether an archived property's name is immediately reusable.

This script NEVER targets the real `lv_org_type` property (that literal string appears only
in this docstring and inline comments — grep for it and confirm every hit is prose, never a
URL/body). It operates on exactly ONE disposable property, PROBE_PROPERTY_NAME below, a
module constant with no CLI override — there is no legitimate reason for this script to be
pointable anywhere else, so no argument for it exists at all.

Same idiom as scripts/sync_hubspot_properties.py / scripts/snapshot_hubspot_schema.py:
env-gated, dry-run-by-default, `_has_credentials()` skip-to-exit-0, the same portal guard,
and the same two-key write gate (DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true).
Step 2 also writes a company RECORD value, so it is additionally gated by the existing
TEST_COMPANY_IDS allowlist (the record-write boundary), never a free-text company id.

Usage:
    python scripts/probe_org_type_migration.py               # dry-run preview, zero calls
    DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
        python scripts/probe_org_type_migration.py            # armed 9-step ladder (operator only)

ARMED runs are classifier-blocked for agents in this environment (Phase 20 Plan 04
precedent) — this script is built and dry-run here; the armed invocation is an operator
action packaged by Task 3.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src import taxonomy  # noqa: E402
from src.hubspot_client import BASE_URL  # noqa: E402  (constant only, no side effects)

# Portal guard — same constant convention as every other schema-mutating script.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# The ONE disposable property this script will ever touch. Deliberately double-underscored
# and phase-scoped, mirroring snapshot_hubspot_schema.py's own PROBE_PROPERTY_NAME idiom —
# never `lv_org_type` (the real property), never anything an argument could redirect.
PROBE_PROPERTY_NAME = "lv__phase21_org_type_probe"
PROBE_GROUP_NAME = "companyinformation"  # the same group lv_org_type itself lives in

NOT_OBSERVED = "not-yet-observed"
VERDICT_KEYS = [
    "in_place_type_patch_allowed",
    "existing_value_after_conversion",
    "out_of_vocab_write_after_conversion_rejected",
    "reverse_patch_allowed",
    "emptying_lifts_block",
    "name_immediately_reusable",
    "recommended_migration_shape",
]


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    # Identical two-key gate to sync_hubspot_properties.py — never a third gate name.
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow


def _resolved_property_name() -> str:
    return PROBE_PROPERTY_NAME


def _property_name_ok(name: str) -> bool:
    return name == PROBE_PROPERTY_NAME


def _resolved_test_company_id() -> str:
    ids = [x.strip() for x in os.getenv("TEST_COMPANY_IDS", "").split(",") if x.strip()]
    return ids[0] if ids else ""


def _test_company_ok(company_id: str) -> bool:
    ids = {x.strip() for x in os.getenv("TEST_COMPANY_IDS", "").split(",") if x.strip()}
    return bool(company_id) and company_id in ids


# --- taxonomy-derived probe values (never re-typed as a literal vocabulary) -----------

def _enum_options() -> list:
    return [
        {"label": key, "value": key, "displayOrder": idx, "hidden": False}
        for idx, key in enumerate(taxonomy.ORG_TYPES.keys())
    ]


IN_VOCAB_PROBE_VALUE = sorted(k for k in taxonomy.ORG_TYPES if k != taxonomy.DEFAULT_ORG_TYPE)[0]
OUT_OF_VOCAB_PROBE_VALUE = "lv__phase21_probe_out_of_vocab_value"  # deliberately unmapped


def _text_property_spec() -> dict:
    return {
        "name": PROBE_PROPERTY_NAME,
        "label": "[PROBE] Phase 21 org_type migration probe (disposable)",
        "type": "string",
        "fieldType": "text",
        "groupName": PROBE_GROUP_NAME,
        "options": [],
    }


def _enum_property_patch() -> dict:
    return {"type": "enumeration", "fieldType": "select", "options": _enum_options()}


def _text_property_revert_patch() -> dict:
    return {"type": "string", "fieldType": "text", "options": []}


def _enum_property_spec_for_recreate() -> dict:
    spec = dict(_text_property_spec())
    spec.update({"type": "enumeration", "fieldType": "select", "options": _enum_options()})
    return spec


# --- live HTTP helpers (each returns a status code, never raises on non-2xx — a rejected
# probe step IS the observation, not a crash) -------------------------------------------

def _safe_body(response):
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


def _create_property_live(spec: dict):
    import requests
    from src.hubspot_client import hs_headers
    r = requests.post(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(),
                       json=spec, timeout=30)
    return r.status_code, _safe_body(r)


def _patch_property_live(patch: dict):
    import requests
    from src.hubspot_client import hs_headers
    r = requests.patch(f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}",
                        headers=hs_headers(), json=patch, timeout=30)
    return r.status_code, _safe_body(r)


def _archive_property_live():
    import requests
    from src.hubspot_client import hs_headers
    r = requests.delete(f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}",
                         headers=hs_headers(), timeout=30)
    return r.status_code


def _patch_company_property_live(company_id: str, value):
    import requests
    from src.hubspot_client import hs_headers
    r = requests.patch(f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                        headers=hs_headers(), json={"properties": {PROBE_PROPERTY_NAME: value}},
                        timeout=30)
    return r.status_code, _safe_body(r)


def _get_company_property_live(company_id: str):
    import requests
    from src.hubspot_client import hs_headers
    r = requests.get(f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                      headers=hs_headers(), params={"properties": PROBE_PROPERTY_NAME},
                      timeout=30)
    r.raise_for_status()
    return r.json()


# --- printing helpers --------------------------------------------------------------------

def _banner(n: int, title: str) -> None:
    print(f"\n=== STEP {n}: {title} ===")


def _dry_run_line(method: str, url: str, body=None) -> None:
    print(f"[DRY RUN] Would {method} {url}")
    if body is not None:
        print(f"Body: {json.dumps(body, indent=2, sort_keys=True)}")


def _print_verdict(verdict: dict) -> None:
    print("\n=== VERDICT ===")
    for key in VERDICT_KEYS:
        print(f"{key}: {verdict.get(key, NOT_OBSERVED)}")


def _print_residue(residue: list) -> None:
    print("\n=== RESIDUAL STATE ===")
    if residue:
        print(f"RESIDUE LEFT IN PORTAL: {residue} — property {PROBE_PROPERTY_NAME!r} may still "
              f"exist live. Remove manually: "
              f"DELETE {BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}")
    else:
        print("Clean — nothing left behind in the portal.")


def _recommend_shape(verdict: dict) -> str:
    if verdict["in_place_type_patch_allowed"] == "yes":
        if verdict["reverse_patch_allowed"] == "yes":
            return "in place (cheap reverse-PATCH rollback confirmed)"
        return "in place (rollback is NOT a cheap reverse-PATCH — see reverse_patch_allowed)"
    if verdict["name_immediately_reusable"] == "yes":
        return "archive-and-recreate under the same name"
    if str(verdict["name_immediately_reusable"]).startswith("no"):
        return "shadow property under a new name"
    return NOT_OBSERVED


# --- the 9-step ladder ---------------------------------------------------------------------

def run_ladder(company_id: str, armed: bool) -> tuple:
    """Runs (or previews, if not armed) all 9 steps. Returns (verdict dict, residue list)."""
    verdict = {k: NOT_OBSERVED for k in VERDICT_KEYS}
    residue = []
    step1_ok = None  # None while unobserved (dry-run)

    # STEP 1: create the disposable property as text.
    _banner(1, "Create the disposable property as text")
    text_spec = _text_property_spec()
    if armed:
        status, body = _create_property_live(text_spec)
        step1_ok = status == 201
        if step1_ok:
            residue.append("property")
        print(f"HTTP {status} — Reading: property creation {'ok' if step1_ok else 'FAILED, body=' + str(body)}.")
    else:
        _dry_run_line("POST", f"{BASE_URL}/crm/v3/properties/companies", text_spec)

    # STEP 2: write an IN-VOCABULARY value onto the test company's disposable property.
    _banner(2, "Write an IN-VOCABULARY org-type value onto the test company's disposable property")
    if armed and step1_ok:
        status, body = _patch_company_property_live(company_id, IN_VOCAB_PROBE_VALUE)
        print(f"HTTP {status} — Reading: wrote {IN_VOCAB_PROBE_VALUE!r} -> "
              f"{'ok' if status == 200 else 'FAILED, body=' + str(body)}.")
    elif armed:
        print("Skipped: step 1 did not succeed.")
    else:
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                       {"properties": {PROBE_PROPERTY_NAME: IN_VOCAB_PROBE_VALUE}})

    # STEP 3: attempt the in-place conversion to enumeration/select.
    _banner(3, "Attempt the in-place conversion: PATCH property to enumeration/select")
    enum_patch = _enum_property_patch()
    step3_ok = None
    if armed and step1_ok:
        status, body = _patch_property_live(enum_patch)
        step3_ok = status == 200
        verdict["in_place_type_patch_allowed"] = "yes" if step3_ok else f"no (HTTP {status})"
        print(f"HTTP {status} — Reading: in-place type conversion "
              f"{'ALLOWED' if step3_ok else 'BLOCKED'}.")
    elif armed:
        print("Skipped: step 1 did not succeed.")
    else:
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}", enum_patch)

    # STEP 4: read the test company back and classify the surviving value.
    _banner(4, "Read the test company back and classify the surviving value")
    if armed and step1_ok:
        try:
            record = _get_company_property_live(company_id)
            value = record.get("properties", {}).get(PROBE_PROPERTY_NAME)
            if value == IN_VOCAB_PROBE_VALUE:
                verdict["existing_value_after_conversion"] = "preserved verbatim"
            elif value in (None, ""):
                verdict["existing_value_after_conversion"] = "blanked"
            else:
                verdict["existing_value_after_conversion"] = f"changed to {value!r}"
            print(f"Reading: surviving value = {value!r} -> {verdict['existing_value_after_conversion']}.")
        except Exception as exc:  # noqa: BLE001 — a broken record read IS an observation here
            verdict["existing_value_after_conversion"] = f"record now errors ({exc})"
            print(f"Reading: GET failed -> {verdict['existing_value_after_conversion']}.")
    elif armed:
        print("Skipped: step 1 did not succeed.")
    else:
        _dry_run_line("GET", f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                       {"properties": PROBE_PROPERTY_NAME})

    # STEP 5: only if step 3 succeeded, attempt an OUT-OF-VOCABULARY write.
    _banner(5, "If step 3 succeeded, attempt to write an OUT-OF-VOCABULARY value")
    if armed and step1_ok and step3_ok:
        status, body = _patch_company_property_live(company_id, OUT_OF_VOCAB_PROBE_VALUE)
        rejected = status != 200
        verdict["out_of_vocab_write_after_conversion_rejected"] = "yes" if rejected else "no (accepted!)"
        print(f"HTTP {status} — Reading: out-of-vocab write "
              f"{'REJECTED' if rejected else 'ACCEPTED (unexpected)'}.")
    elif armed:
        print("Skipped: step 3 did not succeed, nothing to test here.")
    else:
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                       {"properties": {PROBE_PROPERTY_NAME: OUT_OF_VOCAB_PROBE_VALUE}})
        print("(only executed live if step 3's conversion succeeds)")

    # STEP 6: only if step 3 succeeded, attempt the REVERSE conversion.
    _banner(6, "Attempt the REVERSE conversion back to text")
    if armed and step1_ok and step3_ok:
        status, body = _patch_property_live(_text_property_revert_patch())
        allowed = status == 200
        verdict["reverse_patch_allowed"] = "yes" if allowed else f"no (HTTP {status})"
        print(f"HTTP {status} — Reading: reverse conversion {'ALLOWED' if allowed else 'BLOCKED'}.")
    elif armed:
        print("Skipped: step 3 did not succeed, nothing to reverse.")
    else:
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}",
                       _text_property_revert_patch())
        print("(only executed live if step 3's conversion succeeds)")

    # STEP 7: only if step 3 was blocked, blank the value and retry the conversion.
    _banner(7, "If step 3 was blocked, blank the test company's value and retry the conversion")
    if armed and step1_ok and step3_ok is False:
        blank_status, _ = _patch_company_property_live(company_id, "")
        print(f"HTTP {blank_status} — Reading: blanked the test company's disposable-property value.")
        retry_status, retry_body = _patch_property_live(enum_patch)
        lifted = retry_status == 200
        verdict["emptying_lifts_block"] = "yes" if lifted else f"no (HTTP {retry_status})"
        print(f"HTTP {retry_status} — Reading: retry after emptying "
              f"{'SUCCEEDED' if lifted else 'still blocked'}.")
        if lifted:
            step3_ok = True  # the property is now live as enumeration for steps 8/9
    elif armed and step1_ok:
        print("Skipped: step 3 already succeeded, nothing to isolate.")
    elif armed:
        print("Skipped: step 1 did not succeed.")
    else:
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                       {"properties": {PROBE_PROPERTY_NAME: ""}})
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}", enum_patch)
        print("(only executed live if step 3's conversion was blocked)")

    # STEP 8: archive the property, then immediately attempt to recreate it under the SAME
    # name with a DIFFERENT type (enumeration, regardless of what step 3 left it as).
    _banner(8, "Archive the disposable property, then attempt to recreate it under the same name")
    if armed and step1_ok:
        archive_status = _archive_property_live()
        archived = archive_status in (200, 204)
        if archived and "property" in residue:
            residue.remove("property")
        print(f"HTTP {archive_status} — Reading: archive {'ok' if archived else 'FAILED'}.")
        recreate_spec = _enum_property_spec_for_recreate()
        recreate_status, recreate_body = _create_property_live(recreate_spec)
        reusable = recreate_status == 201
        verdict["name_immediately_reusable"] = "yes" if reusable else f"no (HTTP {recreate_status})"
        print(f"HTTP {recreate_status} — Reading: name reuse {'ALLOWED' if reusable else 'BLOCKED'}.")
        if reusable:
            residue.append("property")
    elif armed:
        print("Skipped: step 1 did not succeed.")
    else:
        _dry_run_line("DELETE", f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}")
        _dry_run_line("POST", f"{BASE_URL}/crm/v3/properties/companies", _enum_property_spec_for_recreate())

    # STEP 9: cleanup — archive whatever remains, print residual state.
    _banner(9, "Cleanup: archive whatever remains and print residual state")
    if armed:
        if "property" in residue:
            final_status = _archive_property_live()
            if final_status in (200, 204, 404):
                residue.remove("property")
            print(f"HTTP {final_status} — Reading: final archive "
                  f"{'ok' if final_status in (200, 204, 404) else 'FAILED'}.")
        if step1_ok:
            blank_status, _ = _patch_company_property_live(company_id, "")
            print(f"HTTP {blank_status} — Reading: cleared test company's disposable-property value.")
    else:
        _dry_run_line("DELETE", f"{BASE_URL}/crm/v3/properties/companies/{PROBE_PROPERTY_NAME}")
        _dry_run_line("PATCH", f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                       {"properties": {PROBE_PROPERTY_NAME: ""}})

    verdict["recommended_migration_shape"] = _recommend_shape(verdict) if armed else NOT_OBSERVED
    return verdict, residue


def main(argv=None) -> int:
    # No arguments accepted at all — there is no legitimate reason for this script to be
    # pointable at anything other than PROBE_PROPERTY_NAME / the resolved test company.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this probe.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    assert _property_name_ok(_resolved_property_name()), "probe target drifted from the module constant"

    company_id = _resolved_test_company_id()
    if not _test_company_ok(company_id):
        print("REFUSED: no valid test company id found in TEST_COMPANY_IDS — step 2 writes a "
              "record value, and the record-write allowlist must govern it. No API call made.")
        return 1

    armed = _writes_allowed()
    if not armed:
        print("DRY RUN (default) — the full probe ladder below is a PREVIEW only; zero HTTP "
              "calls are made. Set DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true to arm.")
    else:
        print(f"ARMED — running the live 9-step ladder against test company {company_id}.")

    verdict, residue = run_ladder(company_id, armed)

    _print_verdict(verdict)
    _print_residue(residue)

    if armed and residue:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
