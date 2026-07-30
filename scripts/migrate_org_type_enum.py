#!/usr/bin/env python3
"""scripts/migrate_org_type_enum.py

Phase 21 Task 2 — the gated `lv_org_type` text-to-enumeration migration.

Implements exactly ONE migration shape: IN PLACE conversion (PATCH the existing
`lv_org_type` property's `type`/`fieldType`/`options`), per the operator's live probe
verdict recorded in `.planning/phases/21-transport-schema-hygiene/21-03-SUMMARY.md`
(`recommended_migration_shape: in place (cheap reverse-PATCH rollback confirmed)`). The
other two shapes the probe considered (archive-and-recreate, shadow-property-under-a-new-
name) are NOT implemented here — the verdict ruled them out, and an unexercised branch of
a one-way-door migration is a liability, not a hedge.

This is the ONE script in this repo allowed to name the real `lv_org_type` property in a
request URL or body (every other org-type script in this migration — the probe, the
inventory — deliberately never does).

Same idiom as scripts/sync_hubspot_properties.py: env-gated, dry-run-by-default,
`_has_credentials()` skip-to-exit-0, the portal guard, and the two-key write gate
(DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true). Adds two gates unique to this
one-way door, both refusing BEFORE any HTTP call:

  - Runbook gate: `docs/ORG-TYPE-ENUM-MIGRATION.md` must exist and carry all four
    machine-read markers (MIGRATION-SHAPE, ROLLBACK-COMMAND, VERDICT-SOURCE,
    REFERENCE-ARTIFACTS) with real, non-placeholder values. This is "rollback documented
    before the migration runs," enforced structurally rather than by memory.
  - Pre-flight inventory gate: the newest committed
    `config/hubspot_migration/org_type_inventory-*.json` must show zero
    out-of-vocabulary values and must have been produced against the taxonomy version
    currently loaded — otherwise a stray value could be rejected or silently orphaned by
    the conversion.

The option set is derived from `src/taxonomy.py`'s `ORG_TYPES` — never a hand-typed
vocabulary literal — so the schema cannot drift from what `normalize_org_type()` is
allowed to emit.

Usage:
    python scripts/migrate_org_type_enum.py               # forward dry-run (default)
    DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
        python scripts/migrate_org_type_enum.py            # armed forward conversion

    python scripts/migrate_org_type_enum.py --rollback     # reverse dry-run (default)
    DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
        python scripts/migrate_org_type_enum.py --rollback # armed reverse conversion

Both directions are a single PATCH against the live `lv_org_type` property (per the
probe's confirmed cheap reverse-PATCH rollback) — there is no separate rollback script
for this migration; `--rollback` on this same script IS the rollback command the runbook
names. The forward direction is additionally gated by the runbook + inventory gates
above; `--rollback` is not (reverting to a permissive text type cannot itself reject or
orphan a value the way a forward text->enum conversion can).

ARMED runs are classifier-blocked for agents in this environment (Phase 20 Plan 04
precedent) — this script is built and dry-run here; the armed invocation (either
direction) is an operator action (Operator Runbook Section C).
"""
import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src import taxonomy  # noqa: E402

MIGRATION_DIR = ROOT / "config" / "hubspot_migration"
RUNBOOK_PATH = ROOT / "docs" / "ORG-TYPE-ENUM-MIGRATION.md"

# Portal guard — same constant convention as every other schema-mutating script.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# The ONE property this script is allowed to name in a request. Not a CLI argument —
# there is no legitimate reason for this script to be pointable at anything else.
TARGET_OBJECT_TYPE = "companies"
TARGET_PROPERTY_NAME = "lv_org_type"

MARKER_KEYS = ["MIGRATION-SHAPE", "ROLLBACK-COMMAND", "VERDICT-SOURCE", "REFERENCE-ARTIFACTS"]
PLACEHOLDER_VALUES = {"", "tbd", "todo", "n/a", "na", "placeholder", "see probe", "xxx"}


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    # Identical two-key gate to sync_hubspot_properties.py — never a third gate name.
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow


# --- runbook gate ------------------------------------------------------------------------

def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


def parse_runbook_markers(text: str) -> dict:
    """Returns {marker_key: value_or_None}. A marker is present only if its line matches
    `KEY: <non-empty>` — multiple occurrences take the first match (mirrors how a human
    reads top-to-bottom)."""
    found = {}
    for key in MARKER_KEYS:
        # `[ \t]*` (never `\s*`) after the colon — `\s` matches newlines too, which would
        # let an empty value's match greedily swallow the next marker's entire line.
        match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", text, re.MULTILINE)
        found[key] = match.group(1).strip() if match else None
    return found


def runbook_gate_ok(path: "Path | None" = None) -> tuple:
    """(ok, message). Refuses if the runbook is missing, or any of the four markers is
    absent or placeholder-valued — this IS the structural enforcement of "rollback
    documented before the migration runs," not satisfiable by a file that merely exists.

    `path` defaults to the CURRENT value of the module-level `RUNBOOK_PATH` global
    (looked up at call time, not bound at def time) so tests can `monkeypatch.setattr`
    the module constant and have `main()`'s no-arg call pick it up."""
    path = path if path is not None else RUNBOOK_PATH
    if not path.exists():
        return False, f"runbook not found at {path} — write it before arming any migration."
    markers = parse_runbook_markers(path.read_text())
    problems = []
    for key in MARKER_KEYS:
        value = markers.get(key)
        if value is None:
            problems.append(f"marker {key!r} is missing")
        elif _is_placeholder(value):
            problems.append(f"marker {key!r} has a placeholder value ({value!r})")
    if problems:
        return False, "runbook gate refused: " + "; ".join(problems)
    return True, "runbook gate ok: all four markers present with real values."


# --- pre-flight inventory gate ------------------------------------------------------------

def find_latest_inventory(directory: "Path | None" = None) -> "Path | None":
    # Same call-time global lookup as runbook_gate_ok, for the same reason.
    directory = directory if directory is not None else MIGRATION_DIR
    candidates = sorted(directory.glob("org_type_inventory-*.json"))
    return candidates[-1] if candidates else None


def inventory_gate_ok(path) -> tuple:
    """(ok, message). Refuses if no artifact is found, if its out-of-vocabulary bucket is
    non-empty (printing the offending values and sample ids), or if it was produced
    against a different taxonomy version than the one currently loaded."""
    if path is None:
        return False, ("no committed org_type_inventory-*.json artifact found — run "
                        "scripts/inventory_org_type_values.py and commit its output first.")
    data = json.loads(Path(path).read_text())
    if data.get("taxonomy_version") != taxonomy.VERSION:
        return False, (f"inventory {path} was produced against taxonomy version "
                        f"{data.get('taxonomy_version')!r}, but {taxonomy.VERSION!r} is "
                        "currently loaded — re-run the inventory before arming.")
    out_of_vocab = data.get("out_of_vocabulary") or {}
    if out_of_vocab:
        lines = [f"  {value!r}: count={info.get('count')} "
                 f"samples={info.get('sample_record_ids')}"
                 for value, info in out_of_vocab.items()]
        return False, ("pre-flight gate refused: out-of-vocabulary values present in "
                        f"{path}:\n" + "\n".join(lines) +
                        "\nRemediate (map each to a canonical key or the default) before "
                        "arming.")
    return True, f"pre-flight gate ok: {path} shows zero out-of-vocabulary values."


# --- taxonomy-derived option set (never re-typed as a literal vocabulary) ----------------

def enum_options() -> list:
    return [
        {"label": key, "value": key, "displayOrder": idx, "hidden": False}
        for idx, key in enumerate(taxonomy.ORG_TYPES.keys())
    ]


def forward_patch_body() -> dict:
    return {"type": "enumeration", "fieldType": "select", "options": enum_options()}


def rollback_patch_body() -> dict:
    return {"type": "string", "fieldType": "text", "options": []}


def _options_values(options) -> set:
    return {str(o.get("value")) for o in (options or [])}


# --- live HTTP helpers ---------------------------------------------------------------------

def _get_property_live() -> dict:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{TARGET_OBJECT_TYPE}/{TARGET_PROPERTY_NAME}",
                      headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _patch_property_live(patch: dict):
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.patch(f"{BASE_URL}/crm/v3/properties/{TARGET_OBJECT_TYPE}/{TARGET_PROPERTY_NAME}",
                        headers=hs_headers(), json=patch, timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = r.text[:500]
    return r.status_code, body


# --- manifest -------------------------------------------------------------------------------

def manifest_path(run_id: str, directory: Path = MIGRATION_DIR) -> Path:
    return directory / f"org-type-enum-manifest-{run_id}.json"


def write_manifest(run_id: str, entry: dict, directory: Path = MIGRATION_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = manifest_path(run_id, directory)
    path.write_text(json.dumps(entry, indent=2, sort_keys=True, default=str) + "\n")
    return path


# --- printing --------------------------------------------------------------------------------

def _print_plan(action: str, patch: dict) -> None:
    url = f"https://api.hubapi.com/crm/v3/properties/{TARGET_OBJECT_TYPE}/{TARGET_PROPERTY_NAME}"
    print(f"[{action}] Would PATCH {url}")
    print(f"Body: {json.dumps(patch, indent=2, sort_keys=True)}")
    if action == "FORWARD":
        print(f"Resolved option set ({len(patch['options'])} values): "
              f"{[o['value'] for o in patch['options']]}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollback", action="store_true",
                         help="Reverse the conversion: PATCH lv_org_type back to "
                              "type=string, fieldType=text, options=[].")
    parser.add_argument("--confirm", default=None,
                         help="Pre-supplied typed confirmation (for non-interactive "
                              "callers). Must be exactly 'yes' to proceed once armed.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this migration.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    action = "ROLLBACK" if args.rollback else "FORWARD"
    patch = rollback_patch_body() if args.rollback else forward_patch_body()

    if action == "FORWARD":
        # The two gates unique to this one-way door — both refuse before any HTTP call.
        # --rollback is exempt: reverting to a permissive text type cannot itself reject
        # or orphan a value the way a forward text->enum conversion can, so neither gate
        # applies to un-arming the door.
        ok, message = runbook_gate_ok()
        if not ok:
            print(f"REFUSED: {message}")
            return 1
        inventory_path = find_latest_inventory()
        ok, message = inventory_gate_ok(inventory_path)
        if not ok:
            print(f"REFUSED: {message}")
            return 1

    _print_plan(action, patch)

    armed = _writes_allowed()
    if not armed:
        print("DRY RUN (default) — no writes made. Set DRY_RUN=false AND "
              "ALLOW_HUBSPOT_PROPERTY_WRITES=true to arm.")
        return 0

    confirm = args.confirm if args.confirm is not None else input(
        f"Type 'yes' to {action.lower()} the live lv_org_type property: ")
    if confirm.strip().lower() != "yes":
        print("REFUSED: confirmation not given — no writes made.")
        return 1

    run_id = str(uuid.uuid4())
    pre_change = _get_property_live()
    status, response_body = _patch_property_live(patch)
    if status != 200:
        print(f"FAILED: PATCH returned HTTP {status} — no manifest written, no further "
              f"assertions run. Response: {response_body}")
        return 1

    post_change = _get_property_live()
    intended_options = _options_values(patch["options"])
    live_options = _options_values(post_change.get("options"))
    confirmed = (
        post_change.get("type") == patch["type"]
        and post_change.get("fieldType") == patch["fieldType"]
        and live_options == intended_options
    )
    if not confirmed:
        print(f"POST-WRITE CONFIRMATION FAILED — the live property does not match the "
              f"intended {action.lower()} shape. This is a PARTIAL MIGRATION; treat it as "
              f"unresolved, not success. Live: {post_change}")
        return 1

    manifest = write_manifest(run_id, {
        "run_id": run_id,
        "action": action.lower(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pre_change_property": pre_change,
        "patch_body": patch,
        "post_change_property": post_change,
    })
    print(f"CONFIRMED: {action.lower()} succeeded — live property matches the intended shape.")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
