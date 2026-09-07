"""operator-claude-plugin/scripts/suggestion_declines.py

The plugin's next persisted artifact. A SIBLING of `held_queue.json`, never a section
inside it (D-69-01): it follows every convention `held_queue.py` established --
resolved under `durable_paths.resolve_state_path().parent`, written with
`durable_paths._atomic_write_0600`, whole-document overwrite, validate-every-entry
before anything is written, the secret/grant-name refusal (`_looks_forbidden`), and a
`classify_read`-style reader (added Task 3).

**Why this store exists and `held_queue` does not widen to cover it (D-69-02).**
`confidence.ALL_HOLD_CODES` is the match-gate vocabulary -- "could not identify this
person". A suggestion-round `partition_for_dispatch` decline means something entirely
different -- "identified fine, declined to send" (no email, a stranger's email domain,
an unknown company domain, a weak search source). Letting a decline into `held_queue`
would put it in the review queue wearing a match verdict's clothes, and
`held_queue.save`'s own `HeldQueueError` on any of these codes is correct behaviour
that stays. This module gains no `confidence` import and names no `confidence` code --
`suggest_contacts.PARTITION_REASON_CODES` is its own, deliberately disjoint,
vocabulary, pinned disjoint from `confidence.ALL_HOLD_CODES` by test.

**The document ACCUMULATES; each entry carries its OWN `run_id` (D-69-03).**
Deliberately diverges from `held_queue`'s single-`run_id` document, where a new run
overwrites and `classify_read` reports `another_run` as a rejection. A deferred entry
has to survive a run boundary, so run scope moves from the document to the entry --
this document carries NO run id and NO timestamp of its own. A new run's declines
MERGE into the document; they never overwrite it. There is consequently no
"another run" state at the document level -- `classify_read` (Task 3) returns one of
three answers, not `held_queue`'s four.

**The forbidden-name refusal is REIMPLEMENTED, not imported**, per `held_queue.py`'s
own stated discipline (held_queue.py:68-70) -- a future change to one cannot silently
weaken another. This is the third instance of the same discipline in this plugin
(`held_queue.py`'s own copy of `run_manifest.py`'s being the second).

# ponytail: whole-document overwrite, last writer wins, no lock -- single-operator
# assumption inherited from every sibling store in this plugin. Per-key locking only
# if two operators ever share one durable directory on one machine.

# ponytail: the `"arm"` marker in `_FORBIDDEN_NAME_MARKERS` matches inside ordinary
# words -- a real company name like "Armidale Jockey Club", or a locator path
# containing "farm" or "pharmacy", refuses the save. Inherited verbatim from
# `held_queue` on purpose (D-69-01), which is exactly why `first_refusal` below is
# PUBLIC: the caller pre-checks with it and reports the one entry it cannot store
# rather than losing a whole batch's save to it.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import durable_paths
import enrichment
import suggest_contacts

QUEUE_FILENAME = "suggestion_declines.json"
ENTRIES_FIELD = "entries"
KEY_SEPARATOR = "::"
NAME_SEPARATOR = "|"

# Deliberately NOT `held_queue.ROW_FIELD_ALLOWLIST` and deliberately excluding
# `row_id` (D-69-04; `preingest.build_rows_spec` also refuses a row that already
# carries one). Equals `extraction.canonical_props()` exactly -- pinned by test.
ROW_FIELD_ALLOWLIST = enrichment.MATCH_LOOKUP_KEYS + ("jobtitle", "phone", "company_id")

# Reimplemented (not imported) per `held_queue.py:101-144`'s own precedent.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

# The read-classification vocabulary (Task 3's `classify_read`). No ANOTHER_RUN:
# D-69-03 makes the whole document multi-run by design, so there is no "wrong run" to
# detect at the document level -- an individual entry's own `run_id` is still
# informative and is what `partition_by_run` (Task 3) reads.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"


class SuggestionDeclineError(Exception):
    """Raised when an entry cannot be persisted safely -- a `reason_code` outside
    `suggest_contacts.PARTITION_REASON_CODES`, a missing/empty `run_id`, or a
    key/value whose name suggests an arming grant, a live-write permission, a secret,
    or an API key. Nothing is written when this raises."""


def _looks_forbidden(value) -> bool:
    lowered = str(value).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)


def _first_forbidden(value):
    """Recursively scans keys and string leaves for a forbidden-shaped name --
    returns the offending string, or `None`. `ROW_FIELD_ALLOWLIST` is the first line;
    this is the second, belt-and-braces check."""
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden(key):
                return key
            found = _first_forbidden(sub)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_forbidden(item)
            if found is not None:
                return found
    elif isinstance(value, str) and _looks_forbidden(value):
        return value
    return None


def queue_path() -> Path:
    """Resolved fresh on every call -- the same durable directory `held_queue.
    queue_path()` resolves into, never a second resolution rule."""
    return durable_paths.resolve_state_path().parent / QUEUE_FILENAME


def entry_key(company_id, row):
    """The composite string key for `entries` (D-69-04), or `None` when `company_id`
    is `None`/empty or `suggest_contacts.name_key(row)` is `None` -- an incomplete
    identity is never a key. Uses `str(company_id)`.

    Separator contract: `KEY_SEPARATOR` cannot appear inside a numeric HubSpot company
    id. `NAME_SEPARATOR` inside a normalised name is NOT defended -- the key is an
    INDEX, not the record of truth; the entry's own `company_id` and `row` fields
    carry the actual data.
    """
    if not company_id:
        return None
    name = suggest_contacts.name_key(row)
    if name is None:
        return None
    first, last = name
    return f"{company_id}{KEY_SEPARATOR}{first}{NAME_SEPARATOR}{last}"


def build_entry(row, reason_code, reason, run_id, company_id, provenance=None) -> dict:
    """One declined person's entry, ready to merge into the map `save()` expects.
    `recorded_at` lives on the ENTRY, never the document -- re-saving an unchanged map
    is therefore byte-identical (no document-level timestamp to drift)."""
    return {
        "reason_code": reason_code,
        "reason": reason,
        "run_id": run_id,
        "company_id": str(company_id),
        "row": {key: row[key] for key in ROW_FIELD_ALLOWLIST if key in row},
        "provenance": dict(provenance or {}),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def first_refusal(key, entry):
    """A human sentence naming what is wrong with persisting `key`/`entry`, or `None`
    when it is safe. Checks, in order: the key is forbidden-shaped; `entry` is not a
    dict; `reason_code` is not in `suggest_contacts.PARTITION_REASON_CODES`; `run_id`
    is not a non-empty string; a forbidden-shaped marker anywhere in `row`,
    `provenance`, or `reason`.

    PUBLIC because the caller pre-checks with it (see plan 02) so one odd company name
    cannot cost a whole batch's save.
    """
    if _looks_forbidden(key):
        return (
            f"refusing to persist a suggestion-decline entry keyed {key!r} -- its "
            "name suggests an arming grant, a live-write permission, a secret, or an "
            "API key. Nothing was written."
        )
    if not isinstance(entry, dict):
        return f"entry for key {key!r} is not a dict. Nothing was written."

    reason_code = entry.get("reason_code")
    if reason_code not in suggest_contacts.PARTITION_REASON_CODES:
        return (
            f"entry {key!r} carries reason_code {reason_code!r}, which is not one of "
            "suggest_contacts.PARTITION_REASON_CODES. Nothing was written."
        )

    run_id = entry.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return (
            f"entry {key!r} carries run_id {run_id!r}, which is not a non-empty "
            "string. Nothing was written."
        )

    offender = _first_forbidden(entry.get("row"))
    if offender is None:
        offender = _first_forbidden(entry.get("provenance"))
    if offender is None and _looks_forbidden(entry.get("reason") or ""):
        offender = entry.get("reason")
    if offender is not None:
        return (
            f"refusing to persist a suggestion-decline entry for {key!r} -- "
            f"{offender!r} suggests an arming grant, a live-write permission, a "
            "secret, or an API key. Nothing was written."
        )
    return None


def save(entries, path=None) -> None:
    """Persist the WHOLE current set of decline entries -- mirrors `held_queue.save`'s
    contract: the caller assembles the full `{key: entry}` map (typically `load()`'s
    own return, with this run's new/updated entries merged in) and this function
    overwrites the file atomically. Validates every entry BEFORE anything is written,
    so a save that raises leaves the previous document untouched.

    No `run_id` argument here (unlike `held_queue.save`) -- D-69-03 means run scope
    lives on each entry, not the document, so there is nothing document-level to
    stamp. Serialised with `sort_keys=True, ensure_ascii=False` so identical content
    always serialises to identical bytes -- re-saving the same map twice, or draining
    nothing, must not perturb the file.
    """
    for key, entry in entries.items():
        refusal = first_refusal(key, entry)
        if refusal is not None:
            raise SuggestionDeclineError(refusal)

    target = Path(path) if path is not None else queue_path()
    document = {ENTRIES_FIELD: dict(entries)}
    durable_paths._atomic_write_0600(
        target, json.dumps(document, sort_keys=True, ensure_ascii=False)
    )


def _validated_entries(document):
    """`entries`, or `None` when `document` fails the usability check -- shared by
    `load()` and `classify_read()` (Task 3) so both agree on what "usable" means."""
    if not isinstance(document, dict):
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, dict):
        return None
    for key, entry in entries.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            return None
        if entry.get("reason_code") not in suggest_contacts.PARTITION_REASON_CODES:
            return None
        run_id = entry.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            return None
    return entries


def load(path=None) -> dict:
    """The `{key: entry}` map, or `{}` when there is nothing usable -- missing,
    unreadable, malformed, or schema-mismatched all degrade to the SAME empty result,
    never a partially-trusted one (mirrors `held_queue.load()`'s own reasoning)."""
    target = Path(path) if path is not None else queue_path()
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = _validated_entries(document)
    return dict(entries) if entries is not None else {}
