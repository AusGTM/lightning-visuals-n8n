# Operator Usage Guide

A task-oriented guide to running the Lightning Visuals enrichment backend from Claude.
During everyday use you never open a terminal, n8n, or a config file — you talk to Claude,
and this plugin does the rest. (One-time setup is the exception: you fill two values into a
settings file yourself, so no secret ever passes through the chat.)

For how the plugin works underneath, see [README.md](README.md); this guide is about *what to say* and *what to expect*.

**One habit that covers everything:** describe what you want in plain words. You never need
to remember a command name — every skill triggers off ordinary phrasing. The slash forms
(e.g. `/operator-claude-plugin:contact-upload`) exist, but "load this spreadsheet into
HubSpot" works just as well.

---

## First-time setup

> "Set up the enrichment plugin" · "Is the plugin configured?"

Run once after installing, or whenever something says a setting is missing. Claude checks
the configuration, tells you exactly which keys are present or absent, and walks you through
anything that needs filling in. If another task ever refuses with a message about a missing
key, this is the skill it is pointing you at.

**Needs an admin first:** the backend itself (n8n Cloud workflows, credentials) must already
be deployed. This plugin is the steering wheel, not the engine.

---

## Loading contacts into HubSpot

### From a spreadsheet

> "Load this contact spreadsheet into HubSpot" · "Upload contacts.csv"

Give Claude a CSV or XLSX (drag it into the chat or name the path). You get:

1. **A preview first, always.** How many rows, how the columns mapped, what looks wrong
   (bad emails, duplicates, unmapped headers). Nothing is sent yet.
2. **Your approval, then an explicit arm.** Approving the preview sends nothing by itself;
   nothing reaches the backend until you also say **"arm the upload"** — and that arm lasts
   for this conversation only.
3. **A per-record outcome report.** Created / updated / refused, each with a reason, and a
   safe retry path for transport failures. (A row with no email address is called out
   separately — it cannot resolve on retry and needs an email or manual handling in HubSpot.)

Not limited to spreadsheets — pasted text, a JSON export from another tool, a URL, even a
screenshot of a table all work. Claude extracts a contact table, shows the same preview, and
proceeds the same way.

### Enrich first, then load

> "Enrich these contacts before uploading them" · "Fill in the gaps before they go in"

Same as an upload, but each new contact is matched against HubSpot and enriched from the
data providers *before* it is created — so nothing lands in HubSpot incomplete. Costs
provider credits; the preview includes a cost estimate before you approve. This flow asks
for permission **twice**, at two different moments — once before any provider credit is
spent, and again (after a full enriched preview) before anything is written to HubSpot.

## Enriching records already in HubSpot

> "Enrich these companies: 123, 456" · "Run the waterfall on the June Prospects list"

Works by record ID or by naming a HubSpot list — you never need a HubSpot login or token;
the backend resolves list names itself. Before anything runs you see a **cost guard**: how
many records (for a list, the honest word "unknown" — the backend resolves list counts, and
the plugin won't invent a number), which providers will be called, and the estimated credit
spend. Approve, say **"arm the enrichment"**, and Claude dispatches, watches the run until
it settles, and reports per-record outcomes read back from the run itself.

Two things to know:

- **Writes are off at rest.** Enrichment computes results, but writing them to real records
  happens only inside a deliberate, bounded "armed window" — a one-send approval you make
  explicitly. If nothing is armed, results are computed and reported to you, and nothing at
  all is written to HubSpot.
- **Provider choice is per-request.** "Enrich with Apollo only" works; so does "no
  providers" (spends nothing).

## Asking what the backend is doing

> "What's the backend doing?" · "Is anything stuck?" · "How many provider credits are left?"

A read-only dashboard in words: which workflows are on, what is running right now, whether
anything has been running suspiciously long, why the last failure failed, how many records
wait on a human, and remaining Lusha and ZoomInfo credits (Apollo has no readable credit
pool — it always shows "unknown", and that is normal, not broken). Safe to ask any time — it
changes nothing.

## Starting and stopping things

> "Pause enrichment" · "Turn the dedupe job off" · "Run the review poller weekly instead"
> "Start an ingestion run now"

Four backend mutations exist, and only these four: switch a workflow on/off, switch an
individual scheduled job on/off, change a job's schedule (in plain words — "daily", "every
weekday at 9am"; you will never see cron syntax), and a one-shot arm-dispatch-disarm cycle
for a specific send. (Starting an ingestion run is also available, but it goes through the
lane's own preview, cost guard, and arming — this skill adds no shortcut around them.)
Everything shows you a plan and asks for confirmation before touching anything, and tells you how to reverse it. Anything outside that list is refused by
construction — refused before any change is possible, not caught after.

**Budget note:** every schedule fire costs one n8n execution against a **2,500/month plan**.
The shipped cadences (daily/weekly/monthly, ~95 executions/month idle) are set against that
budget — speeding a job up multiplies its cost. The *deployed build* refuses to bake a
cadence that fast, but a schedule change made here applies at runtime without a rebuild.

That runtime path has its own budget floor. Before showing you a cadence proposal, the
plugin adds up what the **whole schedule** — every scheduled job in the workflow, not just
the one you're changing — would cost per month, and refuses the change if that total busts
a configured share of the plan allowance (`n8n_monthly_execution_allowance`,
`n8n_schedule_floor_max_share`), stating the requested cost, the whole-schedule cost, the
ceiling and the allowance before anything else. You can let a refused change through
anyway, for that one change only, by saying the exact phrase the refusal gives you — the
override never persists to a later change or a later session, and each time you say it the
consequence is restated in full, including that the deployed build's per-tick dispatch cap
was derived from the *previous* cadence and does not move with a runtime-only change.

**Boundary:** this floor guards the plugin's own cadence action only. A trigger re-timed
directly in the n8n editor bypasses it entirely — that path is what the unattended sweep's
burn-rate alarm backstops instead, by watching the actual execution rate rather than a
schedule's declared interval.

## Working the review queue

> "What needs review?" · "Show me the review queue"

Records the pipeline flagged for a human decision, one at a time, in plain language: what
the conflict is, what each source claims, and the exact property write that approval would
send — computed by the backend, shown to you *before* it happens. Approve, say **"arm review writeback"**, and — provided
the admin-set submit switch is on — the write is made and then **re-read to confirm it
landed**; reject and your reason is recorded and the record stays queued (rejection never silently clears anything). Protected fields are
labelled; the backend, not the client, is what enforces protection.

## Why are we losing deals?

> "Why are deals being lost?" · "Loss reasons against ICP tier"

Builds a report of closed-lost reasons cross-tabulated with each company's ICP tier and
score — the pattern-finder for things like "we lose Tier A deals on price." Read-only.

## The unattended sweep

Not something you invoke — a scheduled check an **admin** installs on your machine (see
`skills/backend-sweep/SWEEP-CRON-TEMPLATE.md`). Once installed, it watches the backend with
no session open and raises a notification only when something needs a human: a failed run, a
dead credential, an exhausted quota, a stuck lock, a review backlog past its threshold, or
live-write permission left switched on with nothing dispatching (the residue of a crash
between arming and disarming).

Silence means healthy — and a sweep that *runs* but cannot do its job is loud about it (a
banner, a non-zero exit, a "not configured" notice). One silence it cannot break: a schedule
that was never installed, or that has stopped firing, produces nothing at all — which is why
"the sweep never notifies" is the first admin-table row to check. You can preview what the next unattended fire would say with
"run the backend sweep."

---

## What keeps you safe

- **Nothing writes without a preview and your approval.** Uploads, enrichment writes, review
  decisions, control actions — all show you the exact change first.
- **Writes are disarmed at rest.** Turning a workflow on does not enable writes; those need
  their own explicit, bounded arming, scoped to the specific records of that send.
- **One deliberate exception, and it can only delete work, not create it:** when the write
  gate is closed, the scheduled poller clears its own queue flags (so a closed gate can
  never re-create the runaway loop that once burned 73× the monthly execution budget).
  That path can write exactly two bookkeeping values and nothing else.
- **Verification is by re-reading, never by trusting a success response.** When this plugin
  says "verified", it re-fetched the record and looked.
- **Refusals are explicit.** A record that wasn't processed says so and says why — nothing
  is silently dropped, capped, or skipped.

## When to call the admin

| Symptom | Why it's the admin |
| --- | --- |
| "Not configured" errors that setup can't resolve | Backend keys/deploys live outside the plugin |
| Provider credits exhausted | Buying credits is a commercial action |
| The unattended sweep never notifies | The schedule is installed on your machine by an admin |
| You want live writes enabled for a batch send | The one-shot armed send only works in a shell where an admin has set the arming switch (`ALLOW_N8N_ARM`) |
| You want something faster than daily and the budget floor refuses it | The refusal names the exact one-time override phrase; raising the plan's execution allowance itself is a commercial decision an admin owns |
| Review approvals refuse with "submit not enabled" | `ALLOW_REVIEW_SUBMIT` is an environment variable only an administrator sets; previewing and rejecting still work without it |
