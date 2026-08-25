"""The enrichment skill's packaging and conversation contract (INGEST-04, DISPATCH-02).

Deliberately a SEPARATE file from `test_plugin_manifest.py` rather than an extension of
it. That file is held uncommitted by an operator mid-23-06 and hardcodes a single
`contact-upload` SKILL_PATH; editing it — or widening a glob onto it — would collide with
work in flight. The assertions here are the same ones it makes, scoped to this skill.
"""
import re
from pathlib import Path

import enrichment
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PLUGIN_ROOT / "skills" / "enrich-records" / "SKILL.md"


def _text():
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalized(text):
    """Markdown wraps lines and prefixes blockquotes; neither changes what the operator
    reads. Compare on collapsed whitespace with the quote markers and bold markers
    removed, so a reflow cannot fail a wording assertion (and cannot hide one either)."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip()


def test_the_skill_exists_with_parseable_frontmatter_carrying_name_and_description():
    text = _text()
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert {"name", "description"} <= set(frontmatter)
    assert frontmatter["name"] == "enrich-records"


def test_the_description_fires_on_natural_operator_phrasing_and_names_the_slash_form():
    description = yaml.safe_load(_text().split("---", 2)[1])["description"].lower()
    assert "enrich" in description
    assert "hubspot" in description
    assert "/operator-claude-plugin:enrich-records" in description


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


def test_the_view_refusal_is_the_one_recorded_sentence_not_a_paraphrase():
    """Amendment #7 has exactly one phrasing of record, and it is a module constant so the
    backend, the client and the operator-facing copy cannot drift into three."""
    assert _normalized(enrichment.VIEW_REFUSAL) in _normalized(_text()), (
        "the view refusal was paraphrased — it must be `enrichment.VIEW_REFUSAL` verbatim"
    )


def test_the_skill_states_the_endpoint_and_the_disarmed_state_before_any_work():
    first_step = _normalized(_text().split("2. **Resolve which records", 1)[0])
    assert "hubspot/enrichment/event" in first_step
    assert "disarmed" in first_step


def test_the_skill_names_the_arming_phrase_and_scopes_it_to_the_conversation():
    body = _normalized(_text())
    assert '"arm the enrichment"' in body
    assert "never written to disk" in body
    assert "for this conversation only" in body


def test_the_skill_says_a_list_count_is_unknown_rather_than_zero():
    body = _normalized(_text())
    assert "`unknown`" in body
    assert "does not mean zero" in body


def test_the_skill_refuses_to_claim_per_record_outcomes():
    assert "Do not claim per-record outcomes" in _normalized(_text())


# ---------------------------------------------------------------------------------
# D-53-04 (2026-08-25): while a write grant covering this lane and these records is
# open, the per-turn arming phrase is not asked again. All ADDITIVE -- every pin above
# stays exactly as it was, including the phrase, the disk clause and the scope clause,
# which bind the ungranted path this decision leaves untouched.
# ---------------------------------------------------------------------------------


def test_the_skill_says_an_open_grant_replaces_the_per_turn_phrase():
    body = _normalized(_text()).lower()
    assert "if a write grant covering this lane and these records is already open" in body
    assert "do not ask for the phrase again" in body
    assert "with no grant open, everything above is exactly as it is today" in body


def test_the_skill_says_what_a_grant_does_not_remove():
    """Without this line an operator reasonably concludes the safety went away with the
    question (T-53-19). It did not: the preview, the record scoping, the per-send window
    and the loud disarm failure are all unchanged by a grant."""
    body = _normalized(_text()).lower()
    assert "a grant removes the question, not the safety" in body
    assert "bounded to that send's records" in body
    assert "reported loudly" in body


def test_the_skill_says_revocation_bites_at_the_next_send_not_mid_dispatch():
    body = _normalized(_text()).lower()
    assert "refuses the next send" in body
    assert "does not stop a dispatch already running" in body


def test_the_grant_branch_shows_the_window_scoped_to_this_sends_records():
    body = _normalized(_text())
    assert "write_grant.authorize_send" in body
    assert "n8n_arming.armed_window" in body
    assert "never the grant's whole record set" in body.lower()


def test_the_skill_does_not_re_ask_for_approval_under_a_grant():
    """D-53-06 (operator, 2026-08-25), found by the walk of Phase 53 itself.

    53-04 made the ARMING PHRASE conditional on an open grant, and stopped there. The
    "Ask for approval" step is older than grants and was left unconditional, so a grant
    removed one ask and left the other standing: the operator opened a grant and was
    immediately asked "want to run the send now?" — half the friction removed, none of
    the protection given back. The approval a grant carries is the yes given to the
    envelope BEFORE the run; asking again during it is the stop-and-ask the grant exists
    to remove.
    """
    body = _normalized(_text()).lower()
    assert "under an open grant covering this lane and these records, do not ask again" in body
    assert "informs rather than gates" in body, (
        "the skill must say what happens to the preview under a grant — it is still shown, "
        "but it no longer gates, because the gate moved earlier"
    )
