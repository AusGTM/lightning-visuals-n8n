"""Phase 73 Plan 01, Task 1 (F-B5, D-73-13): the frozen proof, written BEFORE the fix.

Attempt 2's Stage B (run `6891d018e84f4d869eb8080292dac6c5`, enrichment executions
`12432`-`12449`) sent 35 companies + 1 name-only row and produced, per the live
`written_records-6891d018e84f4d869eb8080292dac6c5.json` artifact this test's fixture
reproduces byte-for-byte: 24 rows classified `("contacts", None, "failed")`, 18 rows
`("contacts", "research_failed", "failed")`, 11 rows `("companies", "create",
"created_id_unknown")`, 1 row `("companies", "skip", "no_action")` — every one of the
54 recovered rows unjoinable (zero carry a `row_id` or a top-level `hs_object_id`).

This test drives the EXACT pipeline the live run went through — `written_records.
classify_item` over `Build Response`'s own recovered items, then `run_report.
_build_records` — over a committed, redacted recording of that run, so the RED result
below is read from real runData, not authored to match a guess.

Fixture provenance:
  - `tests/n8n/fixtures/frozen/exec_12434.runData.json` / `exec_12449.runData.json` —
    full runData, frozen live via `scripts/freeze_execution_rundata.py` (D-73-13's
    named two executions).
  - `tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json` — an
    EXCERPT (`Decide Company Action` + `Build Response` only) across all 18 executions
    of this run. The named two executions alone cannot prove the run's reconciliation:
    12434 carries 2 creates + 1 research marker, 12449 carries 1 skip + 1 create + 1
    research marker — neither contains a single `enrich` row, so a test built only
    from them could never assert an update outcome at all, red or green. This third
    fixture is a deliberate, documented departure from "exactly two" (deviation Rule 2
    — the plan's own literal fixture count would leave this test unable to prove the
    thing D-73-13 exists to prove).
"""
import json
from pathlib import Path

import written_records
import run_report
import report_enrichment

FROZEN_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "n8n" / "fixtures" / "frozen"
RUN_ID = "6891d018e84f4d869eb8080292dac6c5"


def _load_excerpt():
    return json.loads(
        (FROZEN_DIR / "run_6891d018-decide-and-response.excerpt.json").read_text())


def _build_response_rows(run_data):
    rows = []
    for run in run_data.get("Build Response", []):
        for branch in run.get("data", {}).get("main", []):
            for item in (branch or []):
                j = item.get("json")
                if isinstance(j, dict):
                    rows.append(j)
    return rows


def _rows_per_execution(excerpt):
    """`{execution_id: (rows, run_data)}` — run_data stays SCOPED to its own execution
    (matches what `chunking.dispatch_and_recover` actually has in hand per execution;
    `Decide Company Action`'s id lookup must never cross into a sibling execution)."""
    per_execution = {}
    for execution_id, execution in excerpt["executions"].items():
        run_data = execution.get("runData", {})
        per_execution[execution_id] = (_build_response_rows(run_data), run_data)
    return per_execution


def test_named_fixtures_exist_and_are_execution_12434_and_12449():
    """The two D-73-13 explicitly names, frozen full (not excerpted)."""
    for execution_id in (12434, 12449):
        path = FROZEN_DIR / f"exec_{execution_id}.runData.json"
        assert path.exists(), f"missing frozen fixture {path}"
        data = json.loads(path.read_text())
        assert str(data["execution_id"]) == str(execution_id)
        assert "runData" in data and isinstance(data["runData"], dict)


def test_frozen_recording_matches_the_real_written_records_distribution():
    """The exact shape observed live (T-73-01-03's whole subject) — reproduced from
    the committed fixture, not asserted from memory. This is the ground truth this
    plan's `must_haves` and Task 2's fix are measured against."""
    excerpt = _load_excerpt()
    all_rows = []
    for _execution_id, (rows, _run_data) in _rows_per_execution(excerpt).items():
        all_rows.extend(rows)

    assert len(all_rows) == 54

    entries = [written_records.classify_item(r) for r in all_rows]
    from collections import Counter
    shape = Counter((e["object_type"], e["action"], e["outcome"]) for e in entries)

    assert shape[("contacts", None, "failed")] == 24
    assert shape[("contacts", "research_failed", "failed")] == 18
    assert shape[("companies", "create", "created_id_unknown")] == 11
    assert shape[("companies", "skip", "no_action")] == 1
    assert sum(shape.values()) == 54

    assert sum(1 for e in entries if e.get("hs_object_id")) == 0
    assert sum(1 for e in entries if e.get("row_id")) == 0


def test_run_report_enrich_account_reconciles_after_backfill():
    """The D-73-13 target: 24 update/enrich + 11 create + 1 skip, joined correctly.

    `written_records.classify_item` is fed rows AFTER `report_enrichment.
    backfill_missing_identity` — the same transform `chunking.dispatch_and_recover`
    applies before persisting to `written_records` (Task 2's fix). Before that fix
    lands, every row here is `action=None`/`hs_object_id=None` (the previous test),
    so this assertion is RED against the pre-fix code and is the deliverable Task 1
    records; it turns GREEN once Task 2's fix is in place.
    """
    excerpt = _load_excerpt()

    all_entries = []
    total_excluded_markers = 0
    for _execution_id, (rows, run_data) in _rows_per_execution(excerpt).items():
        backfilled, excluded = report_enrichment.backfill_missing_identity(rows, run_data)
        total_excluded_markers += excluded
        all_entries.extend(written_records.classify_item(r) for r in backfilled)

    # D-73-12 (amended, see report_enrichment.backfill_missing_identity's own
    # docstring): the 18 whole-request research markers never described a row at all
    # (one per execution, never one per company) — they are EXCLUDED here rather than
    # forced into a per-record bucket, which is what "never counted as unjoinable"
    # means for a marker that was never a record. Recorded, never silently dropped.
    assert total_excluded_markers == 18

    from collections import Counter
    action_shape = Counter((e["object_type"], e["action"], e["outcome"]) for e in all_entries)
    assert action_shape[("companies", "enrich", "write_attempted")] == 24
    assert action_shape[("companies", "create", "written")] == 11
    assert action_shape[("companies", "skip", "no_action")] == 1
    assert sum(action_shape.values()) == 36  # 35 dispatched companies + 1 name-only skip

    records, unjoinable_seen = run_report._build_records(all_entries)

    joined_by_hs_object_id = sum(1 for b in records.values() if b["join"] == "hs_object_id")
    unjoinable = sum(1 for b in records.values() if b["join"] == "unjoinable")

    # 24 enrich + 11 create = 35 rows now carry a real HubSpot id and join correctly —
    # D-73-11's stated target in full.
    assert joined_by_hs_object_id == 35

    # The Illawarra skip never existed in HubSpot: the companies form mints no
    # `row_id` (enrichment.build_envelope's `companies` branch never sets one) and a
    # skipped row has no `id` either — there is no HubSpot id to recover and no
    # row_id to fall back to. Giving it an identity would mean joining by name or by
    # `company_dependency_id`, which is a SECOND join key `run_report.
    # _identity_for_entry` does not have today and which D-73-11/D-73-12 do not ask
    # for — Task 2's acceptance criteria forbids adding one ("No new join function
    # was added to run_report.py"). This is the one row the plan's literal "zero
    # unjoinable" cannot honestly reach without that addition; documented here and in
    # the plan SUMMARY rather than faked.
    assert unjoinable == 1
    assert unjoinable_seen is True

    assert joined_by_hs_object_id + unjoinable == 36
