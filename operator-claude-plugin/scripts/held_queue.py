"""operator-claude-plugin/scripts/held_queue.py

The plugin's FOURTH persisted artifact (`artifact_store.py` first, `run_manifest.py`
second, `written_records.py` third). AFTER-02 needs held and confidence-held rows to
survive the session, and neither existing store can carry them: `run_manifest.py`
holds verdict WORDS and refuses widening its schema by design, and a never-landed row
has no HubSpot record to flag (`written_records.py` is write-outcome only). So this is
a THIRD durable artifact, written the way `run_manifest.py` was written, for the same
reasons its own docstring gives — a store that accepts arbitrary keys becomes a
general-purpose store one commit later.

**Schema.** A run id, a timestamp, and `entries`: a map of `row_id -> entry`, where an
entry carries:
  - `hold_code` — one of `confidence.ALL_HOLD_CODES`, the closed vocabulary.
  - `reason` — the human sentence `confidence.assess()` produced.
  - `observed_signals` — REVIEW-FACING context (which field disagreed, which providers
    disagreed about it) — what the end-of-run review pass shows the operator.
  - `resume_fingerprint` — the RESUME-FACING comparison key (see `fingerprint()`).
  - `row` — an ALLOWLISTED snapshot of the row (see `ROW_FIELD_ALLOWLIST`), enough to
    re-send it.
  - `status` — OPTIONAL, added by quick 260911-w6p (F2-2). `{"verb", "at", "run_id"}`
    once an operator has recorded a decision (`create`/`skip`/`retry`/`drop`); absent
    means undecided, which is what every entry saved before this widening still is.
    A deliberate entry-schema widening under the 2026-09-11 F2 ruling, cited by
    date, not drift — this module's own standing warning is that a store which
    accepts arbitrary keys becomes a general-purpose store one commit later, and
    this key is closed-vocabulary and validated on both the read and the write side
    precisely so it is not that. See `record_verb()`/`entry_verb()`/`is_settled()`/
    `open_entries()`.

**Facets are a READ, never a write.** `classify_facet()` (260911-w6p, F2-2) derives one
of `new_person` / `needs_company` / `nothing_found` from an existing `no_match` entry
plus the caller's own resolved company domains. A facet is NEVER persisted and NEVER a
hold code — `confidence.ALL_HOLD_CODES` stays exactly six words; widening it to a
seventh would make a review-time distinction a resume-time one, which is not what this
change does.

`observed_signals` and `resume_fingerprint` are two DIFFERENT fields for two DIFFERENT
consumers — the review pass reads the first, `run_manifest.rows_to_resume` reads the
second — because collapsing them into one field is exactly what cycle-3 review found
broken: hashing the enrichment signals the review pass needs to SHOW made the resume
comparison always-unequal, re-spending provider credit on every resume to reach an
identical hold.

**The fingerprint is PER-`hold_code`.** `fingerprint()` hashes the `hold_code` plus
ONLY the two of the outcome contract's five signals a resume's FREE MATCH PASS (zero
provider credit, `preingest.fetch_matches` with an empty provider list) can itself
re-derive: `match_tier` and `candidate_count`. Every other signal (per-field provider
agreement, conflict group names, adjudicated field names) is excluded because the free
match pass cannot observe it AT ALL — hashing it would make the comparison
always-unequal, which is the exact money bug this module exists to prevent for every
enrichment-stage hold. `confidence.ENRICHMENT_STAGE_HOLD_CODES` names the one hold code
this consequence actually applies to; every other code holds on a match-stage signal
that a resume CAN observe changing, so re-inclusion there is a real, working comparison.

**The read path classifies before it degrades** (REVIEW-C11). `classify_read()` is a
PROBE over the raw file, returning `"absent"`, `"parseable"`, `"anomalous"`, or
`"another_run"` — four states `load()`'s own return value cannot carry by design (it
degrades every anomaly to the SAME empty result, mirroring `run_manifest.load()`'s own
reasoning: a partially-trusted queue is worse than an empty one, because presenting an
empty review pass over an unreadable file tells the operator the batch had nothing to
look at, when held rows may in fact exist and are not shown). The two consumers get two
different sentences from the SAME read: the resume path (`load()`) keeps degrade-whole
unchanged; the review pass (`classify_read()`) can say WHICH of the four it saw.

**Write order relative to `run_manifest.py`** (REVIEW-07's other half): the QUEUE entry
is written FIRST, the MANIFEST verdict (`run_manifest.CONFIDENCE_HELD`) SECOND. A crash
between them leaves a queue entry for a row the manifest does not mention — an
unmentioned row is simply re-run on the next resume, the safe direction (a duplicate
provider call, never a dropped contact). The reverse order would mark a row held with
nothing recorded to review, which is the silent-drop this whole plan exists to prevent.
This module does not enforce the order itself (there is no single call that does both
writes) — the two `save()` calls are made by the caller, in this order, and
`test_held_queue.py` asserts the outcome of that ordering directly.

**Row content and the allowlist** (REVIEW-A7). A re-send needs the row's original
specification — a bare `row_id` cannot rebuild a request — but only the identity keys
and the columns the envelope projects, never whatever else happened to be in the
operator's spreadsheet. `ROW_FIELD_ALLOWLIST` used to mirror `enrichment.
MATCH_LOOKUP_KEYS` exactly (`row_id` + the five match keys); quick 260911-w6o widened
it to 11 names — `row_id` + `MATCH_LOOKUP_KEYS` + `jobtitle`, `phone`, `company_id`
(the `suggestion_declines.py` precedent, equal to `extraction.canonical_props()`) +
`mobilephone`, `lv_linkedin_url` (what the waterfall promotes for a mobile and a
LinkedIn, `preingest.promotable_contact_props()`) — because a held entry used to
carry only the operator's spreadsheet line, discarding everything the waterfall
found for it (F2-1: a 7-credit Lusha reveal thrown away at the persist boundary). It
is still a CLOSED, enumerated tuple, never `extraction.canonical_props()` or
`preingest.promotable_contact_props()` imported directly (a cycle with `preingest`,
which imports this module). The forbidden-name scan below is a SECOND line, not the
first — it targets grants, secrets, and tokens; the allowlist is what actually keeps
an arbitrary spreadsheet column off disk. As of 260911-w6o that scan targets KEY
NAMES only for `row` (see `save()`'s call site) — `observed_signals`, `reason`, and
`row_id` keep full key-and-value scanning, unchanged.

Carries `run_manifest.py`'s Phase 23 D-11 forbidden-name refusal verbatim in substance
(reimplemented, not imported — the same discipline `written_records.py` already
applies to this same list, so a future change to one cannot silently weaken another):
the arming grant exists as a call argument for one turn and must never be readable off
disk on a later run.

Writes through `durable_paths._atomic_write_0600`; the filename is deliberately not a
dotfile (Phase 23 D-04). ONE GLOBAL FILE, never one per run (unlike
`written_records.py`) — "held rows collect into ONE review queue, cleared in a single
pass" (D-61-07) is a promise about a single durable backlog, not a per-run artifact; an
entry from an earlier run stays in the queue until an operator's review clears it,
across however many later runs happen in between.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import confidence
import durable_paths
import enrichment

QUEUE_FILENAME = "held_queue.json"

# The whole document schema. Anything else is a rejection, not a widening.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
ENTRIES_FIELD = "entries"

# REVIEW-A7, widened by quick 260911-w6o (F2-1): identity keys + the columns the
# envelope projects, and nothing else -- still a CLOSED, enumerated tuple. Enumerated
# rather than derived from `extraction.canonical_props()` / `preingest.
# promotable_contact_props()` on purpose: `preingest` imports `held_queue` (a cycle),
# and `extraction._load_mapping` raises when the column mapping is unresolvable,
# which would turn an importable module into an unimportable one. `jobtitle`,
# `phone`, `company_id` mirror `suggestion_declines.ROW_FIELD_ALLOWLIST` verbatim;
# `mobilephone` and `lv_linkedin_url` are the waterfall's own promoted keys for a
# mobile and a LinkedIn. Deliberately NOT admitted: `seniority`, `lv_persona_group`,
# and the five location keys -- none is named in F2-1, none is needed by a create,
# and each is PII this store would then hold with no consumer.
ROW_FIELD_ALLOWLIST = ("row_id",) + enrichment.MATCH_LOOKUP_KEYS + (
    "jobtitle", "phone", "company_id", "mobilephone", "lv_linkedin_url",
)

# Phase 23 D-11, reimplemented (not imported) per `run_manifest.py`'s own precedent.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

# quick 260911-any: whole-token matching, not raw substring — see
# `run_manifest.py`'s matching block for the shared rationale, reimplemented fresh
# here per this module's own anti-DRY discipline.
_CAMEL_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_TOKEN = re.compile(r"[^a-z0-9]+")
_INFLECTION_SUFFIXES = ("", "s", "ed", "ing")


def _tokenised(value) -> str:
    """`value`, camel-broken, lowercased, and split into a padded, space-joined run
    of tokens (e.g. `" armed row "`) — the shape a marker is matched against."""
    broken = _CAMEL_BREAK.sub(" ", str(value)).lower()
    tokens = [token for token in _NON_TOKEN.split(broken) if token]
    return f" {' '.join(tokens)} "


_FORBIDDEN_TOKEN_RUNS = tuple(
    _tokenised(marker).rstrip() + suffix + " "
    for marker in _FORBIDDEN_NAME_MARKERS
    for suffix in _INFLECTION_SUFFIXES
)

# classify_read()'s four answers (REVIEW-C11).
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"
ANOTHER_RUN = "another_run"

# classify_facet()'s three answers (260911-w6p, F2-2) — a READ over a `no_match` hold,
# never persisted, never a fourth member of `confidence.ALL_HOLD_CODES`.
FACET_NEW_PERSON = "new_person"
FACET_NEEDS_COMPANY = "needs_company"
FACET_NOTHING_FOUND = "nothing_found"
ALL_FACETS = frozenset({FACET_NEW_PERSON, FACET_NEEDS_COMPANY, FACET_NOTHING_FOUND})

# The four durable verbs an operator can record against a held entry (260911-w6p,
# F2-2). `retry` is deliberately not in SETTLED_VERBS — see `is_settled()`.
VERB_CREATE = "create"
VERB_SKIP = "skip"
VERB_RETRY = "retry"
VERB_DROP = "drop"
ALL_VERBS = frozenset({VERB_CREATE, VERB_SKIP, VERB_RETRY, VERB_DROP})
SETTLED_VERBS = frozenset({VERB_CREATE, VERB_SKIP, VERB_DROP})
STATUS_FIELD = "status"


class HeldQueueError(Exception):
    """Raised when an entry cannot be persisted safely — a `hold_code` outside
    `confidence.ALL_HOLD_CODES`, or a key/value whose name suggests an arming grant, a
    live-write permission, a secret, or an API key (Phase 23 D-11, see module
    docstring). Nothing is written when this raises."""


def _looks_forbidden(value) -> bool:
    tokenised = _tokenised(value)
    return any(run in tokenised for run in _FORBIDDEN_TOKEN_RUNS)


def _first_forbidden(value):
    """Recursively scans keys and string leaves of an already-built entry's `row` /
    `observed_signals` payload for a forbidden-shaped name — returns the offending
    string, or `None`. The allowlist (`ROW_FIELD_ALLOWLIST`) is the first line; this is
    the second, belt-and-braces check `run_manifest.py`'s own docstring describes."""
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
    quick 260911-w6o's narrowing of the `row` payload's own scan. Safe only because
    `_allowlisted_row` already filters `row` to a closed, enumerated tuple before this
    runs (see `save()`'s call site) -- a forbidden-shaped KEY can never reach `row`
    through `build_entry` at all, so this scan's only live effect there was refusing
    VALUES: a person's own name, a company's own name, an email. Deliberately does
    NOT call `_first_forbidden` for the value case; `run_report.
    _looks_forbidden_value` is the shipped precedent for a key matcher and a value
    matcher legitimately differing."""
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
    """Resolved fresh on every call — the same durable directory
    `run_manifest.manifest_path()` and `artifact_store.state_path()` both resolve into,
    never a second resolution rule."""
    return durable_paths.resolve_state_path().parent / QUEUE_FILENAME


def fingerprint(hold_code, outcome) -> str:
    """The resume-time comparison key. Hashes EXACTLY `hold_code`, `outcome.match_tier`,
    and `outcome.candidate_count` — see module docstring for why every other signal is
    deliberately excluded. `outcome` is `preingest.Outcome` or anything exposing those
    two attributes; an `UNPARSEABLE_OUTCOME` (both attributes `None`) is inside this
    function's normal domain, not a special case — it simply hashes to a value that
    stays identical across resumes for as long as the row stays unparseable.
    """
    payload = json.dumps(
        {"hold_code": hold_code, "match_tier": outcome.match_tier,
         "candidate_count": outcome.candidate_count},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _allowlisted_row(row) -> dict:
    return {key: row[key] for key in ROW_FIELD_ALLOWLIST if key in row}


def build_entry(row, hold_code, reason, outcome, observed_signals=None) -> dict:
    """One held row's queue entry, ready to hand to `save()` (merged into the map
    `save()` expects: `{row_id: entry, ...}`)."""
    return {
        "hold_code": hold_code,
        "reason": reason,
        "observed_signals": dict(observed_signals or {}),
        "resume_fingerprint": fingerprint(hold_code, outcome),
        "row": _allowlisted_row(row),
    }


def classify_facet(entry, known_company_domains=frozenset()):
    """Read-time facet over a `no_match` hold (260911-w6p, F2-2). `confidence.
    HOLD_NO_MATCH` conflates two situations the operator answers with two different
    verbs — a provider NOT_FOUND at a company that is not in HubSpot, and a rich
    reveal of a real new person at a company that IS. This function separates them
    WITHOUT adding a fourth hold code: it is a pure read over an already-persisted
    entry, never written back, never validated by `save()`/`load()`.

    `entry` is one `held_queue.json` entry (the value half of the `{row_id: entry}`
    map). Returns `None` for anything that is not a `no_match` hold — a conflict hold
    keeps its own approve/reject lane, and this function only ever answers for
    `no_match`, so the facet vocabulary can never grow into a second hold vocabulary.

    `known_company_domains` is an ARGUMENT, not a lookup this function performs
    itself: the entry alone cannot tell the two situations apart (both carry a
    company NAME and an email at a domain built from that name, and nothing in the
    entry, the merged row, or the propose-lane response records whether the company
    already exists in HubSpot). The caller resolves the domains (a HubSpot read, or
    the run's own knowledge) and passes them in; this function stays pure — no
    network, no config read, no clock. WITH THE DEFAULT EMPTY SET nothing is ever
    `new_person` — a caller that resolves no domains gets `needs_company` for every
    usable-email entry, the safe, review-first direction.

    Decision table, read top to bottom, first match wins, TOTAL (mirrors
    `confidence.assess`'s own shape):

      0. `entry` is not a dict, or its `hold_code` is not `confidence.HOLD_NO_MATCH`
         -> `None`.
      1. No usable email -> `FACET_NOTHING_FOUND`. Usable means: `entry["row"]` is a
         dict carrying an `email` that strips to non-empty, splits on exactly one `@`
         into a non-empty local part and a non-empty host, that host survives
         `enrichment._clean_domain` (imported, never re-implemented — one guard,
         mirrored in `n8n/code/companyLink.js`), and the cleaned host is not in
         `enrichment.FREEMAIL_DOMAINS`. This row also absorbs every malformed shape
         `load()` already lets through — a missing or non-dict `row`, a non-string
         `email` — so this function answers rather than raising on an entry the store
         already considered valid.
      2. The cleaned host is in `known_company_domains` (each supplied value
         normalized through the SAME `_clean_domain` before comparison, so a caller
         passing a URL or a `www.` host still matches) -> `FACET_NEW_PERSON`.
      3. Terminal, everything else -> `FACET_NEEDS_COMPANY`. Covers both a blank
         company column and a company HubSpot does not hold, deliberately: in both
         the operator's next move is the same one — create the company.

    Two derivation choices, recorded here rather than re-derived by a later reader:
      - The row's own `company` NAME string is never consulted. The ruling says "at
        the company's own domain"; the recorded entries prove a name check cannot
        separate the two cases anyway (`Atherton Turf Club` -> `athertonturfclub.
        com.au` and `Australian Turf Club` -> `australianturfclub.com.au` are the
        same shape), and `known_company_domains` already IS the statement that the
        company is present.
      - Freemail/ISP addresses land in `nothing_found` conservatively. It is not a
        claim the person can never be created (§13.0.1's ingest lane can still
        resolve a company by exact name) — it is a claim that this queue has no
        address worth pre-suggesting a create with. A fourth facet is outside the
        ruling.
    """
    if not isinstance(entry, dict) or entry.get("hold_code") != confidence.HOLD_NO_MATCH:
        return None

    row = entry.get("row")
    email = row.get("email") if isinstance(row, dict) else None
    if not isinstance(email, str):
        return FACET_NOTHING_FOUND

    email = email.strip()
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return FACET_NOTHING_FOUND

    cleaned = enrichment._clean_domain(parts[1])
    if not cleaned or cleaned in enrichment.FREEMAIL_DOMAINS:
        return FACET_NOTHING_FOUND

    known_cleaned = {enrichment._clean_domain(d) for d in known_company_domains}
    if cleaned in known_cleaned:
        return FACET_NEW_PERSON

    return FACET_NEEDS_COMPANY


def entry_verb(entry):
    """The verb recorded against `entry`, or `None` — tolerant of a non-dict `entry`
    and a non-dict `status`, so a reader never has to guard the shape itself."""
    if not isinstance(entry, dict):
        return None
    status = entry.get(STATUS_FIELD)
    if not isinstance(status, dict):
        return None
    verb = status.get("verb")
    return verb if verb in ALL_VERBS else None


def is_settled(entry) -> bool:
    """`True` when `entry` carries one of the three SETTLED verbs (`create`, `skip`,
    `drop`). `retry` is deliberately NOT settled — it is the operator asking to look
    again, the same disposition `rows_to_resume` already gives `unchecked`."""
    return entry_verb(entry) in SETTLED_VERBS


def open_entries(entries: dict) -> dict:
    """The subset of an `{row_id: entry}` map with no settled verb — one filter every
    later report or review table calls, instead of each growing its own."""
    return {row_id: entry for row_id, entry in entries.items() if not is_settled(entry)}


def record_verb(row_id, verb, run_id, path=None) -> dict:
    """Load the current queue, stamp `row_id`'s entry with `verb`/timestamp/`run_id`,
    save, and return the updated `{row_id: entry}` map.

    Refuses — raising `HeldQueueError`, writing nothing — a `verb` outside
    `ALL_VERBS`, a `row_id` the loaded queue does not hold (never silently creating an
    entry with no hold), and a `run_id` that trips the store's existing
    `_looks_forbidden` name check.

    The `run_id` recorded is the one PASSED IN, so the file keeps naming the run that
    LAST TOUCHED it rather than the run that first held the rows. Safe today because
    `held_queue.classify_read()` has exactly one caller (`run_report.py:995`) and it
    passes no `expected_run_id`, so nothing compares the document's run id to an
    expected one — a future caller that does must read this line first.

    None of the four verbs deletes an entry. The memory IS the protection: an entry
    that disappeared on `create` would be re-held identically by the next run that
    meets the same row.
    """
    if verb not in ALL_VERBS:
        raise HeldQueueError(
            f"refusing to record verb {verb!r} against row {row_id!r} — not one of "
            "held_queue.ALL_VERBS. Nothing was written."
        )
    if _looks_forbidden(run_id):
        raise HeldQueueError(
            f"refusing to record a verb under run_id {run_id!r} — its name suggests "
            "an arming grant, a live-write permission, a secret, or an API key. "
            "Nothing was written."
        )

    entries = load(path=path)
    if row_id not in entries:
        raise HeldQueueError(
            f"refusing to record verb {verb!r} — row {row_id!r} is not in the held "
            "queue. Nothing was written."
        )

    entries = dict(entries)
    entry = dict(entries[row_id])
    entry[STATUS_FIELD] = {
        "verb": verb,
        "at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
    }
    entries[row_id] = entry
    save(run_id, entries, path=path)
    return entries


def save(run_id, entries, path=None) -> None:
    """Persist the WHOLE current set of held entries — mirrors `run_manifest.save`'s
    contract exactly: the caller assembles the full `{row_id: entry}` map (typically
    `load()`'s own return, with this run's new/updated entries merged in) and this
    function overwrites the file atomically. Validates every entry BEFORE anything is
    written, so a save that raises leaves the previous queue untouched.
    """
    for row_id, entry in entries.items():
        if _looks_forbidden(row_id):
            raise HeldQueueError(
                f"refusing to persist a held-queue entry keyed {row_id!r} — its name "
                "suggests an arming grant, a live-write permission, a secret, or an "
                "API key. Nothing was written."
            )
        hold_code = entry.get("hold_code") if isinstance(entry, dict) else None
        if hold_code not in confidence.ALL_HOLD_CODES:
            raise HeldQueueError(
                f"row {row_id!r} carries hold_code {hold_code!r}, which is not one of "
                f"confidence.ALL_HOLD_CODES. Nothing was written."
            )
        # 260911-w6p (F2-2): `status` is OPTIONAL; when present, its `verb` must be
        # one of the four closed words. Mirrors the `hold_code` check immediately
        # above — a missing `status` is valid, a present one is vocabulary-checked.
        status = entry.get(STATUS_FIELD) if isinstance(entry, dict) else None
        if status is not None and (
            not isinstance(status, dict) or status.get("verb") not in ALL_VERBS
        ):
            raise HeldQueueError(
                f"row {row_id!r} carries a status whose verb is not one of "
                "held_queue.ALL_VERBS. Nothing was written."
            )
        # quick 260911-w6o: `row` scans KEY NAMES only (widened allowlist now
        # legitimately carries a value like an email or a person's own name that
        # would otherwise trip a marker); `observed_signals`/`reason`/`row_id` keep
        # full key-and-value scanning, unchanged.
        offender = _first_forbidden_key(entry.get("row"))
        if offender is None:
            offender = _first_forbidden(entry.get("observed_signals"))
        if offender is None and _looks_forbidden(entry.get("reason") or ""):
            offender = entry.get("reason")
        if offender is not None:
            raise HeldQueueError(
                f"refusing to persist a held-queue entry for row {row_id!r} — "
                f"{offender!r} suggests an arming grant, a live-write permission, a "
                "secret, or an API key. Nothing was written."
            )

    target = Path(path) if path is not None else queue_path()
    document = {
        RUN_ID_FIELD: run_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        ENTRIES_FIELD: dict(entries),
    }
    durable_paths._atomic_write_0600(target, json.dumps(document))


def _validated_entries(document):
    """`entries`, or `None` when `document` fails the usability check — shared by
    `load()` and `classify_read()` so both agree on what "usable" means."""
    if not isinstance(document, dict):
        return None
    entries = document.get(ENTRIES_FIELD)
    if not isinstance(entries, dict):
        return None
    for row_id, entry in entries.items():
        if not isinstance(row_id, str) or not isinstance(entry, dict):
            return None
        if entry.get("hold_code") not in confidence.ALL_HOLD_CODES:
            return None
        if not isinstance(entry.get("resume_fingerprint"), str):
            return None
        # 260911-w6p (F2-2): mirrors the hold_code check above — status is optional,
        # a present one must be a dict whose verb is in ALL_VERBS, or the whole
        # queue degrades to unusable (never a partially-trusted status).
        status = entry.get(STATUS_FIELD)
        if status is not None and (
            not isinstance(status, dict) or status.get("verb") not in ALL_VERBS
        ):
            return None
    return entries


def load(path=None) -> dict:
    """The `{row_id: entry}` map, or `{}` when there is nothing usable — missing,
    unreadable, malformed, half-written, or schema-mismatched all degrade to the SAME
    empty result, never a partially-trusted one (mirrors `run_manifest.load()`'s own
    reasoning verbatim: a queue that silently drops one bad row is worse than an empty
    one — see `classify_read()` for the review pass's own, more honest answer)."""
    target = Path(path) if path is not None else queue_path()
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = _validated_entries(document)
    return dict(entries) if entries is not None else {}


def classify_read(path=None, expected_run_id=None) -> str:
    """REVIEW-C11: what the review pass says it saw, from a fresh probe over the file —
    `load()`'s return value cannot carry this by design. One of `ABSENT`, `PARSEABLE`,
    `ANOMALOUS`, or `ANOTHER_RUN`. Never raises. Does not change `load()`'s own
    degrade-whole behaviour — a caller still calls `load()` for the actual entries and
    `classify_read()` for the sentence to say about them.
    """
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
    if expected_run_id is not None and document.get(RUN_ID_FIELD) != expected_run_id:
        return ANOTHER_RUN
    return PARSEABLE
