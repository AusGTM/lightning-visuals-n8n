# tests/test_n8n_org_type_absence.py
#
# Phase 46 Plan 01, Task 1 (RUBRIC-03) -- permanent guard for the engine-count
# reconciliation recorded in 46-ENGINE-INVENTORY.md: the n8n leg
# (n8n/wf_enrichment_cloud.json + scripts/build_cloud_workflows.py, built from
# n8n/code/mergeCompanies.js) carries NO org-type-keyed numeric point table.
# mergeCompanies.js's own header comment names this "Approach C (Phase 15):
# HubSpot owns these derived outputs" -- only the Python oracle
# (src/icp_scoring.py + config/icp_scoring.yaml) and HubSpot flow 4626124224
# carry an org-type weight table; that is two engines, not the three CONTEXT.md
# D-11 and REQUIREMENTS.md RUBRIC-03 both assert.
#
# Every org-type string that DOES appear in these two n8n artifacts is enum
# membership (taxonomy.generated.js's ORG_TYPES array / ORG_TYPE_SYNONYMS
# string-to-string normalizer) or a frozen JUNE_CANDIDATES fixture blob --
# never a value mapped to a number. This test's regex distinguishes the two
# shapes: it only flags a term that sits immediately (word-boundary) adjacent
# to a ":"/"=" and a number, the actual shape of a weight-table entry.
#
# This is proof-not-inspection: it goes red the instant a future change
# reintroduces a numeric org-type table on the n8n leg. If a real port ever
# lands here, it belongs in Plan 04 (per 46-01-PLAN.md Task 1's action) --
# which must then invert this test into a conformance assertion (mirror
# tests/test_flow_rubric_conformance.py::test_org_type_flow_matches_rubric's
# shape) and update 46-ENGINE-INVENTORY.md's verdict in the same change.
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
N8N_WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"
BUILD_SCRIPT_PATH = ROOT / "scripts" / "build_cloud_workflows.py"

# The score-name terms named explicitly in 46-01-PLAN.md Task 1's search-term list,
# checked alongside the full base_score.org_type key set below.
SCORE_NAME_TERMS = ("org_type_score", "ORG_TYPE_SCORE", "base_score")


def _org_type_keys() -> list:
    with RUBRIC_PATH.open() as f:
        rubric = yaml.safe_load(f)
    return list(rubric["base_score"]["org_type"].keys())


def _numeric_adjacent_hits(text: str, term: str) -> list:
    """Returns every substring where `term` sits at a word boundary, immediately
    (allowing only an optional closing quote and whitespace) followed by a
    ':'/'=' and a number -- the shape of a weight-table entry
    ('"individual_club_team": 15' or 'individual_club_team: 15'), not mere
    string presence anywhere nearby (enum arrays, synonym maps, fixture blobs,
    or coincidental substrings like 'otherSources.size : 0')."""
    pattern = re.compile(r"\b" + re.escape(term) + r"\b\"?\s*[:=]\s*-?\d+")
    return pattern.findall(text)


def _scan(path: Path) -> dict:
    text = path.read_text()
    offenders = {}
    for term in _org_type_keys() + list(SCORE_NAME_TERMS):
        hits = _numeric_adjacent_hits(text, term)
        if hits:
            offenders[term] = hits
    return offenders


def test_n8n_workflow_json_carries_no_org_type_weight_table():
    """RUBRIC-03 -- n8n/wf_enrichment_cloud.json (the deployed, built workflow)
    must never carry an org-type-keyed numeric table. 46-ENGINE-INVENTORY.md
    confirms only two engines (the Python oracle and HubSpot flow 4626124224)
    carry org-type weights; this is the n8n leg's permanent proof of absence."""
    offenders = _scan(N8N_WORKFLOW_PATH)
    assert not offenders, (
        f"n8n/wf_enrichment_cloud.json now has numeric-adjacent org-type terms: "
        f"{offenders} -- if this is a real weight-table port, see this module's "
        "docstring and 46-ENGINE-INVENTORY.md before changing this guard"
    )


def test_build_cloud_workflows_script_carries_no_org_type_weight_table():
    """Sibling guard for the build script that produces wf_enrichment_cloud.json
    (scripts/build_cloud_workflows.py) -- same RUBRIC-03 proof-not-inspection,
    checked against the source rather than the built artifact."""
    offenders = _scan(BUILD_SCRIPT_PATH)
    assert not offenders, (
        f"scripts/build_cloud_workflows.py now has numeric-adjacent org-type "
        f"terms: {offenders} -- if this is a real weight-table port, see this "
        "module's docstring and 46-ENGINE-INVENTORY.md before changing this guard"
    )


def test_merge_companies_js_carries_no_org_type_weight_table():
    """Third leg of the same guard, against the hand-written source
    (n8n/code/mergeCompanies.js) that build_cloud_workflows.py inlines into the
    built workflow. mergeCompanies.js:56-59's own comment documents this
    absence as deliberate ('Approach C ... HubSpot owns these derived
    outputs')."""
    offenders = _scan(ROOT / "n8n" / "code" / "mergeCompanies.js")
    assert not offenders, (
        f"n8n/code/mergeCompanies.js now has numeric-adjacent org-type terms: "
        f"{offenders} -- if this is a real weight-table port, see this module's "
        "docstring and 46-ENGINE-INVENTORY.md before changing this guard"
    )
