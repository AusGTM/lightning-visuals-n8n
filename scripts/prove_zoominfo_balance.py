#!/usr/bin/env python3
"""scripts/prove_zoominfo_balance.py

Phase 57 Plan 04 (G-4, D-57-02) — a DISARMED live re-probe of the ZoomInfo balance read,
because the historically-documented cause (a missing `Accept: application/vnd.api+json`
header) is ALREADY FIXED in current code (`scripts/build_cloud_workflows.py:4614-4630`
sends the header) while the label observed as of the 2026-08-25 walk is `provider_error`
— a DIFFERENT thing from `unrecognized_response_shape`. This script probes and reports;
it writes no fix, because writing one before an observation would be guessing at a cause
that may already be gone.

WHAT `provider_error` VS `unrecognized_response_shape` MEAN (`ENRICH_STATUS_BUILD_
RESPONSE`, `build_cloud_workflows.py:6354-6362`): `provider_error` means the HTTP request
itself errored (an expired mint, a stale cached token, a transient upstream failure —
`raw.error` is truthy); `unrecognized_response_shape` means the request SUCCEEDED and the
body could not be parsed into a balance (`extractCredits` returned null with no
transport-level error). They imply different fixes — a token-mint fix versus a response-
parsing fix — which is the entire reason this script tells them apart rather than
collapsing both into one "ZoomInfo is broken" label.

TWO GATES, BOTH BEFORE ANY TRANSPORT IS CONSTRUCTED (mirrors prove_async_recovery.py and
prove_scale_up_runtime.py):
1. `ALLOW_ZOOMINFO_BALANCE_PROBE` must read EXACTLY `true` (never truthy-coerced — `"True"`,
   `"1"`, `"yes"` all refuse).
2. The wrong-instance guard, copied from `deploy_n8n_workflows.py::_instance_ok()`.

Both gates are evaluated, and the process refuses with zero calls reaching the transport,
before `probe_zoominfo_balance()` ever touches the `transport` argument it was handed —
proved by test (`operator-claude-plugin/tests/test_prove_zoominfo_balance.py`) against an
injected double under the `no_network` fixture, not by reading the source for a gate
(REVIEW-57-M7). No verdict file is written on any refusal path — a refusal is not an
observation.

THIS PROBE NEEDS LESS SAFETY SCAFFOLDING THAN ITS TWO SIBLINGS, and the reason is stated
here rather than left as an unexplained omission: the balance check is the existing
`Status Credit Request` -> `ZoomInfo Usage` chain, which reads a balance, already runs
with `onError: continueRegularOutput`, and writes no HubSpot record. There is no
`mode: "propose"` gate and no empty-providers trick to apply here, because there is no CRM
write on this path to make structurally impossible in the first place.

THE FULL NETWORK PATH — wider than "a read-only GET" (REVIEW-57-M7). Read-only refers to
CRM EFFECT, not to the HTTP verbs involved, and calling this "a read-only GET" would
mislead the next reader about what a gate-on run touches:
  1. This script POSTs to the deployed backend's status endpoint, the same way
     `operator-claude-plugin/scripts/backend_status.py:40-54` (via `cost_guard.
     fetch_balances`) already does. It is a POST, not a GET.
  2. That request runs the deployed status workflow, which probes all three configured
     providers unconditionally.
  3. Apollo's usage call is itself configured as a POST (`scripts/provider_registry.py:
     26-33`) — this script never reaches it directly, but the deployed workflow does on
     every status read regardless of who asked.
  4. ZoomInfo may MINT and CACHE an auth token (`build_cloud_workflows.py:4168-4184`) — a
     state change on the n8n instance, not on any CRM record.
  5. No HubSpot object is read or written; no enrichment is dispatched; no armed window
     opens.

THE TWO-REQUEST PROTOCOL, AND EXACTLY WHAT IT MEASURES (REVIEW-57-H3). A single status
read cannot yield a before-and-after Lusha figure, so this script issues exactly two:
  1. Request #1 — the probe. Its ZoomInfo entry IS the verdict. Its Lusha
     `credits.remaining` figure is recorded as `lusha_before`.
  2. Request #2 — an identical status read issued immediately after. Its Lusha figure is
     recorded as `lusha_after`.
`lusha_after - lusha_before` measures the credit cost of REQUEST #1 only. Request #2's own
cost is NOT measured — measuring it would need a third read, whose cost would need a
fourth, and so on. The regress is cut deliberately at two, and the verdict file discloses
that it was cut there (`lusha_after_cost_unmeasured`) rather than leaving it implied.

`RUN_LIVE_PARITY` (REVIEW-57-M) IS NOT A SECOND GATE ON THIS SCRIPT. It is the ROOT test
suite's ambient-credential guard (`tests/test_conftest_credential_guard.py:6,34,39`) and
governs whether live-credentialled TESTS may run. This script is a script an operator runs
deliberately, not a test the suite collects, and must never be wired into a pytest run.
Its only gate is `ALLOW_ZOOMINFO_BALANCE_PROBE`.

Usage (creds via `.env`, exactly like the deploy/probe scripts already document):
    set -a; source .env; set +a
    ALLOW_ZOOMINFO_BALANCE_PROBE=true .venv/bin/python scripts/prove_zoominfo_balance.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "operator-claude-plugin" / "scripts"))

import backend_status  # noqa: E402 — plugin module; see module docstring for why
import config_gate  # noqa: E402

VERDICT_PATH = (
    ROOT / ".planning" / "phases"
    / "57-ceilings-refusal-before-start-and-post-run-proof"
    / "57-ZOOMINFO-BALANCE-VERDICT.json"
)
PROOF_ENV_VAR = "ALLOW_ZOOMINFO_BALANCE_PROBE"

VERDICT_READABLE = "readable"
VERDICT_PROVIDER_ERROR = "provider_error"
VERDICT_UNRECOGNIZED_SHAPE = "unrecognized_response_shape"
VERDICT_INCONCLUSIVE = "inconclusive"


# --------------------------------------------------------------------------- gates

def _instance_ok() -> bool:
    """Copied from `deploy_n8n_workflows.py::_instance_ok()` — must NOT fail open."""
    url = os.getenv("N8N_URL", "")
    expected = os.getenv("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def _gate_problems() -> list:
    """Both checks run before `probe_zoominfo_balance` ever touches its `transport`
    argument. The env-var comparison is to the exact lowercase string `"true"` — never a
    truthiness coercion, so `"True"`, `"1"`, `"yes"` all refuse."""
    problems = []
    value = os.getenv(PROOF_ENV_VAR)
    if value != "true":
        problems.append(f"{PROOF_ENV_VAR} must read EXACTLY 'true'; got {value!r}")
    if not _instance_ok():
        problems.append(
            "instance guard refused: N8N_URL does not match the expected instance "
            "(set N8N_EXPECTED_URL to pin it, or use a genuine *.n8n.cloud host)"
        )
    return problems


# --------------------------------------------------------------------------- helpers

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _find_balance(rows, provider):
    for row in rows or []:
        if isinstance(row, dict) and str(row.get("provider") or "").lower() == provider:
            return row
    return None


def _classify_zoominfo(row):
    """-> (verdict, error_detail) from a ZoomInfo balances row (or None if the status
    endpoint never reported one at all — an unreachable endpoint, a malformed body, or a
    provider simply absent from the response)."""
    if row is None:
        return VERDICT_INCONCLUSIVE, "zoominfo_not_reported"
    if row.get("unreadable") is False:
        return VERDICT_READABLE, None
    error = row.get("error")
    if error == VERDICT_PROVIDER_ERROR:
        return VERDICT_PROVIDER_ERROR, error
    if error == VERDICT_UNRECOGNIZED_SHAPE:
        return VERDICT_UNRECOGNIZED_SHAPE, error
    return VERDICT_INCONCLUSIVE, error or "unreadable_unspecified_reason"


def _lusha_credits(result):
    if not result.get("available"):
        return None
    rows = (result.get("data") or {}).get("balances")
    row = _find_balance(rows, "lusha")
    if row is None or row.get("unreadable") is not False:
        return None
    return row.get("credits")


def _build_verdict(*, result1, result2, instance_host):
    if not result1.get("available"):
        zi_verdict, zi_detail, zi_row = (
            VERDICT_INCONCLUSIVE,
            result1.get("reason") or "status_endpoint_unavailable",
            None,
        )
    else:
        rows = (result1.get("data") or {}).get("balances")
        zi_row = _find_balance(rows, "zoominfo")
        zi_verdict, zi_detail = _classify_zoominfo(zi_row)

    lusha_before = _lusha_credits(result1)
    lusha_after = _lusha_credits(result2)
    lusha_delta = (
        lusha_after - lusha_before
        if lusha_before is not None and lusha_after is not None
        else None
    )

    return {
        "premise": "zoominfo-balance-probe",
        "verdict": zi_verdict,
        "zoominfo_raw_credits": zi_row.get("credits") if zi_row else None,
        "zoominfo_http_status_present": bool(zi_row and zi_row.get("status") is not None),
        "zoominfo_http_status": zi_row.get("status") if zi_row else None,
        "zoominfo_error": zi_detail,
        "checked_at": _now_iso(),
        "instance_host": instance_host,
        "lusha_before": lusha_before,
        "lusha_after": lusha_after,
        "lusha_delta": lusha_delta,
        "lusha_after_cost_unmeasured": True,
        "lusha_after_cost_unmeasured_reason": (
            "Request #2 exists only to supply lusha_after; its own credit cost is not "
            "measured, because measuring it would need a third read, whose cost would "
            "need a fourth, and so on. lusha_delta measures request #1's (the probe's) "
            "cost only, not the full two-request run."
        ),
    }


def _write_verdict(verdict, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2) + "\n")
    print(f"verdict written: {path}")


# --------------------------------------------------------------------------- entry

def probe_zoominfo_balance(*, transport=None, config=None, verdict_path=None) -> dict:
    """The one entry point. Both gates run before `transport` is touched at all — on any
    refusal this returns `{"refused": True, "reasons": [...]}` without constructing a
    transport, without issuing a call, and without writing a verdict file.

    On the gate-on path, issues exactly two status requests (the two-request protocol
    documented above), builds the verdict, writes it to `verdict_path` (defaulting to the
    real `57-ZOOMINFO-BALANCE-VERDICT.json`) and returns it.
    """
    problems = _gate_problems()
    if problems:
        for problem in problems:
            print(f"REFUSED — {problem}", file=sys.stderr)
        return {"refused": True, "reasons": problems}

    resolved_config = config if config is not None else config_gate.load_config()
    call_transport = transport if transport is not None else requests.post
    target_path = verdict_path if verdict_path is not None else VERDICT_PATH

    result1 = backend_status.fetch_backend_status(resolved_config, transport=call_transport)
    result2 = backend_status.fetch_backend_status(resolved_config, transport=call_transport)

    verdict = _build_verdict(
        result1=result1,
        result2=result2,
        instance_host=urlparse(str(resolved_config.get("n8n_url") or "")).netloc,
    )
    _write_verdict(verdict, target_path)
    return verdict


def main():
    verdict = probe_zoominfo_balance()
    if verdict.get("refused"):
        raise SystemExit(2)
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    main()
