"""operator-claude-plugin/tests/test_resume_or_fail_loudly.py

Phase 61 Plan 05 Task 3 (RUN-03, REVIEW-08/C13/C15). Two things live here, matching the
two pieces of code Task 3 actually adds — `run_manifest.py` itself is deliberately
UNCHANGED (its `load()`/`save()`/`rows_to_resume` all stay byte-identical; the plan's own
`files_modified` list omits it):

1. `chunking.merge_chunk_verdicts` (REVIEW-C13) — read-merge-write over the ACCUMULATED
   manifest document, so a per-chunk save can never erase a prior chunk's verdicts the
   way a bare `run_manifest.save(run_id, {this chunk's own rows})` would. Not wired into
   `dispatch_plan` itself: a verdict is derived downstream (Haiku/Sonnet/confidence), so
   the caller composes the two, the same "a caller composes the two" precedent
   `run_state.mark_dispatched`'s own docstring already names for a different pair.

2. `watch.classify_manifest_read` / `watch.resume_or_disclose` /
   `watch.build_resume_completion_report` (REVIEW-08's report-path half) — the RESUME
   rule underneath (`run_manifest.rows_to_resume`) is reused unmodified; what is new is
   deciding, from a classification of the file itself (never from `load()`'s degrade-to-
   `{}` return, which cannot distinguish "never registered" from "corrupted"), which of
   four disclosure sentences accompanies a full rerun versus an ordinary resume.

Isolation is the unit-level style `test_run_manifest.py`'s own docstring names: every
test below passes an explicit `path=` into a `tmp_path` file, never touching
`CLAUDE_PLUGIN_DATA` or the real durable home.
"""
import json

import run_manifest
import chunking
import watch


# =====================================================================================
# 1. chunking.merge_chunk_verdicts — read-merge-write, bounded crash window (REVIEW-C13)
# =====================================================================================

def test_merge_chunk_verdicts_accumulates_across_calls_never_overwrites(tmp_path):
    path = tmp_path / "run_manifest.json"
    chunking.merge_chunk_verdicts("run-1", {"r1": run_manifest.MATCHED}, path=path)
    chunking.merge_chunk_verdicts("run-1", {"r2": run_manifest.HELD}, path=path)

    accumulated = run_manifest.load(path=path)
    assert accumulated == {"r1": run_manifest.MATCHED, "r2": run_manifest.HELD}, (
        "the second chunk's own merge must not erase the first chunk's verdict — a "
        "bare run_manifest.save(run_id, {this chunk's rows}) would"
    )


def test_merge_chunk_verdicts_crash_between_chunks_loses_at_most_one_chunk(tmp_path):
    path = tmp_path / "run_manifest.json"
    chunking.merge_chunk_verdicts("run-1", {"r1": run_manifest.MATCHED}, path=path)
    # "Crash" here — the second chunk's own merge call never happens.

    accumulated = run_manifest.load(path=path)
    assert accumulated == {"r1": run_manifest.MATCHED}, (
        "the crash window is exactly one chunk wide — the first chunk's own already-"
        "completed save must survive a crash before the second chunk's"
    )


def test_merge_chunk_verdicts_this_chunk_wins_on_overlap(tmp_path):
    path = tmp_path / "run_manifest.json"
    chunking.merge_chunk_verdicts("run-1", {"r1": run_manifest.UNCHECKED}, path=path)
    chunking.merge_chunk_verdicts("run-1", {"r1": run_manifest.ENRICHED}, path=path)

    assert run_manifest.load(path=path) == {"r1": run_manifest.ENRICHED}


# =====================================================================================
# 2a. watch.classify_manifest_read — absent / parseable / anomalous / wrong-run,
#     pinned to agree with run_manifest.load()'s own return (the correctness trap: a
#     legitimately-empty verdicts map must classify PARSEABLE, never ANOMALOUS).
# =====================================================================================

def test_classify_absent_when_file_was_never_written(tmp_path):
    path = tmp_path / "run_manifest.json"
    assert watch.classify_manifest_read(path=path) == watch.ABSENT


def test_classify_parseable_iff_load_returns_the_stored_verdicts(tmp_path):
    path = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"r1": run_manifest.MATCHED}, path=path)

    assert watch.classify_manifest_read(path=path) == watch.PARSEABLE
    assert run_manifest.load(path=path) == {"r1": run_manifest.MATCHED}


def test_classify_parseable_for_a_legitimately_empty_verdict_map(tmp_path):
    # A run that has registered but dispatched no chunk yet — a real, honest {}, not a
    # failure to read. Must not be confused with ANOMALOUS.
    path = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {}, path=path)

    assert watch.classify_manifest_read(path=path) == watch.PARSEABLE
    assert run_manifest.load(path=path) == {}


def test_classify_anomalous_for_unparseable_text_iff_load_returns_empty(tmp_path):
    path = tmp_path / "run_manifest.json"
    path.write_text("not json at all {{{")

    assert watch.classify_manifest_read(path=path) == watch.ANOMALOUS
    assert run_manifest.load(path=path) == {}


def test_classify_anomalous_for_readable_json_with_an_invalid_verdict_word(tmp_path):
    # The internally-inconsistent case the plan's own action text names: a naive
    # implementation that only checks "did json.loads succeed" would call this
    # PARSEABLE and trust it. It must not.
    path = tmp_path / "run_manifest.json"
    path.write_text(json.dumps({
        "run_id": "run-1", "saved_at": "2026-08-30T00:00:00Z",
        "verdicts": {"r1": "not_a_real_verdict"},
    }))

    assert watch.classify_manifest_read(path=path) == watch.ANOMALOUS
    assert run_manifest.load(path=path) == {}


def test_classify_wrong_run_when_expected_run_id_does_not_match_the_stored_one(tmp_path):
    path = tmp_path / "run_manifest.json"
    run_manifest.save("run-A", {"r1": run_manifest.MATCHED}, path=path)

    assert watch.classify_manifest_read(path=path, expected_run_id="run-B") == watch.WRONG_RUN
    # With no expectation at all, the same file is an ordinary parseable read.
    assert watch.classify_manifest_read(path=path) == watch.PARSEABLE


# =====================================================================================
# 2b. watch.resume_or_disclose — one of exactly four disclosure sentences, the
#     underlying resume rule reused unmodified for the one trustworthy case.
# =====================================================================================

_ROWS = [{"row_id": "r1"}, {"row_id": "r2"}, {"row_id": "r3"}]


def test_resume_or_disclose_parseable_skips_completed_rows_and_says_so(tmp_path):
    path = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"r1": run_manifest.MATCHED}, path=path)

    report = watch.resume_or_disclose(_ROWS, path=path)

    assert report.classification == watch.PARSEABLE
    assert [r["row_id"] for r in report.rows] == ["r2", "r3"]
    assert len(report.skipped) == 1
    assert "1" in report.disclosure and "3" in report.disclosure


def test_resume_or_disclose_absent_reruns_everything_with_no_previous_state_sentence(tmp_path):
    path = tmp_path / "run_manifest.json"

    report = watch.resume_or_disclose(_ROWS, path=path)

    assert report.classification == watch.ABSENT
    assert report.rows == tuple(_ROWS)
    assert report.skipped == ()
    assert report.disclosure == "no previous state — running all 3 rows"


def test_resume_or_disclose_unreadable_reruns_everything_never_as_a_first_run(tmp_path):
    path = tmp_path / "run_manifest.json"
    path.write_text("not json at all {{{")

    report = watch.resume_or_disclose(_ROWS, path=path)

    assert report.classification == watch.ANOMALOUS
    assert report.rows == tuple(_ROWS)
    assert report.skipped == ()
    assert "unreadable" in report.disclosure
    assert "nothing was skipped" in report.disclosure
    assert report.disclosure != "no previous state — running all 3 rows", (
        "REVIEW-C15: an unreadable state must never present as a first run"
    )


def test_resume_or_disclose_internally_inconsistent_takes_the_same_full_rerun_path(tmp_path):
    path = tmp_path / "run_manifest.json"
    path.write_text(json.dumps({
        "run_id": "run-1", "saved_at": "2026-08-30T00:00:00Z",
        "verdicts": {"r1": "not_a_real_verdict"},
    }))

    report = watch.resume_or_disclose(_ROWS, path=path)

    assert report.classification == watch.ANOMALOUS
    assert report.rows == tuple(_ROWS), (
        "a test covering only unreadable JSON would pass on an implementation that "
        "trusts a readable-but-corrupted manifest — this is the internally-"
        "inconsistent case named explicitly in the plan"
    )
    assert "unreadable" in report.disclosure


def test_resume_or_disclose_wrong_run_reruns_everything_and_names_the_cause(tmp_path):
    path = tmp_path / "run_manifest.json"
    run_manifest.save("run-A", {"r1": run_manifest.MATCHED}, path=path)

    report = watch.resume_or_disclose(_ROWS, path=path, expected_run_id="run-B")

    assert report.classification == watch.WRONG_RUN
    assert report.rows == tuple(_ROWS)
    assert report.skipped == ()
    assert "different run" in report.disclosure
    assert "nothing was skipped" in report.disclosure


def test_resume_or_disclose_four_sentences_are_pairwise_distinct(tmp_path):
    # An operator reading these must be able to tell which of the four happened — two
    # identical sentences for different causes would defeat the point of naming them.
    absent_path = tmp_path / "absent.json"
    anomalous_path = tmp_path / "anomalous.json"
    anomalous_path.write_text("not json at all {{{")
    wrong_run_path = tmp_path / "wrong_run.json"
    run_manifest.save("run-A", {"r1": run_manifest.MATCHED}, path=wrong_run_path)
    parseable_path = tmp_path / "parseable.json"
    run_manifest.save("run-1", {"r1": run_manifest.MATCHED}, path=parseable_path)

    sentences = {
        watch.resume_or_disclose(_ROWS, path=absent_path).disclosure,
        watch.resume_or_disclose(_ROWS, path=anomalous_path).disclosure,
        watch.resume_or_disclose(_ROWS, path=wrong_run_path, expected_run_id="run-B").disclosure,
        watch.resume_or_disclose(_ROWS, path=parseable_path).disclosure,
    }
    assert len(sentences) == 4


# =====================================================================================
# 2c. watch.build_resume_completion_report — this-pass vs already-done-before-this-pass
# =====================================================================================

def test_completion_report_distinguishes_this_pass_from_already_done(tmp_path):
    path = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"r1": run_manifest.MATCHED}, path=path)
    resume_report = watch.resume_or_disclose(_ROWS, path=path)

    this_pass_verdicts = {"r2": run_manifest.ENRICHED, "r3": run_manifest.HELD}
    completion = watch.build_resume_completion_report(resume_report, this_pass_verdicts)

    assert completion["already_done_before_this_pass"] == 1
    assert completion["completed_this_pass"] == 1
    assert completion["still_held"] == 0
    assert completion["disclosure"] == resume_report.disclosure
