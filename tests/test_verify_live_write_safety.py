# tests/test_verify_live_write_safety.py
#
# Phase 22 Plan 02 (T-22-06..10) — offline proof for scripts/verify_live_write_safety.py.
# Phase 23 Plan 07 (D-19) — reworked for discovery-scoped coverage: the read-back no
# longer names one workflow and two nodes, so the fixtures build NAMED workflows out of
# explicit (node name, declared subset) pairs and every `verify()` call passes a LIST.
# Fully hermetic: no network. Drives the behaviour table with small hand-built workflow
# dicts (never the real n8n/wf_*.json — this plan's read-back logic is proven against
# synthetic shapes so every refusal path is reachable without depending on the committed
# build's exact literals, which tests/test_deploy_write_safety_overlay.py and
# tests/test_write_gate_coverage.py already pin separately).
import pytest
import requests

import scripts.deploy_n8n_workflows as deploy
import scripts.verify_live_write_safety as verifier


def _raise_http(*args, **kwargs):
    raise AssertionError("a live n8n request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    for var in ("N8N_URL", "N8N_API_KEY", "N8N_EXPECTED_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", _raise_http)
    monkeypatch.setattr(requests, "post", _raise_http)
    monkeypatch.setattr(requests, "put", _raise_http)


# Declared off the verifier's OWN checked set, so a constant added to the overlay
# (ALLOW_HUBSPOT_REVIEW_WRITES was the fifth, Phase 30 Plan 01) fails loudly here as a
# stale fixture rather than silently going unchecked.
_DISARMED = {
    "ALLOW_HUBSPOT_RECORD_WRITES": "false",
    "ALLOW_HUBSPOT_CREATE": "false",
    "ALLOW_HUBSPOT_REVIEW_WRITES": "false",
    "TEST_RECORD_DOMAINS": "",
    "TEST_RECORD_IDS": "",
}
_ALIAS = {
    "writes": "ALLOW_HUBSPOT_RECORD_WRITES",
    "create": "ALLOW_HUBSPOT_CREATE",
    "review": "ALLOW_HUBSPOT_REVIEW_WRITES",
    "ids": "TEST_RECORD_IDS",
    "domains": "TEST_RECORD_DOMAINS",
}


def _node(name, declares=None, drain="true", **overrides):
    """One Code node. `declares` is the SUBSET of constants this node writes into its
    jsCode (default: all of them) — the contact lane's `Decide Action` really does
    declare only the create flag, so a partial declaration must be expressible.

    `drain` (Phase 44 Plan 01) is the ALLOW_SJ3_DRAIN_WRITES literal this node declares
    — default "true" because every real gate node declares it at its rest value via
    WRITE_SAFETY_GATE_JS; pass None to build a node that does not declare it."""
    assert set(_DISARMED) == set(verifier.CHECKED_CONSTANTS), (
        "fixture is out of date with verifier.CHECKED_CONSTANTS: "
        f"{set(verifier.CHECKED_CONSTANTS) ^ set(_DISARMED)}"
    )
    values = dict(_DISARMED)
    for key, value in overrides.items():
        values[_ALIAS[key]] = value
    declared = tuple(declares) if declares is not None else tuple(_DISARMED)
    js_code = (
        "// unrelated preamble, e.g. taxonomy consts, should never confuse the parser\n"
        'const SOME_OTHER_CONST = "unrelated";\n'
        + "".join(f'const {n} = "{values[n]}";\n' for n in declared)
        + (f'const {verifier.DRAIN_CONSTANT} = "{drain}";\n' if drain is not None else "")
    )
    return {"name": name, "parameters": {"jsCode": js_code}}


def _wf(name, *nodes):
    return {"name": name, "nodes": list(nodes)}


def _enrichment(contact=None, company=None):
    """The pre-23-07 shape: one workflow, the two `Decide*` nodes — as a LIST, which is
    what `verify()` now takes."""
    nodes = []
    if contact is not None:
        nodes.append(_node("Decide Action", **contact))
    if company is not None:
        nodes.append(_node("Decide Company Action", **company))
    return [_wf("LV Enrichment (Cloud template)", *nodes)]


# --- spec parity: the checked set must never drift from the overlay's own set --------

def test_checked_constants_match_overlay_spec():
    assert set(verifier.CHECKED_CONSTANTS) == set(deploy._OVERLAY_FLAG_SPEC.keys())


def test_boolean_constants_are_derived_not_retyped():
    """Phase 30 Plan 01's fix, preserved by 23-07 rather than redone: the booleans are
    whatever the overlay declares minus the allowlists, so a sixth write-enabling flag is
    read back the moment it exists."""
    assert set(verifier.BOOLEAN_CONSTANTS) == (
        set(deploy._OVERLAY_FLAG_SPEC) - set(verifier.ALLOWLIST_CONSTANTS)
    )


# --- disarmed expectation --------------------------------------------------------------

def test_disarmed_passes_when_both_nodes_fully_disabled():
    result = verifier.verify(_enrichment(contact={}, company={}), "disarmed")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_disarmed_fails_when_one_node_still_has_record_writes_enabled():
    result = verifier.verify(_enrichment(contact={"writes": "true", "ids": "201"}, company={}), "disarmed")
    assert result["ok"] is False
    assert any("Decide Action" in r and "ALLOW_HUBSPOT_RECORD_WRITES" in r for r in result["reasons"])


def test_disarmed_fails_on_stale_allowlist_even_with_flags_disabled():
    result = verifier.verify(_enrichment(contact={}, company={"ids": "9604614548"}), "disarmed")
    assert result["ok"] is False
    assert any("Decide Company Action" in r and "TEST_RECORD_IDS" in r for r in result["reasons"])


def test_disarmed_fails_when_review_writeback_is_still_armed():
    """Phase 30 Plan 01: ALLOW_HUBSPOT_REVIEW_WRITES is a write-enabling flag this
    read-back had no knowledge of when it was written. A live artifact with review
    writeback armed reporting `disarmed PASS` is the exact false-success this script
    exists to prevent, so the checked booleans are derived from the overlay set."""
    result = verifier.verify(_enrichment(contact={"review": "true", "ids": "201"}, company={}), "disarmed")
    assert result["ok"] is False
    assert any("Decide Action" in r and "ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


# --- discovery: coverage follows the deployed artifacts (23-07 Task 1) -----------------

def test_disarmed_fails_on_an_armed_node_outside_the_enrichment_workflow():
    """The defect 23-06 Section B found live: the read-back named ONE workflow and TWO
    `Decide*` nodes, so an armed literal in the contact lane's write gates — a different
    workflow, differently named nodes — produced a confident `disarmed PASS` for a lane it
    never looked at."""
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf(
            "LV Contact Ingest (Cloud template)",
            _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",)),
            _node("Build Write Patch", writes="true", ids="201"),
        ),
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "ALLOW_HUBSPOT_RECORD_WRITES" in r)
    assert "LV Contact Ingest (Cloud template)" in reason
    assert "Build Write Patch" in reason


def test_a_node_declaring_only_the_create_constant_is_judged_on_what_it_declares():
    """The contact lane's `Decide Action` declares ONLY the create flag (23-01). The old
    rule — every node must declare all five — reported that legitimate node as broken."""
    workflows = [
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",)))
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_a_partially_declaring_node_still_fails_on_what_it_does_declare():
    workflows = [
        _wf(
            "LV Contact Ingest (Cloud template)",
            _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",), create="true"),
        )
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_CREATE" in r and "Decide Action" in r for r in result["reasons"])


def test_a_workflow_with_no_declaring_node_contributes_nothing_and_is_not_an_error():
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf("Some Unrelated Workflow", {"name": "Set", "parameters": {"jsCode": "const x = 1;"}}),
        {"name": "Nodeless Workflow"},
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is True
    assert result["declaring_nodes"] == 2


def test_a_scan_that_discovers_zero_declaring_nodes_fails_rather_than_passing():
    """A scan that matched nothing is otherwise indistinguishable from a disarmed
    instance — the vacuous-pass failure shape this milestone keeps hitting."""
    result = verifier.verify([_wf("Some Unrelated Workflow")], "disarmed")
    assert result["ok"] is False
    assert any("zero" in r.lower() or "no node" in r.lower() for r in result["reasons"])


def test_an_empty_workflow_list_is_also_a_zero_discovery_failure():
    result = verifier.verify([], "disarmed")
    assert result["ok"] is False
    assert result["reasons"]


def test_a_finding_names_the_workflow_because_a_node_name_alone_is_ambiguous():
    """Both `LV Enrichment (Cloud template)` and `LV Contact Ingest (Cloud template)`
    contain a node named `Decide Action`."""
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action")),
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", create="true")),
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    assert len(result["reasons"]) == 1
    assert "LV Contact Ingest (Cloud template)" in result["reasons"][0]
    assert "LV Enrichment (Cloud template)" not in result["reasons"][0]


# --- armed expectation ------------------------------------------------------------------

def test_armed_fails_when_review_writeback_is_also_enabled():
    """A dispatch armed window must not silently carry review writeback with it (D-02) —
    the canary's scope is record writes only."""
    workflows = _enrichment(
        contact={"writes": "true", "review": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


def test_armed_passes_with_requested_allowlist_and_writes_enabled_on_both_nodes():
    workflows = _enrichment(
        contact={"writes": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_armed_fails_when_create_flag_is_also_enabled():
    """Backward compatibility, asserted rather than assumed: with no expected-armed set
    the armed expectation keeps Phase 22's exact meaning — record writes and nothing
    else — so an operator who forgets the new argument gets the STRICTER verdict."""
    workflows = _enrichment(
        contact={"writes": "true", "create": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_CREATE" in r for r in result["reasons"])


def test_armed_fails_when_live_allowlist_differs_from_requested():
    workflows = _enrichment(
        contact={"writes": "true", "ids": "999"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "Decide Action" in r and "Company" not in r)
    assert "999" in reason and "201" in reason


def test_armed_requires_a_non_empty_expected_allowlist():
    with pytest.raises(ValueError, match="requires a non-empty"):
        verifier.verify(_enrichment(contact={}, company={}), "armed", expected_allowlist=None)


# --- an armed expectation both windows can state (23-07 Task 2) ------------------------

def _rb3_shape():
    """RB-3 / 23-06 Section B: record writes AND create armed together, review writeback
    still disabled, allowlist set to the canary domain."""
    return [
        _wf(
            "LV Contact Ingest (Cloud template)",
            _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",), create="true"),
            _node("Build Write Patch", writes="true", create="true", domains="australiagtm.com"),
        ),
        _wf(
            "LV Enrichment (Cloud template)",
            _node("Decide Action", writes="true", create="true", domains="australiagtm.com"),
        ),
    ]


def _rb9_shape():
    """RB-9 / 30-07: review writeback alone, allowlist a record id."""
    return [
        _wf(
            "LV Review Decision (Cloud template)",
            _node("Apply Review Decision", review="true", ids="9604614548"),
        )
    ]


def test_the_23_06_window_passes_when_both_its_flags_are_named():
    result = verifier.verify(
        _rb3_shape(), "armed", expected_allowlist="australiagtm.com",
        expected_armed=["ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"],
    )
    assert result["ok"] is True, result["reasons"]
    assert result["expected_armed"] == ["ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"]


def test_the_same_input_fails_when_only_one_of_its_flags_is_named():
    """Naming a flag must never mean "ignore everything I did not name" — that deletes the
    property the check exists for."""
    result = verifier.verify(
        _rb3_shape(), "armed", expected_allowlist="australiagtm.com",
        expected_armed=["ALLOW_HUBSPOT_RECORD_WRITES"],
    )
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_CREATE" in r for r in result["reasons"])


def test_the_30_07_window_passes_when_review_writes_is_named():
    result = verifier.verify(
        _rb9_shape(), "armed", expected_allowlist="9604614548",
        expected_armed=["ALLOW_HUBSPOT_REVIEW_WRITES"],
    )
    assert result["ok"] is True, result["reasons"]


def test_the_30_07_window_fails_under_the_default_expectation():
    result = verifier.verify(_rb9_shape(), "armed", expected_allowlist="9604614548")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


def test_a_named_flag_reading_disabled_fails_and_names_workflow_and_node():
    workflows = [_wf("LV Review Decision (Cloud template)", _node("Apply Review Decision", ids="201"))]
    result = verifier.verify(
        workflows, "armed", expected_allowlist="201",
        expected_armed=["ALLOW_HUBSPOT_REVIEW_WRITES"],
    )
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "ALLOW_HUBSPOT_REVIEW_WRITES" in r)
    assert "LV Review Decision (Cloud template)" in reason and "Apply Review Decision" in reason


def test_an_empty_allowlist_under_an_armed_expectation_is_its_own_finding():
    """`_writeSafetyAllows()` returns false on an empty allowlist, so this state grants
    NOTHING while every flag reads enabled — it must never read as a passing armed window."""
    workflows = [_wf("LV Enrichment (Cloud template)", _node("Decide Action", writes="true"))]
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "allowlist" in r)
    assert "grants" in reason.lower()


def test_an_unknown_expected_armed_flag_raises_rather_than_expecting_nothing():
    with pytest.raises(ValueError, match="unknown expected-armed flag"):
        verifier.verify(
            _rb9_shape(), "armed", expected_allowlist="201",
            expected_armed=["ALLOW_HUBSPOT_REVIEW_WRITE"],  # typo: no trailing S
        )


def test_an_allowlist_constant_is_not_an_expected_armed_flag():
    with pytest.raises(ValueError, match="unknown expected-armed flag"):
        verifier.verify(
            _rb9_shape(), "armed", expected_allowlist="201", expected_armed=["TEST_RECORD_IDS"],
        )


def test_an_explicitly_empty_expected_armed_set_raises():
    with pytest.raises(ValueError, match="at least one"):
        verifier.verify(_rb9_shape(), "armed", expected_allowlist="201", expected_armed=[])


def test_expect_armed_appears_in_the_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--help"])
    assert exc.value.code == 0
    assert "--expect-armed" in capsys.readouterr().out


def test_expect_armed_is_refused_under_the_disarmed_expectation(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--expect-armed", "ALLOW_HUBSPOT_CREATE"])
    assert exc.value.code != 0
    assert "--expect-armed" in capsys.readouterr().err


def test_an_unknown_expect_armed_flag_is_refused_by_the_cli(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main([
            "--expectation", "armed", "--allowlist", "201",
            "--expect-armed", "ALLOW_HUBSPOT_NONSENSE",
        ])
    assert exc.value.code != 0
    assert "ALLOW_HUBSPOT_NONSENSE" in capsys.readouterr().err


def test_the_armed_report_states_what_was_expected_as_well_as_what_was_found(capsys):
    result = verifier.verify(
        _rb9_shape(), "armed", expected_allowlist="9604614548",
        expected_armed=["ALLOW_HUBSPOT_REVIEW_WRITES"],
    )
    verifier._print_report(result)
    out = capsys.readouterr().out
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" in out
    assert "9604614548" in out


# --- a scoped armed expectation that cannot blind the scan (G-60-2, Phase 60 Plan 05) ---
# The live 2026-09-03 walk found `--expectation armed` unusable for a per-lane window:
# `armed_review_window` arms exactly ONE workflow, but the global armed rule required the
# named flag to read "true" wherever it is declared across ALL FOUR workflows, so the three
# correctly-disarmed workflows' own declaring nodes each reported a FAIL. Built from `_wf`
# calls directly (never `_enrichment`, whose one-workflow shape is load-bearing elsewhere).

GRANTED_ID = "9604738976"
REVIEW_WORKFLOW = "LV Review Decision (Cloud)"


def _scoped_fixture(**review_overrides):
    """The shape the live walk was actually in: one workflow armed for review writeback
    with the granted allowlist, three others fully disarmed."""
    review = {"review": "true", "ids": GRANTED_ID}
    review.update(review_overrides)
    return [
        _wf(REVIEW_WORKFLOW, _node("Apply Review Decision", **review)),
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",))),
        _wf("LV Scheduled Maintenance (Cloud)", _node("SJ-3 Drain Gate")),
    ]


def _verify_scoped(workflows, armed_workflow=REVIEW_WORKFLOW, expected_allowlist=GRANTED_ID):
    return verifier.verify(
        workflows, "armed", expected_allowlist=expected_allowlist,
        expected_armed=["ALLOW_HUBSPOT_REVIEW_WRITES"], armed_workflow=armed_workflow,
    )


def test_the_live_walks_shape_passes_under_the_scoped_armed_expectation():
    """RED today: this is the exact shape the 2026-09-03 walk was in, and the global armed
    rule fails it because the other three workflows' correctly-disarmed nodes read the
    named flag as \"false\"."""
    result = _verify_scoped(_scoped_fixture())
    assert result["ok"] is True, result["reasons"]
    assert result["reasons"] == []


def test_a_second_workflow_also_armed_fails_even_when_the_named_one_is_correct():
    """Scoping the assertion must not stop the scan from judging the OTHERS."""
    workflows = _scoped_fixture()
    workflows[1]["nodes"][0] = _node("Decide Action", writes="true", ids=GRANTED_ID)

    result = _verify_scoped(workflows)

    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_RECORD_WRITES" in r for r in result["reasons"])


def test_unnamed_workflow_residue_matching_the_granted_id_still_fails_the_disarmed_rule():
    """Residue that happens to equal the SAME id as the correctly-armed workflow's own
    allowlist would slip past the OLD global armed rule (observed == expected passes
    there); it must still fail once the unnamed workflow is held to the disarmed rule —
    the STRICTER rule this task requires for every workflow that is not named."""
    workflows = _scoped_fixture()
    workflows[2]["nodes"][0] = _node("Decide Action", declares=("TEST_RECORD_IDS",), ids=GRANTED_ID)

    result = _verify_scoped(workflows)

    assert result["ok"] is False
    assert any("TEST_RECORD_IDS" in r and "residue" in r for r in result["reasons"])


def test_naming_a_workflow_that_matches_nothing_fails_and_lists_what_was_scanned():
    """A typo cannot silently produce a pass — the reason names the value given and lists
    the workflow names that were actually scanned."""
    result = _verify_scoped(_scoped_fixture(), armed_workflow="LV Typo'd Workflow Name")

    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "Typo'd" in r)
    assert "LV Typo'd Workflow Name" in reason
    assert REVIEW_WORKFLOW in reason


def test_the_named_workflow_armed_with_the_wrong_allowlist_still_fails():
    result = _verify_scoped(_scoped_fixture(ids="999"))

    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "999" in r)
    assert GRANTED_ID in reason


def test_the_named_workflow_with_an_empty_allowlist_fails_with_the_grants_nothing_reason():
    result = _verify_scoped(_scoped_fixture(ids=""))

    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "grants" in r.lower())
    assert REVIEW_WORKFLOW in reason


def test_omitting_armed_workflow_reproduces_the_pre_scoping_global_verdict():
    """Backward compatibility: with no `armed_workflow`, every code path behaves exactly as
    it does today — including reproducing the very bug G-60-2 diagnosed, which is the
    property that keeps every existing caller (and the completed Phase 22 runbook's command
    lines) meaning what they meant."""
    result = verifier.verify(
        _scoped_fixture(), "armed", expected_allowlist=GRANTED_ID,
        expected_armed=["ALLOW_HUBSPOT_REVIEW_WRITES"],
    )

    assert result["ok"] is False
    assert result["armed_workflow"] is None


def test_drain_check_keeps_its_own_meaning_under_the_scoped_mode():
    workflows = _scoped_fixture()
    for wf in workflows:
        for node in wf["nodes"]:
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace(
                'const ALLOW_SJ3_DRAIN_WRITES = "true";', "")

    result = _verify_scoped(workflows)

    assert result["ok"] is False
    assert any("ALLOW_SJ3_DRAIN_WRITES" in r for r in result["reasons"])


def test_the_report_states_which_workflow_is_expected_armed_when_scoped(capsys):
    result = _verify_scoped(_scoped_fixture())
    verifier._print_report(result)
    out = capsys.readouterr().out

    assert REVIEW_WORKFLOW in out
    assert "disarmed" in out.lower()


def test_armed_workflow_appears_in_the_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--help"])
    assert exc.value.code == 0
    assert "--armed-workflow" in capsys.readouterr().out


def test_armed_workflow_is_refused_by_the_cli_outside_the_armed_expectation(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--armed-workflow", REVIEW_WORKFLOW])
    assert exc.value.code != 0
    assert "--armed-workflow" in capsys.readouterr().err


# --- the drain authority's dedicated check (Phase 44 Plan 01, T-44-05) ------------------
# ALLOW_SJ3_DRAIN_WRITES rests "true" and is deliberately outside CHECKED_CONSTANTS (a
# disarmed branch that hard-requires "false" would declare a correctly-disarmed backend
# armed). Missing or "false" means the SJ-3 drain is silently inert and the stuck queue
# can re-form — a failure with its own reason line, never folded into the five overlay
# constants' verdict.

def test_drain_constant_missing_everywhere_fails_even_when_disarmed_is_clean():
    nodes_without_drain = [
        _node("Decide Action", drain=None),
        _node("Decide Company Action", drain=None),
    ]
    result = verifier.verify([_wf("LV Enrichment (Cloud template)", *nodes_without_drain)], "disarmed")
    assert result["ok"] is False
    assert result["drain"]["ok"] is False
    assert result["drain"]["declaring_nodes"] == 0
    reason = next(r for r in result["reasons"] if "ALLOW_SJ3_DRAIN_WRITES" in r)
    assert "inert" in reason
    # the five overlay constants themselves are clean — the only failure is the drain's
    assert all("ALLOW_SJ3_DRAIN_WRITES" in r for r in result["reasons"])


def test_drain_constant_reading_false_fails_and_names_workflow_and_node():
    workflows = [_wf(
        "LV Scheduled Maintenance (Cloud)",
        _node("SJ-3 Dispatch Gate"),
        _node("SJ-3 Drain Gate", declares=(), drain="false"),
    )]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "ALLOW_SJ3_DRAIN_WRITES" in r)
    assert "LV Scheduled Maintenance (Cloud)" in reason and "SJ-3 Drain Gate" in reason


def test_drain_constant_true_passes_and_does_not_disturb_the_disarmed_verdict():
    result = verifier.verify(_enrichment(contact={}, company={}), "disarmed")
    assert result["ok"] is True
    assert result["drain"] == {
        "constant": "ALLOW_SJ3_DRAIN_WRITES", "expected": "true",
        "declaring_nodes": 2, "ok": True,
    }


def test_drain_check_applies_under_the_armed_expectation_too():
    workflows = _enrichment(
        contact={"writes": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    for wf in workflows:
        for node in wf["nodes"]:
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace(
                'const ALLOW_SJ3_DRAIN_WRITES = "true";', "")
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_SJ3_DRAIN_WRITES" in r for r in result["reasons"])


def test_report_prints_the_drain_authority_as_its_own_line(capsys):
    verifier._print_report(verifier.verify(_enrichment(contact={}, company={}), "disarmed"))
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if "drain authority" in ln)
    assert "ALLOW_SJ3_DRAIN_WRITES" in line and "PASS" in line


def test_drain_constant_stays_out_of_the_overlay_and_checked_sets():
    """The exclusion itself is pinned elsewhere (test_enabled_build_invariants' strict
    5-name equality, operator-claude-plugin's control-flag parity) — this only asserts
    the verifier's own derived sets never silently absorb it."""
    assert verifier.DRAIN_CONSTANT not in verifier.CHECKED_CONSTANTS
    assert verifier.DRAIN_CONSTANT not in verifier.BOOLEAN_CONSTANTS


# --- unknown expectation refuses, never silently no-ops ---------------------------------

def test_unknown_expectation_raises_from_verify():
    with pytest.raises(ValueError, match="unknown expectation"):
        verifier.verify(_enrichment(contact={}, company={}), "bogus")


def test_unknown_expectation_refused_by_cli_with_nonzero_exit(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--expectation", "bogus"])
    assert exc.value.code != 0
    assert "invalid choice" in capsys.readouterr().err.lower()


def test_armed_without_allowlist_refused_by_cli_with_nonzero_exit(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--expectation", "armed"])
    assert exc.value.code != 0
    assert "--allowlist" in capsys.readouterr().err


# --- output discipline: the node body is read but never printed in full ----------------

def test_report_output_never_leaks_the_full_jscode_body(capsys):
    marker = "SECRET_SENTINEL_NEVER_PRINTED_WHOLESALE"
    node = {
        "name": "Decide Action",
        "parameters": {"jsCode": (
            f'// {marker}\n'
            'const ALLOW_HUBSPOT_RECORD_WRITES = "false";\n'
            'const ALLOW_HUBSPOT_CREATE = "false";\n'
            'const TEST_RECORD_DOMAINS = "";\n'
            'const TEST_RECORD_IDS = "";\n'
        )},
    }
    workflows = [_wf("LV Enrichment (Cloud template)", node, _node("Decide Company Action"))]
    result = verifier.verify(workflows, "disarmed")
    verifier._print_report(result)
    out = capsys.readouterr().out
    assert marker not in out
    assert "false" in out  # the parsed literal values ARE printed


def test_report_states_its_own_coverage_so_the_operator_reads_it_rather_than_infers_it(capsys):
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",))),
    ]
    verifier._print_report(verifier.verify(workflows, "disarmed"))
    out = capsys.readouterr().out
    assert "LV Contact Ingest (Cloud template)" in out
    assert "declaring node" in out
    # A partially declaring node prints only what it declares.
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" in out  # the enrichment nodes declare it
    assert out.count("ALLOW_HUBSPOT_CREATE") == 3


# --- no credentials: skip banner, exit 0, zero HTTP calls -------------------------------

def test_no_credentials_skips_with_zero_http_calls(capsys):
    rc = verifier.main([])
    assert rc == 0
    assert "skipped" in capsys.readouterr().out.lower()
