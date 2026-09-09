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
reads anything but "false", or a node count disagrees with the committed JSON.
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
}
WRITE_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")


def _api(method, path, **kw):
    url = os.environ["N8N_URL"].rstrip("/") + "/api/v1" + path
    r = requests.request(method, url, headers={"X-N8N-API-KEY": os.environ["N8N_API_KEY"]},
                         timeout=60, **kw)
    r.raise_for_status()
    return r.json() if r.text else {}


def _flag_values(body):
    """Every `const <FLAG> = "<value>";` literal across the workflow's jsCode, per flag."""
    found = {f: set() for f in WRITE_FLAGS}
    for node in body.get("nodes", []):
        code = (node.get("parameters") or {}).get("jsCode") or ""
        for flag in WRITE_FLAGS:
            marker = f"const {flag} = "
            i = code.find(marker)
            while i != -1:
                j = code.find(";", i)
                found[flag].add(code[i + len(marker):j].strip().strip('"'))
                i = code.find(marker, i + 1)
    return {f: sorted(v) for f, v in found.items()}


def main():
    if not (os.getenv("N8N_URL") and os.getenv("N8N_API_KEY")):
        print("skipped (no n8n creds): N8N_URL and N8N_API_KEY must both be set.")
        return 0
    root = Path(__file__).resolve().parent.parent
    ok = True
    print("| workflow | id | active | live nodes | committed nodes | write flags |")
    print("|---|---|---|---|---|---|")
    for rel, wid in WORKFLOWS.items():
        expected = len(json.loads((root / rel).read_text())["nodes"])
        _api("POST", f"/workflows/{wid}/deactivate")
        _api("POST", f"/workflows/{wid}/activate")
        live = _api("GET", f"/workflows/{wid}")
        flags = _flag_values(live)
        flags_txt = ", ".join(f"{k}={v or ['-']}" for k, v in flags.items())
        row_ok = live.get("active") is True and len(live.get("nodes", [])) == expected \
            and all(v in ([], ["false"]) for v in flags.values())
        ok &= row_ok
        print(f"| {live.get('name')} | `{wid}` | {live.get('active')} | "
              f"{len(live.get('nodes', []))} | {expected} | {flags_txt} |{'' if row_ok else ' **MISMATCH**'}")
    print("\nOK — all active, node counts match, write flags false." if ok
          else "\nMISMATCH — see rows above; do not run UAT until resolved.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
