# Phase 30: Review-Queue Triage - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 30 closes the loop on records the backend flagged for human judgment. The operator sees each
conflict in plain language, adjudicates it conversationally, and the decision is written back to
HubSpot **stamped as a human decision** — so the audit trail distinguishes a person's call from a
model's.

This is the milestone's **second distinct write path**, separate from dispatch. It reuses Phase
28's confirm-then-verify machinery but has its **own** session-scoped gate.

Not in scope: re-implementing the non-clobber merge policy, changing field-policy ownership
classes, or replacing the HubSpot UI as a record-editing surface.

</domain>

<decisions>
## Implementation Decisions

### Review writeback gate
- **D-01:** Review writeback uses a **session-scoped arm plus an exact-write display per decision**.
  The operator arms review writeback once for the session; every individual decision still shows
  the exact property write before it is applied.
- **D-02:** This gate is **separate from dispatch arming** (REVIEW-03 draws that distinction
  deliberately). Arming dispatch does not arm review writeback, and vice versa.
- **D-03:** Ungated, the plugin **shows exactly what it would write and writes nothing** (REVIEW-03).
- **D-04:** Rationale worth preserving: triaging ten records must not mean ten arming steps.
  Friction here pushes the operator back to the HubSpot UI, which defeats the phase.
  — **Reversibility:** reversible — tightening to per-decision arming is a change at one gate check.

### Non-clobber enforcement
- **D-05:** The **backend enforces** the non-clobber policy. The n8n-side review endpoint applies
  the existing merge and field policy — a `manual_protected` value is never overwritten by a review
  decision, and that rule lives in exactly one place.
- **D-06:** The **client reads `config/field_policy.yaml` display-only**, purely to show the
  operator that a value is protected *before* they attempt a decision on it. This is the same
  read-only-lookup pattern as Phase 23 D-07's mapping preview: read the config to explain, never to
  decide.
- **D-07:** The client does **not** refuse locally. Refusing locally would create a second policy
  authority that can drift from the backend's — the thing this milestone has declined everywhere
  else.

### Audit stamping
- **D-08:** Every decision stamps **human source, timestamp, and the operator's stated reason**
  into the existing audit mechanism (REVIEW-04). No new audit schema is invented.
- **D-08a (CORRECTS D-08's premise — 30-RESEARCH.md, verified against deployed schema and code):**
  The flat `<field>_source` / `<field>_verified_at` / `<field>_verified_by_model` /
  `<field>_validation_status` convention described in the root `CLAUDE.md` **does not exist in this
  repo's deployed schema**. The real mechanism is **one JSON blob per object** —
  `lv_enrichment_provenance` (companies) / `lv_contact_enrichment_provenance` (contacts) — with
  entries shaped `{source, confidence, verified_at, validation_status, value, evidence_url?}` and
  **no `verified_by_model` key at all** (`src/merge_policy.py`, `n8n/code/mergeCompanies.js`).
- **D-08b:** D-08's intent is still satisfiable: a human decision **additively merges an entry**
  into that same blob with `source: "human"`, `validation_status: "human_approved"`, and
  `reason: <operator text>`. Additive merge, never replacement — the prior machine entries stay.
- **D-08c:** The review properties this phase drives **are real, but only under the `lv_` prefix**:
  `lv_enrichment_needs_review`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json`,
  `lv_enrichment_review_approved`, `lv_enrichment_reviewed_by`, `lv_enrichment_reviewed_at`,
  `lv_icp_needs_review` — on both companies and contacts. The generic unprefixed names used in root
  `CLAUDE.md` are wrong for this deployment.

### Enforcement path and endpoint — corrected by research
- **D-08d:** The non-clobber engine D-05 defers to **already exists and is tested**:
  `n8n/code/reviewApply.js`, wired into `wf_scheduled_maintenance_cloud.json`'s 15-minute
  `Review Trigger`. It performs compare-and-set staleness checking and never lets a
  `manual_protected` field reach the queue at all. `tests/n8n/reviewLoop.test.mjs` covers the
  contract. **Reuse it; do not re-implement.**
- **D-08e:** A **new synchronous endpoint and a new baked flag are required.** No existing webhook
  carries a review decision, and the existing apply path is a 15-minute poll — incompatible with
  the confirm-then-verify pattern D-01 imports from Phase 28. The plan adds
  `hubspot/review/decision` plus `ALLOW_HUBSPOT_REVIEW_WRITES` in
  `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC`, mirroring how Phases 25/27 grow
  `hubspot/backend-status`. The existing 15-minute loop **stays as a backstop** rather than being
  retired.
- **D-08f:** **D-11's "which source said what" cannot be fully literal.** By the time a field
  reaches `needs_review` the pipeline has resolved to a single `source_provider` + `reason` string;
  true multi-provider disagreement is computed transiently in `scoreEnrichment.js` (`ranked` /
  `conflicts`) and **never persisted**. The queue renders what is stored, and says plainly that it
  is showing the resolved source rather than the full disagreement. Persisting `conflicts` is a
  cheap fast-follow, recorded as deferred rather than assumed.
- **D-09:** The operator's stated reason is captured as free text and stored. A decision without a
  reason is still a decision, but the reason is what makes the audit trail useful later.

### Rejection
- **D-10:** Rejecting a record **records the reason and leaves it in the queue** (REVIEW-05).
  Review flags are **never silently cleared**, and a record never leaves the queue without a
  recorded decision.

### Queue presentation
- **D-11:** The queue lists each record's conflict in plain language — the competing values, which
  source said what, evidence links, and a link to the HubSpot record — so a non-technical operator
  can actually adjudicate. The enrichment pipeline already stores all of this in the source-metadata
  and `enrichment_last_decision` fields; this phase renders it, it does not recompute it.

### Findings from planning
- **D-12 (a real hole in the non-clobber guarantee — REVIEW-02):** `domain` is a
  `DEFAULT_COMPANY_POLICY` key **whose class is `manual_protected`**. But `reviewApply`'s allowlist
  is `Object.keys(DEFAULT_COMPANY_POLICY)` — **membership in the policy object, not the class
  check**. So a stale or hand-edited candidate JSON naming `domain` would pass the allowlist and be
  written, violating REVIEW-02's "a `manual_protected` value is never overwritten by a review
  decision". Fix: **drop `manual_protected` and `review_required` classes before building the
  patch**, consulting that same policy object — **inside the existing authority, not a second
  one**, so D-05/D-07's single-source rule still holds.
- **D-13 (research Open Q3 deliberately NOT followed):** research suggested growing Phase 27's
  `hubspot/backend-status` with a queue-detail mode. Phase 27 is **unbuilt**, so its response shape
  is undecided — building against it would couple this phase to a contract that does not exist yet.
  The queue read lives in **this phase's own workflow** instead. The divergence is stated in
  30-04's objective rather than left implicit.
  — **Its "Phase 27 is unbuilt" premise expired on 2026-07-31; see D-20 for the two standing grounds
  that replace it. The decision itself is unchanged.**
- **D-14 (the pinned flag assertion is widened deliberately, not incidentally):** `_OVERLAYABLE_FLAGS`
  goes from 4 names to 5 to admit `ALLOW_HUBSPOT_REVIEW_WRITES`. This is the opposite call from
  Phase 23's, which **reused** an existing flag precisely to avoid touching the pinned assertion —
  the difference is that Phase 23 had a suitable existing flag and this phase does not. Editing a
  pinned safety assertion is an explicit, justified task here, never an incidental edit.
- **D-15 (reuse is enforced mechanically):** `reviewApply.js` is imported, never forked — and
  `git diff --stat` on that file is an **acceptance criterion**. The 15-minute backstop loop is
  likewise retained under a `git diff --stat` guard on the maintenance workflow, so "we kept the
  backstop" is verified rather than asserted.

### Corrections folded in after the plan-checker run (2026-07-31) — 4 blockers, 2 concerns

**Why these exist:** `30-05` and `30-06` were written against Phase 23's `dispatch.py` idiom and
never absorbed Phase 28's **D-33** and **D-34**, which were adopted *after* those plans were on
disk. `30-01`, `30-03` and `30-07` passed the checker clean and are not touched by any of this.
**A correction left only in a plan gets re-litigated — that is why they are here.**

- **D-16 (review writeback gets its own plugin-side `ALLOW_*` kill switch — `ALLOW_REVIEW_SUBMIT`):**
  Phase 28 **D-34** made gating uniform: *one `ALLOW_*` variable per dangerous capability, value must
  read exactly `true`, checked before any transport is constructed, refusing in plain language that
  names the variable and says an admin sets it.* `review_decision.py` is a new **mutating** client
  module, and its only gate as originally planned was a `review_armed` boolean handed in from the
  conversation — exactly the asymmetry D-34 abolishes. D-34's third property is the binding one:
  the env gate is *"the gate that still holds when an agent, a test harness, or a scheduled routine
  reaches the module by a path nobody anticipated"*, so the human arming step and the no-default
  confirmation are **not** substitutes for it. Three load-bearing properties, carried over verbatim
  from `ALLOW_N8N_ARM`:
  1. **Semantics identical to `ALLOW_N8N_ARM` / `ALLOW_N8N_PROBE`.** Only the exact string `"true"`
     proceeds; `""`, `"1"`, `"yes"`, `"TRUE"`, `"True"` all refuse. Two gates in one milestone that
     disagree on what counts as "on" is worse than one gate.
  2. **Checked before the transport is constructed**, so an unset variable leaves an empty call log.
  3. **It gates submitting a decision, never any un-doing path** — the same way `ALLOW_N8N_ARM`
     gates arming but never disarming. Nothing that records a reason, re-queues a record, or
     otherwise walks a decision back may be blocked by it.
  **Name collision that must not happen:** `ALLOW_HUBSPOT_REVIEW_WRITES` (D-08e, 30-01) is the
  **backend baked constant** — a literal compiled into the workflow JSON, overlaid at deploy time by
  `_OVERLAY_FLAG_SPEC`, and read by `_writeSafetyAllows()` inside n8n. `ALLOW_REVIEW_SUBMIT` is a
  **plugin-side operator environment variable** read by Python on the operator's machine before a
  request is built. They gate different things at different layers, in different processes, and
  either one alone stops a write; reusing the name would make an operator believe setting one has
  done the work of both. Both must be true for a review decision to reach HubSpot.

- **D-17 (the transport parameter is the bare `requests` module — this is a send-shape guard, not a
  style preference):** `30-05` and `30-06` originally told the executor to mirror `dispatch.py`'s
  POST idiom. Live, `scripts/dispatch.py:26` is `transport=requests.post`, and
  `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` `rglob`s **every** plugin script,
  including ones not yet written, flags any function whose `transport` parameter defaults to
  `requests.post`/`requests.put` (`:129-143`), and allowlists exactly two functions in
  `_EXPECTED_SEND_SHAPED` (`:192-195`) — `backend_status.py::fetch_backend_status` and
  `dispatch.py::dispatch`. Mirroring `dispatch.py` therefore turns `fetch_queue`,
  `preview_decision` and `submit_decision` into unexpected send-shaped functions and the suite goes
  red — **and the nearest fix an executor reaches for is appending to the allowlist, which weakens
  the guard that stands between a client path and `dispatch()`'s no-default `armed` parameter.**
  Binding rule, identical to Phase 28 **D-28/D-33**: the `transport` parameter defaults to the
  **bare `requests` module** and every call goes through `transport.post(...)` /
  `getattr(transport, verb)(...)`. **Appending to `_EXPECTED_SEND_SHAPED` is forbidden**;
  `git diff --stat` on `test_retry_reuses_dispatch.py` must be empty when this phase closes.
  **This is not a dodge of the guard, and the distinction matters if anyone reopens it.** The guard
  exists so that `dispatch()` stays the *only* function reachable with a send-shaped default, because
  `dispatch()` is where the no-default `armed` parameter lives. A mutating module that stays off that
  list does not thereby become ungated — it carries its own gates instead, which for
  `review_decision.py` is D-16's `ALLOW_REVIEW_SUBMIT` plus the no-default session arm. This is the
  identical call Phase 28 **D-28** made for `n8n_arming`, a module that writes an *enabled*
  write-safety literal to a live workflow and is therefore strictly more dangerous than this one.

- **D-18 (`review` is its own `config_gate` capability — the key does not exist today):** live,
  `operator-claude-plugin/scripts/config_gate.py:28` `CAPABILITY_KEYS` is exactly `contact-upload`,
  `status`, `control`, and `missing_keys` raises `ValueError(f"unknown capability: {capability!r}")`
  for anything else. Routing a review refusal through `require_capability(cfg, "review")` as planned
  would crash, and the tempting substitute — reusing `"contact-upload"` — is wrong for the same
  reason **28 D-29** split `control` from `status`: *a config that may read the review queue is not
  thereby one that may upload contacts.* So `30-05` adds
  `"review": ("n8n_url", "webhook_secret")` to `CAPABILITY_KEYS` plus its `_CAPABILITY_DESCRIPTIONS`
  row. Per **28 D-35**, adding a capability row is not a one-file change:
  `operator-claude-plugin/tests/test_status_unknown.py` pins the exact capability set twice
  (`:144-145` and `:153`) and both assertions must be updated in the same plan.

- **D-19 (read-back verification means a refetch, not the write's own echo — this changes 30-02):**
  `30-06`'s `verify_decision(intended, response)` was specified against *"the endpoint's post-write
  record properties"*, invoking Phase 28 **D-14** (*a `200` from the backend is never reported as
  success on its own*). But `30-02` specifies `Respond Review Decision` emitting only `would_write`
  and `outcome`; the only post-write data available on that branch is HubSpot's own PATCH echo —
  **the same response, not an independent re-read**, which is precisely what D-14 says is not
  evidence. Resolution: `30-02` inserts a **post-PATCH refetch node** between the PATCH and the
  response node, and writes down the response contract `30-06` consumes. The refetch is one extra
  HubSpot search per *written* decision only — the dry-run branch never reaches it — which is a
  trivial cost next to a phase whose entire purpose is a verified human decision.
  **Response contract (both branches return the same keys; the client branches on `outcome`):**
  `{outcome, message, would_write, verified_properties, verified}` — `would_write` is the patch the
  backend computed, `verified_properties` is the refetched record's values for exactly the
  `would_write` keys (`null` on the dry-run branch and on any non-writing outcome), and `verified`
  is the backend's own key-by-key comparison. The client re-derives the comparison rather than
  trusting `verified`, and an absent or `null` `verified_properties` on a written decision is
  reported as **failed**, never as success.

- **D-20 (30-04's separate-workflow rationale is restated; the decision itself is unchanged):**
  `30-04` justified its own workflow with *"Phase 27 is not built yet."* Phase 27 is now
  code-complete, so that sentence is false. **The decision survives on two standing grounds** and is
  not reopened: Phase 27's status surface keeps its **count-only** role (its response shape is a
  fixed contract several plans already consume), and **28 D-14** exists so that a responder does not
  sit on a shared branch where it can corrupt another lane's responses — the same reasoning that
  made 25-02 build the status endpoint as its own file. Reword, do not re-architect.

- **D-21 (no `conftest.py` edit is needed — the fixture already exists):** `30-05` claimed the stub
  transport had to be extended because *"today every call returns a fixed accepted-status body."*
  That was already false: `operator-claude-plugin/tests/conftest.py:101` `_as_response` and `:142`
  `stub_post_transport_factory` support scripted payloads, `(status, payload)` pairs and raised
  exceptions. And once D-17 is applied the correct fixture is neither of those — it is
  `conftest.py:238` **`stub_module_transport_factory`** (`_StubModuleTransport`, whose
  `.get`/`.post`/`.put` share one ordered `calls` list and which exposes `verbs` and
  `mutating_calls`), shipped by 28-01 for exactly this transport shape. `conftest.py` therefore
  leaves this phase **unmodified**; a third stub would be redundant. Per **28 D-35**, a refusal
  asserts `transport.mutating_calls == []`, not `len(calls) == 0`.

### Corrections folded in from executing 30-02 (2026-07-31)

**Four facts the plan could not have known until the endpoint existed. All four bind 30-03
and 30-06.**

- **D-22 (a synchronous lane cannot reuse `ENRICH_EXTRACT_SEARCH_ROWS` verbatim):** that
  adapter emits `rows.map(...)`, i.e. **zero items on a zero-hit search**. On the four
  scheduled branches zero rows means "nothing to do" and the branch simply ends. On a
  webhook lane with `responseMode: responseNode` it means nothing ever reaches the
  responder and the caller waits out the ~100s Cloudflare ceiling instead of being told the
  record was not found. `30-02` therefore ships `REVIEW_EXTRACT_RECORD`, the same envelope
  handling plus a `{hs_object_id: null, record_found: false}` marker on zero hits, which
  `buildReviewDecision` turns into `outcome: "refused"`. **Any future synchronous lane
  built on a HubSpot search inherits this requirement.**

- **D-23 (an armed-but-not-allowlisted decision returns NO body — the client must treat
  that as failure):** the write gate is a filter Code node. When it drops the row, nothing
  reaches the PATCH, the verify refetch, `Build Review Response` or the responder, so the
  execution ends without a response. This is fail-closed and correct — no write happened —
  but it is **not** a `{outcome: ...}` payload. `30-06`'s client must treat an empty,
  non-JSON, or timed-out response to a `dry_run: false` decision as **failed**, exactly as
  it treats `verified_properties: null`, and must not distinguish it from a rejected write.
  A structured "gate denied" response is deliberately **not** added: an else-branch out of
  the gate would put a path around the write gate, which is the one property
  `tests/test_write_gate_coverage.py` exists to guarantee.

- **D-24 (this endpoint responds with `firstIncomingItem`, not `allIncomingItems`):** the
  two existing responders (`wf_enrichment_cloud`, `wf_backend_status_cloud`) use
  `allIncomingItems`, which renders as a JSON **array**. Exactly one decision is
  adjudicated per request here, so the review endpoint returns the contract **object**
  itself. `30-06` parses a dict, not `body[0]`. (Worth noting in passing:
  `operator-claude-plugin/scripts/backend_status.py:61` already requires a dict from an
  endpoint that emits an array — an unrelated latent mismatch on the Phase 27 lane, still
  unexercised live, recorded here so it is not rediscovered as a Phase 30 defect.)

- **D-25 ("flagged" ORs both `lv_` review flags plus a held candidate):** the plan's
  `not_flagged` predicate was written as "needs-review flag falsy **and** candidate JSON
  empty". Taken literally, a record flagged solely by `lv_icp_needs_review` — a legitimate
  queue member, since `wf_backend_status_cloud`'s `AWAITING_REVIEW_GROUPS` ORs the two
  flags — would have been refused as not-in-the-queue and the operator could never
  adjudicate it. `buildReviewDecision` therefore treats a row as flagged when
  `lv_enrichment_needs_review` **or** `lv_icp_needs_review` is truthy, **or** a candidate
  JSON other than `""`/`"[]"` is held. HubSpot returns booleancheckbox values as the
  strings `"true"`/`"false"`, so the check normalises rather than testing truthiness —
  `"false"` is a truthy JS string.

### Corrections folded in from executing 30-03 (2026-07-31)

**Five facts the plan could not have known until the approve path existed. All five bind
30-04, 30-06 and 30-07.**

- **D-26 (D-12's fix lands in `reviewDecision.js`, NOT inside `reviewApply.js` — and single
  authority still holds):** `30-02`'s handoff said the `manual_protected` guard "belongs
  inside `reviewApply` so D-05/D-07's single-authority rule holds". `30-03`'s own acceptance
  criterion, and **D-15**, say `git diff --stat n8n/code/reviewApply.js` must be empty.
  These cannot both be satisfied and the guard wins: `reviewApply` is **also** the
  15-minute backstop's engine, so widening it changes that loop's behaviour under the very
  guard that exists to prevent it. Single authority is preserved by construction instead —
  the class check reads `DEFAULT_COMPANY_POLICY`'s own `class` values, the same object
  `mergeCompanies` gates with, so there is still exactly one policy table and no second
  authority to drift. **Do not "fix" this by moving the check into `reviewApply`.**

- **D-27 (a contacts approve must never reach `reviewApply` — it would silently de-queue
  the record):** `reviewApply`'s allowlist is the **company** policy's key set. Handed a
  contact candidate it drops every contact field (`jobtitle`, `phone`, …) as
  un-allowlisted, finds nothing stale, and returns its **clear patch** — blanking the
  review flags and the candidate while writing no value at all. That is precisely the
  silent de-queueing **REVIEW-05** forbids. `buildReviewDecision` therefore returns
  `no_candidate` for a contacts approve **before** any engine call. `DEFAULT_CONTACT_POLICY`
  and `lv_contact_enrichment_provenance` are named in the module header as what a future
  contacts apply engine must use, rather than imported as unreachable ceremony.

- **D-28 (every write lane needs its OWN read-back — three contacts nodes, not two):** the
  plan named two credential-bearing contacts nodes (fetch + PATCH). A contacts
  **rejection** does write, and `Review Verify Fetch` POSTs to the *companies* search URL,
  so it cannot read a contact back. Without `Review Contact Verify Fetch`, a landed
  contacts write reaches the responder with `verified_properties: null` — which **D-19**
  requires the client to report as a FAILURE. A read-back is per lane, not per workflow.

- **D-29 (a contact can only be allowlisted by `TEST_RECORD_IDS`):** `_writeSafetyAllows`
  matches on `hs_object_id` or `domain`, and contacts have no `domain` property. Arming
  with `TEST_RECORD_DOMAINS` alone therefore denies every contact — and per **D-23** that
  denial produces **no response at all**, not a refusal message. Asserted in both
  directions in the endpoint tests and stated in the workflow's sticky note. **30-07's
  runbook must say this**, or the operator reads a silent timeout as a broken endpoint.

- **D-30 (the outcome vocabulary grew to six and `unsupported` is retired):** the endpoint
  now returns `rejected | applied | stale | no_candidate | not_flagged | refused`. Nothing
  returns `unsupported` any more. Two of the new three are outcomes an operator will
  routinely meet — `stale` (the record drifted since the candidate was frozen: nothing
  written, still queued) and `no_candidate` (in the queue but holding nothing to promote,
  which is every contact and every dedupe-flagged row). **30-06 must branch on all six**,
  and an approval's `would_write` is a **multi-key patch** — canonical fields, the clear
  patch, and a `lv_enrichment_provenance` JSON blob that can be kilobytes — not the
  single-key patch a rejection produces.

### Corrections folded in from executing 30-04 (2026-07-31)

**Three facts the plan could not have known until the queue read existed. All three bind
30-05 and 30-06.**

- **D-32 (the queue returns ONE envelope, not one item per record — and this is forced,
  not stylistic):** `30-04`'s plan says `Review Queue Rows` should carry the search
  envelope's total "onto every emitted row". Two committed facts make a per-row emission
  impossible. **D-22**: `rows.map(...)` emits ZERO items on a zero-hit search, and on a
  `responseMode: responseNode` webhook that means nothing reaches the responder and the
  caller waits out the ~100s Cloudflare ceiling — and an *empty queue is this phase's
  normal end state*, so this lane meets that case constantly, not rarely. **D-24**: the
  responder is `firstIncomingItem`, so a per-row emission would return the first record and
  silently drop the rest. The node therefore emits exactly one item,
  `{object_type, search_ok, total, returned, rows}`, always. **30-05 reads `.rows`, and
  `total` vs `returned` is how it tells the operator a page is a page.**

- **D-33 (`search_ok` — an empty queue and a failed search are different answers):** HubSpot
  search nodes run `onError: continueRegularOutput` (a repo-wide convention), so a 401, a
  429 or a malformed body arrives at the adapter as an item with no `results` array.
  Treated as an envelope that renders as *"0 flagged records"* — telling the operator their
  backlog is clear when it was never read. The envelope therefore carries `search_ok`, false
  exactly when the item was not a search result. **30-05/30-06 must report `search_ok:
  false` as a failure, never as an empty queue** — the same rule D-19 sets for a written
  decision arriving with `verified_properties: null`.

- **D-34 (the contacts lane DOES request `lv_enrichment_review_candidate_json`; it is
  simply always empty):** 30-03's handoff said contacts render with "no candidate JSON".
  That is true of the *content*, not the property list: the candidate key belongs to
  `_REVIEW_FAMILY`, the tuple both lanes share so a decision cannot become possible on one
  object type and not the other. The queue's contacts search requests it and HubSpot
  returns `""`. **The client must treat a contact as candidate-less by EMPTINESS, not by
  key absence** — a `"k" in row === false` test would be wrong here, which is the exact
  inverse of the key-presence rule 30-03 established for asserting an absent provenance
  key.

### Corrections folded in from executing 30-05 (2026-07-31)

**Two facts the plan could not have known until the client existed. Both bind 30-06.**

- **D-35 (`fetch_queue` has TWO failure modes, and only one of them raises):** the plan
  says the fetch "returns the parsed rows plus the queue total", which describes only the
  success path. A read that must never render a failure as an empty backlog (D-33) cannot
  raise for every failure either — a traceback teaches the operator less than a reason. The
  shipped contract mirrors `backend_status.fetch_backend_status`'s proven split:
  **`config_gate.require_capability(cfg, "review")` RAISES `ConfigError`** for a
  misconfiguration (that is the operator's own fix, named in plain language, and it happens
  before any transport is constructed), while **every runtime failure degrades to
  `{available: False, reason, rows: [], total: None}`** — `endpoint_unreachable`,
  `http_<code>`, `unparseable_response`, `unrecognized_response_shape`, and
  `hubspot_search_did_not_run` for `search_ok: false`. A caller that only checks
  `rows == []` would read every one of those as "nothing needs review". **30-06 must use the
  same split**, and its own `verified_properties: null` / empty-body cases (D-19, D-23) are
  the same class of finding: a failure wearing an empty result's clothes.

- **D-36 (the protected label is emitted per line AND scoped once per page, and the
  provenance blob is not rendered at all):** two presentation rules that follow from D-31
  and 30-04's handoff #4 rather than from taste, so they are recorded rather than left to
  the next editor. (1) The page-level sentence explaining what PROTECTED *means* is emitted
  **only when a field on that page is actually marked** — an unearned protection sentence on
  every page trains the operator to skip the one that matters — and it names the
  review-decision endpoint explicitly, because the 15-minute backstop does not apply the
  class filter while D-31 is open. (2) `lv_enrichment_provenance` /
  `lv_contact_enrichment_provenance` are fetched but **never rendered**: the blob is
  kilobyte-scale and the held candidate already carries source, confidence, reason and
  evidence URL per field, so rendering it would bury the decision in its own audit trail.
  If a future plan needs provenance in the operator's view, it needs a summariser, not a
  dump.

### Claude's Discretion
- Queue ordering and how many conflicts are shown at once.
- Wording of the conflict presentation and of the exact-write display.
- How the operator's reason is elicited.
- Whether the queue renders in chat or as an Artifact (Phase 23 D-09 permits either).
- Batch resolution of several records sharing one conflict shape.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/28-control-actions/28-CONTEXT.md` — the
  confirm-then-verify machinery this phase reuses. D-13/D-14/D-15 (consequence stated, read-back
  verified, out-of-allowlist refused) apply to review writes too.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md` — the
  queue is surfaced there as a count before it is worked here.
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — D-07's read-only-config-lookup pattern, which D-06 here follows for `field_policy.yaml`.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — REVIEW-01..05. §"Out of Scope"
  forbids replacing the HubSpot UI as a record-editing surface; this phase adjudicates flagged
  conflicts, it is not a general CRM editor.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 30" — goal and five success criteria.

### Backend policy (the single source of truth D-05 defers to)
- `config/field_policy.yaml` — ownership classes including `manual_protected`. Read display-only by
  the client (D-06); enforced by the backend.
- `src/merge_policy.py` — the non-clobber merge engine. **Read to understand, never to re-implement.**
- `CLAUDE.md` §6 (source-of-enrichment tracking), §9 (field governance), §22 (human review
  workflow), §23 (audit strategy) — these define the source-metadata fields D-08 stamps into, the
  `human` source and `human_approved` validation status, and the existing review-flow properties
  (`enrichment_review_approved`, `enrichment_reviewed_by`, `enrichment_reviewed_at`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The source-metadata field convention already supports a human decision: `human` is a registered
  source with `trust_rank: 100` and `can_promote_directly: true`, and `human_approved` is an
  existing validation status. D-08 stamps into fields that already exist.
- The existing review-flow properties (`enrichment_needs_review`, `enrichment_review_reason`,
  `enrichment_review_approved`, `enrichment_reviewed_by`, `enrichment_reviewed_at`,
  `lv_icp_needs_review`) — this phase drives them conversationally instead of through a HubSpot view.
- `enrichment_last_decision` and `lv_icp_score_breakdown` already carry the competing values and
  reasoning D-11 renders.
- Phase 28's confirm-then-verify gate machinery.

### Established Patterns
- **The backend owns policy.** D-05/D-07 — the client explains, the backend decides.
- **Nothing leaves a queue silently.** D-10 mirrors the repo's existing refusal to clear review
  flags without a recorded decision.
- **Audit distinguishes who decided.** The whole source-registry design exists so a human decision
  is traceable as such.

### Integration Points
- Reads: Phase 27's review-backlog surface, plus per-record conflict detail through an n8n endpoint
  (the client holds no HubSpot credential).
- Writes: review decisions through an n8n-side review endpoint that applies the existing merge and
  field policy.
- No direct HubSpot access from the client, in either direction.

</code_context>

<specifics>
## Specific Ideas

- The phase succeeds only if a non-technical operator can actually adjudicate. That makes the
  plain-language conflict rendering (D-11) the load-bearing part, not the writeback plumbing.
- Showing that a field is `manual_protected` *before* the operator decides (D-06) is the difference
  between a considered decision and a silently discarded one.

</specifics>

<deferred>
## Deferred Ideas

- **General CRM editing from the plugin** — explicit exclusion, not deferred.
- **Write-back of corrections beyond review decisions** — REQUIREMENTS.md §"Future Requirements".
- **Automated resolution of conflicts** — out of scope by definition; the queue exists because a
  human is required.
- **Rubric revision from accumulated review decisions** — a future analysis task, not this phase.

</deferred>

---

*Phase: 30-review-queue-triage*
*Context gathered: 2026-07-30*
*Corrections D-16…D-21 folded in 2026-07-31 from a `gsd-plan-checker` run (4 blockers, 2 concerns),
after Phase 28's D-33/D-34 landed. Repair edited `30-02`, `30-04`, `30-05`, `30-06` only —
`30-01` was executing concurrently and `30-01`/`30-03`/`30-07` passed clean.*
*D-22…D-25 folded in from executing `30-02`; D-26…D-30 from executing `30-03`;
D-32…D-34 from executing `30-04`; D-35…D-36 from executing `30-05` (all 2026-07-31).*

---

### D-31 — D-12's `manual_protected` hole is closed on ONE path, not two. **OPEN.**

**Found by independent verification of 30-03's completion claim, 2026-07-31.** 30-03 reports the
hole "closed"; that is true of the new endpoint and **not** of the pre-existing backstop. Both
paths were read directly:

| Path | Filter | `domain` (`manual_protected`) | `annualrevenue` (`review_required`) |
|---|---|---|---|
| Review-decision endpoint — `reviewDecision.js:76` `PROTECTED_CLASSES` | by **class** | dropped | dropped |
| 15-minute backstop — `reviewApply.js:41` `allowedFields = Object.keys(DEFAULT_COMPANY_POLICY)` | by **key presence only** | **writable** | **writable** |

`DEFAULT_COMPANY_POLICY` genuinely contains both (`mergeCompanies.js`: `domain →
class: "manual_protected"`, `annualrevenue → class: "review_required"`), so allowlisting by key
admits exactly the two fields the class filter exists to refuse.

**Why this matters more than a cosmetic inconsistency:** the backstop is the path the *documented*
review flow uses. Root `CLAUDE.md` §22.2 step 5 has RevOps approve by setting
`lv_enrichment_review_approved = true` in HubSpot, which the scheduled `Review Trigger (15 min)` →
`Review Search (approved=true)` → `Apply Review` chain then picks up. An operator following the
documented process therefore takes the **unprotected** route, and the protection 30-03 added is
bypassed without anyone doing anything unusual.

**This is pre-existing, not a 30-03 regression.** `reviewApply` has always allowlisted by key.
30-03 made the endpoint strictly safer and correctly refused to widen `reviewApply`, because that
file is the backstop's engine and is pinned byte-identical by a deliberate guard — 30-02 had said
the fix "belongs inside `reviewApply`", and the guard overrode it. **That was the right call under
the constraints; it simply does not finish the job.**

**Not resolvable inside Phase 30's current plan set** — it needs either a change to a guarded file
that alters the 15-minute backstop's behaviour, or an accepted decision that the two paths enforce
different policies. Both are operator decisions, not planner decisions. **Do not let a later plan
quietly close this by editing `reviewApply.js`** — the guard is there so that change is deliberate
and reviewed, and the empty-`git diff --stat` criteria in `30-03` must stay.

**Until it is resolved, `30-07`'s canary must not be read as proving protected-field enforcement**
— it exercises the endpoint path only.
