# Phase 39: Path Decision & Fit-Score Verification - Research

**Researched:** 2026-08-06
**Domain:** HubSpot lead-scoring-tool tier availability + recalculation-latency verification (API probing + operator-driven in-portal confirmation)
**Confidence:** MEDIUM — the central negative finding (no public API exposes hub-tier/product entitlements or lets you create/read a score property before one exists) is well-corroborated across independent sources, but is community-forum-sourced [CITED], not HubSpot's own API reference (which does not document the property at all). The tier-availability claim itself (Sales Hub Pro qualifies) is [CITED: knowledge.hubspot.com] from two independent official KB pages, not the single HANDOVER assertion.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** API probe first — Claude probes API-side (score-type property surfaces,
  product/tier introspection, lead-scoring endpoints) before any portal work. Operator does
  the in-portal walkthrough only to confirm what the API can't show (the lead-scoring UI
  itself: Settings → Account & Billing → Products & Add-ons → lead scoring tool).
- **D-02:** Evidence = files + attestation. Screenshots and raw API responses saved under
  `.planning/phases/39-path-decision-fit-score-verification/evidence/`, plus a written
  verification note carrying dates and portal ID (22617666). Must be re-checkable when
  HubSpot changes packaging.
- **D-03:** If verification shows the lead-scoring tool available, run an empirical probe
  before locking the path: configure one trivial criterion, flip a property on a disposable
  `ZZ-SCORING-TEST-DELETE-ME-*` company **3 times** and take the **median** recalculation
  latency, then tear everything down (same disposable-company pattern as HANDOVER §10
  validation — zero real records touched). Median-of-3 guards against a single noisy sample.
- **D-04:** **The gate is "fires automatically on API-written property changes" — not a
  latency number.** Recalc latency on HubSpot's side is a technical, non-configurable async
  queue (no knob, no SLA, no cost lever), and nothing in the system consumes
  `lv_icp_fit_score` within minutes of a write. Probe outcomes: (a) event-driven,
  minutes-scale → proceed lead-scoring tool; (b) event-driven but slow (tens of minutes to
  ~1 hour) → still proceed, latency recorded as evidence; (c) manual-only, does not fire on
  API writes, or hours+ per record → pause and present the measurement to the operator with
  a recommendation. — **Reversibility:** reversible (gate behavior is a written rule; nothing
  binds until 39-DECISION.md is signed)
- **D-05:** Preferred path remains the lead-scoring-tool rebuild (operator decision
  2026-08-06, HANDOVER §5), contingent on verification passing both gates: company fit
  scores available on Sales Hub Pro, AND recalc fires automatically on API-written property
  changes (D-04 outcomes a/b).
- **D-06:** Fallback is pre-committed for the availability gate: if company fit scores are
  unavailable on Sales Hub Pro, the path is fix-the-four-workflow-chain-in-place — no second
  decision round. (Recalc pathology — D-04 outcome (c) — is the one case that pauses for
  operator review instead.) Custom equation properties stay rejected. — **Reversibility:**
  costly — Phase 40 plans, the parity harness shape, and the cleanup scope (Phase 42) are
  all path-shaped; reversing after Phase 40 planning means replanning that phase.
- **D-07:** Decision rationale inherits HANDOVER §5's mechanism comparison (lead-scoring
  tool vs equation properties vs workflow chain) by citation; the decision record adds only
  the new verification + latency evidence. No re-argument from scratch.
- **D-08:** The path decision lands as a standalone
  `.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md`: verdict,
  evidence links (evidence/ dir), latency measurement, rationale citing HANDOVER §5,
  rejected alternatives. ROADMAP.md/STATE.md get a one-line pointer. Phase 40's planner
  reads one file.
- **D-09:** Branch strategy: merge `feat/v0.6-plugin-entrypoint` → `master` FIRST (branch is
  50 commits ahead, unmerged, and carries the v0.7 planning commits d308b08/1bf2fc3/a59b7ee),
  then cut `feat/v0.7-scoring-remediation` from master. Phase 39 execution artifacts land on
  the new v0.7 branch. — **Reversibility:** one-way — a merge to master publishes v0.6
  history to the mainline; undoing it after further commits requires history rewrite.

### Claude's Discretion

- Exact API endpoints/probe order for availability introspection.
- Evidence file naming and note format inside evidence/.
- Probe criterion choice (any trivial rubric line works; tear down after).

### Deferred Ideas (OUT OF SCOPE)

- "Sweep re-notifies a fixed failure until 100 executions displace it" — operator-plugin/sweep
  concern, outside Phase 39 scoring-path scope.
- "Sweep crontab pins a versioned plugin path; update silently stops the sweep" — same; stays
  in backlog.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| DECIDE-01 | Operator has an in-portal verification of company fit-score availability on Sales Hub Pro, and a recorded path decision — fix the four-workflow chain in place vs lead-scoring-tool rebuild — with rationale. Everything downstream is path-shaped by this. | Architecture Patterns 1–2 give the concrete probe-script shapes for the API-side evidence ladder (D-01) and the recalc-latency measurement (D-03); Common Pitfalls 1–3 flag the exact ways a plan could produce a false verdict; Sources/Secondary confirms Sales Hub Pro tier-qualification from two independent official pages, corroborating HANDOVER §5 rather than resting on a single source |

</phase_requirements>

## Summary

This phase does not need a new library, framework, or architecture — it needs a truthful account of what HubSpot's public API can and cannot prove about a UI-only feature, so the plan doesn't waste a wave scripting a probe that can never produce a real verdict. The short version: **the API-side probe (D-01) can only produce negative/supporting evidence, never a positive "yes, available" verdict.** HubSpot's Account Information API (`GET /account-info/v3/details`) returns portal identity and locale fields only (`portalId`, `accountType`, `timeZone`, `companyCurrency`, `uiDomain`, `dataHostingLocation`) — no hub tier, no product/add-on list. HubSpot's own "APIs by tier" reference table contains zero entries for scoring. And the property type the lead-scoring tool creates (`fieldType: calculation_score`) is `hubspotDefined: true` and **read-only for both value and definition** — it cannot be created via `POST /crm/v3/properties/companies` on *any* tier, so a 400 from that probe is portal-tier-agnostic noise, not a "not available here" signal. The only way to get a positive verdict is what CONTEXT.md D-01 already specifies: the operator's in-portal walkthrough (Settings → Account & Billing → Products & Add-ons → the lead scoring tool itself, which only renders builder UI when the feature is entitled).

Two official HubSpot Knowledge Base pages ([CITED], fetched live) independently confirm: *"Companies (Marketing Hub or Sales Hub): create engagement scores, fit scores, or combined engagement and fit scores"* and *"Sales Hub Professional, Enterprise"* is a supported subscription tier for the tool. This corroborates HANDOVER §5's claim from a second source and raises it from single-assertion to two-independent-official-page confidence — still not proof for *this* portal, which is exactly why D-01/D-02 require the in-portal check regardless.

On recalculation latency: HubSpot's own documentation is deliberately vague (*"The property will update continuously when a record meets any of the score criteria"* — no number, no mechanism). Third-party marketing copy claims "real-time," but that is [ASSUMED]-tier marketing language, not a measured SLA — exactly the gap D-03's median-of-3 empirical probe exists to close. One community thread ("Force Mass Recalculation of HubSpot Score") independently corroborates that the criteria-edit bulk recalc and the per-record event-driven rescore are recognized as two distinct behaviors in the wild, which matches the "Specifics" section's framing precisely — no correction needed to the phase's design there.

No new libraries are needed: `requests`, `python-dotenv`, `pydantic` are already installed and already used by every existing probe script this phase should imitate (`scripts/rollback_canary_proof.py`'s two-key gate + portal guard, `scripts/probe_org_type_migration.py`'s disposable-artifact naming discipline). One genuine gap exists: **no script in this repo deletes a company record.** `src/hubspot_client.py` has `get_record`/`patch_record`/`create_record`/`search_records` but no `delete_record` — the ZZ-SCORING-TEST-DELETE-ME-* create/exercise/delete pattern from HANDOVER §10 was done ad hoc in that session, not committed. The D-03 probe script needs a one-line `requests.delete(f"{BASE_URL}/crm/v3/objects/companies/{id}")` addition, following the same `hs_headers()` / no-token-echo convention as everything else in that module.

**Primary recommendation:** Plan Phase 39 as two sequential scripts plus one written record — (1) a disarmed-by-default availability-probe script that runs the negative-evidence ladder (account-info fetch, properties-API introspection, a deliberately-doomed `POST` attempt against `calculation_score`) and prints everything to a JSON evidence file, handing the operator an exact click-path checklist for the one thing only they can confirm; (2) *conditional on the operator confirming availability*, a two-key-gated (`DRY_RUN=false` + a new `ALLOW_HUBSPOT_SCORING_PROBE=true`) disposable-company latency script that creates one `ZZ-SCORING-TEST-DELETE-ME-*` company, flips one property three times with polling, computes median latency via a small pure function (unit-testable without network), and deletes the company — never touching a real record; (3) `39-DECISION.md`, hand-written, citing both evidence artifacts plus HANDOVER §5.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| API-side availability probe (account-info, properties introspection, doomed POST) | API / Backend (Python script → HubSpot REST API) | Database / Storage (HubSpot CRM property schema being read) | Read-only HTTP calls from a local script; no app server or browser involved |
| In-portal lead-scoring-tool confirmation | External SaaS Admin UI (HubSpot Settings) | — | Not automatable per D-01/CONTEXT.md choice ("API probe first... operator does the in-portal walkthrough"); no tier in the standard 5-tier model owns a third-party vendor's own settings UI — it is explicitly out of this repo's architecture |
| Recalc-latency probe (create → flip×3 → poll → median → delete) | API / Backend (Python script) | Database / Storage (HubSpot CRM company object + lead-scoring engine, opaque) | Script drives the HTTP lifecycle; the actual recalculation happens inside HubSpot's own (undocumented) async pipeline, which this repo cannot inspect, only time from the outside |
| Path decision record (`39-DECISION.md`) | Planning artifact (repo docs, no runtime tier) | — | Pure documentation output; consumed by Phase 40's planner, not by any running system |

## Package Legitimacy Audit

**Not applicable — this phase installs no new packages.** All scripting reuses `requests` (2.34.2 installed), `python-dotenv` (1.2.2 installed), `pydantic` (2.13.4 installed) — already pinned in `requirements.txt` and in active use by every existing HubSpot probe script in `scripts/`. No `pip install` is needed for Phase 39.

## Standard Stack

### Core (reused, not newly introduced)
| Library | Version (installed) | Purpose | Why Standard (here) |
|---------|---------|---------|--------------|
| `requests` | 2.34.2 | Direct HTTP calls to HubSpot REST API | Every existing HubSpot probe script (`snapshot_hubspot_schema.py`, `rollback_canary_proof.py`, `probe_org_type_migration.py`) uses raw `requests`, not the `hubspot-api-client` SDK — stay consistent |
| `python-dotenv` | 1.2.2 | Load `.env` in-process, since `.env` is Read/Bash-permission-blocked to this agent session | `scripts/probe_lusha_v3.py`'s documented one-liner pattern: `python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/X.py', run_name='__main__')"` |
| `pydantic` | 2.13.4 | Optional — only if the probe evidence JSON needs schema validation before writing | Already a project dependency; not required for a phase this small (a plain `json.dump` of a dict is sufficient — pulling in a `BaseModel` for a one-shot evidence file is over-scoping) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `requests` calls | `hubspot-api-client` official SDK | Not installed, not used anywhere else in this repo; adding it for one phase breaks the established "raw requests, thin wrapper" convention with zero benefit for ~6 HTTP calls |
| New `delete_record()` in `src/hubspot_client.py` | Inline `requests.delete()` in the probe script only | `src/hubspot_client.py` already holds `get_record`/`patch_record`/`create_record`/`search_records` as the canonical thin wrappers used by `main.py` and multiple scripts — adding `delete_record()` there (not inline) keeps the module the single source of truth, matches the existing 4-function shape, and is one function, not a new abstraction |

**Installation:** None required — all three libraries confirmed already present in `.venv` (`pip show requests python-dotenv pydantic`, run this session).

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────────┐
                     │ Operator (portal walkthrough)│
                     │ Settings → Account & Billing  │
                     │ → Products & Add-ons          │
                     │ → lead scoring tool builder    │
                     └───────────────┬─────────────┘
                                     │ screenshot + written note
                                     ▼
  ┌──────────────┐   negative    ┌─────────────────────┐
  │ availability │───evidence───▶│ evidence/*.json,     │
  │ probe script │   (JSON)      │ evidence/*.png,       │
  │ (disarmed by │               │ 39-VERIFICATION.md    │
  │  default)    │               └──────────┬───────────┘
  └──────┬───────┘                          │
         │ GET account-info/v3/details      │ both feed
         │ GET/POST crm/v3/properties/...   │
         ▼                                  ▼
  HubSpot REST API (portal 22617666, ap1)  ┌─────────────────────┐
         ▲                                 │  gate check (D-04): │
         │ POST/PATCH/DELETE               │  available? recalc  │
         │ crm/v3/objects/companies         │  auto-fires on API  │
         │                                  │  writes?             │
  ┌──────┴────────┐                        └──────────┬───────────┘
  │ recalc-latency │  create → flip×3 → poll →         │ verdict
  │ probe script   │  median → delete (204)             ▼
  │ (two-key gated,│─────────────────────────▶ ┌──────────────────┐
  │  disposable    │                            │ 39-DECISION.md    │
  │  ZZ-SCORING-   │                            │ (path verdict +   │
  │  TEST-DELETE-  │                            │  rationale citing │
  │  ME-* company) │                            │  HANDOVER §5)      │
  └────────────────┘                            └────────┬───────────┘
                                                           │ one-line pointer
                                                           ▼
                                                  ROADMAP.md / STATE.md
                                                  → gates Phase 40 planning
```

### Recommended Project Structure
```
.planning/phases/39-path-decision-fit-score-verification/
├── 39-CONTEXT.md              # already exists — user decisions
├── 39-RESEARCH.md             # this file
├── 39-PLAN-*.md                # planner output
├── 39-DECISION.md              # D-08: standalone decision record, path verdict
└── evidence/
    ├── account_info_response.json      # GET /account-info/v3/details raw response
    ├── properties_probe_response.json  # GET+POST /crm/v3/properties/companies attempts
    ├── portal_walkthrough_<date>.png   # operator screenshot(s) of the lead-scoring UI
    ├── recalc_latency_probe.json       # D-03 median-of-3 measurement, raw timestamps
    └── VERIFICATION-NOTE.md            # D-02: written attestation, dated, portal ID stamped

scripts/
├── probe_scoring_tool_availability.py   # new — disarmed-by-default negative-evidence ladder
└── probe_scoring_recalc_latency.py      # new — two-key-gated disposable-company latency probe

src/hubspot_client.py
└── delete_record(object_type, record_id, dry_run=True)   # new — the one missing primitive
```

### Pattern 1: Disarmed-by-default negative-evidence ladder (availability probe)
**What:** A read-only script that (a) calls `GET /account-info/v3/details` and records that it contains no tier/product field, (b) calls `GET /crm/v3/properties/companies` and records whether any `fieldType: calculation_score` property already exists, (c) attempts (with the standard two-key write gate) `POST /crm/v3/properties/companies` with a `calculation_score`-shaped body against a disposable property name and records the exact error — expected to fail on every tier, which is itself the evidence that this probe is inconclusive for availability and the portal check is load-bearing.
**When to use:** Before the operator's portal walkthrough, so the operator's evidence-gathering time isn't spent re-deriving what the API already rules out.
**Example:**
```python
# Source: pattern from scripts/snapshot_hubspot_schema.py + scripts/rollback_canary_proof.py
# (this repo, read this session) — no external doc has this exact shape since
# HubSpot's own API reference does not document calculation_score at all.
import os, requests
from datetime import datetime, timezone

BASE_URL = "https://api.hubapi.com"

def probe_account_info(headers):
    r = requests.get(f"{BASE_URL}/account-info/v3/details", headers=headers, timeout=30)
    body = r.json() if r.ok else {"status": r.status_code, "text": r.text}
    return {
        "endpoint": "GET /account-info/v3/details",
        "status": r.status_code,
        "body": body,
        "has_tier_field": any(
            k in body for k in ("hubTier", "subscriptionTier", "productTier")
        ) if isinstance(body, dict) else False,
        "note": "Expected: no tier/product field present (schema is portalId/"
                "accountType/timeZone/companyCurrency/uiDomain/dataHostingLocation).",
    }

def probe_existing_score_properties(headers):
    r = requests.get(f"{BASE_URL}/crm/v3/properties/companies", headers=headers, timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])
    score_props = [p for p in results if p.get("fieldType") == "calculation_score"]
    return {
        "endpoint": "GET /crm/v3/properties/companies",
        "total_properties": len(results),
        "calculation_score_properties_found": score_props,
        "note": "Empty list is inconclusive — score properties only appear here "
                "AFTER the operator builds one in-portal; absence does not mean "
                "unavailable.",
    }
```
**Doomed-POST note:** Do NOT actually attempt to `POST` a `calculation_score` fieldType property against the live portal as part of this evidence ladder unless the plan explicitly wants the literal 400 body captured — the community-sourced finding (`hubspotDefined: true`, read-only for value AND definition) already establishes this call fails identically on every tier ([CITED: community.hubspot.com, two independent threads]). If the plan wants the raw error text as an evidence artifact anyway, gate it behind the same two-key `DRY_RUN=false` / `ALLOW_HUBSPOT_PROPERTY_WRITES=true` convention as every other write attempt in this repo, and label the resulting evidence file explicitly as "expected-to-fail, non-discriminating" so a future reader doesn't mistake a 400 here for a tier-negative signal.

### Pattern 2: Two-key-gated disposable-company latency probe (median-of-3)
**What:** Mirrors `scripts/rollback_canary_proof.py`'s shape exactly: `_has_credentials()` → skip to exit 0; `_portal_ok()` → refuse with no call; `_writes_allowed()` (two-key: `DRY_RUN=false` AND a new env flag) → skip otherwise. Then: `create_record("companies", {...ZZ-SCORING-TEST-DELETE-ME-<ts>...})`, three loops of (flip one property → poll the score property on an interval until it changes or a timeout elapses → record elapsed seconds), compute median via a pure function, then `delete_record("companies", id)` and assert 204.
**When to use:** Only after D-01/D-02 confirm the lead-scoring tool is available in-portal AND the operator has built one trivial scoring criterion there (this script cannot create the scoring rule itself — score-property creation is UI-only, per the properties-API research finding above).
**Example:**
```python
# Source: this repo, read this session (scripts/rollback_canary_proof.py two-key gate +
# portal guard idiom; scripts/snapshot_hubspot_schema.py's dry-run-by-default shape).
# The median function below is new for Phase 39 — no prior art in this repo computes a
# median; kept as a pure function specifically so it is unit-testable without a live probe.
import statistics

def median_latency(samples: list[float]) -> float:
    """samples: elapsed seconds from property-write to observed score change.
    Pure function — the ONE thing in this probe worth a unit test without network."""
    if not samples:
        raise ValueError("no samples")
    return statistics.median(samples)

# Self-check (ponytail: the smallest runnable check for non-trivial logic)
def _demo():
    assert median_latency([10, 12, 14]) == 12
    assert median_latency([5, 100, 6]) == 6  # median resists the one noisy sample
    print("median_latency: PASS")

if __name__ == "__main__":
    _demo()
```

### Anti-Patterns to Avoid
- **Treating a `POST /crm/v3/properties/companies` 400 as a tier-negative signal:** it is read-only/`hubspotDefined` on every tier — the failure is portal-agnostic. Document it as inconclusive, not as evidence of unavailability.
- **Trying to script the operator's portal check with a browser-automation tool:** CONTEXT.md D-01 already explicitly rejected "Claude-in-Chrome assisted" in favor of the operator driving it themselves. Do not reintroduce browser automation into the plan for this step.
- **Building a `create_score_property()` API wrapper:** the properties API cannot create this fieldType on any tier (community-corroborated, two independent threads) — this would be dead code from the moment it's written.
- **Skipping the pure-function extraction for median math:** inlining the median calculation into the live-polling loop makes it untestable without a live disposable-company run; five lines of extraction buys a real unit test.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client with retries/auth for HubSpot | A new requests wrapper class | `src/hubspot_client.py`'s existing `get_record`/`patch_record`/`create_record`/`search_records` functions, add one `delete_record` alongside them | Established four-function shape used across `main.py` and every other probe script; a fifth function that matches the existing signature style is a one-line-diff, not a new pattern |
| Two-key write-safety gating | A new environment-flag scheme, a new "are we live" check | The exact `_has_credentials()` / `_portal_ok()` / `_writes_allowed()` triad from `scripts/rollback_canary_proof.py` and `scripts/probe_org_type_migration.py` | Already the repo convention for exactly this kind of "one disposable live artifact, gated two ways" script; deviating invents a second safety idiom for no reason |
| Loading `.env` inside a permission-blocked session | A custom secrets-loading shim | The documented `python -c "from dotenv import load_dotenv; load_dotenv(); ...runpy..."` one-liner from `scripts/probe_lusha_v3.py`'s own docstring | Already solved, already documented, already the pattern the executor phase will copy verbatim per CONTEXT.md's "Claude's Discretion" note |
| Median-of-N latency math | A rolling-stats library, a pandas dependency | `statistics.median()` (stdlib) | Three numbers; stdlib is not just sufficient, it is the only correct-weight choice |

**Key insight:** Nothing in this phase needs a new abstraction. Every write-capable action this phase performs (create one disposable company, patch it three times, delete it) already has a near-identical, tested precedent in this repo's `scripts/` directory from Phase 15/20/21/22 work. The only genuinely new code is: one `delete_record()` function, one `median_latency()` pure function, and the orchestration gluing polling to the two-key gate.

## Common Pitfalls

### Pitfall 1: Mistaking API silence for a "no"
**What goes wrong:** The properties-API probe returns no `calculation_score` properties and the 400-on-create attempt "fails," and someone concludes the lead-scoring tool is unavailable on this tier.
**Why it happens:** Both signals look tier-negative on the surface, but both are actually portal-tier-agnostic (score properties are always UI-only-creatable; the properties list is always empty until the operator builds one).
**How to avoid:** The plan must make the in-portal walkthrough the *only* authoritative positive-or-negative source for availability, exactly as CONTEXT.md D-01/D-02 already specify — the API probe's job is documented supporting/negative evidence, never the verdict itself.
**Warning signs:** A draft `39-DECISION.md` that cites only API evidence for the availability gate, with no portal screenshot referenced.

### Pitfall 2: Running the recalc-latency probe before a scoring criterion exists in-portal
**What goes wrong:** The probe flips a property on a disposable company, polls a score property that doesn't exist yet (because no lead-scoring model has been built), and either 404s or reads a perpetual `None` — producing a false "manual-only, never fires" verdict (D-04 outcome c), which would incorrectly trigger the operator-pause path.
**Why it happens:** Score properties, per the research above, only materialize after the operator builds the scoring model in the UI — the API-first probe sequence in D-01 can run entirely before that happens, but the D-03 latency probe explicitly cannot.
**How to avoid:** Sequence the plan so D-03's script hard-fails (not silently proceeds) if it cannot find any `calculation_score`-typed property on the companies object before starting the flip loop — a precondition check, not an assumption.
**Warning signs:** A latency-probe script with no pre-flight "does a score property exist" assertion.

### Pitfall 3: Confusing the two documented HubSpot latencies
**What goes wrong:** The probe measures one flip, gets a fast number, and the plan reports "recalc is fast" without distinguishing whether that number is the per-record event-driven rescore (what D-04's gate cares about) or is contaminated by a criteria-edit bulk-recalc window (which the "Force Mass Recalculation" community thread and the CONTEXT.md Specifics section both flag as a separate, much slower, one-time phenomenon).
**Why it happens:** Both are described in vague, unified "continuously updated" language by HubSpot's own docs — there is no vendor-provided vocabulary that forces the distinction.
**How to avoid:** The probe script must build the trivial criterion (or confirm it's already built and stable, not freshly edited) *before* the timing loop starts, and the loop must only ever flip the disposable company's property — never touch the scoring criteria definition itself during the timed window. `39-DECISION.md` should state explicitly which of the two latencies was measured.
**Warning signs:** A single latency number in the decision record with no note on which type of recalc it reflects.

## Code Examples

### Existing repo pattern: two-key write gate (verbatim precedent)
```python
# Source: scripts/rollback_canary_proof.py (this repo, read this session), lines 42-53
def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))

def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID

def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow
```
Reuse this triad verbatim for both new probe scripts, swapping the second flag name to something scoped to this phase (e.g. `ALLOW_HUBSPOT_SCORING_PROBE`) so it cannot accidentally be armed by a flag left on from an unrelated migration script.

### Existing repo pattern: `.env` load without reading the file directly
```bash
# Source: scripts/probe_lusha_v3.py (this repo, read this session), docstring lines 37-39
ALLOW_HUBSPOT_SCORING_PROBE=true DRY_RUN=false .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; \
   runpy.run_path('scripts/probe_scoring_recalc_latency.py', run_name='__main__')"
```
The executor hands the operator this exact `!`-prefixed command per the `.env`-permission-blocked convention noted in CONTEXT.md's environment notes and the user's own memory (`env-file-permission-blocked.md`).

### HubSpot account-info response shape (what NOT to look for)
```json
// Source: HubSpot developer docs (account-info/v3/details reference), corroborated via
// WebSearch this session — [CITED: developers.hubspot.com]. No tier/product field exists.
{
  "portalId": 22617666,
  "accountType": "STANDARD",
  "timeZone": "Australia/Sydney",
  "companyCurrency": "AUD",
  "additionalCurrencies": [],
  "utcOffset": "+10:00",
  "utcOffsetMilliseconds": 36000000,
  "uiDomain": "app-ap1.hubspot.com",
  "dataHostingLocation": "ap1"
}
```
Useful for confirming portal identity (`portalId`, `uiDomain`, `dataHostingLocation`) matches expectations before any write — but contributes nothing to the availability question. The `uiDomain`/`dataHostingLocation` fields are a good live cross-check for the ap1/`app-ap1.hubspot.com` gotcha already documented in HANDOVER §9.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Legacy contact-only `calculation_score` "HubSpot Score" / predictive lead score | Modern lead-scoring tool: fit + engagement + combined scores, on contacts, companies (Marketing Hub or Sales Hub), and deals (combined only) | Legacy score stopped updating 2025-08-31, removed 2026-01-10 (HANDOVER §5, this repo's own prior investigation) | The property internal name / mechanics changed; any pre-2026 blog post or Stack-style answer about "HubSpot Score" describes a retired mechanism, not what Phase 39 is verifying |

**Deprecated/outdated:**
- Legacy predictive `HubSpot Score` (`calculation_score` fieldType as historically documented in the 2022-era community thread) — sunset per this repo's own HANDOVER §5/§9 finding, not something to rebuild against.
- Custom equation properties as the ICP-scoring mechanism — viable but explicitly rejected twice now: once in HANDOVER §5 (not RevOps-editable, formula-fragile) and again in CONTEXT.md D-06 (fallback is fix-the-existing-workflow-chain, not equation properties — this supersedes HANDOVER §8's "if unavailable, fall back to custom equation properties" wording).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Third-party marketing copy claiming lead-scoring recalculation is "real-time" | Summary, Pitfall 3 | If wrong, no plan harm — D-03's empirical median-of-3 probe exists precisely because this claim is not trusted; the assumption is flagged only so nobody accidentally elevates the marketing claim to a documented fact in `39-DECISION.md` |
| A2 | `POST /crm/v3/properties/companies` with a `calculation_score`-shaped body returns 400 on every tier (not just observed by two community posters, never independently reproduced against portal 22617666 in this research session) | Pattern 1, Anti-Patterns | If this repo's own probe run gets a different result (e.g., a 201, or a differently-shaped error), the "portal-agnostic, non-discriminating" framing is wrong and the probe might actually carry signal — the plan should have the probe script capture and print the raw response regardless, so this assumption is falsifiable at execute time rather than baked in as an unverified premise |

## Open Questions

1. **Does the lead-scoring tool's UI itself expose any tier-gating message that the operator's screenshot should specifically capture?**
   - What we know: Two KB pages confirm Sales Hub Pro is a supported tier for company scores in general.
   - What's unclear: Whether an *unsupported*-tier portal shows an upsell/paywall screen (capturable as clean negative evidence) or simply hides the entry point entirely (in which case the operator's evidence is "I could not find X," a harder thing to screenshot convincingly).
   - Recommendation: Have the plan instruct the operator to screenshot whatever they see at Settings → Account & Billing → Products & Add-ons *and* the outcome of attempting to reach the lead-scoring builder specifically, whichever of the two outcomes (paywall vs. absent) actually occurs — both are valid evidence, but the plan shouldn't assume which shape it'll be.

2. **Is `automation` scope (already granted per CONTEXT.md code_context) sufficient for anything the availability probe needs, or is it purely a Phase 40 concern?**
   - What we know: The `automation` scope was granted specifically to read the four existing workflow definitions (HANDOVER §10 amendment), unrelated to the lead-scoring tool.
   - What's unclear: Whether the private app's current scope set includes `crm.objects.companies.write` (needed for the D-03 disposable-company create/patch/delete) — this repo's `.env` is permission-blocked so the scope list can't be directly confirmed this session.
   - Recommendation: The plan's first probe-script run should fail loudly and specifically (403 with scope name in the body) rather than assume write scopes are present; HubSpot 403 bodies name the missing scope, which is sufficient for the operator to grant it before re-running.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `requests` | HTTP calls to HubSpot API | ✓ | 2.34.2 | — |
| `python-dotenv` | Loading `.env` in-process (permission-blocked to direct Read/Bash) | ✓ | 1.2.2 | — |
| `pydantic` | Optional evidence-schema validation | ✓ | 2.13.4 | Plain `json.dump` if not used |
| `.venv` (project virtualenv) | Running any probe script | ✓ | Python present, `import requests, dotenv, pydantic` succeeds | — |
| `HUBSPOT_PRIVATE_APP_TOKEN` | Every live API call | Unconfirmed this session (`.env` Read/Bash-blocked) | — | Scripts already `_has_credentials()`-skip to exit 0 if absent — no plan risk, just means live runs are operator-invoked |
| `automation` scope on private app | Not required for Phase 39 (Phase 40/workflow reads only) | Granted per CONTEXT.md | — | — |
| `crm.objects.companies.write` scope | D-03 disposable-company create/patch/delete | Unconfirmed this session | — | 403 response names the missing scope; operator grants it in the private app's scope settings before re-running |
| git branch state | D-09 branch strategy (merge v0.6 → master, cut v0.7 branch) | Confirmed this session: `feat/v0.6-plugin-entrypoint` still current, unmerged, `master`/`worktree-claude-plugin-entrypoint` remotes exist | — | Plan must sequence the merge-then-cut as its own early task per D-09, before any Phase 39 execution commit lands |

**Missing dependencies with no fallback:** None — every dependency this phase touches either already exists in the repo or degrades to a safe no-op (credential-absent skip).

**Missing dependencies with fallback:** `crm.objects.companies.write` scope (fallback: operator grants scope on 403); `HUBSPOT_PRIVATE_APP_TOKEN` presence (fallback: script skip-to-exit-0, all probing becomes an operator-driven live run instead of an agent-driven one).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2.0+ (already project standard) |
| Config file | none dedicated — repo convention is `tests/test_*.py`, discovered by default pytest rootdir behavior (confirmed pattern from `tests/test_verify_live_write_safety.py` referenced in `scripts/verify_live_write_safety.py`'s own docstring) |
| Quick run command | `.venv/bin/python -m pytest tests/test_scoring_probe_helpers.py -x` |
| Full suite command | `.venv/bin/python -m pytest` (per this repo's documented convention — see `test-suite-run-commands.md` memory entry: dir-form is broken on this Python version, always invoke via `-m pytest`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|--------------|
| DECIDE-01 | `median_latency()` computes the median of 3 elapsed-time samples, resisting a single noisy outlier | unit | `.venv/bin/python -m pytest tests/test_scoring_probe_helpers.py::test_median_latency -x` | ❌ Wave 0 |
| DECIDE-01 | Availability-probe script correctly classifies its own account-info response as "no tier field present" (regression-proofs the negative-evidence claim against a fixture, not a live call) | unit | `.venv/bin/python -m pytest tests/test_scoring_probe_helpers.py::test_account_info_has_no_tier_field -x` | ❌ Wave 0 |
| DECIDE-01 | Full live probe ladder + disposable-company recalc probe | manual/live (operator-invoked, credentialed) | `ALLOW_HUBSPOT_SCORING_PROBE=true DRY_RUN=false .venv/bin/python -c "..."` (see Code Examples) | N/A — inherently live, cannot be a CI-run automated test; this is expected and matches every prior live-probe script in this repo (none are pytest-covered for their live path, only for pure-function helpers) |

### Sampling Rate
- **Per task commit:** run the unit tests for whichever pure-function helper (`median_latency`, response classifiers) that task touches.
- **Per wave merge:** full `pytest` suite green (fast — no network tests exist for this phase by design).
- **Phase gate:** the live probe scripts' own printed PASS/FAIL (matching `rollback_canary_proof.py`'s convention) stands in for an automated phase-gate check, since the actual subject under test is a third-party SaaS UI/API this repo does not control — this is consistent with how every prior live-portal-dependent phase in this repo has gated (no prior phase has attempted to CI-test live HubSpot behavior).

### Wave 0 Gaps
- [ ] `tests/test_scoring_probe_helpers.py` — covers `median_latency()` and any pure classification helpers (account-info tier-field check, calculation_score-property detection) extracted from the two new probe scripts
- [ ] `src/hubspot_client.py::delete_record()` — new function needed before the D-03 probe script can be written; no test file needed beyond exercising it through the probe script's own dry-run mode (mirrors `create_record`/`patch_record`, which also have no dedicated unit test in this repo — dry-run-mode manual inspection is the established bar for these thin wrappers)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | This phase authenticates only as the existing private app; no new auth surface introduced |
| V3 Session Management | No | No session state introduced |
| V4 Access Control | Yes | Portal-guard pattern (`_portal_ok()` against `EXPECTED_PORTAL_ID`) — prevents an operator's misconfigured `.env` from silently mutating the wrong HubSpot portal; reuse verbatim from `scripts/rollback_canary_proof.py` |
| V5 Input Validation | Yes | Probe scripts must validate `TEST_COMPANY_IDS`-style allowlists / disposable-name prefixes before any write, exactly as `scripts/probe_org_type_migration.py` already does (`_test_company_ok()`) — no free-text company ID should ever reach a live PATCH/DELETE call |
| V6 Cryptography | No | No cryptographic operations in this phase; token handling is pass-through only |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Private app token echoed in logs/evidence JSON | Information Disclosure | Never construct or print the token — established repo-wide convention (`hs_headers()` builds the header inline; every probe script's docstring states "the secret value is NEVER printed"). Evidence JSON files must be reviewed before commit to confirm no `Authorization` header value leaked into a captured request/response dump. |
| Wrong-portal write (token valid for a different HubSpot portal than 22617666) | Tampering | `_portal_ok()` two-key portal guard, refuse-with-no-call, reused verbatim |
| Disposable test company mistaken for / colliding with a real record | Tampering / Repudiation | `ZZ-SCORING-TEST-DELETE-ME-*` naming prefix (established HANDOVER §10 convention) + explicit delete-and-204-assert step, never leaving a disposable artifact live after the probe completes |
| Live write happening from a disarmed default (accidental double-negative in gate logic) | Tampering | Two-key gate (`DRY_RUN=false` AND a phase-scoped `ALLOW_*` flag) — a single flag flip alone is insufficient by design, matching every prior write-capable script in this repo |

## Sources

### Primary (HIGH confidence)
- This repo, read this session: `HANDOVER-2026-08-06-icp-scoring.md` §5, §8, §9, §10 — mechanism comparison, blocking open items, portal gotchas, validated F1–F10 defects
- This repo, read this session: `.planning/phases/39-path-decision-fit-score-verification/39-CONTEXT.md` — locked decisions D-01 through D-09
- This repo, read this session: `scripts/rollback_canary_proof.py`, `scripts/probe_org_type_migration.py`, `scripts/snapshot_hubspot_schema.py`, `scripts/probe_lusha_v3.py`, `src/hubspot_client.py` — reusable patterns, verbatim quotes above
- `.venv/bin/pip show requests python-dotenv pydantic` — run this session, confirmed installed versions

### Secondary (MEDIUM confidence — [CITED], official HubSpot docs, fetched live this session)
- https://knowledge.hubspot.com/scoring/understand-the-lead-scoring-tool — "Sales Hub Professional, Enterprise" tier support; "Fit scores (contacts and companies only)"; vague "update continuously" recalc language
- https://knowledge.hubspot.com/crm-setup/set-up-score-properties-to-qualify-leads — "Companies (Marketing Hub or Sales Hub): create engagement scores, fit scores, or combined engagement and fit scores"
- https://developers.hubspot.com/docs/developer-tooling/platform/apis-by-tier — zero entries for "scoring"/"score"; Properties API listed as free-tier/universal
- Account-info API response shape (`portalId`, `accountType`, `timeZone`, `companyCurrency`, `uiDomain`, `dataHostingLocation`) — corroborated via search of the HubSpot developer reference page (direct fetch was blocked by an auth redirect this session; schema corroborated via WebSearch summarizing the same official page)

### Tertiary (LOW confidence — community-forum-sourced, WebSearch only, not independently reproduced against portal 22617666 this session)
- HubSpot Community: "Undocumented contact fieldType - calculation_score" — `hubspotDefined: true`, read-only value+definition
- HubSpot Community: "Hubspot API: Create Score-Properties" / "Possible to create a Score or Calculation custom property via API?" — corroborating "score properties must be created in-app, no documented API creation path"
- HubSpot Community: "Force Mass Recalculation of Hubspot Score" — corroborates the two-distinct-latency framing (criteria-edit bulk vs per-record event-driven) already present in CONTEXT.md's Specifics section
- Third-party blogs/marketing pages (Hubjoy, Weidert, Default, Marketveep, etc.) — "real-time" recalculation claims, explicitly flagged [ASSUMED]/not to be trusted as an SLA (see Assumptions Log A1)

## Metadata

**Confidence breakdown:**
- API-probe-is-inconclusive-for-availability finding: MEDIUM — corroborated by two independent community threads plus the absence of any scoring entry in HubSpot's own tier-availability reference, but not independently reproduced live against portal 22617666 in this research session (that reproduction is the executor's job, per CONTEXT.md's "Do NOT write to HubSpot" instruction for this research pass)
- Sales Hub Pro tier-qualification claim: MEDIUM-HIGH — two independent official KB pages, consistent with each other and with HANDOVER §5's prior finding
- Recalc-latency vagueness / two-latency-types finding: MEDIUM — HubSpot's own docs are genuinely silent on a number; the two-latency distinction is corroborated by one community thread, not an official source; this is precisely why D-03's empirical probe is designed as it is, not a gap this research needed to close further
- Reusable script patterns (two-key gate, dotenv-load one-liner, ZZ-SCORING naming): HIGH — read directly from this repo's own committed source this session

**Research date:** 2026-08-06
**Valid until:** 2026-09-05 (30 days — HubSpot packaging/API surfaces can change without notice; re-verify tier-availability claims if this phase is replanned significantly after that window, and re-run the account-info/properties probes fresh regardless since they are cheap and portal-specific)
