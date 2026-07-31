# Operator Claude Plugin

A conversational **front end and control panel** for the n8n enrichment backend in this
repository. It lets a non-technical operator load contacts, trigger enrichment, watch runs,
change schedules, and resolve review conflicts — from a chat window, without opening n8n.

> **Status: one lane implemented.** Phase 23 shipped the plugin shell and the
> spreadsheet-to-`hubspot/contact-upload` lane described in this README's setup and usage
> sections below. Remaining lanes (non-tabular ingestion, enrichment, status, control,
> notices, review triage) land across phases 24–30 of milestone v0.6; see
> `.planning/workstreams/plugin-entrypoint/ROADMAP.md`.

---

## This is one client, not the interface

**The backend is the product. This plugin is a suggested default client for it.**

n8n is a standalone system. It is reached over plain HTTP — signed webhooks for the work,
the n8n Public API for control and observability. Nothing about that contract is specific to
Claude, to this plugin, or to a chat interface at all. A Slack bot, an internal web app, a
Retool panel, a CLI, or a scheduled script can drive exactly the same backend, and more than
one can do so at the same time.

This plugin exists because it is the fastest way to give one non-technical operator a usable
surface without building and hosting a web app. Treat it as a reference implementation of the
client contract, not as the only way in. If it is ever the wrong shape — more operators, a
customer-facing surface, a workflow that wants buttons rather than sentences — replace the
client, keep the backend.

**Deliberately thin.** No enrichment logic, no scoring, no dedupe, no normalization lives here.
Those are backend concerns and duplicating any of them would fork the source of truth. This
client's whole job is: turn operator intent into a valid backend request, and turn a backend
response into something a human can act on.

---

## What lives where

| Concern | Owner | Why |
| --- | --- | --- |
| Column mapping, phone/email normalization, verification | n8n (`hubspot/contact-upload`) | Single source of truth; already built and tested |
| Identity resolution, dedupe, create/update routing | n8n | Same |
| Provider waterfall, web research, judge escalation | n8n | Same |
| ICP scoring, non-clobber merge policy, field governance | n8n + `config/*.yaml` | Same |
| Provider + HubSpot credentials | **n8n credential store** | The client never holds them |
| Turning messy input into canonical rows | **This client** | Only for input that is not already tabular |
| Preview, cost estimate, approval, arming | **This client** | The human-judgment surface |
| Status, notices, schedule control, review triage | **This client** | What n8n's own UI would otherwise provide |

---

## The client contract

Any front end — this one or its replacement — talks to the backend through these, and nothing
else:

| Surface | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `hubspot/contact-upload` | POST | header secret | Contact rows, binary CSV body |
| `hubspot/enrichment/event` | POST | header secret | Enrich records that already exist |
| `hubspot/backend-status` | POST | header secret | Health: provider credits, queue counts, credential state |
| `/api/v1/workflows`, `/api/v1/executions` | GET | `X-N8N-API-KEY` | Read workflow and run state |
| `/api/v1/workflows/{id}/activate` \| `/deactivate` | POST | `X-N8N-API-KEY` | Turn a workflow on or off |
| `/api/v1/workflows/{id}` | PUT | `X-N8N-API-KEY` | **Allowlisted mutations only** — write-safety flag overlay, Schedule Trigger cadence |

Two things about that last row. Write-safety gates are compiled into the workflows' Code nodes
at deploy time (`ENABLE_BAKED_FLAGS`), and schedule cadence lives in Schedule Trigger
parameters — so both are workflow writes rather than runtime settings. A client that offers
arming or rescheduling must restrict itself to those fields, show the change before making it,
and read the state back afterwards. A `200` is not proof the flag landed.

Everything else about the backend — editing nodes, credentials, workflow structure, deploying
new versions — is an **admin** task performed from this repository's `scripts/`, not something
a client should reach for.

### Porting to a different front end

To build a replacement client, you need to reimplement exactly this much:

1. **Send** — POST canonical contact rows as CSV bytes; POST enrichment events with an explicit
   `providers` selection (absent or unrecognized means *no providers*, which is the primary
   cost gate — never rely on a default).
2. **Structure** — turn non-tabular input into rows over the canonical contact props
   (`email, firstname, lastname, jobtitle, linkedin_url, phone, company`). Tabular input needs
   no mapping; the backend's `Map Columns` node handles arbitrary headers.
3. **Gate** — never send without explicit human approval, and keep live-write permission
   short-lived rather than persistent.
4. **Read** — poll executions and the status endpoint; translate failures into language the
   operator can act on, and say who can fix what.
5. **Report** — per-record outcomes, not HTTP statuses; be explicit when a run is still in
   flight rather than presenting partial state as final.

Nothing on that list requires Python, Claude, or this repository. This client happens to import
`src/file_loader.py` for CSV/TSV/JSON/XLSX reading — a convenience of living in the same repo,
not part of the contract. Any language's file reader substitutes for it.

---

## Operator model

The intended operator is **non-technical and works in Claude Desktop.** They do not open n8n,
run commands, edit config files, or handle secrets. This shapes the design more than anything
else:

- **No terminal instructions during everyday use, ever.** Loading contacts, previewing, approving,
  and arming all happen by talking to the skill — never by running a script. The one exception is
  the one-time setup below: the operator copies a tracked example file and fills in two values
  obtained from an admin. That is a one-time file edit, not an ongoing terminal workflow, and nothing
  about it repeats once the plugin is configured.
- **No secrets typed into the conversation.** The client holds only the n8n base URL, an n8n API
  key, and the webhook secret — set once in the plugin-local config file (see "One-time setup"),
  never pasted into chat, never echoed back by the skill. Provider and HubSpot credentials stay in
  n8n entirely. The operator sees health — "ZoomInfo access expired, ask an admin" — never values.
- **Errors are translated.** Expired credential, rate limit, exhausted quota, malformed record.
  No status codes, no stack traces, no "check the n8n logs".
- **Partial failure is normal and must read as such.** A dead provider does not present as total
  failure; a run still in flight does not present as finished.

## Safety posture

Inherited from the backend and non-negotiable:

- **Disarmed by default.** Approval at the preview is not permission to send.
- **Live-write permission is conversation-scoped.** It lapses when the session ends and is never
  inherited by a later one. n8n's own baked flag is persistent by nature — the client's
  willingness to use it is not, and both facts appear in status. Conflating them is how a silent
  live send happens.
- **Every mutation: state the consequence, show the change, confirm, then verify by read-back.**
- **Every mutation is reversible in one step,** and the client says how at the moment it applies.
- **Unattended monitoring is read-only.** The sweep that watches for problems burns no provider
  credits, enables no writes, and dispatches nothing.

## Cost posture

Provider credits are real money and the operator cannot see a bill. Every batch is previewed
with an estimated provider-credit and Anthropic-token cost derived from the measured rates in
this repo (`scripts/enrichment_cost_ledger.py`, `docs/`), warns when the estimate exceeds the
credits actually remaining, and shows its chunking plan before sending. Aborting at the preview
costs nothing beyond extraction.

---

## One-time setup

Do this once, before the first upload:

1. In `operator-claude-plugin/config/`, copy `operator.local.example.json` to
   `operator.local.json` (same directory). This filename is deliberately not a dotfile —
   dotfiles are unreadable to this environment's tooling.
2. Fill in its two values, both obtained from your n8n admin:
   - `n8n_url` — the `https://` address of your n8n Cloud instance.
   - `webhook_secret` — sent as the `X-Enrichment-Secret` header on every request; never
     shown back to you by the skill, and never typed into the conversation.
3. Install this plugin's own dependencies once: `pip install -r
   operator-claude-plugin/requirements.txt` (`openpyxl`, `requests`, `PyYAML`). If you're
   running in the same Claude Desktop Code-tab environment this plugin was verified
   against, these already import with no install step.
4. `operator.local.json` is gitignored — it is never committed, and the plugin never
   displays its contents back to you.

Two optional keys, both safe to leave as they ship:

- `hubspot_portal_id` — your HubSpot portal id. Used for one thing only: turning each
  flagged record in the review queue into a clickable HubSpot link. Leave it out and the
  queue shows the raw record id and says the link is missing, rather than guessing a URL.
- `field_policy_path` — `null` uses the repo's own `config/field_policy.yaml`. The review
  queue reads that file to *label* a field as protected before you decide anything about
  it. It is a display lookup: the plugin never refuses a decision on its own, because the
  backend is the one authority on what may be written.

If something is missing or malformed, the skill refuses before making any network call
and says in plain language what to fix — run the skill (or `/operator-claude-plugin:contact-upload`)
and its first message names the exact problem and points back to step 1 above.

## Giving it a file

Two ways to hand the skill a spreadsheet, both confirmed working in this plugin's Code-tab
environment:

- **Attach it** to the conversation, the same way you'd attach any file in chat.
- **`@mention` it** by name using the autocomplete picker, if the file already lives inside
  this repository's workspace.

Either way works — just say you have a contact spreadsheet to load and hand it over by
whichever of the two is convenient. You never need to type a filesystem path by hand.

## What the preview shows, and what approving/arming mean

Before anything is sent, the skill shows you a preview built from the file exactly as you
gave it — the plugin never rewrites your file, it only reads it to describe what n8n's
own mapping will do:

- **Row count** — how many contacts are in the file.
- **Header labels** — each column header next to the canonical field n8n will map it to
  (e.g. `Email Address → email`), and every header n8n's mapping won't recognize, called
  out explicitly as dropped, so nothing silently disappears without you seeing it first.
- **Large batches** (more than about 20 rows) show the first 10 and last 3 rows plus a
  fill-rate percentage per column, instead of the whole table, so the preview stays
  readable at any size.
- **On request only**, the same preview can be published as a standalone Artifact instead
  of a chat table.

**Approving** the preview does not send anything by itself — sending is off by default for
every new conversation. **Declining** ends things right there: nothing is sent, and
nothing beyond reading the file has happened. To actually send, say **"arm the upload"**
after approving; arming lasts for that conversation only, is never written to disk, and
has to be said again in a new conversation.

---

## Beyond spreadsheets: pasted text, JSON, a URL, or screenshots

You don't need a spreadsheet to load contacts. Hand the skill any of these instead, and it reads
them the same conversational way:

- **Pasted text** — an email signature, a typed list of names and companies, an email thread.
- **A JSON blob** — a contact export from some other system, in whatever shape it's in.
- **A public URL** — paste the link and the skill fetches the page itself.
- **Screenshots** — one or more images you've already captured (a scrolled profile page, a
  contact list). Hand over as many as you have; if it's a long scrolled sequence, the skill will
  ask you to submit in a couple of batches rather than one huge one.

A few things are true across all four:

- **A row is never completed by guessing.** If something can't be read clearly, or a field just
  isn't there, it's left blank rather than filled in with a plausible guess.
- **Anything uncertain comes back as one list to confirm**, alongside the preview — not one
  interruption per row. If you approve without addressing something on that list, the field it
  names stays blank; nothing gets filled in behind your back.
- **The plugin does not capture screenshots itself, and it does not log into any site.** You
  hand over images you already have. If you ask it to go grab a screenshot of a page, it will
  tell you plainly that it doesn't do that.
- **Profile data from a site the licensed provider waterfall already covers — LinkedIn, for
  one — still comes from that waterfall on the backend,** never from a picture of the page you
  hand over. A screenshot is not a shortcut around that.

Nothing about the credential boundary above changes for any of this: this plugin still holds no
provider or HubSpot credentials, and this phase adds no key of any kind.

## Asking what the backend is doing

Ask in plain language — "what's the backend doing?", "is anything stuck?", "how many
records are waiting for review?", "has anything run out of credit?" — or invoke
`/operator-claude-plugin:backend-status`. **This surface only reads.** It cannot turn a
workflow on or off, start or cancel a run, or change a record.

The answer comes back as text and covers every workflow the n8n API key can see (there is
no list to maintain — a newly deployed or renamed workflow just appears):

- whether each one is switched on, and whether **live writes to HubSpot** are currently
  armed on it;
- what is running right now, and whether it has been running long enough to look wedged —
  stated with both the run's age and the threshold, because that threshold is a
  convention rather than a measurement;
- when it last ran, and if that run failed, **why**, in one sentence naming who can fix
  it — no status codes, no stack traces;
- how many companies and contacts are queued or waiting on a review decision;
- provider credit balances and credential health.

**`unknown` never means zero.** A count or a balance the backend could not read says so
in that word. A provider we cannot ask about (Apollo's key legitimately refuses balance
reads) shows as unknown, not as healthy and not as an empty balance.

### The dashboard

Text is what you get by default. Ask for **a dashboard** and the same reading is published
as an Artifact — one page with the same workflows, counts and balances, stamped with
**when the data was fetched**, not when the page was drawn. A dashboard left open in a tab
is not a live view; it says what was true at the moment stamped on it. Ask for a refresh
and it republishes to the **same link**, so the link is worth bookmarking — including from
a new conversation, which is the only part of this that needed the plugin to remember
anything.

What it remembers is one identifier and the time it was saved, in
`operator-claude-plugin/state/dashboard_artifact.json` — never committed, and carrying no
URL, no secret and no record. It expires after **30 days** by default; change
`dashboard_artifact_ttl_days` in `config/operator.local.json` to make that longer or
shorter, and set it to `0` to stop the link being reused at all. An expired pointer is
deleted the next time the skill runs, and the next dashboard request mints a fresh link.

## Layout

```text
operator-claude-plugin/
  README.md               # this file
  CHANGELOG.md            # changes to this client only; backend changes live in the root CHANGELOG
  requirements.txt        # this plugin's own dependencies — openpyxl, requests, PyYAML
  .claude-plugin/
    plugin.json           # plugin manifest
  skills/contact-upload/
    SKILL.md               # the conversation contract: state target, resolve file, preview, approve, arm, dispatch
  scripts/
    config_gate.py         # load/validate operator.local.json; refuses before any network call
    tabular.py              # read CSV/XLSX headers+rows verbatim; convert XLSX to CSV bytes for the wire
    preview.py              # adaptive, display-only preview (reads config/column_mapping.yaml as a lookup only)
    dispatch.py             # the one POST to hubspot/contact-upload; armed has no default
  config/
    operator.local.example.json  # tracked template — copy to operator.local.json (gitignored) per setup above
  tests/                   # this plugin's own test suite, run under the repo's .venv
```

Backend code stays where it is — the **repo root's** `n8n/`, `src/`, `config/`, `scripts/`
directories are a different thing from this directory's own `config/` and `scripts/` above, and
this plugin never imports from them.

## Related

- `.planning/workstreams/plugin-entrypoint/` — requirements, roadmap, and state for v0.6
- `../README.md` — the backend: architecture, HubSpot data model, enrichment pipeline
- `../CHANGELOG.md` — backend changes
- `../docs/` — cost ledger, operator runbooks, provider contracts (admin-facing)
