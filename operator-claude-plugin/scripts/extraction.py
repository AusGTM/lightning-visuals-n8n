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
"""
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from preview import resolve_mapping_path

SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"


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
    accepted: list       # [{"row": {canonical: value}, "provenance": {...}}, ...]
    rejected: list       # [{"index": int, "reason": str}, ...]
    dropped_keys: list   # [{"index": int, "key": str}, ...]
    ambiguities: list = field(default_factory=list)


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
        raise ExtractionError(
            "mapping_unreadable", f"config/column_mapping.yaml could not be read: {e}"
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
    """
    props = set(canonical_props(mapping_path))
    groups = identity_groups(mapping_path)

    accepted: list = []
    rejected: list = []
    dropped_keys: list = []

    for i, record in enumerate(artifact.get("records", [])):
        try:
            if not isinstance(record, dict):
                rejected.append({"index": i, "reason": "record is not an object"})
                continue

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

            if not has_identity(clean_row, groups):
                rejected.append(
                    {
                        "index": i,
                        "reason": (
                            "no identity present: needs a non-blank 'email', or all "
                            "three of 'firstname'/'lastname'/'company' non-blank"
                        ),
                    }
                )
                continue

            accepted.append({"row": clean_row, "provenance": provenance})
        except Exception as e:  # one bad record must never crash the batch
            rejected.append({"index": i, "reason": f"parse error: {e}"})

    return ExtractionResult(
        accepted=accepted,
        rejected=rejected,
        dropped_keys=dropped_keys,
        ambiguities=artifact.get("ambiguities", []),
    )


def write_dispatch_csv(rows, out_path, mapping_path=None) -> None:
    """Write dispatch-ready CSV bytes to `out_path` for Phase 23's dispatch.py to POST.
    `rows` is a list of flat dicts (canonical prop -> value); the header is every
    canonical prop, in the same deterministic order every time, with an empty cell where
    a row has no value.

    This is the STRUCT-01 enforcement site: any row key outside the canonical set —
    including a `provenance` key smuggled in by a caller that forgot to strip it — raises
    rather than widening the header, so the strip is structural, not a runtime filter
    someone can forget to call.
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
            }
        )
    )
