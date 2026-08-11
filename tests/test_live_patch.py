# tests/test_live_patch.py
#
# merge-policy-bare-name-400 regression test. Fully offline, no network, no API key.
# Locks the boundary-translation contract: rename the 3 keys with a real live
# counterpart, drop (and log) the 8 orphans, stringify booleans, pass everything else
# through unchanged.
import json

from src.live_patch import to_live_patch


def test_renames_the_three_status_keys_with_live_counterparts():
    live = to_live_patch({
        "enrichment_requested": False,
        "enrichment_status": "complete",
        "enrichment_needs_review": True,
    })
    assert live == {
        "lv_enrichment_requested": "false",
        "lv_enrichment_status": "complete",
        "lv_enrichment_needs_review": "true",
    }


def test_drops_the_eight_orphan_keys():
    orphans = {
        "last_enrichment_run_id": "uuid",
        "last_enriched_at": "2026-08-11T00:00:00+00:00",
        "enrichment_confidence": 50,
        "enrichment_last_sources": "apollo,zoominfo",
        "enrichment_primary_source": ["apollo", "zoominfo"],  # list value -- also unsendable
        "enrichment_source_count": 2,
        "enrichment_validation_path": "haiku_only",
        "enrichment_last_decision": "{}",
    }
    live = to_live_patch(dict(orphans))
    assert live == {}


def test_orphan_drop_is_logged(capsys):
    to_live_patch({"last_enriched_at": "x"})
    out = capsys.readouterr().out
    assert "last_enriched_at" in out
    assert "dropped 1 orphan" in out


def test_renames_bare_linkedin_url_from_csv_ingest():
    # src/ingest.py's _UPLOAD_FIELDS emits bare "linkedin_url" (config/column_mapping.yaml's
    # canonical prop name); PN-1 already renamed the live/policy property to
    # lv_linkedin_url. Confirmed reachable via build_merge_result -- a CSV row with a
    # LinkedIn column promotes bare "linkedin_url" into canonical_patch when the contact's
    # current value is blank.
    live = to_live_patch({"linkedin_url": "https://linkedin.com/in/alice"})
    assert live == {"lv_linkedin_url": "https://linkedin.com/in/alice"}


def test_passes_through_already_lv_prefixed_and_native_keys_unchanged():
    live = to_live_patch({
        "lv_enrichment_provenance": json.dumps({"lv_org_type": {"source": "claude_web"}}),
        "lv_org_type_verified_at": "2026-08-11T00:00:00+00:00",
        "industry": "Sports",
        "numberofemployees": 220,
    })
    assert live["lv_enrichment_provenance"] == json.dumps({"lv_org_type": {"source": "claude_web"}})
    assert live["lv_org_type_verified_at"] == "2026-08-11T00:00:00+00:00"
    assert live["industry"] == "Sports"
    assert live["numberofemployees"] == 220


def test_full_status_patch_shape_matches_measured_live_evidence():
    # Mirrors merge_policy.build_merge_result's actual status_patch key set
    # (measured 2026-08-11 via a dry build_merge_result() run).
    status_patch = {
        "enrichment_requested": False,
        "enrichment_status": "complete",
        "last_enrichment_run_id": "uuid",
        "last_enriched_at": "2026-08-11T00:00:00+00:00",
        "enrichment_confidence": 50,
        "enrichment_needs_review": False,
        "enrichment_last_sources": "apollo,zoominfo",
        "enrichment_primary_source": ["apollo", "zoominfo"],
        "enrichment_source_count": 2,
        "enrichment_validation_path": "haiku_only",
        "enrichment_last_decision": "{}",
    }
    live = to_live_patch(status_patch)
    assert live == {
        "lv_enrichment_requested": "false",
        "lv_enrichment_status": "complete",
        "lv_enrichment_needs_review": "false",
    }


if __name__ == "__main__":
    # ponytail: bare assert-based self-check, runnable without pytest.
    test_renames_the_three_status_keys_with_live_counterparts()
    test_drops_the_eight_orphan_keys()
    test_renames_bare_linkedin_url_from_csv_ingest()
    test_passes_through_already_lv_prefixed_and_native_keys_unchanged()
    test_full_status_patch_shape_matches_measured_live_evidence()
    print("ok")
