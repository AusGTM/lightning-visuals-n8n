"""One-off operator helper for 41-03 Task 2 steps 3 and 4: bounce the two rebuilt
workflows, then read back the RUNNING content and prove two things.

Why a helper: n8n_control.set_active() and n8n_read.read_write_safety() are library
functions with no CLI, and the two facts step 4 needs (the June candidate constant is
live, and ALLOW_HUBSPOT_RECORD_WRITES is still disarmed) must come from a read-back
AFTER the activate, not from the mutation's own echo.

Read-only except for the deactivate/activate pair, which is the bounce itself.
Writes the evidence to 41-bounce-readback.json.

Run:
  !.venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/bounce_and_verify.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("operator-claude-plugin/scripts").resolve()))

import config_gate  # noqa: E402
import n8n_control  # noqa: E402
import n8n_read  # noqa: E402

TARGETS = ["LV Enrichment (Cloud template)", "LV Scheduled Maintenance (Cloud)"]
WRITE_FLAG = "ALLOW_HUBSPOT_RECORD_WRITES"
# The June fold's marker: Plan 41-01 embedded the candidate table under this key.
JUNE_MARKERS = ("june_2026", "june_candidates")


def main() -> int:
    config = config_gate.load_config()
    listing = n8n_read.list_workflows(config)
    workflows = listing.get("data", listing) if isinstance(listing, dict) else listing
    by_name = {w.get("name"): w.get("id") for w in workflows if isinstance(w, dict)}

    missing = [n for n in TARGETS if n not in by_name]
    if missing:
        print(f"FAILED — workflow(s) not found by name: {missing}")
        print(f"Names available: {sorted(n for n in by_name if n)}")
        return 1

    evidence = {"bounced": [], "readback": {}}

    for name in TARGETS:
        wid = by_name[name]
        print(f"\n=== {name} (id={wid})")
        down = n8n_control.set_active(wid, False, config)
        print(f"  deactivate: verdict={down.verdict} observed={down.observed}")
        up = n8n_control.set_active(wid, True, config)
        print(f"  activate:   verdict={up.verdict} observed={up.observed}")
        evidence["bounced"].append(
            {"name": name, "id": wid,
             "deactivate_verdict": str(down.verdict), "activate_verdict": str(up.verdict),
             "observed_active": up.observed}
        )

    # Read back AFTER both bounces — this is the running content, not the mutation echo.
    for name in TARGETS:
        wid = by_name[name]
        body = n8n_read.get_workflow(config, wid)
        safety = n8n_read.read_write_safety(body, WRITE_FLAG)
        blob = json.dumps(body)
        june_hits = sorted({m for m in JUNE_MARKERS if m in blob})
        evidence["readback"][name] = {
            "id": wid,
            "write_safety": safety,
            "june_markers_present": june_hits,
        }
        print(f"\n=== read-back: {name}")
        print(f"  {WRITE_FLAG}: {json.dumps(safety)}")
        print(f"  June markers found: {june_hits or 'NONE'}")

    out = Path(__file__).with_name("41-bounce-readback.json")
    out.write_text(json.dumps(evidence, indent=2, default=str))
    print(f"\nEvidence written: {out}")

    enrich = evidence["readback"][TARGETS[0]]
    armed_literal = str(enrich["write_safety"].get("value", "")).lower()
    ok_disarmed = "false" in armed_literal
    ok_june = bool(enrich["june_markers_present"])
    print("\n--- gate ---")
    print(f"  enrichment disarmed:      {'PASS' if ok_disarmed else 'FAIL'} ({armed_literal or 'unknown'})")
    print(f"  June constant is running: {'PASS' if ok_june else 'FAIL'}")
    return 0 if (ok_disarmed and ok_june) else 1


if __name__ == "__main__":
    raise SystemExit(main())
