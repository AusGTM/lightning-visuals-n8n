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


def test_a_company_with_only_a_name_is_accepted_and_looked_up_by_name():
    """SUPERSEDED 2026-08-25 by the operator's ruling from the Phase 53 walk. This test
    previously asserted that a domainless company was REFUSED, on the reasoning that domain
    is the only identity the backend searches on. That stopped being true the same day: the
    companies branch gained an exact-name fallback search, so a company already in HubSpot
    resolves by name alone.

    The operator's ruling is the deciding half: a blanket refusal hands the research back to
    an operator who does not want to do it. The guard that survives is "never silently invent
    a domain" — a profile URL is dropped rather than passed through — not "go and find one
    yourself". Creating a NEW company still needs a domain, because domain is the dedupe
    anchor; that half is unchanged and is pinned by the create-path tests."""
    envelope = enrichment.build_envelope({"companies": [{"name": "No Domain Ltd"}]}, [])
    assert envelope["events"] == [{"objectType": "companies", "name": "No Domain Ltd"}]


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
