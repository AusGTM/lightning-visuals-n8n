"""operator-claude-plugin/scripts/extraction.py

Python's half of D-01: Claude (in-session, no Anthropic API call) reads pasted prose, a
foreign-shaped JSON blob, a fetched page, or a screenshot and writes what it found to a
scratch file as JSON. This module validates that file, applies the identity pre-flight,
reports what it dropped, and hands Phase 23's dispatch path a CSV that provably carries
canonical props only. It never extracts anything itself.

Extraction artifact contract (the schema SKILL.md instructs Claude to emit):

    {
      "batch_id": "...",
      "source": {"kind": "prose|json|url|screenshot", "detail": "..."},
      "records": [
        {
          "row": {<canonical prop>: <value>, ...},
          "provenance": {"input": "...", "locator": "..."}
        },
        ...
      ],
      "ambiguities": [...]
    }

`row` may carry any key Claude emitted; only the 7 canonical props (derived from
config/column_mapping.yaml, never retyped here) survive validation — everything else is
stripped and reported, never silently dropped (INGEST-03). `provenance.input` names which
input the row came from; `provenance.locator` names the span within it (a span of text, a
JSON path, a URL, or an image name and region) — together the two facts STRUCT-03
requires of every accepted row.

After the identity pre-flight, `validate()` also runs overlap dedupe (D-08/D-09) and
ambiguity aggregation (D-06/D-07):

  - Two accepted rows whose first-satisfied identity group (per `identity_groups()`,
    tried in order) agrees exactly once trimmed and case-folded collapse into one row.
    The merged row's `provenance` becomes a LIST of every source provenance record that
    fed it (unmerged rows keep a single provenance dict, unchanged from 24-01). A
    non-identity field the merged records disagree on is dropped from the row and
    reported as an ambiguity rather than one source winning.
  - Two accepted rows that agree on every field of some identity group one of them
    fully carries, but where the group is incomplete on the other side, are NOT merged:
    both survive and an ambiguity is raised asking whether they are the same person.
  - Ambiguities from the artifact itself, from merge conflicts, and from near-duplicates
    are aggregated into ONE list, each entry shaped
    `{"record_index": int, "field": str | None, "reason": str}` — `record_index` is the
    position in the deduplicated record list (the same order `accepted` preserves, minus
    any record this module's own D-07 check subsequently rejects for contradicting one
    of its own ambiguities). Sorted by `(record_index, field)` so two runs over the same
    artifact produce byte-identical output.
  - D-07 enforcement: a record carrying both an ambiguity naming a field AND a
    non-empty value for that same field is a contradiction (the extraction said it was
    unsure, then filled it anyway) and is rejected. This is the *structural* half of
    STRUCT-04 — the only invention this module can mechanically detect. It cannot
    verify that an extracted value is TRUE; that is a prompt contract 24-03's SKILL.md
    carries, not a code guarantee (24-RESEARCH.md's STRUCT-04 row).
  - There is no function anywhere in this module that applies or resolves an ambiguity.
    The correction path does not need one: the operator answers in chat, Claude rewrites
    the artifact, and `validate()` runs again over the corrected file. A Python
    resolution path would be a second way for a value to enter a row — exactly the
    surface D-07 exists to keep closed.
"""
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from preview import resolve_mapping_path

SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"

# The company-lane mapping file (Phase 58) — same directory convention as
# preview.py's PLUGIN_MAPPING_PATH, but company extraction has no repo-root fallback
# copy: it is a plugin-only config, never duplicated the way column_mapping.yaml is
# for a dev-checkout convenience. Passed explicitly as `mapping_path` wherever a
# record's own `record_type` selects the company lane.
COMPANY_MAPPING_PATH = Path(__file__).resolve().parent.parent / "config" / "company_column_mapping.yaml"


class ExtractionError(Exception):
    """Raised when the extraction artifact cannot be validated at all: missing file,
    unparseable JSON, wrong top-level shape, empty records list, or an unavailable
    mapping file. Carries a machine-readable `code` alongside the operator-readable
    message so the CLI can relay the sentence without inventing its own wording."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class ExtractionResult:
    accepted: list       # [{"row": {canonical: value}, "provenance": {...} | [...]}, ...]
    rejected: list       # [{"index": int, "reason": str}, ...]
    dropped_keys: list   # [{"index": int, "key": str}, ...]
    ambiguities: list = field(default_factory=list)   # [{"record_index", "field", "reason"}, ...]
    collapses: list = field(default_factory=list)      # [{"record_index", "merged_from": [...]}, ...]


def _load_mapping(mapping_path=None) -> dict:
    resolved = resolve_mapping_path(mapping_path)
    if resolved is None:
        raise ExtractionError(
            "mapping_unavailable",
            "config/column_mapping.yaml could not be found — the canonical field "
            "allowlist cannot be built without it. This is an input-validation "
            "allowlist; an allowlist that silently becomes empty is not a control.",
        )
    try:
        with Path(resolved).open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        # Names whichever mapping file was actually being resolved — a missing
        # COMPANY_MAPPING_PATH must not report column_mapping.yaml's absence.
        raise ExtractionError(
            "mapping_unreadable", f"{resolved} could not be read: {e}"
        ) from None
    return data or {}


def canonical_props(mapping_path=None) -> list[str]:
    """The 7 canonical contact props: the deduplicated VALUES of column_mapping.yaml's
    `aliases` map, in a deterministic (sorted) order. Never a literal in this file."""
    data = _load_mapping(mapping_path)
    aliases = dict(data.get("aliases") or {})
    return sorted(set(aliases.values()))


def identity_groups(mapping_path=None) -> list:
    """column_mapping.yaml's `required_identity.any_of` groups, verbatim. Never a
    literal in this file."""
    data = _load_mapping(mapping_path)
    required = data.get("required_identity") or {}
    return required.get("any_of") or []


def _present(value) -> bool:
    """Coerce to string, strip, test non-empty — mirrors the deployed `Map Columns`
    node's requiredIdentity()/_present(), which trims before checking presence.
    Deliberately diverges from src/file_loader.py::_has_identity, which omits the trim
    and would wrongly accept a whitespace-only field; the n8n JS is authoritative because
    it is what the live backend actually runs."""
    return value is not None and str(value).strip() != ""


def has_identity(row: dict, groups=None) -> bool:
    """True when, for some group in `groups` (defaults to identity_groups()), every key
    in that group is present (trimmed, non-empty) in `row`. Any satisfied group passes."""
    if groups is None:
        groups = identity_groups()
    return any(all(_present(row.get(key)) for key in group) for group in groups)


def _casefold_trim(value) -> str:
    """A dedupe MATCH case-folds and trims; `_present()`/`has_identity()` deliberately do
    not — presence and equality are different questions (24-RESEARCH.md Pitfall 5)."""
    return str(value).strip().casefold()


def _group_presence(row: dict, group: list) -> tuple:
    """For one identity group's fields on one row: ({field: casefolded/trimmed value}
    for fields that are present), and whether every field of the group is present."""
    present = {f: _casefold_trim(row[f]) for f in group if _present(row.get(f))}
    return present, len(present) == len(group)


def _first_satisfied_key(row: dict, groups: list):
    """The record's identity key for exact-match clustering: the first group in
    `groups` order that `row` fully satisfies, as `(group_index, casefolded tuple)`.
    Every accepted record satisfies at least one group (has_identity() already
    guaranteed that at the pre-flight), so this never returns None for an accepted row."""
    for gi, group in enumerate(groups):
        present, full = _group_presence(row, group)
        if full:
            return (gi, tuple(present[f] for f in group))
    return None


def _compare_identity(row_a: dict, row_b: dict, groups: list):
    """Compare two accepted rows against every identity group. No similarity score, no
    edit distance, no threshold — only ever exact (casefolded, trimmed) equality of
    fields both rows actually carry (24-RESEARCH.md Pitfall 5); anything short of that is
    either "near_dup" or no signal at all, never a collapse.

    Returns:
      ("match", None, None)       - some group is fully present on both sides and every
                                     field they share agrees.
      ("near_dup", field, side)   - some group is fully present on exactly one side, and
                                     every field both sides actually carry agrees, but the
                                     group is not fully present on the other side. `side`
                                     ("a" or "b") names the incomplete row; `field` is the
                                     first field of that group missing from it.
      (None, None, None)          - no group gives either signal, including when two rows
                                     disagree on a field they both carry — disagreement is
                                     evidence of two different people, never a signal.
    """
    near_dup = None
    for group in groups:
        pa, full_a = _group_presence(row_a, group)
        pb, full_b = _group_presence(row_b, group)
        common = set(pa) & set(pb)
        if not common or any(pa[f] != pb[f] for f in common):
            continue
        if full_a and full_b:
            return "match", None, None
        if near_dup is None:
            if full_a:
                field_name = next(f for f in group if not _present(row_b.get(f)))
                near_dup = (field_name, "b")
            elif full_b:
                field_name = next(f for f in group if not _present(row_a.get(f)))
                near_dup = (field_name, "a")
    if near_dup is not None:
        return ("near_dup", *near_dup)
    return None, None, None


def _merge_cluster(entries: list) -> tuple:
    """Merge >=2 accepted entries that share an exact identity key into one surviving
    row: each field is taken where the cluster agrees (the union of what either side
    supplied); a field the cluster disagrees on is dropped from the merged row and its
    name returned as a conflict, rather than one source winning. Provenance becomes a
    list naming every source the merged row was read from.

    `record_type` carries through from the cluster's own entries (all entries in one
    dedupe() call share the same type since Phase 58's per-type grouping runs
    dedupe() separately per type — see `validate()`) — absent on entries that predate
    the `record_type` field, in which case the merged entry carries none either."""
    keys = set()
    for e in entries:
        keys.update(e["row"].keys())

    merged_row = {}
    conflicts = []
    for key in sorted(keys):
        values = [e["row"][key] for e in entries if _present(e["row"].get(key))]
        if not values:
            continue
        if len({_casefold_trim(v) for v in values}) == 1:
            merged_row[key] = values[0]
        else:
            conflicts.append(key)

    provenance = [e["provenance"] for e in entries]
    merged = {"row": merged_row, "provenance": provenance}
    record_type = entries[0].get("record_type")
    if record_type is not None:
        merged["record_type"] = record_type
    return merged, conflicts


def dedupe(accepted: list, groups=None) -> tuple:
    """Collapse overlap in a scrolled screenshot sequence onto the identity rule (D-08),
    and surface anything short of an exact identity-key match as an ambiguity instead of
    guessing with a similarity score (D-09).

    Matching is keyed on each record's FIRST satisfied identity group only (per
    `_first_satisfied_key`) — a deliberate simplification, not full pairwise clustering
    across every group a record happens to satisfy. The near-duplicate check below is
    the deliberately separate mechanism that still compares every group pairwise, so a
    record whose primary key differs from another's can still surface as a question
    rather than silently passing through unmatched.
    # ponytail: a record that fully satisfies a NON-primary group matching another
    # record's own non-primary group (differing primary keys, e.g. one side keyed by
    # email, the other by name+company, yet also fully agreeing on the other's group)
    # is not flagged. Add pairwise cross-cluster "match" handling if this proves live.

    Returns (final_accepted, collapses, ambiguities):
      final_accepted — `accepted`, with exact-identity-key clusters merged into one row
      collapses      — one entry per merge: `{"record_index", "merged_from": [...]}` —
                        `record_index` is the surviving row's position in
                        `final_accepted`; `merged_from` lists the pre-merge positions in
                        `accepted` that fed it
      ambiguities    — one entry per merge conflict and per near-duplicate pair, in the
                        shared `{"record_index", "field", "reason"}` shape (near-dup
                        entries also carry `"other_record_index"` naming the row it was
                        compared against)
    """
    if groups is None:
        groups = identity_groups()
    n = len(accepted)
    if n <= 1:
        return list(accepted), [], []

    clusters_by_key: dict = {}
    key_order: list = []
    for i, entry in enumerate(accepted):
        key = _first_satisfied_key(entry["row"], groups)
        if key not in clusters_by_key:
            clusters_by_key[key] = []
            key_order.append(key)
        clusters_by_key[key].append(i)

    final_accepted: list = []
    collapses: list = []
    ambiguities: list = []
    original_to_final: dict = {}

    for key in key_order:
        member_idxs = clusters_by_key[key]
        final_index = len(final_accepted)
        for i in member_idxs:
            original_to_final[i] = final_index

        if len(member_idxs) == 1:
            final_accepted.append(accepted[member_idxs[0]])
            continue

        merged_entry, conflicts = _merge_cluster([accepted[i] for i in member_idxs])
        final_accepted.append(merged_entry)
        collapses.append({"record_index": final_index, "merged_from": member_idxs})
        for field_name in conflicts:
            ambiguities.append(
                {
                    "record_index": final_index,
                    "field": field_name,
                    "reason": (
                        f"merged records disagree on '{field_name}' — value left "
                        "absent rather than picking one source over another"
                    ),
                }
            )

    seen_pairs = set()
    for a in range(n):
        for b in range(a + 1, n):
            if original_to_final[a] == original_to_final[b]:
                continue  # already the same surviving row
            signal, field_name, incomplete_side = _compare_identity(
                accepted[a]["row"], accepted[b]["row"], groups
            )
            if signal != "near_dup":
                continue
            incomplete_original = a if incomplete_side == "a" else b
            other_original = b if incomplete_side == "a" else a
            incomplete_final = original_to_final[incomplete_original]
            other_final = original_to_final[other_original]
            pair_key = tuple(sorted((incomplete_final, other_final)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            ambiguities.append(
                {
                    "record_index": incomplete_final,
                    "other_record_index": other_final,
                    "field": field_name,
                    "reason": (
                        f"agrees with record {other_final} on the identity fields both "
                        f"carry, but '{field_name}' is absent here — asking whether "
                        "these are the same person rather than guessing"
                    ),
                }
            )

    return final_accepted, collapses, ambiguities


def _ambiguity_sort_key(entry):
    """Deterministic sort: (record_index, field), tolerating an ambiguity entry that
    isn't shaped like ours (a raw string, say) by sorting it after every dict entry."""
    if not isinstance(entry, dict):
        return (1, 0, "")
    idx = entry.get("record_index")
    return (0, idx if isinstance(idx, int) else 0, entry.get("field") or "")


def load_artifact(path) -> dict:
    """Parse the extraction artifact at `path`. Never a best-effort or partial parse of
    malformed JSON — a fragile parse is exactly the failure INGEST-06 exists to prevent,
    so every way this can go wrong raises ExtractionError with a distinct machine-
    readable `code` rather than degrading to a silent zero-row success."""
    p = Path(path)
    if not p.exists():
        raise ExtractionError(
            "artifact_not_found", f"Extraction artifact not found at {p} — nothing to validate."
        )

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise ExtractionError("artifact_unreadable", f"Could not read {p}: {e}") from None

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtractionError(
            "artifact_not_json",
            f"Extraction artifact at {p} is not valid JSON ({e}). Extraction did not "
            "produce structured rows — try again rather than guess-parsing it.",
        ) from None

    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ExtractionError(
            "artifact_wrong_shape",
            f"Extraction artifact at {p} is not the expected mapping with a 'records' "
            "list — extraction did not produce the expected shape.",
        )

    if len(data["records"]) == 0:
        raise ExtractionError(
            "artifact_empty",
            "Extraction artifact has zero records. This is an error, not a zero-row "
            "success: either the source had nothing extractable, or extraction went "
            "wrong — check the model's own summary above and try again.",
        )

    return data


def validate(artifact: dict, mapping_path=None) -> ExtractionResult:
    """Split the artifact's records into accepted (canonical row + provenance) and
    rejected (index + reason), reporting every non-canonical key dropped along the way.
    Per-record try/except isolation: one malformed record becomes a reject with a reason,
    never a crashed batch.

    Order of operations per record, which matters: diff the row's keys against
    canonical_props() FIRST, recording every non-canonical key before removing it, THEN
    apply has_identity to what remains — reporting before removal is the only place
    "reported rather than silently dropped" can be honoured, since the backend's own
    `Map Columns` node drops an unmapped key with no error and no channel back to the
    operator.

    After the per-record pre-flight, three more passes run over what was accepted, in
    this order (each depends on the one before it):

      1. `dedupe()` — collapse overlap onto the identity rule (D-08), raising an
         ambiguity for a merge conflict or a near-duplicate instead of guessing (D-09).
      2. Aggregate every ambiguity — the artifact's own plus dedupe's — into one sorted
         list (D-06).
      3. D-07 enforcement: a record whose row carries a value for a field one of the
         now-aggregated ambiguities names on that same record is a contradiction — the
         extraction step said it was unsure, then filled it anyway — and is rejected.

    Each record carries its own `record_type` (`"contacts"` or `"companies"`); an
    absent key means `"contacts"` — every artifact and test that predates Phase 58
    keeps working unchanged. The per-record pre-flight below (non-canonical key
    stripping, identity check) reads whichever mapping — `mapping_path` for contacts,
    `COMPANY_MAPPING_PATH` for companies — that record's own type selects, rather than
    resolving one prop set and one group set once for the whole batch.

    `dedupe()` and the D-07 contradiction pass are identity-group-driven with no
    field-name assumption baked in (58-RESEARCH.md), so they run TWICE — once per
    record type, each against its own identity groups, on the two type-partitioned
    accepted lists — rather than once over a mixed batch. The results are then
    reassembled companies-first (D-58-13, operator ruling 2026-08-25) into one
    combined `accepted` list, each entry stamped with its own `record_type` so a
    caller can route it without re-reading the artifact. Every per-group local index
    dedupe() returns (`record_index`/`other_record_index`/`merged_from`) is remapped
    onto its final position in that combined list before ambiguity aggregation runs
    — never left to be re-derived from list position alone, since a group-split
    reassembly bug would otherwise point an ambiguity at the wrong record silently.
    Ambiguity aggregation itself stays ONE sorted list across the whole artifact
    (D-06), and the D-07 check still keys on that combined `record_index`.
    """
    contact_props = set(canonical_props(mapping_path))
    contact_groups = identity_groups(mapping_path)
    company_props = set(canonical_props(COMPANY_MAPPING_PATH))
    company_groups = identity_groups(COMPANY_MAPPING_PATH)

    accepted: list = []
    rejected: list = []
    dropped_keys: list = []

    for i, record in enumerate(artifact.get("records", [])):
        try:
            if not isinstance(record, dict):
                rejected.append({"index": i, "reason": "record is not an object"})
                continue

            record_type = "companies" if record.get("record_type") == "companies" else "contacts"
            props = company_props if record_type == "companies" else contact_props
            record_groups = company_groups if record_type == "companies" else contact_groups

            row = record.get("row")
            if not isinstance(row, dict):
                rejected.append({"index": i, "reason": "record's 'row' is not an object"})
                continue

            provenance = record.get("provenance")
            if (
                not isinstance(provenance, dict)
                or not _present(provenance.get("input"))
                or not _present(provenance.get("locator"))
            ):
                rejected.append(
                    {
                        "index": i,
                        "reason": (
                            "record has no provenance, or provenance is missing which "
                            "input or which span/locator produced it"
                        ),
                    }
                )
                continue

            clean_row = {}
            for key, value in row.items():
                if key in props:
                    clean_row[key] = value
                else:
                    dropped_keys.append({"index": i, "key": key})

            if not has_identity(clean_row, record_groups):
                if record_type == "companies":
                    reason = "no identity present: give the company's name — that alone is enough"
                else:
                    reason = (
                        "no identity present: needs a non-blank 'email', or all "
                        "three of 'firstname'/'lastname'/'company' non-blank"
                    )
                rejected.append({"index": i, "reason": reason})
                continue

            accepted.append({"row": clean_row, "provenance": provenance, "record_type": record_type})
        except Exception as e:  # one bad record must never crash the batch
            rejected.append({"index": i, "reason": f"parse error: {e}"})

    # Split the pre-flight-accepted list into per-type groups, each keeping its own
    # relative artifact order, so dedupe() judges every record against its OWN
    # type's identity groups (D-58-13) rather than one set for a mixed batch. A
    # company row and a contact row can never collapse into each other by
    # construction — they are never in the same dedupe() call.
    company_accepted = [e for e in accepted if e["record_type"] == "companies"]
    contact_accepted = [e for e in accepted if e["record_type"] == "contacts"]

    company_deduped, company_collapses, company_ambiguities = dedupe(
        company_accepted, company_groups
    )
    contact_deduped, contact_collapses, contact_ambiguities = dedupe(
        contact_accepted, contact_groups
    )

    # Reassemble companies-first. `company_offset` is 0 (companies keep their own
    # dedupe()-local indices unchanged); `contact_offset` shifts the contacts
    # group's local indices past however many company rows now precede them.
    deduped_accepted = company_deduped + contact_deduped
    contact_offset = len(company_deduped)

    def _remap_collapse(entry, offset):
        remapped = dict(entry)
        remapped["record_index"] = entry["record_index"] + offset
        return remapped

    def _remap_ambiguity(entry, offset):
        remapped = dict(entry)
        if isinstance(remapped.get("record_index"), int):
            remapped["record_index"] += offset
        if isinstance(remapped.get("other_record_index"), int):
            remapped["other_record_index"] += offset
        return remapped

    collapses = [_remap_collapse(c, 0) for c in company_collapses] + [
        _remap_collapse(c, contact_offset) for c in contact_collapses
    ]
    dedupe_ambiguities = [_remap_ambiguity(a, 0) for a in company_ambiguities] + [
        _remap_ambiguity(a, contact_offset) for a in contact_ambiguities
    ]

    all_ambiguities = list(artifact.get("ambiguities") or []) + dedupe_ambiguities
    all_ambiguities.sort(key=_ambiguity_sort_key)

    final_accepted: list = []
    for i, entry in enumerate(deduped_accepted):
        contradicting_field = None
        for amb in all_ambiguities:
            if not isinstance(amb, dict) or amb.get("record_index") != i:
                continue
            f = amb.get("field")
            if f and _present(entry["row"].get(f)):
                contradicting_field = f
                break
        if contradicting_field:
            rejected.append(
                {
                    "index": i,
                    "reason": (
                        f"record flagged '{contradicting_field}' as an unresolved "
                        "ambiguity yet its row still carries a value for that field — "
                        "an unconfirmed ambiguity must leave the value absent, never "
                        "asserted (D-07)"
                    ),
                }
            )
        else:
            final_accepted.append(entry)

    return ExtractionResult(
        accepted=final_accepted,
        rejected=rejected,
        dropped_keys=dropped_keys,
        ambiguities=all_ambiguities,
        collapses=collapses,
    )


def hold_emailless(rows: list) -> tuple:
    """Partition `rows` into `(sendable, held)`. The deployed ingest lane resolves a
    contact by email only (37-CONTEXT.md §4.1) — a row with no usable `email` produces
    no HubSpot write and no object id, and therefore cannot be enriched later either,
    since both enrichment entry points need an existing id. Held here rather than sent
    and left to silently fail.

    A firstname+lastname+company row still satisfies `column_mapping.yaml`'s
    `required_identity.any_of` and is still a valid EXTRACTION row — valid to extract,
    valid to match, valid to enrich. It is only invalid to INGEST. Extraction identity
    and ingest identity are different questions; this function answers the second one
    only and never touches `has_identity`'s rule.

    Presence is decided by `_present` — the same trimming predicate `has_identity` uses
    — so the two can never disagree about what counts as an empty email cell.

    Returns `(sendable, held)`: `sendable` is every row whose `email` is present, in
    input order. `held` is one entry per remaining row, each
    `{"index": int, "row": dict, "reason": str}` naming the row's original position (in
    `rows`, not `sendable`), the row itself, and why it is held. Every input row appears
    in exactly one of the two outputs; neither list mutates an input row; no file is
    written.
    """
    sendable: list = []
    held: list = []
    for i, row in enumerate(rows):
        if _present(row.get("email")):
            sendable.append(row)
        else:
            held.append(
                {
                    "index": i,
                    "row": row,
                    "reason": (
                        "no usable email — the deployed ingest lane resolves a contact "
                        "by email only, so this row would reach HubSpot as no write "
                        "and no object id, silently"
                    ),
                }
            )
    return sendable, held


def write_dispatch_csv(rows, out_path, mapping_path=None) -> None:
    """Write dispatch-ready CSV bytes to `out_path` for Phase 23's dispatch.py to POST.
    `rows` is a list of flat dicts (canonical prop -> value); the header is every
    canonical prop, in the same deterministic order every time, with an empty cell where
    a row has no value.

    This is the STRUCT-01 enforcement site: any row key outside the canonical set —
    including a `provenance` key smuggled in by a caller that forgot to strip it — raises
    rather than widening the header, so the strip is structural, not a runtime filter
    someone can forget to call.

    It is also the STRUCT-02 email-gate enforcement site: a row with no usable `email`
    RAISES rather than being written with an empty email cell. A return value (a
    filtered list) is something a caller can ignore; the failure this guards against —
    a row silently disappearing once it reaches HubSpot — must be loud at the call
    site. A caller that wants to separate and report held rows first should call
    `hold_emailless(rows)` and pass only its `sendable` half here.

    Both guards below run BEFORE `out_path` is opened, so a refused call leaves the
    filesystem untouched — not even an empty file is created.
    """
    header = canonical_props(mapping_path)
    allowed = set(header)

    for i, row in enumerate(rows):
        extra = sorted(set(row.keys()) - allowed)
        if extra:
            raise ExtractionError(
                "non_canonical_key_in_row",
                f"Row {i} carries key(s) outside the canonical set and cannot be "
                f"written to the dispatch CSV: {extra}",
            )
        if not _present(row.get("email")):
            raise ExtractionError(
                "emailless_row_cannot_ingest",
                f"Row {i} has no usable email — the deployed ingest lane resolves a "
                "contact by email only, so this row would reach HubSpot as no write "
                "and no object id. Call hold_emailless(rows) first to separate and "
                "report rows like this one, then pass only its 'sendable' half here.",
            )

    out_path = Path(out_path)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if row.get(col) is None else row.get(col) for col in header])


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: extraction.py <artifact_path>"}))
        raise SystemExit(1)

    try:
        _artifact = load_artifact(sys.argv[1])
        _result = validate(_artifact)
    except ExtractionError as _e:
        print(json.dumps({"ok": False, "code": _e.code, "error": str(_e)}))
        raise SystemExit(1)

    print(
        json.dumps(
            {
                "ok": True,
                "accepted": _result.accepted,
                "rejected": _result.rejected,
                "dropped_keys": _result.dropped_keys,
                "ambiguities": _result.ambiguities,
                "collapses": _result.collapses,
            }
        )
    )
