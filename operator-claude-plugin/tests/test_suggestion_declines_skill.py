"""Tests for `skills/suggestion-declines/SKILL.md` (Phase 69 Plan 03).

The standalone drain (D-69-08 surface 2): reachable with no round running, offering
exactly four actions (`send`, `defer`, `delete`, `export`, D-69-06) over the backlog
`suggestion_declines.py` (plan 01) and `suggest-contacts/SKILL.md` step 8 (plan 02)
already persist.

Uses `test_skill_sequence_coverage`'s own `extract_python_blocks`/`parse_calls`/
`scripts_modules` helpers to parse the new SKILL.md's fences, rather than
re-implementing that parser -- the same idiom `test_autonomy_switch_prose.py` uses for
`_step`/`_numbered_step_spans`, copied here (not imported) for the same reason that
file states: independent evolution, no risk of colliding with work in flight in the
file it mirrors.
"""
import csv
import re
from pathlib import Path

import pytest

import extraction
import suggestion_declines

from test_skill_sequence_coverage import extract_python_blocks, parse_calls, scripts_modules

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PLUGIN_ROOT / "skills" / "suggestion-declines" / "SKILL.md"


def _skill_text():
    assert SKILL_PATH.exists(), f"{SKILL_PATH} does not exist yet"
    return SKILL_PATH.read_text(encoding="utf-8")


def _numbered_step_spans(text):
    """Copied from `test_autonomy_switch_prose.py` (itself copied from
    `test_implicit_approval_contract.py`) -- every top-level numbered step
    (`N. **...`) as `(step_number, span_text)`, a span running from its own heading to
    the next top-level heading or end of file."""
    matches = list(re.finditer(r"^(\d+)\. \*\*", text, flags=re.MULTILINE))
    assert matches, "expected at least one top-level numbered step in SKILL.md"
    spans = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((match.group(1), text[start:end]))
    return spans


def _step(text, number):
    for n, span in _numbered_step_spans(text):
        if n == str(number):
            return span
    raise AssertionError(f"no top-level numbered step {number} found in SKILL.md")


# =====================================================================================
# Fixture builders -- real `suggestion_declines.build_entry`/`entry_key`, never a
# hand-rolled dict, so a fixture that would fail `first_refusal` fails HERE too.
# =====================================================================================


def _entry(run_id, company_id, first, last, reason_code="no_email",
           reason="no usable email"):
    row = {"firstname": first, "lastname": last, "company": f"{last} Racing Club"}
    return suggestion_declines.build_entry(row, reason_code, reason, run_id, company_id)


def _seed_three_entries(path):
    """Three entries across two run ids -- one run of two, a second run of one --
    saved for real through `suggestion_declines.save`."""
    e1 = _entry("run-1", "1001", "Pat", "Alpha")
    e2 = _entry(
        "run-1", "1002", "Sam", "Beta", reason_code="email_domain_mismatch",
        reason="email domain stranger.example does not match beta.example",
    )
    e3 = _entry("run-2", "1003", "Robin", "Delta")
    k1 = suggestion_declines.entry_key("1001", e1["row"])
    k2 = suggestion_declines.entry_key("1002", e2["row"])
    k3 = suggestion_declines.entry_key("1003", e3["row"])
    entries = {k1: e1, k2: e2, k3: e3}
    suggestion_declines.save(entries, path=path)
    return entries, (k1, k2, k3)


# =====================================================================================
# Task 1: the drain's spine -- load, act on one entry, save
# =====================================================================================


def test_the_documented_drain_spine_deletes_one_entry_and_leaves_the_rest(tmp_path):
    path = tmp_path / "suggestion_declines.json"
    _entries, (k1, k2, k3) = _seed_three_entries(path)

    loaded = suggestion_declines.load(path=path)
    batch = suggestion_declines.partition_by_run(loaded, None)
    assert set(batch["backlog"]) == {k1, k2, k3}

    updated = suggestion_declines.apply_action(loaded, k2, "delete")
    suggestion_declines.save(updated, path=path)

    reloaded = suggestion_declines.load(path=path)
    assert set(reloaded) == {k1, k3}, "delete must remove exactly the chosen key and no other"
    assert reloaded[k1] == loaded[k1]
    assert reloaded[k3] == loaded[k3]


def test_defer_changes_nothing_on_disk(tmp_path):
    path = tmp_path / "suggestion_declines.json"
    _seed_three_entries(path)
    before = path.read_bytes()

    loaded = suggestion_declines.load(path=path)
    key = next(iter(loaded))
    updated = suggestion_declines.apply_action(loaded, key, "defer")
    suggestion_declines.save(updated, path=path)

    assert path.read_bytes() == before, "defer must not perturb the file's bytes at all"


def test_the_drain_reads_the_whole_backlog_without_a_run(tmp_path):
    path = tmp_path / "suggestion_declines.json"
    _entries, keys = _seed_three_entries(path)
    loaded = suggestion_declines.load(path=path)

    batch = suggestion_declines.partition_by_run(loaded, None)

    assert batch["this_run"] == {}
    assert set(batch["backlog"]) == set(keys), (
        "the standalone route needs no round to reach the backlog"
    )


# =====================================================================================
# Task 1: step 3's four-and-only-four action listing
# =====================================================================================

_FIFTH_ACTION_CANDIDATES = ("suppress", "ignore", "archive", "snooze", "skip")


def test_the_drain_skill_offers_exactly_the_four_actions():
    span = _step(_skill_text(), 3)
    lowered = span.lower()
    for action in suggestion_declines.DRAIN_ACTIONS:
        assert action in lowered, f"step 3 must name {action!r}"
    for candidate in _FIFTH_ACTION_CANDIDATES:
        assert candidate not in lowered, (
            f"step 3 must not name a fifth action word {candidate!r}"
        )


# =====================================================================================
# Task 1: no parallel write path, no match-gate vocabulary, no forbidden substring
# =====================================================================================

_FORBIDDEN_FENCE_CALLS = (
    "dispatch.dispatch", "write_grant.authorize_send",
    "write_grant.authorize_ungranted_send", "write_grant.plan_grant",
    "write_grant.open_grant", "n8n_arming.armed_window",
    "config_gate.autonomy_enabled", "run_report.build_run_report",
)


def _extracted_calls(text):
    modules = scripts_modules()
    all_calls = []
    for _block_index, _line_number, source in extract_python_blocks(text):
        all_calls.extend(parse_calls(source, modules))
    return all_calls


def test_the_drain_skill_carries_no_parallel_write_path():
    text = _skill_text()
    calls = _extracted_calls(text)
    for forbidden in _FORBIDDEN_FENCE_CALLS:
        assert forbidden not in calls, (
            f"{forbidden} must not be called from a suggestion-declines fence of its own"
        )
    assert "pre_spend_pause" not in text, (
        "the pre-spend pause lives only in the re-entered enrich-before-ingest steps"
    )
    assert "build_run_report" not in text, (
        "the mandatory end-of-run account lives only in the re-entered enrich-before-"
        "ingest step 9"
    )


def test_the_drain_skill_names_no_forbidden_substring():
    lowered = _skill_text().lower()
    assert "icp" not in lowered, "forbidden substring 'icp' found (D-10b)"
    assert "tier" not in lowered, "forbidden substring 'tier' found (D-10b)"


def test_the_drain_skill_never_touches_the_match_gate_vocabulary():
    text = _skill_text()
    calls = _extracted_calls(text)
    for forbidden in ("confidence.assess", "held_queue.build_entry", "held_queue.save"):
        assert forbidden not in calls, (
            f"{forbidden} is the match-gate vocabulary; a suggestion-round decline "
            "answers a different question and must never route through it"
        )


# =====================================================================================
# Task 2: export -- a spreadsheet the operator fixes by hand and feeds back through
# contact-upload
# =====================================================================================


def test_export_writes_canonical_headers_including_company_id(tmp_path):
    e1 = _entry("run-1", "2001", "Pat", "Alpha")
    k1 = suggestion_declines.entry_key("2001", e1["row"])
    entries = {k1: e1}
    out_path = tmp_path / "export.csv"

    header = suggestion_declines.export_rows(entries, [k1], out_path)

    assert header == extraction.canonical_props()
    with out_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        written_header = next(reader)
    assert written_header == extraction.canonical_props()
    assert "company_id" in written_header


def test_export_writes_an_emailless_row_rather_than_refusing_it(tmp_path):
    e1 = _entry("run-1", "2002", "Sam", "Beta")  # no_email -- row carries no email key
    assert "email" not in e1["row"]
    k1 = suggestion_declines.entry_key("2002", e1["row"])
    entries = {k1: e1}
    out_path = tmp_path / "export.csv"

    suggestion_declines.export_rows(entries, [k1], out_path)

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["email"] == "", "an emailless decline must export a blank cell, not raise"


def test_export_fills_company_id_from_the_entry_not_the_row(tmp_path):
    e1 = _entry("run-1", "2003", "Robin", "Gamma")
    assert "company_id" not in e1["row"], "build_entry never adds company_id to row on its own"
    k1 = suggestion_declines.entry_key("2003", e1["row"])
    entries = {k1: e1}
    out_path = tmp_path / "export.csv"

    suggestion_declines.export_rows(entries, [k1], out_path)

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["company_id"] == "2003"


def test_export_leaves_the_store_unchanged(tmp_path):
    path = tmp_path / "suggestion_declines.json"
    entries, (k1, _k2, _k3) = _seed_three_entries(path)
    before = path.read_bytes()

    loaded = suggestion_declines.load(path=path)
    out_path = tmp_path / "export.csv"
    suggestion_declines.export_rows(loaded, [k1], out_path)

    assert path.read_bytes() == before, "export must never write to the store's own file"

    updated = suggestion_declines.apply_action(loaded, k1, "export")
    assert updated == loaded, "export is a copy, never a move"


def test_export_never_calls_write_dispatch_csv():
    calls = _extracted_calls(_skill_text())
    assert "extraction.write_dispatch_csv" not in calls, (
        "export must never reach write_dispatch_csv's STRUCT-02 emailless refusal -- "
        "handing the operator an incomplete row to fix is the whole point of export"
    )
