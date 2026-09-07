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

4. **Send.** *(This step is filled by a later task of this plan — it re-enters
   `enrich-before-ingest/SKILL.md`'s own steps for the write, adding no fences of its
   own.)*

5. **Defer or delete — no write, no HubSpot call.** Neither action leaves this machine
   and neither needs anything beyond what the apply step below already does. `defer` is
   a true no-op: the apply loop below returns the entry unchanged. `delete` is applied
   by that same loop and removes the entry from the store with nothing written in its
   place (D-69-07) — no tombstone, no suppression key — so the next round that finds the
   same person again offers them again.

6. **Export.** *(This step is filled by a later task of this plan — it writes a
   spreadsheet the operator fixes by hand and feeds back through `contact-upload`.)*

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
