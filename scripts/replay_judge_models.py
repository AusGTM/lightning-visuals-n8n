#!/usr/bin/env python3
"""scripts/replay_judge_models.py

Phase 63 Plan 03 (D-63-06) — offline replay of two judge models over stored
`confidence_band`-only judge inputs pulled from past n8n executions, deciding
whether Haiku 4.5 is adequate to replace Sonnet 5 on that record class (D-63-05
lever 2). No provider credit, no HubSpot write, and no NEW n8n execution is
ever produced by this module — it reads work that already happened and makes
Anthropic Messages calls only.

Two-phase CLI, deliberately decoupled so their credential preconditions differ:

  --extract   Reads N8N_URL / N8N_API_KEY. Walks the n8n executions API (GET
              only, reusing scripts/enrichment_cost_ledger.py's readers),
              pulls stored judge_request_body items from "Build Judge Request"
              (companies lane) and "Build Contact Judge Request" (contacts
              lane), and caches them to a gitignored working directory
              (default .judge-replay-corpus/). Also prints the reasons[]
              distribution over the extracted corpus (D-63-07's by-product,
              not a separate task).

  --replay    Reads ANTHROPIC_API_KEY only — makes exactly two Anthropic
              Messages calls per confidence_band-only cached input, and writes
              the committed verdict artifact. Never re-touches n8n; refuses by
              name if no cached corpus exists.

Only n8n verb anywhere in this module: GET. Only write verbs anywhere: local
files (the corpus cache, the verdict artifact). No POST/PUT/PATCH/DELETE to
n8n or to any HubSpot base URL exists in this module, live or otherwise.

`main()`'s `--replay` path resolves the two compared model ids from
scripts/build_cloud_workflows.py's CONFIG_FLAG_DEFAULTS, imported LAZILY
inside `_resolve_model_ids()` — never at module import time. Importing that
module regenerates n8n/code/*.generated.js as a side effect (deterministic
from config/escalation_policy.yaml and config/taxonomy.yaml — a diff there is
pre-existing drift this harness would surface, not cause), and a bare pytest
import of this module must never trigger that write.

Corpus item ids ("{execution_id}:{item_index}") use ONE running counter per
execution across BOTH lanes (companies node output counted before contacts
node output, in n8n's own runData order) — not a per-lane counter — so ids
never collide within one execution and re-extracting the same executions
reproduces the same ids, deterministically.

"Compared" (the number that gates HARNESS_FAILURE and the min-corpus check)
counts only rows where AT LEAST ONE model produced a usable verdict
(classification agree / immaterial / material). A `both_unparseable` row —
neither model returned a usable verdict — is recorded in the report but
EXCLUDED from that count: it must never dilute the SHIP bar towards a false
adequacy claim (a model response that is null, empty, or unparseable must
never become an implicit agreement). A corpus that compares to zero — an
empty input list, every model call raising, or every row landing
both_unparseable for any other reason — is HARNESS_FAILURE, never a silent
"the models agreed" (D-13's zero-assertions rule, restated here).

Verdict vocabulary: SHIP DROP HARNESS_FAILURE
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

from enrichment_cost_ledger import _get_execution, _list_executions, _node_output_items  # noqa: E402

DEFAULT_CORPUS_DIR = ROOT / ".judge-replay-corpus"
DEFAULT_REPORT_DIR = ROOT / ".planning" / "phases" / "63-the-unattended-lane-actually-runs-unattended"
VERDICT_ARTIFACT_NAME = "63-JUDGE-REPLAY-VERDICT.json"
ESCALATION_POLICY_PATH = ROOT / "config" / "escalation_policy.yaml"

# The two node names judge.js's inlined "Build Judge Request" (companies) and
# "Build Contact Judge Request" (contacts) Code nodes are built as. Every row
# passes through, judge-needing or not — only rows with a non-null
# judge_request_body are kept (n8n/code/judge.js buildJudgeRequestBody caller).
COMPANIES_NODE = "Build Judge Request"
CONTACTS_NODE = "Build Contact Judge Request"

DEFAULT_MIN_CORPUS = 10
DEFAULT_LIST_LIMIT = 100

SHIP = "SHIP"
DROP = "DROP"
HARNESS_FAILURE = "HARNESS_FAILURE"


def _load_required_verdict_keys() -> list:
    """The judge verdict's required key set, read from config/escalation_policy.yaml
    (the single source), plus "chosen_field" — added by n8n/code/judge.js's
    buildJudgeRequestBody system prompt but never listed in output_required."""
    with ESCALATION_POLICY_PATH.open() as f:
        policy = yaml.safe_load(f)
    required = list(policy["sonnet_5"]["output_required"])
    required.append("chosen_field")
    return required


def _canonical_sha256(obj) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =====================================================================================
# Corpus extraction — GET only.
# =====================================================================================

def extract_corpus(execution_ids=None, limit=DEFAULT_LIST_LIMIT) -> dict:
    """Walk n8n executions (GET only, via scripts/enrichment_cost_ledger.py's
    readers) and pull stored judge_request_body items.

    execution_ids, if given, replaces the _list_executions(limit) call with an
    explicit id list (test/CLI convenience) — still exactly one _get_execution
    GET per id, still no other n8n verb.

    Returns {corpus: [...], total_executions_scanned, total_judge_inputs_found,
    per_lane_counts: {companies, contacts}, reasons_distribution: {by_reason,
    by_reason_set}}. Each corpus item: input_id, lane, judge_reasons,
    judge_request_body, body_sha256. The reasons[] distribution and per-lane
    counts are computed over every kept item — a by-product of extraction, not
    a separate measurement pass (D-63-07).
    """
    if execution_ids is None:
        listed = _list_executions(limit=limit)
        execution_ids = [
            e.get("id") for e in listed if isinstance(e, dict) and e.get("id") is not None
        ]

    corpus = []
    per_lane_counts = {"companies": 0, "contacts": 0}
    reason_counts = {}
    reason_set_counts = {}
    scanned = 0

    for execution_id in execution_ids:
        try:
            execution = _get_execution(execution_id)
        except Exception:  # noqa: BLE001 — one bad execution must not sink the whole extraction
            continue
        scanned += 1

        run_data = (((execution or {}).get("data") or {}).get("resultData") or {}).get("runData")
        if not isinstance(run_data, dict):
            continue

        item_index = 0  # ONE counter across both lanes, per execution — see module docstring
        for lane, node_name in (("companies", COMPANIES_NODE), ("contacts", CONTACTS_NODE)):
            runs = run_data.get(node_name)
            if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
                continue
            for item in _node_output_items(runs[0]):
                current_index = item_index
                item_index += 1
                payload = item.get("json") if isinstance(item, dict) else None
                if not isinstance(payload, dict):
                    continue
                body = payload.get("judge_request_body")
                if body is None:
                    continue

                reasons = list(payload.get("judge_reasons") or [])
                for r in reasons:
                    reason_counts[r] = reason_counts.get(r, 0) + 1
                reason_set_key = ",".join(sorted(reasons))
                reason_set_counts[reason_set_key] = reason_set_counts.get(reason_set_key, 0) + 1

                corpus.append({
                    "input_id": f"{execution_id}:{current_index}",
                    "lane": lane,
                    "judge_reasons": reasons,
                    "judge_request_body": body,
                    "body_sha256": _canonical_sha256(body),
                })
                per_lane_counts[lane] += 1

    return {
        "corpus": corpus,
        "total_executions_scanned": scanned,
        "total_judge_inputs_found": len(corpus),
        "per_lane_counts": per_lane_counts,
        "reasons_distribution": {"by_reason": reason_counts, "by_reason_set": reason_set_counts},
    }


def confidence_band_only(corpus) -> list:
    """The subset of a corpus list whose judge_reasons is EXACTLY one element
    equal to "confidence_band" — the only class D-63-06 is evidence about."""
    return [item for item in corpus if list(item.get("judge_reasons") or []) == ["confidence_band"]]


# =====================================================================================
# Comparison core — pure, offline-testable, no network access of its own.
# =====================================================================================

def _input_sort_key(input_id: str):
    """Ascending execution id (numeric), then ascending item index (numeric)
    within that execution — a stable, diffable row order. An id that doesn't
    parse as "{int}:{int}" sorts after every well-formed id rather than
    raising, so a malformed corpus entry never crashes the report."""
    exec_part, _, idx_part = str(input_id).partition(":")
    try:
        return (0, int(exec_part), int(idx_part))
    except ValueError:
        return (1, str(input_id), 0)


def _normalize_value(v):
    """Lowercase/strip strings; map the usual truthy/falsy spellings to real
    booleans. Anything else (numbers, None, already-boolean, lists) passes
    through unchanged."""
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
        return s
    return v


def _parse_verdict(response, required_keys):
    """response: whatever call_model returned — a dict, or None. Returns the
    dict unchanged only if it carries EVERY required_keys entry; None
    otherwise. Never raises — ambiguity fails to "unparseable", never to a
    guess."""
    if not isinstance(response, dict):
        return None
    for key in required_keys:
        if key not in response:
            return None
    return response


def _classify(parsed_a, parsed_b) -> str:
    usable_a = parsed_a is not None
    usable_b = parsed_b is not None
    if not usable_a and not usable_b:
        return "both_unparseable"
    if usable_a != usable_b:
        return "material"

    decision_a, decision_b = parsed_a.get("decision"), parsed_b.get("decision")
    field_a, field_b = parsed_a.get("chosen_field"), parsed_b.get("chosen_field")
    value_a = _normalize_value(parsed_a.get("chosen_value"))
    value_b = _normalize_value(parsed_b.get("chosen_value"))
    core_matches = (decision_a == decision_b) and (field_a == field_b) and (value_a == value_b)
    if not core_matches:
        return "material"

    immaterial_matches = (
        parsed_a.get("confidence") == parsed_b.get("confidence")
        and parsed_a.get("reason") == parsed_b.get("reason")
        and parsed_a.get("evidence_summary") == parsed_b.get("evidence_summary")
        and parsed_a.get("evidence_url") == parsed_b.get("evidence_url")
    )
    return "agree" if immaterial_matches else "immaterial"


def build_report(inputs, call_model, model_a, model_b, min_corpus=DEFAULT_MIN_CORPUS):
    """The comparison core. Pure and offline-testable: `call_model(model,
    request_body) -> dict | None` is injected, and this function performs no
    network access, import-time or call-time, of its own.

    For each input, in ascending input_id order, calls both models (a raising
    call_model is caught PER CALL and treated as no usable verdict for that
    call — it never crashes the replay and never masks a real result on the
    other model), classifies the pair (agree / immaterial / material /
    both_unparseable — see _classify), and derives one verdict:

      HARNESS_FAILURE — zero inputs compared (empty input list, every model
                         call raised, or every row otherwise landed
                         both_unparseable). Exit code 1 — the only verdict
                         with a non-zero exit.
      DROP             — one or more material classifications, OR the
                         compared count is below min_corpus
                         ("insufficient_corpus"). Exit code 0.
      SHIP              — at least min_corpus inputs compared and zero
                         material classifications. Exit code 0.

    Returns (report_dict, exit_code). report_dict["rows"] carries, per input:
    input_id, lane, body_sha256, classification, and each model's decision +
    normalised chosen_value — never the request body, a company name, or an
    evidence URL.
    """
    required_keys = _load_required_verdict_keys()
    ordered_inputs = sorted(inputs, key=lambda i: _input_sort_key(i["input_id"]))

    rows = []
    counts = {"agree": 0, "immaterial": 0, "material": 0, "both_unparseable": 0}
    material_rows = []

    for inp in ordered_inputs:
        body = inp["judge_request_body"]
        try:
            response_a = call_model(model_a, body)
        except Exception:  # noqa: BLE001 — a raising model must not crash the replay
            response_a = None
        try:
            response_b = call_model(model_b, body)
        except Exception:  # noqa: BLE001
            response_b = None

        parsed_a = _parse_verdict(response_a, required_keys)
        parsed_b = _parse_verdict(response_b, required_keys)
        classification = _classify(parsed_a, parsed_b)
        counts[classification] += 1

        row = {
            "input_id": inp["input_id"],
            "lane": inp.get("lane"),
            "body_sha256": inp.get("body_sha256") or _canonical_sha256(body),
            "classification": classification,
            "model_a": {
                "decision": parsed_a.get("decision") if parsed_a else None,
                "chosen_value": _normalize_value(parsed_a.get("chosen_value")) if parsed_a else None,
            },
            "model_b": {
                "decision": parsed_b.get("decision") if parsed_b else None,
                "chosen_value": _normalize_value(parsed_b.get("chosen_value")) if parsed_b else None,
            },
        }
        rows.append(row)
        if classification == "material":
            material_rows.append(row)

    inputs_compared = counts["agree"] + counts["immaterial"] + counts["material"]

    drop_reasons = []
    if counts["material"] > 0:
        drop_reasons.append("material_disagreement")
    if 0 < inputs_compared < min_corpus:
        drop_reasons.append("insufficient_corpus")

    if inputs_compared == 0:
        verdict = HARNESS_FAILURE
        exit_code = 1
    elif drop_reasons:
        verdict = DROP
        exit_code = 0
    else:
        verdict = SHIP
        exit_code = 0

    report = {
        "verdict": verdict,
        "model_a": model_a,
        "model_b": model_b,
        "min_corpus": min_corpus,
        "total_inputs": len(ordered_inputs),
        "inputs_compared": inputs_compared,
        "counts": counts,
        "drop_reasons": drop_reasons,
        "material_rows": material_rows,
        "rows": rows,
    }
    return report, exit_code


def _write_report(report: dict, report_dir=DEFAULT_REPORT_DIR) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / VERDICT_ARTIFACT_NAME
    payload = {**report, "written_at_utc": _utc_now_iso()}
    with path.open("w") as f:
        json.dump(payload, f, indent=2, sort_keys=True, default=str)
    return path


# =====================================================================================
# Corpus cache — the local, gitignored hand-off between --extract and --replay.
# =====================================================================================

def _corpus_cache_path(corpus_dir) -> Path:
    return Path(corpus_dir) / "corpus.json"


def _write_corpus_cache(extraction: dict, corpus_dir=DEFAULT_CORPUS_DIR) -> Path:
    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    path = _corpus_cache_path(corpus_dir)
    payload = {**extraction, "extracted_at_utc": _utc_now_iso()}
    with path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def _read_corpus_cache(corpus_dir=DEFAULT_CORPUS_DIR) -> dict:
    path = _corpus_cache_path(corpus_dir)
    if not path.exists():
        raise SystemExit(f"REFUSED: no cached corpus at {path}. Run --extract first.")
    with path.open() as f:
        return json.load(f)


# =====================================================================================
# Live shell — the only place this module touches Anthropic or reads env credentials.
# =====================================================================================

def _live_call_model(model, request_body):
    """The --replay live model caller. Sends the STORED body with its `model`
    key OVERRIDDEN to the model under comparison for this call — the stored
    body carries whichever production model built it baked in
    (n8n/code/judge.js buildJudgeRequestBody), so posting it unmodified would
    silently call the same model twice and manufacture a vacuous agreement.

    Lets a transport/API exception RAISE (build_report catches it per-call and
    it counts toward the all-raised HARNESS_FAILURE path) — returns None only
    when a response arrived but did not parse as the required JSON shape.
    Same SDK-content-is-a-list-of-blocks handling as src/validator_sonnet.py,
    and deliberately no `temperature` override — claude-sonnet-5 400s on a
    non-default temperature (validator_sonnet.py's own comment is the receipt).
    """
    from anthropic import Anthropic

    from src.classifier_haiku import _parse_json, _response_text

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    call_kwargs = {**request_body, "model": model}
    msg = client.messages.create(**call_kwargs)
    try:
        return _parse_json(_response_text(msg))
    except (ValueError, TypeError):
        return None


def _resolve_model_ids():
    """Lazily imports scripts.build_cloud_workflows — a module-level side
    effect (regenerates n8n/code/*.generated.js, deterministic from the YAML
    sources) that is acceptable at CLI-invocation time but must never fire on
    a bare pytest import of THIS module, hence the import lives inside this
    function, not at module top level."""
    import build_cloud_workflows

    defaults = build_cloud_workflows.CONFIG_FLAG_DEFAULTS
    model_a = defaults["ANTHROPIC_JUDGE_MODEL"]
    model_b = defaults.get("ANTHROPIC_JUDGE_MODEL_CHEAP", "claude-haiku-4-5")
    return model_a, model_b


def _print_extraction_summary(extraction: dict) -> None:
    band_only = confidence_band_only(extraction["corpus"])
    print(f"executions scanned: {extraction['total_executions_scanned']}")
    print(f"judge inputs found: {extraction['total_judge_inputs_found']}")
    print(f"confidence_band-only subset: {len(band_only)}")
    print("per-lane split:")
    for lane, count in extraction["per_lane_counts"].items():
        print(f"  {lane}: {count}")
    print("reasons[] distribution (by_reason):")
    for reason, count in sorted(extraction["reasons_distribution"]["by_reason"].items()):
        print(f"  {reason}: {count}")
    print("reasons[] distribution (by_reason_set):")
    for reason_set, count in sorted(extraction["reasons_distribution"]["by_reason_set"].items()):
        print(f"  [{reason_set}]: {count}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--extract", action="store_true", default=False,
                         help="Pull the corpus from n8n executions (GET only) and cache it.")
    parser.add_argument("--replay", action="store_true", default=False,
                         help="Compare both models over the cached confidence_band-only corpus.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIST_LIMIT,
                         help="Max executions to list for --extract.")
    parser.add_argument("--min-corpus", type=int, default=DEFAULT_MIN_CORPUS,
                         help="Minimum confidence_band-only inputs compared before SHIP is reachable.")
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR),
                         help="Gitignored working directory for the cached corpus.")
    args = parser.parse_args(argv)

    if not args.extract and not args.replay:
        print("Nothing to do — pass --extract, --replay, or both.")
        return 1

    corpus_dir = Path(args.corpus_dir)
    exit_code = 0

    if args.extract:
        if not (os.getenv("N8N_URL") and os.getenv("N8N_API_KEY")):
            print("REFUSED: N8N_URL and N8N_API_KEY must both be set to run extraction. "
                  "No n8n call made.")
            return 1
        extraction = extract_corpus(limit=args.limit)
        _write_corpus_cache(extraction, corpus_dir=corpus_dir)
        _print_extraction_summary(extraction)

    if args.replay:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("REFUSED: ANTHROPIC_API_KEY must be set to run the replay. "
                  "No Anthropic call made.")
            return 1
        extraction = _read_corpus_cache(corpus_dir=corpus_dir)
        band_only = confidence_band_only(extraction.get("corpus") or [])
        model_a, model_b = _resolve_model_ids()
        report, exit_code = build_report(
            band_only, _live_call_model, model_a, model_b, min_corpus=args.min_corpus
        )
        report["corpus_provenance"] = {
            "total_executions_scanned": extraction.get("total_executions_scanned"),
            "total_judge_inputs_found": extraction.get("total_judge_inputs_found"),
            "per_lane_counts": extraction.get("per_lane_counts"),
            "confidence_band_only_count": len(band_only),
        }
        report["reasons_distribution"] = extraction.get("reasons_distribution")
        path = _write_report(report)
        print(f"wrote {path}")
        print(f"verdict: {report['verdict']}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
