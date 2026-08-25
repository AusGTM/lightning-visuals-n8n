---
name: backend-control
description: Turn backend workflows on or off, switch an individual scheduled job on or off, change a job's schedule in plain words, start an ingestion run, or enable live writes for one specific send. Use when the operator asks to stop or start something, pause or resume a job, run things more or less often, reschedule, "turn on live mode", or send a batch for real — or invoke it directly as /operator-claude-plugin:backend-control.
---

# Backend Control

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


**This skill changes things.** Its whole shape is one rule: the operator is told exactly
what will change, in plain language, and nothing mutates until they have said an explicit
yes to that exact statement. Everything runs through `scripts/control_actions.py` — never
call `n8n_control`, `n8n_arming`, or `n8n_cadence` directly, and never touch the n8n API
yourself. Any path around the choke point is a path around the confirmation. Write grants
have their own choke point, `scripts/write_grant.py`, with the same rule: plan, show,
confirm with an explicit yes, and never arm around it.

## The shape of every action

1. **Plan.** Call `control_actions.plan_action(request, config)`. It reads the current
   state and returns a proposal: the consequence sentence, the before-and-after values,
   and the one-step undo.
2. **Show.** Read the operator the `consequence` verbatim or near-verbatim, plus the
   before → after values, plus how they would undo it. Small change, small message — but
   never skip the consequence.
3. **Confirm.** Ask, and wait. Only an explicit yes proceeds. On yes, call
   `control_actions.execute_action(proposal, "yes", config)`. On anything else — silence,
   "maybe", a new topic — nothing happens, and say so.
4. **Report the verdict, not the request.** The result's `outcome` comes from an
   independent re-read of the backend. `verified` means the re-read showed the change;
   say so and quote the `reversal` sentence. `failed` means **the change did not take
   effect** — say exactly that, never "done". A `200` from n8n is not success and is
   never described as such.

## What each action sounds like

**Turning a workflow on or off** — the consequence names what stops running, including
how many scheduled jobs go quiet with it.

**Switching one scheduled job on or off** — the consequence says the *other* jobs keep
running untouched. This is the answer when someone wants one poller paused without
stopping the whole backend.

**Changing a schedule** — ask for the cadence in plain words ("hourly", "every weekday
at 9am"). The proposal repeats back what that was understood to mean, in words, and shows
the current cadence next to it. The operator confirms *meaning*. **Schedule syntax never
appears in either direction** — if they paste cron-looking syntax, the plan step refuses
with example phrases; relay the examples, don't translate the syntax.

**A phrase that can't be confidently understood is refused, not guessed.** The refusal
carries at least three worked examples — offer them as-is. A misread schedule silently
changes how often the backend spends provider credits, which is why guessing is the one
thing this surface never does.

**A cadence proposal can also come back as a budget refusal.** Before proposing a
schedule change, the plan step adds up what the WHOLE schedule would cost per month —
every scheduled job in the workflow, not just the one being changed — and refuses if that
total busts the configured budget share. That refusal carries the arithmetic (the
requested job's own monthly cost, the whole schedule's monthly cost, the ceiling, and the
plan allowance): show the operator those numbers verbatim, exactly as you would any other
refusal.

The refusal also names one exact phrase — `"override the budget floor"` — that lets that
one change through anyway, for that one change only. **Never volunteer the override
before the refusal has been shown.** Showing the numbers first and offering the escape
hatch only after is the whole point of the gate; a skill that leads with the override
defeats it. If the operator then asks to go ahead anyway, pass their exact words back as
the request's `budget_floor_override_phrase` field and re-plan — the resulting proposal's
`consequence` restates the arithmetic plus a sentence about the deployed build's per-tick
dispatch cap not moving with a runtime-only cadence change; read that back in full before
asking for confirmation, same as any other proposal. The override does not persist: a
later cadence change, even in the same conversation, needs its own explicit override.

**Starting a run** — `control_actions.start_lane(lane, config, armed=..., payload=...)`.
It delegates to the lane's own dispatch path with its preview, cost guard, and arming
gate fully intact — this skill adds no shortcut around them. A lane whose dispatcher
hasn't shipped is refused by name with the reason; offer what does work.

**Enabling live writes for a send** — presented to the operator as **one action**, not
three. The consequence covers the whole cycle: live writes on for this send only,
bounded to exactly the records in this batch (the backend cannot write any record
outside that list), and off again the moment the send finishes. Do not ask three
separate confirmations for arm, send, and disarm — one decision, one confirmation.
If the result comes back `disarm_failed`, that is its own state, and the operator must
be told in so many words: **live writes may still be enabled, and an admin needs to
check n8n directly.** Never summarize that away, and never report the send as cleanly
finished around it.

**Opening a write grant** — the same shape one step larger: one action, one confirmation,
for a whole named batch instead of one send. `write_grant.plan_grant(...)` composes the
proposal and `write_grant.open_grant(proposal, "yes", config)` opens it; only the exact
string `yes` proceeds, exactly as `execute_action` does. Show the operator the envelope as
arithmetic before the yes — the record count, worst-case provider credits per provider,
worst-case Anthropic dollars, projected n8n executions and the configured monthly
allowance — plus which lanes it covers, which records, and whether creates are included.
Then ask once. **Say what the figure is:** it discloses what the batch can cost, it does
not prevent it, and the remaining monthly allowance is not yet checked before starting.

While the grant is open, each send in that batch arms and disarms its own window bounded
to that send's records — never the grant's whole set — without asking again. The grant
needs `allow_write_grants` set to the JSON boolean `true` in `operator.local.json` by an
n8n admin; with it unset, `plan_grant` refuses and names the key, the file, and who sets
it. Do not tell the operator to set a shell environment variable: `ALLOW_N8N_ARM` still
gates the scheduled and cron paths, and it is not something an operator in this
conversation can set.

**Revoking a grant** — `write_grant.revoke_grant(grant)`, and it is idempotent. Say
plainly when it bites: it **refuses the next SEND**, and it **does not stop a dispatch
already running**. At the two-record chunk ceiling a forty-record send is twenty chunks,
and all twenty go out after a revoke. Never describe revoking as stopping the run.

**Closing a grant** — `write_grant.close_grant(grant, reason)`, with a reason from the
recorded set; a free-text reason raises rather than being silently accepted. A grant also
closes on its own on completion, session end, an error, a ceiling breach, or two
consecutive disarm failures. Closing arms nothing and disarms nothing by itself — each
send already disarmed its own window.

## What gets refused, and how to say it

A refusal is a boundary, not a malfunction — deliver it as one:

- **Changing workflow structure, nodes, or credentials:** "This plugin operates the
  backend — turning things on and off, scheduling, and sends. Changing what the backend
  *is* — its nodes, its structure, its credentials — is done by an admin from the
  repository. Ask your n8n admin."
- **Running a scheduled scan right now, off-cycle:** relay
  `control_actions.start_scheduled_scan()`'s answer — n8n has no way to fire a workflow
  on request (verified against this instance), and the two available levers are turning
  the workflow on/off and re-timing the job. Offer to do either.
- **Missing configuration:** the config gate's message already names the missing key and
  what still works. Relay it; don't call the plugin broken when only one capability is
  unconfigured.

## Never

- Never mutate without a shown consequence and an explicit yes for *that* proposal.
- Never re-use a confirmation across actions — one yes, one change.
- Never render schedule-expression syntax to the operator, in either direction.
- Never describe a `failed` verdict as anything but "this did not take effect".
- Never quietly tidy a `disarm_failed` — it outranks whatever else was being reported.
