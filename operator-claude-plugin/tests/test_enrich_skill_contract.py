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
