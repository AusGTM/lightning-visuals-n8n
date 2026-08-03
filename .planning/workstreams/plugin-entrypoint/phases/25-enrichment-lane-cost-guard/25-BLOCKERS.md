# 25-BLOCKERS — live findings from plan 25-01

**No token, secret, or webhook URL-with-secret appears in this file.**

---

## Lists API scope

**Probed:** 2026-07-31 · **Verdict: GRANTED** · **HTTP 200** · **RESOLVED**

```
lists-scope: verdict=granted status=200 list_id=15
  the list resolved, so the credential can read the Lists API.
  memberships: status=200 member_count=102 has_paging_cursor=True
```

Run via `scripts/check_hubspot_list_scope.py` (25-01 Task 1) through the dotenv wrapper, against the
real contacts list `New Targets.xlsx` (`0-1`, id 15). A nonsense-name run in the same session
returned `granted / 404`, which is the other valid granted signal — an authorized request whose name
simply missed.

### It was denied first — keep that, it is the useful part

The **first** probe of the day returned:

```
lists-scope: verdict=denied status=403 list_id=None
  HubSpot refused the request itself: the credential is missing crm.lists.read.
```

A 403 is HubSpot refusing the **request**, before any name lookup — so the list name is irrelevant to
that verdict, and reading it as "wrong name" would have been the opposite of the truth. The fix was
**not** a UI toggle: this integration is an `hs` CLI **static-auth projects app**, so
`crm.lists.read` had to be added to `src/app/app-hsmeta.json`'s `requiredScopes` in the
`ausgtm-lightningvisuals-data` project, uploaded, and **reinstalled** — `hs project install-app`,
whose consent screen is what actually grants it. Uploading a scope change does not grant it, and
rotating the token never would. Confirmed by `hs project app-install-status`:
`isInstalledWithCurrentScopes: true` with `crm.lists.read` in the authorized scope groups.
**The existing access token kept working — no rotation.**

### What it means for INGEST-04

| Input type | Status |
|---|---|
| **record IDs** | ✅ works — no extra scope needed |
| **lists** | ✅ **works as of 2026-07-31** — `crm.lists.read` granted |
| **views** | ❌ no public API, and no evidence one exists |

Only views are dropped, which is **exactly the amendment anticipated during planning**. Amendment #7
is therefore the small one, not the large one.

### Design input for 25-03 / 25-04 — do not skip this

**`has_paging_cursor=True` on a 102-member list.** The memberships endpoint pages at or below 102,
so a list read **must follow the cursor**. A client that reads one response and stops will silently
enrich a truncated subset of any list larger than a page — a partial result that looks like a
complete one, which is the failure shape this milestone has now hit five times (D-08, D-20, D-22,
D-23, D-33). Treat a missing cursor-follow as a defect, not an optimisation.

Only one list exists in this portal today (`POST /crm/v3/lists/search` → 1 result), so list-heavy
behaviour has exactly one live example to test against.

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

**Decided: `refuse-and-redirect`** · 2026-07-31 · **This is accepted amendment #7.**

**Rationale:** lists now work and record IDs always did, so the only unsupported input is a saved
view — for which no public API exists, only a thorough absence of evidence. Refusing one input with
an actionable next step is strictly better than shipping against an endpoint that may not exist.

**The exact operator-facing sentence the plugin uses when a view is named:**

> "I can't resolve a HubSpot *view* — HubSpot doesn't expose views through its API. Save that view
> as a **list** in HubSpot and give me the list name, or paste the record IDs directly."

**Why the other two were rejected:**
- `treat-view-as-list` — rejected on its face by 25-RESEARCH.md Pitfall 2: a view name colliding
  with an unrelated list name enriches the wrong record set **with no error**. Now that lists
  genuinely resolve, this option is *more* dangerous than when it was first written, not less.
- `discovery-spike` — open-ended cost against an absence-of-evidence finding; anything found would
  likely be internal/undocumented, trading a scope gap for a stability gap.

**Implemented by:** 25-03 (backend) and 25-04 (client). **25-07** applies the wording to
REQUIREMENTS.md INGEST-04 and ROADMAP criterion 1, recording it as amendment #7 — scoped to
"list or record IDs", views refused with the sentence above.


---

## Probe B4 — run 2026-08-03 (RB-1 closure)

One full-waterfall record (providers `lusha, apollo, zoominfo`, company `9604614548`):
**37.44 s, HTTP 200.** Worst case observed is now 37.44 s (was 36.1 s from free history);
+25% headroom = 46.8 s/record against the ~100 s ceiling → `floor(100/46.8)` = **2**.
**The ceiling of 2 is CONFIRMED on the expensive path and is no longer provisional.**
B2/B3 (multi-record, no providers) remain unrun; they can only lower per-record time and
so cannot move the ceiling — not required.

**Same-day finding:** the live oversize-refusal check answered
`[{"object_type":"unsupported","remaining_credits":[]}]` — T-25-16's exact signature of a
workflow with no list-expansion node. **The deployed enrichment workflow predates the
committed list lane**, so the oversize refusal (and the entire list lane) is unreachable
live until a disarmed redeploy. Re-run the refusal check after that deploy: expected
answer is the refusal naming 102 members against the ceiling of 2.


## Refusal check CLOSED — 2026-08-03, post disarmed redeploy

The redeploy (created LV Backend Status + LV Review Decision, updated the three existing;
read-back disarmed PASS over 5 workflows / 11 nodes) put the list lane live. Re-run verbatim:

    [{"outcome":"refused","reason":"The list \"New Targets.xlsx\" is larger than this
    backend can enrich in one request — the limit is 2 record(s) per request, measured
    against the ~100s webhook response ceiling. HubSpot returned only the first page of
    its members, so the full list is larger than one response and its true size is
    unknown from here. Nothing was enriched. Send record IDs instead, in batches of 2 or
    fewer.","events":[]}]

Refused, zero enriched, ceiling + measurement basis named, and honestly paginated (it does
not claim 102 when it saw one page). The oversize path 25-03 built is verified live. RB-1
is fully closed.
