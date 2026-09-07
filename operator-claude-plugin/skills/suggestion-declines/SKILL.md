---
name: suggestion-declines
description: Review and work the backlog of people a suggestion round declined to send — send, defer, delete, or export each one, any time, without running a new round first. Use when the operator asks to review, work, drain, or clear the suggestion declines, asks what people are still waiting from an earlier suggestion round, or invokes it directly as /operator-claude-plugin:suggestion-declines.
---

# Work the Suggestion Declines

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under.

A `suggest-contacts` round declines to send a person for one of five reasons — no usable
email, a personal mailbox, a stranger's email domain, an unknown company domain, or a weak
search source — and persists them to `suggestion_declines.json` instead of sending or
dropping them. This skill is the durable, standalone surface for that backlog (D-69-08,
surface 2): it opens with no round running, shows every person any round has ever declined,
and lets the operator work through them at their own pace. `suggest-contacts/SKILL.md`
step 9 points here at the end of every round rather than reimplementing any of this.

## Steps

1. **Check configuration, then read the store and say honestly what you saw.**

   `scripts/suggestion_declines.py` is a library, not a CLI — import it, alongside
   `config_gate`, the same way every other batch skill in this plugin does. Load
   configuration first, in its own fence — this skill binds it here and reads it again,
   unchanged, at the `send` step below, the same way every other batch skill in this
   plugin binds `config` once at its own first step:

   ```python
   config = config_gate.load_config()
   ```

   If loading raises `ConfigError`, relay its message to the operator exactly as given
   — it already names the missing key and where to fix it — and STOP.

   Then call `suggestion_declines.classify_read()`, which returns one of `absent` (no
   file — no one has ever been held), `parseable` (read cleanly) or `anomalous` (the
   file exists and could not be read). On `anomalous`, say so plainly — the store exists
   and could not be read — rather than reporting an empty backlog; an empty report over
   an unreadable file tells the operator there was nothing to look at when there may be
   plenty. On `absent`, say plainly there is nothing to drain, and stop there: this is
   not an error and nothing here halts — it is the honest report that no one has ever
   been held.

   Otherwise, read the whole backlog. With no round in progress there is no run handle
   to compare declines against, so everything currently in the store is backlog — never
   `this_run`:

   ```python
   declines = suggestion_declines.load()
   batch = suggestion_declines.partition_by_run(declines, None)
   ```

2. **Render one numbered list, oldest run first.** Per entry, in `batch["backlog"]`:
   the person's name and job title, the company, the reason in the operator's own
   words using the same five-code vocabulary `suggest-contacts` step 9 already uses
   (no usable email, a personal mailbox, a stranger's email domain, an unknown company
   domain, or a weak, rank-3 search source), the entry's own prose `reason`, the run it
   was declined in (`entry["run_id"]`), and its locator — render
   `entry["provenance"]["locator"]` and nothing else from that dict. Number the list so
   the operator can answer by number.

3. **The operator picks an action per entry.** There are four actions and no fifth:
   `send`, `defer`, `delete`, `export`. State what each costs, in one line each:

   - `send` writes to HubSpot and goes through every gate a normal send goes through —
     it is not exempt from any of them.
   - `defer` costs nothing at all — the entry is left exactly as it is and reappears in
     the next batch.
   - `delete` is permanent and records nothing in its place, so a later round that
     rediscovers the same person offers them again, exactly as if they had never been
     held before.
   - `export` writes a spreadsheet and leaves the entry in the store — it is a copy,
     not a move, and the entry stays until it is sent or deleted.

   This per-entry choice is genuine, and there is no default to state instead of asking
   it: the operator answers per entry, by number, and every entry gets its own answer.

4. **Send.** Nothing here opens a grant or dispatches on its own. Everything that does
   either lives in `enrich-before-ingest/SKILL.md`'s own steps 5 and 7, re-entered
   verbatim below — this skill deliberately keeps no copy of those fences, so there is
   only ever one place those gates live.

   **(a) Build and validate the records here, because nothing downstream will.**
   `enrich-before-ingest/SKILL.md` step 5 is grant/autonomy/pause only, and its step 7
   starts from rows its own step 2 already validated — a drained row that is not
   validated in this fence is never validated at all. One record per chosen entry,
   the operator-supplied field(s) merged onto the stored row, the entry's own
   `company_id` carried through onto the row — it is what makes the ingest lane
   re-associate the contact (CLAUDE.md 13.0.1's manual override), and it survives both
   `preingest.strip_enrichment_extras` and `extraction.write_dispatch_csv`'s STRUCT-01
   guard because it is a member of `extraction.canonical_props()`:

   ```python
   records = [
       {"record_type": "contacts",
        "row": {**entry["row"], **supplied.get(key, {}), "company_id": entry["company_id"]},
        "provenance": entry["provenance"]}
       for key, entry in chosen.items()
   ]
   extraction.validate(suggest_contacts.round_artifact(records))
   rows = [record["row"] for record in records]

   send_ids = sorted({entry["company_id"] for entry in chosen.values()})
   send_domains = [record["row"]["email"].rpartition("@")[2] for record in records]
   allow_create = True
   ```

   `extraction.validate()` is the gate on whatever the operator typed, exactly as it is
   for a spreadsheet-typed address; step 7's own `extraction.hold_emailless` is the
   backstop if the field is still missing after this fence, so a still-emailless row is
   held there rather than written blank. `send_ids` names the company records the
   armed window is scoped to — the person does not exist in HubSpot yet, so there is no
   contact id to name. `send_domains` is one domain per chosen row, the figure
   `plan_grant`'s `suggestion_companies=` prices. `allow_create = True` — a decline is a
   person not yet in HubSpot; the ingest lane's own dedupe still decides
   create-vs-update. `config` is already bound at step 1, read again here unchanged. A
   stored row never carries a `row_id`, so there is nothing to strip on the way in.

   **(b) Hand `rows` to `enrich-before-ingest/SKILL.md` step 5's grant block, then its
   step 7 dispatch block, VERBATIM and unchanged.** Step 5 is where the `write`
   autonomy level is read, the grant is planned, and the pre-spend pause happens. Step
   7 is where the CSV is built (`preingest.strip_enrichment_extras` before
   `extraction.strip_row_id`, in that order), the send is authorized, the armed window
   opens, the dispatch runs, and the outcome is recorded. A list of one row is not a
   special case — the block is written over a list.

   **(c) Then run `enrich-before-ingest/SKILL.md` step 9's mandatory end-of-run account
   over this same run and the same run id — never a second report.**

   **(d) Removal ordering.** Only after `write_grant.record_dispatch_outcome` has been
   called does step 7 of this skill apply `send` to the map, below. A refused or failed
   send leaves the person in the store, where the next drain will offer them again.

   **(e) A drained send is a normal send.** It is not exempt from the grant, the
   per-run ceiling, or any gate a spreadsheet upload clears.

5. **Defer or delete — no write, no HubSpot call.** Neither action leaves this machine
   and neither needs anything beyond what the apply step below already does. `defer` is
   a true no-op: the apply loop below returns the entry unchanged. `delete` is applied
   by that same loop and removes the entry from the store with nothing written in its
   place (D-69-07) — no tombstone, no suppression key — so the next round that finds the
   same person again offers them again.

6. **Export.** One fence, over the entries the operator chose to export:

   ```python
   header = suggestion_declines.export_rows(declines, chosen_keys, out_path)
   ```

   Tell the operator what they now have: a spreadsheet with the same column names
   `contact-upload` already accepts, one row per chosen person, with whatever field
   made this decline unsendable left blank for them to fill in. The `company_id`
   column is what re-associates the contact to the right company on the way back in
   (CLAUDE.md 13.0.1's manual override) — it must not be deleted. The entry stays in
   the store until it is sent or deleted from here, so an exported person still
   appears in the next batch unless the operator says otherwise. `contact-upload` is
   the way back in — name it.

7. **Apply and save.** For a `send`, the entry for that person is applied here only
   after `write_grant.record_dispatch_outcome` has already been called for it at the
   send step above — a refused or failed send leaves the person in the store, unchanged,
   for the next drain to offer again. `defer`, `delete` and `export` are never gated on
   anything beyond the operator's own choice.

   ```python
   for key, action in picks.items():
       declines = suggestion_declines.apply_action(declines, key, action)
   suggestion_declines.save(declines)
   ```
