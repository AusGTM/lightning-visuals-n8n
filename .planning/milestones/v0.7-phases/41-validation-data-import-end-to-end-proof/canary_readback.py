"""One-off operator helper for 41-03 Task 3: a read-only before/after snapshot of the
canary run.

Captures three things in one call: the live write-safety state on the armed enrichment
workflow (ALLOW_HUBSPOT_RECORD_WRITES / ALLOW_HUBSPOT_CREATE / TEST_RECORD_IDS /
TEST_RECORD_DOMAINS -- this settles the plan's must-settle question about whether the
window auto-closes after one dispatch), the recent-executions page filtered to the two
workflow ids (tick-split and wall-clock as machine-readable timestamps), and the five
canary companies' lv_* properties (the before/after pair Melbourne Racing Club's
acceptance criterion needs).

GET only -- n8n_read + src.hubspot_client.get_record, nothing else reachable. Writes
41-canary-readback-<label>.json next to this script.

Run once before queuing and once ~30min after (adjust the label):
  !.venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/canary_readback.py before
  !.venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/canary_readback.py after
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "operator-claude-plugin" / "scripts"))

import config_gate  # noqa: E402
import n8n_read  # noqa: E402

from src.hubspot_client import get_record  # noqa: E402
from tests.scoring_fixtures import FIT_SCORE_PROPS  # noqa: E402

TARGETS = ["LV Enrichment (Cloud template)", "LV Scheduled Maintenance (Cloud)"]
WRITE_FLAGS = ["ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
               "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"]
CANARY_IDS = ["9604614548", "15008671672", "16047156820", "17861423879", "15274105699"]
# FIT_SCORE_PROPS plus D-07's canonical-write scope fields it doesn't already carry,
# plus the queue/status pair the SJ-3 filter reads (lv_enrichment_status NEQ "running").
EXTRA_PROPS = ["lv_content_type", "lv_employee_band", "lv_sponsorship_reliant",
               "lv_enrichment_status", "lv_enrichment_requested"]
READ_PROPS = FIT_SCORE_PROPS + EXTRA_PROPS


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("before", "after"):
        print("usage: canary_readback.py before|after")
        return 1
    label = sys.argv[1]

    config = config_gate.load_config()
    listing = n8n_read.list_workflows(config)
    workflows = listing.get("data", listing) if isinstance(listing, dict) else listing
    by_name = {w.get("name"): w.get("id") for w in workflows if isinstance(w, dict)}
    missing = [n for n in TARGETS if n not in by_name]
    if missing:
        print(f"FAILED - workflow(s) not found by name: {missing}")
        print(f"Names available: {sorted(n for n in by_name if n)}")
        return 1

    evidence = {"label": label, "write_safety": {}, "recent_executions": {}, "companies": {}}

    enrich_id = by_name[TARGETS[0]]
    enrich_body = n8n_read.get_workflow(config, enrich_id)
    for flag in WRITE_FLAGS:
        evidence["write_safety"][flag] = n8n_read.read_write_safety(enrich_body, flag)

    page = n8n_read.recent_executions(config) or []
    for name in TARGETS:
        wid = by_name[name]
        hits = [e for e in page if isinstance(e, dict) and str(e.get("workflowId")) == str(wid)]
        evidence["recent_executions"][name] = [
            {"id": e.get("id"), "status": e.get("status"), "finished": e.get("finished"),
             "startedAt": e.get("startedAt"), "stoppedAt": e.get("stoppedAt")}
            for e in hits
        ]

    for cid in CANARY_IDS:
        try:
            evidence["companies"][cid] = get_record("companies", cid, READ_PROPS)["properties"]
        except Exception as exc:  # noqa: BLE001 -- a read failure is evidence, not a crash
            evidence["companies"][cid] = {"error": str(exc)}

    out = Path(__file__).with_name(f"41-canary-readback-{label}.json")
    out.write_text(json.dumps(evidence, indent=2, default=str))
    print(f"\nEvidence written: {out}")

    rw = evidence["write_safety"].get("ALLOW_HUBSPOT_RECORD_WRITES", {})
    ids = evidence["write_safety"].get("TEST_RECORD_IDS", {})
    id_count = len([v for v in (ids.get("value") or "").split(",") if v])
    print(f"\n--- write safety ({label}) ---")
    print(f"  ALLOW_HUBSPOT_RECORD_WRITES: {json.dumps(rw)}")
    print(f"  TEST_RECORD_IDS count: {id_count}")
    print(f"  ALLOW_HUBSPOT_CREATE: {json.dumps(evidence['write_safety'].get('ALLOW_HUBSPOT_CREATE'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
