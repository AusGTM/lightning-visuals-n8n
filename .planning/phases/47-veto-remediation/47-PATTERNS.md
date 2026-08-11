# Phase 47: Veto Remediation - Pattern Map

**Mapped:** 2026-08-11
**Files analyzed:** 1 new script (D-18 amendment forces two write legs) + 2 test-sibling targets
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/remediate_veto_companies.py` (new, name is Claude's discretion) | script / batch-CRUD orchestrator | batch PATCH + poll-settle + webhook POST | `scripts/backfill_seed_company_scores.py` | exact (component-write + settle half) |
| — arming ceremony inside same script or a thin wrapper | script / safety-gate | event-driven arm/dispatch/disarm | `scripts/june_run_arm.py` | exact |
| — web-research enrichment step | service call | request-response (LLM + web_search tool) | `src/web_research.py::claude_web_research` | exact |
| — HubSpot writes | service client | CRUD (batch PATCH / GET / search) | `src/hubspot_client.py` | exact |
| — n8n webhook POST leg (D-18) | service call | event-driven (synthetic property-change event) | `operator-claude-plugin/scripts/enrichment.py::dispatch_enrichment` (+ `dispatch.py`'s armed-gate shape) | role-match (correct auth header + envelope shape; POSTs a different envelope than the raw HubSpot-webhook-event array D-18 needs) |
| `tests/test_remediate_veto_companies.py` (new sibling) | test | unit (offline) | `tests/test_backfill_seed_company_scores.py` | exact |
| `tests/test_scoring_parity.py::test_veto_clear_after_correction` (existing, will start passing or needs a documented reason it doesn't) | test | integration (live, disposable) | itself — already committed, extract verbatim below | exact |

## Pattern Assignments

### `scripts/remediate_veto_companies.py` — Leg 1: component-score write (role: script, flow: batch CRUD)

**Analog:** `scripts/backfill_seed_company_scores.py` (reuse via import, do not copy-paste the whole file — call its functions or lift the identical shape for a second, separately-gated script per D-11/D-19's "operator-only, per-shell, never set by Claude" env-gate discipline).

**Two-key arm gate + hard record cap** (lines 80-85, 138-165):
```python
DEFAULT_MAX_RECORDS = 10
HARD_CEILING_RECORDS = 25

def _resolved_max_records() -> int:
    raw = os.getenv("BACKFILL_MAX_RECORDS", str(DEFAULT_MAX_RECORDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_MAX_RECORDS
    return min(value, HARD_CEILING_RECORDS)

def enforce_sample_cap(sample_ids: list) -> bool:
    return len(sample_ids) <= _resolved_max_records()

def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SCORE_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow
```
For this phase: `BACKFILL_MAX_RECORDS` (or the new phase's equivalent env var) must be set ≥17 (default 10 refuses 17 explicit IDs — RESEARCH.md Pitfall 3).

**`compute_components()` — the ONLY thing allowed to compute the 5 writable score properties** (lines 93-117):
```python
def compute_components(props: dict) -> dict:
    canonical = {k: props.get(k) for k in CANONICAL_INPUT_PROPS if props.get(k) not in (None, "")}
    record = HubSpotRecord(object_type="companies", id="0", properties=canonical)
    result = compute_icp_score(record, {})
    by_signal = {c["signal"]: c["points"] for c in result.breakdown["components"]}
    gambling_points = 0
    for deduction in result.breakdown["graduated_deductions"]:
        if deduction["signal"] == "gambling_operator":
            gambling_points = deduction["points"]
    return {
        "org_type_score": by_signal.get("org_type", 0),
        "geography_score": by_signal.get("geography", 0),
        "annual_revenue_score": by_signal.get("revenue_band", 0),
        "produces_content_score": by_signal.get("produces_content", 0),
        "gambling_score": gambling_points,
    }
```
This phase's script must run this AFTER writing the three new canonical inputs
(`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized` from D-08's web
research) — `compute_components` reads `props` passed in, it does not fetch; the caller
is responsible for re-fetching the record (or passing the just-written values through)
before calling it, per D-04's "enrich first, then one recompute" ordering.

**Never-write guard (D-07) — copy this comment verbatim into the new script** (lines 69-71, 19-22):
```python
# The five writable component properties this script is the ONLY thing in this plan
# allowed to write. lv_icp_fit_score/_tier/_flag/_reason are derived elsewhere and must
# never appear in a payload this script builds.
```
Extend the guard's *scope* for this phase: the new script also must never write
`lv_anti_icp_flag`/`lv_anti_icp_reason` directly (same rule); it changes the three
canonical inputs and lets the calculated property / WF1 / n8n Decide node derive the
rest.

**`_settle()` — verbatim, NO expected-value assertion (D-10 gap, confirmed by RESEARCH.md)** (lines 252-271):
```python
def _settle(company_id: str, prop: str, timeout: float = 120, interval: float = 5) -> None:
    """Polls prop until it stops changing across two consecutive reads, or timeout
    elapses. Prints the final value -- this script has no assertion of its own on the
    result, Task 3's parity sweep is what checks correctness."""
    start = time.monotonic()
    previous = None
    first_read = True
    while True:
        record = get_record("companies", company_id, [prop])
        current = record.get("properties", {}).get(prop)
        elapsed = time.monotonic() - start
        if not first_read and current == previous:
            print(f"  {company_id}: {prop}={current!r} (settled after {elapsed:.1f}s)")
            return
        first_read = False
        previous = current
        if elapsed >= timeout:
            print(f"  {company_id}: {prop}={current!r} (timed out after {elapsed:.1f}s)")
            return
        time.sleep(interval)
```
D-10 requires "fail loudly on any record that never settles" — this body does not raise
on timeout OR on wrong-value. The planner must specify a **new wrapper**, not a drop-in
reuse, e.g. `_settle_and_assert(company_id, prop, expected, timeout, interval)` that
calls this poll shape (or `tests/scoring_fixtures.py::settle()`, identical signature,
returns `(value, elapsed)` instead of printing) and raises if the final value doesn't
match `expected`. Two independent poll loops are needed per record — one for
`lv_icp_tier` (pure-HubSpot latency, ~120s/5s defaults) and one for
`lv_anti_icp_flag`/`lv_anti_icp_reason` (n8n-dependent latency, mechanism-specific) —
per RESEARCH.md's Validation Architecture "Sampling Rate" note; do not share one timeout.

**`--company-id` repeatable flag, not `--ids`** (lines 198-203):
```python
parser.add_argument("--company-id", action="append", default=[], dest="company_ids",
                     help="Explicit company id to seed (repeatable). If omitted, the "
                          "sample is selected via search_records for companies with "
                          "at least one canonical lv_* input populated.")
```
Pin the 17 via 17 repeated `--company-id` args (or add a `--ids` comma-list alias in the
new script) — do not assume `--ids` exists on the reused script.

---

### Leg 2: the operator-only arming ceremony (D-11/D-19, two surfaces now)

**Analog:** `scripts/june_run_arm.py`

**Asymmetric arm/disarm gate — arm checked, disarm deliberately NOT gated** (lines 12-29, 100-121):
```python
"""
Every safety check stays inside n8n_arming ... the ALLOW_N8N_ARM kill switch, the
allowlist charset validation, and the fail-closed re-scan are never duplicated here.
...
Disarm mode is deliberately NOT gated on ALLOW_N8N_ARM -- an operator must always be able
to close the window, per n8n_arming.disarm's own docstring...
"""
def disarm(workflow_name: str = DEFAULT_WORKFLOW_NAME) -> dict:
    """Close the window and verify it closed, by an independent re-read. Never calls
    n8n_arming.arm_for_dispatch -- the two are separate operator actions by D-06."""
    cfg = config_gate.load_config()
    workflow_id = executions_client.resolve_workflow_id(cfg, workflow_name=workflow_name)
    ...
    try:
        return n8n_arming.disarm(workflow_id, cfg)
    except n8n_arming.DisarmFailed as exc:
        return exc.outcome
```
Per the Amendment (D-18/D-19): this phase's VETO-02 window must arm **both** surfaces —
(1) the new script's own two-key env gate (`DRY_RUN=false` + a phase-scoped
`ALLOW_*` flag, mirroring `ALLOW_SCORE_BACKFILL`) for the direct-PATCH leg, AND (2) n8n's
`ALLOW_HUBSPOT_RECORD_WRITES` + `TEST_RECORD_IDS` gate via `n8n_arming.arm_for_dispatch()`
for the webhook-POST leg, with `TEST_RECORD_IDS` set to exactly the 17 pinned IDs. Both
must be disarmed and read back afterward (D-13).

**`n8n_arming.arm_for_dispatch()` — record-scoped grant, empty-allowlist refusal** (`operator-claude-plugin/scripts/n8n_arming.py:264-363`):
```python
def arm_for_dispatch(workflow_id, record_ids, record_domains, allow_create, config,
                     transport=None):
    """Grant live writes for ONE dispatch, bounded to exactly the records in it.
    ...
    """
    ...
    if not ids and not domains:
        return {
            "outcome": REFUSED,
            "detail": ("refusing to arm: the record allowlist is empty. The deployed "
                       "_writeSafetyAllows() returns false when both allowlists are empty, "
                       "so arming the flag alone would report a successful arming that "
                       "grants nothing at all — worse than refusing, because it reads as "
                       "success."),
        }
    targets = {
        "ALLOW_HUBSPOT_RECORD_WRITES": True,
        "TEST_RECORD_IDS": ",".join(ids),
        "TEST_RECORD_DOMAINS": ",".join(domains),
    }
    ...
    return {
        "outcome": ARMED,
        "workflow_id": workflow_id,
        "prior": dict(prior),
        "observed": result.observed,
        "record_ids": ids,
        "record_domains": domains,
        "reversal": result.reversal,
        "consequence": (
            f"Live writes are enabled on {workflow_id} for exactly "
            f"{len(ids)} record id(s) ... and for nothing else..."),
    }
```

**`n8n_arming.disarm()` — proves closure by independent re-read** (`operator-claude-plugin/scripts/n8n_arming.py:366-415`):
```python
def disarm(workflow_id, config, transport=None):
    """Take live writes away again and PROVE it by an independent re-read.
    Deliberately NOT gated on ALLOW_N8N_ARM. ...
    """
    ...
    if result.verdict != n8n_control.VERIFIED or still_enabled:
        return {
            "outcome": DISARM_FAILED,
            ...
            "detail": (
                f"DISARM FAILED on {workflow_name!r} ({workflow_id}). Observed "
                f"{still_enabled or observed!r} where {expected!r} was required. "
                f"LIVE WRITES MAY STILL BE ENABLED — an admin should open n8n and check "
                f"this workflow directly. Do not treat this run as finished."),
        }
    return {"outcome": DISARMED, "workflow_id": workflow_id,
            "workflow_name": workflow_name, "observed": observed}
```

**`OVERLAY_DISABLED_LITERALS` — the flags at rest** (`operator-claude-plugin/scripts/n8n_arming.py:46-58`):
```python
OVERLAY_DISABLED_LITERALS = {
    "ALLOW_HUBSPOT_RECORD_WRITES": '"false"',
    "ALLOW_HUBSPOT_CREATE": '"false"',
    "ALLOW_HUBSPOT_REVIEW_WRITES": '"false"',
    "TEST_RECORD_IDS": '""',
    "TEST_RECORD_DOMAINS": '""',
}
```

---

### Leg 3: web-research enrichment (D-08) (role: service call, flow: request-response)

**Analog:** `src/web_research.py::claude_web_research`

**`ProviderResult` shape D-09's metadata stamping consumes** — `evidence_urls` /
`evidence_summary` / `confidence`, plus the field-keyed `evidence_by_field` dict
(preferred source for per-field evidence per RESEARCH.md):
```python
def claude_web_research(record: HubSpotRecord) -> ProviderResult:
    if os.getenv("USE_MOCK_WEB_RESEARCH", "true").lower() == "true":
        return mock_claude_web_research(record)
    from anthropic import Anthropic
    client = Anthropic()
    model = os.getenv("ANTHROPIC_RESEARCH_MODEL", "claude-sonnet-5")
    max_uses = int(os.getenv("WEB_RESEARCH_MAX_SEARCHES", "5"))
    props = record.properties
    user_payload = {
        "task": "company_icp_research",
        "company": {"name": props.get("name"), "domain": props.get("domain"),
                    "website": props.get("website"), "country": props.get("country"),
                    "industry": props.get("industry")},
        "required_fields": REQUIRED_FIELDS,
        "return_only_json": True,
    }
    msg = client.messages.create(
        model=model, max_tokens=4096, system=RESEARCH_SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        messages=[{"role": "user", "content": json.dumps(user_payload)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    data = _extract_json(text)
    data.setdefault("provider", "claude_web")
    data.setdefault("object_type", record.object_type)
    return ProviderResult(**data)
```
`REQUIRED_FIELDS` (`src/web_research.py:15-24`) includes all three of D-05's widened
input set (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`) plus
`lv_is_hardware_vendor` (relevant to Simtech LED per D-17) — call once per record, take
what's needed, don't re-derive a narrower prompt.

**D-14 data-honesty rule is already baked into the system prompt**, no new logic needed:
```
"Prefer \"unknown\"/null over guessing — an absent search result is NOT evidence of absence."
```

---

### Leg 4: HubSpot batch writes (role: service client, flow: CRUD)

**Analog:** `src/hubspot_client.py`

```python
def batch_update_companies(updates: list[dict], dry_run=True):
    if len(updates) > 100:
        raise ValueError(...)
    payload = {"inputs": updates}
    if dry_run or not updates:
        print(json.dumps({"dry_run": True, "method": "POST",
                           "url": f"{BASE_URL}/crm/v3/objects/companies/batch/update",
                           "payload": payload}, indent=2, default=str))
        return {"dry_run": True, "payload": payload}
    url = f"{BASE_URL}/crm/v3/objects/companies/batch/update"
    r = requests.post(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def get_record(object_type: str, record_id: str, properties: list[str]):
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
    params = {"properties": ",".join(properties)}
    r = requests.get(url, headers=hs_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def search_records(object_type: str, filters: list[dict], properties: list[str], limit=100):
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/search"
    payload = {"filterGroups": [{"filters": filters}], "properties": properties, "limit": limit}
    r = requests.post(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
```
Use directly (import, don't re-wrap) for all three legs' HubSpot I/O — this is the one
client the whole repo already funnels through, dry-run-safe by default, never prints
headers/token.

---

### Leg 5 (D-18 amendment): the n8n webhook POST per record (role: service call, flow: event-driven)

**No committed caller POSTs the exact HubSpot-shaped property-change event array D-18
specifies** (`objectId`, `objectType: "company"`, `subscriptionType`, `propertyName`,
`occurredAt`). The closest analog for the auth header + armed-gate shape is
`operator-claude-plugin/scripts/enrichment.py::dispatch_enrichment` (POSTs a *different*
envelope — `{"providers": [...], "events": [{"objectId", "objectType"}, ...]}` — to the
same endpoint), paired with `dispatch.py`'s `NotArmedError`/armed-parameter discipline:

```python
# operator-claude-plugin/scripts/enrichment.py:247-278
def enrichment_target(config):
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{ENRICHMENT_PATH}"

def dispatch_enrichment(envelope, armed, config, transport=requests):
    config_gate.require_capability(config, "enrichment")
    if not armed:
        raise NotArmedError(
            "Live writes are off for this conversation — nothing was sent. Say the "
            "arming phrase to turn sending on for this conversation only."
        )
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    try:
        response = transport.post(
            enrichment_target(config), headers=headers, json=envelope,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception:
        ...
```
```python
# operator-claude-plugin/scripts/dispatch.py:10-15, 23-40
"""
The only network call this plugin makes: a multipart POST to the deployed
`hubspot/contact-upload` webhook. `armed` has NO default — a caller that forgets it gets
a TypeError, never a silent send (D-11, D-13, T-23-01).
"""
def dispatch(file_path, armed, config, transport=requests.post):
    ...
    if not armed:
        raise NotArmedError(...)
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    ...
    response = transport(url, headers=headers, files=files, timeout=30)
```
`ENRICHMENT_PATH = "webhook/hubspot/enrichment/event"` (`enrichment.py:31`) is confirmed
identical to D-18's target path. The new script's per-record POST body must instead be a
raw event array matching what Phase 40-03 proved live (per CONTEXT.md D-18):
```json
[{"objectId": "9604732797", "objectType": "company",
  "subscriptionType": "company.propertyChange",
  "propertyName": "lv_country_region_normalized", "occurredAt": 1783316400000}]
```
No existing helper builds this exact array — write it as a small, local function in the
new script (or extend `enrichment.py`'s envelope builder with a new event shape); do not
invent a third webhook client, reuse the `X-Enrichment-Secret` header pattern and
`armed`-no-default discipline shown above.

---

## Shared Patterns

### Dry-run-first, print-exact-payload discipline
**Source:** `src/hubspot_client.py` (every write function), `scripts/backfill_seed_company_scores.py:232-242`
**Apply to:** every write in the new script — batch PATCH, single PATCH (if any),
and the webhook POST leg. Matches D-13's "mandatory disarmed dry-run printing the exact
PATCH payloads before arming."
```python
dry_run = not _writes_allowed()
for update in updates:
    print(json.dumps({"id": update["id"], "properties": update["properties"]}, indent=2))
for chunk in _chunked(updates, BATCH_CHUNK_SIZE):
    batch_update_companies(chunk, dry_run=dry_run)
if dry_run:
    print("DRY RUN complete -- no write performed. Set DRY_RUN=false and "
          "ALLOW_SCORE_BACKFILL=true to arm.")
    return 0
```

### Portal-id pin, never trusted to env alone
**Source:** `scripts/backfill_seed_company_scores.py:56, 158-159, 209-212`
```python
EXPECTED_PORTAL_ID = "22617666"
def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID
...
if not _portal_ok():
    print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
          f"({EXPECTED_PORTAL_ID}). No API call made.")
    return 1
```
**Apply to:** the new script's `main()`, same as every other live-write script in this repo.

### Never-write guard on derived fields (D-07)
**Source:** `scripts/backfill_seed_company_scores.py:19-22, 69-71`
**Apply to:** the new script's docstring and payload-building function — assert (in the
offline test) that no built payload's `properties` dict ever contains
`lv_icp_fit_score`/`lv_icp_tier`/`lv_anti_icp_flag`/`lv_anti_icp_reason` as a key.

### Settle-and-assert wrapper (new logic, no existing analog is sufficient — D-10 gap)
**Source:** `_settle()` above + `tests/scoring_fixtures.py::settle()` (identical
poll shape, returns instead of printing) — neither asserts. The new script must add a
thin wrapper around one of these two that raises on wrong-final-value, not just timeout.

## No Analog Found

| File/Concern | Role | Data Flow | Reason |
|---|---|---|---|
| Raw HubSpot-property-change event-array builder (D-18's exact `objectId`/`objectType`/`subscriptionType`/`propertyName`/`occurredAt` shape) | utility | transform | `operator-claude-plugin/scripts/enrichment.py` builds a related but structurally different envelope for the same endpoint; nothing in the repo currently emits the raw HubSpot-shaped event array. `tests/test_scoring_parity.py::test_veto_clear_after_correction` (lines 441-466, quoted in 47-RESEARCH.md) exercises the OLDER `lv_enrichment_requested` + SJ-3-poller path, not a direct webhook POST — it is not itself a POST-builder analog, only a proof that the derived-field chain is n8n-owned. |
| Per-ID before/after assertion script for exactly these 17 companies | script / test | batch verify | Confirmed absent by RESEARCH.md's "Wave 0 Gaps" — `scripts/run_scoring_parity.py` samples the wider population, not this cohort. New, small script/test needed. |

## Metadata

**Analog search scope:** `scripts/`, `src/`, `operator-claude-plugin/scripts/`, `tests/`
**Files scanned (read in full or targeted):** `scripts/backfill_seed_company_scores.py`,
`scripts/june_run_arm.py`, `operator-claude-plugin/scripts/n8n_arming.py` (targeted),
`src/web_research.py`, `src/hubspot_client.py`, `operator-claude-plugin/scripts/dispatch.py`,
`operator-claude-plugin/scripts/enrichment.py` (targeted), `tests/scoring_fixtures.py` (targeted)
**Pattern extraction date:** 2026-08-11

## PATTERN MAPPING COMPLETE

**Phase:** 47 - veto-remediation
**Files classified:** 1 new script (3 write legs: component-PATCH, n8n-arm/webhook-POST, web-research) + 2 test siblings
**Analogs found:** 6 / 6 (1 leg — the raw event-array webhook POST body — has no exact caller in-repo; closest role-match named and reasons given)

### Coverage
- Files with exact analog: 4 (component-write half, arming ceremony, web-research adapter, HubSpot client)
- Files with role-match analog: 1 (webhook-POST leg — correct auth/armed-gate shape, different envelope)
- Files with no analog: 1 concern (raw event-array builder; new, small, no existing pattern to deviate from)

### Key Patterns Identified
- Every live write in this repo follows dry-run-by-default + explicit two-key arm (`DRY_RUN=false` + a phase-scoped `ALLOW_*` flag) + portal-id pin + print-exact-payload — `backfill_seed_company_scores.py` is the canonical shape to mirror for the new script's direct-PATCH leg.
- Derived scoring fields (`lv_icp_fit_score`/`_tier`/`_flag`/`_reason`) are never written directly by any script in this repo — enforced by comment + an offline test (`tests/test_backfill_seed_company_scores.py`), not by name `T-40-22` (that's a plan-task label, not a test function).
- n8n arming is a record-scoped, independently-re-read grant (`n8n_arming.arm_for_dispatch`/`disarm`) — disarm is deliberately ungated so an operator can always close the window; this asymmetry must be preserved in whatever wraps it for this phase.
- `_settle()`/`settle()` are stability polls, not correctness assertions — D-10's "fail loudly" bar requires new wrapper logic layered on top, for both the pure-HubSpot chain (`lv_icp_tier`) and the n8n-dependent chain (`lv_anti_icp_flag`/`lv_anti_icp_reason`), polled separately with separate timeouts.

### File Created
`.planning/phases/47-veto-remediation/47-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files. Note: this phase's BLOCKING FINDING (D-18/D-19 amendment) means the plan needs a genuinely new webhook-POST-body builder — flagged above under "No Analog Found" — rather than a pure reuse.
