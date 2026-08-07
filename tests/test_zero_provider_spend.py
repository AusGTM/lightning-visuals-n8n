# tests/test_zero_provider_spend.py
#
# Phase 41 Plan 03, Task 1 — DATA-01's "zero provider spend" claim is structural, not a
# runtime flag (41-RESEARCH.md Pitfall 1). SJ-3 (the 15-min `lv_enrichment_requested`
# poller in `n8n/wf_scheduled_maintenance_cloud.json`) dispatches into the enrichment
# workflow via an event object its own "SJ-3 Build Dispatch Event" Code node builds
# (`scripts/build_cloud_workflows.py`'s `ENRICH_SJ3_BUILD_DISPATCH_EVENT`). That event
# never sets a `providers` key. On the receiving side, "Parse HubSpot Event"
# (`ENRICH_PARSE_EVENT_CLOUD`, same builder) computes
# `providersRaw = parsed.providers ?? event.providers` and feeds it to
# `resolveEnabledProviders()` (`n8n/code/providerSelection.js`), whose "no recognized
# value" branch resolves to an EMPTY enabled-provider set (CONTEXT Locked Decision 2 —
# safe default, explicit opt-in required). So a canary run through SJ-3 cannot reach
# ZoomInfo/Apollo/Lusha regardless of any env var or config flag — this is asserted
# against the BUILT artifact (`n8n/wf_scheduled_maintenance_cloud.json`), not the builder
# source, so a future builder refactor that reintroduces the key is caught in the shipped
# workflow, not just in the generator that produced it.
#
# This file does not rebuild or redeploy anything — the built workflow JSON already on
# disk is the plan's fixed evidence, and the whole point is to prove IT is safe.
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_WORKFLOW = ROOT / "n8n" / "wf_scheduled_maintenance_cloud.json"
JUNE_CANDIDATES = ROOT / "config" / "june_candidates.json"

DISPATCH_NODE_NAME = "SJ-3 Build Dispatch Event"
SEARCH_NODE_NAME = "SJ-3 Search (requested poller)"

# A `providers` key assigned anywhere in the dispatch-event jsCode (object-literal key
# position, e.g. `providers: "all"`) is the ONLY way this event could opt into the
# provider waterfall (Pitfall 1). `providers_requested` / `providersRaw` etc. do not
# match — the word-boundary + immediate colon requires an exact `providers:` key.
PROVIDER_KEY_RE = re.compile(r"\bproviders\s*:")

# The five canary companies (41-03-PLAN.md's `<artifacts_this_phase_produces>` /
# Task 1 action), chosen to exercise five distinct code paths in one SJ-3 tick rather
# than five similar records. Each rationale below is the reason this specific record
# was picked, not a restatement of its expected outcome.
CANARY_IDS = {
    "9604614548": (
        "Melbourne Racing Club — the only company in the portal carrying prior "
        "canonical lv_* state (Phase 40-07's portfolio measurement), so it is the "
        "only record that exercises the non-clobber path against existing values "
        "rather than blank ones."
    ),
    "15008671672": (
        "Racing NSW — maps to governing_body_league, an evidence-gated org type, so "
        "it proves the per-field evidence URL survives from the June table through "
        "the merge gate."
    ),
    "16047156820": (
        "Queensland Racing Integrity Commission — proves the D-02 exception list "
        "fires and the record lands regulator rather than the deterministic table's "
        "governing_body_league."
    ),
    "17861423879": (
        "Sportsbet — proves lv_is_gambling_operator drives the graduated deduction "
        "without setting the anti-ICP flag."
    ),
    "15274105699": (
        "Supertech Electronics — proves lv_is_hardware_vendor fires the hard veto: "
        "flag true, reason written, tier D."
    ),
}

# Composed (never run by this test, or by any autonomous task) for Task 2 to hand the
# operator verbatim — scripts/check_provider_credits.py's own documented usage line
# (`python scripts/check_provider_credits.py`), wrapped exactly as every other operator
# command in this phase loads `.env` via python-dotenv before invoking the script by
# path. One reading brackets the canary "before", the same command run again after the
# canary is the "after" half of the zero-spend proof.
CREDIT_CHECK_COMMAND = (
    ".venv/bin/python -c "
    "\"from dotenv import load_dotenv; load_dotenv(); import runpy; "
    "runpy.run_path('scripts/check_provider_credits.py', run_name='__main__')\""
)


def _load_workflow():
    return json.loads(MAINTENANCE_WORKFLOW.read_text())


def _node_by_name(workflow, name):
    for node in workflow["nodes"]:
        if node["name"] == name:
            return node
    raise AssertionError(f"no node named {name!r} in {MAINTENANCE_WORKFLOW.name}")


def test_maintenance_workflow_artifact_exists():
    assert MAINTENANCE_WORKFLOW.is_file(), (
        f"{MAINTENANCE_WORKFLOW} must already be built — this test asserts against "
        "the shipped artifact, it does not build one"
    )


def test_sj3_dispatch_event_enables_no_provider():
    workflow = _load_workflow()
    node = _node_by_name(workflow, DISPATCH_NODE_NAME)
    assert node["type"] == "n8n-nodes-base.code", node["type"]
    js_code = node["parameters"]["jsCode"]
    match = PROVIDER_KEY_RE.search(js_code)
    assert match is None, (
        f"{DISPATCH_NODE_NAME}'s jsCode assigns a `providers` key "
        f"({js_code[max(0, match.start() - 40):match.start() + 40]!r} ...) — this "
        "reintroduces a path to the provider waterfall on the zero-spend canary lane"
    )


def test_sj3_search_predicate_targets_requested_true():
    workflow = _load_workflow()
    node = _node_by_name(workflow, SEARCH_NODE_NAME)
    assert node["type"] == "n8n-nodes-base.httpRequest", node["type"]
    json_body = node["parameters"]["jsonBody"]

    # Filters are rendered by _hs_search_json_body_expr as
    # `{ propertyName: "...", operator: "...", value: ... }` — extract every triple
    # in appearance order rather than assume this is the only filter in the group.
    filters = re.findall(
        r'propertyName:\s*"([^"]+)"\s*,\s*operator:\s*"([^"]+)"'
        r'(?:\s*,\s*value:\s*"([^"]*)")?',
        json_body,
    )
    assert ("lv_enrichment_requested", "EQ", "true") in filters, (
        f"{SEARCH_NODE_NAME}'s search filter no longer targets "
        f"lv_enrichment_requested EQ \"true\" — the queue write "
        "(`lv_enrichment_requested=\"true\"`, string form) can no longer trigger the "
        f"poller. Filters found: {filters!r}"
    )


@pytest.mark.parametrize("company_id,rationale", sorted(CANARY_IDS.items()))
def test_canary_id_is_a_real_june_candidate_row(company_id, rationale):
    candidates = json.loads(JUNE_CANDIDATES.read_text())
    assert company_id in candidates["rows"], (
        f"canary id {company_id} ({rationale}) is not a key in "
        f"{JUNE_CANDIDATES}'s rows"
    )


def test_canary_set_has_exactly_five_ids_each_with_a_rationale():
    assert len(CANARY_IDS) == 5
    for company_id, rationale in CANARY_IDS.items():
        assert rationale.strip(), f"canary id {company_id} has no recorded rationale"


def test_credit_check_command_uses_the_scripts_documented_usage_line():
    # scripts/check_provider_credits.py's own docstring: "Usage: python
    # scripts/check_provider_credits.py" — this composed command must invoke that exact
    # script path, so the operator command Task 2 hands over is not a drifted copy.
    assert "scripts/check_provider_credits.py" in CREDIT_CHECK_COMMAND
    assert CREDIT_CHECK_COMMAND.strip().startswith(".venv/bin/python")
