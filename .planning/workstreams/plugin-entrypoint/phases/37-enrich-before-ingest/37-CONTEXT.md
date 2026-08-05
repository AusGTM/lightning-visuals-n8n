# Phase 37: Enrich Before Ingest (client) — Context & Handover

**Written:** 2026-08-05 for a context clear. **Read this first; it is self-contained.**
**Workstream:** `plugin-entrypoint` · **Client only** (`operator-claude-plugin/`).
**DEPENDS ON PHASE 36**, which adds the backend `mode:"propose"` and the match lane. Do not start this
until 36 is deployed and bounced — every step here calls those.

---

## 1. The problem

A contact row with **firstname + lastname + company but no email dead-ends completely and silently.**
Live case: 9 Gold Coast Turf Club directors extracted from their board page — names, roles, company,
no emails. All 9 evaporate on upload.

The deployed ingest lane resolves identity by **email only**. A no-email row becomes
`outcome:"ambiguous"` → `review` → a bare `Set` node emitting `{"queue":"needs_review"}`. **No HubSpot
write, no object id, no footprint.** So it cannot be enriched later either — both enrichment entry
points need an existing HubSpot object id.

`skills/contact-upload/SKILL.md` step 7 already documents the symptom: *"this row cannot resolve on
retry ... until it gets an email address or is handled manually in HubSpot."*

**VERIFIED, and this is why the fix cannot live only in the new flow:** `config/column_mapping.yaml`'s
identity rule is `any_of: [[email], [firstname, lastname, company]]`, and
`extraction.write_dispatch_csv` guards only against **extra** keys. So the plain extraction lane
accepts emailless rows today, writes them with an empty email cell, and they evaporate. **The gate
belongs at that choke point**, which fixes every caller at once and is also the smaller diff.

---

## 2. The decision (operator, 2026-08-05)

Enrich-first is the **default**; ingest-first stays available for dense datasets. Governing rule, the
operator's words: *"a contact and company should be as enriched as possible BEFORE ingest. We do NOT
want incomplete contacts and companies in HubSpot."*

### Target flow

```
extract → match against HubSpot (exact, then fuzzy-propose) → operator confirms
        → enrich the unmatched   (cost preview → "arm the enrichment")
        → ENRICHED PREVIEW
        → "arm the upload" → ingest   (rows without an email are HELD, never sent)
```

### Locked decisions

| # | Decision |
|---|---|
| 1 | Match tiers: `email EQ` → HIGH, auto. Else `lastname EQ` + `company CONTAINS_TOKEN` → MEDIUM, **proposed per row**. No hit → enrich. A failed match chunk is `unchecked`, **never** `unmatched`. |
| 2 | **Enriched preview before arming ingestion.** |
| 3 | **Ingest gate: email present, else HELD and reported. No force flag.** The way to send a held row is to give it an email. |
| 4 | **Chunking required** — batch uploads are a certainty. |
| 5 | **Two arming phrases, unchanged.** |
| 6 | **Contacts only.** There is no company canonical set (`column_mapping.yaml` defines seven contact props and one identity rule). Companies are the named upgrade path, not built here. |

---

## 3. What exists — reuse, do not reinvent

- **`scripts/preview_enrichment.py`** — renders records/providers/cost/chunks. **Every function is
  PURE, no network.** `cost_guard.estimate_batch(record_count, object_type, providers, rates)` is
  plain arithmetic over a COUNT and never touches a record id — **it already works for rows that are
  not HubSpot records.** Only `records_block()` hardcodes "these already exist in HubSpot".
- **`scripts/chunking.py`** — `plan_chunks()` splits `spec["record_ids"]` only; `chunk_ceiling()` reads
  `max_records_per_chunk` (currently **2**, derived from a measured 37.44 s/record full-waterfall
  against a ~100 s Cloudflare ceiling) with a deliberate **no-fallback refusal**; `dispatch_plan()`
  iterates chunks, skips failures, returns `DispatchOutcome`.
- **`scripts/enrichment.py`** — `build_envelope()` accepts `record_ids` | `list` | `view`(refused);
  `dispatch_enrichment(envelope, armed, config, transport=requests)`, `DEFAULT_TIMEOUT=120`
  (deliberately above the ~100 s ceiling).
- **`scripts/header_suggest.py` + `scripts/name_split.py`** — **the propose-then-confirm precedent to
  follow**: propose with a confidence and a named reason, confirm per item, and the writer applies
  ONLY what was resolved because it has no fallback of its own.
- **`scripts/config_gate.py`** — `CAPABILITY_KEYS`; `contact-upload` and `enrichment` need identical
  keys and are separate rows purely so a refusal uses the right wording.

---

## 4. Module delta — 1 new file, 5 small edits, 0 new send paths for enrichment or ingest

**New: `scripts/preingest.py`**

| function | kind | job |
|---|---|---|
| `rows_from_table(path)` | pure | canonical-keyed rows via `preview.label_headers`' **exact** alias lookup only. No second mapping authority, no fuzzy — `preview.py:39-44` forbids fuzzy there and this must not smuggle it in. |
| `build_rows_spec(rows)` | pure | ids assigned **once, before chunking** — a per-chunk `enumerate` collides across chunks. |
| `fetch_matches(chunk, config, transport=requests.post)` | network, **unarmed** | one POST per chunk; body carries only the lookup keys. |
| `match_batch(plan, config)` | network loop | sequential, skip-a-failing-chunk, mirrors `dispatch_plan`'s contract without arming. |
| `classify_matches(rows, response)` | pure | the tiering. |
| `apply_match_decisions(classified, resolved)` | pure | applies **only** what the operator resolved. |
| `merge_enriched(rows, responses)` | pure | joins by **`row_id`, never by position**. |
| `render_enriched_preview(...)` | pure | the post-enrichment, pre-ingest render. |

**Edited:**

1. **`scripts/extraction.py`** — `hold_emailless(rows) -> (sendable, held)`, and `write_dispatch_csv`
   **raises** when handed an emailless row, naming the rule and pointing at `hold_emailless`. Loud, not
   a return value a caller can ignore. Guards run **before any file is opened**, so a refused call
   leaves the disk untouched (`header_suggest`'s idiom).
2. **`scripts/chunking.py`** — `plan_chunks` gains a `rows` branch (positional, same as `record_ids`);
   `failed_batch()` gains the matching branch; `chunk_ceiling(config, key=CEILING_KEY)` gains the key
   parameter so match reads its own ceiling. **Do not reuse `max_records_per_chunk` for match** — it is
   2, derived from the waterfall, and would make a 200-row batch 100 round trips for a call that runs
   two HubSpot searches. Ship `max_rows_per_match_request` in `operator.local.example.json` with a
   **measured** value and the measurement in the comment, the way the 37.44 s note is carried.
3. **`scripts/enrichment.py`** — `build_envelope` gains a `rows` form. **`dispatch_enrichment` is
   untouched**, so the enrichment half of this flow adds **no send path** and reuses the arming gate,
   the 120 s timeout, `dispatch_plan`'s skip rule and `failed_batch` re-send.
4. **`scripts/preview_enrichment.py`** — one new `records_block` branch for a rows spec ("these rows
   are **not** in HubSpot yet — nothing is created by enriching them"). The "already exist in HubSpot"
   tail stays on the ids/list branches. `cost_block`/`providers_block`/`chunks_block` unchanged. `__main__`
   gains: if `argv[1]` names an existing file, read the spec from it (200 rows will not fit in argv).
5. **`scripts/config_gate.py`** — one `"match": ("n8n_url", "webhook_secret")` row + description. Key-identical
   to the others, separate for the same reason the `enrichment` row is separate: a match refusal must
   not print upload wording.

**New skill: `skills/enrich-before-ingest/SKILL.md`** — owns the turn sequence and hands off to
`contact-upload` steps 6–10 **verbatim** for dispatch/report/retry/cleanup. Do **not** fold this into
`contact-upload/SKILL.md`: it is already 18.3 KB with 10 steps and a lettered insert.

---

## 5. Operator-facing turn sequence

1. **Target + the two-arm warning.** `config_gate.py`; relay target, disarmed, `can_send`. Then say up
   front that this flow asks you to arm **twice, at two different moments, and why** — so the second
   ask is not a surprise that trains the operator to pre-arm.
2. **Rows + match.** Rows from `extraction.md` (the live 9-directors case) or `rows_from_table`. Then a
   chunked, **unarmed** match. Four groups reported: **auto-matched** (count only), **proposed**
   (per row), **unmatched** (→ enrichment), **unchecked** (a match chunk that failed — reported as its
   own state with a retry offer, because *"we did not find one"* and *"we could not look"* are
   different answers).
3. **Confirmation** — one proposal per turn, each showing enough of the candidate to judge it
   (id, firstname, lastname, email, company, jobtitle, lastmodifieddate) **in the same breath as the
   question**. This is `sample_values`' exact reasoning: an operator who has not seen the candidate is
   being asked to rubber-stamp. Two or more MEDIUM candidates → **ambiguous**, all shown, never
   auto-picked. A batched yes is not a confirmation.
4. **Cost preview** over the unmatched + rejected-proposal set. Four blocks, unchanged.
5. **"arm the enrichment" → enrich** via `dispatch_plan`; `merge_enriched` writes results back.
6. **ENRICHED PREVIEW** — per row: what came in, what enrichment added, its source, and the gate
   verdict SEND / HELD. Held rows named with reasons. State explicitly that nothing has reached HubSpot.
7. **"arm the upload" → ingest** — `write_dispatch_csv` (raises if a held row slipped) → `dispatch.py`
   → contact-upload steps 7–9 for the report → **restate the held rows AFTER the backend report**
   (they appear in no execution, and a row mentioned once five turns earlier is a row nobody acts on)
   → offer confirmed-match ids to `enrich-records` → step 10 deletes the scratch artifacts.

**Bucket outcome worth stating in the skill:** a **confirmed MEDIUM match with no email** is not
ingested (emailless is the dead-end) and not enriched by attributes either — but it now has an object
id, which is exactly what `enrich-records` needs. Hand the ids to that lane. This flow does not write
the spreadsheet's own columns onto a matched record; the only property-write path the client has is
email-keyed contact-upload. Say so plainly.

**Consequence to state:** this flow sends a **rewritten** CSV of exactly the approved rows, not the
operator's original file. Holding rows back is impossible otherwise, and it is already what the
extraction lane does.

---

## 6. Arming — two phrases, and why they cannot collapse

**Two: "arm the enrichment" before the spend, "arm the upload" before the write.** No combined phrase,
no carry-over, no change to either existing lane.

1. They guard two different irreversible things — money, and records in HubSpot — at two different
   moments, **with the enriched preview between them**. The second arm *is* the operator's response to
   that preview. That is not friction; it is the decision the whole flow exists to create.
2. A combined phrase would necessarily be spoken **before** the enriched preview exists, granting the
   HubSpot write before the operator can see what they are approving.
3. It is structurally impossible to collapse by accident: the enriched preview must land in the
   operator's turn before the ingest arm can be spoken, so the two `armed` arguments are necessarily in
   **different turns**. Even an operator who says both phrases up front is asked again, because the
   grant is a per-call argument that never outlives its turn. **Pin this as a skill-contract test.**
4. The match POST needs **no** arming — it writes nothing and spends nothing. Make that structural, not
   asserted (see §7).

`enrich-records/SKILL.md`'s invariant survives verbatim: arming one lane still arms no other.

---

## 7. The AST arming guard — amend deliberately, and close a hole

`tests/test_retry_reuses_dispatch.py` pins the send-shaped function set:

```python
_EXPECTED_SEND_SHAPED = [("backend_status.py", ["fetch_backend_status"]), ("dispatch.py", ["dispatch"])]
```

failing with *"A second dispatch path would let a retry bypass the arming gate"*.

`fetch_matches` is a body-carrying POST, so write it `transport=requests.post` — **visible to the
guard** — and add it to the allowlist with reasoning in the same register as the status entry: *the
match POST reads HubSpot search results, writes nothing and spends nothing; it is a read wearing a
POST's clothes, allowlisted rather than armed.*

**Two keeper tests stop that being a rubber stamp:** the match POST passes no `files=`/`data=`, and its
`json=` body keys are AST-pinned to a frozen lookup allowlist `{email, firstname, lastname, company}` —
deliberately not phone/jobtitle/linkedin_url. Plus a server-half counterpart: the match endpoint's node
chain contains no write node (mirror `test_backend_status_wiring.py`).

**The hole:** `enrichment.dispatch_enrichment(..., transport=requests)` is **module-shaped**, and the
guard only matches `requests.post` as an attribute — so **it has never seen the enrichment send path.**
A second dispatch path is already invisible today, and the tempting move here is to write the match
client the same way to slip past. Instead extend `_send_shaped_function_names` to also flag a function
whose `transport` defaults to the bare `requests` module and calls `transport.post/.put`, and allowlist
`dispatch_enrichment` with its reasoning (armed, no default, the enrichment lane's single send).
~10 lines of AST. Without it the guard's own failure message is not true of the code it guards.

---

## 8. Definition of done

1. The 9-directors case walks end to end: extract → match → confirm → enrich → enriched preview →
   ingest, and **every row that reaches HubSpot carries an email**.
2. Rows the waterfall could not complete are **named and held**, never sent — `write_dispatch_csv`
   raises and the file is not created.
3. A match chunk that fails yields `unchecked`, never `unmatched`.
4. `apply_match_decisions` refuses a decision naming an unproposed row, or a candidate id not among
   that row's own candidates. Nothing applied on refusal.
5. `merge_enriched` joins by id, refuses a duplicate id, and ignores an unknown id rather than
   attaching it to a row.
6. The rows envelope is pinned **byte-identical py↔js** (`tests/n8n/rowsEnvelopeContract.test.mjs`) —
   this is the D-19 flat-vs-nested class that shipped once and killed the list lane while both suites
   stayed green.
7. Two arming phrases, no combined one, and the ingest-arm section appears **after** the
   enriched-preview section by heading index.
8. Suites green; plugin version bumped in the SAME commit as the CHANGELOG cut; pushed; **merged to
   master**; marketplace clone refreshed.

---

## 9. Non-negotiables

1. **Pin behaviour at the layer the operator reaches** — CLI as a subprocess against an isolated plugin
   root for anything the operator experiences; direct import for pure logic. Harnesses:
   `tests/test_config_gate.py::_run_cli`, `_run_header_cli` in `tests/test_header_suggest.py`.
2. **Never fix a test by making its premise false.**
3. **Red-check every new test** — revert, confirm the specific assertion fails, restore.
4. **Commit explicit paths only.** Never `git commit -a`.
5. **Never touch `~/.claude/plugins/`** in tests or scripts.
6. **The autouse `no_network` guard** means no test may perform a real request — use
   `stub_post_transport_factory` / `stub_module_transport_factory` from `tests/conftest.py`.
7. **Release checklist:** bump `.claude-plugin/plugin.json` in the SAME commit as the CHANGELOG cut →
   push → **push to master** → refresh the marketplace clone. `0.9.0` shipped with a correct bump
   sitting on a feature branch and the Update button stayed grey until master had it. **Master is the
   branch the marketplace reads.**

---

## 10. One existing test flips deliberately

The emailless-row round-trip case in the extraction tests (Ben's row, empty email cell) currently
asserts the row is written. It now asserts the **refusal**. That is the intended behaviour change and
the fix for the live case — record it in the SUMMARY, do not silence it.

---

## 11. Test commands (exact forms — alternatives are broken here)

```bash
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q   # 1052 passed, 5 skipped
.venv/bin/python -m pytest -q                                  # 1933 passed, 6 skipped
node --test tests/n8n/*.test.mjs                                # 553 pass (FILE glob only)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json             # must be 0
```

---

## 12. Rejected — do not re-propose without new evidence

One combined arming phrase (grants the write before the preview exists) · carrying an arm across turns
· writing the match client module-shaped to slip past the AST guard · one endpoint with a
match/enrich mode flag (puts spend/no-spend on a boolean) · zipping enrichment responses to rows by
position (silent misalignment, unspottable) · a "force send anyway" flag (contradicts the governing
rule) · creating a stub HubSpot record so an emailless row gets an id (that IS the incomplete contact
the rule forbids, and it makes a dedupe problem later) · client-side fuzzy matching against a
downloaded HubSpot mirror (no credential, second identity authority) · reusing `max_records_per_chunk`
for match (2 rows per search request) · putting the gate only in the new flow (the extraction lane has
the same dead-end today).

---

## 13. Amendment — operator, 2026-08-05 (second session, recorded verbatim in intent)

**Governing addition:** *"at the end of an enrichment cycle there shouldn't be an unenriched contact
or company, and if there is due to a break in the enrichment batch, there should be a way to resume
idempotently."* HubSpot-as-queue is the **intended** design for enrichment state, not a fallback —
do not build boundaries that close it off.

Both of these are IN SCOPE for this phase ("belt and suspenders — implement both"):

**(a) Run manifest + idempotent resume (pre-ingest).** Client-side state today is conversational and
evaporates on a broken batch; re-running re-spends provider credits on rows already enriched. Fix:
persist a run manifest mapping `row_id → terminal verdict` (matched / enriched / held / unchecked)
as its own artifact under `durable_paths.resolve_state_path` — NOT inside `artifact_store.py`, whose
field-refusal is deliberate and stays. Resume = skip rows holding a terminal verdict, re-request only
the rest. `row_id` is client-generated, stable, echoed verbatim by the backend, never interpreted —
it is the idempotency key. The manifest never stores an arming grant (Phase 23 D-11 holds: the grant
lives only in the turn).

**(b) Post-ingest handoff to the HubSpot queue.** Once ingested rows have object ids, set
`enrichment_requested = true` on the created records so the existing scheduled poller
(CLAUDE.md §13.2/§19) sweeps anything the pre-ingest pass could not finish — same move this phase
already makes for confirmed-match ids via `enrich-records`, extended to created records. This is what
actually guarantees no record ends a cycle unenriched; §12's stub-record rejection stands, but its
cost is now bounded: pre-ingest exclusion is temporary, not terminal.

**Ceiling ruling (closes the open decision in 37-VALIDATION.md):** the unconditional
`events.length > 2` refusal in `Parse HubSpot Event` is an unnecessarily strict boundary when applied
to `mode:"propose"` — the 2 was derived from full-waterfall timing (37.44 s/record) and a match call
runs zero provider calls. Make the guard **mode-aware in Phase 36 before its deploy** (one deploy,
not two): `return_only` requests get their own ceiling; write-path requests keep 2. The match
ceiling's number must be **earned by a live probe** (B4's shape: measured latency + headroom against
the ~100 s Cloudflare bound) at the first live propose run — ship a conservative provisional value
with the derivation in the comment, replace it with the measured one, same discipline as the 37.44 s
note.
