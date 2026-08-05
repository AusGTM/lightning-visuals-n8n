"""The enrich-before-ingest skill's packaging and two-arm safety contract (37-CONTEXT.md
sec 6). Mirrors `test_enrich_skill_contract.py`'s structure and its `_normalized()`
idiom, deliberately kept a SEPARATE file rather than folded into that one -- same
reasoning that file states about not colliding with work in flight elsewhere.

The two pins that matter most here are NOT wording assertions: they are a
character-offset comparison (the enriched-preview heading must precede the ingest-arm
heading) and a same-numbered-step exclusion (the two arming phrases must never share a
step). Both are the mechanism that stops a later edit from silently collapsing the
two-grant design into one.
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
    normalized = _normalized(_text()).lower()
    for spelling in _COMBINED_PHRASE_SPELLINGS:
        assert spelling not in normalized, (
            f"a combined arming phrase slipped into SKILL.md: {spelling!r} -- a "
            "combined phrase would necessarily be spoken before the enriched preview "
            "exists, granting the HubSpot write before the operator can see what "
            "they are approving"
        )


def test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading():
    """The ordering IS the safety property (37-CONTEXT.md sec 6.3): the enriched
    preview must land in the operator's turn before the ingest arm can be spoken,
    which is what makes the two `armed` arguments necessarily fall in different
    turns. A later edit that reorders these two sections would collapse the design
    with no other test noticing -- so the offsets are compared directly rather than
    inferred from any other property of the document."""
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
        f"{preview_offset}) -- the enriched preview must land in the operator's turn "
        "before the ingest arm can be spoken"
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


def test_the_skill_states_the_grant_never_outlives_its_turn_and_arms_no_other_lane():
    body = _normalized(_text()).lower()
    assert "never outlives" in body or "never written to disk" in body
    assert "arming one lane does not arm any other lane" in body
