#!/usr/bin/env python3
"""scripts/enrichment_cost_ledger.py

Phase 22 Plan 01 Task 2 built the TOKEN-USAGE half (list/extract/capture over n8n's
executions API). Phase 22 Plan 03 adds the PROVIDER-CREDIT half plus the cited 2026-07-30
estimates baseline and the estimate-versus-actual report, so the whole point of an armed
canary window — "what does one enriched record actually cost?" — has one answer.

Subcommands:

  list       (Plan 01) GET a small page of the executions collection.
  extract    (Plan 01) GET one execution; print Anthropic token usage per node.
  capture    (Plan 01) Same GET; write a redacted allow-listed fixture.
  credits    (Plan 03) Balance snapshot over the CONFIGURED providers' usage endpoints,
             reusing check_provider_credits.py's per-provider check functions by import
             (never a new HTTP client, never a match/enrich endpoint). `--settle` makes
             this a settled AFTER-capture: waits, then re-reads until stable or bounded
             out (docs/LUSHA-V3-CONTRACT.md §1's ~4s Lusha eventual-consistency lag).
             Writes a snapshot JSON to the phase's snapshots directory.
  diff       (Plan 03) Pure diff of two snapshot JSON files -> per-provider spend, with
             unknown propagation and top-up-anomaly detection.
  report     (Plan 03) Provider credit diff + Anthropic token usage (from a live
             --execution-id or a --fixture file, e.g. Plan 01's committed fixture) priced
             against the cited estimates baseline -> three printed blocks + a per-record
             figure, marked partial whenever any input was unknown.
  estimates  (Plan 03) Print the cited 2026-07-30 estimates baseline table.
  durations  (29-02) Per recent execution of a named workflow: wall-clock duration
             (stoppedAt - startedAt, data this ledger already fetched and never used),
             the record count recovered from its write nodes, and the derived
             seconds-per-record — plus a summary carrying the max and a high percentile,
             with unknowns counted separately and never averaged in as zero. Reads only.

Reuses `_has_n8n()`/`_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from
scripts/deploy_n8n_workflows.py for the token half, and imports
scripts/check_provider_credits.py wholesale (`_HAS`/`_CHECK`/`_is_number`/PROVIDER_REGISTRY)
for the credit half — one module owns each concern; this ledger never re-derives either.
No PATCH/POST path to n8n or a provider match/enrich endpoint exists here — only usage/
executions reads. Prints only counts, node names, models, token counters and credit
balances — never a credential value, a full node body, or a prompt (T-22-02, T-22-13).

Usage:
    python scripts/enrichment_cost_ledger.py list
    python scripts/enrichment_cost_ledger.py extract --execution-id 12345
    python scripts/enrichment_cost_ledger.py capture --execution-id 12345
    python scripts/enrichment_cost_ledger.py credits --label pre-canary
    python scripts/enrichment_cost_ledger.py credits --label post-canary --settle
    python scripts/enrichment_cost_ledger.py diff --before snap1.json --after snap2.json
    python scripts/enrichment_cost_ledger.py report --before snap1.json --after snap2.json \\
        --fixture tests/fixtures/n8n/execution_rundata_usage.json --record-count 1
    python scripts/enrichment_cost_ledger.py estimates
    python scripts/enrichment_cost_ledger.py durations --limit 50
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_n8n_workflows import _has_n8n, _base_url, _n8n_headers, _get_live_workflows  # noqa: E402
import check_provider_credits as credit_checker  # noqa: E402 — reused by import, never copied (T-22-12)

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "n8n" / "execution_rundata_usage.json"
ENRICHMENT_WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"
SNAPSHOTS_DIR = ROOT / ".planning" / "phases" / "22-armed-e2e-enrichment-canary" / "snapshots"

# The four httpRequest nodes calling api.anthropic.com/v1/messages directly (company +
# contact lanes, research + judge) — pinned so a node rename can't leave this ledger
# silently reading nothing. tests/test_enrichment_cost_ledger.py asserts every one of
# these names exists in the committed cloud workflow JSON.
ANTHROPIC_NODE_NAMES = ("Claude Web Research", "Judge Call", "Contact Web Research", "Contact Judge Call")

USAGE_COUNTERS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

DEFAULT_SETTLE_INTERVAL_SECONDS = 5
DEFAULT_SETTLE_MAX_ATTEMPTS = 4


# =====================================================================================
# Plan 03 Task 2 — cited 2026-07-30 estimates baseline. ONE module-level table, the only
# source every report comparison reads. Every entry names the document (+ section) it was
# measured or inferred from; a missing figure is recorded `value: None` with a `confidence`
# note naming what must supply it — never fabricated (T-22-14: a wrong-but-confident
# baseline is worse than a visibly missing one).
# =====================================================================================
ESTIMATES = {
    "lusha_contacts_first_time_enrich": {
        "value": 1, "unit": "credits/contact",
        "citation": "docs/LUSHA-V3-CONTRACT.md — §7-8, live 2026-07-30 probe (first-time contacts enrich)",
        "confidence": "measured",
    },
    "lusha_companies_match": {
        "value": 2, "unit": "credits/company",
        "citation": "docs/LUSHA-V3-CONTRACT.md — §5, live 2026-07-30 probe (companies combined match+enrich call)",
        "confidence": "measured",
    },
    "lusha_contacts_stored_id_reuse": {
        "value": 0, "unit": "credits/contact",
        "citation": "docs/LUSHA-V3-CONTRACT.md — §8, 4/4 stored-id /contacts/enrich calls billed 0 credits",
        "confidence": "measured",
    },
    "zoominfo_per_match": {
        "value": 1.08, "unit": "credits/match",
        "citation": (".planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/22-RESEARCH.md — Assumption A3 "
                     "(v2-era measurement; ZoomInfo pricing is unaffected by the Lusha-only v3 migration)"),
        "confidence": "inferred (measured pre-v3, carried forward — no ZoomInfo pricing change this milestone)",
    },
    "apollo_per_match": {
        "value": None, "unit": "credits/match",
        "citation": ("scripts/check_provider_credits.py — this account's APOLLO_API_KEY is non-master, "
                     "live 403 on the usage endpoint"),
        "confidence": "unknown — no committed document states this account's Apollo per-match cost",
    },
    "anthropic_research_model_input_per_mtok": {
        "value": 1.00, "unit": "USD/million input tokens (claude-haiku-4-5)",
        "citation": ".planning/milestones/v0.3-phases/14-judge-wiring/RESEARCH.md — Model/Cost Analysis table",
        "confidence": "measured (WebSearch-sourced against Anthropic's model catalog, cross-checked twice)",
    },
    "anthropic_research_model_output_per_mtok": {
        "value": 5.00, "unit": "USD/million output tokens (claude-haiku-4-5)",
        "citation": ".planning/milestones/v0.3-phases/14-judge-wiring/RESEARCH.md — Model/Cost Analysis table",
        "confidence": "measured (WebSearch-sourced against Anthropic's model catalog, cross-checked twice)",
    },
    "anthropic_judge_model_input_per_mtok": {
        "value": 2.00,
        "unit": "USD/million input tokens (claude-sonnet-5, intro pricing thru 2026-08-31; $3.00 standard after)",
        "citation": ".planning/milestones/v0.3-phases/14-judge-wiring/RESEARCH.md — Model/Cost Analysis table",
        "confidence": "measured (intro pricing, time-bound — re-check after 2026-08-31)",
    },
    "anthropic_judge_model_output_per_mtok": {
        "value": 10.00,
        "unit": "USD/million output tokens (claude-sonnet-5, intro pricing thru 2026-08-31; $15.00 standard after)",
        "citation": ".planning/milestones/v0.3-phases/14-judge-wiring/RESEARCH.md — Model/Cost Analysis table",
        "confidence": "measured (intro pricing, time-bound — re-check after 2026-08-31)",
    },
    "haiku_research_call_allin_estimate": {
        "value": 0.07, "unit": "USD/company research call (tokens + web-search fees, all-in)",
        "citation": (".planning/quick/260730-fij-enable-web-research-haiku/260730-fij-SUMMARY.md — "
                     "Cost Note"),
        "confidence": "rough (operator-stated estimate recorded at the time of the Haiku research-model swap)",
    },
}

# Per-model $/MTok, derived from ESTIMATES above (never re-typed).
MODEL_PRICES = {
    "claude-haiku-4-5": {
        "input_per_mtok": ESTIMATES["anthropic_research_model_input_per_mtok"]["value"],
        "output_per_mtok": ESTIMATES["anthropic_research_model_output_per_mtok"]["value"],
    },
    "claude-sonnet-5": {
        "input_per_mtok": ESTIMATES["anthropic_judge_model_input_per_mtok"]["value"],
        "output_per_mtok": ESTIMATES["anthropic_judge_model_output_per_mtok"]["value"],
    },
}

# Which ESTIMATES entry a given provider's credit spend compares against. Lusha's dominant
# per-record cost is the first-time contacts enrich; the id-reuse/companies variants stay
# in ESTIMATES for the operator to read directly (22-LEDGER.md), not folded into this map.
PROVIDER_ESTIMATE_KEY = {
    "lusha": "lusha_contacts_first_time_enrich",
    "zoominfo": "zoominfo_per_match",
    "apollo": "apollo_per_match",
}


def print_estimates() -> None:
    print("2026-07-30 cost estimates baseline (cited):")
    for key, entry in ESTIMATES.items():
        value = "unknown" if entry["value"] is None else entry["value"]
        print(f"  {key}: {value} {entry['unit']}")
        print(f"    source: {entry['citation']}")
        print(f"    confidence: {entry['confidence']}")


# =====================================================================================
# Plan 01 Task 2 — token-usage half (unchanged).
# =====================================================================================

def _get_execution(execution_id: str) -> dict:
    import requests
    r = requests.get(
        f"{_base_url()}/api/v1/executions/{execution_id}",
        params={"includeData": "true"},
        headers=_n8n_headers(), timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _list_executions(limit: int = 20) -> list:
    import requests
    r = requests.get(
        f"{_base_url()}/api/v1/executions",
        params={"limit": limit},
        headers=_n8n_headers(), timeout=30,
    )
    r.raise_for_status()
    return (r.json() or {}).get("data", [])


def _node_output_items(run: dict) -> list:
    """A single NodeRun's output items (`data.main[0]`) — defensive against any shape
    mismatch: never raises, returns [] on anything unexpected."""
    if not isinstance(run, dict):
        return []
    data = run.get("data")
    if not isinstance(data, dict):
        return []
    main = data.get("main")
    if not isinstance(main, list) or not main:
        return []
    branch = main[0]
    return branch if isinstance(branch, list) else []


def _first_node_output_json(run: dict):
    for item in _node_output_items(run):
        candidate = item.get("json") if isinstance(item, dict) else None
        if isinstance(candidate, dict):
            return candidate
    return None


def extract_token_usage(execution: dict) -> dict:
    """Pure over an already-fetched execution dict. Never raises — any shape mismatch
    yields {"available": False, "reason": ..., "rows": []}. A node that ran but carried
    no usage object is reported usage_available=False ("usage-unavailable"); a node that
    never ran is reported status="not_run" — the two are different findings, never
    conflated as "zero tokens" (must_haves behaviour table)."""
    data = execution.get("data")
    if not isinstance(data, dict):
        return {"available": False, "reason": "execution payload has no 'data'", "rows": []}
    result_data = data.get("resultData")
    if not isinstance(result_data, dict):
        return {"available": False, "reason": "no resultData in execution payload", "rows": []}
    run_data = result_data.get("runData")
    if not isinstance(run_data, dict):
        return {"available": False, "reason": "runData is not a mapping", "rows": []}

    # A node key genuinely ABSENT from runData (or present with an empty run list) is a
    # normal, expected shape — that node simply didn't run. A node key PRESENT with a
    # non-list value is a malformed/truncated payload, not a legitimate "didn't run"
    # state — fail the whole extraction closed rather than guess at a partial result.
    for node_name in ANTHROPIC_NODE_NAMES:
        if node_name in run_data and not isinstance(run_data[node_name], list):
            return {
                "available": False,
                "reason": f"runData[{node_name!r}] run items are not a list",
                "rows": [],
            }

    rows = []
    for node_name in ANTHROPIC_NODE_NAMES:
        runs = run_data.get(node_name)
        if not runs:
            rows.append({"node": node_name, "status": "not_run"})
            continue
        if not isinstance(runs[0], dict):
            rows.append({"node": node_name, "status": "ran", "usage_available": False})
            continue
        body = _first_node_output_json(runs[0])
        usage = body.get("usage") if isinstance(body, dict) else None
        if not isinstance(usage, dict):
            rows.append({"node": node_name, "status": "ran", "usage_available": False,
                         "model": body.get("model") if isinstance(body, dict) else None})
            continue
        rows.append({
            "node": node_name,
            "status": "ran",
            "usage_available": True,
            "model": body.get("model"),
            **{counter: usage.get(counter) for counter in USAGE_COUNTERS},
        })
    return {"available": True, "reason": None, "rows": rows}


def build_redacted_fixture(execution: dict) -> dict:
    """Allow-list ONLY (T-22-02, never a deny-list): keeps node name, model, the usage
    counters, and run status for each Anthropic node — nothing else. The result is itself
    execution-shaped (same data.resultData.runData nesting) so it round-trips straight
    back through extract_token_usage()."""
    data = execution.get("data") if isinstance(execution.get("data"), dict) else {}
    result_data = data.get("resultData") if isinstance(data.get("resultData"), dict) else {}
    run_data = result_data.get("runData") if isinstance(result_data.get("runData"), dict) else {}

    redacted_run_data = {}
    for node_name in ANTHROPIC_NODE_NAMES:
        runs = run_data.get(node_name)
        if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
            continue
        body = _first_node_output_json(runs[0]) or {}
        redacted_item = {"model": body.get("model")}
        usage = body.get("usage")
        if isinstance(usage, dict):
            redacted_item["usage"] = {k: usage.get(k) for k in USAGE_COUNTERS if k in usage}
        redacted_run_data[node_name] = [{
            "executionStatus": runs[0].get("executionStatus"),
            "data": {"main": [[{"json": redacted_item}]]},
        }]

    return {"data": {"resultData": {"runData": redacted_run_data}}}


def _write_fixture(fixture: dict, path: Path = FIXTURE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    return path


# =====================================================================================
# Plan 03 Task 1 — provider credit capture, settle handling, diff, and the report.
# =====================================================================================

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _has_any_provider_creds() -> bool:
    return any(credit_checker._HAS[name]() for name in credit_checker.PROVIDER_REGISTRY)


def capture_credit_snapshot(label: str) -> dict:
    """One entry per provider in credit_checker.PROVIDER_REGISTRY. A provider WITHOUT
    credentials configured is recorded {"configured": False, ...} rather than omitted —
    "never checked" and "checked but unknown" must stay distinguishable. A configured
    provider whose usage endpoint refuses (Apollo's non-master-key 403) is recorded with
    its real HTTP status and credits=None — the capture itself still succeeds."""
    providers = {}
    for name in credit_checker.PROVIDER_REGISTRY:
        if not credit_checker._HAS[name]():
            providers[name] = {"configured": False, "credits": None, "status": None}
            continue
        result = credit_checker._CHECK[name]()
        providers[name] = {
            "configured": True,
            "credits": result.get("credits"),
            "status": result.get("status"),
            "error": result.get("error"),
        }
    return {"label": label, "captured_at": _utc_now_iso(), "providers": providers}


def capture_settled_snapshot(label: str, *, settle_interval: float = DEFAULT_SETTLE_INTERVAL_SECONDS,
                              max_attempts: int = DEFAULT_SETTLE_MAX_ATTEMPTS,
                              sleep_fn=None, capture_fn=None) -> dict:
    """A settled AFTER-capture: waits `settle_interval` before the FIRST read (Lusha's
    documented ~4s eventual-consistency lag, docs/LUSHA-V3-CONTRACT.md §1), then re-reads
    until the provider balances stop changing between reads or `max_attempts` is reached.
    Records how many reads it took and whether it stabilised in the returned snapshot's
    "settle" key — a settle that never stabilises is still useful evidence (Pitfall 2:
    T-22-15), never a raised error.

    `sleep_fn`/`capture_fn` default to `time.sleep`/`capture_credit_snapshot` looked up at
    call time (not bound as a default-argument value) so tests can monkeypatch
    `enrichment_cost_ledger.time.sleep` directly, or inject a scripted `capture_fn`."""
    sleep_fn = sleep_fn or time.sleep
    capture_fn = capture_fn or capture_credit_snapshot

    sleep_fn(settle_interval)
    snapshot = capture_fn(label)
    attempts = 1
    stable = False
    while attempts < max_attempts:
        sleep_fn(settle_interval)
        next_snapshot = capture_fn(label)
        attempts += 1
        if next_snapshot["providers"] == snapshot["providers"]:
            snapshot = next_snapshot
            stable = True
            break
        snapshot = next_snapshot
    snapshot["settle"] = {"attempts": attempts, "stable": stable, "interval_seconds": settle_interval}
    return snapshot


def _write_snapshot(snapshot: dict, label: str) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SNAPSHOTS_DIR / f"credits-{label}-{ts}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    return path


def diff_snapshots(before: dict, after: dict) -> dict:
    """Pure over two snapshot dicts. Never raises: a malformed snapshot yields
    {"providers": {}, "any_unknown": True, "reason": ...}. Per provider: a credits value
    missing/unknown in EITHER snapshot yields spend=None (never 0, never a number derived
    from a partial pair). An after-balance HIGHER than the before-balance (a mid-window
    top-up) is reported as anomaly="top_up" with spend=None, never a negative spend."""
    before_providers = before.get("providers") if isinstance(before, dict) else None
    after_providers = after.get("providers") if isinstance(after, dict) else None
    if not isinstance(before_providers, dict) or not isinstance(after_providers, dict):
        return {"providers": {}, "any_unknown": True, "reason": "malformed snapshot(s)"}

    providers = {}
    for name in sorted(set(before_providers) | set(after_providers)):
        b = before_providers.get(name) if isinstance(before_providers.get(name), dict) else {}
        a = after_providers.get(name) if isinstance(after_providers.get(name), dict) else {}
        b_credits = b.get("credits")
        a_credits = a.get("credits")
        if not credit_checker._is_number(b_credits) or not credit_checker._is_number(a_credits):
            providers[name] = {"before": b_credits, "after": a_credits, "spend": None, "anomaly": None}
            continue
        delta = b_credits - a_credits
        if delta < 0:
            providers[name] = {"before": b_credits, "after": a_credits, "spend": None, "anomaly": "top_up"}
        else:
            providers[name] = {"before": b_credits, "after": a_credits, "spend": delta, "anomaly": None}

    any_unknown = any(row["spend"] is None for row in providers.values())
    return {"providers": providers, "any_unknown": any_unknown}


def build_report(before_snapshot: dict, after_snapshot: dict, token_usage, record_count: int = 1) -> dict:
    """Provider credit diff + Anthropic token usage, both priced against ESTIMATES/
    MODEL_PRICES. Unknowns propagate: the overall report is `partial` whenever any
    provider spend is unknown/anomalous OR the token usage is unavailable OR a node's
    model has no cited price. `per_record_usd` prices the Anthropic dollars only — no
    committed source states a credits-to-dollars conversion for any provider (T-22-11),
    so credits stay reported per-provider rather than folded into a fabricated total."""
    diff = diff_snapshots(before_snapshot, after_snapshot)
    partial = bool(diff.get("any_unknown"))

    provider_rows = []
    for name, row in diff["providers"].items():
        estimate_key = PROVIDER_ESTIMATE_KEY.get(name)
        estimate = ESTIMATES.get(estimate_key, {}).get("value") if estimate_key else None
        actual = row["spend"]
        delta = actual - estimate if (actual is not None and estimate is not None) else None
        provider_rows.append({
            "provider": name, "actual": actual, "estimate": estimate, "delta": delta,
            "anomaly": row["anomaly"],
        })

    anthropic_available = bool(token_usage and token_usage.get("available"))
    anthropic_rows = []
    anthropic_total_usd = 0.0
    if not anthropic_available:
        partial = True
    else:
        for row in token_usage["rows"]:
            if row.get("status") != "ran" or not row.get("usage_available"):
                continue
            model_id = str(row.get("model") or "")
            # The API reports dated IDs (claude-haiku-4-5-20251001); the price table
            # keys aliases. Exact match first, then alias-prefix match.
            price = MODEL_PRICES.get(model_id) or next(
                (v for k, v in MODEL_PRICES.items() if model_id.startswith(k + "-")), None
            )
            if price is None:
                partial = True
                anthropic_rows.append({**row, "cost_usd": None})
                continue
            cost = (
                (row.get("input_tokens") or 0) / 1_000_000 * price["input_per_mtok"]
                + (row.get("output_tokens") or 0) / 1_000_000 * price["output_per_mtok"]
            )
            anthropic_total_usd += cost
            anthropic_rows.append({**row, "cost_usd": round(cost, 6)})

    per_record_usd = None
    if not partial:
        per_record_usd = anthropic_total_usd / record_count if record_count else anthropic_total_usd

    return {
        "providers": provider_rows,
        "anthropic": {
            "available": anthropic_available,
            "rows": anthropic_rows,
            "total_usd": round(anthropic_total_usd, 6),
        },
        "record_count": record_count,
        "per_record_usd": per_record_usd,
        "partial": partial,
    }


def print_report(report: dict) -> None:
    print("=== Provider credits: actual vs estimate ===")
    for row in report["providers"]:
        est = "unknown" if row["estimate"] is None else row["estimate"]
        act = "unknown" if row["actual"] is None else row["actual"]
        delta = "unknown" if row["delta"] is None else row["delta"]
        anomaly = f" ANOMALY={row['anomaly']}" if row["anomaly"] else ""
        print(f"  {row['provider']}: actual={act} estimate={est} delta={delta}{anomaly}")

    print("=== Anthropic usage per call ===")
    if not report["anthropic"]["available"]:
        print("  UNAVAILABLE: no token usage supplied, or the execution's runData was unreadable")
    else:
        for row in report["anthropic"]["rows"]:
            cost = "unknown (no cited price for this model)" if row["cost_usd"] is None else f"${row['cost_usd']:.6f}"
            print(f"  node={row['node']!r} model={row.get('model')!r} "
                  f"input_tokens={row.get('input_tokens')} output_tokens={row.get('output_tokens')} cost={cost}")

    print("=== Totals ===")
    for row in report["providers"]:
        print(f"  total credits ({row['provider']}): {row['actual'] if row['actual'] is not None else 'unknown'}")
    print(f"  total anthropic USD: {report['anthropic']['total_usd']}")
    per_record = report["per_record_usd"]
    per_record_display = "unknown" if per_record is None else round(per_record, 6)
    partial_note = " [PARTIAL — one or more inputs unknown]" if report["partial"] else ""
    print(f"  per-record USD ({report['record_count']} record(s)): {per_record_display}{partial_note}")


# =====================================================================================
# Phase 29 Plan 02 Task 2 — how long a run actually takes, per record (D-06a).
#
# `/api/v1/executions` has always returned both `startedAt` and `stoppedAt`; this ledger
# only ever read `startedAt`. No new endpoint, no new HTTP path — `durations` reuses
# `_list_executions()` and `_get_execution()`, so this module's standing no-write
# guarantee is untouched (T-29-04). Prints ids, timestamps, counts and derived rates only
# (T-29-05).
#
# Unknown is never zero, throughout: a run still in flight has an UNKNOWN duration, and
# folding it in as 0 drags the measured bound down — the failure direction that produces a
# watch giving up while a healthy run is still going.
# =====================================================================================

# The write nodes in wf_enrichment_cloud.json — how many records an execution actually
# processed, recovered by counting their output items the same way extract_token_usage()
# recovers token counters. Pinned by name; a rename shows up as an unknown count, never as
# a silent zero.
WRITE_NODE_NAMES = ("HubSpot Update", "HubSpot Create",
                    "HubSpot Company Update", "HubSpot Company Create")

DURATIONS_DEFAULT_WORKFLOW = "LV Enrichment (Cloud template)"


def _parse_iso(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def execution_duration_seconds(execution):
    """Elapsed seconds, or None when either timestamp is absent or unparseable.

    None means "still running, or the field genuinely was not populated" — NOT zero.
    """
    if not isinstance(execution, dict):
        return None
    started = _parse_iso(execution.get("startedAt"))
    stopped = _parse_iso(execution.get("stoppedAt"))
    if started is None or stopped is None:
        return None
    return (stopped - started).total_seconds()


def execution_record_count(execution):
    """How many records an execution wrote, summed over the write nodes present in its
    run data — or None when none of them appears at all.

    A write node PRESENT with zero output items is a genuine 0 (it ran and wrote nothing);
    a write node ABSENT is unknown (this execution's run data does not say). Requires a
    full execution payload (`includeData=true`); the collection endpoint carries no runData.
    """
    if not isinstance(execution, dict):
        return None
    data = execution.get("data")
    result_data = data.get("resultData") if isinstance(data, dict) else None
    run_data = result_data.get("runData") if isinstance(result_data, dict) else None
    if not isinstance(run_data, dict):
        return None

    total = None
    for node_name in WRITE_NODE_NAMES:
        runs = run_data.get(node_name)
        if not isinstance(runs, list):
            continue
        total = 0 if total is None else total
        for run in runs:
            total += len(_node_output_items(run))
    return total


def _percentile(values, fraction):
    """Nearest-rank percentile over an already-sorted-able list. Small samples are the
    normal case here, so no interpolation — the reported value is always one that was
    actually observed."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(fraction * len(ordered) + 0.5)) - 1))
    return ordered[index]


def summarize_durations(rows) -> dict:
    """Pure over the per-execution rows. Unknowns are COUNTED, never averaged in as zero,
    and the sample size is a reported field: a bound derived from two executions is not
    the same claim as one derived from fifty, and the output must not present them alike.
    """
    rows = [row for row in rows if isinstance(row, dict)]
    durations = [row.get("duration_seconds") for row in rows]
    known_durations = [d for d in durations if isinstance(d, (int, float))]

    per_record = []
    unknown_duration = 0
    unknown_records = 0
    for row in rows:
        duration = row.get("duration_seconds")
        records = row.get("record_count")
        if not isinstance(duration, (int, float)):
            unknown_duration += 1
            continue
        if not isinstance(records, int) or records <= 0:
            unknown_records += 1
            continue
        per_record.append(duration / records)

    return {
        "sample_size": len(rows),
        "computed": len(per_record),
        "unknown_duration": unknown_duration,
        "unknown_record_count": unknown_records,
        "max_duration_seconds": max(known_durations) if known_durations else None,
        "max_seconds_per_record": max(per_record) if per_record else None,
        "p95_seconds_per_record": _percentile(per_record, 0.95),
    }


def print_durations(rows, summary) -> None:
    print("=== Per-execution durations ===")
    for row in rows:
        duration = row.get("duration_seconds")
        records = row.get("record_count")
        rate = (duration / records
                if isinstance(duration, (int, float)) and isinstance(records, int) and records > 0
                else None)
        print(f"  id={row.get('execution_id')} workflow={row.get('workflow')!r} "
              f"duration_s={'unknown' if duration is None else round(duration, 2)} "
              f"records={'unknown' if records is None else records} "
              f"s_per_record={'unknown' if rate is None else round(rate, 3)}")

    print("=== Summary ===")
    print(f"  sample size: {summary['sample_size']} execution(s); "
          f"{summary['computed']} yielded a per-record rate")
    print(f"  unknown duration: {summary['unknown_duration']}   "
          f"unknown record count: {summary['unknown_record_count']}")
    for key in ("max_duration_seconds", "max_seconds_per_record", "p95_seconds_per_record"):
        value = summary[key]
        print(f"  {key}: {'unknown' if value is None else round(value, 3)}")
    if not summary["computed"]:
        print("  NO MEASURED RATE — every execution read was unknown on one side or the "
              "other. A bound chosen from this run is provisional, not measured (D-06).")


def collect_durations(workflow_name=None, limit: int = 20) -> list:
    """One row per recent execution: duration from the collection response, record count
    from that execution's own run data. Read-only, two existing GET helpers, no new path.
    """
    rows = []
    for execution in _list_executions(limit):
        name = (execution.get("workflowData") or {}).get("name")
        if workflow_name and name != workflow_name:
            continue
        try:
            full = _get_execution(execution.get("id"))
        except Exception:
            full = None
        rows.append({
            "execution_id": execution.get("id"),
            "workflow": name,
            "status": execution.get("status"),
            "duration_seconds": execution_duration_seconds(execution),
            "record_count": execution_record_count(full) if full else None,
        })
    return rows


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="list",
                         choices=["list", "extract", "capture", "credits", "diff", "report",
                                  "estimates", "durations"])
    parser.add_argument("--workflow", default=DURATIONS_DEFAULT_WORKFLOW,
                         help="durations mode: workflow name to measure ('' for all)")
    parser.add_argument("--execution-id", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--label", default="snapshot")
    parser.add_argument("--settle", action="store_true")
    parser.add_argument("--settle-interval", type=float, default=DEFAULT_SETTLE_INTERVAL_SECONDS)
    parser.add_argument("--settle-max-attempts", type=int, default=DEFAULT_SETTLE_MAX_ATTEMPTS)
    parser.add_argument("--before", default=None)
    parser.add_argument("--after", default=None)
    parser.add_argument("--fixture", default=None)
    parser.add_argument("--record-count", type=int, default=1)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if args.mode == "estimates":
        print_estimates()
        return 0

    if args.mode == "credits":
        if not _has_any_provider_creds():
            print("skipped (no provider creds): none of LUSHA_API_KEY / APOLLO_API_KEY / "
                  "ZOOMINFO_CLIENT_ID+ZOOMINFO_CLIENT_SECRET are set.")
            return 0
        if args.settle:
            snapshot = capture_settled_snapshot(
                args.label, settle_interval=args.settle_interval, max_attempts=args.settle_max_attempts)
        else:
            snapshot = capture_credit_snapshot(args.label)
        path = _write_snapshot(snapshot, args.label)
        print(f"wrote {path}")
        for name, row in snapshot["providers"].items():
            print(f"  {name}: configured={row['configured']} credits={row['credits']} status={row['status']}")
        if "settle" in snapshot:
            print(f"  settle: attempts={snapshot['settle']['attempts']} stable={snapshot['settle']['stable']}")
        if args.json:
            print(json.dumps(snapshot, default=str))
        return 0

    if args.mode == "diff":
        if not args.before or not args.after:
            print("REFUSED: diff mode requires --before and --after snapshot paths.")
            return 1
        before = json.loads(Path(args.before).read_text())
        after = json.loads(Path(args.after).read_text())
        result = diff_snapshots(before, after)
        for name, row in result["providers"].items():
            print(f"  {name}: before={row['before']} after={row['after']} spend={row['spend']} anomaly={row['anomaly']}")
        if args.json:
            print(json.dumps(result, default=str))
        return 0

    if args.mode == "report":
        if not args.before or not args.after:
            print("REFUSED: report mode requires --before and --after snapshot paths.")
            return 1
        before = json.loads(Path(args.before).read_text())
        after = json.loads(Path(args.after).read_text())
        token_usage = None
        if args.execution_id:
            if not _has_n8n():
                print("skipped (no n8n creds): --execution-id requires N8N_URL/N8N_API_KEY.")
                return 0
            token_usage = extract_token_usage(_get_execution(args.execution_id))
        elif args.fixture:
            token_usage = extract_token_usage(json.loads(Path(args.fixture).read_text()))
        report = build_report(before, after, token_usage, record_count=args.record_count)
        print_report(report)
        if args.json:
            print(json.dumps(report, default=str))
        return 0

    # list / extract / capture / durations — n8n-only, reads only.
    if not _has_n8n():
        print("skipped (no n8n creds): the n8n URL and API key must both be set to run this ledger.")
        return 0

    if args.mode == "durations":
        rows = collect_durations(args.workflow or None, args.limit)
        summary = summarize_durations(rows)
        print_durations(rows, summary)
        if args.json:
            print(json.dumps({"rows": rows, "summary": summary}, default=str))
        return 0

    if args.mode == "list":
        executions = _list_executions(args.limit)
        try:
            workflows_by_id = {w.get("id"): w.get("name") for w in _get_live_workflows()}
        except Exception:
            workflows_by_id = {}
        for ex in executions:
            workflow_id = ex.get("workflowId")
            name = (ex.get("workflowData") or {}).get("name") or workflows_by_id.get(workflow_id, "unknown")
            status = ex.get("status") or ("finished" if ex.get("finished") else "running")
            print(f"id={ex.get('id')} workflow={name!r} status={status} started={ex.get('startedAt')}")
        if args.json:
            print(json.dumps(executions, default=str))
        return 0

    if not args.execution_id:
        print("REFUSED: extract/capture mode requires --execution-id.")
        return 1

    execution = _get_execution(args.execution_id)

    if args.mode == "extract":
        usage = extract_token_usage(execution)
        if not usage["available"]:
            print(f"UNAVAILABLE: {usage['reason']}")
            return 1
        for row in usage["rows"]:
            if row["status"] == "not_run":
                print(f"node={row['node']!r} status=not_run")
            elif not row.get("usage_available"):
                print(f"node={row['node']!r} status=ran usage_available=false model={row.get('model')!r}")
            else:
                counters = " ".join(f"{c}={row.get(c)}" for c in USAGE_COUNTERS)
                print(f"node={row['node']!r} status=ran model={row['model']!r} {counters}")
        if args.json:
            print(json.dumps(usage, default=str))
        return 0

    # capture
    fixture = build_redacted_fixture(execution)
    path = _write_fixture(fixture)
    print(f"wrote {path}")
    if args.json:
        print(json.dumps(fixture, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
