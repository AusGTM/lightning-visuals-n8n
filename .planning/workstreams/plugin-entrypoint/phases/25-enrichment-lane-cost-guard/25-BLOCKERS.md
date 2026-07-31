# 25-BLOCKERS — live findings from plan 25-01

**No token, secret, or webhook URL-with-secret appears in this file.**

---

## Lists API scope

**Probed:** 2026-07-31 · **Verdict: DENIED** · **HTTP 403**

```
lists-scope: verdict=denied status=403 list_id=None
  HubSpot refused the request itself: the credential is missing crm.lists.read.
```

Run via `scripts/check_hubspot_list_scope.py` (25-01 Task 1) through the dotenv wrapper, against
object type `0-2` (companies) with a deliberately non-existent list name. **The name is irrelevant
to this verdict** — a 403 is HubSpot refusing the *request*, before it ever looks the name up. A 404
would have meant granted-but-name-missed; that is not what came back.

**This settles the Lists API only.** HubSpot saved views remain a separate concept with no public
API, unprobed and unprobeable.

### What it means for INGEST-04

INGEST-04 names "list, view, or record IDs". As of this probe:

| Input type | Status |
|---|---|
| **record IDs** | ✅ works — no extra scope needed |
| **lists** | ❌ **denied** — credential lacks `crm.lists.read` |
| **views** | ❌ no public API, and no evidence one exists |

**Two of the three named input types are unavailable.** This is a materially larger gap than the
amendment anticipated during planning, which assumed lists would work and only views would be
dropped.

### The decision this forces — OPERATOR INPUT REQUIRED

Either:

- **(A) Add `crm.lists.read` to the HubSpot app and re-probe.** Restores lists, leaving only views
  dropped — the originally anticipated amendment #7. **Cost is not a UI toggle:** this repo's
  HubSpot integration is an `hs` CLI **projects app, not a classic private app**, so a scope change
  requires `hs project install-app` and a re-auth cycle. That is an operator task with a real
  failure mode, not a checkbox.
- **(B) Scope INGEST-04 down to record IDs only.** No HubSpot change. Amendment #7 becomes larger
  than planned: both lists *and* views are dropped, and the enrichment lane accepts record IDs
  alone.

**Do not let a plan choose this silently.** 25-03 (backend) and 25-04 (client) both implement
whichever branch is taken, and 25-07 applies the wording to REQUIREMENTS.md and ROADMAP criterion 1.

---

## Chunk timing

**Status: PARTIALLY PRE-MEASURED — the live four-POST probe has NOT been run.**

Measured free and read-only on 2026-07-31 by plan 29-02, from `/api/v1/executions` on the live
tenant (full detail in `../29-notices-unattended-sweep/29-TIMING.md`):

| Measured | Value | Basis |
|---|---|---|
| Max single-run duration | **38.9 s** | n=5, company lane |
| Max seconds-per-record | **36.1 s** | n=2 (only 2 runs carried a recoverable record count) |
| Headroom rate | **45 s/record** | observed max + ~25% |

**Derived, pending confirmation:** at ~36 s/record against the ~100 s Cloudflare response ceiling,
`max_records_per_chunk` computes to **2** (`floor(100 / 45)`), and a 3-record POST at ~108 s would
already breach the ceiling.

**What is still unmeasured, and why the live probe still matters:**

- Every measured run is **single-record, company-lane**. Linearity at N>1 is **extrapolated**, and
  Probe B2/B3 exist to test exactly that.
- **None is a full waterfall.** Probe B4 remains the only source for the expensive path — and the
  chunk default must survive the expensive path, not the cheap one.

**The full-waterfall fire (B4) has NOT been run.** Any `max_records_per_chunk` adopted before it is
derived from partial data, and this file says so rather than presenting 2 as a settled number.

---

## View resolution

**Status: NOT YET DECIDED — blocked on the Lists-scope decision above.**

The original three options (`refuse-and-redirect`, `discovery-spike`, `treat-view-as-list`) were
framed assuming lists worked. With lists **denied**, `treat-view-as-list` is doubly rejected — it
would resolve a view against an API this credential cannot call at all.

Record the choice here once the Lists-scope decision is made, naming the option, the date, one
sentence of rationale, the exact operator-facing refusal sentence, and which plan implements it
(25-03 backend, 25-04 client).
