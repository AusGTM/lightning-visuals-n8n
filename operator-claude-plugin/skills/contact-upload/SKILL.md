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
   unavailable. But for the rest of this conversation, **do not ask for this send at all** —
   there is nothing to arm, and inviting an operator to approve a send that will be refused
   wastes their decision. Step 5's consent paragraph is
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
   extraction contract for everything that isn't already tabular, for **people and
   companies both** (Phase 58). One read of the input produces both kinds of row in a
   single artifact, companies first (D-58-13) — never a second pass over the same
   source looking for what the first pass skipped. Once it hands you the validator's
   accepted rows, continue at step 3 below with the **contact** rows in place of a
   read file — everything from the preview onward is identical either way. The
   **company** rows do not continue in this skill: they leave for the company lane
   (`enrich-records`' companies form), never folded into this contact-ingest request.

2b. **Check the headers before you preview.** (Lettered, not renumbered — this file
   cross-references its own step numbers in eight places, and renumbering ten steps to
   insert one is a large diff whose entire risk is a stale pointer. Leave it lettered.)

   ```
   python3 scripts/header_suggest.py <path>
   ```

   This reads the same `config/column_mapping.yaml` the preview does and sorts every
   header into four lists. Branch on them:

   - **`available: false`** — say plainly that header checking is unavailable and go
     straight to step 3, exactly as step 3 already handles `mapping_available: false`.
     Never invent suggestions from a table that could not be read.
   - **`mapped`** — nothing to say. Step 3's preview already shows every mapping.
   - **`refusals`** — relay the `reason` field **verbatim**. Do not paraphrase it into
     something softer and do not offer a workaround the reason does not name. Same
     register as the backend's own `enumRefusalMessage` — a refusal that names its
     reason, not an error.
   - **`splittable`** — a full-name column. It cannot map to one property, but it CAN be
     split locally, per row, for the operator to review. Say so and run the
     `next_command` the entry gives you:

     ```
     python3 scripts/name_split.py <path> --propose "Full Name"
     ```

     Show the proposals as a table — `raw`, proposed `firstname`, proposed `lastname` —
     and put the `needs_attention` rows **first**, each with its `reason`. Those are the
     ones only a person can settle: a single word that could be a given name or a
     surname, or three parts where a middle name and a two-word surname look identical.
     A surname carrying a particle (`van der Berg`) comes back `high` confidence and
     whole — say that plainly so the operator can see the splitter is not naively cutting
     on whitespace.

     The operator may correct any row. When they are done, write the resolved pairs to a
     JSON file (a list of `[firstname, lastname]`, **one per data row, in file order**)
     and apply them:

     ```
     python3 scripts/name_split.py <path> --apply "Full Name" --resolved <resolved.json>
     ```

     The returned `split_path` carries `firstname`/`lastname` columns in place of the
     original, and becomes the path you carry forward — feed it to step 2b's
     `--confirm` pass if other headers still need correcting, then to step 3.

     Three rules. The splitter **never** applies its own proposals — `--apply` writes only
     what the operator resolved, which is why the resolved list is an argument and not
     something the tool re-derives. It refuses a resolved list whose length does not match
     the data rows, because a misaligned split silently attaches one person's surname to
     another person's row and cannot be spotted in the output. And this split is a local,
     reviewed data transform for THIS file only: it is never sent to the backend as a
     rule, never stored, and `Map Columns` still has no name-splitter.
   - **`suggestions`** — **one confirmation per header, each answered before the next is
     asked.** Show the header, the proposed canonical prop, and that header's
     `sample_values` in the same breath. The sample values are the point: a header like
     `Ph.` could be a phone column or a photo column, and an operator who has not seen
     what is in it is being asked to rubber-stamp. **A single batched yes covering
     several headers is not a confirmation and must not be accepted as one.** Declining
     costs nothing — the header stays as it is and the backend drops it, which is the
     honest outcome.
   - **`unresolved`** — say the backend will drop that column, and that this is a
     reported outcome rather than a failure. Do not offer a guess.

   Then, **only** when the operator has said yes to at least one header, run one
   invocation carrying every confirmed header:

   ```
   python3 scripts/header_suggest.py <path> --confirm "Ph.=phone" --confirm "SRC=canonical"
   ```

   Two constraints. The path is always the **original** file, never a previously
   corrected one — running the correction against its own output is how a two-round
   session rewrites a header twice. And the returned `corrected_path` becomes **the**
   path for step 3 and every step after it: one path, previewed and dispatched, so what
   the operator approves is provably what is sent. If the operator confirmed nothing,
   carry the original path forward unchanged.

   The boundary this whole step lives inside: the client corrects the header row of the
   file it sends and nothing else. It maps no data, writes no canonical-prop value into
   any row, and the backend's `Map Columns` node stays the single authority on what a
   header means.

3. **Build and show the preview.**

   ```
   python3 scripts/preview.py <path>
   ```

   The path to preview is `corrected_path` when step 2b produced one, otherwise the
   original. This preview is the operator's view of the real mapping prediction — the
   re-preview that makes an approval mean something.

   This reads the file once and reads `config/column_mapping.yaml` only as a read-only
   lookup for labelling — it never changes what gets sent. The file goes over the wire
   exactly as read; canonical mapping happens on the backend's `Map Columns` node. Treat
   the preview as a prediction of what the backend will do, not a transformation this
   plugin performed.

   **Say what the company rule means for this file, here, before any arming.** Since
   2026-08-25 the backend never creates a contact it cannot associate to a company: a new
   contact whose company cannot be resolved is **held for review**, not created. The
   backend resolves it from the contact's email domain first (a free/consumer address —
   gmail, bigpond, optusnet — resolves nothing), then from an exact company-name match,
   and it never creates a company itself. So an upload of new contacts at a company that
   is not in HubSpot yet will hold every one of those rows. If that is this file, say so
   now and offer the two ways through: enrich or create the company first with
   `enrich-records`, or give the rows a `company_id` column naming the HubSpot company
   record id directly.

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

   **The `resolvable` group (D-59-08).** A row rejected for failing the identity rule
   also appears here naming the field(s) that would satisfy it (`missing`) — do not
   leave it as a dead end. For each entry, try a resolution from `extraction.md`'s four
   legitimate sources (HubSpot lookup, an earlier operator statement, a provider result,
   or a stated derivation from another field on the row), propose the resolved value to
   the operator, and wait for a yes. On confirmation, rewrite the artifact with the
   value plus a `resolutions` entry naming the source, and re-run the validator — never
   write a resolved value on your own authority. Keep the same "presented once, never
   one interruption per row" discipline the rest of this preview follows; a resolvable
   group that interrupted per row would be exactly the friction this ruling exists to
   remove. Only after a resolution finds nothing, or the operator declines it, does the
   row stay rejected.

   **If `row_count` is 0, STOP at the preview — do not continue to step 4.** A file that
   parsed but carried no data rows and a file that is fine but has nothing to send look
   identical in the numbers, and the cost block will cheerfully report a "real, explainable
   zero" for a file that could not be read. Say plainly that no rows were found, and name
   what usually causes it so the operator can act: an empty file, a file with only a header
   row, an export of the wrong sheet, or a sheet whose data starts below some other content.
   Check `headers` and say which case it looks like — headers present with no rows is a
   different mistake from no headers at all. Then ask for a different file. **Do not ask for
   approval and do not ask for this send at all**: there is nothing to approve, and inviting a
   decision that cannot matter wastes it. (Same reasoning as the `can_send: false` branch in
   step 1.)

4. **Ask for approval — unless a grant already carries it.** With no grant open: if the
   operator declines, STOP here — nothing is sent, and nothing beyond reading the file has
   happened. Declining costs nothing beyond that one read.

   **Under an open grant covering this lane and these records, do not ask again.** The
   operator already approved this send when they opened the grant: the envelope's
   arithmetic and the consequence sentence were what they said yes to, and that yes was
   given *before* the run rather than during it (D-53-06, operator 2026-08-25). Asking
   "shall I proceed?" here would restore the very stop-and-ask the grant exists to remove —
   half the friction, none of the protection. Say which grant the send runs under, then go
   straight on. The preview above is still rendered and still shown; under a grant it
   informs rather than gates, because the gate moved earlier.

5. **Ask for this send, in the operator's own words.** Skip this step entirely when step 1
   reported `"can_send": false` — see there. Otherwise: disarmed is the default and the
   state of every new conversation. Say plainly that sending is off, then ask for this send
   by naming what it will do — how many rows, and that it writes them to HubSpot. **An
   affirmative answering that question — "yes", "go ahead", "do it", "please" — arms this
   send and nothing else.** There is no phrase to learn: an operator saying yes must never
   have to produce the system's wording to be heard (VOCAB-05).

   **Consent counts only where it is attached to what was shown.** An affirmative that
   answers nothing, or answers some other question, or arrives before this send has been
   described, does **not** arm anything — ask once more, naming what will happen, and take
   that answer. Anything ambiguous is not consent: treat it as not armed, and ask. This
   state is never written to disk — it exists only as the `armed` flag passed to the one
   dispatch call below, for this send only. Arming this send arms nothing else: not the
   next send on this lane, not the enrichment lane, not the review lane.

   **If a write grant covering this lane and these records is already open, do not ask at
   all.** Say which grant the send is running under and dispatch under it —
   not asking twice is the whole point of a grant. With no grant open, everything above is
   exactly as it is today.

   **A grant removes the question, not the safety.** The preview still runs and is still
   shown, the records are still named, each send still arms and disarms its own window
   bounded to that send's records, and a failed disarm is still reported loudly as its own
   state. Revoking a grant **refuses the next send** — it **does not stop a dispatch already
   running**, so a revoke arriving mid-dispatch still lets that send finish.

   Whichever consent applies — a standing grant, or this send's own yes — step 6's dispatch
   opens the same kind of record-scoped armed window; see there for the code (F2,
   2026-08-25: the yes now arms a window for this send, where it used to arm the command
   line's own POST only, and nothing on the backend).

6. **Dispatch under an open grant, or otherwise only once the operator has said yes to
   this send.**

   **Every send opens its own record-scoped armed window — never a bare dispatch with the
   backend still disarmed.** Under a grant, `write_grant.authorize_send` builds the
   decision from it. With no grant open, this send's own yes is what authorizes it:
   `write_grant.authorize_ungranted_send` builds a single-use grant scoped to exactly this
   send's records — using the SAME `allow_write_grants` authority and the SAME Guardrail A
   dirty-backend refusal a standing grant gets — and discards it once this dispatch
   finishes; it is never remembered as a standing grant, never written to disk. Both
   functions return the identical `{armed, workflow_id, grant, refusal, detail}` shape, so
   the dispatch is the same call either way:

   `send_ids`/`send_domains`/`allow_create`/`send_path`/`send_row_count` are whatever the
   earlier steps resolved for this send (`send_row_count` is `row_count` from step 3's
   preview) — bound to real names here, never left as angle-bracket placeholders, because
   this block is executable Python and an AST test (`test_write_grant.py`) `compile()`s it
   (REVIEW-57-M4):

   ```python
   import chunking, config_gate, dispatch, n8n_arming, write_grant

   cfg = config_gate.load_config()
   decision = (
       write_grant.authorize_send(
           grant, lane="contacts",
           record_ids=send_ids, record_domains=send_domains)
       if grant is not None else
       write_grant.authorize_ungranted_send(
           cfg, lane="contacts", object_type="contacts",
           record_ids=send_ids, record_domains=send_domains,
           allow_create=allow_create, label="this send")
   )
   if not decision["armed"]:
       # revoked, closed, outside the grant, the admin has not enabled write grants, or
       # the backend is not in a known-disarmed state — STOP and report decision["detail"]
       ...

   # Phase 57 / D-57-01 / REVIEW-57-H7: THE FOURTH DISPATCH PATH. This is a single-shot
   # send — the whole file in one POST — with no chunk boundary to stop mid-run at, so
   # the ceiling check is PRE-CALL. `ok` — bounded by the sampled monthly remainder;
   # `unknown` — self-bound to this batch's own quote (REVIEW-57-H6), never left
   # unbounded; `over` is reached only when the operator overrode the preflight refusal.
   ceiling = decision["grant"]["ceiling"]
   if ceiling["verdict"] == write_grant.CEILING_OK:
       execution_ceiling = ceiling["remaining_sampled"]
   elif ceiling["verdict"] == write_grant.CEILING_UNKNOWN:
       execution_ceiling = ceiling["projected_executions"]
   else:
       execution_ceiling = ceiling["projected_executions"]

   would_be = 1 + send_row_count
   if execution_ceiling is not None and would_be > execution_ceiling:
       # DO NOT SEND. The rows go to the remainder queue with
       # `remainder_queue.REASON_CEILING_BREACH` (57-03's store — this disposition is
       # prose here until 57-03 Task 3 lands and wires it; the guard above is real code
       # now). Tell the operator spending stopped BEFORE this send, name the file's rows
       # as recoverable — nothing here is lost, only unsent — and close the grant for
       # the breach.
       grant = write_grant.record_dispatch_outcome(
           decision["grant"], None, cfg, reason=write_grant.CLOSED_CEILING_BREACH)
   else:
       # Grant closure on every exit (REVIEW-57-H8/M5): `outcome`/`disarm` start None so
       # an exception raised before `dispatch.dispatch()` returns cannot leave either
       # name unbound when the closure below runs.
       outcome = None
       disarm = None
       crashed = False
       try:
           with n8n_arming.armed_window(decision["workflow_id"], send_ids, send_domains,
                                        allow_create, cfg, grant=decision["grant"]) as window:
               result = dispatch.dispatch(send_path, True, cfg)
               # One spend vocabulary (REVIEW-57-H7): wrap this single-shot send's
               # result into the SAME `DispatchOutcome` shape every chunked leg
               # produces, so `chunking.projected_spend` sees it exactly as it sees a
               # chunked leg — never a second "extra spend" argument anywhere.
               outcome = chunking.single_dispatch_outcome(
                   result, record_count=send_row_count, run_id=result["run_id"])
           disarm = window.disarm_result
       except Exception:
           crashed = True
           raise
       finally:
           close_reason = write_grant.CLOSED_UNHANDLED_ERROR if crashed else None
           grant = write_grant.record_dispatch_outcome(
               decision["grant"], outcome, cfg, disarm=disarm, reason=close_reason)
   ```

   The allowlist handed to `armed_window` is **this send's records, never the grant's whole
   record set**. That narrowing is what keeps every window strictly smaller than the grant
   it runs under; passing the grant's full list would widen every window to the whole batch
   and every test would still pass.

   `dispatch.dispatch` returns `{"body": <the raw JSON body>, "run_id": <str>,
   "written_records_failures": [...]}`, not a bare body. The webhook response step 7 works
   from is `result["body"]` — hand it to the next step exactly as returned, unparsed. This
   send is now recorded, at the write site, into a `written_records-<run_id>.json` artifact
   in the plugin's durable state directory (`scripts/written_records.py`) — the same
   artifact a write grant's own consequence sentence already promises at arming time,
   regardless of which lane the grant covers. There is nothing to say about this to the
   operator here unless `result["written_records_failures"]` is non-empty: when it is, say
   so plainly before step 7's report, the same way `enrich-before-ingest`'s D-59-10 relay
   does — this send's own outcome could not be recorded even though the write itself may
   already have landed; a bookkeeping miss is never a dispatch failure.

7. **Report the outcome — per record, not a bare acceptance.**

   First, check whether the synchronous body from step 6 is even usable: import
   `scripts/report.py` (its functions are a library, the same way
   `scripts/config_gate.py`/`scripts/tabular.py` already are, not a CLI) and call
   `sync_response_is_sufficient(body)` on it, where `body = result["body"]`.

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

   **Report the association, per row, alongside the write.** Each row in the
   synchronous body carries `association`: `associated` (the contact is now linked to
   `company_id`), `not_confirmed` (the association was gated or HubSpot refused it —
   the contact landed, the link did not), `not_attempted`, or `none` (no company was
   resolved for this row). A row whose `action` is `review` with a `reason` mentioning a
   company was **held on purpose** — nothing was written for it, and it is not a failure
   to retry blindly. Name those rows individually with their reason.

   **Offer the manual override for held rows, once, in that same message.** The operator
   can answer with the company for any held row, in one line per row:

   - `<row>. company: <hubspot company id>` — associate this row to that company record.
   - `<row>. company: <domain>` — the company's website domain, if they have that rather
     than the id; look it up with `enrich-records`' companies form first, then use the id
     it resolves.

   Apply the answers by adding a `company_id` column to that row in a **new** dispatch CSV
   (never the operator's original file) and re-sending it through step 6's arming gate — a
   re-send is a send. Do not carry an answer over to a row the operator did not name.

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
   is a send: if the operator has not said yes to this re-send, this call
   refuses exactly as an original send refuses. There is no separate retry function and
   nothing to parse out of the failed subset — reuse the send you already have. Then
   return to step 7 to report the new outcome.

10. **Clean up.** If this batch came from `extraction.md`, delete the scratch artifact
    you wrote once the batch ends — whether it was dispatched or the operator declined.
    Delete the corrected file step 2b wrote the same way, for the same reason: same
    scratch directory, same end-of-batch rule, dispatched or declined alike. That covers
    both artifacts 2b can produce — the header-corrected copy and any split-name copy.
    Provenance is scoped to this session and to the operator's decision in the moment;
    it is not a durable record, the scratch directory is gitignored so it never reaches
    history, and deleting the file is what keeps it from outliving the conversation on
    disk.
