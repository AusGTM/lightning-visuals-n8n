#!/usr/bin/env python3
"""scripts/prove_async_recovery.py

Gap-closure (2026-08-31), operator decision "Option B" — the DISARMED, differential live
proof that `operator-claude-plugin/scripts/watch.py::recover_async_dispatch` recovers the
same proposed values a synchronous `mode: "propose"` dispatch would have returned on the
wire, from the settled execution instead.

WHY DIFFERENTIAL: every offline/injected-transport test in this repo passed while the bug
this proves against (`async_ack=True` on a propose-mode dispatch silently discards the
proposed field values — see `watch.py`'s "Async recovery" section docstring, and
`.planning/phases/61-autonomous-batch-runs/61-ASYNC-RECOVERY-VERDICT.json`'s own
`scope_boundary`) is invisible to an injected transport: nothing offline observes a real
`Build Async Ack` actually winning the race against the real chain. Only a live run can.

WHAT THIS SENDS: two disarmed POSTs to the real `hubspot/enrichment/event` webhook, the
SAME synthetic row content both times (`mode: "propose"` — return-only, CLAUDE.md's own
`isReturnOnly()` write guard — and `providers: []`, zero credit spend):
  1. Synchronously (no `async_ack`) — the response body IS the proposed-values payload.
  2. Asynchronously (`async_ack: true`, a client-minted `run_id`) — the response is an ack
     only; the proposed values are recovered afterward via
     `watch.recover_async_dispatch(cfg, run_id, expected_chunk_count=1)`, which correlates
     on the EXACT `run_id` (never `executions_client.find_execution_for_dispatch`'s
     time-proximity guess).

ASSERTION: the recovered payload equals the synchronous body (both are a one-row list from
the SAME `Build Response` node's own item shape). This is the exact assertion that would
FAIL under a naive "just add `async_ack=True`" implementation (Option C from the
checkpoint) — it is the one worth having.

Zero HubSpot writes, zero provider calls, zero Anthropic calls, nothing armed — `mode:
"propose"` and `providers: []` make both structurally true regardless of the workflow's
own write-safety gate.

TWO GATES, BOTH BEFORE ANY TRANSPORT IS CONSTRUCTED (mirrors prove_scale_up_runtime.py):
1. `ALLOW_ASYNC_RECOVERY_PROOF` must read EXACTLY `true`.
2. The wrong-instance guard, copied from `deploy_n8n_workflows.py::_instance_ok()`.

Usage (creds via `.env`, exactly like the deploy/probe scripts already document):
    set -a; source .env; set +a
    ALLOW_ASYNC_RECOVERY_PROOF=true .venv/bin/python scripts/prove_async_recovery.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "operator-claude-plugin" / "scripts"))

import chunking  # noqa: E402 — plugin module; see module docstring for why
import config_gate  # noqa: E402
import run_state  # noqa: E402
import watch  # noqa: E402

VERDICT_PATH = ROOT / ".planning" / "phases" / "61-autonomous-batch-runs" / "61-ASYNC-RECOVERY-VERDICT.json"
PROOF_ENV_VAR = "ALLOW_ASYNC_RECOVERY_PROOF"


# --------------------------------------------------------------------------- gates

def _instance_ok() -> bool:
    url = os.getenv("N8N_URL", "")
    expected = os.getenv("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def _require_gates() -> None:
    problems = []
    if os.getenv(PROOF_ENV_VAR) != "true":
        problems.append(f"{PROOF_ENV_VAR} must read EXACTLY 'true'; got {os.getenv(PROOF_ENV_VAR)!r}")
    if not os.getenv("N8N_URL"):
        problems.append("N8N_URL must be set")
    elif not _instance_ok():
        problems.append("wrong-instance guard refused")
    if problems:
        print("REFUSED — this fires the real production enrichment webhook.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)


# --------------------------------------------------------------------------- fixtures

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _synthetic_row(row_id):
    return {
        "row_id": row_id,
        "linkedin_url": f"https://www.linkedin.com/company/probe-async-recovery-{row_id}/",
    }


def _spec(row_id):
    return {"rows": [_synthetic_row(row_id)], "object_type": "contacts"}


def _write_verdict(verdict):
    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n")
    print(f"verdict written: {VERDICT_PATH}")


# --------------------------------------------------------------------------- main

def main():
    _require_gates()
    cfg = config_gate.load_config()
    ceiling = chunking.chunk_ceiling(cfg)

    # --- 1. synchronous send: the response body IS the proposed-values payload ---------
    sync_plan = chunking.plan_chunks(_spec("prove-async-sync-1"), ceiling)
    sync_outcome = chunking.dispatch_plan(sync_plan, [], True, cfg)
    sync_responses = [
        item for body in sync_outcome.responses
        for item in (body if isinstance(body, list) else [body])
    ]

    # --- 2. async send: recover the SAME shape from the settled execution --------------
    run_id = run_state.new_run_id()  # minted before any HTTP call (REVIEW-C14)
    async_plan = chunking.plan_chunks(_spec("prove-async-async-1"), ceiling)
    run_state.start_run(run_id, ["prove-async-async-1"])
    async_outcome = chunking.dispatch_plan(
        async_plan, [], True, cfg, run_id=run_id, async_ack=True,
    )
    run_state.mark_dispatched(run_id, ["prove-async-async-1"])

    async_wire_responses = [
        item for body in async_outcome.responses
        for item in (body if isinstance(body, list) else [body])
    ]
    if async_wire_responses != [
        {"run_id": run_id, "accepted": True, "row_id": "prove-async-async-1"}
    ]:
        verdict = {
            "premise": "async-recovery-differential",
            "answer": None,
            "basis": "observed",
            "outcome": "STOP — the async send's own wire response was not the expected ack shape",
            "scope_boundary": (
                "the synchronous response for the async_ack=true send did not match "
                "{run_id, accepted: true, row_id} — either Build Async Ack did not win "
                "the race this time, or its shape has changed. Recovering from the "
                "execution was not attempted."
            ),
            "observed": {"async_wire_responses": async_wire_responses},
        }
        _write_verdict(verdict)
        print("STOP: unexpected async wire response — see verdict.", file=sys.stderr)
        raise SystemExit(1)

    recovery = watch.recover_async_dispatch(cfg, run_id, async_plan.chunk_count)

    if not recovery["recovered"]:
        verdict = {
            "premise": "async-recovery-differential",
            "answer": None,
            "basis": "observed",
            "outcome": "STOP — recovery did not settle within the bound",
            "scope_boundary": (
                "watch.recover_async_dispatch did not find a settled execution carrying "
                "this run_id within the bound — either the correlation (Parse HubSpot "
                "Event's own run_id) did not match anything, or the execution had not "
                "settled yet. Not a data-mismatch finding; a timing/correlation one."
            ),
            "observed": {"run_id": run_id, "recovery": recovery},
        }
        _write_verdict(verdict)
        print("STOP: recovery did not settle — see verdict.", file=sys.stderr)
        raise SystemExit(1)

    # --- 3. the assertion that would have failed under the naive implementation -------
    # Both sends carry different row_ids (so each response is unambiguously its own),
    # so compare every field EXCEPT row_id — the one deliberate, expected difference.
    def _without_row_id(items):
        return [{k: v for k, v in item.items() if k != "row_id"} for item in items]

    sync_shape = _without_row_id(sync_responses)
    recovered_shape = _without_row_id(recovery["responses"])
    matches = sync_shape == recovered_shape

    verdict = {
        "premise": "async-recovery-differential",
        "question": (
            "does watch.recover_async_dispatch recover, from the execution, the SAME "
            "proposed-values payload a synchronous mode=propose dispatch would have "
            "returned on the wire?"
        ),
        "answer": matches,
        "basis": "observed",
        "scope_boundary": (
            "DISARMED: mode='propose' + providers=[] over 1 synthetic contact row, sent "
            "twice (once sync, once async_ack=true) -- zero HubSpot writes, zero provider "
            "calls, zero Anthropic calls, nothing armed. Correlation used the EXACT "
            "client-minted run_id read off Parse HubSpot Event's own output, never "
            "executions_client.find_execution_for_dispatch's time-proximity guess. This "
            "is NOT D-61-08's gated live unattended run."
        ),
        "observed": {
            "run_id": run_id,
            "matched_executions": recovery["matched_executions"],
            "sync_responses_without_row_id": sync_shape,
            "recovered_responses_without_row_id": recovered_shape,
            "shapes_equal": matches,
        },
    }
    _write_verdict(verdict)

    if not matches:
        print(
            "FINDING: recovered payload does NOT equal the synchronous body — this is a "
            "real finding, not a test bug. See the verdict file.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("PROVEN: async recovery reproduces the synchronous body exactly.")


if __name__ == "__main__":
    main()
