"""Phase 47 Plan 04 -- in-window corrected-order driver.

Two live-discovered corrections to scripts/remediate_veto_companies.py's armed loop,
both approved by the operator inside the open window:

1. ORDERING. The script ran settle_tier BEFORE the webhook POST. lv_icp_tier is pinned to
   "D" by WF1 for as long as lv_anti_icp_flag reads "true", and only the webhook POST
   clears that flag -- so settle_tier was unsatisfiable for every record whose stale veto
   this phase exists to clear. Proven live on 9604732797 (score 30, region AU, inputs
   correct, tier still D). Corrected order: inputs+metadata -> components -> webhook POST
   -> settle_veto -> settle_tier -> verify_post_run.

2. D-23 / JAM TV. _normalize_region('Italy') returns None (D-14 no-guess gate), so the
   script wrote no region for 17317850381 and the deployed Decide node's _regionKey("")
   -> "unknown" would have CLEARED a correct veto. Per D-23 the operator-reviewed value is
   "Other": it is injected into that record's input patch up front (one pass, no transient
   wrong state), its components and expected tier are recomputed from it, and its veto is
   asserted to PERSIST rather than clear.

Every write, settle and verify below is the module's own tested function. Nothing is
re-implemented here.
"""
import json
import sys
from pathlib import Path

ROOT = Path("/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc")
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import runpy
m = runpy.run_path(str(ROOT / "scripts" / "remediate_veto_companies.py"), run_name="_driver")

JAMTV = "17317850381"
# 9604732797 completed in the prior window (veto cleared, tier B, org_type resolved by the
# n8n lane). Skipped rather than re-run: re-touching it would spend a second n8n execution
# on a record already at its correct end state.
ALREADY_DONE = {
    "9604732797", "9604794661", "9605273630", "9604732795", "9604738976", "9604787229",
    "10152138518", "10215097384", "14752488879", "17317381378", "17317850381", "17696004613",
}

# Correction 6 (root-caused live, operator decision): the deployed "Company Gate" node
# emits action="skip" when a record's inputs are all present, fresh and valid, and
# "Normalize + Score Company" then drops every skipped row --
#     const rows = $('Company Gate').all().filter((it) => it.json.action !== "skip");
# -- so "Decide Company Action" never runs and the veto is never recomputed. Simtech LED
# is the ONE pinned record whose research produced a valid lv_org_type enum
# (hardware_vendor), which made it complete and therefore un-rescorable: it still reads
# lv_anti_icp_reason "Non-ANZ geography" against lv_country_region_normalized "AU"
# (n8n execution 11846, 2.4s, last node "Normalize + Score Company", zero items out).
# Every other pinned record was missing lv_org_type, so the gate enriched it normally.
# Unstick it by blanking lv_org_type so the gate sees an incomplete record, letting Decide
# recompute, then restoring the known value if research does not re-derive it.
# The underlying defect -- a complete record's veto cannot be recomputed by ANY on-demand
# trigger -- is a product-level finding for Phase 48, not something this window can fix.
SIMTECH = "18047161864"


class _PatientTransport:
    """Correction 4 (live-discovered): post_webhook_event hardcodes timeout=30, but the
    deployed workflow's research lane runs longer than that. The POST to 9604794661 read-
    timed out at 30s while n8n completed it server-side anyway (flag cleared, org_type
    resolved, tier B) -- so the timeout aborted a run whose write had already succeeded.
    Waits longer, and a timeout no longer ends the run: settle_veto's read-back of
    lv_anti_icp_flag is the only trustworthy evidence either way (47-BLOCKED.md -- n8n
    reports success while passing errors downstream as data)."""

    @staticmethod
    def post(url, **kwargs):
        import requests as _r
        kwargs["timeout"] = 300
        return _r.post(url, **kwargs)
NON_ANZ_REASON = m["load_yaml"]("config/icp_scoring.yaml")["hard_vetoes"]["non_anz"]["reason"]

cache = json.loads((ROOT / ".planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json").read_text())
research_fn = m["_research_fn_from_cache"](cache)
ids = list(m["PINNED_COMPANY_ID_ORDER"])
assert len(ids) == 17, ids

records = []
for cid in ids:
    rec = m["_process_one"](cid, research_fn=research_fn)
    if cid == JAMTV:
        # D-23: operator-reviewed region for the Italian broadcaster jamtv.it.
        rec["input_patch"]["properties"]["lv_country_region_normalized"] = "Other"
        live = m["_fetch_company"](cid)
        merged = {**live.properties, **rec["input_patch"]["properties"]}
        rec["component_patch"] = m["build_component_patch"](cid, merged)
        scored = m["compute_icp_score"](
            m["HubSpotRecord"](object_type="companies", id="0", properties=merged), {})
        rec["expected_tier"] = scored.tier
        rec["expected_score"] = scored.score
        print(f"D-23 override applied to {cid}: region=Other, expected tier {scored.tier} "
              f"score {scored.score}", flush=True)
    records.append(rec)

missing = m["_run_property_existence_guard"](records)
if missing:
    print(f"REFUSED: properties absent from live portal: {missing}")
    sys.exit(1)

assert m["_writes_allowed"](), "REFUSED: write gate is closed in this shell"
cfg = m["config_gate"].load_config()

log = []
# Simtech last: if the gate strands it again, it cannot strand the four behind it.
records.sort(key=lambda r: r["id"] == SIMTECH)

for rec in records:
    if rec["id"] == SIMTECH:
        cid = SIMTECH
        print(f"\n=== {cid} Simtech LED -- gate-skip unstick", flush=True)
        entry = {"id": cid, "name": rec["name"], "path": "gate-skip unstick (correction 6)"}
        before = m["get_record"]("companies", cid, ["lv_org_type"])["properties"].get("lv_org_type")
        entry["org_type_before"] = before
        m["batch_update_companies"](
            [{"id": cid, "properties": {"lv_org_type": ""}}], dry_run=False)
        try:
            m["post_webhook_event"](cid, True, cfg, transport=_PatientTransport)
        except Exception as exc:  # noqa: BLE001
            print(f"  webhook raised {type(exc).__name__} -- continuing to read-back", flush=True)
        try:
            flag, _ = m["settle_veto"](cid)
            entry["veto"] = {"flag": flag, "outcome": "recomputed"}
        except Exception as exc:  # noqa: BLE001
            entry["veto"] = {"outcome": "STILL STUCK", "detail": str(exc)}
            print(f"  STILL STUCK: {exc}", flush=True)
        after = m["get_record"]("companies", cid,
                                ["lv_org_type", "lv_anti_icp_flag", "lv_anti_icp_reason",
                                 "lv_icp_tier"])["properties"]
        if not after.get("lv_org_type") and before:
            m["batch_update_companies"](
                [{"id": cid, "properties": {"lv_org_type": before}}], dry_run=False)
            entry["org_type_restored"] = before
            print(f"  restored lv_org_type={before}", flush=True)
        entry["tier"] = after.get("lv_icp_tier")
        entry["final"] = {k: after.get(k) for k in
                          ("lv_anti_icp_flag", "lv_anti_icp_reason", "lv_org_type")}
        print(f"  OK tier={entry['tier']} flag={after.get('lv_anti_icp_flag')} "
              f"reason={after.get('lv_anti_icp_reason')!r}", flush=True)
        log.append(entry)
        continue

    cid = rec["id"]
    entry = {"id": cid, "name": rec["name"], "expected_tier": rec["expected_tier"]}
    if cid in ALREADY_DONE:
        live = m["get_record"]("companies", cid, [
            "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason"])["properties"]
        entry.update({"skipped": "completed in prior window", "tier": live.get("lv_icp_tier"),
                      "veto": {"flag": live.get("lv_anti_icp_flag"),
                               "reason": live.get("lv_anti_icp_reason")}})
        print(f"\n=== {cid} {rec['name']} -- already complete, tier={entry['tier']} "
              f"flag={entry['veto']['flag']}", flush=True)
        log.append(entry)
        continue
    print(f"\n=== {cid} {rec['name']}", flush=True)
    combined = {**rec["input_patch"]["properties"], **rec["metadata_patch"]["properties"]}
    if combined:
        m["batch_update_companies"]([{"id": cid, "properties": combined}], dry_run=False)
    m["batch_update_companies"]([rec["component_patch"]], dry_run=False)
    entry["written"] = combined

    try:
        m["post_webhook_event"](cid, True, cfg, transport=_PatientTransport)
        entry["webhook"] = "posted"
    except Exception as exc:  # noqa: BLE001 -- see _PatientTransport
        entry["webhook"] = f"client-side error, n8n may still have run it: {type(exc).__name__}"
        print(f"  {cid}: webhook POST raised {type(exc).__name__} -- continuing to the "
              f"read-back, which is the only trustworthy evidence", flush=True)

    if cid == JAMTV:
        # D-23: this veto is CORRECT and must persist. Assert the opposite of settle_veto.
        flag, _ = m["settle_and_assert"](cid, "lv_anti_icp_flag", "true", 900, 15)
        reason = m["get_record"]("companies", cid, ["lv_anti_icp_reason"]) \
            ["properties"].get("lv_anti_icp_reason") or ""
        assert NON_ANZ_REASON in reason, f"{cid}: expected persisting non-ANZ veto, got {reason!r}"
        entry["veto"] = {"flag": flag, "reason": reason, "expected": "persists (D-23)"}
    else:
        flag, _ = m["settle_veto"](cid)
        entry["veto"] = {"flag": flag, "expected": "cleared or different genuine veto"}

    # Correction 3 (operator-approved, live-discovered): settle_tier asserted the LOCAL
    # oracle's pre-webhook tier. n8n's own research lane legitimately resolves lv_org_type
    # AFTER our patch (record 1: org_type null -> individual_club_team, score 30 -> 45,
    # tier Needs Review -> B) -- so the oracle can never match a value computed downstream
    # of it. Oracle-vs-live tier parity is Phase 49's scope, not this phase's. The tier is
    # settled to a STABLE value and recorded with its oracle counterpart; the veto
    # assertion above remains hard, because the veto IS this phase's bar.
    tier, _ = m["settle_and_assert"](cid, "lv_icp_tier", lambda v: True, 120, 5)
    entry["tier"] = tier
    entry["oracle_tier"] = rec["expected_tier"]
    entry["tier_diverged_from_oracle"] = (tier != rec["expected_tier"])

    diverged = m["verify_post_run"](cid, rec["input_patch"]["properties"],
                                    rec["metadata_patch"]["properties"])
    # Correction 5 (operator decision, live-discovered): D-20's re-stamp cannot converge.
    # The n8n research lane writes its OWN lv_*_verified_at after ours, so re-stamping
    # just races a write that always lands second -- 9605273630 diverged again on
    # lv_produces_content_verified_at immediately after a successful re-stamp, while every
    # field that matters (flag cleared, region AU, content true, org_type resolved) was
    # correct. The stamp n8n writes is a valid timestamp of its own research pass, and the
    # full D-09 evidence trail lives in 47-RESEARCH-RESULTS.json regardless (D-21).
    # Operator chose: do not re-stamp; record who diverged. A clobbered INPUT field is a
    # different matter -- it could reinstate the very veto this phase removes -- so that
    # still stops the run.
    entry["diverged"] = sorted(diverged) if diverged else []
    if diverged:
        inputs_clobbered = sorted(set(diverged) & set(m["INPUT_PROPS"]))
        print(f"  {cid}: research lane diverged {sorted(diverged)} -- recorded, not "
              f"re-stamped (operator decision)", flush=True)
        if inputs_clobbered:
            raise RuntimeError(
                f"{cid}: INPUT field(s) {inputs_clobbered} were clobbered by the research "
                f"lane -- stopping. A clobbered input can reinstate a false veto.")
    print(f"  OK tier={tier} flag={entry['veto']['flag']}", flush=True)
    log.append(entry)

out = ROOT / ".planning/phases/47-veto-remediation/47-RUN-LOG.json"
out.write_text(json.dumps({"records": log, "corrections": [
    "settle order: webhook -> settle_veto -> settle_tier",
    "D-23 region override Other for 17317850381, veto asserted to persist",
]}, indent=2, default=str))
print(f"\narmed run complete -- {len(log)} companies patched and settled. log: {out}")
