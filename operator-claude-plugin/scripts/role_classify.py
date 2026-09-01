"""operator-claude-plugin/scripts/role_classify.py

Phase 62's ONLINE half of the role vocabulary: matches one already-extracted job title
string against a supplied list of role families and returns the matching family label,
or `None`. Pure -- no I/O, no network, no model call -- mirroring
`company_domain.needs_research()`'s discipline: this module DECIDES a match, it never
derives or refreshes the family list itself. The list is always a parameter; where it
comes from (Haiku clustering of live `jobtitle` values, cached) is `role_vocabulary.py`'s
job, a different module for a different (offline, build-time) problem.

Each family entry is `{"label": <str>, "members": [<title>, ...]}`. Matching is
case-folded and whitespace-normalised over the member titles, exact match only -- no
fuzzy matching, no partial/substring matching. A title this module cannot place is `None`,
never a guess.

This module also carries the OFFLINE-cache-facing half of the same feature: loading the
committed `role_vocabulary.yaml` (written by the repo-root `scripts/role_vocabulary.py`)
and rendering the operator-facing role menu with its evidence status attached, per
D-62-06/D-62-07. `load_families()`/`offer_block()`/`chosen_families()` all take the
vocabulary dict as a parameter or return one -- none of them re-derive it.
"""
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VOCABULARY_PATH = PLUGIN_ROOT / "config" / "role_vocabulary.yaml"

# D-62-07's mitigation. This exact sentence is what lets an operator tell a portal-derived
# role list from an invented one at a glance -- not optional formatting.
DISCLOSURE_SENTENCE = (
    "These roles were NOT derived from this portal's own contacts -- they are a generic "
    "list. Run scripts/role_vocabulary.py against this portal to replace them with roles "
    "that actually recur here."
)


class RoleVocabularyError(Exception):
    """Raised when the plugin's role-vocabulary cache is missing or unparseable. Names
    the file -- mirrors cost_guard.CostRateError's register: a missing shipped config
    file is an incomplete install, never a silent empty list, which would render as "no
    roles recur here" and read as a finding rather than a broken install."""


def load_families(path=None) -> dict:
    """Loads the cached role-family vocabulary PLUS its document-level evidence metadata
    (`evidenced`, `source`, `built_on`, `top_n`, `distinct_titles_sampled`) -- never the
    family list alone, because a caller holding only the list cannot tell a counted
    family from an invented one."""
    import yaml

    vocab_path = Path(path) if path is not None else DEFAULT_VOCABULARY_PATH
    if not vocab_path.exists():
        raise RoleVocabularyError(
            f"Role vocabulary cache not found at {vocab_path}. It ships with the "
            "plugin -- if it is missing, the install is incomplete; reinstall rather "
            "than offering an empty role list."
        )
    try:
        vocabulary = yaml.safe_load(vocab_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise RoleVocabularyError(
            f"Role vocabulary cache at {vocab_path} could not be parsed as YAML."
        ) from None

    if not isinstance(vocabulary, dict) or "families" not in vocabulary:
        raise RoleVocabularyError(
            f"Role vocabulary cache at {vocab_path} is missing its 'families' field."
        )
    return vocabulary


def offer_block(vocabulary) -> str:
    """Renders the operator-facing role menu. Evidenced families show their recurrence
    count; an un-evidenced (generic-fallback) vocabulary opens with a plain sentence
    stating the list was not derived from this portal's own contacts and naming the
    rebuild as the way to evidence it -- this sentence IS D-62-07's whole mitigation and
    SUGGEST-03's amended condition, not optional formatting."""
    lines = []
    if not vocabulary.get("evidenced"):
        lines.append(DISCLOSURE_SENTENCE)
        lines.append("")
    lines.append("Pick the roles worth enriching for this batch:")
    for family in vocabulary.get("families") or []:
        label = family.get("label")
        if vocabulary.get("evidenced"):
            lines.append(f"- {label} (seen {family.get('recurrence', 0)} times)")
        else:
            lines.append(f"- {label}")
    return "\n".join(lines)


def chosen_families(vocabulary, labels):
    """Validates the operator's ONCE-PER-BATCH role selection against the vocabulary's
    own family labels, raising RoleVocabularyError on any label that doesn't exist.
    Round-level only: this takes a single list of labels for the whole batch, never a
    per-record selection (SUGGEST-02) -- callers pass the same list to every company in
    the round, not a fresh one per company."""
    known = {family.get("label") for family in (vocabulary.get("families") or [])}
    unknown = [label for label in labels if label not in known]
    if unknown:
        raise RoleVocabularyError(
            f"Unknown role label(s) not in this vocabulary: {unknown}. "
            f"Known labels: {sorted(l for l in known if l)}."
        )
    return list(labels)


def _normalize(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def classify_title(title, family_list):
    """One already-extracted job title string, and a list of role families, in; the
    matching family's `label`, or `None`, out. Never fetches, never calls a model, never
    derives or refreshes `family_list` -- that list is always supplied by the caller."""
    normalized_title = _normalize(title)
    if not normalized_title:
        return None
    for family in family_list or []:
        members = family.get("members") or []
        for member in members:
            if _normalize(member) == normalized_title:
                return family.get("label")
    return None
