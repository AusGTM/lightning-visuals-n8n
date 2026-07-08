# n8n Contact Ingest — Cloud template + local replica

Milestone 3 Wave B. A HubSpot contact-ingestion pipeline expressed as an n8n
workflow whose business logic is the Wave-A JS (`n8n/code/*.js`) **inlined into
Code nodes** — because n8n **Cloud Code nodes cannot `require()` sibling files
or npm**. Two artifacts, one source of truth:

| File | Purpose |
| ---- | ------- |
| `wf_contact_ingest_cloud.json` | Production-shaped template you import to n8n **Cloud**. Real HubSpot + HTTP nodes; you add credentials there. |
| `wf_contact_ingest_local.json` | Headless-executable variant. Same inlined JS; file input + HubSpot calls are mocked so it runs on the local container with **no** HubSpot creds. |

Both are generated from the Wave-A modules by `scripts/build_cloud_workflows.py`
(re-run it after editing any `n8n/code/*.js`). The inliner strips each module's
`require(...)` / `module.exports` lines and pastes the needed functions into each
Code-node body, then wraps them with the n8n Code I/O contract
(`$input.all()` → `return [{json:...}]`).

## Pipeline

```
Trigger → (file → rows) → Code:mapColumns → Code:normalizePhone
  → HTTP:verifyEmail(batch) → Code:applyEmail
  → HubSpot:searchByEmail → Code:resolveIdentity → Code:mergeContacts
  → IF(action) → HubSpot:update / HubSpot:create(gated) / Set:review
```

Per-row outcome → action:

| Outcome | When | Action |
| ------- | ---- | ------ |
| `match` | strong-key (email/LinkedIn) single hit | `update` |
| `net_new` | valid email, 0 hits | `create` **if `allow_create`**, else `review` |
| `ambiguous` | weak-key hit, multiple hits, or no-email/insufficient identity | `review` |
| `rejected` | fails required-identity gate (no email AND no firstname+lastname+company) | `skip` |

## Import to n8n Cloud

1. n8n Cloud → **Workflows → Import from File** → select
   `wf_contact_ingest_cloud.json`.
2. Add **HubSpot credentials** (a HubSpot private-app token) on the three
   HubSpot nodes: **HubSpot Search by Email**, **HubSpot Update**,
   **HubSpot Create**. The scopes are the CLAUDE.md minimum
   (`crm.objects.contacts.read` / `.write`).
3. The trigger is a **Webhook** (`POST /webhook/hubspot/contact-upload`) whose
   body carries the uploaded file; **Extract From File** parses CSV → rows.
   Point your upload form / HubSpot-side trigger at that webhook URL.
4. **`create` is gated OFF by default** (`Set Config → allow_create=false`).
   Flip it to `true` only after you've reviewed the dry-run behaviour.

No credentials are needed to *import* — import is the v2.4.4 validity gate and
succeeds without them; they're only needed when the HubSpot nodes execute.

## Run the local replica

```bash
bash scripts/n8n_contact_replica.sh
```

Imports `wf_contact_ingest_local.json` into the running `n8n` container
(v2.4.4), executes it headless, and asserts all four ingestion paths fired, the
**real** email verifier returned a status, and **no** HubSpot write occurred.
Actual output:

```
  Bob Smith        outcome=match      action=update   email_status=NO_MX_RECORDS
  Alice Anderson   outcome=net_new    action=review   email_status=NO_MX_RECORDS
  Carol Jones      outcome=ambiguous  action=review   email_status=NO_EMAIL
  Dave Nguyen      outcome=ambiguous  action=review   email_status=NO_EMAIL
  (no id)          outcome=rejected   action=skip     email_status=NO_EMAIL
```

(`NO_MX_RECORDS` is the live verifier's real status for the `example.com`
fixture addresses — no MX records — so the emails route to review while identity
still matches syntactically. See the email note below.)

## Cloud vs local differences

Only the edges differ; the inlined JS Code nodes are identical.

| Concern | Cloud template | Local replica |
| ------- | -------------- | ------------- |
| File input | Webhook upload → **Extract From File** | **Emit Fixture Rows** Code node (the 5-path fixture inline) |
| HubSpot search | real **HubSpot** node → **Adapt Search Results** Code node | **HubSpot Search (MOCK)** Code node (canned: bob→`200`, Carol→weak `300`, else 0) |
| HubSpot write | **IF(action)** → HubSpot **Update** / **Create** (gated) / **Set** review | **Decide Action** Code node ECHOES the dry-run PATCH/POST payload; no write |
| Email verify | **real** HTTP batch node | **real** HTTP batch node (unchanged) |

## Email verifier (real HTTP node)

Both workflows call the free
[`rapid-email-verifier`](https://rapid-email-verifier.fly.dev) batch endpoint
(`POST /api/validate/batch`, up to 100 emails/call). The node is **non-gating**:
if the verifier is unreachable, `onError: continueRegularOutput` lets the run
proceed and **Apply Email** falls back to `PROBABLY_VALID` (surfaced as
`email_verify_fallback: true`) so identity/merge still run.

Identity resolution uses the *syntactic* email check (`normalizeEmailBasic`),
**not** the verifier verdict — so a syntactically-valid-but-unverified address
(e.g. `NO_MX_RECORDS`) still matches/creates while carrying a review flag. To
hard-gate on deliverability, branch on `email_valid` before the HubSpot write.

## AU-phone disclaimer

`normalizePhone.js` is an **AU-only heuristic**, not `libphonenumber` — Code
nodes can't import npm. It recognises `0XXXXXXXXX` (10-digit national) and
`61XXXXXXXXX`, trusts a leading `+` as already-E.164, and returns **`null` for
anything non-AU or ambiguous**. Callers route `null` to review — never guess,
never silently drop. For global coverage, swap the phone node for a
phone-validation API.
