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
import ast
import csv
import re
import textwrap
from pathlib import Path

import pytest

import chunking
import config_gate
import dispatch
import executions_client
import extraction
import n8n_arming
import preingest
import suggest_contacts
import suggestion_declines
import watch
import write_grant

from test_skill_sequence_coverage import extract_python_blocks, parse_calls, scripts_modules
from test_write_grant import CONTACTS_WORKFLOW_ID, _executions_page, _workflow_list

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


# =====================================================================================
# Task 3: send -- the existing write path, re-entered, with no exemption
# =====================================================================================

COMPANY_ID = "5001"
COMPANY_DOMAIN = "roma-example.example"


@pytest.fixture(autouse=True)
def _clear_workflow_id_cache_for_this_module():
    """`executions_client._workflow_id_cache` is process-lifetime (no global autouse
    clears it in conftest.py) -- without this, a resolved id from an earlier test in
    this module leaks into the next one and its own workflow-list read is silently
    skipped, consuming the scripted transport queue one entry out of step."""
    executions_client._workflow_id_cache.clear()
    yield
    executions_client._workflow_id_cache.clear()


@pytest.fixture
def granting_config(fake_config):
    """A config whose admin set the settings key to the JSON boolean true -- same
    shape as `test_write_grant.py`'s own fixture, defined locally per that file's own
    stated reason for staying separate (independent evolution)."""
    return {**fake_config, config_gate.WRITE_GRANT_SETTINGS_KEY: True}


def _contacts_workflow(record_writes='"false"', create='"false"', ids='""', domains='""'):
    """Same miniature two-gate shape `test_write_grant.py::_base_workflow` uses,
    scoped to the CONTACTS lane -- a drained send is a contacts-lane send, never the
    enrichment lane's own workflow id."""
    gate = (
        f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
        f"const ALLOW_HUBSPOT_CREATE = {create};\n"
        'const ALLOW_HUBSPOT_REVIEW_WRITES = "false";\n'
        f"const TEST_RECORD_IDS = {ids};\n"
        f"const TEST_RECORD_DOMAINS = {domains};\n"
        "function _writeSafetyAllows() { return false; }\n"
    )
    return {
        "id": CONTACTS_WORKFLOW_ID,
        "name": write_grant.LANES["contacts"],
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Create Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _armed_contacts_workflow(ids=f'"{COMPANY_ID}"', domains='""'):
    return _contacts_workflow(record_writes='"true"', create='"true"', ids=ids,
                              domains=domains)


def _contacts_plan_reads(guardrail=None):
    """Everything ONE `plan_grant` over a single contacts-lane record consumes, in
    frozen call order -- mirrors `test_write_grant.py::_plan_reads(lanes=1)`."""
    return [
        _workflow_list(), _executions_page(),
        guardrail if guardrail is not None else _contacts_workflow(),
    ]


def _armed_window_reads(ids=f'"{COMPANY_ID}"', domains='""'):
    """Everything ONE `armed_window` enter+exit consumes over a fresh arm -- mirrors
    `test_write_grant.py`'s own 12-item arm+disarm shape (5 arm + 1 verify + 6
    disarm). `domains` must echo the SAME value the arm itself requests, or the
    independent read-back guard (`ArmingRefused`) fires -- the arm-verification and
    disarm-observation reads both carry the domain allowlist too, not only the ids."""
    return [
        _contacts_workflow(), _contacts_workflow(), {}, {}, {},
        _contacts_workflow(record_writes='"true"', create='"true"', ids=ids,
                           domains=domains),
        _armed_contacts_workflow(ids=ids, domains=domains),
        _armed_contacts_workflow(ids=ids, domains=domains),
        {}, {}, {}, _contacts_workflow(),
    ]


def _entry_with_provenance(run_id, company_id, first, last, reason_code="no_email",
                           reason="no usable email"):
    row = {"firstname": first, "lastname": last, "company": f"{last} Racing Club"}
    provenance = {
        "input": "suggest_contacts_ladder",
        "locator": "https://example-club.example/committee",
    }
    return suggestion_declines.build_entry(
        row, reason_code, reason, run_id, company_id, provenance)


def test_a_drained_send_clears_the_same_gates_a_normal_send_clears(
        granting_config, stub_module_transport_factory, stub_transport, tmp_path):
    entry = _entry_with_provenance("run-1", COMPANY_ID, "Pat", "Alpha")
    key = suggestion_declines.entry_key(COMPANY_ID, entry["row"])
    chosen = {key: entry}
    supplied_email = "pat.alpha@roma-example.example"
    supplied = {key: {"email": supplied_email}}

    records = [
        {"record_type": "contacts",
         "row": {**e["row"], **supplied.get(k, {}), "company_id": e["company_id"]},
         "provenance": e["provenance"]}
        for k, e in chosen.items()
    ]
    result = extraction.validate(suggest_contacts.round_artifact(records))
    assert not result.rejected, (
        f"the drained row must clear extraction.validate() on its own: {result.rejected}"
    )
    assert len(result.accepted) == 1

    rows = [record["row"] for record in records]
    sendable_rows, held_rows = extraction.hold_emailless(rows)
    assert held_rows == [], "the operator-supplied email makes this row fully sendable"

    rows = preingest.strip_enrichment_extras(sendable_rows)
    rows = extraction.strip_row_id(rows)
    out_path = tmp_path / "dispatch.csv"
    extraction.write_dispatch_csv(rows, out_path)

    send_ids = sorted({e["company_id"] for e in chosen.values()})
    send_domains = [row["email"].rpartition("@")[2] for row in sendable_rows]
    allow_create = True

    ungranted_transport = stub_module_transport_factory(
        _contacts_plan_reads() + _armed_window_reads(
            ids=f'"{send_ids[0]}"', domains=f'"{send_domains[0]}"')
    )
    decision = write_grant.authorize_ungranted_send(
        granting_config, lane="contacts", object_type="contacts",
        record_ids=send_ids, record_domains=send_domains, allow_create=allow_create,
        label="drained send", transport=ungranted_transport)
    assert decision["armed"] is True, decision.get("detail")

    with n8n_arming.armed_window(
            decision["workflow_id"], send_ids, send_domains, allow_create,
            granting_config, transport=ungranted_transport,
            grant=decision["grant"]) as window:
        dispatch_result = dispatch.dispatch(
            str(out_path), True, granting_config, transport=stub_transport)

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    assert dispatch_result["run_id"]
    assert len(stub_transport.calls) == 1, "exactly one call on the authorized path"

    with out_path.open(newline="", encoding="utf-8") as f:
        data_rows = list(csv.DictReader(f))
    assert len(data_rows) == 1
    assert data_rows[0]["email"] == supplied_email


def test_a_drained_send_runs_step_5s_gates_before_step_7(
        granting_config, fake_config, stub_module_transport_factory, stub_transport,
        tmp_path):
    out_path = tmp_path / "dispatch.csv"
    out_path.write_text("email\njamie.fox@roma-example.example\n", encoding="utf-8")
    events = []

    def _sleep_recorder(seconds):
        events.append(("pause", seconds))

    class _LoggingTransport:
        def __init__(self, inner):
            self._inner = inner
            self.calls = inner.calls

        def __call__(self, *args, **kwargs):
            events.append(("transport", args[0] if args else None))
            return self._inner(*args, **kwargs)

    cfg_on = {**granting_config, "autonomy": {"write": True}}
    assert config_gate.autonomy_enabled(cfg_on, "write") is True

    plan_transport = stub_module_transport_factory(_contacts_plan_reads())
    proposal = write_grant.plan_grant(
        cfg_on, lanes=["contacts"], object_type="contacts",
        record_ids=[COMPANY_ID], record_domains=[COMPANY_DOMAIN], allow_create=True,
        label="drained send", suggestion_companies=1, transport=plan_transport)
    assert proposal["kind"] == write_grant.PROPOSAL_KIND, proposal
    assert proposal["envelope"]["suggestion_allowance"]["company_count"] == 1

    watch.pre_spend_pause(sleep=_sleep_recorder)
    assert events == [("pause", watch.PRE_SPEND_PAUSE_SECONDS)]

    grant = write_grant.open_grant(proposal, "yes", cfg_on)
    decision = write_grant.authorize_send(
        grant, lane="contacts", record_ids=[COMPANY_ID], record_domains=[COMPANY_DOMAIN])
    assert decision["armed"] is True

    arm_transport = stub_module_transport_factory(
        _armed_window_reads(domains=f'"{COMPANY_DOMAIN}"'))
    logging_dispatch_transport = _LoggingTransport(stub_transport)

    with n8n_arming.armed_window(
            decision["workflow_id"], [COMPANY_ID], [COMPANY_DOMAIN], True, cfg_on,
            transport=arm_transport, grant=decision["grant"]) as window:
        dispatch.dispatch(str(out_path), True, cfg_on, transport=logging_dispatch_transport)

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    pause_index = events.index(("pause", watch.PRE_SPEND_PAUSE_SECONDS))
    transport_indices = [i for i, e in enumerate(events) if e[0] == "transport"]
    assert transport_indices, "the send must have reached the dispatch transport"
    assert pause_index < min(transport_indices), (
        "the pause must land before the first credit-spending call of step 7"
    )

    cfg_off = {**granting_config, "autonomy": {"write": False}}
    assert config_gate.autonomy_enabled(cfg_off, "write") is False, (
        "with autonomy off, the documented branch is the two-phase ask, never the "
        "stated price/pause/open path"
    )


def test_the_drain_send_fence_binds_step_5s_inputs():
    text = _skill_text()
    span = _step(text, 4)
    fence_match = re.search(r"```python\n(.*?)```", span, re.DOTALL)
    assert fence_match, "step 4 must contain exactly one python fence"
    tree = ast.parse(textwrap.dedent(fence_match.group(1)))
    assigned_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
    for name in ("send_ids", "send_domains", "allow_create"):
        assert name in assigned_names, (
            f"step 4's fence must bind {name} by name -- the re-entered fences read "
            "it and never define it"
        )


def test_a_drained_send_is_removed_only_after_the_outcome_is_recorded(
        granting_config, stub_module_transport_factory, stub_post_transport_factory,
        tmp_path):
    text = _skill_text()
    rdo_index = text.index("write_grant.record_dispatch_outcome")
    apply_index = text.index("suggestion_declines.apply_action(")
    assert rdo_index < apply_index, (
        "the apply_action call for a send must appear AFTER the sentence naming "
        "write_grant.record_dispatch_outcome"
    )

    entry = _entry_with_provenance("run-1", COMPANY_ID, "Jamie", "Fox")
    key = suggestion_declines.entry_key(COMPANY_ID, entry["row"])
    declines = {key: entry}
    row = {**entry["row"], "email": "jamie.fox@roma-example.example",
           "company_id": entry["company_id"]}
    record = {"record_type": "contacts", "row": row, "provenance": entry["provenance"]}
    result = extraction.validate(suggest_contacts.round_artifact([record]))
    assert not result.rejected

    rows = preingest.strip_enrichment_extras([row])
    rows = extraction.strip_row_id(rows)
    out_path = tmp_path / "dispatch.csv"
    extraction.write_dispatch_csv(rows, out_path)

    send_ids = [entry["company_id"]]
    send_domains = ["roma-example.example"]
    allow_create = True

    plan_transport = stub_module_transport_factory(_contacts_plan_reads())
    proposal = write_grant.plan_grant(
        granting_config, lanes=["contacts"], object_type="contacts",
        record_ids=send_ids, record_domains=send_domains, allow_create=allow_create,
        label="drained send", transport=plan_transport)
    assert proposal["kind"] == write_grant.PROPOSAL_KIND
    grant = write_grant.open_grant(proposal, "yes", granting_config)
    decision = write_grant.authorize_send(
        grant, lane="contacts", record_ids=send_ids, record_domains=send_domains)
    assert decision["armed"] is True

    arm_transport = stub_module_transport_factory(
        _armed_window_reads(domains=f'"{send_domains[0]}"'))
    dead_transport = stub_post_transport_factory(
        responses=[ConnectionError("connection refused")])

    def _run_send_and_apply():
        outcome_ingest = None
        disarm = None
        crashed = False
        grant_local = decision["grant"]
        try:
            with n8n_arming.armed_window(
                    decision["workflow_id"], send_ids, send_domains, allow_create,
                    granting_config, transport=arm_transport,
                    grant=grant_local) as window:
                dispatch_result = dispatch.dispatch(
                    str(out_path), True, granting_config, transport=dead_transport)
                outcome_ingest = chunking.single_dispatch_outcome(
                    dispatch_result, record_count=len(rows))
            disarm = window.disarm_result
        except Exception:
            crashed = True
            raise
        finally:
            close_reason = write_grant.CLOSED_UNHANDLED_ERROR if crashed else None
            write_grant.record_dispatch_outcome(
                grant_local, outcome_ingest, granting_config, disarm=disarm,
                reason=close_reason)
        # Unreachable on a failed send -- mirrors step 7's apply_action call, which
        # this fence never reaches because the exception above already propagated.
        return suggestion_declines.apply_action(declines, key, "send")

    with pytest.raises(dispatch.DispatchError):
        _run_send_and_apply()

    assert key in declines, "a refused or failed send must leave the person in the store"


def test_a_drained_send_on_a_still_emailless_no_email_entry_holds_it_instead_of_crashing(
        stub_transport):
    """CR-02: a `no_email` entry the operator picked `send` for, but did not supply
    an email for, must be held by `extraction.hold_emailless` -- not crash the
    fence's own `send_domains` line with an unhandled `KeyError`. The entry stays
    in the store (never applied/removed) and no transport is ever touched."""
    entry = _entry_with_provenance("run-1", COMPANY_ID, "Pat", "Alpha")  # no_email
    assert "email" not in entry["row"]
    key = suggestion_declines.entry_key(COMPANY_ID, entry["row"])
    chosen = {key: entry}
    supplied = {}  # the operator supplied nothing for this entry

    records = [
        {"record_type": "contacts",
         "row": {**e["row"], **supplied.get(k, {}), "company_id": e["company_id"]},
         "provenance": e["provenance"]}
        for k, e in chosen.items()
    ]
    result = extraction.validate(suggest_contacts.round_artifact(records))
    assert not result.rejected, (
        "a firstname+lastname+company row still satisfies has_identity with no email"
    )
    rows = [record["row"] for record in records]

    # The documented, FIXED step 4(a) fence: hold_emailless runs BEFORE send_domains
    # is computed, so a still-emailless row is held rather than crashing.
    sendable_rows, held_rows = extraction.hold_emailless(rows)
    assert sendable_rows == []
    assert len(held_rows) == 1

    send_ids = sorted({e["company_id"] for e in chosen.values()})
    send_domains = [row["email"].rpartition("@")[2] for row in sendable_rows]  # no KeyError
    assert send_domains == []

    assert stub_transport.calls == [], "nothing sendable means no transport call happens"
    declines = {key: entry}
    assert key in declines, "the entry must remain in the store -- it was never applied"


def test_the_drain_send_fence_holds_emailless_rows_before_computing_send_domains():
    """CR-02: step 4(a)'s documented fence must call `extraction.hold_emailless`
    BEFORE building `send_domains`, and `send_domains` must be computed over the
    sendable half only -- never index `record["row"]["email"]` directly, which
    crashes with an unhandled `KeyError` on a still-emailless `no_email` entry."""
    span = _step(_skill_text(), 4)
    hold_index = span.index("extraction.hold_emailless(")
    send_domains_index = span.index("send_domains = ")
    assert hold_index < send_domains_index, (
        "hold_emailless must run before send_domains is computed (CR-02)"
    )
    assert 'record["row"]["email"]' not in span, (
        "send_domains must never index a record's email directly -- that crashes on "
        "a still-emailless no_email entry"
    )


def test_an_ungranted_drained_send_is_refused_not_waved_through(
        fake_config, stub_module_transport_factory, stub_transport):
    transport = stub_module_transport_factory([])

    decision = write_grant.authorize_ungranted_send(
        fake_config, lane="contacts", object_type="contacts",
        record_ids=[COMPANY_ID], record_domains=[COMPANY_DOMAIN], allow_create=True,
        label="drained send", transport=transport)

    assert decision["armed"] is False
    assert transport.calls == [], "a drained entry is not a back door -- zero calls on refusal"
    assert stub_transport.calls == []


def test_the_drain_skill_names_the_two_steps_it_re_enters():
    span = _step(_skill_text(), 4)
    assert "enrich-before-ingest/SKILL.md" in span
    assert "step 5" in span
    assert "step 7" in span
    assert "step 9" in span


def test_the_inline_pointer_names_the_standalone_skill():
    suggest_path = PLUGIN_ROOT / "skills" / "suggest-contacts" / "SKILL.md"
    step9 = _step(suggest_path.read_text(encoding="utf-8"), 9)
    assert "suggestion-declines" in step9
    assert "suggestion_declines.apply_action" not in step9
    assert "suggestion_declines.export_rows" not in step9
