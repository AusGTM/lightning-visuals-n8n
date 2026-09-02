# tests/test_replay_judge_models.py
#
# Phase 63 Plan 03 Task 1 — offline proof for scripts/replay_judge_models.py's
# comparison core. Fully hermetic: build_report() never touches the network,
# only ever receives a stubbed call_model, and this suite never imports
# scripts.build_cloud_workflows (which regenerates n8n/code/*.generated.js as
# a module-import side effect — that import lives only inside
# replay_judge_models._resolve_model_ids(), called from main(), never here).
import random
import re
from pathlib import Path

import scripts.replay_judge_models as replay

ROOT = Path(__file__).resolve().parent.parent
MODULE_SOURCE = (ROOT / "scripts" / "replay_judge_models.py").read_text()

MODEL_A = "claude-sonnet-5"
MODEL_B = "claude-haiku-4-5"

REQUIRED_KEYS = replay._load_required_verdict_keys()


def _input(input_id, chosen_value="governing_body_league", extra=None):
    body = {"company": {"name": "Example Racing League"}}
    item = {
        "input_id": input_id,
        "lane": "companies",
        "judge_reasons": ["confidence_band"],
        "judge_request_body": body,
        "body_sha256": replay._canonical_sha256(body),
    }
    if extra:
        item.update(extra)
    return item


def _verdict(decision="promote", chosen_field="lv_org_type", chosen_value="governing_body_league",
             confidence=88, reason="matches evidence", evidence_url="https://example.org/about",
             evidence_summary="about page"):
    return {
        "decision": decision,
        "chosen_value": chosen_value,
        "chosen_field": chosen_field,
        "confidence": confidence,
        "evidence_url": evidence_url,
        "evidence_summary": evidence_summary,
        "validation_status": "sonnet_validated",
        "reason": reason,
    }


def _always(verdict):
    def _call(model, body):
        return dict(verdict)
    return _call


def _by_model(mapping):
    def _call(model, body):
        v = mapping[model]
        return dict(v) if v is not None else None
    return _call


# ---------------------------------------------------------------------------
# Case 1: two models agreeing -> SHIP once the minimum is met.
# ---------------------------------------------------------------------------
def test_agreeing_models_ship_once_minimum_met():
    inputs = [_input(f"100:{i}") for i in range(3)]
    call_model = _always(_verdict())
    report, exit_code = replay.build_report(inputs, call_model, MODEL_A, MODEL_B, min_corpus=3)
    assert report["verdict"] == replay.SHIP
    assert exit_code == 0
    assert report["counts"]["agree"] == 3
    assert report["inputs_compared"] == 3


# ---------------------------------------------------------------------------
# Case 2: differing decision -> DROP/material.
# ---------------------------------------------------------------------------
def test_differing_decision_is_material_and_drops():
    inputs = [_input("101:0")]
    call_model = _by_model({
        MODEL_A: _verdict(decision="promote"),
        MODEL_B: _verdict(decision="needs_review"),
    })
    report, exit_code = replay.build_report(inputs, call_model, MODEL_A, MODEL_B, min_corpus=1)
    assert report["verdict"] == replay.DROP
    assert exit_code == 0
    assert "material_disagreement" in report["drop_reasons"]
    assert report["rows"][0]["classification"] == "material"


# ---------------------------------------------------------------------------
# Case 3: differing chosen_value -> DROP/material.
# ---------------------------------------------------------------------------
def test_differing_chosen_value_is_material_and_drops():
    inputs = [_input("102:0")]
    call_model = _by_model({
        MODEL_A: _verdict(chosen_value="governing_body_league"),
        MODEL_B: _verdict(chosen_value="content_producer"),
    })
    report, exit_code = replay.build_report(inputs, call_model, MODEL_A, MODEL_B, min_corpus=1)
    assert report["verdict"] == replay.DROP
    assert "material_disagreement" in report["drop_reasons"]
    assert report["rows"][0]["classification"] == "material"


# ---------------------------------------------------------------------------
# Case 4: differing confidence/prose only -> immaterial, still SHIP.
# ---------------------------------------------------------------------------
def test_differing_confidence_and_prose_only_is_immaterial_and_ships():
    inputs = [_input("103:0")]
    call_model = _by_model({
        MODEL_A: _verdict(confidence=88, reason="reason A", evidence_summary="summary A"),
        MODEL_B: _verdict(confidence=81, reason="reason B", evidence_summary="summary B"),
    })
    report, exit_code = replay.build_report(inputs, call_model, MODEL_A, MODEL_B, min_corpus=1)
    assert report["rows"][0]["classification"] == "immaterial"
    assert report["verdict"] == replay.SHIP
    assert exit_code == 0
    assert report["counts"]["material"] == 0


# ---------------------------------------------------------------------------
# Case 5: one model returning None -> material.
# ---------------------------------------------------------------------------
def test_one_model_returning_none_is_material():
    inputs = [_input("104:0")]
    call_model = _by_model({MODEL_A: _verdict(), MODEL_B: None})
    report, exit_code = replay.build_report(inputs, call_model, MODEL_A, MODEL_B, min_corpus=1)
    assert report["rows"][0]["classification"] == "material"
    assert report["verdict"] == replay.DROP
    assert "material_disagreement" in report["drop_reasons"]


# ---------------------------------------------------------------------------
# Case 6: both models returning None -> both_unparseable, never an agreement.
# Mixed with one genuinely agreeing row so the corpus isn't all-unparseable
# (that combination is HARNESS_FAILURE — case 8). min_corpus=2 so the
# excluded both_unparseable row also produces insufficient_corpus, proving it
# was excluded from "compared" rather than silently counted.
# ---------------------------------------------------------------------------
def test_both_models_returning_none_is_both_unparseable_not_agreement():
    inputs = [_input("105:0"), _input("105:1")]
    call_model = _by_model({MODEL_A: _verdict(), MODEL_B: _verdict()})

    def _mixed(model, body):
        if body is inputs[1]["judge_request_body"]:
            return None
        return call_model(model, body)

    report, exit_code = replay.build_report(inputs, _mixed, MODEL_A, MODEL_B, min_corpus=2)
    by_id = {r["input_id"]: r for r in report["rows"]}
    assert by_id["105:0"]["classification"] == "agree"
    assert by_id["105:1"]["classification"] == "both_unparseable"
    assert report["counts"]["both_unparseable"] == 1
    # the both_unparseable row never counts as compared, so this 2-row corpus
    # only has 1 compared input against a minimum of 2 -> DROP, never SHIP.
    assert report["inputs_compared"] == 1
    assert report["verdict"] == replay.DROP
    assert "insufficient_corpus" in report["drop_reasons"]


# ---------------------------------------------------------------------------
# Case 7: empty input list -> HARNESS_FAILURE, non-zero exit.
# ---------------------------------------------------------------------------
def test_empty_input_list_is_harness_failure():
    report, exit_code = replay.build_report([], _always(_verdict()), MODEL_A, MODEL_B)
    assert report["verdict"] == replay.HARNESS_FAILURE
    assert exit_code != 0
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Case 8: call_model that always raises -> HARNESS_FAILURE, non-zero exit.
# A run that checked nothing must never report success.
# ---------------------------------------------------------------------------
def test_call_model_always_raising_is_harness_failure():
    inputs = [_input(f"106:{i}") for i in range(5)]

    def _raiser(model, body):
        raise RuntimeError("simulated Anthropic transport failure")

    report, exit_code = replay.build_report(inputs, _raiser, MODEL_A, MODEL_B, min_corpus=1)
    assert report["verdict"] == replay.HARNESS_FAILURE
    assert exit_code == 1
    assert report["inputs_compared"] == 0
    assert report["counts"]["both_unparseable"] == 5


# ---------------------------------------------------------------------------
# Case 9: a single-element input list -> DROP/insufficient_corpus, never SHIP.
# ---------------------------------------------------------------------------
def test_single_element_corpus_is_insufficient_corpus_never_ships():
    inputs = [_input("107:0")]
    report, exit_code = replay.build_report(inputs, _always(_verdict()), MODEL_A, MODEL_B)
    assert replay.DEFAULT_MIN_CORPUS == 10  # the default this test relies on
    assert report["verdict"] == replay.DROP
    assert "insufficient_corpus" in report["drop_reasons"]
    assert report["verdict"] != replay.SHIP


# ---------------------------------------------------------------------------
# Case 10: determinism — two runs over the same shuffled input list emit rows
# in identical, ascending (execution id, item index) order.
# ---------------------------------------------------------------------------
def test_determinism_of_row_order_across_shuffles():
    ids = [f"{execution}:{idx}" for execution in (5, 20, 3) for idx in (2, 0, 1)]
    inputs_a = [_input(i) for i in ids]
    inputs_b = list(inputs_a)
    random.Random(42).shuffle(inputs_a)
    random.Random(7).shuffle(inputs_b)

    call_model = _always(_verdict())
    report_a, _ = replay.build_report(inputs_a, call_model, MODEL_A, MODEL_B, min_corpus=1)
    report_b, _ = replay.build_report(inputs_b, call_model, MODEL_A, MODEL_B, min_corpus=1)

    order_a = [r["input_id"] for r in report_a["rows"]]
    order_b = [r["input_id"] for r in report_b["rows"]]
    assert order_a == order_b
    expected = sorted(ids, key=replay._input_sort_key)
    assert order_a == expected


# ---------------------------------------------------------------------------
# Row schema — no request body, company name, or evidence URL ever lands in a
# written row.
# ---------------------------------------------------------------------------
def test_row_schema_never_carries_request_body_or_evidence():
    inputs = [_input(f"108:{i}") for i in range(3)]
    report, _ = replay.build_report(inputs, _always(_verdict()), MODEL_A, MODEL_B, min_corpus=1)
    for row in report["rows"]:
        assert set(row.keys()) == {"input_id", "lane", "body_sha256", "classification", "model_a", "model_b"}
        assert "judge_request_body" not in row
        assert "evidence_url" not in row
        assert "evidence_summary" not in row
        assert set(row["model_a"].keys()) == {"decision", "chosen_value"}
        assert set(row["model_b"].keys()) == {"decision", "chosen_value"}


# ---------------------------------------------------------------------------
# The live call site sends the STORED body with the model overridden per
# call, never the stored (baked) model twice — the mechanism that keeps a
# replay from vacuously "agreeing" with itself.
# ---------------------------------------------------------------------------
def test_build_report_passes_the_compared_model_not_a_stored_one():
    # A stored body deliberately carries a THIRD model id (what a real n8n
    # Code node bakes in via buildJudgeRequestBody) that is neither of the two
    # models under comparison — proving build_report/call_model never reads a
    # model off the stored body itself.
    stored_model = "claude-baked-production-model"
    inputs = [_input("109:0", extra={
        "judge_request_body": {"model": stored_model, "messages": []},
    })]
    seen = []

    def _spy(model, body):
        seen.append(model)
        assert body["model"] == stored_model  # the stored body is passed through unmodified
        return _verdict()

    replay.build_report(inputs, _spy, MODEL_A, MODEL_B, min_corpus=1)
    # The two calls used the models under comparison, not the stored one — a
    # live caller (_live_call_model) is responsible for overriding `model` on
    # the body it actually sends; build_report itself never reads or trusts
    # a model id embedded in the stored payload.
    assert seen == [MODEL_A, MODEL_B]
    assert stored_model not in seen


# ---------------------------------------------------------------------------
# confidence_band_only — the class selector.
# ---------------------------------------------------------------------------
def test_confidence_band_only_selects_exactly_the_single_reason_class():
    corpus = [
        _input("110:0"),
        {**_input("110:1"), "judge_reasons": ["confidence_band", "org_type_conflict"]},
        {**_input("110:2"), "judge_reasons": ["hardware_vendor_detected"]},
        {**_input("110:3"), "judge_reasons": []},
    ]
    band_only = replay.confidence_band_only(corpus)
    assert [i["input_id"] for i in band_only] == ["110:0"]


# ---------------------------------------------------------------------------
# _normalize_value — string case/whitespace + truthy/falsy mapping.
# ---------------------------------------------------------------------------
def test_normalize_value_maps_truthy_falsy_and_case():
    assert replay._normalize_value(" True ") is True
    assert replay._normalize_value("NO") is False
    assert replay._normalize_value("  Governing_Body_League ") == "governing_body_league"
    assert replay._normalize_value(42) == 42
    assert replay._normalize_value(None) is None


# ---------------------------------------------------------------------------
# _parse_verdict — a dict missing a required key is unparseable, never a guess.
# ---------------------------------------------------------------------------
def test_parse_verdict_requires_every_key():
    full = _verdict()
    assert replay._parse_verdict(full, REQUIRED_KEYS) == full
    missing = dict(full)
    del missing["chosen_field"]
    assert replay._parse_verdict(missing, REQUIRED_KEYS) is None
    assert replay._parse_verdict(None, REQUIRED_KEYS) is None
    assert replay._parse_verdict("not a dict", REQUIRED_KEYS) is None


# ---------------------------------------------------------------------------
# Source-level guard: no write verb, no HubSpot base URL, anywhere in this
# module — T-63-13's mitigation, proven by scanning the source text.
# ---------------------------------------------------------------------------
def test_module_source_contains_no_write_verbs_or_hubspot_url():
    for verb in ("requests.post", "requests.put", "requests.patch", "requests.delete"):
        assert verb not in MODULE_SOURCE, f"forbidden write verb found: {verb}"
    assert "api.hubapi.com" not in MODULE_SOURCE
    assert "hubapi.com" not in MODULE_SOURCE


def test_module_docstring_names_all_three_verdicts_as_bare_tokens():
    tokens = set(MODULE_SOURCE.split())
    assert {"SHIP", "DROP", "HARNESS_FAILURE"} <= tokens


def test_min_corpus_default_is_ten_and_exposed_as_cli_flag():
    assert replay.DEFAULT_MIN_CORPUS == 10
    assert re.search(r"--min-corpus", MODULE_SOURCE)
