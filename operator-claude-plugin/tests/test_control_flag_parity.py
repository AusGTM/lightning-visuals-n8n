"""28-03 Task 1 — the parity pins.

PLUGIN-04 forbids importing across the client/backend boundary, so `n8n_arming` copies
the deploy script's overlay table rather than importing it. These tests are what stops
that copy from drifting: they read `scripts/deploy_n8n_workflows.py` as TEXT and compare.

They also pin the round trip through the SHIPPED reader — a declaration the plugin writes
must be read back by `n8n_read.read_write_safety`, the same function Phase 27 built and
the status surface uses. Writer and reader cannot desync while this passes.
"""
import ast
import json
import re
from pathlib import Path

import pytest

import n8n_arming
import n8n_read

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy_n8n_workflows.py"
ARMING_SOURCE = Path(n8n_arming.__file__).read_text()


def _deploy_text():
    return DEPLOY_SCRIPT.read_text()


def _workflow(path):
    return json.loads((REPO_ROOT / "n8n" / path).read_text())


def _declaration_count(workflow, flag):
    decl_re = re.compile(rf"const\s+{re.escape(flag)}\s*=\s*[^;]+;")
    return sum(len(decl_re.findall((node.get("parameters") or {}).get("jsCode") or ""))
               for node in workflow.get("nodes", []) if isinstance(node, dict))


# --- parity with the deploy script's table -------------------------------------------

def test_the_overlayable_names_match_the_deploy_scripts_table():
    """FIVE names, not the four 28-03-PLAN.md describes. ALLOW_HUBSPOT_REVIEW_WRITES was
    added to _OVERLAY_FLAG_SPEC by 30-01 (D-02/D-08e) after Phase 28 was planned. This
    test is the reason that drift is a failure rather than a silent capability gap."""
    text = _deploy_text()
    spec_block = text.split("_OVERLAY_FLAG_SPEC = {", 1)[1].split("}", 1)[0]
    in_deploy = set(re.findall(r'"([A-Z_]+)":', spec_block))

    assert in_deploy == set(n8n_arming.OVERLAY_DISABLED_LITERALS), (
        "the plugin's copy of the overlay table has drifted from "
        "deploy_n8n_workflows.py::_OVERLAY_FLAG_SPEC"
    )
    assert len(in_deploy) == 5


def test_each_disabled_literal_matches_the_deploy_scripts_table():
    text = _deploy_text()
    spec_block = text.split("_OVERLAY_FLAG_SPEC = {", 1)[1].split("}", 1)[0]
    for flag, disabled in n8n_arming.OVERLAY_DISABLED_LITERALS.items():
        row = re.search(rf'"{flag}":\s*\((.+?),', spec_block)
        assert row, f"{flag} is not in the deploy script's table"
        # The table stores the JS literal INSIDE a Python string — the source text is
        # `'"false"'`. literal_eval unwraps exactly one layer, so the comparison is
        # against the JS literal itself rather than against quoting.
        in_deploy = ast.literal_eval(row.group(1).strip())
        assert in_deploy == disabled, (
            f"{flag}'s disabled literal drifted: plugin has {disabled}, "
            f"deploy script has {in_deploy}"
        )


def test_the_write_enabling_set_matches_the_deploy_script():
    text = _deploy_text()
    block = text.split("_WRITE_ENABLING_FLAGS = frozenset({", 1)[1].split("})", 1)[0]
    assert set(re.findall(r'"([A-Z_]+)"', block)) == set(n8n_arming.WRITE_ENABLING_FLAGS)


def test_the_allowlist_value_CHARACTER_CLASS_matches_but_the_separator_deliberately_does_not():
    """Pin the charset only.

    The deploy script permits `|` as its separator and converts it to a comma at deploy
    time, purely because `,` already separates entries inside the ENABLE_BAKED_FLAGS
    environment-variable envelope. The plugin has no such envelope, so comma-direct is the
    correct plugin-side separator — a test pinning `|` here would fail a correct
    implementation."""
    text = _deploy_text()
    deploy_re = re.search(r"_ALLOWLIST_VALUE_RE = re\.compile\(r\"(.+?)\"\)", text).group(1)

    assert "[A-Za-z0-9._-]" in deploy_re
    assert "[A-Za-z0-9._-]" in n8n_arming._ALLOWLIST_VALUE_RE.pattern
    assert "|" in deploy_re, "the deploy script's envelope separator"
    assert "," in n8n_arming._ALLOWLIST_VALUE_RE.pattern, "comma-direct plugin-side"


# --- no second reader -----------------------------------------------------------------

def test_the_module_defines_no_reader_of_its_own():
    """A duplicate reader cannot detect a desync it is itself the cause of."""
    assert "def read_write_safety" not in ARMING_SOURCE
    assert re.search(r"re\.compile\(.{0,40}const.{0,40}=\s*\(\[\^;\]", ARMING_SOURCE) is None, (
        "a private capturing declaration-reader has been reintroduced alongside the "
        "imported n8n_read.read_write_safety"
    )
    assert "import n8n_read" in ARMING_SOURCE


# --- the round trip through the shipped reader ---------------------------------------

def test_a_declaration_the_plugin_writes_is_read_back_by_phase_27s_reader():
    workflow = _workflow("wf_contact_ingest_cloud.json")
    armed, counts = n8n_arming.set_write_safety(
        workflow, {"ALLOW_HUBSPOT_RECORD_WRITES": True, "TEST_RECORD_IDS": "12345,67890"})

    observed = n8n_read.read_write_safety(armed, "ALLOW_HUBSPOT_RECORD_WRITES")
    assert observed["value"] == "true"
    assert observed["disagreement"] is None
    # 3 declaring nodes since 2026-08-25: the update and create gates plus the
    # association gate, all embedding the same shared write-safety blob.
    assert counts["ALLOW_HUBSPOT_RECORD_WRITES"] == 3

    allowlist = n8n_read.read_write_safety(armed, "TEST_RECORD_IDS")
    assert allowlist["value"] == "12345,67890"
    assert allowlist["disagreement"] is None


# --- rewrite counts, asserted AND derived --------------------------------------------

def test_maintenance_workflow_rewrite_counts():
    """5 declaring nodes since Phase 44 Plan 01: the four spliced write gates plus
    "SJ-3 Dispatch Gate", which embeds the same shared gate blob verbatim (D-02)."""
    workflow = _workflow("wf_scheduled_maintenance_cloud.json")
    _, counts = n8n_arming.set_write_safety(
        workflow, {"ALLOW_HUBSPOT_RECORD_WRITES": True, "ALLOW_HUBSPOT_CREATE": True})
    assert counts == {"ALLOW_HUBSPOT_RECORD_WRITES": 5, "ALLOW_HUBSPOT_CREATE": 5}


def test_contact_ingest_rewrite_counts_create_leads_by_one():
    """The create constant appears in one more node than the record-writes constant,
    added by 23-01. Counts rose by one each on 2026-08-25: the association lane's own
    write gate embeds the same shared write-safety blob as every other gate."""
    workflow = _workflow("wf_contact_ingest_cloud.json")
    _, counts = n8n_arming.set_write_safety(
        workflow, {"ALLOW_HUBSPOT_RECORD_WRITES": True, "ALLOW_HUBSPOT_CREATE": True})
    assert counts == {"ALLOW_HUBSPOT_RECORD_WRITES": 3, "ALLOW_HUBSPOT_CREATE": 4}


def test_rewrite_counts_are_derived_across_every_committed_cloud_workflow():
    """Never memorise a declaration count. The two tests above pin the two workflows the
    plan names; this one derives every count from the artifact itself, so a workflow
    gaining or losing a write gate — or a NEW workflow appearing, as
    wf_review_decision_cloud.json did via 30-02 — fails here rather than during an armed
    window."""
    seen = 0
    for path in sorted((REPO_ROOT / "n8n").glob("wf_*_cloud.json")):
        workflow = json.loads(path.read_text())
        for flag in n8n_arming.OVERLAYABLE_FLAGS:
            expected = _declaration_count(workflow, flag)
            if not expected:
                continue
            value = "x" if flag in n8n_arming.ALLOWLIST_FLAGS else True
            _, counts = n8n_arming.set_write_safety(workflow, {flag: value})
            assert counts[flag] == expected, f"{path.name}/{flag}"
            seen += 1
    assert seen >= 20, "discovery found suspiciously few declarations — did the scan break?"


# --- refusals -------------------------------------------------------------------------

def test_a_name_outside_the_overlayable_set_is_refused_and_the_message_lists_them():
    workflow = _workflow("wf_contact_ingest_cloud.json")
    with pytest.raises(n8n_arming.ArmingRefused) as excinfo:
        n8n_arming.set_write_safety(workflow, {"MAX_WEB_RESEARCH_PER_RUN": 999})
    message = str(excinfo.value)
    for flag in n8n_arming.OVERLAYABLE_FLAGS:
        assert flag in message


def test_a_semicolon_in_an_allowlist_value_is_refused_before_any_rewrite():
    workflow = _workflow("wf_contact_ingest_cloud.json")
    with pytest.raises(n8n_arming.ArmingRefused) as excinfo:
        n8n_arming.set_write_safety(
            workflow, {"ALLOW_HUBSPOT_RECORD_WRITES": True,
                       "TEST_RECORD_IDS": "123;const ALLOW_HUBSPOT_CREATE = true"})
    assert "semicolon" in str(excinfo.value)
    # and nothing was rewritten — the untouched input still reads disabled
    assert n8n_read.read_write_safety(workflow, "ALLOW_HUBSPOT_RECORD_WRITES")["value"] == "false"


@pytest.mark.parametrize("bad", ["a b", "id@example", "a/b", "a|b"])
def test_values_outside_the_charset_are_refused(bad):
    workflow = _workflow("wf_contact_ingest_cloud.json")
    with pytest.raises(n8n_arming.ArmingRefused):
        n8n_arming.set_write_safety(workflow, {"TEST_RECORD_IDS": bad})


# --- genuinely bidirectional ----------------------------------------------------------

def test_an_armed_workflow_can_be_set_back_and_the_rescan_passes():
    """The whole reason this module exists: enable_baked_flags() searches for the DISABLED
    literal, so it can arm but can never put a workflow back."""
    workflow = _workflow("wf_contact_ingest_cloud.json")
    armed, _ = n8n_arming.set_write_safety(
        workflow, {"ALLOW_HUBSPOT_RECORD_WRITES": True, "TEST_RECORD_IDS": "12345"})
    assert n8n_read.read_write_safety(armed, "ALLOW_HUBSPOT_RECORD_WRITES")["value"] == "true"

    disarmed, counts = n8n_arming.set_write_safety(
        armed, n8n_arming.disarmed_targets("ALLOW_HUBSPOT_RECORD_WRITES", "TEST_RECORD_IDS"))

    assert n8n_read.read_write_safety(disarmed, "ALLOW_HUBSPOT_RECORD_WRITES")["value"] == "false"
    assert n8n_read.read_write_safety(disarmed, "TEST_RECORD_IDS")["value"] == ""
    # 3 declaring nodes since 2026-08-25: the update and create gates plus the
    # association gate, all embedding the same shared write-safety blob.
    assert counts["ALLOW_HUBSPOT_RECORD_WRITES"] == 3


def test_the_input_workflow_is_never_mutated():
    workflow = _workflow("wf_contact_ingest_cloud.json")
    before = json.dumps(workflow)
    n8n_arming.set_write_safety(workflow, {"ALLOW_HUBSPOT_CREATE": True})
    assert json.dumps(workflow) == before
