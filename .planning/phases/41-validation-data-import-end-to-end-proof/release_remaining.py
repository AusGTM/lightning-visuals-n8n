"""41-04 Task 2: release the remaining 61 June records, then sweep parity.

The canary (41-03 Task 3) is COMPLETE at 5/5 with every rubric path verified — see
41-CANARY-EVIDENCE.md. This is the step 41-04's review gate authorizes.

PREREQUISITE — the operator must arm (Claude is blocked from arming):

  ALLOW_N8N_ARM=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); \
import sys; sys.argv=['june_run_arm.py','--ids','<ALL_66_COMMA_SEPARATED>']; \
import runpy; runpy.run_path('scripts/june_run_arm.py', run_name='__main__')"

The id list is in 41-id-resolution.json; this script prints it if the window is closed, so
it can be pasted straight into the arm command.

Then:

  .venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/release_remaining.py

Resumable: it only queues records that have not already scored, so re-running after an
interruption picks up where it left off rather than re-spending on finished records.

It does NOT disarm — that stays an explicit operator step:

  .venv/bin/python scripts/june_run_arm.py --disarm
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(1, str(REPO_ROOT / "operator-claude-plugin" / "scripts"))

from src.hubspot_client import batch_update_companies, get_record  # noqa: E402

import config_gate  # noqa: E402
import n8n_read  # noqa: E402

HERE = Path(__file__).parent
CANARY = {"9604614548", "15008671672", "16047156820", "17861423879", "15274105699"}
PROPS = ["name", "lv_org_type", "lv_produces_content", "lv_revenue_band",
         "lv_anti_icp_flag", "lv_anti_icp_reason", "lv_icp_fit_score", "lv_icp_tier",
         "lv_enrichment_status", "lv_enrichment_provenance"]
BATCH = 100          # HubSpot batch-update cap; batch_update_companies refuses more
POLL_MINUTES = 240   # 61 records x 2 sequential Anthropic calls through a 15-min poller
POLL_EVERY = 300


def all_ids() -> list:
    d = json.loads((HERE / "41-id-resolution.json").read_text())
    recs = d.get("records", d if isinstance(d, list) else [])
    out = []
    for r in recs:
        rid = str(r.get("resolved_id") or r.get("id") or r.get("hubspot_id") or "").strip()
        if rid:
            out.append(rid)
    return out


def window_state():
    cfg = config_gate.load_config()
    listing = n8n_read.list_workflows(cfg)
    wfs = listing.get("data") if isinstance(listing, dict) else listing
    wf = next(w for w in wfs if w.get("name") == "LV Enrichment (Cloud template)")
    body = n8n_read.get_workflow(cfg, wf["id"])
    safety = n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_RECORD_WRITES")
    return str(safety.get("value")).lower() == "true", json.dumps(body)


def scored(cid: str) -> bool:
    p = get_record("companies", cid, PROPS).get("properties", {})
    return bool(p.get("lv_icp_tier") or p.get("lv_anti_icp_flag"))


def main() -> int:
    ids = all_ids()
    print(f"=== resolved ids: {len(ids)} ===")

    print("\n=== window check ===")
    is_open, blob = window_state()
    print(f"  ALLOW_HUBSPOT_RECORD_WRITES = {is_open}")
    if not is_open:
        print("\nHALT: window closed. Arm first with this id list:\n")
        print(",".join(ids))
        return 1

    missing = [c for c in ids if c not in blob]
    if missing:
        print(f"\nHALT: {len(missing)} id(s) are not in the arm allowlist, so their writes")
        print("would be silently blocked. Re-arm with the full list above.")
        return 1

    print("\n=== selecting records that still need scoring (resumable) ===")
    todo = []
    for c in ids:
        if c in CANARY:
            continue
        if not scored(c):
            todo.append(c)
    print(f"  already scored: {len(ids) - len(CANARY) - len(todo)} | to queue: {len(todo)}")

    if not todo:
        print("  nothing to queue — all records already scored.")
    else:
        print("\n=== queueing ===")
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            upd = [{"id": c, "properties": {"lv_enrichment_requested": "true"}} for c in chunk]
            r = batch_update_companies(upd, dry_run=False)
            print(f"  batch {i // BATCH + 1}: status={r.get('status')} n={len(chunk)}")

        print(f"\n=== poll (up to {POLL_MINUTES}m) ===")
        deadline = time.monotonic() + POLL_MINUTES * 60
        while time.monotonic() < deadline:
            time.sleep(POLL_EVERY)
            done = sum(1 for c in todo if scored(c))
            print(f"  scored: {done}/{len(todo)}")
            if done == len(todo):
                break

    print("\n=== final state ===")
    snap = {c: get_record("companies", c, PROPS).get("properties", {}) for c in ids}
    (HERE / "41-release-state.json").write_text(json.dumps(snap, indent=2, default=str))

    landed = [c for c, p in snap.items() if p.get("lv_icp_fit_score") not in (None, "")]
    parked = [c for c, p in snap.items() if p.get("lv_enrichment_status") == "needs_review"]
    vetoed = [c for c, p in snap.items() if str(p.get("lv_anti_icp_flag")).lower() == "true"]
    noband = [c for c, p in snap.items() if not p.get("lv_revenue_band")]
    print(f"  landed (has score): {len(landed)}/{len(ids)}")
    print(f"  parked to review:   {len(parked)}   (D-12 accepts this)")
    print(f"  hard-vetoed:        {len(vetoed)}   (rubric working on real data)")
    print(f"  no revenue band:    {len(noband)}   (F1 option-c residue)")
    print(f"\nEvidence: {HERE / '41-release-state.json'}")

    print("\nNEXT:")
    print("  1. parity sweep over the landed population:")
    print(f"     PARITY_SAMPLE_IDS={','.join(landed[:5])}... PARITY_REQUIRE_PROVENANCE=true \\")
    print("       .venv/bin/python scripts/run_scoring_parity.py")
    print("  2. DISARM (non-deferrable):")
    print("     .venv/bin/python scripts/june_run_arm.py --disarm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
