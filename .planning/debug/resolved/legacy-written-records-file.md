---
status: resolved
trigger: "P5 item 3 from .planning/HANDOVER-2026-08-29-backlog.md — legacy written_records.json in the operator's durable directory: test debris or genuine pre-change operator file? Decide and either document or delete."
created: 2026-08-29
updated: 2026-08-29
resolution: deleted-as-debris
---

# Legacy `written_records.json` — provenance and disposition

Not a debug session (no defect to reproduce). An investigate-and-decide item, run inline by the
orchestrator on the operator's ruling of 2026-08-29: *"investigate provenance, then you decide."*

## The handover's claim, and why it does not hold

`.planning/HANDOVER-2026-08-29-backlog.md` § P5 said the file was:

> Kept deliberately — it is the only artifact demonstrating why `load()`'s glob is not
> hyphen-anchored.

**That is false.** `operator-claude-plugin/tests/test_written_records.py:359`,
`test_load_globs_and_finds_a_legacy_pre_change_filename_too`, pins exactly that behaviour
hermetically:

```python
def test_load_globs_and_finds_a_legacy_pre_change_filename_too(tmp_path, monkeypatch):
    """The glob is `written_records*.json`, NOT hyphen-anchored — an artifact an
    operator already has under the pre-D-59-09 shared filename must not vanish."""
    _patch_durable_dir(monkeypatch, tmp_path)
    legacy = directory / "written_records.json"
    legacy.write_text(json.dumps({... "entries": [{... "hs_object_id": "1" ...}]}))
    written_records.append_chunk("run-new", 0, {"action": "update", "hs_object_id": "2"})
    entries = written_records.load()
    assert {e["hs_object_id"] for e in entries} == {"1", "2"}
```

It writes its own un-hyphenated `written_records.json` in `tmp_path` and asserts the legacy
entry survives the union. The glob (`WRITTEN_RECORDS_GLOB = "written_records*.json"`,
`scripts/written_records.py:81`) is therefore permanently demonstrated by a test that needs no
file in the operator's real durable directory. The live file was redundant for that purpose.

Note also that the handover pointed the reader at `load()`'s glob without naming the module;
`artifact_store.py` also has a `load()` and it has no glob and no `written_records` reference at
all. The relevant `load()` is `scripts/written_records.py:290`.

## Provenance — untraceable to any operator walk

| Check | Result |
| --- | --- |
| `run_id` present in any walk record or planning doc | **No.** `grep -rn "2acd52f7" .planning/` returns nothing. |
| The two sibling hyphenated files' run_ids | **Both traceable.** `c24bfb6ee35840258a50b7a5abdb6e04` and `7f9893dacf6b48bb812ce5a31d4bc53f` both appear in `53-WALK-RECORD-2.md` (lines 185/205 and 392) — those are genuine walk-run artifacts. |
| Content | Three `contacts` chunks, **every one `"outcome": "not_written"`**, every `hs_object_id` null. A disarmed run. Zero records written, therefore zero audit value. |
| `saved_at` | `2026-08-28T21:09:54.252356+00:00` — during the Phase 59 development session, which STATE.md records as ending `2026-08-28T21:37:49Z` after plan 59-09. |
| Test-suite debris? | No — the autouse `no_durable_writes` fixture blocks tests from writing there. |

Conclusion: **development debris from a disarmed dev run during Phase 59 work**, not operator
data and not test-suite debris.

## Active cost of keeping it

`written_records.load()` with no `path` unions every `written_records*.json` in the durable
directory (D-59-09). Keeping this file means its three phantom `chunk_index` 0/1/2
`not_written` entries are folded into every future no-path read, in an operator-facing surface,
attributed to a run that no record explains. That is a live cost, not inert clutter.

## Disposition — deleted

Deleted from
`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/written_records.json`.

Its full content is preserved verbatim here, so the deletion is reversible by writing this JSON
back to that path:

```json
{"run_id": "2acd52f7eb314e81a7e295de4a9f8917", "saved_at": "2026-08-28T21:09:54.252356+00:00", "entries": [{"chunk_index": 0, "object_type": "contacts", "action": null, "hs_object_id": null, "outcome": "not_written", "reason": null}, {"chunk_index": 1, "object_type": "contacts", "action": null, "hs_object_id": null, "outcome": "not_written", "reason": null}, {"chunk_index": 2, "object_type": "contacts", "action": null, "hs_object_id": null, "outcome": "not_written", "reason": null}]}
```

The two genuine walk artifacts (`written_records-c24bfb6e….json`,
`written_records-7f9893da….json`) were **not** touched.

## What must NOT be inferred from this

The glob stays `written_records*.json`, not hyphen-anchored. Deleting this one debris file does
not license tightening the glob: a real operator may still hold a genuine pre-D-59-09
`written_records.json`, which is precisely what `test_written_records.py:359` protects. Do not
"simplify" that glob.
