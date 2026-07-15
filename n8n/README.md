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

---

# Enrichment workflow (quality-scored waterfall)

The second pipeline (`ENRICHMENT-WORKFLOW-PLAN.md`). It checks HubSpot first,
decides **create / enrich / skip**, then — instead of FIFO stop-on-first-match —
**scores every source per field**, cross-checks, and pushes the best value per
field into the same non-clobber merge. Same two-artifact pattern, same inliner
(`scripts/build_cloud_workflows.py`), same no-`require` constraint.

| File | Purpose |
| ---- | ------- |
| `wf_enrichment_cloud.json` | Production-shaped template. Webhook + real HubSpot + 3 provider HTTP nodes + Switch/IF routing. Add credentials on import. |
| `wf_enrichment_local.json` | Headless-executable. Trigger emits 3 sample identities; HubSpot search + provider waterfall + writes are Code mocks; the scoring/gate/merge logic is real. |

## Pipeline

```
Trigger → Code:buildIdentity → HubSpot:search
  → Code:enrichmentGate (decideAction → create | enrich | skip)
  → Switch(action):
       create+enrich → HTTP:Lusha → HTTP:Apollo → Code:ZoomInfo (cached-token enrich)
                     → Code:normalize+score (best-per-field, provenance)
                     → Code:mergeContacts (non-clobber)
                     → IF create → HubSpot:Create ; IF enrich → HubSpot:Update
       skip          → Set (NoOp)
  → Set: data-quality label + gap-flag (all sources empty → flag manual)
```

Gate branches (`ENRICHMENT-WORKFLOW-PLAN.md §3`):

| Action | When | Write |
| ------ | ---- | ----- |
| `create` | identity not in HubSpot | `POST` contact (gated) |
| `enrich` | found but a required field is missing / stale (`> stale_after_days`) / invalid | `PATCH` contact (gated) |
| `skip` | all required fields present, fresh, valid | none, no credits spent |

## Scoring model (best-of-breed, not FIFO)

Each **candidate value** (a field from a source) scores
`value_score = wA·A + wR·R + wG·G + wT·T`, and the pipeline picks `argmax`
**per field** — best email from one source, best phone from another.

| Term | Meaning | Source |
| ---- | ------- | ------ |
| `A` accuracy | provider's per-field quality signal | Apollo `email_status`, Lusha `A+/A`, ZoomInfo `contactAccuracyScore`, phone `valid_number`/type |
| `R` recency | `1 − min(age/stale_ceiling, 1)` | ZoomInfo `validDate`, Lusha `updateDate`, Apollo `updated_at` (no date → neutral 0.5) |
| `G` agreement | fraction of *other* sources whose **normalized** value matches (cross-check) | E.164 phone, lowercased email, revenue band, NAICS |
| `T` trust | source base rank (tiebreaker) | zoominfo .85, lusha .80, apollo .75 |

Default weights `wA=0.45, wR=0.20, wG=0.25, wT=0.10` (tunable). Default mode
`scored_all` calls every source for full cross-check; `scored_cost_aware` (in
`scoreEnrichment.js`) can early-exit once required fields clear a quality bar.
Each winner carries provenance `{value, source, score, components, agreedBy[]}`.

## Import to n8n Cloud

1. **Workflows → Import from File** → `wf_enrichment_cloud.json`.
2. Add credentials: **HubSpot** on Search/Create/Update, and **provider API
   keys** on the Lusha / Apollo HTTP nodes (generic Header Auth, single static
   key). **ZoomInfo is autonomous** — instead of a static key set
   `ZOOMINFO_CLIENT_ID` / `ZOOMINFO_CLIENT_SECRET` in **n8n Variables**
   (`$vars`). The **ZoomInfo Enrich** Code node mints its own short-lived bearer,
   caches it in workflow **static data** across runs, re-mints only when the
   token is missing or near-expiry, and on a **401** clears the cache, re-mints
   once, and retries — so a stored/static token is never needed. Rotate the
   client secret ~quarterly (ZoomInfo Admin Portal → Integrations → API &
   Webhooks); everything else is unattended.
3. Trigger is a **Webhook** (`POST /webhook/hubspot/enrichment/event`) — point
   your HubSpot private-app webhook subscription at it.
4. Writes are **GATED** — review the dry-run behaviour before enabling.

**`lv_*` property dependency (awaited):** the merge writes company/contact
`lv_*` properties (org type, revenue band, source/evidence metadata) **by name**.
Create them in the HubSpot portal first (see `CLAUDE.md §4–8`); until then the
Cloud writes target properties that don't exist. The local replica mocks the
write, so it needs none.

**Apollo phone is async:** Apollo returns phone numbers via a **webhook
callback**, not inline. Production needs a second Webhook node + a Merge to join
the phone payload back. The template does the inline person/org match only.

## Run the local replica

```bash
bash scripts/n8n_enrichment_replica.sh
```

Imports `wf_enrichment_local.json` into the running `n8n` container, executes it
headless, and asserts all three gate branches fired, the scored waterfall
produced best-per-field winners **with provenance**, and **no** HubSpot write
occurred. Actual output:

```
  jamie.rivera@exampleracing.example       action=create   gap_flag=False
      email          -> apollo    score 0.84  agreedBy[lusha]
      mobilephone    -> apollo    score 0.96  agreedBy[lusha,zoominfo]
      jobtitle       -> zoominfo  score 0.7   agreedBy[-]
  alex.taylor@exampleco.example            action=enrich   gap_flag=False
      email          -> apollo    score 0.84  agreedBy[lusha]
      mobilephone    -> apollo    score 0.96  agreedBy[lusha,zoominfo]
      jobtitle       -> zoominfo  score 0.7   agreedBy[-]
  sam.fresh@examplemedia.example           action=skip     gap_flag=False
```

`email → apollo 0.84` beats Lusha's equally-accurate A+ address on **recency**
(Apollo's `updated_at` is newer), and both agree (`agreedBy[lusha]`) so ZoomInfo's
lone `j.rivera` variant loses. The `skip` identity spends no provider calls.

## Cloud vs local differences

Only the edges differ; the inlined Gate / Normalize+Score / Merge Code nodes are
identical.

| Concern | Cloud template | Local replica |
| ------- | -------------- | ------------- |
| Trigger | **Webhook** (event payload) | **Emit Sample Identities** Code node (3 identities) |
| HubSpot search | real **HubSpot** node → **Adapt Search** | **HubSpot Search (MOCK)** Code node (canned create/enrich/skip records) |
| Providers | 3 real **HTTP** nodes (Lusha/Apollo/ZoomInfo) | **Provider Waterfall (MOCK)** Code node (fixture shapes) |
| Routing | **Switch** + **IF** nodes | per-item `action` field; `Decide Action` echoes the dry-run payload |
| Writes | HubSpot **Create/Update** (gated) | **Decide Action** ECHOES PATCH/POST; no write |
