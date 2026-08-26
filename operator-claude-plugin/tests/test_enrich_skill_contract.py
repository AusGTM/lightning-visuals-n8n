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


def test_the_skill_binds_consent_to_this_send_and_scopes_it_there():
    """RECORDED EDIT -- VOCAB-05, 2026-08-25, taken by the operator.

    This pin used to assert the literal string `"arm the enrichment"` and the clause "for
    this conversation only". Observed live on that day's walk: the operator was shown a
    preview ending "Proceed?", answered "yes", and was told a yes does not dispatch -- say
    the exact phrase. A magic string demanded at the moment they were trying to consent.

    The safety property was never the spelling. It is that consent is unambiguous and
    ATTACHED: a casual "ok" answering nothing must not become a write. So the phrase
    assertion is REPLACED by the clauses carrying that property -- an affirmative arms the
    send it answers, an unattached or ambiguous one arms nothing -- and the scope narrows
    from the conversation to the send, which is what "arms that send only" means. The
    disk clause is unchanged. `armed` still has no default in code (`dispatch_plan` raises
    without it); that structural guarantee is pinned in test_chunking.py and does not move.
    """
    body = _normalized(_text())
    assert '"arm the enrichment"' not in body, (
        "the arming phrase is dead (VOCAB-05) -- an operator must never have to produce "
        "the system's wording to say yes"
    )
    assert "arms this send and nothing else" in body, (
        "the affirmative must be bound to THIS send -- a yes that arms more than the send "
        "it answers is the unattached consent the phrase used to prevent"
    )
    assert "does not arm anything" in body, (
        "an affirmative answering nothing, or some other question, must arm nothing"
    )
    assert "ambiguous is not consent" in body
    assert "never written to disk" in body
    assert "for this send only" in body


def test_the_skill_says_a_list_count_is_unknown_rather_than_zero():
    body = _normalized(_text())
    assert "`unknown`" in body
    assert "does not mean zero" in body


def test_the_skill_relays_what_the_sync_body_says_never_inventing_beyond_it():
    """RECORDED EDIT -- F3, 2026-08-25, live walk of plugin 0.17.0.

    This pin used to assert the literal string "Do not claim per-record outcomes". Read
    too broadly, that sentence told the model to suppress a per-record outcome the
    synchronous body DID carry, not only one it would have had to invent: the walk's body
    read `action: "write_blocked"`, `match.reason: "searched, no hit"`, and the client
    reported "Sent. Backend accepted 1 chunk, 1 row. No failures, nothing to re-send"
    anyway (see .planning/debug/resolved/walk-write-path-defects.md).

    The safety property was never "withhold per-record detail" -- it is "never guess
    beyond what the body says". The string assertion is REPLACED by the clauses carrying
    that property, and by the call into `report_enrichment.build_sync_report`, which now
    computes the created/enriched/blocked/skipped/unknown + match mapping instead of
    leaving it to prose the model could read either way.
    """
    body = _normalized(_text())
    assert "Do not claim per-record outcomes" not in body, (
        "the withhold-everything rule is dead (F3) -- a synchronous body's own action "
        "and match fields must be relayed, not suppressed"
    )
    assert "build_sync_report" in body
    assert "never invent what the body does not carry" in body.lower()
    assert "always relay what it does" in body.lower()
    assert "match_level" in body and "match_reason" in body


# ---------------------------------------------------------------------------------
# D-53-04 (2026-08-25): while a write grant covering this lane and these records is
# open, the per-send ask is not made again. All ADDITIVE -- the pins above bind the
# ungranted path this decision leaves untouched.
#
# AMENDED VOCAB-05 (2026-08-25): this block used to say the pins above stay exactly as
# they were "including the phrase". They do not any more -- the phrase pin was rewritten
# in place (see its own RECORDED EDIT docstring) because the literal string died and the
# attached-consent property it stood for did not. The disk clause and the scope clause
# survive, the scope narrowed from the conversation to the send, and D-53-04 itself is
# untouched by any of it.
# ---------------------------------------------------------------------------------


def test_the_skill_says_an_open_grant_replaces_the_per_send_ask():
    """RECORDED EDIT -- VOCAB-05, 2026-08-25. Was
    `test_the_skill_says_an_open_grant_replaces_the_per_turn_phrase`, asserting the words
    "do not ask for the phrase again". There is no phrase to ask for any more; there is
    still an ask, and a grant still removes it. Same property, current words."""
    body = _normalized(_text()).lower()
    assert "if a write grant covering this lane and these records is already open" in body
    assert "do not ask at all" in body
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


# ---------------------------------------------------------------------------------
# Phase 58 Plan 03 Task 3 (2026-08-26) — the domain confirm table (D-58-04/05/06/07).
# ADDITIVE ONLY: no pin above this point is touched or reworded by this block.
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
    assert "an undecided row stops the whole batch" in body.lower()


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
