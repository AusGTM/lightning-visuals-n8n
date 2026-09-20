#!/usr/bin/env python3
"""scripts/bounce_n8n_workflows.py — deactivate then activate every deployed cloud workflow
and read it back. A stored PUT never reloads a running workflow (memory
`n8n-stored-vs-running-content`), so every deploy needs this. Follows
the bounce-and-verify shape the phase-61 scale-up driver used (that driver was deleted
at Phase 70 Plan 06; this is where the shape now lives), over all five workflows, and prints the
same table `63-DEPLOY-RECORD.md` recorded by hand.

Reads N8N_URL / N8N_API_KEY from the environment (`set -a; . ./.env; set +a`). Writes nothing
to HubSpot and arms nothing: the only mutations are POST /deactivate and POST /activate. The
two write-safety flags are re-read after the bounce and printed; the script exits 1 if either
reads anything but "false", a node count disagrees with the committed JSON, or (D-70-29) a
workflow's live settings.executionOrder reads anything but "v1" — a live body on the legacy
order is the condition that produced every Gate 8 symptom regardless of what the committed
JSON says, and this is the repo's only read-back step that would ever notice.
"""
import json
import os
import sys
from pathlib import Path

import requests

WORKFLOWS = {  # committed file -> live id
    "n8n/wf_backend_status_cloud.json": "Cj83mOgrIm59oxcX",
    "n8n/wf_contact_ingest_cloud.json": "AwbBeShdPgV48eiY",
    "n8n/wf_enrichment_cloud.json": "950HPb7a1GgSAIyZ",
    "n8n/wf_review_decision_cloud.json": "WBJwoZOo63wzeP69",
    "n8n/wf_scheduled_maintenance_cloud.json": "1fXPuIabz3RsAHgn",
    # Phase 73.1 Plan 09 Task 3 (D-06): the discovery lane's first deploy (a CREATE, not
    # a PUT) minted this live id on 2026-09-18 via deploy_n8n_workflows.py's create path.
    "n8n/wf_suggest_discovery_cloud.json": "VJJBZ2oJ0079MSzG",
}
WRITE_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")

# Phase 75 Plan 04 (D-75-17/D-75-18b). ALLOW_HUBSPOT_RECOMPUTE_WRITES is a FOURTH write
# authority (D-75-16), deliberately allowed to read "true" once the operator flips it
# post-supervised-sweep — it ships "false" in every committed workflow today, but this
# bounce must not treat "true" as a defect once the flip lands, nor silently ignore the
# flag and call that a green run. Tracked in a SEPARATE tuple from WRITE_FLAGS, compared
# against the COMMITTED workflow body — not a hardcoded literal in this script — so a
# divergence in EITHER direction (live "true" while committed is "false", or the reverse)
# is caught. WRITE_FLAGS' own all-false rule below is untouched by this addition.
COMMITTED_TRUTH_FLAGS = ("ALLOW_HUBSPOT_RECOMPUTE_WRITES",)


def _api(method, path, **kw):
    url = os.environ["N8N_URL"].rstrip("/") + "/api/v1" + path
    r = requests.request(method, url, headers={"X-N8N-API-KEY": os.environ["N8N_API_KEY"]},
                         timeout=60, **kw)
    r.raise_for_status()
    return r.json() if r.text else {}


def _flag_values(body, flags=WRITE_FLAGS):
    """Every `const <FLAG> = "<value>";` literal across the workflow's jsCode, per flag.
    `flags` defaults to WRITE_FLAGS (every existing call site unchanged); pass
    COMMITTED_TRUTH_FLAGS to scan for the fourth flag instead — same scanner,
    parameterized rather than duplicated (D-75-18b)."""
    found = {f: set() for f in flags}
    for node in body.get("nodes", []):
        code = (node.get("parameters") or {}).get("jsCode") or ""
        for flag in flags:
            marker = f"const {flag} = "
            i = code.find(marker)
            while i != -1:
                j = code.find(";", i)
                found[flag].add(code[i + len(marker):j].strip().strip('"'))
                i = code.find(marker, i + 1)
    return {f: sorted(v) for f, v in found.items()}


def _row_ok(live_body, expected_nodes, committed_body=None) -> bool:
    """Pure predicate — the whole row verdict, extracted so it can be exercised offline.

    True only when the workflow is active, its node count matches the committed body,
    every write flag reads the false literal (or is absent), its execution order reads v1
    (D-70-29), AND — when `committed_body` is supplied — every COMMITTED_TRUTH_FLAGS
    member's live literal equals the SAME flag's literal in the committed body (D-75-18b).
    `committed_body=None` skips that last check rather than failing it, so an existing
    caller with no committed body to compare against is unaffected."""
    flags = _flag_values(live_body)
    exec_order = (live_body.get("settings") or {}).get("executionOrder")
    ok = (
        live_body.get("active") is True
        and len(live_body.get("nodes", [])) == expected_nodes
        and all(v in ([], ["false"]) for v in flags.values())
        and exec_order == "v1"
    )
    if committed_body is not None:
        live_truth = _flag_values(live_body, flags=COMMITTED_TRUTH_FLAGS)
        committed_truth = _flag_values(committed_body, flags=COMMITTED_TRUTH_FLAGS)
        ok = ok and live_truth == committed_truth
    return ok


def main():
    if not (os.getenv("N8N_URL") and os.getenv("N8N_API_KEY")):
        print("skipped (no n8n creds): N8N_URL and N8N_API_KEY must both be set.")
        return 0
    root = Path(__file__).resolve().parent.parent
    ok = True
    print("| workflow | id | active | live nodes | committed nodes | write flags | "
          "recompute flag | execution order |")
    print("|---|---|---|---|---|---|---|---|")
    for rel, wid in WORKFLOWS.items():
        if wid is None:
            print(f"| {rel} | (unset) | - | - | - | - | - | - | "
                  f"**REFUSED: no live id yet — run the operator's first CREATE deploy "
                  f"(plan 09) and fill in the id, or this script would 404 blindly** |")
            continue
        committed = json.loads((root / rel).read_text())
        expected = len(committed["nodes"])
        _api("POST", f"/workflows/{wid}/deactivate")
        _api("POST", f"/workflows/{wid}/activate")
        live = _api("GET", f"/workflows/{wid}")
        flags = _flag_values(live)
        flags_txt = ", ".join(f"{k}={v or ['-']}" for k, v in flags.items())
        # T-75-15: surface the standing recompute flag's CURRENT value on every routine
        # bounce, so an operator scanning output notices it is still armed weeks later.
        recompute_flags = _flag_values(live, flags=COMMITTED_TRUTH_FLAGS)
        recompute_txt = ", ".join(f"{k}={v or ['-']}" for k, v in recompute_flags.items())
        exec_order = (live.get("settings") or {}).get("executionOrder")
        row_ok = _row_ok(live, expected, committed_body=committed)
        ok &= row_ok
        print(f"| {live.get('name')} | `{wid}` | {live.get('active')} | "
              f"{len(live.get('nodes', []))} | {expected} | {flags_txt} | {recompute_txt} | "
              f"{exec_order} |"
              f"{'' if row_ok else ' **MISMATCH**'}")
    print("\nOK — all active, node counts match, write flags false, recompute flag matches "
          "committed, execution order v1." if ok
          else "\nMISMATCH — see rows above; do not run UAT until resolved.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
