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
    # Phase 65 Plan 02 (RICH-04): the tuple gained `preingest.strip_enrichment_extras`,
    # inserted right before `extraction.strip_row_id` -- the new dispatch-boundary strip
    # that drops the field-policy-widened keys `merge_enriched`'s allowlist now admits.
    # The sink is still `extraction.write_dispatch_csv`, so the covering nodeid is
    # unchanged; that test now drives a response carrying a widened key (`seniority`)
    # through the whole sequence, proving the new call is DRIVEN, not merely registered.
    (
        "enrich-before-ingest",
        (
            # Phase 70 Plan 06 (D-70-11): `partition_for_ingest` replaces
            # `extraction.hold_emailless` at the head of this lane — ONE verdict,
            # `confidence.assess` first and the email second, shared with the preview
            # the operator granted the write on.
            "preingest.partition_for_ingest", "preingest.strip_enrichment_extras",
            "extraction.strip_row_id", "extraction.write_dispatch_csv",
        ),
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
    # Phase 67 Plan 03 (AUTO-06, D-67-06, D-67-11), following the 57-05 precedent
    # directly above (`enrich-before-ingest`'s tuple gained the same kind of
    # `run_report.record_audit` pair for the same reason): the tuple gains
    # `run_state.new_run_id` (the run handle, minted before the ceiling branch) and
    # two `run_report.record_audit` calls (one at the moment the ceiling verdict and
    # grant balances are observed, one in the `finally` alongside the second
    # `record_dispatch_outcome`). The sink is still `write_grant.record_dispatch_outcome`
    # (the second, closing call), so the covering nodeid is unchanged.
    (
        "contact-upload",
        (
            "config_gate.load_config", "write_grant.authorize_send",
            "write_grant.authorize_ungranted_send", "run_state.new_run_id",
            "run_report.record_audit", "tabular.read_table",
            "remainder_queue.save", "remainder_queue.build_entry",
            "write_grant.record_dispatch_outcome",
            "n8n_arming.armed_window", "dispatch.dispatch",
            "chunking.single_dispatch_outcome", "write_grant.record_dispatch_outcome",
            "run_report.record_audit",
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
            # Phase 70 Plan 06 (D-70-05/D-70-08a): `enrich-records` sends and reads its
            # rows back in one call now — `dispatch_and_recover` is `dispatch_plan` plus
            # the runData read, correlated on this run's own `run_id`, run INSIDE the
            # armed window.
            "chunking.dispatch_and_recover", "write_grant.record_dispatch_outcome",
            "run_report.record_audit",
        ),
    ): "test_write_grant.py::test_record_dispatch_outcome_closes_the_grant_from_a_real_dispatch_ceiling_stop",
    # Quick task 260911-ss4 (F1): step 2's fence now saves the classification it just
    # produced, under `match_run_id` -- the batch's own D-70-05 correlation handle --
    # so a later fence in a FRESH process reads it back instead of re-sending the
    # batch. The sink moves from `classify_matches` to `match_state.save`, so the
    # covering nodeid repoints to the Task 1 composition test that actually drives a
    # save (never `test_chunking.py`'s existing match-lane test, which has no
    # business touching this new store).
    #
    # Phase 71 Plan 02 (D-71-01..03): the tuple gains `preingest.
    # confirmed_company_domains`, added right after `match_state.save` -- the
    # zero-new-lookup seed for step 6's held-row render. The covering test is
    # extended (not replaced) to also call it over the round-tripped classification.
    (
        "enrich-before-ingest",
        (
            "config_gate.load_config", "chunking.plan_chunks", "chunking.chunk_ceiling",
            "preingest.match_batch", "preingest.classify_matches", "match_state.save",
            "preingest.confirmed_company_domains",
        ),
    ): "test_match_state.py::test_the_recorded_batch_round_trips_through_save_load_apply_and_save_again",
    # Quick task 260911-ss4 (F1): step 3's own fence, new -- load the classification
    # step 2 saved, apply the operator's confirm/deny/pick decisions, save the result
    # back under the same `match_run_id`. Same covering test as the entry above; the
    # checker requires only that the test mention the sink (`match_state.save`), and
    # that test drives it for real, twice, across this exact sequence.
    #
    # Phase 71 Plan 02 (D-71-01..03): re-derives `confirmed_domains` after
    # `apply_match_decisions`, so a step-3 confirmation counts too -- same
    # `preingest.confirmed_company_domains` addition as the entry above.
    (
        "enrich-before-ingest",
        (
            "match_state.load", "preingest.apply_match_decisions", "match_state.save",
            "preingest.confirmed_company_domains",
        ),
    ): "test_match_state.py::test_the_recorded_batch_round_trips_through_save_load_apply_and_save_again",
    # Quick task 260911-ss4 (F1): the linkedin fence used to rebuild the WHOLE match
    # from `rows_from_table` through `classify_matches` purely to reach one unmatched
    # row -- exactly the re-match this quick task removes. It now loads the
    # classification step 2 already persisted. The sink is still `extraction.validate`,
    # so the covering nodeid is unchanged; that test now drives the sequence by saving
    # a classification with a linkedin-only unmatched row, loading it through
    # `match_state.load`, and carrying that row into `extraction.validate`.
    (
        "enrich-before-ingest",
        ("match_state.load", "extraction.validate"),
    ): "test_linkedin_row_composition.py::test_a_lusha_hit_for_the_unmatched_row_is_proposed_through_resolutions_and_revalidated",
    # F2 (uat-batch-review-row-reads-failed, gap-closure 2026-09-09): step 1's new
    # housekeeping fence -- prune stale durable state at the start of a round, never
    # mid-run. Driven end to end over a real config file on disk, proving the
    # operator's own `dashboard_artifact_ttl_days` override reaches the pruner
    # through `config_gate.load_config`'s real file-reading/validation path.
    # `prune_durable_state` lives in run_report.py, not durable_paths.py --
    # test_sweep_read_only.py's static write-verb confinement over the unattended
    # sweep's reachable module closure (durable_paths.py IS in that closure;
    # run_report.py is not).
    (
        "enrich-before-ingest",
        ("config_gate.load_config", "run_report.prune_durable_state"),
    ): "test_run_report.py::test_config_load_composed_with_prune_durable_state_respects_the_operators_configured_ttl",
    # Phase 71 Plan 02 (D-71-01..03): the tuple gains `enrichment._clean_domain`,
    # inserted between `confidence.assess` and `held_queue.build_entry` -- the
    # company_known stamp's own domain-cleaning call. Read from this test's own
    # failure output, not guessed. The covering test is extended to actually stamp
    # a held entry and assert it, not merely re-pinned.
    (
        "enrich-before-ingest",
        (
            "held_queue.load", "run_manifest.load", "preingest.parse_outcome",
            "confidence.assess", "enrichment._clean_domain",
            "held_queue.build_entry", "held_queue.stable_key",
            "held_queue.save",
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
    # Phase 62 Plan 05 Task 2 (amended by Plan 06 Task 2, then by Plan 08 -- gap
    # closure, G-62-4): the suggest-contacts/SKILL.md block was rewritten to fix a
    # blocker -- following the documented sequence, stage 2 could not dispatch at all,
    # because nothing ever minted `row_id`. The block now resolves the role vocabulary
    # and the per-company cap ONCE before the per-company loop (round-level,
    # D-62-12/SUGGEST-02), accumulates every eligible company's synthesised records,
    # then -- once, over the whole batch -- calls `suggest_contacts.mint_row_ids`
    # (which calls `preingest.build_rows_spec` under the hood) and builds the chunk
    # plan through `chunking.plan_chunks`/`chunking.chunk_ceiling`. After stage 2's
    # dispatch (handed `plan` by reference; `enrich-before-ingest/SKILL.md` step 5's own
    # dispatch block, not re-documented here), `suggest_contacts.rejoin_enriched` gives
    # each record its own merged row back -- `preingest.merge_enriched` returns FRESH
    # rows and never mutates its input, so without this join every enriched row would
    # be reported as held -- before `partition_for_dispatch` splits sendable from held
    # and `extraction.validate()` runs once per sendable row.
    #
    # The sink is still `suggest_contacts.round_artifact`, unchanged, so the covering
    # nodeid is unchanged too; the new mint/rejoin/chunking calls this tuple gained are
    # driven end to end, through a real `chunking.dispatch_plan` with a stub transport
    # and a real `preingest.merge_enriched`, by
    # `test_suggest_contacts_composition.py::test_the_documented_round_reaches_an_accepted_chunk_and_an_enriched_sendable_row`
    # (62-08-PLAN.md Task 1), which reaches `ChunkResult(ok=True)` -- the property
    # G-62-4 is about.
    # Quick task 260904-5sd: the tuple gained THREE `search_fallback` calls, all inside
    # the one existing block (a second python block would mint a second sequence
    # identity, which this registry deliberately makes expensive). Two sit in the
    # per-company loop right after `discovery_plan` -- `eligible_after_ladder` decides
    # whether a ladder that found nobody may be escalated at all (a refusal anywhere
    # closes it; D-5sd-04/D-5sd-06), and `rank_results` decides which of the search's
    # URLs may be fetched at all (D-5sd-02). The third, `hold_weak_sources`, is a
    # SECOND records-level pass right after `partition_for_dispatch`: it holds a
    # tier-3-sourced person however confidently the waterfall validated them
    # (D-5sd-05), and it leaves `partition_for_dispatch` itself untouched, since an
    # optional keyword there would be a one-keyword bypass of the operator's ruling.
    #
    # The sink is still `suggest_contacts.round_artifact`, so the covering nodeid is
    # unchanged; that test now drives three companies -- a refused ladder that never
    # reaches the search path, a tier-2 person who becomes sendable only after the
    # merge fills a related-domain email, and a tier-3 person held despite the same
    # successful merge -- so the new joins are proven at the composition level, not
    # merely renamed here.
    #
    # Phase 64 Task 3: the tuple gained `walk_bar` (the round-level bar, resolved
    # once alongside `agreed_cap`) and two `next_candidates` calls bracketing one
    # `walk_pages` call -- the per-company page walk that replaced "stop at the
    # first page that yields anyone" (D-64-01 .. D-64-07). The sink is still
    # `suggest_contacts.round_artifact`, so the covering nodeid is unchanged; that
    # test now also drives `walk_bar`/`next_candidates`/`walk_pages` for real, over
    # the same three companies, asserting the walk's own terminal ending
    # (`cap_exhausted`/`ladder_exhausted`) independently of `eligible_after_ladder`'s
    # separate, attempts-keyed eligibility question.
    #
    # Phase 64 code review CR-01/CR-02 fix: the tuple gained a SECOND `walk_pages`
    # call. CR-01 -- the documented loop re-derived `candidates` from the FULL,
    # unfiltered `sitemap_urls` after every fetch, which made `filter_candidates`
    # (always a PREFIX of the URLs it is handed) return a shrinking prefix of the
    # SAME front URLs rather than what remained unfetched, so the walk read the
    # ladder as exhausted 2-3 fetches early. The re-derivation now happens BEFORE
    # each `walk_pages` call (not after), narrowed to `sitemap_urls` minus what
    # `pages` has already walked. CR-02 -- the pasted URL's own fetch was never
    # folded into `pages` at all, silently dropping it from the union `walk_pages`
    # is documented to produce ("EVERY page fetched... INCLUDING the pasted URL");
    # it is now fetched first and walked before any ladder candidate, which is the
    # second `walk_pages` call. The sink is still `suggest_contacts.round_artifact`,
    # so the covering nodeid is unchanged.
    #
    # Phase 65 Task 1: the tuple gained its FIRST `suggest_contacts.round_outcome`
    # call, right after the second `walk_pages` and before `eligible_after_ladder` --
    # the routing call that replaces the inline `if not people:` cause reasoning
    # (D-65-01). It decides `reentry` from what the walk already has; the caller
    # still asks `eligible_after_ladder` for itself, unmodified (D-65-10).
    #
    # Phase 65 Task 2: the tuple gained its SECOND `suggest_contacts.round_outcome`
    # call, right after `hold_weak_sources` and before `extraction.validate` -- the
    # terminal, per-company classify that stamps each round's own `cause`/`breakdown`
    # onto the `rounds` structure step 9 reads. A terminal call (carrying
    # `rows`/`sendable`/`held`/`fallback`) always returns `reentry: "none"`
    # (D-65-08/D-65-12), so this second call site can never route a third time. The
    # sink is still `suggest_contacts.round_artifact`, so the covering nodeid is
    # unchanged.
    (
        "suggest-contacts",
        (
            "suggest_contacts.eligibility", "role_classify.load_families",
            "suggest_contacts.agreed_cap", "suggest_contacts.walk_bar",
            "suggest_contacts.discovery_plan", "suggest_contacts.next_candidates",
            "suggest_contacts.walk_pages", "suggest_contacts.next_candidates",
            "suggest_contacts.walk_pages",
            "suggest_contacts.round_outcome",
            "search_fallback.eligible_after_ladder", "search_fallback.rank_results",
            "suggest_contacts.select_people", "suggest_contacts.synthesise_rows",
            "suggest_contacts.mint_row_ids", "chunking.plan_chunks",
            "chunking.chunk_ceiling", "suggest_contacts.rejoin_enriched",
            "suggest_contacts.partition_for_dispatch",
            "search_fallback.hold_weak_sources",
            "suggest_contacts.round_outcome",
            "extraction.validate", "suggest_contacts.round_artifact",
        ),
    ): "test_suggest_contacts_composition.py::test_the_documented_round_pipeline_drives_its_real_joins_end_to_end",
    # Phase 69 Plan 02 Task 1 (HELD-01, D-69-02): a NEW, SEPARATE fence -- step 8's
    # held routing, added immediately after the tuple above's own fence, never
    # inside it, so the pipeline tuple's own identity (above) is unchanged. The
    # partition's held rows no longer route into `held_queue` (a suggestion-round
    # decline answers "identified fine, declined to send", a different question
    # from `held_queue`'s match-gate vocabulary) -- they route into
    # `suggestion_declines`, a sibling durable store (plan 01). The sink is
    # `suggestion_declines.partition_by_run`, the structure step 9 renders.
    (
        "suggest-contacts",
        (
            "suggestion_declines.load", "suggest_contacts.company_id_for_index",
            "suggestion_declines.entry_key", "suggestion_declines.build_entry",
            "suggestion_declines.first_refusal", "suggestion_declines.save",
            "suggestion_declines.partition_by_run",
        ),
    ): "test_suggest_contacts_composition.py::test_the_documented_step_8_held_routing_persists_a_declined_person",
    # Phase 69 Plan 02 Task 2 (HELD-01, D-69-05): a second NEW fence -- step 9's
    # empty-records path. A round with no `run_id` (every company found nobody)
    # still reads the deferred backlog straight from the store, with no run to
    # compare against, rather than hiding it behind a round that dispatched
    # nothing. Two calls, one result flowing into the next -- a real sequence, not
    # a contrived split.
    (
        "suggest-contacts",
        ("suggestion_declines.load", "suggestion_declines.partition_by_run"),
    ): "test_suggest_contacts_composition.py::test_the_documented_empty_records_path_still_reads_the_backlog",
    # Phase 69 Plan 03 Task 1: the standalone drain's own step 1 fence -- a SEPARATE
    # skill (`suggestion-declines`), so this is a distinct identity from the tuple
    # immediately above even though the call sequence reads identically. No round is
    # in progress here at all, so `partition_by_run` is always called with `run_id=None`.
    (
        "suggestion-declines",
        ("suggestion_declines.load", "suggestion_declines.partition_by_run"),
    ): "test_suggestion_declines_skill.py::test_the_documented_drain_spine_deletes_one_entry_and_leaves_the_rest",
    # Phase 69 Plan 03 Task 1: the drain's own step 7 apply-and-save fence -- one
    # `apply_action` call per operator pick, folded into `entries`, then one `save`.
    (
        "suggestion-declines",
        ("suggestion_declines.apply_action", "suggestion_declines.save"),
    ): "test_suggestion_declines_skill.py::test_the_documented_drain_spine_deletes_one_entry_and_leaves_the_rest",
    # Phase 69 Plan 03 Task 3: the drain's own send fence (step 4(a)) -- builds one
    # record per chosen entry and validates the batch here, because nothing
    # downstream will (enrich-before-ingest step 5 is grant/autonomy/pause only, and
    # its step 7 starts from rows its own step 2 already validated). `send_ids`/
    # `send_domains`/`allow_create` bind by name in the SAME fence, per the plan's
    # own instruction, but neither is a scripts-module call, so the extracted
    # identity is just the two-call validate/round_artifact pair.
    #
    # Code review fix CR-02 (69-REVIEW-FIX): gained `extraction.hold_emailless`,
    # called BEFORE `send_domains` is computed -- a still-emailless `no_email` entry
    # is held there rather than crashing on `record["row"]["email"]`. Same fence,
    # same covering test (now extended to drive this exact three-call sequence);
    # the OLD two-call tuple below no longer appears in the live file and is
    # replaced, not kept alongside this one.
    (
        "suggestion-declines",
        (
            "extraction.validate", "suggest_contacts.round_artifact",
            "extraction.hold_emailless",
        ),
    ): "test_suggestion_declines_skill.py::test_a_drained_send_clears_the_same_gates_a_normal_send_clears",
    # Quick 260911-w6q (F2-3): step 2b's held-queue read/bucket fence -- open_entries's
    # output feeds the undecided comprehension (entry_verb per entry), whose output feeds
    # classify_facet per entry. One test drives the whole read-render-create-confirm-mark
    # flow for real, so all three review-triage identities below share its nodeid.
    #
    # Phase 71 Plan 02 (D-71-01..03): the tuple gains `held_queue.stamped_domains`,
    # inserted between `held_queue.entry_verb` and `held_queue.classify_facet` -- the
    # stamp-read that replaces the old hardcoded `known_company_domains = set()`. Read
    # from this test's own failure output, not guessed. The covering test now drives a
    # COLD START -- a stamped queue saved to a temp path and loaded fresh, with no
    # domain the test hands the fence directly.
    (
        "review-triage",
        (
            "held_queue.classify_read", "held_queue.load", "held_queue.open_entries",
            "held_queue.entry_verb", "held_queue.stamped_domains", "held_queue.classify_facet",
        ),
    ): "test_review_triage_facets.py::test_one_held_new_person_end_to_end_read_render_create_confirm_mark",
    # Quick 260911-w6q (F2-3): step 4a's CSV-build fence, ported from
    # `enrich-before-ingest/SKILL.md` step 7's own tail (minus the merge/partition head,
    # which does not apply to a held row already carrying its merged fields).
    (
        "review-triage",
        (
            "preingest.strip_enrichment_extras", "extraction.strip_row_id",
            "extraction.write_dispatch_csv",
        ),
    ): "test_review_triage_facets.py::test_one_held_new_person_end_to_end_read_render_create_confirm_mark",
    # Quick 260911-w6q (F2-3): step 4c's confirm fence -- one match_batch call for the
    # whole create batch, joined back to the held rows by email at classify_matches.
    (
        "review-triage",
        (
            "config_gate.load_config", "preingest.build_rows_spec", "chunking.plan_chunks",
            "chunking.chunk_ceiling", "preingest.match_batch", "preingest.classify_matches",
        ),
    ): "test_review_triage_facets.py::test_one_held_new_person_end_to_end_read_render_create_confirm_mark",
    # Quick 260911-w6r (F2-4): enrich-before-ingest/SKILL.md step 6's own read/bucket
    # fence -- the identical shape review-triage's step 2b already registers above,
    # but under THIS skill's own key (the registry is skill-scoped, not shared) and
    # driven by a NEW test in a new file (test_held_queue_facets.py's own tests
    # classify dict literals directly, never a loaded queue -- they do not drive this
    # join; test_review_triage_facets.py's covering test is a different skill's fence).
    # Phase 71 Plan 02 (D-71-01..03): the tuple gains `held_queue.stamped_domains`,
    # inserted between `held_queue.entry_verb` and `held_queue.classify_facet` -- the
    # stamp-read that replaces the old hardcoded `known_company_domains = set()`.
    # Read from this test's own failure output, not guessed. The covering test now
    # derives `known_company_domains` from a real saved-and-reloaded queue's own
    # stamp, never a domain the test hands the fence directly.
    (
        "enrich-before-ingest",
        (
            "held_queue.classify_read", "held_queue.load", "held_queue.open_entries",
            "held_queue.entry_verb", "held_queue.stamped_domains", "held_queue.classify_facet",
        ),
    ): "test_held_facet_render_composition.py::"
       "test_step_6_fence_loads_the_queue_and_facets_what_it_loaded_not_a_dict_literal",
    # Phase 71 Plan 02 (D-71-04): step 8's resume fence now wires `held_entries=` into
    # `watch.resume_or_disclose`, so `held_queue.load` joins it as a nested call in the
    # SAME fenced block -- a NEW two-call identity (the fence carried only one
    # scripts-module call before this wiring, below the >=2 registration threshold).
    (
        "enrich-before-ingest",
        ("watch.resume_or_disclose", "held_queue.load"),
    ): "test_run_manifest.py::"
       "test_resume_or_disclose_with_held_entries_wired_skips_a_settled_row_end_to_end",
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
