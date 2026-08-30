# Operator walk — one company + one contact, end to end

**Written 2026-08-25.** A single pass through the whole system from Claude Desktop: create
and enrich a company that is not in HubSpot yet, then ingest a contact at that company and
watch it land **associated**. Every step below is something the operator says or reads; no
terminal, no n8n, no HubSpot admin.

Two things this walk exists to prove, both new on 2026-08-25:

1. A contact is never created unassociated — a row whose company cannot be resolved is
   **held**, not landed.
2. A company that already exists is never recreated — the backend resolves by **domain
   first, then exact name** on both lanes.

---

## 0. Prerequisites (admin, once)

The backend is already deployed and bounced (Contact Ingest 29 nodes, Enrichment **123**
nodes as of the 2026-08-30 Phase 61 deploy — was 113 when this walk was written; both
active, **all write flags false and both allowlists empty**). What remains is the client:

```bash
git push origin master
git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master
git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD
```

Then in Claude Desktop: **Update** the plugin to at least the version in
`operator-claude-plugin/.claude-plugin/plugin.json` (**0.14.0** when this walk was written;
**0.33.0** as of 2026-08-30). Settings are safe — since
0.7.0 they live outside the versioned install directory. Confirm by asking the plugin to
initialize; it should report setup complete and change nothing.

## The pair

| | Value |
| --- | --- |
| Company | **Greyhound Racing Victoria** |
| Domain | `grv.org.au` |
| Absent from portal | verified live 2026-08-25 (disarmed probe: `action=write_blocked`, `existingRecord=None`, checked on **both** domain and name) |
| Expected ICP | ANZ governing body that streams its own racing content — Tier A or B, no veto |
| Contact | **Damien Ractliffe, Head of Public Affairs** — his address is published on `https://grv.org.au/about/contact-us/`; **copy it from that page**. A role inbox (`media@grv.org.au`) works too if you prefer not to use a named person. |

Nothing here invents an email address. Paste the published one at step 3.

**Expected spend for the whole walk:** ~2–3 provider credits and one Anthropic research
call (~$0.07–0.20) on the company; the contact ingest lane calls no providers. Roughly
6–10 n8n executions against the 2,500/month plan.

---

## 1. Create and enrich the company

Say:

> `/operator-claude-plugin:enrich-records`
>
> Enrich Greyhound Racing Victoria, domain grv.org.au. It may not be in HubSpot yet.

**What must happen before anything is armed.** The skill states the target endpoint and
that dispatch is disarmed, then shows a four-block preview. The records block must say, in
these words, that the company is matched on its **domain** first, that an existing company
is enriched in place and **never duplicated**, and that one with no match is **created if
creation is armed**. If it does not say that, stop — you are on the old plugin.

**Then send it, as ONE decision.** Arming, sending and disarming are a single action —
`control_actions.execute_action` opens an armed window, runs the dispatch inside it, and
disarms on the way out, whatever happens in between. Do not ask for them separately. Say:

> Send this batch with live writes on, bounded to grv.org.au, and allow it to create the
> company.

The control surface reads the backend's current state and shows you one consequence: live
writes on for this send only, bounded to that one domain (the backend cannot write any
record outside the allowlist), off again the moment the send finishes. Say **yes** to that
exact statement — one yes, one cycle. The arm and the disarm each deactivate and
reactivate the workflow, which is what makes the running instance pick up the change; a
bare write to n8n would not.

The result reports `verified` only after an independent re-read of the backend. If it
comes back **`disarm_failed`**, that is its own state and outranks everything else in the
report: live writes may still be on and an admin must check n8n directly.

**Read the outcome.** The lane reports at chunk granularity. Ask for backend status, or
ask it to check the company, to see the record itself. Expect a new company with
`lv_org_type`, `lv_produces_content`, an ICP score and a tier.

Do not continue the walk until the disarm is confirmed.

## 2. Confirm the company is findable before touching contacts

HubSpot's search index is eventually consistent — a company created seconds ago may not
answer a domain search yet. Ask for the same enrich-records form again, **with providers
set to none, and do not arm anything**:

> Run enrich-records for Greyhound Racing Victoria, grv.org.au, with providers none. Don't
> arm anything — I just want to know whether it resolves now.

Expect the backend to report the record as already existing (its gate says `skip` or
`enrich`, with a record id) rather than proposing to create it. Providers `none` makes
that check structurally free rather than accidentally free — do not run it with the
default full waterfall. **Do not go to step 3 until the company
comes back with a record id.** Skipping this wait is the one way to make a correct walk
look broken: the contact would be held for "no company matched", which is the system
working exactly as designed on a company it cannot yet see.

## 3. Ingest the contact

Put one row in a CSV (a spreadsheet, or paste the details and let the plugin extract
them):

```csv
email,firstname,lastname,company,job title
<the published address>,Damien,Ractliffe,Greyhound Racing Victoria,Head of Public Affairs
```

Say:

> `/operator-claude-plugin:contact-upload`

and attach the file, or `@`-mention it.

**The preview now says something new.** Before any arming, it states that the backend
will not create a contact it cannot associate to a company, how it resolves one (email
domain, then exact company name), and what would happen to this file if the company were
missing. Read that and check it matches what step 2 confirmed.

**Send it, as one decision** — same single arm-send-disarm cycle as step 1, on the other
workflow:

> Send this upload with live writes on, bounded to grv.org.au, and allow it to create the
> contact.

Read the consequence back, say **yes** once, and let the cycle run. Again: a
`disarm_failed` result outranks everything else.

**Read the per-row outcome.** Each row now reports an `association` alongside its write:

| Value | Means |
| --- | --- |
| `associated` | the contact is linked to that company — the walk's pass condition |
| `not_confirmed` | the contact landed, the link did not (gated, or HubSpot refused) |
| `not_attempted` | a company was resolved but no association was requested |
| `none` | no company was resolved for this row |

A row whose action is `review` with a company reason was **held on purpose** — nothing was
written for it. That is not a failure and not something to retry blindly.

**If a row is held**, answer it in one line and re-send:

> `1. company: <the HubSpot company record id>`

The plugin adds a `company_id` column to that row in a **new** dispatch file — never your
original — and the re-send goes through the arming gate again, because a re-send is a
send.

## 4. Verify in HubSpot

Open the company record in HubSpot and check, in this order:

1. **Exactly one** Greyhound Racing Victoria company record exists — not two.
2. The contact appears under its **Contacts** association.
3. The company carries an ICP score and tier, and `lv_anti_icp_flag` is false.

Then ask the plugin for backend status once more and confirm both workflows report **live
writes off**.

---

## What this walk does not cover

- **The enrichment lane never creates a contact at all — it holds one.** The 2026-08-25
  association rule is still implemented in the ingest lane only, and rather than land an
  unassociated contact, Phase 61 (2026-08-30) downgrades an armed `create` on the
  enrichment workflow's contacts branch to `review`, with a reason telling you to route
  that contact through the contact-upload ingest lane instead. So this walk's ingest lane
  remains the only path that creates a contact, and no lane lands one unassociated. (The
  root `CHANGELOG.md` still lists the old "lands unassociated" wording under Known debt —
  that entry is stale.)
- **Freemail contacts.** A contact whose only address is gmail/bigpond/optusnet resolves
  no company from its domain, so it depends on the exact company-name match or on you
  naming the company id. That is deliberate: associating every consumer address to one
  arbitrary company is worse than holding the row.
- **Two companies with the same name** resolve to neither. Ambiguity is held, not guessed.
