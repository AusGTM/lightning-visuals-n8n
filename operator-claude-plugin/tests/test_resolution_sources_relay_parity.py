"""Parity test for bug_003 (2026-08-29 ultrareview).

`enrich-records/SKILL.md` and `enrich-before-ingest/SKILL.md` both instruct relaying a
`resolvable` entry's `resolution_sources` to the operator (D-59-08). Before this fix the
two disagreed on whether an entry claims one value or several: `enrich-records/SKILL.md`
said "name which of the four `resolution_sources` values ... it claims" while
`enrich-before-ingest/SKILL.md` said "naming the `resolution_sources` value the entry
claims" — unambiguously singular. Neither reading is correct: `RecordSpecError.__init__`
(enrichment.py:95-118) types an entry's `sources` as a tuple, and GATE-03's `name` entry
(enrichment.py:427-436) carries THREE of the four values at once. A singular-implying
relay silently drops real values the operator needs to see.

Deliberately a separate file from `test_enrich_skill_contract.py` and
`test_enrich_before_ingest_skill_contract.py` — this is a CROSS-file parity check, not a
per-skill contract, and belongs to neither of those single-`SKILL_PATH` files.
"""
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
ENRICH_RECORDS_SKILL = PLUGIN_ROOT / "skills" / "enrich-records" / "SKILL.md"
ENRICH_BEFORE_INGEST_SKILL = PLUGIN_ROOT / "skills" / "enrich-before-ingest" / "SKILL.md"

# The exact singular phrasing bug_003 found in enrich-before-ingest/SKILL.md — pinned
# absent in BOTH files so neither can drift back to implying one value.
_SINGULAR_PHRASE = "the `resolution_sources` value the entry claims"


def _normalized(path):
    """Same idiom as test_enrich_skill_contract.py / test_enrich_before_ingest_skill_
    contract.py's own `_normalized()` — markdown wrapping and bold markers don't change
    what the operator reads."""
    text = path.read_text(encoding="utf-8")
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip()


def test_both_skills_instruct_naming_every_resolution_sources_value_the_entry_carries():
    for path in (ENRICH_RECORDS_SKILL, ENRICH_BEFORE_INGEST_SKILL):
        body = _normalized(path)
        assert (
            "name every `resolution_sources` value" in body
            or "naming every `resolution_sources` value" in body
        ), (
            f"{path} must instruct enumerating EVERY value the entry's `sources` "
            "tuple carries, not implying a single pick — GATE-03's `name` entry "
            "carries three of the four (enrichment.py:427-436)"
        )


def test_neither_skill_implies_a_resolvable_entry_carries_only_one_source():
    for path in (ENRICH_RECORDS_SKILL, ENRICH_BEFORE_INGEST_SKILL):
        body = _normalized(path)
        assert _SINGULAR_PHRASE not in body, (
            f"{path} implies a resolvable entry names exactly one resolution_sources "
            "value — an entry's `sources` tuple can carry up to three of the four "
            "(GATE-03's `name` entry, enrichment.py:427-436)"
        )
