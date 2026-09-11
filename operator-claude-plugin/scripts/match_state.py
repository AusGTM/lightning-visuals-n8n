"""operator-claude-plugin/scripts/match_state.py

Quick task 260911-ss4 (F1, `uat-autonomous-batch-2026-09-09.md`). The plugin's NEXT
persisted artifact, mirroring `run_state.py`'s module shape. Holds exactly one thing no
existing store could: `preingest.classify_matches`'s own five-key classification for
ONE batch's step-2 match, so a later fence -- a fresh process every time -- reads it
back instead of re-sending the whole batch through `preingest.match_batch` again. The
recorded UAT batch (`a254d1eda71246a2a964922cdf5c2bd2`, 2026-09-11) paid for the match
SIX times over because nothing survived between fences; this closes that leak.

**Schema.** `run_id` (the match's own `preingest.MatchOutcome.run_id`, D-70-05's
correlation handle -- never a second id minted here), `saved_at` (UTC isoformat), and
`classification` -- `preingest.classify_matches`'s own five keys (`auto_matched`,
`proposed`, `unmatched`, `unchecked`, `unknown_response_row_ids`), persisted as given.

Four decisions, each load-bearing:

1. **The forbidden-name guard scans NAMES ONLY -- top-level classification keys, every
   `row_id`, and every KEY inside a persisted `row` dict. It never scans string
   VALUES.** Phase 23 D-11 is about a grant, a secret, or a token being readable off
   disk under its own name; a contact's `firstname` is not a name in that sense.
   `held_queue._first_forbidden` scans string leaves, and against the recorded UAT
   batch 2 (Grant Dewsbury) that would refuse the row outright and drop the fence
   straight back into the re-match this store exists to stop. Reimplemented fresh in
   this module, per the plugin's anti-DRY per-store discipline (D-69-01) -- never
   imported from a sibling.
2. **Rows are persisted VERBATIM, with no field allowlist.** `held_queue`'s allowlist
   (`row_id` + `enrichment.MATCH_LOOKUP_KEYS`) is complete because its only consumer is
   a re-send of a MATCH request, and that tuple is the proven projection for one. This
   store's consumers include `extraction.write_dispatch_csv`, whose header is
   `extraction.canonical_props()` -- wider, and config-driven from
   `column_mapping.yaml`. An allowlist narrower than that would silently drop a column
   the operator supplied. A future narrowing is a decision, not drift.
3. **`load` RAISES `MatchStateError` on absent, unreadable, malformed, or another
   run's file** -- naming the run -- mirroring `run_state.mark_dispatched`'s refusal
   rather than `run_state.load`-style degrade-to-empty. An empty classification
   returned here would flow into `classified["unmatched"]` and read as "nothing to
   enrich", or raise a `TypeError` two lines on; either way the fence's recovery is
   the re-match this fix removes. `classify_read` stays the non-raising probe so the
   SKILL prose has words for what it saw.
4. **`save` validates every name BEFORE writing**, so a refused save leaves any
   previous document untouched -- `run_manifest.save`'s validate-then-apply discipline.

Writes through `durable_paths._atomic_write_0600`, same durable directory as every
other artifact in this family, filename deliberately not a dotfile (Phase 23 D-04).
ONE FILE PER RUN (`match_state-<run_id>.json`), mirroring `run_state.run_state_path`'s
exact naming shape.

Registered in `run_report._PRUNE_SHORT_TTL_GLOBS` (a within-round working file, same
7-day family as `run_state-*.json`) and in
`test_forbidden_marker_parity._KEY_MATCHER_MODULES` (an eighth matcher, behaviourally
identical to the other seven).
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

# --- schema ------------------------------------------------------------------------

RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
CLASSIFICATION_FIELD = "classification"

# `preingest.classify_matches`'s own five keys -- persisted exactly as returned.
CLASSIFICATION_KEYS = (
    "auto_matched", "proposed", "unmatched", "unchecked", "unknown_response_row_ids",
)

# classify_read()'s three answers.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"

# Phase 23 D-11, reimplemented (not imported) per `run_state.py`/`held_queue.py`'s own
# precedent -- a future change to one list must not silently weaken another.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

_CAMEL_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_TOKEN = re.compile(r"[^a-z0-9]+")
_INFLECTION_SUFFIXES = ("", "s", "ed", "ing")


def _tokenised(value) -> str:
    """`value`, camel-broken, lowercased, and split into a padded, space-joined run
    of tokens (e.g. `" armed row "`) -- the shape a marker is matched against."""
    broken = _CAMEL_BREAK.sub(" ", str(value)).lower()
    tokens = [token for token in _NON_TOKEN.split(broken) if token]
    return f" {' '.join(tokens)} "


_FORBIDDEN_TOKEN_RUNS = tuple(
    _tokenised(marker).rstrip() + suffix + " "
    for marker in _FORBIDDEN_NAME_MARKERS
    for suffix in _INFLECTION_SUFFIXES
)


def _looks_forbidden(value) -> bool:
    tokenised = _tokenised(value)
    return any(run in tokenised for run in _FORBIDDEN_TOKEN_RUNS)


class MatchStateError(Exception):
    """Raised when a match classification cannot be persisted or read back safely --
    a document key, a `row_id`, or a `row` key whose name suggests an arming grant, a
    live-write permission, a secret, or an API key (save); or a file that is absent,
    unreadable, malformed, or recorded under a different run's id (load). Nothing is
    written when a save raises; nothing is returned when a load raises."""


def match_state_path(run_id) -> Path:
    """Where ONE batch's match classification lives -- resolved fresh on every call,
    the same durable directory every sibling store resolves into."""
    return durable_paths.resolve_state_path().parent / f"match_state-{run_id}.json"


def _first_forbidden_name(classification):
    """Scans NAMES ONLY (see module docstring, decision 1) -- top-level classification
    keys, every `row_id` (including `unknown_response_row_ids`' bare id list), and
    every KEY inside a persisted `row` dict. Never a string VALUE. Returns the
    offending name, or `None`."""
    for group_key, entries in classification.items():
        if _looks_forbidden(group_key):
            return group_key
        if group_key == "unknown_response_row_ids":
            for row_id in entries:
                if _looks_forbidden(row_id):
                    return row_id
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            row_id = entry.get("row_id")
            if row_id is not None and _looks_forbidden(row_id):
                return row_id
            row = entry.get("row")
            if isinstance(row, dict):
                for key in row:
                    if _looks_forbidden(key):
                        return key
    return None


def save(run_id, classification, path=None) -> None:
    """Persist one batch's whole classification. Validates every name BEFORE writing
    (decision 4) -- a refused save leaves any previous document untouched."""
    if _looks_forbidden(run_id):
        raise MatchStateError(
            f"refusing to persist match state under run id {run_id!r} -- its name "
            "suggests an arming grant, a live-write permission, a secret, or an API "
            "key. Nothing was written."
        )
    offender = _first_forbidden_name(classification)
    if offender is not None:
        raise MatchStateError(
            f"refusing to persist match state for run {run_id!r} -- {offender!r} "
            "suggests an arming grant, a live-write permission, a secret, or an API "
            "key. Nothing was written."
        )
    target = Path(path) if path is not None else match_state_path(run_id)
    document = {
        RUN_ID_FIELD: run_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        CLASSIFICATION_FIELD: classification,
    }
    durable_paths._atomic_write_0600(target, json.dumps(document))


def _load_document(run_id, path=None):
    """The raw document, or `None` if it cannot be read, is malformed, or is recorded
    under a DIFFERENT run's id. Shared by `classify_read()` and `load()` so both agree
    on what "usable" means."""
    target = Path(path) if path is not None else match_state_path(run_id)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get(RUN_ID_FIELD) != run_id:
        return None
    classification = document.get(CLASSIFICATION_FIELD)
    if not isinstance(classification, dict):
        return None
    if set(classification) != set(CLASSIFICATION_KEYS):
        return None
    return document


def classify_read(run_id, path=None) -> str:
    """What this run's own match-state file looks like, from a fresh probe -- never
    raises. `ABSENT` (never saved), `PARSEABLE` (a real, readable document belonging to
    this run), or `ANOMALOUS` (present but unreadable, malformed, or recorded under a
    different run's id -- must never present as zero matches, see module docstring)."""
    target = Path(path) if path is not None else match_state_path(run_id)
    if not target.exists():
        return ABSENT
    return PARSEABLE if _load_document(run_id, path) is not None else ANOMALOUS


def load(run_id, path=None) -> dict:
    """This run's own classification, or raise (decision 3). Never degrades to an
    empty classification -- an empty one would read as "no matches" and skip real
    rows, or raise two lines on in a caller that assumes the five keys are lists."""
    document = _load_document(run_id, path)
    if document is not None:
        return document[CLASSIFICATION_FIELD]
    target = Path(path) if path is not None else match_state_path(run_id)
    if not target.exists():
        raise MatchStateError(
            f"no match state found for run {run_id!r} at {target} -- step 2 has not "
            "been run yet, or nothing was saved. Re-run step 2 once; never guess a "
            "classification."
        )
    raise MatchStateError(
        f"match state at {target} could not be read for run {run_id!r} -- it is "
        "unreadable, malformed, or recorded under a different run's id. Nothing was "
        "returned; never a degraded empty classification."
    )
