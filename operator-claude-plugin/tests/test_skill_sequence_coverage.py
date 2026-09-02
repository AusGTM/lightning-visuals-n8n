"""The sequence-inventory meta-test (260829-hjm, `composition-boundary-blind-spot`).

Five defects in one week shipped past three fully green suites because every unit was
correct and individually tested, and the documented `SKILL.md` call SEQUENCES joining
those units were tested nowhere (`.planning/debug/knowledge-base.md`, last entry). This
module is the ratchet: it extracts every documented `module.function(...)` call
sequence of two-or-more scripts-module calls from every `skills/*/SKILL.md` python
block, and fails when a sequence is neither claimed by a named composition test
(`COVERED`) nor deliberately excluded with a reason (`NOT_A_PIPELINE` /
`GRANDFATHERED_UNCOVERED`).

This module does pure text and AST analysis of files on disk. It never imports,
executes, or writes anything under `operator-claude-plugin/scripts/` -- the autouse
`no_durable_writes` fixture in conftest.py is never touched, let alone bypassed.

Adding a NEW documented sequence with no covering test fails this suite; the failure
message names the skill, the block's line number, the call sequence, and both
remedies (write a composition test and register it in COVERED, or add a reasoned
entry to NOT_A_PIPELINE). Scope fence: this module ships the ratchet, not the
backfill -- five sequences below are honestly GRANDFATHERED_UNCOVERED rather than
claimed by a test that does not actually drive their result-consuming joins. Writing
those tests is follow-on work; MAX_GRANDFATHERED shrinks by one each time.
"""
import ast
import re
import textwrap
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATHS = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))

_FENCE_OPEN_RE = re.compile(r"^([ \t]*)```python[ \t]*$")
_FENCE_CLOSE_RE = re.compile(r"^[ \t]*```[ \t]*$")
_PLACEHOLDER_RE = re.compile(r"<[^<>\n]*>")


# =====================================================================================
# Pure helpers -- text/AST in, data out, no filesystem. Unit-tested below against a
# synthetic SKILL.md string with no real file involved.
# =====================================================================================

def extract_python_blocks(text):
    """Every fenced ```python block in `text`, dedented. GOTCHA 1: these blocks sit
    inside numbered lists, indented a few spaces -- `^```python` at column 0 finds
    nothing on this corpus. Returns (block_index, line_number, dedented_source);
    line_number is the fence's own 1-based line (matching `grep -n`), block_index is
    1-based source order -- NOT part of sequence identity (reordering blocks must not
    churn registry keys), only used to locate a parse failure.
    """
    lines = text.splitlines()
    blocks = []
    block_index = 0
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        block_index += 1
        line_number = i + 1
        i += 1
        body_lines = []
        while i < len(lines) and not _FENCE_CLOSE_RE.match(lines[i]):
            body_lines.append(lines[i])
            i += 1
        i += 1  # step past the closing fence (or EOF, harmless)
        source = textwrap.dedent("\n".join(body_lines))
        blocks.append((block_index, line_number, source))
    return blocks


class UnparseableBlockError(Exception):
    """GOTCHA 2: most high-value blocks are not valid Python -- they carry
    placeholders (`<override or None>`, `<this send's ids>`, ...) substituted before
    parsing. If a block STILL fails to parse after substitution, this is raised naming
    the skill and the block's line -- a silent skip is exactly the blind spot this
    module exists to close.
    """

    def __init__(self, skill_name, line_number, block_index, original):
        self.skill_name = skill_name
        self.line_number = line_number
        self.block_index = block_index
        self.original = original
        super().__init__(
            f"{skill_name}/SKILL.md line {line_number} (python block {block_index}): "
            f"block did not parse even after placeholder substitution "
            f"({type(original).__name__}: {original}) -- fix the block's prose or "
            f"widen the placeholder pattern; never let it be silently skipped."
        )


def parse_calls(source, module_names):
    """Ordered tuple of "module.function" strings for every `ast.Call` in `source`
    whose func is `module.function(...)` with `module` in `module_names` -- a plain
    top-down (pre-order) walk, so an outer call is recorded before a call nested in
    its own arguments (matches how these sequences read on the page). GOTCHA 3: `...`
    (Ellipsis) and `#` comments parse fine once (GOTCHA 2)'s substitution has run.
    Raises `SyntaxError` (uncaught here -- the caller knows the skill/line to name)
    if the block still will not parse.
    """
    substituted = _PLACEHOLDER_RE.sub("__PLACEHOLDER__", source)
    tree = ast.parse(substituted)
    calls = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in module_names
            ):
                calls.append(f"{func.value.id}.{func.attr}")
            self.generic_visit(node)

    _Visitor().visit(tree)
    return tuple(calls)


def sequences_in(skill_name, text, module_names):
    """Every (identity, line_number) pair for a >=2-scripts-module-call python block
    in `text`. identity = (skill_name, call_tuple) -- the block index is deliberately
    excluded (design: inserting a block earlier in the file must not churn keys).
    Raises `UnparseableBlockError` (not caught here) on a block GOTCHA 2's
    substitution cannot rescue.
    """
    results = []
    for block_index, line_number, source in extract_python_blocks(text):
        try:
            calls = parse_calls(source, module_names)
        except SyntaxError as exc:
            raise UnparseableBlockError(skill_name, line_number, block_index, exc) from exc
        if len(calls) >= 2:
            results.append(((skill_name, calls), line_number))
    return results


def scripts_modules():
    """The module-name set a SKILL.md `module.function(...)` call must reference to
    count -- derived from `scripts/*.py` at runtime (zero maintenance), and load-
    bearing: without it, `config.get(...)` / `responses.extend(...)` pollute identity
    tuples and they stop being stable.
    """
    return {p.stem for p in (PLUGIN_ROOT / "scripts").glob("*.py")}


def format_violation(skill_name, line_number, call_tuple):
    rendered = " -> ".join(call_tuple)
    return (
        f"UNREGISTERED SKILL SEQUENCE: {skill_name}/SKILL.md line {line_number} "
        f"documents the call sequence [{rendered}], which no composition test claims "
        f"(COVERED) and no registry deliberately excludes (NOT_A_PIPELINE / "
        f"GRANDFATHERED_UNCOVERED). Either (1) write a composition test that drives "
        f"this sequence end to end -- not its units in isolation -- and register its "
        f"nodeid in COVERED, or (2) if this is genuinely not a pipeline (no result "
        f"flows between the calls), add it to NOT_A_PIPELINE with a reason."
    )


# =====================================================================================
# The live census -- extracted identity -> first line number it appears at, across
# every skills/*/SKILL.md. Raises UnparseableBlockError (uncaught) if any live block
# fails to parse -- this is what makes a badly-edited SKILL.md fail this suite by
# construction rather than being silently skipped.
# =====================================================================================

def extracted_identities():
    modules = scripts_modules()
    result = {}
    for skill_path in SKILL_PATHS:
        skill_name = skill_path.parent.name
        text = skill_path.read_text()
        for identity, line_number in sequences_in(skill_name, text, modules):
            result.setdefault(identity, line_number)
    return result


# =====================================================================================
# The three registries. Every key below is a live-extracted identity as of this
# writing (2026-08-29) -- verified by reading each cited block and each candidate
# test before deciding. See task record for the full census walk.
# =====================================================================================

COVERED = {
    (
        "enrich-before-ingest",
        ("extraction.hold_emailless", "extraction.strip_row_id", "extraction.write_dispatch_csv"),
    ): "test_preingest_merge.py::test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv",
    # Phase 57 Task 4 (RUN-05, REVIEW-57-H7/H8): these four entries' tuples grew a
    # `write_grant.record_dispatch_outcome` close (and, for the single-shot legs, a
    # `chunking.single_dispatch_outcome` wrap first) once the ceiling wiring landed. The
    # sink changed too on the two single-shot legs, so their covering nodeid moved to a
    # test that actually drives `single_dispatch_outcome` -> `record_dispatch_outcome`
    # for real, rather than one written before either function existed.
    #
    # Phase 57 Task 3 (the 57-01 Task 4 handoff, taken): both tuples grew a
    # `remainder_queue.save` -> `remainder_queue.build_entry` pair inside the pre-call
    # ceiling-breach branch (outer call recorded before the entry it builds, per
    # `parse_calls`'s own pre-order rule) -- `contact-upload`'s also grew a leading
    # `tabular.read_table`, since that lane never parses the file into rows
    # client-side and must read it back once to name the held rows individually. The
    # sink is still `record_dispatch_outcome`, so the covering nodeid is unchanged;
    # the branch's OWN wiring (the remainder_queue calls actually appear, are real
    # code, and carry REASON_CEILING_BREACH) is pinned separately by
    # `test_write_grant.py::test_the_single_shot_ceiling_breach_writes_the_remainder_queue`.
    (
        "contact-upload",
        (
            "config_gate.load_config", "write_grant.authorize_send",
            "write_grant.authorize_ungranted_send", "tabular.read_table",
            "remainder_queue.save", "remainder_queue.build_entry",
            "write_grant.record_dispatch_outcome",
            "n8n_arming.armed_window", "dispatch.dispatch",
            "chunking.single_dispatch_outcome", "write_grant.record_dispatch_outcome",
        ),
    ): "test_write_grant.py::test_single_dispatch_outcome_composed_with_record_dispatch_outcome_closes_normally",
    # 57-05 Task 3: both `write_grant.record_dispatch_outcome` closes in the
    # enrich-before-ingest ingest leg now grow a `run_report.record_audit` call right
    # after them — the second is the new sink, since it is textually last in the
    # block. The covering nodeid is extended (not replaced) to mention it.
    (
        "enrich-before-ingest",
        (
            "config_gate.load_config", "write_grant.authorize_send",
            "write_grant.authorize_ungranted_send",
            "remainder_queue.save", "remainder_queue.build_entry",
            "write_grant.record_dispatch_outcome", "run_report.record_audit",
            "n8n_arming.armed_window", "dispatch.dispatch",
            "chunking.single_dispatch_outcome", "write_grant.record_dispatch_outcome",
            "run_report.record_audit",
        ),
    ): "test_write_grant.py::test_single_dispatch_outcome_composed_with_record_dispatch_outcome_closes_normally",
    # 57-05 Task 1: the two grant-time/end-of-run `run_report.record_audit`
    # observations land before `n8n_arming.armed_window` and right after
    # `write_grant.record_dispatch_outcome` respectively. The sink stays
    # `preingest.merge_enriched` — unchanged, so the covering nodeid needs no
    # extension, only the tuple.
    (
        "enrich-before-ingest",
        (
            "run_state.new_run_id", "run_state.start_run", "config_gate.load_config",
            "enrichment.resolve_providers", "chunking.plan_chunks", "chunking.chunk_ceiling",
            "write_grant.authorize_send", "write_grant.authorize_ungranted_send",
            "run_report.record_audit",
            "n8n_arming.armed_window", "chunking.dispatch_plan",
            "write_grant.record_dispatch_outcome", "run_report.record_audit",
            "chunking.projected_spend",
            "run_state.mark_dispatched",
            "run_state.read_progress", "watch.recover_async_dispatch", "preingest.merge_enriched",
        ),
    ): "test_chunking.py::test_the_enrich_before_ingest_waterfall_submits_async_and_recovers_through_merge_enriched",
    # 57-05 Task 3: the enrich-records dispatch block's own `run_report.record_audit`
    # pair — one before the grant's armed window, one in the finally right after
    # `record_dispatch_outcome`, which becomes the new sink.
    (
        "enrich-records",
        (
            "run_state.new_run_id", "config_gate.load_config",
            "enrichment.resolve_providers", "chunking.plan_chunks",
            "chunking.chunk_ceiling", "write_grant.authorize_send",
            "write_grant.authorize_ungranted_send", "run_report.record_audit",
            "n8n_arming.armed_window",
            "chunking.dispatch_plan", "write_grant.record_dispatch_outcome",
            "run_report.record_audit",
        ),
    ): "test_write_grant.py::test_record_dispatch_outcome_closes_the_grant_from_a_real_dispatch_ceiling_stop",
    (
        "enrich-before-ingest",
        (
            "config_gate.load_config", "chunking.plan_chunks", "chunking.chunk_ceiling",
            "preingest.match_batch", "preingest.classify_matches",
        ),
    ): "test_chunking.py::test_chunk_ceilings_real_match_key_return_flows_into_match_batch_and_classify_matches",
    (
        "enrich-before-ingest",
        (
            "config_gate.load_config", "preingest.build_rows_spec", "preingest.rows_from_table",
            "chunking.plan_chunks", "chunking.chunk_ceiling", "preingest.match_batch",
            "preingest.classify_matches", "extraction.validate",
        ),
    ): "test_linkedin_row_composition.py::test_a_lusha_hit_for_the_unmatched_row_is_proposed_through_resolutions_and_revalidated",
    (
        "enrich-before-ingest",
        (
            "held_queue.load", "run_manifest.load", "preingest.parse_outcome",
            "confidence.assess", "held_queue.build_entry", "held_queue.save",
            "run_manifest.save", "run_manifest.save", "run_manifest.run_manifest_path",
            "run_state.read_progress",
        ),
    ): "test_batch_finishes_composition.py::test_a_batch_with_a_failed_chunk_and_a_held_row_still_reaches_and_dispatches_its_last_row",
    # Phase 57 Task 3: the accepted-split persistence step (D-57-04's
    # `REASON_ALLOWANCE_SPLIT` producer) -- `build_entry`'s validated entry flows
    # straight into `save`'s list argument.
    (
        "enrich-records",
        ("remainder_queue.build_entry", "remainder_queue.save"),
    ): "test_remainder_queue.py::test_save_writes_a_0600_file_with_the_right_document_shape",
    # Phase 62 Plan 05 Task 2 (amended by Plan 06 Task 2, gap closure): the
    # suggest-contacts/SKILL.md's one documented python block -- the round's real join,
    # eligibility feeding discovery_plan, the discovered people feeding select_people
    # with load_families' own family list, the survivors' cap resolved through
    # agreed_cap() before feeding synthesise_rows, a simulated stage-2 merge, then
    # partition_for_dispatch splitting sendable from held before extraction.validate()
    # runs once per sendable row.
    (
        "suggest-contacts",
        (
            "suggest_contacts.eligibility", "suggest_contacts.discovery_plan",
            "role_classify.load_families", "suggest_contacts.select_people",
            "suggest_contacts.agreed_cap", "suggest_contacts.synthesise_rows",
            "suggest_contacts.partition_for_dispatch",
            "extraction.validate", "suggest_contacts.round_artifact",
        ),
    ): "test_suggest_contacts_composition.py::test_the_documented_round_pipeline_drives_its_real_joins_end_to_end",
}

NOT_A_PIPELINE = {
    (
        "review-triage",
        ("review_queue.policy_class", "review_queue.record_link"),
    ): "two independent read-only lookups bound into lambdas for render_queue's two "
       "callback slots; no result flows from one into the other",
}

# Shrink-only. Each entry names the specific undriven join, not merely "no test
# found" -- honesty rule (PLAN.md Design section). Writing the covering test for any
# one of these is its own follow-on task, and doing so shrinks MAX_GRANDFATHERED by 1.
#
# All five originally-grandfathered entries are closed as of 260829-lg3 -- this dict is
# now the empty literal, the correct end state per the ratchet's own "shrinks by one
# each time" rule (not a headroom-preserving non-zero count).
GRANDFATHERED_UNCOVERED = {}

MAX_GRANDFATHERED = 0


# =====================================================================================
# Pure-helper unit tests -- synthetic SKILL.md text, no filesystem, no real corpus.
# =====================================================================================

def test_a_block_with_two_scripts_module_calls_yields_one_identity_in_source_order():
    text = (
        "1. Do the thing:\n\n"
        "   ```python\n"
        "   cfg = config_gate.load_config()\n"
        "   result = dispatch.dispatch(path, True, cfg)\n"
        "   ```\n"
    )
    identities = sequences_in("fake-skill", text, {"config_gate", "dispatch"})
    assert identities == [
        (("fake-skill", ("config_gate.load_config", "dispatch.dispatch")), 3),
    ]


def test_a_block_with_only_one_scripts_module_call_yields_no_identity():
    text = (
        "   ```python\n"
        "   cfg = config.get(\"key\")\n"
        "   result = dispatch.dispatch(path, True, cfg)\n"
        "   responses.extend(result)\n"
        "   ```\n"
    )
    identities = sequences_in("fake-skill", text, {"dispatch"})
    assert identities == [], (
        "config.get and responses.extend must not pollute the identity -- only one "
        "call (dispatch.dispatch) is against a real scripts module"
    )


def test_a_block_that_will_not_parse_even_after_substitution_raises_naming_skill_and_line():
    text = (
        "   ```python\n"
        "   mod_a.first(\n"
        "   mod_b.second(<placeholder>\n"
        "   ```\n"
    )
    with pytest.raises(UnparseableBlockError) as excinfo:
        sequences_in("broken-skill", text, {"mod_a", "mod_b"})
    message = str(excinfo.value)
    assert "broken-skill" in message
    assert "line 1" in message, "the fence's own line, not the failing statement's"


def test_placeholder_substitution_lets_a_block_with_prose_placeholders_parse():
    text = (
        "   ```python\n"
        "   providers = enrichment.resolve_providers(<override or None>, cfg)\n"
        "   outcome = chunking.dispatch_plan(plan, providers, <this send's ids>, cfg)\n"
        "   ```\n"
    )
    identities = sequences_in("fake-skill", text, {"enrichment", "chunking"})
    assert identities == [
        (("fake-skill", ("enrichment.resolve_providers", "chunking.dispatch_plan")), 1),
    ]


def test_the_guard_bites_permanently_on_a_synthetic_unregistered_sequence():
    """The permanent proof this guard fires -- a synthetic SKILL.md block with an
    unregistered two-call sequence, run through the pure helpers with no real
    registries, no real corpus, no filesystem. This is what makes the guard a ratchet
    rather than a one-time census: it keeps biting on any future addition, forever.
    """
    text = (
        "9. **Fake step.**\n\n"
        "   ```python\n"
        "   spec = preingest.build_rows_spec(rows)\n"
        "   extraction.write_dispatch_csv(spec[\"rows\"], out_path)\n"
        "   ```\n"
    )
    modules = {"preingest", "extraction"}
    [(identity, line_number)] = sequences_in("fake-skill", text, modules)
    skill_name, call_tuple = identity
    fake_covered, fake_not_a_pipeline, fake_grandfathered = {}, {}, {}

    assert identity not in fake_covered
    assert identity not in fake_not_a_pipeline
    assert identity not in fake_grandfathered

    message = format_violation(skill_name, line_number, call_tuple)
    assert "fake-skill" in message
    assert "line 3" in message
    assert "preingest.build_rows_spec" in message and "extraction.write_dispatch_csv" in message
    assert "write a composition test" in message and "COVERED" in message
    assert "NOT_A_PIPELINE" in message, "both remedies must be named"


# =====================================================================================
# The live corpus. `extracted_identities()` propagates UnparseableBlockError
# uncaught -- a block that stops parsing fails THIS suite, naming the skill and line,
# rather than being silently skipped.
# =====================================================================================

def test_no_new_or_orphaned_sequence_exists_in_the_live_corpus():
    """The ratchet itself: every sequence documented today must be claimed by exactly
    one of the three registries, and every registry entry must still point at a real,
    live sequence. This single set-equality assertion IS the census pin -- the
    registries above hold the identities; there is no second hard-coded count to
    drift out of sync with them.
    """
    live = set(extracted_identities())
    registered = set(COVERED) | set(NOT_A_PIPELINE) | set(GRANDFATHERED_UNCOVERED)
    missing = live - registered
    orphaned = registered - live
    assert not missing, (
        f"new, unregistered SKILL.md sequence(s): "
        f"{[format_violation(s, extracted_identities()[(s, c)], c) for s, c in missing]}"
    )
    assert not orphaned, (
        f"registry entries no longer matching any live SKILL.md sequence "
        f"(update or remove them): {sorted(orphaned)}"
    )


def test_registries_have_no_orphaned_keys():
    live = set(extracted_identities())
    for name, registry in (
        ("COVERED", COVERED), ("NOT_A_PIPELINE", NOT_A_PIPELINE),
        ("GRANDFATHERED_UNCOVERED", GRANDFATHERED_UNCOVERED),
    ):
        orphans = set(registry) - live
        assert not orphans, f"{name} has entries matching no live sequence: {orphans}"


def test_the_three_registries_are_pairwise_disjoint():
    covered, not_a_pipeline, grandfathered = set(COVERED), set(NOT_A_PIPELINE), set(GRANDFATHERED_UNCOVERED)
    assert not (covered & not_a_pipeline), covered & not_a_pipeline
    assert not (covered & grandfathered), covered & grandfathered
    assert not (not_a_pipeline & grandfathered), not_a_pipeline & grandfathered


def test_grandfathered_count_is_within_its_shrink_only_ceiling():
    assert len(GRANDFATHERED_UNCOVERED) <= MAX_GRANDFATHERED


def test_every_not_a_pipeline_and_grandfathered_entry_carries_a_non_empty_reason():
    for registry_name, registry in (
        ("NOT_A_PIPELINE", NOT_A_PIPELINE), ("GRANDFATHERED_UNCOVERED", GRANDFATHERED_UNCOVERED),
    ):
        for identity, reason in registry.items():
            assert isinstance(reason, str) and reason.strip(), (
                f"{registry_name}[{identity}] has no non-empty reason"
            )


def _test_function_source(nodeid):
    file_part, _, func_name = nodeid.partition("::")
    path = PLUGIN_ROOT / "tests" / file_part
    assert path.exists(), f"{nodeid}: {path} does not exist"
    text = path.read_text()
    marker = f"def {func_name}("
    assert marker in text, f"{nodeid}: no such test function in {file_part}"
    start = text.index(marker)
    rest = text[start:]
    next_def = re.search(r"\ndef ", rest[1:])
    return rest if next_def is None else rest[: next_def.start() + 1]


def test_every_covered_nodeid_resolves_to_a_real_test_mentioning_the_sequences_sink():
    """A staleness guard, not proof of coverage (design note): catches a typo'd
    nodeid and a covering test refactored out from under its own name. Deliberately
    checks only the SINK (last) call's bare function name, not every name in the
    tuple -- a realistic covering test uses a fixture in place of config_gate.
    load_config, and demanding every name would force a dishonest weakening later.
    """
    for identity, nodeid in COVERED.items():
        _skill_name, call_tuple = identity
        sink_function = call_tuple[-1].rsplit(".", 1)[-1]
        source = _test_function_source(nodeid)
        assert sink_function in source, (
            f"{nodeid} does not mention {sink_function!r} (the sink of {identity}) "
            f"in its own source -- either the nodeid is stale or the covering test "
            f"was refactored out from under it"
        )
