"""The companies spec form (2026-08-25) — the only client path that can reach the
backend's company create lane.

Two properties are load-bearing and both fail silently if they regress:

1. **Domain is mandatory.** Domain is the identity anchor the backend's company lane
   searches on. A domainless company cannot be matched, only created — which is exactly
   the duplicate-company outcome this form exists to prevent.
2. **The envelope carries no `mode`.** A rows form sets `mode: "propose"` and is
   structurally return-only; this form must NOT, or the backend would report success
   having written nothing (the silent-success class Phase 47.5 removed).
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import chunking  # noqa: E402
import enrichment  # noqa: E402
import preview_enrichment  # noqa: E402


def test_a_company_becomes_one_companies_event_with_a_cleaned_domain():
    envelope = enrichment.build_envelope(
        {"companies": [{"name": "Perth Racing", "domain": "HTTPS://www.PerthRacing.com.au/about"}]},
        ["lusha", "apollo"],
    )
    assert envelope["events"] == [
        {"objectType": "companies", "domain": "perthracing.com.au", "name": "Perth Racing"}
    ]
    assert envelope["providers"] == ["lusha", "apollo"]


def test_the_companies_form_never_carries_propose_mode():
    envelope = enrichment.build_envelope(
        {"companies": [{"name": "X", "domain": "x.example"}]}, []
    )
    assert "mode" not in envelope, (
        "a companies form is a WRITE form — a propose mode would make the backend report "
        "success having written nothing"
    )


def test_a_company_without_a_domain_is_refused_by_name():
    with pytest.raises(enrichment.RecordSpecError) as excinfo:
        enrichment.build_envelope({"companies": [{"name": "No Domain Ltd"}]}, [])
    assert "No Domain Ltd" in str(excinfo.value)
    assert "domain" in str(excinfo.value).lower()


def test_an_empty_companies_list_is_refused_rather_than_dispatched():
    with pytest.raises(enrichment.RecordSpecError):
        enrichment.build_envelope({"companies": []}, [])


def test_the_plan_chunks_and_counts_a_companies_batch():
    companies = [{"name": f"C{i}", "domain": f"c{i}.example"} for i in range(5)]
    plan = chunking.plan_chunks({"companies": companies}, 2)
    assert plan.record_count == 5
    assert plan.row_counts == (2, 2, 1)
    assert [c["companies"][0]["name"] for c in plan.chunks] == ["C0", "C2", "C4"]


def test_the_preview_says_matched_first_created_only_if_absent():
    spec = {"companies": [{"name": "Perth Racing", "domain": "perthracing.com.au"}]}
    plan = chunking.plan_chunks(spec, 20)
    block = preview_enrichment.records_block(spec, plan)
    assert "Perth Racing" in block
    assert "domain" in block
    # The operator must be able to read, from the preview alone, that this can create.
    assert "created" in block and "never duplicated" in block
