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

   Then say, before answering anything else, that **review writeback is disarmed: nothing
   reaches HubSpot until the operator says yes to a specific record's exact write.** Say it
   even if the operator only asked a question.

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

3. **Let the operator pick one record.** One record at a time. Do not batch approvals
   across records, and do not pick for them.

4. **Elicit the decision and a reason.**

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

5. **Show the exact write, from the backend, before anything is sent.**

   ```
   review_decision.preview_decision(config, object_type, record_id, decision, reason)
   ```

   The `would_write` map it returns is **the backend's own computed patch**, not a
   reconstruction made here. Show every key and value in it. On an approval it is a
   multi-key patch and includes a provenance blob that can run to kilobytes — summarise the
   blob as "the audit trail entry for this decision" rather than pasting it.

   Preview works whether or not writeback is armed and whether or not the environment
   variable in step 6 is set. That is deliberate: the operator cannot approve what they
   cannot see.

   If the preview comes back with `available: false`, or with a non-writing outcome
   (`stale`, `no_candidate`, `not_flagged`, `refused`), report it now in the operator's
   terms — what happened, that **nothing was written**, and what to do next — and do not
   offer to submit. In particular:
   - `stale` — the record changed since the pipeline froze this candidate. Nothing written,
     still queued. Re-run enrichment or reject with a reason.
   - `no_candidate` — the record is in the queue but holds nothing to promote. Every
     contact is in this position, and so is every record flagged as a possible duplicate.
     There is a reason to record, but nothing to approve.
   - `not_flagged` — the record is not in the queue. Nothing to decide.

6. **Confirm this record's exact write, then submit it.**

   Read the exact write back to the operator and get an explicit yes for **this record**.
   **That yes is the arm.** An affirmative answering the exact write just shown — "yes",
   "go ahead", "do it", "please" — arms `review_armed=True` for that one submit and nothing
   else. There is no phrase to learn: an operator saying yes must never have to produce the
   system's wording to be heard (VOCAB-05).

   Disarmed is the default and the state of every new conversation, and it is the state
   again after every submit: consent here is per record, never per session, however many
   records have already been worked. An affirmative that answers nothing, answers some
   other question, or arrives before the exact write has been read back does **not** arm
   anything — read the write back and ask again. Anything ambiguous is not consent.

   **A yes here authorizes this record's write and nothing else.** It does not arm the
   contact-upload lane or the enrichment lane, and a yes given on either of those does not
   authorize a review write. Say so plainly if the operator seems to expect otherwise.
   None of it is written to disk; it exists only as an argument passed for this one call.

   ```
   review_decision.submit_decision(config, object_type, record_id, decision, reason,
                                   reviewed_by, review_armed=True, preview=preview)
   ```

   **If it refuses with `reason: "submit_not_enabled"`, relay the message as given and
   stop.** That refusal is about `ALLOW_REVIEW_SUBMIT`, an environment variable on the
   machine this plugin runs on, which **only an administrator sets**. This skill cannot set
   it, this conversation cannot set it, and you must not offer to — do not export it, do
   not write it into a file, do not tell the operator to run a command, and do not suggest
   any way around it. Ask them to contact whoever administers this plugin. Rejecting a
   record still works without it, and so does previewing; say so, because that is often the
   thing the operator actually needs right now.

7. **Report verified or failed — from the re-read, never from the response.**

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

   Then offer the next record.

## What this skill never asks the operator to do

Run a command, edit a file, paste a secret, or set an environment variable. If something
cannot be done from this conversation — the environment variable in step 6, the backend's
own `ALLOW_HUBSPOT_REVIEW_WRITES` allowlist, a missing config key — name it, say who can do
it, and stop there.
