"""Offline coverage for `scripts/prove_phase70_runtime.py` (Phase 70 Plan 07 Task 3).

The driver's LIVE half is deferred to Gate 3 (the end-of-phase UAT — see
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md`).
What is testable here is everything that must hold BEFORE it is ever pointed at n8n:

  - it refuses loudly, before constructing any transport, on a missing gate;
  - it refuses when a live body's write flag reads anything other than `"false"` — the
    T-70-19 mitigation, and the one guard between this proof and an accidental write;
  - `--predict-only` produces a verdict that never claims `shapes_equal: true`;
  - the prediction it produces is the same row-alignment the two mixed-batch acceptance
    tests assert offline — one returned row per input row, no duplicate identity.

The comparison helper is tested against a KNOWN mismatch too: a comparator that cannot
fail is not a comparator, and `shapes_equal` is the field the whole verdict turns on.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import prove_phase70_runtime as driver  # noqa: E402


# --------------------------------------------------------------------------- gates

def test_gates_refuse_without_the_explicit_opt_in():
    with pytest.raises(SystemExit) as exc:
        driver.require_gates(env={"N8N_URL": "https://x.n8n.cloud", "N8N_API_KEY": "k"})
    assert exc.value.code == 2


def test_gates_refuse_a_truthy_but_not_exact_opt_in():
    """"true" and nothing else — the same discipline every request-level flag uses."""
    with pytest.raises(SystemExit):
        driver.require_gates(env={
            driver.PROOF_ENV_VAR: "TRUE",
            "N8N_URL": "https://x.n8n.cloud", "N8N_API_KEY": "k",
        })


def test_gates_refuse_a_wrong_instance():
    with pytest.raises(SystemExit):
        driver.require_gates(env={
            driver.PROOF_ENV_VAR: "true",
            "N8N_URL": "https://not-n8n.example.com", "N8N_API_KEY": "k",
        })


def test_gates_refuse_without_an_executions_api_key():
    """The result channel IS the executions API (D-70-05): no key, no readable result."""
    with pytest.raises(SystemExit):
        driver.require_gates(env={
            driver.PROOF_ENV_VAR: "true", "N8N_URL": "https://x.n8n.cloud",
        })


# --------------------------------------------------------------------------- disarm guard

def _body(flag_value, flag=driver.WRITE_FLAG_NAMES[0]):
    return {"nodes": [{
        "name": "HubSpot Update Write Gate",
        "parameters": {"jsCode": f'const {flag} = "{flag_value}";\nreturn items;'},
    }]}


def test_disarm_guard_accepts_a_body_whose_every_flag_reads_false():
    reading = driver.require_disarmed({"LV Enrichment": _body("false")})
    assert reading["LV Enrichment"]["HubSpot Update Write Gate"] == {
        driver.WRITE_FLAG_NAMES[0]: "false"}


def test_disarm_guard_refuses_an_armed_live_body(capsys):
    """T-70-19: the one guard between this disarmed proof and an accidental live write."""
    with pytest.raises(SystemExit) as exc:
        driver.require_disarmed({"LV Enrichment": _body("true")})
    assert exc.value.code == 2
    assert "not 'false'" in capsys.readouterr().err


def test_disarm_guard_refuses_a_body_with_no_flag_declaration_at_all(capsys):
    """A shape change is a refusal, never a pass: a guard that finds nothing to check is
    not a guard that found everything safe."""
    with pytest.raises(SystemExit):
        driver.require_disarmed({"LV Enrichment": {"nodes": [{"name": "X", "parameters": {}}]}})
    assert "no write-flag declaration" in capsys.readouterr().err


def test_disarm_guard_sees_the_real_committed_bodies_as_disarmed():
    """The committed JSON ships disarmed — if this ever fails, something armed the repo."""
    bodies = {
        p.name: json.loads(p.read_text())
        for p in (driver.ENRICHMENT_WF, driver.INGEST_WF)
    }
    reading = driver.require_disarmed(bodies)
    assert reading[driver.ENRICHMENT_WF.name], "the enrichment lane declares write flags"


# --------------------------------------------------------------------------- comparison

def test_shapes_equal_is_true_for_the_same_rows_in_a_different_order():
    a = [{"row_id": "1", "action": "review"}, {"row_id": "2", "action": "review"}]
    assert driver.shapes_equal(a, list(reversed(a))) is True


def test_shapes_equal_is_false_when_a_row_is_missing():
    """The F5-collapse shape — the defect class this whole phase closed."""
    a = [{"row_id": "1", "action": "review"}, {"row_id": "2", "action": "review"}]
    assert driver.shapes_equal(a, a[:1]) is False


def test_shapes_equal_is_false_when_a_row_is_duplicated():
    """A Merge firing twice would double every reported row."""
    a = [{"row_id": "1", "action": "review"}, {"row_id": "2", "action": "review"}]
    assert driver.shapes_equal(a, a + a[:1]) is False


def test_shapes_equal_is_false_when_an_outcome_differs():
    a = [{"row_id": "1", "action": "review"}]
    b = [{"row_id": "1", "action": "write_blocked"}]
    assert driver.shapes_equal(a, b) is False


# --------------------------------------------------------------------------- predict-only

@pytest.fixture(scope="module")
def predicted_verdict(tmp_path_factory):
    """Run the driver's own CLI in `--predict-only`, end to end, in a subprocess.

    End to end on purpose: the prediction half subprocesses the walker CLI, and this is
    what proves that path works against the COMMITTED JSON of both lanes — including the
    `--trigger` flag the enrichment lane needs (it has two trigger nodes, so the CLI's
    single-trigger auto-detect cannot resolve it).
    """
    out = tmp_path_factory.mktemp("verdict") / "verdict.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prove_phase70_runtime.py"),
         "--predict-only", "--out", str(out)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert out.exists()
    return json.loads(out.read_text())


def test_predict_only_never_claims_shape_equality(predicted_verdict):
    """An offline run must never write `shapes_equal: true` — that field is the live
    observation, and a driver that can fabricate it is worse than no driver (T-70-20)."""
    assert predicted_verdict["shapes_equal"] is None
    assert predicted_verdict["answer"] is None
    assert predicted_verdict["status"] == "predicted_only_awaiting_gate_3"
    assert predicted_verdict["execution_ids"] == []
    assert predicted_verdict["live_settings_execution_order"] is None
    assert "Gate 3" in predicted_verdict["scope_boundary"]


def test_predict_only_records_zero_writes(predicted_verdict):
    assert predicted_verdict["writes_performed"] == 0


def test_predict_only_carries_no_credential(predicted_verdict):
    """T-70-03: the verdict records execution ids and row shapes only."""
    blob = json.dumps(predicted_verdict).lower()
    for secret_ish in ("api_key", "apikey", "authorization", "n8n_api", "secret",
                       "password", "token", "bearer"):
        assert secret_ish not in blob, f"verdict must not carry {secret_ish!r}"


def test_every_send_predicts_one_row_per_input_row(predicted_verdict):
    """The same assertion the two mixed-batch acceptance tests make, on the same JSON —
    stated here so the driver's prediction half is known good BEFORE it is compared
    against anything live."""
    assert len(predicted_verdict["sends"]) == 4
    for send in predicted_verdict["sends"]:
        assert send["predicted_row_count"] == send["input_row_count"], (
            f"{send['name']}: predicted {send['predicted_row_count']} rows for "
            f"{send['input_row_count']} inputs"
        )


def test_the_four_sends_are_two_lanes_by_two_shapes(predicted_verdict):
    names = [s["name"] for s in predicted_verdict["sends"]]
    assert names == ["enrichment_2x2", "enrichment_single_lane",
                     "ingest_2x2", "ingest_single_lane"], (
        "D-70-19: a 2x2 AND a single-lane send per lane — the 2x2 alone cannot catch a "
        "Merge waiting on an input that never fires"
    )


# --------------------------------------------------------------------------- G-70-4 / D-70-22
#
# Execution 12207 (70-RUNTIME-VERDICT.json, ingest_2x2): the recovered rows were
# row-for-row equal to the walker's prediction on action/outcome/email — the ONLY
# difference was the "reported_outcome" key `report.reconcile` stamps onto every row
# dispatch.dispatch() returns under "rows". Comparing THAT against the walker's raw
# prediction fails on a client artifact, never a runtime divergence. Built directly
# from the verdict's own recorded keys, so this reproduces 12207's exact shape.

_12207_RECONCILED_ROW = {
    "action": "review", "association": None, "company_id": None,
    "company_match": None, "contact_id": None,
    "email": "p70-i-domain-a@runtime-proof.invalid", "email_status": None,
    "hs_object_id": None, "outcome": "net_new", "reason": None,
    "reported_outcome": "review", "row_id": None,
}


def test_ingest_recovered_rows_reads_the_raw_key_not_the_reconciled_one():
    """D-70-22 (G-70-4): fails on execution 12207's exact shape before the fix —
    `_ingest_recovered_rows` (and the "raw_rows" key it reads) did not exist before this
    change, and the reconciled rows alone never compare equal to the walker's prediction.
    """
    raw_row = {k: v for k, v in _12207_RECONCILED_ROW.items() if k != "reported_outcome"}
    predicted_row = dict(raw_row)  # the walker's raw prediction never carries the key either

    dispatch_result = {"rows": [_12207_RECONCILED_ROW], "raw_rows": [raw_row]}

    recovered = driver._ingest_recovered_rows(dispatch_result)

    assert driver.shapes_equal([predicted_row], recovered) is True
    # Sanity: the OLD source (the reconciled "rows") is exactly what execution 12207
    # showed as unequal — proves the comparator (row_shape/shapes_equal) never needed to
    # change; only which row set the ingest branch reads did.
    assert driver.shapes_equal([predicted_row], dispatch_result["rows"]) is False


def test_ingest_recovered_rows_defaults_to_empty_when_the_key_is_absent():
    """A dispatch result shaped like the pre-fix return (no "raw_rows" at all) must
    never crash — it degrades to zero recovered rows, same discipline as every other
    `.get(...) or []` read in this driver."""
    assert driver._ingest_recovered_rows({"rows": [_12207_RECONCILED_ROW]}) == []
