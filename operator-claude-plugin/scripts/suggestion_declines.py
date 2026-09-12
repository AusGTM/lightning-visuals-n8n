"""operator-claude-plugin/scripts/suggestion_declines.py

The plugin's next persisted artifact. A SIBLING of `held_queue.json`, never a section
inside it (D-69-01): it follows every convention `held_queue.py` established --
resolved under `durable_paths.resolve_state_path().parent`, written with
`durable_paths._atomic_write_0600`, whole-document overwrite, validate-every-entry
before anything is written, the secret/grant-name refusal (`_looks_forbidden`), and a
`classify_read`-style reader.

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
"another run" state at the document level -- `classify_read` returns one of
three answers, not `held_queue`'s four.

**The forbidden-name refusal is REIMPLEMENTED, not imported**, per `held_queue.py`'s
own stated discipline (held_queue.py:68-70) -- a future change to one cannot silently
weaken another. This is the third instance of the same discipline in this plugin
(`held_queue.py`'s own copy of `run_manifest.py`'s being the second).

# ponytail: whole-document overwrite, last writer wins, no lock -- single-operator
# assumption inherited from every sibling store in this plugin. Per-key locking only
# if two operators ever share one durable directory on one machine.

# `first_refusal` below is PUBLIC: the caller pre-checks with it and reports the one
# entry it cannot store rather than losing a whole batch's save to it -- still the
# right shape after quick 260911-any's whole-token matching fix, since a genuinely
# forbidden-shaped marker still costs one decline its own storage.
"""
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import durable_paths
import enrichment
import extraction
import suggest_contacts

QUEUE_FILENAME = "suggestion_declines.json"
ENTRIES_FIELD = "entries"
KEY_SEPARATOR = "::"
NAME_SEPARATOR = "|"

# Deliberately NOT `held_queue.ROW_FIELD_ALLOWLIST` and deliberately excluding
# `row_id` (D-69-04; `preingest.build_rows_spec` also refuses a row that already
# carries one). Equals `extraction.canonical_props()` exactly -- pinned by test.
# Phase 72 Plan 01 (D-72-03): `mobilephone` split off the `phone` alias group into its
# own canonical target -- added here to keep this literal equal to canonical_props().
# Phase 72 Plan 02 (D-72-01): the remaining six promotable_contact_props() keys added
# too -- same reason, keep this literal equal to canonical_props() as it widens.
ROW_FIELD_ALLOWLIST = enrichment.MATCH_LOOKUP_KEYS + (
    "jobtitle", "phone", "mobilephone", "company_id",
    "city", "state", "country", "hs_state_code", "hs_country_region_code",
    "seniority", "lv_persona_group",
)

# Reimplemented (not imported) per `held_queue.py:101-144`'s own precedent.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

# quick 260911-any: whole-token matching, not raw substring -- reimplemented fresh
# per this module's own anti-DRY discipline (see module docstring).
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

# The read-classification vocabulary (`classify_read`, below). No ANOTHER_RUN:
# D-69-03 makes the whole document multi-run by design, so there is no "wrong run" to
# detect at the document level -- an individual entry's own `run_id` is still
# informative and is what `partition_by_run`, below, reads.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"


class SuggestionDeclineError(Exception):
    """Raised when an entry cannot be persisted safely -- a `reason_code` outside
    `suggest_contacts.PARTITION_REASON_CODES`, a missing/empty `run_id`, or a
    key/value whose name suggests an arming grant, a live-write permission, a secret,
    or an API key. Nothing is written when this raises."""


def _looks_forbidden(value) -> bool:
    tokenised = _tokenised(value)
    return any(run in tokenised for run in _FORBIDDEN_TOKEN_RUNS)


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


def _first_forbidden_key(value):
    """Like `_first_forbidden` but scans KEY NAMES only, never string leaf values --
    the identical narrowing `held_queue.py`'s `260911-w6o` change gave `row`'s own
    scan, reimplemented here per this module's own anti-DRY discipline (D-69-01).
    Safe only because `ROW_FIELD_ALLOWLIST` already filters `row` to a closed,
    enumerated tuple before this runs (see `build_entry()`) -- a forbidden-shaped KEY
    can never reach `row` through `build_entry` at all, so this scan's only live
    effect was refusing VALUES: a person's own name, a company's own name, an email
    (Phase 71, D-71-04's own todo fold -- `entry_key` has ALWAYS produced name-shaped
    keys, so this store refuses a decline for a person named Grant today, in
    production, before this change)."""
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden(key):
                return key
            found = _first_forbidden_key(sub)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_forbidden_key(item)
            if found is not None:
                return found
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
    when it is safe. Checks, in order: `entry` is not a dict; the key is
    forbidden-shaped AND is not the entry's own derived identity; `reason_code` is not
    in `suggest_contacts.PARTITION_REASON_CODES`; `run_id` is not a non-empty string;
    a forbidden-shaped marker anywhere in `row`'s KEY NAMES, `provenance`, or `reason`.

    PUBLIC because the caller pre-checks with it (see plan 02) so one odd company name
    cannot cost a whole batch's save.

    Phase 71 (D-71-04's own todo fold): the entries-map KEY is `entry_key(company_id,
    row)` -- a composite of a resolved `company_id` and the row's OWN normalised name
    -- so a person whose normalised firstname is a whole-token marker (e.g. "Grant")
    tripped `_looks_forbidden(key)` unconditionally, in production, before this
    narrowing. The key is exempt from the marker scan EXACTLY when it equals the
    entry's own recomputed `entry_key` -- any other key is an arbitrary
    caller-supplied string and keeps the full refusal. `row`'s own scan is narrowed to
    KEY NAMES ONLY for the identical reason `held_queue.py`'s `260911-w6o` narrowed
    `row`'s scan there -- `ROW_FIELD_ALLOWLIST` already closes the field set, so the
    value scan's only live effect was refusing a person's own name. `provenance` and
    `reason` keep FULL key-and-value scanning, unchanged.
    """
    if not isinstance(entry, dict):
        if _looks_forbidden(key):
            return (
                f"refusing to persist a suggestion-decline entry keyed {key!r} -- its "
                "name suggests an arming grant, a live-write permission, a secret, or "
                "an API key. Nothing was written."
            )
        return f"entry for key {key!r} is not a dict. Nothing was written."

    exempt_key = entry_key(entry.get("company_id"), entry.get("row") or {})
    if key != exempt_key and _looks_forbidden(key):
        return (
            f"refusing to persist a suggestion-decline entry keyed {key!r} -- its "
            "name suggests an arming grant, a live-write permission, a secret, or an "
            "API key. Nothing was written."
        )

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

    offender = _first_forbidden_key(entry.get("row"))
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

    CR-01: refuses outright, before validating a single entry, when a file already
    exists at `target` and reads back `ANOMALOUS` -- this document ACCUMULATES
    (D-69-03), so overwriting it with only whatever the caller happened to read
    before the file went bad would silently discard every earlier run's backlog.
    Every caller (this module's own `load()`-then-`save()` callers included) gets
    this guard for free; nothing here relies on a caller remembering to
    `classify_read()` first.
    """
    target = Path(path) if path is not None else queue_path()
    if target.exists() and classify_read(path=target) == ANOMALOUS:
        raise SuggestionDeclineError(
            f"{target} exists but could not be read cleanly -- refusing to overwrite "
            "it and destroy whatever it currently holds. Report this to the operator "
            "instead of saving; nothing was written."
        )

    for key, entry in entries.items():
        refusal = first_refusal(key, entry)
        if refusal is not None:
            raise SuggestionDeclineError(refusal)

    document = {ENTRIES_FIELD: dict(entries)}
    durable_paths._atomic_write_0600(
        target, json.dumps(document, sort_keys=True, ensure_ascii=False)
    )


def _validated_entries(document):
    """`entries`, or `None` when `document` fails the usability check -- shared by
    `load()` and `classify_read()` so both agree on what "usable" means."""
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


def classify_read(path=None) -> str:
    """What a review pass says it saw, from a fresh probe over the file -- `load()`'s
    return value cannot carry this by design. One of `ABSENT`, `PARSEABLE`,
    `ANOMALOUS`. Never raises. D-69-03 makes the document inherently multi-run, so a
    "wrong run" is not a document-level fact here (contrast `held_queue.classify_read`'s
    `ANOTHER_RUN`) -- an individual entry's own `run_id` is still informative and is
    what `partition_by_run` reads."""
    target = Path(path) if path is not None else queue_path()
    if not target.exists():
        return ABSENT
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ANOMALOUS
    entries = _validated_entries(document)
    if entries is None:
        return ANOMALOUS
    return PARSEABLE


def partition_by_run(entries, run_id):
    """`{"this_run": {...}, "backlog": {...}}`, splitting on each entry's own
    `run_id` -- pure, no I/O. The two halves are disjoint and together equal
    `entries`. `run_id=None` puts everything in `backlog` -- the end-of-round surface
    for a round that never dispatched has no run handle to compare against and must
    not invent one."""
    this_run = {}
    backlog = {}
    for key, entry in entries.items():
        if (
            run_id is not None
            and isinstance(entry, dict)
            and entry.get("run_id") == run_id
        ):
            this_run[key] = entry
        else:
            backlog[key] = entry
    return {"this_run": this_run, "backlog": backlog}


# The four drain actions (D-69-06). `send`/`delete` remove the entry; `defer`/`export`
# leave it untouched.
DRAIN_ACTIONS = ("send", "defer", "delete", "export")


def apply_action(entries, key, action):
    """A NEW dict reflecting one drain decision. `"delete"` and `"send"` remove the
    key; `"defer"` and `"export"` return an equal copy. Raises `SuggestionDeclineError`
    on an action outside `DRAIN_ACTIONS` or a key absent from `entries`.

    Two ceilings, stated plainly: `"send"` is the CALLER's promise that the dispatch
    already succeeded -- this function cannot see a transport and performs no write of
    its own. `"delete"` writes nothing in the entry's place -- no tombstone, no
    suppression key (D-69-07) -- so a later round that rediscovers the same person
    re-queues them.
    """
    if action not in DRAIN_ACTIONS:
        raise SuggestionDeclineError(
            f"action {action!r} is not one of {DRAIN_ACTIONS}. Nothing was changed."
        )
    if key not in entries:
        raise SuggestionDeclineError(
            f"key {key!r} is not in the entries map. Nothing was changed."
        )
    result = dict(entries)
    if action in ("send", "delete"):
        del result[key]
    return result


def export_rows(entries, keys, out_path) -> list[str]:
    """Write one CSV row per `key` in `keys` to `out_path`, ready for the operator to
    fix by hand and feed back through `contact-upload`. Returns the header it wrote
    (`extraction.canonical_props()`, unchanged) so the caller can name the columns to
    the operator.

    Deliberately NOT `extraction.write_dispatch_csv` -- that function raises
    `emailless_row_cannot_ingest` on exactly the rows most declines are (D-69-01: a
    `no_email`/`email_domain_*` decline has no usable email by definition), and the
    header it would refuse to widen is the SAME header this writer uses. The
    difference is the guard, not the shape: `write_dispatch_csv` exists to stop a
    silent HubSpot write with no object id; `export_rows` exists to hand the operator
    an incomplete row THEY will complete before it ever reaches a dispatch. No email
    guard runs here on purpose.

    `company_id` is OVERLAID from the entry's own field onto the row -- never read
    from `entry["row"]`, which may not carry it at all -- so the exported column is
    always what re-associates the contact to the right company on the way back in
    (CLAUDE.md 13.0.1's manual override), even for a row `build_entry` stored before
    any `company_id` key existed on it.

    Never touches `entries` or the file `save()`/`load()` read from -- a copy, never a
    move (D-69-06): the entry stays in the store until it is sent or deleted.
    """
    header = extraction.canonical_props()
    rows = []
    for key in keys:
        if key not in entries:
            raise SuggestionDeclineError(
                f"key {key!r} is not in the entries map. Nothing was written."
            )
        entry = entries[key]
        row = dict(entry.get("row") or {})
        row["company_id"] = entry.get("company_id")
        rows.append(row)

    target = Path(out_path)
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, restval="", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)

    return header
