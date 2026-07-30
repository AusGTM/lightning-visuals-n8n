# Operator Claude Plugin

A conversational **front end and control panel** for the n8n enrichment backend in this
repository. It lets a non-technical operator load contacts, trigger enrichment, watch runs,
change schedules, and resolve review conflicts — from a chat window, without opening n8n.

> **Status: planned, not yet implemented.** This directory currently holds only its README and
> CHANGELOG. Implementation lands across phases 23–30 of milestone v0.6; see
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

- **No terminal instructions, ever.** If the client cannot do something itself, it says so in
  plain language and names the person who can. "Run this script" is a bug, not a fallback.
- **No secrets in the conversation.** Configuration is admin-provisioned. The client holds only
  the n8n base URL, an n8n API key, and the webhook secret. Provider and HubSpot credentials
  stay in n8n. The operator sees health — "ZoomInfo access expired, ask an admin" — never values.
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

## Layout

```text
operator-claude-plugin/
  README.md      # this file
  CHANGELOG.md   # changes to this client only; backend changes live in the root CHANGELOG
```

Implementation files arrive with phase 23. Backend code stays where it is — `n8n/`, `src/`,
`config/`, `scripts/` are not this directory's concern.

## Related

- `.planning/workstreams/plugin-entrypoint/` — requirements, roadmap, and state for v0.6
- `../README.md` — the backend: architecture, HubSpot data model, enrichment pipeline
- `../CHANGELOG.md` — backend changes
- `../docs/` — cost ledger, operator runbooks, provider contracts (admin-facing)
