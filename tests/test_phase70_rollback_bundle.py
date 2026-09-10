"""tests/test_phase70_rollback_bundle.py — pins the D-70-21 rollback target.

D-70-21 (Phase 70 gap closure, Wave 0): if the Phase 70 graph defect needs to be worked
around before the fix lands, the live n8n Cloud instance rolls back to the pre-Phase-70
workflow bodies at commit `59812be`, disarmed. This module is the pinned, tested fact
behind that rollback target — not a remembered SHA. It reads the five workflow bodies
straight out of git history (never from the working tree's `n8n/` directory, which by
Phase 70 already holds the regenerated JSON) and asserts:

  - each of the five parses as JSON and its node count matches the pinned counts
    (CLAUDE.md §13.0.2, 70-CONTEXT.md's D-70-21: 17/29/123/26/39);
  - each carries the `name` of the live workflow it will overwrite;
  - the bundle is disarmed at rest: every `ALLOW_HUBSPOT_RECORD_WRITES` /
    `ALLOW_HUBSPOT_CREATE` jsCode declaration reads the `"false"` literal, and every
    `TEST_RECORD_IDS` / `TEST_RECORD_DOMAINS` declaration reads the empty literal.

Skipped (not failed) when the pinned commit is absent from the local object store — e.g.
a fresh shallow clone — so the suite stays green there; the skip reason names the SHA.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# D-70-21: the pinned rollback target. Do not change this SHA without re-deriving the
# five node counts and names below from `git show <sha>:n8n/wf_<x>_cloud.json`.
ROLLBACK_COMMIT_SHA = "59812be"

# filename under n8n/ -> (expected node count, expected live workflow `name`)
WORKFLOW_SPECS = {
    "wf_backend_status_cloud.json": (17, "LV Backend Status (Cloud template)"),
    "wf_contact_ingest_cloud.json": (29, "LV Contact Ingest (Cloud template)"),
    "wf_enrichment_cloud.json": (123, "LV Enrichment (Cloud template)"),
    "wf_review_decision_cloud.json": (26, "LV Review Decision (Cloud)"),
    "wf_scheduled_maintenance_cloud.json": (39, "LV Scheduled Maintenance (Cloud)"),
}

# The two write-enabling flags and the two allowlist flags this rollback bundle must be
# disarmed on. Same names scripts/bounce_n8n_workflows.py reads back live post-bounce.
WRITE_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")
ALLOWLIST_FLAGS = ("TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")

_FLAG_RE = {
    flag: re.compile(r'const %s = "([^"]*)"' % flag)
    for flag in WRITE_FLAGS + ALLOWLIST_FLAGS
}


def _sha_present() -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{ROLLBACK_COMMIT_SHA}^{{commit}}"],
        cwd=ROOT, capture_output=True,
    ).returncode == 0


if not _sha_present():
    pytest.skip(
        f"D-70-21 rollback commit {ROLLBACK_COMMIT_SHA} not present in the local git "
        "object store (shallow clone?) — the rollback pin cannot be verified here.",
        allow_module_level=True,
    )


def _body_at_sha(filename: str) -> dict:
    """The pre-Phase-70 workflow body, read from git history — never from the working
    tree's `n8n/` directory, which by Phase 70 holds the regenerated (post-70) JSON."""
    result = subprocess.run(
        ["git", "show", f"{ROLLBACK_COMMIT_SHA}:n8n/{filename}"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _declared_flag_values(body: dict, flag: str) -> set:
    values = set()
    for node in body.get("nodes", []):
        code = (node.get("parameters") or {}).get("jsCode") or ""
        values.update(_FLAG_RE[flag].findall(code))
    return values


@pytest.mark.parametrize("filename", sorted(WORKFLOW_SPECS))
def test_pre_phase70_body_parses_and_matches_pinned_node_count(filename):
    expected_count, _ = WORKFLOW_SPECS[filename]
    body = _body_at_sha(filename)
    assert len(body["nodes"]) == expected_count, (
        f"{filename} at {ROLLBACK_COMMIT_SHA} has {len(body['nodes'])} nodes, "
        f"pinned count is {expected_count} (D-70-21)"
    )


@pytest.mark.parametrize("filename", sorted(WORKFLOW_SPECS))
def test_pre_phase70_body_name_matches_the_live_workflow_it_overwrites(filename):
    _, expected_name = WORKFLOW_SPECS[filename]
    body = _body_at_sha(filename)
    assert body.get("name") == expected_name


@pytest.mark.parametrize("filename", sorted(WORKFLOW_SPECS))
def test_pre_phase70_body_is_disarmed_at_rest(filename):
    body = _body_at_sha(filename)
    for flag in WRITE_FLAGS:
        declared = _declared_flag_values(body, flag)
        assert declared <= {"false"}, (
            f"{filename}'s {flag} declares {declared} — expected only the disarmed "
            f'"false" literal; D-70-21 requires the rollback bundle to be armed by '
            "nobody"
        )
    for flag in ALLOWLIST_FLAGS:
        declared = _declared_flag_values(body, flag)
        assert declared <= {""}, (
            f"{filename}'s {flag} declares {declared} — expected only the empty "
            "allowlist literal"
        )
