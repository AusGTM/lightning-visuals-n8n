"""The enrich-before-ingest skill's packaging and two-arm safety contract (37-CONTEXT.md
sec 6). Mirrors `test_enrich_skill_contract.py`'s structure and its `_normalized()`
idiom, deliberately kept a SEPARATE file rather than folded into that one -- same
reasoning that file states about not colliding with work in flight elsewhere.

The two pins that matter most here are NOT wording assertions: they are a
character-offset comparison (the enriched-preview heading must precede the ingest-arm
heading) and a same-numbered-step exclusion (the two arming phrases must never share a
step).

WHAT THOSE TWO PINS DEFEND CHANGED ON 2026-08-25, and this file no longer claims
otherwise. Under D-53-05 -- taken by the operator, deliberately, for speed -- ONE write
grant may authorize both lanes of this flow, which means the HubSpot write can be
authorized before the enriched preview exists. The pins below therefore no longer stop
that collapse; they bind the UNGRANTED path (unchanged by D-53-04) and they carry the
record that the ordering protection was removed on purpose and by whom. The protections
that remain are asserted here too: the allowlist stays record-scoped to the named batch,
and the disclosure the operator was given in exchange -- that the write is authorized
before the enriched preview exists -- is pinned so a later edit cannot quietly drop it
after the protection was already traded for it.
"""
import re
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PLUGIN_ROOT / "skills" / "enrich-before-ingest" / "SKILL.md"

ARM_ENRICHMENT_PHRASE = '"arm the enrichment"'
ARM_UPLOAD_PHRASE = '"arm the upload"'

# Literal, unique substrings that locate each section's own heading -- not full
# sentences, so a later wording tweak elsewhere in the step doesn't break the find().
ENRICHED_PREVIEW_HEADING = "6. **The enriched preview"
INGEST_ARM_HEADING = '7. **Say "arm the upload,"'

# The exact heading text of contact-upload/SKILL.md's steps 6-10 (37-RESEARCH.md sec
# C.13), which this skill must reference rather than duplicate.
CONTACT_UPLOAD_HANDOFF_HEADINGS = (
    "Dispatch only once the operator has said the arming phrase this turn.",
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


def test_both_arming_phrases_appear():
    # Normalized because the second occurrence of the enrichment phrase (inside the
    # bold marker in prose) wraps across a markdown line break — a reflow that does
    # not change what the operator reads and must not fail this assertion.
    body = _normalized(_text())
    assert ARM_ENRICHMENT_PHRASE in body
    assert ARM_UPLOAD_PHRASE in body


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
            "write grant open this flow still asks twice, and the two phrases are what "
            "it asks with (D-53-04). A combined authorization is expressible only as a "
            "write grant, which is disclosed rather than phrased"
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
    a later edit cannot drop the sentence the operator was given in exchange."""
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
    assert "authorized before the enriched preview exists" in _normalized(text).lower(), (
        "D-53-05 traded the ordering protection for one thing only: the operator being "
        "told, at the yes, that a grant covering both lanes authorizes the HubSpot write "
        "before the enriched preview exists. Without that sentence the trade is worse "
        "than the one the operator agreed to"
    )


def test_the_two_arming_phrases_never_share_a_numbered_step():
    """A step containing both phrases would necessarily ask for the write grant
    before the enriched preview exists (37-CONTEXT.md sec 6.2) -- they guard two
    different irreversible things at two different moments."""
    for number, span in _numbered_step_spans(_text()):
        normalized_span = _normalized(span)
        has_enrichment_phrase = ARM_ENRICHMENT_PHRASE in normalized_span
        has_upload_phrase = ARM_UPLOAD_PHRASE in normalized_span
        assert not (has_enrichment_phrase and has_upload_phrase), (
            f"numbered step {number} contains both arming phrases -- they must be "
            "spoken in different turns, never both granted by one step's own text"
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


def test_the_skill_says_the_grant_branch_does_not_ask_for_the_phrase_again():
    body = _normalized(_text()).lower()
    assert "do not ask for the phrase again" in body
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
