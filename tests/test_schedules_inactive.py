# tests/test_schedules_inactive.py
#
# Phase 16.1 Plan 02 Task 3 (SC-7, reviews A5) — offline proof that the scheduled-
# maintenance workflow ships an explicit "active": false marker, and that the enrichment
# webhook workflow (caller-triggered, safe to activate — Track B) carries no
# "active": true. The PRECISE functional guarantee (deploy never POSTs to /activate) is
# proven separately in tests/test_deploy_n8n_workflows.py — this file only proves the
# emitted JSON field.
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEDULED_PATH = ROOT / "n8n" / "wf_scheduled_maintenance_cloud.json"
ENRICHMENT_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def test_scheduled_maintenance_workflow_active_is_explicitly_false():
    doc = json.loads(SCHEDULED_PATH.read_text())
    assert "active" in doc, "build_scheduled_maintenance_cloud() must emit an explicit active key"
    assert doc["active"] is False


def test_scheduled_maintenance_json_marker_grep():
    text = SCHEDULED_PATH.read_text()
    assert text.count('"active": false') == 1


def test_enrichment_webhook_workflow_carries_no_active_true():
    """16.1 does not activate the webhook workflow (Track B); it also must not ship an
    active:true marker that a future deploy might start honoring."""
    text = ENRICHMENT_PATH.read_text()
    assert '"active": true' not in text


def test_enrichment_webhook_workflow_has_no_active_key_at_all():
    """Precise per RESEARCH.md Task 4: build_enrichment_cloud() intentionally carries NO
    active key (unlike the scheduled workflow) — the webhook is caller-triggered and safe
    to activate later; adding any active key here would itself be a live-activation-
    adjacent decision this offline builder does not make."""
    doc = json.loads(ENRICHMENT_PATH.read_text())
    assert "active" not in doc
