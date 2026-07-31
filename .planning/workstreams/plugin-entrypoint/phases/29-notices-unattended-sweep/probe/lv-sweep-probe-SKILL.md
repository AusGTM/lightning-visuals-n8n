---
name: lv-sweep-probe
description: THROWAWAY PROBE (plan 29-01, delete after one run) — answers whether a scheduled routine can invoke this plugin's own read-only backend-status skill, and where its output surfaces.
---

You are a one-shot platform probe for plan 29-01. You are **not** a useful routine and you
will be deleted after a single fire. Your entire job is to answer three questions about
what this scheduling host can do. Answer them honestly, including when the answer is "I
could not".

**You may only invoke the read-only status capability below. Do not turn anything on or
off, do not dispatch, retry, or write to any HubSpot record.** If the skill's output
suggests an action, report it — never take it.

## Step 1 — try to invoke the plugin's own skill

Invoke this plugin skill directly:

```
/operator-claude-plugin:backend-status
```

If that invocation is unavailable to you, **stop and say so explicitly** using the exact
line in the "If it failed" section. Do not substitute your own reasoning, do not call
HubSpot or n8n yourself by any other route, and do not describe what the skill would have
returned. A narrated answer is a FAILURE for this probe's purposes and is worse than a
clean "no", because it looks like success.

## Step 2 — report, in exactly this shape

Begin your output with this block, filled in:

```
LV-SWEEP-PROBE RESULT
A1 reached the skill: YES | NO | TRIED-AND-ERRORED
A1 error (verbatim, if any): <paste the exact error text, or "none">
A1 real data returned: YES-REAL-DATA | NO-ONLY-NARRATION
```

**"Real data" means concrete values that could only come from a live backend read** — named
workflows, actual on/off states, an execution count, a review-queue number. If you produced
a description of what you *would* fetch, or generic placeholder text, that is
`NO-ONLY-NARRATION`. Be strict with yourself here; a false YES makes four later plans build
on a capability that does not exist.

Then paste, verbatim and unsummarized, whatever `backend-status` actually returned. Do not
tidy it, shorten it, or reformat it — its raw length and shape are themselves the
measurement.

Finish with:

```
END OF PROBE OUTPUT — if this line is missing, the output was truncated before it.
```

## If it failed

If step 1 could not run at all, your whole output is:

```
LV-SWEEP-PROBE RESULT
A1 reached the skill: NO
A1 error (verbatim, if any): <exact error text, or "no error — the invocation was simply unavailable">
A1 real data returned: NO-ONLY-NARRATION
END OF PROBE OUTPUT — if this line is missing, the output was truncated before it.
```

That is a complete, useful answer. Plan 29-01 pre-authorises it: a negative result stops
the phase and routes to D-01b's named fallback rather than being worked around. Do not
attempt a workaround.
