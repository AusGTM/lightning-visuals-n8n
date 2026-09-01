---
name: review-triage
description: Work the queue of HubSpot records the enrichment pipeline flagged for a human decision — see each conflict in plain language, approve or reject it, and have the result confirmed by re-reading the record. Use when the operator asks what needs review, what is waiting on them, to work or clear the review queue, to look at flagged or held records, or to approve or reject a specific record — or invoke it directly as /operator-claude-plugin:review-triage.
---

# Review Triage

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


The pipeline holds a decision back when it is not sure enough to write it. This skill shows
those held decisions, lets the operator adjudicate one, and reports what actually landed.

**Two things this skill never does.** It never decides for the operator which way a record
should go, and it never claims a write landed because the request was accepted. The verdict
always comes from re-reading the record afterwards.

**The backend owns the policy, not this skill.** The protected-field labels below are a
*display* lookup so the operator knows before they invest in a decision. This client never
refuses a decision on policy grounds — the endpoint is the one authority on what may be
written, and a second opinion here would be a second authority that drifts from it.

## Steps

1. **Check configuration and state the arming position, before any other work.**

   `scripts/review_queue.py` and `scripts/review_decision.py` are libraries, not CLIs —
   the same way `scripts/report.py` is. Import them (`python3` with
   `operator-claude-plugin/scripts` on the path, as `conftest.py` does for the tests) and
   call `config_gate.load_config()` first.

   If loading raises `ConfigError`, relay its message to the operator **exactly as given**
   — it already names the missing key, where to fix it, and what still works — and STOP.
   Never show, echo, or ask for a secret.

   Then say, before answering anything else, the **accurate two-part position** (D-60-01,
   D-60-04, Phase 60): nothing reaches HubSpot until the operator says yes to a specific
   record's exact write, **and** a write grant covering that record must be open. The
   operator can open that grant right here in this conversation — no shell, no deploy —
   once an n8n admin has set `allow_write_grants` in `operator.local.json`. Say it even if
   the operator only asked a question.

2. **Fetch the queue.**

   ```
   review_queue.fetch_queue(config, object_type)      # "companies" or "contacts"
   ```

   It returns `{available, reason, object_type, total, returned, rows}`.

   **If `available` is `false`, the queue was not read — say so and stop.** Do not describe
   an unavailable queue as an empty one. `hubspot_search_did_not_run` in particular means
   HubSpot refused the search, not that the backlog is clear; telling the operator nothing
   needs review when nothing was read is the worst answer this skill can give. Name the
   reason in plain language and say who can fix it.

   If `available` is `true`, render with:

   ```
   review_queue.render_queue(rows, total, policy_lookup, link_lookup)
   ```

   The two lookups are **exactly** these — `link_lookup` takes the whole **row** and must
   extract `hs_object_id` itself, because `render_record` passes it the row, while
   `record_link` takes an **id**. Composing them any other way renders a broken URL with
   the entire row dict in it (found live, RB-9 step 5):

   ```python
   policy_lookup = lambda field: review_queue.policy_class(object_type, field)
   link_lookup = lambda row: review_queue.record_link(
       object_type, row.get("hs_object_id"), config.get("hubspot_portal_id"))
   ```

   `total` greater than `returned` means this is a page, not the whole backlog — the
   rendering already says so. Companies and contacts are separate fetches; if the operator
   asks "what needs review" without saying which, show both.

3. **Let the operator pick which records to work this sitting.** Do not pick for them. They
   may name one record, several, or say to work the whole page shown — either way, the
   records named here are what step 4 scopes the sitting's authority to.

4. **Open the sitting — one grant, one batch window, for the whole sitting (D-60-06).**

   Mint the run id before any HTTP call — the same run this sitting's `written_records`
   artifact and step 8's account are both keyed by:

   ```python
   import n8n_arming, run_state, write_grant

   run_id = run_state.new_run_id()
   ```

   **If a grant already open from an earlier enrichment or contact-ingest batch in this
   conversation covers the records step 3 named, reuse it (D-60-02) — do not open a
   second one.** One grant opened for any of the three lanes covers all three together, so
   a record already enriched or ingested under an open grant can be triaged here with no
   second deliberate yes.

   **Otherwise, plan and open a grant over exactly the records step 3 named,** naming
   `lanes=["review"]` and `providers=[]` — a review batch spends no provider credit, and
   naming the configured provider selection here would price the envelope against credits
   this sitting never touches:

   ```python
   proposal = write_grant.plan_grant(
       config, lanes=["review"], object_type=object_type,
       record_ids=record_ids, record_domains=record_domains, allow_create=False,
       providers=[])
   ```

   Present the proposal exactly as any other grant offer is presented, and only once the
   operator confirms:

   ```python
   grant = write_grant.open_grant(proposal, confirmation, config)
   ```

   Then open **one** batch window over the grant's own record scope and hold it for the
   **whole sitting** — every record picked in step 3, not one window per decision:

   ```python
   batch = write_grant.authorize_review_batch(grant)
   if not batch["armed"]:
       # relay batch["detail"] and stop — nothing to open, nothing armed
       ...
   ```

   ```python
   with n8n_arming.armed_review_window(
           batch["workflow_id"], batch["record_ids"], batch["record_domains"],
           config, grant=grant) as window:
       ...  # steps 5-8 run inside this block, once per record the operator picked
   # window.disarm_result is available once the block exits — on the happy path,
   # on a mid-sitting exception, and on a mid-sitting revocation alike (the context
   # manager's own guarantee, unchanged from the per-send window dispatch already uses).
   ```

   **Say plainly that the window is grant-wide but every decision inside it is still
   checked per record** (D-60-03): a record the grant does not name is refused even
   mid-sitting, exactly as if no window were open at all — the batch window widens WHEN
   the backend accepts a review write, never WHAT it may write.

5. **Elicit the decision and a reason.**

   The two decisions are **approve** and **reject**, and nothing else is a decision word.

   - **Approve** promotes the record's own held candidate through the backend's existing
     non-clobber merge.
   - **Reject records the operator's reason and leaves the record in the queue.** Say it in
     those words. A rejection does not clear, dismiss, remove, resolve or close anything —
     the record is still flagged afterwards and will still appear in this queue. A review
     flag is never cleared without a recorded decision.

   **Ask for a reason every time**, in the operator's own words, and say why: the reason is
   what makes this decision legible to whoever reads the record in six months. If they
   decline to give one, **accept the decision anyway** — a decision without a reason is
   still a decision. Do not block on it and do not invent one.

6. **Show the exact write, from the backend, before anything is sent.**

   ```
   review_decision.preview_decision(config, object_type, record_id, decision, reason)
   ```

   The `would_write` map it returns is **the backend's own computed patch**, not a
   reconstruction made here. Show every key and value in it. On an approval it is a
   multi-key patch and includes a provenance blob that can run to kilobytes — summarise the
   blob as "the audit trail entry for this decision" rather than pasting it.

   Preview works whether or not a grant is open and whether or not the batch window from
   step 4 is armed. That is deliberate: the operator cannot approve what they cannot see.

   If the preview comes back with `available: false`, or with a non-writing outcome
   (`stale`, `no_candidate`, `not_flagged`, `refused`), report it now in the operator's
   terms — what happened, that **nothing was written**, and what to do next — and do not
   offer to submit. In particular:
   - `stale` — the record changed since the pipeline froze this candidate. Nothing written,
     still queued. Re-run enrichment or reject with a reason.
   - `no_candidate` — the record is in the queue but holds nothing to promote. Every
     record flagged as a possible duplicate is in this position: there is a reason to
     record, but nothing to approve. A contacts approve does not land here today, because
     no contact currently in the review queue holds a candidate — approving a contact is
     a real write: its enriched value was already saved to HubSpot at the moment the
     record was flagged, so approving promotes nothing new; it takes the record out of
     the queue and records who decided and when.
   - `not_flagged` — the record is not in the queue. Nothing to decide.

7. **Confirm this record's exact write, then submit it.**

   Read the exact write back to the operator and get an explicit yes for **this record**.
   **That yes is the arm.** An affirmative answering the exact write just shown — "yes",
   "go ahead", "do it", "please" — arms `review_armed=True` for that one submit and nothing
   else. There is no phrase to learn: an operator saying yes must never have to produce the
   system's wording to be heard (VOCAB-05). **This per-record ritual is unchanged by the
   grant** — what changed underneath it is only the authority, never the act.

   Disarmed is the default and the state of every new conversation, and it is the state
   again after every submit: consent here is per record, never per session, however many
   records have already been worked. An affirmative that answers nothing, answers some
   other question, or arrives before the exact write has been read back does **not** arm
   anything — read the write back and ask again. Anything ambiguous is not consent.

   **A yes here authorizes this record's write and nothing else.** It does not arm the
   contact-upload lane or the enrichment lane, and a yes given on either of those does not
   authorize a review write. Say so plainly if the operator seems to expect otherwise — the
   per-record consent stays lane-specific even though, since Phase 60, one grant now spans
   all three lanes: the grant is the authority, the yes is still the act.

   ```
   review_decision.submit_decision(config, object_type, record_id, decision, reason,
                                   reviewed_by, review_armed=True, grant=grant,
                                   run_id=run_id, preview=preview)
   ```

   **If it refuses with `reason: "grant_not_authorized"`, relay the message as given and
   offer to open a grant covering this record — the same offer step 4 makes at the start of
   a sitting, scoped to just this one record if that is all the operator wants right now.**
   That refusal replaces the old shell-environment-variable refusal this skill used to
   produce, which no longer exists: opening a grant is something the operator can do from
   this conversation, so route them there rather than to an administrator.

   **One true sentence about what a reject achieves with no grant open, said plainly and
   not softened (cross-AI review MEDIUM-3, D-60-07 amendment):** a reject is always
   *sent*, even with no grant open — that carve-out survives — but the deployed backend
   checks its own record allowlist before it looks at the decision word, so a reject on a
   record no open grant covers still comes back `not_allowlisted` and the record **stays
   flagged**. Do not promise the operator that rejecting always clears the queue entry.
   Relay whichever outcome came back, and if it is `not_allowlisted`, offer the same remedy
   an approve gets: open a grant covering the record.

8. **Report verified or failed — from the re-read, never from the response.**

   ```
   review_decision.verify_decision(preview["would_write"], response)
   ```

   Report its `status` and `message`:

   - **`verified`** — the record was read back after the write and holds the approved
     values. This is the only wording that means the change landed.
   - **`failed`** — say plainly that the change is **not confirmed** and the operator should
     check the record in HubSpot. This covers a mismatch (the named fields are in the
     message), a record that could not be read back, and an empty or unreachable response.
     An empty response usually means this record is not on the backend's allowlist — a real
     "nothing was written", not a broken tool. Never soften a `failed` into "probably fine".
   - **`not_written`** — the endpoint's own non-writing outcome. Relay its message; nothing
     changed and the record is still queued.

   Then offer the next record — still inside the same batch window from step 4, until the
   operator is done with this sitting.

   **When the sitting ends, give the end-of-run account (D-60-08).** Read this run's own
   artifact through
   `written_records.load(path=written_records.written_records_path(run_id))` — never the
   path-less `written_records.load()`, which would fold in every previous run's writes too.

   Tell the operator which records this sitting actually wrote to HubSpot, from that
   file's own entries — not from what was asked for, and not from the response body of any
   one submit. **A decision whose bookkeeping failed still landed** — the write always wins
   over the log (D-59-10) — and is reported as such from the `written_records` key on that
   decision's own submit envelope (`True` on a clean append, or the exception's type name
   when the append itself failed); a bookkeeping failure never means the write did not
   happen, only that this file may be missing that one entry.

## What this skill never asks the operator to do

Run a command, edit a file, or paste a secret. If something cannot be done from this
conversation — a missing config key, or the admin's `allow_write_grants` settings key that
turns on grant-opening in the first place — name it, say who can do it, and stop there.
