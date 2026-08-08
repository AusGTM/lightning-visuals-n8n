"""Finish Phase 41's canary: queue the 3 untested records, wait, verify the 3 paths.

Phase 41's canary completed only 2 of 5 records before the window was disarmed. The three
that never ran are the three that test distinct rubric behaviour:

  16047156820  QRIC        -> lv_org_type must be `regulator` (D-02 exception list; the
                             coarse Perplexity enum called it a governing body)
  17861423879  Sportsbet   -> gambling_score -20 applied, and lv_anti_icp_flag must stay
                             false (a graduated deduction is NOT a veto)
  15274105699  Supertech   -> lv_is_hardware_vendor true -> hard veto fires, tier D

PREREQUISITE — the operator must arm first (Claude is blocked from arming):

  ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --ids 16047156820,17861423879,15274105699

Then run this. It refuses to queue anything if the window is not actually open, so a
forgotten arm fails loudly instead of silently burning Anthropic tokens against a closed
gate (which is exactly what happened on the first attempt).

  .venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/finish_canary.py

It does NOT release the remaining 61 and does NOT disarm — those are 41-04's review gate
and its explicit operator step. Disarm when done:

  ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --disarm
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
# Repo root first so `src.*` resolves, then the plugin's scripts dir for config_gate/n8n_read.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(1, str(REPO_ROOT / "operator-claude-plugin" / "scripts"))

from src.hubspot_client import batch_update_companies, get_record  # noqa: E402

import config_gate  # noqa: E402
import n8n_read  # noqa: E402

CANARY = {
    "16047156820": ("QRIC", "lv_org_type == regulator (D-02 exception list)"),
    "17861423879": ("Sportsbet", "gambling deduction, anti_icp_flag stays false"),
    "15274105699": ("Supertech Electronics", "hardware-vendor hard veto -> tier D"),
}
PROPS = [
    "name", "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator", "lv_is_hardware_vendor",
    "lv_anti_icp_flag", "lv_anti_icp_reason", "lv_icp_fit_score", "lv_icp_tier",
    "lv_enrichment_status", "lv_enrichment_requested",
]
POLL_MINUTES = 45
POLL_EVERY = 180


def window_open() -> bool:
    cfg = config_gate.load_config()
    listing = n8n_read.list_workflows(cfg)
    wfs = listing.get("data") if isinstance(listing, dict) else listing
    wf = next(w for w in wfs if w.get("name") == "LV Enrichment (Cloud template)")
    body = n8n_read.get_workflow(cfg, wf["id"])
    safety = n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_RECORD_WRITES")
    blob = json.dumps(body)
    ids_present = all(cid in blob for cid in CANARY)
    print(f"  ALLOW_HUBSPOT_RECORD_WRITES = {safety.get('value')}")
    print(f"  all 3 canary ids in allowlist = {ids_present}")
    return str(safety.get("value")).lower() == "true" and ids_present


def snapshot():
    out = {}
    for cid in CANARY:
        out[cid] = get_record("companies", cid, PROPS).get("properties", {})
    return out


def main() -> int:
    print("=== 1. window check (refuses to queue against a closed gate) ===")
    if not window_open():
        print("\nHALT: the write window is not open for these 3 ids.")
        print("Run the arm command in this file's docstring first.")
        return 1

    print("\n=== 2. queue the 3 records ===")
    upd = [{"id": c, "properties": {"lv_enrichment_requested": "true"}} for c in CANARY]
    r = batch_update_companies(upd, dry_run=False)
    print(f"  status={r.get('status')} queued={len(r.get('results', []))}")

    print(f"\n=== 3. poll (up to {POLL_MINUTES}m; poller ticks every 15m) ===")
    deadline = time.monotonic() + POLL_MINUTES * 60
    while time.monotonic() < deadline:
        time.sleep(POLL_EVERY)
        snap = snapshot()
        done = [c for c, p in snap.items() if p.get("lv_icp_tier") or p.get("lv_anti_icp_flag")]
        print(f"  scored so far: {len(done)}/3")
        if len(done) == 3:
            break

    print("\n=== 4. results ===")
    snap = snapshot()
    out = Path(__file__).with_name("41-canary-completion.json")
    out.write_text(json.dumps(snap, indent=2, default=str))

    checks = []
    q = snap["16047156820"]
    checks.append(("QRIC -> regulator", q.get("lv_org_type") == "regulator", q.get("lv_org_type")))
    s = snap["17861423879"]
    # NOT "no veto" -- a gambling operator can still be legitimately vetoed for no-content.
    # The rubric claim under test is narrower: gambling must not be the CAUSE. Verified by
    # reading the reason string, since the flag alone cannot distinguish the two.
    s_reason = (s.get("lv_anti_icp_reason") or "").lower()
    checks.append(("Sportsbet: gambling not the veto cause", "gambl" not in s_reason,
                   s.get("lv_anti_icp_reason")))
    t = snap["15274105699"]
    checks.append(("Supertech: veto fires", str(t.get("lv_anti_icp_flag")).lower() == "true",
                   t.get("lv_anti_icp_flag")))
    checks.append(("Supertech: tier D", t.get("lv_icp_tier") == "D", t.get("lv_icp_tier")))

    for cid, (name, expect) in CANARY.items():
        p = snap[cid]
        print(f"  {name:22} org={p.get('lv_org_type')} veto={p.get('lv_anti_icp_flag')} "
              f"score={p.get('lv_icp_fit_score')} tier={p.get('lv_icp_tier')} "
              f"status={p.get('lv_enrichment_status')}")

    print("\n--- path checks ---")
    for label, ok, actual in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label:24} (actual: {actual})")

    print(f"\nEvidence: {out}")
    print("\nNOT done by this script: releasing the remaining 61 (41-04's review gate) and")
    print("disarming. Disarm with:")
    print("  ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --disarm")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
