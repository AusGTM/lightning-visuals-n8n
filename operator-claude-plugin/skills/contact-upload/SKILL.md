---
name: contact-upload
description: Load a contact spreadsheet (CSV or XLSX) into HubSpot through the n8n enrichment backend. Use when the operator asks to load, upload, or import contacts into HubSpot from a spreadsheet — or invoke it directly as /operator-claude-plugin:contact-upload.
---

# Contact Upload

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


This skill turns a spreadsheet into a `hubspot/contact-upload` request. It never maps
columns, normalizes phone numbers, verifies emails, or resolves identity — n8n's
`Map Columns` node and everything downstream of it in `wf_contact_ingest_cloud.json`
already does that. This skill's whole job is: read the file unchanged, show what would
be sent, and — only when explicitly armed — send it.

## Steps

1. **State the target up front, before any other work.** Run:

   ```
   python3 scripts/config_gate.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator
   exactly as given, then STOP. Never show, echo, or ask for a secret, and never
   surface a raw socket or parser error — the script has already translated that.

   If it reports `"ok": true`, tell the operator the endpoint from `"target"` and that
   dispatch is currently **disarmed** for this conversation. Say this even if the
   operator only asked a question, before doing anything else.

   **Then read `"can_send"`.** When it is `false`, this config can read and preview but
   **cannot send at all** — a key it needs is unset. Say so in this same first message,
   relaying `"send_blocked_reason"` exactly as given (it names the key, the file, and who
   has the value). Then carry on and build the preview normally: previewing costs nothing
   and showing the operator their own file parsed is useful even when sending is
   unavailable. But for the rest of this conversation, **do not offer the arming phrase
   and do not ask whether to send** — there is nothing to arm, and inviting an operator to
   arm a send that will be refused wastes their decision. Step 5's arming paragraph is
   skipped entirely; step 6 is unreachable. If they ask to send anyway, repeat the reason
   and name the admin as the person who can fix it.

2. **Resolve the input file.** If the operator has attached a file in this session, try
   reading it at whatever path the attachment resolves to, inside a single try/except.
   If that is unavailable, ask the operator to `@mention` the spreadsheet by name (the
   autocomplete picker, not a typed path) — `@` reaches any file already in the
   workspace, and this is the reliable leg for a file that lives elsewhere on disk (a
   Downloads folder, a Desktop file) once attached. If neither path resolves, ask the
   operator directly for one. Do not scan temp directories, retry in a loop, or guess at
   a storage convention.

   **If the input is not a spreadsheet** — pasted text, a JSON blob, a URL, or one or
   more images — the file-reading path above does not apply. Read
   `extraction.md` in this skill's own directory and follow it instead: it is the
   extraction contract for everything that isn't already tabular. Once it hands you the
   validator's accepted rows, continue at step 3 below with those rows in place of a
   read file — everything from the preview onward is identical either way.

3. **Build and show the preview.**

   ```
   python3 scripts/preview.py <path>
   ```

   This reads the file once and reads `config/column_mapping.yaml` only as a read-only
   lookup for labelling — it never changes what gets sent. The file goes over the wire
   exactly as read; canonical mapping happens on the backend's `Map Columns` node. Treat
   the preview as a prediction of what the backend will do, not a transformation this
   plugin performed.

   Render the result as a **markdown table in chat by default.** Only publish it as an
   Artifact if the operator asks for one. Always show:
   - the total row count (`row_count`)
   - each source header next to the canonical prop it maps to, from `header_labels`
     (e.g. `Email Address → email`)
   - every dropped header called out explicitly (`"dropped": true` — no canonical prop
     matched), and any canonical prop no header maps to (`unmapped_canonical_props`,
     e.g. a missing email column)
   - if `mapping_available` is `false`, say plainly that labels are unavailable rather
     than guessing them

   If `adaptive` is `true` (more than ~20 rows), do not print every row. Show instead:
   the leading and trailing sample rows (`sample_rows.leading` / `.trailing`) and the
   per-column fill rates (`fill_rates`) — including for dropped columns, since a column
   the backend will drop is exactly the one the operator wants to notice. If `adaptive`
   is `false`, show every row from `sample_rows`.

   **For a batch that came from `extraction.md` rather than a file,** the preview shows
   everything above plus what a spreadsheet preview never needs: provenance beside each
   row (which input it came from, and where in it), the rejected rows with their
   reasons, any reported keys that did not map to a canonical prop, and the single
   ambiguity block — one list of every uncertain cell in the batch, presented once,
   never one interruption per row.

4. **Ask for approval.** If the operator declines, STOP here — nothing is sent, and
   nothing beyond reading the file has happened. Declining costs nothing beyond that one
   read.

5. **Check arming.** Skip this step entirely when step 1 reported `"can_send": false` —
   see there. Otherwise: disarmed is the default and the state of every new conversation.
   Say plainly that sending is off, and that the operator can turn it on for this
   conversation only by saying: **"arm the upload"**. This state is never written to
   disk — it exists only as the `armed` flag passed to the one dispatch call below, for
   this turn only.

6. **Dispatch only once the operator has said the arming phrase this turn.**

   ```
   python3 scripts/dispatch.py <path> armed
   ```

   The webhook response you get back here is the raw JSON body `dispatch.py` printed
   under `"response"` — hand it to the next step exactly as returned, unparsed.

7. **Report the outcome — per record, not a bare acceptance.**

   First, check whether the synchronous body from step 6 is even usable: import
   `scripts/report.py` (its functions are a library, the same way
   `scripts/config_gate.py`/`scripts/tabular.py` already are, not a CLI) and call
   `sync_response_is_sufficient(body)` on it.

   n8n Cloud's webhook response is cut off by a Cloudflare-enforced ceiling of
   roughly one hundred seconds (a 524 on breach) — treat crossing it, or any
   connection/gateway error from step 6, as a fallback trigger, not a failed send.

   - **If the body is sufficient** (every item carries a row-identifying field, or is
     a full HubSpot object with an `id` and `properties`), render the outcome
     directly from it.
   - **If it is not** — thin, `Set Review`-shaped (only a `queue` marker), or the POST
     timed out/gatewayed — correlate and fetch through `scripts/executions_client.py`
     instead: resolve the `LV Contact Ingest (Cloud template)` workflow id, list its
     recent executions, call `find_execution_for_dispatch()` against the time you
     sent the POST, then `get_execution()` on the result. Feed that execution into
     `scripts/report.py`'s `build_contact_report()` to get the counts, the ledger,
     and the in-flight state.

   When the report came from the executions API, **say so in your own words**, and
   say the run may still be progressing — a report built this way is never presented
   as a finished one, even when it already shows some rows landing (D-03).

   Then render, in this order:
   1. **Summary counts first** — created / updated-matched / needs_review / rejected
      (and not-confirmed, if any write was gated or filtered before it reached
      HubSpot).
   2. **The failing rows in full**, each with its reason and its identity (a contact
      id or HubSpot object id) or, failing that, its position in the batch — these
      are the actionable ones regardless of batch size.
   3. **The successful rows** only when the batch is small; above the small-batch
      threshold, offer the complete per-record detail on request rather than
      printing it — full per-row detail can carry contact PII (email, phone, name),
      so keep it to the actionable subset or an explicit ask. Never paste a raw
      execution payload into the conversation.

   If a row's `email_status` is `NO_EMAIL` and its outcome is `ambiguous`, say
   plainly that this row cannot resolve on retry — the deployed workflow searches
   HubSpot only by email, so it will land in `needs_review` on every attempt until it
   gets an email address or is handled manually in HubSpot. Do not present it as an
   ordinary retryable failure.

   Finally, print the run handle (execution id, if you have one) and state plainly
   when it was matched by time proximity rather than returned by the webhook, so the
   operator knows it could name a neighbouring run. Tell them they can ask for a
   re-check whenever they want one — **the re-check happens only when they ask**.
   Never offer a countdown, an automatic refresh, or a "checking again shortly"; this
   skill does not watch a run on its own.

8. **Re-check, only when the operator asks.** The report handed you a run handle in step
   7. If the operator asks to re-check it, perform exactly **one** fetch —
   `resolve_workflow_id()` → `list_executions()` → `get_execution()` on that same
   execution id via `scripts/executions_client.py` — and render `build_contact_report()`
   again from the fresh result. Do not schedule anything, do not offer to keep watching,
   and do not promise to come back on your own: the unprompted bounded watch that checks
   without being asked is a later capability (built once, deliberately not here), and
   this step exists so it never grows a poll loop in the meantime. Re-checking happens
   only when the operator asks for it, every time.

9. **Retry a transport failure — same dispatch, same arming gate.** Step 7's report
   tags every failing row with what a re-send can and cannot fix. Only rows tagged
   `transport_failure` (`resendable_rows`) are worth re-sending; offer those, by name,
   if any exist.

   State the safety property in your own words before retrying: re-sending is safe
   because the backend resolves identity on every row and updates a record it already
   has rather than creating a second one — the client keeps no record of what it
   previously sent, on purpose, since a client-side ledger of accepted rows would be a
   second dedupe authority that can drift from the backend's own. This holds for rows
   carrying an email address. Point at any `permanently_stuck` rows and say plainly
   those are not part of the re-send — they need an email address or manual handling in
   HubSpot, not another attempt.

   To retry, hand the same file straight back to the **one** dispatch entry point —

   ```
   python3 scripts/dispatch.py <path> armed
   ```

   — the same function, the same arguments, the same arming gate as step 6. A re-send
   is a send: if the operator has not said the arming phrase again this turn, this call
   refuses exactly as an original send refuses. There is no separate retry function and
   nothing to parse out of the failed subset — reuse the send you already have. Then
   return to step 7 to report the new outcome.

10. **Clean up.** If this batch came from `extraction.md`, delete the scratch artifact
    you wrote once the batch ends — whether it was dispatched or the operator declined.
    Provenance is scoped to this session and to the operator's decision in the moment;
    it is not a durable record, the scratch directory is gitignored so it never reaches
    history, and deleting the file is what keeps it from outliving the conversation on
    disk.
