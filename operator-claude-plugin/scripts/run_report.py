"""operator-claude-plugin/scripts/run_report.py

The plugin's SEVENTH persisted artifact family (`artifact_store.py` first,
`run_manifest.py` second, `written_records.py` third, `held_queue.py` fourth,
`run_state.py` fifth, `remainder_queue.py` sixth). Phase 57 Plan 05 (AFTER-01, AFTER-03's
operator-facing half, G-4's disclosure half): one end-of-run report joining every
durable store a run touches, plus a small per-run record of the facts that would
otherwise die with the process.

**Two halves, added in two tasks.**

Task 1 (this half): `record_audit` / `load_audit` / `classify_audit_read` — a per-run
`run_audit-<run_id>.json` file holding OBSERVATIONS ONLY: the ceiling verdict from grant
time, which provider balances were readable, the disarm result, and any ceiling-stop
metadata. A crashed run loses all four today; this persists them at the moment each is
OBSERVED so a report can be reconstructed after a crash. `record_audit` MERGES into
whatever the file already holds (REVIEW-57-M11) — the ceiling verdict is written at
grant time, the disarm result at the end of the run, and a second call must never erase
the first.

**What must never go in it, said once, here.** These are OBSERVATIONS: a verdict word,
a readability state, a disarm-result word, a chunk index, a count. The GRANT is never
among them — GRANT-06 forbids a grant being persisted or rehydrated, and D-57-05 is
rated one-way. A FRESH, per-module copy of the forbidden-name markers (never imported —
the same deliberate anti-DRY convention `held_queue.py`/`written_records.py`/
`run_manifest.py`/`remainder_queue.py` all document) scans every value passed to
`record_audit` and raises rather than persisting anything grant-shaped.

**The scan is narrowed exactly like `remainder_queue.py`'s (REVIEW-57-M2), with one more
twist this module needs that no sibling does.** A plain leaf-scan against all ten
markers would refuse the module's OWN vocabulary: `disarm`/`disarmed`/`disarm_failed`
all contain the substring `"arm"`, and `write_grant.EXECUTIONS_BASIS` — a real, load-
bearing observation string this module is asked to persist verbatim — contains
`"webhook"`. Both are real facts this record exists to hold, not authority smuggled in
under a data field. So: every KEY, at every depth, is scanned against ALL TEN markers
(a grant, token, or allowlist arrives as a NAMED field, and nothing about "arm" or
"webhook" is a legitimate KEY name inside an audit record). A scalar string VALUE is
scanned against the eight markers that exclude `"arm"` and `"webhook"` — the two
markers whose value-position false positives are this module's own everyday
vocabulary — so a value shaped like a real grant, secret, token, or credential still
raises, while "disarmed" and the executions-basis sentence do not. The four top-level
call arguments (`ceiling`, `balances`, `disarm`, `ceiling_stop`) are treated as SCHEMA,
never scanned as data themselves — `record_audit(run_id, disarm=...)` must not refuse
on its own parameter name containing "arm".

**The audit record is itself a durable input** (REVIEW-57-M4): `run_audit-<run_id>.json`
can be absent, malformed, or another run's exactly as the five primary stores can.
`classify_audit_read` mirrors `written_records.classify_read`/`run_manifest.classify_read`
exactly — same four words, same never-raise contract — so an unreadable audit record
degrades to a named `gaps` entry rather than silently reading as "no ceiling verdict was
observed".

Writes through `durable_paths._atomic_write_0600`, mirrors the pytest-safety guard
`written_records.py`/`remainder_queue.py` both carry (`_refuses_real_durable_write_under_pytest`):
a test that forgets to patch `run_audit_path` must never decorate the operator's real
durable directory.

Task 2 adds `build_run_report` — the join over the five primary stores plus this record.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import artifact_store
import chunking
import durable_paths
import held_queue
import remainder_queue
import run_manifest
import run_state
import write_grant
import written_records

# The whole document schema. Anything else is a rejection, not a widening.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
FACTS_FIELD = "facts"

# classify_audit_read()'s four answers — the same contract as
# written_records.classify_read / run_manifest.classify_read / held_queue.classify_read.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"
ANOTHER_RUN = "another_run"

# Phase 23 D-11, reimplemented fresh (not imported) — see module docstring. Scanning
# KEYS at every depth uses all ten; scanning scalar VALUES excludes "arm" and "webhook"
# (this module's own vocabulary: a standalone "armed"/"disarmed" observation and
# EXECUTIONS_BASIS's "webhook execution" text are real observations, never authority).
# quick 260911-any: both sets are now matched as whole TOKENS, not raw substrings —
# see `_tokenised`/`_looks_forbidden_key`/`_looks_forbidden_value` below. Neither
# set's membership changed.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)
_VALUE_MARKERS = tuple(m for m in _FORBIDDEN_NAME_MARKERS if m not in ("arm", "webhook"))

# quick 260911-any: whole-token matching, not raw substring — reimplemented fresh per
# this module's own anti-DRY discipline.
_CAMEL_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_TOKEN = re.compile(r"[^a-z0-9]+")
_INFLECTION_SUFFIXES = ("", "s", "ed", "ing")


def _tokenised(value) -> str:
    """`value`, camel-broken, lowercased, and split into a padded, space-joined run
    of tokens (e.g. `" armed row "`) — the shape a marker is matched against."""
    broken = _CAMEL_BREAK.sub(" ", str(value)).lower()
    tokens = [token for token in _NON_TOKEN.split(broken) if token]
    return f" {' '.join(tokens)} "


def _token_runs(markers):
    return tuple(
        _tokenised(marker).rstrip() + suffix + " "
        for marker in markers
        for suffix in _INFLECTION_SUFFIXES
    )


_FORBIDDEN_TOKEN_RUNS = _token_runs(_FORBIDDEN_NAME_MARKERS)
_VALUE_TOKEN_RUNS = _token_runs(_VALUE_MARKERS)

# The four observation fields `record_audit` accepts. Schema, not data — never fed
# through the forbidden-name scan under their OWN names ("disarm" contains "arm").
_AUDIT_FIELDS = ("ceiling", "balances", "disarm", "ceiling_stop")


class RunReportError(Exception):
    """Raised when an audit observation cannot be persisted safely — a key or value
    anywhere in it whose name suggests an arming grant, a live-write permission, a
    secret, an API key, a webhook, or a credential (Phase 23 D-11 / GRANT-06 /
    D-57-05). Nothing is written when this raises."""


def _looks_forbidden_key(name) -> bool:
    tokenised = _tokenised(name)
    return any(run in tokenised for run in _FORBIDDEN_TOKEN_RUNS)


def _looks_forbidden_value(value) -> bool:
    tokenised = _tokenised(value)
    return any(run in tokenised for run in _VALUE_TOKEN_RUNS)


def _first_forbidden(value):
    """Recursively scans keys (all ten markers) and scalar string leaves (the eight
    value markers) at every depth of an already-built observation payload. Returns the
    offending name, or `None`. See module docstring for why keys and values use
    different marker sets."""
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden_key(key):
                return key
            found = _first_forbidden(sub)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_forbidden(item)
            if found is not None:
                return found
    elif isinstance(value, str) and _looks_forbidden_value(value):
        return value
    return None


def run_audit_path(run_id) -> Path:
    """Where ONE run's audit record lives — resolved fresh on every call, the same
    durable directory every sibling store resolves into, never a second resolution
    rule. Keyed by `run_id`, one file per run, mirroring every other per-run artifact
    in this family."""
    return durable_paths.resolve_state_path().parent / f"run_audit-{run_id}.json"


def report_path(run_id) -> Path:
    """Where ONE run's rendered end-of-run report block lives — F3 (gap-closure
    2026-09-09): SKILL.md step 9's own fence was pure prose at the render step
    ("Render `report["block"]` to the operator verbatim"), so the block existed only
    as a Python return value with nothing persisting it. Resolved fresh, same durable
    directory as every sibling artifact, one `.md` file per run, mirroring
    `run_audit_path`'s own convention."""
    return durable_paths.resolve_state_path().parent / f"run_report-{run_id}.md"


def _persist_report(run_id, block, path=None) -> bool:
    """Persist the rendered block verbatim — makes "was this report actually shown"
    a file-existence check instead of a memory of chat scrollback. Never raises:
    mirrors every sibling store's degrade-on-I/O-failure contract (D-59-10's same
    posture) — a persistence miss must never make `build_run_report`'s own
    never-raise promise a lie, and must never withhold the in-memory report from the
    caller. Called for BOTH the happy path and the internal-error degrade path, so a
    crash mid-build still leaves something durable naming that this run's report was
    incomplete."""
    target = Path(path) if path is not None else report_path(run_id)
    if _refuses_real_durable_write_under_pytest(target):
        return False
    try:
        durable_paths._atomic_write_0600(target, block)
        return True
    except OSError:
        return False


# =========================================================================================
# F2 (uat-batch-review-row-reads-failed, gap-closure 2026-09-09): nothing pruned the
# durable directory — 393 files / 1.5 MB after one week, 362 of them 155-byte
# `run_state-*.json` files, one per `run_state.new_run_id()` including every
# offline/preview run that never dispatched. Not a space problem for years at this
# growth rate, but a LISTING problem now: the end-of-run report and any `glob` over the
# directory walk hundreds of dead files. `artifact_store`'s `dashboard_artifact_ttl_days`
# was the only TTL anywhere, and it covers exactly one file.
#
# Lives HERE, not in `durable_paths.py` (the design's original, more obvious home):
# `test_sweep_read_only.py` statically verifies the unattended sweep's own module
# import closure (`config_gate` -> `durable_paths`, among others) never reaches a
# function that performs a filesystem WRITE — `durable_paths.py`'s own writes are
# confined, by that test, to exactly `_atomic_write_0600`/`_migrate_once`. A pruner
# that deletes files is a write. `run_report.py` is NOT in the sweep's reachable
# closure (it already imports `write_grant`, `chunking`, and every store this file
# reads/writes, none of which the sweep can reach either), so this is where a new
# write-capable function is safe to add.
# =========================================================================================

# `run_state-*` carries only dispatched row ids for resume, and a resume attempted
# after this many days re-runs everything anyway (Phase 61) — nothing is lost by
# deleting it sooner than the longer TTL below.
PRUNE_SHORT_TTL_DAYS = 7

# One glob pattern per per-run artifact family, paired with which TTL applies.
# `run_manifest-*.json`/`written_records-*.json` never match the BARE
# `run_manifest.json`/`written_records.json` (no run id) — those are a different,
# standing/legacy store this function must never touch (see `PRUNE_NEVER` below).
# `run_report-*.md` is this same module's own artifact, added to the family it was
# born into.
_PRUNE_SHORT_TTL_GLOBS = ("run_state-*.json", "match_state-*.json")
_PRUNE_LONG_TTL_GLOBS = (
    "written_records-*.json", "run_audit-*.json", "run_manifest-*.json",
    "run_report-*.md",
)

# Never pruned, named explicitly rather than "everything not otherwise matched" — a
# glob widened later must not silently start deleting one of these. `held_queue.json`
# and `suggestion_declines.json` carry no run attribution at all (global backlogs);
# `operator.local.json` (and its `.example`/any backup) is the plugin's own config,
# never a per-run artifact.
PRUNE_NEVER = ("held_queue.json", "suggestion_declines.json")
PRUNE_NEVER_PREFIXES = ("operator.local.json",)


def prune_durable_state(config=None, now=None) -> list:
    """Delete durable per-run artifacts past their TTL. Returns the list of file
    NAMES actually deleted (never a `Path`, so a caller can print them without
    leaking the operator's home directory) — empty when nothing was due, never
    `None`. Never raises: an unreadable or undeletable file is skipped and pruning
    continues with the rest, the same degrade-not-halt posture every sibling
    durable-store writer in this plugin follows (D-59-10).

    Run at the START of a round, never mid-run — deleting a file a live dispatch is
    about to append to would corrupt the partial-run guarantee
    (`written_records.append_chunk`'s own D-59-07 contract) these files exist for.

    Two TTL families, both measured from the file's own MTIME — not a `saved_at`
    field parsed from its content. Uniform across every JSON store AND the
    plain-text `run_report-*.md` (which carries no such field at all), and immune to
    any clock skew between an embedded timestamp and the actual write:
      - `run_state-*.json` / `match_state-*.json`: `PRUNE_SHORT_TTL_DAYS` (7) — both
        within-round working files, never a durable outcome record.
      - `written_records-*.json` / `run_audit-*.json` / `run_manifest-*.json` /
        `run_report-*.md`: `artifact_store.TTL_CONFIG_KEY`
        (`dashboard_artifact_ttl_days`, default 30, reused rather than a second key) —
        the end-of-run report for a run this old has been read, or never will be.

    `held_queue.json`, `suggestion_declines.json`, `operator.local.json` (and any
    sibling starting with that name) are never touched — see `PRUNE_NEVER`/
    `PRUNE_NEVER_PREFIXES`.
    """
    now = now or datetime.now(timezone.utc)
    directory = durable_paths.resolve_state_path().parent
    short_ttl = timedelta(days=PRUNE_SHORT_TTL_DAYS)
    long_ttl = artifact_store._ttl(config)  # `_ttl(None)` already falls back to DEFAULT_TTL_DAYS

    deleted = []
    for globs, ttl in ((_PRUNE_SHORT_TTL_GLOBS, short_ttl), (_PRUNE_LONG_TTL_GLOBS, long_ttl)):
        for pattern in globs:
            try:
                matches = sorted(directory.glob(pattern))
            except OSError:
                continue
            for path in matches:
                if path.name in PRUNE_NEVER or path.name.startswith(PRUNE_NEVER_PREFIXES):
                    continue  # unreachable given the glob patterns above; a second,
                              # independent guard rather than trusting glob alone.
                try:
                    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                    if now - mtime < ttl:
                        continue
                    path.unlink()
                except OSError:
                    continue
                deleted.append(path.name)

    return deleted


def _refuses_real_durable_write_under_pytest(target: Path) -> bool:
    """Mirrored verbatim from `written_records.py`/`remainder_queue.py`'s own guard: if
    `run_audit_path` resolves into the operator's REAL durable directory while running
    under pytest — because nothing patched it for this test — refuse the write rather
    than decorate the operator's live state with test artifacts."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        return target.resolve().parent == durable_paths.durable_dir().resolve()
    except OSError:
        return False


def _read_document(target: Path):
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def record_audit(run_id, *, ceiling=None, balances=None, disarm=None,
                  ceiling_stop=None, path=None) -> bool:
    """Persist whichever of the four ephemeral observations this call is carrying,
    MERGED into whatever `run_id`'s audit record already holds — never a replace
    (REVIEW-57-M11). Only the keyword arguments actually supplied (non-`None`) are
    merged in; a caller that observes the ceiling at grant time and the disarm result
    at the end of the run makes two calls, and both survive.

    Raises `RunReportError` (nothing written) on any forbidden-shaped key or value
    anywhere in `ceiling`/`balances`/`disarm`/`ceiling_stop` — see module docstring for
    exactly which markers apply to a key and which to a value.

    Returns `True` on a successful write, `False` (never raises) on an I/O failure —
    this is called from the same live dispatch paths the other bookkeeping writes are,
    and must never halt a run over a bookkeeping miss (D-59-10's same discipline).
    """
    updates = {}
    for field, value in (("ceiling", ceiling), ("balances", balances),
                         ("disarm", disarm), ("ceiling_stop", ceiling_stop)):
        if value is None:
            continue
        offender = _first_forbidden(value)
        if offender is not None:
            raise RunReportError(
                f"refusing to persist a run-audit observation for {field!r} — "
                f"{offender!r} suggests an arming grant, a live-write permission, a "
                "secret, an API key, a webhook, or a credential (GRANT-06/D-57-05). "
                "Nothing was written."
            )
        updates[field] = value

    if not updates:
        return True

    target = Path(path) if path is not None else run_audit_path(run_id)

    if _refuses_real_durable_write_under_pytest(target):
        return False

    try:
        existing_document = _read_document(target)
        existing_facts = existing_document.get(FACTS_FIELD) if isinstance(existing_document, dict) else None
        facts = dict(existing_facts) if isinstance(existing_facts, dict) else {}
        facts.update(updates)

        document = {
            RUN_ID_FIELD: run_id,
            STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
            FACTS_FIELD: facts,
        }
        durable_paths._atomic_write_0600(target, json.dumps(document))
        return True
    except (OSError, TypeError):
        # OSError: the same environment-condition degrade every sibling store's writer
        # follows. TypeError: a caller passed a value `json.dumps` cannot serialize (a
        # dataclass instead of `dataclasses.asdict(...)`, say) — a defect in the DATA
        # this call was given, but still a bookkeeping miss, never a reason to halt the
        # live dispatch this is called from (D-59-10's same posture).
        return False


def load_audit(run_id, path=None) -> dict:
    """This run's persisted observations, or `{}` when there is nothing usable —
    missing, unreadable, or malformed all degrade to the same empty result, never
    raising. A caller wanting to know WHY it is empty uses `classify_audit_read`."""
    target = Path(path) if path is not None else run_audit_path(run_id)
    document = _read_document(target)
    if document is None:
        return {}
    facts = document.get(FACTS_FIELD)
    return dict(facts) if isinstance(facts, dict) else {}


def classify_audit_read(run_id, path=None) -> str:
    """What this run's own audit record looks like, from a fresh probe — never raises
    (REVIEW-57-M4). `ABSENT` (no file), `PARSEABLE` (a real, readable document,
    including one holding no facts yet), `ANOMALOUS` (present but unparseable, or not a
    mapping, or `facts` is not a mapping), or `ANOTHER_RUN` (a readable document whose
    own stored `run_id` does not match). Same contract every sibling classifier in this
    family carries.
    """
    try:
        target = Path(path) if path is not None else run_audit_path(run_id)
        if not target.exists():
            return ABSENT
        document = _read_document(target)
        if document is None:
            return ANOMALOUS
        facts = document.get(FACTS_FIELD)
        if not isinstance(facts, dict):
            return ANOMALOUS
        if document.get(RUN_ID_FIELD) != run_id:
            return ANOTHER_RUN
        return PARSEABLE
    except (TypeError, ValueError, OSError):
        return ABSENT


# =========================================================================================
# Task 2 — build_run_report: one report from five stores plus the audit record
# (AFTER-01, AFTER-03's operator-facing half, G-4's disclosure half).
# =========================================================================================

# The words this report renders come from `written_records` — imported, never restated
# (must_haves: "Use the SAME outcome words written_records defines").
_WRITE_OUTCOMES = frozenset({
    written_records.WRITTEN, written_records.WRITE_ATTEMPTED,
    written_records.CREATED_ID_UNKNOWN, written_records.WRITTEN_ID_UNKNOWN,
})

_OUTCOME_TEXT = {
    written_records.WRITTEN:
        "written — a create whose response echoed back a real HubSpot id. Operator does nothing.",
    written_records.WRITE_ATTEMPTED:
        "write attempted — the id was already known before the write; this proves the write "
        "was permitted and attempted, never that it landed. Spot-check the record if it matters.",
    written_records.CREATED_ID_UNKNOWN:
        "created, id unknown — the record was likely created but the response carried no id; "
        "never fabricated.",
    written_records.WRITTEN_ID_UNKNOWN:
        "write attempted, id unknown — open this row's record and confirm.",
    written_records.GATED:
        "gated — this row would have been written; open a grant and re-send it to write it. "
        "This is recoverable, never a failure.",
    written_records.HELD:
        "held for review — a human or a second automated pass needs to decide before it can "
        "be written.",
    written_records.FAILED:
        "failed — this action failed, was refused, or is an outcome never seen before; retry, "
        "or fix the input.",
    written_records.NO_ACTION:
        "no action needed — a success, not a failure: either a look-only preview, or the "
        "record already had complete, fresh, valid data.",
}

_ASSOCIATION_TEXT = {
    "associated": "associated",
    "not_confirmed": "association not confirmed",
    "not_attempted": "association not attempted",
    "none": "no association",
}

_SAMPLING_CAVEAT = (
    "If the month-to-date sample rested on an exhausted listing rather than on back-paging, "
    "the sampled spend is a LOWER bound (n8n prunes history and a pruned execution was still "
    "billed) — so the headroom the ceiling worked from was an UPPER bound."
)
_CONCURRENCY_CAVEAT = (
    "The ceiling is a conservative point-in-time LOCAL control; other sessions, schedulers, "
    "and grants consume the same instance-wide allowance, so zero local overshoot is not zero "
    "instance-wide overrun."
)
_REMAINDER_STANDING_CAVEAT = (
    "Note: the remainder queue records only DELIBERATE ceiling stops and accepted allowance "
    "splits — it says nothing about a run that crashed mid-dispatch; a crash's own account "
    "lives in written_records, not here."
)


def _association_text(value):
    if value in _ASSOCIATION_TEXT:
        return _ASSOCIATION_TEXT[value]
    return "association unknown"


def _balance_readable(info):
    if not isinstance(info, dict):
        return False
    if info.get("verdict") == "unknown":
        return False
    if info.get("unreadable") is True:
        return False
    value = info.get("remaining_credits", info.get("credits"))
    return value is not None


def _lane_for_entry(entry):
    object_type = entry.get("object_type") or "unknown"
    action = entry.get("action") or "unknown"
    return f"{object_type}:{action}"


def _identity_for_entry(entry, counter):
    row_id = entry.get("row_id")
    if row_id:
        return row_id, "row_id"
    hs_object_id = entry.get("hs_object_id")
    if hs_object_id:
        return hs_object_id, "hs_object_id"
    counter[0] += 1
    return f"unjoinable-{counter[0]}", "unjoinable"


def _build_records(entries):
    """`{(identity, lane): {"identity", "lane", "join", "events": [entry, ...]}}` — never
    keyed by `row_id` alone (REVIEW-57-H: one row can carry an enrichment event and an
    ingest event under one run) and never dropping an entry with no join key at all
    (REVIEW-57-H7: kept, marked unjoinable)."""
    records = {}
    counter = [0]
    unjoinable_seen = False
    for entry in entries:
        identity, join_kind = _identity_for_entry(entry, counter)
        lane = _lane_for_entry(entry)
        key = (identity, lane)
        bucket = records.setdefault(
            key, {"identity": identity, "lane": lane, "join": join_kind, "events": []})
        bucket["events"].append(entry)
        if join_kind == "unjoinable":
            unjoinable_seen = True
    return records, unjoinable_seen


def _identities_in_spec(spec):
    ids = set()
    if not isinstance(spec, dict):
        return ids
    rows = spec.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("row_id"):
                ids.add(row["row_id"])
    record_ids = spec.get("record_ids")
    if isinstance(record_ids, list):
        ids.update(str(v) for v in record_ids)
    return ids


def _classify_remainder_read(run_id):
    """A local, fresh four-word probe over remainder_queue's per-run file — never added
    to `remainder_queue.py` itself (not this plan's file to widen); mirrors the shape
    every sibling classifier in this family already carries."""
    target = remainder_queue.remainder_path(run_id)
    if not target.exists():
        return ABSENT
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ANOMALOUS
    if not isinstance(document, dict):
        return ANOMALOUS
    entries = document.get(remainder_queue.ENTRIES_FIELD)
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        return ANOMALOUS
    if document.get(remainder_queue.RUN_ID_FIELD) != run_id:
        return ANOTHER_RUN
    return PARSEABLE


def _add_gap(gaps, store_name, classification):
    """ABSENT is a legitimate zero for every store except `written_records` (every real
    dispatch appends to it — its absence means nothing durable exists for this run_id
    at all). ANOMALOUS/ANOTHER_RUN are always a gap, for every store, because they mean
    the evidence exists but cannot be trusted (T-57-28)."""
    if classification == PARSEABLE:
        return
    if classification == ABSENT:
        if store_name == "written_records":
            gaps.append(f"{store_name}: absent — no durable file exists for this run.")
        return
    if classification == ANOMALOUS:
        gaps.append(f"{store_name}: malformed (anomalous) — present but unreadable or "
                    "schema-mismatched.")
    elif classification == ANOTHER_RUN:
        gaps.append(f"{store_name}: another run's file — this run's own data could not "
                    "be read from it.")


def _find_contradictions(run_id, records, scoped_verdicts, remainder_entries,
                         held_map, progress, entries):
    """The contradiction matrix (REVIEW-57-H) — five independently written stores can
    disagree after a crash. Every detected disagreement becomes a named entry; NONE is
    silently resolved in favour of one store."""
    contradictions = []

    # Row 1: written ledger reports a write outcome; the manifest says held/confidence_held
    # for the SAME row.
    for (identity, lane), bucket in records.items():
        if bucket["join"] != "row_id":
            continue
        verdict = scoped_verdicts.get(identity)
        if verdict not in (run_manifest.HELD, run_manifest.CONFIDENCE_HELD):
            continue
        for event in bucket["events"]:
            if event.get("outcome") in _WRITE_OUTCOMES:
                contradictions.append({
                    "kind": "written_vs_held",
                    "row_id": identity,
                    "written_outcome": event.get("outcome"),
                    "manifest_verdict": verdict,
                    "description": (
                        f"row {identity}: written-records reports "
                        f"{event.get('outcome')!r} but the manifest recorded "
                        f"{verdict!r} for the same row — both shown, neither resolved; "
                        "this row needs a human look."
                    ),
                })

    # Row 2: a row is in the remainder queue AND in the written records for this run.
    written_identities = {k[0] for k in records}
    for entry in remainder_entries:
        overlap = _identities_in_spec(entry.get("spec")) & written_identities
        if overlap:
            contradictions.append({
                "kind": "remainder_and_written",
                "row_ids": sorted(overlap),
                "description": (
                    f"row(s) {sorted(overlap)} appear both in the remainder queue and "
                    "in this run's written records — it may have been sent and "
                    "re-queued, or the ceiling stop raced the send."
                ),
            })

    # Row 3: association says associated but the write outcome is unknown or absent.
    for (identity, lane), bucket in records.items():
        for event in bucket["events"]:
            if event.get("association") == "associated" and event.get("outcome") not in _WRITE_OUTCOMES:
                contradictions.append({
                    "kind": "associated_without_confirmed_write",
                    "row_id": identity,
                    "outcome": event.get("outcome"),
                    "description": (
                        f"row {identity}: association reports 'associated' but the "
                        f"write outcome is {event.get('outcome')!r} — an association "
                        "without a confirmed write is not evidence of one."
                    ),
                })

    # Row 4: run_state still reads "running" while durable per-row results exist.
    if progress.state == run_state.OK and (progress.running or 0) > 0 and entries:
        contradictions.append({
            "kind": "interrupted_run",
            "running_count": progress.running,
            "description": (
                f"run_state still reports {progress.running} row(s) as 'running' "
                f"while this run's written-records list already holds {len(entries)} "
                "entrie(s) — the run may have crashed between dispatch and "
                "verdict-recording. The results are shown; the running tally is not "
                "trusted."
            ),
        })

    # Row 5: a held_queue row this run actually touched carries no matching manifest
    # verdict for it — attribution unknown (held_queue itself carries no run_id at
    # all: REVIEW-57-H2, see module docstring's own note on why this is keyed by
    # row_id, restricted to rows THIS run's own written-records evidence names).
    for (identity, lane), bucket in records.items():
        if bucket["join"] != "row_id":
            continue
        if identity not in held_map:
            continue
        if scoped_verdicts.get(identity) in (run_manifest.HELD, run_manifest.CONFIDENCE_HELD):
            continue
        contradictions.append({
            "kind": "held_queue_attribution_unknown",
            "row_id": identity,
            "description": (
                f"row {identity} appears in the global held-queue backlog, but this "
                "run's own manifest does not record it as held — backlog attribution "
                "unknown; never counted into this run."
            ),
        })

    return contradictions


def _render_block(run_id, records, held_section, remainder_entries, spend, disarm,
                  balances, contradictions, gaps, total_row_ids_count, original_row_count):
    lines = []
    if gaps or contradictions:
        lines.append(
            f"**REPORT INCOMPLETE** — {len(gaps)} gap(s), {len(contradictions)} "
            "contradiction(s) named below. This report joins FIVE primary durable "
            "stores plus one run-audit record; not all of them could be read cleanly."
        )
        lines.append("")

    lines.append(f"## End-of-run report — {run_id}")
    lines.append("")

    # F4 (uat-batch-review-row-reads-failed, gap-closure 2026-09-09): states this
    # run's own registered row count against the caller-supplied original batch
    # count, so a row that never reached `run_state.start_run` at all (whatever the
    # cause — an out-of-band dispatch, a future code defect, anything) is visible on
    # the report's own face rather than only discoverable by diffing store files.
    lines.append("### Row accounting")
    if total_row_ids_count is None:
        lines.append(
            "- This run's own registered row count: not observed (run_state unreadable)."
        )
    else:
        lines.append(
            f"- This run's own registered row count (run_state.total_row_ids): "
            f"{total_row_ids_count}."
        )
    if original_row_count is None:
        lines.append(
            "- Original batch row count: not provided by the caller — a mismatch "
            "cannot be checked this run."
        )
    elif original_row_count == total_row_ids_count:
        lines.append(
            f"- Matches the original batch's {original_row_count} row(s) — every "
            "row accounted for."
        )
    else:
        lines.append(
            f"- **MISMATCH**: the original batch named {original_row_count} row(s), "
            f"but only {total_row_ids_count} ever reached this run's own tracked "
            f"scope. {abs(original_row_count - (total_row_ids_count or 0))} row(s) "
            "never registered with run_state at all — check for a dispatch outside "
            "chunking.dispatch_plan."
        )
    lines.append("")

    lines.append("### Per-record outcomes")
    if records:
        for (identity, lane), bucket in sorted(records.items()):
            display_identity = identity
            if bucket["join"] == "unjoinable":
                display_identity = f"{identity} (UNJOINABLE — no row_id and no HubSpot id)"
            for event in bucket["events"]:
                outcome = event.get("outcome")
                text = _OUTCOME_TEXT.get(outcome, str(outcome))
                assoc = _association_text(event.get("association"))
                lines.append(
                    f"- {display_identity} [{lane}]: {event.get('action')} -> {text} "
                    f"(association: {assoc})"
                )
    else:
        lines.append("- (no records)")
    lines.append("")

    lines.append("### Held rows")
    this_run_held = held_section.get("this_run") or []
    if this_run_held:
        for h in this_run_held:
            lines.append(f"- HELD: row {h['row_id']} — verdict {h['verdict']}")
    else:
        lines.append("- (no rows held by this run)")
    backlog = held_section.get("backlog") or {}
    if backlog:
        lines.append(
            f"- Backlog (global held_queue, NOT attributed to this run): "
            f"{len(backlog)} row(s) held across all runs."
        )
    lines.append("")

    lines.append("### Remainder queue")
    lines.append(f"- {_REMAINDER_STANDING_CAVEAT}")
    if remainder_entries:
        for entry in remainder_entries:
            lines.append(
                f"- {entry.get('reason')}: {entry.get('record_count')} record(s), "
                f"{entry.get('note') or ''}"
            )
    else:
        lines.append("- (nothing queued)")
    lines.append("")

    lines.append("### Spend against ceiling")
    lines.append(f"- Projected executions this run (from what was attempted): "
                 f"{spend.get('projected_executions')}")
    ceiling = spend.get("ceiling")
    if isinstance(ceiling, dict):
        verdict = ceiling.get("verdict")
        lines.append(
            f"- Ceiling verdict: **{verdict}** — projected "
            f"{ceiling.get('projected_executions')}, sampled "
            f"{ceiling.get('spent_sampled')} spent, {ceiling.get('remaining_sampled')} "
            f"remaining of the configured {ceiling.get('allowance')} allowance."
        )
        if ceiling.get("overridden"):
            lines.append(
                f"- **OVERRIDDEN** by the operator: {ceiling.get('override_reason')} "
                f"(authority: {ceiling.get('override_authority')}). This run must "
                "never read as under-ceiling."
            )
    else:
        lines.append("- Ceiling verdict: not observed for this run.")
    lines.append(f"- Basis: {spend.get('basis')}")
    lines.append(f"- {spend.get('executions_basis')}")
    lines.append(f"- {_SAMPLING_CAVEAT}")
    lines.append(f"- {_CONCURRENCY_CAVEAT}")
    for stop in spend.get("ceiling_stops") or []:
        lines.append(
            f"- Ceiling stop at chunk {stop['chunk_index']}: a deliberate budget stop "
            f"— spending halted before this chunk was sent. {stop['unsent_count']} "
            "unsent row-group(s) are queued in the remainder queue, to be sent only by "
            "a future run the operator separately authorises."
        )
    lines.append("")

    lines.append("### Provider balances")
    if balances:
        for provider, info in sorted(balances.items()):
            readable = _balance_readable(info)
            state = "readable" if readable else "unreadable"
            reason = info.get("reason") if isinstance(info, dict) else None
            lines.append(f"- {provider}: {state}" + (f" ({reason})" if reason else ""))
        unreadable = sorted(p for p, info in balances.items() if not _balance_readable(info))
        readable_list = sorted(p for p, info in balances.items() if _balance_readable(info))
        lines.append(
            f"- Spend was bounded only for the balance(s) that could be read: "
            f"{readable_list or 'none'}. {unreadable or 'none'} could not be confirmed "
            "readable, so the ceiling did not guard that part of spend (D-57-02)."
        )
    else:
        lines.append("- (no balances observed)")
    lines.append("")

    lines.append("### Disarm")
    if disarm is None:
        lines.append("- Not observed for this run.")
    else:
        outcome = disarm.get("outcome") if isinstance(disarm, dict) else disarm
        lines.append(f"- {outcome}.")
    lines.append("")

    if contradictions:
        lines.append("### Contradictions (never silently resolved)")
        for c in contradictions:
            lines.append(f"- [{c['kind']}] {c['description']}")
        lines.append("")

    if gaps:
        lines.append("### Known gaps")
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    return "\n".join(lines)


def build_run_report(run_id, config, *, outcomes=(), disarm=None, balances=None,
                     ceiling=None, original_row_count=None):
    """One end-of-run report over FIVE primary durable stores
    (`written_records`, `run_state`, `run_manifest`, `held_queue`, `remainder_queue`)
    plus one run-audit record (`record_audit`/`load_audit`) — AFTER-01, AFTER-03's
    operator-facing half, G-4's disclosure half.

    `outcomes` is a SEQUENCE of this run's `chunking.DispatchOutcome`s (plural — the
    pair pipeline runs match/enrich/re-request/ingest passes under one grant and one
    `run_id`). `disarm`/`balances`/`ceiling` are the caller's own live observations;
    each falls back to this run's persisted audit record when omitted, and only then to
    a stated gap. Never raises: a missing or malformed input degrades to a named entry
    in `gaps`, never an exception.

    `original_row_count` (F4, uat-batch-review-row-reads-failed, gap-closure
    2026-09-09): keyword-only, defaults to `None` — the caller's own count of rows the
    batch started with (e.g. the spreadsheet's row count), compared in the rendered
    block against `run_state.total_row_ids`'s own count for this run. A mismatch
    means some row never reached `run_state.start_run` at all — the exact shape F4
    found live (a row dispatched out-of-band, bypassing every SKILL.md-sanctioned
    bookkeeping path) — named on the report's own face rather than only discoverable
    by diffing store files by hand. `None` (the caller did not pass it) states the
    comparison as unavailable rather than guessing.

    The rendered block is PERSISTED to `report_path(run_id)` before this function
    returns — for both the happy path and the internal-error degrade path below —
    closing F3: "was the end-of-run report actually rendered" becomes a
    file-existence check, never only a memory of what scrolled past in chat.
    """
    try:
        report = _build_run_report(
            run_id, config, tuple(outcomes or ()), disarm, balances, ceiling,
            original_row_count,
        )
    except Exception as exc:  # noqa: BLE001 — this is the report's own never-raise contract.
        gaps = [f"internal report error: {exc!r} — this report is incomplete."]
        block = (
            "**REPORT INCOMPLETE** — an internal error prevented building this report.\n"
            f"- {gaps[0]}"
        )
        report = {
            "run_id": run_id, "records": {}, "held": {"this_run": [], "backlog": {}},
            "remainder": [], "spend": {}, "disarm": None, "balances": {},
            "contradictions": [], "gaps": gaps, "block": block,
        }
    _persist_report(run_id, report["block"])
    return report


def _build_run_report(run_id, config, outcomes, disarm, balances, ceiling, original_row_count):
    gaps = []

    # --- written_records --------------------------------------------------------------
    wr_classification = written_records.classify_read(run_id)
    _add_gap(gaps, "written_records", wr_classification)
    all_entries = written_records.load()
    entries = [e for e in all_entries if e.get(written_records.RUN_ID_FIELD) == run_id]
    records, unjoinable_seen = _build_records(entries)
    if unjoinable_seen:
        gaps.append(
            "the pair pipeline's final ingest leg strips row_id before the CSV is "
            "written (extraction.strip_row_id) — rows from that leg with no HubSpot id "
            "either cannot be joined at all and are kept, rendered UNJOINABLE, rather "
            "than dropped or silently counted as a complete join."
        )

    # --- run_manifest (run-scoped) + run_state, one manifest snapshot for both -------
    rm_classification = run_manifest.classify_read(run_id)
    _add_gap(gaps, "run_manifest", rm_classification)
    scoped = run_manifest.load_scoped(
        run_manifest.run_manifest_path(run_id), expected_run_id=run_id)

    rs_classification = run_state.classify_read(run_id)
    _add_gap(gaps, "run_state", rs_classification)
    progress = run_state.read_progress(run_id, manifest_snapshot=scoped)

    # --- held_queue (global backlog, never attributed to this run) -------------------
    hq_classification = held_queue.classify_read()
    _add_gap(gaps, "held_queue", hq_classification)
    held_map = held_queue.load()
    if held_map:
        gaps.append(
            f"held_queue: {len(held_map)} backlog row(s) exist globally; held_queue "
            "carries no run attribution at all, so this report cannot confirm any of "
            "them belong to this run — shown as backlog only, never counted into this "
            "run's own held total."
        )
    this_run_held = [
        {"row_id": row_id, "verdict": verdict}
        for row_id, verdict in scoped.verdicts.items()
        if verdict in (run_manifest.HELD, run_manifest.CONFIDENCE_HELD)
    ]
    held_section = {"this_run": this_run_held, "backlog": held_map}

    # --- remainder_queue (this run's rows only) ---------------------------------------
    remainder_classification = _classify_remainder_read(run_id)
    _add_gap(gaps, "remainder_queue", remainder_classification)
    remainder_entries = [
        e for e in remainder_queue.load() if e.get(remainder_queue.RUN_ID_FIELD) == run_id
    ]

    # --- the audit record (crash-reconstruction fallback) -----------------------------
    audit_classification = classify_audit_read(run_id)
    _add_gap(gaps, "run_audit", audit_classification)
    audit_facts = load_audit(run_id)
    resolved_ceiling = ceiling if ceiling is not None else audit_facts.get("ceiling")
    resolved_disarm = disarm if disarm is not None else audit_facts.get("disarm")
    resolved_balances = balances if balances is not None else audit_facts.get("balances")

    # --- spend -------------------------------------------------------------------------
    projected_from_outcomes = (
        sum(chunking.projected_spend(o) for o in outcomes) if outcomes else None
    )
    ceiling_stops = []
    for outcome in outcomes:
        stop = getattr(outcome, "ceiling_stop", None)
        if stop is not None:
            ceiling_stops.append({
                "chunk_index": stop.chunk_index,
                "unsent_count": len(stop.unsent_chunks),
                "reason": stop.reason,
            })
    audit_ceiling_stop = audit_facts.get("ceiling_stop")
    if audit_ceiling_stop and not ceiling_stops:
        ceiling_stops.append(audit_ceiling_stop)

    spend = {
        "projected_executions": projected_from_outcomes,
        "ceiling": resolved_ceiling,
        "basis": run_state.SPEND_BASIS,
        "executions_basis": write_grant.EXECUTIONS_BASIS,
        "ceiling_stops": ceiling_stops,
    }

    # --- contradictions ------------------------------------------------------------
    contradictions = _find_contradictions(
        run_id, records, scoped.verdicts, remainder_entries, held_map, progress, entries)

    block = _render_block(
        run_id, records, held_section, remainder_entries, spend, resolved_disarm,
        resolved_balances, contradictions, gaps, progress.total, original_row_count)

    return {
        "run_id": run_id,
        "records": records,
        "held": held_section,
        "remainder": remainder_entries,
        "spend": spend,
        "disarm": resolved_disarm,
        "balances": resolved_balances,
        "contradictions": contradictions,
        "gaps": gaps,
        "block": block,
    }
