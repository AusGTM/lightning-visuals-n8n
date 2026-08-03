# 30-07 / RB-9 — the armed review canary

**Status: PRE-FLIGHT SEEDED, CANARY NOT YET RUN.** Every verdict below is an observation or it is
left blank. Nothing here may be filled in from expectation.

---

## Pre-flight — established read-only, 2026-08-03, before any arming

| Item | Value |
|---|---|
| Canary record | **`9604614548` — Melbourne Racing Club, a COMPANY** |
| How it was chosen | RB-7's armed enrichment produced it: the pipeline flagged it `needs_review` and held a real conflict, satisfying step 1 with no setup |
| The held conflict | `industry` — provider `arts, entertainment, and recreation` vs stored `SPORTS`; staged as a review candidate, current value untouched |
| Review workflow | `WBJwoZOo63wzeP69` — `LV Review Decision (Cloud)`, **currently inactive** |
| Review endpoints | `hubspot/review/queue`, `hubspot/review/decision` — both in that workflow, hence `http_404` until step 4 |
| Flag state BEFORE | **disarmed everywhere** — `verify_live_write_safety.py --expectation disarmed` → `VERDICT: disarmed PASS`, 5 workflows / 11 declaring nodes |
| Tenant | `https://alexherman.app.n8n.cloud` |

Because the record is a **company**, point 3's "contacts are allowlistable only by `TEST_RECORD_IDS`"
trap does not apply — but `TEST_RECORD_IDS=9604614548` is what to use regardless.

### The reload gap applies here — read this before step 3

`ENABLE_BAKED_FLAGS` overlays every workflow in the deploy set, and `ALLOW_HUBSPOT_REVIEW_WRITES` is
declared in four, **three of them ACTIVE**:

```
LV Scheduled Maintenance (Cloud)     ACTIVE    4 nodes  <-- hosts the 15-min approve backstop
LV Enrichment (Cloud template)       ACTIVE    2 nodes
LV Contact Ingest (Cloud template)   ACTIVE    2 nodes
LV Review Decision (Cloud)           inactive  2 nodes
```

`deploy_n8n_workflows.py` PUTs without activating, so those three keep serving disarmed bodies until
bounced. Predicted, before the fact:

1. **Step 3b will report `armed PASS` while three running instances are still disarmed** — it reads
   stored content. Same false confidence that burned RB-3.
2. **Step 8's APPROVE will probably do nothing**, because the documented approve flow goes through
   `reviewApply.js`'s 15-minute backstop, which lives in `LV Scheduled Maintenance` — active, cadence
   confirmed live (ticks 03:30, 03:45, 04:00Z). Its running body will still be disarmed.

**Mitigation: bounce all three active workflows immediately after step 3, and again after step 9.**
Step 4 handles `LV Review Decision` by activating it from cold.

**Step 9's order is reversed from the runbook's original:** deactivate `LV Review Decision` FIRST,
then redeploy disarmed, then bounce the three actives, then read back.

**Record whether prediction 2 held.** If the approve lands without a bounce, the model of the
backstop is wrong and that is the more valuable finding.

---

## The run — to be filled in by the operator

### Step 2 — before snapshot
- `canary_record_snapshot.py snapshot --label 30-07-review-canary --company-id 9604614548`
- Snapshot path:

### Step 3 — armed deploy, review writes only
- Rewrite count for `ALLOW_HUBSPOT_REVIEW_WRITES` (**must be non-zero**; zero = refused, deployed nothing):
- Bounce of the three active workflows run: ☐

### Step 3b — armed read-back
- `--expectation armed --allowlist 9604614548 --expect-armed ALLOW_HUBSPOT_REVIEW_WRITES`
- Verdict (verbatim):
- **If this does not pass, do not take a decision.**

### Step 4 — activate the review-decision workflow
- Activated: ☐  · queue endpoint reachable afterwards (no longer 404): ☐

### Step 5 — the queue read
- Record appears in the queue: ☐
- Conflict rendered in plain language:
- Protected fields labelled:

### Step 6 — decision to the exact-write display, writeback NOT armed
- Property write shown: ☐  · states nothing was sent: ☐

### Step 6b — the plugin gate, proven independently
- With `ALLOW_REVIEW_SUBMIT` **unset**, attempt the rejection.
- Refusal names the variable: ☐ / verbatim text:

### Step 7 — REJECT
- Verdict from `verify_decision` (never from an HTTP status):
- Review reason holds the text: ☐
- **Record is STILL queued** — needs-review flag and stored candidate unchanged: ☐

### Step 8 — APPROVE
- Verdict:
- Candidate values now on the record: ☐
- Review flags cleared: ☐
- Provenance blob: entry per applied field naming a **human** source, `human_approved`, timestamp,
  reason: ☐
- **Previously recorded machine source still readable in that entry:** ☐
- **Provenance entries for untouched fields intact:** ☐
- Did the approve require the bounce predicted above? (yes / no — either answer is a finding):

### Step 9 — close out (ORDER REVERSED from the runbook's original)
- `LV Review Decision` deactivated **first**: ☐
- Disarmed redeploy run: ☐
- Three active workflows bounced: ☐
- `verify_live_write_safety.py --expectation disarmed` verdict:
- Live read-back confirms the review constant in its **disabled** form: ☐
- `ALLOW_REVIEW_SUBMIT` unset: ☐

### Step 10 — snapshot comparison
- `canary_record_snapshot.py compare --snapshot <path>` output:
- **Any record other than `9604614548` written → STOP and report. That is a gate failure.**

### D-31 caveat — do NOT write "protected fields are protected"
`manual_protected` is filtered on the review-decision endpoint (`reviewDecision.js`, by class) but
**not** on the 15-minute backstop (`reviewApply.js`, allowlists by key, leaving `domain` and
`annualrevenue` writable) — and the backstop is the path the approve flow uses. Record what was
observed, nothing wider.

### Anything that did not behave as described — verbatim
