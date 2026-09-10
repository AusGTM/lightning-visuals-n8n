#!/usr/bin/env python3
"""scripts/prove_phase70_runtime.py

Phase 70 Plan 07 Task 3 (D-70-19) — the DISARMED live driver that answers the one
question this phase cannot answer offline: **is the walker a faithful model of the n8n
runtime?**

WHY THIS EXISTS. Every GREEN this phase produced was produced by
`tests/n8n/lib/walkWorkflow.mjs`, which models a Merge as fire-once-when-every-input-has-
data. Its own header says that is a spec, "not n8n's real multi-wave behaviour". Phase 70
put native `Merge` nodes at every convergence point and every HTTP hop of five workflows —
and **no committed workflow in this repo has ever contained a native Merge node before
this phase**. So the offline harness is currently an unvalidated model of a mechanism this
repo has never run. If the recovered live rows are NOT shape-equal to the walker's
prediction, every offline GREEN this phase produced is called into question — and the
correct response is to REPORT that as a finding, never to adjust the walker until it
agrees.

WHAT IT SENDS (four sends, all DISARMED, zero writes):
  1. enrichment lane — a 2-identity-lane x 2-action batch
  2. enrichment lane — a single-lane-only batch
  3. ingest lane     — a 2-identity-lane x 2-action batch
  4. ingest lane     — a single-lane-only batch
The allowlist is EMPTY, so every row is expected to come back blocked. That is the
intended result, not a failure. The single-lane sends are not decoration: the 2x2 shape
exercises every lane by construction and therefore cannot catch a Merge waiting on an
input that never fires — the common real shape, and the failure mode the whole design
rests on not happening.

HOW EACH SIDE IS PRODUCED:
  - OBSERVED: rows recovered from the settled execution's runData via the plugin's ONE
    poll site, `watch.recover_dispatch` (D-70-05/D-70-08 — `test_report_sufficiency.py`
    permits exactly one poll site and `watch.py` is it). Nothing here re-implements a
    wait loop, and nothing here reads the HTTP body for a row outcome: since D-70-07 the
    body is an ack (`{run_id, accepted, row_ids}`) and carries no rows at all.
  - PREDICTED: by SUBPROCESSING the committed walker CLI against the same committed JSON
    with the same input rows. Subprocessed deliberately (T-70-20): the prediction must
    come from the frozen, committed instrument, not from anything this driver could
    accidentally tune after seeing the live answer.

`--predict-only` runs the prediction half ALONE, contacts nothing, and writes a verdict
with `shapes_equal: null` and `status: "predicted_only_awaiting_gate_3"`. That is the mode
this repo runs today: the live half is deferred to the end-of-phase UAT (Gate 3 in
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md`).
**An offline run never writes `shapes_equal: true`.**

TWO GATES, BOTH BEFORE ANY TRANSPORT IS CONSTRUCTED — the shape
`scripts/prove_async_recovery.py` established and this file follows:
  1. `ALLOW_PHASE70_RUNTIME_PROOF` must read EXACTLY `true`.
  2. The wrong-instance guard, copied from `deploy_n8n_workflows.py::_instance_ok()`.
Plus a THIRD, specific to this proof (T-70-19): every write flag read back from the LIVE
workflow body must read exactly `"false"`. Anything else and the driver refuses without
sending. It never arms anything, and it never deploys or bounces — both are the
operator's step, and a stored update never reloads a running workflow.

The verdict records execution ids and row shapes only — never a credential, never a
webhook secret (T-70-03).

Usage:
    # offline, contacts nothing:
    .venv/bin/python scripts/prove_phase70_runtime.py --predict-only

    # live, disarmed, AFTER the operator has deployed and bounced:
    set -a; source .env; set +a
    ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "operator-claude-plugin" / "scripts"))

PHASE_DIR = ROOT / ".planning" / "phases" / "70-one-merge-one-result-channel-n8n-runtime-truth"
VERDICT_PATH = PHASE_DIR / "70-RUNTIME-VERDICT.json"
WALKER_CLI = ROOT / "tests" / "n8n" / "lib" / "walkWorkflow.mjs"
PROOF_ENV_VAR = "ALLOW_PHASE70_RUNTIME_PROOF"

ENRICHMENT_WF = ROOT / "n8n" / "wf_enrichment_cloud.json"
INGEST_WF = ROOT / "n8n" / "wf_contact_ingest_cloud.json"

# The write flags whose live value must read exactly "false" before anything is sent.
WRITE_FLAG_NAMES = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")


# --------------------------------------------------------------------------- the sends

def _enrichment_events(rows):
    return [{"objectType": "contact", **row} for row in rows]


# Four sends, declared once and shared by BOTH halves — the prediction and the live run
# must be driven from the identical input rows or the comparison means nothing.
SENDS = [
    {
        "name": "enrichment_2x2",
        "lane": "enrichment",
        "workflow": ENRICHMENT_WF,
        "trigger": "Webhook Trigger",
        "response_node": "Build Response",
        # propose mode: `Parse HubSpot Event` caps a WRITE request at 2 events and
        # refuses an oversize one WHOLE, so a 4-row 2x2 rides the propose ceiling (20).
        # Same reasoning, and the same shape, as tests/n8n/enrichmentMixedBatch.test.mjs.
        "mode": "propose",
        "rows": [
            {"email": "p70-email-a@runtime-proof.invalid", "row_id": "e-email-a"},
            {"email": "p70-email-b@runtime-proof.invalid", "row_id": "e-email-b"},
            {"linkedin_url": "https://www.linkedin.com/in/p70-runtime-proof-a", "row_id": "e-li-a"},
            {"linkedin_url": "https://www.linkedin.com/in/p70-runtime-proof-b", "row_id": "e-li-b"},
        ],
    },
    {
        "name": "enrichment_single_lane",
        "lane": "enrichment",
        "workflow": ENRICHMENT_WF,
        "trigger": "Webhook Trigger",
        "response_node": "Build Response",
        "mode": "propose",
        "rows": [
            {"email": "p70-single-a@runtime-proof.invalid", "row_id": "e-single-a"},
            {"email": "p70-single-b@runtime-proof.invalid", "row_id": "e-single-b"},
        ],
    },
    {
        "name": "ingest_2x2",
        "lane": "ingest",
        "workflow": INGEST_WF,
        "trigger": "Webhook Trigger",
        "response_node": "Build Ingest Response",
        "mode": None,
        "rows": [
            {"email": "p70-i-domain-a@runtime-proof.invalid", "firstname": "P70", "lastname": "DomainA", "company": "Runtime Proof Co"},
            {"email": "p70-i-domain-b@runtime-proof.invalid", "firstname": "P70", "lastname": "DomainB", "company": "Runtime Proof Co"},
            {"email": "p70-i-name-a@runtime-proof-nodomain.invalid", "firstname": "P70", "lastname": "NameA", "company": "Runtime Proof Name Club"},
            {"email": "p70-i-name-b@runtime-proof-nodomain.invalid", "firstname": "P70", "lastname": "NameB", "company": "Runtime Proof Name Club"},
        ],
    },
    {
        "name": "ingest_single_lane",
        "lane": "ingest",
        "workflow": INGEST_WF,
        "trigger": "Webhook Trigger",
        "response_node": "Build Ingest Response",
        "mode": None,
        "rows": [
            {"email": "p70-i-single-a@runtime-proof.invalid", "firstname": "P70", "lastname": "SingleA", "company": "Runtime Proof Co"},
            {"email": "p70-i-single-b@runtime-proof.invalid", "firstname": "P70", "lastname": "SingleB", "company": "Runtime Proof Co"},
        ],
    },
]


# --------------------------------------------------------------------------- gates

def _instance_ok(env=None) -> bool:
    # `env` is threaded through rather than read from os.environ directly: a guard whose
    # answer depends on ambient process state cannot be tested, and an untested guard is
    # the one that fails on the day it matters.
    env = os.environ if env is None else env
    url = env.get("N8N_URL", "")
    expected = env.get("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def require_gates(env=None) -> None:
    """Refuse BEFORE any transport is constructed. Raises SystemExit(2) on refusal."""
    env = os.environ if env is None else env
    problems = []
    if env.get(PROOF_ENV_VAR) != "true":
        problems.append(
            f"{PROOF_ENV_VAR} must read EXACTLY 'true'; got {env.get(PROOF_ENV_VAR)!r}")
    if not env.get("N8N_URL"):
        problems.append("N8N_URL must be set")
    elif not _instance_ok(env):
        problems.append("wrong-instance guard refused")
    if not env.get("N8N_API_KEY"):
        # Refusal BEFORE start, never a half-run that cannot be read back (D-70-10):
        # without the executions API there is no result channel at all, since the wire
        # carries only an ack.
        problems.append(
            "N8N_API_KEY must be set — the result channel IS the executions API (D-70-05); "
            "without it a send produces an ack and nothing readable")
    if problems:
        print("REFUSED — this fires the real production webhooks.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)


def write_flags_in(body) -> dict:
    """Every write-flag declaration found in a workflow body, as {node: {flag: value}}.

    Reads the SAME `const FLAG = "value";` shape `n8n_arming.set_write_safety` writes, so
    a node it would have rewritten is a node this sees.
    """
    import re
    found = {}
    for node in (body or {}).get("nodes", []):
        js = ((node.get("parameters") or {}).get("jsCode")) or ""
        per_node = {}
        for flag in WRITE_FLAG_NAMES:
            m = re.search(rf'const {flag} = "([^"]*)";', js)
            if m:
                per_node[flag] = m.group(1)
        if per_node:
            found[node.get("name")] = per_node
    return found


def require_disarmed(live_bodies) -> dict:
    """Refuse unless EVERY write flag in EVERY live body reads exactly "false" (T-70-19).

    Returns the full reading so the verdict can record it. Raises SystemExit(2) on any
    other value — including a missing one, which means the shape changed and this guard
    is no longer checking what it thinks it is.
    """
    reading = {}
    offenders = []
    for name, body in live_bodies.items():
        reading[name] = write_flags_in(body)
        if not reading[name]:
            offenders.append(f"{name}: no write-flag declaration found at all")
        for node, flags in reading[name].items():
            for flag, value in flags.items():
                if value != "false":
                    offenders.append(f"{name}/{node}/{flag} reads {value!r}, not 'false'")
    if offenders:
        print("REFUSED — a live body is not disarmed. Nothing was sent.", file=sys.stderr)
        for o in offenders:
            print(f"  - {o}", file=sys.stderr)
        raise SystemExit(2)
    return reading


# --------------------------------------------------------------------------- prediction

# One neutral "nothing resolved" HTTP body, shaped to satisfy every adapter on both
# lanes at once: an empty `results` list for the searches, `matched: false` for the
# provider reveals, and a token for the ZoomInfo mints. This is the honest model of the
# live sends — every identity search runs against synthetic `.invalid` addresses that
# resolve nothing, and every provider is disabled — so every HTTP hop returns nothing on
# BOTH sides of the comparison.
NEUTRAL_HTTP_BODY = {
    "results": [], "data": {}, "matched": False, "access_token": "stub-token",
    "id": None, "properties": {},
}
# The walker pairs call i with stub entry i and THROWS on an unstubbed HTTP node (by
# design — an unstubbed hop is a silent hole in a prediction). An oversized array is
# harmless; a short one is not.
_STUB_DEPTH = 8
_HTTP_TYPES = ("n8n-nodes-base.httpRequest", "n8n-nodes-base.hubspot")


def _neutral_stubs(workflow_path) -> dict:
    body = json.loads(Path(workflow_path).read_text())
    return {
        node["name"]: [dict(NEUTRAL_HTTP_BODY) for _ in range(_STUB_DEPTH)]
        for node in body.get("nodes", [])
        if node.get("type") in _HTTP_TYPES
    }


def _fixture_for(send) -> dict:
    """The walker fixture for one send: the SAME rows, and a neutral stub per HTTP node."""
    stubs = _neutral_stubs(send["workflow"])
    if send["lane"] == "enrichment":
        body = {"run_id": None, "events": _enrichment_events(send["rows"])}
        if send["mode"]:
            body["mode"] = send["mode"]
        return {"triggerItems": [{"body": body}], "httpStubs": stubs}
    return {"triggerItems": list(send["rows"]), "httpStubs": stubs}


def predict(send, *, tmp_dir, runner=subprocess.run) -> list:
    """Predicted rows for one send, from the COMMITTED walker CLI in a subprocess.

    Subprocessed on purpose (T-70-20): the prediction comes from the frozen instrument,
    never from anything this driver could tune after seeing the live rows.
    """
    fixture_path = Path(tmp_dir) / f"{send['name']}.json"
    fixture_path.write_text(json.dumps(_fixture_for(send)))
    proc = runner(
        ["node", str(WALKER_CLI),
         "--workflow", str(send["workflow"]),
         "--rows", str(fixture_path),
         "--node", send["response_node"],
         "--trigger", send["trigger"]],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"walker CLI failed for {send['name']}: {proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- comparison

def row_shape(row) -> dict:
    """The comparable shape of one row: its keys, sorted, plus the fields that identify
    it and say what happened to it.

    Shape, not value: the live run's timestamps, run ids and HubSpot ids legitimately
    differ from an offline prediction's. What must NOT differ is which rows came back,
    how many, and what outcome each carries — which is exactly what a Merge misbehaving
    would change.
    """
    row = row or {}
    return {
        "keys": sorted(row.keys()),
        "row_id": row.get("row_id"),
        "email": row.get("email") or (row.get("properties") or {}).get("email"),
        "action": row.get("action"),
        "outcome": row.get("outcome"),
    }


def _ingest_recovered_rows(dispatch_result) -> list:
    """The row set to compare against the walker's raw prediction on the ingest lane
    (D-70-22, G-70-4): `dispatch.dispatch()`'s "raw_rows" — the recovery BEFORE
    `report.reconcile` stamps a "reported_outcome" key onto every row. The walker's
    prediction reads `Build Ingest Response`'s own output directly and never produces
    that key, so comparing the RECONCILED rows ("rows") against it fails on a client
    artifact (execution 12207), not a runtime divergence. The reconciled rows stay the
    operator-facing set every other caller reads; this reads the same single recovery
    call under its own key, no second poll.
    """
    return dispatch_result.get("raw_rows") or []


def shapes_equal(predicted, recovered) -> bool:
    """True when the two row lists are the same multiset of shapes.

    Order-insensitive by design: n8n's `executionOrder: v1` and the walker's queue can
    legitimately interleave lanes differently. Row IDENTITY and COUNT are what this
    phase asserts, never row order.
    """
    def key(rows):
        return sorted(json.dumps(row_shape(r), sort_keys=True) for r in rows)
    return key(predicted) == key(recovered)


# --------------------------------------------------------------------------- verdict

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_verdict(*, per_send, live_execution_order, write_flag_reading, predict_only):
    """The D-70-19 verdict. Records execution ids and row shapes only — never a
    credential and never a webhook secret (T-70-03).
    """
    settled = [s for s in per_send if s.get("settled") is False]
    all_equal = (
        None if predict_only
        else all(s.get("shapes_equal") is True for s in per_send) and not settled
    )
    return {
        "premise": "phase-70-runtime-truth",
        "question": (
            "do the rows recovered from a disarmed live run's runData match, shape for "
            "shape, the rows the committed walker predicts for the same input?"
        ),
        "status": "predicted_only_awaiting_gate_3" if predict_only else "observed",
        "basis": "predicted (offline, nothing contacted)" if predict_only else "observed",
        "answer": all_equal,
        "shapes_equal": all_equal,
        "generated_at": _now_iso(),
        "live_settings_execution_order": live_execution_order,
        "execution_ids": [s.get("execution_id") for s in per_send if s.get("execution_id")],
        "writes_performed": 0,
        "write_flags_read_from_live_bodies": write_flag_reading,
        "sends": per_send,
        "scope_boundary": (
            "PREDICTION ONLY — nothing was contacted, no execution ran, no live "
            "settings.executionOrder was read, and `shapes_equal` is deliberately null "
            "rather than true. The live half is Gate 3 in 70-DEFERRED-GATES.md."
            if predict_only else
            "DISARMED: every write flag read 'false' in the live bodies before anything "
            "was sent, the allowlist was empty, and every row was expected blocked. Zero "
            "HubSpot writes, nothing armed. This is NOT the gated live unattended run."
        ),
    }


def write_verdict(verdict, path=VERDICT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2) + "\n")
    return path


# --------------------------------------------------------------------------- main

def run_predict_only() -> dict:
    import tempfile
    per_send = []
    with tempfile.TemporaryDirectory() as tmp:
        for send in SENDS:
            predicted = predict(send, tmp_dir=tmp)
            per_send.append({
                "name": send["name"],
                "lane": send["lane"],
                "input_row_count": len(send["rows"]),
                "predicted_row_count": len(predicted),
                "predicted_shapes": [row_shape(r) for r in predicted],
                "recovered_row_count": None,
                "shapes_equal": None,
                "execution_id": None,
                "settled": None,
            })
    return build_verdict(per_send=per_send, live_execution_order=None,
                         write_flag_reading=None, predict_only=True)


def run_live() -> dict:
    require_gates()
    import csv
    import requests
    import chunking          # noqa: E402 — plugin modules; see prove_async_recovery.py
    import config_gate       # noqa: E402
    import dispatch          # noqa: E402
    import executions_client  # noqa: E402
    import run_state         # noqa: E402
    import scheduled_arm     # noqa: E402
    import watch             # noqa: E402
    import tempfile

    cfg = config_gate.load_config()

    # --- gate 3: read the LIVE bodies back and refuse unless every flag is "false" -----
    # Workflow names come from the SAME constants the recovery poll resolves by
    # (`watch._LANE_RECOVERY_CONFIG`), never a literal of this driver's own — a literal
    # here drifted from the live name ("... (Cloud)" vs "... (Cloud template)") and was
    # found only when the driver first ran, 2026-09-10.
    live_bodies = {}
    execution_order = {}
    for wf_name in (scheduled_arm.ENRICHMENT_WORKFLOW_NAME, watch.INGEST_WORKFLOW_NAME):
        wf_id = executions_client.resolve_workflow_id(cfg, workflow_name=wf_name)
        if wf_id is None:
            print(f"REFUSED — no live workflow named {wf_name!r}. Nothing was sent.",
                  file=sys.stderr)
            raise SystemExit(2)
        body = executions_client._get_json(
            cfg, f"{executions_client._base_url(cfg)}/api/v1/workflows/{wf_id}", None,
            requests.get)
        live_bodies[wf_name] = body
        # D-70-02's observed-live upgrade: record what it ACTUALLY is, not what it was
        # expected to be. An absent key is recorded as None — the engine default.
        execution_order[wf_name] = (body.get("settings") or {}).get("executionOrder")
    flag_reading = require_disarmed(live_bodies)

    per_send = []
    with tempfile.TemporaryDirectory() as tmp:
        for send in SENDS:
            predicted = predict(send, tmp_dir=tmp)
            run_id = run_state.new_run_id()  # minted BEFORE any HTTP call
            if send["lane"] == "ingest":
                # The ingest lane is a multipart CSV POST to the contact-upload webhook
                # (`dispatch.dispatch`), which recovers its own rows from runData on the
                # ingest lane (D-70-05). Routing these rows through `chunking.dispatch_plan`
                # would post an enrichment envelope to the enrichment webhook and then poll
                # the ingest workflow for a run id it never saw.
                csv_path = Path(tmp) / f"{send['name']}.csv"
                with csv_path.open("w", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=list(send["rows"][0]))
                    writer.writeheader()
                    writer.writerows(send["rows"])
                result = dispatch.dispatch(str(csv_path), True, cfg, run_id=run_id)
                # D-70-22 (G-70-4): the RAW recovery, not the client-reconciled "rows" —
                # see _ingest_recovered_rows's own docstring for why.
                recovered = _ingest_recovered_rows(result)
                settled = bool(result.get("recovered"))
                execution_ids = list(result.get("execution_ids") or [])
            else:
                spec = {"rows": list(send["rows"]), "object_type": "contacts"}
                plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))
                chunking.dispatch_plan(plan, [], True, cfg, run_id=run_id)
                recovery = watch.recover_dispatch(cfg, run_id, plan.chunk_count,
                                                  lane=send["lane"])
                recovered = recovery.get("responses") or []
                settled = bool(recovery.get("recovered"))
                execution_ids = list(recovery.get("execution_ids") or [])
            per_send.append({
                "name": send["name"],
                "lane": send["lane"],
                "run_id": run_id,
                "input_row_count": len(send["rows"]),
                "predicted_row_count": len(predicted),
                "recovered_row_count": len(recovered),
                "predicted_shapes": [row_shape(r) for r in predicted],
                "recovered_shapes": [row_shape(r) for r in recovered],
                "shapes_equal": shapes_equal(predicted, recovered),
                "execution_id": execution_ids[0] if execution_ids else None,
                "execution_ids": execution_ids,
                "settled": settled,
            })

    return build_verdict(per_send=per_send, live_execution_order=execution_order,
                         write_flag_reading=flag_reading, predict_only=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--predict-only", action="store_true",
                        help="run the prediction half alone; contacts nothing")
    # `--out` exists so a test can run this end to end without rewriting the committed
    # verdict artifact on every pytest run. The live invocation never passes it.
    parser.add_argument("--out", default=None, help="write the verdict here instead")
    args = parser.parse_args(argv)

    verdict = run_predict_only() if args.predict_only else run_live()
    path = write_verdict(verdict, Path(args.out) if args.out else VERDICT_PATH)
    print(f"verdict written: {path}")

    if args.predict_only:
        print("PREDICTION ONLY — shapes_equal is null. The live half is Gate 3 "
              "(70-DEFERRED-GATES.md).")
        return 0
    if verdict["shapes_equal"] is not True:
        print(
            "FINDING: the recovered rows are NOT shape-equal to the walker's prediction, "
            "or an execution did not settle. This is a finding to REPORT — do not adjust "
            "the walker to match. See the verdict file.",
            file=sys.stderr,
        )
        return 1
    print("PROVEN: the live rows match the walker's prediction on every send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
