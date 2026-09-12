# Operator Usage Guide

A task-oriented guide to running the Lightning Visuals enrichment backend from Claude.
During everyday use you never open a terminal, n8n, or a config file — you talk to Claude,
and this plugin does the rest. (One-time setup is the exception: you fill three values into a
settings file yourself, so no secret ever passes through the chat — see
[Installation and settings](#installation-and-settings) below.)

For how the plugin works underneath, see [README.md](README.md); this guide is about *what to say* and *what to expect*.

**One habit that covers everything:** describe what you want in plain words. You never need
to remember a command name — every skill triggers off ordinary phrasing. The slash forms
(e.g. `/operator-claude-plugin:contact-upload`) exist, but "load this spreadsheet into
HubSpot" works just as well.

---

## Installation and settings

Everything in this section is done once per machine. After it, the operator never opens a
terminal or a config file again. Steps 1–3 need a terminal; step 4 is the last time you touch
a file by hand. Nothing here asks you to type a secret into the conversation — secrets go into
the settings file directly.

### Who does what

| Task | Who |
| --- | --- |
| Deploy the n8n Cloud workflows and hold the credentials | n8n admin — the backend is the engine, this plugin is the steering wheel |
| Install the plugin, create and fill the settings file | operator (values supplied by the admin) |
| Turn on `allow_write_grants`, set `ALLOW_N8N_ARM`, install the unattended sweep | admin only |

### 1. Prerequisites

- **Claude Code** (terminal CLI or the desktop app's Code tab) with plugins enabled. All
  commands below are typed in a terminal; the plugin itself is then used from the chat.
- **`git`** on your PATH — the marketplace is fetched from a public GitHub repository.
- **Python 3** with three packages: `openpyxl`, `requests`, `PyYAML`. In the Claude Desktop
  Code-tab environment this plugin was verified against they already import; anywhere else,
  install them once from the plugin directory: `pip install -r requirements.txt`.
- **Three values from your n8n admin**, which you will type into the settings file in step 4
  (never into the chat): the `https://` address of the n8n Cloud instance, the webhook
  shared secret, and an n8n API key.

### 2. Install the plugin

```
claude plugin marketplace add https://github.com/AusGTM/lightning-visuals-n8n.git
claude plugin install operator-claude-plugin@lightning-visuals-operator
```

The first command registers the marketplace under the name `lightning-visuals-operator`
(it clones the repository to `~/.claude/plugins/marketplaces/lightning-visuals-operator`);
the second installs the plugin from it into a versioned folder under
`~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/<version>/`.

Then **restart Claude Code.** Skills bind to the installed plugin version when a session
starts; a session that was already open keeps running the old (or no) plugin until it is
restarted. `claude plugin list` shows the installed version.

### 3. Create the settings file

In a fresh session say **"Set up the enrichment plugin"** (or
`/operator-claude-plugin:initialize`). Claude runs a read-only check, tells you the **full
path** of the settings file, offers to put the template there, and lists which values are
still needed. It never asks you for a value and never shows the file back to you.

The file is `operator.local.json`. On a normal install its path is:

```
~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json
```

That folder is outside the versioned install, so the file survives every plugin update
untouched. (Resolution order, first hit wins: the `LV_OPERATOR_CONFIG` environment variable
if an admin set one; then the durable folder above; then a legacy copy at
`config/operator.local.json` inside the plugin folder; then, once, a copy left by an older
installed version, which is migrated into the durable folder for you.)

Doing it by hand instead: from the installed plugin folder (the directory holding `scripts/`
and `skills/`), run `python3 scripts/init_check.py --create`. It copies
`config/operator.local.example.json` into place and refuses to overwrite an existing file.
The file is never committed and is gitignored in the source repository.

### 4. Fill in the required keys

Open the file in any text editor and replace the three placeholders. Every value comes from
your n8n admin.

| Key | What it is | Needed for |
| --- | --- | --- |
| `n8n_url` | `https://` address of the n8n Cloud instance | everything |
| `webhook_secret` | shared secret sent as the `X-Enrichment-Secret` header on every dispatch | uploads, enrichment, matching, review decisions, the sweep |
| `n8n_api_key` | n8n API key (n8n → Settings → n8n API), sent as `X-N8N-API-KEY` on read-only calls to the executions and workflows API. A **different** secret from `webhook_secret`. | uploads, enrichment, matching, backend status, start/stop controls, the sweep — every lane that sends a batch needs it, because a batch's per-record outcome is read back from n8n's execution record |

A file with a placeholder still in it "looks filled in" at a glance and is the most common
miss; the check in step 5 names the exact key.

### 5. Verify

Say **"Is the plugin configured?"** (or run `/operator-claude-plugin:initialize` again). The
expected answer is *already set up*, plus the settings-file location. Then ask **"What's the
backend doing?"** — a read-only status call that proves `n8n_url` and `n8n_api_key` work
without changing anything. An upload preview (any small CSV) proves `webhook_secret`; the
preview sends nothing.

### Optional settings

All ship with safe defaults in the template. Change them only when you have a reason; each
`_..._note` entry in the template explains its key in full.

| Key | Default | Does |
| --- | --- | --- |
| `hubspot_portal_id` | unset | turns each review-queue record into a clickable HubSpot link; without it the raw record id is shown |
| `enrichment_providers` | `["zoominfo", "apollo", "lusha"]` | which providers an enrichment batch calls; a named subset or `[]` (spend nothing) are the other two legal values; can be overridden per batch in conversation |
| `stuck_execution_minutes` | `15` | how long an n8n execution may run before the status check and the sweep call it stuck |
| `n8n_monthly_execution_allowance` | `2500` | the n8n plan's monthly execution budget; must equal `monthly_execution_allowance` in the backend's `config/execution_budget.yaml` (a test fails when they disagree); missing or `0` means the burn-rate alarm is **off** |
| `n8n_schedule_floor_max_share` | `0.25` | share of that allowance the whole scheduled cadence may consume before a cadence change is refused; must equal the backend's `idle_floor_max_share` |
| `burn_rate_alarm_threshold` | `1.0` | the sweep alarms when the sampled execution rate, projected over 30 days, exceeds the allowance times this |
| `dashboard_artifact_ttl_days` | `30` | how long the status dashboard artifact is kept before being rebuilt |
| `watch_bound_seconds` | `600` | how long the in-session watch waits on a dispatched run before saying "still running" |
| `max_records_per_chunk` | `2` | records per enrichment POST; derived from a live timing probe against the ~100 s webhook response ceiling — do not raise without re-measuring |
| `max_rows_per_match_request` | `20` | rows per match POST; mirrors the backend constant `ENRICH_MAX_PROPOSE_RECORDS` — raise the backend first, this second |
| `column_mapping_path` | `null` | `null` uses the plugin's shipped `config/column_mapping.yaml` for spreadsheet header mapping |
| `field_policy_path` | `null` | `null` uses the shipped `config/field_policy.yaml`, read only to *label* a field as protected in the review queue |

### Admin-only switches

These change what the plugin is *allowed* to do. An operator does not set them.

- **`allow_write_grants`** (in the same settings file, default `false`). Set to the JSON
  boolean `true` to let an operator open a write grant in conversation — name a batch, see the
  worst-case spend, say yes once, and each send in that batch may arm live HubSpot writes for
  exactly the records in the grant. Absent, `false`, the string `"true"`, `1` and `"yes"` all
  read as **off**. It turns on the interactive path only; it never enables unattended writing.
- **`autonomy`** object (`read_only`, `spend_no_write`, `write`; all default **on**, including
  when the object is absent). Setting a level to the JSON boolean `false` makes rounds at that
  level ask before proceeding instead of stating the price and pausing seven seconds. It is a
  default-setter, never an authority: it cannot arm anything that `allow_write_grants` (or
  `ALLOW_N8N_ARM` for headless runs) has not already authorised.
- **`ALLOW_N8N_ARM=true`** — an environment variable, not a settings key. The sole authority
  for the headless and cron paths (`scripts/scheduled_arm.py`), which have no operator to
  confirm anything. The one-shot armed send from a conversation also only works in a shell
  where an admin has set it.
- **`LV_OPERATOR_CONFIG`** — an environment variable that points the plugin at a settings file
  somewhere other than the durable folder. An escape hatch; leave it unset unless you need it.
- **The unattended sweep** is not installed by installing the plugin. An admin installs its
  `cron`/`launchd` schedule following `skills/backend-sweep/SWEEP-CRON-TEMPLATE.md`; the sweep
  needs all three required keys and refuses loudly, not silently, when one is missing.

### Fewer permission prompts (optional)

Every task runs `python3 scripts/<name>.py` from the plugin folder through Bash, and in
Claude Code's default permission mode each run is a prompt. To allowlist exactly those, and
nothing else, add to `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["Bash(python3 scripts/*)"]
  }
}
```

Confirm with `/permissions`. This does not loosen anything about HubSpot writes — see
[Why it keeps asking permission](#why-it-keeps-asking-permission).

### Updating the plugin

```
claude plugin marketplace update lightning-visuals-operator
claude plugin update operator-claude-plugin@lightning-visuals-operator
```

Then restart Claude Code. The marketplace clone never refreshes on its own, which is why the
first command exists; the second installs the newest version into a new versioned folder.
Your settings file is not touched — it lives in the durable folder, not the install folder.
`/operator-claude-plugin:initialize` after an update should answer *already set up*.

---

## First-time setup

> "Set up the enrichment plugin" · "Is the plugin configured?"

Run once after installing (step 3 above), or whenever something says a setting is missing.
Claude checks the configuration, tells you exactly which keys are present or absent, and
walks you through anything that needs filling in. If another task ever refuses with a
message about a missing key, this is the skill it is pointing you at.

**Needs an admin first:** the backend itself (n8n Cloud workflows, credentials) must already
be deployed. This plugin is the steering wheel, not the engine.

---

## Loading contacts into HubSpot

### From a spreadsheet

> "Load this contact spreadsheet into HubSpot" · "Upload contacts.csv"

Give Claude a CSV or XLSX (drag it into the chat or name the path). You get:

1. **A preview first, always.** How many rows, how the columns mapped, what looks wrong
   (bad emails, duplicates, unmapped headers). Nothing is sent yet.
2. **The send itself.** Approving the preview sends nothing by itself. By default
   (autonomy ON, since 0.41.0) Claude states the price, waits seven seconds so you can say
   stop, then arms **that send only** — not the next one, and nothing in another lane — and
   proceeds. If your admin turned the `write` level off, Claude asks instead, and a plain
   "yes" arms the send the same way. A refusal (over the monthly ceiling, over the per-round
   cap, no write grant allowed) is a refusal on both paths; nothing proceeds past one.
3. **A per-record outcome report.** Created / updated / refused, each with a reason, and a
   safe retry path for transport failures. (A row with no email address is called out
   separately — it cannot resolve on retry and needs an email or manual handling in HubSpot.)

Not limited to spreadsheets — pasted text, a JSON export from another tool, a URL, even a
screenshot of a table all work. Claude extracts a contact table, shows the same preview, and
proceeds the same way.

**What a row needs to be usable:** an email address, *or* a LinkedIn profile URL, *or* first
name + last name + company. A row with only a LinkedIn URL is fine on its own — you are not
asked to supply a company for it. A name with neither a company nor an email is the case that
still goes to review rather than being matched, on purpose: matching the wrong person is worse
than matching nobody.

### Enrich first, then load

> "Enrich these contacts before uploading them" · "Fill in the gaps before they go in"

Same as an upload, but each new contact is matched against HubSpot and enriched from the
data providers *before* it is created — so nothing lands in HubSpot incomplete. Costs
provider credits; the preview includes a cost estimate before you approve.

**How many times you are asked depends on one thing.** Open a **write grant** for the batch
and you say yes once, and that one yes carries the whole batch — matching, enrichment,
creation and association. With no grant open the flow asks **twice**, at two different
moments: once before any provider credit is spent, and again (after a full enriched preview)
before anything is written to HubSpot.

Either way, the run itself does not stop to ask you about individual rows. Rows the system
is confident about go through; rows it is not confident about are **held** — never guessed,
never written — and the batch finishes regardless. The held rows come back at the end as
**one review list**, named person by person with the reason each is held, which you clear in
a single pass. If a run breaks partway, resuming picks up the rows that never settled rather
than re-spending credit on the ones that did; a resumed batch always asks for a fresh grant.

## Enriching records already in HubSpot

> "Enrich these companies: 123, 456" · "Run the waterfall on the June Prospects list"

Works by record ID or by naming a HubSpot list — you never need a HubSpot login or token;
the backend resolves list names itself. Before anything runs you see a **cost guard**: how
many records (for a list, the honest word "unknown" — the backend resolves list counts, and
the plugin won't invent a number), which providers will be called, and the estimated credit
spend. Approve, answer the send question with a plain "yes", and Claude dispatches, watches
the run until it settles, and reports per-record outcomes read back from the run itself.

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
send — computed by the backend, shown to you *before* it happens. Say yes to that exact
write — your yes arms that one record and nothing else — and, provided
the admin-set submit switch is on — the write is made and then **re-read to confirm it
landed**; reject and your reason is recorded and the record stays queued (rejection never silently clears anything). Protected fields are
labelled; the backend, not the client, is what enforces protection.

## Who's at these companies?

> "Who's at these companies?" · "Find contacts for these" · "Fill in who works there"

Offered automatically after a company batch, for any company with nobody named on it.

It reads **the company's own website first** — from the sitemap, toward the about / board /
team / contact pages — and everything it proposes comes from a page it actually fetched,
with that page shown next to the person so you can check it.

If the site names nobody, it may fall back to a web search, **but only when the crawl ended
cleanly**: the page was read and simply had no names, or it ran out of our own fetch budget.
If the site *refused* us — robots, a block, an error — the fallback stays shut, and one
refusal shuts it no matter where in the crawl it happened. We don't go looking somewhere
else after being told no.

Search results are judged by **where they live, not what they say** — the client reads only
the address, never the blurb, because a blurb isn't something it can verify. Best is the
company's own site, then LinkedIn, then a curated list of industry sites; anything else is
refused outright and named.

**Anyone found on an industry site is shown but always held**, however confident everything
else looked, with the address quoted in the reason. Those sites can name the right person
and still be years out of date about whether they still hold the role — your call, not the
client's. Only people from the company's own site or LinkedIn come through ready to send.

## People a round declined to send

> "Work the suggestion declines" · "Who is still waiting from the last round?"

A person the round found but would not send — no email, or an email that belongs to
someone else's company — is kept, not lost. They collect in a file on your machine that
survives the session and builds up across rounds. Open the backlog any time, no new round
needed. For each person: **send** once you have supplied what was missing (it goes through
every gate a spreadsheet upload does), **defer** to the next batch, **delete** (a later round
that finds them again will offer them again), or **export** a spreadsheet you fix by hand
and load back in through the normal upload.

## Why are we losing deals?

> "Why are deals being lost?" · "Loss reasons against ICP tier"

Builds a report of closed-lost reasons cross-tabulated with each company's ICP tier and
score — the pattern-finder for things like "we lose Tier A deals on price." Read-only.

## The unattended sweep

Not something you invoke — a scheduled check an **admin** installs on your machine (see
`skills/backend-sweep/SWEEP-CRON-TEMPLATE.md`). Once installed, it watches the backend with
no session open and raises a notification only when something needs a human: a failed run, a
dead credential, an exhausted quota, a stuck lock, a review backlog past its threshold,
live-write permission left switched on with nothing dispatching (the residue of a crash
between arming and disarming), or the n8n execution rate running high enough to blow
through the monthly plan.

Silence means healthy — and a sweep that *runs* but cannot do its job is loud about it (a
banner, a non-zero exit, a "not configured" notice). One silence it cannot break: a schedule
that was never installed, or that has stopped firing, produces nothing at all — which is why
"the sweep never notifies" is the first admin-table row to check. You can preview what the next unattended fire would say with
"run the backend sweep."

---

## Why it keeps asking permission

Everything here runs small local scripts, and Claude asks before running each one — so a
single batch can mean several approvals in a row. Two ways to stop that:

- **Ask your admin to allowlist these commands** (one line in your Claude settings). The
  prompting stops for this plugin and stays on for everything else. Prefer this.
- **Bypass permissions mode.** Also stops it, but for the *whole session* — anything else
  done in that session runs unprompted too.

**Neither one lets anything write to HubSpot on its own.** Writing still needs the switch
your admin sets, a grant you open for a named batch, and an arming window covering only
that send's records. Approving fewer prompts does not widen what can be written; approving
more of them does not protect you from a batch you already said yes to.

## What keeps you safe

- **Nothing writes without a preview.** Uploads, enrichment writes, review decisions,
  control actions — all show you the exact change first. Since 0.41.0 a batch round proceeds
  after stating its price and pausing seven seconds unless you interrupt; your admin can turn
  that off per level (`autonomy.write`, `autonomy.spend_no_write`) so it asks again. Control
  actions always ask.
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
- **A batch that asks less is not a batch that checks less.** Running without per-row
  approval changed who gets asked, not what gets enforced: the non-clobber merge policy,
  the write gates, the per-send armed window and the post-run list of exactly which records
  were written are all unchanged. A held row is held, not dropped — it comes back by name.

## When to call the admin

| Symptom | Why it's the admin |
| --- | --- |
| "Not configured" errors that setup can't resolve | Backend keys/deploys live outside the plugin |
| Provider credits exhausted | Buying credits is a commercial action |
| The unattended sweep never notifies | The schedule is installed on your machine by an admin |
| You want live writes enabled for a batch send | The one-shot armed send only works in a shell where an admin has set the arming switch (`ALLOW_N8N_ARM`) |
| You want something faster than daily and the budget floor refuses it | The refusal names the exact one-time override phrase; raising the plan's execution allowance itself is a commercial decision an admin owns |
| Review approvals refuse with "grant not authorized" | No grant is open for this record — open one yourself, in this conversation; only if `allow_write_grants` itself has never been turned on does this need an admin, once, in `operator.local.json` |
