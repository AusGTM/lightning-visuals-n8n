"""The enrich-before-ingest skill's packaging and two-arm safety contract (37-CONTEXT.md
sec 6). Mirrors `test_enrich_skill_contract.py`'s structure and its `_normalized()`
idiom, deliberately kept a SEPARATE file rather than folded into that one -- same
reasoning that file states about not colliding with work in flight elsewhere.

The two pins that matter most here are NOT wording assertions: they are a
character-offset comparison (the enriched-preview heading must precede the ingest-ask
heading) and a same-numbered-step exclusion (the two consents must never share a step).

VOCAB-05 (2026-08-25) killed the two literal arming phrases those pins used to locate;
they locate the two per-send consent sentences now. What the pins defend is unchanged:
this flow asks twice, once per irreversible consequence, and never in one step.

WHAT THOSE TWO PINS DEFEND CHANGED ON 2026-08-25, and this file no longer claims
otherwise. Under D-53-05 -- taken by the operator, deliberately, for speed -- ONE write
grant may authorize both lanes of this flow, which means the HubSpot write can be
authorized before the enriched preview exists. The pins below therefore no longer stop
that collapse; they bind the UNGRANTED path (unchanged by D-53-04) and they carry the
record that the ordering protection was removed on purpose and by whom. The protections
that remain are asserted here too: the allowlist stays record-scoped to the named batch.

RECORDED EDIT -- D-59-07, operator, 2026-08-28. The paragraph above used to end by
saying that the disclosure the operator was given in exchange -- that the write is
authorized before the enriched preview exists -- was pinned so a later edit could not
quietly drop it. That sentence is now RETIRED as operator-facing text (53-04 called it
"the whole of what you got for the protection you traded", a warning nobody could act
on until after the fact anyway); this module no longer pins its presence. What is
pinned instead, in
`test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading`, is that
the retired sentence is GONE from SKILL.md, and that a plain, non-blocking statement
plus a pointer to the post-run written-records list took its place. The D-53-05 trade
itself -- one grant, both lanes, the record-scoped allowlist and the ordering all
unchanged -- is untouched by this edit; only what the operator reads about it changed.
Leaving the paragraph above unedited would be stale prose asserting a pin that no
longer exists, which is worse for a later reader than no note at all.
"""
import re
from pathlib import Path

import pytest
import yaml

import held_queue
import write_grant
from test_skill_sequence_coverage import extract_python_blocks, parse_calls, scripts_modules

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PLUGIN_ROOT / "skills" / "enrich-before-ingest" / "SKILL.md"

# RECORDED EDIT -- VOCAB-05, 2026-08-25, taken by the operator. These two names used to
# hold the literal arming phrases this skill demanded. The phrases are dead: an operator
# answering the question they were asked, in their own words, arms the send that question
# described. What the phrases protected -- consent that is unambiguous and ATTACHED to a
# shown consequence -- survives as the two per-send consent sentences below, which are what
# the pins now locate. The dead spellings are kept as a NEGATIVE pin so a later edit cannot
# quietly reintroduce them.
DEAD_ARMING_PHRASES = ('"arm the enrichment"', '"arm the upload"')
ENRICHMENT_CONSENT = "arms this run and nothing else"
INGEST_CONSENT = "arms this write and nothing else"

# Literal, unique substrings that locate each section's own heading -- not full
# sentences, so a later wording tweak elsewhere in the step doesn't break the find().
ENRICHED_PREVIEW_HEADING = "6. **The enriched preview"
INGEST_ARM_HEADING = '7. **Ask for the HubSpot write,'

# The exact heading text of contact-upload/SKILL.md's steps 6-10 (37-RESEARCH.md sec
# C.13), which this skill must reference rather than duplicate.
CONTACT_UPLOAD_HANDOFF_HEADINGS = (
    "Dispatch under an open grant, or otherwise only once the operator has said yes to "
    "this send.",
    "Report the outcome — per record, not a bare acceptance.",
    "Re-check, only when the operator asks.",
    "Retry a transport failure — same dispatch, same arming gate.",
    "Clean up.",
)

MATCH_GROUP_WORDS = ("auto-matched", "proposed", "unmatched", "unchecked")

# Plausible ways a paraphrase could smuggle a single, combined authorization back in --
# checked as a LIST, not one literal, so a paraphrase does not slip through.
_COMBINED_PHRASE_SPELLINGS = (
    "arm the enrichment and the upload",
    "arm the enrichment and upload",
    "arm the upload and the enrichment",
    "arm the upload and enrichment",
    "arm the enrichment/upload",
    "arm the upload/enrichment",
    "arm both",
    "arm the whole flow",
    "arm the whole batch",
    "arm everything",
    "arm the batch",
    "arm the enrichment and upload lanes",
)


def _text():
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalized(text):
    """Markdown wraps lines and prefixes blockquotes; neither changes what the operator
    reads. Compare on collapsed whitespace with the quote markers and bold markers
    removed, so a reflow cannot fail a wording assertion (and cannot hide one either)."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip()


def _numbered_step_spans(text):
    """Split the document into `(step_number, span_text)` pairs for every top-level
    numbered step (a line starting `N. **`). A span runs from its own heading up to
    the next top-level heading, or end of file for the last one."""
    matches = list(re.finditer(r"^(\d+)\. \*\*", text, flags=re.MULTILINE))
    assert matches, "expected at least one top-level numbered step in SKILL.md"
    spans = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((match.group(1), text[start:end]))
    return spans


def test_the_skill_exists_with_parseable_frontmatter_carrying_name_and_description():
    text = _text()
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert {"name", "description"} <= set(frontmatter)
    assert frontmatter["name"] == "enrich-before-ingest"


def test_the_description_fires_on_natural_operator_phrasing_and_names_the_slash_form():
    description = yaml.safe_load(_text().split("---", 2)[1])["description"].lower()
    assert "enrich" in description
    assert "hubspot" in description
    assert "/operator-claude-plugin:enrich-before-ingest" in description


def test_no_commands_directory_was_added_for_this_skill():
    """A plugin skill is already both auto-triggered and slash-invocable; a commands/
    directory would be a second entry point for identical behaviour (D-14b)."""
    assert not (PLUGIN_ROOT / "commands").exists()


def test_every_script_the_skill_names_exists_on_disk():
    referenced = set(re.findall(r"scripts/(\w+\.py)", _text()))
    assert referenced, "expected the skill body to reference at least one script"
    for script in referenced:
        assert (PLUGIN_ROOT / "scripts" / script).exists(), (
            f"SKILL.md references scripts/{script}, which does not exist on disk"
        )


def test_both_sends_are_asked_for_separately_and_neither_asks_with_a_phrase():
    """RECORDED EDIT -- VOCAB-05, 2026-08-25. Was `test_both_arming_phrases_appear`.

    The property was never that two PHRASES appear -- it is that this flow asks TWICE, on
    the ungranted path, for two different irreversible things: provider credit at step 5,
    a HubSpot write at step 7. That is asserted directly now. The phrases themselves are
    pinned absent, because an operator asked to produce the system's wording at the moment
    they are saying yes is the defect VOCAB-05 removed.
    """
    body = _normalized(_text())
    assert ENRICHMENT_CONSENT in body, "step 5 must ask for the waterfall run itself"
    assert INGEST_CONSENT in body, "step 7 must ask separately for the HubSpot write"
    for dead in DEAD_ARMING_PHRASES:
        assert dead not in body, (
            f"the dead arming phrase {dead} reappeared -- consent is bound to the send "
            "just described, never to a string the operator has to be taught"
        )


def test_no_combined_or_third_arming_phrase_appears():
    """RECORDED EDIT -- D-53-05, 2026-08-25, taken by the operator.

    This pin used to mean "a single combined authorization must not exist here", because
    such an authorization is necessarily given before the enriched preview exists. The
    operator was shown that cost in full and accepted it, for speed. A single combined
    authorization now DOES exist: the write grant, which may cover both lanes at once. What
    it costs, in plain prose: rows held for review, and merge conflicts where the source
    file's own value was kept over a differing provider value, are authorized UNSEEN --
    the enriched preview is the only place either becomes visible ahead of a write.

    What this pin holds now: the two per-send arming PHRASES are still never combined. That
    is the ungranted path, which D-53-04 leaves exactly as it was, and it is a real
    property -- with no grant open this flow still asks twice. The new truth is asserted
    alongside it rather than instead of it, so neither the removal nor the disclosure can
    be lost by a later sweep.
    """
    normalized = _normalized(_text()).lower()
    for spelling in _COMBINED_PHRASE_SPELLINGS:
        assert spelling not in normalized, (
            f"a combined arming PHRASE slipped into SKILL.md: {spelling!r} -- with no "
            "write grant open this flow still asks twice, once per consequence "
            "(D-53-04). A combined authorization is expressible only as a write grant, "
            "which is disclosed rather than phrased. (VOCAB-05, 2026-08-25: the per-send "
            "phrases died and the asks did not -- this list still guards the shape of a "
            "single combined arm, whatever words a paraphrase reaches for)"
        )
    assert "the enrichment lane and the contacts lane" in normalized, (
        "the skill must name which lanes one grant may cover (D-53-05) -- an operator "
        "left to infer that a single grant spans both lanes is exactly the surprise the "
        "old two-phrase design existed to prevent"
    )


def test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading():
    """RECORDED EDIT -- D-53-05, 2026-08-25, taken by the operator.

    This ordering USED TO BE the safety property (37-CONTEXT.md sec 6.3): the enriched
    preview had to land in the operator's turn before the ingest arm could be spoken, so
    the HubSpot write could not be approved before the operator saw what they were
    approving. That protection was REMOVED ON PURPOSE. One write grant may now cover both
    lanes, and when it does the write is authorized before the enriched preview exists --
    so held rows and merge conflicts (a source value kept over a differing provider value),
    which the enriched preview is the only place to see before a write, are authorized
    unseen. The operator was shown that in full and took it for speed.

    The offset comparison is kept because it is still true, and still load-bearing, on the
    UNGRANTED path: with no grant open this flow asks twice and the preview still lands
    between the asks. It is no longer evidence that the write cannot be authorized early.
    What replaced the protection is the DISCLOSURE, asserted below in the same function so
    a later edit cannot drop the sentence the operator was given in exchange.

    RECORDED EDIT -- D-59-07, operator, 2026-08-28. The DISCLOSURE named in the paragraph
    above -- "the write is authorized before the enriched preview exists" -- is itself now
    retired as operator-facing text: it was compensation nobody could act on until after
    the fact anyway (53-04's own words). It is replaced by a plain, non-blocking statement
    that the grant enables enrichment and writes to HubSpot, plus a pointer to the post-run
    written-records list (`written_records.json`) the operator can open in HubSpot and
    amend. The offset comparison above is UNCHANGED -- it still guards the ungranted path.
    What changed below is the final assertion: it now asserts the new statement is present
    AND that the retired sentence is gone, so the retired wording cannot come back
    unnoticed. The D-53-05 trade the paragraph above describes (one grant, both lanes) is
    itself untouched by this edit.

    RECORDED EDIT -- D-59-09, operator, 2026-08-29. `written_records.json` above named the
    single file every run used to share; each run now writes its own
    `written_records-<run_id>.json` file, and the final assertion below checks the glob
    pattern (`written_records*.json`) rather than that one retired name."""
    text = _text()
    preview_offset = text.find(ENRICHED_PREVIEW_HEADING)
    ingest_offset = text.find(INGEST_ARM_HEADING)

    assert preview_offset != -1, (
        f"could not find the enriched-preview heading {ENRICHED_PREVIEW_HEADING!r} in "
        "SKILL.md -- a find() returning -1 must fail loudly, not silently compare as "
        "'earlier' than the ingest-arm heading"
    )
    assert ingest_offset != -1, (
        f"could not find the ingest-arm heading {INGEST_ARM_HEADING!r} in SKILL.md -- "
        "a find() returning -1 must fail loudly, not silently compare as 'later' than "
        "the enriched-preview heading"
    )
    assert ingest_offset > preview_offset, (
        f"the ingest-arm heading (character offset {ingest_offset}) must appear "
        f"strictly after the enriched-preview heading (character offset "
        f"{preview_offset}) -- on the ungranted path the enriched preview must still "
        "land in the operator's turn before the ingest arm can be spoken"
    )
    normalized = _normalized(text).lower()
    assert "enables enrichment and writes to hubspot" in normalized, (
        "D-59-07 replaced the retired warning with a plain, non-blocking statement of "
        "fact, said at the yes: a grant covering both lanes enables enrichment and "
        "writes to HubSpot. Without that sentence the operator is told nothing at the "
        "moment that matters"
    )
    assert "written_records-<run_id>.json" in normalized, (
        "D-59-07's replacement for the retired warning points at the post-run "
        "written-records list -- without it the plain statement above is not actionable, "
        "which is exactly what made the retired warning worthless. D-59-09 (2026-08-29) "
        "moved the artifact from one shared file to one per run, so this pin now checks "
        "the per-run filename shape rather than the retired single fixed filename -- "
        "not the `written_records*.json` glob text, which `_normalized()` strips the "
        "asterisk from and would make an unreadable pin."
    )
    # NEGATIVE -- D-59-07, 2026-08-28: the retired D-53-05 warning must never come back,
    # softened or not. This is what makes the pin above a re-point rather than a
    # weakening.
    assert "authorized before the enriched preview exists" not in normalized, (
        "the retired D-53-05 warning reappeared -- D-59-07 retired it as operator-facing "
        "text, replaced by the plain statement and the written-records pointer asserted "
        "above"
    )


def test_no_single_numbered_step_solicits_both_consents():
    """RECORDED EDIT -- VOCAB-05, 2026-08-25. Was
    `test_the_two_arming_phrases_never_share_a_numbered_step`; the phrases are gone, the
    property is not. A step soliciting both consents would necessarily take the HubSpot
    write's yes before the enriched preview exists (37-CONTEXT.md sec 6.2) -- they guard
    two different irreversible things at two different moments."""
    for number, span in _numbered_step_spans(_text()):
        normalized_span = _normalized(span)
        assert not (ENRICHMENT_CONSENT in normalized_span
                    and INGEST_CONSENT in normalized_span), (
            f"numbered step {number} solicits both consents -- they must be given in "
            "different turns, never both taken by one step's own text"
        )


def test_the_skill_names_all_four_match_groups():
    body = _normalized(_text()).lower()
    for word in MATCH_GROUP_WORDS:
        assert word in body, f"expected the match-group word {word!r} in SKILL.md"


def test_the_skill_says_unchecked_means_the_lookup_could_not_run():
    body = _normalized(_text())
    assert "could not look" in body


def test_the_skill_states_nothing_has_reached_hubspot_at_the_enriched_preview_stage():
    body = _normalized(_text()).lower()
    assert "nothing here has reached hubspot yet" in body


def test_the_skill_references_contact_upload_steps_six_through_ten_by_heading_text():
    body = _normalized(_text())
    for heading in CONTACT_UPLOAD_HANDOFF_HEADINGS:
        assert _normalized(heading) in body, (
            f"expected contact-upload/SKILL.md's heading {heading!r} to be quoted by "
            "SKILL.md, not paraphrased or reproduced as new prose"
        )


def test_the_skill_does_not_reproduce_contact_upload_step_bodies():
    """The handoff is BY REFERENCE. None of contact-upload's own step mechanics --
    its dispatch code line, its report-ordering rules, its retry gate wording --
    should be re-typed here; only the heading text (asserted above) should appear."""
    body = _text()
    # contact-upload's step 7 spells out the report ordering in this exact phrase;
    # its presence here would mean the mechanics were copied, not referenced.
    assert "created / updated-matched / needs_review / rejected" not in body


def test_no_last_modified_field_is_implied_on_the_match_candidate_endpoint():
    assert "lastmodifieddate" not in _text().lower()


# ---------------------------------------------------------------------------------
# FINDING 2 (53-WALK-RECORD.md, .planning/debug/merge-enriched-drops-responses.md):
# step 5 used to hand chunking.dispatch_plan's per-chunk-list responses straight to
# merge_enriched, which silently filed every row as unanswered. The original fix was a
# manual flatten step, mirroring preingest.rerequest_unanswered's own normalization for
# this same endpoint. Gap-closure (2026-08-31) replaced step 5's dispatch+merge with an
# async submit + recovery (`watch.recover_async_dispatch`), whose own `responses` are
# already flat by construction — so the manual flatten is gone from THIS step (it still
# lives, unchanged, in `preingest.rerequest_unanswered`), and what these two tests pin
# is the negative (the broken raw-per-chunk call must never reappear) and the positive
# (the recovered, already-flat payload is what actually reaches merge_enriched).
# ---------------------------------------------------------------------------------

UNFLATTENED_MERGE_CALL = "preingest.merge_enriched(unmatched_rows, outcome.responses)"


def test_step_5_does_not_hand_dispatch_plans_raw_responses_straight_to_merge_enriched():
    body = _text()
    assert UNFLATTENED_MERGE_CALL not in body, (
        "outcome.responses is one raw body PER CHUNK, not one item per row -- passing "
        "it straight to merge_enriched reproduces FINDING 2 (every row silently filed "
        "as unanswered, no error)"
    )


RECOVERED_MERGE_CALL = 'preingest.merge_enriched(unmatched_rows, recovery["responses"])'


def test_step_5_merges_the_recovered_async_payload_not_dispatch_plans_raw_per_chunk_body():
    """Gap-closure (2026-08-31, operator decision "Option B"): step 5 now dispatches
    with `async_ack=True` and recovers the proposed values from the settled execution
    (`watch.recover_async_dispatch`) rather than reading `outcome.responses` off the
    wire — `recovery["responses"]` is already flat by construction (one settled
    execution's own `Build Response` output IS one chunk's rows, never one raw body per
    chunk), so the OLD manual per-chunk flatten loop this test used to pin no longer
    belongs in this step; it survives, unchanged, in `preingest.rerequest_unanswered`'s
    own re-request pass. What this test still pins: the call that reaches
    `merge_enriched` is the recovered payload, never `outcome.responses` unflattened
    (see the sibling test above, still pinned unchanged)."""
    body = _text()
    assert "watch.recover_async_dispatch" in body, (
        "step 5 must recover the proposed values from the settled execution, not "
        "assume they arrived on the wire"
    )
    assert RECOVERED_MERGE_CALL in body


# ---------------------------------------------------------------------------------
# 37-CONTEXT.md sec 13's confirmation-format amendment (2026-08-05, at this skill's
# own read-through): one-proposal-per-turn is superseded by a batched numbered table.
# These pins are ADDITIVE -- every pin above this point stays exactly as it was.
# ---------------------------------------------------------------------------------

CONFIRMATION_VERBS = (
    "`<label>. approve`",
    "`<label>. deny`",
    "`<label>. pick <sub-label>`",
    "`<label>. email: <address>`",
)


def test_the_confirmation_vocabulary_is_pinned_to_exactly_four_verbs():
    body = _normalized(_text())
    for verb in CONFIRMATION_VERBS:
        assert verb in body, f"expected the constrained verb {verb!r} in SKILL.md"


def test_deny_all_is_offered():
    assert "`deny all`" in _normalized(_text())


def test_bare_approve_all_never_appears_without_a_trailing_count_or_scope():
    """The literal phrase 'approve all' may appear ONLY immediately followed by a
    count/scope form (e.g. 'approve all 6') -- a bare 'approve all' with no scope is
    exactly the mistake the amendment forbids: guessing what "all" means and
    approving the wrong candidate against it silently evaporates the true row (the
    original nine-directors bug, one row at a time)."""
    body = _normalized(_text())
    matches = list(re.finditer(r"approve all", body, re.IGNORECASE))
    assert matches, "expected at least one 'approve all' (scoped) example in SKILL.md"
    for match in matches:
        tail = body[match.end():match.end() + 6]
        assert re.match(r"\s*\d", tail), (
            f"found a bare 'approve all' with no trailing count/scope at character "
            f"offset {match.start()}: {body[max(0, match.start() - 20):match.end() + 20]!r}"
        )


def test_a_pending_row_is_restated_never_defaulted():
    body = _normalized(_text()).lower()
    assert "pending" in body
    assert "restated" in body
    assert "never defaulted" in body


def test_ambiguous_rows_are_restricted_to_pick():
    body = _normalized(_text()).lower()
    assert "takes only" in body


def test_one_bad_line_refuses_the_whole_table_naming_the_offending_line():
    body = _normalized(_text()).lower()
    assert "refuses the whole table" in body
    assert "names the offending line" in body


def test_the_skill_states_the_grant_never_outlives_its_turn_and_arms_no_other_lane():
    body = _normalized(_text()).lower()
    assert "never outlives" in body or "never written to disk" in body
    assert "arming one lane does not arm any other lane" in body


# ---------------------------------------------------------------------------------
# D-53-05 / D-53-04 (2026-08-25): one write grant may cover both lanes, and while it
# is open neither per-send arming phrase is asked for. These pins are ADDITIVE -- the
# only rewrite in this file is the recorded edit to the two pins above.
# ---------------------------------------------------------------------------------


def test_the_skill_says_the_grant_branch_does_not_ask_again():
    """RECORDED EDIT -- VOCAB-05, 2026-08-25. Was
    `test_the_skill_says_the_grant_branch_does_not_ask_for_the_phrase_again`. The phrase is
    dead; the ask it used to spell is not, and a grant still removes it."""
    body = _normalized(_text()).lower()
    assert "do not ask at all" in body and "do not ask again" in body
    assert "with no grant open" in body, (
        "D-53-04: the grant is an ADDITION. The skill must say that with no grant open "
        "today's two-ask behaviour is unchanged, or an operator reads the grant as having "
        "replaced the careful path rather than added to it"
    )


def test_the_skill_says_what_a_grant_does_not_remove():
    body = _normalized(_text()).lower()
    assert "a grant removes the question, not the safety" in body
    assert "bounded to that send's records" in body
    assert "reported loudly" in body


def test_the_skill_says_revocation_bites_at_the_next_send_not_mid_dispatch():
    """GRANT-05 as re-scoped: a revoke refuses the NEXT send. At the 2-record chunk
    ceiling a 40-record send is 20 chunks and all of them run after a revoke, because
    `dispatch_plan` loops its chunks with no grant-aware hook. A skill that said
    "revoking stops the run" would be describing something that does not exist."""
    body = _normalized(_text()).lower()
    assert "refuses the next send" in body
    assert "does not stop a dispatch already running" in body


def test_the_skill_distinguishes_the_grant_that_spans_lanes_from_the_arm_that_does_not():
    """The pin above (`arming one lane does not arm any other lane`) stays TRUE under
    D-53-05 and stays in the file -- but a reader who sees a grant spanning two lanes
    will draw the wrong conclusion from it unless the skill writes the distinction down.
    D-53-05 collapsed the asks at the level of the GRANT (the authorization); each ARM
    still opens its own window over one lane and only that send's records, which is what
    53-01's scope check inside `arm_for_dispatch` enforces. Pinning the prose is the same
    fix 53-01 Task 3 applied to the parity pin: a literal that survives while its claim
    has quietly changed meaning is worse than no pin."""
    body = _normalized(_text()).lower()
    assert "each individual arm still opens its own window over one lane" in body
    assert "only that send's records" in body


def test_the_skill_never_widens_a_window_to_the_grants_whole_record_set():
    """T-53-18b. The collapse widened WHEN the approval is given, never WHAT it covers.
    A skill that handed the grant's full record list to `armed_window` would widen every
    window to the whole batch while every test in the suite still passed."""
    body = _normalized(_text()).lower()
    assert "never the grant's whole record set" in body


def test_the_skill_asks_nothing_at_the_waterfall_step_under_a_grant():
    """D-53-06 (operator, 2026-08-25), found by the Phase 53 operator walk.

    Step 5's arming phrase was made grant-conditional by 53-04; the ask around it was not.
    Under a grant the operator already approved this send when they opened it — and for a
    two-lane grant they were told AT THAT MOMENT that the HubSpot write was being
    authorized before this preview existed (D-53-05). Re-asking here would restore the
    stop-and-ask while giving back none of the protection that was traded for it.
    """
    body = _normalized(_text()).lower()
    assert "if a write grant covering this lane and these rows is open, ask for nothing here" in body
    assert "d-53-06" in body


# ---------------------------------------------------------------------------------
# F11 (`.planning/UAT-autonomous-batch-2026-09-09.md`, quick task 260911-ss6): the
# skill's own sentence at step 9 already claims a grant "ends on completion, revocation,
# session end, error or a ceiling breach" -- step 7 (formerly 5/7) supplies the
# revocation/error/ceiling-breach closes, but nothing ever closed on ordinary completion,
# and nothing closes at session end either. These four pin the fix: a step-10 close
# reached on every exit, positioned after the end-of-run report, guarded so it never
# re-closes a grant another path already closed.
# ---------------------------------------------------------------------------------


def test_the_skill_closes_the_grant_after_the_end_of_run_report():
    text = _text()
    assert "write_grant.close_grant(" in text, (
        "the healthy-completion close has no call site at all -- F11's own gap"
    )
    assert text.index("write_grant.close_grant(") > text.rindex("build_run_report("), (
        "the operator reads the end-of-run report first; the grant's close comes after it"
    )


def test_the_skill_names_batch_complete_and_session_end_as_its_two_closes():
    text = _text()
    assert "write_grant.CLOSED_BATCH_COMPLETE" in text
    assert "write_grant.CLOSED_SESSION_END" in text


def test_the_skill_never_re_closes_a_grant_another_path_already_closed():
    text = _text()
    assert 'grant.get("state") == write_grant.OPEN' in text, (
        "close_grant does not inspect state -- the fence must gate on OPEN itself, in "
        "exactly this shape, or a ceiling-breach/crash close can be silently overwritten"
    )
    body = _normalized(text).lower()
    assert "never closed a second time" in body


def test_every_close_reason_the_skill_names_is_a_real_close_reason():
    text = _text()
    names = sorted(set(re.findall(r"write_grant\.CLOSED_[A-Z_]+", text)))
    assert names, "expected at least one write_grant.CLOSED_* reference in the skill"
    for qualified in names:
        name = qualified.split(".", 1)[1]
        assert hasattr(write_grant, name), f"{name} does not exist on the write_grant module"
        value = getattr(write_grant, name)
        assert value in write_grant.CLOSE_REASONS, (
            f"write_grant.{name} = {value!r} is not a member of write_grant.CLOSE_REASONS"
        )


# ---------------------------------------------------------------------------------
# Phase 58 Plan 03 Task 3 (2026-08-26) — the domain confirm table (D-58-04/05/06/07),
# reached here via the mixed contact+company extraction handoff (58-01). ADDITIVE
# ONLY: no pin above this point is touched or reworded by this block.
# ---------------------------------------------------------------------------------


def test_the_skill_documents_the_domain_confirm_table_with_its_three_columns():
    body = _normalized(_text())
    assert "the company, the proposed website, and where that came from with a one-line" in body


def test_the_skill_says_the_shown_table_answer_covers_the_batch_or_leaves_it_unsent():
    body = _normalized(_text()).lower()
    assert (
        "an affirmative answering this shown table, in the same turn, covers the batch"
        in body
    )
    assert (
        "anything that is not clearly an answer to this table leaves the batch unsent"
        in body
    )


def test_the_skill_states_the_three_per_row_moves_and_the_decline_outcome():
    body = _normalized(_text())
    assert "accept as shown" in body
    assert "type the right website instead" in body
    assert "say this one is wrong" in body
    assert "looked up by its name instead" in body.lower()
    assert "never dropped" in body.lower()


def test_the_skill_states_the_profile_page_rule_at_the_confirm_step():
    body = _normalized(_text()).lower()
    assert "never recorded as their website" in body
    assert "every later company from that source is mistaken for" in body


def test_the_skill_refuses_the_batch_while_any_row_is_undecided():
    body = _normalized(_text())
    assert "company_domain.to_envelope_spec" in body


# ---------------------------------------------------------------------------------
# 59-09 gap closure (D-59-10, 2026-08-29) — a written-records bookkeeping failure
# never stops a dispatch, but a run that finishes with an incomplete list must say
# so loudly. This block pins the fourth of the plan's four required surfaces (the
# other three are chunking.DispatchOutcome, scheduled_arm.py's outcome/exit code,
# and enrich-records/SKILL.md's own equivalent pin).
# ---------------------------------------------------------------------------------


def test_the_skill_reports_an_incomplete_written_records_list_loudly():
    body = _normalized(_text())
    assert "outcome.written_records_failures" in body
    assert "INCOMPLETE" in body, (
        "the incomplete condition must be stated in words an operator cannot miss, "
        "not buried in a field name"
    )
    assert "D-59-10" in body
    assert "an undecided row stops the whole batch" in body.lower()


# ---------------------------------------------------------------------------------
# Quick task 260911-ss4 (F1, uat-autonomous-batch-2026-09-09.md): step 2's match ran
# once, but nothing survived it -- every later fence, a fresh process each time,
# re-ran preingest.match_batch and re-sent the whole batch. The recorded run spent SIX
# 4-row propose executions plus TWO 2-row sends where two would have done. These pins
# hold the fix: exactly one match_batch call (step 2's), a match_state.load(match_run_id)
# fence or prose mention in every later step that used to rebuild the match, and step 2
# printing match_run_id so a fresh process has the id it needs.
# ---------------------------------------------------------------------------------

def _step_span(number):
    for step_number, span in _numbered_step_spans(_text()):
        if step_number == number:
            return span
    raise AssertionError(f"no top-level step {number!r} found in SKILL.md")


def test_exactly_one_match_batch_call_and_it_sits_in_step_2():
    text = _text()
    assert text.count("preingest.match_batch(") == 1, (
        "the recorded F1 leak was a SECOND match_batch call (step 5's linkedin fence) "
        "re-sending the whole batch every time a later fence needed the classification"
    )
    assert "preingest.match_batch(" in _step_span("2")


def test_step_2_binds_and_prints_match_run_id_then_saves():
    span = _step_span("2")
    assert "match_run_id = outcome.run_id" in span
    assert "print(match_run_id)" in span, (
        "a fresh process must have match_run_id to pass to match_state.load — never "
        "re-derive it by re-sending the batch"
    )
    assert "match_state.save(match_run_id, classified)" in span


def test_step_3_loads_applies_and_saves_back_under_the_same_match_run_id():
    span = _step_span("3")
    assert "match_state.load(match_run_id)" in span
    assert "preingest.apply_match_decisions" in span
    assert "match_state.save(match_run_id" in span


def test_step_4_loads_the_persisted_classification_before_building_unmatched_rows():
    span = _step_span("4")
    assert "classified = match_state.load(match_run_id)" in span


@pytest.mark.parametrize("step_number", ["5", "6", "9"])
def test_steps_5_6_and_9_name_match_state_load_in_prose_as_the_rebuild_path(step_number):
    span = _step_span(step_number)
    assert "match_state.load(match_run_id)" in span, (
        f"step {step_number} consumes unmatched_rows/the classification without a "
        "stated source — exactly how the recorded leak refilled them by re-matching"
    )


def test_step_5s_linkedin_fence_loads_the_persisted_classification_not_a_second_match():
    span = _step_span("5")
    assert "classified = match_state.load(match_run_id)" in span
    assert "preingest.classify_matches" not in span, (
        "step 5's linkedin fence used to rebuild the WHOLE match from rows_from_table "
        "through classify_matches purely to reach one unmatched row"
    )


def test_step_7_loads_the_persisted_classification_before_confirmed_ids():
    span = _step_span("7")
    assert "classified = match_state.load(match_run_id)" in span


# =====================================================================================
# quick 260911-w6o (F2-1): the persist fence hands build_entry the MERGED row.
# =====================================================================================

# The fence's own build_entry call, as edited -- first argument is the merged-row
# lookup, falling back to the loop's own `row` only when this id has no merged entry.
PERSIST_FENCE_BUILD_ENTRY_CALL = (
    "entry = held_queue.build_entry(\n"
    "           merged_by_id.get(row_id, row), verdict.hold_code, verdict.reason, parsed)"
)

# The OLD call shape (bare `row`, the actual F2-1 defect) -- must be gone.
OLD_PERSIST_FENCE_BUILD_ENTRY_CALL = (
    "held_queue.build_entry(row, verdict.hold_code, verdict.reason, parsed)"
)


def test_the_persist_fence_hands_build_entry_the_merged_row_not_the_source_row():
    """F2-1: a held row's entry used to store the SOURCE spreadsheet line, discarding
    everything the waterfall found for it -- recorded run
    a254d1eda71246a2a964922cdf5c2bd2 threw a 7-credit Lusha reveal away this way
    (executions 12365-12376). The persist fence's build_entry call must pass the
    merged row, and must name `merge_report` as where it came from."""
    span = _step_span("5")
    assert PERSIST_FENCE_BUILD_ENTRY_CALL in span
    assert OLD_PERSIST_FENCE_BUILD_ENTRY_CALL not in span
    assert "merge_report" in span, (
        "the fence must name merge_report as the source of the merged rows it reads"
    )


def test_the_persist_fence_adds_no_merge_call_the_registered_sequence_is_untouched():
    """The merged rows arrive as a variable from the dispatch step's own
    `MergeResult` -- never a second `preingest.merge_enriched(...)` call inside this
    fence, which would silently drift `test_skill_sequence_coverage.py`'s registered
    call tuple for this exact block. Scoped to the FENCED python block only (via the
    same `extract_python_blocks`/`parse_calls` extraction that module itself uses),
    never a whole-file/whole-span grep -- the prose immediately above the fence
    legitimately names the `preingest.merge_enriched` rebuild path in a sentence, and
    a whole-span scan would refuse that very sentence."""
    modules = scripts_modules()
    persist_fence_source = None
    for _block_index, _line_number, source in extract_python_blocks(_text()):
        if "held_queue.build_entry(" in source and "run_state.read_progress(" in source:
            persist_fence_source = source
            break
    assert persist_fence_source is not None, "could not locate the persist fence's own python block"

    calls = parse_calls(persist_fence_source, modules)
    assert "preingest.merge_enriched" not in calls, (
        "the persist fence must consume merge_report as a variable, never re-derive "
        "it with a second merge_enriched call"
    )
    # The exact registered sequence (test_skill_sequence_coverage.py's COVERED entry
    # for this block) must be byte-for-byte unchanged -- a dict comprehension over
    # merge_report.rows and a .get() on a local dict add no scripts-module call.
    # Phase 71 (D-71-04): `held_queue.stable_key` is now the persist key's own
    # derivation, inserted between `build_entry` and `save`.
    assert calls == (
        "held_queue.load", "run_manifest.load", "preingest.parse_outcome",
        "confidence.assess", "held_queue.build_entry", "held_queue.stable_key",
        "held_queue.save",
        "run_manifest.save", "run_manifest.save", "run_manifest.run_manifest_path",
        "run_state.read_progress",
    )


# =====================================================================================
# Quick 260911-w6r (F2-4): step 6 shows the held rows by facet and hands over a ready
# answer, never a question (UAT F4); step 5's stale review-pass/open-todo text is
# corrected; step 9 restates the facets and the answer. Operator ruling 2026-09-11.
# =====================================================================================

# The recorded run's own asked question (UAT F4, .planning/UAT-autonomous-batch-
# 2026-09-09.md line 78) -- the rejected shape, quoted exactly rather than paraphrased.
F4_REJECTED_QUESTION = "how do you want to handle batch 1's two held rows?"

# review-triage/SKILL.md's create-step headings (4a/4b/4c), exact bold text -- quoted
# by heading in step 6, never reproduced. Same idiom as CONTACT_UPLOAD_HANDOFF_HEADINGS
# above, plus a cross-file existence check that pin does not have.
REVIEW_TRIAGE_CREATE_HEADINGS = (
    "Held rows: build the CSV for the creates this sitting chose (2c's `create` verb).",
    "Send it — contact-upload's own dispatch, by heading, never a second copy of it here.",
    "Confirm by re-reading, then mark — ONE call for the whole create batch, never one per row",
)

# A distinctive literal from review-triage's OWN create fence (4a) -- its presence here
# would mean the mechanics were copied, not referenced (mirrors
# test_the_skill_does_not_reproduce_contact_upload_step_bodies above).
REVIEW_TRIAGE_CREATE_FENCE_LITERAL = 'held_entries[rid]["row"] for rid in chosen_row_ids'

REVIEW_TRIAGE_SKILL_PATH = PLUGIN_ROOT / "skills" / "review-triage" / "SKILL.md"


def test_step_6_asks_nothing_about_held_rows_and_names_f4_as_the_rejected_shape():
    """UAT F4: step 6 used to ask "how do you want to handle batch 1's two held
    rows?" on a lane whose own doc says it does not ask at step 6. The 2026-09-11 F2
    ruling replaces the question with a facet render and a ready answer."""
    span = _step_span("6")
    normalized = _normalized(span).lower()
    assert "this is a rendering, not a question" in normalized
    assert F4_REJECTED_QUESTION.lower() in normalized
    assert "is the rejected shape" in normalized


@pytest.mark.parametrize("facet", sorted(held_queue.ALL_FACETS))
def test_step_6_names_every_shipped_facet(facet):
    """Read off held_queue.ALL_FACETS -- never a hand-typed list that can drift."""
    span = _step_span("6")
    assert f"FACET_{facet.upper()}" in span, (
        f"held_queue.ALL_FACETS names {facet!r}; step 6 must render it by the "
        "classifier's own constant name"
    )


def test_step_6_carries_the_ready_answer_with_both_routes():
    span = _step_span("6")
    normalized = _normalized(span).lower()
    assert "create all 2" in normalized
    assert "/operator-claude-plugin:review-triage" in span


def test_bare_create_all_never_appears_without_a_trailing_count_or_scope():
    """Direct mirror of test_bare_approve_all_never_appears_without_a_trailing_count_
    or_scope's own \\s*\\d regex, reused unchanged -- a bare 'create all' would repeat
    the original nine-directors mistake for a create instead of a match."""
    body = _normalized(_text())
    matches = list(re.finditer(r"create all", body, re.IGNORECASE))
    assert matches, "expected at least one 'create all' (scoped) example in SKILL.md"
    for match in matches:
        tail = body[match.end():match.end() + 6]
        assert re.match(r"\s*\d", tail), (
            f"found a bare 'create all' with no trailing count/scope at character "
            f"offset {match.start()}: {body[max(0, match.start() - 20):match.end() + 20]!r}"
        )


def test_step_6_never_waits_and_reaches_step_7_regardless():
    span = _step_span("6")
    normalized = _normalized(span).lower()
    assert "silence is a valid outcome" in normalized
    assert "the batch continues to step 7" in normalized


def test_step_6_quotes_review_triages_create_headings_and_they_still_exist_there():
    span = _step_span("6")
    review_triage_text = REVIEW_TRIAGE_SKILL_PATH.read_text(encoding="utf-8")
    for heading in REVIEW_TRIAGE_CREATE_HEADINGS:
        assert _normalized(heading) in _normalized(span), (
            f"expected review-triage/SKILL.md's create-step heading {heading!r} to be "
            "quoted by step 6, not paraphrased or reproduced as new prose"
        )
        assert _normalized(heading) in _normalized(review_triage_text), (
            f"the quoted heading {heading!r} no longer exists verbatim in "
            "review-triage/SKILL.md -- a renamed heading must be re-quoted here too"
        )


def test_step_6_does_not_reproduce_review_triages_create_mechanics():
    assert REVIEW_TRIAGE_CREATE_FENCE_LITERAL not in _text()


def test_step_6_states_the_grant_boundary_the_refusal_relay_and_no_widening():
    span = _step_span("6")
    normalized = _normalized(span).lower()
    assert "standing grant opened at step 5" in normalized
    assert "relay the refusal in the operator's own terms" in normalized
    assert "grant_not_authorized" in normalized
    assert "the grant is never widened here" in normalized
    assert "no second standing grant is opened" in normalized


def test_step_5_no_longer_promises_a_review_pass_positioned_after_the_report_step():
    span = _step_span("5")
    assert "review pass described after step 7's report" not in span


def test_step_5_no_longer_points_at_the_closed_pending_todo():
    text = _text()
    assert "no-plugin-path-turns-an-approved-held-row-into-a-sent-row" not in text


def test_step_9_restates_the_facet_counts_and_the_ready_answer():
    span = _step_span("9")
    normalized = _normalized(span).lower()
    for facet in held_queue.ALL_FACETS:
        assert f"facet_{facet}" in normalized
    assert "create all 2" in normalized
