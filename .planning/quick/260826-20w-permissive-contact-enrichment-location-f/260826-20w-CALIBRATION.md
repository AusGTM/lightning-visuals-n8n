# 260826-20w Task 1 — Evidence: withholding inventory + empirical threshold walk

Read-only reconnaissance. No source file changed by this task.

## (a)/(b) Live executions 11932-11956, workflow 950HPb7a1GgSAIyZ

Fetched full `includeData=true` payloads for executions 11932-11956 via plain `urllib`
(the operator's `X-N8N-API-KEY` header, base `https://alexherman.app.n8n.cloud`) — the
throwaway fetch/analysis scripts live in the session scratchpad, not the repo. Of the 25
ids, 8 belong to the enrichment workflow `950HPb7a1GgSAIyZ` and exercised the contacts
branch (`Merge Winners` + `Decide Action` present): **11934, 11935, 11937, 11948, 11949,
11950, 11956**. The rest (`Cj83mOgrIm59oxcX` = backend-status, `1fXPuIabz3RsAHgn` =
review-decision) carry no contact merge decisions.

**Distinct confidence values observed across every contact merge decision in these 8
executions: `{85}`.** Distinct `source_provider`: `{"waterfall"}`. **The flat-confidence
finding in the plan's `<context>` is CONFIRMED, not merely assumed** — every decision on
every field, across every sampled execution, carries exactly `confidence: 85,
source_provider: "waterfall"`. This IS a cliff, not a distribution — there is no live
CSV-lane (`confidence: 80`) traffic in this sample window; that constant is confirmed by
static read of `scripts/build_cloud_workflows.py:293` (`row_to_provider_result` /
`ENRICH_MERGE`'s CSV wrapper) rather than live execution, because no ingest-lane
(`wf_contact_ingest_cloud`, id `Cj83mOgrIm59oxcX`) execution in this window is a real CSV
upload run — the two `Cj83mOgrIm59oxcX` executions in range (11933, 11936... actually all
of `Cj83mOgrIm59oxcX` in this window) are the `backend-status` webhook, a different
workflow that happens to share an id prefix visually but is a distinct `workflowId`.

The real observed candidate, every time: **John Tsatsimas, Football NSW, email
`johnt@footballnsw.com.au`**, HubSpot contact id **`347569451461`**. Its `existingRecord`
carries a **blank email** in every one of these 8 executions (`existing_email: None`) —
this record has never had an email written to it by this pipeline, which is exactly the
withholding the plan exists to fix. `347569451461` is simultaneously the plan's named
"known test record" AND the Football NSW blank-email contact the plan expected to have
to search for separately — Task 3 can target one record for both proofs.

Per-execution email decision (identical shape every time except id/timestamp):

```json
{
  "field": "email", "current_value": null, "chosen_value": "johnt@footballnsw.com.au",
  "source_provider": "waterfall", "decision": "needs_review",
  "confidence": 85, "reason": "Best confidence 85 below threshold 95.",
  "validation_status": "human_review_required", "evidence_url": null
}
```

`Decide Action`'s built `properties` patch in every execution that reaches it (11935,
11937, 11948, 11956) **never contains `email`** — the withholding is end-to-end confirmed
live, not just in the merge decision.

## (c) Threshold walk table

Real observed candidates in this window: only ONE — Football NSW / John Tsatsimas /
`johnt@footballnsw.com.au` at confidence 85 (waterfall lane). The CSV lane's 80 and the
`hubspot_native` lane's 85 are cited from static code
(`scripts/build_cloud_workflows.py:293,2868,2888`), not live traffic, and included because
the table's job is to show which LANES a level admits, not to synthesize a spread that
does not exist.

| Threshold | Football NSW email (85, waterfall) | csv lane (80) admitted? | hubspot_native lane (85) admitted? | waterfall lane (85) admitted? |
|---|---|---|---|---|
| 95 | withheld (needs_review, current behavior) | no | no | no |
| 90 | withheld (needs_review) | no | no | no |
| **85** | **promote** | no | yes | yes |
| **80** | **promote** | **yes** | yes | yes |
| 75 | promote | yes | yes | yes |
| 70 | promote | yes | yes | yes |

**Chosen threshold: 80.** Reasoning: every level from 85 down promotes the one real
candidate this window observed, so the Football NSW proof does not distinguish 85 from
80. The lane-admission column does: 85 silently excludes the CSV upload lane's
emails from ever promoting into a blank field, while 80 is the highest bar that still
admits every one of the three real contact-enrichment ingest lanes this repo has. There
is no evidence any real candidate ever arrives below 80 — the merge boundary discards
per-provider accuracy and always passes one of exactly three flat constants (85/85/80),
so there is no continuum to tune against, only a three-point set, and 80 is its minimum.
Choosing 80 over 85 costs nothing extra in junk-admission risk (no real value below 85
exists in the wild to admit) and buys the CSV lane the same permissive treatment as the
other two, which the review flag then covers uniformly. **What junk this admits:** none
observed — the only value on record below 95 is the CSV lane's fixed 80, itself a static
per-row multiplier for uploaded spreadsheet rows the operator already vetted at upload
time (Section 6.1, `src/ingest.py`), not a provider-accuracy signal that could be
independently low-quality. The review flag (T-20w-01) is what actually bounds the risk
of any single promoted email being wrong, regardless of which of the three lanes supplied
it.

## (d) Withholding inventory — every rule in the contact merge path

| File:line | Rule | Disposition | Reason |
|---|---|---|---|
| `n8n/code/mergeContacts.js:25` `DEFAULT_CONTACT_POLICY.email` | `class: manual_protected, min_confidence: 95` | **RELAX** | The rule this plan exists to change — no real candidate ever clears 95; HubSpot's own dedupe/merge handles identity collisions on write, the client does not need to rebuild that logic client-side (operator ruling, plan objective). |
| `n8n/code/mergeContacts.js:172-173` (pre-change) `if (field === "email" && decision === "promote") decision = "stage_only"` | Hard override: even if the gate said promote, email demotes to stage_only. | **RELAX** | Belt-and-braces for the old policy; with `email` now `fill_blank_only`, keep the promotion and instead redirect the field's `validation_status` to the human-review literal so the decide node can flag it — do not demote the decision itself. |
| `n8n/code/mergeContacts.js:109-114` `fieldClass === "fill_blank_only"` existing-value branch | A non-blank current value always routes to `stage_only`, regardless of confidence. | **KEEP** | This is the non-clobber guarantee itself — the plan's scope is explicitly "promotion into a BLANK field only." |
| `n8n/code/mergeContacts.js:115-120` `fieldClass === "stale_refreshable"` existing-value branch | A non-blank current value with a fresh/refresh candidate routes to `needs_review`, never silently overwritten. | **KEEP** | Same non-clobber boundary; jobtitle's refresh path is untouched by this plan. |
| `n8n/code/mergeContacts.js:227-266` `foldContactResearch` overlap precedence | A research-sourced candidate for a field the provider merge already decided wins ONLY if judge-promoted or a genuine gap; otherwise withheld and rewritten `stage_only`/`withheld_by_overlap_precedence`. | **KEEP** | This is a write-safety gate over an already-adjudicated conflict, not a blank-field withholding rule — out of this plan's scope (research candidates are jobtitle/seniority only, never location or email). |
| `n8n/code/mergeContacts.js` (CONTACT_CACHE_KEY_FIELDS / stale-timestamp fix) | Cache-key datetime stamped only on actual promotion. | **KEEP** | Correctness fix from Phase 16.2, orthogonal to this plan. |
| `config/field_policy.yaml:112-116` contacts `email` block | Mirrors the JS policy — `manual_protected`, `promote_to_canonical: false`, `stage_only: true`, `min_confidence: 95`. | **RELAX** | Must mirror the JS change exactly (both engines, one class/threshold source of truth) — `src/merge_policy.py`'s shared `deterministic_gate` needs no code change since it reads this YAML at runtime. |
| `config/field_policy.yaml` `protect_if_current_present` on phone/mobilephone/linkedin | Existing-value protection flag on the three already-permissive fields. | **KEEP** | Unaffected — this plan only adds new `fill_blank_only` entries (location) and reclassifies email; it does not touch the semantics of `protect_if_current_present` on fields that already have it. |
| `n8n/code/contactJudge.js:139-146` allowlist (`chosen_field` must be `jobtitle` or `seniority`) | The Claude web-research judge may adjudicate exactly two fields; a verdict naming `email` (or any other field) is never treated as a promotion signal. | **KEEP** | Scope guard for a DIFFERENT concern (which fields the research/judge chain may touch) — not a withholding rule over waterfall-provider candidates, and this plan does not add email or location to the research chain (`test_contact_research_never_names_pii_fields` in `tests/test_cloud_contacts_branch.py` already pins email out of the research prompt; unaffected). |
| `n8n/code/enrichmentGate.js` identity gate | Gates whether the waterfall runs AT ALL for a given identity (cost control). | **KEEP** (confirmed, per plan's expected-KEEP list) | A cost control on whether to call providers, not a withholding rule on what a called provider's candidate may do once returned. |
| `scripts/build_cloud_workflows.py:1531` `ENRICH_DECIDE_CLOUD` (contacts) — no review-flag write at all | The companies decide node (`ENRICH_DECIDE_CO_CLOUD`, `:3172-3183`) writes `lv_enrichment_needs_review`/`lv_enrichment_status`/`lv_enrichment_review_reason`/`lv_enrichment_review_candidate_json` from its `needsReview` array; the contacts node has no equivalent block. | **RELAX (add)** | This is the gap T-20w-01's mitigation depends on — without it, a permissively-promoted email is invisible to the triage queue. New predicate is narrow: promote AND human-review validation_status, not "any needs_review" (that would also catch jobtitle's routine stale-refresh reviews and flood the queue — explicitly out of scope, see plan). |
| `src/merge_policy.py:141-147` `deterministic_gate` `manual_protected` branch | Same code as the JS gate's manual_protected branch. | **KEEP (code) / inert (behavior)** | Per plan: no Python code change. Once `config/field_policy.yaml` reclassifies contacts `email` to `fill_blank_only`, this branch is simply never reached for that field again — companies' `domain` still uses it. |

No other withholding rule exists in the five files read in full
(`mergeContacts.js`, `contactJudge.js`, `enrichmentGate.js`, `src/merge_policy.py`,
`config/field_policy.yaml` contacts block, plus the `ENRICH_MERGE`/`ENRICH_DECIDE_CLOUD`
wrapper blocks in `scripts/build_cloud_workflows.py`).

## (e) Pin inventory — every assertion/prose statement pinning the email hard-stop

| File:line | What it pins | Rewrite plan |
|---|---|---|
| `n8n/code/mergeContacts.js:10-12` (module header) | "Email can NEVER land in canonicalPatch on this enrich path (belt-and-braces...)" | Rewrite in place: state the new rule (promote into blank + human-review flag) and the reason (HubSpot's own dedupe/merge owns identity collisions). |
| `n8n/code/mergeContacts.js:25` `DEFAULT_CONTACT_POLICY.email` | `class: "manual_protected", min_confidence: 95` | Change to `class: "fill_blank_only", min_confidence: 80`, comment records the calibration reasoning above. |
| `n8n/code/mergeContacts.js:172-173` | The hard override line itself | Replace with a `validation_status` override on promote (see disposition table above). |
| `tests/n8n/mergeContacts.test.mjs:110-118` (`"mergeContacts: email hard guard still forces stage_only..."`) | Asserts an override-policy promote is force-demoted to `stage_only` | Rewrite: assert email now PROMOTES into a blank field and carries the human-review `validation_status`; add a second case proving an EXISTING non-blank email is still `stage_only` (non-clobber unchanged). |
| `config/field_policy.yaml:112-116` | contacts `email` block | Mirror the JS change; comment records the same reasoning. |
| `tests/test_create_payload_identity.py:165-179` (`test_the_policy_classes_that_motivated_bug_19_are_unchanged`) | Asserts (regex) that contacts `email` is `manual_protected` in `mergeContacts.js`, AND that the string `field === "email" && decision === "promote"` is present | **Load-bearing pin, must rewrite** — Task 2's verify script greps `mergeContacts.js` for the ABSENCE of that exact predicate string, so this test's presence-assertion of the same string would now fail by construction if left untouched. Rewrite to: (a) keep the companies `domain` manual_protected assertion untouched (BUG-19 for companies is unaffected), (b) drop the contacts email manual_protected assertion, (c) assert instead that contacts `email` is `fill_blank_only` AND that the create-branch identity seed (BUG 19's actual fix, `properties.email = id.email` under a create guard) is still present — that seed logic is untouched by this plan and remains the reason a create is findable. |
| `tests/test_contact_ingest.py:10,43,90` (comments only, no assertion depends on the class name) | Comments describing email as "manual_protected" | Light comment update — the tests' HubSpot fixtures always carry a PRESENT existing email, so `fill_blank_only` + non-blank routes to `stage_only` identically to the old `manual_protected` path; no assertion changes, comment wording updated for accuracy. |
| `tests/test_write_node_transport.py:144` (comment only) | "email is manual_protected and can never promote into the patch" | Light comment update — same reasoning, no assertion change (this test asserts node wiring, not merge decisions). |
| `tests/test_e2e_ingest.py:45,109` (comments only) | Same pattern as `test_contact_ingest.py` — existing email always present in the fixture | Light comment update, no assertion change. |
| `tests/n8n/parity.test.mjs:214` (comment only) | "email (manual_protected, min_conf 95 > csv 80) -> never canonical" over a fixture with a PRESENT existing email | Light comment update — assertion (`!("email" in canonicalPatch)`) is unaffected since `fill_blank_only` + existing non-blank also routes to `stage_only`. |
| `tests/n8n/createIdentitySeed.test.mjs:77` (comment only) | "email is manual_protected AND hard-forced to stage_only on enrich" over a HAND-BUILT merge object that never contains an `email` key at all | Light comment update — assertion (`out.properties.email === undefined`) is unaffected because this test's merge fixture never carries an email candidate in the first place; the seed-guard behavior it is really testing (no unconditional seed on enrich) is untouched. |
| `tests/n8n/writePatchBodyFlow.test.mjs:117-135` (the `DEFAULT_CONTACT_POLICY` doc-comment block + the "Excluded: email (85 < 95 threshold...)" assertion comment) | Documents the OLD per-field expected outcome table against a SEED_ROW with an EXISTING non-blank email (`"brendan@lightningvisuals.com"`) | Rewrite the doc-comment block's email row to the new class/threshold and its actual new reason (existing non-blank -> `stage_only` under `fill_blank_only`, not "confidence 85 < 95"); the assertion itself (`item.properties.email === undefined`) needs no change — same outcome, different reason. |
| `tests/n8n/bareEventChainFlow.test.mjs:349` (comment only) | "canonicalPatch never carries email (manual_protected), so a create must seed it directly from identity_keys" | Light comment update — this test's Lusha/Apollo HTTP mocks are both `{}`, so no email candidate ever reaches `mergeContacts` regardless of policy; the asserted value (`final.properties.email`) comes entirely from the BUG-19 identity seed, untouched by this plan. |
| `n8n/code/reviewDecision.js:44-54,89,229-235` | Documents that contact `approve` always returns `no_candidate` because "no contact enrichment candidate is ever staged in this deployment" and `PROTECTED_CLASSES` (`manual_protected`/`review_required`) | **No rewrite needed** — this module refuses contact `approve` unconditionally on `objectType === "contacts"`, BEFORE it ever consults a field policy or a held candidate; it stays correct regardless of email's class, and reviewDecision.js is not in this plan's file list. Verified in Task 3, not touched here (see the plan's explicit instruction to only "note" this in the SUMMARY as a follow-up, never widen). |

Historical-predicate discipline: the two rewritten source-level comments above (module
header + `DEFAULT_CONTACT_POLICY` comment) will describe the OLD rule in prose without
quoting `field === "email" && decision === "promote"` verbatim, since Task 2's automated
verify greps `n8n/code/mergeContacts.js` for a zero-count of that exact string.

## (f) Per-provider location key shapes observed live (executions 11934/35/37/48/49/50/56)

| Provider | city | state | country | ISO/code field |
|---|---|---|---|---|
| **Lusha** (v3 contacts, `location`) | present 4/4 non-error rows (`"Sydney"`) | **absent 4/4 rows** — no `state` key in the envelope at all, matches the offline fixture (`tests/fixtures/enrichment/lusha_v3_contact.json`) | present 4/4 (`"Australia"`, a full name) | `countryIso2` present 4/4 (`"AU"`) — this is a DEDICATED code field, distinct from the free-text `country` name |
| **Apollo** (`person`) | present only when Apollo actually matched a person record with location data: 1/5 non-null rows (execution 11948, `"Sydney"`); the other 4 returned `person.city/.state/.country` all `None` (unmatched or sparse Apollo record) | present 1/5 (`"New South Wales"` — a full name, never a code) | present 1/5 (`"Australia"` — a full name) | **none** — Apollo's contact record carries no dedicated ISO2/code field at all; only the free-text name fields |
| **ZoomInfo** (GTM contact enrich, `attributes`) | **absent** — the live response's full key set (execution 11948) is `company, contactAccuracyScore, directPhoneDoNotCall, firstName, jobTitle, lastName, lastUpdatedDate, managementLevel, mobilePhone, mobilePhoneDoNotCall, validDate` — no city/state/country/location field of any shape | absent | absent | absent |

**Decision recorded for Task 2:** `zoominfoCandidates` is left untouched for location —
there is no verified location outputField in the live GTM contact response to map, and
none of the sampled executions surfaced one. `lushaCandidates` and `apolloCandidates`
gain city/state/country candidates from free text, plus `hs_country_region_code` derived
ONLY from an already code-shaped value (Lusha's dedicated `countryIso2`, confirmed
code-shaped 4/4 live) — never from a name (Apollo's `country`/`state` are full names in
100% of observed live traffic, so a live Apollo row will not produce an
`hs_country_region_code`/`hs_state_code` candidate today; Task 2's tests exercise the
code-shaped path with synthetic fixtures to prove the logic is correct even though live
traffic hasn't exercised it).

## Portal property verification (no live probe needed)

The five HubSpot-native contact location properties — `city`, `state`, `country`,
`hs_state_code`, `hs_country_region_code` — are confirmed present, `Type: string`,
`Read only value: false` in the operator's 2026-08-26 portal export at
`docs/hs_props/hubspot-properties-export-contacts-19-other-objects-2026-08-26/contact.csv`
(independently re-verified in this task by parsing the CSV with Python's `csv.DictReader`
and reading each of the five rows' `Type`/`Read only value` columns directly — all five
read `string` / `false`). No live property-listing probe is required or was spent. The
same export also carries `ip_city`, `ip_country`, `ip_country_code`, `ip_state`,
`ip_state_code` and similar — these are HubSpot's own analytics fields and are explicitly
**not** write targets for this plan; `tests/test_contact_location_properties.py` (Task 2)
asserts none of them appear in the contact location write set.
