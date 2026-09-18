---
name: backend-status
description: Report what the HubSpot enrichment backend is doing — which workflows are switched on, what is running right now, whether anything has been running too long, why the last failure failed, and how many records are waiting on a human. Use when the operator asks what the backend is doing, what is running, whether something is stuck or wedged, whether enrichment is working, how many records are waiting for review, or whether a provider has run out of credit — or invoke it directly as /operator-claude-plugin:backend-status.
---

<!-- CRM-ACCESS-BLOCK v1 (D-14a/D-14b/D-14d, D-15a/D-15b/D-15c/D-15d) -->
<!-- Canonical source: operator-claude-plugin/config/crm_access_block.md -->
<!-- Do not edit this block inside a SKILL.md. Edit the canonical file above and copy it -->
<!-- verbatim into every skill; test_crm_access_block.py pins that every copy matches. -->

**Before any HubSpot access this session, read this.**

**Portal rule (D-14a).** Any HubSpot tool outside this plugin's own lanes — the claude.ai
HubSpot connector, an MCP HubSpot server, the `hs` CLI — must prove IT is on portal
`22617666` before its first call this session, read or write. The proof is that tool
looking up, through itself, a record this plugin knows exists: an `hs_object_id` from
`written_records`, or the configured sentinel id. Zero results is the lookup proof
failing — it means the wrong portal: stop the step and say so, naming the portal the
plugin expects and the record that was not found. Do not retry, do not fall back to a
plugin lane silently, and do not treat a zero result as "the record does not exist." The
2026-09-18 session's connector was on a different portal and returned zero results for
contacts the plugin had just created — this rule exists to stop exactly that. This rule
is skill text the assistant follows when reading this skill; there is no runtime hook
and no code gate enforcing the portal proof.

**Connector-write rule (D-14b).** A write through such a tool, once its portal is
proven, is under the SAME session grant as every other write path: call
`write_grant.covers()` before it, append the outcome to `written_records` with
`source: connector`, and associate a created contact to its company in the same step,
exactly as the ingest lane does. One yes governs all paths.

**Session-grant rule (D-15a/b/c/d).** The first yes covers the whole session — every
lane, and the domains and ids named in that proposal. Every later send goes through
`covers()` on that one grant. A send outside its record set widens the grant with
`widen()` and STATES the widening; it never asks again and never opens a second grant.
Opening a second grant while one is already open is refused by the code, naming the
open grant. The ask itself is one sentence: this yes covers every send this session across the
named lanes for the named domains, widening as new domains appear, and the operator may
say revoke at any time (`CLOSED_REVOKED`).

<!-- END CRM-ACCESS-BLOCK -->

# Backend Status

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


**This skill reads. It changes nothing.** It does not turn a workflow on or off, does not
start, stop or cancel a run, does not retry anything, and writes to no HubSpot record.
If the operator asks you to act on what you find here, say plainly that this surface can
only look — turning things on and off is the `backend-control` skill's job, and it has
its own confirmation before anything changes. Point them at it rather than acting here.
An operator who believes this skill can act on their behalf is a worse outcome than one
who has to ask twice.

## On start

Before step 1, clear an expired dashboard pointer:

```
python3 scripts/artifact_store.py collect
```

That is the whole of this plugin's persisted state — one dashboard Artifact identifier
and when it was saved, nothing else — and it expires after `dashboard_artifact_ttl_days`
in the operator config (30 days by default). Collection happens here, on open, because
this client runs nothing on a schedule. Say nothing to the operator about it; it is
housekeeping, not an answer to their question.

## Steps

1. **Check the status capability's configuration first, before any other work.** Run:

   ```
   python3 scripts/status.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator
   **exactly as given** — including the part that says what still works — and then STOP.
   That message already names the missing key and where to fix it, and it never contains
   a configured value. Do not paraphrase it, do not guess at the cause, and never show,
   echo or ask for a secret.

   Note that the status check needs `n8n_url` and `n8n_api_key`. A missing
   `webhook_secret` does **not** stop it: it costs only the backend-supplied half
   (provider balances, HubSpot counts, credential health), which reports itself
   unavailable while the workflow and execution half still answers.

2. **Get the answer and render it.**

   ```
   python3 scripts/render_text.py
   ```

   This reads every workflow the n8n API key can see — there is no allowlist, so a newly
   deployed or renamed workflow is in the answer without anyone editing a config file —
   and prints the whole picture as plain text. Relay it to the operator as text. Do not
   turn it into a table unless they ask for one, and do not summarise away a count.

   Two things in that output need saying in your own words if the operator glosses over
   them:

   - **`unknown` is not zero.** A count that reads `unknown` means the backend could not
     tell us, not that there are none. Never round it down to "nothing to worry about".
   - **A wedged run's threshold is a convention, not a measurement.** The output states
     both the run's age and the threshold for exactly that reason. If a job legitimately
     takes longer than the threshold, say so rather than presenting the verdict as fact.
   - **Portal check (D-14c/D-14a), when `hubspot_portal_id` is set.** The backend reads
     the HubSpot account with the n8n credential and reports which portal it is on
     (`wf_backend_status_cloud`'s `HubSpot Account Info` probe). A "Portal check" line
     appears only when the operator has set `hubspot_portal_id` — an unset value means
     the guard did not run, not that the portal is fine. **This proves the n8n
     credential's portal only.** Any OTHER HubSpot tool used this session — the
     claude.ai connector, an MCP HubSpot server, the `hs` CLI — must still prove ITSELF
     by its own lookup (D-14a, the portal rule above); this check's result must never be
     used to skip that.

3. **When a workflow's last run failed, report the cause.** `render_text.py` already
   fetches that one execution's detail and prints the translated cause, because the
   failure is often invisible from run status alone: every provider-facing node is
   configured to carry on when it errors, so a rejected credential or an exhausted
   balance leaves the run reading `success` while nothing was actually enriched.

   If the operator names a specific execution and asks what went wrong with it:

   ```
   python3 scripts/execution_errors.py <execution_id>
   ```

   Report each finding's `sentence` and `who_can_fix`, and nothing else about it — no
   status code, no node name, no stack trace. If a finding's `is_interpretation` is true,
   say plainly that the plugin does not recognise that failure signature, keep the
   interpretation and the `raw` text visibly apart, and attribute it to an admin. Never
   tell the operator they can fix something the plugin did not recognise.

   Fetch an execution's detail only for a run already known to have failed or one the
   operator names. Never pull it for every run — those payloads are large.

4. **Answer with text. Offer the dashboard only if asked.**

   <!-- 27-05 DASHBOARD STEP — the dashboard publisher, wired by plan 27-05. -->
   **Text is the default. Never publish a dashboard unless the operator asks for one**
   — by name ("dashboard", "a page I can look at", "something I can bookmark") or by
   asking to refresh one they already have. Step 2's text answer is the answer.

   When they do ask:

   1. Get the remembered identifier, if there is one:

      ```
      python3 scripts/artifact_store.py load
      ```

   2. Build the page:

      ```
      python3 scripts/render_dashboard.py
      ```

      It prints one self-contained HTML document built from the same reading step 2
      renders as text, so the two can never disagree about what the backend is doing.
      **Publish that HTML as an Artifact verbatim.** Do not rewrite it, do not summarise
      it, and do not build your own page from the text answer.

      **A file attachment is not a dashboard.** The deliverable of this step is the
      published Artifact's URL — the stable link the operator can bookmark and find
      again from a new conversation. If you did not call the Artifact tool, you have
      not done this step: sharing the HTML as a file skips the remembered identifier,
      breaks the same-URL promise below, and leaves the expired-pointer housekeeping
      unrun. (This exact miss happened in live UAT, 2026-08-03 — a session rendered
      the HTML and attached it as a file, and every cross-session property silently
      vanished.)

      - If step 1 returned an `artifact_id`, **update that Artifact** rather than
        creating one, so the operator's bookmarked link still works.
      - If it returned nothing, create a new one and then remember it:

        ```
        python3 scripts/artifact_store.py save <the new artifact id>
        ```

   3. Tell the operator two things about it: the link stays the same when they ask for a
      refresh, including in a new conversation, and **the timestamp on the page is when
      the data was fetched, not when the page was drawn.** A dashboard they left open is
      not a live view — it says what was true at the moment stamped on it.

   Everything on the dashboard obeys the same rule as the text: `unknown` means the
   backend could not tell us, never that the count is zero or that a provider is fine.

5. **Re-check only when the operator asks.** If they want a fresh reading, run step 2
   again — once. Do not schedule anything, do not offer a countdown or an automatic
   refresh, and do not promise to come back on your own. This skill does not watch the
   backend; it answers a question when asked.
