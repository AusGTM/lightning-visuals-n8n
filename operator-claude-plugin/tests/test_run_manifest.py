"""Tests for `run_manifest.py` (Phase 37 Plan 06):

Task 1: the manifest file itself — its own artifact, its own schema, its own refusal,
beside the dashboard pointer and never inside `artifact_store.py`.

Task 2: `rows_to_resume` — skip what completed, re-request what did not.

Task 3: the no-re-spend proof (against a recording transport, by row-id SET) and the
sweep-import-closure check.

Isolation mirrors `test_artifact_store.py`: `CLAUDE_PLUGIN_DATA` pointed at a `tmp_path`,
never real `~/.claude`. Most tests pass an explicit `path=` (the unit-level style used
throughout this suite); the two location tests below isolate via the env var instead,
since `manifest_path()`'s own default-path resolution is what they exercise.
"""
import json
import stat

import pytest

import artifact_store
import chunking
import durable_paths
import preingest
import run_manifest

# =====================================================================================
# Task 1a: manifest_path() — its own file, beside the dashboard pointer
# =====================================================================================


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    """Mirrors test_artifact_store.py's identically-named helper: CLAUDE_PLUGIN_DATA is
    durable_paths.durable_dir()'s own env override, so setting it resolves state_path()
    deterministically without touching this machine's real ~/.claude."""
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


def test_manifest_path_shares_a_parent_with_the_dashboard_pointer_but_not_its_name(
        monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    manifest = run_manifest.manifest_path()
    dashboard = artifact_store.state_path()

    assert manifest != dashboard
    assert manifest.parent == dashboard.parent


def test_manifest_path_is_not_a_dotfile(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert not run_manifest.manifest_path().name.startswith(".")


# =====================================================================================
# Task 1b: save() — the schema, the refusal
# =====================================================================================


def test_save_then_load_round_trips_the_verdicts(tmp_path):
    target = tmp_path / "run_manifest.json"
    verdicts = {"row-1": "matched", "row-2": "held"}

    run_manifest.save("run-abc", verdicts, path=target)

    assert run_manifest.load(path=target) == verdicts


def test_save_writes_at_mode_0600(tmp_path):
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-abc", {"row-1": "matched"}, path=target)

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_save_refuses_a_verdict_outside_the_four_allowed_words(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-abc", {"row-1": "definitely_not_a_verdict"}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_verdict_and_writes_nothing(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-abc", {"r1": "armed"}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_key_naming_the_offending_key(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError) as exc:
        run_manifest.save("run-abc", {"armed_batch": "matched"}, path=target)
    assert "armed_batch" in str(exc.value)
    assert not target.exists()


def test_save_refuses_a_secret_shaped_key(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError) as exc:
        run_manifest.save("run-abc", {"webhook_secret": "matched"}, path=target)
    assert "webhook_secret" in str(exc.value)
    assert not target.exists()


def test_save_refuses_an_api_key_shaped_key(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-abc", {"n8n_api_key": "matched"}, path=target)
    assert not target.exists()


def test_a_rejected_save_leaves_a_previously_saved_manifest_untouched(tmp_path):
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched"}, path=target)
    before = target.read_text()

    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-2", {"row-2": "armed"}, path=target)

    assert target.read_text() == before


def test_a_save_that_fails_partway_leaves_the_previous_manifest_readable(
        tmp_path, monkeypatch):
    """The atomic-write property, not the validation guard above: even a WRITE-time
    failure (disk full, permission yanked mid-write) must not corrupt what was already
    on disk. Forces the failure inside durable_paths._atomic_write_0600's own
    os.replace, which is the last step of that pattern — everything before it touches
    only a temp file, so a failure there proves the whole target file, not just a
    validation guard, is what stays intact."""
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched"}, path=target)
    before = target.read_text()

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(durable_paths.os, "replace", _boom)

    with pytest.raises(OSError):
        run_manifest.save("run-2", {"row-1": "enriched"}, path=target)

    assert target.read_text() == before


# =====================================================================================
# Task 1c: load() — every failure degrades to "no manifest"
# =====================================================================================


def test_load_on_a_missing_file_returns_empty_without_raising(tmp_path):
    target = tmp_path / "run_manifest.json"
    assert not target.exists()
    assert run_manifest.load(path=target) == {}


def test_load_on_malformed_json_returns_empty_without_raising(tmp_path):
    target = tmp_path / "run_manifest.json"
    target.write_text("not json", encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_file_that_is_not_a_mapping_returns_empty(tmp_path):
    target = tmp_path / "run_manifest.json"
    target.write_text(json.dumps(["row-1", "matched"]), encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_manifest_missing_the_verdicts_field_returns_empty(tmp_path):
    target = tmp_path / "run_manifest.json"
    target.write_text(json.dumps({"run_id": "run-1", "saved_at": "2026-08-05T00:00:00Z"}),
                      encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_verdicts_map_carrying_an_invalid_word_returns_empty_not_partial(
        tmp_path):
    """One bad entry degrades the WHOLE manifest — never a partially-trusted map that
    silently drops just the bad row."""
    target = tmp_path / "run_manifest.json"
    target.write_text(json.dumps({
        "run_id": "run-1", "saved_at": "2026-08-05T00:00:00Z",
        "verdicts": {"row-1": "matched", "row-2": "not_a_real_verdict"},
    }), encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_truncated_manifest_returns_empty(tmp_path):
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched", "row-2": "enriched"}, path=target)
    full_text = target.read_text()
    target.write_text(full_text[:len(full_text) // 2], encoding="utf-8")

    assert run_manifest.load(path=target) == {}


# =====================================================================================
# The two artifacts are genuinely separate stores
# =====================================================================================


def test_saving_the_manifest_never_touches_the_dashboard_pointer_file(
        monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    dashboard_path = artifact_store.state_path()
    before = dashboard_path.read_text()

    run_manifest.save("run-1", {"row-1": "matched"})

    assert dashboard_path.read_text() == before
    assert run_manifest.manifest_path().exists()


def test_the_module_exposes_no_fourth_verb():
    """Keeps the module from growing an accidental extra write path — mirrors
    test_artifact_store.py's own 'exactly load/save/collect' guard, minus collect (this
    manifest has no TTL/GC concept; a stale manifest is just superseded by the next
    save)."""
    import inspect

    public = {name for name in vars(run_manifest)
              if not name.startswith("_") and inspect.isfunction(getattr(run_manifest, name))
              and getattr(run_manifest, name).__module__ == "run_manifest"}
    assert public == {"manifest_path", "save", "load", "rows_to_resume"}


# =====================================================================================
# Task 2: rows_to_resume
# =====================================================================================


def _row(row_id, email=None):
    row = {"row_id": row_id, "firstname": "First", "lastname": "Doe", "company": "GCTC"}
    if email is not None:
        row["email"] = email
    return row


def test_a_row_verdicted_matched_or_enriched_is_excluded():
    rows = [_row("row-1"), _row("row-2")]
    manifest = {"row-1": "matched", "row-2": "enriched"}

    result = run_manifest.rows_to_resume(rows, manifest)

    assert result.rows == ()
    assert {entry["row_id"] for entry in result.skipped} == {"row-1", "row-2"}


def test_a_row_verdicted_unchecked_is_included_we_could_not_look_is_a_reason_to_look_again():
    rows = [_row("row-1")]
    manifest = {"row-1": "unchecked"}

    result = run_manifest.rows_to_resume(rows, manifest)

    assert result.rows == (rows[0],)
    assert result.skipped == ()


def test_a_held_row_without_an_email_stays_excluded_and_is_reported_still_held():
    rows = [_row("row-1")]  # no email
    manifest = {"row-1": "held"}

    result = run_manifest.rows_to_resume(rows, manifest)

    assert result.rows == ()
    assert result.still_held == ({"row_id": "row-1", "verdict": "held"},)


def test_a_held_row_that_now_carries_an_email_is_included():
    rows = [_row("row-1", email="now@example.com")]
    manifest = {"row-1": "held"}

    result = run_manifest.rows_to_resume(rows, manifest)

    assert result.rows == (rows[0],)
    assert result.still_held == ()


def test_a_row_absent_from_the_manifest_is_included():
    rows = [_row("row-1")]
    result = run_manifest.rows_to_resume(rows, {})
    assert result.rows == (rows[0],)


def test_an_empty_or_absent_manifest_means_every_row_is_included():
    rows = [_row("row-1"), _row("row-2"), _row("row-3")]

    assert run_manifest.rows_to_resume(rows, {}).rows == tuple(rows)
    assert run_manifest.rows_to_resume(rows, None).rows == tuple(rows)


def test_over_25_rows_with_18_recorded_enriched_it_resumes_7_and_names_18_skipped():
    rows = [_row(f"row-{i}") for i in range(1, 26)]
    manifest = {f"row-{i}": "enriched" for i in range(1, 19)}

    result = run_manifest.rows_to_resume(rows, manifest)

    assert len(result.rows) == 7
    assert len(result.skipped) == 18
    resumed_ids = {row["row_id"] for row in result.rows}
    assert resumed_ids == {f"row-{i}" for i in range(19, 26)}


def test_rows_to_resume_preserves_original_order():
    rows = [_row("row-1"), _row("row-2"), _row("row-3")]
    manifest = {"row-2": "matched"}

    result = run_manifest.rows_to_resume(rows, manifest)

    assert [row["row_id"] for row in result.rows] == ["row-1", "row-3"]


def test_rows_to_resume_is_pure_and_performs_no_file_read(tmp_path, monkeypatch):
    """No disk access at all — even pointing manifest_path() somewhere that would raise
    if touched must not affect the result, since this function takes an ALREADY-LOADED
    manifest."""
    def _explode():
        raise AssertionError("rows_to_resume must never read the manifest from disk")

    monkeypatch.setattr(run_manifest, "load", _explode)

    rows = [_row("row-1")]
    result = run_manifest.rows_to_resume(rows, {"row-1": "matched"})
    assert result.rows == ()


# =====================================================================================
# Task 2: build_rows_spec id stability is what makes the whole resume work
# =====================================================================================


def test_build_rows_spec_ids_are_stable_so_a_manifest_from_the_first_call_still_filters_the_second():
    input_rows = [
        {"firstname": "Jane", "lastname": "Doe", "company": "GCTC"},
        {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"},
    ]

    first = preingest.build_rows_spec(input_rows)
    second = preingest.build_rows_spec(input_rows)

    first_ids = [row["row_id"] for row in first["rows"]]
    second_ids = [row["row_id"] for row in second["rows"]]
    assert first_ids == second_ids

    manifest = {first_ids[0]: "matched"}
    result = run_manifest.rows_to_resume(second["rows"], manifest)
    assert [row["row_id"] for row in result.rows] == [second_ids[1]]


# =====================================================================================
# Task 3: the no-re-spend proof — asserted on the SET of row ids, not a call count
# =====================================================================================


def _match_item(row_id, tier, hs_object_id=None):
    match = {"tier": tier}
    if tier == "medium":
        match["candidates"] = []
    item = {"row_id": row_id, "mode": "propose", "action": "proposed", "match": match}
    if hs_object_id is not None:
        item["hs_object_id"] = hs_object_id
    return item


def _sent_row_ids(stub):
    """Every row_id present across every recorded call's request body — the set the
    no-re-spend proof is asserted against, never a bare len(stub.calls)."""
    ids = set()
    for call in stub.calls:
        for event in call["json"]["events"]:
            ids.add(event["row_id"])
    return ids


def test_a_resume_re_requests_only_rows_that_still_needed_work(
        fake_config, stub_post_transport_factory, tmp_path):
    input_rows = [
        {"firstname": f"First{i}", "lastname": "Doe", "company": "GCTC"} for i in range(5)
    ]
    spec = preingest.build_rows_spec(input_rows)
    plan = chunking.plan_chunks(spec, ceiling=5)  # one chunk, all 5 rows

    first_stub = stub_post_transport_factory(responses=[[
        _match_item("row-1", "high", hs_object_id="111"),
        _match_item("row-2", "high", hs_object_id="222"),
        _match_item("row-3", "none"),
        _match_item("row-4", "medium"),
        _match_item("row-5", "unknown"),  # -> unchecked
    ]])
    outcome = preingest.match_batch(plan, fake_config, transport=first_stub)
    classified = preingest.classify_matches(
        spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids)

    # Only genuinely terminal outcomes get a verdict: the two high-tier auto-matches.
    # unmatched (row-3) and proposed (row-4) are still open decisions, not persisted.
    verdicts = {entry["row_id"]: "matched" for entry in classified["auto_matched"]}
    manifest_path = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", verdicts, path=manifest_path)

    loaded = run_manifest.load(path=manifest_path)
    resume = run_manifest.rows_to_resume(spec["rows"], loaded)
    assert {row["row_id"] for row in resume.rows} == {"row-3", "row-4", "row-5"}

    resume_spec = {"rows": list(resume.rows), "object_type": "contacts"}
    resume_plan = chunking.plan_chunks(resume_spec, ceiling=5)
    second_stub = stub_post_transport_factory()  # fresh recorder
    preingest.match_batch(resume_plan, fake_config, transport=second_stub)

    assert _sent_row_ids(second_stub) == {"row-3", "row-4", "row-5"}, (
        "the resume must ask about exactly the still-open rows and none of the "
        "already-matched ones — asserted on the SET of ids in the request bodies, "
        "since a count alone could coincide while the wrong rows were sent"
    )


def test_a_resume_against_a_truncated_manifest_re_requests_every_row(
        fake_config, stub_post_transport_factory, tmp_path):
    """Degrading to a full run costs money; degrading to a partial skip costs a
    contact. Only one of those is recoverable, so a manifest this module cannot trust
    must re-request everything, never a subset."""
    input_rows = [
        {"firstname": f"First{i}", "lastname": "Doe", "company": "GCTC"} for i in range(3)
    ]
    spec = preingest.build_rows_spec(input_rows)
    manifest_path = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched", "row-2": "enriched"}, path=manifest_path)

    full_text = manifest_path.read_text()
    manifest_path.write_text(full_text[: len(full_text) // 2], encoding="utf-8")

    loaded = run_manifest.load(path=manifest_path)
    resume = run_manifest.rows_to_resume(spec["rows"], loaded)

    resume_spec = {"rows": list(resume.rows), "object_type": "contacts"}
    resume_plan = chunking.plan_chunks(resume_spec, ceiling=5)
    stub = stub_post_transport_factory()
    preingest.match_batch(resume_plan, fake_config, transport=stub)

    assert _sent_row_ids(stub) == {"row-1", "row-2", "row-3"}


# =====================================================================================
# Task 3: the unattended sweep still cannot write a byte
# =====================================================================================


def test_run_manifest_is_absent_from_the_sweeps_import_closure():
    """The compensating check for the sweep's read-only guard: run_manifest must never
    enter sweep_entry's transitive import closure, since the sweep neither runs nor
    resumes a batch. test_sweep_read_only.py's own allowlist-equality assertion already
    fails loudly if this ever changes; this is a second, load-bearing statement of the
    same fact, local to the module this plan actually adds."""
    import test_sweep_read_only as sweep_guard

    closure = sweep_guard.transitive_closure(sweep_guard.SWEEP_ENTRYPOINT, sweep_guard.SCRIPTS)
    assert "run_manifest" not in closure
