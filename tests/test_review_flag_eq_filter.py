# tests/test_review_flag_eq_filter.py
#
# Phase 43 Plan 01 (D-08, PIPE-01) — live-gated proof that HubSpot's EQ filter behavior
# for a booleancheckbox property is what this phase assumes it is. 43-RESEARCH.md
# Pitfall 5: the write-behavior of a bare-JSON-boolean PATCH to a booleancheckbox
# property was genuinely unknown offline (silently coerced / silently unfilterable /
# hard 400 all remained consistent with the evidence gathered this session) — this
# module resolves that empirically rather than assuming an outcome. Authored here,
# executed by the operator in 43-04 (RUN_LIVE_PARITY=true + live HubSpot credentials).
#
# Skips cleanly with ZERO network calls when RUN_LIVE_PARITY is unset — the disposable
# company/patch/search calls only happen inside a test body, which pytest never enters
# when the skipif condition is true.
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import AWAITING_REVIEW_GROUPS  # noqa: E402

from src.hubspot_client import get_record, patch_record, search_records  # noqa: E402
from tests.scoring_fixtures import disposable_company  # noqa: E402

live = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PARITY") != "true",
    reason="opt-in: set RUN_LIVE_PARITY=true to hit the live HubSpot portal",
)

# AWAITING_REVIEW_GROUPS[0] is the exact filter shape build_cloud_workflows.py's
# "Awaiting Review" search uses for this field — reused directly rather than
# hand-rolled, so a future drift in the real filter shape breaks this test too.
NEEDS_REVIEW_FILTER = AWAITING_REVIEW_GROUPS[0]


@live
def test_bare_boolean_patch_write_behavior_is_recorded():
    """Reproduces the PRE-FIX code path's actual output shape — a bare JSON boolean, sent
    via a raw patch_record call that bypasses the (now-fixed) n8n coercion — and records
    what HubSpot actually stored. Resolves 43-RESEARCH.md Pitfall 5's three-way
    uncertainty (silent coercion / silent filter-miss / hard 400) with a live read, rather
    than assuming one of the three."""
    with disposable_company() as company_id:
        patch_record(
            "companies", company_id, {"lv_enrichment_needs_review": True}, dry_run=False
        )
        stored = get_record("companies", company_id, ["lv_enrichment_needs_review"])
        value = stored.get("properties", {}).get("lv_enrichment_needs_review")
        # No assertion on WHICH outcome — this test's job is to make the outcome visible
        # (in the SUMMARY/operator run output) for 43-04 to record, not to assert a
        # specific pre-fix behavior. It only fails if the PATCH itself raises (outcome 3,
        # a hard 400 — HubSpot rejected the bare boolean outright).
        print(f"bare-boolean PATCH of lv_enrichment_needs_review stored as: {value!r}")


@live
def test_corrected_string_patch_is_matched_by_the_awaiting_review_eq_filter():
    """The actual PIPE-01 proof: PATCH with the corrected quoted string, then run the
    exact AWAITING_REVIEW_GROUPS[0] filter shape and assert the disposable company's id
    appears in the results — the real consumer this fix repairs, not just an offline
    grep over generated JSON."""
    with disposable_company() as company_id:
        patch_record(
            "companies", company_id, {"lv_enrichment_needs_review": "true"}, dry_run=False
        )
        result = search_records(
            "companies", NEEDS_REVIEW_FILTER, ["hs_object_id"], limit=100
        )
        found_ids = {r["id"] for r in result.get("results", [])}
        assert company_id in found_ids, (
            f"disposable company {company_id} was PATCHed with lv_enrichment_needs_review="
            '"true" but did not appear in a search using AWAITING_REVIEW_GROUPS[0]\'s exact '
            "filter shape — the EQ filter is not matching the corrected write"
        )
