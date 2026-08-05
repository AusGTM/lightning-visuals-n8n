"""operator-claude-plugin/scripts/run_manifest.py

The plugin's SECOND persisted artifact (`artifact_store.py`'s D-09b register is the
first). It lives beside the dashboard pointer, under the same durable home
(`durable_paths.resolve_state_path()`'s directory), and exists because a batch that
breaks halfway through the match/enrich/ingest cycle (37-CONTEXT.md §13a) currently
leaves no record of which rows completed — so re-running it re-spends provider credits
on rows already enriched, and worse, can leave a contact silently unenriched forever if
the operator gives up rather than re-running.

This is a SEPARATE file, not a widening of `artifact_store.py`. Read that module's own
docstring before touching this one: its two-field refusal (`artifact_id`, `saved_at`) is
deliberate — a store that accepts arbitrary keys becomes a general-purpose store one
commit later, and the first thing parked in one would be the arming grant Phase 23 D-11
deliberately keeps off disk. Widening `artifact_store.py` once makes widening it again
arguable. This module gets its OWN schema and its OWN refusal instead.

Schema: a run id, a timestamp, and a map of `row_id -> verdict`. A verdict is exactly
one of five words — `matched`, `enriched`, `held`, `unchecked`, `unanswered` — anything
else is a rejection, not a widening. `save()` also refuses any verdict-map key or value
whose name suggests an arming grant, a live-write permission, a secret, or an API key: Phase
23 D-11 holds here too — the grant exists only as a call argument, for one turn, and a
grant read back off disk on a later run would be a live send nobody authorised in that
conversation.

Every read failure degrades to "no manifest" rather than raising, mirroring
`artifact_store.py`'s own reasoning verbatim: a missing, unreadable, malformed, or
half-written manifest all mean the same thing to a resume — there is nothing to skip —
and none of them is worth an error the operator has to read. This is the load-bearing
safety property: a truncated verdict map read as complete would skip rows that were
never enriched, which is the exact failure (an unenriched contact at the end of a
cycle) this module exists to prevent. So `load()` never returns a partial map either —
a manifest that fails ANY validation degrades to the SAME empty result as a missing
file, never a partially-trusted one.

Writes through `durable_paths._atomic_write_0600` — a same-package use of that
module's private helper, not a second atomic-write implementation. It already carries
the exact guarantee this file needs (temp file in the target's own directory, chmod
0600, fsync, `os.replace`), and duplicating it here would be a second copy of the one
pattern this plugin already went to the trouble of centralizing (durable_paths.py's own
module docstring, on `config_gate.py`/`artifact_store.py` sharing one resolution
authority).

The filename is deliberately NOT a dotfile: dotfiles are unreadable to this
environment's tooling (Phase 23 D-04), so a dotfile manifest would be dead at runtime —
the same reasoning `artifact_store.py` and `durable_paths.py` already carry for the
files they own.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import durable_paths

MANIFEST_FILENAME = "run_manifest.json"

# The whole schema. Anything else is a rejection, not a widening — see artifact_store.py's
# own ID_FIELD/STAMP_FIELD comment for the same discipline applied to a different pair.
RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
VERDICTS_FIELD = "verdicts"

# The five words a verdict may be, and no others (37-CONTEXT §13a, T-38-02 for the
# fifth). `matched`/`enriched` are genuinely done; `held`, `unchecked` and `unanswered`
# are terminal for the RUN that recorded them but not permanent for the ROW — a resume
# re-requests all three under the right condition. `unanswered` joins `unchecked` on
# that same non-terminal-for-the-ROW footing: the run ended without a verdict for that
# row (a two-row chunk answered with one item, say), which is a reason to ask again,
# not a reason to stop asking.
MATCHED = "matched"
ENRICHED = "enriched"
HELD = "held"
UNCHECKED = "unchecked"
UNANSWERED = "unanswered"
ALLOWED_VERDICTS = frozenset({MATCHED, ENRICHED, HELD, UNCHECKED, UNANSWERED})

# Phase 23 D-11: the arming grant exists only as a call argument, for one turn — never
# read back off disk on a later run, or it becomes a live send nobody authorised in that
# conversation. A verdict map is the one thing `save()` ever receives from outside this
# module, so it is the one thing checked for a key or value whose NAME suggests that
# grant, a live-write permission, a secret, or an API key smuggled in under a
# row_id-shaped key. Deliberately broad substrings (["arm"] also catches "armed",
# "disarm", "arming") — a false-positive refusal on a legitimate row_id costs nothing;
# a missed one costs the one thing this module must never hold.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)


class ManifestError(Exception):
    """Raised when a verdict map cannot be persisted safely — a verdict outside the
    five allowed words, or a key/value whose name suggests the one thing this module
    must never hold on disk (see module docstring, Phase 23 D-11)."""


def _looks_forbidden(name) -> bool:
    lowered = str(name).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)


def manifest_path() -> Path:
    """Where the manifest lives — resolved fresh on every call, never a module-level
    constant (33-02's migration can create the durable file mid-run, the same reason
    `artifact_store.state_path()` resolves fresh).

    Takes `durable_paths.resolve_state_path()`'s PARENT and joins this module's own
    filename — the same durable directory the dashboard pointer resolves into, never a
    second resolution rule and never a second env var. This is what makes a plugin
    update not abandon a half-finished batch: the manifest survives exactly as long as
    the dashboard pointer does.
    """
    return durable_paths.resolve_state_path().parent / MANIFEST_FILENAME


def save(run_id, verdicts, path=None) -> None:
    """Persist one run's verdicts. Validates every entry BEFORE anything is written —
    a save that raises leaves the previous manifest (if any) untouched, mirroring
    `apply_match_decisions`' validate-then-apply discipline in `preingest.py`.

    `verdicts` maps `row_id -> one of the five allowed words`. Any other value raises,
    and any key or value whose name suggests an arming grant, a live-write permission,
    a secret, or an API key raises too — see module docstring.
    """
    for row_id, verdict in verdicts.items():
        if _looks_forbidden(row_id):
            raise ManifestError(
                f"refusing to persist verdict key {row_id!r} — its name suggests an "
                "arming grant, a live-write permission, a secret, or an API key. Phase "
                "23 D-11: the grant exists only as a call argument, for one turn; a "
                "grant read back off disk on a later run would be a live send nobody "
                "authorised in that conversation. Nothing was written."
            )
        if _looks_forbidden(verdict):
            raise ManifestError(
                f"refusing to persist verdict {verdict!r} for row {row_id!r} — its "
                "name suggests an arming grant, a live-write permission, a secret, or "
                "an API key. Nothing was written."
            )
        if verdict not in ALLOWED_VERDICTS:
            raise ManifestError(
                f"row {row_id!r} carries verdict {verdict!r}, which is not one of the "
                f"five allowed words ({sorted(ALLOWED_VERDICTS)}). Nothing was written."
            )

    target = Path(path) if path is not None else manifest_path()
    document = {
        RUN_ID_FIELD: run_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        VERDICTS_FIELD: dict(verdicts),
    }
    durable_paths._atomic_write_0600(target, json.dumps(document))


def load(path=None) -> dict:
    """The verdict map (`row_id -> verdict`), or `{}` when there is nothing usable to
    resume against — missing, unreadable, malformed, half-written, or schema-mismatched
    all degrade to the SAME empty result rather than raising (see module docstring).

    A manifest carrying even ONE bad entry (a verdict outside the five words, or a
    non-string key) degrades whole, not partially: a truncated verdict map read as
    partially complete would skip rows that were never enriched, which is the exact
    failure this module exists to prevent. Degrading to a full run costs money;
    degrading to a partial skip costs a contact — only one of those is recoverable, so
    every anomaly is treated as "no manifest" rather than "a manifest missing one row".
    """
    target = Path(path) if path is not None else manifest_path()
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(document, dict):
        return {}

    verdicts = document.get(VERDICTS_FIELD)
    if not isinstance(verdicts, dict):
        return {}

    cleaned = {}
    for row_id, verdict in verdicts.items():
        if not isinstance(row_id, str) or verdict not in ALLOWED_VERDICTS:
            return {}
        cleaned[row_id] = verdict
    return cleaned


@dataclass(frozen=True)
class ResumeResult:
    """One resume decision's outcome, mirroring `MatchOutcome`/`MergeResult`'s
    payload-plus-report shape from `preingest.py`. `rows` is ready to hand straight to
    `chunking.plan_chunks`/`preingest.match_batch` — every other field REPORTS why a
    row was left out, so a resume tells the operator "18 of 25 already done" rather
    than silently showing a smaller batch."""

    rows: tuple = field(default_factory=tuple)
    skipped: tuple = field(default_factory=tuple)
    still_held: tuple = field(default_factory=tuple)


def _present(value) -> bool:
    """Mirrors `preingest._present`'s trim-then-check rule, kept local rather than
    imported — this module never reaches into another module's private name."""
    return value is not None and str(value).strip() != ""


def rows_to_resume(rows, manifest):
    """The subset of `rows` that still needs work, in original order, plus a report of
    what was left out and why. Pure: takes an already-loaded manifest (`load()`'s
    return), performs no file read itself — mirroring how `chunking.plan_chunks` takes
    an already-read ceiling rather than reading config itself.

    A row verdicted `matched` or `enriched` is done and excluded.

    A row verdicted `unchecked` is INCLUDED — "we could not look" is a reason to look
    again, not an answer about the row. `unchecked` is terminal for the RUN that
    recorded it (that run is over) but not an answer about the row itself; skipping it
    on resume would leave a contact unenriched at the end of the cycle for the sole
    reason that a chunk timed out once, which is the outcome 37-CONTEXT §13a's
    governing addition exists to prevent.

    A row verdicted `unanswered` is INCLUDED too, on this exact same branch — same
    reason, one layer down (T-38-02, the live case this word exists for): a two-row
    chunk that came back carrying only one item leaves the other row's verdict
    `unanswered`, and that is a reason to ask again, not a reason to stop asking. It is
    not written to a second branch, so the two can never drift apart.

    A row verdicted `held` is excluded not because it completed but because sending it
    would fail identically — the ingest gate holds any row without an email, and
    nothing about a resume changes that. It is re-included the moment it gains an
    email, which is the only thing that changes its outcome, and is reported in
    `still_held` when it stays excluded so the operator sees a count that has not
    moved rather than a row that silently vanished.

    A row absent from the manifest (or when the manifest is empty/absent entirely) is
    included — a resume with no manifest is just a run.
    """
    manifest = manifest or {}
    to_resume, skipped, still_held = [], [], []

    for row in rows:
        row_id = row.get("row_id")
        verdict = manifest.get(row_id)

        if verdict in (MATCHED, ENRICHED):
            skipped.append({"row_id": row_id, "verdict": verdict})
            continue

        if verdict == HELD:
            if _present(row.get("email")):
                to_resume.append(row)
            else:
                still_held.append({"row_id": row_id, "verdict": verdict})
            continue

        # verdict is UNCHECKED, UNANSWERED, or the row is absent from the manifest
        # entirely (verdict is None) — all three are re-requested, the same decision
        # for the same reason (T-38-02): none of them is an answer about the row.
        to_resume.append(row)

    return ResumeResult(rows=tuple(to_resume), skipped=tuple(skipped),
                        still_held=tuple(still_held))
