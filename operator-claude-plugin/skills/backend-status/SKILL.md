---
name: backend-status
description: Report what the HubSpot enrichment backend is doing — which workflows are switched on, what is running right now, whether anything has been running too long, why the last failure failed, and how many records are waiting on a human. Use when the operator asks what the backend is doing, what is running, whether something is stuck or wedged, whether enrichment is working, how many records are waiting for review, or whether a provider has run out of credit — or invoke it directly as /operator-claude-plugin:backend-status.
---

# Backend Status

**This skill reads. It changes nothing.** It does not turn a workflow on or off, does not
start, stop or cancel a run, does not retry anything, and writes to no HubSpot record.
If the operator asks you to act on what you find here, say plainly that this surface can
only look — turning things on and off is a separate capability that does not exist yet.
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
