"""Composition test for Phase 61 Plan 03 Task 3 (D-61-05 CORRECTED, second half).

Registers the census identity (`test_skill_sequence_coverage.py`'s `COVERED`) for the new
`enrich-before-ingest/SKILL.md` step-5 code block this task added: a linkedin-only row
driven end to end from `preingest.rows_from_table` through `build_rows_spec`,
`plan_chunks`, `match_batch`, `classify_matches`, and a `resolutions`-carrying
re-`validate()` — proving the reuse claim the plan makes (D-61-02, D-59-08): a value the
enrichment waterfall returns for a row is proposed through the SAME `resolutions` /
`provider_result` loop `extraction.md`'s own adapters use, never a second surface.
"""
import csv
import json
from pathlib import Path

import chunking
import config_gate
import extraction
import preingest

CONFIG_EXAMPLE = (
    Path(__file__).resolve().parent.parent / "config" / "operator.local.example.json"
)


def _match_ceiling_config(fake_config):
    """`fake_config` (conftest.py) carries no `max_rows_per_match_request` — chunk_ceiling
    has no fallback for a missing key by design (T-25-0x), so every test in this file reads
    the real shipped ceiling the same way test_chunking.py's own match-lane test does."""
    return {
        **fake_config,
        "max_rows_per_match_request": json.loads(CONFIG_EXAMPLE.read_text())["max_rows_per_match_request"],
    }


def _linkedin_only_csv(tmp_path):
    """A one-row spreadsheet with nothing but a LinkedIn URL column — the exact
    walk-failure row (53-WALK-RECORD-3.md FINDING D)."""
    path = tmp_path / "linkedin_only.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["LinkedIn URL"])
        writer.writerow(["https://www.linkedin.com/in/dana-osei"])
    return path


def _none_tier_match_item(row_id):
    return {"row_id": row_id, "mode": "propose", "action": "proposed", "match": {"tier": "none"}}


def test_a_linkedin_only_row_reaches_unmatched_through_the_real_match_lane(
        tmp_path, fake_config, stub_post_transport_factory):
    """`rows_from_table` -> `build_rows_spec` -> `plan_chunks` -> `match_batch` ->
    `classify_matches`, with no client-side identity gate anywhere on this path (Task
    1's fix lives in the backend's `Map Columns` node and the YAML `columnMap.js` pair,
    not here) — the row simply flows through to a real HubSpot search on its
    `linkedin_url` key, exactly like an email row would on its own key."""
    path = _linkedin_only_csv(tmp_path)
    rows = preingest.rows_from_table(path)["rows"]
    assert rows == [{"linkedin_url": "https://www.linkedin.com/in/dana-osei"}]

    spec = preingest.build_rows_spec(rows)
    row_id = spec["rows"][0]["row_id"]

    cfg = _match_ceiling_config(fake_config)
    ceiling = chunking.chunk_ceiling(cfg, key="max_rows_per_match_request")
    plan = chunking.plan_chunks(spec, ceiling)
    assert plan.chunk_count == 1

    match_transport = stub_post_transport_factory(responses=[[_none_tier_match_item(row_id)]])
    outcome = preingest.match_batch(plan, cfg, transport=match_transport)
    classified = preingest.classify_matches(
        spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids,
    )

    assert classified["auto_matched"] == []
    assert classified["proposed"] == []
    assert classified["unchecked"] == []
    assert [entry["row_id"] for entry in classified["unmatched"]] == [row_id]


def test_a_lusha_hit_for_the_unmatched_row_is_proposed_through_resolutions_and_revalidated(
        tmp_path, fake_config, stub_post_transport_factory):
    """The join this task adds: what `classify_matches` calls `unmatched` is exactly
    what the waterfall (step 4-5) works on next. Once Lusha — the only provider that
    reads a bare `linkedin_url`, D-61-04 — returns a value this row did not already
    carry, it is proposed and, once confirmed, recorded as a `resolutions` entry and
    the corrected record validated again through the SAME loop `extraction.md`'s own
    adapters use (D-59-08's `provider_result` source) — never a second proposal
    surface, and never written on Claude's own authority."""
    path = _linkedin_only_csv(tmp_path)
    spec = preingest.build_rows_spec(preingest.rows_from_table(path)["rows"])
    row_id = spec["rows"][0]["row_id"]

    cfg = _match_ceiling_config(fake_config)
    ceiling = chunking.chunk_ceiling(cfg, key="max_rows_per_match_request")
    plan = chunking.plan_chunks(spec, ceiling)
    match_transport = stub_post_transport_factory(responses=[[_none_tier_match_item(row_id)]])
    outcome = preingest.match_batch(plan, cfg, transport=match_transport)
    classified = preingest.classify_matches(
        spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids,
    )
    unmatched_row = classified["unmatched"][0]

    # Lusha's own contact-enrich result named this row's company -- a value the
    # source spreadsheet never carried. Propose it, then (as if the operator said
    # yes) record it as a `resolutions` entry naming `provider_result`.
    record = {
        "row": {**unmatched_row["row"], "company": "Acme Racing"},
        "provenance": {"input": "lusha_waterfall", "locator": unmatched_row["row_id"]},
        "resolutions": [
            {"field": "company", "source": "provider_result", "detail": "Lusha contact enrich"}
        ],
    }

    result = extraction.validate({"records": [record]})

    assert result.rejected == []
    assert len(result.accepted) == 1
    accepted = result.accepted[0]
    assert accepted["row"]["linkedin_url"] == "https://www.linkedin.com/in/dana-osei"
    assert accepted["row"]["company"] == "Acme Racing"
    assert accepted["resolutions"] == [
        {"field": "company", "source": "provider_result", "detail": "Lusha contact enrich"}
    ]


def test_a_resolutions_entry_naming_an_illegitimate_source_is_rejected_not_laundered():
    """T-59-20, restated for this exact join: nothing about a linkedin-sourced row
    exempts it from the closed `RESOLUTION_SOURCES` vocabulary. A resolution claiming
    Claude's own recall (or any spelling outside the four legitimate identifiers)
    rejects the whole record rather than being accepted unlabelled."""
    record = {
        "row": {"linkedin_url": "https://www.linkedin.com/in/dana-osei", "company": "Acme Racing"},
        "provenance": {"input": "lusha_waterfall", "locator": "row-1"},
        "resolutions": [
            {"field": "company", "source": "claude_recall", "detail": "companies like this usually..."}
        ],
    }

    result = extraction.validate({"records": [record]})

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "claude_recall" in result.rejected[0]["reason"]


def test_config_gate_load_config_and_extraction_validate_are_both_real_scripts_modules():
    """A cheap guard against the census's own module-name derivation silently going
    stale: `scripts_modules()` derives its allowlist from `scripts/*.py` at runtime, so
    a rename of either module used in the new SKILL.md block would otherwise surface
    only as a confusing AST-identity mismatch rather than here, at the source."""
    assert callable(config_gate.load_config)
    assert callable(extraction.validate)
